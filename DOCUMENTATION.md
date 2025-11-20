# AI CLI - Comprehensive Documentation

Complete technical documentation for the AI CLI system.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [@ Prefix Feature](#-prefix-feature)
- [MCP Tool System](#mcp-tool-system)
- [RAG Context System](#rag-context-system)
- [Session Management](#session-management)
- [Code Generation](#code-generation)
- [Code Execution](#code-execution)
- [Configuration](#configuration)
- [Docker Services](#docker-services)
- [Development Guide](#development-guide)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         User CLI                            │
│                       (main.py)                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
    ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌──────────────┐
│ Ollama │  │   MCP    │  │    Redis     │
│ Client │  │ System   │  │ RAG Context  │
└────────┘  └──────────┘  └──────────────┘
    │              │              │
    │         ┌────┴────┐         │
    │         ▼         ▼         │
    │    ┌────────┬────────┐     │
    │    │ Coder  │ Custom │     │
    │    │  MCP   │  MCPs  │     │
    │    └────────┴────────┘     │
    │                             │
    ▼                             ▼
┌────────────┐            ┌──────────────┐
│  Ollama    │            │ Redis API +  │
│  Service   │            │ Transformer  │
└────────────┘            └──────────────┘
```

### Core Modules

- **main.py**: Entry point, CLI loop, @ prefix handling, message routing
- **src/config/**: YAML configuration management
- **src/ollama_client/**: Ollama API client with streaming support
- **src/chat/**: Conversation context management
- **src/mcp/**: MCP client for tool execution
- **src/file_completer.py**: @ prefix TAB autocomplete
- **src/utils/tree.py**: Directory tree visualization
- **system_mcps/coder/**: Code execution, file operations, context management

### Data Flow

1. **User Input** → @ prefix parsing → File/directory context extraction
2. **Context Addition** → MCP `add_file_context` → Redis storage + embedding
3. **Content Injection** → System message with file contents → LLM
4. **LLM Response** → Code detection → MCP tool execution
5. **Result Display** → User feedback with formatted output

---

## @ Prefix Feature

### Overview

The @ prefix feature enables instant file and directory context injection with TAB autocomplete.

### Usage Patterns

#### 1. File Context
```bash
▶ @utils/helpers.py what does this file do?
# TAB autocomplete shows files/directories
# File content automatically injected into conversation
```

#### 2. Directory Context
```bash
▶ @src/models/ explain the data models
# Adds all files in directory + ASCII tree structure
# Recursive traversal with size statistics
```

#### 3. Code Generation
```bash
▶ @new_feature.py create a user authentication module
# LLM generates code, automatically writes to new_feature.py
# File creation handled by write_python_code MCP tool
```

#### 4. Working Directory
```bash
▶ @WD analyze the entire project structure
# Special keyword for entire working directory
# Useful for project-wide analysis
```

### How It Works

#### Step 1: Autocomplete
```python
# src/file_completer.py
class AtPrefixFileCompleter(Completer):
    def get_completions(self, document, complete_event):
        # Finds @ prefix in input
        # Lists files/directories from filesystem
        # Yields Completion objects with metadata
```

#### Step 2: Context Extraction
```python
# main.py
at_context = extract_at_context(user_input, os.getcwd())
# Returns: {
#   'files': ['path/to/file1.py', 'path/to/file2.py'],
#   'directories': ['src/models/'],
#   'non_existing': ['new_file.py']  # For code generation
# }
```

#### Step 3: MCP Tool Calls
```python
# Add file context
result = mcp_client.call_tool('coder', 'add_file_context', {
    'file_path': 'utils/helpers.py',
    'working_dir': os.getcwd(),
    'session_id': session_id  # Optional
})

# Add directory context (includes tree)
result = mcp_client.call_tool('coder', 'add_directory_context', {
    'dir_path': 'src/models/',
    'working_dir': os.getcwd(),
    'session_id': session_id
})
```

#### Step 4: Content Injection
```python
# main.py collects content from MCP responses
injected_context_parts = [
    "File: utils/helpers.py\n```python\n<content>\n```",
    "Directory Structure: src/models/\n```\n<tree>\n```"
]

# Injected as system message before user message
system_message = {
    'role': 'system',
    'content': f"The user has provided the following files/directories as context:\n\n{context}"
}
```

### Configuration

No configuration required - works out of the box with current working directory.

**Exclusions** (from tree and directory traversal):
- `.git/`, `__pycache__/`, `node_modules/`, `.venv/`, `venv/`
- `*.pyc`, `*.pyo`, `*.pyd`, `.DS_Store`

---

## MCP Tool System

### Overview

Model Context Protocol (MCP) provides extensible tool execution for the LLM.

### Architecture

```
┌─────────────┐
│   main.py   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     stdio     ┌──────────────┐
│ MCP Client  │◄─────────────►│ MCP Server   │
│ (src/mcp/)  │               │ (coder)      │
└─────────────┘               └──────────────┘
       │                              │
       │                              ▼
       │                      ┌──────────────┐
       │                      │ Tool Handler │
       │                      │ Functions    │
       │                      └──────────────┘
       │                              │
       └──────────Result──────────────┘
```

### Available MCP Servers

#### 1. Coder MCP (`system_mcps/coder/`)

**Tools:**
- `execute_python` - Execute Python code, return output
- `execute_r` - Execute R code, return output
- `detect_code` - Detect language and extract code from text
- `write_python_code` - Create new Python file with code
- `write_r_code` - Create new R file with code
- `edit_python_code` - Edit existing Python file
- `edit_r_code` - Edit existing R file
- `add_file_context` - Add file to RAG context with embeddings
- `add_directory_context` - Add directory to RAG context with tree

### MCP Client Usage

```python
from src.mcp.client import MCPClient

# Initialize
mcp_client = MCPClient(
    system_mcps_dir=Path("system_mcps"),
    postgres_url="http://localhost:15000",
    verbose=True
)

# Initialize tools in database
await mcp_client.initialize_tools_in_db()

# Call tool
result = await mcp_client.call_tool(
    mcp_name='coder',
    tool_name='execute_python',
    arguments={'code': 'print("Hello")'}
)
```

### Creating Custom MCPs

1. Create directory: `system_mcps/my_mcp/`
2. Create `server.py`:

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("my_mcp")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="my_tool",
            description="Description of what this tool does",
            inputSchema={
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "Parameter description"}
                },
                "required": ["param"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "my_tool":
        param = arguments.get("param")
        result = f"Processed: {param}"
        return [TextContent(type="text", text=result)]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

3. MCP automatically discovered and loaded on CLI start

---

## RAG Context System

### Overview

Redis-backed vector embeddings enable semantic search and context persistence.

### Architecture

```
┌──────────────┐
│  File/Dir    │
│  Content     │
└──────┬───────┘
       │
       ▼
┌────────────────┐    HTTP    ┌─────────────────┐
│ add_*_context  │───────────►│   Redis API     │
│   MCP Tool     │            │ (Flask:17000)   │
└────────────────┘            └────────┬────────┘
                                       │
                              ┌────────┼────────┐
                              │        │        │
                              ▼        ▼        ▼
                          ┌───────┬───────┬─────────┐
                          │Embed  │Store  │ Search  │
                          │(API)  │(Redis)│(Cosine) │
                          └───────┴───────┴─────────┘
```

### Redis API Endpoints

**Base URL**: `http://localhost:17000`

#### POST /context/store
Store file/directory context with embeddings.

```json
{
  "context_type": "file",
  "path": "utils/helpers.py",
  "content": "<file content>",
  "session_id": "uuid-string",
  "metadata": {}
}
```

**Response:**
```json
{
  "status": "success",
  "key": "session:uuid:context:utils/helpers.py",
  "embedding_dim": 768
}
```

#### POST /context/search
Search contexts using semantic similarity.

```json
{
  "query": "user authentication functions",
  "top_k": 5,
  "threshold": 0.7,
  "session_id": "uuid-string"
}
```

**Response:**
```json
{
  "results": [
    {
      "path": "auth/user.py",
      "content": "...",
      "similarity": 0.89,
      "context_type": "file"
    }
  ]
}
```

#### GET /context/list
List all stored contexts.

```json
{
  "contexts": [
    {
      "key": "session:uuid:context:file.py",
      "type": "file",
      "size": 1234
    }
  ]
}
```

#### DELETE /context/delete
Delete specific context.

```json
{"path": "utils/helpers.py", "session_id": "uuid"}
```

#### POST /session/clear
Clear all contexts for session.

```json
{"session_id": "uuid"}
```

#### POST /temp/clear
Clear all temporary (non-session) contexts.

### Embedding Model

- **Model**: `sentence-transformers/paraphrase-mpnet-base-v2`
- **Dimensions**: 768
- **Service**: Transformer API (port 18000)
- **Similarity**: Cosine similarity, threshold 0.7

### Redis Keys

- **Session contexts**: `session:{uuid}:context:{path}`
- **Temporary contexts**: `temp:context:{path}` (TTL: 1 hour)
- **Tree structures**: `{path}/__TREE__` (special context type)

### Storage Model

```json
{
  "context_type": "file|directory|directory_tree",
  "path": "relative/path/to/file.py",
  "content": "actual file content",
  "embedding": [0.123, -0.456, ...],  // 768 dimensions
  "metadata": {
    "added_at": "2025-01-15T10:30:00",
    "size": 1234,
    "session_id": "uuid"
  }
}
```

---

## Session Management

### Overview

Sessions maintain conversation context across multiple interactions with automatic history injection.

### Usage

```bash
▶ session start
📝 Session started: abc123de...
   Started at: 14:30:45

▶ What is the capital of France?
▶ Paris

▶ What's the population?  # Context preserved
▶ Paris has approximately 2.2 million people...

▶ session info
📊 Session Info:
  • Session ID: abc123de...
  • Duration: 120s
  • Interactions: 2

▶ session end
✅ Session ended
   Started at: 14:30:45
   Duration: 2m 0s
   Interactions: 2
```

### How It Works

1. **Session Start**: UUID generated, stored in database
2. **Interaction**: Each prompt/response pair stored with session ID
3. **Context Injection**: Last 5 interactions injected as system message
4. **Session End**: Metadata calculated, summary displayed

### Database Schema

```sql
-- PostgreSQL tables
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(20)  -- 'active' or 'ended'
);

CREATE TABLE interactions (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    prompt TEXT,
    response TEXT,
    timestamp TIMESTAMP,
    tool_calls JSONB
);
```

### Configuration

```yaml
# config.yaml
chat:
  max_context_length: 10  # Non-session context limit
  # Session contexts: last 5 interactions (hardcoded)
```

See [docs/SESSION_FEATURE.md](docs/SESSION_FEATURE.md) for detailed documentation.

---

## Code Generation

### Overview

Generate code files directly from LLM responses using @ prefix for non-existing files.

### Usage

```bash
▶ @auth/user.py create a User class with login method
# LLM generates Python code
# Automatically written to auth/user.py
```

### Flow

1. **Detection**: `@auth/user.py` detected as non-existing file
2. **Target Setting**: `target_file = "auth/user.py"`
3. **LLM Instruction**: System message added:
   ```
   The user wants to write code to the file: auth/user.py.
   Generate Python code in a code block that will be automatically written to this file.
   Provide complete, working code that can be directly written to the file.
   ```
4. **Code Extraction**: `detect_code` tool extracts code from response
5. **File Writing**: `write_python_code` or `write_r_code` tool writes file

### Supported Languages

- **Python**: `.py` extension → `write_python_code` tool
- **R**: `.R`, `.r` extensions → `write_r_code` tool

### File Operations

#### Write New File
```python
# MCP Tool: write_python_code
arguments = {
    "file_path": "auth/user.py",
    "code": "class User:\n    pass",
    "working_dir": "/home/user/project"
}
```

#### Edit Existing File
```python
# MCP Tool: edit_python_code
arguments = {
    "file_path": "auth/user.py",
    "code": "class User:\n    def login(self): pass",
    "working_dir": "/home/user/project"
}
```

### Safety Features

- **Path Validation**: Prevents directory traversal attacks
- **Existence Check**: `write_*` tools reject existing files
- **Parent Directory Creation**: Automatically creates missing parent dirs
- **Error Handling**: Detailed error messages for permission/IO issues

---

## Code Execution

### Overview

Execute Python and R code with automatic output capture.

### Usage

```bash
▶ run this code: print("Hello, World!")
# Code automatically executed
# Real output displayed (not predicted)
```

### Execution Flow

1. **Keyword Detection**: `run`, `execute`, `exec` in prompt
2. **LLM Instruction**: System message:
   ```
   The user wants to execute code. Provide ONLY the code in a code block.
   Do NOT predict, guess, or show what the output will be.
   The code will be automatically executed and the real output will be displayed.
   ```
3. **Code Extraction**: `detect_code` tool identifies language and code
4. **Execution**: `execute_python` or `execute_r` tool runs code
5. **Output Display**: stdout/stderr shown to user

### Execution Environments

#### Python
- **Interpreter**: System Python (same as CLI)
- **Timeout**: 30 seconds
- **Working Directory**: Current CLI working directory
- **Output**: Combined stdout + stderr

#### R
- **Command**: `Rscript --vanilla`
- **Timeout**: 30 seconds
- **Working Directory**: Current CLI working directory
- **Output**: Combined stdout + stderr

### Security Considerations

⚠️ **Warning**: Code execution has no sandboxing. Only run trusted code.

- Uses `subprocess` with timeout
- No network restrictions
- No filesystem restrictions
- No resource limits (CPU/memory)

### Error Handling

- **Syntax Errors**: Captured in stderr
- **Runtime Errors**: Captured in stderr
- **Timeout**: Execution killed after 30s
- **No Code**: Error message if no code block detected

---

## Configuration

### config.yaml

```yaml
# Ollama Configuration
ollama:
  url: "http://localhost:11434"
  model: "tinyllama"
  timeout: 120

# Chat Configuration
chat:
  system_prompt: "You are a helpful AI assistant."
  max_context_length: 10
  temperature: 0.7
  stream: true
```

### .env

```bash
# Ollama
OLLAMA_HOST_PORT=11434

# PostgreSQL (Session DB)
POSTGRES_HOST_PORT=15432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_cli

# PostgreSQL API
POSTGRES_API_PORT=15000

# Redis
REDIS_HOST_PORT=26379

# Redis API
REDIS_API_PORT=17000

# Transformer API
TRANSFORMER_API_PORT=18000
```

### Environment Variables Priority

1. Environment variables (highest priority)
2. `.env` file
3. `config.yaml`
4. Defaults (lowest priority)

---

## Docker Services

### Services Overview

| Service | Port | Purpose |
|---------|------|---------|
| Ollama | 11434 | LLM inference |
| PostgreSQL | 15432 | Session database |
| PostgreSQL API | 15000 | Session REST API |
| Redis | 26379 | Context storage |
| Redis API | 17000 | Context REST API |
| Transformer | 18000 | Embedding generation |

### docker-compose.yml

```yaml
services:
  ollama:
    profiles: [ollama]
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

  postgresql:
    profiles: [app]
    image: postgres:15-alpine
    ports:
      - "${POSTGRES_HOST_PORT:-15432}:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-ai_cli}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    profiles: [app]
    image: redis:7-alpine
    ports:
      - "${REDIS_HOST_PORT:-26379}:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  redis-api:
    profiles: [app]
    build:
      context: .
      dockerfile: src/redis/flask-app/Dockerfile
    ports:
      - "${REDIS_API_PORT:-17000}:5000"
    depends_on:
      - redis
      - transformer

  transformer:
    profiles: [app]
    build:
      context: .
      dockerfile: src/transformer/Dockerfile
    ports:
      - "${TRANSFORMER_API_PORT:-18000}:5000"

volumes:
  ollama_data:
  postgres_data:
  redis_data:
```

### Docker Profiles

- **ollama**: Ollama service only
- **app**: All application services (PostgreSQL, Redis, Transformer)

### Starting Services

```bash
# Start all services
make up-all

# Start only Ollama
docker compose --profile ollama up -d

# Start only app services
docker compose --profile app up -d

# Start specific service
docker compose up -d redis
```

### Health Checks

```bash
# Check all services
make status

# Check Redis API
make redis-api-health
curl http://localhost:17000/health

# Check Transformer API
make transformer-health
curl http://localhost:18000/health

# Check PostgreSQL API
curl http://localhost:15000/health
```

---

## Development Guide

### Setting Up Development Environment

```bash
# Clone repository
git clone <repo-url>
cd cli

# Create virtual environment
make venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make install

# Build all Docker images
make build-all-services

# Start all services
make up-all

# Run CLI
make run
```

### Project Layout

```
src/
├── config/              # Configuration management
│   └── __init__.py
├── ollama_client/       # Ollama API client
│   └── __init__.py
├── chat/                # Chat context management
│   └── __init__.py
├── mcp/                 # MCP client system
│   ├── __init__.py
│   └── client.py
├── redis/               # Redis API service
│   └── flask-app/
│       ├── app.py
│       └── Dockerfile
├── utils/               # Utility modules
│   └── tree.py
└── file_completer.py    # @ prefix autocomplete

system_mcps/
└── coder/               # Coder MCP server
    └── server.py

docs/
├── AT_PREFIXER_FEATURE.md
├── SESSION_FEATURE.md
└── MAKEFILE_COMMANDS.md
```

### Adding a New Feature

1. **Create module**: `src/my_feature/`
2. **Implement logic**: `src/my_feature/__init__.py`
3. **Integrate in main**: Import and use in `main.py`
4. **Add tests**: `tests/test_my_feature.py`
5. **Document**: Update `DOCUMENTATION.md`

### Testing

```bash
# Run tests
make test

# Run specific test
pytest tests/test_mcp.py -v

# Run with coverage
pytest --cov=src tests/
```

### Debugging

#### Enable Verbose Mode
```bash
python main.py --verbose
# Or: make run VERBOSE=1
```

#### MCP Debugging
```python
# main.py
mcp_client.set_debug_callback(debug_print)
```

#### Redis Debugging
```bash
# Connect to Redis CLI
make redis-cli

# Show all keys
KEYS *

# Get context
GET session:abc123:context:file.py

# Show stats
INFO keyspace
```

---

## API Reference

### MCP Client

```python
class MCPClient:
    def __init__(
        self,
        system_mcps_dir: Path,
        postgres_url: str,
        verbose: bool = False
    )

    async def initialize_tools_in_db(self) -> None:
        """Register all MCP tools in PostgreSQL database."""

    async def call_tool(
        self,
        mcp_name: str,
        tool_name: str,
        arguments: dict
    ) -> str:
        """Execute MCP tool and return result."""

    async def list_mcps(self) -> list[str]:
        """List all available MCP servers."""

    async def get_tools(self, mcp_name: str) -> list[dict]:
        """Get all tools from specific MCP server."""

    def set_debug_callback(self, callback: Callable) -> None:
        """Set debug output callback."""
```

### File Completer

```python
class AtPrefixFileCompleter(Completer):
    def __init__(self, working_dir: str)

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Generate file/directory completions for @ prefix."""

def parse_at_prefixed_paths(text: str) -> list[str]:
    """Extract all @ prefixed paths from text."""

def extract_at_context(text: str, working_dir: str) -> dict:
    """Categorize @ paths into files, directories, non_existing."""

def remove_at_prefixed_paths(text: str) -> str:
    """Remove all @ prefixed paths from text."""
```

### Tree Utilities

```python
def generate_tree(
    directory: str,
    prefix: str = "",
    max_depth: int = 10
) -> str:
    """Generate ASCII tree structure."""

def generate_tree_summary(
    directory: str,
    max_depth: int = 10
) -> dict:
    """Generate tree with statistics."""
    # Returns: {'tree': str, 'stats': {'files': int, 'directories': int, 'total_size': int}}

def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string (B, KB, MB, GB)."""

def count_items(directory: str) -> tuple[int, int, int]:
    """Count files, directories, and total size."""
```

### Session Manager

```python
class SessionManager:
    def start_session(self) -> str:
        """Start new session, return session ID."""

    def end_session(self) -> dict:
        """End current session, return summary."""

    def is_active(self) -> bool:
        """Check if session is active."""

    def get_session_id(self) -> str:
        """Get current session ID."""

    def add_interaction(self, prompt: str, response: str) -> None:
        """Add interaction to session."""

    def get_session_context(self, max_interactions: int = 5) -> str:
        """Get formatted context from last N interactions."""

    def get_session_info(self) -> dict:
        """Get current session information."""
```

---

## Troubleshooting

### @ Prefix Not Working

**Symptoms**: TAB doesn't show file completions

**Solutions**:
1. Ensure `prompt_toolkit` is installed: `pip install prompt_toolkit`
2. Check working directory: Files must exist in current directory
3. Restart CLI to reload file completer

### File Content Not Showing in LLM

**Symptoms**: LLM says "I don't see any code"

**Solutions**:
1. **Restart CLI** - Code changes require process restart
2. Check Redis API is running: `make redis-api-health`
3. Check file was added: `make redis-cli` → `KEYS *`
4. Enable verbose mode: `python main.py --verbose`

### Redis Connection Failed

**Symptoms**: `Failed to add file context`, connection errors

**Solutions**:
1. Start Redis services: `make up-redis`
2. Check Redis is running: `docker compose ps redis`
3. Check Redis API: `make redis-api-health`
4. Check ports in `.env`: `REDIS_HOST_PORT`, `REDIS_API_PORT`

### Transformer API Not Working

**Symptoms**: Embedding generation fails

**Solutions**:
1. Start transformer: `docker compose up -d transformer`
2. Check health: `curl http://localhost:18000/health`
3. Check logs: `docker compose logs transformer`
4. Rebuild if needed: `docker compose build transformer`

### Code Execution Timeout

**Symptoms**: Code execution stops after 30 seconds

**Solutions**:
1. Optimize code to run faster
2. Increase timeout in `system_mcps/coder/server.py`:
   ```python
   result = subprocess.run(..., timeout=60)  # 60 seconds
   ```

### MCP Tool Not Found

**Symptoms**: `Unknown tool '<tool_name>'`

**Solutions**:
1. List available tools: Type `mcps` in CLI
2. Check tool details: Type `mcp-tools coder`
3. Restart CLI to reload MCPs
4. Check MCP server logs: Look for errors in CLI verbose mode

### Session Database Issues

**Symptoms**: Session commands fail, database errors

**Solutions**:
1. Run migrations: `make migrate-session`
2. Check PostgreSQL: `docker compose ps postgresql`
3. Check PostgreSQL API: `curl http://localhost:15000/health`
4. Reset database: `docker compose down -v postgresql && make up-all`

### Docker Build Failures

**Symptoms**: `docker compose build` fails

**Solutions**:
1. Clean Docker cache: `docker system prune -a`
2. Rebuild without cache: `docker compose build --no-cache`
3. Check Dockerfile syntax
4. Check internet connection (for package downloads)

### Port Already in Use

**Symptoms**: `bind: address already in use`

**Solutions**:
1. Check what's using port: `lsof -i :PORT` (Linux/Mac) or `netstat -ano | findstr :PORT` (Windows)
2. Change port in `.env`: `REDIS_HOST_PORT=26380`
3. Stop conflicting service
4. Restart Docker: `docker compose down && make up-all`

### Permission Denied Errors

**Symptoms**: Can't write files, access denied

**Solutions**:
1. Check file permissions: `ls -la`
2. Run with correct user: `docker compose up --user $(id -u):$(id -g)`
3. Fix volume permissions: `sudo chown -R $USER:$USER .`

---

## Additional Resources

- **@ Prefixer Feature**: [docs/AT_PREFIXER_FEATURE.md](docs/AT_PREFIXER_FEATURE.md)
- **Session Management**: [docs/SESSION_FEATURE.md](docs/SESSION_FEATURE.md)
- **Makefile Commands**: [docs/MAKEFILE_COMMANDS.md](docs/MAKEFILE_COMMANDS.md)
- **Ollama Documentation**: https://ollama.ai/
- **MCP Specification**: https://modelcontextprotocol.io/

---

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes and test thoroughly
4. Update documentation
5. Commit: `git commit -m "feat: add my feature"`
6. Push: `git push origin feature/my-feature`
7. Create Pull Request

## License

See LICENSE file for details.
