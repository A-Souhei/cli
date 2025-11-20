# AI CLI - Quick Reference Guide

## File Structure by Purpose

### Core CLI Entry Points
- `/home/user/cli/main.py` - Main application entry (554-818 lines)
  - Query processing loop (lines 610-800)
  - Command handling (lines 619-693)
  - Rating/feedback (lines 765-782)
  - Code execution (lines 757-763)

### Configuration & State Management
- `/home/user/cli/src/config/manager.py` - Config loader
- `/home/user/cli/src/chat/manager.py` - Conversation context (lines 6-88)
- `/home/user/cli/src/selector.py` - Interactive selection UI

### External Service Clients
- `/home/user/cli/src/ollama_client/client.py` - Ollama LLM API client
- `/home/user/cli/src/mcp/client.py` - MCP server management (12-356 lines)

### API Services
- `/home/user/cli/src/postgresql/app/app.py` - Flask API for ratings & tool storage (21-459)
- `/home/user/cli/src/transformer/app.py` - NLP service for embeddings (21-386)

### NLP Utilities
- `/home/user/cli/src/transformer/embedding_similarity.py` - Similarity metrics
- `/home/user/cli/src/transformer/nlp_tasks.py` - Sentiment, summary, keywords

### MCP Tools
- `/home/user/cli/system_mcps/coder/server.py` - Code execution tools

### Database
- `/home/user/cli/src/postgresql/init.sql` - Schema (conversation_ratings, mcp_tools)

---

## Key Functions by Task

### When User Types a Query
```python
main.py:
  613 → prompt()                          # Get user input
  618 → [Command check]                   # Check if special command
  700 → get_prompt_guidance()             # Find similar past responses
  703 → chat_manager.add_user_message()   # Add to context
  706 → chat_manager.get_messages()       # Get full conversation
  735 → ollama_client.chat()              # Send to LLM (stream or full)
  750 → CustomMarkdown()                  # Display response
  753 → chat_manager.add_assistant_message() # Store in context
```

### When Response Contains Code
```python
main.py:
  299 → handle_code_execution()           # Main handler
  311 → mcp_client.detect_code()          # Find code blocks (regex)
  336 → InteractiveSelector()             # Ask for confirmation
  354 → mcp_client.call_tool()            # Execute via MCP
  363 → display_execution_result()        # Show output
```

### When User Rates a Response
```python
main.py:
  218 → process_rating()                  # Main handler
  226 → get_all_ratings()                 # Fetch from DB
  229 → extract_keywords()                # Get keywords from response
  232 → find_similar_prompt()             # Find similar past prompt
  235-252 → [Update or create]            # Store/update in DB
```

### When System Searches for Similar Prompts
```python
main.py:
  255 → get_prompt_guidance()             # Main function
  262 → get_all_ratings()                 # Get all past ratings
  268 → find_similar_prompt()             # Find best match
  210 → check_similarity()                # Call transformer service
```

### When CLI Starts
```python
main.py:
  554 → main()                            # Entry point
  561 → ConfigManager()                   # Load config.yaml
  564 → OllamaClient()                    # Connect to Ollama
  571 → ChatManager()                     # Initialize context
  578 → MCPClient()                       # Set up MCP manager
  590 → mcp_client.initialize_tools_in_db() # Store all tool definitions
```

---

## API Endpoint Mapping

### Transformer Service (http://localhost:16050)
```
Endpoint           | Purpose                    | Called From
/embed             | Generate embedding vector  | postgresql/app.py:get_embedding()
/similarity        | Compare two texts          | main.py:check_similarity()
/keywords          | Extract keywords           | main.py:extract_keywords()
```

### PostgreSQL Flask API (http://localhost:15000)
```
Endpoint              | Purpose                    | Called From
/ratings/create       | Save new rating           | main.py:create_rating()
/ratings              | Get all ratings           | main.py:get_all_ratings()
/ratings/<id>/update  | Update existing rating    | main.py:update_rating()
/mcp-tools/store      | Store tool with embedding | mcp/client.py:initialize_tools_in_db()
/mcp-tools/match      | Find similar tool         | mcp/client.py:match_tool()
```

---

## Database Tables

### conversation_ratings
```
id               INTEGER PRIMARY KEY
user_rating      INTEGER (0-10)
prompt_text      TEXT
response_text    TEXT
tags             JSONB (e.g., {"keywords": ["python", "loops"]})
created_at       TIMESTAMP
updated_at       TIMESTAMP
```

