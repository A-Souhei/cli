"""
Smart Merge Module - Intelligently merge LLM-generated code with original files.

When the LLM generates full file content instead of search/replace blocks,
this module attempts to safely merge the changes by:
1. Identifying which functions/classes were modified
2. Only replacing the specific changed sections
3. Preserving all unchanged code

This is a fallback for when the LLM doesn't follow format instructions.
"""

import difflib
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CodeBlock:
    """Represents a block of code (function, class, or import section)."""
    name: str
    start_line: int
    end_line: int
    content: str
    block_type: str  # 'import', 'function', 'class', 'other'


def extract_code_blocks(content: str) -> List[CodeBlock]:
    """
    Extract logical code blocks from Python content.
    
    Identifies:
    - Import sections
    - Function definitions
    - Class definitions
    """
    lines = content.split('\n')
    blocks = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            i += 1
            continue
        
        # Import block
        if stripped.startswith('import ') or stripped.startswith('from '):
            start = i
            while i < len(lines) and (
                lines[i].strip().startswith('import ') or 
                lines[i].strip().startswith('from ') or
                lines[i].strip() == ''
            ):
                i += 1
            blocks.append(CodeBlock(
                name='imports',
                start_line=start,
                end_line=i - 1,
                content='\n'.join(lines[start:i]),
                block_type='import'
            ))
            continue
        
        # Function definition
        if stripped.startswith('def '):
            match = re.match(r'def\s+(\w+)\s*\(', stripped)
            if match:
                func_name = match.group(1)
                start = i
                indent = len(line) - len(line.lstrip())
                i += 1
                # Find end of function
                while i < len(lines):
                    if lines[i].strip() == '':
                        i += 1
                        continue
                    current_indent = len(lines[i]) - len(lines[i].lstrip())
                    if current_indent <= indent and lines[i].strip():
                        break
                    i += 1
                blocks.append(CodeBlock(
                    name=func_name,
                    start_line=start,
                    end_line=i - 1,
                    content='\n'.join(lines[start:i]),
                    block_type='function'
                ))
                continue
        
        # Class definition
        if stripped.startswith('class '):
            match = re.match(r'class\s+(\w+)', stripped)
            if match:
                class_name = match.group(1)
                start = i
                indent = len(line) - len(line.lstrip())
                i += 1
                # Find end of class
                while i < len(lines):
                    if lines[i].strip() == '':
                        i += 1
                        continue
                    current_indent = len(lines[i]) - len(lines[i].lstrip())
                    if current_indent <= indent and lines[i].strip():
                        break
                    i += 1
                blocks.append(CodeBlock(
                    name=class_name,
                    start_line=start,
                    end_line=i - 1,
                    content='\n'.join(lines[start:i]),
                    block_type='class'
                ))
                continue
        
        # Other code
        i += 1
    
    return blocks


def find_changed_sections(original: str, modified: str) -> List[Tuple[str, str]]:
    """
    Find sections that changed between original and modified code.
    
    Returns list of (original_section, modified_section) tuples.
    """
    original_blocks = extract_code_blocks(original)
    modified_blocks = extract_code_blocks(modified)
    
    changes = []
    
    # Create lookup by name
    original_by_name = {b.name: b for b in original_blocks}
    modified_by_name = {b.name: b for b in modified_blocks}
    
    # Find modified blocks
    for name, mod_block in modified_by_name.items():
        if name in original_by_name:
            orig_block = original_by_name[name]
            # Check if content changed
            if orig_block.content.strip() != mod_block.content.strip():
                changes.append((orig_block.content, mod_block.content))
        else:
            # New block - add it
            changes.append(('', mod_block.content))
    
    return changes


