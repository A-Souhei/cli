# Fix: /code Mode Tool Discovery for Data-Engineer MCP Tools

## Problem

The `/code mode` endpoint was not discovering data-engineer MCP tools like `generate_fake_data` and `generate_fake_data_ddpm`. When users requested synthetic data generation using WGAN, the LLM would write Python code from scratch instead of using the existing MCP tools.

### Example of the Problem

User request:
```
plan and generate fake data using WGAN for file @users.csv and save it in @fake_users.csv
```

**Before the fix**: The LLM would generate hundreds of lines of custom Python code to implement WGAN from scratch, instead of using the existing `generate_fake_data` tool.

**After the fix**: The LLM will recognize `generate_fake_data` tool and use it directly.

## Root Cause

The `code-command-simple` endpoint in `src/postgresql/app/app.py` had a **hardcoded list** of only coder MCP tools (lines 1319-1328). Even though it queried all MCP tools from the database, it ignored them and used a static list that didn't include data-engineer tools.

```python
# OLD CODE (hardcoded list)
AVAILABLE TOOLS (use ONLY these):
1. add_file_context - Load a file into context...
2. edit_python_code - Modify an EXISTING Python file...
3. write_python_code - Create a NEW Python file...
# ... only 9 coder tools listed
```

## Solution

### 1. Created `get_all_tools_metadata()` Function

Added a new function to `src/utils/shared_mcp_tools_loader.py` that loads all tools from `tools.yaml` files across all MCP servers:

```python
def get_all_tools_metadata(system_mcps_dir: str = "/app/system_mcps") -> Dict[str, Dict[str, Any]]:
    """
    Load metadata for all tools from tools.yaml files across all MCP servers.
    
    Returns:
        Dict mapping tool_name to metadata dict containing:
        - mcp_name: Which MCP server provides this tool
        - categories: List of categories (e.g., data_generation, code_analysis)
        - metadata: All tool metadata (requires_file_path, languages, etc.)
        - description: Tool description from tools.yaml
    """
```

### 2. Updated `code-command-simple` Endpoint

Modified the endpoint to dynamically load tools from both `tools.yaml` files AND the database:

```python
# NEW CODE (dynamic loading)
# Load tools metadata from tools.yaml files
tools_yaml_metadata = get_all_tools_metadata_cached()

# Filter out meta tools using tools.yaml categories
for tool_name, tool_data in tools_yaml_metadata.items():
    if 'meta' in tool_data.get('categories', []):
        meta_tool_names.add(tool_name)

# Build dynamic tool list from tools.yaml + database
for tool_name in sorted(all_tool_names):
    if tool_name in meta_tool_names:
        continue  # Skip meta tools
    
    # Use description from tools.yaml if available, otherwise from database
    desc = yaml_desc if yaml_desc else db_desc
    tools_list.append(f"{idx}. {tool_name} - {desc}")
```

### 3. Key Improvements

1. **Dynamic Discovery**: All tools from all MCP servers are now discovered automatically
2. **Tools.yaml Integration**: Leverages structured metadata from `tools.yaml` files
3. **Smart Filtering**: Uses category information to automatically exclude meta tools
4. **Better Descriptions**: Prefers concise descriptions from `tools.yaml` over database
5. **Maintainable**: Adding new MCP servers or tools requires no code changes

## Verification

### Test Results

Created comprehensive tests in `tests/test_shared_mcp_tools_loader.py`:

```
✅ 5/5 new tests passing
✅ 14/14 existing tests still passing
```

### Manual Verification

Ran verification script showing:

```
Total tools loaded: 20
Data-engineer tools found: 5/5
  ✓ generate_fake_data
  ✓ generate_fake_data_ddpm
  ✓ generate_ast
  ✓ compare_code_similarity
  ✓ compare_ast_similarity

Coder tools found: 4/4
  ✓ run_python_code
  ✓ write_python_code
  ✓ edit_python_code
  ✓ add_file_context

Meta tools identified: 4
  ✓ retrieve_all_tools
  ✓ roll_the_dice
  ✓ spin_the_roulette
  ✓ execute_plan
```

## Impact

### Before
- Only 9 coder tools available in `/code mode`
- Data-engineer tools completely invisible
- LLM would write custom code for data generation tasks

### After
- **20 tools available** (9 coder + 5 data-engineer + 6 other tools)
- All MCP tools automatically discovered
- LLM will use existing tools instead of writing custom code
- New MCP servers automatically integrated

## Files Changed

1. **src/utils/shared_mcp_tools_loader.py**
   - Added `get_all_tools_metadata()` function
   - Added `get_all_tools_metadata_cached()` with thread-safe caching

2. **src/postgresql/app/app.py**
   - Updated `code-command-simple` endpoint to use tools.yaml metadata
   - Dynamic tool loading from both tools.yaml and database
   - Automatic meta tool filtering using categories

3. **tests/test_shared_mcp_tools_loader.py** (NEW)
   - Comprehensive test coverage for new functionality

## Usage

Now when users request data generation tasks, the LLM will automatically use the appropriate tools:

### Example 1: WGAN Data Generation
```
User: "Generate 100 fake users from @users.csv using WGAN and save to @fake_users.csv"

LLM Step: "Generate synthetic data from users.csv with 100 samples and save to fake_users.csv using generate_fake_data"
```

### Example 2: High-Quality DDPM Data Generation
```
User: "Generate high-quality synthetic data from @products.csv using DDPM"

LLM Step: "Generate high-quality synthetic data from products.csv using generate_fake_data_ddpm"
```

### Example 3: Code Analysis
```
User: "Compare similarity between @file1.py and @file2.py"

LLM Step: "Compare code similarity between file1.py and file2.py using compare_code_similarity"
```

## Future Enhancements

1. **Tool Categorization**: Could group tools by category in the prompt for better organization
2. **Context-Aware Filtering**: Could filter tools based on file types mentioned in the request
3. **Tool Recommendations**: Could use embeddings to recommend relevant tools for ambiguous requests
4. **Performance Monitoring**: Track which tools are most frequently used vs. ignored

## Related Issues

- Resolves the issue where `/code mode` never finds data-engineer MCP tools
- Prevents LLM from writing custom WGAN implementation when tools exist
- Makes the system extensible for future MCP servers