### mcp_tools
```
id               INTEGER PRIMARY KEY
mcp_name         TEXT (e.g., "coder")
tool_name        TEXT (e.g., "run_python_code")
description      TEXT
embedding        JSONB (384-dimensional vector)
created_at       TIMESTAMP
updated_at       TIMESTAMP
UNIQUE(mcp_name, tool_name)
```

---

## Configuration Points

### config.yaml
```yaml
ollama:
  url: "http://192.168.31.23:11434"
  model: "llama3.1:8b"
  timeout: 120

chat:
  system_prompt: "You are a helpful AI assistant."
  max_context_length: 10
  temperature: 0.7
  stream: true
```

### Environment Variables (docker-compose)
```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=vuhitra
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
OLLAMA_HOST=0.0.0.0
TRANSFORMER_API_URL=http://localhost:16050
```

### Hard-coded Constants (main.py)
```python
POSTGRES_API_URL = "http://localhost:15000"           # Line 85
TRANSFORMER_API_URL = "http://localhost:16050"        # Line 86
SIMILARITY_THRESHOLD = 0.7                            # Line 87
SATISFACTORY_RATING_THRESHOLD = 7                     # Line 88
```

---

## Important Data Structures

### Message Format (used throughout)
```python
{
  'role': 'system|user|assistant',
  'content': 'The actual text'
}
```

### Rating Entry (conversation_ratings table)
```python
{
  'id': 1,
  'user_rating': 8,
  'prompt_text': 'How do I sort a Python list?',
  'response_text': 'You can use the sort() method...',
  'tags': {'keywords': ['python', 'sorting', 'list']},
  'created_at': '2024-11-20T10:30:00'
}
```

### Tool Match Response (/mcp-tools/match)
```python
{
  'status': 'success',
  'count': 1,
  'matches': [
    {
      'mcp_name': 'coder',
      'tool_name': 'run_python_code',
      'description': 'Execute Python code...',
      'similarity': 0.85
    }
  ],
  'best_match': {...}
}
```

### Code Detection Result
```python
{
  'language': 'python',
  'code': 'print("Hello, World!")'
}
# or None if no code found
```

---

## Common Workflows

### Add Session Management
1. Generate UUID in `main()` when starting
2. Pass session_id to `create_rating()` and `update_rating()`
3. Modify `/ratings/create` to accept `session_id`
4. Modify `/ratings` to filter by `session_id` parameter
5. Add session_id column to conversation_ratings table

### Add Custom MCP Tool
1. Create directory in `system_mcps/<tool_name>/`
2. Implement `server.py` using MCP SDK
3. Define tools in `@app.list_tools()` decorator
4. Handle execution in `@app.call_tool()` decorator
5. Tool auto-registers on next CLI startup

### Modify Similarity Behavior
- Threshold: main.py line 87 (SIMILARITY_THRESHOLD)
- Satisfactory rating: main.py line 88 (SATISFACTORY_RATING_THRESHOLD)
- Metric used: main.py line 118 ('metric': 'cosine')
- Model: src/transformer/app.py line 36 (EMBEDDING_MODEL)

---

## Debugging Tips

### Enable Verbose Mode
```bash
python main.py -v
```
Shows debug output with icons (🔍, ✅, ❌, etc.)

### Check Service Health
```bash
curl http://localhost:15000/health    # PostgreSQL API
curl http://localhost:16050/health    # Transformer
curl http://localhost:11434/api/tags  # Ollama
```

### View Docker Logs
```bash
docker-compose logs -f postgres-api
docker-compose logs -f transformer
docker-compose logs -f ollama
```

### Database Inspection
```bash
docker-compose exec postgres psql -U postgres -d vuhitra
\dt  -- list tables
SELECT * FROM conversation_ratings;
SELECT * FROM mcp_tools;
```

### Trace a Rating
1. Rating created: `/ratings/create` endpoint
2. Keywords extracted: `/keywords` endpoint
3. Similarity checked: `/similarity` endpoint
4. Stored in DB: conversation_ratings table
5. Used for guidance: `get_prompt_guidance()` function

---

## Performance Considerations

### Bottlenecks
1. **Embedding generation** (Transformer) - ~100ms per text
2. **Similarity search** - O(n) through all past ratings
3. **Ollama inference** - depends on model size
4. **Database queries** - small tables, not a concern

### Optimizations
- Embeddings cached in mcp_tools JSONB column
- Only top 5 keywords extracted (not full text)
- Batch embedding operations available at `/embed/batch`
- Context window limited to 10 messages by default

### Scaling Points
- Add index on conversation_ratings.created_at for time queries
- Implement vector database (Weaviate, Milvus) for scaling
- Cache embeddings in Redis for repeated queries
- Move rating storage to async queue

