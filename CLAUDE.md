# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI CLI is an Ollama-powered chat interface with advanced features including:
- Interactive CLI and Web UI for AI conversations
- Ollama++ API Service (OpenWebUI-compatible API with enhanced features)
- RAG context system with Redis-backed vector embeddings
- MCP (Model Context Protocol) tool system for code execution and file operations
- Session persistence with Redis storage
- Multi-service Docker architecture

## Critical Development Rules

### 1. Sentry Error Tracking
**ALWAYS** use `src/sentry_config.py` for any new endpoints or services:
```python
from src.sentry_config import configure_sentry, capture_exception

# In your service/endpoint initialization:
configure_sentry(service_name="your-service-name")

# For error handling:
try:
    # ... your code
except Exception as e:
    capture_exception(e)
    # ... handle error
```

This ensures consistent error tracking across all services via Sentry.

### 2. Avoid Source Code Bloating
**DO NOT** create monolithic files. When a file grows large or complex:
- Extract related functionality into new modules
- Create logical groupings in separate files
- Import and compose rather than accumulating code in one place
- Follow the existing pattern: `src/utils/` contains focused, single-purpose modules

### 3. Testing Before Commits
**NEVER** commit code until all tests pass:
```bash
make test           # Run all tests
make test-unit      # For quick feedback (no Docker dependencies)
```

Ensure your changes don't break existing functionality before committing.

### 4. Push Policy
**NEVER** push to remote without explicit user consent. Always:
- Wait for user to request a push
- Confirm branch and changes before pushing
- Never use `git push --force` on main/master branches

## Development Commands

### Setup
```bash
make setup              # Complete setup (venv + dependencies + Docker)
make venv               # Create virtual environment only
make install            # Install Python dependencies only
```

### Building Services
```bash
make build-all-services # Build all Docker images
make build              # Build PostgreSQL + Flask image
make build-transformer  # Build transformer image
make build-redis        # Build Redis API image
```

### Running
```bash
make run                # Run CLI (uses ./start.sh)
make run-verbose        # Run CLI in verbose mode
make ui                 # Start Web UI in background (detached, no logs)
make ui-logs            # Start Web UI in foreground with logs
make ui-stop            # Stop the running Web UI

# Direct CLI commands
./venv/bin/python main.py --show-ui              # Start UI in background
./venv/bin/python main.py --show-ui --with-logs  # Start UI in foreground with logs
./venv/bin/python main.py --stop-ui              # Stop UI server
```

**Note**: The UI runs on port 18080. When starting the CLI normally, any running UI instance is automatically cleaned up to prevent conflicts.

### Docker Services
```bash
make up-all             # Start all services (Ollama + PostgreSQL + Redis + Transformer)
make up                 # Start Ollama only
make up-redis           # Start Redis services only
make down               # Stop containers
make restart            # Restart containers
make status             # Show container status
make logs               # View container logs
```

### Testing
```bash
make test               # Run all tests (pytest + unit tests)
make test-unit          # Run unit tests only (no Docker dependencies)
make test-integration   # Run integration tests (requires containers)
make test-spin          # Run spin_the_roulette tests
make test-all           # Run all tests including slow tests

# Run specific tests
./venv/bin/pytest tests/test_ollama_api_integration.py -v
./venv/bin/pytest tests/ -v -m "not slow"  # Skip slow tests
```

### Database Management
```bash
make exec-postgres      # Access PostgreSQL CLI
make update-schema      # Update PostgreSQL schema
make migrate-session    # Apply session feature migration
```

### Redis Management
```bash
make redis-cli          # Access Redis CLI
make redis-clear        # Clear all Redis data (with confirmation)
make redis-info         # Show Redis statistics
make redis-api-health   # Check Redis API health
make redis-logs         # Show Redis API logs
```

### Ollama Management
```bash
make pull-model MODEL=llama2  # Pull a specific model
make list-models              # List available models
make exec-ollama CMD="ollama list"  # Execute command in Ollama container
```

## Architecture

### Core Components

**Main Entry Point**: `main.py`
- Initializes ConfigManager, OllamaClient, ChatManager, MCPClient
- Handles interactive CLI loop with prompt_toolkit
- Preserves original working directory in `AI_CLI_ORIGINAL_DIR` env var

