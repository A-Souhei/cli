# Coder MCP Server

A Model Context Protocol (MCP) server that provides tools for executing Python and R code, as well as detecting code snippets in text.

## Features

### Tools

#### 1. `run_python_code`
Execute Python code in the CLI's virtual environment.

- **Description**: Runs Python code from the current working directory where the CLI was opened
- **Environment**: Uses the same Python environment as the CLI with all installed packages (pandas, numpy, scikit-learn, matplotlib, etc.)
- **Parameters**:
  - `code` (required): The Python code to execute
  - `working_dir` (optional): Working directory for execution (defaults to current directory)
- **Returns**: JSON object with stdout, stderr, exit_code, and python_executable
- **Timeout**: 30 seconds

**Example**:
```json
{
  "code": "import pandas as pd\nprint(pd.__version__)"
}
```

#### 2. `run_r_code`
Execute R code using the host system's R installation.

- **Description**: Runs R code from the current working directory where the CLI was opened
- **Environment**: Uses host-installed R and R libraries
- **Parameters**:
  - `code` (required): The R code to execute
  - `working_dir` (optional): Working directory for execution (defaults to current directory)
- **Returns**: JSON object with stdout, stderr, and exit_code
- **Timeout**: 30 seconds
- **Requirements**: R must be installed on the host system

**Example**:
```json
{
  "code": "print(R.version.string)"
}
```

#### 3. `detect_code`
Detect and extract Python or R code from text responses.

- **Description**: Analyzes text (such as LLM responses) and identifies code blocks with language specifiers
- **Detection**: Looks for ```python or ```r code blocks, also uses heuristics for generic code blocks
- **Parameters**:
  - `text` (required): The text to analyze for code content
- **Returns**: JSON object with `language` and `code` fields if detected, or `null` if no code found

**Example**:
```json
{
  "text": "Here's a solution:\n```python\nimport numpy as np\nprint(np.array([1,2,3]))\n```"
}
```

## Installation

1. Install the MCP package:
```bash
pip install mcp
```

2. Configure your MCP client to use this server via stdio.

## Usage

The server runs as a stdio MCP server and can be started with:

```bash
python system_mcps/coder/server.py
```

## Notes

- Python code execution uses the CLI's virtual environment, ensuring access to all data analysis packages
- R code execution requires R to be installed on the host system
- Both code execution tools have a 30-second timeout to prevent hanging
- The detect_code tool supports both explicit language tags and heuristic-based detection
