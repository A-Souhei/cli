# AI CLI - Ollama-Powered Chat Interface

A minimal, modular AI command-line interface that connects to Ollama services (local or remote) for interactive AI conversations.

## Features

- 🤖 Connect to local or remote Ollama services
- 💬 Interactive chat with AI models
- 📁 **@ Prefix Autocomplete** - TAB completion for files/directories with automatic context injection
- 🔍 **RAG Context System** - Redis-backed vector embeddings for semantic search
- 🌳 **Directory Tree Visualization** - ASCII tree structure for directory context
- 🐍 **Code Generation** - Write Python/R code to files automatically
- 📝 **MCP Tool System** - Modular Context Protocol for extensible operations
- 📚 **Session Management** - Context-persistent conversations with history injection
- ⚡ **Code Execution** - Run Python/R code with automatic output capture
- ⚙️ Configurable via YAML file
- 🔄 Streaming and non-streaming response modes
- 🐳 Docker Compose with Redis, PostgreSQL, Transformer services
- 🚀 Easy setup with automated scripts and Makefile

## Quick Start

```bash
# Automated setup (recommended)
make setup

# Build and start all services (Ollama, Redis, Transformer, PostgreSQL)
make build-all-services
make up-all

# Run the CLI
make run
# Or: ./start.sh
```

See [DOCUMENTATION.md](DOCUMENTATION.md) for detailed guides and [docs/](docs/) for specific features.

## Project Structure

```
cli/
├── config.yaml              # Configuration for Ollama and chat
├── docker-compose.yml       # Multi-service Docker setup
├── Makefile                # Build automation and commands
├── main.py                 # Main entry point
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── docs/                   # Feature documentation
│   ├── AT_PREFIXER_FEATURE.md
│   ├── SESSION_FEATURE.md
│   └── MAKEFILE_COMMANDS.md
├── src/                    # Core modules
│   ├── config/             # Configuration management
│   ├── ollama_client/      # Ollama client
│   ├── chat/               # Chat management
│   ├── mcp/                # MCP client system
│   ├── redis/              # Redis API service
│   │   └── flask-app/      # Flask API for embeddings
│   ├── utils/              # Utilities (tree, etc.)
│   └── file_completer.py   # @ prefix autocomplete
├── system_mcps/            # MCP tool servers
│   └── coder/              # Code execution & file tools
└── testing/                # Test applications
    ├── python_app/         # Python test structure
    └── r_app/              # R test structure
```

## Prerequisites

- Python 3.7 or higher
- Docker and Docker Compose (for running Ollama in a container)
- Make (optional, for using Makefile commands)

## Installation

### Quick Setup (Recommended)

```bash
# Run automated setup
make setup
# Or: ./setup.sh

# This will:
# - Create Python virtual environment
# - Install all dependencies
# - Create .env file
# - Optionally start Docker containers
```

### Option 1: Using Docker Compose

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd cli
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Start Ollama service:**
   ```bash
   docker compose --profile ollama up -d
   ```
   
   This will:
   - Start the Ollama service in a container
   - Automatically pull the `tinyllama` model (~1GB, CPU-friendly)
   - Create a persistent volume for model storage

4. **Wait for model download (first time only):**
   ```bash
   docker compose logs -f ollama-setup
   ```
   Wait until you see "Ollama setup complete!"

5. **Run the CLI:**
   ```bash
   ./start.sh
   ```

### Option 2: Using Local Ollama Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd cli
   ```

2. **Install Ollama locally:**
   Follow instructions at [https://ollama.ai/](https://ollama.ai/)

3. **Pull a model:**
   ```bash
   ollama pull tinyllama  # or llama2, mistral, etc.
   ```

4. **Configure the CLI:**
   Edit `config.yaml` to set your Ollama service URL and preferred model:
   ```yaml
   ollama:
     url: "http://localhost:11434"  # Change for remote Ollama
     model: "tinyllama"             # Change to your preferred model
     timeout: 120
   
   chat:
     system_prompt: "You are a helpful AI assistant."
     max_context_length: 10
     temperature: 0.7
     stream: true
   ```

5. **Run the CLI:**
   ```bash
   ./start.sh
   ```

   The script will automatically:
   - Create a Python virtual environment
   - Install all required dependencies
   - Start the AI CLI

## Usage

Once the CLI starts, you can:

- **Chat with AI:** Simply type your message and press Enter
- **@ Prefix for files:** Type `@filename` + TAB for autocomplete, automatically adds file context
- **@ Prefix for directories:** Type `@dirname/` to add entire directory with tree visualization
- **Generate code:** Type `@newfile.py <description>` to generate code directly to file
- **Clear history:** Type `clear` to reset the conversation
- **List models:** Type `models` to see available Ollama models
- **Switch model:** Type `switch` to change the current model
- **MCP tools:** Type `mcps` to list available tools, `mcp-tools <name>` for tool details
- **Session commands:**
  - `session start` - Start a context-persistent session
  - `session end` - End the current session
  - `session info` - Display current session information
- **Exit:** Type `exit` or `quit` to close the CLI

### Session Feature

The session feature allows you to maintain conversation context across multiple prompts by automatically injecting previous interactions as context. When a session is active, the last 5 interactions are automatically included as context, enabling coherent multi-turn conversations.

**Example:**
```
▶ session start
📝 Session started at 14:30:45

