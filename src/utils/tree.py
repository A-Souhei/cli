"""Directory tree generation utility."""

import os
from pathlib import Path
from typing import List, Set


def generate_tree(
    directory: str,
    prefix: str = "",
    is_last: bool = True,
    max_depth: int = 10,
    current_depth: int = 0,
    exclude_patterns: Set[str] = None
) -> str:
    """
    Generate an ASCII tree representation of a directory structure.

    Args:
        directory: Path to the directory
        prefix: Prefix for the current line (used for recursion)
        is_last: Whether this is the last item in the current level
        max_depth: Maximum depth to traverse
        current_depth: Current depth (used for recursion)
        exclude_patterns: Set of patterns to exclude (e.g., {'.git', '__pycache__', 'node_modules'})

    Returns:
        String representation of the directory tree
    """
    if exclude_patterns is None:
        exclude_patterns = {
            '.git',
            '__pycache__',
            'node_modules',
            '.pytest_cache',
            '.mypy_cache',
            '.tox',
            'venv',
            '.venv',
            'env',
            '.env',
            '*.pyc',
            '.DS_Store',
            'dist',
            'build',
            '*.egg-info'
        }

    # Check depth limit
    if current_depth > max_depth:
        return ""

    # Get the directory name
    dir_path = Path(directory)
    if not dir_path.exists():
        return f"{prefix}[Error: Directory not found]\n"

    if not dir_path.is_dir():
        return f"{prefix}[Error: Not a directory]\n"

    # Start with the directory name (only on first call)
    result = []
    if current_depth == 0:
        result.append(f"{dir_path.name}/\n")

    # Get all entries and sort them (directories first, then files)
    try:
        entries = list(dir_path.iterdir())
    except PermissionError:
        return f"{prefix}[Permission Denied]\n"

    # Filter out excluded patterns
    entries = [
        e for e in entries
        if not any(
            pattern.rstrip('*') in e.name or e.name.endswith(pattern.lstrip('*'))
            for pattern in exclude_patterns
        )
    ]

    # Sort: directories first, then files, both alphabetically
    entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

    # Process each entry
    for i, entry in enumerate(entries):
        is_last_entry = (i == len(entries) - 1)

        # Determine the tree characters
        if is_last_entry:
            current_prefix = "└── "
            next_prefix = "    "
        else:
            current_prefix = "├── "
            next_prefix = "│   "

        # Add the current entry
        if entry.is_dir():
            result.append(f"{prefix}{current_prefix}{entry.name}/\n")

            # Recursively process subdirectory
            sub_tree = generate_tree(
                str(entry),
                prefix=prefix + next_prefix,
                is_last=is_last_entry,
                max_depth=max_depth,
                current_depth=current_depth + 1,
                exclude_patterns=exclude_patterns
            )
            result.append(sub_tree)
        else:
            # Get file size for display
            try:
                size = entry.stat().st_size
                size_str = format_size(size)
                result.append(f"{prefix}{current_prefix}{entry.name} ({size_str})\n")
            except:
                result.append(f"{prefix}{current_prefix}{entry.name}\n")

    return "".join(result)


def format_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 KB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def generate_tree_summary(directory: str, max_depth: int = 10) -> dict:
    """
    Generate tree and summary statistics for a directory.

    Args:
        directory: Path to the directory
        max_depth: Maximum depth to traverse

    Returns:
        Dict with 'tree' (string) and 'stats' (dict with file/dir counts)
    """
    tree_output = generate_tree(directory, max_depth=max_depth)

    # Count files and directories
    stats = count_items(directory, max_depth=max_depth)

    return {
        'tree': tree_output,
        'stats': stats
    }


def count_items(directory: str, max_depth: int = 10, current_depth: int = 0, exclude_patterns: Set[str] = None) -> dict:
    """
    Count files and directories recursively.

    Args:
        directory: Path to the directory
        max_depth: Maximum depth to traverse
        current_depth: Current depth (used for recursion)
        exclude_patterns: Set of patterns to exclude

    Returns:
        Dict with 'files', 'directories', and 'total_size' counts
    """
    if exclude_patterns is None:
        exclude_patterns = {
            '.git',
            '__pycache__',
            'node_modules',
            '.pytest_cache',
            '.mypy_cache',
            '.tox',
            'venv',
            '.venv',
            'env',
            '.env',
            '*.pyc',
            '.DS_Store',
            'dist',
            'build',
            '*.egg-info'
        }

    if current_depth > max_depth:
        return {'files': 0, 'directories': 0, 'total_size': 0}

    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        return {'files': 0, 'directories': 0, 'total_size': 0}

    files = 0
    directories = 0
    total_size = 0

    try:
        for entry in dir_path.iterdir():
            # Skip excluded patterns
            if any(
                pattern.rstrip('*') in entry.name or entry.name.endswith(pattern.lstrip('*'))
                for pattern in exclude_patterns
            ):
                continue

            if entry.is_dir():
                directories += 1
                # Recursively count subdirectory
                sub_stats = count_items(
                    str(entry),
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                    exclude_patterns=exclude_patterns
                )
                files += sub_stats['files']
                directories += sub_stats['directories']
                total_size += sub_stats['total_size']
            else:
                files += 1
                try:
                    total_size += entry.stat().st_size
                except:
                    pass
    except PermissionError:
        pass

    return {
        'files': files,
        'directories': directories,
        'total_size': total_size
    }


def generate_compact_tree(directory: str, max_depth: int = 5) -> str:
    """
    Generate a compact tree with limited depth for quick overview.

    Args:
        directory: Path to the directory
        max_depth: Maximum depth (default: 5 for compact view)

    Returns:
        Compact tree string
    """
    return generate_tree(directory, max_depth=max_depth)
