# Implementation Plan: Diff-Based Code Editing

## Problem Statement

The current `edit_python_code` and `edit_r_code` tools use full-file replacement. When the LLM generates only partial file content (e.g., 44 characters instead of the complete file), all existing code is lost. This plan implements diff-based editing using unified diff format to prevent data loss.

## Root Cause

- **Current behavior**: Tools replace entire file with LLM-generated code
- **Issue**: LLM sometimes ignores instructions to output complete file
- **Result**: File content is truncated/destroyed
- **Solution**: Use diff-based editing where LLM only generates changes, not entire files

## User Requirements

1. **Replace** existing edit_python_code/edit_r_code tools (not add new ones)
2. **Fail with error** if diff doesn't apply cleanly (don't modify file)
3. Use **unified diff format** (standard git-style diffs)
4. **Verify model**: User suspects qwen2.5-coder is being used (to be confirmed via `/model status`)

## Implementation Strategy

Convert the edit tools to accept and apply unified diffs while maintaining backward compatibility with full-file replacement as a fallback.

---

## Critical Files to Modify

1. **`src/utils/diff_parser.py`** (NEW FILE) - Core diff parsing/application logic
2. **`system_mcps/coder/server.py`** (lines 1001-1057) - Tool implementations
3. **`src/ui/routes/chat.py`** (lines 1699-1740) - UI LLM prompt generation
4. **`main.py`** (~lines 1232-1320) - CLI LLM prompt generation
5. **`tests/test_coder_mcp.py`** - Test suite

---

## Phase 1: Core Diff Parser Module

**Create**: `src/utils/diff_parser.py`

### Data Structure
```python
@dataclass
class DiffHunk:
    """Represents a single hunk in a unified diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    diff_lines: list[str]  # Lines with ' ', '+', '-' prefixes
```

### Key Functions

#### 1. `parse_unified_diff(diff_text: str) -> list[DiffHunk]`
- Parse unified diff format from LLM output
- Look for `---` and `+++` headers
- Parse `@@ -old_start,old_count +new_start,new_count @@` headers
- Extract diff lines for each hunk
- **Error handling**:
  - `InvalidDiffFormatError` - Missing headers or invalid format
  - `MissingHunkHeaderError` - Missing @@ markers
  - `MalformedDiffLineError` - Invalid line prefixes

#### 2. `validate_diff_hunks(original_content: str, diff_hunks: list[DiffHunk]) -> tuple[bool, str]`
- Verify all context lines match exactly
- Check line numbers are within file bounds
- Ensure no overlapping hunks
- Verify hunks are in order
- **Returns**: `(is_valid: bool, error_message: str)`

#### 3. `apply_diff_to_file(file_path: str, diff_hunks: list[DiffHunk], working_dir: str) -> tuple[bool, str]`
- Read original file
- Validate hunks match file content
- Apply each hunk (additions/deletions)
- **Atomic write**: Write to temp file first, then rename
- **Rollback**: Preserve original file on any failure
- **Returns**: `(success: bool, message: str)`

#### 4. `detect_diff_format(code_text: str) -> bool`
- Detect if input is a diff or full file
- Check for `---`, `+++`, and `@@` markers
- Used for backward compatibility

---

## Phase 2: Update Tool Implementations

**Modify**: `system_mcps/coder/server.py`

### Changes to `edit_python_code` (lines 1001-1028) and `edit_r_code` (lines 1030-1057)

