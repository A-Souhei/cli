"""Context command handlers for AI CLI."""
import os
import json
import httpx
from src.file_completer import extract_at_context
from src.utils.llmignore import filter_at_context


def display_ignored_items(console, ignored_items: list, item_type: str, max_display: int = 5) -> None:
    """
    Display a list of ignored files or directories from .llmignore.

    Args:
        console: Rich console for output
        ignored_items: List of ignored file/directory paths
        item_type: Type of items ('file' or 'directory')
        max_display: Maximum number of items to display before truncating
    """
    if not ignored_items:
        return

    item_label = f"{item_type}(s)" if item_type == 'file' else f"{item_type}(ies)"
    console.print(f"[yellow]⚠️  Ignored {len(ignored_items)} {item_label} by .llmignore:[/yellow]")

    for item in ignored_items[:max_display]:
        console.print(f"[dim]  • {item}[/dim]")

    if len(ignored_items) > max_display:
        remaining = len(ignored_items) - max_display
        console.print(f"[dim]  ... and {remaining} more[/dim]")


def handle_context_add(console, user_input_normalized, get_user_working_dir,
                       session_manager, mcp_client, run_async, debug_print, verbose=False):
    """
    Handle context add command.

    Add files or directories to context without triggering LLM.
    Usage:
        /context add @file - Add a specific file
        /context add @subdirectory - Add a specific directory
        /context add ALL - Add entire working directory
    """
    # Check if user wants to add ALL (entire working directory)
    # Use token matching to avoid false positives with filenames containing 'ALL'
    tokens = user_input_normalized.strip().split()
    if len(tokens) >= 3 and tokens[2].upper() == 'ALL':
        working_dir = get_user_working_dir()
        console.print(f"\n📁 [cyan]Adding entire working directory to context:[/cyan] {working_dir}")

        # Create a context with just the working directory
        at_context = {
            'files': [],
            'directories': [working_dir],
            'non_existing': []
        }
    else:
        # Extract @ prefixed paths from the command
        at_context = extract_at_context(user_input_normalized, get_user_working_dir())

        # Check if any paths were provided
        if not at_context['files'] and not at_context['directories']:
            console.print("\n⚠️  [yellow]No files or directories specified.[/yellow]")
            console.print("[dim]Usage:[/dim]")
            console.print("[dim]  /context add @file - Add a specific file[/dim]")
            console.print("[dim]  /context add @directory - Add a specific directory[/dim]")
            console.print("[dim]  /context add ALL - Add entire working directory[/dim]\n")
            return True

    # Filter @ context based on .llmignore patterns
    filtered_context, ignored_context = filter_at_context(at_context, get_user_working_dir())

    # Warn user about ignored files/directories
    if ignored_context['files'] or ignored_context['directories']:
        console.print()
        display_ignored_items(console, ignored_context['files'], 'file')
        display_ignored_items(console, ignored_context['directories'], 'directory')
        console.print()

    # Use filtered context
    at_context = filtered_context

    # Get session ID if active
    session_id = session_manager.get_session_id() if session_manager.is_active() else None

    if verbose:
        if session_id:
            debug_print(f"Adding context to session: {session_id[:16]}...", icon="🔍", style="cyan")
        else:
            debug_print("No active session - adding to temporary context", icon="⚠️", style="yellow")

    # Track what was added
    added_files = []
    added_dirs = []
    errors = []

    # Add file contexts
    for file_path in at_context['files']:
        try:
            # Add file context using MCP tool
            args = {
                'file_path': file_path,
                'working_dir': get_user_working_dir()
            }
            if session_id:
                args['session_id'] = session_id

            if verbose:
                debug_print(f"Calling MCP tool with args: {args}", icon="🔧", style="dim")

            result = run_async(mcp_client.call_tool('coder', 'add_file_context', args))

            if verbose:
                debug_print(f"MCP result length: {len(result) if result else 0}", icon="📤", style="dim")
                if result:
                    debug_print(f"MCP result preview: {result[:150]}...", icon="📄", style="dim")

            # Parse result
            if not result:
                if verbose:
                    debug_print(f"No result returned from add_file_context for {file_path}", icon="⚠️", style="yellow")
                errors.append(f"{file_path}: No result returned")
            elif not result.strip():
                if verbose:
                    debug_print(f"Empty result returned from add_file_context for {file_path}", icon="⚠️", style="yellow")
                errors.append(f"{file_path}: Empty result")
            else:
                # Check if it's a plain text error message (from MCP server)
                if result.strip().startswith("Error:"):
                    error_msg = result.strip()
                    if verbose:
                        debug_print(f"MCP error: {error_msg}", icon="⚠️", style="yellow")
                    errors.append(f"{file_path}: {error_msg}")
                else:
                    # Try to parse as JSON
                    try:
                        result_data = json.loads(result)
                        if result_data.get('status') == 'success':
                            added_files.append(file_path)
                            if verbose:
                                debug_print(f"Added file context: {file_path}", icon="📄", style="cyan")
                        else:
                            error_msg = result_data.get('error', 'Unknown error')
                            errors.append(f"{file_path}: {error_msg}")
                    except json.JSONDecodeError as e:
                        if verbose:
                            debug_print(f"Failed to parse file context result as JSON: {e}", icon="⚠️", style="yellow")
                            debug_print(f"Result content: {result[:500]}", icon="📄", style="dim")
                        errors.append(f"{file_path}: Parse error - {str(e)}")
        except Exception as e:
            if verbose:
                debug_print(f"Failed to add file context for {file_path}: {e}", icon="⚠️", style="yellow")
            errors.append(f"{file_path}: {str(e)}")

    # Add directory contexts
    for dir_path in at_context['directories']:
        try:
            # Add directory context using MCP tool
            args = {
                'dir_path': dir_path,
                'working_dir': get_user_working_dir()
            }
            if session_id:
                args['session_id'] = session_id

            result = run_async(mcp_client.call_tool('coder', 'add_directory_context', args))

            if verbose:
                debug_print(f"MCP result length: {len(result) if result else 0}", icon="📤", style="dim")
                if result:
                    debug_print(f"MCP result preview: {result[:200]}...", icon="📄", style="dim")

            # Parse result
            if not result:
                if verbose:
                    debug_print(f"No result returned from add_directory_context for {dir_path}", icon="⚠️", style="yellow")
                errors.append(f"{dir_path}: No result returned")
            elif not result.strip():
                if verbose:
                    debug_print(f"Empty result returned from add_directory_context for {dir_path}", icon="⚠️", style="yellow")
                errors.append(f"{dir_path}: Empty result")
            else:
                # Check if it's a plain text error message (from MCP server)
                if result.strip().startswith("Error:"):
                    error_msg = result.strip()
                    if verbose:
                        debug_print(f"MCP error: {error_msg}", icon="⚠️", style="yellow")
                    errors.append(f"{dir_path}: {error_msg}")
                else:
                    # Try to parse as JSON
                    try:
                        result_data = json.loads(result)
                        if result_data.get('tree_added'):
                            tree_stats = result_data.get('tree_stats', {})
                            added_dirs.append((dir_path, tree_stats))
                            if verbose:
                                debug_print(f"Added directory context: {dir_path}", icon="📁", style="cyan")
                        else:
                            error_msg = result_data.get('error', 'Unknown error')
                            errors.append(f"{dir_path}: {error_msg}")
                    except json.JSONDecodeError as parse_err:
                        if verbose:
                            debug_print(f"Failed to parse directory result as JSON: {parse_err}", icon="⚠️", style="yellow")
                            debug_print(f"Result content: {result[:500]}", icon="📄", style="dim")
                        errors.append(f"{dir_path}: Parse error - {str(parse_err)}")
        except Exception as e:
            if verbose:
                debug_print(f"Failed to add directory context for {dir_path}: {e}", icon="⚠️", style="yellow")
            errors.append(f"{dir_path}: {str(e)}")

    # Handle non-existing paths
    if at_context['non_existing']:
        console.print("\n⚠️  [yellow]Non-existing paths (skipped):[/yellow]")
        for path in at_context['non_existing']:
            console.print(f"  • [dim]{path}[/dim]")
        console.print()

    # Display summary
    console.print()
    if added_files:
        console.print(f"✓ [green]Added {len(added_files)} file(s) to context:[/green]")
        for file_path in added_files:
            console.print(f"  • [cyan]{file_path}[/cyan]")

    if added_dirs:
        console.print(f"✓ [green]Added {len(added_dirs)} directory(s) to context:[/green]")
        for dir_path, stats in added_dirs:
            files_count = stats.get('files', 0)
            dirs_count = stats.get('directories', 0)
            console.print(f"  • [cyan]{dir_path}[/cyan] [dim]({files_count} files, {dirs_count} directories)[/dim]")

    if errors and verbose:
        console.print(f"\n⚠️  [yellow]Errors ({len(errors)}):[/yellow]")
        for error in errors:
            console.print(f"  • [dim]{error}[/dim]")

    if not added_files and not added_dirs:
        console.print("⚠️  [yellow]No content was added to context.[/yellow]")

    console.print()
    return True


