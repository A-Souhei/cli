"""
Chat API routes for the UI.

Provides endpoints for:
- Sending chat messages to the LLM
- Streaming responses
"""

import os
import sys
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.sentry_config import capture_exception
from src.session.manager import SessionManager

chat_bp = Blueprint('chat', __name__)

# Reuse a single session manager instance for the UI server so
# session state persists across requests.
_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Return the shared SessionManager instance."""
    return _session_manager


@chat_bp.route('/models', methods=['GET'])
def get_available_models():
    """
    Get list of available models from the Ollama API.
    """
    try:
        from src.config.manager import ConfigManager
        import httpx
        
        config = ConfigManager()
        ollama_url = config.get_ollama_url()
        # Call Ollama API to get models
        response = httpx.get(f"{ollama_url}/api/tags", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        models = [model['name'] for model in data.get('models', [])]
        
        return jsonify({
            'status': 'success',
            'models': models
        })
    except Exception as e:
        capture_exception(e)
        # Return empty list with 200 status so frontend doesn't break
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch models: {str(e)}',
            'models': []
        })


def get_ollama_client():
    """Get or create an Ollama client instance."""
    from src.ollama_client.client import OllamaClient
    from src.config.manager import ConfigManager
    
    config = ConfigManager()
    host = config.get_ollama_url()
    model = config.get_ollama_model()
    timeout = config.get_ollama_timeout()
    
    return OllamaClient(host=host, model=model, timeout=timeout), config


@chat_bp.route('/send', methods=['GET', 'POST'])
def send_message():
    """
    Send a message to the LLM and get a response.
    
    Request body:
        message: The user message
        model: Optional model name (defaults to config model)
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
        
        # Get client and config
        client, config = get_ollama_client()
        
        # Use provided model or default from config
        if not model:
            model = config.get_ollama_model()
        
        # Build the message with file contents included
        full_message = message
        if file_contents:
            file_context = "\n\n--- Attached Files ---\n"
            for filename, content in file_contents.items():
                file_context += f"\n### File: {filename}\n```\n{content}\n```\n"
            full_message = file_context + "\n--- User Message ---\n" + message
        
        # Prepare messages for the API
        messages = [
            {"role": "user", "content": full_message}
        ]
        
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
            session_manager.save_to_redis()
            
            return jsonify({
                'status': 'success',
                'response': content,
                'model': model,
                'session_active': session_manager.is_active(),
                'session_id': session_manager.get_session_id()
            })
            
        except Exception as e:
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
            return jsonify({
                'status': 'success',
                'response': '⚠️ **Repomap Create** is a long-running operation.\n\nPlease use the CLI to run:\n```\n/repomap create\n```'
            })
        elif cmd == 'repomap load':
            return jsonify({
                'status': 'success',
                'response': '⚠️ **Repomap Load** requires CLI context.\n\nPlease use the CLI to run:\n```\n/repomap load\n```'
            })
        elif cmd == 'repomap update':
            return jsonify({
                'status': 'success',
                'response': '⚠️ **Repomap Update** is a long-running operation.\n\nPlease use the CLI to run:\n```\n/repomap update\n```'
            })
        elif cmd == 'clear':
            return jsonify({
                'status': 'success',
                'response': '🗑️ Chat history cleared.'
            })
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
        except:
            pass
    
    summary = session_manager.end_session()
    
    return jsonify({
        'status': 'success',
        'response': f'✅ **Session ended!**\n\n{summary if summary else "Session saved."}',
        'session_active': False
    })


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
    """List available models."""
    try:
        client, _ = get_ollama_client()
        models = client.list_models()
        
        if models:
            model_list = "\n".join([f"• `{m}`" for m in models])
            return jsonify({
                'status': 'success',
                'response': f"📋 **Available Models:**\n\n{model_list}"
            })
        else:
            return jsonify({
                'status': 'success',
                'response': "📋 **Available Models:**\n\n_No models found._"
            })
    except Exception as e:
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
    """Handle /code command."""
    import requests
    import os
    
    postgres_api_url = os.getenv('POSTGRES_API_URL', 'http://localhost:15000')
    
    try:
        response = requests.post(
            f"{postgres_api_url}/mcp-tools/code-command-simple",
            json={
                'text': prompt,
                'session_id': 'ui-session'
            },
            timeout=180
        )
        
        if response.status_code == 200:
            data = response.json()
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
        return jsonify({
            'status': 'error',
            'message': f'❌ Error: {str(e)}'
        })


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
