"""Model command handlers for AI CLI."""
import requests

from src.llm_client.factory import LLMClientFactory


def handle_models_alias(user_input_normalized):
    """Convert /models command to /model command."""
    # Convert /models <cmd> to /model <cmd>
    return 'model ' + user_input_normalized[7:]


def handle_models_list(console, ollama_client):
    """Handle models list command."""
    console.print("\n📋 [bold]Available models:[/bold]")
    try:
        models = ollama_client.list_models()
        for model in models:
            if model == ollama_client.model:
                console.print(f"  • {model} [cyan](current)[/cyan]")
            else:
                console.print(f"  • {model}")
    except Exception as e:
        console.print(f"❌ [red]Error listing models: {e}[/red]")
    console.print()
    return True  # Continue the loop


def handle_switch_model(console, ollama_client, InteractiveSelector, model_registry=None,
                        secrets_manager=None, llm_checker=None):
    """Handle switch command for model selection.

    Uses model registry first (to include Anthropic models),
    falls back to Ollama list if registry is unavailable.

    Returns:
        tuple: (True, new_client) if model was switched and client recreated
        True: if command handled but no client change needed
    """
    console.print()
    try:
        models = []
        # Track what the actual running client is using (not just registry active status)
        # This is important when fallback is in use but an anthropic model is "active" in registry
        actual_client_model = ollama_client.model if ollama_client else None
        actual_client_type = type(ollama_client).__name__ if ollama_client else None

        # Determine current_model based on actual client, not registry
        current_model = None
        if actual_client_type == 'AnthropicClient':
            current_model = f"{actual_client_model} (anthropic)"
        elif actual_client_model:
            # Check if it's a registered Ollama model
            current_model = f"{actual_client_model} (ollama)"
            # Or just the raw model name if not in registry format
            if model_registry:
                for model_type in ['general', 'coder']:
                    for m in model_registry.list_models(model_type):
                        if m.model_name == actual_client_model and getattr(m, 'provider', 'ollama') == 'ollama':
                            current_model = f"{actual_client_model} (ollama)"
                            break

        # First, try to get models from registry (includes Anthropic)
        if model_registry:
            for model_type in ['general', 'coder']:
                registered_models = model_registry.list_models(model_type)
                for m in registered_models:
                    provider = getattr(m, 'provider', 'ollama')
                    display_name = f"{m.model_name} ({provider})"
                    if display_name not in models:
                        models.append(display_name)
        
        # Also try to get Ollama models if available
        try:
            if ollama_client:
                ollama_models = ollama_client.list_models()
                for m in ollama_models:
                    if m not in models and f"{m} (ollama)" not in models:
                        models.append(m)
        except Exception:
            # Ollama unavailable, continue with registry models only
            pass
        
        if not models:
            console.print("❌ [red]No models available[/red]")
            console.print("[dim]Add a model with: /model general add anthropic <model_name>[/dim]\n")
            return True

        # Show interactive selector
        selector = InteractiveSelector(
            title="🔄 Select Model",
            choices=models,
            current=current_model
        )
        selected = selector.show()

        if selected and selected != current_model:
            # Determine if this is a registry model or raw Ollama model
            if model_registry and '(' in selected:
                # This is a registry model like "claude-3-5-sonnet (anthropic)"
                model_name = selected.split(' (')[0]
                # Find and activate this model in registry
                for model_type in ['general', 'coder']:
                    registered_models = model_registry.list_models(model_type)
                    for m in registered_models:
                        if m.model_name == model_name:
                            model_registry.set_active_model(m.model_id)
                            # Reset llm_checker cache so next call gets fresh config
                            if llm_checker:
                                llm_checker.reset()
                            # Create new client based on provider
                            provider = getattr(m, 'provider', 'ollama')
                            try:
                                new_client = LLMClientFactory.create_client(
                                    m, secrets_manager=secrets_manager
                                )
                                console.print(f"\\n✓ [green]Switched to model:[/green] [bold]{selected}[/bold]\\n")
                                return (True, new_client)
                            except ValueError as e:
                                console.print(f"\\n❌ [red]Failed to switch: {e}[/red]\\n")
                                return True

            # Otherwise, update the ollama client directly (raw Ollama model)
            if ollama_client:
                # Extract just the model name if it has provider suffix
                raw_model = selected.split(' (')[0] if ' (' in selected else selected
                ollama_client.model = raw_model
                console.print(f"\\n✓ [green]Switched to model:[/green] [bold]{selected}[/bold]\\n")
        elif selected:
            console.print(f"\\n[dim]Already using {selected}[/dim]\\n")
        else:
            console.print("\\n[dim]Cancelled[/dim]\\n")
    except Exception as e:
        console.print(f"\\n❌ [red]Error switching model: {e}[/red]\\n")
    return True  # Continue the loop


