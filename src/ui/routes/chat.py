"""
Chat API routes for the UI.

Provides endpoints for:
- Sending chat messages to the LLM
- Streaming responses
"""

import os
import sys
import asyncio
import re
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from flask import Blueprint, jsonify, request

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Apply nest_asyncio for nested event loop support (like main.py)
import nest_asyncio
nest_asyncio.apply()

# Persistent event loop for async operations
# This ensures MCP client subprocess handles stay on the same loop
_async_loop = None
_loop_thread = None
_loop_lock = threading.Lock()


def _get_or_create_event_loop():
    """Get or create a persistent event loop running in a background thread."""
    global _async_loop, _loop_thread
    
    with _loop_lock:
        if _async_loop is None or not _async_loop.is_running():
            # Create a new event loop
            _async_loop = asyncio.new_event_loop()
            
            # Start the loop in a background thread
            def run_loop():
                asyncio.set_event_loop(_async_loop)
                _async_loop.run_forever()
            
            _loop_thread = threading.Thread(target=run_loop, daemon=True)
            _loop_thread.start()
            
            # Wait for the loop to start
            import time
            for _ in range(50):  # Wait up to 0.5 seconds
                if _async_loop.is_running():
                    break
                time.sleep(0.01)
            
            # Verify the loop actually started
            if not _async_loop.is_running():
                raise RuntimeError("Failed to start event loop within timeout")
    
    return _async_loop


def run_async(coro):
    """
    Run an async coroutine on the persistent event loop.
    This ensures all MCP client operations use the same loop,
    avoiding 'Future attached to a different loop' errors.
    """
    loop = _get_or_create_event_loop()
    
    # Submit the coroutine to the loop and wait for result
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    
    # Wait for the result with a timeout
    try:
        return future.result(timeout=120)  # 2 minute timeout for long operations
    except Exception as e:
        raise e

from src.sentry_config import capture_exception
from src.session.manager import SessionManager
from src.session.title_generator import SessionTitleGenerator
from src.mcp import MCPClient
from src.file_completer import extract_at_context
from src.utils.file_action_handler import build_system_messages, detect_file_actions
from src.utils.code_handlers import handle_file_modifications

chat_bp = Blueprint('chat', __name__)

# In-memory session store for UI sessions (fallback when Redis is unavailable)
# This stores completed/saved sessions that can be listed in the UI
_ui_sessions_store: Dict[str, Dict[str, Any]] = {}


def get_ui_sessions() -> List[Dict[str, Any]]:
    """Get all UI sessions from the in-memory store."""
    return list(_ui_sessions_store.values())


def save_ui_session(session_data: Dict[str, Any]) -> None:
    """Save a session to the in-memory UI store."""
    session_id = session_data.get('session_id')
    if session_id:
        _ui_sessions_store[session_id] = session_data


def delete_ui_session(session_id: str) -> bool:
    """Delete a session from the in-memory UI store."""
    if session_id in _ui_sessions_store:
        del _ui_sessions_store[session_id]
        return True
    return False


def clear_ui_sessions() -> int:
    """Clear all sessions from the in-memory UI store."""
    count = len(_ui_sessions_store)
    _ui_sessions_store.clear()
    return count


def _create_session_manager() -> SessionManager:
    """Create a SessionManager with title generation enabled."""
    from src.config.manager import ConfigManager
    
    config = ConfigManager()
    
    # Create title generator using local tinyollama (lightweight model for title generation)
    title_generator = None
    if config.has_tinyollama_config():
        title_generator = SessionTitleGenerator(
            ollama_url=config.get_tinyollama_url(),  # Use LOCAL tinyollama
            model=config.get_tinyollama_model(),
            timeout=config.get_tinyollama_timeout()
        )
    
    # Create session manager with title generator
    session_manager = SessionManager(title_generator=title_generator)
    return session_manager


# Reuse a single session manager instance for the UI server so
# session state persists across requests.
_session_manager = _create_session_manager()


def get_session_manager() -> SessionManager:
    """Return the shared SessionManager instance."""
    return _session_manager


# Cache for tool categories from MCP
_tool_categories_cache: Dict[str, List[str]] = {}
_tool_categories_loaded = False


def _load_tool_categories_from_mcp(mcp_client: 'MCPClient') -> Dict[str, List[str]]:
    """
    Load tool categories from the MCP's get_tool_metadata tool.
    Falls back to hardcoded defaults if MCP call fails.
    """
    global _tool_categories_cache, _tool_categories_loaded
    
    if _tool_categories_loaded:
        return _tool_categories_cache
    
    # Default hardcoded values as fallback
    defaults = {
        'code_generation': ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code', 'run_python_code', 'run_r_code'],
        'valid_coding': [
            'run_python_code', 'run_r_code', 'detect_code',
            'write_python_code', 'write_r_code',
            'edit_python_code', 'edit_r_code',
            'add_file_context', 'add_directory_context',
            'verify_file_modifications'
        ],
        'meta': ['retrieve_all_tools', 'roll_the_dice', 'spin_the_roulette']
    }
    
    try:
        # Call the MCP tool to get metadata
        result = mcp_client.call_tool('get_tool_metadata', {'list_categories': True})
        
        if result and isinstance(result, str):
            data = json.loads(result)
            if data.get('status') == 'success' and 'categories' in data:
                # Now fetch the full tools for each category
                for category_name in data['categories'].keys():
                    cat_result = mcp_client.call_tool('get_tool_metadata', {'category': category_name})
                    if cat_result and isinstance(cat_result, str):
                        cat_data = json.loads(cat_result)
                        if cat_data.get('status') == 'success' and 'tools' in cat_data:
                            _tool_categories_cache[category_name] = cat_data['tools']
                
                _tool_categories_loaded = True
                return _tool_categories_cache
    except Exception as e:
        # Log but don't fail - fall back to defaults
        print(f"[DEBUG] Failed to load tool categories from MCP: {e}")
    
    # Fall back to defaults
    _tool_categories_cache = defaults
    _tool_categories_loaded = True
    return _tool_categories_cache


def get_tool_category(category_name: str, mcp_client: 'MCPClient' = None) -> List[str]:
    """
    Get tools for a specific category, loading from MCP if needed.
    """
    global _tool_categories_cache, _tool_categories_loaded
    
    if not _tool_categories_loaded and mcp_client:
        _load_tool_categories_from_mcp(mcp_client)
    
    return _tool_categories_cache.get(category_name, [])


def _save_current_session_to_ui_store() -> None:
    """Save the current session to the UI in-memory store."""
    session_manager = get_session_manager()
    if not session_manager.is_active():
        return
    
    session_data = {
        'session_id': session_manager.get_session_id(),
        'title': session_manager.get_title() or 'Untitled Session',
        'working_dir': session_manager.get_working_dir(),
        'start_time': session_manager.session_start_time.isoformat() if session_manager.session_start_time else datetime.now().isoformat(),
        'num_interactions': len(session_manager.session_history),
        'history': session_manager.session_history.copy(),
        'saved_at': datetime.now().isoformat()
    }
    save_ui_session(session_data)


@chat_bp.route('/models', methods=['GET'])
def get_available_models():
    """
    Get list of registered models from ModelRegistry for chat.
    Only returns general and coder models (not embedding models).
    Also returns the currently active model.
    """
    try:
        from src.model_registry import ModelRegistry

        registry = ModelRegistry()

        # Get general and coder models only (not embedding)
        general_models = registry.list_models('general')
        coder_models = registry.list_models('coder')

        # Combine and extract unique model names
        all_models = general_models + coder_models
        model_names = list(set(m.model_name for m in all_models if m.model_name))

        # Get active general model to set as default
        active_model = registry.get_active_model('general')
        active_model_name = active_model.model_name if active_model else None

        return jsonify({
            'status': 'success',
            'models': model_names,
            'active_model': active_model_name
        })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch models: {str(e)}',
            'models': [],
            'active_model': None
        }), 500


def get_ollama_client():
    """Get or create an Ollama client instance using active general model."""
    from src.ollama_client.client import OllamaClient
    from src.config.manager import ConfigManager
    from src.model_registry import ModelRegistry

    config = ConfigManager()
    registry = ModelRegistry()

    # Try to get active general model from registry
    general_model = registry.get_active_model('general')

    if general_model:
        # Use registered general model
        host = general_model.url
        model = general_model.model_name
        timeout = general_model.timeout
    else:
        # Fallback to config (for backward compatibility)
        host = config.get_ollama_url()
        model = config.get_ollama_model()
        timeout = config.get_ollama_timeout()

    return OllamaClient(host=host, model=model, timeout=timeout), config


def get_mcp_client():
    """Get or create an MCP client instance for UI file operations."""
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    system_mcps_dir = project_root / 'system_mcps'
    postgres_url = os.getenv('POSTGRES_API_URL', 'http://localhost:15000')

    return MCPClient(
        system_mcps_dir=system_mcps_dir,
        postgres_url=postgres_url,
        verbose=False
    )


