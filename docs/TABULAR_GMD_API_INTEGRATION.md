# Tabular GMD API Integration

## Overview

The `generate_fake_data_with_ddpm` tool in the data-engineer MCP server has been updated to use the tabular-gmd API endpoint as the primary method for synthetic data generation, with automatic fallback to the local numpy-based implementation.

## Changes Made

### 1. Configuration (`config.yaml`)

Added tabular-gmd service configuration:

```yaml
# Tabular GMD (Gaussian Multinomial Diffusion) configuration
# Service for generating synthetic tabular data using diffusion models
tabular_gmd:
  url: "http://192.168.31.23:15432"
  timeout: 300  # 5 minutes - synthetic data generation can take time
```

### 2. Server Implementation (`system_mcps/data-engineer/server.py`)

Updated `generate_synthetic_data_ddpm()` function to:

1. **Primary Method**: Try to use the tabular-gmd API endpoint
   - Reads configuration from `config.yaml`
   - Performs health check on the endpoint
   - Uses the `/quick-generate` endpoint for all-in-one file upload and generation
   - Returns results with `model_type: "gmd_ddpm_api"`

2. **Fallback Method**: Use local numpy-based implementation
   - Activated if API is unreachable or returns an error
   - Uses the local tabular-gmd library
   - Returns results with `model_type: "gmd_ddpm"`

### 3. Tool Description

Updated the tool description to inform users about the API endpoint usage:

```
Generate synthetic tabular data using Gaussian Multinomial Diffusion (GMD/DDPM). 
This tool first attempts to use the configured tabular-gmd API endpoint 
which provides GPU-accelerated synthetic data generation. If the API is unreachable, it automatically 
falls back to the local tabular-gmd library using numpy backend.
```

## API Endpoint Details

### Health Check
```bash
curl <TABULAR_GMD_URL>/health
```

Example Response:
```json
{
  "gpu_available": true,
  "gpu_count": 1,
  "gpu_name": "NVIDIA GeForce RTX 2070 with Max-Q Design",
  "status": "healthy",
  "timestamp": "2025-12-17T14:48:38.390060"
}
```

### Quick Generate Endpoint
```bash
POST <TABULAR_GMD_URL>/quick-generate
Content-Type: multipart/form-data
```

**Parameters:**
- `file`: CSV file to upload
- `num_samples`: Number of synthetic samples to generate
- `num_epochs`: Number of training epochs
- `num_timesteps` (optional): Number of diffusion timesteps
- `schedule_type` (optional): Diffusion schedule type (e.g., 'cosine', 'linear')
- `device`: Device to use ('auto', 'cpu', 'cuda')

**Response:** CSV file with synthetic data

## Benefits

1. **Performance**: GPU-accelerated generation via the API is significantly faster than CPU-based local implementation
2. **Automatic Fallback**: No user intervention needed if API is unavailable
3. **Transparency**: Response includes information about which method was used (`model_type`)
4. **Configuration**: Easy to change endpoint via `config.yaml`

## Testing

To test the endpoint configuration, check if it's reachable and operational by running the health check endpoint with the URL configured in `config.yaml`.

## Usage Example

The tool usage remains the same from the user's perspective:

```json
{
  "name": "generate_fake_data_with_ddpm",
  "arguments": {
    "file_path": "data.csv",
    "num_samples": 100,
    "epochs": 10
  }
}
```

The implementation will automatically:
1. Try the API endpoint (if configured and reachable)
2. Fall back to local implementation (if API unavailable)
3. Return results with appropriate metadata

## Future Enhancements

Possible improvements:
- Add API authentication support
- Support for other tabular-gmd endpoints (e.g., `/generate-and-evaluate`)
- Metrics collection on API vs local usage
- Load balancing across multiple API endpoints
