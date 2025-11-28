"""Main entry point for the AI CLI application."""

import sys
import json
import argparse
import re
import requests
import urllib.parse
import subprocess
import asyncio
import os
from pathlib import Path
from src.config import ConfigManager
from src.ollama_client import OllamaClient
from src.chat import ChatManager
from src.selector import InteractiveSelector
from src.mcp import MCPClient
from src.session import SessionManager
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.theme import Theme
from rich.style import Style
from rich.spinner import Spinner
from rich.live import Live
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import FormattedText
from src.file_completer import CombinedCompleter, extract_at_context, remove_at_prefixed_paths
from src.utils.tree import generate_tree

# Apply nest_asyncio once globally to allow nested event loops
import nest_asyncio
nest_asyncio.apply()


# Cache for user working directory (set once at startup)
_USER_WORKING_DIR = None


def get_user_working_dir():
    """
    Get the user's original working directory.
    When running globally via ai-cli, uses AI_CLI_CWD env var.
    Otherwise falls back to current directory.
    Result is cached for performance.
    """
    global _USER_WORKING_DIR
    if _USER_WORKING_DIR is None:
        _USER_WORKING_DIR = os.environ.get('AI_CLI_CWD', os.getcwd())
    return _USER_WORKING_DIR


# Constants for repomap functionality
MAX_FILE_CONTENT_PREVIEW = 2000  # Maximum characters to include from each file

# Source code file extensions to include in repomap
SOURCE_CODE_EXTENSIONS = {
    # Python
    '.py', '.pyw', '.pyi',
    # JavaScript/TypeScript
    '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',
    # Web
    '.html', '.htm', '.css', '.scss', '.sass', '.less',
    # Java
    '.java', '.kt', '.kts', '.scala',
    # C/C++
    '.c', '.h', '.cpp', '.hpp', '.cc', '.hh', '.cxx', '.hxx',
    # C#
    '.cs', '.csx',
    # Go
    '.go',
    # Rust
    '.rs',
    # Ruby
    '.rb', '.rake', '.gemspec',
    # PHP
    '.php',
    # Swift
    '.swift',
    # R
    '.r', '.R',
    # Shell
    '.sh', '.bash', '.zsh', '.fish',
    # Config/Data
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
    # Markdown/Documentation
    '.md', '.rst', '.txt',
    # SQL
    '.sql',
    # Dockerfile
    'Dockerfile',
    # Makefile
    'Makefile',
}

# Directories to exclude from repomap scanning
REPOMAP_EXCLUDE_DIRS = {
    '.git', '__pycache__', 'node_modules', '.pytest_cache',
    '.mypy_cache', '.tox', 'venv', '.venv', 'env', '.env',
    'dist', 'build', '.eggs', '.cache',
    '.idea', '.vscode', 'target', 'bin', 'obj', 'coverage',
    'htmlcov', '.coverage', '.nyc_output', 'migrations',
}

# Directory patterns to exclude (suffix matching)
REPOMAP_EXCLUDE_SUFFIXES = {'.egg-info'}


def collect_source_files(working_dir: str, max_files: int = 500) -> list:
    """
    Collect all source code files from the working directory.
    
    Args:
        working_dir: Root directory to scan
        max_files: Maximum number of files to collect
        
    Returns:
        List of dicts with 'path', 'content', and 'size' keys
    """
    files = []
    working_path = Path(working_dir)
    
    for file_path in working_path.rglob('*'):
        # Check if we've reached the limit before processing more files
        if len(files) >= max_files:
            break
            
        # Skip directories in exclusion list (only check directory parts, not filename)
        if any(excluded in file_path.parts[:-1] for excluded in REPOMAP_EXCLUDE_DIRS):
            continue
        
        # Skip directories matching suffix patterns (e.g., *.egg-info)
        if any(part.endswith(suffix) for part in file_path.parts[:-1] for suffix in REPOMAP_EXCLUDE_SUFFIXES):
            continue
            
        # Skip non-files
        if not file_path.is_file():
            continue
            
        # Check if file matches source code extensions
        if file_path.suffix in SOURCE_CODE_EXTENSIONS or file_path.name in SOURCE_CODE_EXTENSIONS:
            try:
                relative_path = file_path.relative_to(working_path)
                file_size = file_path.stat().st_size
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    
                files.append({
                    'path': str(relative_path),
                    'content': content,
                    'size': file_size
                })
                    
            except (OSError, UnicodeDecodeError):
                # Skip files that can't be read
                continue
                
    return files


def generate_repomap_prompt(files: list, tree_output: str = None) -> str:
    """
    Generate an LLM prompt to create a comprehensive repository map.

    Args:
        files: List of file dicts with 'path', 'content', and 'size' keys
        tree_output: Optional directory tree string to include (default: None - no tree section added)

    Returns:
        Prompt string for the LLM
    """
    # Build file summaries
    file_summaries = []
    for f in files:
        file_summaries.append(f"### {f['path']} ({f['size']} bytes)")
        # Truncate content to avoid overwhelming the LLM
        content = f['content']
        if len(content) > MAX_FILE_CONTENT_PREVIEW:
            content_preview = content[:MAX_FILE_CONTENT_PREVIEW]
        else:
            content_preview = content
        file_summaries.append(f"```\n{content_preview}\n```\n")
    
    # Build tree section if provided
    tree_section = ""
    if tree_output:
        tree_section = f"""## Directory Tree

```
{tree_output}
```

"""
    
    # Join file summaries with newlines
    files_content = "\n".join(file_summaries)
    
    prompt = f"""You are a software architect analyzing a codebase. Create a comprehensive repository map (repomap) that will help developers understand the structure and purpose of this codebase.

{tree_section}## Files in the Repository

{files_content}

## CRITICAL Instructions - Read Carefully

**BEFORE writing the repository map:**
1. Carefully examine the Directory Tree above
2. List ALL top-level directories and applications you see (e.g., python_app/, r_app/, frontend/, etc.)
3. Identify if there are multiple programming languages or separate applications
4. Note which files and directories ACTUALLY exist (don't invent/hallucinate directories not shown in the tree)

**REQUIREMENTS:**
- Document EVERY top-level directory/application shown in the tree
- If multiple languages exist (Python, R, JavaScript, etc.), document EACH separately
- ONLY describe files and directories that appear in the actual tree above
- DO NOT invent or assume the existence of files/directories not shown (like config/, tests/, docker-compose.yml, etc.)
- Base your analysis on the actual file contents provided, not assumptions

## Repository Map Structure

Create a detailed repository map with these sections:

1. **Project Overview**:
   - List ALL applications/components found in the repository
   - Brief description of what each application does
   - Note if this is a multi-language or multi-application repository

2. **Applications/Components**:
   - Create a subsection for EACH top-level directory/application
   - For each application, describe its purpose and structure
   - If multiple language implementations exist, document each one

3. **Architecture**:
   - Describe the overall architecture
   - If multiple apps, describe how they might relate
   - Mention design patterns observed in the actual code

4. **Directory Structure**:
   - Explain the purpose of each major directory THAT EXISTS in the tree
   - Describe how files are organized in EACH application
   - Do NOT add directories that don't exist

5. **Key Components**:
   - List main modules, classes, and functions from ALL applications
   - Describe their responsibilities based on actual code
   - Cover components from all programming languages present

6. **Entry Points**:
   - Identify entry points for EACH application
   - Base this on actual file names (app.py, app.R, main.*, index.*, etc.)

7. **Dependencies**:
   - List dependencies observed in the actual code
   - Only mention what you can verify from the file contents

8. **Data Flow**:
   - Describe how data flows in EACH application
   - If multiple apps, describe potential interactions

9. **Configuration**:
   - Only describe configuration files that ACTUALLY exist in the tree
   - Do NOT mention config files that aren't shown

10. **Testing**:
    - Only describe test files/directories that ACTUALLY exist
    - If no tests are visible, say so

11. **Getting Started**:
    - Provide instructions for EACH application/language
    - Only reference files that actually exist

Please provide a clear, well-structured repository map in Markdown format that accurately reflects the COMPLETE codebase including ALL applications and languages."""

    return prompt


async def load_repomap_to_context(mcp_client, repomap_path: str, working_dir: str, session_id: str = None) -> dict:
    """
    Load a .repomap file into context using the MCP client.
    
    Args:
        mcp_client: MCPClient instance
        repomap_path: Path to the .repomap file
        working_dir: Working directory
        session_id: Optional session ID for persistence
        
    Returns:
        Result dict with status and message
    """
    args = {
        'file_path': repomap_path,
        'working_dir': working_dir
    }
    if session_id:
        args['session_id'] = session_id
        
    result = await mcp_client.call_tool('coder', 'add_file_context', args)
    
    try:
        return json.loads(result) if result else {'status': 'error', 'message': 'MCP tool returned empty result'}
    except json.JSONDecodeError as parse_error:
        # Provide more specific error information with type safety
        result_str = str(result) if result is not None else ''
        error_preview = (result_str[:100] + '...') if len(result_str) > 100 else result_str
        return {'status': 'error', 'message': f'Failed to parse response: {parse_error}. Response: {error_preview}'}


def run_async(coro):
    """
    Run an async coroutine safely, handling nested event loop scenarios.
    Uses nest_asyncio which has been applied globally to allow asyncio.run()
    even when an event loop is already running.
    """
    # With nest_asyncio applied globally, asyncio.run() works even in nested contexts
    return asyncio.run(coro)

# Create custom theme
custom_theme = Theme({
    "markdown.code": "cyan on #000000",
})

# Initialize rich console with custom theme
console = Console(theme=custom_theme)


