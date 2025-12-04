# main.py Structure Documentation

This document explains the refactored structure of `main.py` and how its components are organized into separate modules.

## Overview

The original `main.py` file had 2583 lines, which made it difficult to maintain and iterate on. It has been refactored into a more modular structure, reducing the main file to approximately 1969 lines (24% reduction).

## File Structure

### Main File (`main.py`)

The main file now contains:

1. **Critical Imports and Setup** (Lines 1-92)
   - Working directory preservation
   - Import statements for all dependencies
   - Import of new CLI modules (initialization, dispatcher)
   - Global configuration for nested async event loops

2. **Helper Functions** (Lines 93-204)
   - `get_user_working_dir()` - Returns user's original working directory
   - `set_user_working_dir(new_path)` - Changes working directory
   - `run_async(coro)` - Executes async coroutines in sync context
   - `CustomMarkdown` - Custom markdown rendering class
   - `debug_print(message, icon, style)` - Debug output helper

3. **Global Variables** (Lines 147-195)
   - Rich console theme and console instance
   - History file path
   - API URLs (PostgreSQL, Redis, Transformer)
   - VERBOSE flag

4. **Main Function** (Lines 205-1903)
   - Initialization using `CLIInitializer`
   - Command dispatcher setup
   - Main chat loop with:
     - Command dispatch handling
     - Repomap commands (create, load, update)
     - Datamap commands (create, load, update)
     - Code execution commands
     - Chat processing and LLM interaction
     - Rating system
     - Session management
     - Error handling

5. **Entry Point** (Lines 1904-1969)
   - Argument parsing
   - UI server management
   - Main function invocation

### New Modules

#### `src/cli/initialization.py`

**Purpose**: Handles initialization of all CLI components

**Class**: `CLIInitializer`

**Key Responsibilities**:
- Load configuration from `ConfigManager`
- Initialize model registry
- Set up embedding client with fallback
- Run database migrations
- Check model availability
- Initialize Ollama client
- Create chat manager
- Set up session manager with title generator
- Initialize MCP client and tools
- Display startup banner
- Create command history and file completer

**Usage**:
```python
initializer = CLIInitializer(
    verbose=verbose,
    debug_print=debug_print,
    run_async=run_async,
    get_user_working_dir=get_user_working_dir,
    console=console,
    history_file=HISTORY_FILE,
    postgres_api_url=POSTGRES_API_URL
)
components = initializer.initialize_all()
```

#### `src/cli/dispatcher.py`

**Purpose**: Routes user commands to appropriate handlers

**Class**: `CommandDispatcher`

**Key Responsibilities**:
- Dispatch commands to their handlers
- Manage command completer updates
- Handle command routing logic

**Commands Handled**:
- `exit`, `quit` → Basic commands
- `clear` → Clear chat history  
- `wd`, `wd show`, `wd change`, `wd cd` → Working directory commands
- `models`, `switch` → Model listing and switching
- `mcps`, `mcp-tools` → MCP tools
- `session start`, `session end`, `session info`, `session restore`, `session delete`, `session list`, `session clear` → Session management
- `model <subcommands>` → Model registry management

**Usage**:
```python
dispatcher = CommandDispatcher(
    console=console,
    config=config,
    ollama_client=ollama_client,
    # ... other dependencies
)

dispatch_result = dispatcher.dispatch(user_input_normalized)
if dispatch_result is None:
    return  # Exit requested
elif dispatch_result is True:
    continue  # Command handled, continue loop
# else: not a command, process as chat
```

### Command Handler Modules

#### `src/cli/commands/basic.py`

**Functions**:
- `handle_exit(console, mcp_client, run_async, debug_print, verbose)` - Handles exit/quit
- `handle_clear(console, chat_manager)` - Clears chat history

#### `src/cli/commands/working_dir.py`

**Functions**:
- `handle_wd_show(console, get_user_working_dir)` - Shows current working directory
- `handle_wd_change(console, user_input_normalized, ...)` - Changes working directory

