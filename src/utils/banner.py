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

           Powered by Ollama
"""
    except Exception:
        return "VUHITRA CLI - Powered by Ollama"


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

    # Print command help
    console.print("\n[bold cyan]Commands:[/bold cyan]")
    console.print("  [bold]'/exit'[/bold] or [bold]'/quit'[/bold] - Exit the CLI")
    console.print("  [bold]'/clear'[/bold] - Clear chat history")
    console.print("  [bold]'/models'[/bold] - List available models")
    console.print("  [bold]'/switch'[/bold] - Switch to a different model")
    console.print("  [bold]'/mcps'[/bold] - List system MCPs")
    console.print("  [bold]'/mcp-tools <name>'[/bold] - List tools in an MCP")
    console.print("  [bold]'/session start'[/bold] - Start a context session")
    console.print("  [bold]'/session end'[/bold] - End the current session")
    console.print("  [bold]'/session info'[/bold] - View current session info")
    console.print("  [bold]'/session restore <id>'[/bold] - Restore a saved session")
    console.print("  [bold]'/session list'[/bold] - List all saved sessions")
    console.print("  [bold]'/session clear'[/bold] - Clear all saved sessions")
    console.print("  [bold]'/context show'[/bold] - Show current context (chat, session, metadata)")
    console.print("  [bold]'/context clear'[/bold] - Clear current context (keeps session active)")
    console.print("  [bold]'/repomap create'[/bold] - Create a repository map from working directory")
    console.print("  [bold]'/repomap load'[/bold] - Load existing .repomap file into context")
    console.print("  [bold]'/repomap update'[/bold] - Update existing .repomap with new files")
    console.print("  [bold]'/datamap create'[/bold] - Create a data map from data files (--files-only, --with-pg, --with-files)")
    console.print("  [bold]'/datamap load'[/bold] - Load existing .datamap file into context")
    console.print("  [bold]'/datamap update'[/bold] - Update existing .datamap with new files (--with-files, --with-pg)")
    console.print("  [bold]'/code <prompt>'[/bold] - Analyze and execute code tasks (requires session)")
    console.print()
