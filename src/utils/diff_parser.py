"""
Diff Parser Module - Parse and apply unified diffs to files.

This module provides functions to parse unified diffs (git-style diffs) and apply them
to files with atomic operations and validation. It's designed to prevent data loss by
validating diffs before applying them and failing cleanly if the diff doesn't match.
"""

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional


class InvalidDiffFormatError(Exception):
    """Raised when diff format is invalid or missing required headers."""
    pass


class MissingHunkHeaderError(Exception):
    """Raised when a hunk is missing the @@ header."""
    pass


class MalformedDiffLineError(Exception):
    """Raised when a diff line has an invalid prefix."""
    pass


@dataclass
class DiffHunk:
    """Represents a single hunk in a unified diff."""
    old_start: int      # Starting line number in old file (1-indexed)
    old_count: int      # Number of lines in old file
    new_start: int      # Starting line number in new file (1-indexed)
    new_count: int      # Number of lines in new file
    diff_lines: List[str]  # Lines with ' ', '+', '-' prefixes


def parse_unified_diff(diff_text: str) -> List[DiffHunk]:
    """
    Parse a unified diff into a list of DiffHunk objects.
    
    Args:
        diff_text: The unified diff text (must include --- and +++ headers)
        
    Returns:
        List of DiffHunk objects
        
    Raises:
        InvalidDiffFormatError: If diff is missing required headers
        MissingHunkHeaderError: If a hunk is missing @@ markers
        MalformedDiffLineError: If a diff line has an invalid prefix
    """
    lines = diff_text.strip().split('\n')
    
    # Validate we have diff headers
    has_old_header = False
    has_new_header = False
    
    for line in lines:
        if line.startswith('---'):
            has_old_header = True
        elif line.startswith('+++'):
            has_new_header = True
            
    if not (has_old_header and has_new_header):
        raise InvalidDiffFormatError(
            "Diff must include '---' and '+++' headers. "
            "Expected unified diff format."
        )
    
    hunks = []
    current_hunk = None
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Skip header lines
        if line.startswith('---') or line.startswith('+++'):
            i += 1
            continue
            
        # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
        if line.startswith('@@'):
            # Save previous hunk if exists
            if current_hunk is not None:
                hunks.append(current_hunk)
            
            # Parse the hunk header
            match = re.match(r'^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@', line)
            if not match:
                raise MissingHunkHeaderError(
                    f"Invalid hunk header format: {line}. "
                    f"Expected: @@ -old_start,old_count +new_start,new_count @@"
                )
            
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1
            
            current_hunk = DiffHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                diff_lines=[]
            )
            i += 1
            continue
        
        # Process diff lines (must have a hunk active)
        if current_hunk is None:
            # Skip non-diff lines before first hunk
            i += 1
            continue
            
        # Validate line prefix
        if line and line[0] not in [' ', '+', '-']:
            # Allow empty lines as context
            if line.strip() == '':
                current_hunk.diff_lines.append(' ')
            else:
                raise MalformedDiffLineError(
                    f"Invalid diff line prefix: '{line[0]}'. "
                    f"Expected ' ', '+', or '-'"
                )
        else:
            current_hunk.diff_lines.append(line)
        
        i += 1
    
    # Don't forget the last hunk
    if current_hunk is not None:
        hunks.append(current_hunk)
    
    if not hunks:
        raise InvalidDiffFormatError("No valid hunks found in diff")
    
    return hunks


def validate_diff_hunks(original_content: str, diff_hunks: List[DiffHunk]) -> Tuple[bool, str]:
    """
    Validate that diff hunks can be applied to the original content.
    
    This function checks:
    - Context lines match exactly
    - Line numbers are within file bounds
    - Hunks don't overlap
    - Hunks are in order
    
    Args:
        original_content: The original file content as a string
        diff_hunks: List of DiffHunk objects to validate
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
        error_message is empty string if valid
    """
    original_lines = original_content.splitlines()
    
    # Check hunks are in order and don't overlap
    prev_end = 0
    for hunk in diff_hunks:
        if hunk.old_start < 1:
            return False, f"Invalid hunk: old_start must be >= 1, got {hunk.old_start}"
        
        if hunk.old_start <= prev_end:
            return False, f"Hunks overlap or out of order at line {hunk.old_start}"
        
        prev_end = hunk.old_start + hunk.old_count - 1
        
        # Check bounds
        if hunk.old_start + hunk.old_count - 1 > len(original_lines):
            return False, (
                f"Hunk extends beyond file: "
                f"line {hunk.old_start + hunk.old_count - 1} > {len(original_lines)}"
            )
    
    # Validate context lines match
    for hunk in diff_hunks:
        old_line_idx = hunk.old_start - 1  # Convert to 0-indexed
        
        for diff_line in hunk.diff_lines:
            if not diff_line:  # Empty line
                continue
                
            prefix = diff_line[0]
            content = diff_line[1:] if len(diff_line) > 1 else ''
            
            if prefix == ' ':  # Context line - must match
                if old_line_idx >= len(original_lines):
                    return False, (
                        f"Context line at position {old_line_idx + 1} "
                        f"exceeds file length {len(original_lines)}"
                    )
                
                if original_lines[old_line_idx] != content:
                    return False, (
                        f"Context mismatch at line {old_line_idx + 1}:\n"
                        f"Expected: {repr(original_lines[old_line_idx])}\n"
                        f"Got: {repr(content)}"
                    )
                old_line_idx += 1
                
            elif prefix == '-':  # Deletion - must match
                if old_line_idx >= len(original_lines):
                    return False, (
                        f"Deletion line at position {old_line_idx + 1} "
                        f"exceeds file length {len(original_lines)}"
                    )
                
                if original_lines[old_line_idx] != content:
                    return False, (
                        f"Deletion mismatch at line {old_line_idx + 1}:\n"
                        f"Expected to delete: {repr(original_lines[old_line_idx])}\n"
                        f"Diff wants to delete: {repr(content)}"
                    )
                old_line_idx += 1
                
            elif prefix == '+':  # Addition - just skip, doesn't affect validation
                pass
            else:
                return False, f"Invalid diff line prefix: {repr(prefix)}"
    
    return True, ""


