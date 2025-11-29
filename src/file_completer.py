"""File and directory completer for @ prefix and / commands in CLI."""

import os
from typing import Iterable
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class SlashCommandCompleter(Completer):
    """
    Custom completer that provides slash command completions.

    When the user types / at the beginning of input, this completer shows
    available commands with their descriptions.
    """

    # Define all available slash commands with descriptions
    COMMANDS = [
        ('/exit', 'Exit the CLI'),
        ('/quit', 'Exit the CLI'),
        ('/clear', 'Clear chat history'),
        ('/models', 'List available models'),
        ('/switch', 'Switch to a different model'),
        ('/mcps', 'List system MCPs'),
        ('/mcp-tools <name>', 'List tools in an MCP'),
        ('/session start', 'Start a context session'),
        ('/session end', 'End the current session'),
        ('/session info', 'View current session info'),
        ('/repomap create', 'Create a repository map from working directory'),
        ('/repomap load', 'Load existing .repomap file into context'),
        ('/datamap create', 'Create a data map from data files'),
        ('/datamap create --files-only', 'Create a data map from local data files only'),
        ('/datamap create --with-pg', 'Create a data map including PostgreSQL database'),
        ('/datamap create --with-files --with-pg', 'Create a data map from files and PostgreSQL'),
        ('/datamap load', 'Load existing .datamap file into context'),
        ('/code <prompt>', 'Analyze and execute code tasks (requires session)'),
    ]

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Get completions for slash commands.

        Args:
            document: The current document
            complete_event: The completion event

        Yields:
            Completion objects for matching slash commands
        """
        text = document.text_before_cursor

        # Only provide completions if the text starts with /
        if not text.startswith('/'):
            return

        # Get the command prefix (everything after /)
        command_prefix = text[1:].lower()

        # Find matching commands
        for command, description in self.COMMANDS:
            command_without_slash = command[1:]  # Remove the leading /

            # Check if this command matches the prefix
            if command_without_slash.lower().startswith(command_prefix):
                # Calculate how much to replace (from the / to cursor)
                start_position = -len(text)

                yield Completion(
                    text=command,
                    start_position=start_position,
                    display=command,
                    display_meta=description
                )


class CombinedCompleter(Completer):
    """
    Combined completer that handles both slash commands and @ file paths.
    """

    def __init__(self, working_dir: str = None):
        """
        Initialize the combined completer.

        Args:
            working_dir: Working directory for file completion
        """
        self.working_dir = working_dir or os.getcwd()
        self.slash_completer = SlashCommandCompleter()
        self.file_completer = AtPrefixFileCompleter(working_dir)

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Get completions from both slash commands and file paths.

        Args:
            document: The current document
            complete_event: The completion event

        Yields:
            Completion objects from both completers
        """
        text = document.text_before_cursor

        # If text starts with /, use slash command completer
        if text.startswith('/'):
            yield from self.slash_completer.get_completions(document, complete_event)

        # If text contains @, use file completer (can work with /code @file.py)
        if '@' in text:
            yield from self.file_completer.get_completions(document, complete_event)


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
