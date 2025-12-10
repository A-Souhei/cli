#!/usr/bin/env python3
"""
Tester MCP Server - A Model Context Protocol server for intelligent test planning and execution.

This MCP server provides tools to:
1. Create execution plans from prompts
2. Execute pytest tests
3. Create test files
4. Validate code with unit tests
"""

import os
import sys
import subprocess
import re
import json
import requests
from pathlib import Path
from typing import Any, Optional, List, Dict

# Add the CLI root to path
cli_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(cli_root))

# Debug mode (set via environment variable)
DEBUG_MODE = os.getenv('MCP_DEBUG', 'false').lower() == 'true'

def debug_print(message: str, **kwargs):
    """Print debug messages if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}", file=sys.stderr)
        if kwargs:
            print(f"[DEBUG] Args: {json.dumps(kwargs, indent=2)}", file=sys.stderr)
        sys.stderr.flush()

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("Error: mcp package not found. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Initialize the MCP server
app = Server("tester")


def get_postgres_api_url() -> str:
    """Get PostgreSQL API URL from environment or use default."""
    return os.getenv('POSTGRES_API_URL', 'http://localhost:15000')


def get_ollama_api_url() -> str:
    """Get Ollama API URL from environment or use default."""
    return os.getenv('OLLAMA_API_URL', 'http://localhost:11434')


def validate_working_dir(working_dir: str) -> tuple[bool, str]:
    """
    Validate the working directory to prevent directory traversal attacks.

    Args:
        working_dir: Path to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    try:
        path = Path(working_dir).resolve()
    except (ValueError, OSError) as e:
        return False, f"Invalid path: {str(e)}"

    if not path.exists():
        return False, f"Directory does not exist: {working_dir}"

    if not path.is_dir():
        return False, f"Path is not a directory: {working_dir}"

    # Prevent access to sensitive system directories
    sensitive_dirs = [
        Path("/etc"),
        Path("/sys"),
        Path("/proc"),
        Path("/dev"),
        Path("/root"),
        Path("/boot"),
    ]

    for sensitive_dir in sensitive_dirs:
        try:
            path.relative_to(sensitive_dir)
            return False, f"Access to sensitive directory not allowed: {sensitive_dir}"
        except ValueError:
            continue

    return True, ""


def call_ollama(prompt: str, model: str = "tinyllama", temperature: float = 0.3) -> Optional[str]:
    """
    Call Ollama API to generate text.

    Args:
        prompt: The prompt to send to Ollama
        model: The model to use (default: tinyllama)
        temperature: Temperature for generation (default: 0.3)

    Returns:
        Generated text or None if request fails
    """
    ollama_url = get_ollama_api_url()
    debug_print(f"call_ollama: Calling Ollama at {ollama_url} with model {model}")

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            },
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            generated_text = result.get("response", "")
            debug_print(f"call_ollama: Generated {len(generated_text)} characters")
            return generated_text
        else:
            debug_print(f"call_ollama: Error {response.status_code} - {response.text}")
            return None

    except requests.exceptions.Timeout:
        debug_print("call_ollama: Request timed out")
        return None
    except requests.exceptions.ConnectionError:
        debug_print(f"call_ollama: Could not connect to Ollama at {ollama_url}")
        return None
    except Exception as e:
        debug_print(f"call_ollama: Error - {str(e)}")
        return None


