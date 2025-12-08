"""Makemap functionality for the AI CLI.

Provides parsing and generation of .makemap files from Makefiles,
similar to .repomap and .datamap functionality.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any


# Makefile names to look for (in order of preference)
MAKEFILE_NAMES = ['Makefile', 'makefile', 'GNUmakefile']

# Max characters to include from recipe
MAX_RECIPE_PREVIEW = 500


def find_makefile(working_dir: str) -> Optional[Path]:
    """
    Find the Makefile in the working directory.

    Args:
        working_dir: Root directory to search

    Returns:
        Path to Makefile if found, None otherwise
    """
    working_path = Path(working_dir)

    for makefile_name in MAKEFILE_NAMES:
        makefile_path = working_path / makefile_name
        if makefile_path.exists() and makefile_path.is_file():
            return makefile_path

    return None


def parse_makefile(makefile_path: str) -> Dict[str, Any]:
    """
    Parse a Makefile to extract targets, dependencies, variables, and descriptions.

    Args:
        makefile_path: Path to the Makefile

    Returns:
        Dict with 'targets', 'variables', 'phony_targets', and 'content' keys
    """
    path = Path(makefile_path)
    if not path.exists():
        return {
            'targets': [],
            'variables': {},
            'phony_targets': [],
            'content': '',
            'error': f'Makefile not found: {makefile_path}'
        }

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return {
            'targets': [],
            'variables': {},
            'phony_targets': [],
            'content': '',
            'error': f'Failed to read Makefile: {str(e)}'
        }

    lines = content.split('\n')
    targets = []
    variables = {}
    phony_targets = set()

    # Track comments before targets for descriptions
    pending_comments = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines but reset comments
        if not stripped:
            pending_comments = []
            i += 1
            continue

        # Collect comments (potential descriptions)
        if stripped.startswith('#'):
            # Check for ## style comments (common for help text)
            if '##' in stripped:
                # Extract description after ##
                desc_match = re.search(r'##\s*(.+)$', stripped)
                if desc_match:
                    pending_comments.append(desc_match.group(1).strip())
            else:
                # Regular comment
                comment_text = stripped.lstrip('#').strip()
                if comment_text:
                    pending_comments.append(comment_text)
            i += 1
            continue

        # Parse .PHONY declarations
        phony_match = re.match(r'^\.PHONY\s*:\s*(.+)$', stripped)
        if phony_match:
            phony_list = phony_match.group(1).split()
            phony_targets.update(phony_list)
            pending_comments = []
            i += 1
            continue

        # Parse variable definitions (VAR := value, VAR ?= value, VAR = value)
        var_match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*[:?]?=\s*(.*)$', stripped)
        if var_match and ':' not in var_match.group(1):
            var_name = var_match.group(1)
            var_value = var_match.group(2).strip()
            variables[var_name] = {
                'value': var_value,
                'description': ' '.join(pending_comments) if pending_comments else None
            }
            pending_comments = []
            i += 1
            continue

        # Parse target definitions (target: dependencies)
        target_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_\-\.]*)\s*:\s*(.*)$', stripped)
        if target_match:
            target_name = target_match.group(1)
            dependencies = target_match.group(2).strip()

            # Skip special targets starting with .
            if target_name.startswith('.'):
                pending_comments = []
                i += 1
                continue

            # Collect the recipe (indented lines following the target)
            recipe_lines = []
            j = i + 1
            while j < len(lines):
                recipe_line = lines[j]
                # Recipe lines start with tab
                if recipe_line.startswith('\t'):
                    recipe_lines.append(recipe_line[1:])  # Remove leading tab
                    j += 1
                elif recipe_line.strip() == '':
                    # Empty line might be part of recipe
                    j += 1
                else:
                    break

            # Extract description from ## in the same line (common pattern)
            inline_desc_match = re.search(r'##\s*(.+)$', dependencies)
            if inline_desc_match:
                description = inline_desc_match.group(1).strip()
                dependencies = re.sub(r'\s*##.*$', '', dependencies).strip()
            else:
                description = ' '.join(pending_comments) if pending_comments else None

            # Build recipe preview
            recipe = '\n'.join(recipe_lines)
            if len(recipe) > MAX_RECIPE_PREVIEW:
                recipe = recipe[:MAX_RECIPE_PREVIEW] + '...'

            targets.append({
                'name': target_name,
                'dependencies': dependencies.split() if dependencies else [],
                'description': description,
                'recipe': recipe,
                'is_phony': target_name in phony_targets
            })

            pending_comments = []
            i = j
            continue

        # Line didn't match any pattern
        pending_comments = []
        i += 1

    return {
        'targets': targets,
        'variables': variables,
        'phony_targets': list(phony_targets),
        'content': content
    }


def collect_makefile_targets(working_dir: str) -> Dict[str, Any]:
    """
    Find and parse the Makefile in the working directory.

    Args:
        working_dir: Root directory to search

    Returns:
        Dict with parsed Makefile data or error information
    """
    makefile_path = find_makefile(working_dir)

    if not makefile_path:
        return {
            'found': False,
            'error': f'No Makefile found in {working_dir}',
            'targets': [],
            'variables': {},
            'phony_targets': []
        }

    parsed = parse_makefile(str(makefile_path))
    parsed['found'] = True
    parsed['path'] = str(makefile_path)

    return parsed


def generate_makemap_prompt(parsed_makefile: Dict[str, Any], tree_output: str = None) -> str:
    """
    Generate an LLM prompt to create a comprehensive makemap.

    Args:
        parsed_makefile: Dict from parse_makefile() with targets, variables, etc.
        tree_output: Optional directory tree string to include

    Returns:
        Prompt string for the LLM
    """
    # Build targets section
    targets_section = []
    for target in parsed_makefile.get('targets', []):
        target_info = f"### {target['name']}"
        if target.get('dependencies'):
            target_info += f"\n- Dependencies: {', '.join(target['dependencies'])}"
        if target.get('description'):
            target_info += f"\n- Description: {target['description']}"
        if target.get('recipe'):
            recipe_preview = target['recipe'][:200] + '...' if len(target['recipe']) > 200 else target['recipe']
            target_info += f"\n- Recipe:\n```\n{recipe_preview}\n```"
        targets_section.append(target_info)

    # Build variables section
    variables_section = []
    for var_name, var_info in parsed_makefile.get('variables', {}).items():
        var_entry = f"- **{var_name}**: `{var_info['value']}`"
        if var_info.get('description'):
            var_entry += f" - {var_info['description']}"
        variables_section.append(var_entry)

    # Build tree section if provided
    tree_section = ""
    if tree_output:
        tree_section = f"""## Directory Tree

