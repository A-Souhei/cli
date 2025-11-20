"""Main entry point for the AI CLI application."""

import sys
import json
import argparse
import requests
import urllib.parse
from pathlib import Path
from src.config import ConfigManager
from src.ollama_client import OllamaClient
from src.chat import ChatManager
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import FormattedText

# Initialize rich console
console = Console()

# Set up history file
HISTORY_FILE = Path.home() / ".ai_cli_history"

# API Configuration
POSTGRES_API_URL = "http://localhost:15000"
TRANSFORMER_API_URL = "http://localhost:16050"
SIMILARITY_THRESHOLD = 0.7  # Cosine similarity threshold for considering prompts similar
SATISFACTORY_RATING_THRESHOLD = 7  # Rating >= 7 is considered satisfactory

# Global verbose flag
VERBOSE = False


def debug_print(message, style="dim", icon="🔍"):
    """Print message only if verbose mode is enabled."""
    if VERBOSE:
        console.print(f"{icon} {message}", style=style)


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
        # Update if current rating is higher or equal
        if user_rating >= stored_rating:
            if update_rating(best_match['id'], user_rating, response_text, keywords):
                debug_print(f"Rating updated - Similar prompt (similarity: {best_similarity:.2f}), {stored_rating} → {user_rating}", "green", "✅")
                debug_print(f"Keywords: {', '.join(keywords)}", "cyan", "🏷️")
            else:
                debug_print("Failed to update existing rating", "red", "❌")
        else:
            debug_print(f"Rating skipped - Stored rating higher ({stored_rating} > {user_rating})", "yellow", "⏭️")
    else:
        # No similar prompt found, create new entry
        if create_rating(user_rating, prompt_text, response_text, keywords):
            debug_print(f"New prompt stored with rating {user_rating}", "green", "💾")
            debug_print(f"Keywords: {', '.join(keywords)}", "cyan", "🏷️")
        else:
            debug_print("Failed to save new rating", "red", "❌")


def get_prompt_guidance(prompt_text):
    """
    Get guidance for the LLM based on similar past prompts and their ratings.

    Returns a guidance string to inject into the conversation, or None if no guidance.
    """
    # Get all existing ratings
    existing_ratings = get_all_ratings()

    if not existing_ratings:
        return None

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
        tags = best_match.get('tags', {})
        keywords = tags.get('keywords', []) if isinstance(tags, dict) else []

        if not keywords:
            return None

        keywords_str = ', '.join(keywords)

        if stored_rating >= SATISFACTORY_RATING_THRESHOLD:
            # Satisfactory response - use these keywords
            guidance = (
                f"[Context: A similar question was previously answered satisfactorily. "
                f"Consider incorporating these relevant concepts: {keywords_str}]"
            )
        else:
            # Unsatisfactory response - avoid these keywords
            guidance = (
                f"[Context: A similar question was previously answered unsatisfactorily. "
                f"Consider avoiding or improving upon these concepts: {keywords_str}]"
            )

        return guidance

    return None


def print_banner():
    """Print CLI banner."""
    banner_text = Text()
    banner_text.append("🤖 AI CLI", style="bold cyan")
    banner_text.append(" - Powered by Ollama", style="dim")

    console.print()
    console.print(Panel(banner_text, border_style="cyan"))
    console.print("  Type [bold]'exit'[/bold] or [bold]'quit'[/bold] to exit")
    console.print("  Type [bold]'clear'[/bold] to clear chat history")
    console.print("  Type [bold]'models'[/bold] to list available models")
    console.print()


def main(verbose=False):
    """Main function to run the AI CLI."""
    global VERBOSE
    VERBOSE = verbose

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
        console.print(f"  📦 Model: [bold]{config.get_ollama_model()}[/bold]")
        console.print(f"  🔗 Server: [dim]{config.get_ollama_url()}[/dim]")
        console.print()

        # Initialize command history
        history = FileHistory(str(HISTORY_FILE))

        # Main chat loop
        while True:
            try:
                # Get user input with history support
                user_input = prompt(
                    FormattedText([('class:prompt', '👤 You: ')]),
                    history=history
                ).strip()

                # Handle special commands
                if user_input.lower() in ['exit', 'quit']:
                    console.print("\n👋 [bold]Goodbye![/bold]")
                    break

                if user_input.lower() == 'clear':
                    chat_manager.clear_history()
                    console.print("\n🗑️ [yellow]Chat history cleared[/yellow]\n")
                    continue

                if user_input.lower() == 'models':
                    console.print("\n📋 [bold]Available models:[/bold]")
                    try:
                        models = ollama_client.list_models()
                        for model in models:
                            if model == config.get_ollama_model():
                                console.print(f"  • {model} [cyan](current)[/cyan]")
                            else:
                                console.print(f"  • {model}")
                    except Exception as e:
                        console.print(f"❌ [red]Error listing models: {e}[/red]")
                    console.print()
                    continue

                # Skip empty input
                if not user_input:
                    continue

                # Get guidance based on similar past prompts
                guidance = get_prompt_guidance(user_input)

                # Add user message to context
                chat_manager.add_user_message(user_input)

                # Get messages and inject guidance if available
                messages = chat_manager.get_messages()
                if guidance:
                    # Insert guidance as a system message before the last user message
                    guidance_message = {'role': 'system', 'content': guidance}
                    # Insert before the last message (which is the user's current message)
                    messages = messages[:-1] + [guidance_message, messages[-1]]
                    debug_print(guidance, "magenta", "🧠")

                # Get AI response
                console.print("🤖 [bold cyan]AI:[/bold cyan]")

                # Get response (stream or not) and collect full response
                if stream:
                    full_response = ""
                    for chunk in ollama_client.chat(
                        messages=messages,
                        stream=True,
                        temperature=temperature
                    ):
                        full_response += chunk
                else:
                    response = ollama_client.chat(
                        messages=messages,
                        stream=False,
                        temperature=temperature
                    )
                    full_response = response.get('message', {}).get('content', '')

                # Render response as markdown
                console.print(Markdown(full_response))

                # Add assistant response to context
                chat_manager.add_assistant_message(full_response)

                console.print()  # Extra line for readability

                # Ask for rating
                try:
                    rating_input = prompt("⭐ Rate (0-10, Enter to skip): ").strip()

                    if rating_input:  # User provided input
                        try:
                            rating = int(rating_input)
                            if 0 <= rating <= 10:
                                process_rating(rating, user_input, full_response)
                            else:
                                console.print("❌ [red]Invalid rating. Enter 0-10.[/red]")
                        except ValueError:
                            console.print("❌ [red]Invalid input. Enter a number.[/red]")
                    # If empty input (Enter pressed), do nothing - silently skip
                except EOFError:
                    pass  # Handle piped input gracefully

                console.print()  # Extra line for readability

            except KeyboardInterrupt:
                console.print("\n\n👋 [bold]Goodbye![/bold]")
                break
            except Exception as e:
                console.print(f"\n❌ [red]Error: {e}[/red]")
                console.print("[dim]Please try again.[/dim]\n")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure config.yaml exists in the project root.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing CLI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI CLI - Powered by Ollama")
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose mode to show debug information'
    )
    args = parser.parse_args()
    main(verbose=args.verbose)
