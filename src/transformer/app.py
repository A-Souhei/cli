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
from nlp_tasks import analyze_sentiment, summarize_text, extract_keywords
from embedding_similarity import calculate_similarity
import numpy as np
import torch

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure Sentry
configure_sentry(service_name="transformer-nlp")

# Load embedding model
model = None
codebert_model = None
codebert_tokenizer = None


def get_model():
    """Lazy load the embedding model."""
    global model
    if model is None:
        model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        model = SentenceTransformer(model_name)
    return model


def get_codebert_model():
    """Lazy load the CodeBERT model for code embeddings."""
    global codebert_model, codebert_tokenizer
    if codebert_model is None:
        from transformers import AutoTokenizer, AutoModel
        model_name = 'microsoft/codebert-base'
        codebert_tokenizer = AutoTokenizer.from_pretrained(model_name)
        codebert_model = AutoModel.from_pretrained(model_name)
    return codebert_model, codebert_tokenizer


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


@app.route('/keywords', methods=['GET'])
def extract_keywords_endpoint():
    """
    Extract keywords from the given text.

    Query Parameters:
    - text: The text to extract keywords from
    - top_n: Number of keywords to extract (default: 5)

    Returns:
    - keywords: List of keywords with their relevance scores
    - count: Number of keywords extracted
    """
    try:
        text = request.args.get('text')

        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Missing text parameter'
            }), 400

        top_n = request.args.get('top_n', type=int, default=5)

        result = extract_keywords(text, top_n=top_n)

        return jsonify({
            'status': 'success',
            'text': text,
            **result
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/code/embed', methods=['POST'])
def embed_code():
    """
    Generate embeddings for code snippets using CodeBERT.

    Request Body (JSON):
    - code: The code snippet to embed
    - language: Optional programming language (e.g., python, javascript)

    Returns:
    - embedding: List of float values representing the code embedding
    - dimension: Size of the embedding vector
    - model: Model used for embedding
    """
    try:
        
        data = request.get_json()
        if not data or 'code' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing code in request body'
            }), 400

        code = data['code']
        language = data.get('language', '')

        # Get CodeBERT model and tokenizer
        model, tokenizer = get_codebert_model()

        # Tokenize the code
        inputs = tokenizer(code, return_tensors='pt', truncation=True, max_length=512, padding=True)

        # Generate embeddings
        with torch.no_grad():
            outputs = model(**inputs)
            # Use [CLS] token embedding as code representation
            embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()

        return jsonify({
            'status': 'success',
            'code': code,
            'language': language,
            'embedding': embedding.tolist(),
            'dimension': len(embedding),
            'model': 'microsoft/codebert-base'
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/code/embed/batch', methods=['POST'])
def embed_code_batch():
    """
    Generate embeddings for multiple code snippets using CodeBERT.

    Request Body (JSON):
    - codes: List of code snippets to embed
    - languages: Optional list of programming languages (same length as codes)

    Returns:
    - embeddings: List of embedding vectors
    - count: Number of code snippets embedded
    - dimension: Size of each embedding vector
    - model: Model used for embedding
    """
    try:
        
        data = request.get_json()
        if not data or 'codes' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing codes array in request body'
            }), 400

        codes = data['codes']
        languages = data.get('languages', [''] * len(codes))

        if not isinstance(codes, list) or not codes:
            return jsonify({
                'status': 'error',
                'message': 'codes must be a non-empty array'
            }), 400

        # Get CodeBERT model and tokenizer
        model, tokenizer = get_codebert_model()

        # Batched tokenization and model inference for efficiency
        inputs = tokenizer(
            codes,
            return_tensors='pt',
            truncation=True,
            max_length=512,
            padding=True
        )
        with torch.no_grad():
            outputs = model(**inputs)
            # Use [CLS] token embedding as code representation for each code snippet
            embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy().tolist()

        return jsonify({
            'status': 'success',
            'codes': codes,
            'languages': languages,
            'embeddings': embeddings,
            'count': len(codes),
            'dimension': len(embeddings[0]),
            'model': 'microsoft/codebert-base'
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/similarity', methods=['GET'])
def compare_similarity():
    """
    Compare the similarity between two texts using embeddings.

    Query Parameters:
    - text1: First text to compare
    - text2: Second text to compare
    - metric: Distance metric (default: cosine). Options: cosine, euclidean, dot_product

    Returns:
    - similarity: Similarity score between the two texts
    - metric: The metric used for comparison
    - text1: First text
    - text2: Second text
    """
    try:
        text1 = request.args.get('text1')
        text2 = request.args.get('text2')

        if not text1 or not text2:
            return jsonify({
                'status': 'error',
                'message': 'Missing text1 or text2 parameter'
            }), 400

        metric = request.args.get('metric', 'cosine')
        
        # Validate metric
        valid_metrics = ['cosine', 'euclidean', 'dot_product']
        if metric not in valid_metrics:
            return jsonify({
                'status': 'error',
                'message': f'Invalid metric. Must be one of: {", ".join(valid_metrics)}'
            }), 400

        # Get the model and generate embeddings
        embedding_model = get_model()
        embedding1 = embedding_model.encode(text1)
        embedding2 = embedding_model.encode(text2)

        # Convert to numpy arrays if needed
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Calculate similarity
        similarity = calculate_similarity(vec1, vec2, metric=metric)

        return jsonify({
            'status': 'success',
            'text1': text1,
            'text2': text2,
            'metric': metric,
            'similarity': float(similarity),
            'interpretation': _interpret_similarity(similarity, metric)
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/code/similarity', methods=['POST'])
def compare_code_similarity():
    """
    Compare the similarity between two code snippets using CodeBERT embeddings.

    Request Body (JSON):
    - code1: First code snippet to compare
    - code2: Second code snippet to compare
    - language1: Optional programming language for code1
    - language2: Optional programming language for code2
    - metric: Distance metric (default: cosine). Options: cosine, euclidean, dot_product

    Returns:
    - similarity: Similarity score between the two code snippets
    - metric: The metric used for comparison
    - interpretation: Human-readable interpretation of the score
    - model: Model used for embeddings
    """
    try:
        
        data = request.get_json()
        if not data or 'code1' not in data or 'code2' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing code1 or code2 in request body'
            }), 400

        code1 = data['code1']
        code2 = data['code2']
        language1 = data.get('language1', '')
        language2 = data.get('language2', '')
        metric = data.get('metric', 'cosine')

        # Validate metric
        valid_metrics = ['cosine', 'euclidean', 'dot_product']
        if metric not in valid_metrics:
            return jsonify({
                'status': 'error',
                'message': f'Invalid metric. Must be one of: {", ".join(valid_metrics)}'
            }), 400

        # Get CodeBERT model and tokenizer
        model, tokenizer = get_codebert_model()

        # Generate embeddings for both code snippets
        embeddings = []
        for code in [code1, code2]:
            inputs = tokenizer(code, return_tensors='pt', truncation=True, max_length=512, padding=True)
            with torch.no_grad():
                outputs = model(**inputs)
                embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()
                embeddings.append(embedding)

        # Convert to numpy arrays
        vec1 = np.array(embeddings[0])
        vec2 = np.array(embeddings[1])

        # Calculate similarity
        similarity = calculate_similarity(vec1, vec2, metric=metric)

        return jsonify({
            'status': 'success',
            'code1': code1,
            'code2': code2,
            'language1': language1,
            'language2': language2,
            'metric': metric,
            'similarity': float(similarity),
            'interpretation': _interpret_similarity(similarity, metric),
            'model': 'microsoft/codebert-base'
        }), 200

    except Exception as e:
        return handle_error(e)


def _interpret_similarity(score: float, metric: str) -> str:
    """Helper function to interpret similarity scores."""
    if metric == 'cosine':
        if score > 0.9:
            return 'Very similar'
        elif score > 0.7:
            return 'Similar'
        elif score > 0.5:
            return 'Somewhat similar'
        elif score > 0.3:
            return 'Slightly similar'
        else:
            return 'Not similar'
    elif metric == 'dot_product':
        # Interpretation depends on embedding normalization
        return 'Higher values indicate more similarity'
    elif metric == 'euclidean':
        # For euclidean, we return inverse (1/(1+distance)) so higher is better
        if score > 0.8:
            return 'Very similar'
        elif score > 0.6:
            return 'Similar'
        elif score > 0.4:
            return 'Somewhat similar'
        else:
            return 'Not similar'
    return 'Unknown'


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
    print("  GET  /keywords?text=<text> - Extract keywords from text")
    print("  GET  /similarity?text1=<text>&text2=<text> - Compare similarity between two texts")
    print("  POST /code/embed - Generate code embeddings using CodeBERT")
    print("  POST /code/embed/batch - Generate embeddings for multiple code snippets")
    print("  POST /code/similarity - Compare similarity between two code snippets")
    print()

    # Run the app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
