# Tool Discovery Flow Diagram

## Before Fix: Hardcoded Tool List ❌

```
User Request: "Generate fake data from @users.csv using WGAN"
     |
     v
┌────────────────────────────────────────────────────────┐
│  code-command-simple endpoint                          │
│                                                        │
│  HARDCODED LIST:                                      │
│  1. add_file_context                                  │
│  2. edit_python_code                                  │
│  3. write_python_code                                 │
│  4. run_python_code                                   │
│  5. run_r_code                                        │
│  6. write_r_code                                      │
│  7. edit_r_code                                       │
│  8. add_directory_context                            │
│  9. verify_file_modifications                        │
│                                                        │
│  (Data-engineer tools NOT included)                  │
└────────────────────────────────────────────────────────┘
     |
     v
LLM Prompt: "Use ONLY these 9 tools"
     |
     v
LLM Response: "I'll write custom WGAN code..."
     |
     v
Result: 100+ lines of generated Python code ❌
```

## After Fix: Dynamic Discovery ✅

```
User Request: "Generate fake data from @users.csv using WGAN"
     |
     v
┌────────────────────────────────────────────────────────┐
│  code-command-simple endpoint                          │
│                                                        │
│  Step 1: Load from tools.yaml                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │ system_mcps/                                      │ │
│  │   ├─ coder/tools.yaml                            │ │
│  │   │   • run_python_code                          │ │
│  │   │   • write_python_code                        │ │
│  │   │   • edit_python_code                         │ │
│  │   │   • add_file_context                         │ │
│  │   │   • ... (meta tools excluded by category)    │ │
│  │   │                                               │ │
│  │   └─ data-engineer/tools.yaml                    │ │
│  │       • generate_fake_data ← FOUND!              │ │
│  │       • generate_fake_data_ctgan                  │ │
│  │       • generate_ast                             │ │
│  │       • compare_code_similarity                  │ │
│  │       • compare_ast_similarity                   │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Step 2: Combine with Database descriptions           │
│  Step 3: Filter meta tools by category                │
│  Step 4: Build dynamic tool list                      │
│                                                        │
│  RESULT: 20 tools available                           │
└────────────────────────────────────────────────────────┘
     |
     v
LLM Prompt: "Use ONLY these 20 tools (including generate_fake_data)"
     |
     v
LLM Response: "Generate synthetic data from users.csv 
               using generate_fake_data tool"
     |
     v
Result: Uses existing tested MCP tool ✅
```

## Key Components

### 1. get_all_tools_metadata()

```python
system_mcps/
├── coder/
│   └── tools.yaml
│       categories:
│         code_generation: [write_python_code, ...]
│         valid_coding: [run_python_code, ...]
│         meta: [spin_the_roulette, ...]  ← Excluded
│       tools:
│         run_python_code:
│           requires_file_path: true
│           description: "Execute Python code"
│
└── data-engineer/
    └── tools.yaml
        categories:
          data_generation: [generate_fake_data, ...]
          code_analysis: [generate_ast, ...]
        tools:
          generate_fake_data:
            requires_file_path: true
            uses_ml_model: true
            description: "Generate synthetic data using WGAN"
```

### 2. Tool Loading Process

```
┌─────────────────────────────────────────────────────┐
│ get_all_tools_metadata_cached()                     │
│                                                     │
│ For each MCP directory:                            │
│   1. Load tools.yaml                               │
│   2. Extract categories                            │
│   3. Extract tool metadata                         │
│   4. Build tool-to-categories mapping              │
│   5. Store in cache                                │
│                                                     │
│ Returns: {                                         │
│   'generate_fake_data': {                          │
│     'mcp_name': 'data-engineer',                   │
│     'categories': ['data_generation', ...],        │
│     'metadata': {...},                             │
│     'description': '...'                           │
│   },                                               │
│   ...                                              │
│ }                                                  │
└─────────────────────────────────────────────────────┘
```

### 3. Meta Tool Filtering

```
┌────────────────────────────────────────────────────┐
│ Filter Meta Tools                                  │
│                                                    │
│ For each tool:                                     │
│   if 'meta' in tool.categories:                   │
│     exclude from /code mode                        │
│                                                    │
│ Excluded:                                          │
│   • spin_the_roulette  (orchestration)            │
│   • retrieve_all_tools (meta)                     │
│   • roll_the_dice      (meta)                     │
│   • execute_plan       (orchestration)            │
│                                                    │
│ Included:                                          │
│   • generate_fake_data      (data_generation)     │
│   • run_python_code         (execution)           │
│   • write_python_code       (file_write)          │
│   • compare_code_similarity (code_analysis)       │
└────────────────────────────────────────────────────┘
```

## Benefits of Dynamic Discovery

### Extensibility
```
Add new MCP server:
  system_mcps/new-mcp/
    └── tools.yaml

Result: Tools automatically discovered ✅
No code changes needed ✅
```

### Maintainability
```
Before: Update hardcoded list in code
After:  Update tools.yaml file
```

### Correctness
```
Before: LLM writes custom code (may have bugs)
After:  LLM uses tested MCP tools (reliable)
```

## Testing Flow

```
┌─────────────────────────────────────────────────────┐
│ Test: test_get_all_tools_metadata()                 │
│                                                     │
│ 1. Load tools from system_mcps/                    │
│ 2. Verify coder tools found                        │
│ 3. Verify data-engineer tools found                │
│ 4. Verify meta tools identified                    │
│ 5. Verify tool metadata structure                  │
│                                                     │
│ Result: ✅ All tools discovered correctly           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Manual Verification                                 │
│                                                     │
│ Run: python /tmp/test_tool_discovery.py            │
│                                                     │
│ Output:                                             │
│   Total tools: 20                                   │
│   Data-engineer: 5/5 ✓                             │
│   Coder: 4/4 ✓                                     │
│   Meta filtered: 4 ✓                               │
│                                                     │
│ Result: ✅ Discovery working as expected            │
└─────────────────────────────────────────────────────┘
```

## Summary

**Problem**: Hardcoded 9-tool list → Data-engineer tools invisible  
**Solution**: Dynamic loading from tools.yaml → All 20+ tools visible  
**Result**: LLM uses existing tools instead of writing custom code  

The fix transforms the system from static to dynamic, making it:
- ✅ Extensible (new MCPs auto-discovered)
- ✅ Maintainable (no hardcoded lists)
- ✅ Correct (uses tested tools)
- ✅ Efficient (faster responses)
