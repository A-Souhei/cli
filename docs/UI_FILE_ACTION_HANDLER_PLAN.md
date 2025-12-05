# Implementation Plan: Unified File Action Handler for CLI and UI

## Problem Statement

Currently, the CLI (`main.py`) has action keyword detection and automatic MCP tool usage when users reference files with `@` prefix, but the Web UI (`src/ui/routes/chat.py`) lacks this functionality. This leads to inconsistent behavior:

- **CLI**: `import @utils/helpers.py validate_email into @services/user_service.py` → Automatically uses `edit_python_code` tool ✅
- **UI**: Same prompt → LLM only provides explanations, doesn't modify files ❌

## Solution: Extract Shared Logic

Create a unified file action handler that both CLI and UI can use, eliminating code duplication and ensuring consistent behavior across interfaces.

---

## Architecture

### New Module: `src/utils/file_action_handler.py`

**Purpose**: Centralized logic for detecting file modification requests and generating appropriate system instructions.

**Key Functions**:

1. `detect_file_actions(user_input: str, at_context: dict, config: ConfigManager) -> dict`
   - Detects action keywords from config
   - Identifies files to modify/create from `@` prefix
   - Returns action metadata

2. `generate_file_modification_instructions(files_to_modify: list, files_to_create: list) -> str`
   - Generates system message instructing LLM to use `file: <path>` format
   - Includes examples and anti-patterns
   - Returns formatted instruction string

3. `build_system_messages(at_context: dict, user_input: str, config: ConfigManager, **kwargs) -> list`
   - Orchestrates all system message generation
   - Combines file context, action instructions, session context, etc.
   - Returns list of system messages to inject

---

## Implementation Steps

### Step 1: Create the Shared Module

**File**: `src/utils/file_action_handler.py`

```python
"""
Shared file action detection and instruction generation.
Used by both CLI and UI to provide consistent file modification behavior.
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import re


def detect_file_actions(
    user_input: str,
    at_context: Dict[str, Any],
    config: 'ConfigManager'
) -> Dict[str, Any]:
    """
    Detect if user input contains file modification actions.

    Args:
        user_input: User's message
        at_context: Dict with 'files' and 'non_existing' lists
        config: ConfigManager instance

    Returns:
        Dict with:
            - has_action: bool
            - action_keywords_found: list
            - files_to_modify: list
            - files_to_create: list
    """
    action_keywords = config.get_file_action_keywords()
    user_input_lower = user_input.lower()

    found_keywords = [kw for kw in action_keywords if kw in user_input_lower]
    has_action = len(found_keywords) > 0

    # Collect files
    all_files_to_modify = list(at_context.get('files', []))
    all_files_to_create = list(at_context.get('non_existing', []))

    # Look for additional files mentioned in create patterns
    if 'create' in user_input_lower:
        create_pattern = r'create\s+((?:[\w/]+/)?[\w.]+\.(?:py|r|R))'
        create_matches = re.findall(create_pattern, user_input_lower)
        for matched_file in create_matches:
            if matched_file not in all_files_to_create and matched_file not in all_files_to_modify:
                all_files_to_create.append(matched_file)

    return {
        'has_action': has_action,
        'action_keywords_found': found_keywords,
        'files_to_modify': all_files_to_modify,
        'files_to_create': all_files_to_create
    }


def generate_file_modification_instructions(
    files_to_modify: List[str],
    files_to_create: List[str]
) -> str:
    """
    Generate system instructions for file modifications.

    Args:
        files_to_modify: List of existing files to modify
        files_to_create: List of new files to create

    Returns:
        Formatted instruction string
    """
    instruction_parts = []

    if files_to_modify:
        instruction_parts.append(
            f"The user wants to MODIFY these existing files: {', '.join(files_to_modify)}"
        )

    if files_to_create:
        instruction_parts.append(
            f"The user wants to CREATE these new files: {', '.join(files_to_create)}"
        )

    if not instruction_parts:
        return ""

    format_instruction = """
IMPORTANT: For EACH file you need to create or modify, you MUST use this EXACT format:

file: <full_file_path>
```python
<complete file code here>
```

Example:
file: testing/python_app/models/base.py
```python
class BaseModel:
    pass
```

file: testing/python_app/models/user.py
```python
from .base import BaseModel

class User(BaseModel):
    pass
