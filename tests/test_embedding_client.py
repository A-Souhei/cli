"""Unit tests for EmbeddingClient."""

import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.skip(reason="Requires transformers, torch packages not in requirements-test.txt")

from src.embedding_client.client import EmbeddingClient
from src.model_registry.manager import ModelRegistry


@pytest.fixture
def mock_registry():
    """Create a mock ModelRegistry for testing."""
    registry = ModelRegistry(use_memory=True)
    return registry


@pytest.fixture
def embedding_client(mock_registry):
    """Create an EmbeddingClient instance for testing."""
    return EmbeddingClient(
        model_registry=mock_registry,
        fallback_url='http://localhost:16050'
    )


def test_init(mock_registry):
    """Test EmbeddingClient initialization."""
    client = EmbeddingClient(mock_registry, 'http://test:8000')
    assert client.model_registry == mock_registry
    assert client.fallback_url == 'http://test:8000'
    assert client._last_dimensions is None


def test_get_active_embedding_config_no_model(embedding_client, mock_registry):
    """Test getting config when no active embedding model exists."""
    config = embedding_client._get_active_embedding_config()
    assert config is None


def test_get_active_embedding_config_with_model(embedding_client, mock_registry):
    """Test getting config when active embedding model exists."""
    # Add an embedding model
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60,
        embedding_dimensions=384
    )
    
    config = embedding_client._get_active_embedding_config()
    assert config is not None
    assert config[0] == 'http://external:8000'
    assert config[1] == 60
    assert config[2] == 384


@patch('requests.post')
def test_call_external_service_single_text(mock_post, embedding_client):
    """Test calling external service with single text."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'embedding': [0.1, 0.2, 0.3],
        'dimensions': 3
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = embedding_client._call_external_service(
        'http://test:8000',
        30,
        ['Hello world']
    )
    
    assert result['embeddings'] == [[0.1, 0.2, 0.3]]
    assert result['dimensions'] == 3
    mock_post.assert_called_once()


@patch('requests.post')
def test_call_external_service_batch(mock_post, embedding_client):
    """Test calling external service with batch of texts."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'embeddings': [[0.1, 0.2], [0.3, 0.4]],
        'dimensions': 2
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = embedding_client._call_external_service(
        'http://test:8000',
        30,
        ['Hello', 'World']
    )
    
    assert result['embeddings'] == [[0.1, 0.2], [0.3, 0.4]]
    assert result['dimensions'] == 2


@patch('requests.get')
def test_call_local_service(mock_get, embedding_client):
    """Test calling local transformer service."""
    mock_response1 = MagicMock()
    mock_response1.json.return_value = {
        'status': 'success',
        'embedding': [0.1, 0.2, 0.3],
        'dimension': 3
    }
    mock_response1.raise_for_status = MagicMock()
    
    mock_response2 = MagicMock()
    mock_response2.json.return_value = {
        'status': 'success',
        'embedding': [0.4, 0.5, 0.6],
        'dimension': 3
    }
    mock_response2.raise_for_status = MagicMock()
    
    mock_get.side_effect = [mock_response1, mock_response2]
    
    result = embedding_client._call_local_service(['Hello', 'World'])
    
    assert result['embeddings'] == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert result['dimensions'] == 3
    assert mock_get.call_count == 2


def test_auto_detect_dimensions(embedding_client, mock_registry):
    """Test auto-detecting embedding dimensions."""
    # Add embedding model without dimensions
    model = mock_registry.add_model(
        model_type='embedding',
        url='http://test:8000',
        model_name='',
        timeout=60
    )
    
    # Auto-detect dimensions
    sample_embedding = [0.1, 0.2, 0.3, 0.4]
    dims = embedding_client._auto_detect_dimensions(model.model_id, sample_embedding)
    
    assert dims == 4
    assert embedding_client._last_dimensions == 4
    
    # Verify it was stored in registry
    updated_model = mock_registry.get_model(model.model_id)
    assert updated_model.embedding_dimensions == 4


