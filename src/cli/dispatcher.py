"""Command dispatcher for AI CLI application.

This module routes user commands to their appropriate handlers.
"""

# Import command handlers
from src.cli.commands.basic import handle_exit, handle_clear
from src.cli.commands.working_dir import handle_wd_show, handle_wd_change
from src.cli.commands.session import (
    handle_session_start, handle_session_end, handle_session_info,
    handle_session_restore, handle_session_delete, handle_session_list,
    handle_session_clear
)
from src.cli.commands.mcp import handle_mcps, handle_mcp_tools
from src.cli.commands.model import (
    handle_models_alias, handle_models_list, handle_switch_model,
    handle_model_commands
)


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
                 verbose=False):
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
        self.combined_completer = None
    
    def dispatch(self, user_input_normalized):
        """
        Dispatch user input to appropriate command handler.
        
        Returns:
            - None if command should exit
            - True if command was handled and loop should continue
            - False if input is not a command (should be processed as chat)
        """
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
            return handle_switch_model(self.console, self.ollama_client,
                                      self.InteractiveSelector)
        
        # Handle MCP commands
        if user_input_normalized.lower() == 'mcps':
            return handle_mcps(self.list_system_mcps)
        
        if user_input_normalized.lower().startswith('mcp-tools '):
            return handle_mcp_tools(self.console, user_input_normalized,
                                   self.run_async, self.get_mcp_tools)
        
        # Handle session commands
        if user_input_normalized.lower() == 'session start':
            return handle_session_start(self.console, self.session_manager,
                                       self.get_user_working_dir)
        
        if user_input_normalized.lower() == 'session end':
            return handle_session_end(self.console, self.session_manager,
                                     self.debug_print)
        
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
        
        # Handle model commands
        if user_input_normalized.lower().startswith('model '):
            return handle_model_commands(self.console, user_input_normalized,
                                        self.model_registry, self.llm_checker,
                                        self.config, self.transformer_url)
        
        # Not a recognized command - return False to indicate chat processing
        return False
    
    def get_updated_completer(self):
        """Get the updated completer if it was changed."""
        return self.combined_completer
