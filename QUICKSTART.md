# Quick Start Guide

## Using Docker Compose (Recommended)

### 1. Start Ollama Service

```bash
# Copy environment file
cp .env.example .env

# Start Ollama with Docker Compose
docker compose --profile ollama up -d

# Monitor the setup process (first time only)
docker compose logs -f ollama-setup
```

Wait until you see "Ollama setup complete!" in the logs.

### 2. Run the AI CLI

```bash
./start.sh
```

### 3. Start Chatting!

The CLI will start and you can begin chatting with the AI:

```
You: Hello! What can you help me with?
AI: [Response from tinyllama model]
```

### Available Commands

- `clear` - Reset conversation history
- `models` - List available models  
- `exit` or `quit` - Exit the CLI

## Docker Compose Commands

```bash
# Start Ollama
docker compose --profile ollama up -d

# Stop Ollama
docker compose --profile ollama down

# View logs
docker compose logs -f ollama

# Check status
docker compose ps

# Restart Ollama
docker compose restart ollama

# Pull additional models
docker compose exec ollama ollama pull llama2
docker compose exec ollama ollama pull mistral

# List models in container
docker compose exec ollama ollama list
```

## Switching Models

1. Pull a new model:
   ```bash
   docker compose exec ollama ollama pull llama2
   ```

2. Update `config.yaml`:
   ```yaml
   ollama:
     model: "llama2"
   ```

3. Restart the CLI

## Troubleshooting

**Container won't start:**
```bash
docker compose logs ollama
```

**Model not found:**
```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama pull tinyllama
```

**Port already in use:**
Edit `.env` and change `OLLAMA_HOST_PORT` to a different port.

**Reset everything:**
```bash
docker compose down -v
docker compose --profile ollama up -d
```
