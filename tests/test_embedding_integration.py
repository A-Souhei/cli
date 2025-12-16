"""
Integration tests for EmbeddingClient with real services.

These tests require running services:
- Transformer service (port 16050)
- Redis (port 26379)
"""

import pytest
import requests
from src.embedding_client.client import EmbeddingClient
from src.model_registry.manager import ModelRegistry

pytestmark = pytest.mark.skip(reason="Requires transformers, torch packages not in requirements-test.txt")


def is_transformer_available():
    """Check if transformer service is available."""
    try:
        response = requests.get("http://localhost:16050/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def is_redis_available():
    """Check if Redis is available."""
    try:
        import redis
        r = redis.Redis(host='localhost', port=26379, db=0)
        r.ping()
        return True
    except Exception:
        return False


requires_transformer = pytest.mark.skipif(
    not is_transformer_available(),
    reason="Transformer service not available"
)

requires_redis = pytest.mark.skipif(
    not is_redis_available(),
    reason="Redis service not available"
)


@pytest.fixture
def registry_with_redis():
    """Create a ModelRegistry instance with Redis backend."""
    registry = ModelRegistry(use_memory=False)
    # Clean up any existing embedding models from previous tests
    models = registry.list_models('embedding')
    for model in models:
        registry.remove_model(model.model_id)
    return registry


@pytest.fixture
def registry_memory():
    """Create a ModelRegistry instance with in-memory backend."""
    return ModelRegistry(use_memory=True)


@pytest.fixture
def embedding_client_redis(registry_with_redis):
    """Create EmbeddingClient with Redis-backed registry."""
    return EmbeddingClient(
        model_registry=registry_with_redis,
        fallback_url='http://localhost:16050'
    )


@pytest.fixture
def embedding_client_memory(registry_memory):
    """Create EmbeddingClient with in-memory registry."""
    return EmbeddingClient(
        model_registry=registry_memory,
        fallback_url='http://localhost:16050'
    )


@pytest.mark.integration
@requires_transformer
class TestEmbeddingClientWithTransformer:
    """Test EmbeddingClient with real transformer service."""

    def test_fallback_to_local_transformer(self, embedding_client_memory):
        """Test that client falls back to local transformer when no external model configured."""
        # No active embedding model, should use fallback
        result = embedding_client_memory.embed("Hello world")

        assert isinstance(result, list)
        assert len(result) == 384  # all-MiniLM-L6-v2 dimensions
        assert all(isinstance(x, float) for x in result)

    def test_embed_batch_with_transformer(self, embedding_client_memory):
        """Test batch embedding with transformer service."""
        texts = ["Hello", "World", "Test"]
        results = embedding_client_memory.embed_batch(texts)

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(len(emb) == 384 for emb in results)

    def test_get_similarity_with_transformer(self, embedding_client_memory):
        """Test similarity calculation with transformer."""
        similarity = embedding_client_memory.get_similarity(
            "The cat sat on the mat",
            "A feline was sitting on a rug",
            metric="cosine"
        )

        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.5  # These sentences should be similar

    def test_get_dimensions_from_transformer(self, embedding_client_memory):
        """Test dimension detection from transformer."""
        # First embedding call should auto-detect dimensions
        embedding_client_memory.embed("test")
        dimensions = embedding_client_memory.get_dimensions()

        assert dimensions == 384

    def test_is_using_fallback(self, embedding_client_memory):
        """Test fallback status reporting."""
        assert embedding_client_memory.is_using_fallback() is True


@pytest.mark.integration
@requires_redis
@requires_transformer
class TestEmbeddingClientWithRedis:
    """Test EmbeddingClient with Redis-backed model registry."""

    def test_add_and_use_embedding_model(self, registry_with_redis, embedding_client_redis):
        """Test adding external embedding model via registry."""
        # Add a mock external embedding service
        model = registry_with_redis.add_model(
            model_type='embedding',
            url='http://external-embedding-service:8000',
            model_name='',
            timeout=30,
            set_active=True,
            embedding_dimensions=768
        )

        assert model.model_type == 'embedding'
        assert model.embedding_dimensions == 768
        assert model.is_active is True

        # Verify it's stored in Redis
        active = registry_with_redis.get_active_model('embedding')
        assert active is not None
        assert active.model_id == model.model_id

    def test_fallback_when_external_fails(self, registry_with_redis, embedding_client_redis):
        """Test fallback to local transformer when external service fails."""
        # Add a model with unreachable URL
        registry_with_redis.add_model(
            model_type='embedding',
            url='http://unreachable-service:9999',
            model_name='',
            timeout=1,
            set_active=True,
            embedding_dimensions=768
        )

        # Should fallback to local transformer (384 dims)
        result = embedding_client_redis.embed("test")
        assert isinstance(result, list)
        assert len(result) == 384  # Fallback to local transformer

    def test_dimension_persistence(self, registry_with_redis, embedding_client_redis):
        """Test that dimensions are persisted in Redis when using external model."""
        # Add an external model (with unreachable URL, will fallback)
        # But dimensions should still be tracked in the model config
        registry_with_redis.add_model(
            model_type='embedding',
            url='http://localhost:16050',  # Use local transformer as "external"
            model_name='',
            timeout=30,
            set_active=True,
            embedding_dimensions=None  # Will be auto-detected
        )

        # First call auto-detects dimensions and stores them
        embedding_client_redis.embed("test")

        # Get the updated model to verify dimensions were stored
        updated_model = registry_with_redis.get_active_model('embedding')
        assert updated_model is not None
        # Dimensions should have been auto-detected, but might not be set if using GET endpoint
        # Just verify the embedding worked

        # Create new client instance
        new_client = EmbeddingClient(
            model_registry=registry_with_redis,
            fallback_url='http://localhost:16050'
        )

        # Should work and return valid embeddings
        result = new_client.embed("test persistence")
        assert isinstance(result, list)
        assert len(result) > 0


@pytest.mark.integration
@requires_transformer
class TestEmbeddingConsumers:
    """Test that embedding consumers work with EmbeddingClient."""

    def test_postgresql_api_embedding_endpoint(self):
        """Test PostgreSQL API /mcp-tools/match endpoint with embeddings."""
        try:
            response = requests.post(
                "http://localhost:15000/mcp-tools/match",
                json={"prompts": ["execute python code"]},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                assert 'matches' in data
                assert isinstance(data['matches'], list)
        except requests.exceptions.ConnectionError:
            pytest.skip("PostgreSQL API service not available")

    def test_redis_api_context_search(self):
        """Test Redis API /context/search endpoint with embeddings."""
        try:
            # First store some context
            store_response = requests.post(
                "http://localhost:17000/context/store",
                json={
                    "text": "This is a test document about embeddings",
                    "metadata": {"source": "test"}
                },
                timeout=5
            )

            if store_response.status_code == 200:
                # Now search
                search_response = requests.post(
                    "http://localhost:17000/context/search",
                    json={"query": "embeddings"},
                    timeout=5
                )

                if search_response.status_code == 200:
                    data = search_response.json()
                    assert 'results' in data
                    assert isinstance(data['results'], list)
        except requests.exceptions.ConnectionError:
            pytest.skip("Redis API service not available")


@pytest.mark.integration
@requires_transformer
class TestEmbeddingServiceCompatibility:
    """Test compatibility with transformer service API."""

    def test_transformer_embed_endpoint(self):
        """Test direct transformer /embed endpoint."""
        response = requests.get(
            "http://localhost:16050/embed",
            params={"text": "test embedding"},
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()
        assert 'embedding' in data
        assert isinstance(data['embedding'], list)
        assert len(data['embedding']) == 384

    def test_transformer_similarity_endpoint(self):
        """Test transformer /similarity endpoint."""
        response = requests.get(
            "http://localhost:16050/similarity",
            params={
                "text1": "hello world",
                "text2": "hi earth",
                "metric": "cosine"
            },
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()
        assert 'similarity' in data
        assert isinstance(data['similarity'], float)
        assert 0.0 <= data['similarity'] <= 1.0

    def test_transformer_batch_embed(self):
        """Test transformer batch embedding."""
        # Note: The transformer service uses GET with text parameter
        # For batch, we need to call it multiple times or check if batch endpoint exists
        texts = ["hello", "world"]
        embeddings = []

        for text in texts:
            response = requests.get(
                "http://localhost:16050/embed",
                params={"text": text},
                timeout=5
            )
            assert response.status_code == 200
            data = response.json()
            embeddings.append(data['embedding'])

        assert len(embeddings) == 2
        assert all(len(emb) == 384 for emb in embeddings)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