@patch('requests.post')
def test_embed_single_text_external(mock_post, embedding_client, mock_registry):
    """Test embedding single text with external service."""
    # Add external model
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60,
        embedding_dimensions=3
    )
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'embedding': [0.1, 0.2, 0.3],
        'dimensions': 3
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = embedding_client.embed('Hello')
    
    assert result == [0.1, 0.2, 0.3]


@patch('requests.get')
def test_embed_fallback_to_local(mock_get, embedding_client):
    """Test fallback to local service when no external model."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'status': 'success',
        'embedding': [0.1, 0.2, 0.3],
        'dimension': 3
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response
    
    result = embedding_client.embed('Hello')
    
    assert result == [0.1, 0.2, 0.3]
    assert embedding_client._last_dimensions == 3


@patch('requests.post')
@patch('requests.get')
def test_embed_fallback_on_external_failure(mock_get, mock_post, embedding_client, mock_registry):
    """Test fallback to local when external service fails."""
    # Add external model
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60
    )
    
    # External service fails
    mock_post.side_effect = Exception("Connection failed")
    
    # Local service succeeds
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'status': 'success',
        'embedding': [0.1, 0.2, 0.3],
        'dimension': 3
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response
    
    result = embedding_client.embed('Hello')
    
    assert result == [0.1, 0.2, 0.3]


@patch('requests.post')
def test_embed_batch(mock_post, embedding_client, mock_registry):
    """Test batch embedding."""
    # Add external model
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60,
        embedding_dimensions=2
    )
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'embeddings': [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
        'dimensions': 2
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = embedding_client.embed_batch(['Hello', 'World', 'Test'])
    
    assert len(result) == 3
    assert result[0] == [0.1, 0.2]
    assert result[1] == [0.3, 0.4]
    assert result[2] == [0.5, 0.6]


def test_embed_batch_empty(embedding_client):
    """Test batch embedding with empty list."""
    result = embedding_client.embed_batch([])
    assert result == []


@patch('requests.post')
def test_get_similarity(mock_post, embedding_client, mock_registry):
    """Test similarity calculation."""
    # Add external model
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60,
        embedding_dimensions=3
    )
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'embeddings': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        'dimensions': 3
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    # Test cosine similarity (should be 0 for orthogonal vectors)
    similarity = embedding_client.get_similarity('Hello', 'World', metric='cosine')
    assert abs(similarity) < 0.01  # Close to 0


@patch('requests.post')
def test_get_similarity_invalid_metric(mock_post, embedding_client, mock_registry):
    """Test similarity with invalid metric."""
    # Add external model
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60,
        embedding_dimensions=3
    )
    
    # Mock the embedding response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'embeddings': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        'dimensions': 3
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    with pytest.raises(ValueError, match="Unsupported metric"):
        embedding_client.get_similarity('Hello', 'World', metric='invalid')


def test_get_dimensions_no_model(embedding_client):
    """Test getting dimensions when no model is configured."""
    dims = embedding_client.get_dimensions()
    assert dims is None


def test_get_dimensions_from_model(embedding_client, mock_registry):
    """Test getting dimensions from active model."""
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60,
        embedding_dimensions=768
    )
    
    dims = embedding_client.get_dimensions()
    assert dims == 768


def test_is_using_fallback_no_model(embedding_client):
    """Test checking fallback status when no external model."""
    assert embedding_client.is_using_fallback() is True


def test_is_using_fallback_with_model(embedding_client, mock_registry):
    """Test checking fallback status when external model exists."""
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60
    )
    
    assert embedding_client.is_using_fallback() is False


@patch('requests.post')
def test_dimension_mismatch_warning(mock_post, embedding_client, mock_registry):
    """Test warning when dimensions mismatch."""
    # Add model with expected dimensions
    mock_registry.add_model(
        model_type='embedding',
        url='http://external:8000',
        model_name='',
        timeout=60,
        embedding_dimensions=3
    )
    
    # Return different dimensions
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'embeddings': [[0.1, 0.2, 0.3, 0.4]],  # 4 dimensions instead of 3
        'dimensions': 4
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    # Should emit warning
    with pytest.warns(RuntimeWarning, match="Embedding dimension mismatch"):
        embedding_client.embed_batch(['Hello'])
