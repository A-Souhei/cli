"""Make command handlers for AI CLI application.

This module handles all /make commands including:
- /make map generate - Generate .makemap from Makefile
- /make map load - Load .makemap into context
- /make map update - Update .makemap with new targets
- /make <prompt> - Execute make commands using natural language
"""

import os
import re
import json
import requests
from rich.spinner import Spinner
from rich.live import Live
from rich.markdown import Markdown

from src.chat import ChatManager
from src.utils.tree import generate_tree
from src.utils.makemap import (
    find_makefile,
    parse_makefile,
    generate_makemap_prompt,
    generate_makemap_update_prompt,
    load_makemap_to_context,
    get_target_names,
)


# API Configuration (should match main.py)
POSTGRES_API_URL = "http://localhost:15000"


def handle_make_map_generate(console, user_input_normalized, llm_checker,
                              get_user_working_dir, config, ollama_client,
                              stream, temperature, verbose, CustomMarkdown):
    """Handle /make map generate command."""
    # Check if make_map is disabled (e.g., when using tinyollama)
    if llm_checker.is_feature_disabled('makemap_create'):
        console.print("\n⚠️  [yellow]/make map generate is disabled when using tinyollama fallback.[/yellow]")
        console.print("[dim]This feature requires a larger model for reliable Makefile analysis.[/dim]")
        console.print("[dim]Connect to the primary Ollama server to use this feature.[/dim]\n")
        return True

    # Check if Makefile exists
    makefile_path = find_makefile(get_user_working_dir())
    if not makefile_path:
        console.print(f"\n❌ [red]No Makefile found in: {get_user_working_dir()}[/red]")
        console.print("[dim]This command requires a Makefile to exist in the working directory.[/dim]\n")
        return True

    console.print("\n🔧 [bold cyan]Generating make map...[/bold cyan]")
    console.print(f"[dim]Scanning Makefile: {makefile_path}[/dim]\n")

    try:
        # Parse the Makefile
        console.print("[yellow]📂 Parsing Makefile...[/yellow]")
        parsed = parse_makefile(str(makefile_path))

        if 'error' in parsed:
            console.print(f"[red]❌ Error parsing Makefile: {parsed['error']}[/red]\n")
            return True

        targets = parsed.get('targets', [])
        variables = parsed.get('variables', {})
        console.print(f"[green]✓ Found {len(targets)} targets, {len(variables)} variables[/green]")

        # Generate directory tree
        console.print("\n[yellow]🌳 Generating directory tree...[/yellow]")
        tree_output = generate_tree(get_user_working_dir(), max_depth=3)
        console.print(f"[green]✓ Directory tree generated[/green]\n")

        # Generate the LLM prompt
        console.print("[yellow]🤖 Generating make map with LLM...[/yellow]")
        makemap_prompt = generate_makemap_prompt(parsed, tree_output=tree_output)

        # Use a separate chat manager for makemap generation
        makemap_chat_manager = ChatManager(system_prompt=config.get_system_prompt())
        makemap_chat_manager.add_user_message(makemap_prompt)
        messages = makemap_chat_manager.get_messages()

        spinner = Spinner("dots", text="[dim]Analyzing Makefile...[/dim]", style="cyan")

        with Live(spinner, console=console, refresh_per_second=10):
            if stream:
                full_response = ""
                for chunk in ollama_client.chat(
                    messages=messages,
                    stream=True,
                    temperature=temperature
                ):
                    full_response += chunk
            else:
                response = ollama_client.chat(
                    messages=messages,
                    stream=False,
                    temperature=temperature
                )
                full_response = response.get('message', {}).get('content', '')

        # Create makemap content with tree
        makemap_content = f"""# Make Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""

        # Write the makemap to file
        makemap_file_path = os.path.join(get_user_working_dir(), '.makemap')
        with open(makemap_file_path, 'w', encoding='utf-8') as f:
            f.write(makemap_content)

        console.print(f"\n[bold green]✓ Make map created successfully![/bold green]")
        console.print(f"[cyan]📄 Saved to: {makemap_file_path}[/cyan]\n")

        # Show preview
        preview_lines = makemap_content.split('\n')[:20]
        console.print("[dim]Preview:[/dim]")
        console.print(CustomMarkdown('\n'.join(preview_lines) + '\n...', code_theme="monokai"))
        console.print()

    except Exception as e:
        console.print(f"\n❌ [red]Error creating make map: {e}[/red]\n")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    return True


def handle_make_map_load(console, get_user_working_dir, session_manager,
                          mcp_client, run_async, verbose):
    """Handle /make map load command."""
    makemap_file_path = os.path.join(get_user_working_dir(), '.makemap')

    if not os.path.exists(makemap_file_path):
        console.print(f"\n❌ [red]No .makemap file found at: {makemap_file_path}[/red]")
        console.print("[dim]Use '/make map generate' to generate a make map first.[/dim]\n")
        return True

    console.print(f"\n📂 [cyan]Loading make map: {makemap_file_path}[/cyan]")

    try:
        # Get session ID if active
        session_id = session_manager.get_session_id() if session_manager.is_active() else None

        # Load the makemap into context
        result = run_async(load_makemap_to_context(
            mcp_client,
            '.makemap',
            get_user_working_dir(),
            session_id
        ))

        if result.get('status') == 'success':
            content_size = result.get('content_size', 0)
            console.print(f"[bold green]✓ Make map loaded into context![/bold green]")
            console.print(f"[dim]  Size: {content_size:,} bytes[/dim]")
            if session_id:
                console.print(f"[dim]  Session: {session_id[:16]}...[/dim]")
            else:
                console.print(f"[dim]  Session: temporary (start a session for persistence)[/dim]")
            console.print()
        else:
            error_msg = result.get('message', 'Unknown error')
            console.print(f"[yellow]⚠️  Warning: {error_msg}[/yellow]")
            console.print("[dim]The makemap file may still be usable.[/dim]\n")

    except Exception as e:
        console.print(f"\n❌ [red]Error loading make map: {e}[/red]\n")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    return True


def handle_make_map_update(console, llm_checker, get_user_working_dir, config,
                            ollama_client, stream, temperature, verbose, CustomMarkdown):
    """Handle /make map update command."""
    # Check if make_map is disabled (e.g., when using tinyollama)
    if llm_checker.is_feature_disabled('makemap_update'):
        console.print("\n⚠️  [yellow]/make map update is disabled when using tinyollama fallback.[/yellow]")
        console.print("[dim]This feature requires a larger model for reliable Makefile analysis.[/dim]")
        console.print("[dim]Connect to the primary Ollama server to use this feature.[/dim]\n")
        return True

    makemap_file_path = os.path.join(get_user_working_dir(), '.makemap')

    if not os.path.exists(makemap_file_path):
        console.print(f"\n❌ [red]No .makemap file found at: {makemap_file_path}[/red]")
        console.print("[dim]Use '/make map generate' to generate a make map first.[/dim]\n")
        return True

    # Check if Makefile exists
    makefile_path = find_makefile(get_user_working_dir())
    if not makefile_path:
        console.print(f"\n❌ [red]No Makefile found in: {get_user_working_dir()}[/red]\n")
        return True

    console.print("\n🔧 [bold cyan]Updating make map...[/bold cyan]")

    try:
        # Read existing makemap
        with open(makemap_file_path, 'r', encoding='utf-8') as f:
            existing_makemap = f.read()

        # Parse the Makefile
        console.print("[yellow]📂 Parsing Makefile...[/yellow]")
        parsed = parse_makefile(str(makefile_path))

        if 'error' in parsed:
            console.print(f"[red]❌ Error parsing Makefile: {parsed['error']}[/red]\n")
            return True

        all_targets = parsed.get('targets', [])

        # Find existing target names in the makemap (targets are marked with ### in markdown)
        existing_target_names = set(re.findall(r'^### (\w+)', existing_makemap, re.MULTILINE))

        # Filter to new targets only
        new_targets = [t for t in all_targets if t['name'] not in existing_target_names]

        if not new_targets:
            console.print("[green]✓ Make map is already up to date. No new targets found.[/green]\n")
            return True

        console.print(f"[green]✓ Found {len(new_targets)} new targets to add[/green]")
        for t in new_targets:
            console.print(f"[dim]  - {t['name']}[/dim]")

        # Generate the update prompt
        console.print("\n[yellow]🤖 Updating make map with LLM...[/yellow]")
        update_prompt = generate_makemap_update_prompt(new_targets, existing_makemap)

        # Use a separate chat manager for update
        update_chat_manager = ChatManager(system_prompt=config.get_system_prompt())
        update_chat_manager.add_user_message(update_prompt)
        messages = update_chat_manager.get_messages()

        spinner = Spinner("dots", text="[dim]Updating make map...[/dim]", style="cyan")

        with Live(spinner, console=console, refresh_per_second=10):
            if stream:
                full_response = ""
                for chunk in ollama_client.chat(
                    messages=messages,
                    stream=True,
                    temperature=temperature
                ):
                    full_response += chunk
            else:
                response = ollama_client.chat(
                    messages=messages,
                    stream=False,
                    temperature=temperature
                )
                full_response = response.get('message', {}).get('content', '')

        # Write the updated makemap
        with open(makemap_file_path, 'w', encoding='utf-8') as f:
            f.write(full_response)

        console.print(f"\n[bold green]✓ Make map updated successfully![/bold green]")
        console.print(f"[cyan]📄 Updated: {makemap_file_path}[/cyan]")
        console.print(f"[dim]Added {len(new_targets)} new target(s)[/dim]\n")

        # Show preview
        preview_lines = full_response.split('\n')[:20]
        console.print("[dim]Preview:[/dim]")
        console.print(CustomMarkdown('\n'.join(preview_lines) + '\n...', code_theme="monokai"))
        console.print()

    except Exception as e:
        console.print(f"\n❌ [red]Error updating make map: {e}[/red]\n")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    return True


def handle_make_execute(console, user_input_normalized, llm_checker, get_user_working_dir,
                         session_manager, config, ollama_client, mcp_client, model_registry,
                         stream, temperature, run_async, debug_print, verbose, CustomMarkdown):
    """Handle /make <prompt> command - execute make commands using natural language."""
    # Check if make mode is disabled (e.g., when using tinyollama)
    if llm_checker.is_feature_disabled('code_mode'):
        console.print("\n⚠️  [yellow]/make command is disabled when using tinyollama fallback.[/yellow]")
        console.print("[dim]This feature requires a larger model for reliable command matching.[/dim]")
        console.print("[dim]Connect to the primary Ollama server to use this feature.[/dim]\n")
        return True

    # Check if coder model is available
    if not llm_checker.has_coder_model():
        console.print("\n⚠️  [yellow]No coder model configured.[/yellow]")
        console.print("[dim]The /make command requires a coder model for optimal results.[/dim]")
        console.print("[dim]Add a coder model with: /model coder add <url> <model_name>[/dim]\n")
        return True

    # Check if Makefile exists
    makefile_path = find_makefile(get_user_working_dir())
    if not makefile_path:
        console.print(f"\n❌ [red]No Makefile found in: {get_user_working_dir()}[/red]")
        console.print("[dim]This command requires a Makefile to exist in the working directory.[/dim]\n")
        return True

    prompt_text = user_input_normalized[5:].strip()  # Extract text after "make "

    if not prompt_text:
        console.print("\n❌ [red]Usage: /make <prompt>[/red]")
        console.print("[dim]Example: /make run the tests[/dim]")
        console.print("[dim]Example: /make build the project[/dim]\n")
        return True

    # Auto-start session if not active
    if not session_manager.is_active():
        console.print("\n[cyan]ℹ️  Starting a new session for /make command...[/cyan]")
        session_manager.start_session(working_dir=get_user_working_dir())

    session_id = session_manager.get_session_id()

    # Auto-generate .makemap if it doesn't exist
    makemap_file_path = os.path.join(get_user_working_dir(), '.makemap')
    makemap_loaded_key = f'makemap_loaded_{makemap_file_path}'

    if not os.path.exists(makemap_file_path):
        console.print("[cyan]📝 Auto-generating .makemap (first time use)...[/cyan]")
        try:
            # Parse the Makefile
            parsed = parse_makefile(str(makefile_path))

            if 'error' not in parsed:
                # Generate directory tree
                tree_output = generate_tree(get_user_working_dir(), max_depth=3)

                # Generate the LLM prompt
                makemap_prompt = generate_makemap_prompt(parsed, tree_output=tree_output)

                # Use a separate chat manager for makemap generation
                makemap_chat_manager = ChatManager(system_prompt=config.get_system_prompt())
                makemap_chat_manager.add_user_message(makemap_prompt)
                messages = makemap_chat_manager.get_messages()

                spinner = Spinner("dots", text="[dim]Generating make map...[/dim]", style="cyan")

                with Live(spinner, console=console, refresh_per_second=10):
                    if stream:
                        full_response = ""
                        for chunk in ollama_client.chat(
                            messages=messages,
                            stream=True,
                            temperature=temperature
                        ):
                            full_response += chunk
                    else:
                        response = ollama_client.chat(
                            messages=messages,
                            stream=False,
                            temperature=temperature
                        )
                        full_response = response.get('message', {}).get('content', '')

                # Create makemap content
                makemap_content = f"""# Make Map

