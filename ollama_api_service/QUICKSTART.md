# Ollama++ API - Quick Start Guide

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose installed
- At least 4GB free disk space
- Port 8080 available (configurable)

### Step 1: Start the Services

```bash
# From the project root directory (/home/user/cli/)
docker compose --profile ollama --profile app --profile api up -d
```

This will start:
- Ollama (LLM runtime)
- PostgreSQL (tool storage)
- Redis (vector storage)
- Transformer (embeddings)
- **Ollama API** (new service!)

### Step 2: Verify the Service

```bash
# Check if the API is running
curl http://localhost:8080/health

# Expected output:
{
  "status": "healthy",
  "ollama": "connected",
  "models_available": 1,
  "mcp_tools": 11
}
```

### Step 3: Test with a Simple Chat

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

### Step 4: Use with OpenWebUI

```bash
# Install OpenWebUI
docker run -d \
  -p 3000:8080 \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --add-host=host.docker.internal:host-gateway \
  ghcr.io/open-webui/open-webui:main

# Open http://localhost:3000 in your browser
# Go to Settings → Connections
# Set Ollama API URL to: http://host.docker.internal:8080
# Click "Verify Connection"
# Start chatting!
```

## 📖 Common Operations

### List Available Models

```bash
curl http://localhost:8080/api/tags
```

### Chat with Streaming

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [{"role": "user", "content": "Count to 10"}],
    "stream": true
  }'
```

### Upload a File

```bash
curl -X POST http://localhost:8080/api/files/upload \
  -F "files=@mydata.csv" \
  -F "auto_inject=true"

# Returns session_id and @reference path
# Then use in chat:
curl -X POST http://localhost:8080/api/chat/with-files \
  -F "message=Analyze @mydata.csv" \
  -F "files=@mydata.csv" \
  -F "stream=false"
```

### Execute Python Code

```bash
curl -X POST http://localhost:8080/api/code/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(\"Hello from Python!\")\nprint(2 + 2)",
    "language": "python"
  }'
```

### List Available MCP Tools

```bash
curl http://localhost:8080/api/tools/list
```

### Find Relevant Tools

```bash
curl -X POST http://localhost:8080/api/tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "I want to run some Python code",
    "top_k": 3
  }'
```

## 🔍 Troubleshooting

### Service won't start

```bash
# Check logs
docker compose logs ollama-api

# Common issues:
# 1. Port 8080 already in use
#    Solution: Change OLLAMA_API_PORT in .env

# 2. Ollama service not healthy
#    Solution: docker compose logs ollama

# 3. Missing dependencies
#    Solution: docker compose build --no-cache ollama-api
```

### OpenWebUI can't connect

```bash
# Make sure the API is accessible
curl http://localhost:8080/health

# If using Docker Desktop on Mac/Windows, use:
# http://host.docker.internal:8080

# If on Linux, use:
# http://172.17.0.1:8080
# or the actual IP of the host
```

### MCP tools not working

```bash
# Check if MCP client initialized
curl http://localhost:8080/api/tools/health

# If unhealthy, check system_mcps directory is mounted:
docker compose exec ollama-api ls -la /app/system_mcps
```

## 📚 Next Steps

1. Read the full [README.md](./README.md) for all features
2. Check [API Documentation](http://localhost:8080/docs) (Swagger UI)
3. Try the [example scripts](./examples/)
4. Integrate with your applications using the OpenAI-compatible endpoint

## 🔧 Configuration

Edit `.env` file in project root:

```bash
# Copy from example
cp .env.example .env

# Edit as needed
nano .env

# Key settings:
OLLAMA_API_PORT=8080          # API port
OLLAMA_API_URL=...            # Ollama service URL
MCP_DEBUG=false               # Enable MCP debug logs
```

Then restart:

```bash
docker compose down
docker compose --profile ollama --profile app --profile api up -d
```

## 🎯 Key Features at a Glance

| What | How | Example |
|------|-----|---------|
| **Standard Ollama** | Just works! | Use with any Ollama client |
| **OpenWebUI** | Point to port 8080 | Full compatibility |
| **File Upload** | `/api/files/upload` | Upload & reference with @ |
| **Code Execution** | `/api/code/execute` | Run Python/R safely |
| **Tool Discovery** | `/api/tools/retrieve` | Semantic search |
| **RAG Context** | `/api/context/add` | Inject custom context |
| **OpenAI Format** | `/v1/chat/completions` | Drop-in replacement |

---

**Need help?** Check the logs: `docker compose logs -f ollama-api`
