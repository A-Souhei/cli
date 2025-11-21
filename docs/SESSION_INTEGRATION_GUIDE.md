# Session Management Integration Guide

## Where Sessions Fit in the Current Architecture

### Current Flow (No Sessions)
```
CLI Startup
  ├─ Initialize ChatManager with new context
  ├─ Initialize MCPClient for this run
  └─ Start Interactive Loop
      └─ Each user input creates ratings in DB
         (but not linked to any session concept)
```

### Proposed Flow (With Sessions)
```
CLI Startup
  ├─ Generate or load Session UUID
  ├─ Initialize ChatManager with session_id
  ├─ Initialize MCPClient for this run
  └─ Start Interactive Loop
      ├─ Each user input → stored with session_id
      ├─ Can query: "Show me all ratings from session X"
      └─ Can resume: "Continue from session Y's last message"
```

---

## Integration Points

### 1. ChatManager Enhancement
**File**: `src/chat/manager.py`

Current:
```python
class ChatManager:
    def __init__(self, system_prompt: str, max_context_length: int = 10):
        self.messages = []
        # Add system prompt...
```

Enhanced:
```python
class ChatManager:
    def __init__(self, system_prompt: str, max_context_length: int = 10, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.messages = []
        # Add system prompt...
    
    def get_session_id(self) -> str:
        return self.session_id
```

### 2. Rating Creation
**File**: `main.py`, function `create_rating()` (lines 154-171)

Current:
```python
def create_rating(user_rating, prompt_text, response_text, tags):
    params = {
        'user_rating': user_rating,
        'prompt_text': prompt_text,
        'response_text': response_text,
        'tags': json.dumps({'keywords': tags})
    }
```

Enhanced:
```python
def create_rating(user_rating, prompt_text, response_text, tags, session_id=None):
    params = {
        'user_rating': user_rating,
        'prompt_text': prompt_text,
        'response_text': response_text,
        'tags': json.dumps({'keywords': tags}),
        'session_id': session_id  # NEW
    }
```

### 3. Rating Update
**File**: `main.py`, function `update_rating()` (lines 174-190)

Current:
```python
def update_rating(rating_id, user_rating, response_text, tags):
    payload = {
        'user_rating': user_rating,
        'response_text': response_text,
        'tags': {'keywords': tags}
    }
```

Enhanced:
```python
def update_rating(rating_id, user_rating, response_text, tags, session_id=None):
    payload = {
        'user_rating': user_rating,
        'response_text': response_text,
        'tags': {'keywords': tags},
        'session_id': session_id  # NEW
    }
```

### 4. Rating Processing
**File**: `main.py`, function `process_rating()` (lines 218-252)

Current:
```python
def process_rating(user_rating, prompt_text, response_text):
    # ... processing logic ...
    create_rating(user_rating, prompt_text, response_text, keywords)
```

Enhanced:
```python
def process_rating(user_rating, prompt_text, response_text, session_id=None):
    # ... processing logic ...
    create_rating(user_rating, prompt_text, response_text, keywords, session_id)
```

### 5. Main Loop Integration
**File**: `main.py`, main function (lines 554-818)

Current:
```python
def main(verbose=False):
    # ... initialization ...
    chat_manager = ChatManager(...)  # No session_id
    
    while True:
        # ... chat loop ...
        process_rating(rating, user_input, full_response)  # No session_id
```

Enhanced:
```python
def main(verbose=False):
    # ... initialization ...
    session_id = str(uuid.uuid4())  # Generate or load session
    chat_manager = ChatManager(..., session_id=session_id)
    
    while True:
        # ... chat loop ...
        process_rating(rating, user_input, full_response, session_id)
```

### 6. Database Schema Changes
**File**: `src/postgresql/init.sql`

