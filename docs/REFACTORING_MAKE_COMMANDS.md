# Refactoring: Unbloating main.py - /make Commands

## Overview
This refactoring extracts the `/make` command handlers from `main.py` into a separate module to reduce code bloat and improve maintainability.

## Changes Made

### 1. Created New Module: `src/cli/commands/make.py`
- **Lines**: 890 lines
- **Purpose**: Contains all `/make` command logic
- **Handlers**:
  - `handle_make_map_generate()` - Generates .makemap from Makefile using LLM
  - `handle_make_map_load()` - Loads .makemap into context for session
  - `handle_make_map_update()` - Updates existing .makemap with new targets
  - `handle_make_execute()` - Executes make commands using natural language

### 2. Updated `src/cli/dispatcher.py`
- **Added imports** for all 4 make command handlers
- **Updated constructor** to accept additional parameters:
  - `stream` - for streaming LLM responses
  - `temperature` - for LLM temperature setting
  - `CustomMarkdown` - for rendering markdown previews
- **Added routing logic** for /make commands:
  - `/make map generate` → `handle_make_map_generate()`
  - `/make map load` → `handle_make_map_load()`
  - `/make map update` → `handle_make_map_update()`
  - `/make <prompt>` → `handle_make_execute()`

### 3. Updated `main.py`
- **Removed**: 537 lines of `/make` command handling code (lines 963-1490)
- **Removed**: Direct imports from `src.utils.makemap`
- **Updated**: CommandDispatcher initialization to pass new parameters
- **Result**: Reduced from 2465 lines to 1928 lines (21.8% reduction)

## Benefits

1. **Improved Code Organization**
   - Follows existing pattern for command handlers (session, context, model, etc.)
   - Separates concerns - main.py focuses on main loop, commands are modular

2. **Better Maintainability**
   - Each command module is self-contained and testable
   - Easier to find and modify specific command logic
   - Reduces cognitive load when working with main.py

3. **Consistency**
   - All commands now follow the same architectural pattern
   - Uniform handler signatures and return values

4. **No Functionality Loss**
   - All 24 makemap unit tests pass ✓
   - Full integration tests pass ✓
   - All existing tests continue to pass ✓

## Testing

### Unit Tests
```bash
# Run makemap tests
./venv/bin/pytest tests/test_makemap.py -v
# Result: 24/24 passed
```

### Integration Tests
```bash
# Run full test suite
make test-unit
# Result: All tests passed
```

### Manual Verification
- Python syntax validation for all modified files ✓
- Import checks for all new modules ✓
- Handler callability verification ✓

## Implementation Details

### Handler Pattern
All handlers follow this pattern:
1. Accept necessary dependencies as parameters (dependency injection)
2. Return `True` to indicate command was handled
3. Handle all errors internally with appropriate user messages
4. Use console for all output (rich formatting)

### Example Handler Signature
```python
def handle_make_map_generate(console, user_input_normalized, llm_checker,
                              get_user_working_dir, config, ollama_client,
                              stream, temperature, verbose, CustomMarkdown):
    # ... implementation ...
    return True  # Command was handled
```

## Files Modified

1. `src/cli/commands/make.py` - NEW (890 lines)
2. `src/cli/dispatcher.py` - Modified (imports + routing + constructor)
3. `main.py` - Modified (removed 537 lines, updated dispatcher init)

## Migration Notes

- No breaking changes to command syntax
- All `/make` commands work exactly as before
- No changes to user-facing behavior
- Internal architecture only

## Future Improvements

Potential follow-up refactorings:
1. Extract `/code` command to `src/cli/commands/code.py`
2. Extract `/repomap` commands to `src/cli/commands/repomap.py`
3. Extract `/datamap` commands to `src/cli/commands/datamap.py`
4. Continue pattern until main.py only contains main loop logic

## References

- Original Implementation Plan: `docs/MAKE_COMMAND_PLAN.md`
- Similar pattern: See `src/cli/commands/session.py`, `src/cli/commands/model.py`
- Test file: `tests/test_makemap.py`
