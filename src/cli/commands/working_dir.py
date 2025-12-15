"""Working directory command handlers for AI CLI."""
import os
from pathlib import Path


def handle_wd_show(console, get_user_working_dir):
    """Handle wd/wd show command."""
    console.print(f"\n📂 [bold]Working Directory:[/bold] [cyan]{get_user_working_dir()}[/cyan]\n")
    return True  # Continue the loop


def handle_wd_change(console, user_input_normalized, get_user_working_dir, set_user_working_dir, CombinedCompleter):
    """Handle wd change/wd cd command."""
    # Extract path - handle both 'wd change' and 'wd cd'
    if user_input_normalized.lower().startswith('wd change '):
        new_path = user_input_normalized[10:].strip()
    else:
        new_path = user_input_normalized[6:].strip()
    
    if not new_path:
        console.print("\n❌ [red]Usage: /wd change <path>[/red]")
        console.print("[dim]Example: /wd change ~/projects/myapp[/dim]\n")
        return True
    
    # Expand ~ to home directory
    new_path = os.path.expanduser(new_path)
    
    if set_user_working_dir(new_path):
        console.print(f"\n✓ [green]Working directory changed to:[/green] [cyan]{get_user_working_dir()}[/cyan]")
        # Update file completer with new working directory
        system_mcps_dir = Path(__file__).parent.parent.parent.parent / "system_mcps"
        combined_completer = CombinedCompleter(
            working_dir=get_user_working_dir(),
            system_mcps_dir=system_mcps_dir
        )
        console.print("[dim]File completion paths updated[/dim]\n")
        return combined_completer  # Return updated completer
    else:
        console.print(f"\n❌ [red]Directory not found:[/red] {new_path}\n")
        return True
