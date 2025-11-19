# AI CLI - Ollama-Powered Chat Interface

A minimal, modular AI command-line interface that connects to Ollama services (local or remote) for interactive AI conversations.

## Features

- 🤖 Connect to local or remote Ollama services
- 💬 Interactive chat with AI models
- ⚙️ Configurable via YAML file
- 🔄 Streaming and non-streaming response modes
- 📝 Conversation context management
- 🎯 Modular architecture with separated features
- 🐳 Docker Compose setup for Ollama
- 🚀 Easy setup with automated shell script

## Project Structure

```
cli/
├── config.yaml              # Configuration file for Ollama and chat settings
├── docker-compose.yml       # Docker Compose for Ollama service
├── .env.example            # Environment variables template
├── requirements.txt         # Python dependencies
├── start.sh                # Shell script to setup and run the CLI
├── main.py                 # Main entry point
└── src/
    ├── config/             # Configuration management module
    │   └── __init__.py
    ├── ollama_client/      # Ollama client module
    │   └── __init__.py
    └── chat/               # Chat management module
        └── __init__.py
```

## Prerequisites

- Python 3.7 or higher
- Docker and Docker Compose (for running Ollama in a container)

## Installation

### Option 1: Using Docker Compose (Recommended)

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
- **Clear history:** Type `clear` to reset the conversation
- **List models:** Type `models` to see available Ollama models
- **Exit:** Type `exit` or `quit` to close the CLI

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

## Docker Compose Management

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