**Configuration**: `config.yaml`
- Ollama settings: url, model, coder_model, timeout
- Tinyollama settings: lightweight fallback with disabled_features list
- Chat settings: system_prompt, max_context_length, temperature, stream

### Module Structure

```
src/
├── config/              # Configuration management
│   ├── manager.py       # ConfigManager - loads config.yaml
│   └── llm_availability.py  # LLM service availability checking
├── model_registry/      # Dynamic model configuration
│   ├── manager.py       # ModelRegistry - Redis-backed model storage
│   └── availability.py  # Model availability checking
├── embedding_client/    # Embedding service abstraction
│   └── client.py        # EmbeddingClient - external services + fallback
├── ollama_client/       # Ollama API client
│   └── client.py        # OllamaClient - communicates with Ollama service
├── chat/                # Chat context management
│   └── manager.py       # ChatManager - maintains conversation history
├── mcp/                 # Model Context Protocol system
│   └── client.py        # MCPClient - manages MCP tool servers
├── session/             # Session persistence
│   ├── manager.py       # SessionManager - Redis-backed session storage
│   └── title_generator.py  # Auto-generates session titles
├── utils/               # Utility functions
│   ├── tree.py          # Directory tree visualization
│   ├── repomap.py       # Repository mapping for codebase context
│   ├── datamap.py       # Data file mapping and PostgreSQL signatures
│   ├── ratings.py       # Rating processing and prompt guidance
│   ├── code_handlers.py # Code detection, execution, file writing
│   ├── mcp_discovery.py # MCP server discovery
│   └── banner.py        # CLI banner display
├── file_completer.py    # @ prefix file/directory autocomplete
├── selector.py          # Interactive selection UI
└── ui/                  # Web UI (Flask)
    ├── server.py        # Flask application
    └── routes/          # API endpoints
```

### Microservices Architecture

**PostgreSQL API** (`src/postgresql/flask-app/`)
- Port: 15000
- Stores conversation ratings and MCP tool definitions
- Endpoints: `/ratings`, `/mcp-tools/store`, `/mcp-tools/match`

**Redis API** (`src/redis/flask-app/`)
- Port: 17000
- RAG vector storage and session persistence
- Depends on Transformer service for embeddings

**Transformer Service** (`src/transformer/`)
- Port: 16050
- Sentence embeddings using `all-MiniLM-L6-v2` (384 dimensions)
- Endpoints: `/embed`, `/similarity`, `/keywords`, `/sentiment`, `/summarize`

**Ollama++ API** (`ollama_api_service/`)
- Port: 8080
- OpenWebUI-compatible API with enhanced features
- FastAPI application with routes for chat, generate, OpenAI compatibility, tools, files
- Integrates MCP tools, RAG, and code execution

### MCP (Model Context Protocol) System

**Location**: `system_mcps/coder/`

**Available Tools**:
1. `run_python_code` - Execute Python in CLI's venv
2. `run_r_code` - Execute R code
3. `detect_code` - Extract code from text

**Tool Matching**:
- Tools stored with embeddings in PostgreSQL on startup
- User input matched against tool embeddings via `/mcp-tools/match`
- Default similarity threshold: 0.5

### RAG & Similarity Search

**Flow**:
1. User input → Embedding service generates embedding
2. Compare with stored tool/prompt embeddings using cosine similarity
3. If similarity ≥ 0.7: provide prompt guidance based on past ratings
4. Extract keywords from responses for future guidance

**Embedding Model**: Dynamic with fallback
- **Default**: Local Sentence-Transformers `all-MiniLM-L6-v2` (384 dimensions)
- **Configurable**: External embedding services via `/model embedding add <url>`
- **Auto-detection**: Embedding dimensions detected automatically
- **Fallback**: Seamless fallback to local transformer service

**EmbeddingClient**:
- Abstraction layer for embedding generation
- Supports external services with automatic fallback
- Auto-detects dimensions on first call
- Used by PostgreSQL API, Redis API, and ratings system

### Session Management

**Features**:
- Auto-save to Redis
- Session restoration by ID
- Title auto-generation using LLM
- Working directory tracking (raises WorkingDirectoryMismatchError if mismatch)

