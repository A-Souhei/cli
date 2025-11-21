# Recursive Tool Retrieval API

## Overview

The Recursive Tool Retrieval API is an intelligent endpoint that processes multiple prompts/sentences simultaneously, using transformer embeddings to find the most relevant MCP (Model Context Protocol) tools and automatically extracting parameters from the text.

## Table of Contents

- [Architecture](#architecture)
- [Endpoint Details](#endpoint-details)
- [Request Format](#request-format)
- [Response Format](#response-format)
- [Parameter Extraction](#parameter-extraction)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)
- [Testing](#testing)

## Architecture

### How It Works

```
User Prompts/Sentences
    ↓
[Batch Embedding] → Transformer Service generates embeddings
    ↓
[Tool Matching] → Compare embeddings with all registered MCP tools
    ↓
[Parameter Extraction] → Extract parameters from text using regex patterns
    ↓
[Results] → Return ranked tools with extracted parameters
```

### Components

1. **PostgreSQL API** (`/mcp-tools/retrieve`)
   - Main endpoint handler
   - Orchestrates the retrieval process
   - Port: 15000

2. **Transformer Service** (`/embed/batch`)
   - Generates embeddings for multiple texts
   - Model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
   - Port: 16050

3. **MCP Tools Database**
   - Stores registered tools with pre-computed embeddings
   - PostgreSQL table: `mcp_tools`

4. **Parameter Extractor**
   - Heuristic-based extraction for common parameter patterns
   - Supports code, file paths, directory paths

## Endpoint Details

### URL
```
POST http://localhost:15000/mcp-tools/retrieve
```

### Method
```
POST
```

### Content-Type
```
application/json
```

### Timeout
- Recommended: 60 seconds (for large batches)
- Default: 30 seconds

## Request Format

### JSON Body Parameters

All parameters are passed in the JSON request body.

```json
{
  "prompts": ["prompt1", "prompt2"],
  "threshold": 0.5,
  "mcp_filter": ["coder"],
  "extract_params": true
}
```

**Parameter Schema:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompts` | array[string] | Yes | - | List of text prompts/sentences to process |
| `threshold` | float | No | 0.5 | Minimum cosine similarity (0.0-1.0). Lower = more permissive |
| `mcp_filter` | array[string] | No | null | Only match tools from specified MCPs (e.g., ["coder"]) |
| `extract_params` | boolean | No | true | Whether to extract parameters from prompts |

## Response Format

### Success Response (200 OK)

```json
{
  "status": "success",
  "count": 2,
  "results": [
    {
      "prompt": "Run this Python code: print('hello')",
      "prompt_index": 0,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "run_python_code",
        "description": "Execute Python code in a virtual environment",
        "similarity": 0.87,
        "extracted_params": {
          "code": "print('hello')"
        }
      }
    },
    {
      "prompt": "Create a Python file test.py",
      "prompt_index": 1,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "write_python_code",
        "description": "Create a new Python file",
        "similarity": 0.82,
        "extracted_params": {
          "file_path": "test.py"
        }
      }
    }
  ],
  "metadata": {
    "threshold": 0.5,
    "mcp_filter": null,
    "total_prompts": 2,
    "total_tools_searched": 10
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "success" or "error" |
| `count` | integer | Number of prompts processed |
| `results` | array | Array of results, one per prompt |
| `results[].prompt` | string | The original prompt text |
| `results[].prompt_index` | integer | Index of the prompt in the input array |
| `results[].best_match` | object or null | Best matching tool (null if no match above threshold) |
| `best_match.mcp_name` | string | Name of the MCP providing this tool |
| `best_match.tool_name` | string | Name of the tool |
| `best_match.description` | string | Tool description |
| `best_match.similarity` | float | Cosine similarity score (0-1) |
| `best_match.extracted_params` | object | Parameters extracted from prompt |
| `metadata` | object | Request metadata |
| `metadata.threshold` | float | Similarity threshold used |
| `metadata.mcp_filter` | array or null | MCP filter applied |
| `metadata.total_prompts` | integer | Total number of prompts processed |
| `metadata.total_tools_searched` | integer | Total number of tools in database |
```

### Error Response (4xx/5xx)

```json
{
  "status": "error",
  "message": "Detailed error message"
}
```

### Common Error Codes

| Code | Message | Cause |
|------|---------|-------|
| 400 | "Missing required field: prompts" | No prompts provided |
| 400 | "prompts must be a list of strings" | Invalid prompts format |
| 404 | "No tools found in database" | MCP tools not initialized |
| 500 | "Failed to generate embeddings" | Transformer service error |

## Parameter Extraction

The endpoint automatically extracts parameters from prompts based on tool types.

### Supported Patterns

#### 1. Code Execution Tools (`run_*`, `execute_*`, `eval_*`)

**Extracts:** `code` parameter

**Patterns:**
- Markdown code blocks: ` ```python\ncode\n``` `
- Inline code: `` `code` ``
- Quoted strings: `"code"` or `'code'`
- Plain text after command words

**Examples:**
```
"Run this: `print('hello')`"
→ { "code": "print('hello')" }

"Execute ```python\nimport pandas\n```"
→ { "code": "import pandas" }
```

#### 2. File Operations (`write_*`, `edit_*`, `create_*`)

**Extracts:** `file_path` and `code` parameters

**Patterns:**
- File paths: `test.py`, `path/to/file.r`, `/absolute/path.py`
- Extensions: `.py`, `.r`, `.txt`, `.json`, `.csv`, `.md`

**Examples:**
```
"Create file test.py with code"
→ { "file_path": "test.py" }

"Edit analysis.r with new code"
→ { "file_path": "analysis.r" }
```

#### 3. Context Operations (`add_*_context`, `context`)

**Extracts:** `file_path` or `directory_path` parameters

**Patterns:**
- Unix paths: `/home/user/project`
- Windows paths: `C:\Users\project`
- Relative paths: `./src/main.py`

**Examples:**
```
"Add file context for src/app.py"
→ { "file_path": "src/app.py" }

"Add directory /home/user/project to context"
→ { "directory_path": "/home/user/project" }
```

#### 4. Generic Fallback

If no specific pattern matches, the entire text is stored as `input`:

```
"Some generic text"
→ { "input": "Some generic text" }
```

### Limitations

- **Heuristic-based:** Uses regex patterns, not semantic understanding
- **Simple extraction:** May not handle complex nested structures
- **Language-specific:** Optimized for Python and R code
- **Future improvement:** Consider using LLM for more sophisticated extraction

## Usage Examples

### Example 1: Single Python Code Execution

```bash
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": ["Run this Python code: print(\"Hello World\")"]
  }'
```

**Response:**
```json
{
  "status": "success",
  "count": 1,
  "results": [{
    "prompt": "Run this Python code: print(\"Hello World\")",
    "prompt_index": 0,
    "best_match": {
      "mcp_name": "coder",
      "tool_name": "run_python_code",
      "description": "Execute Python code in a virtual environment",
      "similarity": 0.91,
      "extracted_params": {
        "code": "print(\"Hello World\")"
      }
    }
  }]
}
```

### Example 2: Multiple Operations

```bash
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": [
      "Execute Python: import pandas as pd",
      "Create R file analysis.r",
      "Add file context for main.py"
    ],
    "threshold": 0.4
  }'
```

### Example 3: Filtered by MCP

```bash
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": ["code execution"],
    "mcp_filter": ["coder"],
    "threshold": 0.3
  }'
```

### Example 4: Without Parameter Extraction

```bash
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": ["Find tools related to data analysis"],
    "extract_params": false
  }'
```

### Example 5: Python Requests

```python
import requests

response = requests.post(
    "http://localhost:15000/mcp-tools/retrieve",
    json={
        "prompts": [
            "Run Python code to analyze CSV",
            "Create visualization script",
            "Add data directory to context"
        ],
        "threshold": 0.5
    },
    timeout=60
)

data = response.json()
for result in data["results"]:
    print(f"Prompt: {result['prompt']}")
    if result["best_match"]:
        best = result["best_match"]
        print(f"  Tool: {best['tool_name']}")
        print(f"  Similarity: {best['similarity']:.2f}")
        print(f"  Params: {best['extracted_params']}")
    print()
```

## Error Handling

### Common Errors and Solutions

#### 1. "Failed to generate embeddings"

**Cause:** Transformer service is down or unreachable

**Solution:**
```bash
# Check transformer service health
curl http://localhost:16050/health

# Restart the service
docker-compose restart transformer
```

#### 2. "No tools found in database"

**Cause:** MCP tools haven't been initialized

**Solution:**
```bash
# Initialize MCP tools
python -c "
from src.mcp.client import MCPClient
import asyncio

async def init():
    client = MCPClient(
        'system_mcps',
        'postgresql://postgres:postgres@localhost:25432/vuhitra'
    )
    await client.initialize_tools_in_db()

asyncio.run(init())
"
```

#### 3. Connection Timeout

**Cause:** Large batch or slow network

**Solution:**
- Reduce batch size (split into smaller chunks)
- Increase request timeout
- Check service resource usage

#### 4. Low Similarity Scores

**Cause:** Threshold too high or poor prompt quality

**Solution:**
- Lower threshold (try 0.3-0.4)
- Improve prompt specificity
- Check if tools are properly registered

## Best Practices

### 1. Batch Size

- **Recommended:** 10-50 prompts per request
- **Maximum:** 100 prompts (may cause timeout)
- **Large batches:** Split into multiple requests

### 2. Threshold Selection

| Threshold | Use Case |
|-----------|----------|
| 0.7-1.0 | Exact/near-exact matches only |
| 0.5-0.7 | High confidence matches (recommended) |
| 0.3-0.5 | Exploratory/broad matching |
| 0.0-0.3 | Very permissive (may include noise) |

### 3. Optimizing Performance

```python
# Good: Process related prompts together
prompts = [
    "Run Python analysis",
    "Create Python visualization",
    "Execute Python tests"
]

# Bad: Mix unrelated prompts (less efficient caching)
prompts = [
    "Run Python code",
    "Unrelated random text",
    "Another random thing"
]
```

### 4. Parameter Extraction

- **Enable by default** unless you only need tool discovery
- **Verify extracted parameters** before using them
- **Provide clear prompts** with explicit parameters
- **Use code blocks** for better extraction accuracy

### 5. Error Handling

```python
import requests
from requests.exceptions import Timeout, RequestException

def retrieve_tools(prompts, max_retries=3):
    """Retrieve tools with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:15000/mcp-tools/retrieve",
                json={"prompts": prompts},
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
        except RequestException as e:
            print(f"Error: {e}")
            raise

    return None
```

## Testing

### Running Tests

```bash
# Run all tool retrieval tests
pytest tests/test_tool_retrieval.py -v

# Run specific test class
pytest tests/test_tool_retrieval.py::TestRecursiveToolRetrieval -v

# Run with coverage
pytest tests/test_tool_retrieval.py --cov=src/postgresql/app

# Run integration tests (requires services)
docker-compose up -d
pytest tests/test_tool_retrieval.py -v
```

### Manual Testing

```bash
# 1. Check service health
curl http://localhost:15000/health
curl http://localhost:16050/health

# 2. Store test tools
curl -X POST http://localhost:15000/mcp-tools/store \
  -H "Content-Type: application/json" \
  -d '{
    "mcp_name": "coder",
    "tool_name": "run_python_code",
    "description": "Execute Python code"
  }'

# 3. Test retrieval
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{"prompts": ["Run Python code"]}'
```

### Test Coverage

The test suite includes:

- **Basic functionality** (single/multiple prompts)
- **Parameter extraction** (code, files, paths)
- **Filtering** (threshold, mcp_filter)
- **Error handling** (invalid inputs, missing services)
- **Edge cases** (empty lists, high thresholds)
- **Performance** (batch embeddings, sorting)

## Performance Considerations

### Typical Response Times

| Prompts | Tools | Avg Time |
|---------|-------|----------|
| 1 | 10 | ~200ms |
| 10 | 10 | ~500ms |
| 50 | 10 | ~1.5s |
| 100 | 50 | ~5s |

### Optimization Tips

1. **Cache embeddings** for frequently used prompts
2. **Use mcp_filter** to reduce search space
3. **Adjust threshold** to balance precision vs. recall
4. **Batch similar prompts** together
5. **Monitor service resources** (CPU, memory)

## Future Enhancements

- [ ] **LLM-based parameter extraction** for better accuracy
- [ ] **Semantic grouping** of related prompts
- [ ] **Tool chaining** to execute sequences
- [ ] **Confidence scores** for extracted parameters
- [ ] **Custom extraction patterns** via configuration
- [ ] **Caching layer** for repeated queries
- [ ] **Async processing** for very large batches
- [ ] **Vector database** (pgvector) for faster search

## API Versioning

Current Version: **v1**

Endpoint: `POST /mcp-tools/retrieve`

No breaking changes planned. New features will be additive (backwards compatible).

## Related Documentation

- [MCP Tools API](../DOCUMENTATION.md#mcp-tools)
- [Transformer Service](../src/transformer/app.py)
- [Embedding Similarity](../src/transformer/embedding_similarity.py)
- [Test Suite](../tests/test_tool_retrieval.py)

## Support

For issues or questions:
1. Check the [test suite](../tests/test_tool_retrieval.py) for examples
2. Review [error handling](#error-handling) section
3. Enable debug logging: `export LOG_LEVEL=DEBUG`
4. Check service logs: `docker-compose logs transformer postgres-api`

## License

Same as parent project license.
