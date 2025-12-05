"""
Shared file action detection and instruction generation.
Used by both CLI and UI to provide consistent file modification behavior.
"""

from typing import Dict, List, Any, Optional
import re
import os


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
