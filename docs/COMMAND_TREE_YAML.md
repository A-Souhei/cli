# Command Tree YAML Configuration

## Overview

The CLI command completion system now uses a YAML configuration file (`command_tree.yaml`) instead of hardcoded Python dictionaries. This makes it easy to add, modify, or remove commands without touching the code.

## File Location

The `command_tree.yaml` file is located in the project root directory:

```
cli/
├── command_tree.yaml  ← Command tree configuration
├── src/
│   └── file_completer.py  ← Loads and uses the YAML
└── tests/
    ├── test_nested_completions.py
    └── test_yaml_command_tree.py
```

## YAML Structure

The YAML file uses a hierarchical structure to define commands and subcommands:

```yaml
commands:
  command_name:
    description: "What this command does"
    subcommands: null  # For leaf commands (no further nesting)
  
  nested_command:
    description: "Command with subcommands"
    subcommands:
      subcommand_1:
        description: "First subcommand"
        subcommands: null
      subcommand_2:
        description: "Second subcommand"
        subcommands:
          sub_subcommand:
            description: "Deeply nested command"
            subcommands: null
```

### Key Rules

1. **Top Level**: Must have a `commands:` key containing all root commands
2. **Each Command**: Has two properties:
   - `description`: A short description shown in the dropdown
   - `subcommands`: Either `null` (for leaf commands) or a nested dictionary of subcommands
3. **Nesting**: Commands can be nested to any depth
4. **Placeholders**: Use `<name>` or `[optional]` for parameter placeholders

## Examples

### Simple Command (No Subcommands)

```yaml
commands:
  help:
    description: "Show help message"
    subcommands: null
```

### Command with Subcommands

```yaml
commands:
  session:
    description: "Session management"
    subcommands:
      start:
        description: "Start a new context session"
        subcommands: null
      end:
        description: "End the current session"
        subcommands: null
      list:
        description: "List all saved sessions"
        subcommands: null
```

### Deeply Nested Commands

```yaml
commands:
  model:
    description: "Model management"
    subcommands:
      general:
        description: "General models"
        subcommands:
          list:
            description: "List general models"
            subcommands: null
          add:
            description: "Add general model"
            subcommands:
              "<url>":
                description: "Model URL"
                subcommands:
                  "<model_name>":
                    description: "Model name"
                    subcommands: null
```

This creates the completion tree:
- `/model` → Shows "general", "coder", "embedding", etc.
- `/model general` → Shows "list", "add", "use", "remove"
- `/model general add` → Shows "<url>" placeholder
- `/model general add <url>` → Shows "<model_name>" placeholder

## Adding New Commands

To add a new command:

1. Open `command_tree.yaml`
2. Add your command under the appropriate level
3. Provide a description and subcommands (or `null`)
4. Save the file
5. Restart the CLI (the YAML is cached after first load)

**Example**: Adding a new `/debug` command with subcommands:

```yaml
commands:
  # ... existing commands ...
  
  debug:
    description: "Debug utilities"
    subcommands:
      show:
        description: "Show debug information"
        subcommands: null
      clear:
        description: "Clear debug logs"
        subcommands: null
      level:
        description: "Set debug level"
        subcommands:
          "<level>":
            description: "Debug level (0-5)"
            subcommands: null
```

## Validation

The CLI includes comprehensive tests to ensure YAML validity:

```bash
# Run tests to validate the command tree
pytest tests/test_yaml_command_tree.py -v

# Run all completion tests
pytest tests/test_nested_completions.py tests/test_yaml_command_tree.py -v
```

## Fallback Behavior

If the YAML file fails to load (missing, malformed, etc.), the CLI falls back to a minimal hardcoded command tree with basic commands:
- help
- exit
- quit
- clear
- models
- session
- context

This ensures the CLI remains functional even if the YAML file has issues.

## Cache

The command tree is loaded once and cached in memory for performance. To reload after changes:

1. Restart the CLI application
2. Or clear the cache programmatically (for development):

```python
from src.file_completer import SlashCommandCompleter
SlashCommandCompleter._command_tree_cache = None
```

## Benefits

✅ **Easy Maintenance**: Update commands without touching Python code  
✅ **Version Control Friendly**: YAML diffs are readable and reviewable  
✅ **No Code Deploy**: Just update the YAML file and restart  
✅ **Clear Structure**: Hierarchical format matches the command structure  
✅ **Validation**: Tests ensure the YAML is valid and complete  
✅ **Backward Compatible**: Existing code continues to work unchanged

## Technical Details

### Internal Format Conversion

The YAML structure is converted to an internal Python format:

```python
{
    'command': (description, subcommands_dict or None)
}
```

This conversion happens automatically when the YAML is loaded.

### Code Reference

- **YAML Loader**: `src/file_completer.py::_load_command_tree_from_yaml()`
- **Completer Class**: `src/file_completer.py::SlashCommandCompleter`
- **YAML File**: `command_tree.yaml`
- **Tests**: `tests/test_yaml_command_tree.py`

## Troubleshooting

### Error: "Command tree YAML file not found"

**Solution**: Ensure `command_tree.yaml` exists in the project root directory.

### Error: "yaml.scanner.ScannerError"

**Solution**: Check YAML syntax. Common issues:
- Incorrect indentation (must use spaces, not tabs)
- Missing colons after keys
- Unquoted strings with special characters
- Mismatched brackets in placeholders like `<name>`

### Commands not appearing in dropdown

**Solutions**:
1. Check that the command is in the YAML file
2. Verify YAML indentation is correct
3. Ensure `description` and `subcommands` keys are present
4. Restart the CLI to reload the cache
5. Run tests: `pytest tests/test_yaml_command_tree.py -v`

### Description not showing

**Solution**: Descriptions must be non-empty strings. Check that your command has a valid description.

## Future Enhancements

Potential improvements to the YAML-based system:

- [ ] Hot-reload without restart
- [ ] YAML schema validation with JSON Schema
- [ ] Command aliases defined in YAML
- [ ] Command metadata (permissions, availability checks)
- [ ] Multi-language descriptions
- [ ] Auto-generate documentation from YAML
