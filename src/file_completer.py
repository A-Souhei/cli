"""File and directory completer for @ prefix in CLI."""

import os
from pathlib import Path
from typing import Iterable
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class AtPrefixFileCompleter(Completer):
    """
    Custom completer that provides file and directory completions for @ prefix.

    When the user types @ followed by TAB, this completer shows:
    - Files in the current working directory
    - Directories in the current working directory
    - Files in subdirectories when navigating
    """

    def __init__(self, working_dir: str = None):
        """
        Initialize the file completer.

        Args:
            working_dir: Working directory for file completion. Defaults to current directory.
        """
        self.working_dir = working_dir or os.getcwd()

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Get completions for the current input.

        Args:
            document: The current document
            complete_event: The completion event

        Yields:
            Completion objects for matching files/directories
        """
        # Get the text before the cursor
        text = document.text_before_cursor

        # Find all @ prefixed paths in the text
        # We look for the last @ to complete
        last_at = text.rfind('@')

        if last_at == -1:
            # No @ found, no completions
            return

        # Get the text after the last @
        path_text = text[last_at + 1:]

        # Get the word before the cursor (the part we're completing)
        word_before_cursor = document.get_word_before_cursor(WORD=True)

        # Determine the directory to search in
        if '/' in path_text:
            # User is navigating into subdirectories
            dir_path = os.path.dirname(path_text)
            search_prefix = os.path.basename(path_text)
            full_dir = os.path.join(self.working_dir, dir_path) if dir_path else self.working_dir
        else:
            # Searching in current directory
            dir_path = ""
            search_prefix = path_text
            full_dir = self.working_dir

        # Check if directory exists
        if not os.path.isdir(full_dir):
            return

        try:
            # List all entries in the directory
            entries = os.listdir(full_dir)
        except PermissionError:
            # Can't read directory
            return

        # Filter and sort entries
        matching_entries = []

        for entry in entries:
            # Skip hidden files unless user explicitly typed a dot
            if entry.startswith('.') and not search_prefix.startswith('.'):
                continue

            # Check if entry matches the search prefix
            if entry.lower().startswith(search_prefix.lower()):
                full_path = os.path.join(full_dir, entry)

                # Determine if it's a file or directory
                is_dir = os.path.isdir(full_path)

                # Calculate the display text
                if dir_path:
                    display = f"{dir_path}/{entry}"
                else:
                    display = entry

                # Add trailing slash for directories
                if is_dir:
                    display += "/"

                # Calculate how much of the word to replace
                # We want to replace from after the @ to the cursor
                start_position = -len(path_text)

                matching_entries.append({
                    'text': display,
                    'is_dir': is_dir,
                    'start_position': start_position
                })

        # Sort: directories first, then files, alphabetically
        matching_entries.sort(key=lambda x: (not x['is_dir'], x['text'].lower()))

        # Yield completions
        for entry in matching_entries:
            # Add metadata to display
            if entry['is_dir']:
                display_meta = "directory"
            else:
                display_meta = "file"

            yield Completion(
                text=entry['text'],
                start_position=entry['start_position'],
                display=entry['text'],
                display_meta=display_meta
            )


def parse_at_prefixed_paths(text: str) -> list[str]:
    """
    Parse @ prefixed file/directory paths from user input.

    Special keywords:
    - @WD: Represents the entire working directory

    Args:
        text: User input text

    Returns:
        List of file/directory paths (without @ prefix)
    """
    import re

    # Pattern to match @path (path can include letters, numbers, dots, slashes, underscores, hyphens)
    # It should stop at whitespace or end of string
    # Also match @WD as a special keyword
    pattern = r'@([\w\-./]+)'

    matches = re.findall(pattern, text)
    return matches


def extract_at_context(text: str, working_dir: str) -> dict:
    """
    Extract @ prefixed paths and categorize them into files and directories.

    Special keywords:
    - @WD: Represents the entire working directory

    Args:
        text: User input text
        working_dir: Working directory for resolving relative paths

    Returns:
        Dict with 'files', 'directories', and 'non_existing' lists
    """
    paths = parse_at_prefixed_paths(text)

    result = {
        'files': [],
        'directories': [],
        'non_existing': []
    }

    for path in paths:
        # Handle special @WD keyword
        if path == 'WD':
            # Add entire working directory
            result['directories'].append('.')
            continue

        # Remove trailing slash if present
        path = path.rstrip('/')

        # Convert to absolute path
        if not os.path.isabs(path):
            full_path = os.path.join(working_dir, path)
        else:
            full_path = path

        # Categorize
        if os.path.isfile(full_path):
            result['files'].append(path)
        elif os.path.isdir(full_path):
            result['directories'].append(path)
        else:
            result['non_existing'].append(path)

    return result


def remove_at_prefixed_paths(text: str) -> str:
    """
    Remove @ prefixed paths from text, leaving the rest of the user input.

    Args:
        text: User input text

    Returns:
        Text with @ prefixed paths removed
    """
    import re

    # Pattern to match @path
    pattern = r'@[\w\-./]+'

    # Replace with empty string
    cleaned = re.sub(pattern, '', text)

    # Clean up extra whitespace
    cleaned = ' '.join(cleaned.split())

    return cleaned.strip()
