# Data Engineer MCP Server

A Model Context Protocol (MCP) server that provides advanced data engineering and code analysis tools.

## Features

### 1. Synthetic Data Generation (`generate_fake_data`)
Generate synthetic data from real data files using WGAN (Wasserstein GAN) via ydata-synthetic.

**Capabilities:**
- Load data from CSV, JSON, or Parquet files
- Generate statistically similar synthetic data
- Preserve data distributions and relationships
- Configurable number of samples
- Privacy-preserving data generation

**Use Cases:**
- Testing with realistic data without exposing sensitive information
- Augmenting training datasets
- Creating demo datasets

### 2. Abstract Syntax Tree Generation (`generate_ast`)
Generate and analyze Abstract Syntax Trees (AST) from Python code files.

**Capabilities:**
- Parse Python source code into AST representation
- Extract structural information (classes, functions, variables)
- Identify code patterns and complexity
- Support for both files and code strings
- Detailed AST visualization

**Use Cases:**
- Code analysis and refactoring
- Static code analysis
- Understanding code structure
- Code generation validation

### 3. Code Similarity Analysis (`compare_code_similarity`)
Compare code similarity using CodeBERT embeddings from the transformer service.

**Capabilities:**
- Semantic code comparison using CodeBERT
- Support for multiple programming languages
- Multiple similarity metrics (cosine, euclidean, dot product)
- File-to-file or snippet-to-snippet comparison
- Interpretation of similarity scores

**Use Cases:**
- Code duplication detection
- Finding similar code patterns
- Code review and refactoring
- Plagiarism detection

### 4. AST-Based Code Similarity (`compare_ast_similarity`)
Compare code similarity using Abstract Syntax Tree representations with CodeBERT embeddings.

**Capabilities:**
- Generate AST from Python files
- Compare AST structures using CodeBERT
- Focus on code structure rather than naming/formatting
- Structural similarity indicators (classes, functions, nodes)
- Multiple similarity metrics (cosine, euclidean, dot product)
- Enhanced interpretation with structural analysis

**Use Cases:**
- Detecting structurally similar code with different naming conventions
- Code clone detection across different coding styles
- Refactoring analysis and validation
- Identifying functionally equivalent implementations
- Advanced plagiarism detection that accounts for variable renaming

## Installation

The MCP server is automatically installed as part of the AI CLI setup. Dependencies are managed separately for this MCP:

```bash
# Install from the data-engineer directory
cd system_mcps/data-engineer
pip install -r requirements.txt
```

## Usage

The data-engineer MCP is automatically started by the AI CLI when needed. You can interact with it through:

1. **Direct CLI commands** - Tools are automatically matched to user prompts
2. **Tool invocation** - Explicitly call tools via MCP protocol
3. **Code mode** - Use `/code` mode with data engineering tasks

## Dependencies

- **ydata-synthetic**: WGAN-based synthetic data generation
- **pandas**: Data manipulation and file I/O
- **numpy**: Numerical operations
- **requests**: HTTP client for transformer service
- **mcp**: Model Context Protocol SDK

## Environment Variables

- `TRANSFORMER_URL`: URL for transformer service (default: http://localhost:16050)
- `MCP_DEBUG`: Enable debug logging (default: false)

## Example Workflows

### Generate Synthetic Data
```python
# User prompt: "Generate 1000 fake samples from @data.csv"
# Tool: generate_fake_data
{
    "file_path": "data.csv",
    "num_samples": 1000,
    "output_path": "synthetic_data.csv"
}
```

### Analyze Code Structure
```python
# User prompt: "Show me the AST of @my_script.py"
# Tool: generate_ast
{
    "file_path": "my_script.py",
    "output_format": "json"
}
```

### Compare Code Similarity
```python
# User prompt: "How similar are @file1.py and @file2.py?"
# Tool: compare_code_similarity
{
    "file_path1": "file1.py",
    "file_path2": "file2.py",
    "metric": "cosine"
}
```

### Compare AST-Based Similarity
```python
# User prompt: "Compare the structure of @script1.py and @script2.py using AST"
# Tool: compare_ast_similarity
{
    "file_path1": "script1.py",
    "file_path2": "script2.py",
    "metric": "cosine"
}
```

## Architecture

The data-engineer MCP follows the same architecture as other system MCPs:

1. **Server Process**: Standalone Python process using stdio for communication
2. **MCP Protocol**: JSON-RPC 2.0 messages for tool discovery and execution
3. **Tool Registration**: Tools are automatically registered in PostgreSQL with embeddings
4. **Integration**: Seamlessly integrated with AI CLI's tool matching system

## Testing

Tests are located in `tests/test_data_engineer_mcp.py`:

```bash
# Run data-engineer MCP tests
pytest tests/test_data_engineer_mcp.py -v
```

## Security Considerations

- File operations are restricted to the working directory
- Input validation on all file paths
- Sensitive directory access is blocked
- .llmignore filtering is applied to prevent exposure of secrets
- WGAN models are loaded securely from ydata-synthetic

## Limitations

- Synthetic data generation requires sufficient real data (minimum 10 samples required, 100+ recommended for best quality)
- AST generation only supports Python code
- Code similarity requires transformer service to be running
- WGAN training can be computationally expensive for large datasets

## Contributing

When adding new tools to this MCP:

1. Follow the existing tool pattern in `server.py`
2. Add tool metadata to `tools.yaml`
3. Update this README with tool documentation
4. Add comprehensive tests
5. Validate security considerations
