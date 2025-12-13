#!/usr/bin/env python3
"""
Data Engineer MCP Server - A Model Context Protocol server for data engineering tasks.

This MCP server provides tools for:
1. Synthetic data generation using WGAN (ydata-synthetic)
2. Abstract Syntax Tree (AST) generation from Python code
3. Code similarity analysis using CodeBERT embeddings
4. AST-based code similarity comparison for structural analysis
"""

import os
import sys
import json
import ast as python_ast
import requests
import yaml
from pathlib import Path
from typing import Any, Dict

# Constants
DEBUG_MODE = os.getenv('MCP_DEBUG', 'false').lower() == 'true'
MIN_DATASET_SIZE_FOR_SYNTHESIS = 10  # Minimum rows required for synthetic data generation
DEFAULT_SYNTHESIS_EPOCHS = 10  # Default training epochs for faster MCP processing
SYNTHESIS_BATCH_SIZE_MAX = 32  # Maximum batch size for synthesis training


def debug_print(message: str, **kwargs):
    """Print debug messages if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}", file=sys.stderr)
        if kwargs:
            print(f"[DEBUG] Args: {json.dumps(kwargs, indent=2)}", file=sys.stderr)
        sys.stderr.flush()


# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("Error: mcp package not found. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Initialize the MCP server
app = Server("data-engineer")

# Load tool metadata from YAML
_TOOLS_METADATA_CACHE = None


def load_tools_metadata() -> dict:
    """
    Load tool metadata from tools.yaml file.
    Caches the result for subsequent calls.
    """
    global _TOOLS_METADATA_CACHE
    if _TOOLS_METADATA_CACHE is not None:
        return _TOOLS_METADATA_CACHE

    tools_yaml_path = Path(__file__).parent / "tools.yaml"
    try:
        with open(tools_yaml_path, 'r') as f:
            _TOOLS_METADATA_CACHE = yaml.safe_load(f)
            return _TOOLS_METADATA_CACHE
    except Exception as e:
        debug_print(f"Failed to load tools.yaml: {e}")
        return {"categories": {}, "tools": {}}


def get_transformer_url() -> str:
    """Get transformer service URL from environment or use default."""
    return os.getenv('TRANSFORMER_URL', 'http://localhost:16050')


def validate_working_dir(working_dir: str) -> tuple[bool, str]:
    """
    Validate the working directory to prevent directory traversal attacks.

    Args:
        working_dir: Path to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    try:
        path = Path(working_dir).resolve()
    except (ValueError, OSError) as e:
        return False, f"Invalid path: {str(e)}"

    if not path.exists():
        return False, f"Directory does not exist: {working_dir}"

    if not path.is_dir():
        return False, f"Path is not a directory: {working_dir}"

    # Prevent access to sensitive system directories
    sensitive_dirs = [
        Path("/etc"),
        Path("/sys"),
        Path("/proc"),
        Path("/dev"),
        Path("/root"),
        Path("/boot"),
    ]

    for sensitive_dir in sensitive_dirs:
        try:
            path.relative_to(sensitive_dir)
            return False, f"Access to sensitive directory not allowed: {sensitive_dir}"
        except ValueError:
            continue

    return True, ""


def read_file_safe(file_path: str, working_dir: str) -> tuple[bool, str]:
    """
    Safely read a file with validation.

    Args:
        file_path: Path to the file
        working_dir: Working directory for relative paths

    Returns:
        Tuple of (success, content_or_error)
    """
    try:
        if not os.path.isabs(file_path):
            file_path = os.path.join(working_dir, file_path)

        path = Path(file_path).resolve()

        # Validate the file is within working directory
        try:
            path.relative_to(Path(working_dir).resolve())
        except ValueError:
            return False, f"File is outside working directory: {file_path}"

        if not path.exists():
            return False, f"File does not exist: {file_path}"

        if not path.is_file():
            return False, f"Path is not a file: {file_path}"

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        return True, content

    except Exception as e:
        return False, f"Error reading file: {str(e)}"


