"""Code handling functionality for the AI CLI."""

import os
import re
import json


async def handle_code_file_writing(mcp_client, response_text: str, target_file: str, 
                                    get_working_dir_func, console=None, debug_print_func=None):
    """
    Detect code from LLM response and write it to a target file.

    Args:
        mcp_client: MCP client instance
        response_text: The LLM response text
        target_file: Path to the target file to write
        get_working_dir_func: Function to get the working directory
        console: Rich console for output (optional)
        debug_print_func: Function for debug output (optional)

    Returns:
        Write result or None
    """
    def _debug(msg, **kwargs):
        if debug_print_func:
            debug_print_func(msg, **kwargs)
    
    def _print(msg):
        if console:
            console.print(msg)
        else:
            print(msg)
    
    # Detect code in the response
    detected = mcp_client.detect_code(response_text)

    if not detected:
        _debug("No code detected in response to write to file", icon="ℹ️")
        return None

    language = detected['language']
    code = detected['code']

    _debug(f"Detected {language.upper()} code block for file: {target_file}", icon="🔍")

    # Determine if file exists to choose between write and edit
    file_exists = os.path.exists(target_file)

    # Determine tool based on language and file existence
    if language == "python":
        tool_name = "edit_python_code" if file_exists else "write_python_code"
        mcp_name = "coder"
    elif language == "r":
        tool_name = "edit_r_code" if file_exists else "write_r_code"
        mcp_name = "coder"
    else:
        _debug(f"Unsupported language for file writing: {language}", icon="⚠️")
        return None

    # Inform user what we're about to do
    action = "Updating" if file_exists else "Creating"
    _print(f"\n[cyan]{action} {target_file} with generated {language.upper()} code...[/cyan]")

    # Write the code to file
    result = await mcp_client.call_tool(
        mcp_name=mcp_name,
        tool_name=tool_name,
        arguments={
            "file_path": target_file,
            "code": code,
            "working_dir": get_working_dir_func()
        }
    )

    # Parse result
    try:
        result_data = json.loads(result)
        if result_data.get('status') == 'success':
            _print(f"[green]✓ Successfully wrote code to {target_file}[/green]\n")
        else:
            _print(f"[red]✗ Failed to write to {target_file}: {result_data.get('message')}[/red]\n")
    except Exception as e:
        if "Error:" in result:
            _print(f"[red]✗ {result}[/red]\n")
        else:
            _print(f"[red]✗ Failed to write to {target_file}: {e}[/red]\n")

    return result


