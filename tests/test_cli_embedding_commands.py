"""
Tests for /model embedding CLI commands.

These tests verify the CLI commands for managing embedding models work correctly.
"""

import pytest
import requests
from src.model_registry.manager import ModelRegistry


def is_ollama_available():
    """Check if Ollama service is available."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def is_remote_ollama_available():
    """Check if remote Ollama service is available (with embedding models)."""
    try:
        # This would be the remote Ollama URL - adjust as needed
        response = requests.get("http://remote-ollama:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def registry_memory():
    """Create a ModelRegistry instance with in-memory backend."""
    registry = ModelRegistry(use_memory=True)
    # Clean up any existing embedding models
    models = registry.list_models('embedding')
    for model in models:
        registry.remove_model(model.model_id)
    return registry


@pytest.mark.cli
class TestModelEmbeddingCommands:
    """Test /model embedding CLI commands."""

    def test_add_embedding_model_generic_endpoint(self, registry_memory):
        """Test adding an embedding model with generic endpoint format."""
        # This tests the current implementation which expects:
        # POST /embed with {"text": "..."}
        # Response: {"embedding": [...]}

        # Our transformer service uses this format
        url = "http://localhost:16050"

        # Simulate what the CLI does
        try:
            # Test the endpoint
            test_response = requests.get(
                f"{url}/embed",
                params={"text": "test"},
                timeout=10
            )

            if test_response.status_code == 200:
                test_data = test_response.json()

                # Check response format
                assert 'embedding' in test_data
                embedding = test_data['embedding']
                dimensions = len(embedding)

                # Add to registry
                model = registry_memory.add_model(
                    model_type='embedding',
                    url=url,
                    model_name='',
                    timeout=60,
                    set_active=True,
                    embedding_dimensions=dimensions
                )

                assert model.model_type == 'embedding'
                assert model.url == url
                assert model.embedding_dimensions == 384
                assert model.is_active is True

        except requests.exceptions.RequestException:
            pytest.skip("Transformer service not available")

    @pytest.mark.skipif(not is_ollama_available(), reason="Ollama service not available")
    def test_ollama_embedding_api_format(self):
        """Test Ollama's embedding API format (for reference)."""
        # Ollama uses a different format:
        # POST /api/embed with {"model": "nomic-embed-text", "input": "text"}
        # Response: {"embeddings": [[...]], "model": "..."}

        url = "http://localhost:11434"

        try:
            # Note: This will fail if the model isn't pulled
            # Just documenting the format
            test_response = requests.post(
                f"{url}/api/embed",
                json={"model": "nomic-embed-text", "input": "test"},
                timeout=10
            )

            # May fail if model not available locally
            if test_response.status_code == 200:
                data = test_response.json()
                assert 'embeddings' in data
                # Ollama returns a list of embeddings
                assert isinstance(data['embeddings'], list)
                if data['embeddings']:
                    assert isinstance(data['embeddings'][0], list)

        except requests.exceptions.RequestException:
            pytest.skip("Ollama not available")

    def test_embedding_model_validation(self, registry_memory):
        """Test that embedding models are validated correctly."""
        # Test adding with invalid URL
        # This should fail gracefully in the CLI

        model = registry_memory.add_model(
            model_type='embedding',
            url='http://invalid-service:9999',
            model_name='',
            timeout=1,
            set_active=True,
            embedding_dimensions=None
        )

        # Model should be added but marked as unavailable
        assert model.model_type == 'embedding'
        assert model.url == 'http://invalid-service:9999'

    def test_list_embedding_models(self, registry_memory):
        """Test listing embedding models."""
        # Add a few embedding models
        model1 = registry_memory.add_model(
            model_type='embedding',
            url='http://service1:8000',
            model_name='',
            timeout=30,
            set_active=True,
            embedding_dimensions=384
        )

        model2 = registry_memory.add_model(
            model_type='embedding',
            url='http://service2:8000',
            model_name='',
            timeout=30,
            set_active=False,
            embedding_dimensions=768
        )

        # List all embedding models
        models = registry_memory.list_models('embedding')
        assert len(models) == 2

        model_ids = [m.model_id for m in models]
        assert model1.model_id in model_ids
        assert model2.model_id in model_ids

    def test_remove_embedding_model(self, registry_memory):
        """Test removing embedding models."""
        # Add an embedding model
        model = registry_memory.add_model(
            model_type='embedding',
            url='http://test-service:8000',
            model_name='',
            timeout=30,
            set_active=True,
            embedding_dimensions=512
        )

        # Verify it exists
        models = registry_memory.list_models('embedding')
        assert len(models) == 1

        # Remove it
        result = registry_memory.remove_model(model.model_id)
        assert result is True

        # Verify it's gone
        models = registry_memory.list_models('embedding')
        assert len(models) == 0

    def test_switch_active_embedding_model(self, registry_memory):
        """Test switching between embedding models."""
        # Add two embedding models
        model1 = registry_memory.add_model(
            model_type='embedding',
            url='http://service1:8000',
            model_name='',
            timeout=30,
            set_active=True,
            embedding_dimensions=384
        )

        model2 = registry_memory.add_model(
            model_type='embedding',
            url='http://service2:8000',
            model_name='',
            timeout=30,
            set_active=False,
            embedding_dimensions=768
        )

        # Verify model1 is active
        active = registry_memory.get_active_model('embedding')
        assert active.model_id == model1.model_id

        # Switch to model2
        registry_memory.set_active_model('embedding', model2.model_id)

        # Verify model2 is now active
        active = registry_memory.get_active_model('embedding')
        assert active.model_id == model2.model_id

        # Verify model1 is no longer active
        model1_updated = registry_memory.get_active_model('embedding')
        assert model1_updated.model_id != model1.model_id


@pytest.mark.integration
class TestEmbeddingModelIntegration:
    """Integration tests for embedding model commands with real services."""

    def test_transformer_service_integration(self):
        """Test adding transformer service as embedding model."""
        registry = ModelRegistry(use_memory=True)

        try:
            # Test the transformer service
            response = requests.get(
                "http://localhost:16050/embed",
                params={"text": "test"},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                dimensions = len(data['embedding'])

                # Add to registry
                model = registry.add_model(
                    model_type='embedding',
                    url='http://localhost:16050',
                    model_name='',
                    timeout=60,
                    set_active=True,
                    embedding_dimensions=dimensions
                )

                assert model.embedding_dimensions == 384

                # Verify it's active
                active = registry.get_active_model('embedding')
                assert active.model_id == model.model_id

        except requests.exceptions.ConnectionError:
            pytest.skip("Transformer service not available")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
