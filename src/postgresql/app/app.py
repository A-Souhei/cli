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
import re
import requests
import yaml

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

# Load config.yaml for Ollama configuration
def load_config():
    """Load configuration from config.yaml."""
    config_paths = ['/app/config.yaml', 'config.yaml', '../config.yaml']
    for config_path in config_paths:
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"Warning: Could not load config.yaml: {e}")
            continue
    print("Warning: Configuration file not found: /app/config.yaml")
    return {}

# Load configuration
CONFIG = load_config()

# Ollama service configuration - read from config.yaml, fallback to env var
OLLAMA_API_URL = CONFIG.get('ollama', {}).get('url', os.getenv('OLLAMA_API_URL', 'http://localhost:11434'))
DEFAULT_OLLAMA_MODEL = CONFIG.get('ollama', {}).get('model', 'tinyllama')
OLLAMA_TIMEOUT = CONFIG.get('ollama', {}).get('timeout', 120)
print(f"Using Ollama - URL: {OLLAMA_API_URL}, Model: {DEFAULT_OLLAMA_MODEL}, Timeout: {OLLAMA_TIMEOUT}")


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
    session_id = db.Column(Text, nullable=True, index=True)  # Session ID for context grouping
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
            tags=tags,
            session_id=data.get('session_id')
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


def get_batch_embeddings(texts):
    """Get embeddings for multiple texts from transformer service."""
    try:
        response = requests.get(
            f"{TRANSFORMER_API_URL}/embed/batch",
            params={"texts": json.dumps(texts)},
            timeout=60
        )
        if response.status_code == 200:
            return response.json().get('embeddings')
        return None
    except Exception as e:
        print(f"Error getting batch embeddings: {e}")
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


def extract_parameters_from_text(text, tool_name):
    """
    Extract parameters from text based on common patterns.

    This is a simple heuristic-based extraction. For production use,
    consider using an LLM or more sophisticated NLP techniques.

    Parameters:
    -----------
    text : str
        The input text/sentence to extract parameters from
    tool_name : str
        The name of the tool to extract parameters for

    Returns:
    --------
    dict
        Extracted parameters as key-value pairs
    """
    params = {}
    text_lower = text.lower()

    # Common patterns for different tool types

    # 1. Code execution tools (run_python_code, run_r_code)
    if 'run' in tool_name or 'execute' in tool_name or 'eval' in tool_name:
        # Look for code blocks in backticks or quotes
        code_patterns = [
            r'```(?:python|r)?\s*(.*?)```',  # Code blocks
            r'`([^`]+)`',  # Inline code
            r'"([^"]+)"',  # Double quotes
            r"'([^']+)'",  # Single quotes
        ]

        for pattern in code_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                params['code'] = match.group(1).strip()
                break

        # If no code block found, use the entire text after command words
        if 'code' not in params:
            # Remove common command words
            code_text = re.sub(r'\b(run|execute|eval|this|the|following|code|python|r)\b', '', text_lower, flags=re.IGNORECASE)
            params['code'] = code_text.strip()

    # 2. File operations (write_python_code, write_r_code, edit_*_code)
    elif 'write' in tool_name or 'edit' in tool_name or 'create' in tool_name:
        # Look for file paths
        file_patterns = [
            r'(?:file|path|to|at|in)\s+([^\s,;]+\.(?:py|r|txt|json|csv|md))',
            r'([^\s,;]+\.(?:py|r|txt|json|csv|md))',
        ]

        for pattern in file_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params['file_path'] = match.group(1)
                break

        # Look for code content
        code_patterns = [
            r'```(?:python|r)?\s*(.*?)```',
            r'code[:\s]+(.+)',
        ]

        for pattern in code_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                params['code'] = match.group(1).strip()
                break

    # 3. Context operations (add_file_context, add_directory_context)
    elif 'context' in tool_name or 'add' in tool_name:
        # Look for file or directory paths - first try @ prefixed paths
        at_path_match = re.search(r'@([\w\-./]+(?:\.py|\.r|\.R)?)', text)
        if at_path_match:
            path = at_path_match.group(1)  # group(1) excludes the @
            if 'directory' in tool_name or 'folder' in text_lower:
                params['directory_path'] = path
            else:
                params['file_path'] = path
        else:
            # Fallback to other path patterns
            path_patterns = [
                r'([^\s,;@]+(?:/[^\s,;@]+)+)',  # Unix-style paths (exclude @)
                r'([A-Za-z]:\\[^\s,;]+)',  # Windows-style paths
                r'(?:file|directory|folder|path)\s+([^\s,;@]+)',  # Keyword-prefixed paths
            ]

            for pattern in path_patterns:
                match = re.search(pattern, text)
                if match:
                    path = match.group(1)
                    # Skip if path is just "context" or other keywords
                    if path.lower() not in ['context', 'file', 'directory', 'folder', 'path', 'for', 'to', 'at']:
                        if 'directory' in tool_name or 'folder' in text_lower:
                            params['directory_path'] = path
                        else:
                            params['file_path'] = path
                        break

    # 4. Generic text content extraction
    if not params:
        # If no specific parameters found, include the text as a generic 'input' parameter
        params['input'] = text

    return params