@chat_bp.route('/send', methods=['GET', 'POST'])
def send_message():
    """
    Send a message to the LLM and get a response.
    
    Request body:
        message: The user message
        model: Optional model name (defaults to config model)
        file_contents: Optional dict of file contents (for UI file uploads)
    """
    # Handle GET requests with a clear error message
    if request.method == 'GET':
        return jsonify({
            'status': 'error',
            'message': 'This endpoint requires a POST request with a JSON body containing a "message" field.'
        }), 405
    
    session_manager = get_session_manager()

    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body required'
            }), 400
        
        message = data.get('message')
        if not message:
            return jsonify({
                'status': 'error',
                'message': 'Message is required'
            }), 400
        
        model = data.get('model')
        file_contents = data.get('file_contents', {})
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        
        # Ensure there is an active session before sending the message
        if not session_manager.is_active():
            session_manager.start_session(working_dir=working_dir)
        
        # Auto-detect make commands from normal prompts if .makemap exists
        # Skip if input looks like a command (starts with common command prefixes)
        if not message.startswith('/') and not message.startswith(':'):
            makemap_file_path = os.path.join(working_dir, '.makemap')
            if os.path.exists(makemap_file_path):
                from src.cli.commands.make import parse_makemap_file, find_all_matching_commands
                makemap_commands = parse_makemap_file(makemap_file_path)
                if makemap_commands:
                    matches = find_all_matching_commands(message, makemap_commands, min_score=8)
                    if matches:
                        # Treat as a /make command - redirect to handle_make_command
                        return handle_make_command(message)
        
        # Get client and config
        client, config = get_ollama_client()
        
        # Use provided model or default from config
        if not model:
            model = config.get_ollama_model()
        
        # Extract @ prefixed file/directory paths for file action detection
        at_context = extract_at_context(message, working_dir)

        # Build injected context parts from file_contents (UI uploads)
        injected_context_parts = []
        if file_contents:
            for filename, content in file_contents.items():
                injected_context_parts.append(f"File: {filename}\n```\n{content}\n```")

        # Load contents of @ referenced files (matching CLI behavior)
        # This ensures the LLM has full context when editing files
        for file_path in at_context['files']:
            try:
                # Load file content by reading from filesystem
                full_path = os.path.join(working_dir, file_path) if not os.path.isabs(file_path) else file_path
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                        injected_context_parts.append(f"File: {file_path}\n```\n{file_content}\n```")
            except Exception as e:
                # Log but don't fail - continue with other files
                capture_exception(e)

        # Also load contents of @ referenced directories (matching CLI behavior)
        for dir_path in at_context.get('directories', []):
            try:
                # Resolve full directory path
                full_dir_path = os.path.join(working_dir, dir_path) if not os.path.isabs(dir_path) else dir_path
                if os.path.exists(full_dir_path) and os.path.isdir(full_dir_path):
                    for root, _, files in os.walk(full_dir_path):
                        for fname in files:
                            file_path = os.path.join(root, fname)
                            # Compute relative path for display
                            rel_path = os.path.relpath(file_path, working_dir)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    file_content = f.read()
                                    injected_context_parts.append(f"File: {rel_path}\n```\n{file_content}\n```")
                            except Exception as e:
                                capture_exception(e)
            except Exception as e:
                capture_exception(e)

        # Build system messages using shared file action handler
        system_messages = build_system_messages(
            at_context=at_context,
            user_input=message,
            config=config,
            injected_context_parts=injected_context_parts,
            target_file=None,  # UI doesn't use target_file feature
            session_context=None,  # Could add session context here if needed
            guidance=None  # Could add RAG guidance here if needed
        )
        
        # Build the message with system messages
        messages = []
        
        # Add system messages first
        if system_messages:
            messages.extend(system_messages)
        
        # Add user message
        messages.append({"role": "user", "content": message})
        
        # Call Ollama API - use the underlying client directly for non-streaming
        try:
            response = client.client.chat(
                model=model,
                messages=messages,
                stream=False
            )
            
            # Extract the response content
            if isinstance(response, dict):
                content = response.get('message', {}).get('content', '')
            else:
                # Handle ollama library response object
                content = response.message.content if hasattr(response, 'message') else str(response)
            
            session_manager.add_interaction(message, content, {
                'model': model,
                'source': 'ui'
            })
            
            # Try to save to Redis, but always save to UI store as fallback
            try:
                session_manager.save_to_redis()
            except Exception as redis_err:
                capture_exception(redis_err)  # Log but don't fail - we have UI store
            
            # Always save to UI in-memory store for display
            _save_current_session_to_ui_store()
            
            # Check for file modification actions and process them
            action_result = detect_file_actions(message, at_context, config)

            if action_result['has_action'] and (action_result['files_to_modify'] or action_result['files_to_create']):
                # Execute file modifications using MCP
                try:
                    # Execute file modifications asynchronously
                    mod_result = run_async(_handle_file_modifications_async(
                        response_text=content,
                        files_to_modify=action_result['files_to_modify'],
                        files_to_create=action_result['files_to_create'],
                        working_dir=working_dir
                    ))

                    modification_info = {
                        'detected': True,
                        'files_to_modify': action_result['files_to_modify'],
                        'files_to_create': action_result['files_to_create'],
                        'modified': mod_result.get('modified', []),
                        'created': mod_result.get('created', []),
                        'errors': mod_result.get('errors', [])
                    }

                    return jsonify({
                        'status': 'success',
                        'response': content,
                        'model': model,
                        'session_active': session_manager.is_active(),
                        'session_id': session_manager.get_session_id(),
                        'file_modifications': modification_info
                    })
                except Exception as mod_error:
                    capture_exception(mod_error)
                    # Continue without file modifications if there's an error
            
            return jsonify({
                'status': 'success',
                'response': content,
                'model': model,
                'session_active': session_manager.is_active(),
                'session_id': session_manager.get_session_id()
            })
            
        except Exception as e:
            capture_exception(e)
            return jsonify({
                'status': 'error',
                'message': f'LLM Error: {str(e)}'
            }), 500
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@chat_bp.route('/command', methods=['POST'])
def execute_command():
    """
    Execute a CLI command.
    
    Request body:
        command: The command to execute (e.g., /session start, /models, /code ...)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body required'
            }), 400
        
        command = data.get('command', '').strip()
        if not command:
            return jsonify({
                'status': 'error',
                'message': 'Command is required'
            }), 400
        
        # Support : shortcut for /make command
        # e.g., ": run tests" becomes "/make run tests"
        if command.startswith(':') and len(command) > 1:
            make_prompt = command[1:].strip()
            if make_prompt:
                command = f'/make {make_prompt}'
        
        # Normalize command (remove leading /)
        cmd = command.lower()
        if cmd.startswith('/'):
            cmd = cmd[1:]
        
        # Handle different commands
        if cmd == 'session start':
            return handle_session_start()
        elif cmd == 'session end':
            return handle_session_end()
        elif cmd == 'session info':
            return handle_session_info()
        elif cmd in ['session list', 'sessions list', 'sessions']:
            return handle_session_list()
        elif cmd.startswith('session restore '):
            session_id = cmd[16:].strip()
            return handle_session_restore(session_id)
        elif cmd.startswith('session delete '):
            session_id = cmd[15:].strip()
            return handle_session_delete(session_id)
        elif cmd == 'models':
            return handle_models()
        elif cmd == 'mcps':
            return handle_mcps()
        elif cmd.startswith('code '):
            code_prompt = command[5:].strip() if command.startswith('/') else command[4:].strip()
            return handle_code_command(code_prompt)
        elif cmd == 'repomap create':
            return handle_repomap_create()
        elif cmd == 'repomap load':
            return handle_repomap_load()
        elif cmd == 'repomap update':
            return handle_repomap_update()
        elif cmd.startswith('datamap create'):
            # Parse flags from the command
            args_str = cmd[14:].strip() if len(cmd) > 14 else ''
            return handle_datamap_create(args_str)
        elif cmd == 'datamap load':
            return handle_datamap_load()
        elif cmd == 'datamap update' or cmd.startswith('datamap update '):
            args_str = cmd[15:].strip() if len(cmd) > 15 else ''
            return handle_datamap_update(args_str)
        elif cmd == 'make map generate':
            return handle_makemap_generate()
        elif cmd == 'make map load':
            return handle_makemap_load()
        elif cmd == 'make map update':
            return handle_makemap_update()
        elif cmd.startswith('make ') and not cmd.startswith('make map'):
            make_prompt = command[5:].strip() if command.startswith('/') else command[4:].strip()
            return handle_make_command(make_prompt)
        elif cmd == 'clear':
            return handle_clear()
        elif cmd == 'context show':
            return handle_context_show_ui()
        elif cmd == 'context clear':
            return handle_context_clear_ui()
        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown command: {command}\n\nType `/help` or click the Help button for available commands.'
            }), 400
            
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


def handle_session_start():
    """Start a new session."""
    session_manager = get_session_manager()
    
    if session_manager.is_active():
        return jsonify({
            'status': 'error',
            'message': '⚠️ Session already active. End current session first.',
            'session_active': True,
            'session_id': session_manager.get_session_id()
        })
    
    working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
    session_manager.start_session(working_dir=working_dir)
    session_id = session_manager.get_session_id()
    
    return jsonify({
        'status': 'success',
        'response': f'📝 **Session started!**\n\nSession ID: `{session_id[:16]}...`',
        'session_active': True,
        'session_id': session_id
    })


def handle_session_end():
    """End current session."""
    session_manager = get_session_manager()
    
    if not session_manager.is_active():
        return jsonify({
            'status': 'error',
            'message': '⚠️ No active session to end.',
            'session_active': False
        })
    
    # Check if session has interactions before ending
    num_interactions = len(session_manager.session_history)
    
    # Save before ending if there are interactions
    if num_interactions > 0:
        try:
            session_manager.save_to_redis()
        except Exception as e:
            capture_exception(e)
    
    summary = session_manager.end_session()
    
    return jsonify({
        'status': 'success',
        'response': f'✅ **Session ended!**\n\n{summary if summary else "Session saved."}',
        'session_active': False
    })


def _call_llm_for_map(prompt: str, system_msg: str) -> str:
    """
    Helper function to call LLM for generating repository/data maps.
    
    Args:
        prompt: The user prompt to send to the LLM
        system_msg: The system message describing the assistant's role
        
    Returns:
        The LLM response content as a string
        
    Raises:
        Exception: If the LLM call fails
    """
    client, config = get_ollama_client()
    
    messages = [
        {'role': 'system', 'content': system_msg},
        {'role': 'user', 'content': prompt}
    ]
    
    response = client.chat(messages=messages, stream=False)
    
    # Extract response content
    if hasattr(response, 'message'):
        return response.message.content
    elif isinstance(response, dict):
        return response.get('message', {}).get('content', '')
    else:
        return str(response)


def handle_clear():
    """Clear chat and start a new session."""
    session_manager = get_session_manager()
    
    # Always end the current session (save first if it has interactions)
    if session_manager.is_active():
        num_interactions = len(session_manager.session_history)
        if num_interactions > 0:
            try:
                session_manager.save_to_redis()
            except Exception as e:
                capture_exception(e)
        # Force end the session
        session_manager.end_session()
    
    # Start a fresh session
    working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
    session_manager.start_session(working_dir=working_dir)
    new_session_id = session_manager.get_session_id()
    
    return jsonify({
        'status': 'success',
        'response': '🗑️ Chat cleared. New session started.',
        'session_active': True,
        'session_id': new_session_id
    })


def handle_context_show_ui():
    """Show current context in UI."""
    session_manager = get_session_manager()
    
    response = "📋 **Current Context**\n\n"
    
    # Session info
    if session_manager.is_active():
        info = session_manager.get_session_info()
        response += "**Session:** Active\n"
        response += f"- ID: `{info['session_id'][:16]}...`\n"
        if info.get('title'):
            response += f"- Title: {info['title']}\n"
        response += f"- Duration: {int(info['duration_seconds'])}s\n"
        response += f"- Interactions: {info['num_interactions']}\n"
        
        if session_manager.session_working_dir:
            response += f"- Working Dir: `{session_manager.session_working_dir}`\n"
        
        # Session metadata
        if session_manager.session_metadata:
            response += "\n**Session Metadata:**\n"
            for key, value in session_manager.session_metadata.items():
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                elif isinstance(value, (list, dict)):
                    value = f"{type(value).__name__} with {len(value)} items"
                response += f"- {key}: {value}\n"
        
        # Session history summary
        if session_manager.session_history:
            response += f"\n**Session History:** {len(session_manager.session_history)} interactions\n"
            for i, interaction in enumerate(session_manager.session_history[-3:], 1):
                prompt = interaction.get('prompt', '')[:50]
                if len(interaction.get('prompt', '')) > 50:
                    prompt += "..."
                response += f"{i}. {prompt}\n"
            if len(session_manager.session_history) > 3:
                response += f"... and {len(session_manager.session_history) - 3} more\n"
    else:
        response += "**Session:** Not active\n"
    
    return jsonify({
        'status': 'success',
        'response': response,
        'session_active': session_manager.is_active(),
        'session_id': session_manager.get_session_id() if session_manager.is_active() else None
    })


def handle_context_clear_ui():
    """Clear context in UI (keeps session active)."""
    session_manager = get_session_manager()
    
    # Clear session context but keep session active
    if session_manager.is_active():
        session_manager.session_history.clear()
        session_manager.session_metadata.clear()
        response = "🗑️ Context cleared (session still active)."
    else:
        response = "🗑️ Context cleared."
    
    return jsonify({
        'status': 'success',
        'response': response,
        'session_active': session_manager.is_active(),
        'session_id': session_manager.get_session_id() if session_manager.is_active() else None
    })


def handle_repomap_create():
    """Create a repository map."""
    from src.utils.repomap import collect_source_files, generate_repomap_prompt
    from src.utils.tree import generate_tree
    
    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        
        # Collect source files
        source_files = collect_source_files(working_dir)
        
        if not source_files:
            return jsonify({
                'status': 'error',
                'message': '❌ No source code files found in the working directory.'
            }), 400
        
        # Generate directory tree
        tree_output = generate_tree(working_dir, max_depth=5)
        
        # Generate the LLM prompt
        repomap_prompt = generate_repomap_prompt(source_files, tree_output=tree_output)
        
        # Call LLM to generate the repomap
        try:
            full_response = _call_llm_for_map(
                prompt=repomap_prompt,
                system_msg='You are a helpful assistant that creates repository maps.'
            )
        except Exception as llm_error:
            capture_exception(llm_error)
            return jsonify({
                'status': 'error',
                'message': f'❌ Error calling LLM: {str(llm_error)}'
            }), 500
        
        # Prepend the tree to the repomap output
        repomap_content = f"""# Repository Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""
        
        # Write the repomap to file
        repomap_path = os.path.join(working_dir, '.repomap')
        with open(repomap_path, 'w', encoding='utf-8') as f:
            f.write(repomap_content)
        
        return jsonify({
            'status': 'success',
            'response': f'''✅ **Repository map created successfully!**

📄 Saved to: `{repomap_path}`

**Summary:**
- Found **{len(source_files)}** source files
- Generated directory tree
- Analyzed codebase structure

Use `/repomap load` to load it into context.'''
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error creating repository map: {str(e)}'
        }), 500


