# /code Command - Unified Code Task Execution

## Overview

The `/code` command is a powerful unified interface that combines the three major coder MCP tools to analyze, match, and execute complex coding tasks automatically. It orchestrates the complete workflow from text analysis to tool execution.

## What It Does

The `/code` command chains together:

1. **spin_the_roulette** (Text-to-Sequence)
   - Breaks down your prompt into individual instruction steps
   - Uses AI to intelligently split complex tasks

2. **retrieve_all_tools** (Tool Matching)
   - Matches each instruction step with the best available MCP tool
   - Uses semantic similarity to find the most appropriate tool

3. **roll_the_dice** (Tool Execution)
   - Executes the matched tools in sequence
   - Provides real-time feedback on execution status

## Usage

### Basic Syntax

```
/code <prompt_sentences>
```

### Prerequisites

The `/code` command requires a session (needed by `roll_the_dice` for context persistence).

**Auto-Session**: If no session is active, `/code` will automatically start one for you.

You can also manually start a session:
```
/session start
```

### Example Usage

```bash
# Execute a complex coding task (session will auto-start if needed)
/code create a python script that reads data from users.csv, filters active users, and generates a bar chart showing user distribution by country

# The command will:
# 1. Analyze your prompt
# 2. Break it into steps:
#    - Read CSV file
#    - Filter data
#    - Generate visualization
# 3. Match appropriate tools for each step
# 4. Execute the tools automatically
```

### More Examples

```bash
# Data analysis task
/code load the sales data, calculate monthly totals, and create a line plot of the trends

# Code generation and execution
/code write a function to validate email addresses and test it with sample inputs

# Multi-file project
/code create a flask API with endpoints for user CRUD operations and add basic authentication
```

## Command Flow

```
┌─────────────────────────────────────────────────────────┐
│ User: /code <prompt>                                    │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│ Step 1: Text-to-Sequence Analysis                      │
│ - Calls /mcp-tools/code-command endpoint                │
│ - Breaks prompt into instruction steps                  │
│ - Uses LLM (Ollama) for intelligent parsing             │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: Tool Matching                                   │
│ - Matches each step with best MCP tool                  │
│ - Uses semantic similarity (embeddings)                 │
│ - Returns similarity scores                             │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: Tool Execution                                  │
│ - Calls roll_the_dice MCP tool                         │
│ - Executes up to max_tools (default: 5)                │
│ - Provides execution results and status                 │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│ Output: Execution Results                               │
│ - Shows instruction sequence                            │
│ - Displays matched tools                                │
│ - Presents execution output                             │
└─────────────────────────────────────────────────────────┘
```

## API Endpoint

The `/code` command uses the `/mcp-tools/code-command` endpoint internally.

### Endpoint Details

**URL**: `POST http://localhost:15000/mcp-tools/code-command`

**Request Body**:
```json
{
  "text": "Your complex coding task description...",
  "session_id": "session-123",
  "model": "tinyllama",        // optional
  "max_iterations": 3,          // optional
  "max_tools": 5                // optional
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Successfully processed text into N steps and matched with M tools",
  "sequence": [
    "instruction step 1",
    "instruction step 2",
    "..."
  ],
  "tools_matched": [
    {
      "step": "instruction text",
      "step_index": 0,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "run_python_code",
        "description": "Execute Python code...",
        "similarity": 0.87
      }
    }
  ],
  "execution_ready": {
    "prompts": ["step 1", "step 2"],
    "session_id": "session-123",
    "max_tools": 5
  },
  "metadata": {
    "text_analysis": {...},
    "tool_retrieval": {...},
    "total_steps": 3,
    "total_tools_matched": 3,
    "model_used": "tinyllama",
    "max_tools": 5
  }
}
```

## Configuration

### Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `max_tools` | 5 | 1-10 | Maximum number of tools to execute |
| `model` | tinyllama | Any Ollama model | LLM model for text analysis |
| `max_iterations` | 3 | 1-5 | Max iterations for instruction subdivision |

### Environment Variables

The endpoint uses these services:
- `POSTGRES_API_URL`: Default `http://localhost:15000`
- `OLLAMA_API_URL`: Default `http://localhost:11434`
- `TRANSFORMER_API_URL`: Default `http://localhost:16050`

## Output Format

The `/code` command provides rich, formatted output:

