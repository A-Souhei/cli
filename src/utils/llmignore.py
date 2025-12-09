"""
LLM Ignore - File filtering based on .llmignore patterns.

This module provides functionality to parse .llmignore files and filter out files
that should never be added to LLM context. It follows .gitignore syntax and ensures
security by preventing sensitive files from being exposed to the AI.

Key Features:
- Standard .gitignore syntax support (globs, negations, comments)
- Hierarchical .llmignore files (directory-specific)
- Security-focused: Files are NEVER added to context if matched
- Works with @ prefix file/directory context

Note: ** glob patterns are simplified to * for compatibility. For full recursive
directory matching, use patterns like dir/* or dir/*.ext instead of dir/**/*.ext
"""

import os
import fnmatch
from typing import List, Tuple
from src.sentry_config import capture_exception


class LLMIgnorePattern:
    """Represents a single pattern from .llmignore file."""
    
    def __init__(self, pattern: str, is_negation: bool = False, base_dir: str = "."):
        """
        Initialize an ignore pattern.
        
        Args:
            pattern: The pattern string (e.g., "*.env", "secrets/")
            is_negation: Whether this is a negation pattern (starts with !)
            base_dir: Base directory where the .llmignore file was found
        """
        self.original = pattern
        self.pattern = pattern.lstrip('!')
        self.is_negation = is_negation
        self.base_dir = base_dir
        
        # Determine if pattern is directory-specific (ends with /)
        self.is_directory_only = self.pattern.endswith('/')
        if self.is_directory_only:
            self.pattern = self.pattern.rstrip('/')
        
        # Determine if pattern is anchored (starts with /)
        self.is_anchored = self.pattern.startswith('/')
        if self.is_anchored:
            self.pattern = self.pattern.lstrip('/')
    
    def matches(self, file_path: str, is_dir: bool = False) -> bool:
        """
        Check if this pattern matches the given file path.
        
        Args:
            file_path: Relative file path to check
            is_dir: Whether the path is a directory
            
        Returns:
            True if the pattern matches the path
        """
        # Directory-only patterns only match directories
        if self.is_directory_only and not is_dir:
            return False
        
        # Normalize path separators
        file_path = file_path.replace(os.sep, '/')
        pattern = self.pattern.replace(os.sep, '/')
        
        # Handle ** glob pattern (matches any number of directories)
        # For simplicity, we replace ** with * which works for most cases
        if '**' in pattern:
            pattern = pattern.replace('**', '*')
        
        if self.is_anchored:
            # Anchored patterns match from the base directory
            if fnmatch.fnmatch(file_path, pattern):
                return True
            # For directories, also match contents
            if fnmatch.fnmatch(file_path, pattern + '/*'):
                return True
            return False
        else:
            # Non-anchored patterns can match at any level
            # Try matching the full path
            if fnmatch.fnmatch(file_path, pattern):
                return True
            
            # Try matching just the filename
            filename = os.path.basename(file_path)
            if fnmatch.fnmatch(filename, pattern):
                return True
            
            # Try matching any parent path component
            parts = file_path.split('/')
            for i in range(len(parts)):
                subpath = '/'.join(parts[i:])
                if fnmatch.fnmatch(subpath, pattern):
                    return True
                # Also check with trailing wildcard for directory matching
                if fnmatch.fnmatch(subpath, pattern + '/*'):
                    return True
        
        return False


