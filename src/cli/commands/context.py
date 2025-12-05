"""Context command handlers for AI CLI."""


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
