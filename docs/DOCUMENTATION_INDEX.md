# AI CLI Documentation Index

This index helps you navigate the complete codebase documentation created during the architecture exploration.

## Documentation Files

### 1. **ARCHITECTURE.md** (14 KB, ~350 lines)
Comprehensive technical documentation covering:
- Overall architecture and entry points
- Prompt/query handling pipeline
- RAG & similarity search logic (3-tier architecture)
- Current API structure and endpoints
- Command handling patterns (MCP system)
- Key patterns and conventions
- Session management considerations
- Complete data flow diagrams

**Start here if you want**: A complete technical overview of how the system works.

### 2. **QUICK_REFERENCE.md** (9 KB, ~312 lines)
Quick lookup guide organized by purpose:
- File structure by functionality
- Key functions with line numbers
- API endpoint mapping
- Database table schemas
- Configuration points
- Important data structures
- Common workflows
- Debugging tips
- Performance considerations

**Start here if you want**: To find specific code locations or understand how to accomplish a task.

### 3. **SESSION_INTEGRATION_GUIDE.md** (10 KB, ~389 lines)
Detailed guide for implementing session management:
- Where sessions fit in current architecture
- 8 specific integration points with code examples
- Database schema changes needed
- Implementation phases with time estimates
- Minimal viable implementation (5 files to change)
- Testing strategies
- Future enhancement ideas

**Start here if you want**: To understand how to add session management to the CLI.

### 4. **README.md** (existing file)
Original project documentation:
- Project overview
- Quick start instructions
- Installation options
- Usage guide
- Configuration options
- Troubleshooting

**Start here if you want**: To set up and run the project.

### 5. **QUICKSTART.md** (existing file)
Quick start guide with minimal setup steps.

---

## Key Discoveries

### Architecture Summary
```
User Input (main.py)
    ↓
ChatManager (context)
    ↓
Ollama Service (LLM) → Response
    ↓
PostgreSQL API (ratings DB + embeddings)
    ↓
Transformer Service (embeddings/similarity)
    ↓
Output + Code Execution (MCP)
```

### Entry Points
- **Main CLI**: `/home/user/cli/main.py` (lines 554-818)
- **Config**: `/home/user/cli/src/config/manager.py`
- **Chat Context**: `/home/user/cli/src/chat/manager.py`
- **MCP Tools**: `/home/user/cli/system_mcps/coder/server.py`
- **PostgreSQL API**: `/home/user/cli/src/postgresql/app/app.py`
- **Transformer Service**: `/home/user/cli/src/transformer/app.py`

### How Queries Are Handled
1. User input received via prompt_toolkit
2. Special commands checked (exit, models, switch, etc.)
3. Prompt guidance searched via embedding similarity
4. Message added to ChatManager context
5. System instructions injected (code execution info)
6. Ollama service called with full conversation
7. Response streamed or collected
8. Code detected and optionally executed
9. User rates response (0-10)
10. Rating processed and stored with keywords

### RAG/Similarity Logic
- **Database**: PostgreSQL stores conversation_ratings + mcp_tools tables
- **Embeddings**: Sentence-Transformers `all-MiniLM-L6-v2` (384-dim vectors)
- **Metrics**: Cosine similarity (threshold: 0.7)
- **Keywords**: Extracted using KeyBERT
- **Guidance**: If similar prompt found, inject context about past results

### API Services
- **Ollama (11434)**: LLM inference via official client
- **PostgreSQL API (15000)**: Flask endpoints for ratings & tools
- **Transformer (16050)**: NLP tasks (embed, similarity, keywords)
- **PostgreSQL (25432)**: Persistent data storage

### Command Patterns
- **Direct commands**: exit, clear, models, switch, mcps, mcp-tools
- **Code detection**: Regex patterns for ```python and ```r blocks
- **Tool matching**: Embedding-based search against stored tool descriptions
- **Execution**: Via MCP (Model Context Protocol) subprocess

---

## Where to Find Things

### I want to...
| Goal | File | Lines |
|------|------|-------|
| Understand the whole system | ARCHITECTURE.md | Section 1-8 |
| Find a specific function | QUICK_REFERENCE.md | "Key Functions by Task" |
| Find a specific endpoint | QUICK_REFERENCE.md | "API Endpoint Mapping" |
| Implement sessions | SESSION_INTEGRATION_GUIDE.md | "Integration Points" |
| Debug an issue | QUICK_REFERENCE.md | "Debugging Tips" |
| Modify configuration | QUICK_REFERENCE.md | "Configuration Points" |
| Add a new MCP tool | QUICK_REFERENCE.md | "Add Custom MCP Tool" |
| Optimize performance | QUICK_REFERENCE.md | "Performance Considerations" |
| Trace a rating storage | QUICK_REFERENCE.md | "Trace a Rating" |
| Set up the project | README.md or QUICKSTART.md | All sections |

