"""Main entry point for the AI CLI application."""

import sys
import json
import argparse
import requests
import urllib.parse
import subprocess
import asyncio
import os
from pathlib import Path
from src.config import ConfigManager
from src.ollama_client import OllamaClient
from src.chat import ChatManager
from src.selector import InteractiveSelector
from src.mcp import MCPClient
from src.session import SessionManager
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

# Apply nest_asyncio once globally to allow nested event loops
import nest_asyncio
nest_asyncio.apply()


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


def get_all_ratings():
    """Get all ratings from the postgres-api."""
    try:
        response = requests.get(f"{POSTGRES_API_URL}/ratings", timeout=10)
        if response.status_code == 200:
            return response.json().get('ratings', [])
        return []
    except Exception as e:
        print(f"[Warning] Could not fetch ratings: {e}")
        return []


def check_similarity(text1, text2):
    """Check similarity between two texts using transformer service."""
    try:
        params = {
            'text1': text1,
            'text2': text2,
            'metric': 'cosine'
        }
        response = requests.get(
            f"{TRANSFORMER_API_URL}/similarity",
            params=params,
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get('similarity', 0)
        return 0
    except Exception as e:
        print(f"[Warning] Could not check similarity: {e}")
        return 0


def extract_keywords(text, top_n=5):
    """Extract keywords from text using transformer service."""
    try:
        params = {
            'text': text,
            'top_n': top_n
        }
        response = requests.get(
            f"{TRANSFORMER_API_URL}/keywords",
            params=params,
            timeout=30
        )
        if response.status_code == 200:
            keywords_data = response.json().get('keywords', [])
            return [kw['keyword'] for kw in keywords_data]
        return []
    except Exception as e:
        print(f"[Warning] Could not extract keywords: {e}")
        return []


def create_rating(user_rating, prompt_text, response_text, tags, session_id=None):
    """Create a new rating in the postgres-api."""
    try:
        params = {
            'user_rating': user_rating,
            'prompt_text': prompt_text,
            'response_text': response_text,
            'tags': json.dumps({'keywords': tags})
        }
        if session_id:
            params['session_id'] = session_id
        response = requests.get(
            f"{POSTGRES_API_URL}/ratings/create",
            params=params,
            timeout=10
        )
        return response.status_code == 201
    except Exception as e:
        print(f"[Warning] Could not create rating: {e}")
        return False


def update_rating(rating_id, user_rating, response_text, tags):
    """Update an existing rating in the postgres-api."""
    try:
        payload = {
            'user_rating': user_rating,
            'response_text': response_text,
            'tags': {'keywords': tags}
        }
        response = requests.patch(
            f"{POSTGRES_API_URL}/ratings/{rating_id}/update",
            json=payload,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"[Warning] Could not update rating: {e}")
        return False


def find_similar_prompt(prompt_text, existing_ratings):
    """
    Find the most similar prompt from existing ratings.

    Args:
        prompt_text: The prompt to compare
        existing_ratings: List of existing rating records

    Returns:
        Tuple of (best_match, best_similarity) or (None, 0) if no match found
    """
    best_match = None
    best_similarity = 0

    for rating in existing_ratings:
        stored_prompt = rating.get('prompt_text', '')
        if stored_prompt:
            similarity = check_similarity(prompt_text, stored_prompt)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = rating

    return best_match, best_similarity


def process_rating(user_rating, prompt_text, response_text, session_id=None):
    """
    Process the user rating by:
    1. Getting all existing ratings
    2. Finding similar prompts
    3. Updating or creating as needed
    """
    # Get all existing ratings
    existing_ratings = get_all_ratings()

    # Extract keywords from current response
    keywords = extract_keywords(response_text)

    # Find the most similar prompt (reuse logic)
    best_match, best_similarity = find_similar_prompt(prompt_text, existing_ratings)

    # Check if we found a similar prompt
    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        stored_rating = best_match.get('user_rating', 0)
        # Update if current rating is higher or equal
        if user_rating >= stored_rating:
            if update_rating(best_match['id'], user_rating, response_text, keywords):
                debug_print(f"Rating updated - Similar prompt (similarity: {best_similarity:.2f}), {stored_rating} → {user_rating}", icon="✅", style="green")
                debug_print(f"Keywords: {', '.join(keywords)}", icon="🏷️", style="cyan")
            else:
                debug_print("Failed to update existing rating", icon="❌", style="red")
        else:
            debug_print(f"Rating skipped - Stored rating higher ({stored_rating} > {user_rating})", icon="⏭️", style="yellow")
    else:
        # No similar prompt found, create new entry
        if create_rating(user_rating, prompt_text, response_text, keywords, session_id):
            debug_print(f"New prompt stored with rating {user_rating}", icon="💾", style="green")
            debug_print(f"Keywords: {', '.join(keywords)}", icon="🏷️", style="cyan")
        else:
            debug_print("Failed to save new rating", icon="❌", style="red")


def get_prompt_guidance(prompt_text):
    """
    Get guidance for the LLM based on similar past prompts and their ratings.

    Returns a guidance string to inject into the conversation, or None if no guidance.
    """
    # Get all existing ratings
    existing_ratings = get_all_ratings()

    if not existing_ratings:
        return None

    # Find the most similar prompt (reuse shared logic)
    best_match, best_similarity = find_similar_prompt(prompt_text, existing_ratings)

    # Check if we found a similar prompt
    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        stored_rating = best_match.get('user_rating', 0)
        tags = best_match.get('tags', {})
        keywords = tags.get('keywords', []) if isinstance(tags, dict) else []

        if not keywords:
            return None

        keywords_str = ', '.join(keywords)

        if stored_rating >= SATISFACTORY_RATING_THRESHOLD:
            # Satisfactory response - use these keywords
            guidance = (
                f"[Context: A similar question was previously answered satisfactorily. "
                f"Consider incorporating these relevant concepts: {keywords_str}]"
            )
        else:
            # Unsatisfactory response - avoid these keywords
            guidance = (
                f"[Context: A similar question was previously answered unsatisfactorily. "
                f"Consider avoiding or improving upon these concepts: {keywords_str}]"
            )

        return guidance

    return None


async def handle_code_execution(mcp_client: MCPClient, response_text: str):
    """
    Detect and execute code from LLM response.

    Args:
        mcp_client: MCP client instance
        response_text: The LLM response text

    Returns:
        Execution result or None
    """
    # Detect code in the response
    detected = mcp_client.detect_code(response_text)

    if not detected:
        debug_print("No code detected in response", icon="ℹ️")
        return None

    language = detected['language']
    code = detected['code']

    debug_print(f"Detected {language.upper()} code block", icon="🔍")

    # Determine tool based on language
    if language == "python":
        tool_name = "run_python_code"
        mcp_name = "coder"
    elif language == "r":
        tool_name = "run_r_code"
        mcp_name = "coder"
    else:
        debug_print(f"Unsupported language: {language}", icon="⚠️")
        return None

    # Ask user for confirmation using InteractiveSelector
    console.print()
    try:
        selector = InteractiveSelector(
            title=f"⚡ Execute {language.upper()} code?",
            choices=["Yes", "No"],
            current="No"
        )
        choice = selector.show()

        if choice != "Yes":
            console.print("\n[dim]Code execution cancelled[/dim]\n")
            return None
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]Code execution cancelled[/dim]\n")
        return None

    # Execute the code
    debug_print(f"Executing {language} code...", icon="⚙️")
    console.print("[yellow]Executing code...[/yellow]\n")

    result = await mcp_client.call_tool(
        mcp_name=mcp_name,
        tool_name=tool_name,
        arguments={"code": code}
    )

    return result