def handle_context_show(console, chat_manager, session_manager):
    """
    Handle context show command.
    
    Displays everything: chat messages, session metadata, loaded files/maps, and file references.
    """
    console.print("\n📋 [bold]Current Context:[/bold]\n")
    
    # Show chat context
    messages = chat_manager.get_messages()
    non_system_messages = [m for m in messages if m.get('role') != 'system']
    console.print(f"[cyan]Chat Messages:[/cyan] {len(non_system_messages)}")
    
    if non_system_messages:
        for msg in non_system_messages[-5:]:  # Show last 5 messages
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # Truncate long content
            if len(content) > 100:
                content = content[:100] + "..."
            role_color = "green" if role == "user" else "blue"
            console.print(f"  • [{role_color}]{role}[/{role_color}]: {content}")
        if len(non_system_messages) > 5:
            console.print(f"  [dim]... and {len(non_system_messages) - 5} more messages[/dim]")
    else:
        console.print("  [dim]No chat messages[/dim]")
    
    # Show session context
    console.print()
    if session_manager.is_active():
        info = session_manager.get_session_info()
        console.print("[cyan]Session:[/cyan] Active")
        console.print(f"  • ID: [cyan]{info['session_id'][:16]}...[/cyan]")
        if info.get('title'):
            console.print(f"  • Title: [cyan]{info['title']}[/cyan]")
        console.print(f"  • Duration: [cyan]{int(info['duration_seconds'])}s[/cyan]")
        console.print(f"  • Interactions: [cyan]{info['num_interactions']}[/cyan]")
        
        # Show working directory
        if session_manager.session_working_dir:
            console.print(f"  • Working Dir: [cyan]{session_manager.session_working_dir}[/cyan]")
        
        # Show session metadata (loaded maps, etc.)
        if session_manager.session_metadata:
            console.print("\n[cyan]Session Metadata:[/cyan]")
            for key, value in session_manager.session_metadata.items():
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                elif isinstance(value, (list, dict)):
                    value = f"{type(value).__name__} with {len(value)} items"
                console.print(f"  • {key}: [dim]{value}[/dim]")
        
        # Show session history summary
        if session_manager.session_history:
            console.print(f"\n[cyan]Session History:[/cyan] {len(session_manager.session_history)} interactions")
            for i, interaction in enumerate(session_manager.session_history[-3:], 1):
                prompt = interaction.get('prompt', '')[:50]
                if len(interaction.get('prompt', '')) > 50:
                    prompt += "..."
                console.print(f"  {i}. [dim]{prompt}[/dim]")
            if len(session_manager.session_history) > 3:
                console.print(f"  [dim]... and {len(session_manager.session_history) - 3} more[/dim]")

        # Show loaded files/directories from Redis context
        try:
            redis_api_url = os.getenv('REDIS_API_URL', 'http://localhost:17000')
            session_id = session_manager.get_session_id()

            with httpx.Client() as client:
                response = client.get(
                    f"{redis_api_url}/context/list",
                    params={"session_id": session_id},
                    timeout=5
                )

                if response.status_code == 200:
                    data = response.json()
                    contexts = data.get('contexts', [])

                    if contexts:
                        console.print(f"\n[cyan]Loaded Files/Directories:[/cyan] {len(contexts)}")
                        for ctx in contexts[:10]:  # Show first 10
                            path = ctx.get('path', 'Unknown')
                            context_type = ctx.get('context_type', 'unknown')
                            type_icon = "📄" if context_type == "file" else "📁" if context_type == "directory" else "📦"
                            console.print(f"  {type_icon} [cyan]{path}[/cyan]")
                        if len(contexts) > 10:
                            console.print(f"  [dim]... and {len(contexts) - 10} more[/dim]")
        except Exception as e:
            # Silently fail - context listing is optional
            pass
    else:
        console.print("[cyan]Session:[/cyan] [dim]Not active[/dim]")

    console.print()
    return True