def handle_repomap_load():
    """Load an existing repomap into context."""
    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        repomap_path = os.path.join(working_dir, '.repomap')
        
        if not os.path.exists(repomap_path):
            return jsonify({
                'status': 'error',
                'message': "❌ No `.repomap` file found.\n\nUse `/repomap create` to generate a repository map first."
            }), 400
        
        # Read the repomap file directly
        with open(repomap_path, 'r', encoding='utf-8') as f:
            context = f.read()
        
        if context:
            # Preview the first part
            preview = context[:500] + '...' if len(context) > 500 else context
            return jsonify({
                'status': 'success',
                'response': f'''✅ **Repository map loaded!**

The repository context is now available for the current conversation.

**Preview:**
```
{preview}
```'''
            })
        else:
            return jsonify({
                'status': 'error',
                'message': "❌ Repository map file is empty."
            }), 400
            
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error loading repository map: {str(e)}'
        }), 500


def handle_repomap_update():
    """Update an existing repomap."""
    from src.utils.repomap import collect_source_files, generate_repomap_update_prompt
    from src.utils.tree import generate_tree
    
    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        repomap_path = os.path.join(working_dir, '.repomap')
        
        if not os.path.exists(repomap_path):
            return jsonify({
                'status': 'error',
                'message': "❌ No `.repomap` file found.\n\nUse `/repomap create` to generate a repository map first."
            }), 400
        
        # Load existing repomap by reading the file directly
        with open(repomap_path, 'r', encoding='utf-8') as f:
            existing_repomap = f.read()
        
        # Collect source files
        source_files = collect_source_files(working_dir)
        
        if not source_files:
            return jsonify({
                'status': 'error',
                'message': '❌ No source code files found in the working directory.'
            }), 400
        
        # Generate directory tree
        tree_output = generate_tree(working_dir, max_depth=5)
        
        # Generate the update prompt
        update_prompt = generate_repomap_update_prompt(source_files, existing_repomap, tree_output=tree_output)
        
        # Call LLM to generate the updated repomap
        try:
            full_response = _call_llm_for_map(
                prompt=update_prompt,
                system_msg='You are a helpful assistant that updates repository maps.'
            )
        except Exception as llm_error:
            capture_exception(llm_error)
            return jsonify({
                'status': 'error',
                'message': f'❌ Error calling LLM: {str(llm_error)}'
            }), 500
        
        # Prepend the tree to the repomap output
        repomap_content = f"""# Repository Map (Updated)

## Directory Tree

```
{tree_output}
```

{full_response}
"""
        
        # Write the repomap to file
        with open(repomap_path, 'w', encoding='utf-8') as f:
            f.write(repomap_content)
        
        return jsonify({
            'status': 'success',
            'response': f'''✅ **Repository map updated successfully!**

📄 Saved to: `{repomap_path}`

**Summary:**
- Found **{len(source_files)}** source files
- Updated directory tree
- Refreshed codebase analysis'''
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error updating repository map: {str(e)}'
        }), 500


def handle_datamap_create(args_str: str = ''):
    """Create a data map."""
    from src.utils.datamap import collect_data_files, generate_datamap_prompt
    
    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        
        # Collect data files (flags like --with-files, --files-only reserved for future use)
        data_sources = collect_data_files(working_dir)
        
        if not data_sources:
            return jsonify({
                'status': 'error',
                'message': '❌ No data files found in the working directory.\n\nSupported formats: CSV, JSON, Excel, Parquet, Feather'
            }), 400
        
        # Generate the LLM prompt
        datamap_prompt = generate_datamap_prompt(data_sources)
        
        # Call LLM to generate the datamap
        try:
            full_response = _call_llm_for_map(
                prompt=datamap_prompt,
                system_msg='You are a helpful assistant that creates data maps describing data files and their schemas.'
            )
        except Exception as llm_error:
            capture_exception(llm_error)
            return jsonify({
                'status': 'error',
                'message': f'❌ Error calling LLM: {str(llm_error)}'
            }), 500
        
        # Create datamap content
        datamap_content = f"""# Data Map

{full_response}
"""
        
        # Write the datamap to file
        datamap_path = os.path.join(working_dir, '.datamap')
        with open(datamap_path, 'w', encoding='utf-8') as f:
            f.write(datamap_content)
        
        # Show summary of file types
        extensions = {}
        for source in data_sources:
            ext = source.get('extension', 'unknown')
            extensions[ext] = extensions.get(ext, 0) + 1
        
        ext_summary = '\n'.join([f"  - {ext}: {count} file(s)" for ext, count in extensions.items()])
        
        return jsonify({
            'status': 'success',
            'response': f'''✅ **Data map created successfully!**

📄 Saved to: `{datamap_path}`

**Summary:**
- Found **{len(data_sources)}** data files
{ext_summary}

Use `/datamap load` to load it into context.'''
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error creating data map: {str(e)}'
        }), 500


