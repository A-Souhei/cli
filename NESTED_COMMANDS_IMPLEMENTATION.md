# Nested Command Dropdown Implementation

## Overview

This document describes the implementation of the hierarchical/nested command dropdown system for the AI CLI. The new system organizes commands in a tree structure, allowing users to explore commands at different levels with contextual completions and descriptions.

## Problem Statement

The previous implementation used a flat list of commands, making it difficult for users to discover related commands and understand the command hierarchy. Users had to memorize long command strings like `/context add TODO_LIST` without any guidance on what subcommands were available at each level.

## Solution

We implemented a hierarchical command tree structure that:
1. Shows relevant subcommands based on the current input level
2. Displays short descriptions for each command option
3. Supports multi-level navigation (e.g., / → /context → /context add → /context add TODO_LIST)
4. Maintains backward compatibility with existing command usage

## Implementation Details

### File Modified
- `src/file_completer.py` - SlashCommandCompleter class

### Key Changes

#### 1. Command Tree Structure
Replaced the flat `COMMANDS` list with a nested `COMMAND_TREE` dictionary:

```python
COMMAND_TREE = {
    'context': ('Context management', {
        'add': ('Add to context without LLM call', {
            '@file': ('Add file to context', None),
            '@directory': ('Add directory to context', None),
            'ALL': ('Add entire working directory', None),
            'ALL_TOOLS': ('Add all MCP tools with descriptions', None),
            'TODO_LIST': ('Generate strategic TODO list', {
                '<description>': ('Task description', None),
            }),
            # ... more options
        }),
        'show': ('Display current context', None),
        'clear': ('Clear current context', None),
        # ... more subcommands
    }),
    # ... more root commands
}
```

Format: `{command: (description, subcommands_dict or None)}`
- Leaf commands have `None` as subcommands
- Non-leaf commands have another dictionary of subcommands

#### 2. Navigation Logic
The `get_completions()` method now:
1. Parses the input to identify completed parts and the current partial input
2. Navigates through the command tree based on completed parts
3. Returns completions for the current level
4. Handles placeholders like `<name>`, `[@path]` for parameter positions

#### 3. Completion Generation
Commands are built with spaces (not slashes):
- `/` → shows root commands
- `/context ` → shows context subcommands
- `/context add ` → shows context add options
- `/model general ` → shows general model commands

## Command Hierarchy

### Root Level Commands
```
/help, /exit, /quit, /clear, /models, /switch, /mcps, /mcp-tools, 
/wd, /session, /context, /repomap, /datamap, /ignore, /make, 
/execute, /code, /model
```

### Key Command Trees

#### /context
```
context
├── add
│   ├── @file
│   ├── @directory
│   ├── ALL
│   ├── ALL_TOOLS
│   ├── TODO_LIST <description>
│   └── MAKE_LIST <description>
├── show
├── clear
├── metrics
├── load
│   ├── TODO_LIST [@path]
│   └── MAKE_LIST [@path]
└── save
    ├── TODO_LIST [@path]
    └── MAKE_LIST [@path]
```

#### /session
```
session
├── start
├── end
├── info
├── list
├── restore <id>
├── delete <id>
└── clear
```

#### /model
```
model
├── status
├── list
├── general
│   ├── list
│   ├── add <url> <model_name>
│   ├── use <model_id>
│   └── remove <model_id>
├── coder (same structure as general)
├── embedding (same structure as general)
└── check [model_id]
```

#### /make
```
make
├── map
│   ├── generate
│   ├── load
│   └── update
└── <prompt>
```

## Testing

### Test Coverage
Created comprehensive test suite in `tests/test_nested_completions.py`:
- 17 test cases covering all command levels
- Tests for root commands, nested subcommands, partial matching
- Tests for descriptions presence
- Tests for leaf node behavior (no completions after leaf)

### Test Results
All 17 tests pass successfully:
```
tests/test_nested_completions.py::TestNestedCompletions::test_root_level_completions PASSED
tests/test_nested_completions.py::TestNestedCompletions::test_context_subcommands PASSED
tests/test_nested_completions.py::TestNestedCompletions::test_context_add_options PASSED
... (14 more tests)
```

## Backward Compatibility

The implementation maintains full backward compatibility:
- Existing command strings work exactly as before
- Users can type full commands directly (e.g., `/session start`)
- No breaking changes to the CLI command processing logic
- The dispatcher in `src/cli/dispatcher.py` remains unchanged

## User Experience

### Before
Users saw a flat list of all possible commands:
```
/session start                 - Start a context session
/session end                   - End the current session
/context add @file            - Add file to context
/context add ALL              - Add entire working directory
... (all combinations shown at once)
```

### After
Users see contextual completions at each level:
```
Level 1: /
  /session    - Session management
  /context    - Context management
  ...

Level 2: /session 
  /session start    - Start a new context session
  /session end      - End the current session
  ...

Level 3: /context add 
  /context add @file      - Add file to context
  /context add ALL        - Add entire working directory
  ...
```

## Adding New Commands

To add a new command:

1. **Find the appropriate location in COMMAND_TREE**
2. **Add the command with description and subcommands**

Example - Adding `/context export` command:
```python
'context': ('Context management', {
    'add': (...),
    'show': (...),
    'export': ('Export context to file', {  # NEW
        '@path': ('Export file path', None),
    }),
    # ... other commands
}),
```

3. **Update tests** in `tests/test_nested_completions.py`
4. **Update dispatcher** in `src/cli/dispatcher.py` to handle the command

## Benefits

1. **Discoverability**: Users can explore commands by typing and seeing what's available
2. **Context-Aware**: Only relevant options shown at each level
3. **Self-Documenting**: Descriptions help users understand what each command does
4. **Scalability**: Easy to add new commands without cluttering the top level
5. **Maintainability**: Hierarchical structure is easier to maintain than flat list

## Future Enhancements

Potential improvements:
1. Add command usage examples in descriptions
2. Support for command aliases at any level
3. Dynamic command loading from plugins
4. Command history-based suggestions
5. Fuzzy matching for typo tolerance

## References

- Implementation: `src/file_completer.py` (SlashCommandCompleter class)
- Tests: `tests/test_nested_completions.py`
- Command Handler: `src/cli/dispatcher.py`
- Documentation: `CLAUDE.md` (Command Management section)
