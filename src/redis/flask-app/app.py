"""Flask API for Redis vector storage (RAG embeddings)."""

from flask import Flask, jsonify, request
import redis
import json
import requests
import os
import sys
from datetime import datetime

# Add shared source directory to path
sys.path.insert(0, '/app/src_shared')

from sentry_config import configure_sentry, capture_exception

# Configure Sentry
configure_sentry(service_name="redis-flask")

app = Flask(__name__)

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'redis')
redis_port = int(os.getenv('REDIS_PORT', '6379'))

# Transformer service configuration
TRANSFORMER_API_URL = os.getenv('TRANSFORMER_API_URL', 'http://transformer:5050')

# Initialize Redis client
redis_client = redis.Redis(
    host=redis_host,
    port=redis_port,
    decode_responses=True,
    socket_connect_timeout=5
)


def handle_error(e, status_code=500):
    """Centralized error handler that logs to Sentry."""
    capture_exception(e)
    return jsonify({
        'status': 'error',
        'message': str(e)
    }), status_code


def get_embedding(text):
    """Get embedding from transformer service."""
    # Validate input
    if not text or not text.strip():
        print("Warning: Empty or whitespace-only text provided for embedding")
        return None

    try:
        response = requests.get(
            f"{TRANSFORMER_API_URL}/embed",
            params={"text": text},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get('embedding')
        return None
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None


def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        redis_client.ping()
        return jsonify({
            'status': 'healthy',
            'service': 'redis-flask',
            'redis_connected': True
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'service': 'redis-flask',
            'redis_connected': False,
            'error': str(e)
        }), 503


def cleanup_expired_temp_contexts():
    """
    Remove expired entries from temp:contexts sorted set.
    Removes all entries with score (expiration timestamp) less than current time.
    """
    try:
        current_time = datetime.utcnow().timestamp()
        # Remove all entries with expiration time < current time
        removed_count = redis_client.zremrangebyscore("temp:contexts", 0, current_time)
        return removed_count
    except Exception as e:
        # Log error but don't fail the calling operation
        print(f"Error cleaning up expired contexts: {e}")
        return 0


@app.route('/context/store', methods=['POST'])
def store_context():
    """
    Store file or directory context with embeddings.

    Request body:
    {
        "session_id": "optional-session-id",
        "context_type": "file" or "directory",
        "path": "file/directory path",
        "content": "text content",
        "metadata": {"key": "value"}
    }
    """
    # Cleanup expired contexts before storing new ones
    cleanup_expired_temp_contexts()
    try:
        data = request.get_json()

        context_type = data.get('context_type')  # 'file' or 'directory'
        path = data.get('path')
        content = data.get('content')
        session_id = data.get('session_id')
        metadata = data.get('metadata', {})

        if not all([context_type, path, content]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields: context_type, path, content'
            }), 400

        # Generate embedding for the content
        embedding = get_embedding(content)
        if not embedding:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate embedding'
            }), 500

        # Create context entry
        context_entry = {
            'context_type': context_type,
            'path': path,
            'content': content,
            'embedding': embedding,
            'metadata': metadata,
            'created_at': datetime.utcnow().isoformat()
        }

        # Store in Redis
        # If session_id is provided, store under session key
        # Otherwise, store under temporary key
        if session_id:
            key = f"session:{session_id}:context:{path}"
            # Add to session set for easy retrieval
            redis_client.sadd(f"session:{session_id}:contexts", path)
        else:
            key = f"temp:context:{path}"
            # Add to temporary sorted set with expiration timestamp
            # This allows automatic cleanup of expired entries
            expiration_time = datetime.utcnow().timestamp() + 3600  # 1 hour from now
            redis_client.zadd("temp:contexts", {path: expiration_time})

        # Store in Redis with specific error handling
        try:
            redis_client.set(key, json.dumps(context_entry))

            # Set TTL for temporary contexts (1 hour)
            if not session_id:
                redis_client.expire(key, 3600)
        except redis.exceptions.ConnectionError as e:
            return jsonify({
                'status': 'error',
                'message': f'Redis connection failed: {str(e)}'
            }), 503

        return jsonify({
            'status': 'success',
            'message': 'Context stored successfully',
            'key': key
        }), 201

    except redis.exceptions.ConnectionError as e:
        return jsonify({
            'status': 'error',
            'message': f'Redis connection failed: {str(e)}'
        }), 503
    except Exception as e:
        return handle_error(e)


