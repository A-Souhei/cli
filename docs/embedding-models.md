# Embedding Models Documentation

## Overview

The AI CLI supports dynamic embedding model configuration, allowing you to use external embedding services while maintaining a local transformer service as a fallback. This provides flexibility in choosing embedding providers based on your needs.

## Architecture

### Components

1. **ModelRegistry** (`src/model_registry/manager.py`)
   - Stores model configurations in Redis
   - Supports three model types: `general`, `coder`, and `embedding`
   - Tracks embedding dimensions and active models

2. **EmbeddingClient** (`src/embedding_client/client.py`)
   - Abstraction layer for embedding generation
   - Automatic fallback to local transformer service
   - Auto-detects embedding dimensions
   - Handles errors gracefully with Sentry integration

3. **Consumers**
   - PostgreSQL API: MCP tool embeddings
   - Redis API: RAG context embeddings
   - Ratings system: Similarity calculations

## Default Configuration

By default, the CLI uses the local transformer service:
- **Service**: Sentence-Transformers `all-MiniLM-L6-v2`
- **Port**: 16050 (configurable via `TRANSFORMER_API_URL`)
- **Dimensions**: 384
- **Characteristics**: Lightweight (80MB), CPU-friendly

## Adding External Embedding Services

### CLI Command

```bash
/model embedding add <url> [model_name] [timeout]
```

**Parameters**:
- `<url>`: URL of the embedding service (e.g., `http://localhost:8000`)
- `[model_name]`: *(Optional)* Name of the embedding model to use (required for Ollama services; ignored for others)
- `[timeout]`: *(Optional)* Timeout in seconds (default: 60)

**Example**:
```bash
# Add an external embedding service
/model embedding add http://localhost:8000 120

# Service is tested automatically:
# - Sends test embedding request
# - Auto-detects dimensions
# - Stores configuration in Redis
# - Sets as active embedding model
```

### API Protocol

External embedding services must support the following endpoint:

#### POST /embed

**Request (Single Text)**:
```json
{
  "text": "sample text to embed"
}
```

**Request (Batch)**:
```json
{
  "texts": ["text1", "text2", "text3"]
}
```

**Response (Single)**:
```json
{
  "embedding": [0.1, 0.2, 0.3, ...],
  "dimensions": 384
}
```

**Response (Batch)**:
```json
{
  "embeddings": [
    [0.1, 0.2, 0.3, ...],
    [0.4, 0.5, 0.6, ...]
  ],
  "dimensions": 384
}
```

**Notes**:
- `dimensions` field is optional but recommended
- Dimensions will be auto-detected from the first embedding if not provided
- HTTP status 200 indicates success

## Managing Embedding Models

### List Models

```bash
# List all models (including embeddings)
/model list

# List only embedding models
/model embedding list
```

### View Status

```bash
/model status
```

Shows:
- Active embedding model (if configured)
- Fallback status (local transformer)
- Embedding dimensions
- Model ID

### Switch Models

```bash
# Switch to a different embedding model
/model embedding use <model_id>

# Get model ID from /model embedding list
```

### Remove Models

```bash
# Remove an embedding model
/model embedding remove <model_id>

# Automatically falls back to local transformer
```

## Fallback Behavior

The EmbeddingClient implements intelligent fallback:

1. **No External Model**: Uses local transformer service
2. **External Service Fails**: Falls back to local transformer
3. **Dimension Mismatch**: Warns user but continues
4. **Both Services Fail**: Raises RuntimeError

### Example Flow

```
┌─────────────────┐
│ User Request    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Active    │     ┌──────────────────┐
│ Embedding Model │────▶│ External Service │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         │ No Model             │ Success
         │ Configured           │
         ▼                       ▼
┌─────────────────┐     ┌──────────────────┐
│ Local           │     │ Return           │
│ Transformer     │     │ Embedding        │
└────────┬────────┘     └──────────────────┘
         │
         │ Failure              ┌──────────────────┐
         ├─────────────────────▶│ RuntimeError     │
         │                      └──────────────────┘
         │ Success
         ▼
┌─────────────────┐
│ Return          │
│ Embedding       │
└─────────────────┘
```

## Dimension Handling

### Auto-Detection

Embedding dimensions are automatically detected on the first successful embedding call:

```python
# First call with new model
embedding = embedding_client.embed("test text")

# Dimensions detected and stored
# Model registry updated automatically
```

### Dimension Mismatches

If you switch between models with different dimensions:

1. **Warning Issued**: System warns about dimension mismatch
2. **Continues Operation**: Embedding still generated
3. **User Action Required**: Consider clearing stored embeddings if switching permanently

**Example Warning**:
```
⚠️  Embedding dimension mismatch! Expected 384, got 768.
This may cause issues with existing stored embeddings.
```

### Best Practices

- **Consistent Dimensions**: Use models with same dimensions when possible
- **Clear Before Switch**: Clear Redis/PostgreSQL embeddings when changing dimension sizes
- **Test First**: Test external service before adding to production

## Integration Examples

### Python Script

