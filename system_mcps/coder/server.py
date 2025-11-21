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

# Add the CLI root to path to import tree utility
cli_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(cli_root))

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("Error: mcp package not found. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Import tree utility
try:
    from src.utils.tree import generate_tree_summary
except ImportError:
    # Fallback if import fails
    def generate_tree_summary(directory: str, max_depth: int = 10) -> dict:
        """Fallback tree generation."""
        return {
            'tree': f"[Tree generation unavailable for {directory}]\n",
            'stats': {'files': 0, 'directories': 0, 'total_size': 0}
        }

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


def get_postgres_api_url() -> str:
    """Get PostgreSQL API URL from environment or use default."""
    return os.getenv('POSTGRES_API_URL', 'http://localhost:15000')


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

    # Get timestamp safely - skip for special markers like __TREE__
    timestamp = None
    if '__TREE__' not in file_path:
        try:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                timestamp = str(file_path_obj.stat().st_mtime)
        except OSError:
            pass  # File may not exist or be inaccessible

    payload = {
        'context_type': context_type,
        'path': file_path,
        'content': content,
        'metadata': {
            'size': len(content),
            'timestamp': timestamp
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
        skipped_files = []
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
                except (OSError, UnicodeDecodeError) as e:
                    # Track files that can't be read
                    skipped_files.append(str(file_path.relative_to(path)))

        message = f"Read {len(files_content)} files from {dir_path}"
        if skipped_files:
            message += f" ({len(skipped_files)} files skipped: {', '.join(skipped_files[:5])}"
            if len(skipped_files) > 5:
                message += f" and {len(skipped_files) - 5} more"
            message += ")"

        return True, message, files_content

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
        ),
        Tool(
            name="verify_file_modifications",
            description=(
                "Verify file modifications by running one of the modified files. "
                "This tool takes a list of files that were created or modified and runs one of them "
                "to verify that the changes are syntactically correct and logically coherent. "
                "It's useful after refactoring operations to ensure no import errors, syntax errors, "
                "or runtime issues were introduced. Returns execution output (stdout/stderr/exit_code)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to run for verification (must be .py, .r, or .R)"
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
            name="retrieve_all_tools",
            description=(
                "Retrieve available MCP tools based on prompts using intelligent semantic matching. "
                "This tool queries the PostgreSQL database with embeddings to find the most relevant "
                "MCP tools for the given prompts. It uses RAG (Retrieval-Augmented Generation) with "
                "semantic similarity to match user intents with available tools across all MCPs. "
                "Returns tool names, descriptions, and similarity scores for each prompt."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompts": {
                        "type": "array",
                        "description": "List of prompts describing what you want to do (e.g., ['Run Python code: print(\"hello\")', 'Edit a file'])",
                        "items": {
                            "type": "string"
                        }
                    }
                },
                "required": ["prompts"]
            }
        ),
        Tool(
            name="roll_the_dice",
            description=(
                "Execute multiple MCP tools iteratively based on semantic search results within a session. "
                "This tool first retrieves relevant tools using retrieve_all_tools, then executes each "
                "tool with inferred parameters. It requires a session_id to maintain context across "
                "multiple tool executions. Results from all tool executions are aggregated and returned. "
                "This is useful for exploratory workflows where you want to try multiple related tools."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompts": {
                        "type": "array",
                        "description": "List of prompts describing what you want to do",
                        "items": {
                            "type": "string"
                        }
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Required session ID for maintaining context across tool executions"
                    },
                    "max_tools": {
                        "type": "integer",
                        "description": "Maximum number of tools to execute (default: 3, max: 10)"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory for tool executions"
                    }
                },
                "required": ["prompts", "session_id"]
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
                "content": content,
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

        # Generate directory tree structure
        full_dir_path = dir_path if os.path.isabs(dir_path) else os.path.join(working_dir, dir_path)
        tree_info = generate_tree_summary(full_dir_path, max_depth=10)
        tree_output = tree_info['tree']
        tree_stats = tree_info['stats']

        # Add tree structure as a special context entry
        tree_context_path = f"{dir_path}/__TREE__"
        tree_result = add_context_to_redis(
            tree_context_path,
            f"Directory Structure for {dir_path}:\n\n{tree_output}\n\nStatistics:\n- Files: {tree_stats['files']}\n- Directories: {tree_stats['directories']}\n- Total Size: {tree_stats['total_size']} bytes",
            session_id,
            "directory_tree"
        )

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
            "files_content": files_content,
            "tree_output": tree_output,
            "tree_added": tree_result.get('status') == 'success',
            "tree_stats": tree_stats,
            "errors": errors,
            "session_id": session_id if session_id else "temporary"
        }, indent=2))]

    elif name == "verify_file_modifications":
        file_path = arguments.get("file_path", "")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not file_path:
            return [TextContent(type="text", text="Error: Missing file_path")]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        # Determine full path
        full_path = file_path if os.path.isabs(file_path) else os.path.join(working_dir, file_path)

        # Check if file exists
        if not os.path.exists(full_path):
            return [TextContent(type="text", text=f"Error: File does not exist: {file_path}")]

        # Check file extension
        if not (file_path.endswith('.py') or file_path.endswith(('.r', '.R'))):
            return [TextContent(type="text", text=f"Error: File must be .py, .r, or .R: {file_path}")]

        # Verify file is readable
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                f.read()  # Just verify it's readable
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading file: {str(e)}")]

        # Determine language and execute the file directly
        try:
            if file_path.endswith('.py'):
                # Run Python file directly
                python_bin = find_cli_venv()
                result = subprocess.run(
                    [python_bin, full_path],
                    capture_output=True,
                    text=True,
                    cwd=working_dir,
                    timeout=30
                )

                return [TextContent(type="text", text=json.dumps({
                    "status": "success",
                    "file_path": file_path,
                    "language": "python",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "verification": "passed" if result.returncode == 0 else "failed"
                }, indent=2))]

            elif file_path.endswith(('.r', '.R')):
                # Run R file directly
                result = subprocess.run(
                    ["Rscript", full_path],
                    capture_output=True,
                    text=True,
                    cwd=working_dir,
                    timeout=30
                )

                return [TextContent(type="text", text=json.dumps({
                    "status": "success",
                    "file_path": file_path,
                    "language": "r",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "verification": "passed" if result.returncode == 0 else "failed"
                }, indent=2))]
        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "file_path": file_path,
                "message": "Execution timed out after 30 seconds"
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "file_path": file_path,
                "message": f"Execution failed: {str(e)}"
            }, indent=2))]

    elif name == "retrieve_all_tools":
        prompts = arguments.get("prompts", [])

        if not prompts:
            return [TextContent(type="text", text="Error: No prompts provided")]

        if not isinstance(prompts, list):
            return [TextContent(type="text", text="Error: prompts must be an array of strings")]

        # Get PostgreSQL API URL
        postgres_api_url = get_postgres_api_url()

        try:
            # Call the PostgreSQL endpoint to retrieve tools based on prompts
            response = requests.post(
                f"{postgres_api_url}/mcp-tools/retrieve",
                json={"prompts": prompts},
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                tools_data = response.json()
                return [TextContent(type="text", text=json.dumps(tools_data, indent=2))]
            else:
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "status_code": response.status_code,
                    "message": f"Failed to retrieve tools from PostgreSQL API",
                    "response": response.text
                }, indent=2))]

        except requests.exceptions.Timeout:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Request to PostgreSQL API timed out (30s limit)"
            }, indent=2))]
        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Could not connect to PostgreSQL API at {postgres_api_url}. Make sure the service is running."
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Error retrieving tools: {str(e)}"
            }, indent=2))]

    elif name == "roll_the_dice":
        prompts = arguments.get("prompts", [])
        session_id = arguments.get("session_id")
        max_tools = arguments.get("max_tools", 3)
        working_dir = arguments.get("working_dir", os.getcwd())

        # Validate session_id (required)
        if not session_id:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "session_id is required. This tool only works within a session."
            }, indent=2))]

        # Validate prompts
        if not prompts:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "No prompts provided"
            }, indent=2))]

        if not isinstance(prompts, list):
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "prompts must be an array of strings"
            }, indent=2))]

        # Validate and cap max_tools
        if max_tools < 1:
            max_tools = 1
        elif max_tools > 10:
            max_tools = 10

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Invalid working directory: {error_msg}"
            }, indent=2))]

        # Get PostgreSQL API URL
        postgres_api_url = get_postgres_api_url()

        try:
            # Step 1: Retrieve tools using the PostgreSQL endpoint
            response = requests.post(
                f"{postgres_api_url}/mcp-tools/retrieve",
                json={"prompts": prompts},
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "message": f"Failed to retrieve tools: {response.status_code}",
                    "response": response.text
                }, indent=2))]

            tools_data = response.json()

            # Step 2: Extract tool information from the response
            # The response format is: {"results": [{"prompt": "...", "tools": [...]}]}
            all_tools = []
            if "results" in tools_data:
                for result in tools_data["results"]:
                    if "tools" in result:
                        all_tools.extend(result["tools"])

            # Remove duplicates by tool_name
            seen_tools = set()
            unique_tools = []
            for tool in all_tools:
                tool_name = tool.get("tool_name")
                if tool_name and tool_name not in seen_tools:
                    seen_tools.add(tool_name)
                    unique_tools.append(tool)

            # Limit to max_tools
            tools_to_execute = unique_tools[:max_tools]

            if not tools_to_execute:
                return [TextContent(type="text", text=json.dumps({
                    "status": "success",
                    "message": "No tools found matching the prompts",
                    "session_id": session_id,
                    "prompts": prompts,
                    "executions": []
                }, indent=2))]

            # Step 3: Execute each tool
            executions = []
            for tool_info in tools_to_execute:
                tool_name = tool_info.get("tool_name")
                tool_description = tool_info.get("description", "")
                similarity_score = tool_info.get("similarity", 0)

                execution_result = {
                    "tool_name": tool_name,
                    "description": tool_description,
                    "similarity_score": similarity_score,
                    "status": "pending"
                }

                try:
                    # Infer parameters based on tool type and prompts
                    tool_arguments = {}

                    if tool_name == "run_python_code":
                        # Try to extract Python code from prompts or use a simple test
                        code = None
                        for prompt in prompts:
                            code_result = detect_code_language(prompt)
                            if code_result and code_result[0] == "python":
                                code = code_result[1]
                                break

                        if not code:
                            # Use a simple test code
                            code = "print('Hello from roll_the_dice!')"

                        tool_arguments = {"code": code, "working_dir": working_dir}

                    elif tool_name == "run_r_code":
                        # Try to extract R code from prompts or use a simple test
                        code = None
                        for prompt in prompts:
                            code_result = detect_code_language(prompt)
                            if code_result and code_result[0] == "r":
                                code = code_result[1]
                                break

                        if not code:
                            # Use a simple test code
                            code = "print('Hello from roll_the_dice!')"

                        tool_arguments = {"code": code, "working_dir": working_dir}

                    elif tool_name == "detect_code":
                        # Use the first prompt as text to analyze
                        tool_arguments = {"text": prompts[0] if prompts else ""}

                    elif tool_name == "add_file_context":
                        # Skip file operations if no file path in prompts
                        execution_result["status"] = "skipped"
                        execution_result["message"] = "No file path found in prompts"
                        executions.append(execution_result)
                        continue

                    elif tool_name == "add_directory_context":
                        # Skip directory operations if no directory path in prompts
                        execution_result["status"] = "skipped"
                        execution_result["message"] = "No directory path found in prompts"
                        executions.append(execution_result)
                        continue

                    else:
                        # Skip unknown tools
                        execution_result["status"] = "skipped"
                        execution_result["message"] = f"Tool '{tool_name}' not supported by roll_the_dice"
                        executions.append(execution_result)
                        continue

                    # Execute the tool by recursively calling call_tool
                    result = await call_tool(tool_name, tool_arguments)

                    # Parse the result
                    if result and len(result) > 0:
                        result_text = result[0].text
                        execution_result["status"] = "executed"
                        execution_result["result"] = result_text
                        try:
                            # Try to parse as JSON for better formatting
                            execution_result["result_json"] = json.loads(result_text)
                        except:
                            pass
                    else:
                        execution_result["status"] = "executed"
                        execution_result["result"] = "No output"

                except Exception as e:
                    execution_result["status"] = "failed"
                    execution_result["error"] = str(e)

                executions.append(execution_result)

            # Step 4: Return aggregated results
            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": f"Executed {len([e for e in executions if e['status'] == 'executed'])} tools",
                "session_id": session_id,
                "prompts": prompts,
                "tools_retrieved": len(unique_tools),
                "tools_attempted": len(tools_to_execute),
                "executions": executions
            }, indent=2))]

        except requests.exceptions.Timeout:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Request to PostgreSQL API timed out (30s limit)"
            }, indent=2))]
        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Could not connect to PostgreSQL API at {postgres_api_url}. Make sure the service is running."
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Error in roll_the_dice: {str(e)}"
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
