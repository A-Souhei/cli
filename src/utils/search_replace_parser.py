"""
Search/Replace Parser Module - Parse and apply search/replace blocks to files.

This module provides functions to parse search/replace blocks (simpler format for LLMs)
and apply them to files with validation. It's designed as an alternative to unified diffs
for models that struggle with diff format.

Format:
<<<SEARCH>>>
code to find
<<<REPLACE>>>
code to replace with
<<<END>>>

Or alternative format:
<<<<<<< SEARCH
code to find
=======
code to replace with
>>>>>>> REPLACE
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional


class SearchReplaceError(Exception):
    """Base exception for search/replace errors."""
    pass


class SearchBlockNotFoundError(SearchReplaceError):
    """Raised when the search text is not found in the file."""
    pass


class MultipleMatchesError(SearchReplaceError):
    """Raised when search text matches multiple locations."""
    pass


class InvalidFormatError(SearchReplaceError):
    """Raised when the search/replace format is invalid."""
    pass


@dataclass
class SearchReplaceBlock:
    """Represents a single search/replace operation."""
    search_text: str      # Text to search for
    replace_text: str     # Text to replace with
    
    def __post_init__(self):
        # Normalize line endings
        self.search_text = self.search_text.replace('\r\n', '\n')
        self.replace_text = self.replace_text.replace('\r\n', '\n')


def detect_search_replace_format(text: str) -> bool:
    """
    Detect if the text contains search/replace blocks.
    
    Args:
        text: The text to check
        
    Returns:
        True if search/replace format is detected
    """
    # Format 1: <<<SEARCH>>> ... <<<REPLACE>>> ... <<<END>>>
    pattern1 = r'<<<\s*SEARCH\s*>>>'
    # Format 2: <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE
    pattern2 = r'<{6,7}\s*SEARCH'
    # Format 3: Simple SEARCH: and REPLACE: markers
    pattern3 = r'^SEARCH:\s*$'
    
    return (
        bool(re.search(pattern1, text, re.IGNORECASE)) or
        bool(re.search(pattern2, text, re.IGNORECASE)) or
        bool(re.search(pattern3, text, re.MULTILINE | re.IGNORECASE))
    )


def parse_search_replace_blocks(text: str) -> List[SearchReplaceBlock]:
    """
    Parse search/replace blocks from text.
    
    Supports multiple formats:
    1. <<<SEARCH>>> ... <<<REPLACE>>> ... <<<END>>>
    2. <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE
    3. SEARCH: ... REPLACE: ... END
    
    Args:
        text: Text containing search/replace blocks
        
    Returns:
        List of SearchReplaceBlock objects
        
    Raises:
        InvalidFormatError: If format is invalid or incomplete
    """
    blocks = []
    
    # Try Format 1: <<<SEARCH>>> ... <<<REPLACE>>> ... <<<END>>>
    pattern1 = re.compile(
        r'<<<\s*SEARCH\s*>>>\s*\n(.*?)<<<\s*REPLACE\s*>>>\s*\n(.*?)<<<\s*END\s*>>>',
        re.DOTALL | re.IGNORECASE
    )
    matches1 = pattern1.findall(text)
    if matches1:
        for search_text, replace_text in matches1:
            blocks.append(SearchReplaceBlock(
                search_text=search_text.strip('\n'),
                replace_text=replace_text.strip('\n')
            ))
        return blocks
    
    # Try Format 2: <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE
    pattern2 = re.compile(
        r'<{6,7}\s*SEARCH\s*\n(.*?)\n={6,7}\s*\n(.*?)\n>{6,7}\s*REPLACE',
        re.DOTALL | re.IGNORECASE
    )
    matches2 = pattern2.findall(text)
    if matches2:
        for search_text, replace_text in matches2:
            blocks.append(SearchReplaceBlock(
                search_text=search_text.strip('\n'),
                replace_text=replace_text.strip('\n')
            ))
        return blocks
    
    # Try Format 3: More lenient - search for paired SEARCH/REPLACE sections
    # This handles variations LLMs might produce
    pattern3 = re.compile(
        r'(?:^|\n)\s*(?:```\w*\s*\n)?'  # Optional code fence
        r'(?:SEARCH|<<<SEARCH>>>|<{3,}SEARCH)\s*:?\s*\n'  # SEARCH marker
        r'(.*?)'  # Search content
        r'(?:^|\n)\s*(?:REPLACE|<<<REPLACE>>>|<{3,}REPLACE|={3,})\s*:?\s*\n'  # REPLACE marker
        r'(.*?)'  # Replace content
        r'(?:(?:^|\n)\s*(?:END|<<<END>>>|>{3,}|```)|$)',  # END marker or end of string
        re.DOTALL | re.IGNORECASE | re.MULTILINE
    )
    matches3 = pattern3.findall(text)
    if matches3:
        for search_text, replace_text in matches3:
            # Clean up potential code fence artifacts
            search_text = search_text.strip('\n').rstrip('`').strip('\n')
            replace_text = replace_text.strip('\n').rstrip('`').strip('\n')
            if search_text:  # Only add if we have search text
                blocks.append(SearchReplaceBlock(
                    search_text=search_text,
                    replace_text=replace_text
                ))
        return blocks
    
    # If no blocks found, raise error
    raise InvalidFormatError(
        "Could not parse search/replace blocks. Expected format:\n"
        "<<<SEARCH>>>\n"
        "code to find\n"
        "<<<REPLACE>>>\n"
        "code to replace with\n"
        "<<<END>>>"
    )


def validate_search_blocks(content: str, blocks: List[SearchReplaceBlock]) -> Tuple[bool, str]:
    """
    Validate that all search blocks can be found exactly once in the content.
    
    Args:
        content: The original file content
        blocks: List of search/replace blocks to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    for i, block in enumerate(blocks, 1):
        count = content.count(block.search_text)
        
        if count == 0:
            # Try to find similar text for better error message
            first_line = block.search_text.split('\n')[0][:50]
            return False, (
                f"Block {i}: Search text not found in file.\n"
                f"Looking for: '{first_line}...'\n"
                f"The code may have been modified or the search text doesn't match exactly."
            )
        
        if count > 1:
            first_line = block.search_text.split('\n')[0][:50]
            return False, (
                f"Block {i}: Search text matches {count} locations.\n"
                f"Looking for: '{first_line}...'\n"
                f"Please include more context to make the search unique."
            )
    
    return True, ""