**New Flow**:
```python
# Import diff_parser at top
from src.utils.diff_parser import (
    parse_unified_diff, validate_diff_hunks,
    apply_diff_to_file, detect_diff_format,
    InvalidDiffFormatError, MissingHunkHeaderError, MalformedDiffLineError
)

# In edit_python_code/edit_r_code:
# 1. Validate working_dir (unchanged)
# 2. Check file exists (unchanged)
# 3. Read original file content
# 4. Detect format and apply:

if detect_diff_format(code):
    # Diff-based path
    try:
        diff_hunks = parse_unified_diff(code)

        # Validate before applying
        is_valid, error_msg = validate_diff_hunks(original_content, diff_hunks)
        if not is_valid:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Invalid diff: {error_msg}",
                "file_path": file_path,
                "diff_applied": False
            }, indent=2))]

        # Apply diff
        success, message = apply_diff_to_file(file_path, diff_hunks, working_dir)
        if not success:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Failed to apply diff: {message}",
                "file_path": file_path,
                "diff_applied": False
            }, indent=2))]

        return [TextContent(type="text", text=json.dumps({
            "status": "success",
            "message": message,
            "file_path": file_path,
            "diff_applied": True,
            "hunks_applied": len(diff_hunks)
        }, indent=2))]

    except (InvalidDiffFormatError, MissingHunkHeaderError, MalformedDiffLineError) as e:
        return [TextContent(type="text", text=json.dumps({
            "status": "error",
            "message": f"Diff parsing error: {str(e)}",
            "file_path": file_path,
            "diff_applied": False
        }, indent=2))]
else:
    # Fallback to full-file replacement (backward compatibility)
    success, message = write_file_safe(file_path, code, working_dir)
    return [TextContent(type="text", text=json.dumps({
        "status": "success" if success else "error",
        "message": message,
        "file_path": file_path,
        "diff_applied": False  # Indicates fallback mode
    }, indent=2))]
```

**Optimization**: Extract common logic into helper function `_edit_code_file()` to avoid duplication between Python and R tools.

---

## Phase 3: Update LLM Prompts

### Update: `src/ui/routes/chat.py::_generate_code_with_llm_sync()` (lines 1699-1740)

**New Prompt Template for Edit Operations**:

```python
llm_prompt = f"""You are a code editor that generates UNIFIED DIFFS for file modifications.

FILE TO EDIT: {file_path} ({line_count} lines)

=== ORIGINAL FILE START ===
{original_file_content}
=== ORIGINAL FILE END ===

REQUESTED CHANGES: {step}

CRITICAL RULES:
1. Generate a UNIFIED DIFF showing ONLY the changes
2. Use standard unified diff format:
   --- {file_path}
   +++ {file_path}
   @@ -old_start,old_count +new_start,new_count @@
3. Include 3 lines of context before and after each change
4. Context lines start with ' ' (space)
5. Deleted lines start with '-' (minus)
6. Added lines start with '+' (plus)
7. DO NOT include the entire file - only changed sections with context
8. DO NOT add explanatory text before or after the diff
9. ONLY output the diff block - nothing else

EXAMPLE FORMAT:
```diff
--- src/example.{code_block_marker}
+++ src/example.{code_block_marker}
@@ -10,7 +10,7 @@
 def existing_function():
     # Some context
     old_line = 123
-    line_to_change = "old value"
+    line_to_change = "new value"
     another_line = 456
     # More context

@@ -25,6 +25,9 @@
 def another_function():
     # Context before
     existing_code = True
+    # New lines being added
+    new_feature = "added"
+    more_code = 123
     # Context after
