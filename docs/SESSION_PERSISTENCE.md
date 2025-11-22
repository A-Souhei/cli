# Session Persistence Feature

## Overview

The CLI now supports **persistent session storage** in Redis, allowing you to save, restore, and manage conversation sessions across different CLI sessions. Sessions are automatically saved after each prompt and stored permanently (no TTL) until explicitly deleted.

## Features

✅ **Auto-save**: Sessions are automatically saved to Redis after every interaction
✅ **Permanent Storage**: Sessions persist in Redis with no TTL until manually cleared
✅ **Restore by ID**: Resume any saved session by its session ID
✅ **List Sessions**: View all your saved sessions with metadata
✅ **Clear Storage**: Remove specific or all saved sessions

## Commands

### Start a New Session
```bash
/session start
```
Creates a new session with a unique ID and begins tracking conversation history.

### End Current Session
```bash
/session end
```
Ends the active session and saves it to Redis. Session can be restored later.

### View Session Info
```bash
/session info
```
Shows information about the currently active session (ID, duration, interaction count).

### Restore a Saved Session
```bash
/session restore <session-id>
```
Restores a previously saved session by its ID, continuing from where you left off.

**Example:**
```bash
/session restore 3f4a2b1c-9d8e-4567-a123-456789abcdef
```

### List All Saved Sessions
```bash
/session list
```
or
```bash
/sessions
```
Lists all saved sessions with their metadata (ID, interaction count, start time).

### Clear All Saved Sessions
```bash
/session clear
```
Deletes ALL saved sessions from Redis storage (with confirmation prompt).

## How It Works

### Auto-Save
- Session is automatically saved to Redis **after every interaction**
- Session is also saved when you run `/session end`
- No manual save command needed!

### Session Data Stored
Each saved session contains:
- **Session ID**: Unique identifier (UUID)
- **History**: All prompt/response interactions
- **Start Time**: When the session began
- **Metadata**: Additional session information (model used, etc.)
- **Saved At**: Timestamp of last save

### Storage
- Sessions are stored in **Redis** (permanent, no TTL)
- Key format: `cli:session:<session-id>`
- All sessions are indexed in `cli:sessions:index` for quick listing

## Use Cases

### 1. Resume Long Conversations
```bash
# Day 1
/session start
# ... have a long conversation about project X ...
/session end
# CLI shows session ID

# Day 2
/session restore 3f4a2b1c-9d8e-4567-a123-456789abcdef
# Continue where you left off!
```

### 2. Multiple Project Contexts
```bash
# Work on project A
/session start
# ... discuss project A ...
/session end

# Switch to project B
/session start
# ... discuss project B ...
/session end

# List both sessions
/session list

# Resume project A later
/session restore <project-a-session-id>
```

### 3. Session Management
```bash
# View all your sessions
/session list

# Clear old sessions periodically
/session clear
```

## Technical Details

### Session Manager Updates

**New Methods:**
- `save_to_redis()` - Save current session to Redis
- `restore_from_redis(session_id)` - Restore session from Redis
- `list_saved_sessions()` - List all saved sessions
- `delete_session(session_id)` - Delete specific session
- `clear_all_sessions()` - Clear all sessions

### Redis API Endpoints

New endpoints in Redis Flask API (`src/redis/flask-app/app.py`):

- `POST /session/store` - Store session data
- `GET /session/retrieve` - Retrieve session data
- `GET /session/list` - List all sessions
- `DELETE /session/delete` - Delete specific session
- `DELETE /session/clear` - Clear all sessions

### Environment Variables

The session manager uses `REDIS_API_URL` environment variable (default: `http://localhost:17000`).

Set in docker-compose.yml or .env:
```bash
REDIS_API_URL=http://localhost:17000
```

## Examples

### Full Workflow
```bash
# Start CLI
python main.py

# Start a new session
▶ /session start
📝 Session started at 14:30:15

# Have conversation
▶ What is Python?
[AI responds about Python...]

▶ Show me an example
[AI shows Python example...]

# View session info
▶ /session info
📊 Session Info:
  • Session ID: 3f4a2b1c-9d8e...
  • Duration: 120s
  • Interactions: 2

# End session (auto-saved)
▶ /session end
✅ Session ended (started at 14:30:15, 2 interactions)
💾 Session saved: 3f4a2b1c-9d8e-4567-a123-456789abcdef

# Exit CLI
▶ /exit
👋 Goodbye!

# Later... start CLI again
python main.py

# List saved sessions
▶ /session list
📋 Saved Sessions:
  • 3f4a2b1c-9d8e...
    Interactions: 2, Started: 2025-11-22T14:30:15

# Restore previous session
▶ /session restore 3f4a2b1c-9d8e-4567-a123-456789abcdef
✅ Session restored: 3f4a2b1c-9d8e-4567-a123-456789abcdef (2 interactions)

# Continue from where you left off!
▶ Can you explain more about Python functions?
[AI responds with context from previous conversation...]
```

## Notes

- Sessions are stored **permanently** in Redis (no TTL)
- Use `/session clear` regularly to remove old sessions
- Session IDs are UUIDs (unique and random)
- RAG context from `@` prefix file uploads is also preserved in the session
- Auto-save happens silently in the background
- If auto-save fails, a debug message is shown (in verbose mode)

## Troubleshooting

### "Failed to auto-save session"
- Check Redis API is running: `curl http://localhost:17000/health`
- Check Redis service is up: `docker compose ps redis-api`
- Check `REDIS_API_URL` environment variable

### "Session not found"
- Make sure you're using the full session ID (copy from `/session list`)
- Check if session was deleted with `/session clear`

### Sessions not persisting
- Verify Redis API endpoints are working:
  ```bash
  curl http://localhost:17000/session/list?prefix=cli:session:
  ```
- Check Redis service logs: `docker compose logs redis-api`

## API Integration

If you want to integrate session persistence into other tools:

```python
from src.session import SessionManager

# Initialize with Redis API URL
session_mgr = SessionManager(redis_api_url="http://localhost:17000")

# Start session
session_id = session_mgr.start_session()

# Add interactions
session_mgr.add_interaction(
    prompt="Hello",
    response="Hi there!",
    metadata={"model": "llama3.1:8b"}
)

# Save to Redis
session_mgr.save_to_redis()

# Later... restore
session_mgr.restore_from_redis(session_id)

# List all sessions
sessions = session_mgr.list_saved_sessions()

# Clear all sessions
count = session_mgr.clear_all_sessions()
```

## Exception to GOLDEN RULE

⚠️ **Note**: This feature modifies CLI code (`main.py`, `src/session/manager.py`, `src/redis/flask-app/app.py`) as an **exception to the GOLDEN RULE** per user request. Future Ollama API service features should not modify CLI code.
