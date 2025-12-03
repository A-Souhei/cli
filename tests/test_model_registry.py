"""Unit tests for ModelRegistry."""

import pytest
from src.model_registry.manager import ModelRegistry, ModelConfig


@pytest.fixture
def registry():
    """Create a ModelRegistry instance for testing (explicit in-memory mode)."""
    reg = ModelRegistry(use_memory=True)
    return reg


def test_add_model(registry):
    """Test adding a model to the registry."""
    model = registry.add_model(
        model_type='general',
        url='http://localhost:11434',
        model_name='llama3.1:8b',
        timeout=120,
        set_active=True
    )

    assert model.model_type == 'general'
    assert model.url == 'http://localhost:11434'
    assert model.model_name == 'llama3.1:8b'
    assert model.timeout == 120
    assert model.is_active is True
    assert model.model_id.startswith('model_')


def test_add_invalid_model_type(registry):
    """Test adding a model with invalid type."""
    with pytest.raises(ValueError):
        registry.add_model(
            model_type='invalid',
            url='http://localhost:11434',
            model_name='test',
            timeout=120
        )


def test_list_models(registry):
    """Test listing models."""
    # Add some models
    registry.add_model('general', 'http://localhost:11434', 'llama3', 120)
    registry.add_model('coder', 'http://localhost:11434', 'qwen', 120)

    # List all models
    all_models = registry.list_models()
    assert len(all_models) == 2

    # List by type
    general_models = registry.list_models('general')
    assert len(general_models) == 1
    assert general_models[0].model_type == 'general'

    coder_models = registry.list_models('coder')
    assert len(coder_models) == 1
    assert coder_models[0].model_type == 'coder'


def test_get_active_model(registry):
    """Test getting the active model."""
    model1 = registry.add_model('general', 'http://localhost:11434', 'llama3', 120, set_active=True)
    model2 = registry.add_model('general', 'http://localhost:11434', 'llama2', 120, set_active=False)

    active = registry.get_active_model('general')
    assert active is not None
    assert active.model_id == model1.model_id
    assert active.is_active is True


def test_set_active_model(registry):
    """Test setting a model as active."""
    model1 = registry.add_model('general', 'http://localhost:11434', 'llama3', 120, set_active=True)
    model2 = registry.add_model('general', 'http://localhost:11434', 'llama2', 120, set_active=False)

    # Initially model1 is active
    active = registry.get_active_model('general')
    assert active.model_id == model1.model_id

    # Switch to model2
    result = registry.set_active_model(model2.model_id)
    assert result is True

    # Verify model2 is now active
    active = registry.get_active_model('general')
    assert active.model_id == model2.model_id
    assert active.is_active is True


def test_remove_model(registry):
    """Test removing a model."""
    model = registry.add_model('general', 'http://localhost:11434', 'llama3', 120)

    # Model should exist
    assert registry.get_model(model.model_id) is not None

    # Remove it
    result = registry.remove_model(model.model_id)
    assert result is True

    # Model should not exist
    assert registry.get_model(model.model_id) is None


def test_remove_nonexistent_model(registry):
    """Test removing a model that doesn't exist."""
    result = registry.remove_model('nonexistent_id')
    assert result is False


def test_update_availability(registry):
    """Test updating model availability."""
    model = registry.add_model('general', 'http://localhost:11434', 'llama3', 120)

    # Initially availability is None
    assert model.is_available is None

    # Update availability
    result = registry.update_availability(model.model_id, True)
    assert result is True

    # Check updated value
    updated_model = registry.get_model(model.model_id)
    assert updated_model.is_available is True
    assert updated_model.last_checked is not None


def test_get_status(registry):
    """Test getting registry status."""
    registry.add_model('general', 'http://localhost:11434', 'llama3', 120)
    registry.add_model('coder', 'http://localhost:11434', 'qwen', 120)

    status = registry.get_status()

    assert status['redis_available'] is False  # In-memory mode
    assert 'general' in status['models']
    assert 'coder' in status['models']
    assert status['models']['general']['count'] == 1
    assert status['models']['coder']['count'] == 1


def test_multiple_models_same_type(registry):
    """Test adding multiple models of the same type."""
    model1 = registry.add_model('general', 'http://localhost:11434', 'llama3', 120, set_active=True)
    model2 = registry.add_model('general', 'http://remote:11434', 'llama2', 120, set_active=False)
    model3 = registry.add_model('general', 'http://other:11434', 'mistral', 120, set_active=False)

    models = registry.list_models('general')
    assert len(models) == 3

    # Only model1 should be active
    active = registry.get_active_model('general')
    assert active.model_id == model1.model_id


def test_remove_active_model(registry):
    """Test removing the active model clears the active status."""
    model1 = registry.add_model('general', 'http://localhost:11434', 'llama3', 120, set_active=True)
    model2 = registry.add_model('general', 'http://localhost:11434', 'llama2', 120, set_active=False)

    # Remove active model
    registry.remove_model(model1.model_id)

    # No active model should be set
    active = registry.get_active_model('general')
    assert active is None


def test_model_config_serialization(registry):
    """Test ModelConfig to_dict and from_dict."""
    model = registry.add_model('general', 'http://localhost:11434', 'llama3', 120)

    # Convert to dict
    model_dict = model.to_dict()
    assert isinstance(model_dict, dict)
    assert model_dict['model_name'] == 'llama3'

    # Convert back to ModelConfig
    restored = ModelConfig.from_dict(model_dict)
    assert restored.model_id == model.model_id
    assert restored.model_name == model.model_name
    assert restored.url == model.url
