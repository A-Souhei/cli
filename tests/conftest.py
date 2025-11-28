"""
Pytest configuration and shared fixtures.

This file contains shared fixtures and configuration for all tests.
"""

import pytest
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "api: API tests")
    config.addinivalue_line("markers", "cli: CLI tests")
    config.addinivalue_line("markers", "mcp: MCP tests")
    config.addinivalue_line("markers", "smoke: Smoke tests")


@pytest.fixture(scope="session")
def api_base_url():
    """Get API base URL from environment or use default."""
    return os.getenv("OLLAMA_API_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def ollama_url():
    """Get Ollama service URL from environment or use default."""
    return os.getenv("OLLAMA_URL", "http://localhost:11434")


@pytest.fixture(scope="session")
def test_model():
    """Default model for tests."""
    return os.getenv("TEST_MODEL", "llama3.1:8b")


@pytest.fixture(scope="function")
def temp_test_file(tmp_path):
    """Create a temporary test file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test file content.")
    return test_file


@pytest.fixture(scope="function")
def sample_python_code():
    """Sample Python code for testing."""
    return """
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
"""


@pytest.fixture(scope="function")
def sample_chat_messages():
    """Sample chat messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi! How can I help you?"},
        {"role": "user", "content": "What is 2+2?"}
    ]


@pytest.fixture(autouse=True)
def reset_env_vars():
    """Reset environment variables after each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
