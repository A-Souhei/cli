"""Main entry point for the AI CLI application."""

# CRITICAL: Capture original working directory BEFORE any imports
# This must be the first thing we do to preserve the true launch directory
import os
import sys
if 'AI_CLI_ORIGINAL_DIR' not in os.environ:
    os.environ['AI_CLI_ORIGINAL_DIR'] = os.getcwd()

import json
import argparse
import re
import requests
import urllib.parse
import subprocess
import asyncio
from pathlib import Path
from src.config import ConfigManager
from src.config.llm_availability import LLMAvailabilityChecker
from src.ollama_client import OllamaClient
from src.chat import ChatManager
from src.selector import InteractiveSelector
from src.mcp import MCPClient
from src.session import SessionManager, SessionTitleGenerator, WorkingDirectoryMismatchError
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.theme import Theme
from rich.style import Style
from rich.spinner import Spinner
from rich.live import Live
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import FormattedText
from src.file_completer import CombinedCompleter, extract_at_context, remove_at_prefixed_paths
from src.utils.tree import generate_tree

# Import repomap functionality from separate module
from src.utils.repomap import (
    collect_source_files,
    generate_repomap_prompt,
    generate_repomap_update_prompt,
    load_repomap_to_context,
)

# Import datamap functionality from separate module
from src.utils.datamap import (
    get_postgresql_signature,
    collect_data_files,
    generate_datamap_prompt,
    generate_datamap_update_prompt,
    load_datamap_to_context,
)

# Import ratings functionality from separate module
from src.utils.ratings import (
    process_rating,
    get_prompt_guidance,
)

# Import code handlers from separate module
from src.utils.code_handlers import (
    handle_code_file_writing,
    handle_file_modifications,
    handle_code_execution,
    display_execution_result,
)

# Import MCP discovery from separate module
from src.utils.mcp_discovery import (
    list_system_mcps,
    get_mcp_tools,
)

# Import banner functionality from separate module
from src.utils.banner import (
    print_banner,
)

# Apply nest_asyncio once globally to allow nested event loops
import nest_asyncio
nest_asyncio.apply()


# Cache for user working directory (set once at startup)
_USER_WORKING_DIR = None


def get_user_working_dir():
    """
    Get the user's original working directory.
    When running globally via ai-cli, uses AI_CLI_CWD env var.
    Otherwise falls back to current directory.
    Result is cached for performance.
    """
    global _USER_WORKING_DIR
    if _USER_WORKING_DIR is None:
        _USER_WORKING_DIR = os.environ.get('AI_CLI_CWD', os.getcwd())
    return _USER_WORKING_DIR


def run_async(coro):
    """
    Run an async coroutine safely, handling nested event loop scenarios.
    Uses nest_asyncio which has been applied globally to allow asyncio.run()
    even when an event loop is already running.
    """
    # With nest_asyncio applied globally, asyncio.run() works even in nested contexts
    return asyncio.run(coro)

# Create custom theme
custom_theme = Theme({
    "markdown.code": "cyan on #000000",
})

# Initialize rich console with custom theme
console = Console(theme=custom_theme)


class CustomMarkdown(Markdown):
    """Custom Markdown renderer with styled code blocks."""

    def __rich_console__(self, console, options):
        """Render markdown with custom code block styling."""
        # Get the rendered markdown elements
        for element in super().__rich_console__(console, options):
            # Check if it's a code block
            if isinstance(element, Panel) and hasattr(element, 'renderable'):
                # Wrap code blocks with blue border and black background
                if isinstance(element.renderable, Syntax):
                    yield Panel(
                        element.renderable,
                        border_style="blue",
                        style=Style(bgcolor="#000000"),
                        padding=(0, 1)
                    )
                else:
                    yield element
            elif isinstance(element, Syntax):
                # Direct Syntax objects (code blocks)
                yield Panel(
                    element,
                    border_style="blue",
                    style=Style(bgcolor="#000000"),
                    padding=(0, 1)
                )
            else:
                yield element

# Set up history file
HISTORY_FILE = Path.home() / ".ai_cli_history"

# API Configuration
POSTGRES_API_URL = "http://localhost:15000"
TRANSFORMER_API_URL = "http://localhost:16050"
SIMILARITY_THRESHOLD = 0.7  # Cosine similarity threshold for considering prompts similar
SATISFACTORY_RATING_THRESHOLD = 7  # Rating >= 7 is considered satisfactory

# Global verbose flag
VERBOSE = False


def debug_print(message, icon="🔍", style="dim"):
    """Print message only if verbose mode is enabled."""
    if VERBOSE:
        console.print(f"{icon} {message}", style=style)