def write_file_safe(file_path: str, content: str, working_dir: str) -> tuple[bool, str]:
    """
    Safely write to a file with validation.

    Args:
        file_path: Path to the file
        content: Content to write
        working_dir: Working directory for relative paths

    Returns:
        Tuple of (success, message)
    """
    try:
        if not os.path.isabs(file_path):
            file_path = os.path.join(working_dir, file_path)

        path = Path(file_path).resolve()

        # Validate the file is within working directory
        try:
            path.relative_to(Path(working_dir).resolve())
        except ValueError:
            return False, f"File is outside working directory: {file_path}"

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True, f"Successfully wrote to {file_path}"

    except Exception as e:
        return False, f"Error writing file: {str(e)}"


def generate_synthetic_data(file_path: str, num_samples: int, working_dir: str) -> Dict[str, Any]:
    """
    Generate synthetic data from a real dataset using ydata-synthetic DDPM.

    Args:
        file_path: Path to the input data file (CSV, JSON, or Parquet)
        num_samples: Number of synthetic samples to generate
        working_dir: Working directory for file operations

    Returns:
        Dict with status and synthetic data or error message
    """
    try:
        # Import ydata-synthetic
        from ydata_synthetic.synthesizers import ModelParameters
        from ydata_synthetic.synthesizers.regular import RegularSynthesizer
        import pandas as pd

        debug_print(f"Loading data from {file_path}")

        # Determine full path
        if not os.path.isabs(file_path):
            file_path = os.path.join(working_dir, file_path)

        path = Path(file_path).resolve()

        # Validate file is within working directory
        try:
            path.relative_to(Path(working_dir).resolve())
        except ValueError:
            return {
                "status": "error",
                "message": f"File is outside working directory: {file_path}"
            }

        if not path.exists():
            return {
                "status": "error",
                "message": f"File does not exist: {file_path}"
            }

        # Load data based on file extension
        file_ext = path.suffix.lower()
        if file_ext == '.csv':
            data = pd.read_csv(path)
        elif file_ext == '.json':
            data = pd.read_json(path)
        elif file_ext in ['.parquet', '.pq']:
            data = pd.read_parquet(path)
        else:
            return {
                "status": "error",
                "message": f"Unsupported file format: {file_ext}. Supported: .csv, .json, .parquet"
            }

        debug_print(f"Loaded data with shape: {data.shape}")

        # Validate data size
        if len(data) < MIN_DATASET_SIZE_FOR_SYNTHESIS:
            return {
                "status": "error",
                "message": f"Dataset too small ({len(data)} rows). Minimum {MIN_DATASET_SIZE_FOR_SYNTHESIS} rows required for synthetic data generation."
            }

        # Prepare data for synthesis
        # Only use numeric and categorical columns
        numeric_cols = data.select_dtypes(include=['int64', 'float64']).columns.tolist()
        categorical_cols = data.select_dtypes(include=['object', 'category']).columns.tolist()

        debug_print(f"Numeric columns: {numeric_cols}, Categorical columns: {categorical_cols}")

        if not numeric_cols and not categorical_cols:
            return {
                "status": "error",
                "message": "No suitable columns found for synthesis. Need numeric or categorical columns."
            }

        # Configure model parameters (lightweight for MCP context)
        model_params = ModelParameters(
            batch_size=min(SYNTHESIS_BATCH_SIZE_MAX, len(data)),
            epochs=DEFAULT_SYNTHESIS_EPOCHS,
            lr=0.001,
            betas=(0.5, 0.9)
        )

        debug_print("Initializing synthesizer...")

        # Initialize synthesizer with regular (non-conditional) model
        synthesizer = RegularSynthesizer(
            modelname='wgan',  # Using WGAN (Wasserstein GAN) for faster training on small datasets
            model_parameters=model_params
        )

        debug_print("Fitting synthesizer...")

        # Fit the synthesizer on the data
        synthesizer.fit(data=data, train_arguments={"epochs": DEFAULT_SYNTHESIS_EPOCHS}, num_cols=numeric_cols, cat_cols=categorical_cols)

        debug_print(f"Generating {num_samples} synthetic samples...")

        # Generate synthetic data
        synthetic_data = synthesizer.sample(num_samples)

        debug_print(f"Generated synthetic data with shape: {synthetic_data.shape}")

        return {
            "status": "success",
            "message": f"Generated {len(synthetic_data)} synthetic samples",
            "num_samples": len(synthetic_data),
            "num_columns": len(synthetic_data.columns),
            "columns": synthetic_data.columns.tolist(),
            "data_preview": synthetic_data.head(5).to_dict(orient='records'),
            "data_full": synthetic_data.to_dict(orient='records')
        }

    except ImportError as e:
        return {
            "status": "error",
            "message": f"ydata-synthetic not installed: {str(e)}. Install with: pip install ydata-synthetic"
        }
    except Exception as e:
        debug_print(f"Error in generate_synthetic_data: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to generate synthetic data: {str(e)}"
        }


