# Data Engineer MCP Server

A Model Context Protocol (MCP) server that provides advanced data engineering and code analysis tools.

## Features

### 1. Fast Synthetic Data Generation (`generate_fake_data`)
Generate synthetic data quickly from real data files using WGAN (Wasserstein GAN) via ydata-synthetic.

**Capabilities:**
- Load data from CSV, JSON, or Parquet files
- Fast generation optimized for quick iterations (10 epochs)
- Generate statistically similar synthetic data
- Preserve data distributions and relationships
- Configurable number of samples
- Privacy-preserving data generation
- Minimum 10 rows required (100+ rows recommended)

**Use Cases:**
- Rapid prototyping and testing with realistic data
- Quick data augmentation for development
- Creating demo datasets without long wait times
- Testing data pipelines with synthetic samples

**Speed vs Quality Trade-off:**
- WGAN is optimized for speed, processing in seconds to a few minutes
- For production-grade quality with better statistical fidelity, use `generate_fake_data_ddpm`

### 2. High-Quality Synthetic Data Generation (`generate_fake_data_ddpm`)
Generate production-grade synthetic data using DDPM (Denoising Diffusion Probabilistic Models) via ydata-synthetic.

**Capabilities:**
- Load data from CSV, JSON, or Parquet files
- Superior statistical fidelity (300+ epochs by default)
- Better preservation of complex relationships and distributions
- Configurable training epochs (minimum 100, default 300)
- Production-grade synthetic data quality
- Privacy-preserving data generation
- Minimum 50 rows required for meaningful results

**Use Cases:**
- Production synthetic datasets requiring high accuracy
- Data sharing while maintaining statistical properties
- Generating training data for machine learning models
- Creating realistic test datasets for critical systems

**Speed vs Quality Trade-off:**
- DDPM provides superior quality but takes significantly longer (several minutes)
- For fast iteration during development, use `generate_fake_data` (WGAN)
- Processing time scales with dataset size and epochs (expect 2-10 minutes typical)

### 3. Abstract Syntax Tree Generation (`generate_ast`)
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

### 4. Code Similarity Analysis (`compare_code_similarity`)
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

### 5. AST-Based Code Similarity (`compare_ast_similarity`)
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

- **ydata-synthetic**: WGAN and DDPM-based synthetic data generation
- **pandas**: Data manipulation and file I/O
- **numpy**: Numerical operations
- **requests**: HTTP client for transformer service
- **mcp**: Model Context Protocol SDK

## Environment Variables

- `TRANSFORMER_URL`: URL for transformer service (default: http://localhost:16050)
- `MCP_DEBUG`: Enable debug logging (default: false)

## Example Workflows

### Generate Synthetic Data (Fast - WGAN)
```python
# User prompt: "Generate 1000 fake samples from @data.csv quickly"
# Tool: generate_fake_data
{
    "file_path": "data.csv",
    "num_samples": 1000,
    "output_path": "synthetic_data.csv"
}
```

### Generate Synthetic Data (High Quality - DDPM)
```python
# User prompt: "Generate 500 high-quality synthetic samples from @data.csv using DDPM"
# Tool: generate_fake_data_ddpm
{
    "file_path": "data.csv",
    "num_samples": 500,
    "epochs": 300,
    "output_path": "synthetic_data_high_quality.csv"
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

- Synthetic data generation requires sufficient real data:
  - WGAN: minimum 10 samples (100+ recommended for best quality)
  - DDPM: minimum 50 samples for meaningful results
- AST generation only supports Python code
- Code similarity requires transformer service to be running
- DDPM training is computationally intensive (several minutes depending on data size and epochs)
- WGAN is faster but may not capture complex relationships as well as DDPM

## Contributing

When adding new tools to this MCP:

1. Follow the existing tool pattern in `server.py`
2. Add tool metadata to `tools.yaml`
3. Update this README with tool documentation
4. Add comprehensive tests
5. Validate security considerations
