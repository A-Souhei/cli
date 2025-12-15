# /code Mode vs Normal Chat Mode

## Understanding the Difference

### Normal Chat Mode
- Direct conversation with the LLM
- LLM has no knowledge of available MCP tools
- Generates code from scratch for tasks
- Good for: Questions, discussions, general code help

**Example:**
```
User: generate fake data using WGAN for @users.csv
LLM: [Generates 100+ lines of custom WGAN Python code]
```

### /code Mode  
- Structured tool execution mode
- System provides LLM with list of all available MCP tools
- LLM breaks request into steps and matches tools
- Executes MCP tools directly instead of generating code
- Good for: Data engineering, code execution, file operations

**Example:**
```
User: /code generate fake data using WGAN for @users.csv
System: 
  Step 1: Generate synthetic data from users.csv using generate_fake_data
  [Executes generate_fake_data MCP tool]
  Result: Created fake_users.csv with 100 synthetic records
```

## When to Use Each Mode

### Use Normal Chat for:
- Asking questions
- Getting explanations
- Discussing architecture
- Code review and suggestions
- General conversations

### Use /code Mode for:
- Generating fake/synthetic data (WGAN, DDPM)
- Code analysis (AST, similarity)
- File operations (create, modify, execute)
- Data engineering tasks
- Running Python/R code
- Complex multi-step coding tasks

## Available MCP Tools in /code Mode

### Coder Tools
- `run_python_code` - Execute Python code
- `run_r_code` - Execute R code  
- `write_python_code` - Create new Python file
- `write_r_code` - Create new R file
- `edit_python_code` - Modify existing Python file
- `edit_r_code` - Modify existing R file
- `add_file_context` - Load file into context
- `add_directory_context` - Load directory into context
- `verify_file_modifications` - Verify code changes
- `run_make` - Execute Makefile targets

### Data-Engineer Tools
- `generate_fake_data` - Fast synthetic data with WGAN
- `generate_fake_data_ddpm` - High-quality synthetic data with DDPM
- `generate_ast` - Generate Abstract Syntax Tree
- `compare_code_similarity` - Compare code using CodeBERT
- `compare_ast_similarity` - Compare code using AST analysis

## Auto-Suggestion Feature (New in commit a78ad29)

The system now detects data engineering keywords and suggests using `/code`:

**Detected Keywords:**
- generate fake data, synthetic data, wgan, ddpm
- generate data, fake data, mock data, test data generation
- ast analysis, code similarity, compare code

**What You'll See:**
```
💡 Tip: For data engineering tasks, use /code command for better results:
   /code [your request]
   This will use specialized MCP tools instead of generating code from scratch.
```

## How the Fix Works

### Original Problem
The `/code mode` endpoint had a hardcoded list of only 9 coder tools, completely missing the 5 data-engineer tools.

### The Fix
1. **Dynamic Tool Loading** - Load tools from `tools.yaml` files across all MCP servers
2. **Category-Based Filtering** - Use tool categories to filter out meta tools automatically
3. **Combined Sources** - Merge descriptions from both `tools.yaml` and database
4. **Auto-Suggestion** - Suggest `/code` when data engineering keywords are detected

### Result
- **Before:** 9 tools available in `/code mode`
- **After:** 20+ tools available in `/code mode` (all MCP servers)

## Examples

### Example 1: Synthetic Data Generation

**Wrong Approach (Normal Chat):**
```
User: plan and generate fake data using WGAN for file @users.csv
```
Result: LLM generates 100+ lines of custom TensorFlow code

**Correct Approach (/code Mode):**
```
User: /code generate fake data using WGAN for file @users.csv and save to @fake_users.csv
```
Result: System uses `generate_fake_data` tool, creates file in seconds

### Example 2: Code Similarity

**Wrong Approach (Normal Chat):**
```
User: compare similarity between @file1.py and @file2.py
```
Result: LLM suggests approaches or generates comparison code

**Correct Approach (/code Mode):**
```
User: /code compare similarity between @file1.py and @file2.py
```
Result: System uses `compare_code_similarity` tool with CodeBERT embeddings

### Example 3: AST Analysis

**Wrong Approach (Normal Chat):**
```
User: generate AST from @mycode.py
```
Result: LLM explains AST or generates parsing code

**Correct Approach (/code Mode):**
```
User: /code generate AST from @mycode.py
```
Result: System uses `generate_ast` tool, returns full AST structure

## Best Practices

1. **Use `/code` for Actions** - Whenever you want something executed or created, use `/code`
2. **Use Chat for Questions** - When you want to understand or discuss, use normal chat
3. **Start with /context add** - Load relevant files with `/context add @file` before using `/code`
4. **Check Available Tools** - The system will show all available tools when you use `/code`
5. **Trust the Suggestions** - If the system suggests using `/code`, follow the advice

## Technical Details

### Tool Discovery Process
1. Load `tools.yaml` from each MCP server directory
2. Extract tool categories and metadata
3. Filter out tools in `meta` category (orchestration tools)
4. Combine with database descriptions
5. Present full tool list to LLM in `/code mode`

### Files Involved
- `src/utils/shared_mcp_tools_loader.py` - Tool metadata loading
- `src/postgresql/app/app.py` - `/code` endpoint implementation
- `system_mcps/*/tools.yaml` - Tool definitions for each MCP server
- `main.py` - Auto-suggestion logic

## Troubleshooting

**Q: Why isn't the data-engineer tool being used?**  
A: Make sure you're using `/code` prefix, not regular chat

**Q: Can I use tools in normal chat mode?**  
A: No, tools are only available in `/code mode`. Use the `/code` prefix.

**Q: How do I know which tools are available?**  
A: Use `/code mode` and the system will show you all available tools

**Q: Why does normal chat generate code instead of using tools?**  
A: Normal chat mode doesn't have access to MCP tools by design. It's optimized for conversation, while `/code` is optimized for execution.

## Summary

- **Normal Chat** = Conversation with LLM (no tool access)
- **/code Mode** = Structured execution with MCP tools (20+ tools)
- **Use /code** for data engineering, file operations, and code execution
- **System now helps** by suggesting `/code` when appropriate keywords detected