def generate_ast_from_code(code_or_file: str, working_dir: str, is_file: bool = True) -> Dict[str, Any]:
    """
    Generate Abstract Syntax Tree (AST) from Python code.

    Args:
        code_or_file: Either a file path or code string
        working_dir: Working directory for file operations
        is_file: Whether code_or_file is a file path (True) or code string (False)

    Returns:
        Dict with AST information or error message
    """
    try:
        # Get code content
        if is_file:
            success, content = read_file_safe(code_or_file, working_dir)
            if not success:
                return {
                    "status": "error",
                    "message": content  # content contains error message
                }
            code = content
            source_type = "file"
            source = code_or_file
        else:
            code = code_or_file
            source_type = "string"
            source = "<code string>"

        debug_print(f"Parsing code from {source_type}: {source}")

        # Parse the code into an AST
        tree = python_ast.parse(code)

        # Extract AST information
        ast_info = {
            "status": "success",
            "source_type": source_type,
            "source": source,
            "ast_dump": python_ast.dump(tree, indent=2),
            "statistics": {
                "total_nodes": 0,
                "classes": [],
                "functions": [],
                "imports": [],
                "variables": []
            }
        }

        # Walk the AST and collect statistics in O(n) time
        # Build parent-child relationships during single pass
        method_nodes = set()
        
        # Single pass: collect all nodes and build parent relationships
        for node in python_ast.walk(tree):
            ast_info["statistics"]["total_nodes"] += 1
            
            if isinstance(node, python_ast.ClassDef):
                # Collect methods for this class
                for item in node.body:
                    if isinstance(item, python_ast.FunctionDef):
                        method_nodes.add(item)
                
                ast_info["statistics"]["classes"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "methods": [m.name for m in node.body if isinstance(m, python_ast.FunctionDef)],
                    "bases": [python_ast.unparse(base) for base in node.bases]
                })

            elif isinstance(node, python_ast.FunctionDef):
                # Only add top-level functions (not methods)
                # Check if this function was marked as a method
                if node not in method_nodes:
                    ast_info["statistics"]["functions"].append({
                        "name": node.name,
                        "lineno": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "decorators": [python_ast.unparse(dec) for dec in node.decorator_list]
                    })

            elif isinstance(node, python_ast.Import):
                for alias in node.names:
                    ast_info["statistics"]["imports"].append({
                        "type": "import",
                        "module": alias.name,
                        "alias": alias.asname,
                        "lineno": node.lineno
                    })

            elif isinstance(node, python_ast.ImportFrom):
                for alias in node.names:
                    ast_info["statistics"]["imports"].append({
                        "type": "from_import",
                        "module": node.module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "lineno": node.lineno
                    })

            elif isinstance(node, python_ast.Assign):
                for target in node.targets:
                    if isinstance(target, python_ast.Name):
                        ast_info["statistics"]["variables"].append({
                            "name": target.id,
                            "lineno": node.lineno
                        })

        # Add summary counts
        ast_info["summary"] = {
            "total_nodes": ast_info["statistics"]["total_nodes"],
            "num_classes": len(ast_info["statistics"]["classes"]),
            "num_functions": len(ast_info["statistics"]["functions"]),
            "num_imports": len(ast_info["statistics"]["imports"]),
            "num_variables": len(ast_info["statistics"]["variables"])
        }

        return ast_info

    except SyntaxError as e:
        return {
            "status": "error",
            "message": f"Syntax error in Python code: {str(e)}",
            "lineno": e.lineno,
            "offset": e.offset,
            "text": e.text
        }
    except Exception as e:
        debug_print(f"Error in generate_ast_from_code: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to generate AST: {str(e)}"
        }