def handle_datamap_load():
    """Load an existing datamap into context."""
    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        datamap_path = os.path.join(working_dir, '.datamap')
        
        if not os.path.exists(datamap_path):
            return jsonify({
                'status': 'error',
                'message': "❌ No `.datamap` file found.\n\nUse `/datamap create` to generate a data map first."
            }), 400
        
        # Read the datamap file directly
        with open(datamap_path, 'r', encoding='utf-8') as f:
            context = f.read()
        
        if context:
            # Preview the first part
            preview = context[:500] + '...' if len(context) > 500 else context
            return jsonify({
                'status': 'success',
                'response': f'''✅ **Data map loaded!**

The data context is now available for the current conversation.

**Preview:**
```
{preview}
```'''
            })
        else:
            return jsonify({
                'status': 'error',
                'message': "❌ Data map file is empty."
            }), 400
            
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error loading data map: {str(e)}'
        }), 500


def handle_datamap_update(args_str: str = ''):
    """Update an existing datamap."""
    from src.utils.datamap import collect_data_files, generate_datamap_update_prompt
    
    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        datamap_path = os.path.join(working_dir, '.datamap')
        
        if not os.path.exists(datamap_path):
            return jsonify({
                'status': 'error',
                'message': "❌ No `.datamap` file found.\n\nUse `/datamap create` to generate a data map first."
            }), 400
        
        # Load existing datamap by reading the file directly
        with open(datamap_path, 'r', encoding='utf-8') as f:
            existing_datamap = f.read()
        
        # Collect data files
        data_sources = collect_data_files(working_dir)
        
        if not data_sources:
            return jsonify({
                'status': 'error',
                'message': '❌ No data files found in the working directory.'
            }), 400
        
        # Generate the update prompt
        update_prompt = generate_datamap_update_prompt(data_sources, existing_datamap)
        
        # Call LLM to generate the updated datamap
        try:
            full_response = _call_llm_for_map(
                prompt=update_prompt,
                system_msg='You are a helpful assistant that updates data maps.'
            )
        except Exception as llm_error:
            capture_exception(llm_error)
            return jsonify({
                'status': 'error',
                'message': f'❌ Error calling LLM: {str(llm_error)}'
            }), 500
        
        # Create updated datamap content
        datamap_content = f"""# Data Map (Updated)

{full_response}
"""
        
        # Write the datamap to file
        with open(datamap_path, 'w', encoding='utf-8') as f:
            f.write(datamap_content)
        
        return jsonify({
            'status': 'success',
            'response': f'''✅ **Data map updated successfully!**

📄 Saved to: `{datamap_path}`

**Summary:**
- Found **{len(data_sources)}** data files
- Refreshed data analysis'''
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error updating data map: {str(e)}'
        }), 500