def call_ollama(prompt, model="tinyllama", temperature=0.3, max_tokens=1000):
    """
    Call Ollama API to generate text.

    Parameters:
    -----------
    prompt : str
        The prompt to send to Ollama
    model : str
        The model name to use (default: tinyllama)
    temperature : float
        Temperature for generation (default: 0.3)
    max_tokens : int
        Maximum tokens to generate (default: 1000)

    Returns:
    --------
    str or None
        Generated text if successful, None otherwise
    """
    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            },
            timeout=OLLAMA_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            return data.get('response', '').strip()
        else:
            print(f"Error calling Ollama: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.Timeout:
        print("Ollama request timed out")
        return None
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to Ollama at {OLLAMA_API_URL}")
        return None
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None


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


@app.route('/mcp-tools/retrieve', methods=['POST'])
def retrieve_tools_recursive():
    """
    Recursively retrieve the best matching tool for each prompt/sentence.

    This endpoint takes a list of prompts, embeds each one, finds the best
    matching tool, and extracts parameters from the prompt.

    JSON Body Parameters:
    - prompts: Array of text prompts/sentences (required)
      Example: ["Run Python code", "Create file"]
    - threshold: Minimum similarity threshold 0-1 (optional, default: 0.5)
    - mcp_filter: Array of MCP names to filter (optional)
      Example: ["coder"]
    - extract_params: Whether to extract parameters (optional, default: true)

    Example:
    POST /mcp-tools/retrieve
    {
        "prompts": ["Run Python code", "Create file"],
        "threshold": 0.5
    }

    Returns:
    {
        "status": "success",
        "count": 2,
        "results": [
            {
                "prompt": "Run Python code",
                "prompt_index": 0,
                "best_match": {
                    "mcp_name": "coder",
                    "tool_name": "run_python_code",
                    "description": "Execute Python code...",
                    "similarity": 0.87,
                    "extracted_params": {
                        "code": ""
                    }
                }
            },
            ...
        ]
    }
    """
    try:
        # Get JSON body
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body must be valid JSON'
            }), 400

        # Get required prompts parameter
        prompts = data.get('prompts')
        if not prompts:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: prompts (must be an array)'
            }), 400

        if not isinstance(prompts, list):
            return jsonify({
                'status': 'error',
                'message': 'prompts must be a list of strings'
            }), 400

        if len(prompts) == 0:
            return jsonify({
                'status': 'error',
                'message': 'prompts parameter must be a non-empty list'
            }), 400

        # Parse optional parameters
        try:
            threshold = float(data.get('threshold', 0.5))
        except (ValueError, TypeError):
            threshold = 0.5

        extract_params = data.get('extract_params', True)
        if isinstance(extract_params, str):
            extract_params = extract_params.lower() in ['true', '1', 'yes']

        # Get mcp_filter if provided
        mcp_filter = data.get('mcp_filter')
        if mcp_filter and not isinstance(mcp_filter, list):
            return jsonify({
                'status': 'error',
                'message': 'mcp_filter must be a list of MCP names'
            }), 400

        # Get context_references (@ file/folder paths from original prompt)
        context_references = data.get('context_references', [])
        if not isinstance(context_references, list):
            context_references = []

        # Get batch embeddings for all prompts
        prompt_embeddings = get_batch_embeddings(prompts)
        if not prompt_embeddings:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate embeddings for prompts'
            }), 500

        if len(prompt_embeddings) != len(prompts):
            return jsonify({
                'status': 'error',
                'message': f'Embedding count mismatch: got {len(prompt_embeddings)}, expected {len(prompts)}'
            }), 500

        # Get all tools from database
        if mcp_filter:
            tools = MCPTool.query.filter(MCPTool.mcp_name.in_(mcp_filter)).all()
        else:
            tools = MCPTool.query.all()

        if not tools:
            return jsonify({
                'status': 'error',
                'message': 'No tools found in database'
            }), 404

        # Process each prompt recursively
        results = []
        for idx, (prompt, prompt_embedding) in enumerate(zip(prompts, prompt_embeddings)):
            # Calculate similarity for all tools
            matches = []
            for tool in tools:
                if tool.embedding:
                    similarity = cosine_similarity(prompt_embedding, tool.embedding)

                    # Boost similarity if tool name is explicitly mentioned in the prompt
                    # This helps when steps say "using run_python_code" or similar
                    prompt_lower = prompt.lower()
                    tool_name_lower = tool.tool_name.lower()
                    if tool_name_lower in prompt_lower:
                        # Apply significant boost for exact tool name mentions
                        similarity = min(similarity + 0.3, 1.0)

                    if similarity >= threshold:
                        match = {
                            'mcp_name': tool.mcp_name,
                            'tool_name': tool.tool_name,
                            'description': tool.description,
                            'similarity': similarity
                        }

                        # Extract parameters if requested
                        if extract_params:
                            extracted = extract_parameters_from_text(
                                prompt,
                                tool.tool_name
                            )

                            # Inject context_references if tool needs file_path or dir_path
                            # and they're not already in the step text
                            if context_references:
                                # Check if tool needs file_path and doesn't have it
                                if 'file_path' not in extracted or not extracted.get('file_path'):
                                    # Tools that need file_path
                                    file_path_tools = ['write_python_code', 'edit_python_code', 'write_r_code',
                                                      'edit_r_code', 'run_python_code', 'run_r_code',
                                                      'verify_file_modifications', 'add_file_context']
                                    if tool.tool_name in file_path_tools:
                                        # Find first file reference (ends with .py, .r, .R)
                                        for ref in context_references:
                                            if ref.endswith(('.py', '.r', '.R')):
                                                extracted['file_path'] = ref
                                                break

                                # Check if tool needs dir_path and doesn't have it
                                if 'dir_path' not in extracted or not extracted.get('dir_path'):
                                    if tool.tool_name == 'add_directory_context':
                                        # Find first directory reference (doesn't end with file extension)
                                        for ref in context_references:
                                            if not ref.endswith(('.py', '.r', '.R')):
                                                extracted['dir_path'] = ref
                                                break

                            match['extracted_params'] = extracted

                        matches.append(match)

            # Sort by similarity (highest first) and get only the best match
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            best_match = matches[0] if matches else None

            # Add to results - only include the best match
            results.append({
                'prompt': prompt,
                'prompt_index': idx,
                'best_match': best_match
            })

        return jsonify({
            'status': 'success',
            'count': len(results),
            'results': results,
            'metadata': {
                'threshold': threshold,
                'mcp_filter': mcp_filter,
                'total_prompts': len(prompts),
                'total_tools_searched': len(tools)
            }
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/mcp-tools/text-to-sequence', methods=['POST'])
def text_to_sequence():
    """
    Convert a long text into a sequence of individual instruction steps.

    This endpoint uses LLM to:
    1. Split text into paragraphs/sections
    2. Analyze each section to determine if it contains multiple instructions
    3. Further subdivide sections that contain multiple instructions
    4. Return a flat list of single-instruction steps compatible with retrieve_all_tools

    Request Body:
    {
        "text": "Long text containing multiple instructions...",
        "model": "tinyllama",  // optional, default: "tinyllama"
        "max_iterations": 3     // optional, default: 3
    }

    Response:
    {
        "status": "success",
        "sequence": [
            "First instruction step",
            "Second instruction step",
            ...
        ],
        "metadata": {
            "original_length": 1500,
            "total_steps": 5,
            "model_used": "tinyllama"
        }
    }
    """
    try:
        # Get JSON body
        data = request.get_json()
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Request body must be valid JSON'
            }), 400

        # Get required text parameter
        if 'text' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: text'
            }), 400

        text = data.get('text')
        if not isinstance(text, str):
            return jsonify({
                'status': 'error',
                'message': 'text must be a string'
            }), 400

        if len(text.strip()) == 0:
            return jsonify({
                'status': 'error',
                'message': 'text parameter must be non-empty'
            }), 400

        # Validate maximum length to prevent performance issues and timeouts
        MAX_TEXT_LENGTH = 50000
        if len(text) > MAX_TEXT_LENGTH:
            return jsonify({
                'status': 'error',
                'message': f'text parameter exceeds maximum length of {MAX_TEXT_LENGTH} characters'
            }), 400

        # Get optional parameters
        model = data.get('model', DEFAULT_OLLAMA_MODEL)

        # Validate model parameter
        # Expected model names: tinyllama, llama2, llama3.1:8b, mistral, codellama, etc.
        # Model name should be a non-empty string without special characters except : and .
        if not isinstance(model, str) or not model.strip():
            return jsonify({
                'status': 'error',
                'message': 'model must be a non-empty string'
            }), 400

        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._:-]*$', model):
            return jsonify({
                'status': 'error',
                'message': 'model name contains invalid characters. Use alphanumeric characters, dots, colons, hyphens, and underscores only.'
            }), 400

        max_iterations = data.get('max_iterations', 3)

        # Validate max_iterations
        if not isinstance(max_iterations, int) or max_iterations < 1:
            max_iterations = 3
        if max_iterations > 5:
            max_iterations = 5

        original_length = len(text)

        # Step 1: Split text into initial paragraphs/sections
        split_prompt = f"""You are a text analysis assistant. Your task is to split the following text into distinct instruction steps or action items. Each step should represent a single, clear instruction or task.

IMPORTANT: Preserve ALL file paths that use @ prefix (e.g., @file.py, @path/to/file.py) EXACTLY as they appear. Do not rephrase or remove these references.

Text to split:
{text}

Please respond with ONLY a JSON array of strings, where each string is a single instruction step. Do not include any explanation or additional text. Format your response exactly like this:
["step 1 text here", "step 2 text here", "step 3 text here"]

If the text is already a single instruction, return it as a single-item array."""

        llm_response = call_ollama(split_prompt, model=model, temperature=0.3, max_tokens=2000)

        if not llm_response:
            return jsonify({
                'status': 'error',
                'message': 'Failed to get response from LLM service. Make sure Ollama is running.'
            }), 503

        # Parse the LLM response to extract JSON array
        try:
            # Try to extract JSON array from response
            json_match = re.search(r'\[.*?\]', llm_response, re.DOTALL)
            if json_match:
                initial_steps = json.loads(json_match.group(0))
            else:
                # If no JSON found, treat the response as a single step
                initial_steps = [llm_response]
        except json.JSONDecodeError:
            # If JSON parsing fails, split by newlines as fallback
            initial_steps = [s.strip() for s in llm_response.split('\n') if s.strip()]

        # Step 2: Iteratively check and subdivide steps that contain multiple instructions
        final_steps = []
        iteration = 0

        for iteration in range(max_iterations):
            steps_to_process = initial_steps if iteration == 0 else final_steps
            final_steps = []

            for step in steps_to_process:
                if not step or len(step.strip()) == 0:
                    continue

                # Ask LLM if this step contains multiple instructions
                check_prompt = f"""You are analyzing an instruction step. Determine if the following text contains multiple distinct instructions or tool usages that should be separated.

IMPORTANT: Preserve ALL file paths that use @ prefix (e.g., @file.py, @path/to/file.py) EXACTLY as they appear. Do not rephrase or remove these references.

Text to analyze:
{step}

Respond with ONLY a JSON object in this exact format:
{{"multiple_instructions": true/false, "steps": ["step1", "step2", ...]}}

- If it contains only ONE instruction, set multiple_instructions to false and return the original text as a single-item array
- If it contains MULTIPLE instructions, set multiple_instructions to true and split it into separate single-instruction steps

Do not include any explanation or additional text."""

                check_response = call_ollama(check_prompt, model=model, temperature=0.2, max_tokens=1500)

                if not check_response:
                    # If LLM fails, keep the step as-is
                    final_steps.append(step)
                    continue

                # Parse the check response
                try:
                    json_match = re.search(r'\{.*?\}', check_response, re.DOTALL)
                    if json_match:
                        check_data = json.loads(json_match.group(0))
                        if check_data.get('multiple_instructions', False):
                            # Add subdivided steps
                            subdivided = check_data.get('steps', [step])
                            final_steps.extend(subdivided)
                        else:
                            # Single instruction, keep as-is
                            substeps = check_data.get('steps', [step])
                            final_steps.extend(substeps)
                    else:
                        # Fallback: keep the step
                        final_steps.append(step)
                except (json.JSONDecodeError, KeyError):
                    # If parsing fails, keep the step as-is
                    final_steps.append(step)

            # If no new subdivisions were made, we're done
            if len(final_steps) == len(steps_to_process):
                break

        # Clean up and deduplicate steps
        cleaned_steps = []
        seen = set()
        for step in final_steps:
            step_clean = step.strip()
            if step_clean and step_clean.lower() not in seen:
                cleaned_steps.append(step_clean)
                seen.add(step_clean.lower())

        return jsonify({
            'status': 'success',
            'sequence': cleaned_steps,
            'metadata': {
                'original_length': original_length,
                'total_steps': len(cleaned_steps),
                'model_used': model,
                'iterations_performed': min(iteration + 1, max_iterations)
            }
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/mcp-tools/code-command-simple', methods=['POST'])
def code_command_simple():
    """
    Simplified /code command endpoint.

    Uses LLM with all MCP tools in context to split user prompt into clear steps,
    where each step is designed to use ONE tool.

    Request Body:
    {
        "text": "User's prompt with multiple instructions...",
        "session_id": "session-123",  // required
        "model": "tinyllama"  // optional, default from config
    }

    Response:
    {
        "status": "success",
        "steps": [
            "Clear prompt for step 1 (designed for one tool)",
            "Clear prompt for step 2 (designed for one tool)",
            ...
        ],
        "session_id": "session-123",
        "metadata": {
            "total_steps": 3,
            "model_used": "tinyllama",
            "tools_available": 15
        }
    }
    """
    try:
        # Get JSON body
        data = request.get_json()
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Request body must be valid JSON'
            }), 400

        # Get required parameters
        text = data.get('text')
        if not text or not isinstance(text, str) or not text.strip():
            return jsonify({
                'status': 'error',
                'message': 'Missing or invalid required parameter: text'
            }), 400

        session_id = data.get('session_id')
        if not session_id:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: session_id'
            }), 400

        # Get optional parameters
        model = data.get('model', DEFAULT_OLLAMA_MODEL)

        # Step 1: Get all MCP tools from database
        tools = MCPTool.query.all()

        if not tools:
            return jsonify({
                'status': 'error',
                'message': 'No MCP tools found in database. Please initialize tools first.'
            }), 404

        # Step 2: Format tools as RAG context for LLM
        # Build list of coding-focused tools only (exclude meta-tools)
        coding_tools = ['run_python_code', 'run_r_code', 'write_python_code', 
                        'write_r_code', 'edit_python_code', 'edit_r_code', 'add_file_context', 
                        'add_directory_context', 'verify_file_modifications']

        # Step 3: Create prompt for LLM to split the user's request
        # Extract any file paths mentioned with @ prefix for context
        mentioned_files = re.findall(r'@([\w\-./]+(?:\.py|\.r|\.R)?)', text)
        file_context = ""
        if mentioned_files:
            file_context = f"\nFiles mentioned by user: {', '.join(mentioned_files)}"
        
        llm_prompt = f"""You are a coding task planner. Break the user's request into executable steps.

USER REQUEST: {text}
{file_context}

AVAILABLE TOOLS (use ONLY these):
1. add_file_context - Load a file into context to read its contents (use FIRST to understand existing code)
2. edit_python_code - Modify an EXISTING Python file (requires the file to exist)
3. write_python_code - Create a NEW Python file (only for new files)
4. run_python_code - Execute Python code directly (for testing/validation)

CRITICAL RULES:
1. Each step must be a plain English sentence describing ONE action
2. ALWAYS start by loading relevant files with add_file_context before editing them
3. Use EXACT file paths from the user's request (paths starting with @)
4. If the user mentions a class/function name, infer the likely file path:
   - UserService → services/user_service.py
   - ProductService → services/product_service.py  
   - helpers → utils/helpers.py
   - Models → models/*.py
5. NEVER use function-call syntax like "tool_name(args)"
6. NEVER reference tools that don't exist (no read_python_code, no read_file)

STEP PATTERN FOR EDITING EXISTING CODE:
1. "Load @path/to/file.py into context using add_file_context" (to read current code)
2. "Load any dependency files into context using add_file_context" (if importing from other files)
3. "Edit @path/to/file.py to [describe changes] using edit_python_code"

EXAMPLES:
User: "Add validation to UserService.create_user using validate_email from utils/helpers.py"
Steps:
["Load services/user_service.py into context using add_file_context",
 "Load utils/helpers.py into context using add_file_context", 
 "Edit services/user_service.py to import validate_email and add email validation to create_user method using edit_python_code"]

User: "Create a new calculator module"
Steps:
["Write a new Python file calculator.py with basic calculator functions using write_python_code"]

Return ONLY a JSON array of step strings. No explanation, just the array:
["step 1", "step 2", "step 3"]"""

        # Step 4: Call LLM
        print(f"[code-command-simple] Calling LLM to split prompt (length: {len(text)})")
        llm_response = call_ollama(llm_prompt, model=model, temperature=0.3, max_tokens=2000)

        if not llm_response:
            return jsonify({
                'status': 'error',
                'message': 'Failed to get response from LLM. Make sure Ollama is running.'
            }), 503

        # Step 5: Parse LLM response to extract steps
        try:
            # Try to extract JSON array from response
            json_match = re.search(r'\[.*?\]', llm_response, re.DOTALL)
            if json_match:
                steps = json.loads(json_match.group(0))
            else:
                # If no JSON found, treat the response as a single step
                steps = [text]  # Fallback to original text
        except json.JSONDecodeError:
            # If JSON parsing fails, split by newlines as fallback
            steps = [s.strip() for s in llm_response.split('\n') if s.strip()]

        # Clean up steps - handle both string and dict formats
        cleaned_steps = []
        for step in steps:
            if isinstance(step, dict):
                # LLM returned dict format like {"prompt": "...", "tool": "..."}
                # Extract just the prompt text
                prompt_text = step.get('prompt', '')
                if prompt_text and prompt_text.strip():
                    cleaned_steps.append(prompt_text.strip())
            elif isinstance(step, str) and step.strip():
                # LLM returned plain string (expected format)
                cleaned_steps.append(step.strip())

        if not cleaned_steps:
            cleaned_steps = [text]  # Fallback to original text

        # Step 6: Validate steps - filter out invalid patterns
        validated_steps = []
        # Non-existent tools that LLM might invent
        non_existent_tools = ['read_python_code', 'read_r_code', 'read_file', 'get_file_contents', 'load_file']
        # Meta-tools that shouldn't be used in step generation
        meta_tools = ['spin_the_roulette', 'retrieve_all_tools', 'roll_the_dice']
        
        for step in cleaned_steps:
            step_lower = step.lower()
            should_skip = False
            
            # Check for non-existent tools
            for invalid_tool in non_existent_tools:
                if invalid_tool in step_lower:
                    print(f"[code-command-simple] Filtering step with non-existent tool '{invalid_tool}': {step[:50]}...")
                    should_skip = True
                    break
            
            # Check for meta-tools (these shouldn't be used in code tasks)
            if not should_skip:
                for meta_tool in meta_tools:
                    if meta_tool in step_lower:
                        print(f"[code-command-simple] Filtering step with meta-tool '{meta_tool}': {step[:50]}...")
                        should_skip = True
                        break
            
            # Check for function-call style format (e.g., "tool_name(args)")
            if not should_skip:
                if re.match(r'^[a-z_]+\s*\(', step_lower):
                    print(f"[code-command-simple] Filtering function-call style step: {step[:50]}...")
                    should_skip = True
            
            if not should_skip:
                validated_steps.append(step)

        # If all steps were filtered, fall back to a sensible default
        if not validated_steps:
            # Check if the original prompt has file references
            file_refs = re.findall(r'@([\w\-./]+\.py)', text)
            if file_refs:
                validated_steps = [f"Load the file {file_refs[0]} into context using add_file_context"]
                if 'edit' in text.lower() or 'add' in text.lower() or 'modify' in text.lower():
                    validated_steps.append(f"Edit the file {file_refs[0]} based on the user's request using edit_python_code")
            else:
                validated_steps = ["Note: No file paths were provided. Please specify the file path with @ prefix (e.g., @path/to/file.py)"]

        print(f"[code-command-simple] Successfully generated {len(validated_steps)} steps (filtered from {len(cleaned_steps)})")

        return jsonify({
            'status': 'success',
            'steps': validated_steps,
            'session_id': session_id,
            'metadata': {
                'total_steps': len(validated_steps),
                'model_used': model,
                'tools_available': len([t for t in tools if t.tool_name not in meta_tools])
            }
        }), 200

    except Exception as e:
        return handle_error(e)