def display_execution_result(result: str):
    """
    Display code execution result in a nice format.

    Args:
        result: JSON string from MCP tool execution
    """
    try:
        result_data = json.loads(result)

        # Check if it's an error
        if result.startswith("Error:"):
            console.print(f"\n❌ [bold red]Execution Error[/bold red]")
            console.print(f"[red]{result}[/red]\n")
            return

        # Display execution complete message
        console.print("\n✓ [bold]Execution Complete[/bold]\n")

        # Show stdout if present
        if result_data.get("stdout"):
            console.print("📄 [bold]Output:[/bold]")
            console.print(result_data["stdout"].strip())
            console.print()

        # Show stderr if present
        if result_data.get("stderr"):
            console.print("⚠️  [bold yellow]Warnings/Errors:[/bold yellow]")
            console.print(f"[yellow]{result_data['stderr'].strip()}[/yellow]")
            console.print()

        # Show exit code
        exit_code = result_data.get("exit_code", -1)
        if exit_code == 0:
            console.print(f"[dim]Exit Code: {exit_code}[/dim]")
        else:
            console.print(f"[red]Exit Code: {exit_code}[/red]")

        console.print()

    except json.JSONDecodeError:
        # Not JSON, display as-is
        console.print(f"\n📄 [bold]Result:[/bold]")
        console.print(result)
        console.print()
    except Exception as e:
        debug_print(f"Error displaying result: {e}", icon="❌")
        console.print(f"[dim]Result: {result}[/dim]\n")


