# $ Prefix: Direct MCP Tool Execution

## Overview

The `$` prefix provides a convenient way to directly execute MCP tools with interactive selection menus. This feature makes MCP tools more discoverable and easier to use without needing to remember exact command syntax.

## Usage

```bash
$ <your natural language description>
```

## How It Works

1. **Type `$` followed by your request**
   ```
   $ generate fake data from @users.csv
   ```

2. **Select MCP Server**
   - Interactive dropdown shows all available MCP servers
   - Use arrow keys to navigate
   - Press Enter to select

3. **Select Tool**
   - Interactive dropdown shows all tools from the selected MCP server
   - Meta tools (orchestration tools) are automatically filtered out
   - Use arrow keys to navigate
   - Press Enter to select

4. **Automatic Parameter Extraction**
   - System uses the **coder model** (required) to analyze your prompt
   - Extracts parameters like file paths, sample counts, output paths
   - Shows extracted parameters for review

5. **Tool Execution**
   - Executes the selected tool with extracted parameters
   - Displays results in formatted output

## Features

### Enforced Coder Model
- The `$` prefix **always uses the coder model** for parameter extraction
- Ensures consistent, high-quality parameter parsing
- Falls back to general model with warning if coder model not configured

### Interactive Selection
- No need to remember exact tool names or MCP server names
- Browse available tools with arrow key navigation
- Visual feedback for selected items

### Smart Parameter Extraction
- Automatically detects file paths (especially `@file.ext` patterns)
- Identifies numeric parameters (sample counts, epochs, etc.)
- Extracts output file paths from phrases like "save to", "save in", "output to"
- **Auto-generates output paths** for data generation tools if not specified
- Adds working directory automatically

### Filtered Tool List
- Meta tools (like `execute_plan`, `spin_the_roulette`) are excluded
- Only shows executable tools relevant to user tasks

## Examples

### Example 1: Generate Fake Data (with explicit output)
```
$ generate 100 fake records from @users.csv and save to @fake_users.csv
```

**Flow:**
1. Select MCP: `data-engineer`
2. Select Tool: `generate_fake_data`
3. Parameters extracted:
   ```json
   {
     "file_path": "users.csv",
     "num_samples": 100,
     "output_path": "fake_users.csv",
     "working_dir": "/path/to/working/dir"
   }
   ```
4. Tool executes and saves synthetic data to fake_users.csv

### Example 1b: Generate Fake Data (auto-generated output)
```
$ generate 100 fake records from @users.csv
```

**Flow:**
1. Select MCP: `data-engineer`
2. Select Tool: `generate_fake_data`
3. Parameters extracted:
   ```json
   {
     "file_path": "users.csv",
     "num_samples": 100,
     "output_path": "fake_users.csv",
     "working_dir": "/path/to/working/dir"
   }
   ```
   Note: `output_path` auto-generated as "fake_users.csv"
4. Tool executes and saves synthetic data to auto-generated filename

### Example 2: Compare Code Similarity
```
$ compare similarity between @file1.py and @file2.py
```

**Flow:**
1. Select MCP: `data-engineer`
2. Select Tool: `compare_code_similarity`
3. Parameters extracted:
   ```json
   {
     "file_path1": "file1.py",
     "file_path2": "file2.py",
     "working_dir": "/path/to/working/dir"
   }
   ```
4. Tool executes and shows similarity score

### Example 3: Generate AST
```
$ create abstract syntax tree for @mycode.py
```

**Flow:**
1. Select MCP: `data-engineer`
2. Select Tool: `generate_ast`
3. Parameters extracted:
   ```json
   {
     "file_path": "mycode.py",
     "working_dir": "/path/to/working/dir"
   }
   ```
4. Tool executes and displays AST

### Example 4: Execute Python Code
```
$ run @test_script.py
```

**Flow:**
1. Select MCP: `coder`
2. Select Tool: `run_python_code`
3. Parameters extracted:
   ```json
   {
     "file_path": "test_script.py",
     "working_dir": "/path/to/working/dir"
   }
   ```
4. Tool executes the script

## Comparison with Other Modes

### $ Prefix vs /code Mode

| Feature | `$ prefix` | `/code mode` |
|---------|-----------|--------------|
| Selection | Interactive dropdowns | Automatic tool matching |
| Control | Manual tool selection | LLM decides tool |
| Steps | Single tool execution | Multi-step execution |
| Model | Coder model (enforced) | Coder model (optional) |
| Use Case | Know which tool to use | Complex multi-step tasks |

### $ Prefix vs Normal Chat

| Feature | `$ prefix` | Normal Chat |
|---------|-----------|--------------|
| Tool Access | Direct MCP tool execution | No tool access |
| Output | Tool execution results | LLM-generated text |
| Code | Uses existing tools | May generate custom code |
| Parameters | LLM extracts from prompt | N/A |

## When to Use Each Mode

### Use `$` Prefix When:
- You know which type of task you want (data generation, code analysis, etc.)
- You want to browse available tools
- You want direct control over tool selection
- You want to ensure coder model is used for parameter extraction

