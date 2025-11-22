# Ollama++ API Service

**Ollama-compatible API with enhanced features** - Drop-in Ollama replacement with MCP tools, RAG, code execution, and file upload support.

## 🎯 Overview

This service provides a fully compatible Ollama API that works with:
- ✅ **OpenWebUI** - Direct integration
- ✅ **Standard Ollama clients** - No changes needed
- ✅ **OpenAI API clients** - Via compatibility layer

**Plus unique enhancements:**
- 🛠️ **MCP Tools** - 11 built-in tools for code execution, file operations, RAG
- 🔍 **Intelligent Tool Matching** - Semantic search with embeddings
- 📝 **Code Execution** - Sandboxed Python/R execution
- 📎 **File Upload with @ Prefix** - Upload files and reference them like the CLI
- 🧠 **RAG Context** - Automatic embedding and semantic search
- 🎯 **Multi-step Orchestration** - Break down complex tasks automatically

## 🚀 Quick Start

### Start with Docker Compose

```bash
# Start all services including Ollama API
docker-compose --profile ollama --profile app --profile api up -d

# Or just the API service (if others are already running)
docker-compose up -d ollama-api
```

The API will be available at: `http://localhost:8080`

### Using with OpenWebUI

1. Install OpenWebUI:
```bash
docker run -d -p 3000:8080 -v open-webui:/app/backend/data --name open-webui ghcr.io/open-webui/open-webui:main
```

2. Configure OpenWebUI to use this API:
   - Open OpenWebUI at `http://localhost:3000`
   - Go to Settings → Connections
   - Set Ollama API URL to: `http://host.docker.internal:8080`
   - Click "Verify Connection"

3. Start chatting with all the enhanced features!

## 📚 API Endpoints

### Standard Ollama Endpoints (OpenWebUI Compatible)

#### POST /api/chat
Chat with streaming support (identical to Ollama)

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "stream": true
  }'
```

#### POST /api/generate
Generate text from prompt (identical to Ollama)

```bash
curl -X POST http://localhost:8080/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "prompt": "Why is the sky blue?",
    "stream": false
  }'
```

#### GET /api/tags
List available models

```bash
curl http://localhost:8080/api/tags
```

### OpenAI Compatible Endpoints

#### POST /v1/chat/completions
OpenAI-compatible chat endpoint

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "stream": false
  }'
```

#### GET /v1/models
List models in OpenAI format

```bash
curl http://localhost:8080/v1/models
```

### Enhanced Endpoints (Unique Features)

#### POST /api/files/upload
Upload files with @ prefix references

```bash
curl -X POST http://localhost:8080/api/files/upload \
  -F "files=@data.csv" \
  -F "files=@script.py" \
  -F "session_id=my-session" \
  -F "auto_inject=true"
```

Response:
```json
{
  "success": true,
  "session_id": "my-session",
  "files": [
    {
      "filename": "data.csv",
      "at_reference": "@data.csv",
      "size": 1234,
      "auto_injected": true
    }
  ],
  "usage_example": "Now you can reference these files in chat with '@data.csv'"
}
```

#### POST /api/chat/with-files
Chat with file attachments in one request

```bash
curl -X POST http://localhost:8080/api/chat/with-files \
  -F "message=Analyze the data in @data.csv" \
  -F "files=@data.csv" \
  -F "model=llama3.1:8b" \
  -F "stream=false"
```

#### GET /api/tools/list
List all available MCP tools

```bash
curl http://localhost:8080/api/tools/list
```

Response:
```json
{
  "success": true,
  "tools": [
    {
      "name": "run_python_code",
      "description": "Execute Python code",
      "mcp_server": "coder",
      "parameters": {...}
    },
    ...
  ],
  "count": 11
}
```

#### POST /api/tools/execute
Execute an MCP tool

```bash
curl -X POST http://localhost:8080/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "run_python_code",
    "arguments": {
      "code": "print(2 + 2)"
    }
  }'
```

#### POST /api/tools/retrieve
Find relevant tools using semantic search

```bash
curl -X POST http://localhost:8080/api/tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "I want to execute some Python code",
    "top_k": 3,
    "threshold": 0.5
  }'
```

#### POST /api/code/execute
Execute code in sandbox

```bash
curl -X POST http://localhost:8080/api/code/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import pandas as pd\nprint(pd.DataFrame({\"a\": [1,2,3]}))",
    "language": "python"
  }'
```

