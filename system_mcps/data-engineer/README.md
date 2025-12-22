# Data Engineer MCP Server

A Model Context Protocol (MCP) server that provides advanced data engineering and code analysis tools.

## Features

This MCP server now provides **8 tools** for data engineering and code analysis tasks.

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
- For production-grade quality with better statistical fidelity, use `generate_fake_data_ctgan`

### 2. High-Quality Synthetic Data Generation (`generate_fake_data_ctgan`)
Generate production-grade synthetic data using CTGAN (Denoising Diffusion Probabilistic Models) via ydata-synthetic.

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
- CTGAN provides superior quality but takes significantly longer (several minutes)
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

### 6. Research-Grade Synthetic Data Generation (`generate_fake_data_with_ddpm`)
Generate synthetic data using Gaussian Multinomial Diffusion (GMD/DDPM) via the tabular-gmd library.

**Capabilities:**
- Combines Gaussian diffusion for numerical features and Multinomial diffusion for categorical features
- Automatic detection and handling of mixed data types
- State-of-the-art diffusion models for tabular data
- Configurable diffusion timesteps (auto-optimized based on dataset size)
- Configurable training epochs (default: 10, minimum: 5)
- Load data from CSV, JSON, or Parquet files
- Privacy-preserving synthetic data generation
- Minimum 10 rows required (50+ rows recommended for quality results)

**Use Cases:**
- Research and academic projects requiring state-of-the-art synthetic data
- Complex tabular data with mixed types (numerical + categorical)
- Privacy-preserving data sharing for research
- Generating training data for machine learning experiments
- Benchmarking and evaluating synthetic data generation methods

**Comparison with Other Methods:**
- **WGAN (generate_fake_data)**: Fastest but lower quality
- **CTGAN (generate_fake_data_ctgan)**: Good quality, moderate speed
- **GMD/DDPM (this tool)**: Research-grade quality using cutting-edge diffusion models
- Processing time depends on epochs, timesteps, and data size (typically 1-5 minutes)

### 7. DDPM-Based Code Comparison (`compare_codes_with_ddpm`)
Compare two code files using DDPM (Denoising Diffusion Probabilistic Models) embeddings via the tabular-gmd service.

**Capabilities:**
- DDPM-based code comparison using diffusion model embeddings
- Different approach than traditional CodeBERT embeddings
- May capture different aspects of code similarity
- Support for Python and R programming languages
- Integration with tabular-gmd remote service
- Automatic health checking and error handling

**Use Cases:**
- Advanced code similarity analysis with diffusion models
- Comparing code from a diffusion model perspective
- Duplicate code detection using alternative embeddings
- Understanding code relationships through DDPM
- Research on code similarity with novel approaches

**Requirements:**
- Requires tabular-gmd service to be running and configured in `config.yaml`
- The service must have the `/code/similarity` endpoint available

### 8. Code Fingerprint Generation (`code_fingerprint`)
Generate unique fingerprints for code files using DDPM embeddings via the tabular-gmd service.

**Capabilities:**
- Compact, deterministic fingerprint generation using DDPM
- Semantic code fingerprinting (not just traditional hashing)
- Robust to minor formatting changes
- Sensitive to meaningful code modifications
- Support for Python and R programming languages
- Integration with tabular-gmd remote service
- Automatic language detection from file extensions

**Use Cases:**
- Quick code change detection
- Code versioning and tracking
- Duplicate code detection across projects
- Code indexing and retrieval systems
- Semantic code fingerprinting for databases
- Build system cache invalidation

**Requirements:**
- Requires tabular-gmd service to be running and configured in `config.yaml`
- The service must have the `/code/fingerprint` endpoint available

**How it differs from traditional hashing:**
- Traditional hashing (MD5, SHA) is sensitive to any character change, including whitespace and comments
- DDPM-based fingerprints capture semantic code properties
- More robust to formatting changes while detecting meaningful code modifications
- Better suited for semantic code tracking and similarity detection

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

- **ydata-synthetic**: WGAN and CTGAN-based synthetic data generation (via transformer service)
- **tabular-gmd**: GMD/DDPM-based synthetic data generation (research-grade diffusion models)
- **pandas**: Data manipulation and file I/O
- **numpy**: Numerical operations
- **requests**: HTTP client for transformer service
- **mcp**: Model Context Protocol SDK

### Installing tabular-gmd

The tabular-gmd library is included as a git submodule. Install it with:

```bash
cd system_mcps/data-engineer/tabular-gmd
pip install -e .
```

## Environment Variables

- `TRANSFORMER_URL`: URL for transformer service (default: http://localhost:16050)
- `MCP_DEBUG`: Enable debug logging (default: false)

## Configuration

The tabular-gmd service endpoint is configured in `config.yaml`:

```yaml
tabular_gmd:
  url: "http://192.168.31.23:15432"  # Change to your tabular-gmd service URL
  timeout: 300  # 5 minutes - for DDPM operations
```

Tools that require the tabular-gmd service:
- `generate_fake_data_with_ddpm`: Uses `/quick-generate` endpoint
- `compare_codes_with_ddpm`: Uses `/code/similarity` endpoint  
- `code_fingerprint`: Uses `/code/fingerprint` endpoint

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

### Generate Synthetic Data (High Quality - CTGAN)
```python
# User prompt: "Generate 500 high-quality synthetic samples from @data.csv using CTGAN"
# Tool: generate_fake_data_ctgan
{
    "file_path": "data.csv",
    "num_samples": 500,
    "epochs": 300,
    "output_path": "synthetic_data_high_quality.csv"
}
```

### Generate Synthetic Data (Research-Grade - GMD/DDPM)
```python
# User prompt: "Generate 200 synthetic samples from @data.csv using diffusion models"
# Tool: generate_fake_data_with_ddpm
{
    "file_path": "data.csv",
    "num_samples": 200,
    "epochs": 10,
    "output_path": "synthetic_data_ddpm.csv"
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

### Compare Codes with DDPM
```python
# User prompt: "Compare @file1.py and @file2.py using DDPM"
# Tool: compare_codes_with_ddpm
{
    "file_path1": "file1.py",
    "file_path2": "file2.py"
}
```

### Generate Code Fingerprint
```python
# User prompt: "Generate a fingerprint for @my_script.py"
# Tool: code_fingerprint
{
    "file_path": "my_script.py"
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
  - CTGAN: minimum 50 samples for meaningful results
  - GMD/DDPM: minimum 10 samples (50+ recommended for good quality)
- AST generation only supports Python code
- Code similarity (CodeBERT) requires transformer service to be running
- DDPM-based code tools require tabular-gmd service to be running and configured
- CTGAN training is computationally intensive (several minutes depending on data size and epochs)
- WGAN is faster but may not capture complex relationships as well as CTGAN
- GMD/DDPM provides research-grade quality but training time depends on epochs and timesteps
- GMD/DDPM (local) requires tabular-gmd submodule to be installed

## Contributing

When adding new tools to this MCP:

1. Follow the existing tool pattern in `server.py`
2. Add tool metadata to `tools.yaml`
3. Update this README with tool documentation
4. Add comprehensive tests
5. Validate security considerations
