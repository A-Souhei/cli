"""Command dispatcher for AI CLI application.

This module routes user commands to their appropriate handlers.
"""

# Import command handlers
from src.cli.commands.basic import handle_exit, handle_clear
from src.cli.commands.working_dir import handle_wd_show, handle_wd_change
from src.utils.banner import print_help
from src.cli.commands.session import (
    handle_session_start, handle_session_end, handle_session_info,
    handle_session_restore, handle_session_delete, handle_session_list,
    handle_session_clear
)
from src.cli.commands.context import (
    handle_context_show, handle_context_clear, handle_context_add,
    handle_context_metrics, handle_context_add_all_tools,
    handle_context_generate_todo_list, handle_context_load_todo_list,
    handle_context_save_todo_list, handle_context_generate_make_list,
    handle_context_load_make_list, handle_context_save_make_list
)
from src.cli.commands.mcp import handle_mcps, handle_mcp_tools
from src.cli.commands.model import (
    handle_models_alias, handle_models_list, handle_switch_model,
    handle_model_commands
)
from src.cli.commands.make import (
    handle_make_map_generate, handle_make_map_load,
    handle_make_map_update, handle_make_execute
)
from src.cli.commands.ignore import handle_ignore_command
from src.cli.commands.execute import handle_execute_plan