```
🎯 Processing code command...
Prompt: create a python script that reads data...

📝 Step 1/2: Analyzing prompt and matching tools...
✓ Found 3 instruction steps
✓ Matched 3 tools

📋 Instruction Sequence:
  1. Read data from CSV file
  2. Process and filter the data
  3. Generate visualization

🔧 Matched Tools:
  • run_python_code (similarity: 0.92)
  • add_file_context (similarity: 0.78)
  • detect_code (similarity: 0.65)

⚡ Step 2/2: Executing tools...

✓ Execution Complete
  • Tools executed: 2

▶ 1. run_python_code
Output:
[execution output here]
Exit Code: 0

⏭  2. add_file_context (skipped)
```

## Error Handling

### Common Errors

1. **No Active Session**
   ```
   ⚠️  The /code command requires an active session.
   Start a session with: session start
   ```

2. **Empty Prompt**
   ```
   ❌ Usage: /code <prompt_sentences>
   Example: /code create a python script that reads a CSV...
   ```

3. **Network Timeout**
   ```
   ❌ Request timeout - the command took too long to process
   ```

4. **Endpoint Error**
   ```
   ❌ Failed to process code command: HTTP 500
   ```

## Best Practices

1. **Start a Session First**
   - Always use `session start` before `/code`
   - Sessions provide context for tool execution

2. **Be Specific**
   - Clear, detailed prompts get better results
   - Example: "create a python script to..." rather than "make a script"

3. **Complex Tasks**
   - The command handles multi-step tasks automatically
   - No need to break down tasks manually

4. **Review the Sequence**
   - Check the instruction sequence shown
   - Verify it matches your intent

5. **Monitor Execution**
   - Watch execution status for each tool
   - Check exit codes and output

## Comparison with Individual Tools

### Using Individual Tools
```bash
# Manual approach - requires multiple steps
spin_the_roulette --text "your prompt"
# ... analyze output ...
retrieve_all_tools --prompts ["step1", "step2"]
# ... check matches ...
roll_the_dice --prompts ["step1", "step2"] --session-id xyz
```

### Using /code Command
```bash
# Unified approach - single command
/code your prompt here
```

## Technical Details

### Architecture

The `/code` command consists of:

1. **Command Handler** (`main.py:948-1086`)
   - Parses user input
   - Manages session validation
   - Orchestrates API calls
   - Formats output

2. **API Endpoint** (`src/postgresql/app/app.py:1032-1264`)
   - Chains internal endpoints
   - Handles text-to-sequence conversion
   - Manages tool retrieval
   - Prepares execution parameters

3. **MCP Integration**
   - Calls `roll_the_dice` MCP tool for execution
   - Uses session context for state management
   - Provides working directory context

### Performance

- **Text Analysis**: ~5-15 seconds (depends on LLM model)
- **Tool Matching**: ~2-5 seconds (depends on number of steps)
- **Tool Execution**: Varies by tools (seconds to minutes)
- **Total**: Typically 10-30 seconds for simple tasks

### Limitations

1. **Session Required**: Must have an active session
2. **Max Tools**: Limited to 10 tools per execution
3. **Text Length**: Prompts limited to 50,000 characters
4. **Network Dependent**: Requires all services running
5. **LLM Performance**: Analysis quality depends on model

## Troubleshooting

### Command Not Recognized
- Ensure you're using `/code` with a leading slash
- Check that the command is in the latest version

### No Tools Matched
- Your prompt may be too vague
- Try being more specific about what you want
- Ensure MCP tools are initialized in the database

### Execution Failures
- Check that required services are running:
  - PostgreSQL API (port 15000)
  - Ollama (port 11434)
  - Transformer service (port 16050)
- Verify session is active with `session info`

### Timeout Issues
- Large prompts may take longer to process
- Complex tasks may need more time
- Check service logs for bottlenecks

## Related Commands

- `session start` - Start a new session
- `session end` - End current session
- `session info` - View session details
- `mcps` - List available MCP servers
- `mcp-tools coder` - View coder MCP tools

## See Also

- [MCP Tools Documentation](./MCP_TOOLS_RETRIEVE_AND_ROLL_THE_DICE.md)
- [Spin the Roulette Documentation](./spin_the_roulette.md)
- [Session Management](./DOCUMENTATION.md)
