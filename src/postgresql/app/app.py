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

# Ollama service configuration
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')


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
    import re

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
        # Look for file or directory paths
        path_patterns = [
            r'([^\s,;]+(?:/[^\s,;]+)+)',  # Unix-style paths (check first for full paths)
            r'([A-Za-z]:\\[^\s,;]+)',  # Windows-style paths
            r'(?:file|directory|folder|path)\s+([^\s,;]+)',  # Keyword-prefixed paths
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
            timeout=120
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
                    if similarity >= threshold:
                        match = {
                            'mcp_name': tool.mcp_name,
                            'tool_name': tool.tool_name,
                            'description': tool.description,
                            'similarity': similarity
                        }

                        # Extract parameters if requested
                        if extract_params:
                            match['extracted_params'] = extract_parameters_from_text(
                                prompt,
                                tool.tool_name
                            )

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
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body must be valid JSON'
            }), 400

        # Get required text parameter
        text = data.get('text')
        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: text'
            }), 400

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

        # Get optional parameters
        model = data.get('model', 'tinyllama')
        max_iterations = data.get('max_iterations', 3)

        # Validate max_iterations
        if not isinstance(max_iterations, int) or max_iterations < 1:
            max_iterations = 3
        if max_iterations > 5:
            max_iterations = 5

        original_length = len(text)

        # Step 1: Split text into initial paragraphs/sections
        split_prompt = f"""You are a text analysis assistant. Your task is to split the following text into distinct instruction steps or action items. Each step should represent a single, clear instruction or task.

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
            import re
            json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
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

        for iteration in range(max_iterations):
            steps_to_process = initial_steps if iteration == 0 else final_steps
            final_steps = []

            for step in steps_to_process:
                if not step or len(step.strip()) == 0:
                    continue

                # Ask LLM if this step contains multiple instructions
                check_prompt = f"""You are analyzing an instruction step. Determine if the following text contains multiple distinct instructions or tool usages that should be separated.

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
                    import re
                    json_match = re.search(r'\{.*\}', check_response, re.DOTALL)
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


# Global error handler for uncaught exceptions
@app.errorhandler(Exception)
def handle_uncaught_exception(e):
    """Handle any uncaught exceptions and send to Sentry."""
    return handle_error(e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
