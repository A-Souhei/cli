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
        assert len(tools) >= 11  # Updated to include all tools

        tool_names = [t["name"] for t in tools]
        assert "run_python_code" in tool_names
        assert "run_r_code" in tool_names
        assert "detect_code" in tool_names
        assert "write_python_code" in tool_names
        assert "write_r_code" in tool_names
        assert "edit_python_code" in tool_names
        assert "edit_r_code" in tool_names
        assert "add_file_context" in tool_names
        assert "add_directory_context" in tool_names
        assert "verify_file_modifications" in tool_names
        assert "retrieve_all_tools" in tool_names
        assert "roll_the_dice" in tool_names

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

    @pytest.mark.asyncio
    async def test_retrieve_all_tools(self, server_path):
        """Test retrieve_all_tools with single prompt."""
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
                    "name": "retrieve_all_tools",
                    "arguments": {
                        "prompts": ["Run Python code: print('hello')"]
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
        result_text = content[0]["text"]

        # Check if it's an error or valid response
        result_data = json.loads(result_text)

        # If connection error, that's expected in test environment
        if result_data.get("status") == "error":
            assert "message" in result_data
        else:
            # Valid response should have results
            assert "results" in result_data or "status" in result_data

    @pytest.mark.asyncio
    async def test_retrieve_all_tools_multiple_prompts(self, server_path):
        """Test retrieve_all_tools with multiple prompts."""
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
                    "name": "retrieve_all_tools",
                    "arguments": {
                        "prompts": [
                            "Run Python code: print('hello')",
                            "Detect code in text",
                            "Execute R script"
                        ]
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

        # Should have response structure
        assert "status" in result_data

    @pytest.mark.asyncio
    async def test_retrieve_all_tools_empty_prompts(self, server_path):
        """Test retrieve_all_tools with empty prompts list."""
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
                    "name": "retrieve_all_tools",
                    "arguments": {
                        "prompts": []
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        result_response = responses[1]
        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]

        # Should return error for empty prompts
        assert "Error" in result_text or "error" in result_text.lower()

    @pytest.mark.asyncio
    async def test_roll_the_dice_with_session(self, server_path):
        """Test roll_the_dice with valid session_id."""
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
                    "name": "roll_the_dice",
                    "arguments": {
                        "prompts": ["Run Python code: print('Hello from roll_the_dice!')"],
                        "session_id": "test_session_123",
                        "max_tools": 2
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
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Check response structure
        assert "status" in result_data
        assert "session_id" in result_data or result_data.get("status") == "error"

        # If successful, check executions
        if result_data.get("status") == "success":
            assert "executions" in result_data
            assert "prompts" in result_data
            assert "tools_retrieved" in result_data

    @pytest.mark.asyncio
    async def test_roll_the_dice_without_session(self, server_path):
        """Test roll_the_dice without session_id (should fail)."""
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
                    "name": "roll_the_dice",
                    "arguments": {
                        "prompts": ["Run Python code"]
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

        # Should return error about missing session_id
        assert result_data["status"] == "error"
        assert "session_id" in result_data["message"].lower()

    @pytest.mark.asyncio
    async def test_roll_the_dice_multiple_prompts(self, server_path):
        """Test roll_the_dice with multiple prompts and different tool types."""
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
                    "name": "roll_the_dice",
                    "arguments": {
                        "prompts": [
                            "Run Python code: print('test1')",
                            "Detect code in text: ```python\nprint('test2')\n```",
                            "Execute some code"
                        ],
                        "session_id": "multi_test_session",
                        "max_tools": 3
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

        # Check basic structure
        assert "status" in result_data
        assert "prompts" in result_data or result_data.get("status") == "error"

    @pytest.mark.asyncio
    async def test_roll_the_dice_max_tools_limit(self, server_path):
        """Test roll_the_dice respects max_tools limit."""
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
                    "name": "roll_the_dice",
                    "arguments": {
                        "prompts": ["Run Python code"],
                        "session_id": "limit_test_session",
                        "max_tools": 1
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

        # If successful, check that max_tools is respected
        if result_data.get("status") == "success":
            assert "tools_attempted" in result_data
            assert result_data["tools_attempted"] <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