def compare_code_files_similarity(file_path1: str, file_path2: str, working_dir: str, metric: str = "cosine") -> Dict[str, Any]:
    """
    Compare similarity between two code files using CodeBERT embeddings.

    Args:
        file_path1: Path to first code file
        file_path2: Path to second code file
        working_dir: Working directory for file operations
        metric: Similarity metric (cosine, euclidean, dot_product)

    Returns:
        Dict with similarity score and interpretation
    """
    try:
        # Read both files
        success1, content1 = read_file_safe(file_path1, working_dir)
        if not success1:
            return {
                "status": "error",
                "message": f"Error reading first file: {content1}"
            }

        success2, content2 = read_file_safe(file_path2, working_dir)
        if not success2:
            return {
                "status": "error",
                "message": f"Error reading second file: {content2}"
            }

        debug_print(f"Comparing {file_path1} and {file_path2}")

        # Detect programming languages from file extensions
        ext1 = Path(file_path1).suffix.lower()
        ext2 = Path(file_path2).suffix.lower()

        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.java': 'java',
            '.go': 'go',
            '.rb': 'ruby',
            '.cpp': 'cpp',
            '.c': 'c',
            '.ts': 'typescript',
            '.php': 'php',
            '.rs': 'rust'
        }

        language1 = language_map.get(ext1, '')
        language2 = language_map.get(ext2, '')

        # Call transformer service /code/similarity endpoint
        transformer_url = get_transformer_url()
        debug_print(f"Calling transformer service at {transformer_url}")

        response = requests.post(
            f"{transformer_url}/code/similarity",
            json={
                "code1": content1,
                "code2": content2,
                "language1": language1,
                "language2": language2,
                "metric": metric
            },
            timeout=60
        )

        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Transformer service error: {response.status_code}",
                "details": response.text
            }

        result = response.json()

        if result.get('status') == 'error':
            return result

        # Add file information to result
        result['file1'] = file_path1
        result['file2'] = file_path2
        result['file1_size'] = len(content1)
        result['file2_size'] = len(content2)

        return result

    except requests.exceptions.ConnectionError:
        transformer_url = get_transformer_url()
        return {
            "status": "error",
            "message": f"Could not connect to transformer service at {transformer_url}. Make sure the service is running."
        }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Request to transformer service timed out"
        }
    except Exception as e:
        debug_print(f"Error in compare_code_files_similarity: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to compare code similarity: {str(e)}"
        }