def apply_diff_to_file(file_path: str, diff_hunks: List[DiffHunk], working_dir: str) -> Tuple[bool, str]:
    """
    Apply diff hunks to a file with atomic operations and validation.
    
    This function:
    1. Reads the original file
    2. Validates the diff hunks
    3. Applies hunks to create new content
    4. Writes to a temp file first
    5. Renames temp file to original (atomic)
    6. Preserves original on any failure
    
    Args:
        file_path: Path to the file (relative or absolute)
        diff_hunks: List of DiffHunk objects to apply
        working_dir: Working directory for relative paths
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            file_path = os.path.join(working_dir, file_path)
        
        path = Path(file_path).resolve()
        
        # Validate file is within working directory
        try:
            path.relative_to(Path(working_dir).resolve())
        except ValueError:
            return False, f"File is outside working directory: {file_path}"
        
        # Read original file
        if not path.exists():
            return False, f"File does not exist: {file_path}"
        
        with open(path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Validate hunks
        is_valid, error_msg = validate_diff_hunks(original_content, diff_hunks)
        if not is_valid:
            return False, f"Diff validation failed: {error_msg}"
        
        # Apply hunks to generate new content
        original_lines = original_content.splitlines()
        new_lines = []
        current_old_idx = 0  # 0-indexed position in original file
        
        for hunk in diff_hunks:
            # Add lines before this hunk (unchanged)
            hunk_start_idx = hunk.old_start - 1  # Convert to 0-indexed
            while current_old_idx < hunk_start_idx:
                new_lines.append(original_lines[current_old_idx])
                current_old_idx += 1
            
            # Apply hunk
            for diff_line in hunk.diff_lines:
                if not diff_line:  # Empty line
                    continue
                    
                prefix = diff_line[0]
                content = diff_line[1:] if len(diff_line) > 1 else ''
                
                if prefix == ' ':  # Context line - keep it
                    new_lines.append(content)
                    current_old_idx += 1
                elif prefix == '-':  # Deletion - skip this line
                    current_old_idx += 1
                elif prefix == '+':  # Addition - add new line
                    new_lines.append(content)
        
        # Add remaining lines after last hunk
        while current_old_idx < len(original_lines):
            new_lines.append(original_lines[current_old_idx])
            current_old_idx += 1
        
        # Create new content
        new_content = '\n'.join(new_lines)
        
        # Preserve original line ending if file ended with newline
        if original_content.endswith('\n'):
            new_content += '\n'
        
        # Atomic write: write to temp file first, then rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f'.{path.name}.',
            suffix='.tmp'
        )
        
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Atomic rename
            os.replace(temp_path, path)
            
            return True, f"Successfully applied {len(diff_hunks)} hunk(s) to {file_path}"
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
        
    except Exception as e:
        return False, f"Error applying diff: {str(e)}"


def detect_diff_format(code_text: str) -> bool:
    """
    Detect if the input text is a unified diff or full file content.
    
    A text is considered a diff if it contains:
    - Both --- and +++ headers
    - At least one @@ hunk header
    
    Args:
        code_text: The text to analyze
        
    Returns:
        True if text appears to be a unified diff, False otherwise
    """
    lines = code_text.strip().split('\n')
    
    has_old_header = False
    has_new_header = False
    has_hunk_header = False
    
    for line in lines:
        if line.startswith('---'):
            has_old_header = True
        elif line.startswith('+++'):
            has_new_header = True
        elif line.startswith('@@'):
            has_hunk_header = True
    
    # All three markers must be present for a valid diff
    return has_old_header and has_new_header and has_hunk_header
