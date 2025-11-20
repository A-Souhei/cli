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
import requests
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


def get_redis_api_url() -> str:
    """Get Redis API URL from environment or use default."""
    return os.getenv('REDIS_API_URL', 'http://localhost:17000')


def add_context_to_redis(file_path: str, content: str, session_id: Optional[str] = None, context_type: str = "file") -> dict:
    """
    Add file or directory context to Redis with RAG embedding.

    Args:
        file_path: Path to the file or directory
        content: Content to embed
        session_id: Optional session ID for persistence
        context_type: Type of context ('file' or 'directory')

    Returns:
        Response from Redis API
    """
    redis_api_url = get_redis_api_url()

    payload = {
        'context_type': context_type,
        'path': file_path,
        'content': content,
        'metadata': {
            'size': len(content),
            'timestamp': str(Path(file_path).stat().st_mtime) if Path(file_path).exists() else None
        }
    }

    if session_id:
        payload['session_id'] = session_id

    try:
        response = requests.post(
            f"{redis_api_url}/context/store",
            json=payload,
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def read_file_safe(file_path: str, working_dir: str) -> tuple[bool, str]:
    """
    Safely read a file with validation.

    Args:
        file_path: Path to the file
        working_dir: Working directory for relative paths

    Returns:
        Tuple of (success, content_or_error)
    """
    try:
        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            file_path = os.path.join(working_dir, file_path)

        path = Path(file_path).resolve()

        # Validate the file is within working directory or a safe location
        try:
            path.relative_to(Path(working_dir).resolve())
        except ValueError:
            return False, f"File is outside working directory: {file_path}"

        if not path.exists():
            return False, f"File does not exist: {file_path}"

        if not path.is_file():
            return False, f"Path is not a file: {file_path}"

        # Read file content
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        return True, content

    except Exception as e:
        return False, f"Error reading file: {str(e)}"


def write_file_safe(file_path: str, content: str, working_dir: str) -> tuple[bool, str]:
    """
    Safely write to a file with validation.

    Args:
        file_path: Path to the file
        content: Content to write
        working_dir: Working directory for relative paths

    Returns:
        Tuple of (success, message)
    """
    try:
        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            file_path = os.path.join(working_dir, file_path)

        path = Path(file_path).resolve()

        # Validate the file is within working directory
        try:
            path.relative_to(Path(working_dir).resolve())
        except ValueError:
            return False, f"File is outside working directory: {file_path}"

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write file content
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True, f"Successfully wrote to {file_path}"

    except Exception as e:
        return False, f"Error writing file: {str(e)}"


def read_directory_recursive(dir_path: str, working_dir: str) -> tuple[bool, str, list]:
    """
    Recursively read all files in a directory.

    Args:
        dir_path: Path to the directory
        working_dir: Working directory for relative paths

    Returns:
        Tuple of (success, error_or_message, files_content_list)
    """
    try:
        # Convert to absolute path if relative
        if not os.path.isabs(dir_path):
            dir_path = os.path.join(working_dir, dir_path)

        path = Path(dir_path).resolve()

        # Validate the directory is within working directory
        try:
            path.relative_to(Path(working_dir).resolve())
        except ValueError:
            return False, f"Directory is outside working directory: {dir_path}", []

        if not path.exists():
            return False, f"Directory does not exist: {dir_path}", []

        if not path.is_dir():
            return False, f"Path is not a directory: {dir_path}", []

        # Recursively read all files
        files_content = []
        for file_path in path.rglob('*'):
            if file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        relative_path = file_path.relative_to(path)
                        files_content.append({
                            'path': str(relative_path),
                            'full_path': str(file_path),
                            'content': content
                        })
                except Exception as e:
                    # Skip files that can't be read
                    continue

        return True, f"Read {len(files_content)} files from {dir_path}", files_content

    except Exception as e:
        return False, f"Error reading directory: {str(e)}", []


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
        ),
        Tool(
            name="write_python_code",
            description=(
                "Write Python code to a new file. This tool is used when the user wants to create "
                "a new Python file with code generated by the LLM. The file will be created in the "
                "specified path (relative to working directory). If the file already exists, this "
                "tool will fail. Use edit_python_code for existing files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the Python file to create (e.g., 'script.py' or 'src/utils.py')"
                    },
                    "code": {
                        "type": "string",
                        "description": "The Python code to write to the file"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["file_path", "code"]
            }
        ),
        Tool(
            name="write_r_code",
            description=(
                "Write R code to a new file. This tool is used when the user wants to create "
                "a new R file with code generated by the LLM. The file will be created in the "
                "specified path (relative to working directory). If the file already exists, this "
                "tool will fail. Use edit_r_code for existing files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the R file to create (e.g., 'script.R' or 'src/analysis.R')"
                    },
                    "code": {
                        "type": "string",
                        "description": "The R code to write to the file"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["file_path", "code"]
            }
        ),
        Tool(
            name="edit_python_code",
            description=(
                "Edit an existing Python file. This tool is used when the user wants to modify "
                "an existing Python file. The entire file content will be replaced with the new code. "
                "The file must exist, otherwise this tool will fail. Use write_python_code for new files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the existing Python file to edit"
                    },
                    "code": {
                        "type": "string",
                        "description": "The new Python code to write to the file (replaces entire content)"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["file_path", "code"]
            }
        ),
        Tool(
            name="edit_r_code",
            description=(
                "Edit an existing R file. This tool is used when the user wants to modify "
                "an existing R file. The entire file content will be replaced with the new code. "
                "The file must exist, otherwise this tool will fail. Use write_r_code for new files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the existing R file to edit"
                    },
                    "code": {
                        "type": "string",
                        "description": "The new R code to write to the file (replaces entire content)"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["file_path", "code"]
            }
        ),
        Tool(
            name="add_file_context",
            description=(
                "Add a file's content to the context for better LLM understanding. This tool reads "
                "a file, generates embeddings using RAG (Retrieval-Augmented Generation), and stores "
                "them in Redis for semantic search. The context can be session-specific (persists for "
                "the session duration) or temporary (persists only for the current prompt). The LLM "
                "can then use this context to better understand user requests for code editing or generation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to add to context"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID. If provided, context persists for the session. Otherwise, it's temporary."
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="add_directory_context",
            description=(
                "Add all files in a directory (recursively) to the context for better LLM understanding. "
                "This tool reads all files in a directory and its subdirectories, generates embeddings "
                "using RAG, and stores them in Redis for semantic search. The context can be session-specific "
                "(persists for the session duration) or temporary (persists only for the current prompt). "
                "This is useful when the user wants to work with an entire project or module."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Path to the directory to add to context"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID. If provided, context persists for the session. Otherwise, it's temporary."
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["dir_path"]
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

    elif name == "write_python_code":
        file_path = arguments.get("file_path", "")
        code = arguments.get("code", "")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not file_path or not code:
            return [TextContent(type="text", text="Error: Missing file_path or code")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        # Check if file already exists
        full_path = file_path if os.path.isabs(file_path) else os.path.join(working_dir, file_path)
        if Path(full_path).exists():
            return [TextContent(type="text", text=f"Error: File already exists: {file_path}. Use edit_python_code to modify existing files.")]

        # Write file
        success, message = write_file_safe(file_path, code, working_dir)
        if success:
            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": message,
                "file_path": file_path
            }, indent=2))]
        else:
            return [TextContent(type="text", text=f"Error: {message}")]

    elif name == "write_r_code":
        file_path = arguments.get("file_path", "")
        code = arguments.get("code", "")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not file_path or not code:
            return [TextContent(type="text", text="Error: Missing file_path or code")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        # Check if file already exists
        full_path = file_path if os.path.isabs(file_path) else os.path.join(working_dir, file_path)
        if Path(full_path).exists():
            return [TextContent(type="text", text=f"Error: File already exists: {file_path}. Use edit_r_code to modify existing files.")]

        # Write file
        success, message = write_file_safe(file_path, code, working_dir)
        if success:
            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": message,
                "file_path": file_path
            }, indent=2))]
        else:
            return [TextContent(type="text", text=f"Error: {message}")]

    elif name == "edit_python_code":
        file_path = arguments.get("file_path", "")
        code = arguments.get("code", "")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not file_path or not code:
            return [TextContent(type="text", text="Error: Missing file_path or code")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        # Check if file exists
        full_path = file_path if os.path.isabs(file_path) else os.path.join(working_dir, file_path)
        if not Path(full_path).exists():
            return [TextContent(type="text", text=f"Error: File does not exist: {file_path}. Use write_python_code to create new files.")]

        # Write file
        success, message = write_file_safe(file_path, code, working_dir)
        if success:
            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": message,
                "file_path": file_path
            }, indent=2))]
        else:
            return [TextContent(type="text", text=f"Error: {message}")]

    elif name == "edit_r_code":
        file_path = arguments.get("file_path", "")
        code = arguments.get("code", "")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not file_path or not code:
            return [TextContent(type="text", text="Error: Missing file_path or code")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        # Check if file exists
        full_path = file_path if os.path.isabs(file_path) else os.path.join(working_dir, file_path)
        if not Path(full_path).exists():
            return [TextContent(type="text", text=f"Error: File does not exist: {file_path}. Use write_r_code to create new files.")]

        # Write file
        success, message = write_file_safe(file_path, code, working_dir)
        if success:
            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": message,
                "file_path": file_path
            }, indent=2))]
        else:
            return [TextContent(type="text", text=f"Error: {message}")]

    elif name == "add_file_context":
        file_path = arguments.get("file_path", "")
        session_id = arguments.get("session_id")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not file_path:
            return [TextContent(type="text", text="Error: Missing file_path")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        # Read file
        success, content = read_file_safe(file_path, working_dir)
        if not success:
            return [TextContent(type="text", text=f"Error: {content}")]

        # Add to Redis with embedding
        result = add_context_to_redis(file_path, content, session_id, "file")

        if result.get('status') == 'success':
            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": f"Added file context: {file_path}",
                "file_path": file_path,
                "content_size": len(content),
                "session_id": session_id if session_id else "temporary"
            }, indent=2))]
        else:
            return [TextContent(type="text", text=f"Error adding context: {result.get('message')}")]

    elif name == "add_directory_context":
        dir_path = arguments.get("dir_path", "")
        session_id = arguments.get("session_id")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not dir_path:
            return [TextContent(type="text", text="Error: Missing dir_path")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        # Read directory recursively
        success, message, files_content = read_directory_recursive(dir_path, working_dir)
        if not success:
            return [TextContent(type="text", text=f"Error: {message}")]

        # Add each file to Redis with embeddings
        added_files = []
        errors = []

        for file_info in files_content:
            result = add_context_to_redis(
                file_info['full_path'],
                file_info['content'],
                session_id,
                "directory"
            )

            if result.get('status') == 'success':
                added_files.append(file_info['path'])
            else:
                errors.append(f"{file_info['path']}: {result.get('message')}")

        return [TextContent(type="text", text=json.dumps({
            "status": "success" if len(added_files) > 0 else "error",
            "message": f"Added {len(added_files)} files from directory: {dir_path}",
            "dir_path": dir_path,
            "added_files": added_files,
            "errors": errors,
            "session_id": session_id if session_id else "temporary"
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
