"""Flask API for PostgreSQL interaction."""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import Integer, Text, DateTime, CheckConstraint
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, jsonify, request
from sentry_config import configure_sentry, capture_exception
import sys
import os
import json

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


@app.route('/ratings/<int:rating_id>/update', methods=['GET'])
def update_rating(rating_id):
    """Update a specific conversation rating."""
    try:
        rating = ConversationRating.query.get_or_404(rating_id)

        # Update fields if provided
        if 'user_rating' in request.args:
            rating.user_rating = int(request.args.get('user_rating'))

        if 'response_text' in request.args:
            rating.response_text = request.args.get('response_text')

        if 'prompt_text' in request.args:
            rating.prompt_text = request.args.get('prompt_text')

        if 'tags' in request.args:
            try:
                rating.tags = json.loads(request.args.get('tags'))
            except json.JSONDecodeError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid JSON format for tags'
                }), 400

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


# Global error handler for uncaught exceptions
@app.errorhandler(Exception)
def handle_uncaught_exception(e):
    """Handle any uncaught exceptions and send to Sentry."""
    return handle_error(e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
