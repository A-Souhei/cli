# AI CLI Architecture Analysis

## 1. OVERALL ARCHITECTURE & ENTRY POINTS

### Application Flow
```
main.py (Entry Point)
├─> ConfigManager (loads config.yaml)
├─> OllamaClient (connects to Ollama service)
├─> ChatManager (maintains conversation context)
├─> MCPClient (manages Model Context Protocol tools)
└─> Interactive CLI Loop (prompt_toolkit)
    ├─> User Input Handler
    ├─> Ollama Chat Request
    ├─> Response Processing
    ├─> Code Detection & Execution
    └─> Rating & Feedback Loop
```

### Entry Point: main.py (lines 554-818)
- **Primary initialization function**: `main(verbose=False)`
- **Key components initialized**:
  1. ConfigManager - reads YAML configuration
  2. OllamaClient - connects to Ollama LLM service
  3. ChatManager - manages conversation history with context window
  4. MCPClient - manages MCP tool servers
  5. FileHistory - persists command history (~/.ai_cli_history)

### Configuration Loading
- **File**: `src/config/manager.py`
- **Config location**: `config.yaml` in project root
- **Parameters loaded**:
  - Ollama: url, model, timeout
  - Chat: system_prompt, max_context_length, temperature, stream

---

## 2. PROMPT/QUERY HANDLING

### Query Processing Pipeline

```
User Input
    ↓
[Command Check] (exit, clear, models, switch, mcps, mcp-tools)
    ↓
[Guidance Check] (get_prompt_guidance) - searches for similar past prompts
    ↓
[Chat Manager] - adds message to context
    ↓
[System Instructions] - code execution instructions injected
    ↓
[Ollama Service] - sends chat request with context
    ↓
[Response Collection] - streams or collects full response
    ↓
[Code Detection] - looks for python/r code blocks
    ↓
[Code Execution] (optional) - executes detected code via MCP
    ↓
[Rating Prompt] - user rates the response (0-10)
    ↓
[Rating Processing] - stores rating with keywords
```

### Special Commands (main.py, lines 618-693)
- `exit`/`quit` - gracefully shutdown
- `clear` - clear chat history
- `models` - list available Ollama models
- `switch` - change current model (interactive selector)
- `mcps` - list available system MCPs
- `mcp-tools <name>` - list tools in specific MCP

### Prompt Guidance System (main.py, lines 255-296)
- **Function**: `get_prompt_guidance(prompt_text)`
- **Process**:
  1. Retrieves all stored ratings from PostgreSQL
  2. Finds most similar past prompt using embedding similarity
  3. If similarity >= 0.7 threshold:
     - Extract keywords from past response
     - If rating >= 7: suggest incorporating keywords
     - If rating < 7: suggest avoiding those keywords
  4. Injects guidance as system message before LLM call

---

## 3. RAG & SIMILARITY SEARCH LOGIC

### Three-Tier Architecture

#### Tier 1: PostgreSQL Database (src/postgresql/init.sql)
- **Tables**:
  1. `conversation_ratings` - stores prompt/response/rating/keywords
  2. `mcp_tools` - stores tool definitions with embeddings

#### Tier 2: Flask API (src/postgresql/app/app.py)
- **Port**: 15000 (POSTGRES_API_URL)
- **Key Endpoints**:
  - `/ratings/create` - save new rating
  - `/ratings` - get all ratings
  - `/ratings/<id>/update` - update existing rating
  - `/mcp-tools/store` - store tool with embedding
  - `/mcp-tools/match` - find best matching tool

#### Tier 3: Transformer Service (src/transformer/app.py)
- **Port**: 16050 (TRANSFORMER_API_URL)
- **Model**: `all-MiniLM-L6-v2` (sentence-transformers)
- **Key Endpoints**:
  - `/embed?text=<text>` - generate embedding
  - `/similarity?text1=<t1>&text2=<t2>&metric=cosine` - compare similarity
  - `/keywords?text=<text>` - extract keywords
  - `/sentiment?text=<text>` - analyze sentiment
  - `/summarize?text=<text>` - summarize text

