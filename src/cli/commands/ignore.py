"""Ignore command handlers for AI CLI."""

import os
from src.file_completer import parse_at_prefixed_paths


def handle_ignore_create(console, working_dir):
    """
    Handle /ignore create command - creates .llmignore file.
    
    Args:
        console: Rich console for output
        working_dir: Working directory path
        
    Returns:
        True to indicate command was handled
    """
    llmignore_path = os.path.join(working_dir, ".llmignore")
    
    # Check if file already exists
    if os.path.exists(llmignore_path):
        console.print(f"\n[yellow]⚠️  .llmignore already exists at: {llmignore_path}[/yellow]")
        console.print("[dim]Use '/ignore add @file' to add files to it[/dim]\n")
        return True
    
    # Create default .llmignore content
    default_content = """# .llmignore - Prevent sensitive files from being added to LLM context
#
# This file works like .gitignore - any files matching these patterns
# will NEVER be added to the AI context, even if explicitly requested
# with @ prefix (e.g., @.env will be blocked).
#
# Pattern syntax (same as .gitignore):
# - Lines starting with # are comments
# - Blank lines are ignored
# - * matches any characters (except /)
# - ? matches a single character
# - / at the end indicates a directory
# - / at the start anchors the pattern to the root
# - ! negates the pattern (un-ignore)

# Environment and secrets
.env
.env.*
*.env

# API keys and certificates
*_key
*_secret
*.pem
*.key

# Configuration with secrets
secrets.yaml
credentials.json

# Dependency directories (usually too large)
node_modules/
venv/
.venv/
__pycache__/

# Build artifacts
dist/
build/
*.egg-info/

# Add your custom patterns below:

"""
    
    try:
        with open(llmignore_path, 'w', encoding='utf-8') as f:
            f.write(default_content)
        
        console.print(f"\n[green]✓ Created .llmignore at: {llmignore_path}[/green]")
        console.print("[dim]Edit this file to customize which files are ignored[/dim]")
        console.print("[dim]Use '/ignore add @file' to add files to it[/dim]\n")
        
    except Exception as e:
        console.print(f"\n[red]❌ Error creating .llmignore: {e}[/red]\n")
    
    return True


def handle_ignore_add(console, working_dir, user_input):
    """
    Handle /ignore add command - adds files to .llmignore.
    
    Args:
        console: Rich console for output
        working_dir: Working directory path
        user_input: Full user input string
        
    Returns:
        True to indicate command was handled
    """
    llmignore_path = os.path.join(working_dir, ".llmignore")
    
    # Check if .llmignore exists
    if not os.path.exists(llmignore_path):
        console.print("\n[yellow]⚠️  .llmignore does not exist[/yellow]")
        console.print("[dim]Use '/ignore create' to create it first[/dim]\n")
        return True
    
    # Extract @ prefixed paths from user input
    # Parse the command more robustly by splitting on whitespace
    parts = user_input.split()
    # Filter out the command parts ('/ignore' and 'add'), keep the rest
    file_parts = [p for p in parts if p not in ['/ignore', 'ignore', 'add']]
    paths_part = ' '.join(file_parts)
    
    if not paths_part:
        console.print("\n[yellow]⚠️  No files specified[/yellow]")
        console.print("[dim]Usage: /ignore add @file1 @file2 ...[/dim]\n")
        return True
    
    # Parse @ prefixed paths
    paths = parse_at_prefixed_paths(paths_part)
    
    if not paths:
        console.print("\n[yellow]⚠️  No @ prefixed files found[/yellow]")
        console.print("[dim]Usage: /ignore add @file1 @file2 ...[/dim]\n")
        return True
    
    # Read existing .llmignore content
    try:
        with open(llmignore_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        
        existing_patterns = set()
        for line in existing_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                existing_patterns.add(line)
        
        # Add new patterns
        new_patterns = []
        skipped_patterns = []
        
        for path in paths:
            # Normalize path (remove trailing slashes for files)
            path = path.rstrip('/')
            
            if path in existing_patterns:
                skipped_patterns.append(path)
            else:
                new_patterns.append(path)
                existing_patterns.add(path)
        
        if not new_patterns:
            console.print(f"\n[yellow]⚠️  All specified files are already in .llmignore[/yellow]")
            for pattern in skipped_patterns:
                console.print(f"[dim]  • {pattern}[/dim]")
            console.print()
            return True
        
        # Append new patterns to .llmignore
        with open(llmignore_path, 'a', encoding='utf-8') as f:
            f.write('\n# Added by /ignore add command\n')
            for pattern in new_patterns:
                f.write(f'{pattern}\n')
        
        console.print(f"\n[green]✓ Added {len(new_patterns)} pattern(s) to .llmignore:[/green]")
        for pattern in new_patterns:
            console.print(f"[cyan]  • {pattern}[/cyan]")
        
        if skipped_patterns:
            console.print(f"\n[dim]Skipped {len(skipped_patterns)} already existing pattern(s):[/dim]")
            for pattern in skipped_patterns:
                console.print(f"[dim]  • {pattern}[/dim]")
        
        console.print()
        
    except Exception as e:
        console.print(f"\n[red]❌ Error updating .llmignore: {e}[/red]\n")
    
    return True


def handle_ignore_command(console, working_dir, user_input):
    """
    Handle /ignore commands.
    
    Args:
        console: Rich console for output
        working_dir: Working directory path
        user_input: Full user input string
        
    Returns:
        True if command was handled, False otherwise
    """
    user_input_lower = user_input.lower().strip()
    
    if user_input_lower == '/ignore create' or user_input_lower.startswith('ignore create'):
        return handle_ignore_create(console, working_dir)
    
    if user_input_lower.startswith('/ignore add') or user_input_lower.startswith('ignore add'):
        return handle_ignore_add(console, working_dir, user_input)
    
    # Unknown /ignore command
    if user_input_lower.startswith('/ignore') or user_input_lower.startswith('ignore'):
        console.print("\n[yellow]⚠️  Unknown /ignore command[/yellow]")
        console.print("[dim]Available commands:[/dim]")
        console.print("[dim]  /ignore create - Create .llmignore file[/dim]")
        console.print("[dim]  /ignore add @file1 @file2 - Add files to .llmignore[/dim]\n")
        return True
    
    return False