class LLMIgnore:
    """Parser and matcher for .llmignore patterns."""
    
    IGNORE_FILENAME = ".llmignore"
    
    def __init__(self, working_dir: str):
        """
        Initialize LLMIgnore with a working directory.
        
        Args:
            working_dir: The working directory to search for .llmignore files
        """
        self.working_dir = os.path.abspath(working_dir)
        self.patterns: List[LLMIgnorePattern] = []
        self._load_patterns()
    
    def _load_patterns(self) -> None:
        """Load patterns from .llmignore file in working directory."""
        ignore_file = os.path.join(self.working_dir, self.IGNORE_FILENAME)
        
        if os.path.isfile(ignore_file):
            try:
                with open(ignore_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        
                        # Check for negation pattern
                        is_negation = line.startswith('!')
                        
                        # Create pattern
                        pattern = LLMIgnorePattern(
                            line,
                            is_negation=is_negation,
                            base_dir=self.working_dir
                        )
                        self.patterns.append(pattern)
            except Exception as e:
                # Log error but don't fail - just continue without ignore patterns
                capture_exception(e)
    
    def is_ignored(self, file_path: str, is_dir: bool = False) -> bool:
        """
        Check if a file or directory should be ignored.
        
        Args:
            file_path: Path to check (relative to working_dir or absolute)
            is_dir: Whether the path is a directory
            
        Returns:
            True if the file should be ignored (not added to context)
        """
        # Convert to relative path if absolute
        if os.path.isabs(file_path):
            try:
                file_path = os.path.relpath(file_path, self.working_dir)
            except ValueError:
                # Path is on different drive or outside working_dir
                # Don't ignore files outside working directory
                return False
        
        # No patterns means nothing is ignored
        if not self.patterns:
            return False
        
        # Apply patterns in order
        # Later patterns override earlier ones
        ignored = False
        
        for pattern in self.patterns:
            if pattern.matches(file_path, is_dir):
                # Negation patterns un-ignore
                ignored = not pattern.is_negation
        
        return ignored
    
    def filter_files(self, file_paths: List[str]) -> Tuple[List[str], List[str]]:
        """
        Filter a list of file paths, separating allowed and ignored files.
        
        Args:
            file_paths: List of file paths to filter
            
        Returns:
            Tuple of (allowed_files, ignored_files)
        """
        allowed = []
        ignored = []
        
        for file_path in file_paths:
            # Check if path is a directory
            full_path = file_path if os.path.isabs(file_path) else \
                       os.path.join(self.working_dir, file_path)
            is_dir = os.path.isdir(full_path)
            
            if self.is_ignored(file_path, is_dir):
                ignored.append(file_path)
            else:
                allowed.append(file_path)
        
        return allowed, ignored
    
    def filter_directory_contents(
        self,
        dir_path: str,
        files_content: List[dict]
    ) -> Tuple[List[dict], List[str]]:
        """
        Filter files found in a directory based on ignore patterns.
        
        This is used when reading directory contents to filter out ignored files.
        It also checks for .llmignore files within subdirectories.
        
        Args:
            dir_path: The directory path being scanned
            files_content: List of dicts with 'path' and 'content' keys
            
        Returns:
            Tuple of (allowed_files_content, ignored_file_paths)
        """
        allowed = []
        ignored = []
        
        # Also load .llmignore from the target directory if it exists
        dir_ignore = None
        full_dir_path = dir_path if os.path.isabs(dir_path) else \
                       os.path.join(self.working_dir, dir_path)
        
        dir_ignore_file = os.path.join(full_dir_path, self.IGNORE_FILENAME)
        if os.path.isfile(dir_ignore_file):
            dir_ignore = LLMIgnore(full_dir_path)
        
        for file_info in files_content:
            file_path = file_info.get('path', '')
            
            # Check against both root .llmignore and directory .llmignore
            is_ignored_root = self.is_ignored(
                os.path.join(dir_path, file_path) if dir_path != '.' else file_path,
                is_dir=False
            )
            
            is_ignored_dir = False
            if dir_ignore:
                is_ignored_dir = dir_ignore.is_ignored(file_path, is_dir=False)
            
            if is_ignored_root or is_ignored_dir:
                ignored.append(file_path)
            else:
                allowed.append(file_info)
        
        return allowed, ignored


def get_llmignore(working_dir: str) -> LLMIgnore:
    """
    Get an LLMIgnore instance for the given working directory.
    
    This is a convenience function for creating LLMIgnore instances.
    
    Args:
        working_dir: The working directory to use
        
    Returns:
        LLMIgnore instance
    """
    return LLMIgnore(working_dir)


def is_file_ignored(file_path: str, working_dir: str) -> bool:
    """
    Check if a single file is ignored.
    
    Convenience function for quick checks.
    
    Args:
        file_path: Path to check
        working_dir: Working directory containing .llmignore
        
    Returns:
        True if file should be ignored
    """
    llmignore = get_llmignore(working_dir)
    return llmignore.is_ignored(file_path)


def filter_at_context(
    at_context: dict,
    working_dir: str
) -> Tuple[dict, dict]:
    """
    Filter @ prefix context based on .llmignore patterns.
    
    This function filters the files and directories extracted from @ prefixed
    paths to ensure ignored files are never added to context.
    
    Args:
        at_context: Dict with 'files', 'directories', 'non_existing' lists
        working_dir: Working directory containing .llmignore
        
    Returns:
        Tuple of (filtered_context, ignored_context) where both are dicts
        with 'files' and 'directories' keys
    """
    llmignore = get_llmignore(working_dir)
    
    # Filter files (treat as files)
    allowed_files = []
    ignored_files = []
    for file_path in at_context.get('files', []):
        if llmignore.is_ignored(file_path, is_dir=False):
            ignored_files.append(file_path)
        else:
            allowed_files.append(file_path)
    
    # Filter directories (treat as directories)
    allowed_dirs = []
    ignored_dirs = []
    for dir_path in at_context.get('directories', []):
        if llmignore.is_ignored(dir_path, is_dir=True):
            ignored_dirs.append(dir_path)
        else:
            allowed_dirs.append(dir_path)
    
    filtered_context = {
        'files': allowed_files,
        'directories': allowed_dirs,
        'non_existing': at_context.get('non_existing', [])
    }
    
    ignored_context = {
        'files': ignored_files,
        'directories': ignored_dirs
    }
    
    return filtered_context, ignored_context
