## Plan: Add `/context show` and `/context clear` Commands

Add a new `/context` command with `show` and `clear` subcommands for both CLI and chat UI. The command displays or clears session context, chat history, and metadata while keeping the session active.

### Steps

1. **Create new command handler file** [`src/cli/commands/context.py`](src/cli/commands/context.py) with `handle_context_show()` and `handle_context_clear()` functions, following the pattern in [`session.py`](src/cli/commands/session.py).

2. **Register commands in dispatcher** in [`src/cli/dispatcher.py`](src/cli/dispatcher.py) — import the new handlers and add routing for `context show` and `context clear` using string matching.

3. **Add UI command handlers** in [`src/chat/routes.py`](src/chat/routes.py) — implement `handle_context_show_ui()` and `handle_context_clear_ui()` in the `/command` endpoint, returning JSON responses with formatted markdown.

4. **Update help text** in [`src/cli/commands/help.py`](src/cli/commands/help.py) — add `/context show` and `/context clear` to the banner/help output.

### Design Decisions

1. **Context scope:** `/context show` displays everything — chat messages, session metadata, loaded files/maps, and file references.

2. **Clear behavior:** `/context clear` clears everything — chat history, session history, session metadata, and file references.

3. **UI display format:** The UI returns pre-formatted markdown for consistency with other command responses.
