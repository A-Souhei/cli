"""Repository mapping functionality for the AI CLI."""

import json
import os
from pathlib import Path


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
