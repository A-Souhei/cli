"""Banner display functionality for the AI CLI."""

from pathlib import Path


def load_banner(base_path=None):
    """
    Load banner from file.
    
    Args:
        base_path: Base path for the application (optional)
        
    Returns:
        Banner text string
    """
    if base_path is None:
        banner_file = Path(__file__).parent.parent.parent / "assets" / "banner.txt"
    else:
        banner_file = Path(base_path) / "assets" / "banner.txt"
    
    try:
        if banner_file.exists():
            return banner_file.read_text()
        else:
            # Fallback banner if file doesn't exist
            return """
           ╦  ╦╦ ╦╦ ╦╦╔╦╗╦═╗╔═╗  ╔═╗╦  ╦
           ╚╗╔╝║ ║╠═╣║ ║ ╠╦╝╠═╣  ║  ║  ║
            ╚╝ ╚═╝╩ ╩╩ ╩ ╩╚═╩ ╩  ╚═╝╩═╝╩

           Powered by Ollama | Claude • MCP Tools • AI Agents
"""
    except Exception:
        return "VUHITRA CLI - Powered by Ollama | Claude"


def print_help(console):
    """
    Print help message with available commands.

    Args:
        console: Rich console instance
    """
    console.print("\n[bold cyan]Available Commands:[/bold cyan]")
    console.print("\n[bold yellow]Basic:[/bold yellow]")
    console.print("  [bold]'/help'[/bold] - Show this help message")
    console.print("  [bold]'/exit'[/bold] or [bold]'/quit'[/bold] - Exit the CLI")
    console.print("  [bold]'/clear'[/bold] - Clear chat history")
    console.print("  [bold]'/models'[/bold] - List available models")
    console.print("  [bold]'/switch'[/bold] - Switch to a different model")

    console.print("\n[bold yellow]MCP Tools:[/bold yellow]")
    console.print("  [bold]'/mcps'[/bold] - List system MCPs")
    console.print("  [bold]'/mcp-tools <name>'[/bold] - List tools in an MCP")

    console.print("\n[bold yellow]Session Management:[/bold yellow]")
    console.print("  [bold]'/session start'[/bold] - Start a context session")
    console.print("  [bold]'/session end'[/bold] - End the current session")
    console.print("  [bold]'/session info'[/bold] - View current session info")
    console.print("  [bold]'/session restore <id>'[/bold] - Restore a saved session")
    console.print("  [bold]'/session list'[/bold] - List all saved sessions")
    console.print("  [bold]'/session clear'[/bold] - Clear all saved sessions")

    console.print("\n[bold yellow]Context Management:[/bold yellow]")
    console.print("  [bold]'/context add @file'[/bold] - Add file/directory to context without LLM call")
    console.print("  [bold]'/context add ALL'[/bold] - Add entire working directory to context")
    console.print("  [bold]'/context add ALL_TOOLS'[/bold] - Add all MCP tools with descriptions to context")
    console.print("  [bold]'/context add TODO_LIST <desc>'[/bold] - Generate strategic TODO list with tool references")
    console.print("  [bold]'/context load TODO_LIST [@path]'[/bold] - Load TODO_LIST from file (default: .todo_list)")
    console.print("  [bold]'/context save TODO_LIST [@path]'[/bold] - Save TODO_LIST to file (default: .todo_list)")
    console.print("  [bold]'/context add MAKE_LIST <desc>'[/bold] - Generate strategic MAKE_LIST with makemap targets")
    console.print("  [bold]'/context load MAKE_LIST [@path]'[/bold] - Load MAKE_LIST from file (default: .make_list)")
    console.print("  [bold]'/context save MAKE_LIST [@path]'[/bold] - Save MAKE_LIST to file (default: .make_list)")
    console.print("  [bold]'/context show'[/bold] - Display current context (chat, session, metadata)")
    console.print("  [bold]'/context metrics'[/bold] - Show context size and usage metrics")
    console.print("  [bold]'/context clear'[/bold] - Clear current context (keeps session active)")

    console.print("\n[bold yellow]Security & Ignore:[/bold yellow]")
    console.print("  [bold]'/ignore create'[/bold] - Create .llmignore file with default patterns")
    console.print("  [bold]'/ignore add @file'[/bold] - Add file(s) to .llmignore")

    console.print("\n[bold yellow]Repository & Data Mapping:[/bold yellow]")
    console.print("  [bold]'/repomap create'[/bold] - Create a repository map")
    console.print("  [bold]'/repomap load'[/bold] - Load existing .repomap file")
    console.print("  [bold]'/repomap update'[/bold] - Update .repomap with new files")
    console.print("  [bold]'/datamap create'[/bold] - Create a data map (--files-only, --with-pg, --with-files)")
    console.print("  [bold]'/datamap load'[/bold] - Load existing .datamap file")
    console.print("  [bold]'/datamap update'[/bold] - Update .datamap (--with-files, --with-pg)")

    console.print("\n[bold yellow]Make Commands:[/bold yellow]")
    console.print("  [bold]'/make <prompt>'[/bold] - Execute make commands using natural language")
    console.print("  [bold]'/make map generate'[/bold] - Generate .makemap from Makefile")
    console.print("  [bold]'/make map load'[/bold] - Load existing .makemap file")
    console.print("  [bold]'/make map update'[/bold] - Update .makemap with new targets")

    console.print("\n[bold yellow]Plan Execution:[/bold yellow]")
    console.print("  [bold]'/execute TODO_LIST [model]'[/bold] - Execute TODO_LIST plan sequentially")
    console.print("  [bold]'/execute MAKE_LIST [model]'[/bold] - Execute MAKE_LIST plan sequentially")

    console.print("\n[bold yellow]Code Execution:[/bold yellow]")
    console.print("  [bold]'/code <prompt>'[/bold] - Analyze and execute code tasks (requires session)")

    console.print("\n[bold yellow]Model Management:[/bold yellow]")
    console.print("  [bold]'/model status'[/bold] - Show all configured models")
    console.print("  [bold]'/model list'[/bold] - List all models")
    console.print("  [bold]'/model <type> list'[/bold] - List models of specific type (general/coder/embedding)")
    console.print("  [bold]'/model <type> add <url> <model_name>'[/bold] - Add a model")
    console.print("  [bold]'/model <type> use <model_id>'[/bold] - Set active model")
    console.print("  [bold]'/model <type> remove <model_id>'[/bold] - Remove a model")
    console.print("  [bold]'/model check [model_id]'[/bold] - Check model availability")

    console.print("\n[bold yellow]File Context:[/bold yellow]")
    console.print("  [bold]'@filename'[/bold] - Add file to context (use Tab for completion)")
    console.print("  [bold]'@directory/'[/bold] - Add directory to context")

    console.print("\n[bold yellow]Keyboard Shortcuts:[/bold yellow]")
    console.print("  [bold]'Ctrl+J'[/bold] - Submit multi-line input")
    console.print("  [bold]'Alt+Enter'[/bold] - Submit multi-line input (Escape then Enter)")
    console.print("  [bold]'Ctrl+C'[/bold] - Clear current input (or skip rating)")
    console.print("  [bold]'Ctrl+D'[/bold] - Delete character (or exit if input is empty)")
    console.print()


def print_banner(console, base_path=None):
    """
    Print CLI banner.

    Args:
        console: Rich console instance
        base_path: Base path for the application (optional)
    """
    # Load and display the ASCII art banner
    banner_text = load_banner(base_path)
    console.print(banner_text, style="bold cyan")

    # Print help hint
    console.print("\n[dim]Type [bold]/help[/bold] to see available commands[/dim]\n")
