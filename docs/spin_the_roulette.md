# spin_the_roulette MCP Tool

## Overview

The `spin_the_roulette` MCP tool converts long, complex text containing multiple instructions into a structured sequence of single-instruction steps, then matches each step with the most appropriate MCP tool. It uses LLM-powered text analysis to intelligently split and organize multi-step tasks.

## Features

- **Intelligent Text Splitting**: Uses LLM to analyze and split text into distinct instruction steps
- **Multi-iteration Subdivision**: Recursively checks each step to identify and separate multiple instructions
- **Automatic Tool Matching**: Matches each instruction step with the most relevant MCP tool using semantic search
- **Compatible Output**: Returns results in a format compatible with `retrieve_all_tools`
- **Configurable Processing**: Supports custom LLM models and iteration limits

## Architecture

The tool consists of two main components:

### 1. Backend Endpoint: `/mcp-tools/text-to-sequence`

Located in `src/postgresql/app/app.py`, this endpoint handles the text analysis:

- Accepts long text containing multiple instructions
- Uses Ollama LLM to split text into instruction steps
- Iteratively subdivides steps that contain multiple instructions
- Returns a flat list of single-instruction texts

### 2. MCP Tool: `spin_the_roulette`

Located in `system_mcps/coder/server.py`, this tool wraps the endpoint:

- Calls the `/mcp-tools/text-to-sequence` endpoint
- Takes the resulting sequence and calls `/mcp-tools/retrieve` to match tools
- Returns both the sequence and matched tools

## Usage

### Basic Usage

```python
# Using the MCP tool
{
    "name": "spin_the_roulette",
    "arguments": {
        "text": "First, run Python code to print hello. Then, create a new file called test.py with some code. Finally, add that file to the context for analysis."
    }
}
```

### With Custom Parameters

```python
{
    "name": "spin_the_roulette",
    "arguments": {
        "text": "Load data from CSV, calculate statistics, create visualization, and save results",
        "model": "tinyllama",
        "max_iterations": 3
    }
}
```

## Example Prompts

### Example 1: Data Analysis Workflow

**Input:**
```
I need to analyze customer data. First, load the data from customers.csv.
Then, calculate the average purchase amount and customer lifetime value for each segment.
After that, create visualizations showing the distribution of customer segments.
Finally, save the analysis results to a report file.
```

**Expected Output:**
```json
{
  "status": "success",
  "sequence": [
    "Load data from customers.csv",
    "Calculate average purchase amount for each customer segment",
    "Calculate customer lifetime value for each segment",
    "Create visualizations showing distribution of customer segments",
    "Save analysis results to a report file"
  ],
  "tools_matched": [
    {
      "step": "Load data from customers.csv",
      "step_index": 0,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "run_python_code",
        "description": "Execute Python code...",
        "similarity": 0.85
      }
    },
    // ... more matches
  ]
}
```

### Example 2: Code Development Task

**Input:**
```
Create a Python script that connects to a database and exports data.
First, write the database connection code.
Then add functions to query and process the data.
After that, implement the export functionality to CSV.
Test the script with sample data and fix any errors.
```

**Expected Sequence:**
- Write database connection code
- Add functions to query data
- Add functions to process data
- Implement export functionality to CSV
- Test script with sample data
- Fix any errors found during testing

### Example 3: Complex Multi-Tool Workflow

**Input:**
```
Set up a new data pipeline: create directories for raw and processed data,
write a Python script to fetch data from an API, add error handling and logging,
create an R script for statistical analysis, and document the entire pipeline.
```

**Expected Sequence:**
- Create directory for raw data
- Create directory for processed data
- Write Python script to fetch data from API
- Add error handling to Python script
- Add logging to Python script
- Create R script for statistical analysis
- Document the data pipeline

## Parameters

### `text` (required)
- **Type**: `string`
- **Description**: Long text containing multiple instructions or tasks to be split and analyzed
- **Example**: `"First do X, then do Y, and finally do Z"`

### `model` (optional)
- **Type**: `string`
- **Default**: `"tinyllama"`
- **Description**: LLM model to use for text analysis
- **Supported Models**: Any model available in your Ollama installation

### `max_iterations` (optional)
- **Type**: `integer`
- **Default**: `3`
- **Range**: `1-5` (values outside this range are clamped)
- **Description**: Maximum number of iterations for subdividing steps that contain multiple instructions