class CustomMarkdown(Markdown):
    """Custom Markdown renderer with styled code blocks."""

    def __rich_console__(self, console, options):
        """Render markdown with custom code block styling."""
        # Get the rendered markdown elements
        for element in super().__rich_console__(console, options):
            # Check if it's a code block
            if isinstance(element, Panel) and hasattr(element, 'renderable'):
                # Wrap code blocks with blue border and black background
                if isinstance(element.renderable, Syntax):
                    yield Panel(
                        element.renderable,
                        border_style="blue",
                        style=Style(bgcolor="#000000"),
                        padding=(0, 1)
                    )
                else:
                    yield element
            elif isinstance(element, Syntax):
                # Direct Syntax objects (code blocks)
                yield Panel(
                    element,
                    border_style="blue",
                    style=Style(bgcolor="#000000"),
                    padding=(0, 1)
                )
            else:
                yield element

# Set up history file
HISTORY_FILE = Path.home() / ".ai_cli_history"

# API Configuration
POSTGRES_API_URL = "http://localhost:15000"
TRANSFORMER_API_URL = "http://localhost:16050"
SIMILARITY_THRESHOLD = 0.7  # Cosine similarity threshold for considering prompts similar
SATISFACTORY_RATING_THRESHOLD = 7  # Rating >= 7 is considered satisfactory

# Global verbose flag
VERBOSE = False


def debug_print(message, icon="🔍", style="dim"):
    """Print message only if verbose mode is enabled."""
    if VERBOSE:
        console.print(f"{icon} {message}", style=style)


def get_all_ratings():
    """Get all ratings from the postgres-api."""
    try:
        response = requests.get(f"{POSTGRES_API_URL}/ratings", timeout=10)
        if response.status_code == 200:
            return response.json().get('ratings', [])
        return []
    except Exception as e:
        print(f"[Warning] Could not fetch ratings: {e}")
        return []


def check_similarity(text1, text2):
    """Check similarity between two texts using transformer service."""
    try:
        params = {
            'text1': text1,
            'text2': text2,
            'metric': 'cosine'
        }
        response = requests.get(
            f"{TRANSFORMER_API_URL}/similarity",
            params=params,
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get('similarity', 0)
        return 0
    except Exception as e:
        print(f"[Warning] Could not check similarity: {e}")
        return 0


def extract_keywords(text, top_n=5):
    """Extract keywords from text using transformer service."""
    try:
        params = {
            'text': text,
            'top_n': top_n
        }
        response = requests.get(
            f"{TRANSFORMER_API_URL}/keywords",
            params=params,
            timeout=30
        )
        if response.status_code == 200:
            keywords_data = response.json().get('keywords', [])
            return [kw['keyword'] for kw in keywords_data]
        return []
    except Exception as e:
        print(f"[Warning] Could not extract keywords: {e}")
        return []


def create_rating(user_rating, prompt_text, response_text, tags, session_id=None):
    """Create a new rating in the postgres-api."""
    try:
        params = {
            'user_rating': user_rating,
            'prompt_text': prompt_text,
            'response_text': response_text,
            'tags': json.dumps({'keywords': tags})
        }
        if session_id:
            params['session_id'] = session_id
        response = requests.get(
            f"{POSTGRES_API_URL}/ratings/create",
            params=params,
            timeout=10
        )
        return response.status_code == 201
    except Exception as e:
        print(f"[Warning] Could not create rating: {e}")
        return False


def update_rating(rating_id, user_rating, response_text, tags):
    """Update an existing rating in the postgres-api."""
    try:
        payload = {
            'user_rating': user_rating,
            'response_text': response_text,
            'tags': {'keywords': tags}
        }
        response = requests.patch(
            f"{POSTGRES_API_URL}/ratings/{rating_id}/update",
            json=payload,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"[Warning] Could not update rating: {e}")
        return False


def find_similar_prompt(prompt_text, existing_ratings):
    """
    Find the most similar prompt from existing ratings.

    Args:
        prompt_text: The prompt to compare
        existing_ratings: List of existing rating records

    Returns:
        Tuple of (best_match, best_similarity) or (None, 0) if no match found
    """
    best_match = None
    best_similarity = 0

    for rating in existing_ratings:
        stored_prompt = rating.get('prompt_text', '')
        if stored_prompt:
            similarity = check_similarity(prompt_text, stored_prompt)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = rating

    return best_match, best_similarity


def process_rating(user_rating, prompt_text, response_text, session_id=None):
    """
    Process the user rating by:
    1. Getting all existing ratings
    2. Finding similar prompts
    3. Updating or creating as needed
    """
    # Get all existing ratings
    existing_ratings = get_all_ratings()

    # Extract keywords from current response
    keywords = extract_keywords(response_text)

    # Find the most similar prompt (reuse logic)
    best_match, best_similarity = find_similar_prompt(prompt_text, existing_ratings)

    # Check if we found a similar prompt
    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        stored_rating = best_match.get('user_rating', 0)
        # Update if current rating is higher or equal
        if user_rating >= stored_rating:
            if update_rating(best_match['id'], user_rating, response_text, keywords):
                debug_print(f"Rating updated - Similar prompt (similarity: {best_similarity:.2f}), {stored_rating} → {user_rating}", icon="✅", style="green")
                debug_print(f"Keywords: {', '.join(keywords)}", icon="🏷️", style="cyan")
            else:
                debug_print("Failed to update existing rating", icon="❌", style="red")
        else:
            debug_print(f"Rating skipped - Stored rating higher ({stored_rating} > {user_rating})", icon="⏭️", style="yellow")
    else:
        # No similar prompt found, create new entry
        if create_rating(user_rating, prompt_text, response_text, keywords, session_id):
            debug_print(f"New prompt stored with rating {user_rating}", icon="💾", style="green")
            debug_print(f"Keywords: {', '.join(keywords)}", icon="🏷️", style="cyan")
        else:
            debug_print("Failed to save new rating", icon="❌", style="red")


def get_prompt_guidance(prompt_text):
    """
    Get guidance for the LLM based on similar past prompts and their ratings.

    Returns a guidance string to inject into the conversation, or None if no guidance.
    """
    # Get all existing ratings
    existing_ratings = get_all_ratings()

    if not existing_ratings:
        return None

    # Find the most similar prompt (reuse shared logic)
    best_match, best_similarity = find_similar_prompt(prompt_text, existing_ratings)

    # Check if we found a similar prompt
    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        stored_rating = best_match.get('user_rating', 0)
        tags = best_match.get('tags', {})
        keywords = tags.get('keywords', []) if isinstance(tags, dict) else []

        if not keywords:
            return None

        keywords_str = ', '.join(keywords)

        if stored_rating >= SATISFACTORY_RATING_THRESHOLD:
            # Satisfactory response - use these keywords
            guidance = (
                f"[Context: A similar question was previously answered satisfactorily. "
                f"Consider incorporating these relevant concepts: {keywords_str}]"
            )
        else:
            # Unsatisfactory response - avoid these keywords
            guidance = (
                f"[Context: A similar question was previously answered unsatisfactorily. "
                f"Consider avoiding or improving upon these concepts: {keywords_str}]"
            )

        return guidance

    return None


async def handle_code_file_writing(mcp_client: MCPClient, response_text: str, target_file: str):
    """
    Detect code from LLM response and write it to a target file.

    Args:
        mcp_client: MCP client instance
        response_text: The LLM response text
        target_file: Path to the target file to write

    Returns:
        Write result or None
    """
    # Detect code in the response
    detected = mcp_client.detect_code(response_text)

    if not detected:
        debug_print("No code detected in response to write to file", icon="ℹ️")
        return None

    language = detected['language']
    code = detected['code']

    debug_print(f"Detected {language.upper()} code block for file: {target_file}", icon="🔍")

    # Determine if file exists to choose between write and edit
    file_exists = os.path.exists(target_file)

    # Determine tool based on language and file existence
    if language == "python":
        tool_name = "edit_python_code" if file_exists else "write_python_code"
        mcp_name = "coder"
    elif language == "r":
        tool_name = "edit_r_code" if file_exists else "write_r_code"
        mcp_name = "coder"
    else:
        debug_print(f"Unsupported language for file writing: {language}", icon="⚠️")
        return None

    # Inform user what we're about to do
    action = "Updating" if file_exists else "Creating"
    console.print(f"\n[cyan]{action} {target_file} with generated {language.upper()} code...[/cyan]")

    # Write the code to file
    result = await mcp_client.call_tool(
        mcp_name=mcp_name,
        tool_name=tool_name,
        arguments={
            "file_path": target_file,
            "code": code,
            "working_dir": get_user_working_dir()
        }
    )

    # Parse result
    try:
        result_data = json.loads(result)
        if result_data.get('status') == 'success':
            console.print(f"[green]✓ Successfully wrote code to {target_file}[/green]\n")
        else:
            console.print(f"[red]✗ Failed to write to {target_file}: {result_data.get('message')}[/red]\n")
    except Exception as e:
        if "Error:" in result:
            console.print(f"[red]✗ {result}[/red]\n")
        else:
            console.print(f"[red]✗ Failed to write to {target_file}: {e}[/red]\n")

    return result


async def handle_file_modifications(mcp_client: MCPClient, response_text: str, files_to_modify: list, files_to_create: list):
    """
    Parse LLM response for multiple file modifications and apply them.

    Args:
        mcp_client: MCP client instance
        response_text: The LLM response text
        files_to_modify: List of existing files mentioned by user
        files_to_create: List of files to create mentioned by user

    Returns:
        Dict with results for each file
    """
    results = {
        'modified': [],
        'created': [],
        'errors': []
    }

    # Pattern to match file paths followed by code blocks
    # Format 1: file: path/to/file.py\n```python\ncode\n``` (PRIMARY FORMAT)
    # Format 2: ```python\n# tool - file: path/to/file.py\ncode\n```
    # Format 3: filename.py\n```python\ncode\n```

    matches = []

    # Try Format 1 first (instructed format): "file:" prefix before code block
    # This pattern is more flexible and handles any file path
    pattern1 = r'(?:file|File):\s*([^\n]+\.(?:py|r|R))\s*\n+```(?:python|r)?\n(.*?)\n```'
    matches = re.findall(pattern1, response_text, re.DOTALL | re.MULTILINE)

    # Try Format 2: filename in comment inside code block
    if not matches:
        pattern2 = r'```(?:python|r)?\n#\s*(?:write_python_code|edit_python_code|write_r_code|edit_r_code)\s*-\s*file:\s*([^\n]+)\n(.*?)\n```'
        matches = re.findall(pattern2, response_text, re.DOTALL | re.MULTILINE)

    # Try Format 3: filename before code block (most lenient, any path structure)
    if not matches:
        pattern3 = r'(?:^|\n)([^\s:]+\.(?:py|r|R))\s*\n+```(?:python|r)?\n(.*?)\n```'
        matches = re.findall(pattern3, response_text, re.DOTALL | re.MULTILINE)

    if not matches:
        debug_print("No file+code patterns found in response", icon="ℹ️", style="yellow")
        console.print("\n[yellow]⚠️  No file modifications detected in LLM response.[/yellow]")
        console.print("[dim]The LLM may not have formatted the response correctly.[/dim]")
        console.print("[dim]Try rephrasing your request or check the LLM output above.[/dim]\n")
        return results

    debug_print(f"Found {len(matches)} file+code blocks to process", icon="📝", style="cyan")
    console.print(f"\n[cyan]📝 Processing {len(matches)} file modification(s)...[/cyan]\n")

    for file_path, code in matches:
        try:
            # Clean up file path
            file_path = file_path.strip()
            code = code.strip()

            # Remove tool comment line if present (from Format 2)
            code_lines = code.split('\n')
            if code_lines and code_lines[0].strip().startswith('#') and ('write_' in code_lines[0] or 'edit_' in code_lines[0]):
                code = '\n'.join(code_lines[1:]).strip()

            # Determine full path
            full_path = os.path.join(get_user_working_dir(), file_path)
            file_exists = os.path.exists(full_path)

            # Determine language and tool
            if file_path.endswith('.py'):
                language = "python"
                tool_name = "edit_python_code" if file_exists else "write_python_code"
            elif file_path.endswith(('.r', '.R')):
                language = "r"
                tool_name = "edit_r_code" if file_exists else "write_r_code"
            else:
                debug_print(f"Unsupported file type: {file_path}", icon="⚠️", style="yellow")
                results['errors'].append(f"{file_path}: Unsupported file type")
                continue

            # Inform user
            action = "Updating" if file_exists else "Creating"
            console.print(f"[cyan]{action} {file_path}...[/cyan]")

            # Call MCP tool
            result = await mcp_client.call_tool(
                mcp_name="coder",
                tool_name=tool_name,
                arguments={
                    "file_path": file_path,
                    "code": code,
                    "working_dir": get_user_working_dir()
                }
            )

            # Parse result
            try:
                result_data = json.loads(result)
                if result_data.get('status') == 'success':
                    console.print(f"✓ [green]{action} {file_path} successfully[/green]")
                    if file_exists:
                        results['modified'].append(file_path)
                    else:
                        results['created'].append(file_path)
                else:
                    error_msg = result_data.get('message', 'Unknown error')
                    console.print(f"✗ [red]Failed to {action.lower()} {file_path}: {error_msg}[/red]")
                    results['errors'].append(f"{file_path}: {error_msg}")
            except json.JSONDecodeError:
                # Result might be plain text error
                if "success" in result.lower():
                    console.print(f"✓ [green]{action} {file_path} successfully[/green]")
                    if file_exists:
                        results['modified'].append(file_path)
                    else:
                        results['created'].append(file_path)
                else:
                    console.print(f"✗ [red]Failed to {action.lower()} {file_path}[/red]")
                    results['errors'].append(f"{file_path}: {result}")

        except Exception as e:
            error_msg = str(e)
            console.print(f"✗ [red]Error processing {file_path}: {error_msg}[/red]")
            results['errors'].append(f"{file_path}: {error_msg}")
            debug_print(f"Error processing {file_path}: {e}", icon="❌", style="red")

    # Summary
    if results['created'] or results['modified']:
        console.print(f"\n[bold green]✓ File Operations Complete[/bold green]")
        if results['created']:
            console.print(f"  Created: {', '.join(results['created'])}")
        if results['modified']:
            console.print(f"  Modified: {', '.join(results['modified'])}")
        if results['errors']:
            console.print(f"  [yellow]Errors: {len(results['errors'])}[/yellow]")

        # Add affected files to results for verification
        results['affected_files'] = results['created'] + results['modified']

    return results


async def handle_code_execution(mcp_client: MCPClient, response_text: str):
    """
    Detect and execute code from LLM response.

    Args:
        mcp_client: MCP client instance
        response_text: The LLM response text

    Returns:
        Execution result or None
    """
    # Detect code in the response
    detected = mcp_client.detect_code(response_text)

    if not detected:
        debug_print("No code detected in response", icon="ℹ️")
        return None

    language = detected['language']
    code = detected['code']

    debug_print(f"Detected {language.upper()} code block", icon="🔍")

    # Determine tool based on language
    if language == "python":
        tool_name = "run_python_code"
        mcp_name = "coder"
    elif language == "r":
        tool_name = "run_r_code"
        mcp_name = "coder"
    else:
        debug_print(f"Unsupported language: {language}", icon="⚠️")
        return None

    # Ask user for confirmation using InteractiveSelector
    console.print()
    try:
        selector = InteractiveSelector(
            title=f"⚡ Execute {language.upper()} code?",
            choices=["Yes", "No"],
            current="No"
        )
        choice = selector.show()

        if choice != "Yes":
            console.print("\n[dim]Code execution cancelled[/dim]\n")
            return None
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]Code execution cancelled[/dim]\n")
        return None

    # Execute the code
    debug_print(f"Executing {language} code...", icon="⚙️")
    console.print("[yellow]Executing code...[/yellow]\n")

    result = await mcp_client.call_tool(
        mcp_name=mcp_name,
        tool_name=tool_name,
        arguments={"code": code}
    )

    return result