Current:
```sql
CREATE TABLE conversation_ratings (
    id SERIAL PRIMARY KEY,
    user_rating INTEGER,
    prompt_text TEXT,
    response_text TEXT,
    tags JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

Enhanced:
```sql
CREATE TABLE conversation_ratings (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,              -- NEW
    user_rating INTEGER,
    prompt_text TEXT,
    response_text TEXT,
    tags JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- NEW: Sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    model_used TEXT,
    total_exchanges INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

-- NEW: Index for fast filtering
CREATE INDEX idx_session_id ON conversation_ratings(session_id);
CREATE INDEX idx_session_created ON sessions(created_at DESC);
```

### 7. PostgreSQL API Enhancement
**File**: `src/postgresql/app/app.py`

New endpoints needed:
```python
@app.route('/ratings', methods=['GET'])
def get_ratings():
    """Enhanced to support session filtering"""
    session_id = request.args.get('session_id')  # NEW
    min_rating = request.args.get('min_rating', type=int)
    
    query = ConversationRating.query
    if session_id:
        query = query.filter(ConversationRating.session_id == session_id)
    if min_rating is not None:
        query = query.filter(ConversationRating.user_rating >= min_rating)
    
    ratings = query.order_by(ConversationRating.created_at.desc()).all()
    return jsonify({...})

@app.route('/sessions', methods=['GET'])
def list_sessions():
    """NEW: List all sessions"""
    sessions = Session.query.order_by(Session.created_at.desc()).all()
    return jsonify({
        'sessions': [{
            'id': s.id,
            'created_at': s.created_at,
            'ended_at': s.ended_at,
            'model_used': s.model_used,
            'total_exchanges': s.total_exchanges
        } for s in sessions]
    })

@app.route('/sessions/<session_id>/resume', methods=['GET'])
def resume_session(session_id):
    """NEW: Get conversation history for a session"""
    ratings = ConversationRating.query.filter_by(session_id=session_id).order_by(
        ConversationRating.created_at.asc()
    ).all()
    return jsonify({
        'ratings': [{
            'prompt_text': r.prompt_text,
            'response_text': r.response_text,
            'created_at': r.created_at
        } for r in ratings]
    })
```

### 8. CLI Command Additions
**File**: `main.py`, special commands section

New commands:
```python
if user_input.lower() == 'sessions':
    # List available sessions
    list_sessions()
    continue

if user_input.lower().startswith('resume '):
    session_id = user_input[7:].strip()
    # Load previous session's chat history
    resume_session(session_id)
    continue

if user_input.lower() == 'session-info':
    # Show current session info
    console.print(f"Current Session ID: {session_id}")
    continue
```

---

## Implementation Steps

### Phase 1: Database & API (1-2 hours)
1. Add uuid import to app.py
2. Create Session model in app.py
3. Add session_id column to ConversationRating model
4. Create migration/update init.sql
5. Add /sessions endpoints
6. Test endpoints with curl

### Phase 2: Core CLI Integration (1-2 hours)
1. Add uuid import to main.py
2. Generate session_id in main()
3. Pass session_id to ChatManager
4. Pass session_id to create_rating/update_rating
5. Update process_rating calls
6. Test rating storage with session_id

### Phase 3: Session Commands (1 hour)
1. Add 'sessions' command handler
2. Add 'resume <session_id>' command handler
3. Add 'session-info' command handler
4. Add help text updates

### Phase 4: Session Resume (2-3 hours)
1. Create resume_session() function
2. Load previous conversation history
3. Restore ChatManager context
4. Update UI to show which session is active
5. Test end-to-end resume workflow

### Phase 5: Testing (1-2 hours)
1. Unit tests for ChatManager session handling
2. Integration tests for API endpoints
3. Manual testing of all workflows

---

## Minimal Viable Session Implementation

If time is limited, implement just this:

1. **Add to ChatManager**:
   ```python
   def __init__(self, ..., session_id=None):
       self.session_id = session_id or str(uuid.uuid4())
   ```

2. **Add to main()**:
   ```python
   session_id = str(uuid.uuid4())
   chat_manager = ChatManager(..., session_id=session_id)
   ```

3. **Add to create_rating()**:
   ```python
   params['session_id'] = session_id
   ```

4. **Add session_id parameter to conversation_ratings**:
   ```sql
   ALTER TABLE conversation_ratings ADD COLUMN session_id TEXT;
   ```

This gives you:
- Unique identification for each CLI run
- Ability to query ratings by session
- Foundation for future resume/history features
- Minimal code changes (~20 lines)

---

## Testing the Session Implementation

### Test 1: Session Creation
```python
# main.py should generate a UUID
session_id = str(uuid.uuid4())
assert len(session_id) == 36  # UUID format
```

### Test 2: Rating Storage
```python
# Rate a response
# Check PostgreSQL:
SELECT * FROM conversation_ratings 
WHERE session_id = '<test-session-uuid>';
# Should have at least 1 row
```

### Test 3: Session Filtering
```bash
curl "http://localhost:15000/ratings?session_id=<uuid>"
# Should return only ratings from that session
```

### Test 4: Session Resume
```bash
curl "http://localhost:15000/sessions/<uuid>/resume"
# Should return conversation history in order
```

---

## Benefits of This Approach

1. **Minimal Changes**: Only ~50 lines of code needed for basic functionality
2. **Backward Compatible**: Doesn't break existing functionality
3. **Extensible**: Foundation for multi-user, multi-session features
4. **Queryable**: Can analyze conversation patterns by session
5. **Persistent**: Sessions stored in database, not ephemeral

---

## Future Enhancements

Once basic sessions work:
1. Load last 10 sessions in CLI startup menu
2. Show session duration and exchange count
3. Export session as JSON/Markdown
4. Tag sessions with metadata
5. Search sessions by keyword
6. Compare ratings across sessions
7. Multi-user sessions (add user_id field)
8. Session branches (fork conversation at any point)
