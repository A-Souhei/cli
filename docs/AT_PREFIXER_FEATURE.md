# @ Prefixer Feature Documentation

## Overview

The **@ Prefixer** feature is a powerful context-aware file and directory reference system that enables seamless interaction with code files through the CLI. It provides autocomplete, RAG (Retrieval-Augmented Generation) embeddings, and intelligent code generation capabilities.

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Usage](#usage)
4. [Autocomplete](#autocomplete)
5. [File Context](#file-context)
6. [Directory Context](#directory-context)
7. [Code Generation](#code-generation)
8. [Session Persistence](#session-persistence)
9. [MCP Tools](#mcp-tools)
10. [Examples](#examples)
11. [Technical Details](#technical-details)

## Features

### Core Capabilities

- **Autocomplete**: Press TAB after `@` to see files and directories in the working directory
- **File Context**: Add individual file contents to LLM context using `@file.py`
- **Directory Context**: Add entire directory trees to context using `@directory/`
- **Code Generation**: Generate code directly to files using `@newfile.py` (for non-existing files)
- **Code Editing**: Modify existing files using `@existingfile.py`
- **RAG Embeddings**: Automatically embed file contents for semantic search
- **Session Persistence**: Context persists across session for continuous work

### Supported Languages

- **Python** (.py files)
- **R** (.R, .r files)
- Extensible architecture for additional languages

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Interface (main.py)                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  AtPrefixFileCompleter                               │  │
│  │  - TAB autocomplete for @ prefixed paths             │  │
│  │  - Shows files and directories                       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────────┐       ┌──────────────────────┐
│  Session Manager  │       │  MCP Coder System    │
│  - Session ID     │       │  - write_python_code │
│  - Persistence    │       │  - write_r_code      │
└──────┬────────────┘       │  - edit_python_code  │
       │                    │  - edit_r_code       │
       │                    │  - add_file_context  │
       │                    │  - add_directory...  │
       │                    └──────────┬───────────┘
       │                               │
       │          ┌────────────────────┘
       │          │
       ▼          ▼
┌─────────────────────────────┐
│  Redis API (Port 17000)     │
│  - Store RAG embeddings     │
│  - Vector search            │
│  - Session-based storage    │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Redis (Port 26379)         │
│  - Key-value storage        │
│  - Context persistence      │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Transformer Service        │
│  - Generate embeddings      │
│  - paraphrase-mpnet-base-v2 │
└─────────────────────────────┘
```

## Usage

### Basic Syntax

```bash
# Add file to context
@path/to/file.py explain this file

# Add directory to context
@src/ what's the structure?

# Add entire working directory (special keyword)
@WD describe the entire project structure

# Create new file
@newfile.py create a hello world script

# Edit existing file
@existingfile.py add error handling
```

### Special Keywords

- **@WD**: Add entire working directory to context (recursive, all files)

### Autocomplete

1. Type `@` in the prompt
2. Press `TAB` to trigger autocomplete
3. Navigate files/directories:
   - **Files**: Shows as `filename.ext`
   - **Directories**: Shows as `dirname/`
4. Type partial name to filter
5. Press `ENTER` to select

### Example Autocomplete Session

```
▶ @<TAB>

Showing completions:
  src/               directory
  tests/             directory
  main.py            file
  config.yaml        file
  README.md          file

▶ @src/<TAB>

Showing completions:
  src/utils/         directory
  src/models/        directory
  src/services/      directory
  src/config.py      file
```

## File Context

### Adding Single File

```bash
▶ @models/user.py explain the User model
```

**What happens:**
1. File is read from disk
2. Content is sent to Transformer service for embedding
3. Embedding stored in Redis with file path as key
4. LLM receives context about the file
5. LLM explains the file with full understanding

### Adding Multiple Files

```bash
▶ @models/user.py @models/product.py create an Order model that references both
```

**What happens:**
1. Both files are read and embedded
2. Both contexts available to LLM
3. LLM generates code understanding relationships
4. New Order model created with proper imports

## Directory Context

### Adding Entire Directory

```bash
▶ @src/models/ describe all models in this directory
```

**What happens:**
1. **Directory tree is generated** - ASCII tree structure created
2. **Tree added to context** - Structure embedded for LLM understanding
3. Directory is recursively traversed
4. All files are read (excluding binary/hidden)
5. Each file is embedded separately
6. All embeddings stored with directory metadata
7. LLM has full directory context + structure

**Example Output:**
```
📁 Directory Structure Added: src/models/
  Files: 3 | Directories: 1
```

The LLM receives the tree structure like:
```
models/
├── __init__.py (150 B)
├── user.py (1.2 KB)
└── product.py (1.5 KB)
```

### Tree Structure Benefits

- **Visual Organization**: LLM sees file hierarchy
- **Size Information**: File sizes help LLM prioritize
- **Quick Navigation**: Easy to reference specific files
- **Structure Understanding**: Better architectural comprehension

### Example Use Cases

```bash
# Understand project structure
@src/ explain the architecture

# Add all utilities
@utils/ these functions are available

# Add test files for reference
@tests/ run similar tests for my new feature

# Entire working directory with tree
@WD provide a complete project overview
```

## Code Generation

### Creating New Files

When you reference a **non-existing file**, the LLM will generate code and **automatically write** it to that file:

```bash
▶ @calculator.py create a calculator class with add, subtract, multiply, divide
```

**Result:**
- `calculator.py` is created in working directory
- Contains complete Calculator class
- No manual file operations needed

### Language Detection

File extension determines the language:

```bash
@script.py   → Python code generated
@analysis.R  → R code generated
@script.r    → R code generated
```

### Editing Existing Files

When you reference an **existing file**, the LLM will modify it:

```bash
▶ @calculator.py add a power function
```

**Result:**
- Existing `calculator.py` is read
- LLM generates updated version with power function
- File is overwritten with new content
- Previous content integrated with changes

## Session Persistence

### Starting a Session

```bash
▶ session start
✓ Session started
Session ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Context Persistence

In an active session, all `@` prefixed contexts are stored with the session ID:

```bash
# Session active
▶ @models/ add to context
✓ Added 3 file(s) and 1 directory(ies) to context

# Later in same session
▶ create a service that uses the Product model
# LLM still has access to models/ context!
```

### Ending a Session

```bash
▶ session end
✓ Session ended
Duration: 15m 32s
Interactions: 12
```

**Note:** Context is cleared when session ends. Temporary contexts (no session) persist only for the current prompt.

## MCP Tools

### Tool: `write_python_code`

**Purpose:** Create a new Python file

**Parameters:**
- `file_path`: Path to file (relative to working directory)
- `code`: Python code to write
- `working_dir`: Optional working directory

**Example:**
```python
{
  "file_path": "script.py",
  "code": "def hello():\n    print('Hello')",
  "working_dir": "/home/user/project"
}
```

### Tool: `write_r_code`

**Purpose:** Create a new R file

**Parameters:**
- `file_path`: Path to file
- `code`: R code to write
- `working_dir`: Optional working directory

### Tool: `edit_python_code`

**Purpose:** Edit existing Python file

**Parameters:**
- `file_path`: Path to existing file
- `code`: New Python code (replaces entire content)
- `working_dir`: Optional working directory

### Tool: `edit_r_code`

**Purpose:** Edit existing R file

**Parameters:**
- `file_path`: Path to existing file
- `code`: New R code (replaces entire content)
- `working_dir`: Optional working directory

### Tool: `add_file_context`

**Purpose:** Add file to RAG context

**Parameters:**
- `file_path`: Path to file
- `session_id`: Optional session ID for persistence
- `working_dir`: Optional working directory

**Returns:**
```json
{
  "status": "success",
  "message": "Added file context: utils/helpers.py",
  "file_path": "utils/helpers.py",
  "content_size": 1234,
  "session_id": "a1b2c3d4..."
}
```

### Tool: `add_directory_context`

**Purpose:** Add all files in directory to RAG context

**Parameters:**
- `dir_path`: Path to directory
- `session_id`: Optional session ID for persistence
- `working_dir`: Optional working directory

**Returns:**
```json
{
  "status": "success",
  "message": "Added 5 files from directory: models/",
  "dir_path": "models/",
  "added_files": ["user.py", "product.py", ...],
  "errors": [],
  "session_id": "a1b2c3d4..."
}
```

## Examples

### Example 1: Quick File Explanation

```bash
▶ @src/utils/helpers.py what does this file do?

# File context added automatically
# LLM explains the helper functions
```

### Example 2: Create New Module

```bash
▶ @src/auth.py create an authentication module with login, logout, and token validation

# New file created at src/auth.py
# Contains complete authentication code
```

### Example 3: Refactor with Context

```bash
▶ @models/user.py @models/product.py refactor to use a common BaseModel

# Both files read and analyzed
# LLM suggests refactoring with base class
# User can then apply changes
```

### Example 4: Session-Based Development

```bash
▶ session start
✓ Session started

▶ @src/ add entire src to context
✓ Added 15 file(s) to context

▶ create a new service that follows the existing patterns
# LLM generates service consistent with codebase

▶ @tests/ add test files to context
✓ Added 8 file(s) to context

▶ create tests for the new service following existing test patterns
# LLM generates tests matching style

▶ session end
✓ Session ended
```

### Example 5: Data Analysis Workflow

```bash
▶ @data/sales.csv @analysis/utils.py create a comprehensive sales analysis script

# Both files added to context
# Analysis script generated with proper imports
# Uses utility functions from utils.py
```

### Example 6: Entire Project Context

```bash
▶ @WD provide a comprehensive overview of this project's architecture and main components

# Entire working directory added to context (recursively)
# LLM analyzes all files
# Provides detailed architecture overview
# Note: Use carefully with large projects!
```

## Technical Details

### File Reading

- **Encoding**: UTF-8
- **Security**: Path validation prevents directory traversal
- **Limits**: Working directory boundary enforcement
- **Hidden Files**: Excluded unless explicitly prefixed with `.`

### Directory Tree Generation

- **Format**: ASCII tree with box-drawing characters
- **Max Depth**: 10 levels (configurable)
- **File Sizes**: Human-readable (B, KB, MB, GB)
- **Exclusions**: `.git`, `__pycache__`, `node_modules`, `venv`, etc.
- **Statistics**: File count, directory count, total size
- **Storage**: Tree stored as special context entry `{path}/__TREE__`

**Tree Example:**
```
src/
├── models/
│   ├── __init__.py (150 B)
│   ├── user.py (1.2 KB)
│   └── product.py (1.5 KB)
├── services/
│   ├── __init__.py (200 B)
│   └── user_service.py (2.3 KB)
└── utils/
    └── helpers.py (850 B)
```

### Embeddings

- **Model**: sentence-transformers/paraphrase-mpnet-base-v2
- **Dimensions**: 768
- **Similarity**: Cosine similarity
- **Threshold**: 0.7 for context matching

### Redis Storage

**Key Format:**
```
session:{session_id}:context:{path}  # Session-specific
temp:context:{path}                   # Temporary (no session)
```

**Value Format:**
```json
{
  "context_type": "file" | "directory" | "directory_tree",
  "path": "relative/path/to/file",
  "content": "file contents or tree structure",
  "embedding": [0.1, 0.2, ...],
  "metadata": {
    "size": 1234,
    "timestamp": "2024-01-01T00:00:00"
  },
  "created_at": "2024-01-01T00:00:00"
}
```

**Context Types:**
- `file`: Individual file content
- `directory`: File within a directory context
- `directory_tree`: ASCII tree structure of directory (special entry)

### Context Lifecycle

1. **Temporary Context** (no session):
   - TTL: 1 hour
   - Scope: Current prompt only
   - Cleanup: Automatic expiration

2. **Session Context**:
   - TTL: Session duration
   - Scope: All prompts in session
   - Cleanup: Manual (session end) or expiration

### Performance

- **Autocomplete**: <50ms
- **File Read**: <100ms per file
- **Embedding**: ~200ms per file
- **Redis Storage**: <10ms

### Limitations

- **Max File Size**: No hard limit (practical: <1MB per file)
- **Max Files per Directory**: No hard limit (practical: <100)
- **Concurrent Sessions**: Unlimited
- **Redis Memory**: Depends on deployment

## Troubleshooting

### Autocomplete Not Working

**Issue**: TAB doesn't show completions

**Solutions:**
1. Ensure you typed `@` first
2. Check working directory is valid
3. Verify file permissions

### Context Not Added

**Issue**: "Failed to add file context"

**Solutions:**
1. Check file exists: `ls path/to/file`
2. Verify file permissions: readable
3. Check Redis service is running
4. Check Transformer service is running

### File Not Created

**Issue**: Generated code not written to file

**Solutions:**
1. Verify file path is within working directory
2. Check write permissions
3. Ensure parent directories exist
4. Check MCP coder service is running

### Session Context Lost

**Issue**: Context not persisting across prompts

**Solutions:**
1. Verify session is active: `session info`
2. Check Redis is running
3. Ensure session wasn't ended

## Best Practices

1. **Start Sessions for Long Work**: Use `session start` for multi-prompt workflows
2. **Use Directories for Broad Context**: `@src/` is better than multiple `@src/file1.py @src/file2.py`
3. **Be Specific with New Files**: `@specific_name.py` better than `@file.py`
4. **Clean Up Sessions**: Always `session end` when done
5. **Use Relative Paths**: Relative to working directory
6. **Combine Contexts Wisely**: Don't overload with too many files (stay under 10-15)

## Future Enhancements

- [ ] Support for more languages (JS, TS, Java, etc.)
- [ ] Git integration for file history
- [ ] Intelligent context pruning
- [ ] Multi-file diff generation
- [ ] Code review mode
- [ ] Automatic test generation
- [ ] Documentation generation
- [ ] Refactoring suggestions

## API Reference

See [MCP_TOOLS.md](MCP_TOOLS.md) for complete API reference.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

See [LICENSE](../LICENSE) for details.
