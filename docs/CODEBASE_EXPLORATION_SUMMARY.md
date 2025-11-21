# AI CLI Codebase Architecture & Implementation Guide

## 1. SYSTEM OVERVIEW

### 1.1 Core Architecture
The AI CLI is a multi-service architecture with the following components:

```
┌─────────────────────────────────────────────────────────┐
│                  AI CLI (main.py)                       │
│              Interactive Chat Interface                  │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
    Ollama      PostgreSQL    Transformer
    (11434)     Flask API     Service
              (15000)         (16050)
                │
        ┌───────▼────────┐
        │  PostgreSQL    │
        │  Database      │
        │  (25432)       │
        └────────────────┘
```

### 1.2 Key Service Ports
- **Ollama**: http://localhost:11434 - LLM chat interface
- **PostgreSQL API**: http://localhost:15000 - Tool & rating storage
- **Transformer Service**: http://localhost:16050 - Text embeddings
- **PostgreSQL DB**: localhost:25432 - Data persistence

---

## 2. MCP TOOLS IMPLEMENTATION

### 2.1 How MCP Tools Work

**retrieve_all_tools** and **roll_the_dice** are two special MCP tools that enable intelligent tool discovery and execution:

#### retrieve_all_tools
- **Location**: `/home/user/cli/system_mcps/coder/server.py` (lines 1084-1137)
- **Purpose**: Find relevant MCP tools based on semantic matching
- **Input**: Array of prompts (e.g., ["Run Python code: print('hello')", "Detect code"])
- **Process**:
  1. Validate prompts (non-empty array)
  2. Call PostgreSQL API: `POST /mcp-tools/retrieve`
  3. API generates embeddings for prompts using Transformer Service
  4. Performs cosine similarity matching against stored tool embeddings
  5. Returns results with similarity scores
- **Output Format**:
```json
{
  "status": "success",
  "count": 1,
  "results": [
    {
      "prompt": "Run Python code",
      "prompt_index": 0,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "run_python_code",
        "description": "Execute Python code...",
        "similarity": 0.95
      }
    }
  ]
}
```

#### roll_the_dice
- **Location**: `/home/user/cli/system_mcps/coder/server.py` (lines 1139-1385)
- **Purpose**: Execute multiple tools iteratively based on semantic search
- **Key Requirements**: 
  - **MANDATORY**: `session_id` - required for context persistence
  - Prompts array (required)
  - Optional: `max_tools` (1-10, default 3), `working_dir`
