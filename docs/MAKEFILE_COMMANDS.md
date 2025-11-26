# Makefile Commands Quick Reference

This document provides a quick reference for all Makefile commands, with special focus on the new Redis and @ prefixer feature commands.

## 📦 Build Commands

### Service Images
```bash
make build                # Build PostgreSQL + Flask API image
make build-postgres       # Build PostgreSQL + Flask image (alias)
make build-transformer    # Build Transformer service image
make build-redis          # Build Redis API image
make build-all            # Build all images (PostgreSQL + Transformer + Redis)
make build-all-services   # Alias for build-all
```

## 🚀 Startup Commands

### Start Services
```bash
make up                   # Start Ollama services only (profile: ollama)
make up-redis             # Start Redis + Redis API + Transformer (profile: app)
make up-all               # Start ALL services (Ollama + PostgreSQL + Redis + Transformer)
make down                 # Stop all containers
make restart              # Restart containers (down + up)
```

### Service URLs (after `make up-all`)
- **Ollama**: http://localhost:11434
- **PostgreSQL**: localhost:35432 (user: postgres, db: vuhitra)
- **PostgreSQL API**: http://localhost:15000
- **Redis**: localhost:26379
- **Redis API**: http://localhost:17000
- **Transformer**: http://localhost:16050
- **Bugsink** (error tracking): http://localhost:8000

## 🔍 Monitoring Commands

### Logs
```bash
make logs                 # Show all container logs (follows)
make redis-logs           # Show Redis API logs (follows)
make flask-logs           # Show PostgreSQL Flask API logs
```

### Status & Health
```bash
make status               # Show status of all containers
make redis-info           # Show Redis server info and statistics
make redis-api-health     # Check Redis API health endpoint
make transformer-health   # Check Transformer service health endpoint
```

## 🗄️ Redis Commands

### Redis Management
```bash
make redis-cli            # Execute Redis CLI in container
                          # Tip: Use 'KEYS *' to list keys, 'GET key' to get value

make redis-clear          # Clear ALL Redis data (with confirmation)
                          # WARNING: Deletes all RAG contexts!

make redis-info           # Show Redis server information:
                          # - Redis version
                          # - Uptime
                          # - Memory usage
                          # - Database statistics
```

### Redis CLI Common Commands
Once in Redis CLI (`make redis-cli`):
```redis
KEYS *                          # List all keys
KEYS session:*                  # List session-specific keys
KEYS temp:*                     # List temporary keys
GET session:{id}:context:{path} # Get specific context
FLUSHALL                        # Clear all data (dangerous!)
INFO                            # Server information
DBSIZE                          # Number of keys
```

## 🗃️ PostgreSQL Commands

### Database Access
```bash
make exec-postgres        # Execute psql in PostgreSQL container
make update-schema        # Update PostgreSQL schema
make migrate-session      # Apply session feature migration
```

### PostgreSQL Commands
Once in psql (`make exec-postgres`):
```sql
\dt                       -- List tables
\d conversation_ratings   -- Describe table
\d mcp_tools              -- Describe MCP tools table
SELECT * FROM conversation_ratings LIMIT 10;
```

## 🤖 Ollama Commands

### Model Management
```bash
make list-models          # List installed Ollama models
make pull-model MODEL=llama2  # Pull a specific model
make exec-ollama CMD="ollama list"  # Execute custom Ollama command
```

### Example Model Operations
```bash
make pull-model MODEL=tinyllama   # Pull tinyllama (default)
make pull-model MODEL=llama2      # Pull llama2
make pull-model MODEL=codellama   # Pull codellama
```

## 🐍 Python Environment Commands

### Virtual Environment
```bash
make venv                 # Create Python virtual environment
make install              # Install Python dependencies
make setup                # Complete setup (venv + deps + Docker)
```

## 🧹 Cleanup Commands

### Clean Up
```bash
make clean                # Remove venv and Docker volumes (with confirmation)
                          # Prompts for:
                          # - Virtual environment removal
                          # - Docker volumes removal (includes models)
```