def handle_model_commands(console, user_input_normalized, model_registry, llm_checker, config, transformer_url, secrets_manager=None):
    """Handle all /model subcommands.
    
    Args:
        secrets_manager: SecretsManager for API keys (needed for Anthropic availability checks)
    """
    model_cmd = user_input_normalized[6:].strip()

    # /model status
    if model_cmd == 'status':
        console.print("\n📊 [bold]Model Status:[/bold]\n")

        # General model
        general = model_registry.get_active_model('general')
        if general:
            availability_icon = "✓" if llm_checker.check_model_availability(general.model_id, secrets_manager=secrets_manager) else "✗"
            provider = getattr(general, 'provider', 'ollama')
            console.print(f"[bold cyan]General Model:[/bold cyan]")
            if provider == 'anthropic':
                console.print(f"  {availability_icon} [magenta]{provider}[/magenta] [cyan]{general.model_name}[/cyan]")
            else:
                console.print(f"  {availability_icon} [cyan]{general.model_name}[/cyan] @ {general.url}")
            console.print(f"  ID: [dim]{general.model_id}[/dim]")
        else:
            console.print("[bold cyan]General Model:[/bold cyan] [yellow]Not configured[/yellow]")
            console.print("  Use: [dim]/model general add <url> <model_name>[/dim]")
            console.print("       [dim]/model general add anthropic <model_name>[/dim]")

        console.print()

        # Coder model
        coder = model_registry.get_active_model('coder')
        if coder:
            availability_icon = "✓" if llm_checker.check_model_availability(coder.model_id, secrets_manager=secrets_manager) else "✗"
            provider = getattr(coder, 'provider', 'ollama')
            console.print(f"[bold cyan]Coder Model:[/bold cyan]")
            if provider == 'anthropic':
                console.print(f"  {availability_icon} [magenta]{provider}[/magenta] [cyan]{coder.model_name}[/cyan]")
            else:
                console.print(f"  {availability_icon} [cyan]{coder.model_name}[/cyan] @ {coder.url}")
            console.print(f"  ID: [dim]{coder.model_id}[/dim]")
        else:
            console.print("[bold cyan]Coder Model:[/bold cyan] [yellow]Not configured[/yellow]")
            console.print("  Use: [dim]/model coder add <url> <model_name>[/dim]")
            console.print("       [dim]/model coder add anthropic <model_name>[/dim]")

        console.print()

        # Embedding model
        embedding = model_registry.get_active_embedding_model()
        if embedding:
            console.print(f"[bold cyan]Embedding Model:[/bold cyan]")
            if embedding.model_name:
                console.print(f"  ✓ [cyan]{embedding.model_name}[/cyan] @ {embedding.url}")
            else:
                console.print(f"  ✓ [cyan]Generic service[/cyan] @ {embedding.url}")
            if embedding.embedding_dimensions:
                console.print(f"  Dimensions: [cyan]{embedding.embedding_dimensions}[/cyan]")
            console.print(f"  ID: [dim]{embedding.model_id}[/dim]")
        else:
            console.print("[bold cyan]Embedding Model:[/bold cyan] [yellow]Using fallback (local transformer)[/yellow]")
            console.print(f"  Fallback URL: [dim]{transformer_url}[/dim]")
            console.print("  Use: [dim]/model embedding add <url> [model_name][/dim]")

        console.print()

        # Fallback
        if config.has_tinyollama_config():
            tinyollama_url = config.get_tinyollama_url()
            tinyollama_available = llm_checker.check_ollama_available(tinyollama_url)
            fallback_icon = "✓" if tinyollama_available else "✗"
            console.print(f"[bold cyan]Fallback (Tinyollama):[/bold cyan]")
            console.print(f"  {fallback_icon} [cyan]{config.get_tinyollama_model()}[/cyan] @ {tinyollama_url}")

        console.print()
        return True

    # /model list or /model <type> list
    parts = model_cmd.split()
    if len(parts) == 1 and parts[0] == 'list':
        # List all models
        console.print("\n📋 [bold]All Models:[/bold]\n")
        for model_type in ['general', 'coder', 'embedding']:
            models = model_registry.list_models(model_type)
            console.print(f"[bold cyan]{model_type.capitalize()} Models:[/bold cyan]")
            if models:
                for m in models:
                    active_marker = "→" if m.is_active else " "
                    if model_type == 'embedding':
                        console.print(f"  {active_marker} [cyan]External service[/cyan] @ {m.url}")
                        if m.embedding_dimensions:
                            console.print(f"    Dimensions: [cyan]{m.embedding_dimensions}[/cyan]")
                    else:
                        console.print(f"  {active_marker} [cyan]{m.model_name}[/cyan] @ {m.url}")
                    console.print(f"    ID: [dim]{m.model_id}[/dim]")
            else:
                console.print("  [dim]No models configured[/dim]")
            console.print()
        return True

    # /model <type> list
    if len(parts) == 2 and parts[1] == 'list':
        model_type = parts[0]
        if model_type not in ['general', 'coder', 'embedding']:
            console.print(f"\n❌ [red]Invalid model type: {model_type}[/red]")
            console.print("[dim]Valid types: general, coder, embedding[/dim]\n")
            return True

        models = model_registry.list_models(model_type)
        console.print(f"\n📋 [bold]{model_type.capitalize()} Models:[/bold]\n")
        if models:
            for m in models:
                active_marker = "→" if m.is_active else " "
                if model_type == 'embedding':
                    console.print(f"  {active_marker} [cyan]External service[/cyan] @ {m.url}")
                    if m.embedding_dimensions:
                        console.print(f"    Dimensions: [cyan]{m.embedding_dimensions}[/cyan]")
                else:
                    console.print(f"  {active_marker} [cyan]{m.model_name}[/cyan] @ {m.url}")
                console.print(f"    ID: [dim]{m.model_id}[/dim]")
        else:
            console.print("  [dim]No models configured[/dim]")
        console.print()
        return True

    # /model embedding add <url> [model_name] [timeout]
    if len(parts) >= 3 and parts[0] == 'embedding' and parts[1] == 'add':
        url = parts[2]
        model_name = ''
        timeout = 60
        
        # Check if model_name is provided (for Ollama)
        if len(parts) > 3:
            # Check if it's a timeout (number) or model name
            if parts[3].isdigit():
                timeout = int(parts[3])
            else:
                model_name = parts[3]
                if len(parts) > 4 and parts[4].isdigit():
                    timeout = int(parts[4])

        console.print(f"\n🔍 [yellow]Testing embedding service at {url}...[/yellow]")
        if model_name:
            console.print(f"   [dim]Model: {model_name}[/dim]")
        
        # Test the embedding service with a sample text
        try:
            test_data = None
            service_type = None
            
            # If model_name is provided, try Ollama API first
            if model_name:
                try:
                    test_response = requests.post(
                        f"{url}/api/embed",
                        json={"model": model_name, "input": "test"},
                        timeout=15
                    )
                    if test_response.status_code == 200:
                        test_data = test_response.json()
                        service_type = 'ollama'
                except requests.exceptions.RequestException:
                    pass
            
            # Try GET first (local transformer service format)
            if test_data is None:
                try:
                    test_response = requests.get(
                        f"{url}/embed",
                        params={"text": "test"},
                        timeout=10
                    )
                    if test_response.status_code == 200:
                        test_data = test_response.json()
                        service_type = 'transformer'
                except requests.exceptions.RequestException:
                    pass
            
            # If GET failed, try POST /embed (generic external services format)
            if test_data is None or ('embedding' not in test_data and 'embeddings' not in test_data):
                try:
                    test_response = requests.post(
                        f"{url}/embed",
                        json={"text": "test"},
                        timeout=10
                    )
                    if test_response.status_code == 200:
                        test_data = test_response.json()
                        service_type = 'generic'
                except requests.exceptions.RequestException:
                    pass
            
            if test_data is None or ('embedding' not in test_data and 'embeddings' not in test_data):
                console.print(f"❌ [red]Could not get embeddings from service[/red]")
                console.print(f"[dim]Tried: Ollama API, GET /embed, POST /embed[/dim]\n")
                return True
            
            # Auto-detect dimensions
            embedding = None
            if 'embedding' in test_data:
                embedding = test_data['embedding']
            elif 'embeddings' in test_data and test_data['embeddings']:
                embedding = test_data['embeddings'][0]
            
            if embedding and isinstance(embedding, list) and len(embedding) > 0:
                dimensions = len(embedding)
            else:
                dimensions = None
            
            model = model_registry.add_model(
                model_type='embedding',
                url=url,
                model_name=model_name,  # Store model name for Ollama
                timeout=timeout,
                set_active=True,
                embedding_dimensions=dimensions
            )
            console.print(f"\n✅ [green]Embedding model registered successfully![/green]")
            console.print(f"  ID: [cyan]{model.model_id}[/cyan]")
            console.print(f"  URL: [cyan]{model.url}[/cyan]")
            if model_name:
                console.print(f"  Model: [cyan]{model_name}[/cyan]")
            console.print(f"  Service Type: [cyan]{service_type}[/cyan]")
            if dimensions:
                console.print(f"  Dimensions: [cyan]{dimensions}[/cyan] (auto-detected)")
            console.print(f"  Timeout: [cyan]{timeout}s[/cyan]")
            console.print(f"  Status: [green]Active[/green]\n")
        except requests.exceptions.RequestException as e:
            console.print(f"❌ [red]Cannot reach embedding service at {url}[/red]")
            console.print(f"[dim]Error: {str(e)}[/dim]\n")
        except Exception as e:
            console.print(f"\n❌ [red]Failed to add embedding model: {e}[/red]\n")
        return True

    # /model <type> add <url_or_provider> <model_name>
    # Supports:
    #   /model general add http://localhost:11434 llama3.1:8b  -> Ollama
    #   /model general add anthropic claude-sonnet-4-20250514  -> Anthropic
    if len(parts) >= 3 and parts[1] == 'add':
        model_type = parts[0]
        first_arg = parts[2]
        timeout = 120

        if model_type not in ['general', 'coder']:
            console.print(f"\n❌ [red]Invalid model type: {model_type}[/red]")
            console.print("[dim]Valid types: general, coder[/dim]\n")
            return True

        # Auto-detect provider based on first argument
        if first_arg.lower() == 'anthropic':
            # Anthropic provider
            if len(parts) < 4:
                console.print(f"\n❌ [red]Model name required for Anthropic[/red]")
                console.print("[dim]Usage: /model {model_type} add anthropic <model_name>[/dim]\n")
                return True

            model_name = parts[3]
            provider = 'anthropic'
            url = ''  # Anthropic doesn't need a URL

            console.print(f"\n🔍 [yellow]Adding Anthropic model: {model_name}...[/yellow]")
            console.print(f"[dim]Note: Availability check requires valid API key in secrets.yaml[/dim]")

            try:
                model = model_registry.add_model(
                    model_type=model_type,
                    url=url,
                    model_name=model_name,
                    timeout=timeout,
                    set_active=True,
                    provider=provider
                )
                console.print(f"\n✅ [green]Anthropic model registered successfully![/green]")
                console.print(f"  ID: [cyan]{model.model_id}[/cyan]")
                console.print(f"  Type: [cyan]{model.model_type}[/cyan]")
                console.print(f"  Provider: [magenta]{provider}[/magenta]")
                console.print(f"  Model: [cyan]{model.model_name}[/cyan]")
                console.print(f"  Status: [green]Active[/green]\n")

                # Refresh llm_checker cache
                llm_checker.reset()
            except Exception as e:
                console.print(f"\n❌ [red]Failed to add model: {e}[/red]\n")
            return True

        elif first_arg.startswith('http://') or first_arg.startswith('https://'):
            # Ollama provider (URL provided)
            if len(parts) < 4:
                console.print(f"\n❌ [red]Model name required[/red]")
                console.print(f"[dim]Usage: /model {model_type} add <url> <model_name>[/dim]\n")
                return True

            url = first_arg
            model_name = parts[3]
            provider = 'ollama'

            console.print(f"\n🔍 [yellow]Checking availability of {model_name} @ {url}...[/yellow]")
            if not llm_checker.check_ollama_available(url):
                console.print(f"❌ [red]Cannot reach Ollama service at {url}[/red]\n")
                return True

            try:
                model = model_registry.add_model(
                    model_type=model_type,
                    url=url,
                    model_name=model_name,
                    timeout=timeout,
                    set_active=True,
                    provider=provider
                )
                console.print(f"\n✅ [green]Model registered successfully![/green]")
                console.print(f"  ID: [cyan]{model.model_id}[/cyan]")
                console.print(f"  Type: [cyan]{model.model_type}[/cyan]")
                console.print(f"  Provider: [cyan]{provider}[/cyan]")
                console.print(f"  Model: [cyan]{model.model_name}[/cyan]")
                console.print(f"  URL: [cyan]{model.url}[/cyan]")
                console.print(f"  Status: [green]Active[/green]\n")

                # Refresh llm_checker cache
                llm_checker.reset()
            except Exception as e:
                console.print(f"\n❌ [red]Failed to add model: {e}[/red]\n")
            return True

        else:
            console.print(f"\n❌ [red]Invalid format[/red]")
            console.print("[dim]Usage:[/dim]")
            console.print(f"  [dim]/model {model_type} add <url> <model_name>         (Ollama)[/dim]")
            console.print(f"  [dim]/model {model_type} add anthropic <model_name>    (Anthropic)[/dim]\n")
            return True

    # /model <type> use <model_id>
    if len(parts) == 3 and parts[1] == 'use':
        model_type = parts[0]
        model_id = parts[2]

        if model_type not in ['general', 'coder', 'embedding']:
            console.print(f"\n❌ [red]Invalid model type: {model_type}[/red]")
            console.print("[dim]Valid types: general, coder, embedding[/dim]\n")
            return True

        try:
            success = model_registry.set_active_model(model_id)
            if success:
                model = model_registry.get_model(model_id)
                console.print(f"\n✅ [green]Active {model_type} model set to:[/green]")
                if model_type == 'embedding':
                    console.print(f"  [cyan]External service[/cyan] @ {model.url}")
                    if model.embedding_dimensions:
                        console.print(f"  Dimensions: [cyan]{model.embedding_dimensions}[/cyan]")
                else:
                    console.print(f"  [cyan]{model.model_name}[/cyan] @ {model.url}")
                console.print()

                # Refresh llm_checker cache
                llm_checker.reset()
            else:
                console.print(f"\n❌ [red]Model not found: {model_id}[/red]\n")
        except Exception as e:
            console.print(f"\n❌ [red]Failed to set active model: {e}[/red]\n")
        return True

    # /model <type> remove <model_id>
    if len(parts) == 3 and parts[1] == 'remove':
        model_type = parts[0]
        model_id = parts[2]

        if model_type not in ['general', 'coder', 'embedding']:
            console.print(f"\n❌ [red]Invalid model type: {model_type}[/red]")
            console.print("[dim]Valid types: general, coder, embedding[/dim]\n")
            return True

        try:
            model = model_registry.get_model(model_id)
            if not model:
                console.print(f"\n❌ [red]Model not found: {model_id}[/red]\n")
                return True

            success = model_registry.remove_model(model_id)
            if success:
                console.print(f"\n✅ [green]Removed model:[/green]")
                if model_type == 'embedding':
                    console.print(f"  [cyan]External service[/cyan] @ {model.url}\n")
                else:
                    console.print(f"  [cyan]{model.model_name}[/cyan] @ {model.url}\n")

                # Refresh llm_checker cache
                llm_checker.reset()
            else:
                console.print(f"\n❌ [red]Failed to remove model[/red]\n")
        except Exception as e:
            console.print(f"\n❌ [red]Failed to remove model: {e}[/red]\n")
        return True

    # /model check [model_id]
    if parts[0] == 'check':
        if len(parts) == 1:
            # Check all active models
            console.print("\n🔍 [bold]Checking all active models...[/bold]\n")
            for model_type in ['general', 'coder']:
                model = model_registry.get_active_model(model_type)
                if model:
                    is_available = llm_checker.check_model_availability(model.model_id, secrets_manager=secrets_manager)
                    status_icon = "✓" if is_available else "✗"
                    status_text = "[green]Available[/green]" if is_available else "[red]Unavailable[/red]"
                    console.print(f"{status_icon} {model_type.capitalize()}: [cyan]{model.model_name}[/cyan] - {status_text}")
                else:
                    console.print(f"  {model_type.capitalize()}: [yellow]Not configured[/yellow]")
            console.print()
        else:
            # Check specific model
            model_id = parts[1]
            model = model_registry.get_model(model_id)
            if not model:
                console.print(f"\n❌ [red]Model not found: {model_id}[/red]\n")
            else:
                console.print(f"\n🔍 [yellow]Checking {model.model_name}...[/yellow]")
                try:
                    is_available = llm_checker.check_model_availability(model_id, secrets_manager=secrets_manager)
                    if is_available:
                        console.print(f"✓ [green]Model is available[/green]\n")
                    else:
                        console.print(f"✗ [red]Model is unavailable[/red]")
                        console.print(f"[dim]Possible reasons:[/dim]")
                        console.print(f"[dim]  - Ollama service at {model.url} is not running[/dim]")
                        console.print(f"[dim]  - Network connection issues[/dim]")
                        console.print(f"[dim]  - Model '{model.model_name}' not pulled on server[/dim]")
                        console.print(f"[dim]  - Timeout or authentication failure[/dim]\n")
                except Exception as e:
                    console.print(f"✗ [red]Model is unavailable[/red]")
                    console.print(f"[dim]Error: {str(e)}[/dim]\n")
        return True

    # /model ping
    if parts[0] == 'ping':
        console.print("\n🏓 [bold]Pinging all active models...[/bold]\n")

        results = {
            'available': [],
            'unavailable': [],
            'not_configured': []
        }

        # Check general model
        general = model_registry.get_active_model('general')
        if general:
            console.print(f"[bold cyan]General Model:[/bold cyan]")
            console.print(f"  Pinging [cyan]{general.model_name}[/cyan] @ {general.url}...", end=" ")
            is_available = llm_checker.check_model_availability(general.model_id, secrets_manager=secrets_manager)
            if is_available:
                console.print("[green]✓ OK[/green]")
                results['available'].append(('general', general))
            else:
                console.print("[red]✗ FAILED[/red]")
                results['unavailable'].append(('general', general))
        else:
            console.print("[bold cyan]General Model:[/bold cyan] [yellow]Not configured[/yellow]")
            results['not_configured'].append('general')

        console.print()

        # Check coder model
        coder = model_registry.get_active_model('coder')
        if coder:
            console.print(f"[bold cyan]Coder Model:[/bold cyan]")
            console.print(f"  Pinging [cyan]{coder.model_name}[/cyan] @ {coder.url}...", end=" ")
            is_available = llm_checker.check_model_availability(coder.model_id, secrets_manager=secrets_manager)
            if is_available:
                console.print("[green]✓ OK[/green]")
                results['available'].append(('coder', coder))
            else:
                console.print("[red]✗ FAILED[/red]")
                results['unavailable'].append(('coder', coder))
        else:
            console.print("[bold cyan]Coder Model:[/bold cyan] [yellow]Not configured[/yellow]")
            results['not_configured'].append('coder')

        console.print()

        # Check embedding model
        embedding = model_registry.get_active_embedding_model()
        if embedding:
            console.print(f"[bold cyan]Embedding Model:[/bold cyan]")
            display_name = embedding.model_name if embedding.model_name else "External service"
            console.print(f"  Pinging [cyan]{display_name}[/cyan] @ {embedding.url}...", end=" ")

            # Test embedding service
            try:
                test_success = False

                # Try Ollama API if model_name is set
                if embedding.model_name:
                    try:
                        test_response = requests.post(
                            f"{embedding.url}/api/embed",
                            json={"model": embedding.model_name, "input": "test"},
                            timeout=5
                        )
                        if test_response.status_code == 200:
                            test_success = True
                    except requests.exceptions.RequestException:
                        pass  # Ollama API not available, try next method

                # Try GET /embed (transformer service)
                if not test_success:
                    try:
                        test_response = requests.get(
                            f"{embedding.url}/embed",
                            params={"text": "test"},
                            timeout=5
                        )
                        if test_response.status_code == 200:
                            test_success = True
                    except requests.exceptions.RequestException:
                        pass  # GET /embed not available, try next method

                # Try POST /embed (generic services)
                if not test_success:
                    try:
                        test_response = requests.post(
                            f"{embedding.url}/embed",
                            json={"text": "test"},
                            timeout=5
                        )
                        if test_response.status_code == 200:
                            test_success = True
                    except requests.exceptions.RequestException:
                        pass  # POST /embed not available, all methods exhausted

                if test_success:
                    console.print("[green]✓ OK[/green]")
                    results['available'].append(('embedding', embedding))
                else:
                    console.print("[red]✗ FAILED[/red]")
                    results['unavailable'].append(('embedding', embedding))
            except Exception:
                console.print("[red]✗ FAILED[/red]")
                results['unavailable'].append(('embedding', embedding))
        else:
            console.print("[bold cyan]Embedding Model:[/bold cyan] [yellow]Using fallback (local transformer)[/yellow]")
            console.print(f"  Pinging [cyan]local transformer[/cyan] @ {transformer_url}...", end=" ")

            # Check transformer service
            try:
                test_response = requests.get(
                    f"{transformer_url}/embed",
                    params={"text": "test"},
                    timeout=5
                )
                if test_response.status_code == 200:
                    console.print("[green]✓ OK[/green]")
                else:
                    console.print("[red]✗ FAILED[/red]")
            except Exception:
                console.print("[red]✗ FAILED[/red]")

        console.print()

        # Summary
        console.print("[bold]Summary:[/bold]")
        console.print(f"  [green]✓ Available:[/green] {len(results['available'])}")
        console.print(f"  [red]✗ Unavailable:[/red] {len(results['unavailable'])}")
        console.print(f"  [yellow]⊝ Not configured:[/yellow] {len(results['not_configured'])}")
        console.print()

        return True

    # Unknown model command
    console.print("\n❌ [red]Unknown model command[/red]")
    console.print("\n[bold]Available commands:[/bold]")
    console.print("  /model status")
    console.print("  /model list")
    console.print("  /model <type> list")
    console.print("  /model <type> add <url> <model_name>          [dim](Ollama)[/dim]")
    console.print("  /model <type> add anthropic <model_name>      [dim](Anthropic)[/dim]")
    console.print("  /model embedding add <url> [model_name] [timeout]")
    console.print("  /model <type> use <model_id>")
    console.print("  /model <type> remove <model_id>")
    console.print("  /model check [model_id]")
    console.print("  /model ping")
    console.print("\n[dim]Where <type> is: general, coder, or embedding[/dim]")
    console.print("[dim]Anthropic models: claude-sonnet-4-20250514, claude-3-5-sonnet-20241022, etc.[/dim]\n")
    return True