async def handle_file_modifications(mcp_client, response_text: str, files_to_modify: list, 
                                     files_to_create: list, get_working_dir_func, 
                                     console=None, debug_print_func=None):
    """
    Parse LLM response for multiple file modifications and apply them.

    Args:
        mcp_client: MCP client instance
        response_text: The LLM response text
        files_to_modify: List of existing files mentioned by user
        files_to_create: List of files to create mentioned by user
        get_working_dir_func: Function to get the working directory
        console: Rich console for output (optional)
        debug_print_func: Function for debug output (optional)

    Returns:
        Dict with results for each file
    """
    def _debug(msg, **kwargs):
        if debug_print_func:
            debug_print_func(msg, **kwargs)
    
    def _print(msg):
        if console:
            console.print(msg)
        else:
            print(msg)
    
    results = {
        'modified': [],
        'created': [],
        'errors': []
    }

    # Pattern to match file paths followed by code blocks
    # Format 1: file: path/to/file.py\n```python\ncode\n``` (PRIMARY FORMAT)
    # Format 2: ```python\n# tool - file: path/to/file.py\ncode\n```
    # Format 3: filename.py\n```python\ncode\n```

    matches = []

    # Try Format 1 first (instructed format): "file:" prefix before code block
    # This pattern is more flexible and handles any file path
    pattern1 = r'(?:file|File):\s*([^\n]+\.(?:py|r|R))\s*\n+```(?:python|r)?\n(.*?)\n```'
    matches = re.findall(pattern1, response_text, re.DOTALL | re.MULTILINE)

    # Try Format 2: filename in comment inside code block
    if not matches:
        pattern2 = r'```(?:python|r)?\n#\s*(?:write_python_code|edit_python_code|write_r_code|edit_r_code)\s*-\s*file:\s*([^\n]+)\n(.*?)\n```'
        matches = re.findall(pattern2, response_text, re.DOTALL | re.MULTILINE)

    # Try Format 3: filename before code block (most lenient, any path structure)
    if not matches:
        pattern3 = r'(?:^|\n)([^\s:]+\.(?:py|r|R))\s*\n+```(?:python|r)?\n(.*?)\n```'
        matches = re.findall(pattern3, response_text, re.DOTALL | re.MULTILINE)

    if not matches:
        _debug("No file+code patterns found in response", icon="ℹ️", style="yellow")
        _print("\n[yellow]⚠️  No file modifications detected in LLM response.[/yellow]")
        _print("[dim]The LLM may not have formatted the response correctly.[/dim]")
        _print("[dim]Try rephrasing your request or check the LLM output above.[/dim]\n")
        return results

    _debug(f"Found {len(matches)} file+code blocks to process", icon="📝", style="cyan")
    _print(f"\n[cyan]📝 Processing {len(matches)} file modification(s)...[/cyan]\n")

    for file_path, code in matches:
        try:
            # Clean up file path
            file_path = file_path.strip()
            code = code.strip()

            # Remove tool comment line if present (from Format 2)
            code_lines = code.split('\n')
            if code_lines and code_lines[0].strip().startswith('#') and ('write_' in code_lines[0] or 'edit_' in code_lines[0]):
                code = '\n'.join(code_lines[1:]).strip()

            # Determine full path
            full_path = os.path.join(get_working_dir_func(), file_path)
            file_exists = os.path.exists(full_path)

            # Determine language and tool
            if file_path.endswith('.py'):
                language = "python"
                tool_name = "edit_python_code" if file_exists else "write_python_code"
            elif file_path.endswith(('.r', '.R')):
                language = "r"
                tool_name = "edit_r_code" if file_exists else "write_r_code"
            else:
                _debug(f"Unsupported file type: {file_path}", icon="⚠️", style="yellow")
                results['errors'].append(f"{file_path}: Unsupported file type")
                continue

            # Inform user
            action = "Updating" if file_exists else "Creating"
            _print(f"[cyan]{action} {file_path}...[/cyan]")

            # Call MCP tool
            result = await mcp_client.call_tool(
                mcp_name="coder",
                tool_name=tool_name,
                arguments={
                    "file_path": file_path,
                    "code": code,
                    "working_dir": get_working_dir_func()
                }
            )

            # Parse result
            try:
                result_data = json.loads(result)
                if result_data.get('status') == 'success':
                    _print(f"✓ [green]{action} {file_path} successfully[/green]")
                    if file_exists:
                        results['modified'].append(file_path)
                    else:
                        results['created'].append(file_path)
                else:
                    error_msg = result_data.get('message', 'Unknown error')
                    _print(f"✗ [red]Failed to {action.lower()} {file_path}: {error_msg}[/red]")
                    results['errors'].append(f"{file_path}: {error_msg}")
            except json.JSONDecodeError:
                # Result might be plain text error
                if "success" in result.lower():
                    _print(f"✓ [green]{action} {file_path} successfully[/green]")
                    if file_exists:
                        results['modified'].append(file_path)
                    else:
                        results['created'].append(file_path)
                else:
                    _print(f"✗ [red]Failed to {action.lower()} {file_path}[/red]")
                    results['errors'].append(f"{file_path}: {result}")

        except Exception as e:
            error_msg = str(e)
            _print(f"✗ [red]Error processing {file_path}: {error_msg}[/red]")
            results['errors'].append(f"{file_path}: {error_msg}")
            _debug(f"Error processing {file_path}: {e}", icon="❌", style="red")

    # Summary
    if results['created'] or results['modified']:
        _print(f"\n[bold green]✓ File Operations Complete[/bold green]")
        if results['created']:
            _print(f"  Created: {', '.join(results['created'])}")
        if results['modified']:
            _print(f"  Modified: {', '.join(results['modified'])}")
        if results['errors']:
            _print(f"  [yellow]Errors: {len(results['errors'])}[/yellow]")

        # Add affected files to results for verification
        results['affected_files'] = results['created'] + results['modified']

    return results


