"""Main entry point for the AI CLI application."""

import sys
import json
import requests
import urllib.parse
from src.config import ConfigManager
from src.ollama_client import OllamaClient
from src.chat import ChatManager

# API Configuration
POSTGRES_API_URL = "http://localhost:15000"
TRANSFORMER_API_URL = "http://localhost:16050"
SIMILARITY_THRESHOLD = 0.7  # Cosine similarity threshold for considering prompts similar


def get_all_ratings():
    """Get all ratings from the postgres-api."""
    try:
        response = requests.get(f"{POSTGRES_API_URL}/ratings", timeout=10)
        if response.status_code == 200:
            return response.json().get('ratings', [])
        return []
    except Exception as e:
        print(f"[Warning] Could not fetch ratings: {e}")
        return []


def check_similarity(text1, text2):
    """Check similarity between two texts using transformer service."""
    try:
        params = {
            'text1': text1,
            'text2': text2,
            'metric': 'cosine'
        }
        response = requests.get(
            f"{TRANSFORMER_API_URL}/similarity",
            params=params,
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get('similarity', 0)
        return 0
    except Exception as e:
        print(f"[Warning] Could not check similarity: {e}")
        return 0


def extract_keywords(text, top_n=5):
    """Extract keywords from text using transformer service."""
    try:
        params = {
            'text': text,
            'top_n': top_n
        }
        response = requests.get(
            f"{TRANSFORMER_API_URL}/keywords",
            params=params,
            timeout=30
        )
        if response.status_code == 200:
            keywords_data = response.json().get('keywords', [])
            return [kw['keyword'] for kw in keywords_data]
        return []
    except Exception as e:
        print(f"[Warning] Could not extract keywords: {e}")
        return []


def create_rating(user_rating, prompt_text, response_text, tags):
    """Create a new rating in the postgres-api."""
    try:
        params = {
            'user_rating': user_rating,
            'prompt_text': prompt_text,
            'response_text': response_text,
            'tags': json.dumps({'keywords': tags})
        }
        response = requests.get(
            f"{POSTGRES_API_URL}/ratings/create",
            params=params,
            timeout=10
        )
        return response.status_code == 201
    except Exception as e:
        print(f"[Warning] Could not create rating: {e}")
        return False


def update_rating(rating_id, user_rating, response_text, tags):
    """Update an existing rating in the postgres-api."""
    try:
        params = {
            'user_rating': user_rating,
            'response_text': response_text,
            'tags': json.dumps({'keywords': tags})
        }
        response = requests.get(
            f"{POSTGRES_API_URL}/ratings/{rating_id}/update",
            params=params,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"[Warning] Could not update rating: {e}")
        return False


def process_rating(user_rating, prompt_text, response_text):
    """
    Process the user rating by:
    1. Getting all existing ratings
    2. Finding similar prompts
    3. Updating or creating as needed
    """
    # Get all existing ratings
    existing_ratings = get_all_ratings()

    # Extract keywords from current response
    keywords = extract_keywords(response_text)

    # Find the most similar prompt
    best_match = None
    best_similarity = 0

    for rating in existing_ratings:
        stored_prompt = rating.get('prompt_text', '')
        if stored_prompt:
            similarity = check_similarity(prompt_text, stored_prompt)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = rating

    # Check if we found a similar prompt
    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        stored_rating = best_match.get('user_rating', 0)
        # Update if current rating is higher
        if user_rating > stored_rating:
            if update_rating(best_match['id'], user_rating, response_text, keywords):
                print(f"[Rating updated] Similar prompt found (similarity: {best_similarity:.2f}), updated rating from {stored_rating} to {user_rating}")
            else:
                print("[Rating] Failed to update existing rating")
        else:
            print(f"[Rating skipped] Similar prompt found with higher rating ({stored_rating} >= {user_rating})")
    else:
        # No similar prompt found, create new entry
        if create_rating(user_rating, prompt_text, response_text, keywords):
            print(f"[Rating saved] New prompt stored with rating {user_rating}")
        else:
            print("[Rating] Failed to save new rating")


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

                    print()  # Extra line for readability

                    # Ask for rating
                    try:
                        rating_input = input("Rate this response (0-10, or press Enter to skip): ").strip()

                        if rating_input:  # User provided input
                            try:
                                rating = int(rating_input)
                                if 0 <= rating <= 10:
                                    process_rating(rating, user_input, full_response)
                                else:
                                    print("[Rating] Invalid rating. Please enter a number between 0 and 10.")
                            except ValueError:
                                print("[Rating] Invalid input. Please enter a number between 0 and 10.")
                        # If empty input (Enter pressed), do nothing - silently skip
                    except EOFError:
                        pass  # Handle piped input gracefully

                    print()  # Extra line for readability
                else:
                    # Non-streaming response
                    response = ollama_client.chat(
                        messages=chat_manager.get_messages(),
                        stream=False,
                        temperature=temperature
                    )
                    full_response = response.get('message', {}).get('content', '')
                    print(full_response)

                    # Add assistant response to context
                    chat_manager.add_assistant_message(full_response)

                    print()  # Extra line for readability

                    # Ask for rating
                    try:
                        rating_input = input("Rate this response (0-10, or press Enter to skip): ").strip()

                        if rating_input:  # User provided input
                            try:
                                rating = int(rating_input)
                                if 0 <= rating <= 10:
                                    process_rating(rating, user_input, full_response)
                                else:
                                    print("[Rating] Invalid rating. Please enter a number between 0 and 10.")
                            except ValueError:
                                print("[Rating] Invalid input. Please enter a number between 0 and 10.")
                        # If empty input (Enter pressed), do nothing - silently skip
                    except EOFError:
                        pass  # Handle piped input gracefully

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
