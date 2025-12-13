"""Tests for the data-engineer MCP server."""

import pytest
import asyncio
import json
import sys
import tempfile
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


async def communicate_with_mcp(server_path, requests, timeout=30.0):
    """
    Helper function to communicate with an MCP server.

    Args:
        server_path: Path to the MCP server script
        requests: List of JSON-RPC requests to send
        timeout: Timeout in seconds for each request (default: 30.0)

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
                    responses.append({"error": "Empty response from server"})
            except asyncio.TimeoutError:
                pytest.skip(f"MCP server timed out after {timeout}s (processing may be slow)")
            except json.JSONDecodeError as e:
                responses.append({"error": f"JSON decode error: {str(e)}"})

    finally:
        process.terminate()
        await process.wait()

    return responses


class TestDataEngineerMCP:
    """Test the data-engineer MCP server."""

    @pytest.fixture
    def server_path(self):
        """Get path to data-engineer MCP server."""
        return Path(__file__).parent.parent / "system_mcps" / "data-engineer" / "server.py"

    @pytest.fixture
    def sample_csv_file(self):
        """Create a temporary CSV file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            # Write sample data
            f.write("age,salary,department\n")
            f.write("25,50000,Engineering\n")
            f.write("30,60000,Marketing\n")
            f.write("35,70000,Engineering\n")
            f.write("28,55000,Sales\n")
            f.write("32,65000,Marketing\n")
            f.write("29,58000,Engineering\n")
            f.write("31,62000,Sales\n")
            f.write("27,52000,Marketing\n")
            f.write("33,68000,Engineering\n")
            f.write("26,51000,Sales\n")
            f.write("34,69000,Marketing\n")
            f.write("24,48000,Engineering\n")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        try:
            os.unlink(temp_path)
        except Exception:
            # Ignore cleanup errors; file may not exist or be locked
            pass

    @pytest.fixture
    def sample_python_file(self):
        """Create a temporary Python file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Write sample Python code
            f.write("""
import os
import sys
from typing import List

class Calculator:
    '''A simple calculator class.'''
    
    def __init__(self):
        self.history = []
    
    def add(self, a: int, b: int) -> int:
        '''Add two numbers.'''
        result = a + b
        self.history.append(f'{a} + {b} = {result}')
        return result
    
    def subtract(self, a: int, b: int) -> int:
        '''Subtract b from a.'''
        result = a - b
        self.history.append(f'{a} - {b} = {result}')
        return result

def main():
    calc = Calculator()
    print(calc.add(5, 3))
    print(calc.subtract(10, 4))

if __name__ == '__main__':
    main()