def list_system_mcps():
    """List all available system MCPs."""
    system_mcps_dir = Path(__file__).parent / "system_mcps"

    if not system_mcps_dir.exists():
        console.print("❌ [red]No system_mcps directory found[/red]\n")
        return

    # Find all directories in system_mcps that contain a server.py file
    mcps = []
    for item in system_mcps_dir.iterdir():
        if item.is_dir():
            server_file = item / "server.py"
            readme_file = item / "README.md"
            if server_file.exists():
                # Try to read description from README
                description = "No description available"
                if readme_file.exists():
                    try:
                        content = readme_file.read_text()
                        # Get first non-empty line after the title
                        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
                        if lines:
                            description = lines[0]  # No character limit
                    except Exception:
                        # Ignore errors reading README, fallback to default description
                        pass
                mcps.append((item.name, description))

    if not mcps:
        console.print("ℹ️  [yellow]No system MCPs found[/yellow]\n")
        return

    # Display as simple list
    console.print("\n📦 [bold]System MCPs:[/bold]")
    for name, description in sorted(mcps):
        console.print(f"  • [bold cyan]{name}[/bold cyan] - [dim]{description}[/dim]")
    console.print()


async def get_mcp_tools(mcp_name):
    """Get tools from a specific MCP server."""
    system_mcps_dir = Path(__file__).parent / "system_mcps"
    mcp_dir = system_mcps_dir / mcp_name
    server_file = mcp_dir / "server.py"

    if not server_file.exists():
        console.print(f"❌ [red]MCP '{mcp_name}' not found[/red]\n")
        return

    try:
        # Start the MCP server process
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(server_file),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "ai-cli",
                    "version": "1.0.0"
                }
            }
        }

        process.stdin.write((json.dumps(init_request) + "\n").encode())
        await process.stdin.drain()

        # Read initialization response
        init_response = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)

        # Send tools/list request
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        process.stdin.write((json.dumps(tools_request) + "\n").encode())
        await process.stdin.drain()

        # Read tools response
        tools_response = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
        tools_data = json.loads(tools_response.decode())

        # Cleanup
        process.terminate()
        await process.wait()

        # Display tools
        if "result" in tools_data and "tools" in tools_data["result"]:
            tools = tools_data["result"]["tools"]

            if not tools:
                console.print(f"ℹ️  [yellow]No tools found in MCP '{mcp_name}'[/yellow]\n")
                return

            # Display as simple list
            console.print(f"\n🔧 [bold]Tools in '{mcp_name}' MCP:[/bold]")
            for tool in tools:
                name = tool.get("name", "Unknown")
                description = tool.get("description", "No description")
                console.print(f"  • [bold cyan]{name}[/bold cyan]")
                console.print(f"    [dim]{description}[/dim]")
            console.print()
        else:
            console.print(f"❌ [red]Failed to get tools from MCP '{mcp_name}'[/red]\n")

    except asyncio.TimeoutError:
        console.print(f"❌ [red]Timeout while communicating with MCP '{mcp_name}'[/red]\n")
    except Exception as e:
        console.print(f"❌ [red]Error getting tools from MCP '{mcp_name}': {e}[/red]\n")


def print_banner():
    """Print CLI banner."""
    banner_text = Text()
    banner_text.append("🤖 AI CLI", style="bold cyan")
    banner_text.append(" - Powered by Ollama", style="dim")

    console.print()
    console.print(Panel(banner_text, border_style="cyan"))
    console.print("  Type [bold]'exit'[/bold] or [bold]'quit'[/bold] to exit")
    console.print("  Type [bold]'clear'[/bold] to clear chat history")
    console.print("  Type [bold]'models'[/bold] to list available models")
    console.print("  Type [bold]'switch'[/bold] to change model")
    console.print("  Type [bold]'mcps'[/bold] to list system MCPs")
    console.print("  Type [bold]'mcp-tools <name>'[/bold] to list tools in an MCP")
    console.print("  Type [bold]'session start'[/bold] to start a context session")
    console.print("  Type [bold]'session end'[/bold] to end the current session")
    console.print()