```python
from src.model_registry.manager import ModelRegistry
from src.embedding_client import EmbeddingClient

# Initialize
registry = ModelRegistry()
client = EmbeddingClient(registry, fallback_url='http://localhost:16050')

# Add external model (in separate script/CLI)
# /model embedding add http://localhost:8000

# Use client
embedding = client.embed("Hello, world!")
print(f"Dimensions: {len(embedding)}")
print(f"Using fallback: {client.is_using_fallback()}")

# Batch embeddings
embeddings = client.embed_batch(["text1", "text2", "text3"])

# Similarity
similarity = client.get_similarity("hello", "hi", metric="cosine")
```

### Flask Service

```python
from flask import Flask, jsonify, request
from src.model_registry.manager import ModelRegistry
from src.embedding_client import EmbeddingClient

app = Flask(__name__)

# Initialize
registry = ModelRegistry()
embedding_client = EmbeddingClient(registry)

@app.route('/embed', methods=['POST'])
def embed():
    data = request.json
    text = data.get('text')
    
    embedding = embedding_client.embed(text)
    
    return jsonify({
        'embedding': embedding,
        'dimensions': len(embedding),
        'using_fallback': embedding_client.is_using_fallback()
    })
```

## Environment Variables

### Docker Services

```bash
# Transformer fallback service
TRANSFORMER_API_URL=http://localhost:16050

# Redis (for model registry)
REDIS_HOST=localhost
REDIS_PORT=26379
```

### CLI Environment

When running globally via `ai-cli`:
- `TRANSFORMER_API_URL`: Fallback transformer service URL
- `AI_CLI_ORIGINAL_DIR`: Preserved working directory

## Monitoring

### Check Embedding Status

```bash
# View active embedding configuration
/model status

# Test embedding generation
# (Uses active model or fallback)
```

### Logs

Embedding operations log to:
- Console output (warnings, errors)
- Sentry (if configured via `SENTRY_DSN`)

**Example Logs**:
```
✓ EmbeddingClient initialized with fallback to http://localhost:16050
  → Using local transformer service (no external embedding model configured)

# Or when external model is active:
✓ EmbeddingClient initialized with fallback to http://localhost:16050
  → Using external embedding service: http://localhost:8000
```

## Troubleshooting

### External Service Not Reachable

**Symptoms**: 
```
❌ Cannot reach embedding service at http://localhost:8000
```

**Solutions**:
1. Check service is running: `curl http://localhost:8000/health`
2. Verify URL is correct
3. Check network connectivity
4. Review service logs

### Dimension Mismatch

**Symptoms**:
```
⚠️  Embedding dimension mismatch! Expected 384, got 768.
```

**Solutions**:
1. Clear stored embeddings in Redis/PostgreSQL
2. Use consistent embedding models
3. Re-embed all content with new model

### Both Services Fail

**Symptoms**:
```
RuntimeError: Both external and local embedding services failed
```

**Solutions**:
1. Start local transformer: `make up-redis`
2. Check Docker services: `make status`
3. Verify transformer API URL
4. Check transformer logs: `docker logs ai-cli-transformer-1`

### Invalid Response Format

**Symptoms**:
```
❌ Invalid response format from embedding service
```

**Solutions**:
1. Verify service implements correct API protocol
2. Check response includes `embedding` or `embeddings` field
3. Test with curl: `curl -X POST http://localhost:8000/embed -H "Content-Type: application/json" -d '{"text":"test"}'`

## Performance Considerations

### Local vs External

| Aspect | Local Transformer | External Service |
|--------|------------------|------------------|
| Latency | ~100-500ms | Variable (network) |
| Throughput | CPU-limited | Depends on service |
| Reliability | Always available | Network-dependent |
| Scalability | Single instance | Can scale horizontally |
| Cost | Free (local) | Varies by provider |

### Optimization Tips

1. **Batch Requests**: Use `embed_batch()` for multiple texts
2. **Caching**: Store frequently used embeddings
3. **Timeout Tuning**: Adjust timeout based on service performance
4. **Connection Pooling**: External services may benefit from connection pooling

## Security

### Best Practices

1. **HTTPS**: Use HTTPS for external services in production
2. **Authentication**: Implement API key authentication for external services
3. **Network Isolation**: Run transformer service in isolated network
4. **Secrets**: Store sensitive URLs/keys in environment variables
5. **Validation**: Validate embedding responses before storage

### Sentry Integration

All embedding operations include Sentry error tracking:
- Exceptions captured automatically
- Includes service URL and context
- Helps diagnose production issues

## Future Enhancements

Potential improvements for future versions:

1. **Provider-Specific Adapters**: Built-in support for OpenAI, Cohere, etc.
2. **Embedding Caching**: Redis-backed embedding cache
3. **Load Balancing**: Multiple external services with round-robin
4. **Async Support**: Async embedding generation for better performance
5. **Batch Optimization**: Automatic batching of concurrent requests
6. **Monitoring Dashboard**: Web UI for embedding service health

## References

- [Sentence-Transformers Documentation](https://www.sbert.net/)
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings)
- [Cohere Embeddings](https://docs.cohere.com/docs/embeddings)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review logs for error messages
3. Open issue on GitHub repository
4. Include relevant logs and configuration