def display_execution_result(result: str):
    """
    Display code execution result in a nice format.

    Args:
        result: JSON string from MCP tool execution
    """
    try:
        result_data = json.loads(result)

        # Check if it's an error
        if result.startswith("Error:"):
            console.print(f"\n❌ [bold red]Execution Error[/bold red]")
            console.print(f"[red]{result}[/red]\n")
            return

        # Display execution complete message
        console.print("\n✓ [bold]Execution Complete[/bold]\n")

        # Show stdout if present
        if result_data.get("stdout"):
            console.print("📄 [bold]Output:[/bold]")
            console.print(result_data["stdout"].strip())
            console.print()

        # Show stderr if present
        if result_data.get("stderr"):
            console.print("⚠️  [bold yellow]Warnings/Errors:[/bold yellow]")
            console.print(f"[yellow]{result_data['stderr'].strip()}[/yellow]")
            console.print()

        # Show exit code
        exit_code = result_data.get("exit_code", -1)
        if exit_code == 0:
            console.print(f"[dim]Exit Code: {exit_code}[/dim]")
        else:
            console.print(f"[red]Exit Code: {exit_code}[/red]")

        console.print()

    except json.JSONDecodeError:
        # Not JSON, display as-is
        console.print(f"\n📄 [bold]Result:[/bold]")
        console.print(result)
        console.print()
    except Exception as e:
        debug_print(f"Error displaying result: {e}", icon="❌")
        console.print(f"[dim]Result: {result}[/dim]\n")


def list_system_mcps():
    """List all available system MCPs."""
    system_mcps_dir = Path(__file__).parent / "system_mcps"

    if not system_mcps_dir.exists():
        console.print("❌ [red]No system_mcps directory found[/red]\n")
        return

    # Find all directories in system_mcps that contain a server.py file
    mcps = []
    for item in system_mcps_dir.iterdir():
        if item.is_dir():
            server_file = item / "server.py"
            readme_file = item / "README.md"
            if server_file.exists():
                # Try to read description from README
                description = "No description available"
                if readme_file.exists():
                    try:
                        content = readme_file.read_text()
                        # Get first non-empty line after the title
                        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
                        if lines:
                            description = lines[0]  # No character limit
                    except Exception:
                        # Ignore errors reading README, fallback to default description
                        pass
                mcps.append((item.name, description))

    if not mcps:
        console.print("ℹ️  [yellow]No system MCPs found[/yellow]\n")
        return

    # Display as simple list
    console.print("\n📦 [bold]System MCPs:[/bold]")
    for name, description in sorted(mcps):
        console.print(f"  • [bold cyan]{name}[/bold cyan] - [dim]{description}[/dim]")
    console.print()


async def get_mcp_tools(mcp_name):
    """Get tools from a specific MCP server."""
    system_mcps_dir = Path(__file__).parent / "system_mcps"
    mcp_dir = system_mcps_dir / mcp_name
    server_file = mcp_dir / "server.py"

    if not server_file.exists():
        console.print(f"❌ [red]MCP '{mcp_name}' not found[/red]\n")
        return

    try:
        # Start the MCP server process
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

        # Cleanup
        process.terminate()
        await process.wait()

        # Display tools
        if "result" in tools_data and "tools" in tools_data["result"]:
            tools = tools_data["result"]["tools"]

            if not tools:
                console.print(f"ℹ️  [yellow]No tools found in MCP '{mcp_name}'[/yellow]\n")
                return

            # Display as simple list
            console.print(f"\n🔧 [bold]Tools in '{mcp_name}' MCP:[/bold]")
            for tool in tools:
                name = tool.get("name", "Unknown")
                description = tool.get("description", "No description")
                console.print(f"  • [bold cyan]{name}[/bold cyan]")
                console.print(f"    [dim]{description}[/dim]")
            console.print()
        else:
            console.print(f"❌ [red]Failed to get tools from MCP '{mcp_name}'[/red]\n")

    except asyncio.TimeoutError:
        console.print(f"❌ [red]Timeout while communicating with MCP '{mcp_name}'[/red]\n")
    except Exception as e:
        console.print(f"❌ [red]Error getting tools from MCP '{mcp_name}': {e}[/red]\n")