def compare_ast_similarity(file_path1: str, file_path2: str, working_dir: str, metric: str = "cosine") -> Dict[str, Any]:
    """
    Compare similarity between two Python code files using AST-normalized code with CodeBERT.
    
    This function parses both files into ASTs, then uses ast.unparse() to convert them
    back to normalized Python code (consistent formatting, no comments). This normalized
    code is then compared using CodeBERT embeddings, focusing on code structure and logic
    rather than variable names or formatting choices.

    Args:
        file_path1: Path to first Python code file
        file_path2: Path to second Python code file
        working_dir: Working directory for file operations
        metric: Similarity metric (cosine, euclidean, dot_product)

    Returns:
        Dict with AST similarity score, AST information, and interpretation
    """
    try:
        debug_print(f"Comparing AST similarity between {file_path1} and {file_path2}")

        # Generate AST for both files
        ast_result1 = generate_ast_from_code(file_path1, working_dir, is_file=True)
        if ast_result1.get("status") != "success":
            return {
                "status": "error",
                "message": f"Failed to generate AST for first file: {ast_result1.get('message')}"
            }

        ast_result2 = generate_ast_from_code(file_path2, working_dir, is_file=True)
        if ast_result2.get("status") != "success":
            return {
                "status": "error",
                "message": f"Failed to generate AST for second file: {ast_result2.get('message')}"
            }

        debug_print(f"Generated ASTs successfully")

        # Convert AST back to normalized Python code using ast.unparse()
        # This produces valid Python code from the AST, which CodeBERT can process properly
        # The unparsed code is normalized (consistent formatting) which helps focus on structure
        try:
            # Parse original code to get AST
            success1, code1 = read_file_safe(file_path1, working_dir)
            success2, code2 = read_file_safe(file_path2, working_dir)
            
            if not success1 or not success2:
                return {
                    "status": "error",
                    "message": "Failed to read source files for AST unparsing"
                }
            
            tree1 = python_ast.parse(code1)
            tree2 = python_ast.parse(code2)
            
            # Unparse AST to normalized code
            normalized_code1 = python_ast.unparse(tree1)
            normalized_code2 = python_ast.unparse(tree2)
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to normalize code from AST: {str(e)}"
            }

        # Call transformer service to compare normalized code using CodeBERT
        transformer_url = get_transformer_url()
        debug_print(f"Calling transformer service for AST similarity at {transformer_url}")

        response = requests.post(
            f"{transformer_url}/code/similarity",
            json={
                "code1": normalized_code1,
                "code2": normalized_code2,
                "language1": "python",
                "language2": "python",
                "metric": metric
            },
            timeout=60
        )

        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Transformer service error: {response.status_code}",
                "details": response.text
            }

        result = response.json()

        if result.get('status') == 'error':
            return result

        # Enhance result with AST-specific information
        result['comparison_type'] = 'ast_based'
        result['file1'] = file_path1
        result['file2'] = file_path2
        result['ast1_stats'] = ast_result1['summary']
        result['ast2_stats'] = ast_result2['summary']
        
        # Add structural similarity indicators
        result['structural_similarity'] = {
            'classes_match': ast_result1['summary']['num_classes'] == ast_result2['summary']['num_classes'],
            'functions_match': ast_result1['summary']['num_functions'] == ast_result2['summary']['num_functions'],
            'num_classes_diff': abs(ast_result1['summary']['num_classes'] - ast_result2['summary']['num_classes']),
            'num_functions_diff': abs(ast_result1['summary']['num_functions'] - ast_result2['summary']['num_functions']),
            'total_nodes_diff': abs(ast_result1['summary']['total_nodes'] - ast_result2['summary']['total_nodes'])
        }

        # Enhanced interpretation considering AST structure
        original_interpretation = result.get('interpretation', '')
        result['interpretation'] = f"AST-based: {original_interpretation}"
        
        # Add note about what AST similarity means
        result['note'] = (
            "This comparison uses AST-normalized code (parsed and unparsed for consistent formatting). "
            "The normalized code is then compared using CodeBERT, which focuses on code structure and "
            "logic patterns rather than specific variable names or formatting choices. This approach is "
            "effective for detecting structurally similar code with different naming conventions or styles."
        )

        return result

    except requests.exceptions.ConnectionError:
        transformer_url = get_transformer_url()
        return {
            "status": "error",
            "message": f"Could not connect to transformer service at {transformer_url}. Make sure the service is running."
        }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Request to transformer service timed out"
        }
    except Exception as e:
        debug_print(f"Error in compare_ast_similarity: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to compare AST similarity: {str(e)}"
        }


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="generate_fake_data",
            description=(
                "Generate synthetic/fake data from a real dataset using DDPM (Denoising Diffusion "
                "Probabilistic Models) via ydata-synthetic. This tool takes a data file (CSV, JSON, "
                "or Parquet) and generates statistically similar synthetic data that preserves the "
                "distributions and relationships in the original data. The synthetic data can be used "
                "for testing, augmentation, or privacy-preserving demonstrations. Requires at least "
                "10 rows of real data. The generated data will have the same columns and similar "
                "statistical properties as the input data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the input data file (CSV, JSON, or Parquet format)"
                    },
                    "num_samples": {
                        "type": "integer",
                        "description": "Number of synthetic samples to generate"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional path to save the synthetic data (CSV format)"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["file_path", "num_samples"]
            }
        ),
        Tool(
            name="generate_ast",
            description=(
                "Generate an Abstract Syntax Tree (AST) from Python code. This tool parses Python "
                "source code and creates a detailed AST representation, including structural information "
                "about classes, functions, imports, and variables. The AST can be used for code analysis, "
                "refactoring, static analysis, or understanding code structure. Supports both file paths "
                "and code strings as input. Returns the full AST dump along with statistics about classes, "
                "functions, imports, and variables found in the code."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the Python file to analyze"
                    },
                    "code": {
                        "type": "string",
                        "description": "Python code string to analyze (alternative to file_path)"
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format: 'json' (default) or 'text'",
                        "enum": ["json", "text"]
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="compare_code_similarity",
            description=(
                "Compare the similarity between two code files using CodeBERT embeddings from the "
                "transformer service. This tool uses semantic code analysis to determine how similar "
                "two code snippets are, regardless of formatting or variable names. It supports multiple "
                "programming languages (Python, JavaScript, Java, Go, Ruby, etc.) and multiple similarity "
                "metrics (cosine, euclidean, dot product). The similarity score ranges from 0 (completely "
                "different) to 1 (identical). Useful for code duplication detection, finding similar "
                "patterns, code review, and plagiarism detection. Requires the transformer service to "
                "be running."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path1": {
                        "type": "string",
                        "description": "Path to the first code file"
                    },
                    "file_path2": {
                        "type": "string",
                        "description": "Path to the second code file"
                    },
                    "code1": {
                        "type": "string",
                        "description": "First code snippet (alternative to file_path1)"
                    },
                    "code2": {
                        "type": "string",
                        "description": "Second code snippet (alternative to file_path2)"
                    },
                    "metric": {
                        "type": "string",
                        "description": "Similarity metric: 'cosine' (default), 'euclidean', or 'dot_product'",
                        "enum": ["cosine", "euclidean", "dot_product"]
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="compare_ast_similarity",
            description=(
                "Compare the similarity between two Python code files using AST-based CodeBERT embeddings. "
                "This tool first generates Abstract Syntax Tree (AST) representations from both files, "
                "then uses CodeBERT to compute semantic similarity between the AST structures. AST-based "
                "comparison focuses on code structure and logic rather than surface-level features like "
                "variable names, comments, or formatting. This makes it superior for detecting structurally "
                "similar code that uses different naming conventions or coding styles. The similarity score "
                "ranges from 0 (completely different structure) to 1 (identical structure). Ideal for "
                "detecting code clones, refactoring analysis, and identifying functionally equivalent "
                "implementations. Only supports Python files. Requires the transformer service to be running."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path1": {
                        "type": "string",
                        "description": "Path to the first Python code file"
                    },
                    "file_path2": {
                        "type": "string",
                        "description": "Path to the second Python code file"
                    },
                    "metric": {
                        "type": "string",
                        "description": "Similarity metric: 'cosine' (default), 'euclidean', or 'dot_product'",
                        "enum": ["cosine", "euclidean", "dot_product"]
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory. Defaults to current directory."
                    }
                },
                "required": ["file_path1", "file_path2"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""

    if name == "generate_fake_data":
        file_path = arguments.get("file_path", "")
        num_samples = arguments.get("num_samples", 100)
        output_path = arguments.get("output_path")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not file_path:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Missing file_path parameter"
            }, indent=2))]

        if num_samples < 1:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "num_samples must be at least 1"
            }, indent=2))]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": error_msg
            }, indent=2))]

        # Generate synthetic data
        result = generate_synthetic_data(file_path, num_samples, working_dir)

        # Optionally save to output file
        if result.get("status") == "success" and output_path:
            try:
                import pandas as pd
                df = pd.DataFrame(result["data_full"])
                
                # Write file safely
                csv_content = df.to_csv(index=False)
                success, message = write_file_safe(output_path, csv_content, working_dir)
                
                if success:
                    result["output_file"] = output_path
                    result["message"] += f" and saved to {output_path}"
                else:
                    result["warning"] = f"Generated data successfully but failed to save: {message}"
            except Exception as e:
                result["warning"] = f"Generated data successfully but failed to save: {str(e)}"

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "generate_ast":
        file_path = arguments.get("file_path")
        code = arguments.get("code")
        output_format = arguments.get("output_format", "json")
        working_dir = arguments.get("working_dir", os.getcwd())

        if not file_path and not code:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Either file_path or code must be provided"
            }, indent=2))]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": error_msg
            }, indent=2))]

        # Generate AST
        if file_path:
            result = generate_ast_from_code(file_path, working_dir, is_file=True)
        else:
            result = generate_ast_from_code(code, working_dir, is_file=False)

        # Format output
        if output_format == "text" and result.get("status") == "success":
            text_output = f"AST for {result['source']}:\n\n"
            text_output += f"Summary:\n"
            text_output += f"  Total nodes: {result['summary']['total_nodes']}\n"
            text_output += f"  Classes: {result['summary']['num_classes']}\n"
            text_output += f"  Functions: {result['summary']['num_functions']}\n"
            text_output += f"  Imports: {result['summary']['num_imports']}\n"
            text_output += f"  Variables: {result['summary']['num_variables']}\n\n"
            text_output += f"Full AST:\n{result['ast_dump']}\n"
            return [TextContent(type="text", text=text_output)]

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "compare_code_similarity":
        file_path1 = arguments.get("file_path1")
        file_path2 = arguments.get("file_path2")
        code1 = arguments.get("code1")
        code2 = arguments.get("code2")
        metric = arguments.get("metric", "cosine")
        working_dir = arguments.get("working_dir", os.getcwd())

        # Validate inputs
        if not (file_path1 or code1) or not (file_path2 or code2):
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Must provide either file_path1 and file_path2, or code1 and code2"
            }, indent=2))]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": error_msg
            }, indent=2))]

        # If code snippets provided, use transformer service directly
        if code1 and code2:
            try:
                transformer_url = get_transformer_url()
                response = requests.post(
                    f"{transformer_url}/code/similarity",
                    json={
                        "code1": code1,
                        "code2": code2,
                        "metric": metric
                    },
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                else:
                    return [TextContent(type="text", text=json.dumps({
                        "status": "error",
                        "message": f"Transformer service error: {response.status_code}",
                        "details": response.text
                    }, indent=2))]

            except Exception as e:
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "message": f"Failed to compare code: {str(e)}"
                }, indent=2))]

        # Otherwise, read files and compare
        result = compare_code_files_similarity(file_path1, file_path2, working_dir, metric)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "compare_ast_similarity":
        file_path1 = arguments.get("file_path1")
        file_path2 = arguments.get("file_path2")
        metric = arguments.get("metric", "cosine")
        working_dir = arguments.get("working_dir", os.getcwd())

        # Validate inputs
        if not file_path1 or not file_path2:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": "Both file_path1 and file_path2 are required"
            }, indent=2))]

        # Validate working directory
        is_valid, error_msg = validate_working_dir(working_dir)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": error_msg
            }, indent=2))]

        # Validate that files are Python files
        if not file_path1.endswith('.py'):
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"First file must be a Python file (.py): {file_path1}"
            }, indent=2))]

        if not file_path2.endswith('.py'):
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Second file must be a Python file (.py): {file_path2}"
            }, indent=2))]

        # Compare AST similarity
        result = compare_ast_similarity(file_path1, file_path2, working_dir, metric)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [TextContent(type="text", text=json.dumps({
            "status": "error",
            "message": f"Unknown tool: {name}"
        }, indent=2))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
