# Testing Guide for Ollama++ API

## Quick Start

### 1. Install Test Dependencies

```bash
# From project root
pip install -r tests/requirements-test.txt
```

### 2. Run Tests

```bash
# Run all unit tests (no services needed)
./tests/run_api_tests.sh unit

# Start services for integration tests
docker compose --profile ollama --profile app --profile api up -d

# Run integration tests
./tests/run_api_tests.sh integration

# Run all tests
./tests/run_api_tests.sh all

# Quick smoke test
./tests/run_api_tests.sh smoke
```

## Test Structure

### Unit Tests (`tests/test_ollama_api_models.py`)

Test Pydantic model validation:
- ✅ Message models
- ✅ Chat request/response
- ✅ Generate request/response
- ✅ OpenAI compatibility
- ✅ Tool models
- ✅ File models

**No services required** - These are fast, isolated tests.

### Integration Tests (`tests/test_ollama_api_integration.py`)

Test API endpoints with running services:
- ✅ Health and info endpoints
- ✅ Ollama standard endpoints (/api/chat, /api/generate, /api/tags)
- ✅ OpenAI compatible endpoints (/v1/chat/completions, /v1/models)
- ✅ Enhanced features (tools, code execution, file upload)
- ✅ Error handling
- ✅ Performance and concurrency

**Requires running services** on http://localhost:8080

## Running Tests

### Option 1: Test Runner Script (Recommended)

```bash
# Unit tests only (fast, no services needed)
./tests/run_api_tests.sh unit

# Integration tests (requires services)
docker compose --profile ollama --profile app --profile api up -d
./tests/run_api_tests.sh integration

# Smoke tests (quick verification)
./tests/run_api_tests.sh smoke

# All tests
./tests/run_api_tests.sh all
```

### Option 2: pytest Directly

```bash
# Run specific test file
pytest tests/test_ollama_api_models.py -v

# Run specific test class
pytest tests/test_ollama_api_integration.py::TestOllamaEndpoints -v

# Run with markers
pytest -m "unit" -v                    # Unit tests only
pytest -m "integration" -v             # Integration tests only
pytest -m "not slow" -v                # Skip slow tests

# Run with coverage
pytest tests/ --cov=ollama_api_service --cov-report=html
```

### Option 3: Manual API Testing

```bash
# Start services
docker compose --profile ollama --profile app --profile api up -d

# Test health
curl http://localhost:8080/health | jq

# Test chat
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }' | jq

# Test tools
curl http://localhost:8080/api/tools/list | jq

# Test code execution
curl -X POST http://localhost:8080/api/code/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(2+2)",
    "language": "python"
  }' | jq
```

## Test Coverage

Check what's tested:

```bash
# Generate coverage report
pytest tests/ --cov=ollama_api_service --cov-report=html --cov-report=term

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Continuous Testing

### Watch Mode (requires pytest-watch)

```bash
pip install pytest-watch
ptw tests/ -- -v
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run unit tests before commit
pytest tests/test_ollama_api_models.py -v
exit $?
```

```bash
chmod +x .git/hooks/pre-commit
```

## Test Markers

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests (needs services)
- `@pytest.mark.slow` - Tests that take >5 seconds
- `@pytest.mark.smoke` - Quick verification tests

Example usage:

```bash
# Run only fast tests
pytest -m "unit" -v

# Run non-slow tests
pytest -m "not slow" -v

# Run specific markers
pytest -m "integration and not slow" -v
```

## Debugging Tests

### Verbose Output

```bash
pytest tests/ -vv --tb=long
```

### Stop on First Failure

```bash
pytest tests/ -x
```

### Run Last Failed Tests

```bash
pytest tests/ --lf
```

### Print Output (disable capture)

```bash
pytest tests/ -s
```

### Debug with pdb

```bash
pytest tests/ --pdb
```

## Common Issues

### Connection Refused

**Problem:** Tests fail with connection errors

**Solution:**
```bash
# Make sure API is running
docker compose ps ollama-api

# Check health
curl http://localhost:8080/health

# View logs
docker compose logs ollama-api
```

### Import Errors

**Problem:** `ModuleNotFoundError`

**Solution:**
```bash
# Ensure you're in project root
cd /home/user/cli

# Install dependencies
pip install -r ollama_api_service/requirements.txt
pip install -r tests/requirements-test.txt
```

### Timeout Errors

**Problem:** Tests timeout

**Solution:**
```bash
# Increase timeout
pytest tests/ --timeout=300

# Check if Ollama is responding
curl http://localhost:11434/api/tags
```

## Performance Benchmarks

Expected execution times:

| Test Suite | Expected Time | Notes |
|------------|---------------|-------|
| Unit tests | < 5 seconds | No services needed |
| Integration (fast) | < 60 seconds | Most endpoints |
| Integration (all) | < 120 seconds | Including slow tests |
| Smoke tests | < 10 seconds | Quick verification |
| Full suite | < 150 seconds | Everything |

## Writing New Tests

### Unit Test Template

```python
import pytest
from ollama_api_service.models import YourModel

class TestYourFeature:
    """Test your new feature."""

    def test_model_validation(self):
        """Test that model validates correctly."""
        model = YourModel(field="value")
        assert model.field == "value"

    def test_edge_case(self):
        """Test edge case handling."""
        # Your test here
        pass
```

### Integration Test Template

```python
import pytest

@pytest.mark.integration
class TestYourEndpoint:
    """Test your new endpoint."""

    def test_endpoint_success(self, api_client):
        """Test successful request."""
        response = api_client.post(
            "/api/your-endpoint",
            json={"key": "value"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_endpoint_error(self, api_client):
        """Test error handling."""
        response = api_client.post(
            "/api/your-endpoint",
            json={}  # Missing required field
        )
        assert response.status_code == 422
```

## Test Data

Use fixtures for common test data:

```python
@pytest.fixture
def sample_request():
    """Sample request data."""
    return {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "test"}]
    }

def test_with_fixture(sample_request, api_client):
    """Test using fixture."""
    response = api_client.post("/api/chat", json=sample_request)
    assert response.status_code == 200
```

## Best Practices

1. ✅ **Run unit tests before committing**
2. ✅ **Run integration tests before pushing**
3. ✅ **Keep tests independent** - No shared state
4. ✅ **Use descriptive names** - `test_chat_with_invalid_model_returns_error`
5. ✅ **Test edge cases** - Empty inputs, large inputs, invalid data
6. ✅ **Mock external services** in unit tests
7. ✅ **Clean up resources** - Use fixtures with cleanup
8. ✅ **Document complex tests** - Add docstrings
9. ✅ **Keep tests fast** - Unit tests < 1s, integration < 5s
10. ✅ **Use markers** - Categorize tests appropriately

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r tests/requirements-test.txt
          pip install -r ollama_api_service/requirements.txt

      - name: Run unit tests
        run: pytest tests/test_ollama_api_models.py -v

      - name: Start services
        run: docker compose --profile ollama --profile app --profile api up -d

      - name: Wait for services
        run: sleep 30

      - name: Run integration tests
        run: pytest tests/test_ollama_api_integration.py -v -m integration

      - name: Generate coverage
        run: pytest tests/ --cov=ollama_api_service --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [httpx documentation](https://www.python-httpx.org/)
- [FastAPI testing guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [Project test documentation](tests/TEST_DOCUMENTATION.md)
