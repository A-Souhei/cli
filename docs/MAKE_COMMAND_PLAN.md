# Implementation Plan: Make Tool for AI CLI

## Overview
Add a new MCP tool `run_make` and a `.makemap` file system with `/make` commands that follow the existing `/code` pattern.

## User Requirements Summary
- **Execution**: Direct execution (no user confirmation)
- **Map Detail**: Full details (targets, dependencies, variables, recipe summaries)
- **Map Requirement**: Auto-generate .makemap if it doesn't exist

---

## Files Created

### 1. `src/utils/makemap.py`
New module following repomap.py/datamap.py pattern:

```python
# Key functions:
def find_makefile(working_dir: str) -> Optional[Path]
def parse_makefile(makefile_path: str) -> dict
def collect_makefile_targets(working_dir: str) -> dict
def generate_makemap_prompt(parsed_makefile: dict, tree_output: str = None) -> str
def generate_makemap_update_prompt(new_targets: list, existing_makemap: str) -> str
async def load_makemap_to_context(mcp_client, makemap_path, working_dir, session_id=None) -> dict
def get_target_names(parsed_makefile: dict) -> list
def find_target_by_name(parsed_makefile: dict, target_name: str) -> Optional[dict]
def validate_target(parsed_makefile: dict, target_name: str) -> bool
```

### 2. `tests/test_makemap.py`
24 unit tests covering all makemap functions

---

## Files Modified

### 1. `system_mcps/coder/server.py`
- Added `run_make` tool to `@app.list_tools()` (line ~950)
- Added handler in `@app.call_tool()` (line ~1991)
- Tool executes: `subprocess.run(["make", target], cwd=working_dir, timeout=300)`

### 2. `system_mcps/coder/tools.yaml`
- Added `run_make` to `valid_coding` and `execution` categories
- Added `make_execution` category
- Added tool metadata with `executes_command: true` and `no_confirmation: true`

### 3. `main.py`
Added command handlers after /datamap section:
- `/make map generate` - Generate .makemap from Makefile using LLM
- `/make map update` - Update .makemap with new targets only
- `/make map load` - Load .makemap into context
- `/make <prompt>` - Main command:
  1. Auto-generate .makemap if missing
  2. Load .makemap into context
  3. Use spin_the_roulette (POST /mcp-tools/code-command-simple)
  4. Use roll_the_dice pattern for execution
  5. Use coder model
  6. Execute make commands directly

### 4. `src/utils/banner.py`
Added to help output:
```
'/make <prompt>'         - Execute make commands using natural language
'/make map generate'     - Generate .makemap from Makefile
'/make map update'       - Update .makemap with new targets
'/make map load'         - Load .makemap into context
```

### 5. `src/ui/routes/chat.py`
Added handlers for /make commands in Web UI:
- `handle_make_command(prompt)`
- `handle_makemap_generate()`
- `handle_makemap_load()`
- `handle_makemap_update()`

---

## Implementation Order

1. Create `src/utils/makemap.py` with core parsing/generation functions
2. Add `run_make` tool to `system_mcps/coder/server.py`
3. Update `system_mcps/coder/tools.yaml`
4. Add `/make` command handlers to `main.py`
5. Update `src/utils/banner.py` help text
6. Add UI support in `src/ui/routes/chat.py`
7. Create `tests/test_makemap.py`
8. Run tests: `make test-unit`

---

## Key Implementation Details

### Makefile Parsing
Extract from Makefile:
- Target names (e.g., `build`, `test`, `clean`)
- Dependencies (e.g., `build: deps install`)
- Variables (e.g., `MODEL=llama2`)
- Comments as descriptions (## comments and comments above targets)
- Recipe content (indented lines following targets)
- .PHONY declarations

### .makemap Format (Markdown)
```markdown
# Make Map

## Directory Tree

```
<tree output>
```

## Overview
<LLM-generated project build overview>

## Targets

### build
**Dependencies**: deps, install
**Description**: Build the project
**Recipe**: docker compose build...

### test
**Dependencies**: build
**Description**: Run tests
**Recipe**: pytest tests/...

## Variables
- MODEL: Model name (default: llama2)
- PORT: Server port (default: 8080)
```

### /make Command Flow
```
User: /make run the tests
    |
    v
[Check .makemap exists] --> No --> [Auto-generate .makemap]
    |
    v
[Load .makemap to context]
    |
    v
[POST /mcp-tools/code-command-simple] (spin_the_roulette)
    |
    v
[Match steps with run_make tool]
    |
    v
[Execute: subprocess.run(["make", "test"])]
    |
    v
[Return stdout/stderr/exit_code]
```

### run_make Tool Schema
```python
Tool(
    name="run_make",
    description=(
        "Execute a make command in the working directory. This tool runs make targets "
        "from the project's Makefile. It requires a Makefile to exist in the working "
        "directory. Returns stdout, stderr, and exit code of the execution. "
        "Use this for build automation, running tests, starting services, cleaning, etc. "
        "Common targets include: build, test, clean, install, run, setup, deploy."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "The make target to execute (e.g., 'build', 'test', 'clean'). If empty, runs the default target."
            },
            "args": {
                "type": "string",
                "description": "Optional additional arguments to pass to make (e.g., 'MODEL=llama2 VERBOSE=1')"
            },
            "working_dir": {
                "type": "string",
                "description": "Optional working directory. Defaults to current directory."
            }
        },
        "required": []
    }
)
```

---

## Usage Examples

### CLI Usage
```bash
# Generate makemap from Makefile
/make map generate

# Load existing makemap into context
/make map load

# Update makemap with new targets
/make map update

# Execute make commands using natural language
/make run the tests
/make build the project
/make clean up
/make run the unit tests
```

### Web UI Usage
Same commands work in the Web UI chat interface.

---

## Critical File Paths
- `src/utils/makemap.py` - Core makemap module
- `system_mcps/coder/server.py` - MCP tool implementation
- `system_mcps/coder/tools.yaml` - Tool metadata
- `main.py` - CLI command handlers
- `src/utils/banner.py` - Help text
- `src/ui/routes/chat.py` - Web UI handlers
- `tests/test_makemap.py` - Unit tests

---

## Testing

Run makemap tests:
```bash
./venv/bin/pytest tests/test_makemap.py -v
```

Run all unit tests:
```bash
make test-unit
```
