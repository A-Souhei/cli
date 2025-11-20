"""Tests for PostgreSQL MCP tools endpoints."""

import pytest
import requests
import json


# Check if services are available
def is_postgres_available():
    """Check if PostgreSQL API is available."""
    try:
        response = requests.get("http://localhost:15000/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def is_transformer_available():
    """Check if Transformer service is available."""
    try:
        response = requests.get("http://localhost:16050/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


# Skip markers
requires_postgres = pytest.mark.skipif(
    not is_postgres_available(),
    reason="PostgreSQL service not available"
)

requires_transformer = pytest.mark.skipif(
    not is_transformer_available(),
    reason="Transformer service not available"
)

requires_both_services = pytest.mark.skipif(
    not (is_postgres_available() and is_transformer_available()),
    reason="PostgreSQL and Transformer services not available"
)


POSTGRES_URL = "http://localhost:15000"
TRANSFORMER_URL = "http://localhost:16050"


@requires_both_services
class TestMCPToolsStorage:
    """Test MCP tools storage endpoints."""

    def test_store_mcp_tool(self):
        """Test storing an MCP tool with embedding."""
        tool_data = {
            "mcp_name": "test_mcp",
            "tool_name": "test_tool",
            "description": "This is a test tool for Python code execution"
        }

        response = requests.post(
            f"{POSTGRES_URL}/mcp-tools/store",
            json=tool_data,
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "stored successfully" in data["message"].lower() or "updated successfully" in data["message"].lower()

    def test_store_mcp_tool_missing_fields(self):
        """Test storing MCP tool with missing fields."""
        tool_data = {
            "mcp_name": "test_mcp",
            "tool_name": "test_tool"
            # description is missing
        }

        response = requests.post(
            f"{POSTGRES_URL}/mcp-tools/store",
            json=tool_data,
            timeout=30
        )

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "missing required fields" in data["message"].lower()

    def test_update_existing_tool(self):
        """Test updating an existing MCP tool."""
        tool_data = {
            "mcp_name": "test_mcp",
            "tool_name": "test_tool",
            "description": "Original description"
        }

        # Store first time
        response1 = requests.post(
            f"{POSTGRES_URL}/mcp-tools/store",
            json=tool_data,
            timeout=30
        )
        assert response1.status_code == 200

        # Update with new description
        tool_data["description"] = "Updated description"
        response2 = requests.post(
            f"{POSTGRES_URL}/mcp-tools/store",
            json=tool_data,
            timeout=30
        )

        assert response2.status_code == 200
        data = response2.json()
        assert data["status"] == "success"
        assert "updated successfully" in data["message"].lower()


@requires_postgres
class TestMCPToolsRetrieval:
    """Test MCP tools retrieval endpoints."""

    def test_get_all_mcp_tools(self):
        """Test getting all MCP tools."""
        response = requests.get(
            f"{POSTGRES_URL}/mcp-tools",
            timeout=10
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "count" in data
        assert "tools" in data
        assert isinstance(data["tools"], list)

        # If there are tools, check structure
        if data["count"] > 0:
            tool = data["tools"][0]
            assert "id" in tool
            assert "mcp_name" in tool
            assert "tool_name" in tool
            assert "description" in tool
            assert "created_at" in tool


@requires_both_services
class TestMCPToolsMatching:
    """Test MCP tools matching with embeddings."""

    def setup_method(self):
        """Set up test tools before each test."""
        # Store some test tools
        test_tools = [
            {
                "mcp_name": "coder",
                "tool_name": "run_python_code",
                "description": "Execute Python code in a virtual environment with data analysis packages"
            },
            {
                "mcp_name": "coder",
                "tool_name": "run_r_code",
                "description": "Execute R statistical programming code"
            },
            {
                "mcp_name": "coder",
                "tool_name": "detect_code",
                "description": "Detect and extract Python or R code from text"
            }
        ]

        for tool in test_tools:
            requests.post(
                f"{POSTGRES_URL}/mcp-tools/store",
                json=tool,
                timeout=30
            )

    def test_match_python_code(self):
        """Test matching Python code to appropriate tool."""
        text = "Run this Python script to analyze data with pandas"

        response = requests.post(
            f"{POSTGRES_URL}/mcp-tools/match",
            json={"text": text, "threshold": 0.3},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "best_match" in data

        if data["best_match"]:
            match = data["best_match"]
            assert "mcp_name" in match
            assert "tool_name" in match
            assert "description" in match
            assert "similarity" in match
            assert 0 <= match["similarity"] <= 1

    def test_match_r_code(self):
        """Test matching R code to appropriate tool."""
        text = "Execute this R code for statistical analysis"

        response = requests.post(
            f"{POSTGRES_URL}/mcp-tools/match",
            json={"text": text, "threshold": 0.3},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_match_with_high_threshold(self):
        """Test matching with high threshold (may return no matches)."""
        text = "Some random unrelated text"

        response = requests.post(
            f"{POSTGRES_URL}/mcp-tools/match",
            json={"text": text, "threshold": 0.9},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        # May or may not have matches depending on the text

    def test_match_missing_text(self):
        """Test matching without providing text."""
        response = requests.post(
            f"{POSTGRES_URL}/mcp-tools/match",
            json={"threshold": 0.5},
            timeout=30
        )

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "missing required field" in data["message"].lower()

    def test_match_returns_multiple_matches(self):
        """Test that matching can return multiple similar tools."""
        text = "code execution tool"

        response = requests.post(
            f"{POSTGRES_URL}/mcp-tools/match",
            json={"text": text, "threshold": 0.2},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "matches" in data
        assert isinstance(data["matches"], list)

        # Matches should be sorted by similarity (highest first)
        if len(data["matches"]) > 1:
            similarities = [m["similarity"] for m in data["matches"]]
            assert similarities == sorted(similarities, reverse=True)


@requires_transformer
class TestEmbeddingService:
    """Test that embedding service is working correctly."""

    def test_embed_text(self):
        """Test text embedding generation."""
        response = requests.get(
            f"{TRANSFORMER_URL}/embed",
            params={"text": "This is a test sentence"},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "embedding" in data
        assert isinstance(data["embedding"], list)
        assert len(data["embedding"]) > 0
        assert "dimension" in data

    def test_embed_empty_text(self):
        """Test embedding with empty text."""
        response = requests.get(
            f"{TRANSFORMER_URL}/embed",
            params={"text": ""},
            timeout=30
        )

        # Should still work, just embedding an empty string
        assert response.status_code in [200, 400]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