def handle_context_clear(console, chat_manager, session_manager):
    """
    Handle context clear command.

    Clears everything: chat history, session history, session metadata, and file references.
    Session remains active but with cleared context.
    """
    # Clear chat history
    chat_manager.clear_history()

    # Clear session context (but keep session active)
    if session_manager.is_active():
        session_manager.session_history.clear()
        session_manager.session_metadata.clear()
        console.print("\n🗑️  [yellow]Context cleared[/yellow] (session still active)\n")
    else:
        console.print("\n🗑️  [yellow]Context cleared[/yellow]\n")

    return True


def handle_context_metrics(console, chat_manager, session_manager):
    """
    Handle context metrics command.

    Display metrics about the current context including size, counts, and memory usage.
    """
    console.print("\n📊 [bold]Context Metrics:[/bold]\n")

    # Chat messages metrics
    messages = chat_manager.get_messages()
    non_system_messages = [m for m in messages if m.get('role') != 'system']
    chat_size = sum(len(json.dumps(m)) for m in non_system_messages)

    console.print("[cyan]Chat Context:[/cyan]")
    console.print(f"  • Messages: [cyan]{len(non_system_messages)}[/cyan]")
    console.print(f"  • Size: [cyan]{chat_size:,}[/cyan] bytes ([cyan]{chat_size / 1024:.2f}[/cyan] KB)")
    console.print(f"  • Est. Tokens: [cyan]{chat_size // 4:,}[/cyan] (approximate)")

    # Session metrics
    console.print()
    if session_manager.is_active():
        info = session_manager.get_session_info()
        session_size = len(json.dumps(session_manager.session_metadata))
        history_size = sum(len(json.dumps(h)) for h in session_manager.session_history)

        console.print("[cyan]Session Context:[/cyan]")
        console.print(f"  • ID: [cyan]{info['session_id'][:16]}...[/cyan]")
        console.print(f"  • Interactions: [cyan]{info['num_interactions']}[/cyan]")
        console.print(f"  • Metadata Size: [cyan]{session_size:,}[/cyan] bytes")
        console.print(f"  • History Size: [cyan]{history_size:,}[/cyan] bytes")

        # Get loaded files/directories from Redis
        total_content_size = 0
        try:
            redis_api_url = os.getenv('REDIS_API_URL', 'http://localhost:17000')
            session_id = session_manager.get_session_id()

            with httpx.Client() as client:
                response = client.get(
                    f"{redis_api_url}/context/list",
                    params={"session_id": session_id},
                    timeout=5
                )

                if response.status_code == 200:
                    data = response.json()
                    contexts = data.get('contexts', [])

                    if contexts:
                        console.print()
                        console.print("[cyan]Loaded Files/Directories:[/cyan]")

                        file_count = 0
                        dir_count = 0
                        tree_count = 0
                        tool_count = 0
                        todo_list_count = 0

                        for ctx in contexts:
                            context_type = ctx.get('context_type', 'unknown')

                            # Try to get size from metadata first, fallback to content length
                            metadata = ctx.get('metadata', {})
                            size = metadata.get('size', 0)
                            if size == 0:
                                content = ctx.get('content', '')
                                size = len(content)

                            total_content_size += size

                            if context_type == 'file':
                                file_count += 1
                            elif context_type == 'directory':
                                dir_count += 1
                            elif context_type == 'directory_tree':
                                tree_count += 1
                            elif context_type == 'tools':
                                tool_count += 1
                            elif context_type == 'todo_list':
                                todo_list_count += 1

                        console.print(f"  • Files: [cyan]{file_count}[/cyan]")
                        console.print(f"  • Directories: [cyan]{dir_count}[/cyan]")
                        console.print(f"  • Trees: [cyan]{tree_count}[/cyan]")
                        if tool_count > 0:
                            console.print(f"  • Tool Collections: [cyan]{tool_count}[/cyan]")
                        if todo_list_count > 0:
                            console.print(f"  • TODO Lists: [cyan]{todo_list_count}[/cyan]")
                        console.print(f"  • Total Content Size: [cyan]{total_content_size:,}[/cyan] bytes ([cyan]{total_content_size / 1024:.2f}[/cyan] KB)")
                        console.print(f"  • Est. Tokens: [cyan]{total_content_size // 4:,}[/cyan] (approximate)")
        except Exception:
            # Silently fail - metrics are optional
            pass
    else:
        console.print("[cyan]Session:[/cyan] [dim]Not active[/dim]")

    # Total metrics
    console.print()
    total_size = chat_size
    if session_manager.is_active():
        total_size += session_size + history_size
        if 'total_content_size' in locals():
            total_size += total_content_size

    console.print("[cyan]Total Context:[/cyan]")
    console.print(f"  • Size: [cyan]{total_size:,}[/cyan] bytes ([cyan]{total_size / 1024:.2f}[/cyan] KB, [cyan]{total_size / (1024 * 1024):.2f}[/cyan] MB)")
    console.print(f"  • Est. Tokens: [cyan]{total_size // 4:,}[/cyan] (approximate)")

    console.print()
    return True