def handle_makemap_generate():
    """Generate a makemap from the Makefile."""
    from src.utils.makemap import find_makefile, parse_makefile, generate_makemap_prompt
    from src.utils.tree import generate_tree

    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())

        # Check if Makefile exists
        makefile_path = find_makefile(working_dir)
        if not makefile_path:
            return jsonify({
                'status': 'error',
                'message': f"❌ No Makefile found in: `{working_dir}`\n\nThis command requires a Makefile to exist in the working directory."
            }), 400

        # Parse the Makefile
        parsed = parse_makefile(str(makefile_path))

        if 'error' in parsed:
            return jsonify({
                'status': 'error',
                'message': f"❌ Error parsing Makefile: {parsed['error']}"
            }), 400

        targets = parsed.get('targets', [])
        variables = parsed.get('variables', {})

        # Generate directory tree
        tree_output = generate_tree(working_dir, max_depth=3)

        # Generate the LLM prompt
        makemap_prompt = generate_makemap_prompt(parsed, tree_output=tree_output)

        # Call LLM
        try:
            full_response = _call_llm_for_map(
                prompt=makemap_prompt,
                system_msg='You are a build system expert. Create comprehensive documentation for Makefiles.'
            )
        except Exception as llm_error:
            capture_exception(llm_error)
            return jsonify({
                'status': 'error',
                'message': f'❌ Error calling LLM: {str(llm_error)}'
            }), 500

        # Create makemap content with tree
        makemap_content = f"""# Make Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""

        # Write the makemap to file
        makemap_file_path = os.path.join(working_dir, '.makemap')
        with open(makemap_file_path, 'w', encoding='utf-8') as f:
            f.write(makemap_content)

        return jsonify({
            'status': 'success',
            'response': f'''✅ **Make map created successfully!**

📄 Saved to: `{makemap_file_path}`

**Summary:**
- Found **{len(targets)}** targets
- Found **{len(variables)}** variables'''
        })

    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error creating make map: {str(e)}'
        }), 500


def handle_makemap_load():
    """Load an existing makemap into context."""
    from src.utils.makemap import load_makemap_to_context

    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        makemap_path = os.path.join(working_dir, '.makemap')

        if not os.path.exists(makemap_path):
            return jsonify({
                'status': 'error',
                'message': "❌ No `.makemap` file found.\n\nUse `/make map generate` to create a make map first."
            }), 400

        # Get session ID if active
        session_manager = get_session_manager()
        session_id = session_manager.get_session_id() if session_manager.is_active() else None

        # Get MCP client
        mcp_client = get_mcp_client()

        # Load the makemap into context
        result = run_async(load_makemap_to_context(
            mcp_client,
            '.makemap',
            working_dir,
            session_id
        ))

        if result.get('status') == 'success':
            content_size = result.get('content_size', 0)
            session_info = f"Session: `{session_id[:16]}...`" if session_id else "Session: temporary (start a session for persistence)"
            return jsonify({
                'status': 'success',
                'response': f'''✅ **Make map loaded into context!**

📄 File: `{makemap_path}`
📊 Size: **{content_size:,}** bytes
{session_info}'''
            })
        else:
            error_msg = result.get('message', 'Unknown error')
            return jsonify({
                'status': 'error',
                'message': f'⚠️ Warning: {error_msg}'
            }), 400

    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error loading make map: {str(e)}'
        }), 500


def handle_makemap_update():
    """Update an existing makemap with new targets."""
    from src.utils.makemap import find_makefile, parse_makefile, generate_makemap_update_prompt
    import re as re_module

    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        makemap_path = os.path.join(working_dir, '.makemap')

        if not os.path.exists(makemap_path):
            return jsonify({
                'status': 'error',
                'message': "❌ No `.makemap` file found.\n\nUse `/make map generate` to create a make map first."
            }), 400

        # Check if Makefile exists
        makefile_path = find_makefile(working_dir)
        if not makefile_path:
            return jsonify({
                'status': 'error',
                'message': f"❌ No Makefile found in: `{working_dir}`"
            }), 400

        # Read existing makemap
        with open(makemap_path, 'r', encoding='utf-8') as f:
            existing_makemap = f.read()

        # Parse the Makefile
        parsed = parse_makefile(str(makefile_path))

        if 'error' in parsed:
            return jsonify({
                'status': 'error',
                'message': f"❌ Error parsing Makefile: {parsed['error']}"
            }), 400

        all_targets = parsed.get('targets', [])

        # Find existing target names in the makemap
        existing_target_names = set(re_module.findall(r'^### (\w+)', existing_makemap, re_module.MULTILINE))

        # Filter to new targets only
        new_targets = [t for t in all_targets if t['name'] not in existing_target_names]

        if not new_targets:
            return jsonify({
                'status': 'success',
                'response': '✅ Make map is already up to date. No new targets found.'
            })

        # Generate the update prompt
        update_prompt = generate_makemap_update_prompt(new_targets, existing_makemap)

        # Call LLM
        try:
            full_response = _call_llm_for_map(
                prompt=update_prompt,
                system_msg='You are a build system expert. Update the make map with new targets.'
            )
        except Exception as llm_error:
            capture_exception(llm_error)
            return jsonify({
                'status': 'error',
                'message': f'❌ Error calling LLM: {str(llm_error)}'
            }), 500

        # Write the updated makemap
        with open(makemap_path, 'w', encoding='utf-8') as f:
            f.write(full_response)

        new_target_names = [t['name'] for t in new_targets]
        return jsonify({
            'status': 'success',
            'response': f'''✅ **Make map updated successfully!**

📄 Updated: `{makemap_path}`

**New targets added ({len(new_targets)}):**
{chr(10).join(f"• `{name}`" for name in new_target_names[:10])}'''
        })

    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error updating make map: {str(e)}'
        }), 500


def handle_make_command(prompt: str):
    """Handle /make <prompt> command - execute make commands using natural language.
    
    Uses .makemap for command matching similar to CLI implementation.
    """
    from src.utils.makemap import find_makefile, parse_makefile, get_target_names, generate_makemap_prompt, load_makemap_to_context
    from src.cli.commands.make import parse_makemap_file, find_matching_command, find_all_matching_commands
    import json as json_module
    import subprocess
    import re

    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())

        if not prompt:
            return jsonify({
                'status': 'error',
                'message': '''❌ **Usage:** `/make <prompt>`

**Examples:**
• `/make run the tests`
• `/make build the project`
• `/make clean up`'''
            }), 400

        # Check if Makefile exists
        makefile_path = find_makefile(working_dir)
        if not makefile_path:
            return jsonify({
                'status': 'error',
                'message': f"❌ No Makefile found in: `{working_dir}`\n\nThis command requires a Makefile to exist in the working directory."
            }), 400

        # Check for .makemap file
        makemap_file_path = os.path.join(working_dir, '.makemap')
        
        if not os.path.exists(makemap_file_path):
            return jsonify({
                'status': 'error',
                'message': f"❌ No `.makemap` file found.\n\nUse `/make map generate` to create a make map first."
            }), 400
        
        # Parse .makemap to get commands
        commands = parse_makemap_file(makemap_file_path)
        
        if not commands:
            return jsonify({
                'status': 'error',
                'message': "❌ No commands found in `.makemap`. Try regenerating with `/make map generate`."
            }), 400
        
        # Find all matching commands with min_score=8
        all_matches = find_all_matching_commands(prompt, commands, min_score=8)
        
        if not all_matches:
            # Fallback: try lower threshold
            all_matches = find_all_matching_commands(prompt, commands, min_score=3)
            
        if not all_matches:
            # Show available commands
            available = '\n'.join([f"• `{cmd['command']}` - {cmd['description']}" for cmd in commands[:10]])
            return jsonify({
                'status': 'error',
                'message': f"❌ No matching command found for: **{prompt}**\n\n**Available commands:**\n{available}"
            }), 400
        
        # Determine if single match or tourniquet (multiple matches)
        results = []
        
        if len(all_matches) > 1 and all_matches[0]['score'] - all_matches[1]['score'] < 5:
            # Multiple close matches - run all of them (tourniquet)
            matches_text = '\n'.join([f"• `{m['command']}` (score: {m['score']}) - {m['description']}" for m in all_matches[:5]])
            response_parts = [f"🎰 **Tourniquet: Found {len(all_matches)} matching commands**\n\n{matches_text}\n"]
            
            for i, match in enumerate(all_matches[:5], 1):  # Limit to 5 commands
                command = match['command']
                description = match['description']
                
                response_parts.append(f"\n---\n### Step {i}: `{command}`\n*{description}*\n")
                
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        cwd=working_dir,
                        capture_output=True,
                        text=True,
                        timeout=60  # Shorter timeout for UI
                    )
                    
                    stdout = result.stdout or ''
                    stderr = result.stderr or ''
                    exit_code = result.returncode
                    
                    # Strip ANSI codes
                    ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    stdout = ansi_pattern.sub('', stdout)
                    stderr = ansi_pattern.sub('', stderr)
                    
                    if exit_code == 0:
                        response_parts.append(f"✅ **Success** (exit: {exit_code})\n")
                    else:
                        response_parts.append(f"❌ **Failed** (exit: {exit_code})\n")
                    
                    if stdout:
                        output_preview = stdout[:1000]
                        if len(stdout) > 1000:
                            output_preview += '\n... (truncated)'
                        response_parts.append(f"```\n{output_preview}\n```\n")
                    
                    if stderr and exit_code != 0:
                        error_preview = stderr[:500]
                        response_parts.append(f"**Errors:**\n```\n{error_preview}\n```\n")
                    
                    results.append({'command': command, 'exit_code': exit_code})
                    
                except subprocess.TimeoutExpired:
                    response_parts.append(f"⚠️ **Timed out** after 60s\n")
                    results.append({'command': command, 'exit_code': -1})
                except Exception as e:
                    response_parts.append(f"❌ **Error:** {str(e)}\n")
                    results.append({'command': command, 'exit_code': -1})
            
            # Summary
            successful = sum(1 for r in results if r['exit_code'] == 0)
            response_parts.append(f"\n---\n### Summary\n✅ Successful: {successful}/{len(results)}")
            
            return jsonify({
                'status': 'success' if successful == len(results) else 'partial',
                'response': ''.join(response_parts)
            })
        
        else:
            # Single match - execute directly
            match = all_matches[0]
            command = match['command']
            description = match['description']
            
            # Check if this is a streaming command (logs, tail, watch, etc.)
            streaming_keywords = {'logs', 'tail', 'watch', 'follow'}
            is_streaming = any(kw in command.lower() for kw in streaming_keywords)
            
            # Use shorter timeout for streaming commands in UI
            timeout = 10 if is_streaming else 300
            
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=working_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                stdout = result.stdout or ''
                stderr = result.stderr or ''
                exit_code = result.returncode
                
                # Strip ANSI codes
                ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                stdout = ansi_pattern.sub('', stdout)
                stderr = ansi_pattern.sub('', stderr)
                
                if exit_code == 0:
                    response = f'''✅ **Make command succeeded!**

📌 **Matched:** `{command}`
📝 *{description}*
📊 Exit code: **{exit_code}**'''
                else:
                    response = f'''❌ **Make command failed!**

📌 **Matched:** `{command}`
📝 *{description}*
📊 Exit code: **{exit_code}**'''
                
                if stdout:
                    output_preview = stdout[:2000]
                    if len(stdout) > 2000:
                        output_preview += '\n... (truncated)'
                    response += f'''

**Output:**
```
{output_preview}
```'''
                
                if stderr:
                    error_preview = stderr[:1000]
                    if len(stderr) > 1000:
                        error_preview += '\n... (truncated)'
                    response += f'''

**Errors:**
```
{error_preview}
```'''
                
                return jsonify({
                    'status': 'success' if exit_code == 0 else 'error',
                    'response': response
                })
                
            except subprocess.TimeoutExpired as e:
                # For streaming commands, timeout is expected - show partial output
                if is_streaming:
                    stdout_partial = ''
                    stderr_partial = ''
                    if hasattr(e, 'stdout') and e.stdout:
                        stdout_partial = e.stdout.decode('utf-8', errors='replace') if isinstance(e.stdout, bytes) else str(e.stdout)
                    if hasattr(e, 'stderr') and e.stderr:
                        stderr_partial = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else str(e.stderr)
                    
                    # Strip ANSI codes
                    ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    stdout_partial = ansi_pattern.sub('', stdout_partial)
                    stderr_partial = ansi_pattern.sub('', stderr_partial)
                    
                    response = f'''✅ **Streaming command captured** (first {timeout}s)

📌 **Matched:** `{command}`
📝 *{description}*
⏱️ *Streaming command - showing first {timeout} seconds of output*'''
                    
                    if stdout_partial:
                        output_preview = stdout_partial[:2000]
                        if len(stdout_partial) > 2000:
                            output_preview += '\n... (truncated)'
                        response += f'''

**Output:**
```
{output_preview}
```'''
                    else:
                        response += '\n\n*(no output captured)*'
                    
                    return jsonify({
                        'status': 'success',
                        'response': response
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': f'⚠️ Command `{command}` timed out after 5 minutes'
                    }), 504

    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Error executing make command: {str(e)}'
        }), 500


def handle_session_info():
    """Get session info."""
    session_manager = get_session_manager()
    info = session_manager.get_session_info()
    
    if not info:
        return jsonify({
            'status': 'success',
            'response': '⚠️ No active session.',
            'session_active': False
        })
    
    return jsonify({
        'status': 'success',
        'response': f'''📊 **Session Info:**

• **Session ID:** `{info['session_id'][:16]}...`
• **Duration:** {int(info['duration_seconds'])}s
• **Interactions:** {info['num_interactions']}''',
        'session_active': True,
        'session_id': info['session_id']
    })


def handle_session_list():
    """List saved sessions."""
    session_manager = get_session_manager()
    sessions = session_manager.list_saved_sessions()
    
    if not sessions:
        return jsonify({
            'status': 'success',
            'response': '📋 **Saved Sessions:**\n\n_No saved sessions found._'
        })
    
    session_list = []
    for sess in sessions[:10]:  # Limit to 10
        session_list.append(f"• `{sess['session_id'][:16]}...` - {sess.get('num_interactions', 0)} interactions")
    
    return jsonify({
        'status': 'success',
        'response': f"📋 **Saved Sessions:**\n\n" + "\n".join(session_list)
    })


def handle_session_restore(session_id):
    """Restore a session."""
    session_manager = get_session_manager()
    
    if session_manager.is_active():
        return jsonify({
            'status': 'error',
            'message': '⚠️ Please end current session before restoring.',
            'session_active': True
        })
    
    try:
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        success = session_manager.restore_from_redis(session_id, current_working_dir=working_dir)
        
        if success:
            return jsonify({
                'status': 'success',
                'response': f'✅ **Session restored!**\n\nSession ID: `{session_id[:16]}...`',
                'session_active': True,
                'session_id': session_id
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'❌ Failed to restore session: {session_id}'
            })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'❌ Error restoring session: {str(e)}'
        })


def handle_session_delete(session_id):
    """Delete a session."""
    session_manager = get_session_manager()
    success = session_manager.delete_session(session_id)
    
    if success:
        return jsonify({
            'status': 'success',
            'response': f'🗑️ **Session deleted!**\n\nSession ID: `{session_id[:16]}...`'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'❌ Failed to delete session: {session_id}'
        })


def handle_models():
    """List registered models from ModelRegistry."""
    try:
        from src.model_registry import ModelRegistry

        registry = ModelRegistry()
        all_models = registry.list_models()

        if all_models:
            # Group models by type
            general_models = [m for m in all_models if m.model_type == 'general']
            coder_models = [m for m in all_models if m.model_type == 'coder']

            response_parts = ["📋 **Registered Models:**\n"]

            if general_models:
                response_parts.append("**General Models:**")
                for m in general_models:
                    active_marker = " ✓" if m.is_active else ""
                    response_parts.append(f"• `{m.model_name}`{active_marker}")

            if coder_models:
                response_parts.append("\n**Coder Models:**")
                for m in coder_models:
                    active_marker = " ✓" if m.is_active else ""
                    response_parts.append(f"• `{m.model_name}`{active_marker}")

            return jsonify({
                'status': 'success',
                'response': "\n".join(response_parts)
            })
        else:
            return jsonify({
                'status': 'success',
                'response': "📋 **Registered Models:**\n\n_No models registered. Use `/model add` to register models._"
            })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'❌ Error listing models: {str(e)}'
        })


def handle_mcps():
    """List MCP servers."""
    import os
    from pathlib import Path
    
    # Check system_mcps directory
    mcps_dir = Path(__file__).parent.parent.parent.parent / 'system_mcps'
    
    if not mcps_dir.exists():
        return jsonify({
            'status': 'success',
            'response': "🔧 **MCP Servers:**\n\n_No MCP servers found._"
        })
    
    mcps = []
    for item in mcps_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            mcps.append(f"• `{item.name}`")
    
    if mcps:
        return jsonify({
            'status': 'success',
            'response': f"🔧 **MCP Servers:**\n\n" + "\n".join(mcps)
        })
    else:
        return jsonify({
            'status': 'success',
            'response': "🔧 **MCP Servers:**\n\n_No MCP servers found._"
        })


def handle_code_command(prompt):
    """Handle /code command - returns steps for user confirmation."""
    import requests
    from src.model_registry import ModelRegistry
    from flask import current_app

    postgres_api_url = os.getenv('POSTGRES_API_URL', 'http://localhost:15000')
    session_manager = get_session_manager()

    # Use configured working directory (from AI_CLI_CWD env var set at startup)
    working_dir = current_app.config.get('WORKING_DIR', os.getcwd())

    # Ensure session is active (like CLI does)
    if not session_manager.is_active():
        session_manager.start_session(working_dir=working_dir)

    session_id = session_manager.get_session_id()

    # Get coder model for /code operations
    model_registry = ModelRegistry()
    coder_model = model_registry.get_active_model('coder')

    # Build request payload with coder model and URL
    code_command_payload = {
        'text': prompt,
        'session_id': session_id
    }

    if coder_model:
        code_command_payload['model'] = coder_model.model_name
        code_command_payload['ollama_url'] = coder_model.url

    try:
        response = requests.post(
            f"{postgres_api_url}/mcp-tools/code-command-simple",
            json=code_command_payload,
            timeout=180
        )

        if response.status_code == 200:
            data = response.json()

            # Check if we got steps back (planning phase)
            steps = data.get('steps', [])
            if steps:
                metadata = data.get('metadata', {})
                
                # Extract @ references from prompt for context
                at_references = re.findall(r'@([\w\-./]+)', prompt)

                # Return steps for user confirmation (UI will display them with Yes/No buttons)
                return jsonify({
                    'status': 'awaiting_confirmation',
                    'steps': steps,
                    'prompt': prompt,
                    'metadata': metadata,
                    'at_references': at_references,
                    'session_id': session_id
                })
            else:
                # Fallback to result/message if available
                return jsonify({
                    'status': 'success',
                    'response': f"✅ **Code Command Executed**\n\n{data.get('result', data.get('message', 'Command completed.'))}"
                })
        else:
            return jsonify({
                'status': 'error',
                'message': f'❌ Code command failed: {response.text}'
            })
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': '⏱️ Code command timed out. Try a simpler task.'
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'error',
            'message': '❌ Cannot connect to the code execution service.\n\nMake sure the PostgreSQL API is running:\n```\ndocker compose --profile app up -d\n```'
        })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'❌ Error: {str(e)}'
        })


@chat_bp.route('/execute-code-steps', methods=['POST'])
def execute_code_steps():
    """
    Execute code steps after user confirmation.
    Matches CLI behavior: loads context maps, generates code with LLM, executes tools.

    Request body:
        prompt: Original code prompt
        steps: List of steps to execute
        at_references: Optional list of @ file references
        session_id: Optional session ID
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body required'
            }), 400

        prompt = data.get('prompt', '')
        steps = data.get('steps', [])
        at_references = data.get('at_references', [])

        if not steps:
            return jsonify({
                'status': 'error',
                'message': 'No steps provided'
            }), 400

        from src.model_registry import ModelRegistry
        from flask import current_app

        postgres_api_url = os.getenv('POSTGRES_API_URL', 'http://localhost:15000')
        session_manager = get_session_manager()

        # Use configured working directory (from AI_CLI_CWD env var set at startup)
        working_dir = current_app.config.get('WORKING_DIR', os.getcwd())

        # Ensure session is active
        if not session_manager.is_active():
            session_manager.start_session(working_dir=working_dir)

        session_id = session_manager.get_session_id()

        # Store @ references in session metadata (like CLI)
        if at_references:
            session_manager.session_metadata['at_references'] = at_references
            session_manager.session_metadata['working_dir'] = working_dir

        # Get model registry for coder model selection
        model_registry = ModelRegistry()

        # Execute all steps in a single async context to avoid event loop issues
        # This creates a fresh MCP client inside the async function
        execution_results = run_async(_execute_all_steps_async(
            steps=steps,
            at_references=at_references,
            working_dir=working_dir,
            session_id=session_id,
            postgres_api_url=postgres_api_url,
            model_registry=model_registry,
            session_manager=session_manager
        ))

        # Format response with execution results
        response_text = _format_execution_response(execution_results)

        return jsonify({
            'status': 'success',
            'response': response_text,
            'execution_results': execution_results
        })

    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Failed to execute code steps: {str(e)}'
        }), 500


