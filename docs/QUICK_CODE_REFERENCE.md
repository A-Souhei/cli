# Quick Code Reference Guide

## File Locations & Line Numbers

### 1. MCP Tool Definitions (system_mcps/coder/server.py)

| Tool | Definition Lines | Implementation Lines |
|------|-----------------|---------------------|
| list_tools() | 358-675 | - |
| call_tool() | 679 | - |
| run_python_code | 682-719 | - |
| run_r_code | 721-767 | - |
| detect_code | 769-785 | - |
| write_python_code | 787-814 | - |
| write_r_code | 816-843 | - |
| edit_python_code | 845-872 | - |
| edit_r_code | 874-901 | - |
| add_file_context | 903-934 | - |
| add_directory_context | 936-997 | - |
| verify_file_modifications | 999-1082 | - |
| **retrieve_all_tools** | **1084-1137** | **Lines 1084-1137** |
| **roll_the_dice** | **1139-1385** | **Lines 1139-1385** |

### 2. PostgreSQL API Endpoints (src/postgresql/app/app.py)

| Endpoint | Method | Lines | Purpose |
|----------|--------|-------|---------|
| /health | GET | 77-80 | Health check |
| /ratings | GET | 128-153 | List all ratings |
| /ratings/<id> | GET | 156-175 | Get specific rating |
| /mcp-tools/store | POST | 443-498 | Store tool with embedding |
| /mcp-tools | GET | 501-519 | List all tools |
| /mcp-tools/match | POST | 522-569 | Single text matching |
| **/mcp-tools/retrieve** | **POST** | **572-739** | **Recursive multi-prompt retrieval** |

**Key Functions**:
- `get_embedding()` - Line 293-306
- `get_batch_embeddings()` - Line 309-322
- `cosine_similarity()` - Line 325-337
- `extract_parameters_from_text()` - Line 340-440

### 3. MCP Client (src/mcp/client.py)

| Function | Lines | Purpose |
|----------|-------|---------|
| __init__() | 14-29 | Initialize client |
| start_server() | 40-95 | Start MCP server process |
| get_tools() | 97-143 | List tools from MCP |
| initialize_tools_in_db() | 145-201 | Store tools in database |
| detect_code() | 203-238 | Extract code from text |
| match_tool() | 240-277 | Match text against tools |
| call_tool() | 279-340 | Execute tool |
| cleanup() | 342-355 | Stop servers |

### 4. Database Schema (src/postgresql/app/app.py)

**MCPTool Model** (Lines 64-74):
```python
class MCPTool(db.Model):
    id = Column(Integer, primary_key=True)
    mcp_name = Column(Text)           # MCP name (e.g., "coder")
    tool_name = Column(Text)          # Tool name (e.g., "run_python_code")
    description = Column(Text)        # Tool description (for embedding)
    embedding = Column(JSON)          # 384-dimensional embedding vector
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

---

## Critical Code Patterns

### Pattern 1: Tool Definition
Location: `system_mcps/coder/server.py`, line ~362

```python
Tool(
    name="tool_name",
    description="What this tool does...",
    inputSchema={
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param1"]
    }
)
```

### Pattern 2: Tool Handler
Location: `system_mcps/coder/server.py`, line ~682

```python
elif name == "tool_name":
    param1 = arguments.get("param1", "")
    
    if not param1:
        return [TextContent(type="text", text="Error: Missing param1")]
    
    try:
        # Implementation
        result = do_something(param1)
        return [TextContent(type="text", text=json.dumps({
            "status": "success",
            "data": result
        }, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]
```

### Pattern 3: Async Tool Execution
Location: `system_mcps/coder/server.py`, line ~1331

```python
result = await call_tool(tool_name, tool_arguments)

if result and len(result) > 0:
    result_text = result[0].text
    execution_result["status"] = "executed"
    execution_result["result"] = result_text
    try:
        execution_result["result_json"] = json.loads(result_text)
    except Exception:
        pass
```

### Pattern 4: Flask API Endpoint
Location: `src/postgresql/app/app.py`, line ~443

```python
@app.route('/mcp-tools/store', methods=['POST'])
def store_mcp_tool():
    try:
        data = request.get_json()
        
        # Validate inputs
        if not all([mcp_name, tool_name, description]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
        
        # Get embedding
        embedding = get_embedding(description)
        
        # Store in database
        tool = MCPTool(
            mcp_name=mcp_name,
            tool_name=tool_name,
            description=description,
            embedding=embedding
        )
        db.session.add(tool)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Tool stored successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        return handle_error(e)
```

### Pattern 5: Cosine Similarity
Location: `src/postgresql/app/app.py`, line ~325

```python
def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)
```

### Pattern 6: Testing with Fixtures
Location: `tests/test_coder_mcp.py`, line ~52

```python
@pytest.mark.asyncio
async def test_something(server_path):
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0.0"}
            }
        }
    ]
    
    responses = await communicate_with_mcp(server_path, requests)
    assert len(responses) == 1