```
{tree_output}
```

"""

    # Full Makefile content for reference
    makefile_content = parsed_makefile.get('content', '')
    if len(makefile_content) > 5000:
        makefile_content = makefile_content[:5000] + '\n... (truncated)'

    prompt = f"""You are a build system expert analyzing a Makefile. Create a comprehensive makemap that documents all build targets, their purposes, and how to use them.

{tree_section}## Makefile Content

```makefile
{makefile_content}
```

## Parsed Targets

{chr(10).join(targets_section) if targets_section else 'No targets found'}

## Parsed Variables

{chr(10).join(variables_section) if variables_section else 'No variables found'}

## Instructions

Create a detailed makemap document with the following sections:

1. **Project Overview**:
   - Brief description of what this project builds
   - Primary build system (Make)
   - Key entry points for developers

2. **Quick Reference**:
   - List the most commonly used targets
   - One-liner descriptions for quick lookup

3. **Targets** (for EACH target found):
   - **Purpose**: What does this target do?
   - **Dependencies**: What must run first?
   - **Usage**: `make <target>` with any required variables
   - **Notes**: Any important considerations

4. **Variables**:
   - Document each variable
   - Default values
   - How to override (e.g., `make target VAR=value`)

5. **Common Workflows**:
   - Development workflow (setup, build, test, run)
   - CI/CD workflow if applicable
   - Cleanup and maintenance