def load_banner():
    """Load banner from file."""
    banner_file = Path(__file__).parent / "assets" / "banner.txt"
    try:
        if banner_file.exists():
            return banner_file.read_text()
        else:
            # Fallback banner if file doesn't exist
            return """
           ╦  ╦╦ ╦╦ ╦╦╔╦╗╦═╗╔═╗  ╔═╗╦  ╦
           ╚╗╔╝║ ║╠═╣║ ║ ╠╦╝╠═╣  ║  ║  ║
            ╚╝ ╚═╝╩ ╩╩ ╩ ╩╚═╩ ╩  ╚═╝╩═╝╩

           Powered by Ollama
"""
    except Exception:
        return "VUHITRA CLI - Powered by Ollama"


def print_banner():
    """Print CLI banner."""
    # Load and display the ASCII art banner
    banner_text = load_banner()
    console.print(banner_text, style="bold cyan")

    # Print command help
    console.print("\n[bold cyan]Commands:[/bold cyan]")
    console.print("  [bold]'/exit'[/bold] or [bold]'/quit'[/bold] - Exit the CLI")
    console.print("  [bold]'/clear'[/bold] - Clear chat history")
    console.print("  [bold]'/models'[/bold] - List available models")
    console.print("  [bold]'/switch'[/bold] - Switch to a different model")
    console.print("  [bold]'/mcps'[/bold] - List system MCPs")
    console.print("  [bold]'/mcp-tools <name>'[/bold] - List tools in an MCP")
    console.print("  [bold]'/session start'[/bold] - Start a context session")
    console.print("  [bold]'/session end'[/bold] - End the current session")
    console.print("  [bold]'/session info'[/bold] - View current session info")
    console.print("  [bold]'/session restore <id>'[/bold] - Restore a saved session")
    console.print("  [bold]'/session list'[/bold] - List all saved sessions")
    console.print("  [bold]'/session clear'[/bold] - Clear all saved sessions")
    console.print("  [bold]'/repomap create'[/bold] - Create a repository map from working directory")
    console.print("  [bold]'/repomap load'[/bold] - Load existing .repomap file into context")
    console.print("  [bold]'/code <prompt>'[/bold] - Analyze and execute code tasks (requires session)")
    console.print()