- **Process**:
  1. Validate session_id (fails if missing)
  2. Call retrieve_all_tools internally via PostgreSQL API
  3. Extract unique tools (deduplication by tool_name)
  4. Limit to max_tools
  5. **Iterate through each tool** (this is key - it's NOT optional):
     - Infer parameters based on tool type
     - Call tool recursively via `call_tool()`
     - Collect execution results
  6. Aggregate results and return
- **Output Format**:
```json
{
  "status": "success",
  "message": "Executed 2 tools",
  "session_id": "my-session",
  "prompts": ["Run Python code"],
  "tools_retrieved": 5,
  "tools_attempted": 2,
  "executions": [
    {
      "tool_name": "run_python_code",
      "description": "Execute Python code...",
      "similarity_score": 0.95,
      "status": "executed",
      "result_json": {
        "stdout": "Hello\n",
        "exit_code": 0
      }
    }
  ]
}
```

### 2.2 Other Available Tools

The coder MCP provides these additional tools:

1. **run_python_code** - Execute Python code
2. **run_r_code** - Execute R code
3. **detect_code** - Extract code blocks from text
4. **write_python_code** - Create new Python file
5. **write_r_code** - Create new R file
6. **edit_python_code** - Modify existing Python file
7. **edit_r_code** - Modify existing R file
8. **add_file_context** - Add file to RAG context
9. **add_directory_context** - Add directory to RAG context
10. **verify_file_modifications** - Run modified files for verification

---

## 3. API ENDPOINTS & STRUCTURE

### 3.1 PostgreSQL Flask API (Port 15000)

#### Tool Management Endpoints

**POST /mcp-tools/store** - Store/update MCP tool with embedding
```json
Request:
{
  "mcp_name": "coder",
  "tool_name": "run_python_code",
  "description": "Execute Python code in virtual environment..."
}

Response:
{
  "status": "success",
  "message": "MCP tool stored successfully"
}
```

**GET /mcp-tools** - List all stored MCP tools
```json
Response:
{
  "status": "success",
  "count": 12,
  "tools": [
    {
      "id": 1,
      "mcp_name": "coder",
      "tool_name": "run_python_code",
      "description": "...",
      "created_at": "2025-01-21T..."
    }
  ]
}
```

**POST /mcp-tools/match** - Find best matching tool for single text
```json
Request:
{
  "text": "Run Python code",
  "threshold": 0.5
}

Response:
{
  "status": "success",
  "best_match": {
    "mcp_name": "coder",
    "tool_name": "run_python_code",
    "similarity": 0.87
  },
  "matches": [...]  // All matches above threshold
}
```

**POST /mcp-tools/retrieve** - Recursive retrieval for multiple prompts
```json
Request:
{
  "prompts": ["Run Python code", "Create file"],
  "threshold": 0.5,
  "extract_params": true  // Optional
}

Response:
{
  "status": "success",
  "count": 2,
  "results": [
    {
      "prompt": "Run Python code",
      "prompt_index": 0,
      "best_match": { ... }
    }
  ],
  "metadata": {
    "threshold": 0.5,
    "total_prompts": 2,
    "total_tools_searched": 12
  }
}
```

### 3.2 Transformer Service (Port 16050)

**GET /embed?text=<text>** - Generate single embedding
**GET /embed/batch?texts=<json_array>** - Batch embeddings
**GET /similarity?text1=<>&text2=<>&metric=cosine** - Compare similarity

All return embeddings (384-dimensional vectors using `all-MiniLM-L6-v2`)

### 3.3 Database Schema

**MCPTool table** (src/postgresql/app/app.py, lines 64-74):
```python
class MCPTool(db.Model):
    id = db.Column(Integer, primary_key=True)
    mcp_name = db.Column(Text)        # "coder", "analyzer", etc.
    tool_name = db.Column(Text)       # "run_python_code"
    description = db.Column(Text)     # Full description for embedding
    embedding = db.Column(JSON)       # 384-dimensional vector
    created_at = db.Column(DateTime)
    updated_at = db.Column(DateTime)
```

---

## 4. HOW TOOLS INTERACT WITH THE LLM

### 4.1 Tool Discovery & Suggestion Flow

```
User Prompt
    ↓
[Chat Manager] - Add to context
    ↓
[Ollama Service] - Generate response
    ↓
[Code Detection] - Look for ```python/r blocks
    ↓
[MCPClient.detect_code()] - Extract code
    ↓
[Optional] Ask user to execute code
    ↓
[MCPClient.call_tool()] - Execute via MCP
    ↓
[Display Results]
```

### 4.2 Tool Matching Process

The retrieve_all_tools endpoint implements semantic matching:

1. **Generate embeddings** (Transformer Service):
   - Each prompt → 384-dimensional vector
   - Each tool description → 384-dimensional vector

2. **Calculate similarity** (PostgreSQL API, line 325-337):
```python
def cosine_similarity(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    return dot_product / (magnitude1 * magnitude2)
```

3. **Return best matches** above threshold (default 0.5):
   - Similarity range: 0.0 to 1.0
   - Higher = more relevant

---

## 5. TESTING STRUCTURE

### 5.1 Test Files

**tests/test_coder_mcp.py** - Unit tests for MCP server
- `test_server_exists()` - Verify server.py exists
- `test_initialize()` - Test MCP initialization
- `test_list_tools()` - Verify tool listing
- `test_retrieve_all_tools()` - Test tool retrieval
- `test_roll_the_dice_with_session()` - Test tool execution

**tests/test_mcp_postgres.py** - Integration tests
- `TestMCPToolsStorage` - Tool storage and updates
- `TestMCPToolsRetrieval` - Tool listing
- `TestMCPToolsMatching` - Embedding-based matching
- `TestEmbeddingService` - Transformer service validation

**tests/test_tool_retrieval.py** - Recursive retrieval tests
- `TestRecursiveToolRetrieval` - Full retrieval flow
- Tests single/multiple prompts
- Tests threshold filtering
- Tests parameter extraction

**tests/validate_tool_retrieval.py** - Validation utilities

### 5.2 Running Tests

```bash
# Run all MCP tests
pytest tests/test_coder_mcp.py -v

# Run specific test
pytest tests/test_coder_mcp.py::TestCoderMCP::test_retrieve_all_tools -v

# Run with debug output
MCP_DEBUG=true pytest tests/test_coder_mcp.py -v -s

# Run integration tests
pytest tests/test_mcp_postgres.py -v

# Run retrieval tests
pytest tests/test_tool_retrieval.py -v
```

---

## 6. RETRIEVE_ALL_TOOLS EXPECTED FORMAT

### Input Format
```json
{
  "prompts": [
    "Run Python code: import pandas as pd",
    "Detect code in text",
    "Execute R script"
  ]
}
```

### Output Format
```json
{
  "status": "success",
  "count": 3,
  "results": [
    {
      "prompt": "Run Python code: import pandas as pd",
      "prompt_index": 0,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "run_python_code",
        "description": "Execute Python code in the CLI's virtual environment...",
        "similarity": 0.95,
        "extracted_params": {
          "code": "import pandas as pd"
        }
      }
    },
    {
      "prompt": "Detect code in text",
      "prompt_index": 1,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "detect_code",
        "description": "Detect and extract Python or R code...",
        "similarity": 0.88,
        "extracted_params": {
          "text": "Detect code in text"
        }
      }
    },
    {
      "prompt": "Execute R script",
      "prompt_index": 2,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "run_r_code",
        "description": "Execute R code using the host system's R installation...",
        "similarity": 0.87,
        "extracted_params": {
          "code": ""
        }
      }
    }
  ],
  "metadata": {
    "threshold": 0.5,
    "total_prompts": 3,
    "total_tools_searched": 12
  }
}
```

### Error Handling
```json
{
  "status": "error",
  "message": "No prompts provided"
}
```

---

## 7. ARCHITECTURE & KEY FILES

### 7.1 Critical Files to Modify/Create

1. **MCP Tool Implementation**
   - `/home/user/cli/system_mcps/coder/server.py` (1404 lines)
     - Add new tools in `list_tools()` function
     - Implement tool logic in `call_tool()` handler
     - Lines 358-675: Tool definitions
     - Lines 679-1388: Tool implementations

2. **API Endpoints**
   - `/home/user/cli/src/postgresql/app/app.py` (750 lines)
     - Tool storage: lines 443-498
     - Tool retrieval: lines 572-739
     - Add new endpoints following same pattern

3. **Testing**
   - `/home/user/cli/tests/test_coder_mcp.py` - Add MCP tests
   - `/home/user/cli/tests/test_mcp_postgres.py` - Add API tests
   - `/home/user/cli/tests/test_tool_retrieval.py` - Add retrieval tests

4. **MCP Client**
   - `/home/user/cli/src/mcp/client.py` (356 lines)
     - Tool initialization: lines 145-201
     - Tool calling: lines 279-340

### 7.2 Directory Structure

```
/home/user/cli/
├── main.py                           # Entry point
├── config.yaml                       # Configuration
├── requirements.txt                  # Python dependencies
├── docker-compose.yml                # Service configuration
├── Makefile                          # Build commands
├── README.md                         # Project overview
│
├── system_mcps/
│   └── coder/
│       ├── server.py                 # MCP server implementation
│       ├── requirements.txt
│       └── README.md
│
├── src/
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── client.py                 # MCP client manager
│   ├── postgresql/
│   │   └── app/
│   │       └── app.py                # Flask API (15000)
│   ├── transformer/
│   │   ├── app.py                    # Embeddings service (16050)
│   │   ├── nlp_tasks.py
│   │   └── embedding_similarity.py
│   ├── config/
│   │   └── manager.py
│   ├── ollama_client/
│   │   └── client.py
│   ├── chat/
│   │   └── manager.py
│   ├── session/
│   │   └── manager.py
│   └── utils/
│       └── tree.py
│
└── tests/
    ├── test_coder_mcp.py             # MCP server tests
    ├── test_mcp_postgres.py          # API integration tests
    ├── test_tool_retrieval.py        # Retrieval endpoint tests
    └── validate_tool_retrieval.py    # Validation utilities
