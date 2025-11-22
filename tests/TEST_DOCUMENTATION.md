# Ollama++ API Testing Documentation

## Overview

This document describes the testing strategy and available tests for the Ollama++ API service.

## Test Organization

```
tests/
├── conftest.py                      # Shared fixtures and configuration
├── test_ollama_api_models.py        # Unit tests for Pydantic models
├── test_ollama_api_integration.py   # Integration tests for API endpoints
├── run_api_tests.sh                 # Test runner script
└── TEST_DOCUMENTATION.md            # This file
```

## Test Categories

### 1. Unit Tests (`test_ollama_api_models.py`)

**Purpose:** Test Pydantic model validation and serialization without external dependencies.

**Tests:**
- Message model validation
- ChatRequest/ChatResponse validation
- GenerateRequest/GenerateResponse validation
- OpenAI format compatibility models
- Tool execution models
- Code execution models
- File attachment models
- Error response models

**Run:**
```bash
pytest tests/test_ollama_api_models.py -v
# Or
./tests/run_api_tests.sh unit
```

**Requirements:** None (no services needed)

### 2. Integration Tests (`test_ollama_api_integration.py`)

**Purpose:** Test API endpoints with running services.

**Test Classes:**
- `TestHealthAndInfo` - Health checks and service info
- `TestOllamaEndpoints` - Standard Ollama API compatibility
- `TestOpenAIEndpoints` - OpenAI API compatibility
- `TestToolsEndpoints` - MCP tools integration
- `TestCodeExecution` - Code execution features
- `TestFileOperations` - File upload and context
- `TestErrorHandling` - Error scenarios
- `TestPerformance` - Performance and concurrency

**Run:**
```bash
# Start services first
docker compose --profile ollama --profile app --profile api up -d

# Run tests
pytest tests/test_ollama_api_integration.py -v -m integration
# Or
./tests/run_api_tests.sh integration
```

**Requirements:** Running API service on http://localhost:8080

### 3. Smoke Tests

**Purpose:** Quick verification that critical endpoints are working.

**Tests:**
- Health endpoint
- Model listing
- Tools listing

**Run:**
```bash
./tests/run_api_tests.sh smoke
```

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Optional: For coverage and timeouts
pip install pytest-cov pytest-timeout
```

### Quick Start

```bash
# Run all tests (requires running services)
./tests/run_api_tests.sh all

# Run only unit tests (no services needed)
./tests/run_api_tests.sh unit

# Run only integration tests
./tests/run_api_tests.sh integration

# Run smoke tests
./tests/run_api_tests.sh smoke
```

### Using pytest directly

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_ollama_api_models.py -v

# Run specific test class
pytest tests/test_ollama_api_integration.py::TestOllamaEndpoints -v

# Run specific test
pytest tests/test_ollama_api_integration.py::TestOllamaEndpoints::test_list_models -v

# Run tests with specific marker
pytest -m "unit" -v
pytest -m "integration" -v
pytest -m "slow" -v

# Run tests with coverage
pytest tests/ --cov=ollama_api_service --cov-report=html

# Run tests in parallel (requires pytest-xdist)
pytest tests/ -n auto
```

## Test Markers

Tests are marked with the following markers:

- `@pytest.mark.unit` - Unit tests (fast, no dependencies)
- `@pytest.mark.integration` - Integration tests (requires services)
- `@pytest.mark.slow` - Slow tests (>5 seconds)
- `@pytest.mark.api` - API-specific tests
- `@pytest.mark.smoke` - Quick smoke tests

## Continuous Integration

### GitHub Actions (Example)

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r ollama_api_service/requirements.txt
          pip install pytest pytest-asyncio httpx
      - name: Run unit tests
        run: pytest tests/test_ollama_api_models.py -v

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Start services
        run: docker compose --profile ollama --profile app --profile api up -d
      - name: Wait for services
        run: sleep 30
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio httpx
      - name: Run integration tests
        run: pytest tests/test_ollama_api_integration.py -v -m integration
```

## Writing New Tests

### Unit Test Example

```python
import pytest
from ollama_api_service.models import ChatRequest, Message

class TestNewFeature:
    """Test new feature."""

    def test_feature_validation(self):
        """Test that feature validates correctly."""
        request = ChatRequest(
            model="llama3.1:8b",
            messages=[Message(role="user", content="test")]
        )
        assert request.model == "llama3.1:8b"
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
class TestNewEndpoint:
    """Test new endpoint."""

    def test_new_endpoint(self, api_client):
        """Test new endpoint returns expected data."""
        response = api_client.get("/api/new-endpoint")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
```

## Test Coverage

To check test coverage:

```bash
# Install coverage tools
pip install pytest-cov coverage

# Run tests with coverage
pytest tests/ --cov=ollama_api_service --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

## Troubleshooting

### Tests fail with connection errors

**Problem:** `ConnectionError: Connection refused`

**Solution:**
```bash
# Make sure services are running
docker compose --profile ollama --profile app --profile api up -d

# Check service health
curl http://localhost:8080/health

# View logs
docker compose logs -f ollama-api
```

### Tests timeout

**Problem:** Tests hang or timeout

**Solution:**
```bash
# Increase timeout in pytest.ini or use command line
pytest tests/ --timeout=300

# Check if Ollama is responding
curl http://localhost:11434/api/tags
```

### Import errors

**Problem:** `ModuleNotFoundError`

**Solution:**
```bash
# Make sure you're in the project root
cd /home/user/cli

# Install all dependencies
pip install -r requirements.txt
pip install -r ollama_api_service/requirements.txt
pip install pytest pytest-asyncio httpx
```

## Best Practices

1. **Keep tests isolated** - Each test should be independent
2. **Use fixtures** - Share common setup via pytest fixtures
3. **Mark tests appropriately** - Use markers to categorize tests
4. **Test edge cases** - Include error conditions and boundaries
5. **Keep tests fast** - Unit tests should run in <1 second
6. **Mock external services** - For unit tests, mock external APIs
7. **Clean up resources** - Use fixtures to ensure cleanup
8. **Write descriptive names** - Test names should describe what they test
9. **Document complex tests** - Add docstrings explaining test logic
10. **Run tests before committing** - Ensure tests pass locally

## Performance Benchmarks

Expected test execution times:

- Unit tests: < 5 seconds total
- Integration tests (without slow): < 60 seconds
- All integration tests: < 120 seconds
- Smoke tests: < 10 seconds
- All tests: < 150 seconds

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [httpx documentation](https://www.python-httpx.org/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Ollama API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
