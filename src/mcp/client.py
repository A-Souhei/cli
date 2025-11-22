"""MCP Client Manager for interacting with MCP servers."""

import asyncio
import json
import sys
import re
import requests
from pathlib import Path
from typing import Optional, Dict, List, Any


class MCPClient:
    """Client for managing MCP server connections and tool execution."""

    def __init__(self, system_mcps_dir: Path, postgres_url: str, verbose: bool = False):
        """
        Initialize the MCP client.

        Args:
            system_mcps_dir: Path to system_mcps directory
            postgres_url: URL for PostgreSQL API
            verbose: Enable verbose logging
        """
        self.system_mcps_dir = system_mcps_dir
        self.postgres_url = postgres_url
        self.verbose = verbose
        self.servers = {}  # mcp_name -> process
        self.tools_cache = {}  # mcp_name -> list of tools
        self.debug_callback = None

    def set_debug_callback(self, callback):
        """Set a callback function for debug messages."""
        self.debug_callback = callback

    def debug_print(self, message: str, icon: str = "🔍"):
        """Print debug message if verbose mode is enabled."""
        if self.verbose and self.debug_callback:
            self.debug_callback(message, icon=icon)

    async def start_server(self, mcp_name: str) -> bool:
        """
        Start an MCP server process.

        Args:
            mcp_name: Name of the MCP server

        Returns:
            bool: True if started successfully, False otherwise
        """
        if mcp_name in self.servers:
            self.debug_print(f"MCP server '{mcp_name}' already running", "✓")
            return True

        server_file = self.system_mcps_dir / mcp_name / "server.py"
        if not server_file.exists():
            self.debug_print(f"MCP server '{mcp_name}' not found", "❌")
            return False

        try:
            self.debug_print(f"Starting MCP server '{mcp_name}'...", "🚀")
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
            self.debug_print(f"MCP server '{mcp_name}' initialized", "✓")

            self.servers[mcp_name] = process
            return True

        except Exception as e:
            self.debug_print(f"Failed to start MCP server '{mcp_name}': {e}", "❌")
            return False

    async def get_tools(self, mcp_name: str) -> Optional[List[Dict]]:
        """
        Get tools from an MCP server.

        Args:
            mcp_name: Name of the MCP server

        Returns:
            List of tools or None if failed
        """
        if mcp_name not in self.servers:
            if not await self.start_server(mcp_name):
                return None

        # Check cache first
        if mcp_name in self.tools_cache:
            return self.tools_cache[mcp_name]

        try:
            process = self.servers[mcp_name]

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

            if "result" in tools_data and "tools" in tools_data["result"]:
                tools = tools_data["result"]["tools"]
                self.tools_cache[mcp_name] = tools
                self.debug_print(f"Retrieved {len(tools)} tools from '{mcp_name}'", "📋")
                return tools

            return None

        except Exception as e:
            self.debug_print(f"Failed to get tools from '{mcp_name}': {e}", "❌")
            return None

    async def initialize_tools_in_db(self):
        """
        Initialize all MCP tools in the database with embeddings.
        This should be called on CLI startup.
        """
        self.debug_print("Initializing MCP tools in database...", "🔧")

        # Discover all MCPs
        if not self.system_mcps_dir.exists():
            self.debug_print("No system_mcps directory found", "⚠️")
            return

        mcp_count = 0
        tool_count = 0

        for item in self.system_mcps_dir.iterdir():
            if item.is_dir() and (item / "server.py").exists():
                mcp_name = item.name
                mcp_count += 1

                # Get tools from this MCP
                tools = await self.get_tools(mcp_name)
                if not tools:
                    continue

                # Store each tool in database
                for tool in tools:
                    try:
                        response = requests.post(
                            f"{self.postgres_url}/mcp-tools/store",
                            json={
                                "mcp_name": mcp_name,
                                "tool_name": tool.get("name"),
                                "description": tool.get("description", "")
                            },
                            timeout=30
                        )

                        if response.status_code == 200:
                            tool_count += 1
                            self.debug_print(
                                f"Stored tool '{tool.get('name')}' from '{mcp_name}'",
                                "💾"
                            )
                        else:
                            self.debug_print(
                                f"Failed to store tool '{tool.get('name')}': {response.text}",
                                "❌"
                            )

                    except Exception as e:
                        self.debug_print(f"Error storing tool: {e}", "❌")

        self.debug_print(
            f"Initialized {tool_count} tools from {mcp_count} MCPs",
            "✓"
        )

    def detect_code(self, text: str) -> Optional[Dict]:
        """
        Detect code in text using regex patterns.

        Args:
            text: Text to analyze

        Returns:
            Dict with 'language' and 'code' if detected, None otherwise
        """
        # Look for code blocks with language specifiers
        patterns = [
            (r"```python\s*\n(.*?)```", "python"),
            (r"```r\s*\n(.*?)```", "r"),
            (r"```R\s*\n(.*?)```", "r"),
        ]

        for pattern, lang in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return {
                    "language": lang,
                    "code": match.group(1).strip()
                }

        # Check for generic code blocks and try to detect language by content
        generic_match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
        if generic_match:
            code = generic_match.group(1).strip()
            # Simple heuristics
            if any(keyword in code for keyword in ["import ", "def ", "print(", "if __name__"]):
                return {"language": "python", "code": code}
            elif any(keyword in code for keyword in ["<-", "library(", "data.frame"]):
                return {"language": "r", "code": code}

        return None

    def match_tool(self, text: str, threshold: float = 0.5) -> Optional[Dict]:
        """
        Match text against MCP tools using embeddings.

        Args:
            text: Text to match
            threshold: Similarity threshold

        Returns:
            Best matching tool or None
        """
        try:
            response = requests.post(
                f"{self.postgres_url}/mcp-tools/match",
                json={
                    "text": text,
                    "threshold": threshold
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                best_match = data.get("best_match")

                if best_match:
                    self.debug_print(
                        f"Matched tool '{best_match.get('tool_name')}' "
                        f"(similarity: {best_match.get('similarity'):.2f})",
                        "🎯"
                    )
                    return best_match

            return None

        except Exception as e:
            self.debug_print(f"Error matching tool: {e}", "❌")
            return None

    async def call_tool(self, mcp_name: str, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """
        Call a tool on an MCP server.

        Args:
            mcp_name: Name of the MCP server
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool result as string or None if failed
        """
        if mcp_name not in self.servers:
            if not await self.start_server(mcp_name):
                return None

        try:
            process = self.servers[mcp_name]

            # Send tools/call request
            call_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            self.debug_print(
                f"Calling tool '{tool_name}' on '{mcp_name}'",
                "⚙️"
            )

            process.stdin.write((json.dumps(call_request) + "\n").encode())
            await process.stdin.drain()

            # Read response
            response = await asyncio.wait_for(process.stdout.readline(), timeout=60.0)
            response_data = json.loads(response.decode())

            if "result" in response_data and "content" in response_data["result"]:
                content = response_data["result"]["content"]
                if content and len(content) > 0:
                    # Handle both dict and object formats
                    if isinstance(content[0], dict):
                        result_text = content[0].get("text", "")
                    else:
                        # If it's an object with a text attribute
                        result_text = getattr(content[0], "text", "")

                    # Debug: log if result is empty
                    if not result_text:
                        self.debug_print(f"Warning: Tool returned empty result. Content: {content}", "⚠️")
                        return None

                    self.debug_print(f"Tool executed successfully", "✓")
                    return result_text

            if "error" in response_data:
                error_msg = response_data["error"].get("message", "Unknown error")
                self.debug_print(f"Tool execution error: {error_msg}", "❌")
                return f"Error: {error_msg}"

            return None

        except asyncio.TimeoutError:
            self.debug_print(f"Tool execution timed out", "❌")
            return "Error: Tool execution timed out"
        except Exception as e:
            self.debug_print(f"Error calling tool: {e}", "❌")
            return f"Error: {str(e)}"

    async def cleanup(self):
        """Cleanup all MCP server processes."""
        self.debug_print("Cleaning up MCP servers...", "🧹")

        for mcp_name, process in self.servers.items():
            try:
                process.terminate()
                await process.wait()
                self.debug_print(f"Stopped MCP server '{mcp_name}'", "✓")
            except Exception as e:
                self.debug_print(f"Error stopping '{mcp_name}': {e}", "❌")

        self.servers.clear()
        self.tools_cache.clear()