#### POST /api/orchestrate
Multi-step task orchestration

```bash
curl -X POST http://localhost:8080/api/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Read data.csv, analyze it, and create a visualization",
    "max_steps": 10,
    "enable_code_generation": true
  }'
```

#### POST /api/context/add
Add content to RAG context

```bash
curl -X POST http://localhost:8080/api/context/add \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Important context information...",
    "path": "@context.txt",
    "session_id": "my-session"
  }'
```

### Health & Info

#### GET /
Service information

#### GET /health
Health check with diagnostics

```bash
curl http://localhost:8080/health
```

## 🔧 Configuration

The service uses the same `config.yaml` as the CLI:

```yaml
ollama:
  url: "http://ollama:11434"
  model: "llama3.1:8b"
  timeout: 120

chat:
  system_prompt: "You are a helpful AI assistant with access to tools."
  max_context_length: 10
  temperature: 0.7
  stream: true
```

Environment variables (set in docker-compose.yml):

- `OLLAMA_API_PORT` - API port (default: 8080)
- `OLLAMA_API_URL` - Ollama service URL
- `POSTGRES_API_URL` - PostgreSQL API URL
- `TRANSFORMER_API_URL` - Transformer service URL
- `REDIS_API_URL` - Redis API URL
- `MCP_DEBUG` - Enable MCP debug logging

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│  Ollama API Service (FastAPI)       │
│  Port: 8080                          │
│                                      │
│  ┌────────────────────────────────┐ │
│  │ Standard Ollama Endpoints      │ │
│  │ /api/chat, /api/generate       │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │ OpenAI Compatible              │ │
│  │ /v1/chat/completions           │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │ Enhanced Features              │ │
│  │ Files, Tools, Code, RAG        │ │
│  └────────────────────────────────┘ │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐         ┌─────▼─────┐
│ Ollama │         │ CLI src/  │
│ LLM    │         │ (mounted) │
└────────┘         └─────┬─────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         ┌────▼────┐          ┌────▼────┐
         │ MCP     │          │ RAG     │
         │ Tools   │          │ Context │
         └─────────┘          └─────────┘
```

## 📖 Documentation

Interactive API documentation is available at:

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## 🎯 Use Cases

### 1. Drop-in Ollama Replacement
Use with any Ollama-compatible client (OpenWebUI, Ollama Python library, etc.)

### 2. OpenAI API Compatibility
Switch from OpenAI to local LLM without code changes

### 3. Code Execution Platform
Execute Python/R code safely with LLM assistance

### 4. RAG Applications
Upload documents and query them with semantic search

### 5. Multi-Agent Workflows
Orchestrate complex tasks with tool chaining

### 6. File Processing
Upload files via API and reference with @ prefix

## 🔒 Security Notes

- Files uploaded via `/api/files/upload` are limited to 10KB for context injection
- Code execution happens in the same environment as the MCP server (not fully sandboxed)
- Consider adding authentication for production use
- CORS is enabled for all origins (configure as needed in `app.py`)

## 🛠️ Development

### Local Testing (without Docker)

```bash
cd ollama_api_service

# Install dependencies
pip install -r requirements.txt

# Set Python path
export PYTHONPATH=/home/user/cli:$PYTHONPATH

# Run the server
python app.py
```

Server runs at: http://localhost:8080

### Rebuild Docker Image

```bash
docker-compose build ollama-api
docker-compose up -d ollama-api
```

### View Logs

```bash
docker-compose logs -f ollama-api
```

## 🎉 Features Summary

| Feature | Ollama | Ollama++ API |
|---------|--------|--------------|
| Chat API | ✅ | ✅ |
| Streaming | ✅ | ✅ |
| Model listing | ✅ | ✅ |
| OpenWebUI compatible | ✅ | ✅ |
| OpenAI compatible | ❌ | ✅ |
| File upload | ❌ | ✅ |
| @ prefix references | ❌ | ✅ |
| MCP tools (11) | ❌ | ✅ |
| Code execution | ❌ | ✅ |
| RAG context | ❌ | ✅ |
| Tool matching | ❌ | ✅ |
| Orchestration | ❌ | ✅ |

## 📝 License

Same as the main CLI project.

## 🤝 Contributing

This service follows the **GOLDEN RULE**: Never modify CLI code!

All new features go into `ollama_api_service/` directory only.