```

### 7.3 Database & Service Dependencies

**PostgreSQL Tables**:
- `mcp_tools` - Tool definitions with embeddings
- `conversation_ratings` - User feedback (optional for this feature)

**External Services Required**:
- Ollama (LLM inference)
- PostgreSQL (data storage)
- Transformer Service (embeddings)

---

## 8. DEBUG MODE

Enable verbose logging for MCP tools:

```bash
# Set debug environment variable
export MCP_DEBUG=true

# Run with debug output
MCP_DEBUG=true python main.py

# Check logs during tool execution
MCP_DEBUG=true pytest tests/test_coder_mcp.py -v -s
```

Debug output includes:
- Tool retrieval requests/responses
- Parameter inference details
- Tool execution steps
- Error messages with context

---

## 9. SUMMARY OF MODIFICATIONS NEEDED

To extend the MCP tool system:

1. **Add New Tool**: 
   - Add Tool definition to `list_tools()` in server.py
   - Implement handler in `call_tool()` function
   - Follow existing patterns (validate inputs, handle errors, return JSON)

2. **Add New Endpoint**:
   - Create Flask route in postgresql/app/app.py
   - Include embedding generation if needed
   - Return proper JSON response format

3. **Add Tests**:
   - Create test class in appropriate test file
   - Use pytest fixtures for setup
   - Test both success and error cases

4. **Handle Parameters**:
   - Automatic parameter extraction available in PostgreSQL API
   - Or implement custom extraction in tool handler

---

## 10. KEY PATTERNS & BEST PRACTICES

### 10.1 Tool Handler Pattern
```python
elif name == "new_tool":
    param1 = arguments.get("param1", "")
    param2 = arguments.get("param2", "")
    
    # Validate inputs
    if not param1:
        return [TextContent(type="text", text="Error: Missing param1")]
    
    try:
        # Implement logic
        result = do_something(param1, param2)
        
        # Return as JSON
        return [TextContent(type="text", text=json.dumps({
            "status": "success",
            "result": result
        }, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]
```

### 10.2 API Endpoint Pattern
```python
@app.route('/api/new-endpoint', methods=['POST'])
def new_endpoint():
    try:
        data = request.get_json()
        # Validate and process
        return jsonify({
            'status': 'success',
            'data': result
        }), 200
    except Exception as e:
        return handle_error(e)
```

### 10.3 Test Pattern
```python
@requires_both_services
class TestNewFeature:
    def setup_method(self):
        """Set up before each test."""
        # Initialize test data
        pass
    
    def test_something(self):
        """Test description."""
        response = requests.post(...)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
```

