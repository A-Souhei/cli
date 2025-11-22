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


def get_ollama_api_url() -> str:
    """Get Ollama API URL from environment or use default."""
    return os.getenv('OLLAMA_API_URL', 'http://localhost:11434')


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
                "Supported tools: run_python_code, run_r_code, detect_code. "
                "File/directory operations (add_file_context, add_directory_context) are skipped if no paths found. "
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
                "required": ["prompts"]
            }
        ),
        Tool(
            name="spin_the_roulette",
            description=(
                "Convert a long text containing multiple instructions into a structured sequence of steps, "
                "then retrieve matching MCP tools for each step. This tool uses LLM to intelligently split "
                "complex multi-step instructions into individual action items. Each instruction is analyzed to "
                "determine if it contains multiple tool usages, and if so, it's further subdivided. The result "
                "is a flat list of single-instruction steps, each matched with the most appropriate MCP tool. "
                "This is perfect for processing complex user requests that involve multiple sequential operations. "
                "The output is compatible with retrieve_all_tools and can be used directly for tool execution planning."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Long text containing multiple instructions or tasks to be split and analyzed"
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional LLM model to use for text analysis (default: tinyllama)"
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum iterations for subdividing steps (default: 3, max: 5)"
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
                "status": "success" if result.returncode == 0 else "error",
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
                "status": "success" if result.returncode == 0 else "error",
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
        debug_print("retrieve_all_tools called", prompts=prompts)

        if not prompts:
            debug_print("retrieve_all_tools: No prompts provided")
            return [TextContent(type="text", text="Error: No prompts provided")]

        if not isinstance(prompts, list):
            debug_print("retrieve_all_tools: prompts is not a list")
            return [TextContent(type="text", text="Error: prompts must be an array of strings")]

        # Get PostgreSQL API URL
        postgres_api_url = get_postgres_api_url()
        debug_print(f"retrieve_all_tools: Using PostgreSQL API at {postgres_api_url}")

        try:
            # Call the PostgreSQL endpoint to retrieve tools based on prompts
            debug_print(f"retrieve_all_tools: Sending request to {postgres_api_url}/mcp-tools/retrieve")
            response = requests.post(
                f"{postgres_api_url}/mcp-tools/retrieve",
                json={"prompts": prompts},
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            debug_print(f"retrieve_all_tools: Received response with status code {response.status_code}")
            if response.status_code == 200:
                tools_data = response.json()
                debug_print(f"retrieve_all_tools: Successfully retrieved {len(tools_data.get('results', []))} results")
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

        debug_print("roll_the_dice called", prompts=prompts, session_id=session_id, max_tools=max_tools)

        # Validate session_id (required)
        if not session_id:
            debug_print("roll_the_dice: Missing session_id")
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "session_id is required. This tool only works within a session."
            }, indent=2))]

        # Validate prompts
        if not prompts:
            debug_print("roll_the_dice: No prompts provided")
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "No prompts provided"
            }, indent=2))]

        if not isinstance(prompts, list):
            debug_print("roll_the_dice: prompts is not a list")
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "prompts must be an array of strings"
            }, indent=2))]

        # Validate and cap max_tools
        if max_tools < 1:
            max_tools = 1
        elif max_tools > 10:
            max_tools = 10

        debug_print(f"roll_the_dice: max_tools set to {max_tools}")

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            debug_print(f"roll_the_dice: Invalid working directory: {error_msg}")
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Invalid working directory: {error_msg}"
            }, indent=2))]

        # Get PostgreSQL API URL
        postgres_api_url = get_postgres_api_url()
        debug_print(f"roll_the_dice: Using PostgreSQL API at {postgres_api_url}")

        try:
            # Step 1: Retrieve tools using the PostgreSQL endpoint
            debug_print(f"roll_the_dice: Step 1 - Retrieving tools for {len(prompts)} prompts")
            response = requests.post(
                f"{postgres_api_url}/mcp-tools/retrieve",
                json={"prompts": prompts},
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            debug_print(f"roll_the_dice: Received response with status {response.status_code}")
            if response.status_code != 200:
                debug_print(f"roll_the_dice: Failed to retrieve tools - {response.status_code}")
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "message": f"Failed to retrieve tools: {response.status_code}",
                    "response": response.text
                }, indent=2))]

            tools_data = response.json()

            # Step 2: Extract tool information from the response
            # The response format is: {"results": [{"prompt": "...", "best_match": {...}}]}
            debug_print("roll_the_dice: Step 2 - Extracting tool information")
            all_tools = []
            if "results" in tools_data:
                for result in tools_data["results"]:
                    # API returns best_match (single object), not tools (array)
                    if "best_match" in result and result["best_match"] is not None:
                        all_tools.append(result["best_match"])

            debug_print(f"roll_the_dice: Found {len(all_tools)} total tools")

            # Remove duplicates by tool_name
            seen_tools = set()
            unique_tools = []
            for tool in all_tools:
                tool_name = tool.get("tool_name")
                if tool_name and tool_name not in seen_tools:
                    seen_tools.add(tool_name)
                    unique_tools.append(tool)

            debug_print(f"roll_the_dice: {len(unique_tools)} unique tools after deduplication")

            # Limit to max_tools
            tools_to_execute = unique_tools[:max_tools]
            debug_print(f"roll_the_dice: Will attempt to execute {len(tools_to_execute)} tools")

            if not tools_to_execute:
                debug_print("roll_the_dice: No tools found matching the prompts")
                return [TextContent(type="text", text=json.dumps({
                    "status": "success",
                    "message": "No tools found matching the prompts",
                    "session_id": session_id,
                    "prompts": prompts,
                    "tools_retrieved": len(unique_tools),
                    "tools_attempted": 0,
                    "executions": []
                }, indent=2))]

            # Step 3: Execute each tool
            debug_print("roll_the_dice: Step 3 - Executing tools iteratively")
            executions = []
            for idx, tool_info in enumerate(tools_to_execute):
                debug_print(f"roll_the_dice: Iteration {idx + 1}/{len(tools_to_execute)}")
                tool_name = tool_info.get("tool_name")
                tool_description = tool_info.get("description", "")
                similarity_score = tool_info.get("similarity", 0)

                debug_print(f"roll_the_dice: Executing tool '{tool_name}' (similarity: {similarity_score})")

                execution_result = {
                    "tool_name": tool_name,
                    "description": tool_description,
                    "similarity_score": similarity_score,
                    "status": "pending"
                }

                try:
                    # Infer parameters based on tool type and prompts
                    tool_arguments = {}

                    if tool_name == "detect_code":
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

                    elif tool_name in ["write_python_code", "write_r_code", "edit_python_code", "edit_r_code", "run_python_code", "run_r_code"]:
                        # For code-generation tools, use LLM to generate code first
                        debug_print(f"roll_the_dice: Code-generation tool detected: {tool_name}")

                        # Find the corresponding prompt for this tool
                        corresponding_prompt = None
                        results_list = tools_data.get("results", [])
                        for result in results_list:
                            if result.get("best_match", {}).get("tool_name") == tool_name:
                                corresponding_prompt = result.get("prompt", "")
                                break

                        if not corresponding_prompt:
                            corresponding_prompt = prompts[idx] if idx < len(prompts) else ""

                        debug_print(f"roll_the_dice: Using prompt: {corresponding_prompt[:100]}...")

                        # Extract file_path from prompt using @ prefix
                        file_path = None
                        import re
                        file_match = re.search(r'@([\w\-./]+\.(?:py|r|R))', corresponding_prompt)
                        if file_match:
                            file_path = file_match.group(1)
                            debug_print(f"roll_the_dice: Extracted file_path: {file_path}")

                        # For run_python_code/run_r_code, check if we should read existing file
                        code = None
                        if tool_name in ["run_python_code", "run_r_code"] and file_path:
                            # Check if prompt is about running an existing file
                            # More flexible: check if it mentions "file" or "script" with @
                            prompt_lower = corresponding_prompt.lower()
                            is_run_file = (
                                ('file' in prompt_lower and '@' in prompt_lower) or
                                ('script' in prompt_lower and '@' in prompt_lower) or
                                'run @' in prompt_lower or
                                'execute @' in prompt_lower
                            )

                            if is_run_file:
                                debug_print(f"roll_the_dice: Reading file: {file_path}")
                                # Read the file
                                try:
                                    full_path = file_path if os.path.isabs(file_path) else os.path.join(working_dir, file_path)
                                    with open(full_path, 'r') as f:
                                        code = f.read()
                                    debug_print(f"roll_the_dice: File read successfully ({len(code)} chars)")
                                    execution_result["code_source"] = "file"
                                except FileNotFoundError:
                                    execution_result["status"] = "failed"
                                    execution_result["error"] = f"File not found: {file_path}"
                                    executions.append(execution_result)
                                    continue
                                except Exception as e:
                                    execution_result["status"] = "failed"
                                    execution_result["error"] = f"Error reading file: {str(e)}"
                                    executions.append(execution_result)
                                    continue

                        # If we haven't read code from file, generate it with LLM
                        if not code:
                            debug_print(f"roll_the_dice: Generating code with LLM")
                            # Safely extract language from tool_name (e.g., "write_python_code" -> "python")
                            lang_parts = tool_name.split('_')
                            language = lang_parts[1] if len(lang_parts) > 1 else "python"
                            code_prompt = f"Generate {language} code for: {corresponding_prompt}\n\nProvide only the code in a markdown code block."
                            llm_response = call_ollama(code_prompt, model="tinyllama", temperature=0.3)

                            if not llm_response:
                                execution_result["status"] = "failed"
                                execution_result["error"] = "Failed to generate code using LLM"
                                executions.append(execution_result)
                                continue

                            # Detect and extract code from LLM response
                            detected = detect_code_language(llm_response)

                            if not detected:
                                execution_result["status"] = "failed"
                                execution_result["error"] = "No code detected in LLM response"
                                execution_result["llm_response"] = llm_response[:500]  # Include first 500 chars for debugging
                                executions.append(execution_result)
                                continue

                            lang, code = detected
                            debug_print(f"roll_the_dice: Extracted {lang} code ({len(code)} chars)")
                            execution_result["code_source"] = "llm"

                        # Build tool arguments based on tool type
                        if tool_name in ["write_python_code", "write_r_code", "edit_python_code", "edit_r_code"]:
                            # These tools require both code and file_path
                            if not file_path:
                                execution_result["status"] = "failed"
                                execution_result["error"] = "No file path found in prompt (use @ prefix, e.g., @file.py)"
                                executions.append(execution_result)
                                continue

                            tool_arguments = {
                                "file_path": file_path,
                                "code": code,
                                "working_dir": working_dir
                            }
                        elif tool_name in ["run_python_code", "run_r_code"]:
                            # These tools just need code
                            tool_arguments = {
                                "code": code,
                                "working_dir": working_dir
                            }

                        execution_result["code_generated"] = len(code)
                        execution_result["file_path"] = file_path

                    else:
                        # Skip unknown tools
                        execution_result["status"] = "skipped"
                        execution_result["message"] = f"Tool '{tool_name}' not supported by roll_the_dice"
                        executions.append(execution_result)
                        continue

                    # Execute the tool by recursively calling call_tool
                    debug_print(f"roll_the_dice: Calling {tool_name} with arguments", arguments=tool_arguments)
                    result = await call_tool(tool_name, tool_arguments)

                    # Parse the result
                    if result and len(result) > 0:
                        result_text = result[0].text
                        execution_result["status"] = "executed"
                        execution_result["result"] = result_text
                        debug_print(f"roll_the_dice: Tool {tool_name} executed successfully")
                        try:
                            # Try to parse as JSON for better formatting
                            execution_result["result_json"] = json.loads(result_text)
                        except Exception:
                            pass
                    else:
                        execution_result["status"] = "executed"
                        execution_result["result"] = "No output"
                        debug_print(f"roll_the_dice: Tool {tool_name} executed with no output")

                except Exception as e:
                    execution_result["status"] = "failed"
                    execution_result["error"] = str(e)
                    debug_print(f"roll_the_dice: Tool {tool_name} failed with error: {str(e)}")

                executions.append(execution_result)

            # Step 4: Return aggregated results
            executed_count = len([e for e in executions if e['status'] == 'executed'])
            tools_word = "tool" if executed_count == 1 else "tools"
            debug_print(f"roll_the_dice: Step 4 - Completed. Executed {executed_count}/{len(tools_to_execute)} {tools_word}")

            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": f"Executed {executed_count} {tools_word}",
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

    elif name == "spin_the_roulette":
        text = arguments.get("text", "")
        model = arguments.get("model", "tinyllama")
        max_iterations = arguments.get("max_iterations", 3)

        debug_print("spin_the_roulette called", text_length=len(text), model=model, max_iterations=max_iterations)

        # Validate text parameter
        if not text:
            debug_print("spin_the_roulette: No text provided")
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "No text provided"
            }, indent=2))]

        if not isinstance(text, str):
            debug_print("spin_the_roulette: text is not a string")
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "text must be a string"
            }, indent=2))]

        # Validate and cap max_iterations
        if not isinstance(max_iterations, int) or max_iterations < 1:
            max_iterations = 3
        elif max_iterations > 5:
            max_iterations = 5

        debug_print(f"spin_the_roulette: max_iterations set to {max_iterations}")

        # Get PostgreSQL API URL
        postgres_api_url = get_postgres_api_url()
        debug_print(f"spin_the_roulette: Using PostgreSQL API at {postgres_api_url}")

        try:
            # Step 1: Call the text-to-sequence endpoint to split the text
            debug_print(f"spin_the_roulette: Step 1 - Calling text-to-sequence endpoint")
            response = requests.post(
                f"{postgres_api_url}/mcp-tools/text-to-sequence",
                json={
                    "text": text,
                    "model": model,
                    "max_iterations": max_iterations
                },
                headers={"Content-Type": "application/json"},
                timeout=180  # Longer timeout for LLM processing
            )

            debug_print(f"spin_the_roulette: text-to-sequence returned status {response.status_code}")

            if response.status_code != 200:
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "status_code": response.status_code,
                    "message": "Failed to convert text to sequence",
                    "response": response.text
                }, indent=2))]

            sequence_data = response.json()
            if sequence_data.get("status") != "success":
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "message": "text-to-sequence endpoint returned error",
                    "details": sequence_data
                }, indent=2))]

            sequence = sequence_data.get("sequence", [])
            debug_print(f"spin_the_roulette: Step 1 complete - Got {len(sequence)} steps from text-to-sequence")

            if not sequence:
                debug_print("spin_the_roulette: No steps extracted from text")
                return [TextContent(type="text", text=json.dumps({
                    "status": "success",
                    "message": "No instruction steps found in text",
                    "sequence": [],
                    "tools_matched": [],
                    "metadata": sequence_data.get("metadata", {})
                }, indent=2))]

            # Step 2: Use retrieve_all_tools to match each step with MCP tools
            debug_print(f"spin_the_roulette: Step 2 - Calling retrieve endpoint with {len(sequence)} prompts")
            retrieve_response = requests.post(
                f"{postgres_api_url}/mcp-tools/retrieve",
                json={"prompts": sequence},
                headers={"Content-Type": "application/json"},
                timeout=60
            )

            debug_print(f"spin_the_roulette: retrieve endpoint returned status {retrieve_response.status_code}")

            if retrieve_response.status_code != 200:
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "status_code": retrieve_response.status_code,
                    "message": "Failed to retrieve tools for sequence steps",
                    "sequence": sequence,
                    "response": retrieve_response.text
                }, indent=2))]

            tools_data = retrieve_response.json()
            debug_print(f"spin_the_roulette: Step 2 complete - Retrieved tool matches")

            # Step 3: Format and return the results
            results = tools_data.get("results", [])

            # Create a summary of matched tools
            tools_summary = []
            for result in results:
                step_info = {
                    "step": result.get("prompt"),
                    "step_index": result.get("prompt_index"),
                    "best_match": result.get("best_match")
                }
                tools_summary.append(step_info)

            debug_print(f"spin_the_roulette: Step 3 complete - Formatted {len(tools_summary)} results")

            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": f"Successfully processed text into {len(sequence)} steps and matched with tools",
                "sequence": sequence,
                "tools_matched": tools_summary,
                "metadata": {
                    "text_analysis": sequence_data.get("metadata", {}),
                    "tool_retrieval": tools_data.get("metadata", {}),
                    "model_used": model
                }
            }, indent=2))]

        except requests.exceptions.Timeout:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Request timed out. LLM processing may take longer for complex texts."
            }, indent=2))]
        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Could not connect to PostgreSQL API at {postgres_api_url}. Make sure the service is running."
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Error in spin_the_roulette: {str(e)}"
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
