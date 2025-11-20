"""Flask API for PostgreSQL interaction."""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import Integer, Text, DateTime, CheckConstraint, Float
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, jsonify, request
from sentry_config import configure_sentry, capture_exception
import sys
import os
import json
import requests

# Add shared source directory to path
sys.path.insert(0, '/app/src_shared')


# Configure Sentry
configure_sentry(service_name="postgres-flask")

app = Flask(__name__)

# Database configuration
db_user = os.getenv('POSTGRES_USER', 'postgres')
db_password = os.getenv('POSTGRES_PASSWORD', 'postgres')
db_name = os.getenv('POSTGRES_DB', 'vuhitra')
db_host = os.getenv('POSTGRES_HOST', 'postgres')  # PostgreSQL service name
db_port = os.getenv('POSTGRES_PORT', '5432')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Transformer service configuration
TRANSFORMER_API_URL = os.getenv('TRANSFORMER_API_URL', 'http://localhost:16050')


def handle_error(e, status_code=500):
    """Centralized error handler that logs to Sentry."""
    capture_exception(e)
    return jsonify({
        'status': 'error',
        'message': str(e)
    }), status_code


# Define the ConversationRating model
class ConversationRating(db.Model):
    __tablename__ = 'conversation_ratings'

    id = db.Column(Integer, primary_key=True)
    user_rating = db.Column(Integer, CheckConstraint('user_rating >= 0 AND user_rating <= 10'))
    prompt_text = db.Column(Text)
    response_text = db.Column(Text)
    tags = db.Column(JSON, default={})
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Define the MCPTool model
class MCPTool(db.Model):
    __tablename__ = 'mcp_tools'

    id = db.Column(Integer, primary_key=True)
    mcp_name = db.Column(Text, nullable=False)  # e.g., "coder"
    tool_name = db.Column(Text, nullable=False)  # e.g., "run_python_code"
    description = db.Column(Text, nullable=False)
    embedding = db.Column(JSON)  # Store embedding as JSON array
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'postgres-flask'}), 200


@app.route('/db/test', methods=['GET'])
def test_db():
    """Test database connection."""
    try:
        db.session.execute('SELECT 1')
        return jsonify({'status': 'success', 'message': 'Database connection successful'}), 200
    except Exception as e:
        return handle_error(e)


@app.route('/ratings/create', methods=['GET'])
def create_rating():
    """Create a new conversation rating."""
    try:
        data = request.args.to_dict()

        # Parse tags if provided as JSON string
        tags = {}
        if 'tags' in data:
            try:
                tags = json.loads(data['tags'])
            except json.JSONDecodeError:
                tags = {}

        rating = ConversationRating(
            user_rating=int(data.get('user_rating', 0)),
            prompt_text=data.get('prompt_text'),
            response_text=data.get('response_text'),
            tags=tags
        )

        db.session.add(rating)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'id': rating.id,
            'message': 'Rating created successfully'
        }), 201
    except Exception as e:
        db.session.rollback()
        return handle_error(e)


@app.route('/ratings', methods=['GET'])
def get_ratings():
    """Get all conversation ratings."""
    try:
        min_rating = request.args.get('min_rating', type=int)

        query = ConversationRating.query
        if min_rating is not None:
            query = query.filter(ConversationRating.user_rating >= min_rating)

        ratings = query.order_by(ConversationRating.created_at.desc()).all()

        return jsonify({
            'status': 'success',
            'count': len(ratings),
            'ratings': [{
                'id': r.id,
                'user_rating': r.user_rating,
                'prompt_text': r.prompt_text,
                'response_text': r.response_text,
                'tags': r.tags,
                'created_at': r.created_at.isoformat()
            } for r in ratings]
        }), 200
    except Exception as e:
        return handle_error(e)


@app.route('/ratings/<int:rating_id>', methods=['GET'])
def get_rating(rating_id):
    """Get a specific conversation rating."""
    try:
        rating = ConversationRating.query.get_or_404(rating_id)

        return jsonify({
            'status': 'success',
            'rating': {
                'id': rating.id,
                'user_rating': rating.user_rating,
                'prompt_text': rating.prompt_text,
                'response_text': rating.response_text,
                'tags': rating.tags,
                'created_at': rating.created_at.isoformat(),
                'updated_at': rating.updated_at.isoformat()
            }
        }), 200
    except Exception as e:
        return handle_error(e, status_code=404)


