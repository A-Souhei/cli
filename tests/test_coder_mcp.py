"""Tests for the coder MCP server."""

import pytest
import asyncio
import json
import sys
from pathlib import Path


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


async def communicate_with_mcp(server_path, requests):
    """
    Helper function to communicate with an MCP server.

    Args:
        server_path: Path to the MCP server script
        requests: List of JSON-RPC requests to send

    Returns:
        List of responses
    """
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(server_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    responses = []

    try:
        for req in requests:
            # Send request
            process.stdin.write((json.dumps(req) + "\n").encode())
            await process.stdin.drain()

            # Read response
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=10.0)
            response = json.loads(response_line.decode())
            responses.append(response)

    finally:
        process.terminate()
        await process.wait()

    return responses


class TestCoderMCP:
    """Test the coder MCP server."""

    @pytest.fixture
    def server_path(self):
        """Get path to coder MCP server."""
        return Path(__file__).parent.parent / "system_mcps" / "coder" / "server.py"

    def test_server_exists(self, server_path):
        """Test that the coder MCP server file exists."""
        assert server_path.exists()
        assert server_path.is_file()

    @pytest.mark.asyncio
    async def test_initialize(self, server_path):
        """Test MCP server initialization."""
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) == 1
        response = responses[0]
        assert "result" in response or "error" not in response

    @pytest.mark.asyncio
    async def test_list_tools(self, server_path):
        """Test listing tools from coder MCP."""
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) == 2
        tools_response = responses[1]

        assert "result" in tools_response
        assert "tools" in tools_response["result"]

        tools = tools_response["result"]["tools"]
        assert len(tools) == 3  # run_python_code, run_r_code, detect_code

        tool_names = [t["name"] for t in tools]
        assert "run_python_code" in tool_names
        assert "run_r_code" in tool_names
        assert "detect_code" in tool_names

        # Check tool structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    @pytest.mark.asyncio
    async def test_run_python_code(self, server_path):
        """Test running Python code."""
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "run_python_code",
                    "arguments": {
                        "code": "print('Hello from Python!')"
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) == 2
        result_response = responses[1]

        assert "result" in result_response
        assert "content" in result_response["result"]

        content = result_response["result"]["content"]
        assert len(content) > 0

        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        assert "stdout" in result_data
        assert "stderr" in result_data
        assert "exit_code" in result_data
        assert "Hello from Python!" in result_data["stdout"]
        assert result_data["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_run_python_code_with_error(self, server_path):
        """Test running Python code that has an error."""
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "run_python_code",
                    "arguments": {
                        "code": "raise ValueError('Test error')"
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        result_response = responses[1]
        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        assert result_data["exit_code"] != 0
        assert "stderr" in result_data

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not Path("/usr/bin/R").exists() and not Path("/usr/local/bin/R").exists(),
        reason="R is not installed"
    )
    async def test_run_r_code(self, server_path):
        """Test running R code."""
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "run_r_code",
                    "arguments": {
                        "code": "print('Hello from R!')"
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        result_response = responses[1]
        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        assert "stdout" in result_data
        assert "stderr" in result_data
        assert "exit_code" in result_data

    @pytest.mark.asyncio
    async def test_detect_code_python(self, server_path):
        """Test detecting Python code."""
        text = """
Here's a solution:
```python
import pandas as pd
df = pd.read_csv('data.csv')
print(df.head())
```
"""

        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "detect_code",
                    "arguments": {
                        "text": text
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        result_response = responses[1]
        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]

        if result_text != "null":
            result_data = json.loads(result_text)
            assert "language" in result_data
            assert "code" in result_data
            assert result_data["language"] == "python"
            assert "pandas" in result_data["code"]

    @pytest.mark.asyncio
    async def test_detect_code_r(self, server_path):
        """Test detecting R code."""
        text = """
Try this R code:
```r
data <- read.csv('file.csv')
summary(data)
```
"""

        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "detect_code",
                    "arguments": {
                        "text": text
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        result_response = responses[1]
        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]

        if result_text != "null":
            result_data = json.loads(result_text)
            assert result_data["language"] == "r"

    @pytest.mark.asyncio
    async def test_detect_code_none(self, server_path):
        """Test detecting code when there is none."""
        text = "This is just regular text without any code blocks."

        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "detect_code",
                    "arguments": {
                        "text": text
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        result_response = responses[1]
        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        assert result_text == "null"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
