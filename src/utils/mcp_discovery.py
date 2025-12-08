"""MCP discovery functionality for the AI CLI."""

import asyncio
import json
import sys
import textwrap
import shutil
from pathlib import Path


def list_system_mcps(console=None, base_path=None):
    """
    List all available system MCPs.
    
    Args:
        console: Rich console for output (optional)
        base_path: Base path to look for system_mcps directory (optional)
    """
    def _print(msg):
        if console:
            console.print(msg)
        else:
            print(msg)
    
    if base_path is None:
        system_mcps_dir = Path(__file__).parent.parent.parent / "system_mcps"
    else:
        system_mcps_dir = Path(base_path) / "system_mcps"

    if not system_mcps_dir.exists():
        _print("❌ [red]No system_mcps directory found[/red]\n")
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
        _print("ℹ️  [yellow]No system MCPs found[/yellow]\n")
        return

    # Display as simple list
    _print("\n📦 [bold]System MCPs:[/bold]")
    for name, description in sorted(mcps):
        _print(f"  • [bold cyan]{name}[/bold cyan] - [dim]{description}[/dim]")
    _print("")


async def get_mcp_tools(mcp_name, console=None, base_path=None):
    """
    Get tools from a specific MCP server.
    
    Args:
        mcp_name: Name of the MCP to query
        console: Rich console for output (optional)
        base_path: Base path to look for system_mcps directory (optional)
    """
    def _print(msg):
        if console:
            console.print(msg)
        else:
            print(msg)
    
    if base_path is None:
        system_mcps_dir = Path(__file__).parent.parent.parent / "system_mcps"
    else:
        system_mcps_dir = Path(base_path) / "system_mcps"
    
    mcp_dir = system_mcps_dir / mcp_name
    server_file = mcp_dir / "server.py"

    if not server_file.exists():
        _print(f"❌ [red]MCP '{mcp_name}' not found[/red]\n")
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
                _print(f"ℹ️  [yellow]No tools found in MCP '{mcp_name}'[/yellow]\n")
                return

            # Display as simple list
            _print(f"\n🔧 [bold]Tools in '{mcp_name}' MCP:[/bold]")
            
            # Get terminal width for text wrapping
            term_width = shutil.get_terminal_size().columns
            # Account for indentation (4 spaces) and some padding
            wrap_width = max(40, term_width - 6)
            
            for tool in tools:
                name = tool.get("name", "Unknown")
                description = tool.get("description", "No description")
                _print(f"  • [bold cyan]{name}[/bold cyan]")
                # Wrap long descriptions to terminal width
                wrapped_lines = textwrap.wrap(description, width=wrap_width)
                for line in wrapped_lines:
                    _print(f"    [dim]{line}[/dim]")
            _print("")
        else:
            _print(f"❌ [red]Failed to get tools from MCP '{mcp_name}'[/red]\n")

    except asyncio.TimeoutError:
        _print(f"❌ [red]Timeout while communicating with MCP '{mcp_name}'[/red]\n")
    except Exception as e:
        _print(f"❌ [red]Error getting tools from MCP '{mcp_name}': {e}[/red]\n")
