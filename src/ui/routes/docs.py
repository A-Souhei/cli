"""
Documentation API routes for the UI.

Provides endpoints for:
- Listing available documentation
- Getting documentation content
"""

import os
from pathlib import Path
from flask import Blueprint, jsonify, request

from src.sentry_config import capture_exception

docs_bp = Blueprint('docs', __name__)


def get_docs_dir() -> Path:
    """Get the docs directory."""
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "docs"


@docs_bp.route('/', methods=['GET'])
def list_docs():
    """List all available documentation files."""
    try:
        docs_dir = get_docs_dir()
        
        if not docs_dir.exists():
            return jsonify({
                'status': 'error',
                'message': 'Documentation directory not found'
            }), 404
        
        docs = []
        for item in sorted(docs_dir.iterdir()):
            if item.is_file() and item.suffix == '.md':
                doc_info = {
                    'name': item.stem,
                    'filename': item.name,
                    'path': str(item),
                    'size': item.stat().st_size
                }
                
                # Read first few lines for description
                try:
                    with open(item, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[:5]
                        # Find first non-empty, non-header line
                        for line in lines:
                            stripped = line.strip()
                            if stripped and not stripped.startswith('#'):
                                doc_info['preview'] = stripped[:150]
                                break
                except Exception:
                    pass
                
                docs.append(doc_info)
        
        return jsonify({
            'status': 'success',
            'count': len(docs),
            'docs': docs
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@docs_bp.route('/<doc_name>', methods=['GET'])
def get_doc(doc_name: str):
    """Get the content of a specific documentation file."""
    try:
        docs_dir = get_docs_dir()
        
        # Add .md extension if not present
        if not doc_name.endswith('.md'):
            doc_name = f"{doc_name}.md"
        
        doc_path = docs_dir / doc_name
        
        if not doc_path.exists():
            return jsonify({
                'status': 'error',
                'message': f'Documentation "{doc_name}" not found'
            }), 404
        
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'status': 'success',
            'doc': {
                'name': doc_path.stem,
                'filename': doc_path.name,
                'content': content,
                'size': len(content)
            }
        })
        
    except Exception as e:
        capture_exception(e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@docs_bp.route('/cli-usage', methods=['GET'])
def get_cli_usage():
    """Get CLI usage documentation."""
    usage_content = """
# AI CLI Usage Guide

## Starting the CLI

```bash
# Run in normal mode
ai-cli

# Run with verbose output
ai-cli --verbose
ai-cli -v

# Run with web UI
ai-cli --show-ui
```

## Available Commands

### Navigation & Control
- `/exit` or `/quit` - Exit the CLI
- `/clear` - Clear chat history
- `/models` - List available models
- `/switch` - Switch to a different model

### Session Management
- `/session start` - Start a new session
- `/session end` - End current session
- `/session info` - Show session information
- `/session list` or `/sessions` - List saved sessions
- `/session restore <id>` - Restore a saved session
- `/session delete <id>` - Delete a saved session
- `/session clear` - Clear all saved sessions

### Repository Mapping
- `/repomap create` - Create a repository map
- `/repomap load` - Load repository map into context
- `/repomap update` - Update repository map with new files

### Data Mapping
- `/datamap create` - Create a data map
- `/datamap load` - Load data map into context
- `/datamap update` - Update data map

### Code Commands
- `/code <prompt>` - Execute code generation/editing commands

### MCP Tools
- `/mcps` - List available MCP servers
- `/mcp-tools <name>` - List tools for a specific MCP

## File Context

Use `@` prefix to reference files in your prompts:

```
@path/to/file.py - Reference a specific file
@path/to/directory/ - Reference a directory (note trailing slash)
```

## Examples

```bash
# Ask a question
What is the capital of France?

# Reference a file in your question
Explain what @src/main.py does

# Generate code
/code write a Python function that calculates fibonacci(20) and save to @testing/fib.py

# Edit a file
/code add error handling to @src/utils.py
```
"""
    return jsonify({
        'status': 'success',
        'doc': {
            'name': 'CLI Usage',
            'content': usage_content
        }
    })
