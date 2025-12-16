"""File and directory completer for @ prefix, / commands, and $ MCP tools in CLI."""

import os
import yaml
from typing import Iterable, Dict, Any, Optional, Tuple
from pathlib import Path
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


def _load_command_tree_from_yaml(yaml_path: Optional[Path] = None) -> Dict[str, Tuple[str, Optional[Dict]]]:
    """
    Load command tree from YAML file and convert to internal format.
    
    Args:
        yaml_path: Path to command_tree.yaml file. If None, uses default location.
        
    Returns:
        Dictionary in format {command: (description, subcommands_dict or None)}
        
    Raises:
        FileNotFoundError: If YAML file doesn't exist
        yaml.YAMLError: If YAML file is malformed
    """
    if yaml_path is None:
        # Default to command_tree.yaml in project root
        # file_completer.py is in src/, so parent.parent gets us to project root
        yaml_path = Path(__file__).parent.parent / "command_tree.yaml"
    
    if not yaml_path.exists():
        raise FileNotFoundError(f"Command tree YAML file not found: {yaml_path}")
    
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    def convert_yaml_to_tree(yaml_dict: Dict[str, Any]) -> Dict[str, Tuple[str, Optional[Dict]]]:
        """Recursively convert YAML structure to internal tree format."""
        tree = {}
        for cmd_name, cmd_data in yaml_dict.items():
            description = cmd_data.get('description', '')
            subcommands_yaml = cmd_data.get('subcommands')
            
            if subcommands_yaml is None:
                # Leaf command
                tree[cmd_name] = (description, None)
            else:
                # Has subcommands - recursively convert
                subcommands_tree = convert_yaml_to_tree(subcommands_yaml)
                tree[cmd_name] = (description, subcommands_tree)
        
        return tree
    
    return convert_yaml_to_tree(data.get('commands', {}))


class SlashCommandCompleter(Completer):
    """
    Custom completer that provides hierarchical slash command completions.

    When the user types / at the beginning of input, this completer shows
    available commands with their descriptions in a nested tree structure.
    
    Command tree is loaded from command_tree.yaml for easy maintenance.
    """

    # Class variable to cache the loaded command tree
    _command_tree_cache: Optional[Dict[str, Tuple[str, Optional[Dict]]]] = None
    
    @classmethod
    def _get_command_tree(cls) -> Dict[str, Tuple[str, Optional[Dict]]]:
        """
        Get the command tree, loading from YAML if not cached.
        
        Returns:
            Command tree dictionary
        """
        if cls._command_tree_cache is None:
            try:
                cls._command_tree_cache = _load_command_tree_from_yaml()
            except (FileNotFoundError, yaml.YAMLError) as e:
                # Fallback to minimal hardcoded tree if YAML fails to load
                print(f"Warning: Failed to load command_tree.yaml: {e}")
                print("Using minimal fallback command tree")
                cls._command_tree_cache = {
                    'help': ('Show help message', None),
                    'exit': ('Exit the CLI', None),
                    'quit': ('Exit the CLI', None),
                    'clear': ('Clear chat history', None),
                    'models': ('List available models', None),
                    'session': ('Session management', None),
                    'context': ('Context management', None),
                }
        
        return cls._command_tree_cache
    
    @property
    def COMMAND_TREE(self) -> Dict[str, Tuple[str, Optional[Dict]]]:
        """Property to access command tree (for backward compatibility)."""
        return self._get_command_tree()

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
