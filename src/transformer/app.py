"""
Transformer NLP Service

A minimal Flask-based microservice ready for future NLP capabilities.
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure Sentry for error tracking
sentry_dsn = os.getenv('SENTRY_DSN', '')
environment = os.getenv('ENVIRONMENT', 'DEV')

if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FlaskIntegration()],
        environment=environment.lower(),
        traces_sample_rate=1.0 if environment == 'DEV' else 0.1,
        send_default_pii=False,
        attach_stacktrace=True,
    )


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


# Global error handler for uncaught exceptions
@app.errorhandler(Exception)
def handle_uncaught_exception(e):
    """Handle any uncaught exceptions."""
    if sentry_dsn:
        sentry_sdk.capture_exception(e)
    
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.getenv('PORT', 5050))

    print(f"Starting Transformer NLP Service on port {port}...")
    print("Available endpoints:")
    print("  GET  / - Service information")
    print("  GET  /health - Health check")
    print()

    # Run the app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
