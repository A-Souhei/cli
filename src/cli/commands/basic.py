"""Basic command handlers for AI CLI."""
import os
import sys


def handle_exit(console, mcp_client, run_async, debug_print, verbose):
    """Handle exit/quit command."""
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


def handle_clear(console, chat_manager):
    """Handle clear command."""
    chat_manager.clear_history()
    console.print("\n🗑️ [yellow]Chat history cleared[/yellow]\n")
    return True  # Continue the loop
