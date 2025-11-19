"""Flask API for PostgreSQL interaction."""

import sys
import os
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, Text, DateTime, CheckConstraint
from datetime import datetime

# Add shared source directory to path
sys.path.insert(0, '/app/src_shared')
from sentry_config import configure_sentry

# Configure Sentry
configure_sentry(service_name="postgres-flask")

app = Flask(__name__)

# Database configuration
db_user = os.getenv('POSTGRES_USER', 'postgres')
db_password = os.getenv('POSTGRES_PASSWORD', 'postgres')
db_name = os.getenv('POSTGRES_DB', 'vuhitra')
db_host = 'localhost'  # PostgreSQL runs on same container

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Define the ConversationRating model
class ConversationRating(db.Model):
    __tablename__ = 'conversation_ratings'
    
    id = db.Column(Integer, primary_key=True)
    prompt_embedding = db.Column(Vector(768))
    response_embedding = db.Column(Vector(768))
    user_rating = db.Column(Integer, CheckConstraint('user_rating >= 0 AND user_rating <= 10'))
    prompt_text = db.Column(Text)
    response_text = db.Column(Text)
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
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/ratings', methods=['POST'])
def create_rating():
    """Create a new conversation rating."""
    try:
        data = request.get_json()
        
        rating = ConversationRating(
            prompt_embedding=data.get('prompt_embedding'),
            response_embedding=data.get('response_embedding'),
            user_rating=data.get('user_rating'),
            prompt_text=data.get('prompt_text'),
            response_text=data.get('response_text')
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
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
                'created_at': r.created_at.isoformat()
            } for r in ratings]
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
                'created_at': rating.created_at.isoformat(),
                'updated_at': rating.updated_at.isoformat()
            }
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