**Commands**:
- `/session start` - Start session
- `/session end` - End session
- `/session info` - Show session info
- `/session list` - List saved sessions
- `/session restore <id>` - Restore previous session
- `/session clear` - Clear all sessions

### Context Management

**Features**:
- Add files/directories to context without triggering LLM
- View current context (chat messages, session data, loaded files)
- Clear context while keeping session active

**Commands**:
- `/context add @file` - Add file to context without LLM call
- `/context add @directory` - Add directory to context without LLM call
- `/context add ALL` - Add entire working directory to context
- `/context add ALL_TOOLS` - Add all MCP tools with descriptions to context
- `/context show` - Display current context (chat, session, metadata)
- `/context metrics` - Show context size and usage metrics
- `/context clear` - Clear context (keeps session active)

**Usage Examples**:
```bash
/context add @src/main.py              # Add a single file
/context add @src/utils/               # Add entire directory
/context add @file1.py @file2.py       # Add multiple files
/context add ALL                       # Add entire working directory
/context add ALL_TOOLS                 # Add all MCP tools reference
/context show                          # View what's in context
/context metrics                       # View context size and metrics
```

**Notes**:
- Unlike using `@file` in a regular prompt (which triggers the LLM), `/context add` only loads the file/directory into context for later use. This allows you to build up context incrementally without wasting tokens on unnecessary LLM responses.
- **ALL_TOOLS keyword**: After running `/context add ALL_TOOLS`, you can reference "ALL_TOOLS" in your prompts to access the complete MCP tools documentation. The LLM will have access to all tool descriptions, parameters, and usage information.

### Model Management

**Commands**:
- `/model status` - Show all configured models
- `/model list` - List all models
- `/model <type> list` - List models of specific type
- `/model <type> add <url> <model_name>` - Add general/coder model
- `/model embedding add <url> [timeout]` - Add external embedding service
- `/model <type> use <model_id>` - Set active model
- `/model <type> remove <model_id>` - Remove model
- `/model check [model_id]` - Check model availability

**Model Types**:
- `general` - General purpose chat models
- `coder` - Code-specific models
- `embedding` - External embedding services (no model_name required)

## Important Patterns

### Working Directory Preservation
The application captures the original working directory at startup:
```python
# In main.py, BEFORE any imports:
if 'AI_CLI_ORIGINAL_DIR' not in os.environ:
    os.environ['AI_CLI_ORIGINAL_DIR'] = os.getcwd()
```

Use `get_user_working_dir()` to access the user's original directory throughout the codebase.

### Code Detection & Execution
1. LLM response analyzed for ```python or ```r code blocks
2. User prompted for execution confirmation via InteractiveSelector
3. Code sent to MCP server via JSON-RPC
4. Results displayed with rich formatting

### Rating & Feedback System
- User rates responses 0-10 after each interaction
- Rating ≥ 7: keywords stored as positive guidance
- Rating < 7: keywords stored as negative guidance
- Similar prompts (≥0.7 similarity) trigger guidance injection

### Error Handling
- Sentry integration for error tracking (optional, via SENTRY_DSN env var)
- Services fail gracefully with warnings
- JSON-RPC errors handled from MCP servers
- Timeout handling on all external API calls

### Async Patterns
- `nest_asyncio` applied globally for nested event loop support
- MCP communication uses async subprocess
- Most API calls are synchronous via `requests`

## Environment Variables

