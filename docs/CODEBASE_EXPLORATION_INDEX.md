# Codebase Exploration Index

This document provides a comprehensive index of all exploration documents created during the codebase analysis.

## Documentation Files Created

### 1. **CODEBASE_EXPLORATION_SUMMARY.md** (10 sections, 500+ lines)
   **Location**: `/home/user/cli/docs/CODEBASE_EXPLORATION_SUMMARY.md`
   
   **Contents**:
   - System Overview & Architecture Diagram
   - Complete MCP Tools Implementation Guide (retrieve_all_tools, roll_the_dice, others)
   - All API Endpoints & Structures (endpoints, request/response formats, database schema)
   - LLM Tool Interaction Flow
   - Complete Testing Structure
   - retrieve_all_tools Expected Format (input/output examples)
   - Key Files & Directory Structure
   - Debug Mode Instructions
   - Modification Points for New Features
   - Code Patterns & Best Practices

   **Best For**: Understanding the overall architecture and how everything fits together

### 2. **QUICK_CODE_REFERENCE.md** (12 sections, 400+ lines)
   **Location**: `/home/user/cli/docs/QUICK_CODE_REFERENCE.md`
   
   **Contents**:
   - File Locations & Line Numbers (quick lookup table)
   - Critical Code Patterns (6 reusable patterns with examples)
   - Important Constants & Configurations
   - Retrieve Endpoint Response Parsing Guide
   - Roll the Dice Execution Flow (step-by-step)
   - Environment Variables
   - Common Errors & Solutions Troubleshooting Table
   - Quick Testing Commands
   - Implementation Checklist

   **Best For**: Quick lookups, code references, and common tasks

### 3. **EXPLORATION_SUMMARY.txt** (Quick reference)
   **Location**: `/home/user/cli/docs/EXPLORATION_SUMMARY.txt`
   
   **Contents**:
   - Overview of created documents
   - 10 Key Findings (summarized)
   - Quick Reference Section
   - Next Steps for Development

   **Best For**: Quick overview and navigation

---

## Quick Navigation by Task

### I Want To...

#### Understand the Architecture
- Start with: **CODEBASE_EXPLORATION_SUMMARY.md** Section 1-4
- Then read: **CODEBASE_EXPLORATION_SUMMARY.md** Section 8 (Testing Structure)

#### Implement a New MCP Tool
- Reference: **QUICK_CODE_REFERENCE.md** Pattern 1-2
- Check line numbers: **QUICK_CODE_REFERENCE.md** "File Locations & Line Numbers"
- Follow: **QUICK_CODE_REFERENCE.md** Implementation Checklist
- Read: **CODEBASE_EXPLORATION_SUMMARY.md** Section 9

#### Add a New API Endpoint
- Reference: **QUICK_CODE_REFERENCE.md** Pattern 4
- Check existing endpoints: **CODEBASE_EXPLORATION_SUMMARY.md** Section 3
- Line numbers: **QUICK_CODE_REFERENCE.md** "PostgreSQL API Endpoints"

#### Write Tests for New Features
- Pattern examples: **QUICK_CODE_REFERENCE.md** Pattern 6
- Testing structure: **CODEBASE_EXPLORATION_SUMMARY.md** Section 5
- Commands: **QUICK_CODE_REFERENCE.md** "Quick Testing Commands"

#### Debug Tool Execution Issues
- Common errors: **QUICK_CODE_REFERENCE.md** "Common Errors & Solutions"
- Debug mode: **CODEBASE_EXPLORATION_SUMMARY.md** Section 8
- Enable: `export MCP_DEBUG=true`

#### Understand retrieve_all_tools
- Implementation: **CODEBASE_EXPLORATION_SUMMARY.md** Section 2.1
- Format: **CODEBASE_EXPLORATION_SUMMARY.md** Section 6
- Code reference: **QUICK_CODE_REFERENCE.md** "File Locations & Line Numbers"
- Line 1084-1137: `/home/user/cli/system_mcps/coder/server.py`

#### Understand roll_the_dice
- Implementation: **CODEBASE_EXPLORATION_SUMMARY.md** Section 2.2
- Execution flow: **QUICK_CODE_REFERENCE.md** "Roll the Dice Execution Flow"
- Code reference: **QUICK_CODE_REFERENCE.md** "File Locations & Line Numbers"
- Line 1139-1385: `/home/user/cli/system_mcps/coder/server.py`

