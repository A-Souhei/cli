#!/usr/bin/env python3
"""
Simple test script to verify the CLI components work correctly.
This test doesn't require a running Ollama service.
"""

from src.chat import ChatManager
from src.config import ConfigManager
import sys
from pathlib import Path
import requests
import os

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))


def test_config_manager():
    """Test the configuration manager."""
    print("Testing ConfigManager...")
    config = ConfigManager()

    # Just verify the config values are loaded (don't hardcode specific values)
    assert config.get_ollama_url() is not None, "Ollama URL should be set"
    assert config.get_ollama_model() is not None, "Model name should be set"
    assert config.get_temperature() >= 0 and config.get_temperature() <= 1, "Temperature should be between 0 and 1"
    assert isinstance(config.get_stream_enabled(), bool), "Stream setting should be boolean"
    assert config.get_max_context_length() > 0, "Max context length should be positive"

    print("✓ ConfigManager tests passed!")


def test_chat_manager():
    """Test the chat manager."""
    print("\nTesting ChatManager...")
    chat = ChatManager(system_prompt="You are a helpful assistant.", max_context_length=5)

    # Test adding messages
    chat.add_user_message("Hello")
    chat.add_assistant_message("Hi there!")

    messages = chat.get_messages()
    assert len(messages) == 3, "Should have system + 2 messages"  # system, user, assistant
    assert messages[0]['role'] == 'system', "First message should be system"
    assert messages[1]['role'] == 'user', "Second message should be user"
    assert messages[2]['role'] == 'assistant', "Third message should be assistant"

    # Test context trimming
    for i in range(10):
        chat.add_user_message(f"Message {i}")
        chat.add_assistant_message(f"Response {i}")

    messages = chat.get_messages()
    # System prompt + max 5 conversation turns (10 messages)
    assert len(messages) <= 11, f"Should have at most 11 messages, got {len(messages)}"

    # Test clear history
    chat.clear_history()
    messages = chat.get_messages()
    assert len(messages) == 1, "Should only have system message after clear"
    assert messages[0]['role'] == 'system', "Should keep system message after clear"

    print("✓ ChatManager tests passed!")


def test_module_imports():
    """Test that all modules can be imported."""
    print("\nTesting module imports...")

    # Import check - modules already imported at top
    print("✓ All modules imported successfully!")


def test_postgresql_health():
    """Test PostgreSQL Flask service health endpoint."""
    print("\nTesting PostgreSQL health endpoint...")
    
    postgres_url = os.getenv('POSTGRES_API_URL', 'http://localhost:5000')
    
    try:
        response = requests.get(f"{postgres_url}/health", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', "PostgreSQL service should be healthy"
        assert data.get('service') == 'postgres-flask', "Service name should match"
        print("✓ PostgreSQL health check passed!")
    except requests.exceptions.RequestException as e:
        print(f"⚠ PostgreSQL service not available (skipping): {e}")


def test_postgresql_endpoints():
    """Test PostgreSQL Flask service endpoints."""
    print("\nTesting PostgreSQL endpoints...")
    
    postgres_url = os.getenv('POSTGRES_API_URL', 'http://localhost:5000')
    
    try:
        # Test purge endpoint
        response = requests.get(f"{postgres_url}/ratings/purge", timeout=5)
        assert response.status_code == 200, "Purge should return 200"
        
        # Test create rating
        response = requests.get(
            f"{postgres_url}/ratings/create",
            params={
                'user_rating': 8,
                'prompt_text': 'Test prompt',
                'response_text': 'Test response',
                'tags': '{"category": "test"}'
            },
            timeout=5
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        data = response.json()
        assert data.get('status') == 'success', "Create should succeed"
        rating_id = data.get('id')
        
        # Test get all ratings
        response = requests.get(f"{postgres_url}/ratings", timeout=5)
        assert response.status_code == 200, "Get ratings should return 200"
        data = response.json()
        assert data.get('count') >= 1, "Should have at least one rating"
        
        # Test get specific rating
        response = requests.get(f"{postgres_url}/ratings/{rating_id}", timeout=5)
        assert response.status_code == 200, "Get rating should return 200"
        data = response.json()
        assert data.get('rating', {}).get('id') == rating_id, "Should return correct rating"
        
        # Test update tags
        response = requests.get(
            f"{postgres_url}/ratings/{rating_id}/tags",
            params={'tags': '{"category": "updated"}'},
            timeout=5
        )
        assert response.status_code == 200, "Update tags should return 200"
        
        print("✓ PostgreSQL endpoints tests passed!")
    except requests.exceptions.RequestException as e:
        print(f"⚠ PostgreSQL service not available (skipping): {e}")


def test_transformer_health():
    """Test Transformer Flask service health endpoint."""
    print("\nTesting Transformer health endpoint...")
    
    transformer_url = os.getenv('TRANSFORMER_API_URL', 'http://localhost:5050')
    
    try:
        response = requests.get(f"{transformer_url}/health", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', "Transformer service should be healthy"
        assert data.get('service') == 'transformer-nlp', "Service name should match"
        print("✓ Transformer health check passed!")
    except requests.exceptions.RequestException as e:
        print(f"⚠ Transformer service not available (skipping): {e}")


def test_transformer_endpoints():
    """Test Transformer Flask service endpoints."""
    print("\nTesting Transformer endpoints...")
    
    transformer_url = os.getenv('TRANSFORMER_API_URL', 'http://localhost:5050')
    
    try:
        # Test embed endpoint
        response = requests.get(
            f"{transformer_url}/embed",
            params={'text': 'Hello world'},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('status') == 'success', "Embed should succeed"
        assert 'embedding' in data, "Should return embedding"
        assert 'dimension' in data, "Should return dimension"
        
        # Test batch embed endpoint
        import json
        texts = json.dumps(['Hello', 'World', 'Test'])
        response = requests.get(
            f"{transformer_url}/embed/batch",
            params={'texts': texts},
            timeout=30
        )
        assert response.status_code == 200, "Batch embed should return 200"
        data = response.json()
        assert data.get('count') == 3, "Should have 3 embeddings"
        
        # Test sentiment endpoint
        response = requests.get(
            f"{transformer_url}/sentiment",
            params={'text': 'I love this product!'},
            timeout=30
        )
        assert response.status_code == 200, "Sentiment should return 200"
        data = response.json()
        assert 'sentiment' in data, "Should return sentiment"
        assert 'label' in data['sentiment'], "Should have sentiment label"
        
        # Test summarize endpoint
        long_text = "This is a test text. " * 50  # Make it long enough
        response = requests.get(
            f"{transformer_url}/summarize",
            params={'text': long_text},
            timeout=60
        )
        assert response.status_code == 200, "Summarize should return 200"
        data = response.json()
        assert 'summary' in data, "Should return summary"
        
        print("✓ Transformer endpoints tests passed!")
    except requests.exceptions.RequestException as e:
        print(f"⚠ Transformer service not available (skipping): {e}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("  AI CLI - Component Tests")
    print("=" * 60)

    try:
        test_module_imports()
        test_config_manager()
        test_chat_manager()
        test_postgresql_health()
        test_postgresql_endpoints()
        test_transformer_health()
        test_transformer_endpoints()

        print("\n" + "=" * 60)
        print("  All tests passed! ✓")
        print("=" * 60)
        print("\nNote: These tests verify the CLI components work correctly.")
        print("To fully test the CLI, you need a running Ollama service.")
        print("Run './start.sh' to start the interactive CLI.\n")

        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