def compute_line_diff(original: str, modified: str) -> List[Tuple[str, str]]:
    """
    Use difflib to find the minimal changes between original and modified.
    
    Returns list of (search_text, replace_text) tuples that can be applied.
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    
    matcher = difflib.SequenceMatcher(None, original_lines, modified_lines)
    
    changes = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            # Lines were changed
            orig_section = ''.join(original_lines[i1:i2])
            mod_section = ''.join(modified_lines[j1:j2])
            
            # Add context lines for reliable matching
            context_before = ''.join(original_lines[max(0, i1-2):i1])
            context_after = ''.join(original_lines[i2:min(len(original_lines), i2+2)])
            
            search = context_before + orig_section + context_after
            replace = context_before + mod_section + context_after
            
            if search.strip() and search != replace:
                changes.append((search.rstrip('\n'), replace.rstrip('\n')))
                
        elif tag == 'insert':
            # Lines were added
            if j1 > 0:
                # Add after previous line
                context = ''.join(modified_lines[max(0, j1-2):j1])
                new_content = ''.join(modified_lines[j1:j2])
                
                # Find where to insert in original
                if i1 > 0:
                    orig_context = ''.join(original_lines[max(0, i1-2):i1])
                    changes.append((orig_context.rstrip('\n'), (orig_context + new_content).rstrip('\n')))
                    
        elif tag == 'delete':
            # Lines were removed
            orig_section = ''.join(original_lines[i1:i2])
            context_before = ''.join(original_lines[max(0, i1-2):i1])
            context_after = ''.join(original_lines[i2:min(len(original_lines), i2+2)])
            
            search = context_before + orig_section + context_after
            replace = context_before + context_after
            
            if search.strip():
                changes.append((search.rstrip('\n'), replace.rstrip('\n')))
    
    return changes


def smart_merge(original: str, llm_output: str) -> Tuple[bool, str, str]:
    """
    Attempt to smartly merge LLM output with original file.
    
    This is used when the LLM generates full file content instead of
    search/replace blocks.
    
    Args:
        original: Original file content
        llm_output: LLM-generated content (may be full file or partial)
        
    Returns:
        Tuple of (success, result_content_or_error, method_used)
    """
    original_lines = len(original.splitlines())
    llm_lines = len(llm_output.splitlines())
    
    # If LLM output is less than 50% of original, try block-based merge
    if llm_lines < original_lines * 0.5:
        # Extract blocks from both
        original_blocks = extract_code_blocks(original)
        llm_blocks = extract_code_blocks(llm_output)
        
        if not llm_blocks:
            return False, "Could not extract code blocks from LLM output", "no_blocks"
        
        # Create lookup by name
        original_by_name = {b.name: b for b in original_blocks}
        
        # Try to match LLM blocks with original
        result = original
        applied = 0
        
        for llm_block in llm_blocks:
            if llm_block.name in original_by_name:
                orig_block = original_by_name[llm_block.name]
                # Replace the original block with LLM's version
                if orig_block.content.strip() != llm_block.content.strip():
                    # Preserve indentation
                    result = result.replace(orig_block.content, llm_block.content)
                    applied += 1
            else:
                # New block - try to append it at a sensible location
                if llm_block.block_type == 'function':
                    # Add after imports if exists, or at end
                    import_block = original_by_name.get('imports')
                    if import_block:
                        insert_point = import_block.content + '\n\n'
                        result = result.replace(
                            import_block.content,
                            import_block.content + '\n\n' + llm_block.content
                        )
                    else:
                        result = result.rstrip() + '\n\n' + llm_block.content + '\n'
                    applied += 1
        
        if applied > 0:
            return True, result, f"smart_merge_block ({applied} changes)"
        
        # Fall back to diff-based approach
        changes = compute_line_diff(original, llm_output)
        
        if not changes:
            return False, "Could not identify changes in partial output", "diff_failed"
        
        # Apply only the identified changes
        result = original
        applied = 0
        for search, replace in changes:
            if search in result:
                result = result.replace(search, replace, 1)
                applied += 1
        
        if applied > 0:
            return True, result, f"smart_merge_partial ({applied} changes)"
        else:
            return False, "Could not apply partial changes", "partial_failed"
    
    # If LLM output is similar length, compare block by block
    changes = find_changed_sections(original, llm_output)
    
    if not changes:
        return False, "No changes detected between original and LLM output", "no_changes"
    
    # Apply changes
    result = original
    applied = 0
    for orig_section, new_section in changes:
        if orig_section == '':
            # New block to add - append at end or find appropriate location
            result = result.rstrip() + '\n\n' + new_section + '\n'
            applied += 1
        elif orig_section in result:
            result = result.replace(orig_section, new_section, 1)
            applied += 1
    
    if applied > 0:
        return True, result, f"smart_merge_blocks ({applied} changes)"
    
    # Last resort: use line-by-line diff
    changes = compute_line_diff(original, llm_output)
    result = original
    applied = 0
    for search, replace in changes:
        if search in result:
            result = result.replace(search, replace, 1)
            applied += 1
    
    if applied > 0:
        return True, result, f"smart_merge_diff ({applied} changes)"
    
    return False, "Could not safely merge changes", "merge_failed"


def is_safe_to_merge(original: str, merged: str) -> Tuple[bool, str]:
    """
    Check if the merge result is safe (didn't lose significant code).
    
    Returns (is_safe, reason)
    """
    orig_lines = len(original.splitlines())
    merged_lines = len(merged.splitlines())
    
    # Check if we lost too many lines
    if merged_lines < orig_lines * 0.7:
        return False, f"Merge would lose too many lines ({orig_lines} -> {merged_lines})"
    
    # Check if we lost any function definitions
    orig_funcs = set(re.findall(r'def\s+(\w+)\s*\(', original))
    merged_funcs = set(re.findall(r'def\s+(\w+)\s*\(', merged))
    
    lost_funcs = orig_funcs - merged_funcs
    if lost_funcs:
        return False, f"Merge would lose functions: {lost_funcs}"
    
    # Check if we lost any class definitions
    orig_classes = set(re.findall(r'class\s+(\w+)', original))
    merged_classes = set(re.findall(r'class\s+(\w+)', merged))
    
    lost_classes = orig_classes - merged_classes
    if lost_classes:
        return False, f"Merge would lose classes: {lost_classes}"
    
    return True, "Merge appears safe"
