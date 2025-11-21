# MCP Tools: retrieve_all_tools and roll_the_dice

## Overview

This document describes two powerful MCP (Model Context Protocol) tools that enable intelligent tool discovery and automated execution workflows:

1. **retrieve_all_tools**: Semantic search for MCP tools
2. **roll_the_dice**: Iterative multi-tool execution in session context

Both tools leverage the PostgreSQL tool retrieval endpoint with RAG embeddings for intelligent matching.

---

## Table of Contents

- [retrieve_all_tools](#retrieve_all_tools)
  - [Description](#retrieve_all_tools-description)
  - [Use Cases](#retrieve_all_tools-use-cases)
  - [Parameters](#retrieve_all_tools-parameters)
  - [Response Format](#retrieve_all_tools-response-format)
  - [Example Usage](#retrieve_all_tools-examples)
- [roll_the_dice](#roll_the_dice)
  - [Description](#roll_the_dice-description)
  - [Use Cases](#roll_the_dice-use-cases)
  - [Parameters](#roll_the_dice-parameters)
  - [Response Format](#roll_the_dice-response-format)
  - [Example Usage](#roll_the_dice-examples)
- [Testing](#testing)
- [Debug Mode](#debug-mode)
- [Architecture](#architecture)

---

## retrieve_all_tools

<a name="retrieve_all_tools-description"></a>
### Description

The `retrieve_all_tools` tool queries the PostgreSQL database to find the most relevant MCP tools based on user prompts using semantic similarity matching with transformer embeddings.

**Key Features:**
- ✅ Multiple prompt support (batch queries)
- ✅ RAG-based semantic matching
- ✅ Similarity scoring for each match
- ✅ Cross-MCP tool search
- ✅ Comprehensive tool metadata

<a name="retrieve_all_tools-use-cases"></a>
### Use Cases

1. **Tool Discovery**: Find available tools for specific tasks
2. **Capability Exploration**: Understand what tools can do
3. **Integration Planning**: Identify tools for workflow automation
4. **Dynamic Tool Selection**: Choose tools based on user intent

<a name="retrieve_all_tools-parameters"></a>
### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompts` | array | Yes | List of prompt strings describing desired functionality |

**Example:**
```json
{
  "prompts": [
    "Run Python code: print('hello')",
    "Detect code in text",
    "Execute R script"
  ]
}
```

<a name="retrieve_all_tools-response-format"></a>
### Response Format

```json
{
  "status": "success",
  "count": 3,
  "results": [
    {
      "prompt": "Run Python code: print('hello')",
      "prompt_index": 0,
      "tools": [
        {
          "mcp_name": "coder",
          "tool_name": "run_python_code",
          "description": "Execute Python code in the CLI's virtual environment...",
          "similarity": 0.95
        }
      ]
    }
  ],
  "metadata": {
    "threshold": 0.5,
    "total_prompts": 3,
    "total_tools_searched": 12
  }
}
```

<a name="retrieve_all_tools-examples"></a>
### Example Usage

#### Example 1: Single Prompt

**Input:**
```json
{
  "name": "retrieve_all_tools",
  "arguments": {
    "prompts": ["Run Python code: print('hello world')"]
  }
}
```

**Output:**
```json
{
  "status": "success",
  "results": [
    {
      "prompt": "Run Python code: print('hello world')",
      "tools": [
        {
          "tool_name": "run_python_code",
          "mcp_name": "coder",
          "similarity": 0.93,
          "description": "Execute Python code..."
        }
      ]
    }
  ]
}
```

#### Example 2: Multiple Prompts

**Input:**
```json
{
  "name": "retrieve_all_tools",
  "arguments": {
    "prompts": [
      "Execute Python code",
      "Analyze R data",
      "Find code snippets in text"
    ]
  }
}
```

**Output:**
```json
{
  "status": "success",
  "count": 3,
  "results": [
    {
      "prompt": "Execute Python code",
      "tools": [
        {"tool_name": "run_python_code", "similarity": 0.91},
        {"tool_name": "write_python_code", "similarity": 0.72}
      ]
    },
    {
      "prompt": "Analyze R data",
      "tools": [
        {"tool_name": "run_r_code", "similarity": 0.88}
      ]
    },
    {
      "prompt": "Find code snippets in text",
      "tools": [
        {"tool_name": "detect_code", "similarity": 0.85}
      ]
    }
  ]
}
```

#### Example 3: Error Handling

**Input (empty prompts):**
```json
{
  "name": "retrieve_all_tools",
  "arguments": {
    "prompts": []
  }
}
```

**Output:**
```text
Error: No prompts provided
```

#### Example 4: Using curl

```bash
# Via MCP (through main CLI)
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": [
      "Run Python code: import pandas",
      "Create a new Python file"
    ]
  }'
```

---

## roll_the_dice

<a name="roll_the_dice-description"></a>
### Description

The `roll_the_dice` tool executes multiple MCP tools iteratively based on semantic search results within a session context. It first retrieves relevant tools, then automatically executes each one with inferred parameters.

**Key Features:**
- ✅ **Mandatory iteration** through all retrieved tools
- ✅ Session-based context management (required)
- ✅ Automatic parameter inference
- ✅ Configurable max_tools limit (1-10)
- ✅ Aggregated execution results
- ✅ Comprehensive error handling per tool

<a name="roll_the_dice-use-cases"></a>
### Use Cases

1. **Exploratory Testing**: Try multiple tools to see what works
2. **Multi-Step Workflows**: Execute sequences of related tools
3. **Parameter Discovery**: Learn tool capabilities through execution
4. **Batch Operations**: Run similar tools with slight variations

<a name="roll_the_dice-parameters"></a>
### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompts` | array | Yes | - | List of prompt strings |
| `session_id` | string | **Yes** | - | Session ID for context (mandatory) |
| `max_tools` | integer | No | 3 | Max tools to execute (capped at 10) |
| `working_dir` | string | No | CWD | Working directory for executions |

**Example:**
```json
{
  "prompts": ["Run Python code: print('test')"],
  "session_id": "my-session-123",
  "max_tools": 2
}
```

<a name="roll_the_dice-response-format"></a>
### Response Format

```json
{
  "status": "success",
  "message": "Executed 2 tools",
  "session_id": "my-session-123",
  "prompts": ["Run Python code"],
  "tools_retrieved": 5,
  "tools_attempted": 2,
  "executions": [
    {
      "tool_name": "run_python_code",
      "description": "Execute Python code...",
      "similarity_score": 0.95,
      "status": "executed",
      "result": "{\"stdout\": \"test\\n\", \"exit_code\": 0}",
      "result_json": {
        "stdout": "test\n",
        "stderr": "",
        "exit_code": 0
      }
    },
    {
      "tool_name": "detect_code",
      "description": "Detect and extract code...",
      "similarity_score": 0.82,
      "status": "executed",
      "result": "null"
    }
  ]
}
```

<a name="roll_the_dice-examples"></a>
### Example Usage

#### Example 1: Basic Usage with Session

**Input:**
```json
{
  "name": "roll_the_dice",
  "arguments": {
    "prompts": ["Run Python code: print('Hello from roll_the_dice!')"],
    "session_id": "test-session-001",
    "max_tools": 2
  }
}
```

**Output:**
```json
{
  "status": "success",
  "message": "Executed 1 tools",
  "session_id": "test-session-001",
  "prompts": ["Run Python code: print('Hello from roll_the_dice!')"],
  "tools_retrieved": 3,
  "tools_attempted": 2,
  "executions": [
    {
      "tool_name": "run_python_code",
      "status": "executed",
      "similarity_score": 0.94,
      "result_json": {
        "stdout": "Hello from roll_the_dice!\n",
        "exit_code": 0
      }
    },
    {
      "tool_name": "detect_code",
      "status": "executed",
      "result": "null"
    }
  ]
}
```

#### Example 2: Multiple Prompts

**Input:**
```json
{
  "name": "roll_the_dice",
  "arguments": {
    "prompts": [
      "Run Python code: import sys; print(sys.version)",
      "Detect code in this text",
      "Execute R script"
    ],
    "session_id": "multi-prompt-session",
    "max_tools": 3
  }
}
```

**Output:**
```json
{
  "status": "success",
  "message": "Executed 3 tools",
  "session_id": "multi-prompt-session",
  "tools_retrieved": 8,
  "tools_attempted": 3,
  "executions": [
    {
      "tool_name": "run_python_code",
      "status": "executed",
      "similarity_score": 0.96
    },
    {
      "tool_name": "detect_code",
      "status": "executed",
      "similarity_score": 0.88
    },
    {
      "tool_name": "run_r_code",
      "status": "executed",
      "similarity_score": 0.85
    }
  ]
}
```

#### Example 3: Error - Missing session_id

**Input:**
```json
{
  "name": "roll_the_dice",
  "arguments": {
    "prompts": ["Run code"]
  }
}
```

**Output:**
```json
{
  "status": "error",
  "message": "session_id is required. This tool only works within a session."
}
```

#### Example 4: With Code Extraction

**Input:**
```json
{
  "name": "roll_the_dice",
  "arguments": {
    "prompts": [
      "```python\nimport pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\nprint(df)\n```"
    ],
    "session_id": "code-extract-session",
    "max_tools": 1
  }
}
```

**Output:**
```json
{
  "status": "success",
  "executions": [
    {
      "tool_name": "run_python_code",
      "status": "executed",
      "result_json": {
        "stdout": "   a\n0  1\n1  2\n2  3\n",
        "exit_code": 0
      }
    }
  ]
}
```

#### Example 5: Max Tools Limit

**Input:**
```json
{
  "name": "roll_the_dice",
  "arguments": {
    "prompts": ["Run any code"],
    "session_id": "limit-test",
    "max_tools": 1
  }
}
```

**Output:**
```json
{
  "status": "success",
  "tools_attempted": 1,
  "executions": [
    {
      "tool_name": "run_python_code",
      "status": "executed"
    }
  ]
}
```

---

## Testing

### Running Tests

```bash
# Run all coder MCP tests (includes new tools)
pytest tests/test_coder_mcp.py -v

# Run specific test
pytest tests/test_coder_mcp.py::TestCoderMCP::test_retrieve_all_tools -v
pytest tests/test_coder_mcp.py::TestCoderMCP::test_roll_the_dice_with_session -v

# Run with debug output
MCP_DEBUG=true pytest tests/test_coder_mcp.py -v -s
```

### Test Cases

#### retrieve_all_tools Tests:
1. ✅ Single prompt
2. ✅ Multiple prompts
3. ✅ Empty prompts (error handling)
4. ✅ Connection error handling

#### roll_the_dice Tests:
1. ✅ With valid session_id
2. ✅ Without session_id (should fail)
3. ✅ Multiple prompts
4. ✅ Max tools limit enforcement
5. ✅ Code extraction from prompts

### Manual Testing

#### Test retrieve_all_tools:

```bash
# Start the CLI in test mode
python3 -m pytest tests/test_coder_mcp.py::TestCoderMCP::test_retrieve_all_tools -v -s

# Or test the endpoint directly
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{"prompts": ["Run Python code"]}'
```

#### Test roll_the_dice:

```bash
# With debug mode enabled
MCP_DEBUG=true python3 -m pytest \
  tests/test_coder_mcp.py::TestCoderMCP::test_roll_the_dice_with_session -v -s
```

---

## Debug Mode

Enable verbose debug logging by setting the `MCP_DEBUG` environment variable:

```bash
# Enable debug mode
export MCP_DEBUG=true

# Run MCP server with debug output
python3 system_mcps/coder/server.py

# Run tests with debug output
MCP_DEBUG=true pytest tests/test_coder_mcp.py -v -s
```

### Debug Output Examples

#### retrieve_all_tools Debug Output:
```
[DEBUG] retrieve_all_tools called
[DEBUG] Args: {
  "prompts": ["Run Python code"]
}
[DEBUG] retrieve_all_tools: Using PostgreSQL API at http://localhost:15000
[DEBUG] retrieve_all_tools: Sending request to http://localhost:15000/mcp-tools/retrieve
[DEBUG] retrieve_all_tools: Received response with status code 200
[DEBUG] retrieve_all_tools: Successfully retrieved 3 results
```

#### roll_the_dice Debug Output:
```
[DEBUG] roll_the_dice called
[DEBUG] Args: {
  "prompts": ["Run Python code"],
  "session_id": "test-123",
  "max_tools": 2
}
[DEBUG] roll_the_dice: max_tools set to 2
[DEBUG] roll_the_dice: Using PostgreSQL API at http://localhost:15000
[DEBUG] roll_the_dice: Step 1 - Retrieving tools for 1 prompts
[DEBUG] roll_the_dice: Received response with status 200
[DEBUG] roll_the_dice: Found 5 total tools
[DEBUG] roll_the_dice: 3 unique tools after deduplication
[DEBUG] roll_the_dice: Will attempt to execute 2 tools
[DEBUG] roll_the_dice: Step 3 - Executing tools iteratively
[DEBUG] roll_the_dice: Iteration 1/2
[DEBUG] roll_the_dice: Executing tool 'run_python_code' (similarity: 0.95)
[DEBUG] roll_the_dice: Inferring parameters for run_python_code
[DEBUG] roll_the_dice: Calling run_python_code with arguments
[DEBUG] Args: {
  "code": "print('Hello from roll_the_dice!')",
  "working_dir": "/home/user/cli"
}
[DEBUG] roll_the_dice: Tool run_python_code executed successfully
[DEBUG] roll_the_dice: Iteration 2/2
[DEBUG] roll_the_dice: Executing tool 'detect_code' (similarity: 0.82)
[DEBUG] roll_the_dice: Tool detect_code executed successfully
[DEBUG] roll_the_dice: Step 4 - Completed. Executed 2/2 tools
```

---

## Architecture

### retrieve_all_tools Flow

```
User Request (MCP Tool Call)
    ↓
[validate prompts]
    ↓
[PostgreSQL API] /mcp-tools/retrieve
    ↓
[Transformer Service] → Generate embeddings
    ↓
[Similarity Matching] → Compare with stored tools
    ↓
[Results] → Return matched tools with scores
```

### roll_the_dice Flow

```
User Request (MCP Tool Call)
    ↓
[validate session_id + prompts]
    ↓
[Step 1: Retrieve Tools]
    ↓
[PostgreSQL API] /mcp-tools/retrieve
    ↓
[Step 2: Extract & Deduplicate]
    ↓
[unique tools] → Limit to max_tools
    ↓
[Step 3: ITERATE THROUGH EACH TOOL]
    ├─> Tool 1: Infer params → Execute → Collect result
    ├─> Tool 2: Infer params → Execute → Collect result
    └─> Tool N: Infer params → Execute → Collect result
    ↓
[Step 4: Aggregate Results]
    ↓
Return: {status, session_id, executions[]}
```

### Component Interaction

```
┌──────────────────────────────────────────────┐
│  Coder MCP Server                            │
│  (system_mcps/coder/server.py)               │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ retrieve_all_tools                     │ │
│  │ - Semantic tool search                 │ │
│  │ - Returns: tool metadata + scores     │ │
│  └─────────────┬──────────────────────────┘ │
│                │                              │
│  ┌─────────────▼──────────────────────────┐ │
│  │ roll_the_dice                          │ │
│  │ - Uses retrieve_all_tools              │ │
│  │ - ITERATES through each tool           │ │
│  │ - Requires session_id                  │ │
│  │ - Returns: execution results           │ │
│  └────────────────────────────────────────┘ │
└──────────────────┬───────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │ PostgreSQL API     │
         │ /mcp-tools/retrieve│
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │ Transformer Service│
         │ (Embeddings)       │
         └────────────────────┘
```

---

## Error Handling

### Common Errors

#### 1. retrieve_all_tools

| Error | Cause | Solution |
|-------|-------|----------|
| "No prompts provided" | Empty prompts array | Provide at least one prompt |
| "prompts must be an array" | Invalid type | Pass array of strings |
| Connection error | PostgreSQL API down | Start the API service |
| Timeout | API taking >30s | Check API health |

#### 2. roll_the_dice

| Error | Cause | Solution |
|-------|-------|----------|
| "session_id is required" | Missing session_id | Provide session_id parameter |
| "No prompts provided" | Empty prompts array | Provide at least one prompt |
| "Invalid working directory" | Bad working_dir | Use valid directory path |
| Tool execution failure | Individual tool error | Check execution details in result |

---

## Best Practices

### retrieve_all_tools

1. **Descriptive Prompts**: Use clear, specific descriptions
   - ✅ Good: "Run Python code: import pandas"
   - ❌ Bad: "code"

2. **Batch Queries**: Group related prompts for efficiency
   ```json
   {
     "prompts": [
       "Execute Python script",
       "Run R analysis",
       "Detect code snippets"
     ]
   }
   ```

3. **Error Handling**: Always check response status
   ```python
   result = call_tool("retrieve_all_tools", {"prompts": [...]})
   if result.get("status") == "error":
       handle_error(result["message"])
   ```

### roll_the_dice

1. **Always Provide session_id**: Tool requires session context
   ```json
   {
     "session_id": "unique-session-id",
     "prompts": [...]
   }
   ```

2. **Limit Tool Count**: Use `max_tools` to control execution time
   ```json
   {
     "max_tools": 2,  // Only execute top 2 matched tools
     "session_id": "...",
     "prompts": [...]
   }
   ```

3. **Check Execution Status**: Review individual tool results
   ```python
   for execution in result["executions"]:
       if execution["status"] == "failed":
           print(f"Tool {execution['tool_name']} failed: {execution['error']}")
   ```

4. **Code Extraction**: Include code in prompts for automatic execution
   ```json
   {
     "prompts": [
       "```python\nprint('Hello')\n```"
     ],
     "session_id": "..."
   }
   ```

---

## Performance Considerations

### retrieve_all_tools

- **Latency**: ~200-500ms per request
- **Batch Size**: Optimal 1-10 prompts
- **Timeout**: 30 seconds
- **Concurrent Requests**: Supported

### roll_the_dice

- **Latency**: Depends on tools executed
  - Tool retrieval: ~200-500ms
  - Each tool execution: ~100ms-5s
  - Total: (retrieval time) + (tool_count × avg_tool_time)
- **Max Tools**: Limited to 10 per request
- **Timeout**: 30s per API call
- **Session**: Maintains context across calls

---

## Related Documentation

- [Tool Retrieval API](TOOL_RETRIEVAL_API.md)
- [Tool Retrieval Feature](TOOL_RETRIEVAL_FEATURE.md)
- [Session Integration Guide](SESSION_INTEGRATION_GUIDE.md)
- [Architecture Overview](ARCHITECTURE.md)

---

## Support

For issues or questions:
1. Check debug logs: `MCP_DEBUG=true`
2. Review test cases: `tests/test_coder_mcp.py`
3. Verify API health: `curl http://localhost:15000/health`

---

**Last Updated**: 2025-01-21
**Version**: 1.0.0
