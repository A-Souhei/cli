# Installing the Session Feature

Follow these steps to enable the session feature in your AI CLI:

## Step 1: Rebuild the PostgreSQL API Container

The Flask API code has been updated to support session_id, so you need to rebuild:

```bash
# Option 1: Using docker compose directly
docker compose build postgres-api
docker compose up -d postgres-api

# Option 2: Using make (if available)
make build-postgres
make up
```

This rebuilds the `postgres-api` container with the updated Flask application that handles `session_id` parameters.

## Step 2: Apply the Database Migration

Add the `session_id` column to the database:

```bash
# Recommended: Using make
make migrate-session

# Alternative: Using the script directly
./scripts/apply_session_migration.sh

# Alternative: Manual migration
docker compose exec postgres psql -U postgres -d vuhitra -f /path/to/migrations/add_session_id.sql
```

## Step 3: Verify the Installation

Check that everything is working:

```bash
# 1. Check container is running
docker compose ps

# 2. Check Flask API health
curl http://localhost:15000/health

# 3. Verify database schema
docker compose exec postgres psql -U postgres -d vuhitra -c "\d conversation_ratings"
# You should see the session_id column in the output

# 4. Test the session feature
make run
# Then try: session start
```

## Troubleshooting

### Container won't start after rebuild
```bash
# Check logs
docker compose logs postgres-api

# Restart services
docker compose restart postgres-api
```

### Migration fails
```bash
# Check if postgres container is running
docker compose ps postgres

# Try running migration manually
docker compose exec postgres psql -U postgres -d vuhitra < migrations/add_session_id.sql
```

### Session commands not working
```bash
# Verify Python dependencies
source venv/bin/activate
python -c "from src.session import SessionManager; print('OK')"

# Check main.py syntax
python -m py_compile main.py
```

## What Gets Updated

### Containers Rebuilt:
- ✅ `postgres-api` (Flask API) - Contains updated app.py

### Containers NOT Affected:
- ⏭️ `ollama` - No changes
- ⏭️ `postgres` - Database itself (only schema changes)
- ⏭️ `transformer` - No changes
- ⏭️ Main CLI (runs on host, not in container)

### Database Changes:
- ✅ Adds `session_id` column to `conversation_ratings` table
- ✅ Adds index on `session_id` for performance

## Quick Start After Installation

Once installed, you can use sessions like this:

```bash
# Start the CLI
make run

# Start a session
▶ session start
📝 Session started at 16:45:10

# Ask related questions
▶ What is Python?
▶ How do I install it?
▶ What are virtual environments?

# Check session info
▶ session info

# End the session
▶ session end
✅ Session ended (started at 16:45:10, 3 interactions)
```

## Full Documentation

See [docs/SESSION_FEATURE.md](docs/SESSION_FEATURE.md) for complete documentation including:
- Detailed usage examples
- Session Manager API reference
- Best practices
- Advanced features