```

Do NOT just explain the changes - provide the COMPLETE, RUNNABLE code for each file in the format above.
Each file should have its own "file: <path>" line followed by a code block.

VERIFICATION: After modifications, one of the files will be executed to verify the changes work correctly.
Ensure all imports are correct, syntax is valid, and the code runs without errors.
"""

    return "\n".join(instruction_parts) + format_instruction


def generate_file_context_message(
    injected_context_parts: List[str]
) -> Optional[Dict[str, str]]:
    """
    Generate system message for file/directory context.

    Args:
        injected_context_parts: List of formatted file/dir contents

    Returns:
        System message dict or None if no context
    """
    if not injected_context_parts:
        return None

    context_content = "\n\n".join(injected_context_parts)
    return {
        'role': 'system',
        'content': f"The user has provided the following files/directories as context:\n\n{context_content}"
    }


def generate_target_file_message(
    target_file: str
) -> Optional[Dict[str, str]]:
    """
    Generate system message for target file writing.

    Args:
        target_file: Path to target file

    Returns:
        System message dict or None
    """
    if not target_file:
        return None

    import os
    file_ext = os.path.splitext(target_file)[1]
    lang = "Python" if file_ext == ".py" else "R" if file_ext in [".R", ".r"] else "appropriate"

    return {
        'role': 'system',
        'content': (
            f"The user wants to write code to the file: {target_file}. "
            f"Generate {lang} code in a code block that will be automatically written to this file. "
            "Provide complete, working code that can be directly written to the file."
        )
    }


def generate_execution_message(
    user_input: str
) -> Optional[Dict[str, str]]:
    """
    Generate system message for code execution.

    Args:
        user_input: User's message

    Returns:
        System message dict or None
    """
    run_keywords = ['run', 'execute', 'exec']
    if not any(keyword in user_input.lower() for keyword in run_keywords):
        return None

    return {
        'role': 'system',
        'content': (
            "The user wants to execute code. Provide ONLY the code in a code block. "
            "Do NOT predict, guess, or show what the output will be. "
            "The code will be automatically executed and the real output will be displayed to the user."
        )
    }


def build_system_messages(
    at_context: Dict[str, Any],
    user_input: str,
    config: 'ConfigManager',
    injected_context_parts: List[str] = None,
    target_file: str = None,
    session_context: str = None,
    guidance: str = None
) -> List[Dict[str, str]]:
    """
    Build all system messages to inject before user's message.

    Args:
        at_context: Dict with 'files' and 'non_existing' lists
        user_input: User's message
        config: ConfigManager instance
        injected_context_parts: File/dir contents to inject
        target_file: Optional target file for writing
        session_context: Optional session context
        guidance: Optional prompt guidance

    Returns:
        List of system messages to inject
    """
    system_messages = []

    # 1. File/directory context
    if injected_context_parts:
        msg = generate_file_context_message(injected_context_parts)
        if msg:
            system_messages.append(msg)

    # 2. File modification instructions
    action_result = detect_file_actions(user_input, at_context, config)
    if action_result['has_action'] and (action_result['files_to_modify'] or action_result['files_to_create']):
        instruction = generate_file_modification_instructions(
            action_result['files_to_modify'],
            action_result['files_to_create']
        )
        if instruction:
            system_messages.append({
                'role': 'system',
                'content': instruction
            })

    # 3. Target file writing
    msg = generate_target_file_message(target_file)
    if msg:
        system_messages.append(msg)

    # 4. Code execution
    msg = generate_execution_message(user_input)
    if msg:
        system_messages.append(msg)

    # 5. Session context
    if session_context:
        system_messages.append({
            'role': 'system',
            'content': session_context
        })

    # 6. Guidance
    if guidance:
        system_messages.append({
            'role': 'system',
            'content': guidance
        })

    return system_messages
```

---

### Step 2: Update CLI (`main.py`)

**Changes**:
1. Import the new module
2. Replace inline logic with function calls
3. Remove duplicated code

**Before** (lines ~1622-1695):
```python
# Detect file modification actions (refactor, update, create, etc.)
action_keywords = config.get_file_action_keywords()
user_input_lower = clean_user_input.lower()
has_action = any(keyword in user_input_lower for keyword in action_keywords)

# If action keywords present with @ prefixed files, instruct to use MCP tools
if has_action and (at_context['files'] or at_context['non_existing']):
    tool_instructions = []
    # ... 70+ lines of logic ...
```

**After**:
```python
from src.utils.file_action_handler import build_system_messages

# Build all system messages (includes file context, actions, session, guidance)
system_messages_to_inject = build_system_messages(
    at_context=at_context,
    user_input=clean_user_input,
    config=config,
    injected_context_parts=injected_context_parts,
    target_file=target_file,
    session_context=session_context,
    guidance=guidance
)
```

---

### Step 3: Update UI (`src/ui/routes/chat.py`)

**Current State**: No action keyword detection, no file modification handling

**Changes**:
1. Import `extract_at_context` from main.py or create shared version
2. Import `build_system_messages` from new module
3. Add action keyword detection to chat endpoint
4. Use `handle_file_modifications` for processing

