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
    # Note: We exit immediately after this, so the file handle cleanup happens via process termination
    try:
        import os
        sys.stderr = open(os.devnull, 'w')
    except Exception:
        pass  # Ignore errors in stderr redirection
    sys.exit(0)


def handle_clear(console, chat_manager):
    """Handle clear command."""
    chat_manager.clear_history()
    console.print("\n🗑️ [yellow]Chat history cleared[/yellow]\n")
    return True  # Continue the loop