```

Start your response with the ```diff marker immediately. No text before the diff block."""
```

### Update: `main.py` (similar section around lines 1232-1320)

Apply the same prompt template changes to CLI code generation flow.

---

## Phase 4: Testing Strategy

**Add to**: `tests/test_coder_mcp.py`

### Test Cases

1. **`test_edit_python_code_with_valid_diff`**
   - Create temp file with known content
   - Generate valid unified diff changing specific lines
   - Verify file modified correctly, only targeted lines changed
   - Check response: `diff_applied=true`

2. **`test_edit_python_code_with_invalid_diff_context`**
   - Generate diff with context lines that don't match original
   - Verify file UNCHANGED
   - Check error response with clear message

3. **`test_edit_python_code_with_malformed_diff`**
   - Test missing @@ headers, invalid line prefixes, missing markers
   - Verify error response, file unchanged

4. **`test_edit_python_code_with_full_file_fallback`**
   - Pass complete file content (not diff)
   - Verify fallback to full-file replacement
   - Check response: `diff_applied=false`

5. **`test_edit_python_code_with_multiple_hunks`**
   - Generate diff with 3+ hunks
   - Verify all hunks applied correctly
   - Check response: `hunks_applied=3`

6. **`test_edit_r_code_with_valid_diff`**
   - Same as test 1 but for R files

7. **Unit tests for `diff_parser.py`**:
   - `test_parse_unified_diff_valid`
   - `test_parse_unified_diff_invalid_format`
   - `test_validate_diff_hunks_context_mismatch`
   - `test_validate_diff_hunks_overlapping`
   - `test_apply_diff_to_file_rollback_on_failure`

---

## Phase 5: Implementation Steps

### Step 1: Create Diff Parser (Est: 2-3 hours)
1. Create `src/utils/diff_parser.py`
2. Implement `DiffHunk` dataclass
3. Implement `parse_unified_diff()` with error handling
4. Implement `validate_diff_hunks()`
5. Implement `apply_diff_to_file()` with atomic writes
6. Implement `detect_diff_format()`
7. Add comprehensive unit tests

**Validation**: All parser unit tests pass

### Step 2: Update Tool Implementations (Est: 1-2 hours)
1. Import diff_parser in `system_mcps/coder/server.py`
2. Modify `edit_python_code` to use diff path
3. Modify `edit_r_code` to use diff path
4. Extract common logic to helper function
5. Update error/success response formats

**Validation**: Manual testing with mock diffs

### Step 3: Update LLM Prompts (Est: 1-2 hours)
1. Update `src/ui/routes/chat.py::_generate_code_with_llm_sync()`
2. Update `main.py` (similar function)
3. Test with actual LLM (qwen2.5-coder or configured coder model)
4. Verify LLM generates valid diffs
5. Add fallback logic for invalid diffs

**Validation**: LLM generates parseable diffs in test runs

### Step 4: Integration Testing (Est: 2-3 hours)
1. Add all test cases to `tests/test_coder_mcp.py`
2. Test through MCP protocol (JSON-RPC)
3. Test both Python and R file editing
4. Test failure scenarios
5. Test backward compatibility

**Validation**: All tests pass, no regressions

### Step 5: Documentation (Est: 1 hour)
1. Update `system_mcps/coder/tools.yaml` (tool descriptions)
2. Add code comments explaining diff vs full-file modes
3. Document error codes and messages

---

## Edge Cases & Considerations

1. **LLM generates partial/invalid diff**
   - Validate completeness before applying
   - Return clear error if incomplete
   - Fall back to full-file mode if needed

2. **File modified between read and write**
   - Use atomic writes (temp file + rename)
   - File modification time checks (future enhancement)

3. **Whitespace differences**
   - Strict matching (no fuzzy matching)
   - Preserve exact whitespace in context

4. **Line ending differences** (CRLF vs LF)
   - Detect and preserve original file's line endings

5. **Large files** (>10k lines)
   - Set reasonable limits, warn if file too large
   - Consider memory-efficient approach if needed

6. **Unicode/encoding issues**
   - Use UTF-8 by default
   - Handle encoding errors gracefully

---

## Rollback Strategy

1. **Immediate Fallback**:
   - If diff format invalid, automatically fall back to full-file replacement
   - No breaking changes

2. **Environment Variable Override**:
   - Add `DISABLE_DIFF_MODE=true` to force full-file mode if needed

3. **Complete Revert**:
   - All changes are additive (new functions)
   - Can disable diff path entirely if needed
   - Existing full-file path remains functional

---

## Success Criteria

1. ✅ Diff parsing works for standard unified diff format
2. ✅ Invalid diffs are rejected without modifying files
3. ✅ Full-file replacement still works (backward compatibility)
4. ✅ LLM generates valid diffs 90%+ of the time
5. ✅ All existing tests pass
6. ✅ New diff-based tests pass
7. ✅ No data loss scenarios (files protected on failure)

---

## Dependencies

- **stdlib only**: Use Python's `difflib` module (no external dependencies)
- **No breaking changes**: Maintain existing tool interface
- **Backward compatible**: Full-file replacement remains available

---

## Estimated Timeline

- **Phase 1 (Diff Parser)**: 2-3 hours
- **Phase 2 (Tool Integration)**: 1-2 hours
- **Phase 3 (LLM Prompts)**: 1-2 hours
- **Phase 4 (Testing)**: 2-3 hours
- **Phase 5 (Documentation)**: 1 hour

**Total**: ~8-11 hours of focused development

---

## Next Steps After Implementation

1. **Monitor LLM diff generation success rate**
   - Track how often LLM generates valid diffs
   - Identify patterns in failures
   - Refine prompts if needed

2. **Verify model configuration**
   - Run `/model status` to confirm which coder model is active
   - If using tinyllama, consider upgrading to qwen2.5-coder for better diff generation

3. **Collect user feedback**
   - Monitor for diff application failures
   - Track fallback frequency
   - Adjust validation strictness if needed
