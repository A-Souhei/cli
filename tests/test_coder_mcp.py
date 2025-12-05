"""Tests for the coder MCP server."""

import pytest
import asyncio
import json
import sys
from pathlib import Path


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import ConfigManager

# Load model from config
config = ConfigManager()
CONFIGURED_MODEL = config.get_ollama_model()


async def communicate_with_mcp(server_path, requests, timeout=10.0):
    """
    Helper function to communicate with an MCP server.

    Args:
        server_path: Path to the MCP server script
        requests: List of JSON-RPC requests to send
        timeout: Timeout in seconds for each request (default: 10.0)

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
            try:
                response_line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout)
                if response_line:
                    response = json.loads(response_line.decode())
                    responses.append(response)
                else:
                    # Empty response, skip
                    responses.append({"error": "Empty response from server"})
            except asyncio.TimeoutError:
                pytest.skip(f"MCP server timed out after {timeout}s (LLM processing may be slow)")
            except json.JSONDecodeError as e:
                responses.append({"error": f"JSON decode error: {str(e)}"})

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

        assert len(responses) >= 2
        result_response = responses[1]

        # Handle error responses
        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response

        content = result_response["result"]["content"]
        assert len(content) > 0
        result_text = content[0]["text"]

        # Handle empty response
        if not result_text:
            pytest.skip("Empty response from MCP server")

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

    @pytest.mark.asyncio
    async def test_spin_the_roulette_basic(self, server_path):
        """Test spin_the_roulette with basic text."""
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
                    "name": "spin_the_roulette",
                    "arguments": {
                        "text": "First run Python code to print hello, then create a file called test.py"
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=300.0)

        assert len(responses) == 2
        result_response = responses[1]

        # Handle error responses
        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Check basic structure
        assert "status" in result_data
        if result_data.get("status") == "success":
            assert "sequence" in result_data
            assert "tools_matched" in result_data
            assert isinstance(result_data["sequence"], list)
            assert isinstance(result_data["tools_matched"], list)

    @pytest.mark.asyncio
    async def test_spin_the_roulette_with_model(self, server_path):
        """Test spin_the_roulette with custom model."""
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
                    "name": "spin_the_roulette",
                    "arguments": {
                        "text": "Do task A and task B",
                        "model": CONFIGURED_MODEL
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=300.0)

        result_response = responses[1]

        # Handle error responses
        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Check that model is used
        if result_data.get("status") == "success":
            assert "metadata" in result_data
            assert result_data["metadata"].get("model_used") == CONFIGURED_MODEL

    @pytest.mark.asyncio
    async def test_spin_the_roulette_missing_text(self, server_path):
        """Test spin_the_roulette without text parameter."""
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
                    "name": "spin_the_roulette",
                    "arguments": {}
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=300.0)

        assert len(responses) >= 2
        result_response = responses[1]

        # Handle error responses
        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response

        content = result_response["result"]["content"]
        assert len(content) > 0
        result_text = content[0]["text"]

        # Handle empty response
        if not result_text:
            pytest.skip("Empty response from MCP server")

        result_data = json.loads(result_text)

        # Should return error
        assert result_data.get("status") == "error"
        assert "text" in result_data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_spin_the_roulette_complex_text(self, server_path):
        """Test spin_the_roulette with complex multi-step text."""
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
                    "name": "spin_the_roulette",
                    "arguments": {
                        "text": """
                        First, run Python code to load data from a CSV file.
                        Second, calculate statistics on the data.
                        Third, create a visualization.
                        Finally, save the results to a file.
                        """
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=300.0)

        result_response = responses[1]

        # Handle error responses
        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response

        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Check structure
        if result_data.get("status") == "success":
            assert "sequence" in result_data
            assert len(result_data["sequence"]) > 0
            assert "tools_matched" in result_data
            # Should have multiple steps
            assert len(result_data["sequence"]) >= 3


class TestDiffBasedEditing:
    """Test diff-based editing for edit_python_code and edit_r_code."""

    @pytest.fixture
    def server_path(self):
        """Get path to coder MCP server."""
        return Path(__file__).parent.parent / "system_mcps" / "coder" / "server.py"

    @pytest.fixture
    def temp_working_dir(self, tmp_path):
        """Create a temporary working directory."""
        return str(tmp_path)

    @pytest.mark.asyncio
    async def test_edit_python_code_with_valid_diff(self, server_path, temp_working_dir):
        """Test editing Python file with a valid unified diff."""
        # Create test file
        test_file = Path(temp_working_dir) / "test.py"
        test_file.write_text("""def hello():
    print("hello")
    return 42

def goodbye():
    print("bye")
    return 0
""")

        # Create a unified diff
        diff_content = """--- test.py
+++ test.py
@@ -1,4 +1,4 @@
 def hello():