async def handle_code_execution(mcp_client, response_text: str, selector_class=None, 
                                 console=None, debug_print_func=None):
    """
    Detect and execute code from LLM response.

    Args:
        mcp_client: MCP client instance
        response_text: The LLM response text
        selector_class: InteractiveSelector class for user confirmation
        console: Rich console for output (optional)
        debug_print_func: Function for debug output (optional)

    Returns:
        Execution result or None
    """
    def _debug(msg, **kwargs):
        if debug_print_func:
            debug_print_func(msg, **kwargs)
    
    def _print(msg):
        if console:
            console.print(msg)
        else:
            print(msg)
    
    # Detect code in the response
    detected = mcp_client.detect_code(response_text)

    if not detected:
        _debug("No code detected in response", icon="ℹ️")
        return None

    language = detected['language']
    code = detected['code']

    _debug(f"Detected {language.upper()} code block", icon="🔍")

    # Determine tool based on language
    if language == "python":
        tool_name = "run_python_code"
        mcp_name = "coder"
    elif language == "r":
        tool_name = "run_r_code"
        mcp_name = "coder"
    else:
        _debug(f"Unsupported language: {language}", icon="⚠️")
        return None

    # Ask user for confirmation using InteractiveSelector
    _print("")
    if selector_class:
        try:
            selector = selector_class(
                title=f"⚡ Execute {language.upper()} code?",
                choices=["Yes", "No"],
                current="No"
            )
            choice = selector.show()

            if choice != "Yes":
                _print("\n[dim]Code execution cancelled[/dim]\n")
                return None
        except (EOFError, KeyboardInterrupt):
            _print("\n[dim]Code execution cancelled[/dim]\n")
            return None
    else:
        # No selector class provided, skip confirmation
        pass

    # Execute the code
    _debug(f"Executing {language} code...", icon="⚙️")
    _print("[yellow]Executing code...[/yellow]\n")

    result = await mcp_client.call_tool(
        mcp_name=mcp_name,
        tool_name=tool_name,
        arguments={"code": code}
    )

    return result


def display_execution_result(result: str, console=None, debug_print_func=None):
    """
    Display code execution result in a nice format.

    Args:
        result: JSON string from MCP tool execution
        console: Rich console for output (optional)
        debug_print_func: Function for debug output (optional)
    """
    def _debug(msg, **kwargs):
        if debug_print_func:
            debug_print_func(msg, **kwargs)
    
    def _print(msg):
        if console:
            console.print(msg)
        else:
            print(msg)
    
    try:
        result_data = json.loads(result)

        # Check if it's an error
        if result.startswith("Error:"):
            _print(f"\n❌ [bold red]Execution Error[/bold red]")
            _print(f"[red]{result}[/red]\n")
            return

        # Display execution complete message
        _print("\n✓ [bold]Execution Complete[/bold]\n")

        # Show stdout if present
        if result_data.get("stdout"):
            _print("📄 [bold]Output:[/bold]")
            _print(result_data["stdout"].strip())
            _print("")

        # Show stderr if present
        if result_data.get("stderr"):
            _print("⚠️  [bold yellow]Warnings/Errors:[/bold yellow]")
            _print(f"[yellow]{result_data['stderr'].strip()}[/yellow]")
            _print("")

        # Show exit code
        exit_code = result_data.get("exit_code", -1)
        if exit_code == 0:
            _print(f"[dim]Exit Code: {exit_code}[/dim]")
        else:
            _print(f"[red]Exit Code: {exit_code}[/red]")

        _print("")

    except json.JSONDecodeError:
        # Not JSON, display as-is
        _print(f"\n📄 [bold]Result:[/bold]")
        _print(result)
        _print("")
    except Exception as e:
        _debug(f"Error displaying result: {e}", icon="❌")
        _print(f"[dim]Result: {result}[/dim]\n")