def main(verbose=False):
    """Main function to run the AI CLI."""
    global VERBOSE
    VERBOSE = verbose

    try:
        # Load configuration
        config = ConfigManager()

        # Initialize Ollama client
        ollama_client = OllamaClient(
            host=config.get_ollama_url(),
            model=config.get_ollama_model(),
            timeout=config.get_ollama_timeout()
        )

        # Initialize chat manager
        chat_manager = ChatManager(
            system_prompt=config.get_system_prompt(),
            max_context_length=config.get_max_context_length()
        )

        # Initialize session manager
        session_manager = SessionManager()

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

        print_banner()
        console.print(f"  📦 Model: [bold]{ollama_client.model}[/bold]")
        console.print(f"  🔗 Server: [dim]{config.get_ollama_url()}[/dim]")
        console.print()

        # Initialize command history
        history = FileHistory(str(HISTORY_FILE))

        # Main chat loop
        while True:
            try:
                # Get user input with history support
                user_input = prompt(
                    FormattedText([('ansigreen bold', '▶ ')]),
                    history=history
                ).strip()

                # Handle special commands
                if user_input.lower() in ['exit', 'quit']:
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

                if user_input.lower() == 'clear':
                    chat_manager.clear_history()
                    console.print("\n🗑️ [yellow]Chat history cleared[/yellow]\n")
                    continue

                if user_input.lower() == 'models':
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

                if user_input.lower() == 'switch':
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

                if user_input.lower() == 'mcps':
                    list_system_mcps()
                    continue

                if user_input.lower().startswith('mcp-tools '):
                    mcp_name = user_input[10:].strip()
                    if not mcp_name:
                        console.print("❌ [red]Usage: mcp-tools <mcp_name>[/red]\n")
                    else:
                        try:
                            run_async(get_mcp_tools(mcp_name))
                        except Exception as e:
                            console.print(f"❌ [red]Error: {e}[/red]\n")
                    continue

                # Handle session commands
                if user_input.lower() == 'session start':
                    if session_manager.is_active():
                        console.print("\n⚠️  [yellow]Session already active. End current session first.[/yellow]\n")
                    else:
                        session_id = session_manager.start_session()
                        console.print()
                    continue

                if user_input.lower() == 'session end':
                    summary = session_manager.end_session()
                    if summary:
                        console.print()
                    continue

                if user_input.lower() == 'session info':
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

                # Skip empty input
                if not user_input:
                    continue

                # Get guidance based on similar past prompts
                guidance = get_prompt_guidance(user_input)

                # Get session context if active
                session_context = None
                if session_manager.is_active():
                    session_context = session_manager.get_session_context(max_interactions=5)
                    if session_context:
                        debug_print(f"Session active: {len(session_manager.get_session_history())} interactions in context", icon="📝", style="cyan")

                # Add user message to context
                chat_manager.add_user_message(user_input)

                # Get messages and inject guidance if available
                messages = chat_manager.get_messages()

                # Inject session context if available
                if session_context:
                    session_message = {'role': 'system', 'content': session_context}
                    messages = messages[:-1] + [session_message, messages[-1]]

                if guidance:
                    # Insert guidance as a system message before the last user message
                    guidance_message = {'role': 'system', 'content': guidance}
                    # Insert before the last message (which is the user's current message)
                    messages = messages[:-1] + [guidance_message, messages[-1]]
                    debug_print(guidance, icon="🧠", style="magenta")

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

                console.print()  # Extra line for readability

                # Check for code and offer to execute
                try:
                    exec_result = run_async(handle_code_execution(mcp_client, full_response))
                    if exec_result:
                        display_execution_result(exec_result)
                except Exception as e:
                    debug_print(f"Error during code execution: {e}", icon="❌")

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
    parser = argparse.ArgumentParser(description="AI CLI - Powered by Ollama")
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose mode to show debug information'
    )
    args = parser.parse_args()
    main(verbose=args.verbose)