6. **Dependencies**:
   - External tools required (docker, python, etc.)
   - How to check/install them

Please provide the makemap in Markdown format. Be thorough but concise."""

    return prompt


def generate_makemap_update_prompt(new_targets: List[Dict], existing_makemap: str) -> str:
    """
    Generate an LLM prompt to update an existing makemap with new targets.

    Args:
        new_targets: List of new target dicts from parse_makefile()
        existing_makemap: The existing .makemap file content

    Returns:
        Prompt string for the LLM
    """
    # Build new targets section
    new_targets_section = []
    for target in new_targets:
        target_info = f"### {target['name']}"
        if target.get('dependencies'):
            target_info += f"\n- Dependencies: {', '.join(target['dependencies'])}"
        if target.get('description'):
            target_info += f"\n- Description: {target['description']}"
        if target.get('recipe'):
            recipe_preview = target['recipe'][:200] + '...' if len(target['recipe']) > 200 else target['recipe']
            target_info += f"\n- Recipe:\n```\n{recipe_preview}\n```"
        new_targets_section.append(target_info)

    prompt = f"""You are a build system expert updating an existing makemap. Your task is to integrate NEW targets into the existing documentation.

## Existing Makemap

{existing_makemap}

## NEW Targets to Add

The following targets are NEW and need to be integrated:

{chr(10).join(new_targets_section)}

## Instructions

1. **DO NOT regenerate the entire makemap from scratch**
2. **Preserve all existing content and structure**
3. **ADD the new targets to the appropriate sections**
4. Update these sections as needed:
   - Add new targets to the Quick Reference section
   - Add detailed documentation for each new target
   - Update Common Workflows if the new targets affect them
   - Update Variables if new targets use/define new variables

5. **Format requirements:**
   - Keep the same markdown structure as the existing makemap
   - Add new targets in a logical order (alphabetically or by category)
   - Maintain consistency in description style

Please provide the UPDATED makemap in Markdown format."""

    return prompt


async def load_makemap_to_context(mcp_client, makemap_path: str, working_dir: str, session_id: str = None) -> dict:
    """
    Load a .makemap file into context using the MCP client.

    Args:
        mcp_client: MCPClient instance
        makemap_path: Path to the .makemap file
        working_dir: Working directory
        session_id: Optional session ID for persistence

    Returns:
        Result dict with status and message
    """
    args = {
        'file_path': makemap_path,
        'working_dir': working_dir
    }
    if session_id:
        args['session_id'] = session_id

    result = await mcp_client.call_tool('coder', 'add_file_context', args)

    try:
        return json.loads(result) if result else {'status': 'error', 'message': 'MCP tool returned empty result'}
    except json.JSONDecodeError as parse_error:
        result_str = str(result) if result is not None else ''
        error_preview = (result_str[:100] + '...') if len(result_str) > 100 else result_str
        return {'status': 'error', 'message': f'Failed to parse response: {parse_error}. Response: {error_preview}'}


def get_target_names(parsed_makefile: Dict[str, Any]) -> List[str]:
    """
    Extract just the target names from a parsed Makefile.

    Args:
        parsed_makefile: Dict from parse_makefile()

    Returns:
        List of target names
    """
    return [target['name'] for target in parsed_makefile.get('targets', [])]


def find_target_by_name(parsed_makefile: Dict[str, Any], target_name: str) -> Optional[Dict]:
    """
    Find a specific target by name.

    Args:
        parsed_makefile: Dict from parse_makefile()
        target_name: Name of the target to find

    Returns:
        Target dict if found, None otherwise
    """
    for target in parsed_makefile.get('targets', []):
        if target['name'] == target_name:
            return target
    return None


def validate_target(parsed_makefile: Dict[str, Any], target_name: str) -> bool:
    """
    Check if a target exists in the Makefile.

    Args:
        parsed_makefile: Dict from parse_makefile()
        target_name: Name of the target to validate

    Returns:
        True if target exists, False otherwise
    """
    return find_target_by_name(parsed_makefile, target_name) is not None