def main(verbose=False):
    """Main function to run the AI CLI."""
    global VERBOSE
    VERBOSE = verbose

    try:
        # Load configuration
        config = ConfigManager()

        # Initialize Ollama client
        ollama_client = OllamaClient(
            host=config.get_ollama_url(),
            model=config.get_ollama_model(),
            timeout=config.get_ollama_timeout()
        )

        # Initialize chat manager
        chat_manager = ChatManager(
            system_prompt=config.get_system_prompt(),
            max_context_length=config.get_max_context_length()
        )

        # Initialize session manager
        session_manager = SessionManager()

        # Initialize MCP client
        system_mcps_dir = Path(__file__).parent / "system_mcps"
        mcp_client = MCPClient(
            system_mcps_dir=system_mcps_dir,
            postgres_url=POSTGRES_API_URL,
            verbose=verbose
        )

        # Set up debug callback for MCP client
        mcp_client.set_debug_callback(debug_print)

        # Initialize MCP tools in database (async operation)
        debug_print("Initializing MCP tools...", icon="🔧")
        try:
            run_async(mcp_client.initialize_tools_in_db())
        except Exception as e:
            debug_print(f"Failed to initialize MCP tools: {e}", icon="⚠️")

        # Get configuration
        temperature = config.get_temperature()
        stream = config.get_stream_enabled()

        # Clear the screen
        console.clear()

        print_banner()
        console.print(f"  📦 Model: [bold]{ollama_client.model}[/bold]")
        console.print(f"  🔗 Server: [dim]{config.get_ollama_url()}[/dim]")
        console.print()

        # Initialize command history
        history = FileHistory(str(HISTORY_FILE))

        # Initialize combined completer for / commands and @ file paths
        combined_completer = CombinedCompleter(working_dir=get_user_working_dir())

        # Main chat loop
        while True:
            try:
                # Get user input with history support and command/file completion
                user_input = prompt(
                    FormattedText([('ansigreen bold', '▶ ')]),
                    history=history,
                    completer=combined_completer
                ).strip()

                # Normalize command input - support both with and without / prefix
                user_input_normalized = user_input.lstrip('/').strip()

                # Handle special commands
                if user_input_normalized.lower() in ['exit', 'quit']:
                    # Cleanup MCP client
                    console.print("\n👋 [bold]Goodbye![/bold]")
                    try:
                        run_async(mcp_client.cleanup())
                    except (Exception, KeyboardInterrupt) as e:
                        # Suppress cleanup errors on exit
                        if verbose:
                            debug_print(f"Cleanup: {e}", icon="🧹")
                    # Redirect stderr to suppress prompt_toolkit task cleanup warnings
                    # Open /dev/null without context manager since we exit immediately
                    sys.stderr = open(os.devnull, 'w')
                    sys.exit(0)

                if user_input_normalized.lower() == 'clear':
                    chat_manager.clear_history()
                    console.print("\n🗑️ [yellow]Chat history cleared[/yellow]\n")
                    continue

                if user_input_normalized.lower() == 'models':
                    console.print("\n📋 [bold]Available models:[/bold]")
                    try:
                        models = ollama_client.list_models()
                        for model in models:
                            if model == ollama_client.model:
                                console.print(f"  • {model} [cyan](current)[/cyan]")
                            else:
                                console.print(f"  • {model}")
                    except Exception as e:
                        console.print(f"❌ [red]Error listing models: {e}[/red]")
                    console.print()
                    continue

                if user_input_normalized.lower() == 'switch':
                    console.print()
                    try:
                        models = ollama_client.list_models()
                        if not models:
                            console.print("❌ [red]No models available[/red]\n")
                            continue

                        # Show interactive selector
                        selector = InteractiveSelector(
                            title="🔄 Select Model",
                            choices=models,
                            current=ollama_client.model
                        )
                        selected = selector.show()

                        if selected and selected != ollama_client.model:
                            # Update the model
                            ollama_client.model = selected
                            console.print(f"\n✓ [green]Switched to model:[/green] [bold]{selected}[/bold]\n")
                        elif selected:
                            console.print(f"\n[dim]Already using {selected}[/dim]\n")
                        else:
                            console.print("\n[dim]Cancelled[/dim]\n")
                    except Exception as e:
                        console.print(f"\n❌ [red]Error switching model: {e}[/red]\n")
                    continue

                if user_input_normalized.lower() == 'mcps':
                    list_system_mcps()
                    continue

                if user_input_normalized.lower().startswith('mcp-tools '):
                    mcp_name = user_input_normalized[10:].strip()
                    if not mcp_name:
                        console.print("❌ [red]Usage: /mcp-tools <mcp_name>[/red]\n")
                    else:
                        try:
                            run_async(get_mcp_tools(mcp_name))
                        except Exception as e:
                            console.print(f"❌ [red]Error: {e}[/red]\n")
                    continue

                # Handle session commands
                if user_input_normalized.lower() == 'session start':
                    if session_manager.is_active():
                        console.print("\n⚠️  [yellow]Session already active. End current session first.[/yellow]\n")
                    else:
                        session_manager.start_session()
                        console.print()
                    continue

                if user_input_normalized.lower() == 'session end':
                    summary = session_manager.end_session()
                    if summary:
                        # Auto-save session when ending
                        try:
                            session_manager.save_to_redis()
                        except Exception as e:
                            debug_print(f"Failed to save session on end: {e}", icon="⚠️")
                        console.print()
                    continue

                if user_input_normalized.lower() == 'session info':
                    info = session_manager.get_session_info()
                    if info:
                        console.print("\n📊 [bold]Session Info:[/bold]")
                        console.print(f"  • Session ID: [cyan]{info['session_id'][:16]}...[/cyan]")
                        console.print(f"  • Duration: [cyan]{int(info['duration_seconds'])}s[/cyan]")
                        console.print(f"  • Interactions: [cyan]{info['num_interactions']}[/cyan]")
                        console.print()
                    else:
                        console.print("\n⚠️  [yellow]No active session[/yellow]\n")
                    continue

                if user_input_normalized.lower().startswith('session restore '):
                    session_id = user_input_normalized[16:].strip()
                    if not session_id:
                        console.print("\n❌ [red]Usage: /session restore <session_id>[/red]\n")
                    else:
                        if session_manager.is_active():
                            console.print("\n⚠️  [yellow]Please end current session before restoring.[/yellow]\n")
                        else:
                            success = session_manager.restore_from_redis(session_id)
                            if success:
                                console.print()
                    continue

                if user_input_normalized.lower() in ['session list', 'sessions list', 'sessions']:
                    console.print("\n📋 [bold]Saved Sessions:[/bold]")
                    sessions = session_manager.list_saved_sessions()
                    if sessions:
                        for sess in sessions:
                            console.print(f"  • [cyan]{sess['session_id'][:16]}...[/cyan]")
                            console.print(f"    Interactions: {sess.get('num_interactions', 0)}, "
                                        f"Started: {sess.get('start_time', 'N/A')}")
                    else:
                        console.print("  [dim]No saved sessions found[/dim]")
                    console.print()
                    continue

                if user_input_normalized.lower() in ['session clear', 'clear sessions']:
                    console.print()
                    try:
                        # Interactive confirmation
                        selector = InteractiveSelector(
                            title="⚠️  Clear ALL saved sessions?",
                            choices=["No", "Yes"],
                            current="No"
                        )
                        choice = selector.show()

                        if choice == "Yes":
                            count = session_manager.clear_all_sessions()
                            console.print(f"\n✅ [green]Cleared {count} session{'s' if count != 1 else ''}.[/green]\n")
                        else:
                            console.print("\n[dim]Cancelled[/dim]\n")
                    except Exception as e:
                        console.print(f"❌ [red]Error clearing sessions: {e}[/red]\n")
                    continue

                # Handle /repomap create command
                if user_input_normalized.lower() == 'repomap create':
                    console.print("\n📦 [bold cyan]Creating repository map...[/bold cyan]")
                    console.print(f"[dim]Scanning working directory: {get_user_working_dir()}[/dim]\n")

                    try:
                        # Collect all source files
                        console.print("[yellow]📂 Collecting source code files...[/yellow]")
                        source_files = collect_source_files(get_user_working_dir())
                        
                        if not source_files:
                            console.print("\n❌ [red]No source code files found in the working directory.[/red]\n")
                            continue
                            
                        console.print(f"[green]✓ Found {len(source_files)} source files[/green]")
                        
                        # Calculate total size
                        total_size = sum(f['size'] for f in source_files)
                        console.print(f"[dim]  Total size: {total_size:,} bytes[/dim]\n")
                        
                        # Generate directory tree
                        console.print("[yellow]🌳 Generating directory tree...[/yellow]")
                        tree_output = generate_tree(get_user_working_dir(), max_depth=5)
                        console.print(f"[green]✓ Directory tree generated[/green]\n")
                        
                        # Generate the LLM prompt with tree
                        console.print("[yellow]🤖 Generating repository map with LLM...[/yellow]")
                        repomap_prompt = generate_repomap_prompt(source_files, tree_output=tree_output)

                        # Check prompt size and warn if it's very large
                        prompt_size = len(repomap_prompt)
                        # Rough estimate: 4 chars per token for most LLMs
                        estimated_tokens = prompt_size // 4
                        if prompt_size > 500_000:  # ~500KB
                            console.print(f"[yellow]⚠️  Warning: Large prompt size ({prompt_size:,} chars, ~{estimated_tokens:,} tokens)[/yellow]")
                            console.print(f"[yellow]   This may exceed token limits for some LLMs or cause slower processing.[/yellow]\n")

                        # Use a separate chat manager for repomap generation to avoid polluting user's history
                        repomap_chat_manager = ChatManager(system_prompt=config.get_system_prompt())
                        repomap_chat_manager.add_user_message(repomap_prompt)
                        messages = repomap_chat_manager.get_messages()
                        
                        spinner = Spinner("dots", text="[dim]Analyzing codebase...[/dim]", style="cyan")
                        
                        with Live(spinner, console=console, refresh_per_second=10):
                            if stream:
                                full_response = ""
                                for chunk in ollama_client.chat(
                                    messages=messages,
                                    stream=True,
                                    temperature=temperature
                                ):
                                    full_response += chunk
                            else:
                                response = ollama_client.chat(
                                    messages=messages,
                                    stream=False,
                                    temperature=temperature
                                )
                                full_response = response.get('message', {}).get('content', '')
                        
                        # No need to save to main chat_manager - repomap generation is isolated
                        
                        # Prepend the tree to the repomap output
                        repomap_content = f"""# Repository Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""

                        # Write the repomap to file
                        repomap_path = os.path.join(get_user_working_dir(), '.repomap')
                        with open(repomap_path, 'w', encoding='utf-8') as f:
                            f.write(repomap_content)
                        
                        console.print(f"\n[bold green]✓ Repository map created successfully![/bold green]")
                        console.print(f"[cyan]📄 Saved to: {repomap_path}[/cyan]\n")
                        
                        # Show preview
                        preview_lines = repomap_content.split('\n')[:20]
                        console.print("[dim]Preview:[/dim]")
                        console.print(CustomMarkdown('\n'.join(preview_lines) + '\n...', code_theme="monokai"))
                        console.print()
                        
                    except Exception as e:
                        console.print(f"\n❌ [red]Error creating repository map: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    continue

                # Handle /repomap load command
                if user_input_normalized.lower() == 'repomap load':
                    repomap_path = os.path.join(get_user_working_dir(), '.repomap')
                    
                    if not os.path.exists(repomap_path):
                        console.print(f"\n❌ [red]No .repomap file found at: {repomap_path}[/red]")
                        console.print("[dim]Use '/repomap create' to generate a repository map first.[/dim]\n")
                        continue
                    
                    console.print(f"\n📂 [cyan]Loading repository map: {repomap_path}[/cyan]")
                    
                    try:
                        # Get session ID if active
                        session_id = session_manager.get_session_id() if session_manager.is_active() else None
                        
                        # Load the repomap into context
                        result = run_async(load_repomap_to_context(
                            mcp_client,
                            '.repomap',
                            os.getcwd(),
                            session_id
                        ))
                        
                        if result.get('status') == 'success':
                            content_size = result.get('content_size', 0)
                            console.print(f"[bold green]✓ Repository map loaded into context![/bold green]")
                            console.print(f"[dim]  Size: {content_size:,} bytes[/dim]")
                            if session_id:
                                console.print(f"[dim]  Session: {session_id[:16]}...[/dim]")
                            else:
                                console.print(f"[dim]  Session: temporary (start a session for persistence)[/dim]")
                            console.print()
                        else:
                            error_msg = result.get('message', 'Unknown error')
                            console.print(f"[yellow]⚠️  Warning: {error_msg}[/yellow]")
                            console.print("[dim]The repomap file may still be usable.[/dim]\n")
                            
                    except Exception as e:
                        console.print(f"\n❌ [red]Error loading repository map: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    continue

                # Handle /code command - simplified version
                if user_input_normalized.lower().startswith('code '):
                    prompt_text = user_input_normalized[5:].strip()  # Extract text after "code "

                    if not prompt_text:
                        console.print("\n❌ [red]Usage: /code <prompt_sentences>[/red]")
                        console.print("[dim]Example: /code write Python code to calculate fibonacci(20) and save to testing/fib.py then run testing/fib.py[/dim]\n")
                        continue

                    # Extract ALL @ references from the original prompt for context
                    at_references = re.findall(r'@([\w\-./]+)', prompt_text)
                    debug_print(f"Extracted @ references from prompt: {at_references}", icon="📎")

                    # Auto-start session if not active
                    if not session_manager.is_active():
                        console.print("\n[cyan]ℹ️  Starting a new session for /code command...[/cyan]")
                        session_manager.start_session()

                    session_id = session_manager.get_session_id()

                    # Load .repomap file into context if it exists and not already loaded in this session
                    repomap_path = os.path.join(get_user_working_dir(), '.repomap')
                    repomap_loaded_key = f'repomap_loaded_{repomap_path}'
                    if os.path.exists(repomap_path) and not session_manager.session_metadata.get(repomap_loaded_key):
                        console.print("[cyan]📦 Loading repository map into context...[/cyan]")
                        try:
                            repomap_result = run_async(load_repomap_to_context(
                                mcp_client,
                                '.repomap',
                                get_user_working_dir(),
                                session_id
                            ))
                            if repomap_result.get('status') == 'success':
                                console.print("[green]✓ Repository map loaded[/green]")
                                # Mark repomap as loaded for this session
                                session_manager.session_metadata[repomap_loaded_key] = True
                            else:
                                debug_print(f"Repomap load warning: {repomap_result.get('message')}", icon="⚠️")
                        except Exception as e:
                            debug_print(f"Failed to load repomap: {e}", icon="⚠️")

                    # Store @ references in session metadata for access by all tools
                    if at_references:
                        session_manager.session_metadata['at_references'] = at_references
                        session_manager.session_metadata['working_dir'] = get_user_working_dir()
                        debug_print(f"Stored @ references in session context: {at_references}", icon="📎")

                    console.print(f"\n🎯 [bold cyan]Processing code command...[/bold cyan]")
                    console.print(f"[dim]Prompt: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}[/dim]\n")

                    try:
                        # Call the simplified code-command endpoint to get steps
                        console.print("📝 [cyan]Analyzing prompt and creating execution steps...[/cyan]")
                        response = requests.post(
                            f"{POSTGRES_API_URL}/mcp-tools/code-command-simple",
                            json={
                                "text": prompt_text,
                                "session_id": session_id
                            },
                            headers={"Content-Type": "application/json"},
                            timeout=180
                        )

                        if response.status_code != 200:
                            console.print(f"\n❌ [red]Failed to process code command: HTTP {response.status_code}[/red]")
                            console.print(f"[dim]{response.text}[/dim]\n")
                            continue

                        data = response.json()

                        if data.get('status') != 'success':
                            console.print(f"\n❌ [red]Code command failed: {data.get('message')}[/red]\n")
                            continue

                        # Get the execution steps
                        steps = data.get('steps', [])

                        if not steps:
                            console.print("\n⚠️  [yellow]No execution steps generated[/yellow]\n")
                            continue

                        console.print(f"✓ [green]Generated {len(steps)} execution steps[/green]\n")

                        # Show the steps
                        console.print("📋 [bold]Execution Steps:[/bold]")
                        for i, step in enumerate(steps, 1):
                            console.print(f"  {i}. {step}")
                        console.print()

                        # Execute each step iteratively with tool matching
                        console.print("⚡ [cyan]Executing steps with tool matching...[/cyan]\n")

                        for i, step in enumerate(steps, 1):
                            console.print(f"[bold]Step {i}/{len(steps)}:[/bold] {step}")
                            console.print()

                            try:
                                # Step 1: Match this step with the best MCP tool
                                debug_print(f"Matching step {i} with tools...", icon="🔍")

                                match_response = requests.post(
                                    f"{POSTGRES_API_URL}/mcp-tools/retrieve",
                                    json={
                                        "prompts": [step],
                                        "threshold": 0.3,
                                        "context_references": at_references  # Pass @ references for parameter injection
                                    },
                                    headers={"Content-Type": "application/json"},
                                    timeout=30
                                )

                                if match_response.status_code == 200:
                                    match_data = match_response.json()
                                    results = match_data.get('results', [])

                                    if results and results[0].get('best_match'):
                                        best_match = results[0]['best_match']
                                        tool_name = best_match.get('tool_name')
                                        mcp_name = best_match.get('mcp_name', 'coder')
                                        similarity = best_match.get('similarity', 0)

                                        # Valid coding tools for /code command execution
                                        valid_coding_tools = [
                                            'run_python_code', 'run_r_code', 'detect_code',
                                            'write_python_code', 'write_r_code',
                                            'edit_python_code', 'edit_r_code',
                                            'add_file_context', 'add_directory_context',
                                            'verify_file_modifications'
                                        ]
                                        
                                        # Meta-tools should not be executed directly in /code steps
                                        meta_tools = ['retrieve_all_tools', 'roll_the_dice', 'spin_the_roulette']
                                        
                                        if tool_name in meta_tools:
                                            console.print(f"  ⚠️  [yellow]Skipping meta-tool '{tool_name}' (not suitable for direct execution)[/yellow]\n")
                                            continue
                                        
                                        if tool_name not in valid_coding_tools:
                                            console.print(f"  ⚠️  [yellow]Matched invalid tool '{tool_name}', skipping step[/yellow]\n")
                                            debug_print(f"Invalid tool matched: {tool_name} (similarity: {similarity})", icon="⚠️")
                                            continue

                                        console.print(f"  🔧 [cyan]Matched tool:[/cyan] {tool_name} [dim](similarity: {similarity:.2f})[/dim]")

                                        # Step 2: For code generation tools, use LLM to generate code first
                                        code_generation_tools = ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code', 'run_python_code', 'run_r_code']

                                        if tool_name in code_generation_tools:
                                            # Check if there's a file path with @ prefix
                                            file_match = re.search(r'@([\w\-./]+\.(?:py|r|R))', step)
                                            file_path = file_match.group(1) if file_match else None

                                            # For run_python_code/run_r_code, check if we should read existing file
                                            if tool_name in ['run_python_code', 'run_r_code'] and file_path:
                                                # Check if prompt is about running an existing file
                                                # More flexible: check if it mentions "file" or "script" with @
                                                step_lower = step.lower()
                                                is_run_file = (
                                                    ('file' in step_lower and '@' in step_lower) or
                                                    ('script' in step_lower and '@' in step_lower) or
                                                    'run @' in step_lower or
                                                    'execute @' in step_lower
                                                )

                                                if is_run_file:
                                                    console.print(f"  📂 [yellow]Reading file: {file_path}[/yellow]")

                                                    # Read the file
                                                    try:
                                                        with open(file_path, 'r') as f:
                                                            code = f.read()
                                                        console.print(f"  ✓ [green]File read ({len(code)} chars)[/green]\n")

                                                        # Build parameters
                                                        extracted_params = best_match.get('extracted_params', {})
                                                        extracted_params['code'] = code
                                                        # Remove file_path - run_python_code/run_r_code don't accept it
                                                        if 'file_path' in extracted_params:
                                                            extracted_params.pop('file_path')
                                                            debug_print(f"Removed file_path from params for {tool_name}", icon="🔧")
                                                    except FileNotFoundError:
                                                        console.print(f"  ❌ [red]File not found: {file_path}[/red]\n")
                                                        continue
                                                    except Exception as e:
                                                        console.print(f"  ❌ [red]Error reading file: {str(e)}[/red]\n")
                                                        continue
                                                else:
                                                    # Generate code with LLM
                                                    console.print(f"  🤖 [yellow]Generating code with LLM...[/yellow]")

                                                    chat_manager.add_user_message(step)
                                                    messages = chat_manager.get_messages()

                                                    spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                                                    with Live(spinner, console=console, refresh_per_second=10):
                                                        if stream:
                                                            full_response = ""
                                                            for chunk in ollama_client.chat(
                                                                messages=messages,
                                                                stream=True,
                                                                temperature=temperature
                                                            ):
                                                                full_response += chunk
                                                        else:
                                                            response = ollama_client.chat(
                                                                messages=messages,
                                                                stream=False,
                                                                temperature=temperature
                                                            )
                                                            full_response = response.get('message', {}).get('content', '')

                                                    chat_manager.add_assistant_message(full_response)

                                                    detected = mcp_client.detect_code(full_response)

                                                    if not detected:
                                                        console.print(f"  ⚠️  [yellow]No code detected in LLM response, skipping tool execution[/yellow]\n")
                                                        continue

                                                    code = detected['code']
                                                    console.print(f"  ✓ [green]Code generated ({len(code)} chars)[/green]\n")

                                                    extracted_params = best_match.get('extracted_params', {})
                                                    extracted_params['code'] = code
                                                    # Remove file_path for run_python_code/run_r_code
                                                    if tool_name in ['run_python_code', 'run_r_code'] and 'file_path' in extracted_params:
                                                        extracted_params.pop('file_path')
                                                        debug_print(f"Removed file_path from params for {tool_name}", icon="🔧")
                                            else:
                                                # For write/edit tools or run without file path, generate code with LLM
                                                console.print(f"  🤖 [yellow]Generating code with LLM...[/yellow]")

                                                # For edit tools, read the original file to provide context
                                                original_file_content = None
                                                if tool_name in ['edit_python_code', 'edit_r_code'] and file_path:
                                                    try:
                                                        if os.path.exists(file_path):
                                                            with open(file_path, 'r') as f:
                                                                original_file_content = f.read()
                                                            console.print(f"  📂 [dim]Read original file: {file_path} ({len(original_file_content)} chars)[/dim]")
                                                    except Exception as e:
                                                        console.print(f"  ⚠️  [yellow]Could not read original file: {e}[/yellow]")

                                                # Build the prompt with original file context for edits
                                                if original_file_content:
                                                    line_count = len(original_file_content.splitlines())
                                                    edit_prompt = f"""TASK: Edit the Python file below. Make ONLY the specific changes requested.