```

---

## Important Constants & Configurations

### Service URLs (main.py, lines 88-92)
```python
POSTGRES_API_URL = "http://localhost:15000"
TRANSFORMER_API_URL = "http://localhost:16050"
SIMILARITY_THRESHOLD = 0.7  # For prompt similarity
SATISFACTORY_RATING_THRESHOLD = 7  # For rating classification
```

### Embedding Model (src/transformer/app.py, line 36)
- **Model Name**: `all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Size**: ~80MB
- **Type**: Sentence Transformers

### Tool Limits (system_mcps/coder/server.py, lines 1170-1174)
```python
# roll_the_dice max_tools constraints
if max_tools < 1:
    max_tools = 1
elif max_tools > 10:
    max_tools = 10
```

---

## Retrieve Endpoint Response Parsing

The `/mcp-tools/retrieve` endpoint returns a specific format:

```python
{
    "status": "success",
    "count": <number of prompts processed>,
    "results": [
        {
            "prompt": "<original prompt>",
            "prompt_index": <0-based index>,
            "best_match": {
                "mcp_name": "<mcp name>",
                "tool_name": "<tool name>",
                "description": "<tool description>",
                "similarity": <0.0-1.0>,
                "extracted_params": {
                    # Parameter extraction (optional)
                }
            }
        }
    ],
    "metadata": {
        "threshold": <similarity threshold>,
        "total_prompts": <number of prompts>,
        "total_tools_searched": <number of tools in database>
    }
}
```

**Important**: The response has ONE `best_match` per prompt, not multiple results.

---

## Roll the Dice Execution Flow

```python
# Input validation (lines 1147-1185)
if not session_id:
    return error("session_id is required")
if not prompts or not isinstance(prompts, list):
    return error("prompts must be non-empty array")
if max_tools < 1 or max_tools > 10:
    adjust max_tools

# Step 1: Retrieve tools (lines 1192-1209)
response = requests.post(
    f"{postgres_api_url}/mcp-tools/retrieve",
    json={"prompts": prompts},
    timeout=30
)

# Step 2: Extract tools (lines 1212-1240)
all_tools = []
for result in response["results"]:
    if result.get("best_match"):
        all_tools.append(result["best_match"])

# Remove duplicates and limit to max_tools
unique_tools = list(dict.fromkeys([t["tool_name"] for t in all_tools]))[:max_tools]

# Step 3: Execute each tool (lines 1251-1354)
for tool_info in tools_to_execute:
    # Infer parameters
    if tool_name == "run_python_code":
        # Extract code from prompts
        tool_arguments = {"code": code, "working_dir": working_dir}
    elif tool_name == "run_r_code":
        tool_arguments = {"code": code, "working_dir": working_dir}
    elif tool_name == "detect_code":
        tool_arguments = {"text": prompts[0]}
    
    # Execute recursively
    result = await call_tool(tool_name, tool_arguments)
    
    # Collect result
    execution_result = {
        "tool_name": tool_name,
        "status": "executed",
        "result": result_text
    }
    executions.append(execution_result)

# Step 4: Return aggregated results (lines 1356-1369)
return {
    "status": "success",
    "executions": executions,
    "tools_attempted": len(tools_to_execute)
}
```

---

## Environment Variables

**MCP_DEBUG** - Enable debug mode
```bash
export MCP_DEBUG=true
```

**API URLs** (from environment):
```bash
POSTGRES_API_URL=http://localhost:15000
TRANSFORMER_API_URL=http://localhost:16050
REDIS_API_URL=http://localhost:17000
```

**Database** (docker-compose.yml):
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=vuhitra
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

---

## Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "No prompts provided" | Empty prompts array | Ensure `prompts` is non-empty |
| "session_id is required" | Missing session_id in roll_the_dice | Always provide session_id |
| "Failed to generate embedding" | Transformer service down | Start: `make up-transformer` |
| "No tools found in database" | No tools stored | Run: `mcp_client.initialize_tools_in_db()` |
| ConnectionError to PostgreSQL | Service not running | Start: `make up-postgres` |
| Timeout (30s) | API taking too long | Check service health, increase timeout |

---

## Quick Testing Commands

```bash
# Test MCP server
pytest tests/test_coder_mcp.py -v

# Test API endpoints
pytest tests/test_mcp_postgres.py -v

# Test tool retrieval
pytest tests/test_tool_retrieval.py -v

# Test with debug output
MCP_DEBUG=true pytest tests/test_coder_mcp.py::TestCoderMCP::test_retrieve_all_tools -v -s

# Run health checks
curl http://localhost:15000/health
curl http://localhost:16050/health

# Test retrieve endpoint directly
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{"prompts": ["Run Python code"]}'
```

---

## Implementation Checklist

When adding a new tool:

- [ ] Add tool definition to `list_tools()` (system_mcps/coder/server.py)
- [ ] Add handler to `call_tool()` function
- [ ] Validate all input parameters
- [ ] Return JSON response with status
- [ ] Handle errors gracefully
- [ ] Add unit tests (tests/test_coder_mcp.py)
- [ ] Test with `retrieve_all_tools` (tool must be stored first)
- [ ] Test with `roll_the_dice` if executable
- [ ] Update tool description in database (via /mcp-tools/store)
- [ ] Document in README.md or docs

