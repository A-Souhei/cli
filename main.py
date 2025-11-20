"""Main entry point for the AI CLI application."""

import sys
import json
import argparse
import requests
import urllib.parse
import subprocess
import asyncio
from pathlib import Path
from src.config import ConfigManager
from src.ollama_client import OllamaClient
from src.chat import ChatManager
from src.selector import InteractiveSelector
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.theme import Theme
from rich.style import Style
from rich.table import Table
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import FormattedText

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


def debug_print(message, style="dim", icon="🔍"):
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


def create_rating(user_rating, prompt_text, response_text, tags):
    """Create a new rating in the postgres-api."""
    try:
        params = {
            'user_rating': user_rating,
            'prompt_text': prompt_text,
            'response_text': response_text,
            'tags': json.dumps({'keywords': tags})
        }
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


def process_rating(user_rating, prompt_text, response_text):
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
                debug_print(f"Rating updated - Similar prompt (similarity: {best_similarity:.2f}), {stored_rating} → {user_rating}", "green", "✅")
                debug_print(f"Keywords: {', '.join(keywords)}", "cyan", "🏷️")
            else:
                debug_print("Failed to update existing rating", "red", "❌")
        else:
            debug_print(f"Rating skipped - Stored rating higher ({stored_rating} > {user_rating})", "yellow", "⏭️")
    else:
        # No similar prompt found, create new entry
        if create_rating(user_rating, prompt_text, response_text, keywords):
            debug_print(f"New prompt stored with rating {user_rating}", "green", "💾")
            debug_print(f"Keywords: {', '.join(keywords)}", "cyan", "🏷️")
        else:
            debug_print("Failed to save new rating", "red", "❌")


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
                            description = lines[0][:80]  # Limit to 80 chars
                    except Exception:
                        pass
                mcps.append((item.name, description))

    if not mcps:
        console.print("ℹ️  [yellow]No system MCPs found[/yellow]\n")
        return

    # Create a table
    table = Table(title="📦 System MCPs", border_style="cyan")
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Description", style="dim")

    for name, description in sorted(mcps):
        table.add_row(name, description)

    console.print()
    console.print(table)
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

            # Create a table
            table = Table(title=f"🔧 Tools in '{mcp_name}' MCP", border_style="cyan")
            table.add_column("Tool Name", style="bold cyan", no_wrap=True)
            table.add_column("Description", style="dim")

            for tool in tools:
                name = tool.get("name", "Unknown")
                description = tool.get("description", "No description")
                # Limit description length for table display
                if len(description) > 100:
                    description = description[:97] + "..."
                table.add_row(name, description)

            console.print()
            console.print(table)
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
                    console.print("\n👋 [bold]Goodbye![/bold]")
                    break

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
                            asyncio.run(get_mcp_tools(mcp_name))
                        except Exception as e:
                            console.print(f"❌ [red]Error: {e}[/red]\n")
                    continue

                # Skip empty input
                if not user_input:
                    continue

                # Get guidance based on similar past prompts
                guidance = get_prompt_guidance(user_input)

                # Add user message to context
                chat_manager.add_user_message(user_input)

                # Get messages and inject guidance if available
                messages = chat_manager.get_messages()
                if guidance:
                    # Insert guidance as a system message before the last user message
                    guidance_message = {'role': 'system', 'content': guidance}
                    # Insert before the last message (which is the user's current message)
                    messages = messages[:-1] + [guidance_message, messages[-1]]
                    debug_print(guidance, "magenta", "🧠")

                # Get AI response
                console.print()  # Add spacing before AI response
                console.print("[bold cyan]▶[/bold cyan]")

                # Get response (stream or not) and collect full response
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

                # Render response as markdown with custom styling
                console.print(CustomMarkdown(full_response, code_theme="monokai"))

                # Add assistant response to context
                chat_manager.add_assistant_message(full_response)

                console.print()  # Extra line for readability

                # Ask for rating
                try:
                    rating_input = prompt("⭐ Rate (0-10, Enter to skip): ").strip()

                    if rating_input:  # User provided input
                        try:
                            rating = int(rating_input)
                            if 0 <= rating <= 10:
                                process_rating(rating, user_input, full_response)
                            else:
                                console.print("❌ [red]Invalid rating. Enter 0-10.[/red]")
                        except ValueError:
                            console.print("❌ [red]Invalid input. Enter a number.[/red]")
                    # If empty input (Enter pressed), do nothing - silently skip
                except EOFError:
                    pass  # Handle piped input gracefully

                console.print()  # Extra line for readability

            except KeyboardInterrupt:
                console.print("\n\n👋 [bold]Goodbye![/bold]")
                break
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