Key variables in `.env`:
- `OLLAMA_API_URL` - Ollama service URL (default: http://localhost:11434)
- `POSTGRES_HOST_PORT` - PostgreSQL host port (default: 35432)
- `FLASK_HOST_PORT` - PostgreSQL API port (default: 15000)
- `REDIS_HOST_PORT` - Redis host port (default: 26379)
- `REDIS_API_PORT` - Redis API port (default: 17000)
- `TRANSFORMER_HOST_PORT` - Transformer service port (default: 16050)
- `OLLAMA_API_PORT` - Ollama++ API port (default: 8080)
- `SENTRY_DSN` - Sentry DSN for error tracking (optional)
- `ENVIRONMENT` - Environment name (default: DEV)
- `MCP_DEBUG` - Enable MCP debugging (default: false)

## Testing Considerations

### Test Organization
- `tests/` - Integration tests (require Docker services)
- `test_cli.py` - Unit tests (no Docker dependencies)
- `tests/test_ollama_api_*.py` - API integration tests
- `tests/test_spin_the_roulette.sh` - curl-based API tests

### Test Markers
- Use `-m "not slow"` to skip long-running tests
- Slow tests typically involve LLM processing (>2min)

### Auto-Skip Behavior
Tests auto-skip if required containers are unavailable (PostgreSQL, Redis, Transformer).

## Special Files

- `.repomap` - Repository structure map (created via `/repomap create`, loaded via `/repomap load`)
- `.datamap` - Data file map with PostgreSQL signatures (created via `/datamap create`)
- `.llmignore` - File ignore patterns for LLM context (works like .gitignore)
- `~/.ai_cli_history` - Command history for prompt_toolkit
- `config.yaml` - Main configuration (NOT config.example.yaml)
- `migrations/` - Database migration scripts

### .llmignore - Security Feature

The `.llmignore` file prevents sensitive files from being added to LLM context:

**Key Features:**
- Works like `.gitignore` - supports globs, negations, comments, directory patterns
- Files matching patterns are NEVER added to context, even if explicitly requested with `@`
- Hierarchical: `.llmignore` files in subdirectories apply to that directory
- Security-focused: Blocks secrets, credentials, API keys from LLM exposure

**Commands:**
- `/ignore create` - Create `.llmignore` file in working directory with default patterns
- `/ignore add @file1 @file2` - Add files to `.llmignore`

**Pattern Syntax:**
```
# Comments start with #
*.env          # Ignore all .env files
secrets/       # Ignore secrets directory
!important.env # Negation: don't ignore this file
/config.yaml   # Anchored: only root config.yaml
```

**Example .llmignore:**
```
# Secrets
.env
*.key
secrets/

# Dependencies
node_modules/
venv/
__pycache__/
```

**Usage Examples:**
```bash
/ignore create                    # Create .llmignore with defaults
/ignore add @.env @secrets.yaml   # Add specific files
/ignore add @credentials/         # Add directory
```

**Where it applies:**
- CLI `@` prefix file/directory context
- Web UI file uploads
- Ollama++ API file operations
- All modes: general, code, make

See `.llmignore.example` for a comprehensive template.

## Web UI

Start with: `make ui` or `python main.py --show-ui`
- Runs on port 18080
- Flask-based UI with session management
- Provides file upload, chat history, and explorer

## Global Installation

Install globally with: `./install-global.sh`
- Creates symlink to `ai-cli` wrapper script
- Wrapper preserves working directory in `AI_CLI_CWD` env var
- Allows running `ai-cli` from anywhere

## Common Development Tasks

### Adding a New MCP Tool
1. Create tool in `system_mcps/<name>/server.py`
2. Implement MCP protocol with tool definitions
3. Tool auto-registered on CLI startup via MCPClient
4. Embedding stored in PostgreSQL for matching

### Modifying API Endpoints
- PostgreSQL API: `src/postgresql/flask-app/app.py`
- Redis API: `src/redis/flask-app/app.py`
- Transformer: `src/transformer/app.py`
- Ollama++ API: `ollama_api_service/routes/`

### Updating Database Schema
1. Modify `src/postgresql/init.sql`
2. Run `make update-schema` to apply changes
3. For session-related changes, use `make migrate-session`

### Testing RAG/Similarity Features
- Use `tests/test_embedding_similarity.py` for unit tests
- Integration tests in `tests/test_tool_retrieval.py`
- Manual testing via `/mcp-tools/match` endpoint

## Docker Profiles

The `docker-compose.yml` uses profiles:
- `ollama` - Ollama service + ollama-setup + ollama-api
- `app` - Redis, Redis API, Transformer services

Use `--profile` to control which services start:
```bash
docker compose --profile ollama up -d          # Ollama only
docker compose --profile app up -d             # RAG services only
docker compose --profile ollama --profile app up -d  # All services
```

Or use Makefile shortcuts: `make up-all`, `make up`, `make up-redis`