@app.route('/mcp-tools/code-command', methods=['POST'])
def code_command():
    """
    Unified endpoint that chains the three major coder MCP tools:
    1. spin_the_roulette (text-to-sequence + tool matching)
    2. retrieve_all_tools (get best matching tools)
    3. Returns data ready for roll_the_dice execution

    This endpoint orchestrates the complete flow for the /code command.

    Request Body:
    {
        "text": "Long prompt with multiple instructions...",
        "session_id": "session-123",  // required for potential execution
        "model": "tinyllama",  // optional, default: "tinyllama"
        "max_iterations": 3,    // optional, default: 3
        "max_tools": 3         // optional, default: 3, max tools to execute
    }

    Response:
    {
        "status": "success",
        "message": "Successfully processed prompt and matched tools",
        "sequence": ["step 1", "step 2", ...],
        "tools_matched": [
            {
                "step": "instruction text",
                "step_index": 0,
                "best_match": {
                    "mcp_name": "coder",
                    "tool_name": "run_python_code",
                    "description": "...",
                    "similarity": 0.87
                }
            },
            ...
        ],
        "execution_ready": {
            "prompts": ["step 1", "step 2", ...],
            "session_id": "session-123",
            "max_tools": 3
        },
        "metadata": {
            "text_analysis": {...},
            "tool_retrieval": {...},
            "total_steps": 5,
            "total_tools_matched": 3
        }
    }
    """
    try:
        # Get JSON body
        data = request.get_json()
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Request body must be valid JSON'
            }), 400

        # Get required text parameter
        if 'text' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: text'
            }), 400

        text = data.get('text')
        if not isinstance(text, str) or not text.strip():
            return jsonify({
                'status': 'error',
                'message': 'text must be a non-empty string'
            }), 400

        # Get required session_id parameter
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: session_id (required for roll_the_dice execution)'
            }), 400

        # Get optional parameters
        model = data.get('model', DEFAULT_OLLAMA_MODEL)
        max_iterations = data.get('max_iterations', 3)
        max_tools = data.get('max_tools', 3)

        # Validate max_iterations
        if not isinstance(max_iterations, int) or max_iterations < 1:
            max_iterations = 3
        if max_iterations > 5:
            max_iterations = 5

        # Validate max_tools
        if not isinstance(max_tools, int) or max_tools < 1:
            max_tools = 3
        if max_tools > 10:
            max_tools = 10

        # STEP 1: Call text-to-sequence endpoint (spin_the_roulette functionality)
        print(f"[code-command] Step 1: Converting text to sequence (length: {len(text)})")
        # Use localhost URL for internal requests (port 5000 is the internal Flask port)
        base_url = "http://localhost:5000"
        sequence_response = requests.post(
            f"{base_url}/mcp-tools/text-to-sequence",
            json={
                "text": text,
                "model": model,
                "max_iterations": max_iterations
            },
            headers={"Content-Type": "application/json"},
            timeout=180
        )

        if sequence_response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': 'Failed to convert text to sequence',
                'step': 'text-to-sequence',
                'status_code': sequence_response.status_code,
                'response': sequence_response.text
            }), 500

        sequence_data = sequence_response.json()
        if sequence_data.get('status') != 'success':
            return jsonify({
                'status': 'error',
                'message': 'text-to-sequence endpoint returned error',
                'details': sequence_data
            }), 500

        sequence = sequence_data.get('sequence', [])
        print(f"[code-command] Step 1 complete: Got {len(sequence)} steps")

        if not sequence:
            return jsonify({
                'status': 'success',
                'message': 'No instruction steps found in text',
                'sequence': [],
                'tools_matched': [],
                'execution_ready': None,
                'metadata': {
                    'text_analysis': sequence_data.get('metadata', {}),
                    'total_steps': 0,
                    'total_tools_matched': 0
                }
            }), 200

        # STEP 2: Call retrieve endpoint to match tools (retrieve_all_tools functionality)
        print(f"[code-command] Step 2: Retrieving tools for {len(sequence)} prompts")
        retrieve_response = requests.post(
            f"{base_url}/mcp-tools/retrieve",
            json={"prompts": sequence, "threshold": 0.35},
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if retrieve_response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': 'Failed to retrieve tools',
                'step': 'retrieve_all_tools',
                'status_code': retrieve_response.status_code,
                'sequence': sequence,
                'response': retrieve_response.text
            }), 500

        tools_data = retrieve_response.json()
        if tools_data.get('status') != 'success':
            return jsonify({
                'status': 'error',
                'message': 'retrieve endpoint returned error',
                'details': tools_data
            }), 500

        print(f"[code-command] Step 2 complete: Retrieved tool matches")

        # STEP 3: Format the matched tools with their corresponding steps
        tools_matched = []
        results = tools_data.get('results', [])

        for result in results:
            step_text = result.get('prompt', '')
            step_index = result.get('prompt_index', 0)
            best_match = result.get('best_match')

            if best_match:
                tools_matched.append({
                    'step': step_text,
                    'step_index': step_index,
                    'best_match': best_match
                })

        print(f"[code-command] Step 3 complete: Formatted {len(tools_matched)} tool matches")

        # Prepare execution parameters for roll_the_dice
        execution_ready = {
            'prompts': sequence,
            'session_id': session_id,
            'max_tools': max_tools
        }

        # Build response
        response_data = {
            'status': 'success',
            'message': f'Successfully processed text into {len(sequence)} steps and matched with {len(tools_matched)} tools',
            'sequence': sequence,
            'tools_matched': tools_matched,
            'execution_ready': execution_ready,
            'metadata': {
                'text_analysis': sequence_data.get('metadata', {}),
                'tool_retrieval': tools_data.get('metadata', {}),
                'total_steps': len(sequence),
                'total_tools_matched': len(tools_matched),
                'model_used': model,
                'max_tools': max_tools
            }
        }

        print(f"[code-command] Complete: {len(sequence)} steps, {len(tools_matched)} tools matched")
        return jsonify(response_data), 200

    except requests.exceptions.Timeout as e:
        return jsonify({
            'status': 'error',
            'message': 'Request timeout while processing',
            'error': str(e)
        }), 504
    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': 'Network error while processing',
            'error': str(e)
        }), 500
    except Exception as e:
        return handle_error(e)


# Global error handler for uncaught exceptions
@app.errorhandler(Exception)
def handle_uncaught_exception(e):
    """Handle any uncaught exceptions and send to Sentry."""
    return handle_error(e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
