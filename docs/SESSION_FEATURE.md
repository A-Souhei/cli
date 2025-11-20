# Session Feature Documentation

## Overview

The session feature enables context persistence across multiple prompts within a conversation session. When a session is active, all prompts and responses are tracked and embedded into the conversation context using RAG (Retrieval-Augmented Generation), allowing the AI to maintain awareness of the full conversation history.

## How It Works

### Without a Session (Default Behavior)
- Each prompt is treated independently
- No conversation history is maintained beyond the default chat context
- Responses are not connected to previous interactions

### With an Active Session
- All prompts and responses are tracked as interactions
- Previous interactions (up to the last 5) are injected as context
- The AI can reference and build upon previous exchanges
- Each interaction includes metadata (model, temperature, etc.)
- Session data is stored with a unique session ID

## Commands

### Start a Session
```bash
session start
```
Starts a new session with a unique session ID. All subsequent prompts will be part of this session until you end it.

Example output:
```
📝 Session started: 12345678...
```

### End a Session
```bash
session end
```
Ends the current session and displays a summary.

Example output:
```
✅ Session ended: 12345678... (5 interactions)
```

### Get Session Info
```bash
session info
```
Displays information about the current active session.

Example output:
```
📊 Session Info:
  • Session ID: 12345678-1234-12...
  • Duration: 127s
  • Interactions: 5
```

## Usage Examples

### Example 1: Multi-step Problem Solving

```bash
▶ session start
📝 Session started: 12345678...

▶ What is the capital of France?
▶ Paris

▶ What's the population of that city?
▶ Paris has approximately 2.2 million people in the city proper...

▶ What are the top tourist attractions there?
▶ In Paris, the top tourist attractions include the Eiffel Tower...

▶ session end
✅ Session ended: 12345678... (3 interactions)
```

In this example, the AI understands "that city" refers to Paris because of the session context.

### Example 2: Code Development

```bash
▶ session start
📝 Session started: abcdef12...

▶ Write a Python function to calculate fibonacci numbers
▶ [AI provides fibonacci function]

▶ Now add memoization to optimize it
▶ [AI modifies the previous function with memoization]

▶ Write unit tests for this function
▶ [AI writes tests for the memoized fibonacci function]

▶ session end
✅ Session ended: abcdef12... (3 interactions)
```

The AI maintains context of the specific function being developed throughout the session.

## Technical Details

### Session Context Injection

When a session is active, the system:
1. Retrieves the last 5 interactions from the session history
2. Formats them as a system message
3. Injects this context before the current user prompt
4. Sends the enhanced context to the LLM

### Context Format

```
[Session Context - N previous interactions]

Interaction 1:
User: [previous prompt]
Assistant: [previous response]

Interaction 2:
User: [previous prompt]
Assistant: [previous response]
...

[Current prompt follows]
```

### Database Storage

Session data is stored in two ways:

1. **In-Memory (During Session)**
   - Full session history with complete prompts and responses
   - Metadata for each interaction
   - Session start time and duration

2. **Database (For Ratings)**
   - Ratings are tagged with the session_id
   - Allows querying all rated interactions from a session
   - Enables session-based analytics

### Session Manager API

The `SessionManager` class provides the following methods:

```python
# Start a new session
session_id = session_manager.start_session(metadata=None)

# Check if a session is active
is_active = session_manager.is_active()

# Add an interaction to the session
session_manager.add_interaction(prompt, response, metadata)

# Get session context as a formatted string
context = session_manager.get_session_context(max_interactions=5)

# Get session information
info = session_manager.get_session_info()

# End the session
summary = session_manager.end_session()
```

## Database Migration

To enable session support in the database, run the migration script:

```bash
# Connect to PostgreSQL
docker exec -it <postgres_container> psql -U postgres -d vuhitra

# Run the migration
\i /path/to/migrations/add_session_id.sql
```

Or using psql directly:
```bash
psql -h localhost -p 25432 -U postgres -d vuhitra -f migrations/add_session_id.sql
```

The migration adds:
- `session_id` column to `conversation_ratings` table
- Index on `session_id` for efficient queries
- Documentation comments

## Debugging

Enable verbose mode to see session context injection:

```bash
python main.py -v
```

When a session is active, you'll see debug messages like:
```
📝 Session active: 3 interactions in context
```

## Best Practices

1. **Start a session when:**
   - You're having a multi-turn conversation on the same topic
   - Building something iteratively (code, documents, etc.)
   - The context from previous messages is important

2. **End a session when:**
   - You're switching to a completely different topic
   - The session has become too long (performance impact)
   - You want to start fresh

3. **Don't use sessions for:**
   - Single, independent queries
   - Unrelated questions in succession
   - When you want completely context-free responses

## Future Enhancements

Potential improvements for the session feature:

1. **Session Persistence**: Save sessions to disk for resuming later
2. **Session Branching**: Create branches from existing sessions
3. **Session Search**: Search through past sessions
4. **Session Export**: Export session history as markdown/JSON
5. **Smart Context Selection**: Use embeddings to select most relevant past interactions
6. **Session Analytics**: Visualize session flow and interaction patterns
7. **Multi-user Sessions**: Share sessions between users
8. **Session Tags**: Tag sessions for better organization

## Troubleshooting

### Session doesn't seem to maintain context

- Check if the session is actually active with `session info`
- Verify verbose mode shows "Session active: N interactions in context"
- Ensure you didn't clear chat history (which is separate from session history)

### Performance issues with long sessions

- Long sessions may slow down responses due to context size
- Consider ending the session and starting a new one
- Default context limit is 5 interactions to balance context and performance

### Database errors

- Ensure the migration has been applied
- Check PostgreSQL API logs for errors
- Verify the session_id column exists in conversation_ratings table

## Architecture

```
User Input
    ↓
Session Active?
    ↓ (yes)
Session Manager
    ↓
Get last 5 interactions
    ↓
Format as context
    ↓
Inject into messages
    ↓
Send to LLM
    ↓
Get Response
    ↓
Store in Session History
    ↓
Store in Database (with session_id)
```