@app.route('/ratings/<int:rating_id>/tags', methods=['GET'])
def update_rating_tags(rating_id):
    """Update tags for a specific conversation rating."""
    try:
        rating = ConversationRating.query.get_or_404(rating_id)

        tags_param = request.args.get('tags')
        if not tags_param:
            return jsonify({
                'status': 'error',
                'message': 'Missing tags query parameter'
            }), 400

        try:
            tags = json.loads(tags_param)
        except json.JSONDecodeError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format for tags'
            }), 400

        rating.tags = tags
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Tags updated successfully',
            'rating': {
                'id': rating.id,
                'tags': rating.tags,
                'updated_at': rating.updated_at.isoformat()
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return handle_error(e)


@app.route('/ratings/<int:rating_id>/update', methods=['PATCH'])
def update_rating(rating_id):
    """Update a specific conversation rating."""
    try:
        rating = ConversationRating.query.get_or_404(rating_id)

        # Get JSON data from request body
        data = request.get_json() or {}

        # Update fields if provided with input validation
        if 'user_rating' in data:
            try:
                user_rating = int(data['user_rating'])
                if not 0 <= user_rating <= 10:
                    return jsonify({
                        'status': 'error',
                        'message': 'user_rating must be between 0 and 10'
                    }), 400
                rating.user_rating = user_rating
            except (ValueError, TypeError):
                return jsonify({
                    'status': 'error',
                    'message': 'user_rating must be a valid integer'
                }), 400

        if 'response_text' in data:
            rating.response_text = data['response_text']

        if 'prompt_text' in data:
            rating.prompt_text = data['prompt_text']

        if 'tags' in data:
            if not isinstance(data['tags'], dict):
                return jsonify({
                    'status': 'error',
                    'message': 'tags must be a valid JSON object'
                }), 400
            rating.tags = data['tags']

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Rating updated successfully',
            'rating': {
                'id': rating.id,
                'user_rating': rating.user_rating,
                'prompt_text': rating.prompt_text,
                'response_text': rating.response_text,
                'tags': rating.tags,
                'updated_at': rating.updated_at.isoformat()
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return handle_error(e)


@app.route('/ratings/purge', methods=['GET'])
def purge_ratings():
    """Delete all conversation ratings."""
    try:
        count = ConversationRating.query.count()
        ConversationRating.query.delete()
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': f'Purged {count} ratings'
        }), 200
    except Exception as e:
        db.session.rollback()
        return handle_error(e)


# MCP Tools endpoints

def get_embedding(text):
    """Get embedding from transformer service."""
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


@app.route('/mcp-tools/store', methods=['POST'])
def store_mcp_tool():
    """Store or update an MCP tool with its embedding."""
    try:
        data = request.get_json()

        mcp_name = data.get('mcp_name')
        tool_name = data.get('tool_name')
        description = data.get('description')

        if not all([mcp_name, tool_name, description]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields: mcp_name, tool_name, description'
            }), 400

        # Get embedding for the description
        embedding = get_embedding(description)
        if not embedding:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate embedding'
            }), 500

        # Check if tool already exists
        existing_tool = MCPTool.query.filter_by(
            mcp_name=mcp_name,
            tool_name=tool_name
        ).first()

        if existing_tool:
            # Update existing tool
            existing_tool.description = description
            existing_tool.embedding = embedding
            existing_tool.updated_at = datetime.utcnow()
            message = 'MCP tool updated successfully'
        else:
            # Create new tool
            new_tool = MCPTool(
                mcp_name=mcp_name,
                tool_name=tool_name,
                description=description,
                embedding=embedding
            )
            db.session.add(new_tool)
            message = 'MCP tool stored successfully'

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': message
        }), 200
    except Exception as e:
        db.session.rollback()
        return handle_error(e)


@app.route('/mcp-tools', methods=['GET'])
def get_mcp_tools():
    """Get all MCP tools with descriptions."""
    try:
        tools = MCPTool.query.all()

        return jsonify({
            'status': 'success',
            'count': len(tools),
            'tools': [{
                'id': t.id,
                'mcp_name': t.mcp_name,
                'tool_name': t.tool_name,
                'description': t.description,
                'created_at': t.created_at.isoformat()
            } for t in tools]
        }), 200
    except Exception as e:
        return handle_error(e)


@app.route('/mcp-tools/match', methods=['POST'])
def match_mcp_tool():
    """Match a prompt/code against MCP tools using embeddings."""
    try:
        data = request.get_json()
        text = data.get('text')
        threshold = data.get('threshold', 0.5)  # Default similarity threshold

        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: text'
            }), 400

        # Get embedding for the input text
        text_embedding = get_embedding(text)
        if not text_embedding:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate embedding for input text'
            }), 500

        # Get all tools and calculate similarity
        tools = MCPTool.query.all()
        matches = []

        for tool in tools:
            if tool.embedding:
                similarity = cosine_similarity(text_embedding, tool.embedding)
                if similarity >= threshold:
                    matches.append({
                        'mcp_name': tool.mcp_name,
                        'tool_name': tool.tool_name,
                        'description': tool.description,
                        'similarity': similarity
                    })

        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x['similarity'], reverse=True)

        return jsonify({
            'status': 'success',
            'count': len(matches),
            'matches': matches,
            'best_match': matches[0] if matches else None
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