### Use `/code` Mode When:
- You have a complex multi-step task
- You want the system to automatically choose the best tools
- You need multiple tools to work together
- You want step-by-step execution with confirmation

### Use Normal Chat When:
- Asking questions
- Getting explanations
- Code review and suggestions
- General conversations
- No tool execution needed

## Available MCP Servers and Tools

### coder MCP
- `run_python_code` - Execute Python code
- `run_r_code` - Execute R code
- `write_python_code` - Create new Python file
- `edit_python_code` - Modify existing Python file
- `write_r_code` - Create new R file
- `edit_r_code` - Modify existing R file
- `add_file_context` - Load file into context
- `add_directory_context` - Load directory into context
- `verify_file_modifications` - Verify code changes
- `run_make` - Execute Makefile targets

### data-engineer MCP
- `generate_fake_data` - WGAN-based synthetic data (fast)
- `generate_fake_data_ddpm` - DDPM-based synthetic data (high quality)
- `generate_ast` - Generate Abstract Syntax Tree
- `compare_code_similarity` - CodeBERT-based code similarity
- `compare_ast_similarity` - AST-based code similarity

## Configuration

### Coder Model Requirement
For best results, configure a coder model:
```
/model coder add http://localhost:11434 codellama
/model coder use <model_id>
```

If no coder model is configured:
- System will use general model with a warning
- Parameter extraction may be less accurate

### Working Directory
- Automatically set to your current working directory
- Can be overridden in extracted parameters

### Output Path Handling (Data Generation Tools)

For data generation tools (`generate_fake_data` and `generate_fake_data_ddpm`):

**Explicit Output Path:**
```
$ generate 100 records from @users.csv and save to @fake_users.csv
```
System extracts: `output_path: "fake_users.csv"`

**Auto-Generated Output Path:**
```
$ generate 100 records from @users.csv
```
System auto-generates: `output_path: "fake_users.csv"` (adds "fake_" prefix)

**Supported Phrases for Output:**
- "save to <filename>"
- "save in <filename>"
- "save it in <filename>"
- "output to <filename>"
- "write to <filename>"

**Auto-Generation Pattern:**
- Input: `users.csv` → Output: `fake_users.csv`
- Input: `data.json` → Output: `fake_data.json`
- Input: `records.parquet` → Output: `fake_records.parquet`

This ensures data generation tools always save results to a file, even if the user doesn't explicitly specify an output path.

## Error Handling

### No MCP Servers Found
```
❌ No MCP servers found
```
**Solution:** Ensure `system_mcps/` directory exists with valid MCP servers

### No Tools Found
```
❌ No tools found in selected MCP
```
**Solution:** Check that the MCP has a `tools.yaml` file with tool definitions

### Tool Execution Failed
```
❌ Tool execution failed: <error>
```
**Solution:** Check extracted parameters and ensure required files exist

### Cancelled Selection
```
Cancelled
```
**User Action:** Press Escape or Ctrl+C during selection to cancel

## Technical Details

### Parameter Extraction Process
1. Construct prompt for coder model with tool name and user request
2. Ask LLM to extract parameters as JSON
3. Parse JSON from LLM response (handles extra text)
4. Add `working_dir` if not present
5. Pass parameters to MCP tool

### Tool Filtering
- Loads tools from `tools.yaml` file
- Iterates through categories
- Excludes tools in `meta` category
- Returns unique list of executable tools

### Result Display
- Attempts to parse result as JSON
- Pretty-prints JSON with indentation
- Falls back to raw text if not JSON

## Keyboard Shortcuts

During dropdown selection:
- `↑` / `↓` - Navigate options
- `Enter` - Select current option
- `Escape` / `Ctrl+C` - Cancel selection

## Tips

1. **Be descriptive** - Include file paths and parameters in your prompt
2. **Use @ prefix** - File paths like `@users.csv` are easier to detect
3. **Check parameters** - Review extracted parameters before execution
4. **Browse tools** - Use `$` to discover available MCP tools
5. **Coder model** - Configure a coder model for better parameter extraction

## Troubleshooting

**Q: Why is my request not working?**
A: Check that:
- You're using the `$` prefix at the start
- Your prompt describes the task clearly
- Required files exist in your working directory
- A coder model is configured

**Q: How do I know which tool to select?**
A: The tool names are descriptive:
- `generate_*` - Creates or generates something
- `compare_*` - Compares two things
- `run_*` - Executes code
- `edit_*` / `write_*` - Modifies or creates files

**Q: Can I skip the dropdowns?**
A: No, the dropdowns ensure you see all available options and make an informed choice. This is by design for discoverability.

**Q: What if parameter extraction is wrong?**
A: Currently, parameters are extracted automatically. A future enhancement could allow manual parameter editing.

## Future Enhancements

Potential improvements:
- Parameter editing before execution
- History of recently used tools
- Favorites/bookmarks for tools
- Parameter templates for common tasks
- Direct tool invocation: `$ mcp:tool params...`
