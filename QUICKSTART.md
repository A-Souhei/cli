# Quick Start Guide

## Automated Setup (Easiest)

```bash
# Run the automated setup
make setup
# Or: ./setup.sh

# Run the CLI
make run
# Or: ./start.sh
```

## Using Makefile Commands (Recommended)

### 1. Setup and Start

```bash
# Complete setup (venv + dependencies + Docker)
make setup

# Start Ollama containers
make up

# Monitor setup progress
make logs
```

### 2. Run the CLI

```bash
make run
```

### 3. Manage Services

```bash
# View all available commands
make help

# Stop containers
make down

# Restart containers
make restart

# Check container status
make status

# Run tests
make test
```

## Using Docker Compose (Manual)

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

### Available CLI Commands

- `clear` - Reset conversation history
- `models` - List available models  
- `exit` or `quit` - Exit the CLI

## Makefile Commands Reference

```bash
# Show all available commands
make help

# Setup
make setup          # Complete setup (venv + dependencies + Docker)
make venv           # Create virtual environment only
make install        # Install dependencies only

# Running
make run            # Run the CLI
make test           # Run tests

# Docker Management
make up             # Start Ollama containers
make down           # Stop Ollama containers
make restart        # Restart containers
make logs           # View container logs
make status         # Show container status

# Model Management
make pull-model MODEL=llama2    # Pull a specific model
make list-models                # List available models

# Cleanup
make clean          # Remove venv and volumes
```

## Docker Compose Commands (Direct)

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
   # Using Makefile
   make pull-model MODEL=llama2
   
   # Or using Docker Compose directly
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
# Using Makefile
make logs

# Or directly
docker compose logs ollama
```

**Model not found:**
```bash
# Using Makefile
make list-models
make pull-model MODEL=tinyllama

# Or directly
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