## Directory Tree

```
{tree_output}
```

{full_response}
"""
                with open(makemap_file_path, 'w', encoding='utf-8') as f:
                    f.write(makemap_content)
                console.print("[green]✓ Make map generated and saved[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not generate .makemap: {e}[/yellow]")

    # Load .makemap file into context if not already loaded
    if os.path.exists(makemap_file_path) and not session_manager.session_metadata.get(makemap_loaded_key):
        console.print("[cyan]🔧 Loading make map into context...[/cyan]")
        try:
            makemap_result = run_async(load_makemap_to_context(
                mcp_client,
                '.makemap',
                get_user_working_dir(),
                session_id
            ))
            if makemap_result.get('status') == 'success':
                console.print("[green]✓ Make map loaded[/green]")
                session_manager.session_metadata[makemap_loaded_key] = True
            else:
                debug_print(f"Makemap load warning: {makemap_result.get('message')}", icon="⚠️")
        except Exception as e:
            debug_print(f"Failed to load makemap: {e}", icon="⚠️")

    console.print(f"\n🔧 [bold cyan]Processing make command...[/bold cyan]")
    console.print(f"[dim]Prompt: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}[/dim]\n")

    # Get coder model for /make operations
    coder_model = model_registry.get_active_model('coder')
    coder_model_name = coder_model.model_name if coder_model else None
    if coder_model_name:
        debug_print(f"Using coder model for /make: {coder_model_name}", icon="🤖")

    try:
        # Call the code-command endpoint to get steps (spin_the_roulette)
        console.print("📝 [cyan]Analyzing prompt and creating execution steps...[/cyan]")

        # Build request payload
        make_command_payload = {
            "text": prompt_text,
            "session_id": session_id
        }
        if coder_model_name:
            make_command_payload["model"] = coder_model_name
        if coder_model:
            make_command_payload["ollama_url"] = coder_model.url

        response = requests.post(
            f"{POSTGRES_API_URL}/mcp-tools/code-command-simple",
            json=make_command_payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        if response.status_code != 200:
            console.print(f"[red]❌ Error from API: {response.text}[/red]\n")
            return True

        result = response.json()
        steps = result.get('steps', [])

        if not steps:
            console.print("[yellow]⚠️  No actionable steps found. Processing as direct make command...[/yellow]")
            # Fall back to direct make execution
            steps = [f"Run make {prompt_text}"]

        console.print(f"\n[green]✓ Found {len(steps)} step(s) to execute:[/green]")
        for i, step in enumerate(steps, 1):
            console.print(f"[dim]  {i}. {step}[/dim]")
        console.print()

        # Execute each step (roll_the_dice pattern)
        for step_num, step in enumerate(steps, 1):
            console.print(f"\n[bold cyan]Step {step_num}/{len(steps)}:[/bold cyan] {step[:80]}{'...' if len(step) > 80 else ''}")

            # Match step with run_make tool via semantic search
            match_response = requests.post(
                f"{POSTGRES_API_URL}/mcp-tools/retrieve",
                json={
                    "prompts": [step],
                    "threshold": 0.3
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if match_response.status_code != 200:
                console.print(f"[yellow]⚠️  Could not match step to tool: {match_response.text}[/yellow]")
                continue

            match_result = match_response.json()
            results = match_result.get('results', [])

            if results and results[0].get('best_match'):
                best_match = results[0]['best_match']
                tool_name = best_match.get('tool_name', '')
                similarity = best_match.get('similarity', 0)
                extracted_params = best_match.get('extracted_params', {})

                debug_print(f"Matched tool: {tool_name} (similarity: {similarity:.2f})", icon="🎯")

                # For make commands, prefer run_make tool
                if tool_name == 'run_make' or 'make' in step.lower():
                    # Extract target from step
                    target = extracted_params.get('target', '')
                    args = extracted_params.get('args', '')

                    # Try to extract target from the step text if not in params
                    if not target:
                        # Parse Makefile to get valid targets
                        parsed = parse_makefile(str(makefile_path))
                        valid_targets = get_target_names(parsed)

                        # Look for target in step text
                        step_lower = step.lower()
                        for t in valid_targets:
                            if t.lower() in step_lower:
                                target = t
                                break

                    console.print(f"[cyan]🔧 Executing: make {target if target else '(default)'} {args}[/cyan]")

                    # Execute make command via MCP
                    make_result = run_async(mcp_client.call_tool(
                        'coder',
                        'run_make',
                        {
                            'target': target,
                            'args': args,
                            'working_dir': get_user_working_dir()
                        }
                    ))

                    if make_result:
                        try:
                            result_data = json.loads(make_result)
                            status = result_data.get('status', 'unknown')
                            stdout = result_data.get('stdout', '')
                            stderr = result_data.get('stderr', '')
                            exit_code = result_data.get('exit_code', -1)

                            if status == 'success':
                                console.print(f"[green]✓ Make command succeeded (exit code: {exit_code})[/green]")
                            else:
                                console.print(f"[red]✗ Make command failed (exit code: {exit_code})[/red]")

                            if stdout:
                                console.print("\n[dim]Output:[/dim]")
                                console.print(stdout[:2000])
                                if len(stdout) > 2000:
                                    console.print("[dim]... (truncated)[/dim]")

                            if stderr:
                                console.print("\n[dim]Errors:[/dim]")
                                console.print(f"[red]{stderr[:1000]}[/red]")
                                if len(stderr) > 1000:
                                    console.print("[dim]... (truncated)[/dim]")

                        except json.JSONDecodeError:
                            console.print(f"[dim]{make_result}[/dim]")
                    else:
                        console.print("[yellow]⚠️  No result from make command[/yellow]")
                else:
                    # If matched a different tool, execute it
                    console.print(f"[cyan]🔧 Executing tool: {tool_name}[/cyan]")
                    tool_result = run_async(mcp_client.call_tool(
                        'coder',
                        tool_name,
                        extracted_params
                    ))
                    if tool_result:
                        try:
                            result_data = json.loads(tool_result)
                            console.print(f"[green]✓ {tool_name} completed[/green]")
                            if verbose:
                                console.print(f"[dim]{json.dumps(result_data, indent=2)[:500]}[/dim]")
                        except json.JSONDecodeError:
                            console.print(f"[dim]{tool_result[:500]}[/dim]")
            else:
                console.print("[yellow]⚠️  Could not match step to any tool[/yellow]")

        console.print(f"\n[bold green]✓ Make command processing complete![/bold green]\n")

    except requests.exceptions.Timeout:
        console.print("[red]❌ Request timed out. The server may be busy.[/red]\n")
    except requests.exceptions.ConnectionError:
        console.print("[red]❌ Could not connect to PostgreSQL API. Is the server running?[/red]")
        console.print("[dim]Start it with: make up-all[/dim]\n")
    except Exception as e:
        console.print(f"\n❌ [red]Error processing make command: {e}[/red]\n")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    return True