class CommandDispatcher:
    """Dispatches user input to appropriate command handlers.
    
    Note: This class has many parameters by design to maintain dependency injection
    and avoid hidden dependencies. Each parameter represents a dependency that the
    dispatcher needs to route commands. This explicit approach makes testing easier
    and dependencies clear, though it does result in a longer constructor signature.
    
    Future refactoring could group related parameters into configuration objects
    if the parameter count becomes unmanageable.
    """
    
    def __init__(self, console, config, ollama_client, chat_manager, mcp_client,
                 session_manager, model_registry, llm_checker, transformer_url,
                 get_user_working_dir, set_user_working_dir, run_async,
                 debug_print, InteractiveSelector, CombinedCompleter,
                 list_system_mcps, get_mcp_tools, WorkingDirectoryMismatchError,
                 verbose=False, stream=False, temperature=0.7, CustomMarkdown=None,
                 secrets_manager=None, auto_session=False):
        """Initialize the command dispatcher with necessary dependencies."""
        self.console = console
        self.config = config
        self.ollama_client = ollama_client
        self.chat_manager = chat_manager
        self.mcp_client = mcp_client
        self.session_manager = session_manager
        self.model_registry = model_registry
        self.llm_checker = llm_checker
        self.transformer_url = transformer_url
        self.get_user_working_dir = get_user_working_dir
        self.set_user_working_dir = set_user_working_dir
        self.run_async = run_async
        self.debug_print = debug_print
        self.InteractiveSelector = InteractiveSelector
        self.CombinedCompleter = CombinedCompleter
        self.list_system_mcps = list_system_mcps
        self.get_mcp_tools = get_mcp_tools
        self.WorkingDirectoryMismatchError = WorkingDirectoryMismatchError
        self.verbose = verbose
        self.stream = stream
        self.temperature = temperature
        self.CustomMarkdown = CustomMarkdown
        self.secrets_manager = secrets_manager
        self.auto_session = auto_session
        self.combined_completer = None
    
    def dispatch(self, user_input_normalized):
        """
        Dispatch user input to appropriate command handler.
        
        Returns:
            - None if command should exit
            - True if command was handled and loop should continue
            - False if input is not a command (should be processed as chat)
        """
        # Handle help command
        # Note: user_input_normalized has already been stripped of the '/' prefix
        # (normalization happens in main.py before dispatch), so we check for 'help' not '/help'
        if user_input_normalized.lower() == 'help':
            print_help(self.console)
            return True

        # Handle exit/quit commands
        if user_input_normalized.lower() in ['exit', 'quit']:
            handle_exit(self.console, self.mcp_client, self.run_async,
                       self.debug_print, self.verbose)
            return None

        # Handle clear command
        if user_input_normalized.lower() == 'clear':
            return handle_clear(self.console, self.chat_manager)
        
        # Handle working directory commands
        if user_input_normalized.lower() == 'wd' or user_input_normalized.lower() == 'wd show':
            return handle_wd_show(self.console, self.get_user_working_dir)
        
        if user_input_normalized.lower().startswith('wd change ') or user_input_normalized.lower().startswith('wd cd '):
            result = handle_wd_change(self.console, user_input_normalized,
                                     self.get_user_working_dir, self.set_user_working_dir,
                                     self.CombinedCompleter)
            # Update completer if it was returned
            if result and result is not True:
                self.combined_completer = result
            return True
        
        # Handle models/model commands  
        if user_input_normalized.lower().startswith('models '):
            user_input_normalized = handle_models_alias(user_input_normalized)
        
        if user_input_normalized.lower() == 'models':
            return handle_models_list(self.console, self.ollama_client)
        
        if user_input_normalized.lower() == 'switch':
            result = handle_switch_model(
                self.console, self.ollama_client,
                self.InteractiveSelector,
                model_registry=self.model_registry,
                secrets_manager=self.secrets_manager,
                llm_checker=self.llm_checker
            )
            # Check if a new client was returned (tuple with new_client)
            if isinstance(result, tuple) and len(result) == 2:
                _, new_client = result
                self.ollama_client = new_client
                return (True, new_client)  # Signal main.py to update its reference
            return result
        
        # Handle MCP commands
        if user_input_normalized.lower() == 'mcps':
            return handle_mcps(self.console, self.list_system_mcps)
        
        if user_input_normalized.lower().startswith('mcp-tools '):
            return handle_mcp_tools(self.console, user_input_normalized,
                                   self.run_async, self.get_mcp_tools)
        
        # Handle session commands
        if user_input_normalized.lower() == 'session start':
            return handle_session_start(self.console, self.session_manager,
                                       self.get_user_working_dir)
        
        if user_input_normalized.lower() == 'session end':
            return handle_session_end(self.console, self.session_manager,
                                     self.debug_print, self.auto_session,
                                     self.get_user_working_dir)
        
        if user_input_normalized.lower() == 'session info':
            return handle_session_info(self.console, self.session_manager)
        
        if user_input_normalized.lower().startswith('session restore '):
            return handle_session_restore(self.console, self.session_manager,
                                         user_input_normalized,
                                         self.get_user_working_dir,
                                         self.WorkingDirectoryMismatchError)
        
        if user_input_normalized.lower().startswith('session delete '):
            return handle_session_delete(self.console, self.session_manager,
                                        user_input_normalized)
        
        if user_input_normalized.lower() in ['session list', 'sessions list', 'sessions']:
            return handle_session_list(self.console, self.session_manager)
        
        if user_input_normalized.lower() in ['session clear', 'clear sessions']:
            return handle_session_clear(self.console, self.session_manager,
                                       self.InteractiveSelector)
        
        # Handle context commands
        if user_input_normalized.lower() == 'context show':
            return handle_context_show(self.console, self.chat_manager, self.session_manager)

        if user_input_normalized.lower() == 'context clear':
            return handle_context_clear(self.console, self.chat_manager, self.session_manager)

        if user_input_normalized.lower() == 'context metrics':
            return handle_context_metrics(self.console, self.chat_manager, self.session_manager)

        # Handle /context load TODO_LIST [@file]
        if user_input_normalized.lower().startswith('context load todo_list'):
            # Extract optional file path
            file_path = None
            parts = user_input_normalized.split(None, 3)  # ['context', 'load', 'todo_list', '@file']
            if len(parts) > 3:
                file_path = parts[3].strip()

            return handle_context_load_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=self.verbose, file_path=file_path
            )

        # Handle /context save TODO_LIST [@file]
        if user_input_normalized.lower().startswith('context save todo_list'):
            # Extract optional file path
            file_path = None
            parts = user_input_normalized.split(None, 3)  # ['context', 'save', 'todo_list', '@file']
            if len(parts) > 3:
                file_path = parts[3].strip()

            return handle_context_save_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=self.verbose, file_path=file_path
            )

        # Handle /context load MAKE_LIST [@file]
        if user_input_normalized.lower().startswith('context load make_list'):
            # Extract optional file path
            file_path = None
            parts = user_input_normalized.split(None, 3)  # ['context', 'load', 'make_list', '@file']
            if len(parts) > 3:
                file_path = parts[3].strip()

            return handle_context_load_make_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=self.verbose, file_path=file_path
            )

        # Handle /context save MAKE_LIST [@file]
        if user_input_normalized.lower().startswith('context save make_list'):
            # Extract optional file path
            file_path = None
            parts = user_input_normalized.split(None, 3)  # ['context', 'save', 'make_list', '@file']
            if len(parts) > 3:
                file_path = parts[3].strip()

            return handle_context_save_make_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=self.verbose, file_path=file_path
            )

        if user_input_normalized.lower().startswith('context add '):
            # Check for special keywords
            if 'ALL_TOOLS' in user_input_normalized.upper():
                return handle_context_add_all_tools(
                    self.console, self.session_manager, self.mcp_client,
                    self.run_async, self.debug_print, verbose=self.verbose
                )
            elif 'TODO_LIST' in user_input_normalized.upper():
                # Extract the user request (everything after TODO_LIST)
                # Find the position case-insensitively
                idx = user_input_normalized.upper().find('TODO_LIST')
                user_request = user_input_normalized[idx + len('TODO_LIST'):].strip() if idx != -1 else ""

                if not user_request:
                    self.console.print("\n⚠️  [yellow]Please provide a description for TODO_LIST generation[/yellow]")
                    self.console.print("[dim]Usage: /context add TODO_LIST <description of task>[/dim]\n")
                    return True

                return handle_context_generate_todo_list(
                    self.console, self.session_manager, self.mcp_client,
                    self.ollama_client, self.config, self.run_async,
                    self.debug_print, user_request, verbose=self.verbose
                )
            elif 'MAKE_LIST' in user_input_normalized.upper():
                # Extract the user request (everything after MAKE_LIST)
                # Find the position case-insensitively
                idx = user_input_normalized.upper().find('MAKE_LIST')
                user_request = user_input_normalized[idx + len('MAKE_LIST'):].strip() if idx != -1 else ""

                if not user_request:
                    self.console.print("\n⚠️  [yellow]Please provide a description for MAKE_LIST generation[/yellow]")
                    self.console.print("[dim]Usage: /context add MAKE_LIST <description of task>[/dim]\n")
                    return True

                return handle_context_generate_make_list(
                    self.console, self.session_manager, self.ollama_client,
                    self.config, self.run_async, self.debug_print, user_request,
                    self.get_user_working_dir, verbose=self.verbose
                )
            else:
                return handle_context_add(
                    self.console, user_input_normalized, self.get_user_working_dir,
                    self.session_manager, self.mcp_client, self.run_async,
                    self.debug_print, verbose=self.verbose
                )
        
        # Handle ignore commands
        if user_input_normalized.lower().startswith('ignore '):
            return handle_ignore_command(self.console, self.get_user_working_dir(),
                                        user_input_normalized)
        
        # Handle model commands
        if user_input_normalized.lower().startswith('model '):
            return handle_model_commands(self.console, user_input_normalized,
                                        self.model_registry, self.llm_checker,
                                        self.config, self.transformer_url,
                                        secrets_manager=self.secrets_manager)
        
        # Handle /make map generate command
        if user_input_normalized.lower().startswith('make map generate'):
            return handle_make_map_generate(
                self.console, user_input_normalized, self.llm_checker,
                self.get_user_working_dir, self.config, self.ollama_client,
                self.stream, self.temperature, self.verbose, self.CustomMarkdown
            )
        
        # Handle /make map load command
        if user_input_normalized.lower() == 'make map load':
            return handle_make_map_load(
                self.console, self.get_user_working_dir, self.session_manager,
                self.mcp_client, self.run_async, self.verbose
            )
        
        # Handle /make map update command
        if user_input_normalized.lower().startswith('make map update'):
            return handle_make_map_update(
                self.console, self.llm_checker, self.get_user_working_dir,
                self.config, self.ollama_client, self.stream, self.temperature,
                self.verbose, self.CustomMarkdown
            )
        
        # Handle /make <prompt> command - execute make commands using natural language
        if user_input_normalized.lower().startswith('make ') and not user_input_normalized.lower().startswith('make map'):
            return handle_make_execute(
                self.console, user_input_normalized, self.llm_checker,
                self.get_user_working_dir, self.session_manager, self.config,
                self.ollama_client, self.mcp_client, self.model_registry,
                self.stream, self.temperature, self.run_async, self.debug_print,
                self.verbose, self.CustomMarkdown
            )

        # Handle /execute command - execute TODO_LIST or MAKE_LIST plans
        if user_input_normalized.lower().startswith('execute '):
            return handle_execute_plan(
                self.console, self.session_manager, self.mcp_client,
                self.get_user_working_dir, self.run_async, user_input_normalized,
                self.debug_print, self.CustomMarkdown, self.ollama_client,
                self.config, self.stream, self.temperature
            )

        # Not a recognized command - return False to indicate chat processing
        return False
    
    def get_updated_completer(self):
        """Get the updated completer if it was changed."""
        return self.combined_completer
