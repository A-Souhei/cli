"""Transformer NLP Service

A minimal Flask-based microservice ready for future NLP capabilities.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from sentry_config import configure_sentry, capture_exception

from flask import Flask, jsonify, request
from flask_cors import CORS
from sentence_transformers import SentenceTransformer
from nlp_tasks import analyze_sentiment, summarize_text

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure Sentry
configure_sentry(service_name="transformer-nlp")

# Load embedding model
model = None


def get_model():
    """Lazy load the embedding model."""
    global model
    if model is None:
        model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        model = SentenceTransformer(model_name)
    return model


def handle_error(e, status_code=500):
    """Centralized error handler that logs to Sentry."""
    capture_exception(e)
    return jsonify({
        'status': 'error',
        'message': str(e)
    }), status_code


@app.route('/', methods=['GET'])
def index():
    """Root endpoint."""
    return jsonify({
        'service': 'transformer-nlp',
        'version': '1.0.0',
        'status': 'ready'
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'transformer-nlp',
        'version': '1.0.0'
    })


@app.route('/embed', methods=['GET'])
def embed_text():
    """
    Embed text and return the embedding vector.

    Query Parameters:
    - text: The text to embed

    Returns:
    - embedding: List of float values representing the text embedding
    - dimension: Size of the embedding vector
    """
    try:
        text = request.args.get('text')

        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Missing text parameter'
            }), 400

        # Get the model and generate embedding
        embedding_model = get_model()
        embedding = embedding_model.encode(text)

        return jsonify({
            'status': 'success',
            'text': text,
            'embedding': embedding.tolist(),
            'dimension': len(embedding)
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/embed/batch', methods=['GET'])
def embed_batch():
    """
    Embed a batch of texts and return their embedding vectors.

    Query Parameters:
    - texts: JSON array of texts to embed (e.g., ["text1", "text2", "text3"])

    Returns:
    - embeddings: List of embedding vectors
    - count: Number of texts embedded
    - dimension: Size of each embedding vector
    """
    try:
        texts_param = request.args.get('texts')

        if not texts_param:
            return jsonify({
                'status': 'error',
                'message': 'Missing texts parameter'
            }), 400

        # Parse JSON array
        import json
        try:
            texts = json.loads(texts_param)
        except json.JSONDecodeError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format for texts parameter'
            }), 400

        if not isinstance(texts, list) or not texts:
            return jsonify({
                'status': 'error',
                'message': 'texts parameter must be a non-empty JSON array'
            }), 400

        # Get the model and generate embeddings
        embedding_model = get_model()
        embeddings = embedding_model.encode(texts)

        return jsonify({
            'status': 'success',
            'texts': texts,
            'embeddings': [emb.tolist() for emb in embeddings],
            'count': len(texts),
            'dimension': len(embeddings[0])
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/sentiment', methods=['GET'])
def sentiment_analysis():
    """
    Analyze sentiment of the given text.

    Query Parameters:
    - text: The text to analyze

    Returns:
    - label: Sentiment label (POSITIVE or NEGATIVE)
    - score: Confidence score (0-1)
    """
    try:
        text = request.args.get('text')

        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Missing text parameter'
            }), 400

        result = analyze_sentiment(text)

        return jsonify({
            'status': 'success',
            'text': text,
            'sentiment': result
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/summarize', methods=['GET'])
def summarize():
    """
    Summarize the given text.

    Query Parameters:
    - text: The text to summarize
    - max_length: Maximum length of summary (default: 130)
    - min_length: Minimum length of summary (default: 30)

    Returns:
    - summary: The summarized text
    - original_length: Length of original text
    - summary_length: Length of summary
    """
    try:
        text = request.args.get('text')

        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Missing text parameter'
            }), 400

        max_length = request.args.get('max_length', type=int, default=130)
        min_length = request.args.get('min_length', type=int, default=30)

        result = summarize_text(text, max_length=max_length, min_length=min_length)

        return jsonify({
            'status': 'success',
            'text': text,
            **result
        }), 200

    except Exception as e:
        return handle_error(e)


# Global error handler for uncaught exceptions
@app.errorhandler(Exception)
def handle_uncaught_exception(e):
    """Handle any uncaught exceptions."""
    return handle_error(e)


if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.getenv('PORT', 5050))

    print(f"Starting Transformer NLP Service on port {port}...")
    print("Available endpoints:")
    print("  GET  / - Service information")
    print("  GET  /health - Health check")
    print("  GET  /embed?text=<text> - Generate text embeddings")
    print("  GET  /embed/batch?texts=<json_array> - Generate embeddings for multiple texts")
    print("  GET  /sentiment?text=<text> - Analyze sentiment")
    print("  GET  /summarize?text=<text> - Summarize text")
    print()

    # Run the app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