### Similarity Search Flow

```
User Prompt
    ↓
[Transformer Service] /keywords
    Extract top 5 keywords from response
    ↓
[Transformer Service] /similarity (for each past prompt)
    Compare using cosine similarity
    ↓
[PostgreSQL API] /mcp-tools/match
    Find similar MCP tool for user input
    ↓
[Decision Logic]
    If similarity >= 0.7:
        → Update if new rating is higher
        → Extract and store keywords
    Else:
        → Create new rating entry
```

### Similarity Metrics (src/transformer/embedding_similarity.py)
- **Cosine Similarity** (default): measures angle between vectors
  - Range: -1 to 1 (typically 0-1 for text embeddings)
  - Most common for text
- **Euclidean Distance**: straight-line distance (lower = more similar)
- **Dot Product**: vector multiplication (highest = most similar)

### Vector Embeddings
- **Model**: Sentence-Transformers `all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Size**: 80MB (lightweight for CPU inference)
- **Stored in**: PostgreSQL JSONB column

---

## 4. CURRENT API STRUCTURE

### Service Architecture
```
┌─────────────────────────────────────┐
│  AI CLI (main.py)                   │
│  - Interactive prompt interface    │
│  - Conversation management         │
│  - Code detection & execution      │
└────────────┬────────────────────────┘
             │
     ┌───────┼──────────┐
     │       │          │
     ▼       ▼          ▼
Ollama   Flask API  Transformer
(11434)  (15000)    Service
                    (16050)
     │       │          │
     └───────┼──────────┘
             │
         ┌───▼────┐
         │Postgres│
         │ (35432)│
         └────────┘
```

### Main API Endpoints

#### Ollama Service
- **URL**: http://localhost:11434 (configurable)
- **Interface**: ollama Python client
- **Endpoint**: `/api/chat` (via client library)

#### PostgreSQL Flask API (src/postgresql/app/app.py)
```
GET  /health                         - Health check
GET  /ratings                        - Get all ratings (with min_rating filter)
GET  /ratings/<id>                   - Get specific rating
GET  /ratings/create                 - Create new rating (GET with params)
PATCH /ratings/<id>/update           - Update rating
GET  /ratings/purge                  - Delete all ratings
POST /mcp-tools/store                - Store tool with embedding
GET  /mcp-tools                      - List all tools
POST /mcp-tools/match                - Find similar tool by text
```

#### Transformer Service (src/transformer/app.py)
```
GET  /health                         - Health check
GET  /embed?text=<text>              - Generate embedding
GET  /embed/batch?texts=<json>       - Batch embeddings
GET  /similarity?text1=<>&text2=<>   - Compare similarity
GET  /keywords?text=<text>           - Extract keywords
GET  /sentiment?text=<text>          - Analyze sentiment
GET  /summarize?text=<text>          - Summarize text
```

---

## 5. COMMAND HANDLING PATTERNS

### MCP (Model Context Protocol) System

#### Structure
```
system_mcps/
└── coder/
    ├── server.py (MCP Server implementation)
    └── README.md

MCPClient (src/mcp/client.py)
├── start_server(mcp_name)     - spawn subprocess
├── get_tools(mcp_name)        - list available tools
├── call_tool(mcp_name, tool_name, arguments) - execute tool
├── detect_code(text)          - find code in response
└── match_tool(text, threshold) - find relevant tool
```

#### MCP Tool Definition (system_mcps/coder/server.py)
**Available Tools**:
1. **run_python_code** - Execute Python in CLI's venv
   - Input: code (string)
   - Returns: {stdout, stderr, exit_code}
   
2. **run_r_code** - Execute R code
   - Input: code (string)
   - Returns: {stdout, stderr, exit_code}
   
3. **detect_code** - Extract code from text
   - Input: text (string)
   - Returns: {language, code} or null

#### Tool Matching Process
1. **Tool Storage** (during startup):
   - MCPClient.initialize_tools_in_db() (line 145)
   - Iterates all system_mcps directories
   - For each tool: store name, description, embedding

2. **Tool Matching** (during conversation):
   - User input sent to PostgreSQL API /mcp-tools/match
   - Compares with all stored tool embeddings
   - Returns best match above threshold (default 0.5)

#### Code Execution Flow (lines 299-410)
```
Response from LLM
    ↓