def get_all_available_tools() -> List[Dict[str, Any]]:
    """
    Retrieve all available MCP tools from PostgreSQL API.

    Returns:
        List of tool dictionaries with name, description, mcp_name
    """
    postgres_api_url = get_postgres_api_url()
    debug_print(f"get_all_available_tools: Querying {postgres_api_url}")

    try:
        response = requests.get(
            f"{postgres_api_url}/mcp-tools/all",
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            tools = data.get('tools', [])
            debug_print(f"get_all_available_tools: Retrieved {len(tools)} tools")
            return tools
        else:
            debug_print(f"get_all_available_tools: Error {response.status_code}")
            return []

    except Exception as e:
        debug_print(f"get_all_available_tools: Error - {str(e)}")
        return []


def match_tools_to_steps(steps: List[str]) -> List[Dict[str, Any]]:
    """
    Match execution steps to available MCP tools using semantic search.

    Args:
        steps: List of execution step descriptions

    Returns:
        List of step-tool mappings with tool info and similarity scores
    """
    postgres_api_url = get_postgres_api_url()
    debug_print(f"match_tools_to_steps: Matching {len(steps)} steps")

    try:
        response = requests.post(
            f"{postgres_api_url}/mcp-tools/retrieve",
            json={"prompts": steps},
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            debug_print(f"match_tools_to_steps: Got {len(results)} matches")
            return results
        else:
            debug_print(f"match_tools_to_steps: Error {response.status_code}")
            return []

    except Exception as e:
        debug_print(f"match_tools_to_steps: Error - {str(e)}")
        return []


def create_execution_plan(prompt: str, model: str = "tinyllama") -> Dict[str, Any]:
    """
    Create an execution plan from a user prompt using LLM.

    Args:
        prompt: User's request
        model: LLM model to use for planning

    Returns:
        Dictionary with plan details including steps and matched tools
    """
    debug_print(f"create_execution_plan: Creating plan for prompt")

    # Create a planning prompt for the LLM
    planning_prompt = f"""You are an expert software developer and tester. Analyze the following user request and create a detailed execution plan.

User Request: {prompt}

Create a step-by-step plan to accomplish this request. Each step should be:
1. Clear and actionable
2. Focused on a single task
3. Include specific file names or paths if mentioned
4. Consider testing requirements

Format your response as a numbered list of steps. Be specific and practical.

Example format:
1. Create a Python file called script.py with the required function
2. Write unit tests in test_script.py to validate the function
3. Run the tests using pytest
4. Execute the script to verify it works

Now create the plan:"""

    # Call LLM to generate plan
    llm_response = call_ollama(planning_prompt, model=model, temperature=0.3)
    
    if not llm_response:
        return {
            "status": "error",
            "message": "Failed to generate plan from LLM",
            "steps": []
        }

    # Parse the response to extract steps
    steps = []
    for line in llm_response.split('\n'):
        line = line.strip()
        # Match numbered items like "1.", "2)", "1 -", etc.
        match = re.match(r'^(\d+)[.):\-\s]+(.+)$', line)
        if match:
            step_text = match.group(2).strip()
            if step_text:
                steps.append(step_text)

    debug_print(f"create_execution_plan: Extracted {len(steps)} steps from LLM response")

    if not steps:
        # Fallback: split by newlines if no numbered items found
        steps = [line.strip() for line in llm_response.split('\n') if line.strip() and not line.strip().startswith('#')]

    return {
        "status": "success",
        "steps": steps,
        "raw_response": llm_response
    }


def find_cli_venv() -> Optional[str]:
    """Find the virtual environment for the CLI."""
    cli_root = Path(__file__).parent.parent.parent
    venv_paths = [
        cli_root / "venv",
        cli_root / ".venv",
        cli_root / "env",
    ]

    for venv_path in venv_paths:
        python_bin = venv_path / "bin" / "python"
        if python_bin.exists():
            return str(python_bin)

    return sys.executable


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="plan_mode",
            description=(
                "Intelligent planning mode that detects code writing/updating tasks and creates execution plans. "
                "This tool analyzes user prompts, generates a step-by-step TODO list, retrieves all available MCP tools, "
                "matches each step with the best tool, and executes iterations with accumulative context. "
                "It validates success through user feedback or unit tests. "
                "Keywords to trigger: 'plan', 'test', 'testing', 'validate', 'plan and test', etc. "
                "Use this when you want a comprehensive plan-test-execute workflow."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "User's request describing what code to write/update and test"
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional LLM model to use for planning (default: tinyllama)"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    },
                    "auto_execute": {
                        "type": "boolean",
                        "description": "If true, automatically execute the plan. If false, return plan for user review (default: false)"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID for maintaining context across executions"
                    }
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="run_pytest",
            description=(
                "Execute pytest tests in a specified directory or file. "
                "Runs pytest with options like verbose output, coverage, and specific test selection. "
                "Returns test results including pass/fail status, output, and coverage information. "
                "Use this to validate code with unit tests."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Path to test file or directory (e.g., 'tests/', 'test_example.py', 'tests/test_module.py::test_function')"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Enable verbose output (default: true)"
                    },
                    "coverage": {
                        "type": "boolean",
                        "description": "Enable coverage reporting (default: false)"
                    },
                    "extra_args": {
                        "type": "string",
                        "description": "Additional pytest arguments (e.g., '-k test_name', '--maxfail=1')"
                    }
                },
                "required": ["test_path"]
            }
        ),
        Tool(
            name="create_pytest_test",
            description=(
                "Create a basic pytest test file with common test patterns. "
                "Generates a test file template with imports, fixtures, and test functions. "
                "Use this to quickly scaffold test files for your code."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "test_file_path": {
                        "type": "string",
                        "description": "Path where the test file should be created (e.g., 'tests/test_module.py')"
                    },
                    "module_to_test": {
                        "type": "string",
                        "description": "Name or path of the module being tested (e.g., 'src.module', 'module.py')"
                    },
                    "test_functions": {
                        "type": "array",
                        "description": "List of test function names to create (e.g., ['test_addition', 'test_validation'])",
                        "items": {
                            "type": "string"
                        }
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["test_file_path"]
            }
        ),
        Tool(
            name="validate_with_test",
            description=(
                "Validate code by running associated tests and return pass/fail status. "
                "This combines test execution with validation logic to determine if code meets requirements. "
                "Returns a structured validation result with test output and recommendations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code_file": {
                        "type": "string",
                        "description": "Path to the code file to validate"
                    },
                    "test_file": {
                        "type": "string",
                        "description": "Path to the test file (if not provided, will try to infer from code_file)"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["code_file"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""

    if name == "plan_mode":
        prompt = arguments.get("prompt", "")
        model = arguments.get("model", "tinyllama")
        working_dir = arguments.get("working_dir", os.getcwd())
        auto_execute = arguments.get("auto_execute", False)
        session_id = arguments.get("session_id")

        if not prompt:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "No prompt provided"
            }, indent=2))]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": error_msg
            }, indent=2))]

        debug_print(f"plan_mode: Starting with prompt: {prompt[:100]}...")

        try:
            # Step 1: Create execution plan
            debug_print("plan_mode: Step 1 - Creating execution plan")
            plan_result = create_execution_plan(prompt, model=model)

            if plan_result.get("status") != "success":
                return [TextContent(type="text", text=json.dumps(plan_result, indent=2))]

            steps = plan_result.get("steps", [])
            if not steps:
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "message": "No execution steps generated from prompt",
                    "raw_response": plan_result.get("raw_response", "")
                }, indent=2))]

            debug_print(f"plan_mode: Generated {len(steps)} execution steps")

            # Step 2: Get all available tools
            debug_print("plan_mode: Step 2 - Retrieving all available MCP tools")
            all_tools = get_all_available_tools()
            debug_print(f"plan_mode: Found {len(all_tools)} available tools")

            # Step 3: Match steps to tools
            debug_print("plan_mode: Step 3 - Matching steps to tools")
            matched_steps = match_tools_to_steps(steps)
            
            # Build step execution plan
            execution_plan = []
            for i, match_result in enumerate(matched_steps):
                step_text = match_result.get("prompt", steps[i] if i < len(steps) else "")
                best_match = match_result.get("best_match")
                
                step_info = {
                    "step_number": i + 1,
                    "description": step_text,
                    "tool": best_match.get("tool_name") if best_match else None,
                    "mcp_name": best_match.get("mcp_name") if best_match else None,
                    "similarity": best_match.get("similarity") if best_match else 0,
                    "status": "pending"
                }
                execution_plan.append(step_info)

            # Return plan (execution will be handled by the caller if auto_execute is True)
            result = {
                "status": "success",
                "message": f"Created execution plan with {len(steps)} steps",
                "prompt": prompt,
                "model_used": model,
                "working_dir": working_dir,
                "session_id": session_id,
                "total_steps": len(steps),
                "available_tools": len(all_tools),
                "execution_plan": execution_plan,
                "raw_plan_response": plan_result.get("raw_response", "")
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Error in plan_mode: {str(e)}"
            }, indent=2))]

    elif name == "run_pytest":
        test_path = arguments.get("test_path", "")
        working_dir = arguments.get("working_dir", os.getcwd())
        verbose = arguments.get("verbose", True)
        coverage = arguments.get("coverage", False)
        extra_args = arguments.get("extra_args", "")

        if not test_path:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "No test_path provided"
            }, indent=2))]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": error_msg
            }, indent=2))]

        try:
            # Find pytest in the CLI venv
            python_exec = find_cli_venv()
            
            # Build pytest command
            cmd = [python_exec, "-m", "pytest"]
            
            if verbose:
                cmd.append("-v")
            
            if coverage:
                cmd.extend(["--cov", "--cov-report=term"])
            
            if extra_args:
                cmd.extend(extra_args.split())
            
            cmd.append(test_path)

            debug_print(f"run_pytest: Executing: {' '.join(cmd)}")

            # Run pytest
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            output = {
                "status": "success" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "test_path": test_path,
                "working_dir": working_dir,
                "command": " ".join(cmd)
            }

            return [TextContent(type="text", text=json.dumps(output, indent=2))]

        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Pytest execution timed out (120s limit)"
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Error running pytest: {str(e)}"
            }, indent=2))]

    elif name == "create_pytest_test":
        test_file_path = arguments.get("test_file_path", "")
        module_to_test = arguments.get("module_to_test", "")
        test_functions = arguments.get("test_functions", [])
        working_dir = arguments.get("working_dir", os.getcwd())

        if not test_file_path:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "No test_file_path provided"
            }, indent=2))]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": error_msg
            }, indent=2))]

        try:
            # Build full path
            full_path = test_file_path if os.path.isabs(test_file_path) else os.path.join(working_dir, test_file_path)
            
            # Create parent directories if needed
            Path(full_path).parent.mkdir(parents=True, exist_ok=True)

            # Generate test template
            test_content = f'''"""Tests for {module_to_test or 'module'}."""

import pytest
'''
            
            if module_to_test:
                test_content += f"# from {module_to_test} import *\n"
            
            test_content += "\n\n"

            # Add pytest fixtures example
            test_content += '''@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {"key": "value"}


'''

            # Add test functions
            if test_functions:
                for func_name in test_functions:
                    # Ensure proper test_ prefix
                    if not func_name.startswith("test_"):
                        func_name = f"test_{func_name}"
                    
                    test_content += f'''def {func_name}():
    """Test for {func_name.replace('test_', '')}."""
    # TODO: Implement test
    assert True


'''
            else:
                # Add a default test
                test_content += '''def test_example():
    """Example test case."""
    assert True
'''

            # Write the file
            with open(full_path, 'w') as f:
                f.write(test_content)

            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": f"Created test file: {test_file_path}",
                "test_file_path": test_file_path,
                "full_path": str(full_path),
                "test_functions_created": len(test_functions) if test_functions else 1,
                "content": test_content
            }, indent=2))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Error creating test file: {str(e)}"
            }, indent=2))]

    elif name == "validate_with_test":
        code_file = arguments.get("code_file", "")
        test_file = arguments.get("test_file")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not code_file:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "No code_file provided"
            }, indent=2))]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": error_msg
            }, indent=2))]

        try:
            # If no test file specified, try to infer it
            if not test_file:
                # Common patterns: module.py -> test_module.py or tests/test_module.py
                code_path = Path(code_file)
                test_candidates = [
                    f"test_{code_path.name}",
                    f"tests/test_{code_path.name}",
                    f"test/test_{code_path.name}",
                ]
                
                for candidate in test_candidates:
                    candidate_path = os.path.join(working_dir, candidate)
                    if os.path.exists(candidate_path):
                        test_file = candidate
                        break
                
                if not test_file:
                    return [TextContent(type="text", text=json.dumps({
                        "status": "error",
                        "message": f"Could not find test file for {code_file}. Tried: {test_candidates}"
                    }, indent=2))]

            # Run the tests
            python_exec = find_cli_venv()
            cmd = [python_exec, "-m", "pytest", "-v", test_file]
            
            debug_print(f"validate_with_test: Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            # Parse the output to determine validation
            passed = result.returncode == 0
            
            validation_result = {
                "status": "success",
                "code_file": code_file,
                "test_file": test_file,
                "validation_passed": passed,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "recommendation": "Code is valid and tests pass!" if passed else "Tests failed. Review the output and fix issues."
            }

            return [TextContent(type="text", text=json.dumps(validation_result, indent=2))]

        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Test execution timed out (120s limit)"
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Error validating with test: {str(e)}"
            }, indent=2))]

    else:
        return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