▶ What is the capital of France?
▶ Paris

▶ What's the population of that city?
▶ Paris has approximately 2.2 million people...
# AI understands "that city" refers to Paris

▶ session end
✅ Session ended (started at 14:30:45, 2 interactions)
```

See [docs/SESSION_FEATURE.md](docs/SESSION_FEATURE.md) for detailed documentation.

### Example Session

```
==================================================
  AI CLI - Powered by Ollama
==================================================
Type 'exit' or 'quit' to exit
Type 'clear' to clear chat history
Type 'models' to list available models
==================================================

Using model: tinyllama
Connected to: http://localhost:11434

You: Hello! Can you help me with Python?
AI: Of course! I'd be happy to help you with Python...

You: exit
Goodbye!
```

## Makefile Commands

The project includes a Makefile for easy management:

```bash
# Show all available commands
make help

# Setup
make setup                    # Complete setup (venv + dependencies + Docker)
make venv                     # Create virtual environment
make install                  # Install Python dependencies

# Build & Run
make build-all-services       # Build all Docker images
make up-all                   # Start all services (Ollama + Redis + Transformer + PostgreSQL)
make up-redis                 # Start only Redis services
make run                      # Run the CLI

# Docker Management
make down                     # Stop Docker containers
make restart                  # Restart Docker containers
make logs                     # View container logs
make status                   # Show container status

# Redis Management
make build-redis              # Build Redis API image
make redis-logs               # Show Redis API logs
make redis-cli                # Execute Redis CLI
make redis-clear              # Clear all Redis data (with confirmation)
make redis-info               # Show Redis statistics
make redis-api-health         # Check Redis API health

# Database
make migrate-session          # Apply session database migration
make update-schema            # Update PostgreSQL schema

# Ollama
make pull-model MODEL=llama2  # Pull a specific model
make list-models              # List available models

# Cleanup
make clean                    # Remove venv and volumes
```

See [docs/MAKEFILE_COMMANDS.md](docs/MAKEFILE_COMMANDS.md) for detailed command documentation.

## Docker Compose Management

### Using Makefile (Recommended):

```bash
# Start Ollama
make up

# Stop Ollama
make down

# View logs
make logs

# Check status
make status
```

### Using Docker Compose directly:

### Start Ollama service:
```bash
docker compose --profile ollama up -d
```

### Stop Ollama service:
```bash
docker compose --profile ollama down
```

### View Ollama logs:
```bash
docker compose logs -f ollama
```

### Check service status:
```bash
docker compose ps
```

### Remove volumes (delete downloaded models):
```bash
docker compose down -v
```

## Configuration Options

### Ollama Settings

- `url`: Ollama service URL (default: `http://localhost:11434`)
- `model`: AI model to use (e.g., tinyllama, llama2, mistral, codellama)
- `timeout`: Request timeout in seconds (default: 120)

### Chat Settings

- `system_prompt`: Initial prompt to guide AI behavior
- `max_context_length`: Number of messages to keep in context (default: 10)
- `temperature`: Response randomness, 0.0-1.0 (default: 0.7)
- `stream`: Enable streaming responses (default: true)

## Manual Setup (Alternative)

If you prefer to set up manually instead of using `start.sh`:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the CLI
python main.py
```

## Troubleshooting

### Ollama Connection Issues

**Using Docker Compose:**
- Ensure Ollama container is running: `docker compose ps`
- Check container logs: `docker compose logs ollama`
- Verify the service is healthy: `docker compose ps` (should show "healthy")
- Restart the service: `docker compose restart ollama`

**Using Local Installation:**
- Ensure Ollama is running: `ollama serve`
- Verify the URL in `config.yaml` matches your Ollama service
- For remote Ollama, ensure network connectivity

### Model Not Found

**Using Docker Compose:**
- Check if setup container completed: `docker compose logs ollama-setup`
- Manually pull a model: `docker compose exec ollama ollama pull tinyllama`
- List available models: `docker compose exec ollama ollama list`

**Using Local Installation:**
- Pull the model: `ollama pull <model-name>`
- Update `config.yaml` with the correct model name
- Use the `models` command in the CLI to see available models

### Docker Compose Issues

- Ensure Docker and Docker Compose are installed
- Check if ports are available (default: 11434)
- View all logs: `docker compose logs`
- Recreate containers: `docker compose down && docker compose --profile ollama up -d`

## Development

The project uses a modular architecture:

- **Config Module** (`src/config/`): Handles configuration loading and management
- **Ollama Client Module** (`src/ollama_client/`): Manages communication with Ollama
- **Chat Module** (`src/chat/`): Handles conversation context and message management

## License

See LICENSE file for details.