@app.route('/context/get', methods=['GET'])
def get_context():
    """
    Get stored context by path.

    Query params:
    - path: file/directory path
    - session_id: optional session ID
    """
    try:
        path = request.args.get('path')
        session_id = request.args.get('session_id')

        if not path:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: path'
            }), 400

        # Try to get from session first, then temp
        key = f"session:{session_id}:context:{path}" if session_id else f"temp:context:{path}"

        context_data = redis_client.get(key)
        if not context_data:
            return jsonify({
                'status': 'error',
                'message': 'Context not found'
            }), 404

        context = json.loads(context_data)

        return jsonify({
            'status': 'success',
            'context': context
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/context/search', methods=['POST'])
def search_context():
    """
    Search for similar contexts using embeddings.

    Request body:
    {
        "query": "search query text",
        "session_id": "optional-session-id",
        "top_k": 5,
        "threshold": 0.7
    }
    """
    try:
        data = request.get_json()

        query = data.get('query')
        session_id = data.get('session_id')
        top_k = data.get('top_k', 5)
        threshold = data.get('threshold', 0.7)

        if not query:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: query'
            }), 400

        # Generate embedding for query
        query_embedding = get_embedding(query)
        if not query_embedding:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate query embedding'
            }), 500

        # Get all contexts (session-specific or temp)
        if session_id:
            paths = redis_client.smembers(f"session:{session_id}:contexts")
            keys = [f"session:{session_id}:context:{path}" for path in paths]
        else:
            # temp:contexts is a sorted set, not a regular set
            paths = redis_client.zrange("temp:contexts", 0, -1)
            keys = [f"temp:context:{path}" for path in paths]

        matches = []

        for key in keys:
            context_data = redis_client.get(key)
            if context_data:
                context = json.loads(context_data)
                embedding = context.get('embedding')

                if embedding:
                    similarity = cosine_similarity(query_embedding, embedding)
                    if similarity >= threshold:
                        matches.append({
                            'path': context.get('path'),
                            'context_type': context.get('context_type'),
                            'content': context.get('content'),
                            'metadata': context.get('metadata'),
                            'similarity': similarity
                        })

        # Sort by similarity (highest first) and limit to top_k
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        matches = matches[:top_k]

        return jsonify({
            'status': 'success',
            'count': len(matches),
            'matches': matches
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/context/list', methods=['GET'])
def list_contexts():
    """
    List all contexts for a session or temp contexts.

    Query params:
    - session_id: optional session ID
    """
    try:
        session_id = request.args.get('session_id')

        if session_id:
            paths = redis_client.smembers(f"session:{session_id}:contexts")
            keys = [f"session:{session_id}:context:{path}" for path in paths]
        else:
            # temp:contexts is a sorted set, not a regular set
            paths = redis_client.zrange("temp:contexts", 0, -1)
            keys = [f"temp:context:{path}" for path in paths]

        contexts = []
        for key in keys:
            context_data = redis_client.get(key)
            if context_data:
                context = json.loads(context_data)
                # Don't include full content and embedding in list
                contexts.append({
                    'path': context.get('path'),
                    'context_type': context.get('context_type'),
                    'created_at': context.get('created_at'),
                    'metadata': context.get('metadata')
                })

        return jsonify({
            'status': 'success',
            'count': len(contexts),
            'contexts': contexts
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/context/delete', methods=['DELETE'])
def delete_context():
    """
    Delete a specific context.

    Query params:
    - path: file/directory path
    - session_id: optional session ID
    """
    try:
        path = request.args.get('path')
        session_id = request.args.get('session_id')

        if not path:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: path'
            }), 400

        if session_id:
            key = f"session:{session_id}:context:{path}"
            redis_client.srem(f"session:{session_id}:contexts", path)
        else:
            key = f"temp:context:{path}"
            # temp:contexts is a sorted set, use zrem instead of srem
            redis_client.zrem("temp:contexts", path)

        deleted = redis_client.delete(key)

        if deleted:
            return jsonify({
                'status': 'success',
                'message': 'Context deleted successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Context not found'
            }), 404

    except Exception as e:
        return handle_error(e)


@app.route('/session/clear', methods=['DELETE'])
def clear_session():
    """
    Clear all contexts for a session.

    Query params:
    - session_id: session ID to clear
    """
    try:
        session_id = request.args.get('session_id')

        if not session_id:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: session_id'
            }), 400

        # Get all context paths for this session
        paths = redis_client.smembers(f"session:{session_id}:contexts")

        # Delete all contexts
        deleted_count = 0
        for path in paths:
            key = f"session:{session_id}:context:{path}"
            if redis_client.delete(key):
                deleted_count += 1

        # Delete the contexts set
        redis_client.delete(f"session:{session_id}:contexts")

        return jsonify({
            'status': 'success',
            'message': f'Cleared {deleted_count} contexts from session',
            'deleted_count': deleted_count
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/temp/clear', methods=['DELETE'])
def clear_temp():
    """Clear all temporary contexts."""
    try:
        # Get all temp context paths (temp:contexts is a sorted set)
        paths = redis_client.zrange("temp:contexts", 0, -1)

        # Delete all temp contexts
        deleted_count = 0
        for path in paths:
            key = f"temp:context:{path}"
            if redis_client.delete(key):
                deleted_count += 1

        # Delete the temp contexts sorted set
        redis_client.delete("temp:contexts")

        return jsonify({
            'status': 'success',
            'message': f'Cleared {deleted_count} temporary contexts',
            'deleted_count': deleted_count
        }), 200

    except Exception as e:
        return handle_error(e)


# Global error handler for uncaught exceptions
@app.errorhandler(Exception)
def handle_uncaught_exception(e):
    """Handle any uncaught exceptions and send to Sentry."""
    return handle_error(e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