**New Flow**:
```python
from src.utils.file_action_handler import build_system_messages, detect_file_actions
from src.utils.code_handlers import handle_file_modifications

@chat_bp.route('/api/chat', methods=['POST'])
def chat():
    user_message = data.get('message', '')

    # 1. Extract @ context
    at_context = extract_at_context(user_message, working_dir)

    # 2. Load file contents for context injection
    injected_context_parts = load_file_contexts(at_context)

    # 3. Build system messages
    system_messages = build_system_messages(
        at_context=at_context,
        user_input=user_message,
        config=config,
        injected_context_parts=injected_context_parts,
        session_context=session_context,
        guidance=guidance
    )

    # 4. Get LLM response
    response = get_llm_response(user_message, system_messages)

    # 5. Check for file modifications
    action_result = detect_file_actions(user_message, at_context, config)
    if action_result['has_action'] and (action_result['files_to_modify'] or action_result['files_to_create']):
        # Process file modifications using MCP tools
        mod_result = await handle_file_modifications(
            mcp_client,
            response,
            action_result['files_to_modify'],
            action_result['files_to_create'],
            lambda: working_dir,
            console=None,
            debug_print_func=None
        )

        # Return modification results in response
        return jsonify({
            'response': response,
            'file_modifications': mod_result
        })

    return jsonify({'response': response})
```

---

### Step 4: Extract `extract_at_context` to Shared Utility

**Current**: Only in `main.py`
**New Location**: `src/utils/context_extraction.py`

This function is needed by both CLI and UI.

---

### Step 5: Update Tests

Add tests for the new module:

**File**: `tests/test_file_action_handler.py`

```python
"""Tests for file action handler."""

import pytest
from src.utils.file_action_handler import (
    detect_file_actions,
    generate_file_modification_instructions,
    build_system_messages
)
from src.config import ConfigManager


class TestFileActionDetection:
    """Test action keyword detection."""

    def test_detect_import_action(self):
        """Test detection of import action."""
        config = ConfigManager()
        at_context = {
            'files': ['services/user_service.py'],
            'non_existing': []
        }
        user_input = "import @utils/helpers.py validate_email into @services/user_service.py"

        result = detect_file_actions(user_input, at_context, config)

        assert result['has_action'] is True
        assert 'import' in result['action_keywords_found']
        assert 'services/user_service.py' in result['files_to_modify']

    def test_no_action_keywords(self):
        """Test when no action keywords present."""
        config = ConfigManager()
        at_context = {'files': [], 'non_existing': []}
        user_input = "what is this file about?"

        result = detect_file_actions(user_input, at_context, config)

        assert result['has_action'] is False
        assert len(result['action_keywords_found']) == 0


class TestInstructionGeneration:
    """Test instruction string generation."""

    def test_generate_modify_instructions(self):
        """Test generating instructions for file modification."""
        instruction = generate_file_modification_instructions(
            files_to_modify=['app.py'],
            files_to_create=[]
        )

        assert 'MODIFY these existing files: app.py' in instruction
        assert 'file: <full_file_path>' in instruction

    def test_generate_create_instructions(self):
        """Test generating instructions for file creation."""
        instruction = generate_file_modification_instructions(
            files_to_modify=[],
            files_to_create=['new_file.py']
        )

        assert 'CREATE these new files: new_file.py' in instruction
```

---

## Migration Strategy

1. **Phase 1**: Create `src/utils/file_action_handler.py` with all shared functions
2. **Phase 2**: Update CLI to use new module (backward compatible)
3. **Phase 3**: Test CLI thoroughly to ensure no regressions
4. **Phase 4**: Extract `extract_at_context` to shared utility
5. **Phase 5**: Update UI to use new module
6. **Phase 6**: Test UI file modification flow
7. **Phase 7**: Add comprehensive tests

---

## Benefits

1. **Consistency**: CLI and UI behave identically for file modifications
2. **Maintainability**: Single source of truth for action detection logic
3. **Testability**: Shared functions are easier to unit test
4. **Extensibility**: Easy to add new action keywords or instruction patterns
5. **Configuration**: Action keywords configurable in `config.yaml`

---

## Success Criteria

- ✅ CLI continues to work as before (no regressions)
- ✅ UI now detects action keywords and uses MCP tools
- ✅ Same prompt produces same behavior in CLI and UI
- ✅ All existing tests pass
- ✅ New tests added for shared module
- ✅ Code duplication eliminated

---

## Estimated Effort

- Create shared module: 1-2 hours
- Update CLI: 30 minutes
- Extract context utility: 30 minutes
- Update UI: 2-3 hours (includes MCP client integration)
- Testing: 1-2 hours
- Documentation: 30 minutes

**Total**: ~6-9 hours

---

## Notes

- The UI's MCP client handling may need adjustment (currently uses persistent loop)
- Consider adding a "file modifications applied" indicator in UI chat
- May want to add undo/revert functionality in UI for file changes
- Consider adding diff preview in UI before applying changes
