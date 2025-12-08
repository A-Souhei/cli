"""Make command handlers for AI CLI application.

This module handles all /make commands including:
- /make map generate - Generate .makemap from Makefile
- /make map load - Load .makemap into context
- /make map update - Update .makemap with new targets
- /make <prompt> - Execute make commands using natural language (no LLM required)
"""

import os
import re
import subprocess
from rich.spinner import Spinner
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text

from src.chat import ChatManager
from src.utils.makemap import (
    find_makefile,
    parse_makefile,
    generate_makemap_prompt,
    generate_makemap_update_prompt,
    load_makemap_to_context,
    get_target_names,
)


# Regex pattern to strip ANSI escape codes
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE_PATTERN.sub('', text)


def parse_makemap_file(makemap_path: str) -> list:
    """
    Parse a .makemap file to extract commands and descriptions.
    
    Returns a list of dicts with 'command' and 'description' keys.
    """
    if not os.path.exists(makemap_path):
        return []
    
    commands = []
    try:
        with open(makemap_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse markdown table rows: | `make xxx` | description |
        # Match pattern: | `make <target>` | <description> |
        pattern = r'\|\s*`(make\s+[^`]+)`\s*\|\s*([^|]+)\|'
        matches = re.findall(pattern, content)
        
        for cmd, desc in matches:
            commands.append({
                'command': cmd.strip(),
                'description': desc.strip()
            })
    except Exception:
        pass
    
    return commands


def find_matching_command(prompt: str, commands: list) -> dict:
    """
    Find the best matching command for a given prompt.
    
    Uses simple text matching - checks if prompt words appear in description.
    Returns the best matching command dict or None.
    """
    if not commands:
        return None
    
    prompt_lower = prompt.lower()
    prompt_words = set(prompt_lower.split())
    
    best_match = None
    best_score = 0
    
    for cmd in commands:
        desc_lower = cmd['description'].lower()
        cmd_lower = cmd['command'].lower()
        
        # Score based on word overlap
        desc_words = set(desc_lower.split())
        common_words = prompt_words & desc_words
        score = len(common_words)
        
        # Bonus for exact target name match
        # Extract target from command (e.g., "make test" -> "test")
        target_match = re.search(r'make\s+(\S+)', cmd['command'])
        if target_match:
            target = target_match.group(1).lower()
            if target in prompt_lower:
                score += 5  # Strong bonus for target name match
        
        # Bonus for key action words
        action_words = ['run', 'build', 'test', 'start', 'stop', 'install', 'clean', 'help', 'show', 'list']
        for word in action_words:
            if word in prompt_lower and word in desc_lower:
                score += 2
        
        if score > best_score:
            best_score = score
            best_match = cmd
    
    # Return match only if we have some confidence
    if best_score > 0:
        return best_match
    
    return None


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

        # Generate the LLM prompt
        console.print("\n[yellow]🤖 Generating make map with LLM...[/yellow]")
        makemap_prompt = generate_makemap_prompt(parsed)

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

        # Create makemap content (commands only, no tree)
        makemap_content = full_response

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
    """Handle /make <prompt> command - execute make commands using natural language.
    
    This function:
    1. Parses the .makemap file to get commands and descriptions
    2. Matches the user prompt to the best command using text matching (no LLM)
    3. Runs the command directly with subprocess
    4. Shows the raw output
    5. Uses LLM to interpret and summarize the results
    """
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
        console.print("[dim]Example: /make show help[/dim]\n")
        return True

    # Check for .makemap file
    makemap_file_path = os.path.join(get_user_working_dir(), '.makemap')

    if not os.path.exists(makemap_file_path):
        console.print("[cyan]📝 No .makemap found. Generating one first...[/cyan]")
        console.print("[dim]Use '/make map generate' to create a make map.[/dim]\n")
        
        # Fall back to parsing Makefile directly
        parsed = parse_makefile(str(makefile_path))
        if 'error' in parsed:
            console.print(f"[red]❌ Error parsing Makefile: {parsed['error']}[/red]\n")
            return True
        
        # Build commands list from parsed Makefile
        commands = []
        for target in parsed.get('targets', []):
            cmd = f"make {target['name']}"
            desc = target.get('description', '') or f"Run {target['name']} target"
            commands.append({'command': cmd, 'description': desc})
    else:
        # Parse the .makemap file
        commands = parse_makemap_file(makemap_file_path)
        
        if not commands:
            console.print("[yellow]⚠️  Could not parse .makemap file. Falling back to Makefile.[/yellow]")
            parsed = parse_makefile(str(makefile_path))
            commands = []
            for target in parsed.get('targets', []):
                cmd = f"make {target['name']}"
                desc = target.get('description', '') or f"Run {target['name']} target"
                commands.append({'command': cmd, 'description': desc})

    if not commands:
        console.print("[red]❌ No make commands found.[/red]\n")
        return True

    console.print(f"\n🔧 [bold cyan]Finding matching make command...[/bold cyan]")
    console.print(f"[dim]Prompt: {prompt_text}[/dim]\n")

    # Find the best matching command
    match = find_matching_command(prompt_text, commands)

    if not match:
        console.print("[yellow]⚠️  No matching command found for your prompt.[/yellow]")
        console.print("\n[dim]Available commands:[/dim]")
        for cmd in commands[:10]:  # Show first 10
            console.print(f"  [cyan]{cmd['command']}[/cyan] - {cmd['description']}")
        if len(commands) > 10:
            console.print(f"  [dim]... and {len(commands) - 10} more[/dim]")
        console.print()
        return True

    command = match['command']
    description = match['description']

    console.print(f"[green]✓ Matched:[/green] [bold]{command}[/bold]")
    console.print(f"[dim]  Description: {description}[/dim]\n")

    # Execute the command
    console.print(f"[cyan]🔧 Executing: {command}[/cyan]\n")

    try:
        # Run the make command
        result = subprocess.run(
            command,
            shell=True,
            cwd=get_user_working_dir(),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Capture output for LLM interpretation (strip ANSI for clean text)
        stdout_output = result.stdout or ''
        stderr_output = result.stderr or ''
        exit_code = result.returncode
        
        # Clean versions for LLM (no ANSI codes)
        clean_stdout = strip_ansi_codes(stdout_output)
        clean_stderr = strip_ansi_codes(stderr_output)

        # Show raw output first (Rich handles ANSI codes via Text.from_ansi)
        if stdout_output:
            console.print("\n[dim]─── Output ───[/dim]")
            # Use Text.from_ansi to properly render ANSI color codes
            stdout_lines = stdout_output.split('\n')
            if len(stdout_lines) > 50:
                display_text = '\n'.join(stdout_lines[:50])
                console.print(Text.from_ansi(display_text))
                console.print(f"[dim]... ({len(stdout_lines) - 50} more lines)[/dim]")
            else:
                console.print(Text.from_ansi(stdout_output))
            console.print("[dim]──────────────[/dim]")

        if stderr_output:
            console.print("\n[dim]─── Stderr ───[/dim]")
            stderr_lines = stderr_output.split('\n')
            if len(stderr_lines) > 20:
                display_text = '\n'.join(stderr_lines[:20])
                console.print(Text.from_ansi(display_text), style="yellow")
                console.print(f"[dim]... ({len(stderr_lines) - 20} more lines)[/dim]")
            else:
                console.print(Text.from_ansi(stderr_output), style="yellow")
            console.print("[dim]──────────────[/dim]")

        # Show exit status
        if exit_code == 0:
            console.print(f"\n[bold green]✓ Command completed successfully (exit code: {exit_code})[/bold green]")
        else:
            console.print(f"\n[bold red]✗ Command failed (exit code: {exit_code})[/bold red]")

        # LLM interpretation of the output
        if ollama_client and not llm_checker.is_feature_disabled('chat'):
            console.print("\n[cyan]🤖 Analyzing output...[/cyan]")
            
            # Prepare the clean output for LLM (truncate if too long, no ANSI codes)
            max_output_chars = 4000
            truncated_stdout = clean_stdout[:max_output_chars] if len(clean_stdout) > max_output_chars else clean_stdout
            truncated_stderr = clean_stderr[:1000] if len(clean_stderr) > 1000 else clean_stderr
            
            # Build the interpretation prompt
            interpretation_prompt = f"""You just ran the command: `{command}`
Exit code: {exit_code} ({'success' if exit_code == 0 else 'failed'})

Standard output:
```
{truncated_stdout if truncated_stdout else '(no output)'}
```

{f'''Standard error:
```
{truncated_stderr}
```''' if truncated_stderr else ''}

Please provide a brief summary:
1. What did the command do?
2. Was it successful? What were the key results?
3. If it failed, what went wrong and how might it be fixed?

Keep your response concise (2-4 sentences)."""

            try:
                # Use a separate chat manager for interpretation
                interpret_chat = ChatManager(system_prompt="You are a helpful assistant that interprets command output. Be concise and focus on actionable insights.")
                interpret_chat.add_user_message(interpretation_prompt)
                messages = interpret_chat.get_messages()

                spinner = Spinner("dots", text="[dim]Interpreting results...[/dim]", style="cyan")

                with Live(spinner, console=console, refresh_per_second=10):
                    if stream:
                        full_response = ""
                        for chunk in ollama_client.chat(
                            messages=messages,
                            stream=True,
                            temperature=0.3  # Lower temperature for factual interpretation
                        ):
                            full_response += chunk
                    else:
                        response = ollama_client.chat(
                            messages=messages,
                            stream=False,
                            temperature=0.3
                        )
                        full_response = response.get('message', {}).get('content', '')

                if full_response:
                    console.print("\n[bold cyan]📋 Summary:[/bold cyan]")
                    console.print(CustomMarkdown(full_response, code_theme="monokai"))
                    
            except Exception as llm_error:
                debug_print(f"LLM interpretation failed: {llm_error}", icon="⚠️")
                # Silently continue - the raw output was already shown
        
        console.print()

    except subprocess.TimeoutExpired:
        console.print("[red]❌ Command timed out after 5 minutes.[/red]\n")
    except Exception as e:
        console.print(f"\n❌ [red]Error executing command: {e}[/red]\n")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    return True