async def _execute_all_steps_async(steps, at_references, working_dir, session_id, 
                                    postgres_api_url, model_registry, session_manager):
    """
    Execute all steps in a single async context.
    Creates a fresh MCP client to ensure all subprocess handles are on the same event loop.
    """
    import requests as http_requests
    from src.utils.repomap import load_repomap_to_context
    from src.utils.datamap import load_datamap_to_context

    # Create a fresh MCP client in this async context
    # This ensures all subprocess handles are created on the current event loop
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    system_mcps_dir = project_root / 'system_mcps'
    postgres_url = os.getenv('POSTGRES_API_URL', 'http://localhost:15000')
    
    mcp_client = MCPClient(
        system_mcps_dir=system_mcps_dir,
        postgres_url=postgres_url,
        verbose=False
    )

    try:
        # Pre-start the coder MCP server to ensure subprocess handles are on current loop
        # This prevents "Future attached to a different loop" errors
        await mcp_client.start_server('coder')

        # Load .repomap if exists and not already loaded (like CLI)
        repomap_path = os.path.join(working_dir, '.repomap')
        repomap_loaded_key = f'repomap_loaded_{repomap_path}'
        if os.path.exists(repomap_path) and not session_manager.session_metadata.get(repomap_loaded_key):
            try:
                repomap_result = await load_repomap_to_context(
                    mcp_client,
                    '.repomap',
                    working_dir,
                    session_id
                )
                if repomap_result.get('status') == 'success':
                    session_manager.session_metadata[repomap_loaded_key] = True
            except Exception:
                pass  # Non-critical, continue execution

        # Load .datamap if exists and not already loaded (like CLI)
        datamap_path = os.path.join(working_dir, '.datamap')
        datamap_loaded_key = f'datamap_loaded_{datamap_path}'
        if os.path.exists(datamap_path) and not session_manager.session_metadata.get(datamap_loaded_key):
            try:
                datamap_result = await load_datamap_to_context(
                    mcp_client,
                    '.datamap',
                    working_dir,
                    session_id
                )
                if datamap_result.get('status') == 'success':
                    session_manager.session_metadata[datamap_loaded_key] = True
            except Exception:
                pass  # Non-critical, continue execution

        # Load tool categories dynamically from MCP (with fallback to hardcoded defaults)
        _load_tool_categories_from_mcp(mcp_client)
        code_generation_tools = get_tool_category('code_generation', mcp_client)
        valid_coding_tools = get_tool_category('valid_coding', mcp_client)
        meta_tools = get_tool_category('meta', mcp_client)

        # Execute each step (matches CLI flow)
        execution_results = []

        # Accumulate context from previous steps for code generation
        accumulated_file_contexts = {}  # {file_path: file_content}

        for i, step in enumerate(steps, 1):
            tool_name = 'unknown'
            try:
                # Step 1: Match this step with the best MCP tool
                match_response = http_requests.post(
                    f"{postgres_api_url}/mcp-tools/retrieve",
                    json={
                        "prompts": [step],
                        "threshold": 0.3,
                        "context_references": at_references
                    },
                    timeout=30
                )

                if match_response.status_code != 200:
                    execution_results.append({
                        'step': i,
                        'tool_name': 'unknown',
                        'status': 'error',
                        'message': 'Failed to match tool'
                    })
                    continue

                match_data = match_response.json()
                matched_results = match_data.get('results', [])

                if not matched_results or not matched_results[0].get('best_match'):
                    execution_results.append({
                        'step': i,
                        'tool_name': 'unknown',
                        'status': 'skipped',
                        'message': 'No matching tool found'
                    })
                    continue

                best_match = matched_results[0]['best_match']
                tool_name = best_match.get('tool_name')
                mcp_name = best_match.get('mcp_name', 'coder')
                extracted_params = best_match.get('extracted_params', {})

                # Skip meta tools
                if tool_name in meta_tools:
                    continue

                # Skip invalid tools
                if tool_name not in valid_coding_tools:
                    execution_results.append({
                        'step': i,
                        'tool_name': tool_name,
                        'status': 'skipped',
                        'message': f'Invalid tool for /code command: {tool_name}'
                    })
                    continue

                # Step 2: For code generation tools, use LLM to generate code first (like CLI)
                if tool_name in code_generation_tools:
                    # Check for file path with @ prefix
                    file_match = re.search(r'@([\w\-./]+\.(?:py|r|R))', step)
                    file_path = file_match.group(1) if file_match else None

                    # For run_python_code/run_r_code with existing file, read the file
                    if tool_name in ['run_python_code', 'run_r_code'] and file_path:
                        step_lower = step.lower()
                        is_run_file = (
                            ('file' in step_lower and '@' in step_lower) or
                            ('script' in step_lower and '@' in step_lower) or
                            'run @' in step_lower or
                            'execute @' in step_lower
                        )

                        if is_run_file:
                            # Read existing file
                            full_file_path = os.path.join(working_dir, file_path) if not os.path.isabs(file_path) else file_path
                            try:
                                with open(full_file_path, 'r', encoding='utf-8') as f:
                                    code = f.read()
                                extracted_params['code'] = code
                                if 'file_path' in extracted_params:
                                    extracted_params.pop('file_path')
                            except FileNotFoundError:
                                execution_results.append({
                                    'step': i,
                                    'tool_name': tool_name,
                                    'status': 'error',
                                    'message': f'File not found: {file_path}'
                                })
                                continue
                        else:
                            # Generate code with LLM (use coder model)
                            code, llm_model_name = _generate_code_with_llm_sync(
                                step, 
                                model_registry, 
                                mcp_client, 
                                tool_name=tool_name,
                                use_coder_model=True
                            )
                            if not code:
                                execution_results.append({
                                    'step': i,
                                    'tool_name': tool_name,
                                    'status': 'error',
                                    'message': 'No code detected in LLM response',
                                    'model': llm_model_name
                                })
                                continue
                            extracted_params['code'] = code
                            extracted_params['_model_used'] = llm_model_name
                            if 'file_path' in extracted_params:
                                extracted_params.pop('file_path')
                    else:
                        # For write/edit tools, generate code with LLM
                        original_file_content = None
                        
                        # For edit tools, read original file for context
                        if tool_name in ['edit_python_code', 'edit_r_code'] and file_path:
                            full_file_path = os.path.join(working_dir, file_path) if not os.path.isabs(file_path) else file_path
                            try:
                                if os.path.exists(full_file_path):
                                    with open(full_file_path, 'r', encoding='utf-8') as f:
                                        original_file_content = f.read()
                            except Exception:
                                # Ignore file read errors - will proceed without original content
                                pass

                        # Generate code with LLM (always use coder model for code generation)
                        use_coder_model = True  # Always use coder model for code generation
                        code, llm_model_name = _generate_code_with_llm_sync(
                            step,
                            model_registry,
                            mcp_client,
                            original_file_content=original_file_content,
                            file_path=file_path,
                            use_coder_model=use_coder_model,
                            tool_name=tool_name,
                            accumulated_contexts=accumulated_file_contexts  # Pass accumulated context
                        )
                        
                        if not code:
                            execution_results.append({
                                'step': i,
                                'tool_name': tool_name,
                                'status': 'error',
                                'message': 'No code detected in LLM response',
                                'model': llm_model_name
                            })
                            continue
                        
                        extracted_params['code'] = code
                        extracted_params['_model_used'] = llm_model_name

                        # Add file_path for write/edit tools
                        if file_path and tool_name in ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code']:
                            extracted_params['file_path'] = file_path
                        elif 'file_path' not in extracted_params and tool_name in ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code']:
                            execution_results.append({
                                'step': i,
                                'tool_name': tool_name,
                                'status': 'error',
                                'message': 'No file path specified'
                            })
                            continue
                else:
                    # Non-code-generation tools: use extracted params
                    # Strip @ prefix from file_path if present
                    if 'file_path' in extracted_params and extracted_params['file_path']:
                        fp = extracted_params['file_path']
                        if fp.startswith('@'):
                            extracted_params['file_path'] = fp[1:]
                    if 'directory_path' in extracted_params and extracted_params['directory_path']:
                        dp = extracted_params['directory_path']
                        if dp.startswith('@'):
                            extracted_params['directory_path'] = dp[1:]

                # Add working_dir and session_id
                extracted_params['working_dir'] = working_dir
                extracted_params['session_id'] = session_id

                # Step 3: Execute the tool using MCP client (await directly since we're in async context)
                result = await mcp_client.call_tool(
                    mcp_name=mcp_name,
                    tool_name=tool_name,
                    arguments=extracted_params
                )

                # Parse result
                result_data = result
                if isinstance(result, str):
                    try:
                        result_data = json.loads(result)
                    except (json.JSONDecodeError, ValueError):
                        # Result is not JSON, keep as string
                        pass

                # Determine status from result
                status = 'success'
                if isinstance(result_data, dict):
                    if result_data.get('status') == 'error':
                        status = 'error'

                # Store file context from add_file_context for use in later steps
                if tool_name == 'add_file_context' and isinstance(result_data, dict):
                    file_content = result_data.get('content', '')  # MCP returns 'content', not 'file_content'
                    file_path_loaded = result_data.get('file_path', '')
                    if file_content and file_path_loaded:
                        accumulated_file_contexts[file_path_loaded] = file_content
                        print(f"[_execute_all_steps_async] Stored context for {file_path_loaded}: {len(file_content)} chars")

                # Store directory context from add_directory_context
                if tool_name == 'add_directory_context' and isinstance(result_data, dict):
                    files = result_data.get('files_content', [])  # MCP returns 'files_content'
                    for file_info in files:
                        if isinstance(file_info, dict):
                            fpath = file_info.get('full_path', file_info.get('path', ''))  # Try full_path first, then path
                            fcontent = file_info.get('content', '')
                            if fpath and fcontent:
                                accumulated_file_contexts[fpath] = fcontent
                                print(f"[_execute_all_steps_async] Stored context for {fpath}: {len(fcontent)} chars")

                # Include model name if it was used for code generation
                result_entry = {
                    'step': i,
                    'tool_name': tool_name,
                    'status': status,
                    'result': result_data
                }
                if '_model_used' in extracted_params:
                    result_entry['model'] = extracted_params['_model_used']
                execution_results.append(result_entry)

                # Add to session history
                if session_manager.is_active():
                    session_manager.add_interaction(
                        prompt=step,
                        response=json.dumps(result_data) if isinstance(result_data, dict) else str(result_data),
                        metadata={'step': i, 'tool': tool_name}
                    )
                    try:
                        session_manager.save_to_redis()
                    except Exception:
                        pass

            except Exception as step_error:
                capture_exception(step_error)
                execution_results.append({
                    'step': i,
                    'tool_name': tool_name,
                    'status': 'error',
                    'message': str(step_error)
                })

        return execution_results

    finally:
        # Cleanup the MCP client
        await mcp_client.cleanup()