def handle_context_load_todo_list(console, session_manager, get_user_working_dir, debug_print, verbose=False, file_path=None):
    """
    Handle loading TODO_LIST from file.

    Args:
        file_path: Optional custom file path. If None, defaults to '.todo_list' in working directory.

    Reads the TODO_LIST file and adds it to context.
    """
    console.print("\n📂 [cyan]Loading TODO_LIST from file...[/cyan]")

    working_dir = get_user_working_dir()

    # Use custom file path if provided, otherwise default to .todo_list
    if file_path:
        # Remove @ prefix if present
        if file_path.startswith('@'):
            file_path = file_path[1:]

        # Handle both absolute and relative paths
        if os.path.isabs(file_path):
            todo_file_path = file_path
        else:
            todo_file_path = os.path.join(working_dir, file_path)
    else:
        todo_file_path = os.path.join(working_dir, '.todo_list')

    # Check if file exists
    if not os.path.exists(todo_file_path):
        console.print(f"\n⚠️  [yellow]File not found: {todo_file_path}[/yellow]")
        console.print("[dim]Create a TODO_LIST first or generate one with:[/dim]")
        console.print("[dim]/context add TODO_LIST <description>[/dim]\n")
        return True

    try:
        # Read the file
        with open(todo_file_path, 'r', encoding='utf-8') as f:
            todo_content = f.read()

        if not todo_content.strip():
            console.print(f"\n⚠️  [yellow]File is empty: {todo_file_path}[/yellow]\n")
            return True

        # Get session ID
        session_id = session_manager.get_session_id() if session_manager.is_active() else None

        if not session_id:
            console.print("\n⚠️  [yellow]No active session - TODO_LIST will be added to temporary context[/yellow]")
        elif verbose:
            debug_print(f"Loading TODO_LIST to session: {session_id[:16]}...", icon="📂", style="cyan")

        # Store in context
        redis_api_url = os.getenv('REDIS_API_URL', 'http://localhost:17000')

        payload = {
            'context_type': 'todo_list',
            'path': 'TODO_LIST',
            'content': todo_content,
            'metadata': {
                'size': len(todo_content),
                'loaded_from_file': True,
                'file_path': todo_file_path
            }
        }

        if session_id:
            payload['session_id'] = session_id

        with httpx.Client() as client:
            response = client.post(
                f"{redis_api_url}/context/store",
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                if result.get('status') == 'success':
                    console.print(f"\n✓ [green]TODO_LIST loaded from file successfully![/green]")
                    console.print(f"[dim]File: {todo_file_path}[/dim]")
                    console.print(f"\n💡 [dim]You can now reference 'TODO_LIST' in your prompts[/dim]\n")
                else:
                    console.print(f"\n⚠️  [yellow]Failed to store TODO_LIST: {result.get('message')}[/yellow]\n")
            else:
                console.print(f"\n⚠️  [yellow]Failed to store TODO_LIST: HTTP {response.status_code}[/yellow]\n")

    except Exception as e:
        console.print(f"\n⚠️  [yellow]Error loading TODO_LIST: {str(e)}[/yellow]\n")
        if verbose:
            debug_print(f"Exception details: {e}", icon="❌", style="red")

    return True


def handle_context_save_todo_list(console, session_manager, get_user_working_dir, debug_print, verbose=False, file_path=None):
    """
    Handle saving TODO_LIST to file.

    Args:
        file_path: Optional custom file path. If None, defaults to '.todo_list' in working directory.

    Retrieves the TODO_LIST from context and saves it to the specified file.
    """
    console.print("\n💾 [cyan]Saving TODO_LIST to file...[/cyan]")

    # Get session ID
    session_id = session_manager.get_session_id() if session_manager.is_active() else None

    if not session_id:
        console.print("\n⚠️  [yellow]No active session - cannot save TODO_LIST[/yellow]\n")
        return True

    try:
        redis_api_url = os.getenv('REDIS_API_URL', 'http://localhost:17000')

        # Retrieve TODO_LIST from context
        with httpx.Client() as client:
            response = client.get(
                f"{redis_api_url}/context/get",
                params={"session_id": session_id, "path": "TODO_LIST"},
                timeout=5
            )

            if response.status_code != 200:
                console.print("\n⚠️  [yellow]TODO_LIST not found in context[/yellow]")
                console.print("[dim]Generate a TODO_LIST first with:[/dim]")
                console.print("[dim]/context add TODO_LIST <description>[/dim]\n")
                return True

            data = response.json()
            context_data = data.get('context', {})
            todo_content = context_data.get('content', '')

            if not todo_content:
                console.print("\n⚠️  [yellow]TODO_LIST is empty[/yellow]\n")
                return True

        # Determine save path
        working_dir = get_user_working_dir()

        if file_path:
            # Remove @ prefix if present
            if file_path.startswith('@'):
                file_path = file_path[1:]

            # Handle both absolute and relative paths
            if os.path.isabs(file_path):
                todo_file_path = file_path
            else:
                todo_file_path = os.path.join(working_dir, file_path)
        else:
            todo_file_path = os.path.join(working_dir, '.todo_list')

        if verbose:
            debug_print(f"Saving to: {todo_file_path}", icon="💾", style="cyan")

        with open(todo_file_path, 'w', encoding='utf-8') as f:
            f.write(todo_content)

        console.print(f"\n✓ [green]TODO_LIST saved successfully![/green]")
        console.print(f"[dim]File: {todo_file_path}[/dim]")
        console.print(f"[dim]Size: {len(todo_content)} bytes[/dim]\n")

    except Exception as e:
        console.print(f"\n⚠️  [yellow]Error saving TODO_LIST: {str(e)}[/yellow]\n")
        if verbose:
            debug_print(f"Exception details: {e}", icon="❌", style="red")

    return True


def handle_context_generate_todo_list(console, session_manager, mcp_client, ollama_client,
                                      config, run_async, debug_print, user_request, verbose=False):
    """
    Handle TODO_LIST generation.

    Generates a strategic TODO list by:
    1. Ensuring ALL_TOOLS is loaded in context
    2. Using LLM to analyze the request and match with available tools
    3. Creating a structured plan with tool references
    4. Storing in context as TODO_LIST keyword
    """
    console.print("\n📋 [cyan]Generating TODO_LIST...[/cyan]")

    # Get session ID
    session_id = session_manager.get_session_id() if session_manager.is_active() else None

    if not session_id:
        console.print("\n⚠️  [yellow]No active session - TODO_LIST will be added to temporary context[/yellow]")
    elif verbose:
        debug_print(f"Generating TODO_LIST for session: {session_id[:16]}...", icon="🔍", style="cyan")

    try:
        redis_api_url = os.getenv('REDIS_API_URL', 'http://localhost:17000')

        # Step 1: Check if ALL_TOOLS is already loaded
        all_tools_loaded = False
        if session_id:
            with httpx.Client() as client:
                response = client.get(
                    f"{redis_api_url}/context/list",
                    params={"session_id": session_id},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    contexts = data.get('contexts', [])
                    all_tools_loaded = any(
                        ctx.get('path') == 'ALL_TOOLS' and ctx.get('context_type') == 'tools'
                        for ctx in contexts
                    )

        # Step 2: Load ALL_TOOLS if not present
        if not all_tools_loaded:
            if verbose:
                debug_print("ALL_TOOLS not found, loading...", icon="🔧", style="yellow")
            console.print("  [dim]Loading ALL_TOOLS first...[/dim]")

            # Call the ALL_TOOLS handler
            result = handle_context_add_all_tools(
                console, session_manager, mcp_client, run_async,
                debug_print, verbose=verbose
            )
            if not result:
                console.print("\n⚠️  [yellow]Failed to load ALL_TOOLS, cannot generate TODO_LIST[/yellow]\n")
                return True

        # Step 3: Get ALL_TOOLS content for LLM context
        all_tools_content = ""
        if session_id:
            with httpx.Client() as client:
                response = client.get(
                    f"{redis_api_url}/context/get",
                    params={"session_id": session_id, "path": "ALL_TOOLS"},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    context_data = data.get('context', {})
                    all_tools_content = context_data.get('content', '')

        if not all_tools_content:
            console.print("\n⚠️  [yellow]Could not retrieve ALL_TOOLS content[/yellow]\n")
            return True

        # Step 4: Generate TODO_LIST using LLM
        if verbose:
            debug_print("Calling LLM to generate TODO_LIST...", icon="🤖", style="cyan")

        console.print("  [dim]Analyzing request and matching with available tools...[/dim]")

        # Create prompt for LLM
        system_prompt = """You are a strategic planning assistant. Your task is to create a detailed TODO list for code-related tasks.

When creating the TODO list:
1. Break down the user's request into logical, actionable steps
2. For each step, identify which MCP tools from ALL_TOOLS can be used
3. Consider both tool capabilities AND your own LLM capabilities (code generation, analysis, etc.)
4. Create a comprehensive plan that leverages the best combination of tools and LLM reasoning
5. Format as a markdown list with tool references in [brackets]

Format:
# TODO_LIST: [Brief Title]

## Steps:
1. [Step description] - [Tool: tool_name OR LLM: capability]
2. [Step description] - [Tool: tool_name OR LLM: capability]
...

## Notes:
- Any important considerations
- Dependencies between steps
- Expected outcomes"""

        user_prompt = f"""Based on the following user request, create a strategic TODO list:

USER REQUEST: {user_request}

AVAILABLE TOOLS:
{all_tools_content}

Generate a comprehensive TODO list that matches each step with the appropriate tool or LLM capability."""

        # Call LLM (supports both Ollama and Anthropic)
        # The client already has the correct model configured
        temperature = 0.3  # Lower temperature for more structured output

        # Build messages for chat
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]

        # Call chat API (works for both OllamaClient and AnthropicClient)
        # Don't pass model parameter - use the client's configured model
        response = ollama_client.chat(
            messages=messages,
            stream=False,
            temperature=temperature
        )

        if not response:
            console.print("\n⚠️  [yellow]Failed to generate TODO_LIST from LLM[/yellow]\n")
            return True

        # Extract content from response
        if isinstance(response, dict):
            todo_list_content = response.get('message', {}).get('content', '')
        else:
            todo_list_content = str(response)

        if not todo_list_content:
            console.print("\n⚠️  [yellow]Empty response from LLM[/yellow]\n")
            return True

        # Step 5: Store TODO_LIST in context
        if verbose:
            debug_print("Storing TODO_LIST in context...", icon="💾", style="cyan")

        payload = {
            'context_type': 'todo_list',
            'path': 'TODO_LIST',
            'content': todo_list_content,
            'metadata': {
                'size': len(todo_list_content),
                'user_request': user_request,
                'generated_with_tools': True
            }
        }

        if session_id:
            payload['session_id'] = session_id

        with httpx.Client() as client:
            response = client.post(
                f"{redis_api_url}/context/store",
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                if result.get('status') == 'success':
                    console.print("\n✓ [green]TODO_LIST generated and stored successfully![/green]")
                    console.print("\n[cyan]Generated TODO_LIST:[/cyan]")
                    console.print(f"\n{todo_list_content}\n")
                    console.print("💡 [dim]You can now reference 'TODO_LIST' in your prompts[/dim]\n")
                else:
                    console.print(f"\n⚠️  [yellow]Failed to store TODO_LIST: {result.get('message')}[/yellow]\n")
            else:
                console.print(f"\n⚠️  [yellow]Failed to store TODO_LIST: HTTP {response.status_code}[/yellow]\n")

    except Exception as e:
        console.print(f"\n⚠️  [yellow]Error generating TODO_LIST: {str(e)}[/yellow]\n")
        if verbose:
            debug_print(f"Exception details: {e}", icon="❌", style="red")

    return True


def handle_context_add_all_tools(console, session_manager, mcp_client, run_async, debug_print, verbose=False):
    """
    Handle context add ALL_TOOLS command.

    Add all MCP tools with their descriptions to context.
    This creates a special context entry that can be referenced with the ALL_TOOLS keyword.
    """
    console.print("\n🔧 [cyan]Adding all MCP tools to context...[/cyan]")

    # Get session ID if active
    session_id = session_manager.get_session_id() if session_manager.is_active() else None

    if not session_id:
        console.print("\n⚠️  [yellow]No active session - tools will be added to temporary context[/yellow]")
    elif verbose:
        debug_print(f"Adding tools to session: {session_id[:16]}...", icon="🔍", style="cyan")

    try:
        # Get all tools from all MCP servers
        if verbose:
            debug_print("Retrieving tools from MCP servers...", icon="🔍", style="cyan")

        all_tools = run_async(mcp_client.list_tools())

        if not all_tools:
            console.print("\n⚠️  [yellow]No MCP tools found[/yellow]\n")
            return True

        # Format tools into a structured document
        tools_doc = "# MCP Tools Reference (ALL_TOOLS)\n\n"
        tools_doc += f"Total tools available: {len(all_tools)}\n\n"

        # Group tools by MCP server
        tools_by_mcp = {}
        for tool in all_tools:
            mcp_name = tool.get('mcp_name', 'unknown')
            if mcp_name not in tools_by_mcp:
                tools_by_mcp[mcp_name] = []
            tools_by_mcp[mcp_name].append(tool)

        # Build documentation
        for mcp_name, tools in tools_by_mcp.items():
            tools_doc += f"## {mcp_name.upper()} MCP Server\n\n"
            tools_doc += f"Tools: {len(tools)}\n\n"

            for tool in tools:
                tool_name = tool.get('name', 'unknown')
                description = tool.get('description', 'No description')
                input_schema = tool.get('inputSchema', {})

                tools_doc += f"### {tool_name}\n\n"
                tools_doc += f"**Description:** {description}\n\n"

                # Add input schema details
                if input_schema and 'properties' in input_schema:
                    tools_doc += "**Parameters:**\n"
                    properties = input_schema.get('properties', {})
                    required = input_schema.get('required', [])

                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'unknown')
                        param_desc = param_info.get('description', 'No description')
                        is_required = param_name in required
                        required_str = " (required)" if is_required else " (optional)"

                        tools_doc += f"- `{param_name}` ({param_type}){required_str}: {param_desc}\n"

                    tools_doc += "\n"

                tools_doc += "---\n\n"

        # Store in Redis with special marker
        redis_api_url = os.getenv('REDIS_API_URL', 'http://localhost:17000')

        payload = {
            'context_type': 'tools',
            'path': 'ALL_TOOLS',
            'content': tools_doc,
            'metadata': {
                'size': len(tools_doc),
                'tool_count': len(all_tools),
                'mcp_servers': list(tools_by_mcp.keys())
            }
        }

        if session_id:
            payload['session_id'] = session_id

        with httpx.Client() as client:
            response = client.post(
                f"{redis_api_url}/context/store",
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                if result.get('status') == 'success':
                    console.print(f"\n✓ [green]Added {len(all_tools)} tools from {len(tools_by_mcp)} MCP server(s)[/green]")
                    for mcp_name, tools in tools_by_mcp.items():
                        console.print(f"  • [cyan]{mcp_name}[/cyan]: {len(tools)} tools")
                    console.print(f"\n💡 [dim]You can now reference 'ALL_TOOLS' in your prompts to access this information[/dim]\n")
                else:
                    console.print(f"\n⚠️  [yellow]Failed to store tools: {result.get('message')}[/yellow]\n")
            else:
                console.print(f"\n⚠️  [yellow]Failed to store tools: HTTP {response.status_code}[/yellow]\n")

    except Exception as e:
        console.print(f"\n⚠️  [yellow]Error adding tools to context: {str(e)}[/yellow]\n")
        if verbose:
            debug_print(f"Exception details: {e}", icon="❌", style="red")

    return True
