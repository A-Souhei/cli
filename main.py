"""Main entry point for the AI CLI application."""

import sys
from src.config import ConfigManager
from src.ollama_client import OllamaClient
from src.chat import ChatManager


def print_banner():
    """Print CLI banner."""
    print("\n" + "=" * 50)
    print("  AI CLI - Powered by Ollama")
    print("=" * 50)
    print("Type 'exit' or 'quit' to exit")
    print("Type 'clear' to clear chat history")
    print("Type 'models' to list available models")
    print("=" * 50 + "\n")


def main():
    """Main function to run the AI CLI."""
    try:
        # Load configuration
        config = ConfigManager()
        
        # Initialize Ollama client
        ollama_client = OllamaClient(
            host=config.get_ollama_url(),
            model=config.get_ollama_model(),
            timeout=config.get_ollama_timeout()
        )
        
        # Initialize chat manager
        chat_manager = ChatManager(
            system_prompt=config.get_system_prompt(),
            max_context_length=config.get_max_context_length()
        )
        
        # Get configuration
        temperature = config.get_temperature()
        stream = config.get_stream_enabled()
        
        print_banner()
        print(f"Using model: {config.get_ollama_model()}")
        print(f"Connected to: {config.get_ollama_url()}\n")
        
        # Main chat loop
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                # Handle special commands
                if user_input.lower() in ['exit', 'quit']:
                    print("\nGoodbye!")
                    break
                
                if user_input.lower() == 'clear':
                    chat_manager.clear_history()
                    print("\n[Chat history cleared]\n")
                    continue
                
                if user_input.lower() == 'models':
                    print("\nAvailable models:")
                    try:
                        models = ollama_client.list_models()
                        for model in models:
                            marker = " (current)" if model == config.get_ollama_model() else ""
                            print(f"  - {model}{marker}")
                    except Exception as e:
                        print(f"Error listing models: {e}")
                    print()
                    continue
                
                # Skip empty input
                if not user_input:
                    continue
                
                # Add user message to context
                chat_manager.add_user_message(user_input)
                
                # Get AI response
                print("AI: ", end='', flush=True)
                
                if stream:
                    # Stream response
                    full_response = ""
                    for chunk in ollama_client.chat(
                        messages=chat_manager.get_messages(),
                        stream=True,
                        temperature=temperature
                    ):
                        print(chunk, end='', flush=True)
                        full_response += chunk
                    print()  # New line after streaming
                    
                    # Add assistant response to context
                    chat_manager.add_assistant_message(full_response)
                else:
                    # Non-streaming response
                    response = ollama_client.chat(
                        messages=chat_manager.get_messages(),
                        stream=False,
                        temperature=temperature
                    )
                    content = response.get('message', {}).get('content', '')
                    print(content)
                    
                    # Add assistant response to context
                    chat_manager.add_assistant_message(content)
                
                print()  # Extra line for readability
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")
                print("Please try again.\n")
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure config.yaml exists in the project root.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing CLI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
