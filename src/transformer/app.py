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


def chunk_code(code: str, tokenizer, max_tokens: int = 400, overlap: int = 50) -> list:
    """
    Split code into overlapping chunks that fit within token limit.
    
    Args:
        code: Code string to chunk
        tokenizer: Tokenizer to use for counting tokens
        max_tokens: Maximum tokens per chunk (default 400, leaving room for special tokens)
        overlap: Number of tokens to overlap between chunks (default 50)
    
    Returns:
        List of code chunks
    """
    # Tokenize the entire code
    tokens = tokenizer.encode(code, add_special_tokens=False)
    
    # If code fits in one chunk, return it
    if len(tokens) <= max_tokens:
        return [code]
    
    chunks = []
    start = 0
    
    while start < len(tokens):
        # Get chunk of tokens
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        
        # Decode back to text
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
        chunks.append(chunk_text)
        
        # Move to next chunk with overlap
        if end >= len(tokens):
            break
        start = end - overlap
    
    return chunks


def embed_code_chunk(code: str, model, tokenizer) -> np.ndarray:
    """
    Generate embedding for a single code chunk using mean pooling.
    
    Args:
        code: Code string to embed
        model: CodeBERT model
        tokenizer: CodeBERT tokenizer
    
    Returns:
        Embedding vector as numpy array
    """
    inputs = tokenizer(code, return_tensors='pt', truncation=True, max_length=512, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
        # Use mean pooling over all tokens (weighted by attention mask)
        attention_mask = inputs['attention_mask']
        token_embeddings = outputs.last_hidden_state
        # Expand attention mask to match embedding dimensions
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        # Sum embeddings and divide by number of tokens (mean pooling)
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        embedding = (sum_embeddings / sum_mask).squeeze().numpy()
    return embedding


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

        # Check if truncation occurred
        code_tokens = len(tokenizer.encode(code, add_special_tokens=True))
        was_truncated = code_tokens > 512

        # Generate embeddings
        with torch.no_grad():
            outputs = model(**inputs)
            # Use mean pooling over all tokens (weighted by attention mask)
            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state
            # Expand attention mask to match embedding dimensions
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            # Sum embeddings and divide by number of tokens (mean pooling)
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            embedding = (sum_embeddings / sum_mask).squeeze().numpy()

        result = {
            'status': 'success',
            'code': code,
            'language': language,
            'embedding': embedding.tolist(),
            'dimension': len(embedding),
            'model': 'microsoft/codebert-base'
        }
        
        if was_truncated:
            result['warning'] = f'Code was truncated from {code_tokens} to 512 tokens. Consider splitting large files for better embeddings.'
            result['truncated'] = True
        
        return jsonify(result), 200

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
        
        # Track truncation per code snippet
        truncation_info = []
        for code in codes:
            tokens = len(tokenizer.encode(code, add_special_tokens=True))
            truncation_info.append({
                'tokens': tokens,
                'truncated': tokens > 512
            })
        
        with torch.no_grad():
            outputs = model(**inputs)
            # Use mean pooling over all tokens for each code snippet
            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state
            # Expand attention mask to match embedding dimensions
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            # Sum embeddings and divide by number of tokens (mean pooling) for each snippet
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            embeddings = (sum_embeddings / sum_mask).cpu().numpy().tolist()

        result = {
            'status': 'success',
            'codes': codes,
            'languages': languages,
            'embeddings': embeddings,
            'count': len(codes),
            'dimension': len(embeddings[0]),
            'model': 'microsoft/codebert-base'
        }
        
        # Add truncation warnings if any code was truncated
        if any(info['truncated'] for info in truncation_info):
            result['truncation_info'] = truncation_info
            result['warning'] = 'One or more code snippets were truncated to 512 tokens'
        
        return jsonify(result), 200

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

        # Check if truncation will occur
        code1_tokens = len(tokenizer.encode(code1, add_special_tokens=True))
        code2_tokens = len(tokenizer.encode(code2, add_special_tokens=True))
        code1_truncated = code1_tokens > 512
        code2_truncated = code2_tokens > 512

        # Generate embeddings for both code snippets using mean pooling
        embeddings = []
        for code in [code1, code2]:
            inputs = tokenizer(code, return_tensors='pt', truncation=True, max_length=512, padding=True)
            with torch.no_grad():
                outputs = model(**inputs)
                # Use mean pooling over all tokens (weighted by attention mask)
                attention_mask = inputs['attention_mask']
                token_embeddings = outputs.last_hidden_state
                # Expand attention mask to match embedding dimensions
                input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                # Sum embeddings and divide by number of tokens (mean pooling)
                sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                embedding = (sum_embeddings / sum_mask).squeeze().numpy()
                embeddings.append(embedding)

        # Convert to numpy arrays
        vec1 = np.array(embeddings[0])
        vec2 = np.array(embeddings[1])

        # Calculate similarity
        similarity = calculate_similarity(vec1, vec2, metric=metric)

        result = {
            'status': 'success',
            'code1': code1,
            'code2': code2,
            'language1': language1,
            'language2': language2,
            'metric': metric,
            'similarity': float(similarity),
            'interpretation': _interpret_similarity(similarity, metric),
            'model': 'microsoft/codebert-base'
        }
        
        # Add truncation warnings
        if code1_truncated or code2_truncated:
            warnings = []
            if code1_truncated:
                warnings.append(f'Code1 was truncated from {code1_tokens} to 512 tokens')
            if code2_truncated:
                warnings.append(f'Code2 was truncated from {code2_tokens} to 512 tokens')
            result['warnings'] = warnings
            result['truncated'] = True
        
        return jsonify(result), 200

    except Exception as e:
        return handle_error(e)


@app.route('/code/similarity/chunked', methods=['POST'])
def compare_code_similarity_chunked():
    """
    Compare code similarity using chunked approach for large files.
    
    Splits both code snippets into overlapping chunks, compares each chunk pair,
    and aggregates results for a more accurate similarity score on large files.
    
    Request Body (JSON):
    - code1: First code snippet to compare
    - code2: Second code snippet to compare
    - language1: Optional programming language for code1
    - language2: Optional programming language for code2
    - metric: Distance metric (default: cosine). Options: cosine, euclidean, dot_product
    - chunk_size: Max tokens per chunk (default: 400)
    - overlap: Token overlap between chunks (default: 50)
    
    Returns:
    - similarity: Aggregated similarity score
    - chunk_similarities: Individual chunk comparison scores
    - num_chunks1: Number of chunks for code1
    - num_chunks2: Number of chunks for code2
    - metric: The metric used for comparison
    - interpretation: Human-readable interpretation
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
        chunk_size = data.get('chunk_size', 400)
        overlap = data.get('overlap', 50)
        
        # Validate metric
        valid_metrics = ['cosine', 'euclidean', 'dot_product']
        if metric not in valid_metrics:
            return jsonify({
                'status': 'error',
                'message': f'Invalid metric. Must be one of: {", ".join(valid_metrics)}'
            }), 400
        
        # Get CodeBERT model and tokenizer
        model, tokenizer = get_codebert_model()
        
        # Chunk both code snippets
        chunks1 = chunk_code(code1, tokenizer, max_tokens=chunk_size, overlap=overlap)
        chunks2 = chunk_code(code2, tokenizer, max_tokens=chunk_size, overlap=overlap)
        
        # Generate embeddings for all chunks
        embeddings1 = [embed_code_chunk(chunk, model, tokenizer) for chunk in chunks1]
        embeddings2 = [embed_code_chunk(chunk, model, tokenizer) for chunk in chunks2]
        
        # Compare chunks using different strategies
        chunk_similarities = []
        
        # Strategy 1: Compare corresponding chunks (pairs by position)
        min_chunks = min(len(chunks1), len(chunks2))
        for i in range(min_chunks):
            sim = calculate_similarity(embeddings1[i], embeddings2[i], metric=metric)
            chunk_similarities.append({
                'chunk1_index': i,
                'chunk2_index': i,
                'similarity': float(sim),
                'comparison_type': 'positional'
            })
        
        # Strategy 2: Find max similarity for each chunk1 against all chunks2
        max_similarities = []
        for i, emb1 in enumerate(embeddings1):
            similarities_for_chunk = []
            for j, emb2 in enumerate(embeddings2):
                sim = calculate_similarity(emb1, emb2, metric=metric)
                similarities_for_chunk.append(float(sim))
            max_sim = max(similarities_for_chunk)
            max_similarities.append(max_sim)
        
        # Calculate aggregate scores
        positional_avg = np.mean([cs['similarity'] for cs in chunk_similarities]) if chunk_similarities else 0.0
        max_avg = np.mean(max_similarities) if max_similarities else 0.0
        
        # Use weighted average: favor positional but consider max similarity
        if len(chunks1) == len(chunks2) == 1:
            # Both fit in single chunk, use direct comparison
            final_similarity = positional_avg
        else:
            # Weight positional more heavily, but account for max similarity
            final_similarity = 0.6 * positional_avg + 0.4 * max_avg
        
        result = {
            'status': 'success',
            'similarity': float(final_similarity),
            'positional_similarity': float(positional_avg),
            'max_match_similarity': float(max_avg),
            'num_chunks1': len(chunks1),
            'num_chunks2': len(chunks2),
            'chunk_size': chunk_size,
            'overlap': overlap,
            'code1_length': len(code1),
            'code2_length': len(code2),
            'language1': language1,
            'language2': language2,
            'metric': metric,
            'interpretation': _interpret_similarity(final_similarity, metric),
            'model': 'microsoft/codebert-base',
            'chunk_similarities': chunk_similarities,
            'note': f'Chunked comparison: code1 split into {len(chunks1)} chunks, code2 into {len(chunks2)} chunks'
        }
        
        return jsonify(result), 200
        
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


@app.route('/synthetic/generate', methods=['POST'])
def generate_synthetic_data():
    """
    Generate synthetic data using WGAN (fast) or CTGAN (high quality).
    
    Request Body (JSON):
    - data: List of dictionaries representing the dataset
    - num_rows: Number of rows from original data to use for training (optional, defaults to all rows)
    - num_samples: Number of synthetic samples to generate (default: 100)
    - model: Model type - 'wgan' for fast or 'ctgan' for high-quality tabular data (default: 'wgan')
    - epochs: Training epochs (default: 300 for wgan, 500 for ctgan)
    
    Returns:
    - synthetic_data: List of generated synthetic records
    - num_samples: Number of samples generated
    - num_rows_used: Number of rows from original data used for training
    - model_used: Model type used for generation
    """
    try:
        data = request.get_json()
        if not data or 'data' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing data in request body'
            }), 400
        
        import pandas as pd
        from ydata_synthetic.synthesizers import ModelParameters
        from ydata_synthetic.synthesizers.regular import RegularSynthesizer
        from ydata_synthetic.synthesizers.base import TrainParameters
        
        # Parse parameters
        input_data = data['data']
        num_rows = data.get('num_rows')  # Optional: limit rows used for training
        num_samples = data.get('num_samples', 100)
        model_type = data.get('model', 'wgan')
        epochs = data.get('epochs', 300 if model_type == 'wgan' else 500)
        
        # Validate model type
        # Available models: wgan (fast), ctgan (high-quality for tabular data)
        if model_type not in ['wgan', 'ctgan']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid model type. Must be "wgan" (fast) or "ctgan" (high-quality tabular)'
            }), 400
        
        # Convert to DataFrame
        df = pd.DataFrame(input_data)
        
        # Limit rows if num_rows is specified
        original_size = len(df)
        if num_rows is not None and num_rows > 0:
            if num_rows > len(df):
                return jsonify({
                    'status': 'error',
                    'message': f'num_rows ({num_rows}) exceeds dataset size ({len(df)} rows)'
                }), 400
            df = df.head(num_rows)
        
        # Validate minimum data size
        if len(df) < 10:
            return jsonify({
                'status': 'error',
                'message': f'Dataset too small ({len(df)} rows). Minimum 10 rows required.'
            }), 400
        
        # Identify numeric and categorical columns
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        if not numeric_cols and not categorical_cols:
            return jsonify({
                'status': 'error',
                'message': 'No suitable columns found. Need numeric or categorical columns.'
            }), 400
        
        # Configure model parameters (epochs is passed to fit(), not ModelParameters)
        batch_size = min(500, len(df))
        
        # Different parameters for WGAN vs CTGAN
        if model_type == 'wgan':
            model_params = ModelParameters(
                batch_size=batch_size,
                lr=0.001,
                betas=(0.5, 0.9)
            )
            # WGAN requires n_critic as a separate parameter (not in ModelParameters)
            synthesizer = RegularSynthesizer(
                modelname=model_type,
                model_parameters=model_params,
                n_critic=5  # Number of critic updates per generator update
            )
        else:  # ctgan
            model_params = ModelParameters(
                batch_size=batch_size,
                lr=0.0002,
                betas=(0.5, 0.9)
            )
            # Initialize CTGAN synthesizer (Conditional Tabular GAN for high-quality tabular data)
            synthesizer = RegularSynthesizer(
                modelname=model_type,
                model_parameters=model_params
            )
        
        # Create TrainParameters object
        train_params = TrainParameters(epochs=epochs)
        
        synthesizer.fit(
            data=df,
            train_arguments=train_params,
            num_cols=numeric_cols,
            cat_cols=categorical_cols
        )
        
        # Generate synthetic data
        synthetic_df = synthesizer.sample(num_samples)
        
        return jsonify({
            'status': 'success',
            'synthetic_data': synthetic_df.to_dict(orient='records'),
            'num_samples': len(synthetic_df),
            'num_rows_used': len(df),
            'original_dataset_size': original_size,
            'num_columns': len(synthetic_df.columns),
            'columns': synthetic_df.columns.tolist(),
            'model_used': model_type,
            'epochs': epochs
        }), 200
        
    except ImportError as e:
        return jsonify({
            'status': 'error',
            'message': f'ydata-synthetic not installed: {str(e)}'
        }), 500
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
    print("  GET  /keywords?text=<text> - Extract keywords from text")
    print("  GET  /similarity?text1=<text>&text2=<text> - Compare similarity between two texts")
    print("  POST /code/embed - Generate code embeddings using CodeBERT")
    print("  POST /code/embed/batch - Generate embeddings for multiple code snippets")
    print("  POST /code/similarity - Compare similarity between two code snippets")
    print("  POST /synthetic/generate - Generate synthetic data using WGAN or CTGAN")
    print()

    # Run the app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