def main(verbose=False):
    """Main function to run the AI CLI."""
    global VERBOSE
    VERBOSE = verbose

    try:
        # Load configuration
        config = ConfigManager()

        # Check LLM availability and get the best available LLM
        llm_checker = LLMAvailabilityChecker(config)
        llm_config = llm_checker.get_available_llm()

        # Initialize Ollama client with the available LLM
        ollama_client = OllamaClient(
            host=llm_config.url,
            model=llm_config.model,
            timeout=llm_config.timeout
        )

        # Initialize chat manager
        chat_manager = ChatManager(
            system_prompt=config.get_system_prompt(),
            max_context_length=config.get_max_context_length()
        )

        # Initialize session title generator (uses local tinyollama)
        title_generator = None
        if config.has_tinyollama_config():
            title_generator = SessionTitleGenerator(
                ollama_url=config.get_tinyollama_url(),
                model=config.get_tinyollama_model(),
                timeout=config.get_tinyollama_timeout()
            )

        # Initialize session manager with title generator
        session_manager = SessionManager(title_generator=title_generator)

        # Initialize MCP client
        system_mcps_dir = Path(__file__).parent / "system_mcps"
        mcp_client = MCPClient(
            system_mcps_dir=system_mcps_dir,
            postgres_url=POSTGRES_API_URL,
            verbose=verbose
        )

        # Set up debug callback for MCP client
        mcp_client.set_debug_callback(debug_print)

        # Initialize MCP tools in database (async operation)
        debug_print("Initializing MCP tools...", icon="🔧")
        try:
            run_async(mcp_client.initialize_tools_in_db())
        except Exception as e:
            debug_print(f"Failed to initialize MCP tools: {e}", icon="⚠️")

        # Get configuration
        temperature = config.get_temperature()
        stream = config.get_stream_enabled()

        # Clear the screen
        console.clear()

        print_banner(console)
        
        # Show LLM status with fallback indicator
        if llm_config.is_tinyollama:
            console.print(f"  📦 Model: [bold yellow]{llm_config.model}[/bold yellow] [dim](fallback - remote unreachable)[/dim]")
            console.print(f"  🔗 Server: [dim]{llm_config.url}[/dim]")
            if llm_config.disabled_features:
                console.print(f"  ⚠️  [dim]Disabled features: {', '.join(llm_config.disabled_features)}[/dim]")
        else:
            console.print(f"  📦 Model: [bold]{llm_config.model}[/bold]")
            console.print(f"  🔗 Server: [dim]{llm_config.url}[/dim]")
        console.print()

        # Initialize command history
        history = FileHistory(str(HISTORY_FILE))

        # Initialize combined completer for / commands and @ file paths
        combined_completer = CombinedCompleter(working_dir=get_user_working_dir())

        # Main chat loop
        while True:
            try:
                # Get user input with history support and command/file completion
                user_input = prompt(
                    FormattedText([('ansigreen bold', '▶ ')]),
                    history=history,
                    completer=combined_completer
                ).strip()

                # Normalize command input - support both with and without / prefix
                user_input_normalized = user_input.lstrip('/').strip()

                # Handle special commands
                if user_input_normalized.lower() in ['exit', 'quit']:
                    # Cleanup MCP client
                    console.print("\n👋 [bold]Goodbye![/bold]")
                    try:
                        run_async(mcp_client.cleanup())
                    except (Exception, KeyboardInterrupt) as e:
                        # Suppress cleanup errors on exit
                        if verbose:
                            debug_print(f"Cleanup: {e}", icon="🧹")
                    # Redirect stderr to suppress prompt_toolkit task cleanup warnings
                    # Open /dev/null without context manager since we exit immediately
                    sys.stderr = open(os.devnull, 'w')
                    sys.exit(0)

                if user_input_normalized.lower() == 'clear':
                    chat_manager.clear_history()
                    console.print("\n🗑️ [yellow]Chat history cleared[/yellow]\n")
                    continue

                if user_input_normalized.lower() == 'models':
                    console.print("\n📋 [bold]Available models:[/bold]")
                    try:
                        models = ollama_client.list_models()
                        for model in models:
                            if model == ollama_client.model:
                                console.print(f"  • {model} [cyan](current)[/cyan]")
                            else:
                                console.print(f"  • {model}")
                    except Exception as e:
                        console.print(f"❌ [red]Error listing models: {e}[/red]")
                    console.print()
                    continue

                if user_input_normalized.lower() == 'switch':
                    console.print()
                    try:
                        models = ollama_client.list_models()
                        if not models:
                            console.print("❌ [red]No models available[/red]\n")
                            continue

                        # Show interactive selector
                        selector = InteractiveSelector(
                            title="🔄 Select Model",
                            choices=models,
                            current=ollama_client.model
                        )
                        selected = selector.show()

                        if selected and selected != ollama_client.model:
                            # Update the model
                            ollama_client.model = selected
                            console.print(f"\n✓ [green]Switched to model:[/green] [bold]{selected}[/bold]\n")
                        elif selected:
                            console.print(f"\n[dim]Already using {selected}[/dim]\n")
                        else:
                            console.print("\n[dim]Cancelled[/dim]\n")
                    except Exception as e:
                        console.print(f"\n❌ [red]Error switching model: {e}[/red]\n")
                    continue

                if user_input_normalized.lower() == 'mcps':
                    list_system_mcps()
                    continue

                if user_input_normalized.lower().startswith('mcp-tools '):
                    mcp_name = user_input_normalized[10:].strip()
                    if not mcp_name:
                        console.print("❌ [red]Usage: /mcp-tools <mcp_name>[/red]\n")
                    else:
                        try:
                            run_async(get_mcp_tools(mcp_name))
                        except Exception as e:
                            console.print(f"❌ [red]Error: {e}[/red]\n")
                    continue

                # Handle session commands
                if user_input_normalized.lower() == 'session start':
                    if session_manager.is_active():
                        console.print("\n⚠️  [yellow]Session already active. End current session first.[/yellow]\n")
                    else:
                        session_manager.start_session(working_dir=get_user_working_dir())
                        console.print()
                    continue

                if user_input_normalized.lower() == 'session end':
                    summary = session_manager.end_session()
                    if summary:
                        # Auto-save session when ending
                        try:
                            session_manager.save_to_redis()
                        except Exception as e:
                            debug_print(f"Failed to save session on end: {e}", icon="⚠️")
                        console.print()
                    continue

                if user_input_normalized.lower() == 'session info':
                    info = session_manager.get_session_info()
                    if info:
                        console.print("\n📊 [bold]Session Info:[/bold]")
                        console.print(f"  • Session ID: [cyan]{info['session_id'][:16]}...[/cyan]")
                        console.print(f"  • Duration: [cyan]{int(info['duration_seconds'])}s[/cyan]")
                        console.print(f"  • Interactions: [cyan]{info['num_interactions']}[/cyan]")
                        console.print()
                    else:
                        console.print("\n⚠️  [yellow]No active session[/yellow]\n")
                    continue

                if user_input_normalized.lower().startswith('session restore '):
                    session_id = user_input_normalized[16:].strip()
                    if not session_id:
                        console.print("\n❌ [red]Usage: /session restore <session_id>[/red]\n")
                    else:
                        if session_manager.is_active():
                            console.print("\n⚠️  [yellow]Please end current session before restoring.[/yellow]\n")
                        else:
                            try:
                                success = session_manager.restore_from_redis(
                                    session_id,
                                    current_working_dir=get_user_working_dir()
                                )
                                if success:
                                    console.print()
                            except WorkingDirectoryMismatchError as e:
                                console.print(f"\n❌ [red]Cannot restore session: working directory mismatch.[/red]")
                                console.print(f"[dim]Session was created in: {e.stored_dir}[/dim]")
                                console.print(f"[dim]Current directory is: {e.current_dir}[/dim]\n")
                    continue

                if user_input_normalized.lower().startswith('session delete '):
                    session_id = user_input_normalized[15:].strip()
                    if not session_id:
                        console.print("\n❌ [red]Usage: /session delete <session_id>[/red]\n")
                    else:
                        success = session_manager.delete_session(session_id)
                        if success:
                            console.print()
                    continue

                if user_input_normalized.lower() in ['session list', 'sessions list', 'sessions']:
                    console.print("\n📋 [bold]Saved Sessions:[/bold]")
                    sessions = session_manager.list_saved_sessions()
                    if sessions:
                        for sess in sessions:
                            console.print(f"  • [cyan]{sess['session_id'][:16]}...[/cyan]")
                            working_dir = sess.get('working_dir')
                            if working_dir:
                                if len(working_dir) > 30:
                                    working_dir_info = f", Dir: {working_dir[:30]}..."
                                else:
                                    working_dir_info = f", Dir: {working_dir}"
                            else:
                                working_dir_info = ""
                            console.print(f"    Interactions: {sess.get('num_interactions', 0)}, "
                                        f"Started: {sess.get('start_time', 'N/A')}{working_dir_info}")
                    else:
                        console.print("  [dim]No saved sessions found[/dim]")
                    console.print()
                    continue

                if user_input_normalized.lower() in ['session clear', 'clear sessions']:
                    console.print()
                    try:
                        # Interactive confirmation
                        selector = InteractiveSelector(
                            title="⚠️  Clear ALL saved sessions?",
                            choices=["No", "Yes"],
                            current="No"
                        )
                        choice = selector.show()

                        if choice == "Yes":
                            count = session_manager.clear_all_sessions()
                            console.print(f"\n✅ [green]Cleared {count} session{'s' if count != 1 else ''}.[/green]\n")
                        else:
                            console.print("\n[dim]Cancelled[/dim]\n")
                    except Exception as e:
                        console.print(f"❌ [red]Error clearing sessions: {e}[/red]\n")
                    continue

                # Handle /repomap create command
                if user_input_normalized.lower() == 'repomap create':
                    # Check if repomap_create is disabled (e.g., when using tinyollama)
                    if llm_checker.is_feature_disabled('repomap_create'):
                        console.print("\n⚠️  [yellow]/repomap create is disabled when using tinyollama fallback.[/yellow]")
                        console.print("[dim]This feature requires a larger model for reliable repository analysis.[/dim]")
                        console.print("[dim]Connect to the primary Ollama server to use this feature.[/dim]\n")
                        continue

                    console.print("\n📦 [bold cyan]Creating repository map...[/bold cyan]")
                    console.print(f"[dim]Scanning working directory: {get_user_working_dir()}[/dim]\n")

                    try:
                        # Collect all source files
                        console.print("[yellow]📂 Collecting source code files...[/yellow]")
                        source_files = collect_source_files(get_user_working_dir())
                        
                        if not source_files:
                            console.print("\n❌ [red]No source code files found in the working directory.[/red]\n")
                            continue
                            
                        console.print(f"[green]✓ Found {len(source_files)} source files[/green]")
                        
                        # Calculate total size
                        total_size = sum(f['size'] for f in source_files)
                        console.print(f"[dim]  Total size: {total_size:,} bytes[/dim]\n")
                        
                        # Generate directory tree
                        console.print("[yellow]🌳 Generating directory tree...[/yellow]")
                        tree_output = generate_tree(get_user_working_dir(), max_depth=5)
                        console.print(f"[green]✓ Directory tree generated[/green]\n")
                        
                        # Generate the LLM prompt with tree
                        console.print("[yellow]🤖 Generating repository map with LLM...[/yellow]")
                        repomap_prompt = generate_repomap_prompt(source_files, tree_output=tree_output)

                        # Check prompt size and warn if it's very large
                        prompt_size = len(repomap_prompt)
                        # Rough estimate: 4 chars per token for most LLMs
                        estimated_tokens = prompt_size // 4
                        if prompt_size > 500_000:  # ~500KB
                            console.print(f"[yellow]⚠️  Warning: Large prompt size ({prompt_size:,} chars, ~{estimated_tokens:,} tokens)[/yellow]")
                            console.print(f"[yellow]   This may exceed token limits for some LLMs or cause slower processing.[/yellow]\n")

                        # Use a separate chat manager for repomap generation to avoid polluting user's history
                        repomap_chat_manager = ChatManager(system_prompt=config.get_system_prompt())
                        repomap_chat_manager.add_user_message(repomap_prompt)
                        messages = repomap_chat_manager.get_messages()
                        
                        spinner = Spinner("dots", text="[dim]Analyzing codebase...[/dim]", style="cyan")
                        
                        with Live(spinner, console=console, refresh_per_second=10):
                            if stream:
                                full_response = ""
                                for chunk in ollama_client.chat(
                                    messages=messages,
                                    stream=True,
                                    temperature=temperature
                                ):
                                    full_response += chunk
                            else:
                                response = ollama_client.chat(
                                    messages=messages,
                                    stream=False,
                                    temperature=temperature
                                )
                                full_response = response.get('message', {}).get('content', '')
                        
                        # No need to save to main chat_manager - repomap generation is isolated
                        
                        # Prepend the tree to the repomap output
                        repomap_content = f"""# Repository Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""

                        # Write the repomap to file
                        repomap_path = os.path.join(get_user_working_dir(), '.repomap')
                        with open(repomap_path, 'w', encoding='utf-8') as f:
                            f.write(repomap_content)
                        
                        console.print(f"\n[bold green]✓ Repository map created successfully![/bold green]")
                        console.print(f"[cyan]📄 Saved to: {repomap_path}[/cyan]\n")
                        
                        # Show preview
                        preview_lines = repomap_content.split('\n')[:20]
                        console.print("[dim]Preview:[/dim]")
                        console.print(CustomMarkdown('\n'.join(preview_lines) + '\n...', code_theme="monokai"))
                        console.print()
                        
                    except Exception as e:
                        console.print(f"\n❌ [red]Error creating repository map: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    continue

                # Handle /repomap load command
                if user_input_normalized.lower() == 'repomap load':
                    repomap_path = os.path.join(get_user_working_dir(), '.repomap')
                    
                    if not os.path.exists(repomap_path):
                        console.print(f"\n❌ [red]No .repomap file found at: {repomap_path}[/red]")
                        console.print("[dim]Use '/repomap create' to generate a repository map first.[/dim]\n")
                        continue
                    
                    console.print(f"\n📂 [cyan]Loading repository map: {repomap_path}[/cyan]")
                    
                    try:
                        # Get session ID if active
                        session_id = session_manager.get_session_id() if session_manager.is_active() else None
                        
                        # Load the repomap into context
                        result = run_async(load_repomap_to_context(
                            mcp_client,
                            '.repomap',
                            os.getcwd(),
                            session_id
                        ))
                        
                        if result.get('status') == 'success':
                            content_size = result.get('content_size', 0)
                            console.print(f"[bold green]✓ Repository map loaded into context![/bold green]")
                            console.print(f"[dim]  Size: {content_size:,} bytes[/dim]")
                            if session_id:
                                console.print(f"[dim]  Session: {session_id[:16]}...[/dim]")
                            else:
                                console.print(f"[dim]  Session: temporary (start a session for persistence)[/dim]")
                            console.print()
                        else:
                            error_msg = result.get('message', 'Unknown error')
                            console.print(f"[yellow]⚠️  Warning: {error_msg}[/yellow]")
                            console.print("[dim]The repomap file may still be usable.[/dim]\n")
                            
                    except Exception as e:
                        console.print(f"\n❌ [red]Error loading repository map: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    continue

                # Handle /repomap update command
                if user_input_normalized.lower() == 'repomap update':
                    # Check if repomap_update is disabled (e.g., when using tinyollama)
                    if llm_checker.is_feature_disabled('repomap_update'):
                        console.print("\n⚠️  [yellow]/repomap update is disabled when using tinyollama fallback.[/yellow]")
                        console.print("[dim]This feature requires a larger model for reliable repository analysis.[/dim]")
                        console.print("[dim]Connect to the primary Ollama server to use this feature.[/dim]\n")
                        continue

                    repomap_path = os.path.join(get_user_working_dir(), '.repomap')
                    
                    if not os.path.exists(repomap_path):
                        console.print(f"\n❌ [red]No .repomap file found at: {repomap_path}[/red]")
                        console.print("[dim]Use '/repomap create' to generate a repository map first.[/dim]\n")
                        continue
                    
                    console.print("\n📦 [bold cyan]Updating repository map...[/bold cyan]")
                    console.print(f"[dim]Scanning working directory for new files: {get_user_working_dir()}[/dim]\n")

                    try:
                        # Read existing repomap content
                        with open(repomap_path, 'r', encoding='utf-8') as f:
                            existing_repomap = f.read()
                        
                        # Extract existing file paths from the repomap
                        # Look for patterns like "### path/to/file.py" in the existing content
                        existing_paths = set()
                        for match in re.finditer(r'^### ([^\s(]+)', existing_repomap, re.MULTILINE):
                            existing_paths.add(match.group(1))
                        
                        # Collect all current source files
                        console.print("[yellow]📂 Collecting source code files...[/yellow]")
                        all_source_files = collect_source_files(get_user_working_dir())
                        
                        # Filter to only new files
                        new_files = [f for f in all_source_files if f['path'] not in existing_paths]
                        
                        if not new_files:
                            console.print("\n[green]✓ No new files found. Repository map is up to date![/green]\n")
                            continue
                            
                        console.print(f"[green]✓ Found {len(new_files)} new source files to add[/green]")
                        for f in new_files[:10]:  # Show first 10
                            console.print(f"[dim]  + {f['path']}[/dim]")
                        if len(new_files) > 10:
                            console.print(f"[dim]  ... and {len(new_files) - 10} more[/dim]")
                        console.print()
                        
                        # Generate updated directory tree
                        console.print("[yellow]🌳 Generating directory tree...[/yellow]")
                        tree_output = generate_tree(get_user_working_dir(), max_depth=5)
                        console.print(f"[green]✓ Directory tree generated[/green]\n")
                        
                        # Generate the update prompt
                        console.print("[yellow]🤖 Updating repository map with LLM...[/yellow]")
                        update_prompt = generate_repomap_update_prompt(new_files, existing_repomap, tree_output=tree_output)

                        # Use a separate chat manager
                        update_chat_manager = ChatManager(system_prompt=config.get_system_prompt())
                        update_chat_manager.add_user_message(update_prompt)
                        messages = update_chat_manager.get_messages()
                        
                        spinner = Spinner("dots", text="[dim]Updating repository map...[/dim]", style="cyan")
                        
                        with Live(spinner, console=console, refresh_per_second=10):
                            if stream:
                                full_response = ""
                                for chunk in ollama_client.chat(
                                    messages=messages,
                                    stream=True,
                                    temperature=temperature
                                ):
                                    full_response += chunk
                            else:
                                response = ollama_client.chat(
                                    messages=messages,
                                    stream=False,
                                    temperature=temperature
                                )
                                full_response = response.get('message', {}).get('content', '')
                        
                        # Prepend the updated tree to the repomap output
                        updated_repomap_content = f"""# Repository Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""

                        # Write the updated repomap to file
                        with open(repomap_path, 'w', encoding='utf-8') as f:
                            f.write(updated_repomap_content)
                        
                        console.print(f"\n[bold green]✓ Repository map updated successfully![/bold green]")
                        console.print(f"[cyan]📄 Updated: {repomap_path}[/cyan]")
                        console.print(f"[dim]Added {len(new_files)} new file(s)[/dim]\n")
                        
                        # Show preview
                        preview_lines = updated_repomap_content.split('\n')[:20]
                        console.print("[dim]Preview:[/dim]")
                        console.print(CustomMarkdown('\n'.join(preview_lines) + '\n...', code_theme="monokai"))
                        console.print()
                        
                    except Exception as e:
                        console.print(f"\n❌ [red]Error updating repository map: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    continue

                # Handle /datamap create command
                if user_input_normalized.lower().startswith('datamap create'):
                    # Check if datamap_create is disabled (e.g., when using tinyollama)
                    if llm_checker.is_feature_disabled('datamap_create'):
                        console.print("\n⚠️  [yellow]/datamap create is disabled when using tinyollama fallback.[/yellow]")
                        console.print("[dim]This feature requires a larger model for reliable data analysis.[/dim]")
                        console.print("[dim]Connect to the primary Ollama server to use this feature.[/dim]\n")
                        continue

                    # Parse command arguments
                    args_str = user_input_normalized[14:].strip()  # Everything after "datamap create"
                    
                    # Parse flags
                    with_files = '--with-files' in args_str or '--files-only' in args_str
                    with_pg = '--with-pg' in args_str
                    files_only = '--files-only' in args_str
                    
                    # Extract PostgreSQL connection string if provided
                    pg_connection = None
                    if with_pg:
                        # Look for the connection string after --with-pg
                        pg_match = re.search(r'--with-pg\s+([^\s]+)', args_str)
                        if pg_match:
                            pg_connection = pg_match.group(1)
                        else:
                            console.print("\n❌ [red]--with-pg requires a connection string: --with-pg username:password@host:port/database[/red]\n")
                            continue
                    
                    # If no flags provided, default to files only
                    if not with_files and not with_pg and not files_only:
                        files_only = True
                        with_files = True
                    
                    console.print("\n📊 [bold cyan]Creating data map...[/bold cyan]")
                    console.print(f"[dim]Scanning working directory: {get_user_working_dir()}[/dim]")
                    if with_files or files_only:
                        console.print("[dim]  - Scanning for data files (CSV, JSON, Excel)[/dim]")
                    if with_pg and pg_connection:
                        console.print(f"[dim]  - Connecting to PostgreSQL[/dim]")
                    console.print()

                    try:
                        data_sources = []
                        pg_signature = None
                        code_files = []
                        
                        # Collect data files if requested
                        if with_files or files_only:
                            console.print("[yellow]📂 Collecting data files...[/yellow]")
                            data_sources = collect_data_files(get_user_working_dir())
                            
                            if data_sources:
                                console.print(f"[green]✓ Found {len(data_sources)} data files[/green]")
                                # Show summary of file types
                                extensions = {}
                                for source in data_sources:
                                    ext = source.get('extension', 'unknown')
                                    extensions[ext] = extensions.get(ext, 0) + 1
                                for ext, count in extensions.items():
                                    console.print(f"[dim]  - {ext}: {count} file(s)[/dim]")
                            else:
                                console.print("[yellow]⚠️  No data files found in working directory[/yellow]")
                        
                        # Connect to PostgreSQL if requested
                        if with_pg and pg_connection:
                            console.print("\n[yellow]🐘 Connecting to PostgreSQL database...[/yellow]")
                            pg_signature = get_postgresql_signature(pg_connection)
                            
                            if 'error' in pg_signature:
                                console.print(f"[yellow]⚠️  PostgreSQL error: {pg_signature['error']}[/yellow]")
                            else:
                                tables_count = len(pg_signature.get('tables', []))
                                if 'database_signatures' in pg_signature:
                                    total_tables = sum(len(db.get('tables', [])) for db in pg_signature.get('database_signatures', []))
                                    console.print(f"[green]✓ Connected to PostgreSQL ({len(pg_signature.get('databases', []))} databases, {total_tables} tables)[/green]")
                                else:
                                    console.print(f"[green]✓ Connected to PostgreSQL ({tables_count} tables)[/green]")
                        
                        # Check if we have any data to process
                        if not data_sources and (not pg_signature or 'error' in pg_signature):
                            console.print("\n❌ [red]No data sources found to create data map.[/red]\n")
                            continue
                        
                        # Collect code files for cross-reference
                        console.print("\n[yellow]📝 Collecting code files for cross-reference...[/yellow]")
                        code_files = collect_source_files(get_user_working_dir(), max_files=50)
                        console.print(f"[green]✓ Found {len(code_files)} code files[/green]")
                        
                        # Generate directory tree
                        console.print("\n[yellow]🌳 Generating directory tree...[/yellow]")
                        tree_output = generate_tree(get_user_working_dir(), max_depth=5)
                        console.print(f"[green]✓ Directory tree generated[/green]\n")
                        
                        # Generate the LLM prompt
                        console.print("[yellow]🤖 Generating data map with LLM...[/yellow]")
                        datamap_prompt = generate_datamap_prompt(
                            data_sources,
                            pg_signature=pg_signature,
                            code_files=code_files,
                            tree_output=tree_output
                        )

                        # Check prompt size and warn if it's very large
                        prompt_size = len(datamap_prompt)
                        estimated_tokens = prompt_size // 4
                        if prompt_size > 500_000:
                            console.print(f"[yellow]⚠️  Warning: Large prompt size ({prompt_size:,} chars, ~{estimated_tokens:,} tokens)[/yellow]")
                            console.print(f"[yellow]   This may exceed token limits for some LLMs or cause slower processing.[/yellow]\n")

                        # Use a separate chat manager for datamap generation
                        datamap_chat_manager = ChatManager(system_prompt=config.get_system_prompt())
                        datamap_chat_manager.add_user_message(datamap_prompt)
                        messages = datamap_chat_manager.get_messages()
                        
                        spinner = Spinner("dots", text="[dim]Analyzing data sources...[/dim]", style="cyan")
                        
                        with Live(spinner, console=console, refresh_per_second=10):
                            if stream:
                                full_response = ""
                                for chunk in ollama_client.chat(
                                    messages=messages,
                                    stream=True,
                                    temperature=temperature
                                ):
                                    full_response += chunk
                            else:
                                response = ollama_client.chat(
                                    messages=messages,
                                    stream=False,
                                    temperature=temperature
                                )
                                full_response = response.get('message', {}).get('content', '')
                        
                        # Prepend the tree to the datamap output
                        datamap_content = f"""# Data Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""

                        # Write the datamap to file
                        datamap_path = os.path.join(get_user_working_dir(), '.datamap')
                        with open(datamap_path, 'w', encoding='utf-8') as f:
                            f.write(datamap_content)
                        
                        console.print(f"\n[bold green]✓ Data map created successfully![/bold green]")
                        console.print(f"[cyan]📄 Saved to: {datamap_path}[/cyan]\n")
                        
                        # Show preview
                        preview_lines = datamap_content.split('\n')[:20]
                        console.print("[dim]Preview:[/dim]")
                        console.print(CustomMarkdown('\n'.join(preview_lines) + '\n...', code_theme="monokai"))
                        console.print()
                        
                    except Exception as e:
                        console.print(f"\n❌ [red]Error creating data map: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    continue

                # Handle /datamap load command
                if user_input_normalized.lower() == 'datamap load':
                    datamap_path = os.path.join(get_user_working_dir(), '.datamap')
                    
                    if not os.path.exists(datamap_path):
                        console.print(f"\n❌ [red]No .datamap file found at: {datamap_path}[/red]")
                        console.print("[dim]Use '/datamap create' to generate a data map first.[/dim]\n")
                        continue
                    
                    console.print(f"\n📂 [cyan]Loading data map: {datamap_path}[/cyan]")
                    
                    try:
                        # Get session ID if active
                        session_id = session_manager.get_session_id() if session_manager.is_active() else None
                        
                        # Load the datamap into context
                        result = run_async(load_datamap_to_context(
                            mcp_client,
                            '.datamap',
                            get_user_working_dir(),
                            session_id
                        ))
                        
                        if result.get('status') == 'success':
                            content_size = result.get('content_size', 0)
                            console.print(f"[bold green]✓ Data map loaded into context![/bold green]")
                            console.print(f"[dim]  Size: {content_size:,} bytes[/dim]")
                            if session_id:
                                console.print(f"[dim]  Session: {session_id[:16]}...[/dim]")
                            else:
                                console.print(f"[dim]  Session: temporary (start a session for persistence)[/dim]")
                            console.print()
                        else:
                            error_msg = result.get('message', 'Unknown error')
                            console.print(f"[yellow]⚠️  Warning: {error_msg}[/yellow]")
                            console.print("[dim]The datamap file may still be usable.[/dim]\n")
                            
                    except Exception as e:
                        console.print(f"\n❌ [red]Error loading data map: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    continue

                # Handle /datamap update command
                if user_input_normalized.lower().startswith('datamap update'):
                    # Check if datamap_update is disabled (e.g., when using tinyollama)
                    if llm_checker.is_feature_disabled('datamap_update'):
                        console.print("\n⚠️  [yellow]/datamap update is disabled when using tinyollama fallback.[/yellow]")
                        console.print("[dim]This feature requires a larger model for reliable data analysis.[/dim]")
                        console.print("[dim]Connect to the primary Ollama server to use this feature.[/dim]\n")
                        continue

                    datamap_path = os.path.join(get_user_working_dir(), '.datamap')
                    
                    if not os.path.exists(datamap_path):
                        console.print(f"\n❌ [red]No .datamap file found at: {datamap_path}[/red]")
                        console.print("[dim]Use '/datamap create' to generate a data map first.[/dim]\n")
                        continue
                    
                    # Parse command arguments
                    args_str = user_input_normalized[14:].strip()  # Everything after "datamap update"
                    
                    # Parse flags
                    with_files = '--with-files' in args_str
                    with_pg = '--with-pg' in args_str
                    
                    # If no flags provided, default to files only
                    if not with_files and not with_pg:
                        with_files = True
                    
                    # Extract PostgreSQL connection string if provided
                    pg_connection = None
                    if with_pg:
                        pg_match = re.search(r'--with-pg\s+([^\s]+)', args_str)
                        if pg_match:
                            pg_connection = pg_match.group(1)
                        else:
                            console.print("\n❌ [red]--with-pg requires a connection string: --with-pg username:password@host:port/database[/red]\n")
                            continue
                    
                    console.print("\n📊 [bold cyan]Updating data map...[/bold cyan]")
                    console.print(f"[dim]Scanning working directory for new data sources: {get_user_working_dir()}[/dim]")
                    if with_files:
                        console.print("[dim]  - Scanning for new data files (CSV, JSON, Excel)[/dim]")
                    if with_pg and pg_connection:
                        console.print(f"[dim]  - Connecting to PostgreSQL for new tables[/dim]")
                    console.print()

                    try:
                        # Read existing datamap content
                        with open(datamap_path, 'r', encoding='utf-8') as f:
                            existing_datamap = f.read()
                        
                        # Extract existing file paths from the datamap
                        existing_paths = set()
                        for match in re.finditer(r'^### ([^\s(]+)', existing_datamap, re.MULTILINE):
                            existing_paths.add(match.group(1))
                        
                        new_data_sources = []
                        new_pg_signature = None
                        code_files = []
                        
                        # Collect new data files if requested
                        if with_files:
                            console.print("[yellow]📂 Collecting data files...[/yellow]")
                            all_data_files = collect_data_files(get_user_working_dir())
                            
                            # Filter to only new files
                            new_data_sources = [f for f in all_data_files if f.get('path') not in existing_paths]
                            
                            if new_data_sources:
                                console.print(f"[green]✓ Found {len(new_data_sources)} new data files[/green]")
                                for source in new_data_sources[:5]:
                                    console.print(f"[dim]  + {source.get('path', 'unknown')}[/dim]")
                                if len(new_data_sources) > 5:
                                    console.print(f"[dim]  ... and {len(new_data_sources) - 5} more[/dim]")
                            else:
                                console.print("[dim]  No new data files found[/dim]")
                        
                        # Connect to PostgreSQL if requested
                        if with_pg and pg_connection:
                            console.print("\n[yellow]🐘 Connecting to PostgreSQL database...[/yellow]")
                            new_pg_signature = get_postgresql_signature(pg_connection)
                            
                            if 'error' in new_pg_signature:
                                console.print(f"[yellow]⚠️  PostgreSQL error: {new_pg_signature['error']}[/yellow]")
                            else:
                                tables_count = len(new_pg_signature.get('tables', []))
                                if 'database_signatures' in new_pg_signature:
                                    total_tables = sum(len(db.get('tables', [])) for db in new_pg_signature.get('database_signatures', []))
                                    console.print(f"[green]✓ Connected to PostgreSQL ({len(new_pg_signature.get('databases', []))} databases, {total_tables} tables)[/green]")
                                else:
                                    console.print(f"[green]✓ Connected to PostgreSQL ({tables_count} tables)[/green]")
                        
                        # Check if we have any new data to process
                        if not new_data_sources and (not new_pg_signature or 'error' in new_pg_signature):
                            console.print("\n[green]✓ No new data sources found. Data map is up to date![/green]\n")
                            continue
                        
                        # Collect code files for cross-reference
                        console.print("\n[yellow]📝 Collecting code files for cross-reference...[/yellow]")
                        code_files = collect_source_files(get_user_working_dir(), max_files=50)
                        console.print(f"[green]✓ Found {len(code_files)} code files[/green]")
                        
                        # Generate updated directory tree
                        console.print("\n[yellow]🌳 Generating directory tree...[/yellow]")
                        tree_output = generate_tree(get_user_working_dir(), max_depth=5)
                        console.print(f"[green]✓ Directory tree generated[/green]\n")
                        
                        # Generate the update prompt
                        console.print("[yellow]🤖 Updating data map with LLM...[/yellow]")
                        update_prompt = generate_datamap_update_prompt(
                            new_data_sources,
                            new_pg_signature=new_pg_signature,
                            existing_datamap=existing_datamap,
                            code_files=code_files,
                            tree_output=tree_output
                        )

                        # Use a separate chat manager
                        update_chat_manager = ChatManager(system_prompt=config.get_system_prompt())
                        update_chat_manager.add_user_message(update_prompt)
                        messages = update_chat_manager.get_messages()
                        
                        spinner = Spinner("dots", text="[dim]Updating data map...[/dim]", style="cyan")
                        
                        with Live(spinner, console=console, refresh_per_second=10):
                            if stream:
                                full_response = ""
                                for chunk in ollama_client.chat(
                                    messages=messages,
                                    stream=True,
                                    temperature=temperature
                                ):
                                    full_response += chunk
                            else:
                                response = ollama_client.chat(
                                    messages=messages,
                                    stream=False,
                                    temperature=temperature
                                )
                                full_response = response.get('message', {}).get('content', '')
                        
                        # Prepend the updated tree to the datamap output
                        updated_datamap_content = f"""# Data Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""

                        # Write the updated datamap to file
                        with open(datamap_path, 'w', encoding='utf-8') as f:
                            f.write(updated_datamap_content)
                        
                        new_count = len(new_data_sources)
                        if new_pg_signature and 'error' not in new_pg_signature:
                            tables_count = len(new_pg_signature.get('tables', []))
                            if 'database_signatures' in new_pg_signature:
                                tables_count = sum(len(db.get('tables', [])) for db in new_pg_signature.get('database_signatures', []))
                            new_count += tables_count
                        
                        console.print(f"\n[bold green]✓ Data map updated successfully![/bold green]")
                        console.print(f"[cyan]📄 Updated: {datamap_path}[/cyan]")
                        console.print(f"[dim]Added {new_count} new data source(s)[/dim]\n")
                        
                        # Show preview
                        preview_lines = updated_datamap_content.split('\n')[:20]
                        console.print("[dim]Preview:[/dim]")
                        console.print(CustomMarkdown('\n'.join(preview_lines) + '\n...', code_theme="monokai"))
                        console.print()
                        
                    except Exception as e:
                        console.print(f"\n❌ [red]Error updating data map: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    continue

                # Handle /code command - simplified version
                if user_input_normalized.lower().startswith('code '):
                    # Check if code mode is disabled (e.g., when using tinyollama)
                    if llm_checker.is_feature_disabled('code_mode'):
                        console.print("\n⚠️  [yellow]/code command is disabled when using tinyollama fallback.[/yellow]")
                        console.print("[dim]This feature requires a larger model for reliable code generation.[/dim]")
                        console.print("[dim]Connect to the primary Ollama server to use this feature.[/dim]\n")
                        continue
                        
                    prompt_text = user_input_normalized[5:].strip()  # Extract text after "code "

                    if not prompt_text:
                        console.print("\n❌ [red]Usage: /code <prompt_sentences>[/red]")
                        console.print("[dim]Example: /code write Python code to calculate fibonacci(20) and save to testing/fib.py then run testing/fib.py[/dim]\n")
                        continue

                    # Extract ALL @ references from the original prompt for context
                    at_references = re.findall(r'@([\w\-./]+)', prompt_text)
                    debug_print(f"Extracted @ references from prompt: {at_references}", icon="📎")

                    # Auto-start session if not active
                    if not session_manager.is_active():
                        console.print("\n[cyan]ℹ️  Starting a new session for /code command...[/cyan]")
                        session_manager.start_session(working_dir=get_user_working_dir())

                    session_id = session_manager.get_session_id()

                    # Load .repomap file into context if it exists and not already loaded in this session
                    repomap_path = os.path.join(get_user_working_dir(), '.repomap')
                    repomap_loaded_key = f'repomap_loaded_{repomap_path}'
                    if os.path.exists(repomap_path) and not session_manager.session_metadata.get(repomap_loaded_key):
                        console.print("[cyan]📦 Loading repository map into context...[/cyan]")
                        try:
                            repomap_result = run_async(load_repomap_to_context(
                                mcp_client,
                                '.repomap',
                                get_user_working_dir(),
                                session_id
                            ))
                            if repomap_result.get('status') == 'success':
                                console.print("[green]✓ Repository map loaded[/green]")
                                # Mark repomap as loaded for this session
                                session_manager.session_metadata[repomap_loaded_key] = True
                            else:
                                debug_print(f"Repomap load warning: {repomap_result.get('message')}", icon="⚠️")
                        except Exception as e:
                            debug_print(f"Failed to load repomap: {e}", icon="⚠️")

                    # Load .datamap file into context if it exists and not already loaded in this session
                    datamap_path = os.path.join(get_user_working_dir(), '.datamap')
                    datamap_loaded_key = f'datamap_loaded_{datamap_path}'
                    if os.path.exists(datamap_path) and not session_manager.session_metadata.get(datamap_loaded_key):
                        console.print("[cyan]📊 Loading data map into context...[/cyan]")
                        try:
                            datamap_result = run_async(load_datamap_to_context(
                                mcp_client,
                                '.datamap',
                                get_user_working_dir(),
                                session_id
                            ))
                            if datamap_result.get('status') == 'success':
                                console.print("[green]✓ Data map loaded[/green]")
                                # Mark datamap as loaded for this session
                                session_manager.session_metadata[datamap_loaded_key] = True
                            else:
                                debug_print(f"Datamap load warning: {datamap_result.get('message')}", icon="⚠️")
                        except Exception as e:
                            debug_print(f"Failed to load datamap: {e}", icon="⚠️")

                    # Store @ references in session metadata for access by all tools
                    if at_references:
                        session_manager.session_metadata['at_references'] = at_references
                        session_manager.session_metadata['working_dir'] = get_user_working_dir()
                        debug_print(f"Stored @ references in session context: {at_references}", icon="📎")

                    console.print(f"\n🎯 [bold cyan]Processing code command...[/bold cyan]")
                    console.print(f"[dim]Prompt: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}[/dim]\n")

                    try:
                        # Call the simplified code-command endpoint to get steps
                        console.print("📝 [cyan]Analyzing prompt and creating execution steps...[/cyan]")
                        response = requests.post(
                            f"{POSTGRES_API_URL}/mcp-tools/code-command-simple",
                            json={
                                "text": prompt_text,
                                "session_id": session_id
                            },
                            headers={"Content-Type": "application/json"},
                            timeout=180
                        )

                        if response.status_code != 200:
                            console.print(f"\n❌ [red]Failed to process code command: HTTP {response.status_code}[/red]")
                            console.print(f"[dim]{response.text}[/dim]\n")
                            continue

                        data = response.json()

                        if data.get('status') != 'success':
                            console.print(f"\n❌ [red]Code command failed: {data.get('message')}[/red]\n")
                            continue

                        # Get the execution steps
                        steps = data.get('steps', [])

                        if not steps:
                            console.print("\n⚠️  [yellow]No execution steps generated[/yellow]\n")
                            continue

                        console.print(f"✓ [green]Generated {len(steps)} execution steps[/green]\n")

                        # Show the steps
                        console.print("📋 [bold]Execution Steps:[/bold]")
                        for i, step in enumerate(steps, 1):
                            console.print(f"  {i}. {step}")
                        console.print()

                        # Execute each step iteratively with tool matching
                        console.print("⚡ [cyan]Executing steps with tool matching...[/cyan]\n")

                        for i, step in enumerate(steps, 1):
                            console.print(f"[bold]Step {i}/{len(steps)}:[/bold] {step}")
                            console.print()

                            try:
                                # Step 1: Match this step with the best MCP tool
                                debug_print(f"Matching step {i} with tools...", icon="🔍")

                                match_response = requests.post(
                                    f"{POSTGRES_API_URL}/mcp-tools/retrieve",
                                    json={
                                        "prompts": [step],
                                        "threshold": 0.3,
                                        "context_references": at_references  # Pass @ references for parameter injection
                                    },
                                    headers={"Content-Type": "application/json"},
                                    timeout=30
                                )

                                if match_response.status_code == 200:
                                    match_data = match_response.json()
                                    results = match_data.get('results', [])

                                    if results and results[0].get('best_match'):
                                        best_match = results[0]['best_match']
                                        tool_name = best_match.get('tool_name')
                                        mcp_name = best_match.get('mcp_name', 'coder')
                                        similarity = best_match.get('similarity', 0)

                                        # Valid coding tools for /code command execution
                                        valid_coding_tools = [
                                            'run_python_code', 'run_r_code', 'detect_code',
                                            'write_python_code', 'write_r_code',
                                            'edit_python_code', 'edit_r_code',
                                            'add_file_context', 'add_directory_context',
                                            'verify_file_modifications'
                                        ]
                                        
                                        # Meta-tools should not be executed directly in /code steps
                                        meta_tools = ['retrieve_all_tools', 'roll_the_dice', 'spin_the_roulette']
                                        
                                        if tool_name in meta_tools:
                                            console.print(f"  ⚠️  [yellow]Skipping meta-tool '{tool_name}' (not suitable for direct execution)[/yellow]\n")
                                            continue
                                        
                                        if tool_name not in valid_coding_tools:
                                            console.print(f"  ⚠️  [yellow]Matched invalid tool '{tool_name}', skipping step[/yellow]\n")
                                            debug_print(f"Invalid tool matched: {tool_name} (similarity: {similarity})", icon="⚠️")
                                            continue

                                        console.print(f"  🔧 [cyan]Matched tool:[/cyan] {tool_name} [dim](similarity: {similarity:.2f})[/dim]")

                                        # Step 2: For code generation tools, use LLM to generate code first
                                        code_generation_tools = ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code', 'run_python_code', 'run_r_code']

                                        if tool_name in code_generation_tools:
                                            # Check if there's a file path with @ prefix
                                            file_match = re.search(r'@([\w\-./]+\.(?:py|r|R))', step)
                                            file_path = file_match.group(1) if file_match else None

                                            # For run_python_code/run_r_code, check if we should read existing file
                                            if tool_name in ['run_python_code', 'run_r_code'] and file_path:
                                                # Check if prompt is about running an existing file
                                                # More flexible: check if it mentions "file" or "script" with @
                                                step_lower = step.lower()
                                                is_run_file = (
                                                    ('file' in step_lower and '@' in step_lower) or
                                                    ('script' in step_lower and '@' in step_lower) or
                                                    'run @' in step_lower or
                                                    'execute @' in step_lower
                                                )

                                                if is_run_file:
                                                    console.print(f"  📂 [yellow]Reading file: {file_path}[/yellow]")

                                                    # Read the file
                                                    try:
                                                        with open(file_path, 'r') as f:
                                                            code = f.read()
                                                        console.print(f"  ✓ [green]File read ({len(code)} chars)[/green]\n")

                                                        # Build parameters
                                                        extracted_params = best_match.get('extracted_params', {})
                                                        extracted_params['code'] = code
                                                        # Remove file_path - run_python_code/run_r_code don't accept it
                                                        if 'file_path' in extracted_params:
                                                            extracted_params.pop('file_path')
                                                            debug_print(f"Removed file_path from params for {tool_name}", icon="🔧")
                                                    except FileNotFoundError:
                                                        console.print(f"  ❌ [red]File not found: {file_path}[/red]\n")
                                                        continue
                                                    except Exception as e:
                                                        console.print(f"  ❌ [red]Error reading file: {str(e)}[/red]\n")
                                                        continue
                                                else:
                                                    # Generate code with LLM
                                                    console.print(f"  🤖 [yellow]Generating code with LLM...[/yellow]")

                                                    chat_manager.add_user_message(step)
                                                    messages = chat_manager.get_messages()

                                                    spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                                                    with Live(spinner, console=console, refresh_per_second=10):
                                                        if stream:
                                                            full_response = ""
                                                            for chunk in ollama_client.chat(
                                                                messages=messages,
                                                                stream=True,
                                                                temperature=temperature
                                                            ):
                                                                full_response += chunk
                                                        else:
                                                            response = ollama_client.chat(
                                                                messages=messages,
                                                                stream=False,
                                                                temperature=temperature
                                                            )
                                                            full_response = response.get('message', {}).get('content', '')

                                                    chat_manager.add_assistant_message(full_response)

                                                    detected = mcp_client.detect_code(full_response)

                                                    if not detected:
                                                        console.print(f"  ⚠️  [yellow]No code detected in LLM response, skipping tool execution[/yellow]\n")
                                                        continue

                                                    code = detected['code']
                                                    console.print(f"  ✓ [green]Code generated ({len(code)} chars)[/green]\n")

                                                    extracted_params = best_match.get('extracted_params', {})
                                                    extracted_params['code'] = code
                                                    # Remove file_path for run_python_code/run_r_code
                                                    if tool_name in ['run_python_code', 'run_r_code'] and 'file_path' in extracted_params:
                                                        extracted_params.pop('file_path')
                                                        debug_print(f"Removed file_path from params for {tool_name}", icon="🔧")
                                            else:
                                                # For write/edit tools or run without file path, generate code with LLM
                                                console.print(f"  🤖 [yellow]Generating code with LLM...[/yellow]")

                                                # For edit tools, read the original file to provide context
                                                original_file_content = None
                                                if tool_name in ['edit_python_code', 'edit_r_code'] and file_path:
                                                    try:
                                                        if os.path.exists(file_path):
                                                            with open(file_path, 'r') as f:
                                                                original_file_content = f.read()
                                                            console.print(f"  📂 [dim]Read original file: {file_path} ({len(original_file_content)} chars)[/dim]")
                                                    except Exception as e:
                                                        console.print(f"  ⚠️  [yellow]Could not read original file: {e}[/yellow]")

                                                # Build the prompt with original file context for edits
                                                if original_file_content:
                                                    line_count = len(original_file_content.splitlines())
                                                    # Determine language based on tool name
                                                    is_r_code = tool_name == 'edit_r_code'
                                                    lang_name = "R" if is_r_code else "Python"
                                                    code_block_marker = "r" if is_r_code else "python"
                                                    comment_prefix = "#" if is_r_code else "#"  # Both use # for comments
                                                    
                                                    edit_prompt = f"""TASK: Edit the {lang_name} file below. Make ONLY the specific changes requested.

FILE TO EDIT: {file_path} ({line_count} lines)

=== ORIGINAL FILE START ===
{original_file_content}
=== ORIGINAL FILE END ===

REQUESTED CHANGES: {step}

CRITICAL RULES:
1. Output the COMPLETE file with ALL {line_count} lines (or close to it)
2. DO NOT remove, truncate, or summarize any existing functions, classes, or code
3. DO NOT add comments like "{comment_prefix} Rest of your methods..." or "{comment_prefix} ... existing code ..."
4. DO NOT change imports, class structure, or method signatures unless specifically requested
5. Make ONLY the minimal changes needed to fulfill the request
6. Preserve all docstrings, comments, and formatting

Wrap your output in a markdown code block like this:
```{code_block_marker}
<the complete updated file content here>
```"""
                                                    chat_manager.add_user_message(edit_prompt)
                                                else:
                                                    chat_manager.add_user_message(step)
                                                
                                                messages = chat_manager.get_messages()

                                                spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                                                # For edit operations with original file, use coder model and allow more tokens
                                                edit_num_predict = 8192 if original_file_content else None
                                                edit_model = config.get_coder_model() if original_file_content else None

                                                with Live(spinner, console=console, refresh_per_second=10):
                                                    if stream:
                                                        full_response = ""
                                                        for chunk in ollama_client.chat(
                                                            messages=messages,
                                                            stream=True,
                                                            temperature=temperature,
                                                            num_predict=edit_num_predict,
                                                            model=edit_model
                                                        ):
                                                            full_response += chunk
                                                    else:
                                                        response = ollama_client.chat(
                                                            messages=messages,
                                                            stream=False,
                                                            temperature=temperature,
                                                            num_predict=edit_num_predict,
                                                            model=edit_model
                                                        )
                                                        full_response = response.get('message', {}).get('content', '')

                                                chat_manager.add_assistant_message(full_response)

                                                detected = mcp_client.detect_code(full_response)

                                                if not detected:
                                                    console.print(f"  ⚠️  [yellow]No code detected in LLM response, skipping tool execution[/yellow]\n")
                                                    continue

                                                code = detected['code']
                                                console.print(f"  ✓ [green]Code generated ({len(code)} chars)[/green]\n")

                                                extracted_params = best_match.get('extracted_params', {})
                                                extracted_params['code'] = code

                                            # Add file_path if extracted from @ prefix (only for write/edit tools)
                                            if file_path and tool_name in ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code']:
                                                extracted_params['file_path'] = file_path
                                            elif 'file_path' not in extracted_params and tool_name in ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code']:
                                                console.print(f"  ⚠️  [yellow]No file path specified, skipping {tool_name}[/yellow]\n")
                                                continue
                                        else:
                                            # Non-code-generation tools: use extracted params
                                            extracted_params = best_match.get('extracted_params', {})
                                            
                                            # Strip @ prefix from file_path if present (LLM may include it)
                                            if 'file_path' in extracted_params and extracted_params['file_path']:
                                                fp = extracted_params['file_path']
                                                if fp.startswith('@'):
                                                    extracted_params['file_path'] = fp[1:]
                                            if 'directory_path' in extracted_params and extracted_params['directory_path']:
                                                dp = extracted_params['directory_path']
                                                if dp.startswith('@'):
                                                    extracted_params['directory_path'] = dp[1:]

                                        # Add working_dir if not present
                                        if 'working_dir' not in extracted_params:
                                            extracted_params['working_dir'] = get_user_working_dir()

                                        # Add session_id for tools that need it
                                        if 'session_id' not in extracted_params and session_manager.is_active():
                                            extracted_params['session_id'] = session_id

                                        debug_print(f"Calling MCP tool: {tool_name} with params: {list(extracted_params.keys())}", icon="⚙️")
                                        console.print(f"  ⚡ [yellow]Executing {tool_name}...[/yellow]\n")

                                        # Step 3: Call the MCP tool
                                        result = run_async(mcp_client.call_tool(
                                            mcp_name=mcp_name,
                                            tool_name=tool_name,
                                            arguments=extracted_params
                                        ))

                                        # Step 4: Display result
                                        try:
                                            result_data = json.loads(result)

                                            if result_data.get('status') == 'success':
                                                console.print(f"  ✓ [green]Success[/green]")

                                                # Show relevant output
                                                if 'stdout' in result_data and result_data['stdout']:
                                                    console.print(f"\n  [dim]Output:[/dim]")
                                                    console.print(f"  {result_data['stdout']}")

                                                if 'stderr' in result_data and result_data['stderr']:
                                                    console.print(f"\n  [yellow]Warnings:[/yellow]")
                                                    console.print(f"  {result_data['stderr']}")

                                                if 'file_path' in result_data:
                                                    console.print(f"  📄 [cyan]File:[/cyan] {result_data['file_path']}")

                                                if 'message' in result_data:
                                                    console.print(f"  💬 {result_data['message']}")
                                            else:
                                                error_msg = result_data.get('message') or result_data.get('error') or 'Unknown error'
                                                console.print(f"  ✗ [red]Failed:[/red] {error_msg}")
                                                # Log full result for debugging
                                                debug_print(f"Full error result: {json.dumps(result_data, indent=2)}", icon="🔍")

                                        except json.JSONDecodeError as e:
                                            # Plain text result (might be an error message)
                                            console.print(f"  📄 [dim]{result}[/dim]")
                                            debug_print(f"JSON decode error: {e}. Raw result: {result}", icon="⚠️")

                                        console.print()

                                        # Add to session
                                        if session_manager.is_active():
                                            session_manager.add_interaction(
                                                prompt=step,
                                                response=result,
                                                metadata={'model': ollama_client.model, 'step': i, 'tool': tool_name}
                                            )
                                            # Auto-save session
                                            try:
                                                session_manager.save_to_redis()
                                            except Exception as e:
                                                debug_print(f"Failed to auto-save session: {e}", icon="⚠️")

                                    else:
                                        # No tool matched - fall back to LLM
                                        console.print(f"  ⚠️  [yellow]No matching tool found, using LLM...[/yellow]\n")

                                        chat_manager.add_user_message(step)
                                        messages = chat_manager.get_messages()

                                        spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                                        with Live(spinner, console=console, refresh_per_second=10):
                                            if stream:
                                                full_response = ""
                                                for chunk in ollama_client.chat(
                                                    messages=messages,
                                                    stream=True,
                                                    temperature=temperature
                                                ):
                                                    full_response += chunk
                                            else:
                                                response = ollama_client.chat(
                                                    messages=messages,
                                                    stream=False,
                                                    temperature=temperature
                                                )
                                                full_response = response.get('message', {}).get('content', '')

                                        console.print("[bold cyan]▶[/bold cyan]")
                                        console.print(CustomMarkdown(full_response, code_theme="monokai"))
                                        console.print()

                                        chat_manager.add_assistant_message(full_response)

                                        if session_manager.is_active():
                                            session_manager.add_interaction(
                                                prompt=step,
                                                response=full_response,
                                                metadata={'model': ollama_client.model, 'step': i}
                                            )
                                            # Auto-save session
                                            try:
                                                session_manager.save_to_redis()
                                            except Exception as e:
                                                debug_print(f"Failed to auto-save session: {e}", icon="⚠️")

                                else:
                                    console.print(f"  ✗ [red]Failed to match tools (HTTP {match_response.status_code})[/red]\n")

                            except Exception as e:
                                console.print(f"[red]✗ Error in step {i}: {e}[/red]\n")
                                if verbose:
                                    import traceback
                                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
                                # Continue with next step even if this one fails

                        console.print(f"\n✓ [bold green]Completed all {len(steps)} steps[/bold green]\n")

                    except requests.exceptions.Timeout:
                        console.print("\n❌ [red]Request timeout - the command took too long to process[/red]\n")
                    except requests.exceptions.RequestException as e:
                        console.print(f"\n❌ [red]Network error: {e}[/red]\n")
                    except Exception as e:
                        console.print(f"\n❌ [red]Error executing /code command: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")

                    continue

                # Skip empty input
                if not user_input:
                    continue

                # Process @ prefixed file/directory paths
                at_context = extract_at_context(user_input, get_user_working_dir())
                context_added = False

                # Collect file and directory contents to inject into conversation
                injected_context_parts = []

                # Add file contexts to Redis (with session if active)
                session_id = session_manager.get_session_id() if session_manager.is_active() else None

                for file_path in at_context['files']:
                    try:
                        # Add file context using MCP tool
                        args = {
                            'file_path': file_path,
                            'working_dir': get_user_working_dir()
                        }
                        if session_id:
                            args['session_id'] = session_id

                        result = run_async(mcp_client.call_tool('coder', 'add_file_context', args))

                        # Parse result to extract file content
                        if not result:
                            debug_print(f"No result returned from add_file_context for {file_path}", icon="⚠️", style="yellow")
                        elif not result.strip():
                            debug_print(f"Empty result returned from add_file_context for {file_path}", icon="⚠️", style="yellow")
                        else:
                            try:
                                result_data = json.loads(result)
                                if result_data.get('status') == 'success' and result_data.get('content'):
                                    # Add file content to injected context
                                    file_content = result_data['content']
                                    injected_context_parts.append(f"File: {file_path}\n```\n{file_content}\n```")
                                    debug_print(f"Added file context: {file_path}", icon="📄", style="cyan")
                                    context_added = True
                            except json.JSONDecodeError as e:
                                debug_print(f"Failed to parse file context result for {file_path}: {e}", icon="⚠️", style="yellow")
                                debug_print(f"Result was: {result[:200]}...", icon="🔍", style="dim")
                    except Exception as e:
                        debug_print(f"Failed to add file context for {file_path}: {e}", icon="⚠️", style="yellow")

                # Add directory contexts to Redis
                for dir_path in at_context['directories']:
                    try:
                        # Add directory context using MCP tool
                        args = {
                            'dir_path': dir_path,
                            'working_dir': get_user_working_dir()
                        }
                        if session_id:
                            args['session_id'] = session_id

                        result = run_async(mcp_client.call_tool('coder', 'add_directory_context', args))

                        # Parse result to show tree and extract contents
                        try:
                            result_data = json.loads(result)
                            if result_data.get('tree_added'):
                                tree_stats = result_data.get('tree_stats', {})
                                console.print(f"\n[cyan]📁 Directory Structure Added: {dir_path}[/cyan]")
                                console.print(f"[dim]  Files: {tree_stats.get('files', 0)} | Directories: {tree_stats.get('directories', 0)}[/dim]\n")

                                # Add tree structure to injected context
                                tree_output = result_data.get('tree_output', '')
                                if tree_output:
                                    injected_context_parts.append(f"Directory Structure: {dir_path}\n```\n{tree_output}\n```")

                                # Add all file contents from directory
                                files_content = result_data.get('files_content', [])
                                for file_info in files_content:
                                    file_path_rel = file_info.get('path', '')
                                    file_content = file_info.get('content', '')
                                    if file_content:
                                        injected_context_parts.append(f"File: {file_path_rel}\n```\n{file_content}\n```")
                        except Exception as parse_err:
                            debug_print(f"Failed to parse directory result: {parse_err}", icon="⚠️", style="yellow")

                        debug_print(f"Added directory context: {dir_path}", icon="📁", style="cyan")
                        context_added = True
                    except Exception as e:
                        debug_print(f"Failed to add directory context for {dir_path}: {e}", icon="⚠️", style="yellow")

                # Handle non-existing files (these will be targets for write operations)
                target_file = None
                if at_context['non_existing']:
                    # Take the first non-existing file as the target
                    target_file = at_context['non_existing'][0]
                    debug_print(f"Target file for output: {target_file}", icon="🎯", style="magenta")

                    # Warn if multiple new files were specified
                    if len(at_context['non_existing']) > 1:
                        other_files = ', '.join(at_context['non_existing'][1:])
                        console.print(f"[yellow]⚠️  Multiple new files specified. Only '{target_file}' will be created. Ignored: {other_files}[/yellow]")

                # Remove @ prefixed paths from user input for cleaner prompt
                clean_user_input = remove_at_prefixed_paths(user_input)

                # If we removed everything, use original input
                if not clean_user_input:
                    clean_user_input = user_input

                # Inform user about context addition
                if context_added:
                    console.print(f"[dim]✓ Added {len(at_context['files'])} file(s) and {len(at_context['directories'])} directory(ies) to context[/dim]")

                # Get guidance based on similar past prompts
                guidance = get_prompt_guidance(clean_user_input)

                # Get session context if active
                session_context = None
                if session_manager.is_active():
                    session_context = session_manager.get_session_context(max_interactions=5)
                    if session_context:
                        debug_print(f"Session active: {len(session_manager.get_session_history())} interactions in context", icon="📝", style="cyan")

                # Add user message to context (use clean input without @ paths)
                chat_manager.add_user_message(clean_user_input)

                # Get messages and inject guidance if available
                messages = chat_manager.get_messages()

                # Collect all system messages to inject before the user's message
                system_messages_to_inject = []

                # Inject file/directory context from @ prefix
                if injected_context_parts:
                    context_content = "\n\n".join(injected_context_parts)
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': f"The user has provided the following files/directories as context:\n\n{context_content}"
                    })

                # Detect file modification actions (refactor, update, create, etc.)
                action_keywords = ['refactor', 'create', 'update', 'modify', 'edit', 'change', 'rewrite', 'add']
                user_input_lower = clean_user_input.lower()
                has_action = any(keyword in user_input_lower for keyword in action_keywords)

                # If action keywords present with @ prefixed files, instruct to use MCP tools
                if has_action and (at_context['files'] or at_context['non_existing']):
                    tool_instructions = []

                    # Collect all files that need to be modified or created
                    all_files_to_modify = list(at_context['files'])
                    all_files_to_create = list(at_context['non_existing'])

                    # Look for additional files to create mentioned in the prompt (like "create base.py")
                    create_pattern = r'create\s+((?:[\w/]+/)?[\w.]+\.(?:py|r|R))'
                    create_matches = re.findall(create_pattern, user_input_lower)
                    if create_matches:
                        for matched_file in create_matches:
                            # Add to create list if not already present
                            if matched_file not in all_files_to_create and matched_file not in all_files_to_modify:
                                all_files_to_create.append(matched_file)

                    # Build comprehensive instruction with explicit format requirements
                    instruction_parts = []

                    if all_files_to_modify:
                        instruction_parts.append(
                            f"The user wants to MODIFY these existing files: {', '.join(all_files_to_modify)}"
                        )

                    if all_files_to_create:
                        instruction_parts.append(
                            f"The user wants to CREATE these new files: {', '.join(all_files_to_create)}"
                        )

                    if instruction_parts:
                        # Add explicit format instructions
                        format_instruction = """
IMPORTANT: For EACH file you need to create or modify, you MUST use this EXACT format:

file: <full_file_path>
```python
<complete file code here>
```

Example:
file: testing/python_app/models/base.py
```python
class BaseModel:
    pass
```

file: testing/python_app/models/user.py
```python
from .base import BaseModel

class User(BaseModel):
    pass
```

Do NOT just explain the changes - provide the COMPLETE, RUNNABLE code for each file in the format above.
Each file should have its own "file: <path>" line followed by a code block.

VERIFICATION: After modifications, one of the files will be executed to verify the changes work correctly.
Ensure all imports are correct, syntax is valid, and the code runs without errors.
"""
                        full_instruction = "\n".join(instruction_parts) + format_instruction
                        tool_instructions.append(full_instruction)

                    if tool_instructions:
                        system_messages_to_inject.append({
                            'role': 'system',
                            'content': "\n\n".join(tool_instructions)
                        })

                # If target file is specified, instruct LLM to generate code for that file
                if target_file:
                    file_ext = os.path.splitext(target_file)[1]
                    lang = "Python" if file_ext == ".py" else "R" if file_ext in [".R", ".r"] else "appropriate"
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': (
                            f"The user wants to write code to the file: {target_file}. "
                            f"Generate {lang} code in a code block that will be automatically written to this file. "
                            "Provide complete, working code that can be directly written to the file."
                        )
                    })

                # If user asks to run/execute code, instruct LLM not to predict output
                run_keywords = ['run', 'execute', 'exec']
                if any(keyword in clean_user_input.lower() for keyword in run_keywords):
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': (
                            "The user wants to execute code. Provide ONLY the code in a code block. "
                            "Do NOT predict, guess, or show what the output will be. "
                            "The code will be automatically executed and the real output will be displayed to the user."
                        )
                    })

                # Inject session context if available
                if session_context:
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': session_context
                    })

                # Add guidance if available
                if guidance:
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': guidance
                    })
                    debug_print(guidance, icon="🧠", style="magenta")

                # Inject all system messages before the last user message
                if system_messages_to_inject:
                    messages = messages[:-1] + system_messages_to_inject + [messages[-1]]

                # Get AI response
                console.print()  # Add spacing before AI response

                # Get response (stream or not) and collect full response
                if stream:
                    # Show spinner while collecting response
                    full_response = ""
                    spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                    with Live(spinner, console=console, refresh_per_second=10):
                        for chunk in ollama_client.chat(
                            messages=messages,
                            stream=True,
                            temperature=temperature
                        ):
                            full_response += chunk

                    # Render complete response as markdown with custom styling
                    console.print("[bold cyan]▶[/bold cyan]")
                    console.print(CustomMarkdown(full_response, code_theme="monokai"))
                else:
                    # Show spinner while waiting for response
                    spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                    with Live(spinner, console=console, refresh_per_second=10):
                        response = ollama_client.chat(
                            messages=messages,
                            stream=False,
                            temperature=temperature
                        )
                        full_response = response.get('message', {}).get('content', '')

                    # Render response as markdown with custom styling
                    console.print("[bold cyan]▶[/bold cyan]")
                    console.print(CustomMarkdown(full_response, code_theme="monokai"))

                # Add assistant response to context
                chat_manager.add_assistant_message(full_response)

                # Add interaction to session history if session is active
                if session_manager.is_active():
                    session_manager.add_interaction(
                        prompt=user_input,
                        response=full_response,
                        metadata={'model': ollama_client.model, 'temperature': temperature}
                    )

                    # Auto-save session to Redis after each interaction
                    try:
                        session_manager.save_to_redis()
                    except Exception as e:
                        debug_print(f"Failed to auto-save session: {e}", icon="⚠️")

                console.print()  # Extra line for readability

                # Check for code and offer to execute or write to file
                try:
                    if has_action and (at_context['files'] or at_context['non_existing']):
                        # Handle file modifications (refactor, update, create, etc.)
                        mod_result = run_async(handle_file_modifications(
                            mcp_client,
                            full_response,
                            at_context['files'],
                            at_context['non_existing']
                        ))

                        # Offer to verify modifications by running one of the files
                        if mod_result and mod_result.get('affected_files'):
                            affected_files = mod_result['affected_files']
                            runnable_files = [f for f in affected_files if f.endswith(('.py', '.r', '.R'))]

                            debug_print(f"Verification: {len(runnable_files)} runnable files found", icon="🔍", style="cyan")

                            if runnable_files:
                                console.print()
                                try:
                                    if len(runnable_files) == 1:
                                        # Only one file, ask if they want to verify
                                        selector = InteractiveSelector(
                                            title=f"🔍 Verify changes by running {runnable_files[0]}?",
                                            choices=["Yes", "No"],
                                            current="Yes"
                                        )
                                        choice = selector.show()
                                        target_verify_file = runnable_files[0] if choice == "Yes" else None
                                    else:
                                        # Multiple files, let user choose
                                        choices = runnable_files + ["Skip verification"]
                                        selector = InteractiveSelector(
                                            title="🔍 Select a file to run for verification:",
                                            choices=choices,
                                            current=choices[0]
                                        )
                                        choice = selector.show()
                                        target_verify_file = choice if choice != "Skip verification" else None

                                    if target_verify_file:
                                        console.print(f"\n[yellow]Running {target_verify_file} for verification...[/yellow]\n")
                                        verify_result = run_async(mcp_client.call_tool(
                                            'coder',
                                            'verify_file_modifications',
                                            {
                                                'file_path': target_verify_file,
                                                'working_dir': get_user_working_dir()
                                            }
                                        ))

                                        # Display verification result
                                        display_execution_result(verify_result)
                                    else:
                                        console.print("\n[dim]Skipping verification run[/dim]\n")

                                except (EOFError, KeyboardInterrupt):
                                    console.print("\n[dim]Skipping verification run[/dim]\n")
                    elif target_file:
                        # Write code to target file
                        run_async(handle_code_file_writing(mcp_client, full_response, target_file))
                    else:
                        # Execute code (with user confirmation)
                        exec_result = run_async(handle_code_execution(mcp_client, full_response))
                        if exec_result:
                            display_execution_result(exec_result)
                except Exception as e:
                    debug_print(f"Error during code handling: {e}", icon="❌")

                # Ask for rating
                try:
                    rating_input = prompt("⭐ Rate (0-10, Enter to skip): ").strip()

                    if rating_input:  # User provided input
                        try:
                            rating = int(rating_input)
                            if 0 <= rating <= 10:
                                # Pass session_id if session is active
                                session_id = session_manager.get_session_id()
                                process_rating(rating, user_input, full_response, session_id)
                            else:
                                console.print("❌ [red]Invalid rating. Enter 0-10.[/red]")
                        except ValueError:
                            console.print("❌ [red]Invalid input. Enter a number.[/red]")
                    # If empty input (Enter pressed), do nothing - silently skip
                except EOFError:
                    pass  # Handle piped input gracefully

                console.print()  # Extra line for readability

            except KeyboardInterrupt:
                # Cleanup MCP client
                console.print("\n\n👋 [bold]Goodbye![/bold]")
                try:
                    run_async(mcp_client.cleanup())
                except (Exception, KeyboardInterrupt) as e:
                    # Suppress cleanup errors on exit
                    if verbose:
                        debug_print(f"Cleanup: {e}", icon="🧹")
                # Redirect stderr to suppress prompt_toolkit task cleanup warnings
                # Open /dev/null without context manager since we exit immediately
                sys.stderr = open(os.devnull, 'w')
                sys.exit(0)
            except Exception as e:
                console.print(f"\n❌ [red]Error: {e}[/red]")
                console.print("[dim]Please try again.[/dim]\n")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure config.yaml exists in the project root.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing CLI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # AI_CLI_ORIGINAL_DIR is already set at the top of this file before imports
    
    parser = argparse.ArgumentParser(description="AI CLI - Powered by Ollama")
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose mode to show debug information'
    )
    parser.add_argument(
        '--show-ui',
        action='store_true',
        help='Launch the web-based UI instead of CLI'
    )
    args = parser.parse_args()
    
    if args.show_ui:
        # Import and start UI server
        from src.ui.server import start_ui_server
        start_ui_server(verbose=args.verbose)
    else:
        main(verbose=args.verbose)
