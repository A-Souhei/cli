"""Session command handlers for AI CLI."""


def handle_session_start(console, session_manager, get_user_working_dir):
    """Handle session start command."""
    if session_manager.is_active():
        console.print("\n⚠️  [yellow]Session already active. End current session first.[/yellow]\n")
    else:
        session_manager.start_session(working_dir=get_user_working_dir())
        console.print()
    return True  # Continue the loop


def handle_session_end(console, session_manager, debug_print):
    """Handle session end command."""
    summary = session_manager.end_session()
    if summary:
        # Auto-save session when ending
        try:
            session_manager.save_to_redis()
        except Exception as e:
            debug_print(f"Failed to save session on end: {e}", icon="⚠️")
        console.print()
    return True  # Continue the loop


def handle_session_info(console, session_manager):
    """Handle session info command."""
    info = session_manager.get_session_info()
    if info:
        console.print("\n📊 [bold]Session Info:[/bold]")
        console.print(f"  • Session ID: [cyan]{info['session_id'][:16]}...[/cyan]")
        console.print(f"  • Duration: [cyan]{int(info['duration_seconds'])}s[/cyan]")
        console.print(f"  • Interactions: [cyan]{info['num_interactions']}[/cyan]")
        console.print()
    else:
        console.print("\n⚠️  [yellow]No active session[/yellow]\n")
    return True  # Continue the loop


def handle_session_restore(console, session_manager, user_input_normalized, get_user_working_dir, WorkingDirectoryMismatchError):
    """Handle session restore command."""
    session_id = user_input_normalized[16:].strip()
    if not session_id:
        console.print("\n❌ [red]Usage: /session restore <session_id>[/red]\n")
    else:
        if session_manager.is_active():
            console.print("\n⚠️  [yellow]Please end current session before restoring.[/yellow]\n")
        else:
            try:
                success = session_manager.restore_from_redis(
                    session_id,
                    current_working_dir=get_user_working_dir()
                )
                if success:
                    console.print()
            except WorkingDirectoryMismatchError as e:
                console.print(f"\n❌ [red]Cannot restore session: working directory mismatch.[/red]")
                console.print(f"[dim]Session was created in: {e.stored_dir}[/dim]")
                console.print(f"[dim]Current directory is: {e.current_dir}[/dim]\n")
    return True  # Continue the loop


def handle_session_delete(console, session_manager, user_input_normalized):
    """Handle session delete command."""
    session_id = user_input_normalized[15:].strip()
    if not session_id:
        console.print("\n❌ [red]Usage: /session delete <session_id>[/red]\n")
    else:
        success = session_manager.delete_session(session_id)
        if success:
            console.print()
    return True  # Continue the loop


def handle_session_list(console, session_manager):
    """Handle session list command."""
    console.print("\n📋 [bold]Saved Sessions:[/bold]")
    sessions = session_manager.list_saved_sessions()
    if sessions:
        for sess in sessions:
            console.print(f"  • [cyan]{sess['session_id'][:16]}...[/cyan]")
            working_dir = sess.get('working_dir')
            if working_dir:
                if len(working_dir) > 30:
                    working_dir_info = f", Dir: {working_dir[:30]}..."
                else:
                    working_dir_info = f", Dir: {working_dir}"
            else:
                working_dir_info = ""
            console.print(f"    Interactions: {sess.get('num_interactions', 0)}, "
                        f"Started: {sess.get('start_time', 'N/A')}{working_dir_info}")
    else:
        console.print("  [dim]No saved sessions found[/dim]")
    console.print()
    return True  # Continue the loop


def handle_session_clear(console, session_manager, InteractiveSelector):
    """Handle session clear command."""
    console.print()
    try:
        # Interactive confirmation
        selector = InteractiveSelector(
            title="⚠️  Clear ALL saved sessions?",
            choices=["No", "Yes"],
            current="No"
        )
        choice = selector.show()

        if choice == "Yes":
            count = session_manager.clear_all_sessions()
            console.print(f"\n✅ [green]Cleared {count} session{'s' if count != 1 else ''}.[/green]\n")
        else:
            console.print("\n[dim]Cancelled[/dim]\n")
    except Exception as e:
        console.print(f"❌ [red]Error clearing sessions: {e}[/red]\n")
    return True  # Continue the loop