---

## Key Files Reference Table

| File | Lines | Purpose | Documentation |
|------|-------|---------|----------------|
| `/home/user/cli/system_mcps/coder/server.py` | 1404 | All MCP tool implementations | QUICK_CODE_REFERENCE.md (Table 1) |
| `/home/user/cli/src/postgresql/app/app.py` | 750 | All API endpoints | QUICK_CODE_REFERENCE.md (Table 2) |
| `/home/user/cli/src/mcp/client.py` | 356 | MCP client manager | QUICK_CODE_REFERENCE.md (Table 3) |
| `/home/user/cli/src/transformer/app.py` | ~200 | Embedding service | CODEBASE_EXPLORATION_SUMMARY.md Section 3.2 |
| `/home/user/cli/main.py` | ~800 | CLI entry point | CODEBASE_EXPLORATION_SUMMARY.md Section 1.3 |
| `/home/user/cli/tests/test_coder_mcp.py` | 22KB | MCP unit tests | CODEBASE_EXPLORATION_SUMMARY.md Section 5.1 |
| `/home/user/cli/tests/test_mcp_postgres.py` | 9KB | API integration tests | CODEBASE_EXPLORATION_SUMMARY.md Section 5.1 |
| `/home/user/cli/tests/test_tool_retrieval.py` | 18KB | Retrieval endpoint tests | CODEBASE_EXPLORATION_SUMMARY.md Section 5.1 |

---

## Service Architecture Overview

```
┌─────────────────────────────────────┐
│  AI CLI (main.py)                   │
│  Entry Point & Interactive Interface│
└────────────────┬────────────────────┘
                 │
     ┌───────────┼───────────┐
     │           │           │
     ▼           ▼           ▼
  Ollama      Flask API   Transformer
 (11434)     (15000)       (16050)
     │           │           │
     └───────────┼───────────┘
                 │
            PostgreSQL
            Database
            (25432)
```

**Services**:
- **Ollama** (11434): LLM inference (chat)
- **PostgreSQL Flask API** (15000): Tool storage, retrieval, matching
- **Transformer Service** (16050): Text embeddings (384-dim vectors)
- **PostgreSQL** (35432): Data persistence

---

## Tool Implementation Overview

### 11 Available Tools

**Code Execution** (3):
- `run_python_code` - Execute Python in CLI's venv
- `run_r_code` - Execute R code
- `detect_code` - Extract code from text

**File Operations** (4):
- `write_python_code` - Create new Python file
- `write_r_code` - Create new R file
- `edit_python_code` - Modify Python file
- `edit_r_code` - Modify R file

**Context Management** (2):
- `add_file_context` - Add file to RAG context
- `add_directory_context` - Add all files in directory

**Special Tools** (2):
- `retrieve_all_tools` - **Find relevant tools via semantic search**
- `roll_the_dice` - **Execute multiple tools iteratively**

**Verification** (1):
- `verify_file_modifications` - Run modified files

---

## retrieve_all_tools vs roll_the_dice

| Aspect | retrieve_all_tools | roll_the_dice |
|--------|-------------------|---------------|
| **Purpose** | Find relevant tools | Execute tools |
| **Input** | List of prompts | Prompts + session_id |
| **Session Required** | No | YES (mandatory) |
| **Output** | Matching tools with scores | Execution results |
| **Executes Tools** | No | YES (iterative) |
| **Location** | Lines 1084-1137 | Lines 1139-1385 |

---

## API Endpoint Summary

### Tool Storage & Retrieval

| Endpoint | Method | Purpose | Input | Output |
|----------|--------|---------|-------|--------|
| `/mcp-tools/store` | POST | Store tool with embedding | mcp_name, tool_name, description | {status, message} |
| `/mcp-tools` | GET | List all tools | - | {status, count, tools[]} |
| `/mcp-tools/match` | POST | Single text matching | text, threshold | {status, best_match, matches[]} |
| `/mcp-tools/retrieve` | POST | Multi-prompt retrieval | prompts[], threshold | {status, count, results[]} |

---

## Database Schema

### mcp_tools Table

```python
id              Integer, Primary Key
mcp_name        Text        # "coder", "analyzer"
tool_name       Text        # "run_python_code"
description     Text        # Full description for embedding
embedding       JSON        # 384-dimensional vector
created_at      DateTime
updated_at      DateTime
```

