"""File and directory completer for @ prefix, / commands, and $ MCP tools in CLI."""

import os
from typing import Iterable
from pathlib import Path
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class SlashCommandCompleter(Completer):
    """
    Custom completer that provides hierarchical slash command completions.

    When the user types / at the beginning of input, this completer shows
    available commands with their descriptions in a nested tree structure.
    """

    # Define hierarchical command structure
    # Format: {command: (description, subcommands_dict)}
    # Leaf commands have None as subcommands
    COMMAND_TREE = {
        'help': ('Show help message', None),
        'exit': ('Exit the CLI', None),
        'quit': ('Exit the CLI', None),
        'clear': ('Clear chat history', None),
        'models': ('List available models', None),
        'switch': ('Switch to a different model', None),
        'mcps': ('List system MCPs', None),
        'mcp-tools': ('List tools in an MCP', {
            '<name>': ('MCP name to query', None),
        }),
        'wd': ('Working directory commands', {
            'show': ('Show current working directory', None),
            'change': ('Change working directory', {
                '<path>': ('Directory path', None),
            }),
            'cd': ('Change working directory (alias)', {
                '<path>': ('Directory path', None),
            }),
        }),
        'session': ('Session management', {
            'start': ('Start a new context session', None),
            'end': ('End the current session', None),
            'info': ('View current session info', None),
            'list': ('List all saved sessions', None),
            'restore': ('Restore a saved session', {
                '<id>': ('Session ID to restore', None),
            }),
            'delete': ('Delete a saved session', {
                '<id>': ('Session ID to delete', None),
            }),
            'clear': ('Clear all saved sessions', None),
        }),
        'context': ('Context management', {
            'add': ('Add to context without LLM call', {
                '@file': ('Add file to context', None),
                '@directory': ('Add directory to context', None),
                'ALL': ('Add entire working directory', None),
                'ALL_TOOLS': ('Add all MCP tools with descriptions', None),
                'TODO_LIST': ('Generate strategic TODO list', {
                    '<description>': ('Task description', None),
                }),
                'MAKE_LIST': ('Generate strategic MAKE_LIST', {
                    '<description>': ('Task description', None),
                }),
            }),
            'show': ('Display current context', None),
            'clear': ('Clear current context', None),
            'metrics': ('Show context size and metrics', None),
            'load': ('Load from file', {
                'TODO_LIST': ('Load TODO_LIST from file', {
                    '[@path]': ('Optional file path', None),
                }),
                'MAKE_LIST': ('Load MAKE_LIST from file', {
                    '[@path]': ('Optional file path', None),
                }),
            }),
            'save': ('Save to file', {
                'TODO_LIST': ('Save TODO_LIST to file', {
                    '[@path]': ('Optional file path', None),
                }),
                'MAKE_LIST': ('Save MAKE_LIST to file', {
                    '[@path]': ('Optional file path', None),
                }),
            }),
        }),
        'repomap': ('Repository mapping', {
            'create': ('Create repository map', None),
            'load': ('Load existing .repomap file', None),
            'update': ('Update existing .repomap', None),
        }),
        'datamap': ('Data file mapping', {
            'create': ('Create data map', {
                '--files-only': ('Local data files only', None),
                '--with-pg': ('Include PostgreSQL database', None),
                '--with-files': ('Include local files', None),
            }),
            'load': ('Load existing .datamap file', None),
            'update': ('Update existing .datamap', {
                '--with-files': ('Include local files', None),
                '--with-pg': ('Include PostgreSQL database', None),
            }),
        }),
        'ignore': ('Security & ignore patterns', {
            'create': ('Create .llmignore file', None),
            'add': ('Add file(s) to .llmignore', {
                '@file': ('File to add', None),
            }),
        }),
        'make': ('Make commands', {
            'map': ('Makefile mapping', {
                'generate': ('Generate .makemap from Makefile', None),
                'load': ('Load existing .makemap file', None),
                'update': ('Update .makemap with new targets', None),
            }),
            '<prompt>': ('Execute make with natural language', None),
        }),
        'execute': ('Execute plans', {
            'TODO_LIST': ('Execute TODO_LIST from context', None),
            'MAKE_LIST': ('Execute MAKE_LIST from context', None),
            '@path': ('Execute plan from file', None),
        }),
        'code': ('Analyze and execute code', {
            '<prompt>': ('Code task description', None),
        }),
        'model': ('Model management', {
            'status': ('Show all configured models', None),
            'list': ('List all models', None),
            'general': ('General models', {
                'list': ('List general models', None),
                'add': ('Add general model', {
                    '<url>': ('Model URL', {
                        '<model_name>': ('Model name', None),
                    }),
                }),
                'use': ('Set active general model', {
                    '<model_id>': ('Model ID', None),
                }),
                'remove': ('Remove general model', {
                    '<model_id>': ('Model ID', None),
                }),
            }),
            'coder': ('Coder models', {
                'list': ('List coder models', None),
                'add': ('Add coder model', {
                    '<url>': ('Model URL', {
                        '<model_name>': ('Model name', None),
                    }),
                }),
                'use': ('Set active coder model', {
                    '<model_id>': ('Model ID', None),
                }),
                'remove': ('Remove coder model', {
                    '<model_id>': ('Model ID', None),
                }),
            }),
            'embedding': ('Embedding services', {
                'list': ('List embedding services', None),
                'add': ('Add embedding service', {
                    '<url>': ('Service URL', {
                        '[timeout]': ('Optional timeout', None),
                    }),
                }),
                'use': ('Set active embedding service', {
                    '<model_id>': ('Model ID', None),
                }),
                'remove': ('Remove embedding service', {
                    '<model_id>': ('Model ID', None),
                }),
            }),
            'check': ('Check model availability', {
                '[model_id]': ('Optional model ID', None),
            }),
        }),
    }

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Get completions for slash commands with nested hierarchy support.

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

        # Remove the leading / and split into parts
        command_parts = text[1:].split()
        
        # Get the current partial command being typed
        if text.endswith(' '):
            # User has completed a word and is ready for next level
            current_part = ''
            completed_parts = command_parts
        else:
            # User is typing a word
            if command_parts:
                current_part = command_parts[-1]
                completed_parts = command_parts[:-1]
            else:
                current_part = ''
                completed_parts = []

        # Navigate to the current level in the command tree
        current_tree = self.COMMAND_TREE
        full_command_so_far = []
        
        for part in completed_parts:
            # Try exact match first
            if part in current_tree:
                desc, subtree = current_tree[part]
                full_command_so_far.append(part)
                if subtree is None:
                    # This is a leaf node, no more completions
                    return
                current_tree = subtree
            else:
                # Check if it matches a placeholder pattern like <name> or [@path]
                found = False
                for key in current_tree.keys():
                    if key.startswith('<') or key.startswith('['):
                        # This is a placeholder, move to its subtree if available
                        desc, subtree = current_tree[key]
                        if subtree:
                            current_tree = subtree
                            found = True
                            break
                if not found:
                    # Can't navigate further, stop
                    return

        # Now generate completions from the current tree level
        for cmd, (description, subtree) in current_tree.items():
            # Check if this command matches the current partial input
            if cmd.lower().startswith(current_part.lower()):
                # Build the full command text with spaces
                full_cmd_parts = full_command_so_far + [cmd]
                full_command = '/' + ' '.join(full_cmd_parts)
                
                # Calculate start position (replace from / to cursor)
                start_position = -len(text)
                
                yield Completion(
                    text=full_command,
                    start_position=start_position,
                    display=full_command,
                    display_meta=description
                )