FILE TO EDIT: {file_path} ({line_count} lines)

=== ORIGINAL FILE START ===
{original_file_content}
=== ORIGINAL FILE END ===

REQUESTED CHANGES: {step}

CRITICAL RULES:
1. Output the COMPLETE file with ALL {line_count} lines (or close to it)
2. DO NOT remove, truncate, or summarize any existing functions, classes, or code
3. DO NOT add comments like "# Rest of your methods..." or "# ... existing code ..."
4. DO NOT change imports, class structure, or method signatures unless specifically requested
5. Make ONLY the minimal changes needed to fulfill the request
6. Preserve all docstrings, comments, and formatting

Wrap your output in a markdown code block like this:
```python
<the complete updated file content here>
```"""
                                                    chat_manager.add_user_message(edit_prompt)
                                                else:
                                                    chat_manager.add_user_message(step)
                                                
                                                messages = chat_manager.get_messages()

                                                spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                                                # For edit operations with original file, use coder model and allow more tokens
                                                edit_num_predict = 8192 if original_file_content else None
                                                edit_model = config.get_coder_model() if original_file_content else None

                                                with Live(spinner, console=console, refresh_per_second=10):
                                                    if stream:
                                                        full_response = ""
                                                        for chunk in ollama_client.chat(
                                                            messages=messages,
                                                            stream=True,
                                                            temperature=temperature,
                                                            num_predict=edit_num_predict,
                                                            model=edit_model
                                                        ):
                                                            full_response += chunk
                                                    else:
                                                        response = ollama_client.chat(
                                                            messages=messages,
                                                            stream=False,
                                                            temperature=temperature,
                                                            num_predict=edit_num_predict,
                                                            model=edit_model
                                                        )
                                                        full_response = response.get('message', {}).get('content', '')

                                                chat_manager.add_assistant_message(full_response)

                                                # Debug: show response length (temporary)
                                                if original_file_content:
                                                    console.print(f"  [dim]LLM response: {len(full_response)} chars[/dim]")
                                                    if len(full_response) < 500:
                                                        console.print(f"  [dim]Response preview: {full_response[:300]}...[/dim]")

                                                detected = mcp_client.detect_code(full_response)

                                                if not detected:
                                                    console.print(f"  ⚠️  [yellow]No code detected in LLM response, skipping tool execution[/yellow]\n")
                                                    continue

                                                code = detected['code']
                                                console.print(f"  ✓ [green]Code generated ({len(code)} chars)[/green]\n")

                                                extracted_params = best_match.get('extracted_params', {})
                                                extracted_params['code'] = code

                                            # Add file_path if extracted from @ prefix (only for write/edit tools)
                                            if file_path and tool_name in ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code']:
                                                extracted_params['file_path'] = file_path
                                            elif 'file_path' not in extracted_params and tool_name in ['write_python_code', 'edit_python_code', 'write_r_code', 'edit_r_code']:
                                                console.print(f"  ⚠️  [yellow]No file path specified, skipping {tool_name}[/yellow]\n")
                                                continue
                                        else:
                                            # Non-code-generation tools: use extracted params
                                            extracted_params = best_match.get('extracted_params', {})
                                            
                                            # Strip @ prefix from file_path if present (LLM may include it)
                                            if 'file_path' in extracted_params and extracted_params['file_path']:
                                                fp = extracted_params['file_path']
                                                if fp.startswith('@'):
                                                    extracted_params['file_path'] = fp[1:]
                                            if 'directory_path' in extracted_params and extracted_params['directory_path']:
                                                dp = extracted_params['directory_path']
                                                if dp.startswith('@'):
                                                    extracted_params['directory_path'] = dp[1:]

                                        # Add working_dir if not present
                                        if 'working_dir' not in extracted_params:
                                            extracted_params['working_dir'] = get_user_working_dir()

                                        # Add session_id for tools that need it
                                        if 'session_id' not in extracted_params and session_manager.is_active():
                                            extracted_params['session_id'] = session_id

                                        debug_print(f"Calling MCP tool: {tool_name} with params: {list(extracted_params.keys())}", icon="⚙️")
                                        console.print(f"  ⚡ [yellow]Executing {tool_name}...[/yellow]\n")

                                        # Step 3: Call the MCP tool
                                        result = run_async(mcp_client.call_tool(
                                            mcp_name=mcp_name,
                                            tool_name=tool_name,
                                            arguments=extracted_params
                                        ))

                                        # Step 4: Display result
                                        try:
                                            result_data = json.loads(result)

                                            if result_data.get('status') == 'success':
                                                console.print(f"  ✓ [green]Success[/green]")

                                                # Show relevant output
                                                if 'stdout' in result_data and result_data['stdout']:
                                                    console.print(f"\n  [dim]Output:[/dim]")
                                                    console.print(f"  {result_data['stdout']}")

                                                if 'stderr' in result_data and result_data['stderr']:
                                                    console.print(f"\n  [yellow]Warnings:[/yellow]")
                                                    console.print(f"  {result_data['stderr']}")

                                                if 'file_path' in result_data:
                                                    console.print(f"  📄 [cyan]File:[/cyan] {result_data['file_path']}")

                                                if 'message' in result_data:
                                                    console.print(f"  💬 {result_data['message']}")
                                            else:
                                                error_msg = result_data.get('message') or result_data.get('error') or 'Unknown error'
                                                console.print(f"  ✗ [red]Failed:[/red] {error_msg}")
                                                # Log full result for debugging
                                                debug_print(f"Full error result: {json.dumps(result_data, indent=2)}", icon="🔍")

                                        except json.JSONDecodeError as e:
                                            # Plain text result (might be an error message)
                                            console.print(f"  📄 [dim]{result}[/dim]")
                                            debug_print(f"JSON decode error: {e}. Raw result: {result}", icon="⚠️")

                                        console.print()

                                        # Add to session
                                        if session_manager.is_active():
                                            session_manager.add_interaction(
                                                prompt=step,
                                                response=result,
                                                metadata={'model': ollama_client.model, 'step': i, 'tool': tool_name}
                                            )
                                            # Auto-save session
                                            try:
                                                session_manager.save_to_redis()
                                            except Exception as e:
                                                debug_print(f"Failed to auto-save session: {e}", icon="⚠️")

                                    else:
                                        # No tool matched - fall back to LLM
                                        console.print(f"  ⚠️  [yellow]No matching tool found, using LLM...[/yellow]\n")

                                        chat_manager.add_user_message(step)
                                        messages = chat_manager.get_messages()

                                        spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                                        with Live(spinner, console=console, refresh_per_second=10):
                                            if stream:
                                                full_response = ""
                                                for chunk in ollama_client.chat(
                                                    messages=messages,
                                                    stream=True,
                                                    temperature=temperature
                                                ):
                                                    full_response += chunk
                                            else:
                                                response = ollama_client.chat(
                                                    messages=messages,
                                                    stream=False,
                                                    temperature=temperature
                                                )
                                                full_response = response.get('message', {}).get('content', '')

                                        console.print("[bold cyan]▶[/bold cyan]")
                                        console.print(CustomMarkdown(full_response, code_theme="monokai"))
                                        console.print()

                                        chat_manager.add_assistant_message(full_response)

                                        if session_manager.is_active():
                                            session_manager.add_interaction(
                                                prompt=step,
                                                response=full_response,
                                                metadata={'model': ollama_client.model, 'step': i}
                                            )
                                            # Auto-save session
                                            try:
                                                session_manager.save_to_redis()
                                            except Exception as e:
                                                debug_print(f"Failed to auto-save session: {e}", icon="⚠️")

                                else:
                                    console.print(f"  ✗ [red]Failed to match tools (HTTP {match_response.status_code})[/red]\n")

                            except Exception as e:
                                console.print(f"[red]✗ Error in step {i}: {e}[/red]\n")
                                if verbose:
                                    import traceback
                                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
                                # Continue with next step even if this one fails

                        console.print(f"\n✓ [bold green]Completed all {len(steps)} steps[/bold green]\n")

                    except requests.exceptions.Timeout:
                        console.print("\n❌ [red]Request timeout - the command took too long to process[/red]\n")
                    except requests.exceptions.RequestException as e:
                        console.print(f"\n❌ [red]Network error: {e}[/red]\n")
                    except Exception as e:
                        console.print(f"\n❌ [red]Error executing /code command: {e}[/red]\n")
                        if verbose:
                            import traceback
                            console.print(f"[dim]{traceback.format_exc()}[/dim]")

                    continue

                # Skip empty input
                if not user_input:
                    continue

                # Process @ prefixed file/directory paths
                at_context = extract_at_context(user_input, get_user_working_dir())
                context_added = False

                # Collect file and directory contents to inject into conversation
                injected_context_parts = []

                # Add file contexts to Redis (with session if active)
                session_id = session_manager.get_session_id() if session_manager.is_active() else None

                for file_path in at_context['files']:
                    try:
                        # Add file context using MCP tool
                        args = {
                            'file_path': file_path,
                            'working_dir': get_user_working_dir()
                        }
                        if session_id:
                            args['session_id'] = session_id

                        result = run_async(mcp_client.call_tool('coder', 'add_file_context', args))

                        # Parse result to extract file content
                        if not result:
                            debug_print(f"No result returned from add_file_context for {file_path}", icon="⚠️", style="yellow")
                        elif not result.strip():
                            debug_print(f"Empty result returned from add_file_context for {file_path}", icon="⚠️", style="yellow")
                        else:
                            try:
                                result_data = json.loads(result)
                                if result_data.get('status') == 'success' and result_data.get('content'):
                                    # Add file content to injected context
                                    file_content = result_data['content']
                                    injected_context_parts.append(f"File: {file_path}\n```\n{file_content}\n```")
                                    debug_print(f"Added file context: {file_path}", icon="📄", style="cyan")
                                    context_added = True
                            except json.JSONDecodeError as e:
                                debug_print(f"Failed to parse file context result for {file_path}: {e}", icon="⚠️", style="yellow")
                                debug_print(f"Result was: {result[:200]}...", icon="🔍", style="dim")
                    except Exception as e:
                        debug_print(f"Failed to add file context for {file_path}: {e}", icon="⚠️", style="yellow")

                # Add directory contexts to Redis
                for dir_path in at_context['directories']:
                    try:
                        # Add directory context using MCP tool
                        args = {
                            'dir_path': dir_path,
                            'working_dir': get_user_working_dir()
                        }
                        if session_id:
                            args['session_id'] = session_id

                        result = run_async(mcp_client.call_tool('coder', 'add_directory_context', args))

                        # Parse result to show tree and extract contents
                        try:
                            result_data = json.loads(result)
                            if result_data.get('tree_added'):
                                tree_stats = result_data.get('tree_stats', {})
                                console.print(f"\n[cyan]📁 Directory Structure Added: {dir_path}[/cyan]")
                                console.print(f"[dim]  Files: {tree_stats.get('files', 0)} | Directories: {tree_stats.get('directories', 0)}[/dim]\n")

                                # Add tree structure to injected context
                                tree_output = result_data.get('tree_output', '')
                                if tree_output:
                                    injected_context_parts.append(f"Directory Structure: {dir_path}\n```\n{tree_output}\n```")

                                # Add all file contents from directory
                                files_content = result_data.get('files_content', [])
                                for file_info in files_content:
                                    file_path_rel = file_info.get('path', '')
                                    file_content = file_info.get('content', '')
                                    if file_content:
                                        injected_context_parts.append(f"File: {file_path_rel}\n```\n{file_content}\n```")
                        except Exception as parse_err:
                            debug_print(f"Failed to parse directory result: {parse_err}", icon="⚠️", style="yellow")

                        debug_print(f"Added directory context: {dir_path}", icon="📁", style="cyan")
                        context_added = True
                    except Exception as e:
                        debug_print(f"Failed to add directory context for {dir_path}: {e}", icon="⚠️", style="yellow")

                # Handle non-existing files (these will be targets for write operations)
                target_file = None
                if at_context['non_existing']:
                    # Take the first non-existing file as the target
                    target_file = at_context['non_existing'][0]
                    debug_print(f"Target file for output: {target_file}", icon="🎯", style="magenta")

                    # Warn if multiple new files were specified
                    if len(at_context['non_existing']) > 1:
                        other_files = ', '.join(at_context['non_existing'][1:])
                        console.print(f"[yellow]⚠️  Multiple new files specified. Only '{target_file}' will be created. Ignored: {other_files}[/yellow]")

                # Remove @ prefixed paths from user input for cleaner prompt
                clean_user_input = remove_at_prefixed_paths(user_input)

                # If we removed everything, use original input
                if not clean_user_input:
                    clean_user_input = user_input

                # Inform user about context addition
                if context_added:
                    console.print(f"[dim]✓ Added {len(at_context['files'])} file(s) and {len(at_context['directories'])} directory(ies) to context[/dim]")

                # Get guidance based on similar past prompts
                guidance = get_prompt_guidance(clean_user_input)

                # Get session context if active
                session_context = None
                if session_manager.is_active():
                    session_context = session_manager.get_session_context(max_interactions=5)
                    if session_context:
                        debug_print(f"Session active: {len(session_manager.get_session_history())} interactions in context", icon="📝", style="cyan")

                # Add user message to context (use clean input without @ paths)
                chat_manager.add_user_message(clean_user_input)

                # Get messages and inject guidance if available
                messages = chat_manager.get_messages()

                # Collect all system messages to inject before the user's message
                system_messages_to_inject = []

                # Inject file/directory context from @ prefix
                if injected_context_parts:
                    context_content = "\n\n".join(injected_context_parts)
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': f"The user has provided the following files/directories as context:\n\n{context_content}"
                    })

                # Detect file modification actions (refactor, update, create, etc.)
                action_keywords = ['refactor', 'create', 'update', 'modify', 'edit', 'change', 'rewrite', 'add']
                user_input_lower = clean_user_input.lower()
                has_action = any(keyword in user_input_lower for keyword in action_keywords)

                # If action keywords present with @ prefixed files, instruct to use MCP tools
                if has_action and (at_context['files'] or at_context['non_existing']):
                    tool_instructions = []

                    # Collect all files that need to be modified or created
                    all_files_to_modify = list(at_context['files'])
                    all_files_to_create = list(at_context['non_existing'])

                    # Look for additional files to create mentioned in the prompt (like "create base.py")
                    create_pattern = r'create\s+((?:[\w/]+/)?[\w.]+\.(?:py|r|R))'
                    create_matches = re.findall(create_pattern, user_input_lower)
                    if create_matches:
                        for matched_file in create_matches:
                            # Add to create list if not already present
                            if matched_file not in all_files_to_create and matched_file not in all_files_to_modify:
                                all_files_to_create.append(matched_file)

                    # Build comprehensive instruction with explicit format requirements
                    instruction_parts = []

                    if all_files_to_modify:
                        instruction_parts.append(
                            f"The user wants to MODIFY these existing files: {', '.join(all_files_to_modify)}"
                        )

                    if all_files_to_create:
                        instruction_parts.append(
                            f"The user wants to CREATE these new files: {', '.join(all_files_to_create)}"
                        )

                    if instruction_parts:
                        # Add explicit format instructions
                        format_instruction = """