## Response Format

```json
{
  "status": "success",
  "message": "Successfully processed text into N steps and matched with tools",
  "sequence": [
    "Step 1 text",
    "Step 2 text",
    ...
  ],
  "tools_matched": [
    {
      "step": "Step 1 text",
      "step_index": 0,
      "best_match": {
        "mcp_name": "coder",
        "tool_name": "run_python_code",
        "description": "Execute Python code...",
        "similarity": 0.87,
        "extracted_params": {
          "code": "..."
        }
      }
    },
    ...
  ],
  "metadata": {
    "text_analysis": {
      "original_length": 500,
      "total_steps": 5,
      "model_used": "tinyllama",
      "iterations_performed": 2
    },
    "tool_retrieval": {
      "threshold": 0.5,
      "total_prompts": 5,
      "total_tools_searched": 12
    },
    "model_used": "tinyllama"
  }
}
```

## Error Handling

### Common Errors

1. **Missing Text Parameter**
```json
{
  "status": "error",
  "message": "No text provided"
}
```

2. **Ollama Not Available**
```json
{
  "status": "error",
  "message": "Failed to get response from LLM service. Make sure Ollama is running."
}
```

3. **Service Connection Error**
```json
{
  "status": "error",
  "message": "Could not connect to PostgreSQL API at http://localhost:15000. Make sure the service is running."
}
```

4. **Timeout Error**
```json
{
  "status": "error",
  "message": "Request timed out. LLM processing may take longer for complex texts."
}
```

## Testing

Tests are located in:
- `tests/test_text_to_sequence.py` - Tests for the backend endpoint
- `tests/test_coder_mcp.py` - Tests for the MCP tool

### Running Tests

```bash
# Test the endpoint (requires PostgreSQL API and Ollama)
pytest tests/test_text_to_sequence.py -v

# Test the MCP tool (requires PostgreSQL API and Ollama)
pytest tests/test_coder_mcp.py::TestCoderMCP::test_spin_the_roulette_basic -v

# Run all spin_the_roulette tests
pytest tests/test_coder_mcp.py -k "spin_the_roulette" -v
```

## Dependencies

- **Ollama**: Required for LLM-based text analysis
  - Default endpoint: `http://localhost:11434`
  - Can be configured via `OLLAMA_API_URL` environment variable

- **PostgreSQL API**: Required for tool retrieval
  - Default endpoint: `http://localhost:15000`
  - Configured via `POSTGRES_API_URL` or auto-detected

- **Transformer Service**: Required for embedding generation
  - Default endpoint: `http://localhost:16050`

## Performance Considerations

- **Processing Time**: Depends on text length and LLM processing speed
  - Simple texts: ~5-10 seconds
  - Complex texts: ~30-60 seconds
  - Very complex texts: up to 180 seconds (timeout limit)

- **Token Usage**: Each iteration requires LLM calls
  - Initial split: ~500-2000 tokens
  - Per-step analysis: ~200-500 tokens per step
  - Total: Can range from 1000 to 10000 tokens depending on complexity

- **Optimization Tips**:
  - Use lower `max_iterations` for faster processing
  - Pre-split very long texts manually if possible
  - Use faster models for simple texts

## Best Practices

1. **Clear Instructions**: Write clear, well-structured text for better splitting
   - Use explicit step markers (First, Second, Then, Finally, etc.)
   - Separate distinct actions with punctuation
   - Group related sub-tasks together

2. **Appropriate Complexity**: Balance detail level
   - Too vague: "Do data analysis" → May not split properly
   - Too detailed: Including code snippets → May confuse the splitter
   - Just right: "Calculate mean and standard deviation from CSV data"

3. **Iteration Tuning**: Adjust `max_iterations` based on text
   - Simple list: `max_iterations: 1`
   - Moderate complexity: `max_iterations: 2-3` (default)
   - Very complex nested tasks: `max_iterations: 4-5`

4. **Validation**: Always check the returned sequence
   - Verify steps make sense
   - Ensure proper order is maintained
   - Check that no steps were lost or merged incorrectly

## Comparison with Related Tools