[detect_code] - regex patterns for ```python/r blocks
    ↓
[Interactive Selector] - ask user for confirmation
    ↓
[call_tool] - send to MCP server via JSON-RPC
    ↓
[display_execution_result] - format and show output
```

### Command Types

#### Direct Commands (main.py, lines 618-693)
- Built-in CLI commands (no MCP needed)
- Handled directly in main loop
- Examples: clear, models, switch

#### Tool Commands (via MCP)
- Detected from code blocks in responses
- Matched against database via embeddings
- Executed through MCPClient.call_tool()

---

## 6. KEY PATTERNS & CONVENTIONS

### Message Context Management
```python
# ChatManager (src/chat/manager.py)
messages = [
    {'role': 'system', 'content': system_prompt},
    {'role': 'user', 'content': '...'},
    {'role': 'assistant', 'content': '...'},
    ...
]
# Auto-trims to max_context_length (default: 10)
# Always preserves system prompt
```

### Rating & Feedback Loop
```
Rating >= 7  → Store as satisfactory
Rating < 7   → Store as unsatisfactory
Keywords     → Extract from response via transformer
Similar?     → Compare with past prompts (threshold: 0.7)
Update/Create → Update if rating higher, else create new
```

### Error Handling
- Centralized via Sentry (optional monitoring)
- API errors caught and logged
- Services fail gracefully (warnings, not crashes)
- JSON-RPC error responses handled

### Async/Concurrency
- Uses `nest_asyncio` for nested event loop support
- MCP communication: async subprocess
- API calls: synchronous via requests
- Timeout handling on all external calls

---

## 7. SESSION MANAGEMENT CONSIDERATIONS

### Current State
- **In-memory**: ChatManager maintains context
- **Persistent**: Ratings stored in PostgreSQL
- **Per-run**: No session concept, continuous mode

### Missing Session Features
1. **Session Identity** - no unique session ID
2. **Session Persistence** - no save/load of chat state
3. **Session Metadata** - no timestamps, user info, tags
4. **Session Queries** - can't filter ratings by session
5. **Session Resumption** - no way to continue old sessions

### Database Schema Ready For Sessions
```sql
-- Could extend conversation_ratings table with:
- session_id (UUID or string)
- user_id (if multi-user support needed)
- conversation_id (group related exchanges)
- timestamp metadata (created_at, updated_at already exists)
```

### Recommended Session Addition Points
1. **Initialize**: Add session_id when ChatManager created
2. **Store**: Include session_id in /ratings/create payload
3. **Query**: Filter by session_id in /ratings endpoint
4. **Resume**: Load previous session chat history
5. **List**: Show available sessions with metadata

---

## 8. DATA FLOW DIAGRAM

```
┌──────────────────────────────────────────────────────────────┐
│                    AI CLI Application                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ConfigManager          ChatManager         MCPClient       │
│  ├─ Load config.yaml   ├─ System prompt    ├─ Start servers│
│  ├─ Ollama URL         ├─ Context window   ├─ Get tools    │
│  └─ Chat params        └─ Message history  └─ Call tools   │
│                                                              │
│         InteractiveSelector                                 │
│         ├─ Model selection                                  │
│         ├─ Code execution confirmation                      │
│         └─ Navigation (arrow keys)                          │
│                                                              │
└──────────────┬─────────────────┬──────────────────┬─────────┘
               │                 │                  │
           Ollama            Transformer        PostgreSQL
          Service           Service              Flask API
         (11434)            (16050)              (15000)
           │                  │                   │
           ├─ /chat          ├─ /embed            ├─ /ratings
           ├─ /models        ├─ /similarity       ├─ /mcp-tools
           └─ /pull          └─ /keywords        └─ /health
                                                   │
                                            PostgreSQL DB
                                            (35432)
                                            ├─ conversation_ratings
                                            └─ mcp_tools
```