class DollarPrefixCompleter(Completer):
    """
    Custom completer that provides MCP tool execution hints.
    
    When the user types $ at the beginning of input, this completer shows
    a helpful hint about the MCP tool execution feature.
    """
    
    def __init__(self, system_mcps_dir: Path = None):
        """
        Initialize the dollar prefix completer.
        
        Args:
            system_mcps_dir: Directory containing MCP servers
        """
        self.system_mcps_dir = system_mcps_dir or Path(__file__).parent.parent.parent / "system_mcps"
        self._mcps_cache = None
    
    def _get_available_mcps(self):
        """Get list of available MCPs (cached)."""
        if self._mcps_cache is None:
            self._mcps_cache = []
            if self.system_mcps_dir.exists():
                for item in self.system_mcps_dir.iterdir():
                    if item.is_dir() and (item / "server.py").exists():
                        self._mcps_cache.append(item.name)
        return self._mcps_cache
    
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Get completions for $ prefix.
        
        Args:
            document: The current document
            complete_event: The completion event
            
        Yields:
            Completion objects with MCP tool execution hints
        """
        text = document.text_before_cursor
        
        # Only provide completions if the text starts with $ and has minimal content
        if not text.startswith('$'):
            return
        
        # If user just typed "$" or "$ ", show helpful suggestions
        if len(text.strip()) <= 2:
            mcps = self._get_available_mcps()
            mcp_count = len(mcps)
            
            yield Completion(
                text='$ ',
                start_position=-len(text),
                display='$ <describe task>',
                display_meta=f'Direct MCP tool execution ({mcp_count} MCPs available)'
            )
            
            # Show a few example prompts
            examples = [
                ('$ generate fake data', 'Generate synthetic data from a file'),
                ('$ analyze code', 'Analyze code quality and patterns'),
                ('$ run python script', 'Execute Python code directly'),
            ]
            
            for example, description in examples:
                yield Completion(
                    text=example,
                    start_position=-len(text),
                    display=example,
                    display_meta=description
                )


class CombinedCompleter(Completer):
    """
    Combined completer that handles slash commands, @ file paths, and $ MCP tools.
    """

    def __init__(self, working_dir: str = None, system_mcps_dir: Path = None):
        """
        Initialize the combined completer.

        Args:
            working_dir: Working directory for file completion
            system_mcps_dir: Directory containing MCP servers
        """
        self.working_dir = working_dir or os.getcwd()
        self.slash_completer = SlashCommandCompleter()
        self.file_completer = AtPrefixFileCompleter(working_dir)
        self.dollar_completer = DollarPrefixCompleter(system_mcps_dir)

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Get completions from slash commands, file paths, and dollar prefix.

        Args:
            document: The current document
            complete_event: The completion event

        Yields:
            Completion objects from all completers
        """
        text = document.text_before_cursor

        # If text starts with /, use slash command completer
        if text.startswith('/'):
            yield from self.slash_completer.get_completions(document, complete_event)
        
        # If text starts with $, use dollar prefix completer
        elif text.startswith('$'):
            yield from self.dollar_completer.get_completions(document, complete_event)

        # If text contains @, use file completer (can work with /code @file.py or $ command @file.py)
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
