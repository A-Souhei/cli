# Quick Reference: /execute @file Shortcut

## Feature
Execute TODO_LIST or MAKE_LIST plans directly from files using the `@` prefix.

## Syntax
```bash
/execute @<path/to/file>
```

## Examples

### Common Usage
```bash
# Execute from working directory
/execute @.todo_list
/execute @.make_list

# Execute from relative path
/execute @plans/deployment.md
/execute @docs/tasks.md

# Execute from absolute path
/execute @/home/user/projects/myapp/plan.md

# Execute from parent directory
/execute @../shared/tasks.md
```

## File Format

### TODO_LIST Format
```markdown
# TODO_LIST

1. First task - Regular task using LLM
2. Install packages [Tool: install_packages]
3. Run tests [Make: make test]
4. Another regular task
```

### MAKE_LIST Format
```markdown
# MAKE_LIST

1. Clean build [Make: make clean]
2. Compile code [Make: make build]
3. Deploy to staging [Tool: deploy_staging]
```

## Supported Bullet Styles
- `1. Task description` (numbered)
- `- Task description` (dash)
- `* Task description` (asterisk)
- `• Task description` (bullet)

## Step Execution Types

### 1. LLM Steps (No tool reference)
```markdown
1. Review the code and suggest improvements
```
→ Executes using configured LLM (Ollama or Claude)

### 2. Make Commands
```markdown
1. Run tests [Make: make test]
```
→ Executes `make test` command

### 3. MCP Tools
```markdown
1. Analyze code [Tool: analyze_code]
```
→ Calls MCP tool via coder server

## Auto-Detection
Plan type is detected from:
1. File content (presence of "TODO_LIST" or "MAKE_LIST" header)
2. Filename (contains "todo" → TODO_LIST, "make" → MAKE_LIST)
3. Default: TODO_LIST

## Test Files Created

### Test Suites
- `tests/test_execute_command.py` - Unit tests (20 tests)
- `tests/test_execute_fixtures.py` - Integration tests (9 tests)

### Fixtures
- `tests/fixtures/sample_todo_list.md` - Comprehensive example
- `tests/fixtures/sample_make_list.md` - Build workflow example
- `tests/fixtures/.todo_list` - Simple dotfile
- `tests/fixtures/.make_list` - Simple make dotfile

## Test Coverage
✅ All 29 tests passing
- File path handling (relative, absolute, dotfiles)
- @ prefix stripping
- Plan type detection
- Step parsing (multiple bullet styles)
- Tool reference parsing ([Tool:...], [Make:...])
- Error handling (missing files, failed commands)
- Integration with session management

## Benefits
- 📁 Execute plans from organized file structure
- 🔄 Reusable plans across sessions
- 📝 Version-controlled plans (git)
- 🤝 Easy sharing with team members
- ⚡ Quick execution without manual loading

## Comparison with Legacy Commands

### Old Way
```bash
# Must load first, then execute
/context load TODO_LIST
/execute TODO_LIST
```

### New Way
```bash
# Direct execution
/execute @.todo_list
```

Both methods still work! The `@` prefix is a convenient shortcut.