IMPORTANT: For EACH file you need to create or modify, you MUST use this EXACT format:

file: <full_file_path>
```python
<complete file code here>
```

Example:
file: testing/python_app/models/base.py
```python
class BaseModel:
    pass
```

file: testing/python_app/models/user.py
```python
from .base import BaseModel

class User(BaseModel):
    pass
```

Do NOT just explain the changes - provide the COMPLETE, RUNNABLE code for each file in the format above.
Each file should have its own "file: <path>" line followed by a code block.

VERIFICATION: After modifications, one of the files will be executed to verify the changes work correctly.
Ensure all imports are correct, syntax is valid, and the code runs without errors.
"""
                        full_instruction = "\n".join(instruction_parts) + format_instruction
                        tool_instructions.append(full_instruction)

                    if tool_instructions:
                        system_messages_to_inject.append({
                            'role': 'system',
                            'content': "\n\n".join(tool_instructions)
                        })

                # If target file is specified, instruct LLM to generate code for that file
                if target_file:
                    file_ext = os.path.splitext(target_file)[1]
                    lang = "Python" if file_ext == ".py" else "R" if file_ext in [".R", ".r"] else "appropriate"
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': (
                            f"The user wants to write code to the file: {target_file}. "
                            f"Generate {lang} code in a code block that will be automatically written to this file. "
                            "Provide complete, working code that can be directly written to the file."
                        )
                    })

                # If user asks to run/execute code, instruct LLM not to predict output
                run_keywords = ['run', 'execute', 'exec']
                if any(keyword in clean_user_input.lower() for keyword in run_keywords):
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': (
                            "The user wants to execute code. Provide ONLY the code in a code block. "
                            "Do NOT predict, guess, or show what the output will be. "
                            "The code will be automatically executed and the real output will be displayed to the user."
                        )
                    })

                # Inject session context if available
                if session_context:
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': session_context
                    })

                # Add guidance if available
                if guidance:
                    system_messages_to_inject.append({
                        'role': 'system',
                        'content': guidance
                    })
                    debug_print(guidance, icon="🧠", style="magenta")

                # Inject all system messages before the last user message
                if system_messages_to_inject:
                    messages = messages[:-1] + system_messages_to_inject + [messages[-1]]

                # Get AI response
                console.print()  # Add spacing before AI response

                # Get response (stream or not) and collect full response
                if stream:
                    # Show spinner while collecting response
                    full_response = ""
                    spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                    with Live(spinner, console=console, refresh_per_second=10):
                        for chunk in ollama_client.chat(
                            messages=messages,
                            stream=True,
                            temperature=temperature
                        ):
                            full_response += chunk

                    # Render complete response as markdown with custom styling
                    console.print("[bold cyan]▶[/bold cyan]")
                    console.print(CustomMarkdown(full_response, code_theme="monokai"))
                else:
                    # Show spinner while waiting for response
                    spinner = Spinner("dots", text="[dim]Thinking...[/dim]", style="cyan")

                    with Live(spinner, console=console, refresh_per_second=10):
                        response = ollama_client.chat(
                            messages=messages,
                            stream=False,
                            temperature=temperature
                        )
                        full_response = response.get('message', {}).get('content', '')

                    # Render response as markdown with custom styling
                    console.print("[bold cyan]▶[/bold cyan]")
                    console.print(CustomMarkdown(full_response, code_theme="monokai"))

                # Add assistant response to context
                chat_manager.add_assistant_message(full_response)

                # Add interaction to session history if session is active
                if session_manager.is_active():
                    session_manager.add_interaction(
                        prompt=user_input,
                        response=full_response,
                        metadata={'model': ollama_client.model, 'temperature': temperature}
                    )

                    # Auto-save session to Redis after each interaction
                    try:
                        session_manager.save_to_redis()
                    except Exception as e:
                        debug_print(f"Failed to auto-save session: {e}", icon="⚠️")

                console.print()  # Extra line for readability

                # Check for code and offer to execute or write to file
                try:
                    if has_action and (at_context['files'] or at_context['non_existing']):
                        # Handle file modifications (refactor, update, create, etc.)
                        mod_result = run_async(handle_file_modifications(
                            mcp_client,
                            full_response,
                            at_context['files'],
                            at_context['non_existing']
                        ))

                        # Offer to verify modifications by running one of the files
                        if mod_result and mod_result.get('affected_files'):
                            affected_files = mod_result['affected_files']
                            runnable_files = [f for f in affected_files if f.endswith(('.py', '.r', '.R'))]

                            debug_print(f"Verification: {len(runnable_files)} runnable files found", icon="🔍", style="cyan")

                            if runnable_files:
                                console.print()
                                try:
                                    if len(runnable_files) == 1:
                                        # Only one file, ask if they want to verify
                                        selector = InteractiveSelector(
                                            title=f"🔍 Verify changes by running {runnable_files[0]}?",
                                            choices=["Yes", "No"],
                                            current="Yes"
                                        )
                                        choice = selector.show()
                                        target_verify_file = runnable_files[0] if choice == "Yes" else None
                                    else:
                                        # Multiple files, let user choose
                                        choices = runnable_files + ["Skip verification"]
                                        selector = InteractiveSelector(
                                            title="🔍 Select a file to run for verification:",
                                            choices=choices,
                                            current=choices[0]
                                        )
                                        choice = selector.show()
                                        target_verify_file = choice if choice != "Skip verification" else None

                                    if target_verify_file:
                                        console.print(f"\n[yellow]Running {target_verify_file} for verification...[/yellow]\n")
                                        verify_result = run_async(mcp_client.call_tool(
                                            'coder',
                                            'verify_file_modifications',
                                            {
                                                'file_path': target_verify_file,
                                                'working_dir': get_user_working_dir()
                                            }
                                        ))

                                        # Display verification result
                                        display_execution_result(verify_result)
                                    else:
                                        console.print("\n[dim]Skipping verification run[/dim]\n")

                                except (EOFError, KeyboardInterrupt):
                                    console.print("\n[dim]Skipping verification run[/dim]\n")
                    elif target_file:
                        # Write code to target file
                        run_async(handle_code_file_writing(mcp_client, full_response, target_file))
                    else:
                        # Execute code (with user confirmation)
                        exec_result = run_async(handle_code_execution(mcp_client, full_response))
                        if exec_result:
                            display_execution_result(exec_result)
                except Exception as e:
                    debug_print(f"Error during code handling: {e}", icon="❌")

                # Ask for rating
                try:
                    rating_input = prompt("⭐ Rate (0-10, Enter to skip): ").strip()

                    if rating_input:  # User provided input
                        try:
                            rating = int(rating_input)
                            if 0 <= rating <= 10:
                                # Pass session_id if session is active
                                session_id = session_manager.get_session_id()
                                process_rating(rating, user_input, full_response, session_id)
                            else:
                                console.print("❌ [red]Invalid rating. Enter 0-10.[/red]")
                        except ValueError:
                            console.print("❌ [red]Invalid input. Enter a number.[/red]")
                    # If empty input (Enter pressed), do nothing - silently skip
                except EOFError:
                    pass  # Handle piped input gracefully

                console.print()  # Extra line for readability

            except KeyboardInterrupt:
                # Cleanup MCP client
                console.print("\n\n👋 [bold]Goodbye![/bold]")
                try:
                    run_async(mcp_client.cleanup())
                except (Exception, KeyboardInterrupt) as e:
                    # Suppress cleanup errors on exit
                    if verbose:
                        debug_print(f"Cleanup: {e}", icon="🧹")
                # Redirect stderr to suppress prompt_toolkit task cleanup warnings
                # Open /dev/null without context manager since we exit immediately
                sys.stderr = open(os.devnull, 'w')
                sys.exit(0)
            except Exception as e:
                console.print(f"\n❌ [red]Error: {e}[/red]")
                console.print("[dim]Please try again.[/dim]\n")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure config.yaml exists in the project root.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing CLI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI CLI - Powered by Ollama")
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose mode to show debug information'
    )
    args = parser.parse_args()
    main(verbose=args.verbose)
