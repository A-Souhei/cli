"""Initialization logic for AI CLI application."""
import os
from pathlib import Path
from prompt_toolkit.history import FileHistory

from src.config import ConfigManager
from src.config.llm_availability import LLMAvailabilityChecker
from src.config.secrets import SecretsManager
from src.model_registry import ModelRegistry
from src.model_registry.availability import ModelAvailabilityChecker
from src.embedding_client import EmbeddingClient
from src.ollama_client import OllamaClient
from src.llm_client.factory import LLMClientFactory
from src.chat import ChatManager
from src.mcp import MCPClient
from src.session import SessionManager, SessionTitleGenerator
from src.file_completer import CombinedCompleter
from src.utils.ratings import set_embedding_client
from src.utils.banner import print_banner
from migrations.migrate_models import run_migration_if_needed


class CLIInitializer:
    """Handles initialization of CLI components.
    
    Note: This class accepts several parameters for dependency injection to enable
    testing and maintain flexibility. The parameters represent external dependencies
    that need to be provided (like callbacks and configuration).
    """
    
    def __init__(self, verbose=False, debug_print=None, run_async=None, 
                 get_user_working_dir=None, console=None, history_file=None,
                 postgres_api_url=None):
        """Initialize the CLI initializer with dependencies."""
        self.verbose = verbose
        self.debug_print = debug_print
        self.run_async = run_async
        self.get_user_working_dir = get_user_working_dir
        self.console = console
        self.history_file = history_file
        self.postgres_api_url = postgres_api_url
        
    def initialize_all(self):
        """
        Initialize all CLI components.
        
        Returns:
            dict: Dictionary containing all initialized components
        """
        # Load configuration
        config = ConfigManager()

        # Load secrets (API keys)
        secrets_manager = SecretsManager()

        # Initialize ModelRegistry
        model_registry = ModelRegistry()
        
        # Initialize EmbeddingClient with fallback to local transformer
        transformer_url = os.getenv('TRANSFORMER_API_URL', 'http://localhost:16050')
        embedding_client = EmbeddingClient(
            model_registry=model_registry,
            fallback_url=transformer_url
        )
        
        # Set embedding client for ratings module
        set_embedding_client(embedding_client)
        
        # Run migration from config.yaml to Redis if needed
        run_migration_if_needed(config, model_registry, verbose=self.verbose)

        # Check model availability using new ModelAvailabilityChecker
        # Pass secrets_manager so Anthropic availability checks work
        llm_checker = ModelAvailabilityChecker(config, model_registry, secrets_manager=secrets_manager)
        llm_config = llm_checker.get_available_llm()
        
        # Initialize LLM client using factory pattern
        # Note: If no model is available, llm_config.url will be empty
        # but we still create the client (graceful degradation)
        provider = getattr(llm_config, 'provider', 'ollama')
        if provider == 'anthropic' and llm_config.model:
            try:
                ollama_client = LLMClientFactory.create_from_params(
                    provider='anthropic',
                    model_name=llm_config.model,
                    timeout=llm_config.timeout,
                    secrets_manager=secrets_manager
                )
            except ValueError:
                # API key not available, fall back to empty Ollama client
                if self.debug_print:
                    self.debug_print("Anthropic API key not found, using placeholder client", icon="⚠️")
                ollama_client = OllamaClient(
                    host='http://localhost:11434',
                    model='none',
                    timeout=llm_config.timeout
                )
        else:
            ollama_client = OllamaClient(
                host=llm_config.url if llm_config.url else 'http://localhost:11434',
                model=llm_config.model if llm_config.model else 'none',
                timeout=llm_config.timeout
            )
        
        # Initialize chat manager
        chat_manager = ChatManager(
            system_prompt=config.get_system_prompt(),
            max_context_length=config.get_max_context_length()
        )
        
        # Initialize session title generator (uses local tinyollama)
        title_generator = None
        if config.has_tinyollama_config():
            title_generator = SessionTitleGenerator(
                ollama_url=config.get_tinyollama_url(),
                model=config.get_tinyollama_model(),
                timeout=config.get_tinyollama_timeout()
            )
        
        # Initialize session manager with title generator
        session_manager = SessionManager(title_generator=title_generator)
        
        # Initialize MCP client
        # Get the project root (where main.py is located)
        project_root = Path(__file__).parent.parent.parent
        system_mcps_dir = project_root / "system_mcps"
        mcp_client = MCPClient(
            system_mcps_dir=system_mcps_dir,
            postgres_url=self.postgres_api_url,
            verbose=self.verbose
        )
        
        # Set up debug callback for MCP client
        if self.debug_print:
            mcp_client.set_debug_callback(self.debug_print)
        
        # Initialize MCP tools in database (async operation)
        if self.debug_print:
            self.debug_print("Initializing MCP tools...", icon="🔧")
        try:
            if self.run_async:
                self.run_async(mcp_client.initialize_tools_in_db())
        except Exception as e:
            if self.debug_print:
                self.debug_print(f"Failed to initialize MCP tools: {e}", icon="⚠️")
        
        # Get configuration
        temperature = config.get_temperature()
        stream = config.get_stream_enabled()
        
        # Clear the screen and show banner
        if self.console:
            self.console.clear()
            print_banner(self.console)
            
            # Show LLM status with fallback indicator
            if llm_config.is_tinyollama:
                self.console.print(f"  📦 Model: [bold yellow]{llm_config.model}[/bold yellow] [dim](fallback - remote unreachable)[/dim]")
                self.console.print(f"  🔗 Server: [dim]{llm_config.url}[/dim]")
                if llm_config.disabled_features:
                    self.console.print(f"  ⚠️  [dim]Disabled features: {', '.join(llm_config.disabled_features)}[/dim]")
            elif provider == 'anthropic':
                self.console.print(f"  📦 Model: [bold magenta]{llm_config.model}[/bold magenta] [dim](Anthropic)[/dim]")
            else:
                self.console.print(f"  📦 Model: [bold]{llm_config.model}[/bold]")
                self.console.print(f"  🔗 Server: [dim]{llm_config.url}[/dim]")
            self.console.print()
        
        # Initialize command history
        history = FileHistory(str(self.history_file)) if self.history_file else None
        
        # Get system_mcps_dir path
        system_mcps_dir = Path(__file__).parent.parent.parent / "system_mcps"
        
        # Initialize combined completer for / commands, @ file paths, and $ MCP tools
        combined_completer = CombinedCompleter(
            working_dir=self.get_user_working_dir(),
            system_mcps_dir=system_mcps_dir
        ) if self.get_user_working_dir else None
        
        # Return all initialized components
        return {
            'config': config,
            'secrets_manager': secrets_manager,
            'model_registry': model_registry,
            'embedding_client': embedding_client,
            'transformer_url': transformer_url,
            'llm_checker': llm_checker,
            'llm_config': llm_config,
            'ollama_client': ollama_client,
            'chat_manager': chat_manager,
            'session_manager': session_manager,
            'mcp_client': mcp_client,
            'temperature': temperature,
            'stream': stream,
            'history': history,
            'combined_completer': combined_completer,
        }
