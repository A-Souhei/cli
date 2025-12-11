"""Execute command handlers for running TODO_LIST and MAKE_LIST plans."""

import json
import re
import subprocess


def parse_tool_reference(step_text):
    """
    Parse tool reference from step text.

    Returns:
        tuple: (tool_type, tool_name) where tool_type is 'tool' or 'make', or (None, None) if no reference found
    """
    # Check for [Tool: tool_name] pattern
    tool_match = re.search(r'\[Tool:\s*([^\]]+)\]', step_text, re.IGNORECASE)
    if tool_match:
        return ('tool', tool_match.group(1).strip())

    # Check for [Make: make target] pattern
    make_match = re.search(r'\[Make:\s*make\s+([^\]]+)\]', step_text, re.IGNORECASE)
    if make_match:
        return ('make', make_match.group(1).strip())

    return (None, None)


def execute_make_command(target, working_dir, console, debug_print):
    """
    Execute a make command.

    Returns:
        tuple: (success, output)
    """
    try:
        console.print(f"[dim]  → Executing: make {target}[/dim]")

        result = subprocess.run(
            ['make', target],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0

        if success:
            console.print(f"[green]  ✓ Make command succeeded[/green]")
        else:
            console.print(f"[red]  ✗ Make command failed with exit code {result.returncode}[/red]")

        return (success, output)

    except subprocess.TimeoutExpired:
        error = f"Make command timed out after 5 minutes"
        console.print(f"[red]  ✗ {error}[/red]")
        return (False, error)
    except Exception as e:
        error = f"Error executing make command: {str(e)}"
        console.print(f"[red]  ✗ {error}[/red]")
        debug_print(error, icon="❌")
        return (False, error)


def execute_mcp_tool(tool_name, working_dir, mcp_client, run_async, console, debug_print, accumulated_context):
    """
    Execute an MCP tool.

    Returns:
        tuple: (success, output)
    """
    try:
        console.print(f"[dim]  → Calling tool: {tool_name}[/dim]")

        # Build tool arguments based on tool name and context
        tool_args = {
            "working_dir": working_dir
        }

        # For code execution tools, we might need to extract code from context
        # For now, pass basic arguments

        result = run_async(
            mcp_client.call_tool('coder', tool_name, tool_args)
        )

        if result:
            console.print(f"[green]  ✓ Tool executed successfully[/green]")
            return (True, result)
        else:
            error = "Tool returned no result"
            console.print(f"[yellow]  ⚠ {error}[/yellow]")
            return (False, error)

    except Exception as e:
        error = f"Error executing tool: {str(e)}"
        console.print(f"[red]  ✗ {error}[/red]")
        debug_print(error, icon="❌")
        return (False, error)


def handle_execute_plan(console, session_manager, mcp_client, get_user_working_dir,
                        run_async, user_input_normalized, debug_print, CustomMarkdown,
                        ollama_client, config, stream, temperature):
    """
    Handle /execute command to run TODO_LIST or MAKE_LIST plans.

    Usage:
        /execute TODO_LIST
        /execute MAKE_LIST

    This command:
    1. Calls execute_plan MCP tool to parse the plan into steps
    2. Executes each step sequentially using the configured LLM (Ollama or Claude)
    3. Accumulates context between steps
    4. Displays results with formatting

    Args:
        console: Rich console for output
        session_manager: Session manager instance
        mcp_client: MCP client for calling tools
        get_user_working_dir: Function to get working directory
        run_async: Function to run async coroutines
        user_input_normalized: Normalized user input
        debug_print: Debug print function
        CustomMarkdown: Custom markdown renderer class
        ollama_client: OllamaClient for calling LLM
        config: Configuration manager
        stream: Stream responses
        temperature: LLM temperature
    """
    # Check if session is active
    if not session_manager.is_active():
        console.print("\n⚠️  [yellow]No active session. Start a session first with /session start[/yellow]\n")
        return True

    # Parse command arguments
    parts = user_input_normalized.split(maxsplit=1)

    if len(parts) < 2:
        console.print("\n❌ [red]Usage: /execute TODO_LIST or /execute MAKE_LIST[/red]")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]  /execute TODO_LIST[/dim]")
        console.print("[dim]  /execute MAKE_LIST[/dim]\n")
        return True

    plan_type = parts[1].upper()

    # Validate plan type
    if plan_type not in ["TODO_LIST", "MAKE_LIST"]:
        console.print(f"\n❌ [red]Invalid plan type: {plan_type}[/red]")
        console.print("[yellow]Must be either TODO_LIST or MAKE_LIST[/yellow]\n")
        return True

    # Get session info
    session_info = session_manager.get_session_info()
    if not session_info:
        console.print("\n⚠️  [yellow]Unable to get session information[/yellow]\n")
        return True

    session_id = session_info['session_id']
    working_dir = get_user_working_dir()

    # Get current model info
    current_model = ollama_client.model

    console.print(f"\n🚀 [bold cyan]Executing {plan_type}[/bold cyan]")
    console.print(f"[dim]Session: {session_id[:16]}...[/dim]")
    console.print(f"[dim]Working Directory: {working_dir}[/dim]")
    console.print(f"[dim]Model: {current_model}[/dim]\n")

    # Step 1: Call execute_plan MCP tool to parse the plan
    debug_print(f"Parsing {plan_type} with execute_plan tool", icon="📝")

    try:
        # Build tool call arguments
        tool_args = {
            "session_id": session_id,
            "plan_type": plan_type,
            "working_dir": working_dir
        }

        # Call the MCP tool to parse the plan
        console.print("[dim]Parsing plan...[/dim]\n")

        result = run_async(
            mcp_client.call_tool('coder', 'execute_plan', tool_args)
        )

        if not result:
            console.print("⚠️  [yellow]No result returned from execute_plan tool[/yellow]\n")
            return True

        result_text = result

        # Parse the result
        try:
            result_json = json.loads(result_text)
        except json.JSONDecodeError as e:
            console.print(f"[red]⚠️  Failed to parse result: {str(e)}[/red]")
            console.print(f"[dim]Raw result: {result_text[:200]}[/dim]\n")
            return True

        status = result_json.get('status', 'unknown')

        if status != 'success':
            # Display error
            error_message = result_json.get('message', 'Unknown error')
            console.print(f"❌ [red]Error: {error_message}[/red]")

            # Show traceback if available
            if 'traceback' in result_json:
                console.print(f"\n[dim]{result_json['traceback']}[/dim]")

            console.print()
            return True

        # Get the parsed steps
        steps = result_json.get('steps', [])
        total_steps = result_json.get('total_steps', 0)

        if total_steps == 0:
            console.print(f"⚠️  [yellow]No steps found in {plan_type}[/yellow]\n")
            return True

        console.print(f"✅ [green]Parsed {total_steps} step{'s' if total_steps != 1 else ''}[/green]\n")

        # Step 2: Execute each step sequentially using the configured LLM
        accumulated_context = f"Executing {plan_type} plan:\n\n"
        executed_count = 0

        for step_data in steps:
            step_num = step_data.get('step_number', '?')
            step_text = step_data.get('step', '')

            console.print(f"[bold cyan]Step {step_num}:[/bold cyan] {step_text}")
            console.print()

            try:
                # Check if step has a tool or make reference
                tool_type, tool_name = parse_tool_reference(step_text)

                execution_result = None
                success = False

                if tool_type == 'make':
                    # Execute make command
                    success, output = execute_make_command(
                        tool_name, working_dir, console, debug_print
                    )
                    execution_result = output

                elif tool_type == 'tool':
                    # Execute MCP tool
                    success, output = execute_mcp_tool(
                        tool_name, working_dir, mcp_client, run_async,
                        console, debug_print, accumulated_context
                    )
                    execution_result = output

                else:
                    # No tool reference - use LLM for reasoning/planning
                    console.print(f"[dim]  → Using LLM for reasoning step[/dim]")

                    # Build prompt for this step with accumulated context
                    step_prompt = f"{accumulated_context}Step {step_num}: {step_text}\n\nExecute this step:"

                    # Format as messages for both OllamaClient and AnthropicClient
                    # Include system prompt like ChatManager does
                    messages = []
                    system_prompt = config.get_system_prompt()
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": step_prompt})

                    response = ollama_client.chat(
                        messages=messages,
                        stream=False,
                        temperature=temperature
                    )

                    # Extract content from response
                    llm_response = response.get('message', {}).get('content', '') if isinstance(response, dict) else response

                    if llm_response:
                        execution_result = llm_response
                        success = True
                    else:
                        console.print(f"[red]⚠️  Step {step_num} failed - no response from LLM[/red]\n")

                # Display result and accumulate context
                if success and execution_result:
                    # Display execution result
                    if tool_type:
                        console.print(f"\n[dim]Output:[/dim]")
                    md = CustomMarkdown(str(execution_result))
                    console.print(md)
                    console.print()

                    # Accumulate context for next steps (truncate to avoid context bloat)
                    result_preview = str(execution_result)[:500] if len(str(execution_result)) > 500 else str(execution_result)
                    accumulated_context += f"\nStep {step_num}: {step_text}\nResult: {result_preview}\n"

                    executed_count += 1

            except Exception as e:
                console.print(f"[red]⚠️  Error executing step {step_num}: {str(e)}[/red]\n")
                debug_print(f"Step {step_num} error: {e}", icon="❌")

        # Step 3: Display summary
        console.print("─" * 60)
        console.print(f"[bold]Summary:[/bold] Executed {executed_count}/{total_steps} steps successfully")

        if executed_count == total_steps:
            console.print(f"✅ [green]All steps completed![/green]\n")
        elif executed_count > 0:
            console.print(f"⚠️  [yellow]Partial completion: {total_steps - executed_count} step(s) failed[/yellow]\n")
        else:
            console.print(f"❌ [red]No steps were executed successfully[/red]\n")

    except Exception as e:
        console.print(f"\n❌ [red]Error executing plan: {str(e)}[/red]\n")
        debug_print(f"execute_plan error: {str(e)}", icon="❌")
        import traceback
        traceback.print_exc()

    return True  # Continue the loop