def apply_search_replace_blocks(
    content: str, 
    blocks: List[SearchReplaceBlock],
    validate: bool = True
) -> Tuple[str, int]:
    """
    Apply search/replace blocks to content.
    
    Args:
        content: The original file content
        blocks: List of search/replace blocks to apply
        validate: Whether to validate blocks before applying
        
    Returns:
        Tuple of (new_content, blocks_applied_count)
        
    Raises:
        SearchBlockNotFoundError: If a search block is not found
        MultipleMatchesError: If a search block matches multiple times
    """
    if validate:
        is_valid, error = validate_search_blocks(content, blocks)
        if not is_valid:
            raise SearchBlockNotFoundError(error)
    
    result = content
    applied_count = 0
    
    for block in blocks:
        # Check how many matches we have
        count = result.count(block.search_text)
        
        if count == 0:
            raise SearchBlockNotFoundError(
                f"Search text not found:\n{block.search_text[:100]}..."
            )
        
        if count > 1:
            raise MultipleMatchesError(
                f"Search text matches {count} locations. Include more context."
            )
        
        # Apply the replacement
        result = result.replace(block.search_text, block.replace_text, 1)
        applied_count += 1
    
    return result, applied_count


def apply_search_replace_to_file(
    file_path: str,
    blocks: List[SearchReplaceBlock],
    working_dir: Optional[str] = None
) -> Tuple[bool, str, int]:
    """
    Apply search/replace blocks to a file atomically.
    
    Args:
        file_path: Path to the file to modify
        blocks: List of search/replace blocks to apply
        working_dir: Working directory for relative paths
        
    Returns:
        Tuple of (success, message, blocks_applied_count)
    """
    # Resolve path
    if working_dir and not os.path.isabs(file_path):
        file_path = os.path.join(working_dir, file_path)
    
    path = Path(file_path).resolve()
    
    # Read original content
    try:
        with open(path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except FileNotFoundError:
        return False, f"File not found: {file_path}", 0
    except Exception as e:
        return False, f"Error reading file: {str(e)}", 0
    
    # Apply blocks
    try:
        new_content, applied_count = apply_search_replace_blocks(
            original_content, 
            blocks,
            validate=True
        )
    except (SearchBlockNotFoundError, MultipleMatchesError) as e:
        return False, str(e), 0
    
    # Write atomically (write to temp file, then rename)
    try:
        temp_path = path.with_suffix(path.suffix + '.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Rename temp file to original (atomic on most systems)
        os.replace(temp_path, path)
        
        return True, f"Successfully applied {applied_count} replacement(s)", applied_count
    except Exception as e:
        # Clean up temp file if it exists
        if temp_path.exists():
            temp_path.unlink()
        return False, f"Error writing file: {str(e)}", 0


def extract_search_replace_from_response(response: str) -> Optional[str]:
    """
    Extract search/replace content from an LLM response.
    
    Handles cases where:
    - Response is wrapped in code blocks
    - Response includes explanatory text
    - Multiple formats are mixed
    
    Args:
        response: The full LLM response
        
    Returns:
        The extracted search/replace content, or None if not found
    """
    # First, try to find search/replace blocks directly
    if detect_search_replace_format(response):
        return response
    
    # Try to extract from code blocks
    code_block_pattern = re.compile(
        r'```(?:\w*\s*\n)?(.*?)```',
        re.DOTALL
    )
    code_blocks = code_block_pattern.findall(response)
    
    for block in code_blocks:
        if detect_search_replace_format(block):
            return block
    
    return None
