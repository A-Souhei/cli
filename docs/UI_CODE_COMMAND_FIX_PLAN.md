## Plan: Fix /code Command Execution in UI

The `/code` command in the UI currently only plans steps but doesn't execute them, showing "Command completed." instead of actual results. This plan addresses the full implementation to match CLI functionality.

### Steps

1. Create `/mcp-tools/execute` endpoint in [app.py](../src/postgresql/app/app.py) to execute individual MCP tools via JSON-RPC, reusing logic from `call_mcp_tool()` function.

2. Update `handle_code_command()` in [chat.py](../src/ui/routes/chat.py) to loop through planned steps, match each with tools via `/mcp-tools/retrieve`, and execute via the new endpoint.

3. Add code generation support by calling the Ollama API before execution for tools like `write_python_code`, `edit_python_code`, similar to CLI's LLM generation flow.

4. Implement session integration in the UI handler using `get_session_manager()` to properly track and save `/code` command interactions.

5. (Optional) Add Server-Sent Events (SSE) endpoint in [chat.py](../src/ui/routes/chat.py) for progressive step-by-step result display in the frontend.

### Further Considerations

1. **MCP Server Process Management**: Should the API spawn MCP server processes on-demand, or should they run persistently? Persistent is more reliable for the UI use case.

2. **Code Generation Model**: Which Ollama model should the API use for code generation? Current CLI uses the chat model, but UI may need a configurable coder model.

3. **Error Handling Strategy**: Should execution stop on first error, or continue and report all failures at the end?