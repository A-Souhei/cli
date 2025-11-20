#!/usr/bin/env python3
"""
Coder MCP Server - A Model Context Protocol server for running Python and R code.

This MCP server provides tools to execute Python and R code, as well as detect
code snippets from text responses.
"""

import os
import sys
import subprocess
import re
import json
from pathlib import Path
from typing import Any, Optional

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("Error: mcp package not found. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Initialize the MCP server
app = Server("coder")


def find_cli_venv() -> Optional[str]:
    """
    Find the virtual environment for the CLI.
    Looks for common venv locations relative to the script.
    """
    # Get the CLI root directory (assuming this script is in system_mcps/coder/)
    cli_root = Path(__file__).parent.parent.parent

    # Common venv locations
    venv_paths = [
        cli_root / "venv",
        cli_root / ".venv",
        cli_root / "env",
    ]

    for venv_path in venv_paths:
        python_bin = venv_path / "bin" / "python"
        if python_bin.exists():
            return str(python_bin)

    # If no venv found, return system python
    return sys.executable


def validate_working_dir(working_dir: str) -> tuple[bool, str]:
    """
    Validate the working directory to prevent directory traversal attacks.

    Args:
        working_dir: Path to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    # Convert to Path object for better path handling
    try:
        path = Path(working_dir).resolve()
    except (ValueError, OSError) as e:
        return False, f"Invalid path: {str(e)}"

    # Check if path exists
    if not path.exists():
        return False, f"Directory does not exist: {working_dir}"

    # Check if it's a directory
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
            # Check if working_dir is under a sensitive directory
            path.relative_to(sensitive_dir)
            return False, f"Access to sensitive directory not allowed: {sensitive_dir}"
        except ValueError:
            # Not under this sensitive directory, continue checking
            continue

    return True, ""


def detect_code_language(text: str) -> Optional[tuple[str, str]]:
    """
    Detect if text contains Python or R code blocks.

    Returns:
        Tuple of (language, code) if code is detected, None otherwise.
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
            return (lang, match.group(1).strip())

    # Check for generic code blocks and try to detect language by content
    generic_match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if generic_match:
        code = generic_match.group(1).strip()
        # Simple heuristics
        if any(keyword in code for keyword in ["import ", "def ", "print(", "if __name__"]):
            return ("python", code)
        elif any(keyword in code for keyword in ["<-", "library(", "data.frame"]):
            return ("r", code)

    return None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="run_python_code",
            description=(
                "Execute Python code in the CLI's virtual environment. "
                "The code runs from the current working directory where the CLI was opened. "
                "This tool uses the same Python environment as the CLI, so all installed packages "
                "in requirements.txt (pandas, numpy, scikit-learn, etc.) are available. "
                "Returns the stdout, stderr, and exit code of the execution."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="run_r_code",
            description=(
                "Execute R code using the host system's R installation. "
                "The code runs from the current working directory where the CLI was opened. "
                "This tool relies on R being installed on the host system, along with any "
                "required R libraries. Returns the stdout, stderr, and exit code of the execution."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The R code to execute"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="detect_code",
            description=(
                "Detect and extract Python or R code from a text response. "
                "This tool analyzes text (such as LLM responses) and identifies code blocks "
                "marked with language specifiers (```python or ```r). If code is detected, "
                "it returns a JSON object with 'language' (python/r) and 'code' fields. "
                "If no code is detected, returns None."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to analyze for code content"
                    }
                },
                "required": ["text"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""

    if name == "run_python_code":
        code = arguments.get("code", "")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not code:
            return [TextContent(type="text", text="Error: No code provided")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        # Find the CLI's Python executable
        python_exec = find_cli_venv()

        try:
            # Run the code
            result = subprocess.run(
                [python_exec, "-c", code],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "python_executable": python_exec
            }

            return [TextContent(type="text", text=json.dumps(output, indent=2))]

        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text="Error: Code execution timed out (30s limit)")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error executing Python code: {str(e)}")]

    elif name == "run_r_code":
        code = arguments.get("code", "")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not code:
            return [TextContent(type="text", text="Error: No code provided")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        try:
            # Check if R is installed
            r_check = subprocess.run(
                ["which", "R"],
                capture_output=True,
                text=True
            )

            if r_check.returncode != 0:
                return [TextContent(
                    type="text",
                    text="Error: R is not installed or not found in PATH. Please install R on your system."
                )]

            # Run the R code
            result = subprocess.run(
                ["R", "--vanilla", "--slave", "-e", code],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }

            return [TextContent(type="text", text=json.dumps(output, indent=2))]

        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text="Error: Code execution timed out (30s limit)")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error executing R code: {str(e)}")]

    elif name == "detect_code":
        text = arguments.get("text", "")

        if not text:
            return [TextContent(type="text", text="null")]

        result = detect_code_language(text)

        if result:
            lang, code = result
            output = {
                "language": lang,
                "code": code
            }
            return [TextContent(type="text", text=json.dumps(output, indent=2))]
        else:
            return [TextContent(type="text", text="null")]

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
