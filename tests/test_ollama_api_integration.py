"""
Integration tests for Ollama API service.

These tests require the API service to be running.
Run with: pytest tests/test_ollama_api_integration.py -v

Prerequisites:
- docker compose --profile ollama --profile app --profile api up -d
"""

import pytest
import httpx
import json
from typing import Generator


# API base URL - can be overridden with environment variable
API_BASE = "http://localhost:8080"


@pytest.fixture
def api_client() -> Generator[httpx.Client, None, None]:
    """Fixture for HTTP client."""
    client = httpx.Client(base_url=API_BASE, timeout=30.0)
    yield client
    client.close()


@pytest.fixture
async def async_api_client():
    """Fixture for async HTTP client."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        yield client


@pytest.mark.integration
class TestHealthAndInfo:
    """Test health and info endpoints."""

    def test_root_endpoint(self, api_client):
        """Test root endpoint returns service info."""
        response = api_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Ollama++ API"
        assert "endpoints" in data

    def test_health_endpoint(self, api_client):
        """Test health check endpoint."""
        response = api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "ollama" in data
        assert "models_available" in data


@pytest.mark.integration
class TestOllamaEndpoints:
    """Test standard Ollama API endpoints."""

    def test_list_models(self, api_client):
        """Test GET /api/tags - list models."""
        response = api_client.get("/api/tags")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_version_endpoint(self, api_client):
        """Test GET /api/version."""
        response = api_client.get("/api/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data

    def test_chat_non_streaming(self, api_client):
        """Test POST /api/chat without streaming."""
        payload = {
            "model": "llama3.1:8b",
            "messages": [
                {"role": "user", "content": "Say 'test' and nothing else."}
            ],
            "stream": False
        }
        response = api_client.post("/api/chat", json=payload, timeout=60.0)
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "llama3.1:8b"
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert data["done"] is True

    def test_chat_streaming(self, api_client):
        """Test POST /api/chat with streaming."""
        payload = {
            "model": "llama3.1:8b",
            "messages": [
                {"role": "user", "content": "Count from 1 to 3."}
            ],
            "stream": True
        }

        chunks = []
        with api_client.stream("POST", "/api/chat", json=payload, timeout=60.0) as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    chunks.append(chunk)
                    if chunk.get("done"):
                        break

        assert len(chunks) > 0
        assert chunks[-1]["done"] is True

    def test_generate_non_streaming(self, api_client):
        """Test POST /api/generate without streaming."""
        payload = {
            "model": "llama3.1:8b",
            "prompt": "Say 'hello' and nothing else.",
            "stream": False
        }
        response = api_client.post("/api/generate", json=payload, timeout=60.0)
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "llama3.1:8b"
        assert "response" in data
        assert data["done"] is True

    def test_generate_streaming(self, api_client):
        """Test POST /api/generate with streaming."""
        payload = {
            "model": "llama3.1:8b",
            "prompt": "Say hello.",
            "stream": True
        }

        chunks = []
        with api_client.stream("POST", "/api/generate", json=payload, timeout=60.0) as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    chunks.append(chunk)
                    if chunk.get("done"):
                        break

        assert len(chunks) > 0
        assert chunks[-1]["done"] is True


@pytest.mark.integration
class TestOpenAIEndpoints:
    """Test OpenAI-compatible endpoints."""

    def test_openai_list_models(self, api_client):
        """Test GET /v1/models."""
        response = api_client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_openai_chat_completions(self, api_client):
        """Test POST /v1/chat/completions."""
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Say 'test' and nothing else."}
            ],
            "stream": False
        }
        response = api_client.post("/v1/chat/completions", json=payload, timeout=60.0)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert len(data["choices"]) > 0
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert "usage" in data

    def test_openai_streaming(self, api_client):
        """Test POST /v1/chat/completions with streaming."""
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "stream": True
        }

        chunks = []
        with api_client.stream("POST", "/v1/chat/completions", json=payload, timeout=60.0) as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str.strip() == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    chunks.append(chunk)

        assert len(chunks) > 0


@pytest.mark.integration
class TestToolsEndpoints:
    """Test enhanced tools endpoints."""

    def test_list_tools(self, api_client):
        """Test GET /api/tools/list."""
        response = api_client.get("/api/tools/list")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "tools" in data
        assert data["count"] > 0
        # Check for specific expected tools
        tool_names = [t["name"] for t in data["tools"]]
        assert "run_python_code" in tool_names

    def test_tools_health(self, api_client):
        """Test GET /api/tools/health."""
        response = api_client.get("/api/tools/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["mcp_connected"] is True

    def test_execute_tool(self, api_client):
        """Test POST /api/tools/execute."""
        payload = {
            "tool_name": "run_python_code",
            "arguments": {
                "code": "print('test')"
            }
        }
        response = api_client.post("/api/tools/execute", json=payload, timeout=60.0)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "result" in data

    def test_retrieve_tools(self, api_client):
        """Test POST /api/tools/retrieve - semantic search."""
        payload = {
            "prompt": "I want to execute Python code",
            "top_k": 3,
            "threshold": 0.3
        }
        response = api_client.post("/api/tools/retrieve", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "tools" in data


@pytest.mark.integration
class TestCodeExecution:
    """Test code execution endpoints."""

    def test_execute_python_code(self, api_client):
        """Test POST /api/code/execute with Python."""
        payload = {
            "code": "print('Hello from Python!')\nprint(2 + 2)",
            "language": "python"
        }
        response = api_client.post("/api/code/execute", json=payload, timeout=30.0)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Hello from Python!" in data["output"]
        assert "4" in data["output"]

    def test_execute_python_code_with_error(self, api_client):
        """Test Python code execution with error."""
        payload = {
            "code": "raise ValueError('Test error')",
            "language": "python"
        }
        response = api_client.post("/api/code/execute", json=payload, timeout=30.0)
        assert response.status_code == 200
        data = response.json()
        # Either success=False or error message present
        assert data["success"] is False or "error" in data


@pytest.mark.integration
class TestFileOperations:
    """Test file upload and context endpoints."""

    def test_upload_file(self, api_client):
        """Test POST /api/files/upload."""
        files = {
            'files': ('test.txt', b'This is a test file content.', 'text/plain')
        }
        data = {
            'auto_inject': 'true'
        }
        response = api_client.post("/api/files/upload", files=files, data=data)
        assert response.status_code == 200
        resp_data = response.json()
        assert resp_data["success"] is True
        assert "session_id" in resp_data
        assert len(resp_data["files"]) == 1
        assert resp_data["files"][0]["at_reference"] == "@test.txt"

    def test_add_context(self, api_client):
        """Test POST /api/context/add."""
        payload = {
            "content": "This is important context information.",
            "path": "@context.txt",
            "session_id": "test-session-123"
        }
        response = api_client.post("/api/context/add", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["path"] == "@context.txt"

    def test_chat_with_files(self, api_client):
        """Test POST /api/chat/with-files."""
        files = {
            'files': ('data.txt', b'Some data content', 'text/plain')
        }
        data = {
            'message': 'What is in the file?',
            'stream': 'false'
        }
        response = api_client.post("/api/chat/with-files", files=files, data=data, timeout=60.0)
        assert response.status_code == 200


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling."""

    def test_invalid_model(self, api_client):
        """Test chat with invalid model."""
        payload = {
            "model": "nonexistent-model:123",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        }
        response = api_client.post("/api/chat", json=payload)
        # Should either fail or handle gracefully
        assert response.status_code in [200, 400, 404, 500]

    def test_missing_required_field(self, api_client):
        """Test request with missing required field."""
        payload = {
            "messages": [{"role": "user", "content": "Hello"}]
            # Missing 'model' field
        }
        response = api_client.post("/api/chat", json=payload)
        assert response.status_code == 422  # Validation error

    def test_invalid_json(self, api_client):
        """Test request with invalid JSON."""
        response = api_client.post(
            "/api/chat",
            content=b"{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.slow
class TestPerformance:
    """Test performance and concurrency."""

    def test_concurrent_requests(self, api_client):
        """Test handling multiple concurrent requests."""
        import concurrent.futures

        def make_request():
            payload = {
                "model": "llama3.1:8b",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": False
            }
            response = api_client.post("/api/chat", json=payload, timeout=60.0)
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request) for _ in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(code == 200 for code in results)

    def test_large_context(self, api_client):
        """Test handling large context."""
        large_content = "This is a test. " * 1000
        payload = {
            "model": "llama3.1:8b",
            "messages": [
                {"role": "user", "content": large_content},
                {"role": "user", "content": "Summarize the above in one word."}
            ],
            "stream": False
        }
        response = api_client.post("/api/chat", json=payload, timeout=120.0)
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