---

## Critical Code Paths

### User Query Processing
```
main.py:613 (prompt input)
  → 618 (command check)
  → 700 (get_prompt_guidance)
  → 703 (chat_manager.add_user_message)
  → 735-747 (ollama_client.chat)
  → 750 (display response)
  → 753 (chat_manager.add_assistant_message)
```

### Rating & Similarity Search
```
main.py:218 (process_rating)
  → 226 (get_all_ratings from PostgreSQL)
  → 229 (extract_keywords via Transformer)
  → 232 (find_similar_prompt)
  → 210 (check_similarity via Transformer)
  → 235-252 (update or create rating)
```

### Code Execution
```
main.py:299 (handle_code_execution)
  → 311 (mcp_client.detect_code)
  → 336 (InteractiveSelector for confirmation)
  → 354 (mcp_client.call_tool)
  → 363 (display_execution_result)
```

---

## Database Schema

### conversation_ratings
Stores user feedback and past interactions:
- `id`: Unique identifier
- `user_rating`: 0-10 score
- `prompt_text`: Original question
- `response_text`: LLM's answer
- `tags`: JSON with keywords
- `created_at`, `updated_at`: Timestamps

### mcp_tools
Stores available tools with embeddings:
- `id`: Unique identifier
- `mcp_name`: Tool namespace (e.g., "coder")
- `tool_name`: Function name (e.g., "run_python_code")
- `description`: Tool documentation
- `embedding`: 384-dimensional vector
- `created_at`, `updated_at`: Timestamps

---

## Configuration Layers

1. **config.yaml** - User-modifiable settings
2. **Environment variables** - Docker-compose secrets
3. **Hard-coded constants** - main.py (lines 85-88)
4. **Service defaults** - each service has its own defaults

---

## Services & Ports

| Service | Port | Language | Purpose |
|---------|------|----------|---------|
| Ollama | 11434 | Go | LLM inference |
| PostgreSQL | 25432 | SQL | Data persistence |
| Flask API | 15000 | Python | Rating & tool storage |
| Transformer | 16050 | Python | Embeddings & NLP |
| CLI | stdin/stdout | Python | Interactive interface |

---

## Key Technologies

- **LLM**: Ollama (local inference)
- **Embeddings**: Sentence-Transformers (all-MiniLM-L6-v2)
- **Database**: PostgreSQL with JSONB
- **API Framework**: Flask
- **CLI Framework**: prompt_toolkit + rich
- **Tool Framework**: Model Context Protocol (MCP)
- **Async**: asyncio with nest_asyncio

---

## Recommended Reading Order

1. **First 5 mins**: README.md - Get oriented
2. **Next 15 mins**: ARCHITECTURE.md sections 1-4 - Understand the system
3. **Next 10 mins**: QUICK_REFERENCE.md - See where things are
4. **As needed**: ARCHITECTURE.md sections 5-8 - Deep dive
5. **For sessions**: SESSION_INTEGRATION_GUIDE.md - Implementation details

---

## Statistics

- **Total Python files**: ~15
- **Main codebase**: main.py (819 lines)
- **API services**: 2 (Flask + Transformer)
- **MCP tools**: 3 (run_python_code, run_r_code, detect_code)
- **Database tables**: 2 (conversation_ratings, mcp_tools)
- **API endpoints**: ~15 total
- **Documentation**: ~1600 lines across 3 new files

---

## Next Steps

Based on your exploration goal, here are recommendations:

### If implementing sessions:
1. Read SESSION_INTEGRATION_GUIDE.md completely
2. Choose between full implementation or MVP
3. Follow the phase breakdown
4. Reference QUICK_REFERENCE.md for specific endpoints

### If extending the system:
1. Understand MCP pattern (ARCHITECTURE.md section 5)
2. Create new tool in system_mcps/<name>/
3. Tool auto-registers via initialize_tools_in_db()

### If modifying behavior:
1. Check QUICK_REFERENCE.md for configuration points
2. Many behaviors tunable via config.yaml
3. Core logic in main.py (query loop) and src/postgresql/app.py (API)

### If debugging:
1. Enable verbose mode: `python main.py -v`
2. Check service health endpoints
3. Inspect PostgreSQL tables directly
4. Follow code paths in QUICK_REFERENCE.md

---

## Document Maintenance

These documents were generated on 2024-11-20 by analyzing:
- Source code: /home/user/cli (main branch)
- Docker configuration: docker-compose.yml
- Database schema: src/postgresql/init.sql
- API implementations: src/postgresql/app/app.py, src/transformer/app.py

To keep current, update these docs when:
- Core functions in main.py change significantly
- New API endpoints are added
- Database schema changes
- New MCP tools are added
- Configuration options change