---

## Important Constants

| Constant | Value | Usage |
|----------|-------|-------|
| Embedding Model | `all-MiniLM-L6-v2` | Sentence Transformers |
| Embedding Dimension | 384 | Vector size |
| Default Threshold | 0.5 | Similarity matching |
| Max roll_the_dice Tools | 10 | Maximum executable tools |
| Default roll_the_dice Tools | 3 | Default max_tools |
| Similarity Range | 0.0 to 1.0 | Cosine similarity score |

---

## Testing Commands Quick Reference

```bash
# Run all MCP tests
pytest tests/test_coder_mcp.py -v

# Run specific test
pytest tests/test_coder_mcp.py::TestCoderMCP::test_retrieve_all_tools -v

# With debug output
MCP_DEBUG=true pytest tests/test_coder_mcp.py -v -s

# Test API endpoints
pytest tests/test_mcp_postgres.py -v

# Test retrieval
pytest tests/test_tool_retrieval.py -v

# Test specific endpoint directly
curl -X POST http://localhost:15000/mcp-tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{"prompts": ["Run Python code"]}'
```

---

## Common Patterns to Copy

### Adding a New Tool

1. In `system_mcps/coder/server.py`, add to `list_tools()`:
   ```python
   Tool(
       name="new_tool",
       description="What it does...",
       inputSchema={...}
   )
   ```

2. Add handler in `call_tool()`:
   ```python
   elif name == "new_tool":
       param = arguments.get("param")
       # Validate, implement, return JSON
       return [TextContent(type="text", text=json.dumps(...))]
   ```

3. Add test:
   ```python
   @pytest.mark.asyncio
   async def test_new_tool(self, server_path):
       # Test implementation
   ```

### Adding a New Endpoint

1. In `src/postgresql/app/app.py`:
   ```python
   @app.route('/api/new-endpoint', methods=['POST'])
   def new_endpoint():
       data = request.get_json()
       # Process data
       return jsonify({'status': 'success', 'data': result}), 200
   ```

2. Add test:
   ```python
   @requires_both_services
   def test_new_endpoint(self):
       response = requests.post(...)
       assert response.status_code == 200
   ```

---

## Troubleshooting Guide

**Problem**: "No prompts provided"
- **Cause**: Empty prompts array
- **Solution**: Ensure `prompts` is non-empty list

**Problem**: "session_id is required"
- **Cause**: Missing session_id in roll_the_dice
- **Solution**: Always provide session_id parameter

**Problem**: "Failed to generate embedding"
- **Cause**: Transformer service not running
- **Solution**: Run `make up-transformer`

**Problem**: Connection refused to PostgreSQL
- **Cause**: Service not running
- **Solution**: Run `make up-postgres`

**Problem**: 30-second timeout
- **Cause**: Service is slow or down
- **Solution**: Check service health with curl

---

## Next Steps

1. **Review the documentation**:
   - Start with CODEBASE_EXPLORATION_SUMMARY.md (sections 1-4)
   - Then review QUICK_CODE_REFERENCE.md for specific tasks

2. **Understand the tools**:
   - Read about retrieve_all_tools (Section 2.1, lines 1084-1137)
   - Read about roll_the_dice (Section 2.2, lines 1139-1385)

3. **Explore test patterns**:
   - Look at tests/test_coder_mcp.py
   - Look at tests/test_mcp_postgres.py

4. **Try running commands**:
   - Enable debug: `export MCP_DEBUG=true`
   - Test endpoints with curl
   - Run tests with pytest

5. **Start development**:
   - Use QUICK_CODE_REFERENCE.md for code patterns
   - Follow the Implementation Checklist
   - Reference existing code for patterns

---

## Document Statistics

| Document | Lines | Size | Created |
|----------|-------|------|---------|
| CODEBASE_EXPLORATION_SUMMARY.md | 500+ | 15KB | 2025-01-21 |
| QUICK_CODE_REFERENCE.md | 400+ | 12KB | 2025-01-21 |
| EXPLORATION_SUMMARY.txt | 200+ | 7KB | 2025-01-21 |
| CODEBASE_EXPLORATION_INDEX.md | This file | - | 2025-01-21 |

---

**Created**: 2025-01-21
**Repository**: AI CLI with MCP Tools
**Status**: Complete