def _generate_code_with_llm_sync(step: str, model_registry, mcp_client,
                                  original_file_content: str = None,
                                  file_path: str = None, use_coder_model: bool = False,
                                  tool_name: str = None, accumulated_contexts: dict = None) -> tuple:
    """
    Generate code using LLM, matching CLI behavior.

    Args:
        step: The step/prompt to generate code for
        model_registry: ModelRegistry instance
        mcp_client: MCPClient instance (for detect_code)
        original_file_content: For edit operations, the original file content
        file_path: Target file path
        use_coder_model: Whether to use coder model (for edit operations)
        tool_name: Name of the tool being used
        accumulated_contexts: Dict of {file_path: file_content} from previous add_file_context steps

    Returns:
        Tuple of (code, model_name) where code is the generated code string or None,
        and model_name is the name of the model used
    """
    model_name_used = None
    try:
        from src.ollama_client.client import OllamaClient
        
        # Get the appropriate model based on use_coder_model flag
        if use_coder_model:
            coder_model = model_registry.get_active_model('coder')
            if coder_model:
                # Create client with coder model's URL and settings
                ollama_client = OllamaClient(
                    host=coder_model.url,
                    model=coder_model.model_name,
                    timeout=coder_model.timeout
                )
                model_name_used = coder_model.model_name
                print(f"[_generate_code_with_llm_sync] Using coder model: {coder_model.model_name} at {coder_model.url}")
            else:
                # Fallback to general model if no coder model available
                ollama_client, _ = get_ollama_client()
                model_name_used = ollama_client.model if hasattr(ollama_client, 'model') else 'unknown'
                print(f"[_generate_code_with_llm_sync] No coder model available, using general model")
        else:
            ollama_client, _ = get_ollama_client()
            model_name_used = ollama_client.model if hasattr(ollama_client, 'model') else 'unknown'

        # Build accumulated context section from previous steps
        context_section = ""
        if accumulated_contexts:
            context_section = "\n\n=== REFERENCE: FILES LOADED IN PREVIOUS STEPS (FOR YOUR REFERENCE ONLY - DO NOT COPY THIS TEXT) ===\n"
            for ctx_path, ctx_content in accumulated_contexts.items():
                # Limit context to first 2000 chars per file to avoid token limits
                truncated_content = ctx_content[:2000] + "..." if len(ctx_content) > 2000 else ctx_content
                context_section += f"\nReference File: {ctx_path}\n{truncated_content}\n"
            context_section += "=== END REFERENCE FILES ===\n\n"

        # Build prompt for edit operations with original file context (like CLI)
        if original_file_content and file_path:
            line_count = len(original_file_content.splitlines())
            is_r_code = tool_name in ['edit_r_code', 'write_r_code'] if tool_name else False
            lang_name = "R" if is_r_code else "Python"
            code_block_marker = "r" if is_r_code else "python"

            llm_prompt = f"""Edit this {lang_name} file. ONLY make the requested changes. Do NOT modify anything else.

ORIGINAL FILE ({line_count} lines):
{original_file_content}
{context_section}
REQUESTED CHANGE: {step}

STRICT RULES - Read carefully:
1. Copy the ENTIRE original file exactly as-is
2. Make ONLY the specific change requested - nothing more
3. Do NOT remove or change existing docstrings (keep triple-quote docstring blocks exactly as they are)
4. Do NOT refactor code (keep list comprehensions, loops, etc. exactly as written)
5. Do NOT add comments to explain your changes
6. Output complete valid {lang_name} code, NOT a git diff

IMPORTANT: The file has {line_count} lines. Your output must also have approximately {line_count} lines.
Do NOT shorten functions at the end of the file. Keep everything identical except your specific change.

Output format:
```{code_block_marker}
[paste complete file with only the requested change]
```"""
        else:
            # For code generation without original file context, still provide code block instructions
            is_r_code = tool_name in ['edit_r_code', 'write_r_code', 'run_r_code'] if tool_name else False
            lang_name = "R" if is_r_code else "Python"
            code_block_marker = "r" if is_r_code else "python"

            llm_prompt = f"""You are a code generator. Generate {lang_name} code for the following request.{context_section}

REQUEST: {step}

CRITICAL RULES:
1. Output ONLY the code, no explanations
2. DO NOT add any text before or after the code block
3. Use proper {lang_name} syntax and best practices

OUTPUT FORMAT (EXACT):
```{code_block_marker}
<your code here>
```

Start your response with the ``` marker immediately. No text before the code block."""

        # Set num_predict for code generation (allow more tokens)
        num_predict = 8192 if use_coder_model else None

        # Call LLM
        messages = [{'role': 'user', 'content': llm_prompt}]
        
        # Debug: Log what we're sending
        print(f"[_generate_code_with_llm_sync] Prompt length: {len(llm_prompt)} chars, num_predict={num_predict}")
        
        try:
            response = ollama_client.chat(
                messages=messages,
                stream=False,
                temperature=0.7,
                num_predict=num_predict
            )
        except Exception as chat_error:
            print(f"[_generate_code_with_llm_sync] Chat error: {chat_error}")
            return (None, model_name_used)
        
        # Debug: Log the raw response
        print(f"[_generate_code_with_llm_sync] Raw response type: {type(response)}")

        # Handle both dict and object responses (ollama library returns object in newer versions)
        if isinstance(response, dict):
            full_response = response.get('message', {}).get('content', '')
        else:
            # Handle ollama library response object
            full_response = response.message.content if hasattr(response, 'message') else str(response)
        
        # If response is empty, check if there's an error in the response
        if not full_response:
            if isinstance(response, dict):
                error = response.get('error')
                if error:
                    print(f"[_generate_code_with_llm_sync] LLM error: {error}")
                    return (None, model_name_used)

        # Debug: Log LLM response for troubleshooting
        print(f"[_generate_code_with_llm_sync] LLM response length: {len(full_response)} chars")
        print(f"[_generate_code_with_llm_sync] First 500 chars: {full_response[:500]}")

        # Detect code in response using the passed mcp_client
        detected = mcp_client.detect_code(full_response)
        if detected:
            print(f"[_generate_code_with_llm_sync] Code detected successfully: {len(detected['code'])} chars")
            return (detected['code'], model_name_used)
        else:
            print(f"[_generate_code_with_llm_sync] ERROR: No code detected in LLM response")
        
        return (None, model_name_used)

    except Exception as e:
        capture_exception(e)
        return (None, model_name_used)