## 🧪 Testing Commands

```bash
make test                 # Run CLI tests
```

## 📖 Help Command

```bash
make help                 # Show all available commands with descriptions
make                      # Same as `make help` (default target)
```

## 🎯 Common Workflows

### First Time Setup
```bash
make setup                # Complete setup
make up-all               # Start all services
# Wait for services to be ready
make redis-api-health     # Verify Redis API is up
make transformer-health   # Verify Transformer is up
make run                  # Start the CLI
```

### Daily Development
```bash
make up-all               # Start all services
make run                  # Run the CLI
# ... do your work ...
make redis-info           # Check Redis status
make logs                 # Check logs if needed
make down                 # Stop when done
```

### Redis Context Management
```bash
# Check what's in Redis
make redis-cli
> KEYS *
> KEYS session:*

# Clear old contexts
make redis-clear

# Check Redis memory usage
make redis-info
```

### Troubleshooting
```bash
# Check service status
make status

# Check specific service health
make redis-api-health
make transformer-health

# View logs
make logs
make redis-logs
make flask-logs

# Restart everything
make restart

# Clean restart
make down
make clean  # Optional: clean volumes
make up-all
```

### Building After Code Changes

#### Redis API Changes
```bash
make build-redis          # Rebuild Redis API
make down
make up-redis             # Start Redis services
```

#### Transformer Changes
```bash
make build-transformer    # Rebuild Transformer
make down
make up-redis             # Start with new Transformer
```

#### PostgreSQL API Changes
```bash
make build-postgres       # Rebuild PostgreSQL API
make down
make up-all               # Restart all services
```

## 🔐 Environment Configuration

### Environment Variables (.env)
The Makefile automatically creates `.env` from `.env.example` if it doesn't exist.

Key variables for @ prefixer feature:
```bash
REDIS_HOST_PORT=26379         # Redis port on host
REDIS_API_PORT=17000          # Redis API port
TRANSFORMER_HOST_PORT=16050   # Transformer service port
POSTGRES_HOST_PORT=35432      # PostgreSQL port
FLASK_HOST_PORT=15000         # PostgreSQL API port
```

## 📊 Monitoring Redis for @ Prefixer Feature

### Check Context Storage
```bash
# See all stored contexts
make redis-cli
> KEYS *

# Session contexts
> KEYS session:*:context:*

# Temporary contexts
> KEYS temp:context:*

# Tree structures
> KEYS *__TREE__

# Get specific context
> GET session:abc123:context:models/user.py

# Check database size
> DBSIZE

# Check memory usage
> INFO memory
```

### Monitor Redis Performance
```bash
make redis-info

# Output shows:
# - Redis version
# - Uptime
# - Memory usage
# - Number of keys
# - Hit rate
```

## 🆘 Emergency Commands

### If Services Won't Start
```bash
make down
docker ps -a              # Check for stuck containers
docker system prune -f    # Clean up Docker
make up-all
```

### If Redis Has Corrupt Data
```bash
make redis-clear          # Clear all Redis data
# OR
make down
docker volume rm vuhitra-redis-data
make up-redis
```

### If Need Complete Reset
```bash
make down
make clean                # Say 'y' to both prompts
docker system prune -af   # Nuclear option
make setup
make up-all
```

## 💡 Tips

1. **Always check health** after starting services: `make redis-api-health`, `make transformer-health`
2. **Use redis-info** regularly to monitor memory usage
3. **Clear old contexts** periodically with `make redis-clear`
4. **Check logs** if something isn't working: `make logs` or `make redis-logs`
5. **Session contexts persist** - use `session end` in CLI or `make redis-clear` to clean up

## 📝 Notes

- Redis data persists in Docker volume `vuhitra-redis-data`
- Transformer models cache in volume `vuhitra-transformer-models`
- Session contexts are automatically cleaned up when session ends (in CLI)
- Temporary contexts expire after 1 hour
- Tree structures are stored with special `__TREE__` suffix in key names