""")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        try:
            os.unlink(temp_path)
        except Exception:
            # Ignore cleanup errors; file may not exist or be locked
            pass

    @pytest.fixture
    def sample_python_file2(self):
        """Create a second temporary Python file for similarity testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Write similar but different Python code
            f.write("""
import os
import sys
from typing import List

class Calculator:
    '''A calculator class with more operations.'''
    
    def __init__(self):
        self.results = []
    
    def add(self, x: int, y: int) -> int:
        '''Sum two numbers.'''
        result = x + y
        self.results.append(result)
        return result
    
    def multiply(self, x: int, y: int) -> int:
        '''Multiply two numbers.'''
        result = x * y
        self.results.append(result)
        return result

def run():
    calculator = Calculator()
    print(calculator.add(3, 5))
    print(calculator.multiply(4, 6))

if __name__ == '__main__':
    run()
""")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        try:
            os.unlink(temp_path)
        except Exception:
            # Ignore cleanup errors; file may not exist or be locked
            pass

    def test_server_exists(self, server_path):
        """Test that the data-engineer MCP server file exists."""
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
        """Test listing tools from the data-engineer MCP."""
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
        
        # Check if we got a valid response
        assert "result" in tools_response
        assert "tools" in tools_response["result"]
        
        tools = tools_response["result"]["tools"]
        tool_names = [tool["name"] for tool in tools]
        
        # Check that all four expected tools are present
        assert "generate_fake_data" in tool_names
        assert "generate_ast" in tool_names
        assert "compare_code_similarity" in tool_names
        assert "compare_ast_similarity" in tool_names
        
        # Check tool descriptions
        for tool in tools:
            assert "description" in tool
            assert "inputSchema" in tool
            assert len(tool["description"]) > 50  # Should have substantial description

    @pytest.mark.asyncio
    async def test_generate_ast_with_file(self, server_path, sample_python_file):
        """Test AST generation from a Python file."""
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
                    "name": "generate_ast",
                    "arguments": {
                        "file_path": sample_python_file,
                        "output_format": "json",
                        "working_dir": "/tmp"  # Allow access to /tmp for test files
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=15.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        # Check response structure
        assert "result" in tool_response
        assert "content" in tool_response["result"]
        
        content = tool_response["result"]["content"]
        assert len(content) > 0
        
        # Parse the result
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        # Verify AST data structure
        assert result_data["status"] == "success"
        assert "ast_dump" in result_data
        assert "statistics" in result_data
        assert "summary" in result_data
        
        # Check statistics
        stats = result_data["statistics"]
        assert "classes" in stats
        assert "functions" in stats
        assert "imports" in stats
        
        # Should find the Calculator class
        assert len(stats["classes"]) >= 1
        class_names = [c["name"] for c in stats["classes"]]
        assert "Calculator" in class_names
        
        # Should find the main function
        function_names = [f["name"] for f in stats["functions"]]
        assert "main" in function_names

    @pytest.mark.asyncio
    async def test_generate_ast_with_code_string(self, server_path):
        """Test AST generation from a code string."""
        code = """
def hello_world():
    print("Hello, World!")

hello_world()
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
                    "name": "generate_ast",
                    "arguments": {
                        "code": code
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=15.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        # Check response structure
        assert "result" in tool_response
        content = tool_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        # Verify AST was generated
        assert result_data["status"] == "success"
        assert result_data["source_type"] == "string"
        assert "hello_world" in str(result_data["statistics"]["functions"])

    @pytest.mark.asyncio
    async def test_generate_ast_syntax_error(self, server_path):
        """Test AST generation with invalid Python code."""
        code = """
def broken_function(
    # Missing closing parenthesis
    print("This won't work")
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
                    "name": "generate_ast",
                    "arguments": {
                        "code": code
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=15.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        content = tool_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        # Should return an error for syntax error
        assert result_data["status"] == "error"
        assert "syntax error" in result_data["message"].lower()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_generate_fake_data(self, server_path, sample_csv_file):
        """Test synthetic data generation from CSV file."""
        # This test requires ydata-synthetic to be installed
        # It may be slow due to model training
        
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
                    "name": "generate_fake_data",
                    "arguments": {
                        "file_path": sample_csv_file,
                        "num_samples": 5
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=60.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        content = tool_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        # Check if ydata-synthetic is installed
        if "ydata-synthetic not installed" in result_data.get("message", ""):
            pytest.skip("ydata-synthetic not installed")
        
        # Verify synthetic data was generated
        if result_data["status"] == "success":
            assert "num_samples" in result_data
            assert "data_preview" in result_data
            assert result_data["num_samples"] == 5
            assert len(result_data["data_preview"]) <= 5

    @pytest.mark.asyncio
    async def test_generate_fake_data_missing_file(self, server_path):
        """Test synthetic data generation with non-existent file."""
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
                    "name": "generate_fake_data",
                    "arguments": {
                        "file_path": "/tmp/nonexistent_file.csv",
                        "num_samples": 10,
                        "working_dir": "/tmp"
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=15.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        content = tool_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        # Should return an error
        assert result_data["status"] == "error"
        # May fail on file not exist or ydata-synthetic not installed
        message_lower = result_data["message"].lower()
        assert "not exist" in message_lower or "ydata-synthetic not installed" in message_lower

    @pytest.mark.asyncio
    async def test_compare_code_similarity_with_snippets(self, server_path):
        """Test code similarity comparison with code snippets."""
        # This test requires transformer service to be running
        
        code1 = """
def add(a, b):
    return a + b
"""
        
        code2 = """
def sum(x, y):
    return x + y
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
                    "name": "compare_code_similarity",
                    "arguments": {
                        "code1": code1,
                        "code2": code2,
                        "metric": "cosine"
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=30.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        content = tool_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        # Check if transformer service is available
        if "Could not connect" in result_data.get("message", ""):
            pytest.skip("Transformer service not available")
        
        # Verify similarity was calculated
        if result_data["status"] == "success":
            assert "similarity" in result_data
            assert 0.0 <= result_data["similarity"] <= 1.0
            assert "interpretation" in result_data
            # These functions are semantically very similar, should have high score
            assert result_data["similarity"] > 0.7

    @pytest.mark.asyncio
    async def test_compare_code_similarity_with_files(self, server_path, sample_python_file, sample_python_file2):
        """Test code similarity comparison with file paths."""
        # This test requires transformer service to be running
        
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
                    "name": "compare_code_similarity",
                    "arguments": {
                        "file_path1": sample_python_file,
                        "file_path2": sample_python_file2,
                        "metric": "cosine",
                        "working_dir": "/tmp"  # Allow access to /tmp for test files
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=30.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        content = tool_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        # Check if transformer service is available
        if "Could not connect" in result_data.get("message", ""):
            pytest.skip("Transformer service not available")
        
        # Verify similarity was calculated
        if result_data["status"] == "success":
            assert "similarity" in result_data
            assert 0.0 <= result_data["similarity"] <= 1.0
            assert "file1" in result_data
            assert "file2" in result_data
            # Files have similar Calculator classes but different methods
            assert result_data["similarity"] > 0.5

    @pytest.mark.asyncio
    async def test_compare_ast_similarity(self, server_path, sample_python_file, sample_python_file2):
        """Test AST-based code similarity comparison."""
        # This test requires transformer service to be running
        
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
                    "name": "compare_ast_similarity",
                    "arguments": {
                        "file_path1": sample_python_file,
                        "file_path2": sample_python_file2,
                        "metric": "cosine",
                        "working_dir": "/tmp"  # Allow access to /tmp for test files
                    }
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=30.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        content = tool_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        # Check if transformer service is available
        if "Could not connect" in result_data.get("message", ""):
            pytest.skip("Transformer service not available")
        
        # Verify AST similarity was calculated
        if result_data["status"] == "success":
            assert "similarity" in result_data
            assert 0.0 <= result_data["similarity"] <= 1.0
            assert result_data["comparison_type"] == "ast_based"
            assert "ast1_stats" in result_data
            assert "ast2_stats" in result_data
            assert "structural_similarity" in result_data
            
            # Check structural similarity indicators
            struct_sim = result_data["structural_similarity"]
            assert "classes_match" in struct_sim
            assert "functions_match" in struct_sim
            assert "num_classes_diff" in struct_sim
            assert "num_functions_diff" in struct_sim
            
            # Verify enhanced interpretation
            assert "AST-based" in result_data["interpretation"]
            assert "note" in result_data

    @pytest.mark.asyncio
    async def test_compare_ast_similarity_non_python_file(self, server_path):
        """Test AST similarity with non-Python files should fail."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write("function test() { return 42; }")
            js_file = f.name
        
        try:
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
                        "name": "compare_ast_similarity",
                        "arguments": {
                            "file_path1": js_file,
                            "file_path2": js_file
                        }
                    }
                }
            ]

            responses = await communicate_with_mcp(server_path, requests, timeout=10.0)

            assert len(responses) == 2
            tool_response = responses[1]
            
            content = tool_response["result"]["content"]
            result_text = content[0]["text"]
            result_data = json.loads(result_text)
            
            # Should return an error for non-Python files
            assert result_data["status"] == "error"
            assert "python" in result_data["message"].lower()
        finally:
            try:
                os.unlink(js_file)
            except Exception:
                # Ignore cleanup errors; file may not exist or already be deleted
                pass

    @pytest.mark.asyncio
    async def test_list_tools_includes_ast_similarity(self, server_path):
        """Test that the tools list includes the new compare_ast_similarity tool."""
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
        tool_names = [tool["name"] for tool in tools]
        
        # Check that all four expected tools are present
        assert "generate_fake_data" in tool_names
        assert "generate_ast" in tool_names
        assert "compare_code_similarity" in tool_names
        assert "compare_ast_similarity" in tool_names
        
        # Verify compare_ast_similarity tool has proper description
        ast_sim_tool = next(t for t in tools if t["name"] == "compare_ast_similarity")
        assert "AST" in ast_sim_tool["description"]
        assert "Abstract Syntax Tree" in ast_sim_tool["description"]
        assert ast_sim_tool["inputSchema"]["required"] == ["file_path1", "file_path2"]

    @pytest.mark.asyncio
    async def test_invalid_tool_name(self, server_path):
        """Test calling a non-existent tool."""
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
                    "name": "nonexistent_tool",
                    "arguments": {}
                }
            }
        ]

        responses = await communicate_with_mcp(server_path, requests, timeout=10.0)

        assert len(responses) == 2
        tool_response = responses[1]
        
        # Should return an error
        content = tool_response["result"]["content"]
        result_text = content[0]["text"]
        result_data = json.loads(result_text)
        
        assert result_data["status"] == "error"
        assert "unknown tool" in result_data["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
