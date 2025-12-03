"""Rating and guidance functionality for the AI CLI."""

import json
import requests

# API Configuration (can be overridden by importing module)
POSTGRES_API_URL = "http://localhost:15000"
TRANSFORMER_API_URL = "http://localhost:16050"
SIMILARITY_THRESHOLD = 0.7  # Cosine similarity threshold for considering prompts similar
SATISFACTORY_RATING_THRESHOLD = 7  # Rating >= 7 is considered satisfactory

# EmbeddingClient instance (set by caller)
_embedding_client = None


def set_embedding_client(client):
    """Set the EmbeddingClient instance to use for similarity calculations."""
    global _embedding_client
    _embedding_client = client


def configure(postgres_url=None, transformer_url=None, similarity_threshold=None, satisfactory_threshold=None):
    """Configure the rating module with custom URLs and thresholds."""
    global POSTGRES_API_URL, TRANSFORMER_API_URL, SIMILARITY_THRESHOLD, SATISFACTORY_RATING_THRESHOLD
    if postgres_url:
        POSTGRES_API_URL = postgres_url
    if transformer_url:
        TRANSFORMER_API_URL = transformer_url
    if similarity_threshold is not None:
        SIMILARITY_THRESHOLD = similarity_threshold
    if satisfactory_threshold is not None:
        SATISFACTORY_RATING_THRESHOLD = satisfactory_threshold


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
    """Check similarity between two texts using embedding service."""
    try:
        # Try to use EmbeddingClient if available
        if _embedding_client:
            return _embedding_client.get_similarity(text1, text2, metric='cosine')
        
        # Fallback to direct transformer service call
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


def create_rating(user_rating, prompt_text, response_text, tags, session_id=None):
    """Create a new rating in the postgres-api."""
    try:
        data = {
            'user_rating': user_rating,
            'prompt_text': prompt_text,
            'response_text': response_text,
            'tags': json.dumps({'keywords': tags})
        }
        if session_id:
            data['session_id'] = session_id
        response = requests.post(
            f"{POSTGRES_API_URL}/ratings/create",
            data=data,
            timeout=10
        )
        return response.status_code == 201
    except Exception as e:
        print(f"[Warning] Could not create rating: {e}")
        return False


def update_rating(rating_id, user_rating, response_text, tags):
    """Update an existing rating in the postgres-api."""
    try:
        payload = {
            'user_rating': user_rating,
            'response_text': response_text,
            'tags': {'keywords': tags}
        }
        response = requests.patch(
            f"{POSTGRES_API_URL}/ratings/{rating_id}/update",
            json=payload,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"[Warning] Could not update rating: {e}")
        return False


def find_similar_prompt(prompt_text, existing_ratings):
    """
    Find the most similar prompt from existing ratings.

    Args:
        prompt_text: The prompt to compare
        existing_ratings: List of existing rating records

    Returns:
        Tuple of (best_match, best_similarity) or (None, 0) if no match found
    """
    best_match = None
    best_similarity = 0

    for rating in existing_ratings:
        stored_prompt = rating.get('prompt_text', '')
        if stored_prompt:
            similarity = check_similarity(prompt_text, stored_prompt)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = rating

    return best_match, best_similarity


def process_rating(user_rating, prompt_text, response_text, session_id=None, debug_print_func=None):
    """
    Process the user rating by:
    1. Getting all existing ratings
    2. Finding similar prompts
    3. Updating or creating as needed
    
    Args:
        user_rating: The user's rating (1-10)
        prompt_text: The prompt text
        response_text: The LLM response text
        session_id: Optional session ID
        debug_print_func: Optional function for debug output
    """
    def _debug(msg, **kwargs):
        if debug_print_func:
            debug_print_func(msg, **kwargs)
    
    # Get all existing ratings
    existing_ratings = get_all_ratings()

    # Extract keywords from current response
    keywords = extract_keywords(response_text)

    # Find the most similar prompt (reuse logic)
    best_match, best_similarity = find_similar_prompt(prompt_text, existing_ratings)

    # Check if we found a similar prompt
    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        stored_rating = best_match.get('user_rating', 0)
        # Update if current rating is higher or equal
        if user_rating >= stored_rating:
            if update_rating(best_match['id'], user_rating, response_text, keywords):
                _debug(f"Rating updated - Similar prompt (similarity: {best_similarity:.2f}), {stored_rating} → {user_rating}", icon="✅", style="green")
                _debug(f"Keywords: {', '.join(keywords)}", icon="🏷️", style="cyan")
            else:
                _debug("Failed to update existing rating", icon="❌", style="red")
        else:
            _debug(f"Rating skipped - Stored rating higher ({stored_rating} > {user_rating})", icon="⏭️", style="yellow")
    else:
        # No similar prompt found, create new entry
        if create_rating(user_rating, prompt_text, response_text, keywords, session_id):
            _debug(f"New prompt stored with rating {user_rating}", icon="💾", style="green")
            _debug(f"Keywords: {', '.join(keywords)}", icon="🏷️", style="cyan")
        else:
            _debug("Failed to save new rating", icon="❌", style="red")


def get_prompt_guidance(prompt_text):
    """
    Get guidance for the LLM based on similar past prompts and their ratings.

    Returns a guidance string to inject into the conversation, or None if no guidance.
    """
    # Get all existing ratings
    existing_ratings = get_all_ratings()

    if not existing_ratings:
        return None

    # Find the most similar prompt (reuse shared logic)
    best_match, best_similarity = find_similar_prompt(prompt_text, existing_ratings)

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
