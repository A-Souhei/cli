"""MCP-related command handlers for AI CLI."""


def handle_mcps(list_system_mcps):
    """Handle mcps command."""
    list_system_mcps()
    return True  # Continue the loop


def handle_mcp_tools(console, user_input_normalized, run_async, get_mcp_tools):
    """Handle mcp-tools command."""
    mcp_name = user_input_normalized[10:].strip()
    if not mcp_name:
        console.print("❌ [red]Usage: /mcp-tools <mcp_name>[/red]\n")
    else:
        try:
            run_async(get_mcp_tools(mcp_name, console=console))
        except Exception as e:
            console.print(f"❌ [red]Error: {e}[/red]\n")
    return True  # Continue the loop