async def _handle_file_modifications_async(response_text: str, files_to_modify: list,
                                            files_to_create: list, working_dir: str):
    """
    Handle file modifications asynchronously using MCP.

    Args:
        response_text: The LLM response text containing file modifications
        files_to_modify: List of existing files to modify
        files_to_create: List of new files to create
        working_dir: The working directory

    Returns:
        Dict with results for each file (modified, created, errors)
    """
    # Create a fresh MCP client in this async context
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    system_mcps_dir = project_root / 'system_mcps'
    postgres_url = os.getenv('POSTGRES_API_URL', 'http://localhost:15000')

    mcp_client = MCPClient(
        system_mcps_dir=system_mcps_dir,
        postgres_url=postgres_url,
        verbose=False
    )

    try:
        # Pre-start the coder MCP server
        await mcp_client.start_server('coder')

        # Call the shared file modification handler
        results = await handle_file_modifications(
            mcp_client=mcp_client,
            response_text=response_text,
            files_to_modify=files_to_modify,
            files_to_create=files_to_create,
            get_working_dir_func=lambda: working_dir,
            console=None,  # UI doesn't use rich console
            debug_print_func=None  # UI doesn't need debug prints
        )

        return results

    finally:
        # Cleanup the MCP client
        await mcp_client.cleanup()


def _format_execution_response(execution_results: list) -> str:
    """Format execution results into a readable response string."""
    response_text = f"✅ **Code Execution Complete**\n\n"
    response_text += f"Executed {len(execution_results)} step(s):\n\n"

    for result in execution_results:
        step_num = result['step']
        tool_name = result.get('tool_name', 'unknown')
        status = result.get('status')
        result_data = result.get('result', {})
        model_name = result.get('model')

        response_text += f"**{step_num}. {tool_name}**"
        if model_name:
            response_text += f" <small style='color: #888; font-size: 0.75em;'>({model_name})</small>"
        response_text += "\n\n"

        if status == 'error':
            error_msg = result.get('message', 'Unknown error')
            if isinstance(result_data, dict) and result_data.get('message'):
                error_msg = result_data.get('message')
            response_text += f"❌ Error: {error_msg}\n\n"
            continue
        elif status == 'skipped':
            response_text += f"⚠️ Skipped: {result.get('message', 'No matching tool')}\n\n"
            continue

        # Show execution details based on tool type
        if tool_name in ['run_python_code', 'run_r_code']:
            if isinstance(result_data, dict):
                stdout = result_data.get('stdout', '').strip()
                stderr = result_data.get('stderr', '').strip()
                exit_code = result_data.get('exit_code', -1)

                if stdout:
                    response_text += f"📄 **Output:**\n```\n{stdout}\n```\n"
                if stderr:
                    response_text += f"⚠️ **Errors/Warnings:**\n```\n{stderr}\n```\n"

                if exit_code == 0:
                    response_text += f"✅ _Exit code: {exit_code}_\n\n"
                else:
                    response_text += f"❌ _Exit code: {exit_code}_\n\n"
            else:
                response_text += f"```\n{result_data}\n```\n\n"

        elif tool_name in ['write_python_code', 'write_r_code', 'edit_python_code', 'edit_r_code']:
            if isinstance(result_data, dict):
                file_path = result_data.get('file_path', 'unknown')
                file_status = result_data.get('status', 'completed')
                message = result_data.get('message', '')
                response_text += f"✓ File {file_status}: `{file_path}`\n"
                if message:
                    response_text += f"   {message}\n"
                response_text += "\n"
            else:
                response_text += f"```\n{result_data}\n```\n\n"

        elif tool_name == 'add_file_context':
            if isinstance(result_data, dict):
                file_path = result_data.get('file_path', 'unknown')
                response_text += f"📂 Loaded file into context: `{file_path}`\n\n"
            else:
                response_text += f"```\n{result_data}\n```\n\n"

        elif tool_name == 'add_directory_context':
            if isinstance(result_data, dict):
                dir_path = result_data.get('directory_path', 'unknown')
                files_count = result_data.get('files_count', 0)
                response_text += f"📁 Loaded directory into context: `{dir_path}` ({files_count} files)\n\n"
            else:
                response_text += f"```\n{result_data}\n```\n\n"

        else:
            # Generic display for other tools
            if isinstance(result_data, dict):
                response_text += f"```json\n{json.dumps(result_data, indent=2)}\n```\n\n"
            else:
                response_text += f"```\n{result_data}\n```\n\n"

    return response_text


@chat_bp.route('/auto-session', methods=['POST'])
def auto_create_session():
    """
    Automatically create or restart a session for UI access.
    Ends any existing session and starts a new one.
    Only saves the previous session if it has interactions.
    """
    try:
        session_manager = get_session_manager()
        
        # End existing session if active
        if session_manager.is_active():
            try:
                # Check if session has interactions before ending
                num_interactions = len(session_manager.session_history)
                
                # Save before ending if there are interactions
                if num_interactions > 0:
                    session_manager.save_to_redis()
                
                session_manager.end_session()
            except Exception as e:
                capture_exception(e)
        
        # Start new session
        working_dir = os.environ.get('AI_CLI_CWD', os.getcwd())
        session_manager.start_session(working_dir=working_dir)
        session_id = session_manager.get_session_id()
        
        return jsonify({
            'status': 'success',
            'session_active': True,
            'session_id': session_id,
            'message': 'Session auto-created'
        })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Failed to create session: {str(e)}',
            'session_active': False
        }), 500


@chat_bp.route('/rate', methods=['POST'])
def submit_rating():
    """
    Submit a rating for a prompt/response pair.
    Uses the same rating logic as the CLI.
    """
    try:
        from src.utils.ratings import process_rating
        
        data = request.get_json()
        rating = data.get('rating')
        prompt_text = data.get('prompt', '')
        response_text = data.get('response', '')
        
        # Validate rating
        if rating is None or not isinstance(rating, int) or rating < 0 or rating > 10:
            return jsonify({
                'status': 'error',
                'message': 'Invalid rating. Must be 0-10.'
            }), 400
        
        if not prompt_text or not response_text:
            return jsonify({
                'status': 'error',
                'message': 'Missing prompt or response text.'
            }), 400
        
        # Get session ID if available
        session_manager = get_session_manager()
        session_id = session_manager.get_session_id() if session_manager.is_active() else None
        
        # Process rating using CLI logic
        process_rating(rating, prompt_text, response_text, session_id)
        
        return jsonify({
            'status': 'success',
            'message': f'Rating {rating} submitted successfully'
        })
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': f'Failed to submit rating: {str(e)}'
        }), 500