#### `src/cli/commands/session.py`

**Functions**:
- `handle_session_start(...)` - Starts a new session
- `handle_session_end(...)` - Ends current session
- `handle_session_info(...)` - Displays session info
- `handle_session_restore(...)` - Restores a saved session
- `handle_session_delete(...)` - Deletes a session
- `handle_session_list(...)` - Lists all sessions
- `handle_session_clear(...)` - Clears all sessions

#### `src/cli/commands/mcp.py`

**Functions**:
- `handle_mcps(list_system_mcps)` - Lists available MCP servers
- `handle_mcp_tools(console, user_input_normalized, ...)` - Shows tools for an MCP server

#### `src/cli/commands/model.py`

**Functions**:
- `handle_models_alias(user_input_normalized)` - Converts /models to /model
- `handle_models_list(console, ollama_client)` - Lists available models
- `handle_switch_model(console, ollama_client, InteractiveSelector)` - Switches active model
- `handle_model_commands(console, user_input_normalized, ...)` - Handles all /model subcommands including:
  - `/model status` - Show model status
  - `/model list` - List all models
  - `/model <type> list` - List models of specific type
  - `/model <type> add` - Add new model
  - `/model embedding add` - Add embedding service
  - `/model <type> use` - Set active model
  - `/model <type> remove` - Remove model
  - `/model check` - Check model availability

## Commands Still in main.py

The following complex command handlers remain in `main.py` for safety and to minimize risk:

### Repomap Commands
- `/repomap create` - Creates repository map using LLM
- `/repomap load` - Loads existing repomap into context
- `/repomap update` - Updates existing repomap

### Datamap Commands  
- `/datamap create` - Creates data file map with PostgreSQL signatures
- `/datamap load` - Loads existing datamap into context
- `/datamap update` - Updates existing datamap

### Code Execution Commands
- `/code <language>` - Executes code in specified language

These commands are complex, involve multi-step LLM interactions, file operations, and intricate logic, so they were intentionally left in place to ensure stability.

## Benefits of Refactoring

1. **Reduced Complexity**: Main file is 24% smaller (614 lines removed)
2. **Better Organization**: Commands are grouped by category
3. **Easier Maintenance**: Changes to specific commands are isolated
4. **Improved Testability**: Individual command handlers can be tested separately
5. **Clearer Structure**: Initialization logic is separated from command handling
6. **Scalability**: New commands can be added to appropriate modules

## Testing

All existing tests should continue to pass as the refactoring maintains the same functionality:

```bash
make test-unit      # Run unit tests
make test           # Run all tests
```

## Future Improvements

Potential future refactoring opportunities:

1. Extract repomap commands to `src/cli/commands/repomap.py`
2. Extract datamap commands to `src/cli/commands/datamap.py`
3. Extract code execution commands to `src/cli/commands/code.py`
4. Extract chat processing logic to `src/cli/chat_loop.py`
5. Create command handler base class for consistent interface
6. Add more comprehensive unit tests for individual handlers

## Migration Guide

For developers working with the codebase:

**Before** (old main.py):
```python
# Everything was in main.py
if user_input_normalized.lower() == 'exit':
    # exit handling code here
    
if user_input_normalized.lower() == 'session start':
    # session start handling code here
```

**After** (refactored):
```python
# Commands delegated to dispatcher
dispatch_result = dispatcher.dispatch(user_input_normalized)
if dispatch_result is None:
    return  # exit
elif dispatch_result is True:
    continue  # handled
```

**Adding New Simple Commands**:

1. Create handler function in appropriate module under `src/cli/commands/`
2. Add dispatch logic to `src/cli/dispatcher.py`
3. Update this documentation

**Adding Complex Commands**:

1. Add directly to main.py's command loop (after dispatcher check)
2. Consider creating a dedicated module if command becomes large
3. Update this documentation
