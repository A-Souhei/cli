# DDPM Code Analysis Tools

## Overview

Two new tools have been added to the data-engineer MCP server that use DDPM (Denoising Diffusion Probabilistic Models) for advanced code analysis:

1. **compare_codes_with_ddpm** - Compare two code files using DDPM embeddings
2. **code_fingerprint** - Generate unique fingerprints for code using DDPM embeddings

## Prerequisites

These tools require the tabular-gmd service to be running and accessible. The service must be configured in `config.yaml`:

```yaml
tabular_gmd:
  url: "http://192.168.31.23:15432"  # Your tabular-gmd service URL
  timeout: 300  # 5 minutes timeout
```

## Tool 1: Compare Codes with DDPM

### Description

Compares two code files using DDPM-based embeddings from the tabular-gmd service. This provides a different comparison approach than traditional CodeBERT embeddings, potentially capturing different aspects of code similarity through diffusion-based representations.

### Endpoints Used

- Health check: `GET {tabular_gmd_url}/health`
- Compare codes: `POST {tabular_gmd_url}/code/similarity`

### Usage

**Via MCP Protocol:**
```json
{
  "name": "compare_codes_with_ddpm",
  "arguments": {
    "file_path1": "src/module1.py",
    "file_path2": "src/module2.py"
  }
}
```

**Via AI CLI:**
```
Compare @src/module1.py and @src/module2.py using DDPM
```

### Supported Languages

- Python (.py)
- R (.r, .R)

Note: The implementation only detects Python and R file extensions. Other file types will default to 'python'.

### Response Format

```json
{
  "status": "success",
  "comparison_method": "ddpm",
  "file1": "src/module1.py",
  "file2": "src/module2.py",
  "file1_size": 1234,
  "file2_size": 2345,
  "endpoint": "http://192.168.31.23:15432/code/similarity",
  "similarity": 0.85,
  "interpretation": "Highly similar code"
}
```

### Error Handling

The tool includes comprehensive error handling:
- Configuration validation (checks if tabular_gmd URL is configured)
- Health check (verifies service is running)
- File validation (ensures files exist and are within working directory)
- Connection error handling (graceful failure if service unavailable)
- Timeout handling (configurable timeout from config)

### Use Cases

- Advanced code similarity analysis using diffusion models
- Comparing code from a diffusion model perspective
- Duplicate detection using alternative embeddings
- Understanding code relationships through DDPM
- Research on code similarity with novel approaches

## Tool 2: Code Fingerprint

### Description

Generates a unique fingerprint for a code file using DDPM embeddings from the tabular-gmd service. Unlike traditional hashing (MD5, SHA), DDPM-based fingerprints capture semantic code properties, making them more robust to minor formatting changes while still being sensitive to meaningful code modifications.

### Endpoints Used

- Health check: `GET {tabular_gmd_url}/health`
- Fingerprint: `POST {tabular_gmd_url}/code/fingerprint`

### Usage

**Via MCP Protocol:**
```json
{
  "name": "code_fingerprint",
  "arguments": {
    "file_path": "src/main.py"
  }
}
```

**Via AI CLI:**
```
Generate a fingerprint for @src/main.py
```

### Supported Languages

Currently supports Python (.py) and R (.r, .R). Language detection is implemented only for these languages. Other file types will default to 'python'.

### Response Format

```json
{
  "status": "success",
  "file": "src/main.py",
  "file_size": 1234,
  "language": "python",
  "endpoint": "http://192.168.31.23:15432/code/fingerprint",
  "fingerprint": "a1b2c3d4e5f6...",
  "metadata": {
    "model": "ddpm",
    "version": "1.0"
  }
}
```

### Error Handling

Similar comprehensive error handling as compare_codes_with_ddpm:
- Configuration validation
- Health check
- File validation
- Connection error handling
- Timeout handling

### Use Cases

- Quick code change detection
- Code versioning and tracking
- Duplicate code detection across projects
- Code indexing and retrieval systems
- Semantic code fingerprinting for databases
- Build system cache invalidation

### Comparison with Traditional Hashing

| Aspect | Traditional Hash (MD5/SHA) | DDPM Fingerprint |
|--------|---------------------------|------------------|
| Sensitivity | Any character change | Meaningful code changes |
| Format changes | Detects all changes | Robust to formatting |
| Semantic understanding | None | Captures code semantics |
| Use case | Exact match detection | Semantic similarity |

## Implementation Details

### Helper Function: get_tabular_gmd_config()

A shared helper function that loads the tabular-gmd configuration from `config.yaml`:

```python
def get_tabular_gmd_config() -> tuple[Optional[str], int]:
    """
    Load tabular-gmd configuration from config.yaml.
    
    Returns:
        Tuple of (url, timeout). Returns (None, 300) if config not found.
    """
```

### Error Response Format

All error responses follow this format:

```json
{
  "status": "error",
  "message": "Descriptive error message"
}
```

Common error messages:
- `"No tabular_gmd URL configured in config.yaml. Please configure the tabular-gmd service endpoint."`
- `"Tabular-gmd API is not healthy (status: {status_code})"`
- `"Could not connect to tabular-gmd service at {url}: {error}"`
- `"Error reading file: {error}"`
- `"File is outside working directory: {path}"`

## Testing

Tests are included in `tests/test_data_engineer_mcp.py`:

1. **test_compare_codes_with_ddpm** - Tests successful comparison
2. **test_compare_codes_with_ddpm_missing_file** - Tests error handling for missing files
3. **test_code_fingerprint** - Tests successful fingerprint generation
4. **test_code_fingerprint_missing_file** - Tests error handling for missing files

Tests automatically skip if the tabular-gmd service is not available.

Run tests with:
```bash
pytest tests/test_data_engineer_mcp.py -v -k "ddpm or fingerprint"
```

## Configuration Example

Complete configuration in `config.yaml`:

```yaml
# Tabular GMD (Gaussian Multinomial Diffusion) configuration
# Service for generating synthetic tabular data and DDPM-based code analysis
tabular_gmd:
  url: "http://192.168.31.23:15432"  # Change to your tabular-gmd service URL
  timeout: 300  # 5 minutes - for DDPM operations
```

## Troubleshooting

### Service Not Available

If you get "Could not connect to tabular-gmd service" errors:

1. Check if the service is running:
   ```bash
   curl http://192.168.31.23:15432/health
   ```

2. Verify the URL in `config.yaml` is correct

3. Check network connectivity to the service

### Configuration Not Found

If you get "No tabular_gmd URL configured" errors:

1. Ensure `config.yaml` exists in the project root
2. Add the `tabular_gmd` section to the config file
3. Restart the MCP server

### Timeout Errors

If operations timeout:

1. Increase the timeout value in `config.yaml`
2. Check if the service is overloaded
3. Verify the service is responding within expected time

## Architecture

Both tools follow the established pattern from `generate_fake_data_with_ddpm`:

1. **Configuration Loading**: Load service URL from `config.yaml`
2. **Health Check**: Verify service is accessible
3. **API Call**: Make POST request to appropriate endpoint
4. **Response Processing**: Parse and enhance response with metadata
5. **Error Handling**: Graceful fallback with descriptive errors

## Future Enhancements

Potential improvements:
- Add API authentication support
- Support for batch operations (multiple files at once)
- Caching of fingerprints for performance
- Metrics collection on tool usage
- Load balancing across multiple tabular-gmd instances
- Support for comparing entire directories