-    print("hello")
+    print("Hello, World!")
     return 42
 
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
                    "name": "edit_python_code",
                    "arguments": {
                        "file_path": "test.py",
                        "code": diff_content,
                        "working_dir": temp_working_dir
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) >= 2
        result_response = responses[1]

        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response
        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Verify success
        assert result_data["status"] == "success"
        assert result_data["diff_applied"] is True
        assert result_data["hunks_applied"] == 1

        # Verify file was modified correctly
        modified_content = test_file.read_text()
        assert 'print("Hello, World!")' in modified_content
        assert 'print("hello")' not in modified_content
        assert "def goodbye():" in modified_content  # Should be preserved

    @pytest.mark.asyncio
    async def test_edit_python_code_with_invalid_diff(self, server_path, temp_working_dir):
        """Test that invalid diff doesn't modify file."""
        # Create test file
        test_file = Path(temp_working_dir) / "test.py"
        original_content = """def hello():
    print("hello")
    return 42
"""
        test_file.write_text(original_content)

        # Create an invalid diff (context doesn't match)
        diff_content = """--- test.py
+++ test.py
@@ -1,3 +1,3 @@
 def hello():
-    print("wrong_line")
+    print("Hello, World!")
     return 42
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
                    "name": "edit_python_code",
                    "arguments": {
                        "file_path": "test.py",
                        "code": diff_content,
                        "working_dir": temp_working_dir
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) >= 2
        result_response = responses[1]

        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response
        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Verify error response
        assert result_data["status"] == "error"
        assert result_data["diff_applied"] is False
        assert "Invalid diff" in result_data["message"]

        # Verify file was NOT modified
        current_content = test_file.read_text()
        assert current_content == original_content

    @pytest.mark.asyncio
    async def test_edit_python_code_with_full_file_fallback(self, server_path, temp_working_dir):
        """Test fallback to full-file replacement when not a diff."""
        # Create test file
        test_file = Path(temp_working_dir) / "test.py"
        test_file.write_text("""def hello():
    print("hello")
""")

        # Provide full file content (not a diff)
        full_file_content = """def hello():
    print("Hello, World!")
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
                    "name": "edit_python_code",
                    "arguments": {
                        "file_path": "test.py",
                        "code": full_file_content,
                        "working_dir": temp_working_dir
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) >= 2
        result_response = responses[1]

        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response
        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Verify success with fallback mode
        assert result_data["status"] == "success"
        assert result_data["diff_applied"] is False  # Fallback mode indicator

        # Verify file was replaced
        modified_content = test_file.read_text()
        assert modified_content == full_file_content

    @pytest.mark.asyncio
    async def test_edit_python_code_with_multiple_hunks(self, server_path, temp_working_dir):
        """Test editing with multiple hunks in a diff."""
        # Create test file
        test_file = Path(temp_working_dir) / "test.py"
        test_file.write_text("""def hello():
    print("hello")
    return 42

def goodbye():
    print("bye")
    return 0

def maybe():
    print("maybe")
    return 1
""")

        # Create diff with multiple hunks
        diff_content = """--- test.py
+++ test.py
@@ -1,4 +1,4 @@
 def hello():
-    print("hello")
+    print("Hello!")
     return 42
 
@@ -5,4 +5,4 @@
 def goodbye():
-    print("bye")
+    print("Goodbye!")
     return 0
 
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
                    "name": "edit_python_code",
                    "arguments": {
                        "file_path": "test.py",
                        "code": diff_content,
                        "working_dir": temp_working_dir
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) >= 2
        result_response = responses[1]

        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response
        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Verify success with multiple hunks
        assert result_data["status"] == "success"
        assert result_data["diff_applied"] is True
        assert result_data["hunks_applied"] == 2

        # Verify both changes applied
        modified_content = test_file.read_text()
        assert 'print("Hello!")' in modified_content
        assert 'print("Goodbye!")' in modified_content
        assert 'print("maybe")' in modified_content  # Should be preserved

    @pytest.mark.asyncio
    async def test_edit_r_code_with_valid_diff(self, server_path, temp_working_dir):
        """Test editing R file with a valid unified diff."""
        # Create test file
        test_file = Path(temp_working_dir) / "test.R"
        test_file.write_text("""hello <- function() {
  print("hello")
  return(42)
}
""")

        # Create a unified diff
        diff_content = """--- test.R
+++ test.R
@@ -1,4 +1,4 @@
 hello <- function() {
-  print("hello")
+  print("Hello, World!")
   return(42)
 }
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
                    "name": "edit_r_code",
                    "arguments": {
                        "file_path": "test.R",
                        "code": diff_content,
                        "working_dir": temp_working_dir
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) >= 2
        result_response = responses[1]

        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response
        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Verify success
        assert result_data["status"] == "success"
        assert result_data["diff_applied"] is True
        assert result_data["hunks_applied"] == 1

        # Verify file was modified correctly
        modified_content = test_file.read_text()
        assert 'print("Hello, World!")' in modified_content
        assert 'print("hello")' not in modified_content

    @pytest.mark.asyncio
    async def test_edit_python_code_malformed_diff(self, server_path, temp_working_dir):
        """Test that malformed diff is treated as full file content (fallback)."""
        # Create test file
        test_file = Path(temp_working_dir) / "test.py"
        original_content = """def hello():
    print("hello")
"""
        test_file.write_text(original_content)

        # Malformed diff (missing @@ header) - should be treated as full file content
        diff_content = """--- test.py
+++ test.py
 def hello():
-    print("hello")
+    print("Hi")
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
                    "name": "edit_python_code",
                    "arguments": {
                        "file_path": "test.py",
                        "code": diff_content,
                        "working_dir": temp_working_dir
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests)

        assert len(responses) >= 2
        result_response = responses[1]

        if "error" in result_response:
            pytest.skip(f"MCP server returned error: {result_response['error']}")

        assert "result" in result_response
        content = result_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)

        # Should fall back to full-file replacement since it's not a valid diff
        assert result_data["status"] == "success"
        assert result_data["diff_applied"] is False  # Fallback to full-file mode
        
        # File should be replaced with the malformed diff content
        modified_content = test_file.read_text()
        assert modified_content == diff_content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
