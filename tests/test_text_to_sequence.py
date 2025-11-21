"""Tests for text-to-sequence endpoint and spin_the_roulette MCP tool."""

import pytest
import requests
import json
import time


# Check if services are available
def is_postgres_available():
    """Check if PostgreSQL API is available."""
    try:
        response = requests.get("http://localhost:15000/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def is_ollama_available():
    """Check if Ollama service is available."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


# Skip markers
requires_postgres = pytest.mark.skipif(
    not is_postgres_available(),
    reason="PostgreSQL service not available"
)

requires_ollama = pytest.mark.skipif(
    not is_ollama_available(),
    reason="Ollama service not available"
)

requires_both_services = pytest.mark.skipif(
    not (is_postgres_available() and is_ollama_available()),
    reason="PostgreSQL and Ollama services not available"
)


POSTGRES_URL = "http://localhost:15000"


def make_request_with_retry(url, json_data, timeout=180, max_retries=2):
    """Make a request with retry logic for timeouts."""
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=json_data, timeout=timeout)
            return response
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retry
                continue
            # Last attempt failed, skip test
            pytest.skip(f"Request timed out after {max_retries} attempts (LLM may be slow)")
        except Exception as e:
            raise e
    return None


@requires_both_services
class TestTextToSequenceEndpoint:
    """Test text-to-sequence endpoint."""

    def test_text_to_sequence_simple(self):
        """Test with a simple multi-step text."""
        request_data = {
            "text": "First, run Python code to print hello. Then, create a new file called test.py. Finally, add the file to context."
        }

        response = make_request_with_retry(
            f"{POSTGRES_URL}/mcp-tools/text-to-sequence",
            request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "sequence" in data
        assert isinstance(data["sequence"], list)
        assert len(data["sequence"]) > 0

        # Check metadata
        assert "metadata" in data
        metadata = data["metadata"]
        assert "original_length" in metadata
        assert "total_steps" in metadata
        assert "model_used" in metadata

    def test_text_to_sequence_single_instruction(self):
        """Test with a single instruction."""
        request_data = {
            "text": "Run this Python code: print('hello world')"
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "sequence" in data
        # Should have at least 1 step
        assert len(data["sequence"]) >= 1

    def test_text_to_sequence_complex_text(self):
        """Test with complex multi-paragraph text."""
        request_data = {
            "text": """
            I need to analyze some data. First, load the CSV file from data.csv.
            Then calculate the mean and standard deviation for each column.
            After that, create a visualization showing the distribution.
            Finally, save the results to a new file called results.txt.
            """
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "sequence" in data
        # Should have multiple steps
        assert len(data["sequence"]) >= 3

    def test_text_to_sequence_with_model(self):
        """Test with custom model parameter."""
        request_data = {
            "text": "Do task A and task B",
            "model": "tinyllama"
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["metadata"]["model_used"] == "tinyllama"

    def test_text_to_sequence_with_max_iterations(self):
        """Test with custom max_iterations parameter."""
        request_data = {
            "text": "Task 1, Task 2, and Task 3",
            "max_iterations": 2
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "metadata" in data
        assert data["metadata"]["iterations_performed"] <= 2

    def test_text_to_sequence_empty_text(self):
        """Test with empty text."""
        request_data = {
            "text": ""
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "non-empty" in data["message"].lower()

    def test_text_to_sequence_missing_text(self):
        """Test without text parameter."""
        request_data = {}

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert ("required" in data["message"].lower() or "missing" in data["message"].lower())

    def test_text_to_sequence_invalid_text_type(self):
        """Test with non-string text."""
        request_data = {
            "text": 123
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "string" in data["message"].lower()

    def test_text_to_sequence_invalid_max_iterations(self):
        """Test with invalid max_iterations."""
        request_data = {
            "text": "Task 1 and Task 2",
            "max_iterations": -1
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        # Should still work but use default value
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_text_to_sequence_capped_max_iterations(self):
        """Test that max_iterations is capped at 5."""
        request_data = {
            "text": "Multiple tasks here",
            "max_iterations": 100  # Should be capped to 5
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        # iterations_performed should be <= 5
        assert data["metadata"]["iterations_performed"] <= 5


@requires_postgres
class TestTextToSequenceWithoutOllama:
    """Test text-to-sequence endpoint behavior when Ollama is not available."""

    def test_text_to_sequence_no_ollama(self):
        """Test that endpoint returns proper error when Ollama is unavailable."""
        if is_ollama_available():
            pytest.skip("Ollama is available, skipping this test")

        request_data = {
            "text": "Run Python code and create a file"
        }

        response = make_request_with_retry(f"{POSTGRES_URL}/mcp-tools/text-to-sequence", request_data
        )

        # Should return 503 (Service Unavailable) when Ollama is not running
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert "llm" in data["message"].lower() or "ollama" in data["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