| Feature | spin_the_roulette | retrieve_all_tools | roll_the_dice |
|---------|-------------------|-------------------|---------------|
| Input | Long text | Array of prompts | Array of prompts |
| Text Analysis | ✅ Yes | ❌ No | ❌ No |
| Tool Matching | ✅ Yes | ✅ Yes | ✅ Yes |
| Tool Execution | ❌ No | ❌ No | ✅ Yes |
| Session Required | ❌ No | ❌ No | ✅ Yes |
| Use Case | Parse complex instructions | Match known prompts to tools | Execute multiple tools |

## Integration Examples

### Example 1: CLI Integration

```python
# Use spin_the_roulette to process user input
user_input = """
I want to analyze my sales data.
Load sales.csv, calculate monthly totals,
create a trend chart, and save to report.pdf
"""

result = mcp_client.call_tool("spin_the_roulette", {
    "text": user_input
})

# Get the sequence and matched tools
sequence = result["sequence"]
tools = result["tools_matched"]

# Display to user
print(f"I've broken down your request into {len(sequence)} steps:")
for i, step in enumerate(sequence, 1):
    tool_match = tools[i-1]["best_match"]
    print(f"{i}. {step}")
    print(f"   → Tool: {tool_match['tool_name']} ({tool_match['similarity']:.2f})")
```

### Example 2: Workflow Automation

```python
# Parse workflow description
workflow_text = load_workflow_template("data_pipeline.txt")

# Split into steps
result = mcp_client.call_tool("spin_the_roulette", {
    "text": workflow_text,
    "max_iterations": 4
})

# Convert to executable workflow
workflow_steps = []
for match in result["tools_matched"]:
    if match["best_match"]:
        workflow_steps.append({
            "tool": match["best_match"]["tool_name"],
            "params": match["best_match"]["extracted_params"],
            "description": match["step"]
        })

# Execute workflow with roll_the_dice or custom executor
execute_workflow(workflow_steps, session_id="workflow_123")
```

## Troubleshooting

### Issue: Steps not properly split

**Symptom**: All text returned as a single step

**Solutions**:
- Ensure Ollama is running and responding
- Try increasing `max_iterations`
- Rewrite text with clearer step markers
- Check Ollama model is capable (tinyllama minimum)

### Issue: Tool matching returning None

**Symptom**: `best_match` is `null` for some steps

**Solutions**:
- Ensure MCP tools are stored in database
- Check tool embeddings are generated
- Verify PostgreSQL API is running
- Lower similarity threshold in retrieve endpoint

### Issue: Timeout errors

**Symptom**: Requests timing out

**Solutions**:
- Reduce `max_iterations`
- Split very long texts manually
- Increase timeout in configuration
- Use faster LLM model

## Future Enhancements

Potential improvements:
- Support for custom prompts/templates
- Parallel step processing
- Step dependency detection
- Automatic parameter extraction refinement
- Support for non-English languages
- Step prioritization and ordering optimization

## API Reference

### Endpoint: POST `/mcp-tools/text-to-sequence`

**Request:**
```json
{
  "text": "string (required)",
  "model": "string (optional, default: tinyllama)",
  "max_iterations": "integer (optional, default: 3, max: 5)"
}
```

**Response:**
```json
{
  "status": "success",
  "sequence": ["step1", "step2", ...],
  "metadata": {
    "original_length": 500,
    "total_steps": 5,
    "model_used": "tinyllama",
    "iterations_performed": 2
  }
}
```

### MCP Tool: `spin_the_roulette`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "description": "Long text containing multiple instructions"
    },
    "model": {
      "type": "string",
      "description": "Optional LLM model (default: tinyllama)"
    },
    "max_iterations": {
      "type": "integer",
      "description": "Max iterations for subdividing (default: 3, max: 5)"
    }
  },
  "required": ["text"]
}
```

**Output:**
Returns JSON containing:
- `status`: "success" or "error"
- `sequence`: Array of instruction steps
- `tools_matched`: Array of tool matches for each step
- `metadata`: Processing information

## Contributing

To contribute improvements:
1. Add tests to `tests/test_text_to_sequence.py` or `tests/test_coder_mcp.py`
2. Update endpoint in `src/postgresql/app/app.py`
3. Update MCP tool in `system_mcps/coder/server.py`
4. Update this documentation
5. Submit a pull request

## License

Same as parent project.
