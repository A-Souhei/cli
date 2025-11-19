#!/usr/bin/env python3
"""
Simple test script to verify the CLI components work correctly.
This test doesn't require a running Ollama service.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import ConfigManager
from src.chat import ChatManager


def test_config_manager():
    """Test the configuration manager."""
    print("Testing ConfigManager...")
    config = ConfigManager()
    
    assert config.get_ollama_url() == "http://localhost:11434", "Ollama URL mismatch"
    assert config.get_ollama_model() == "tinyllama", "Model name mismatch"
    assert config.get_temperature() == 0.7, "Temperature mismatch"
    assert config.get_stream_enabled() is True, "Stream setting mismatch"
    assert config.get_max_context_length() == 10, "Max context length mismatch"
    
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
    
    from src.config import ConfigManager
    from src.ollama_client import OllamaClient
    from src.chat import ChatManager
    
    print("✓ All modules imported successfully!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("  AI CLI - Component Tests")
    print("=" * 60)
    
    try:
        test_module_imports()
        test_config_manager()
        test_chat_manager()
        
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
