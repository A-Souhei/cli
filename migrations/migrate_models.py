"""Migration script for moving models from config.yaml to Redis."""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.manager import ConfigManager
from src.model_registry.manager import ModelRegistry
from src.sentry_config import capture_exception


def migrate_models_to_redis(config_manager: ConfigManager, model_registry: ModelRegistry) -> dict:
    """
    Migrate models from config.yaml to Redis ModelRegistry.

    Args:
        config_manager: ConfigManager instance
        model_registry: ModelRegistry instance

    Returns:
        Dictionary with migration results
    """
    results = {
        'general_migrated': False,
        'coder_migrated': False,
        'errors': []
    }

    try:
        # Check if models already exist in Redis
        existing_general = model_registry.get_active_model('general')
        existing_coder = model_registry.get_active_model('coder')

        if existing_general and existing_coder:
            # Already migrated
            return results

        # Migrate general model if not exists
        if not existing_general:
            try:
                url = config_manager.get_ollama_url()
                model_name = config_manager.get_ollama_model()
                timeout = config_manager.get_ollama_timeout()

                model_registry.add_model(
                    model_type='general',
                    url=url,
                    model_name=model_name,
                    timeout=timeout,
                    set_active=True
                )
                results['general_migrated'] = True
            except Exception as e:
                error_msg = f"Failed to migrate general model: {e}"
                results['errors'].append(error_msg)
                capture_exception(e)

        # Migrate coder model if not exists
        if not existing_coder:
            try:
                url = config_manager.get_ollama_url()  # Coder uses same URL as general
                model_name = config_manager.get_coder_model()
                timeout = config_manager.get_ollama_timeout()

                model_registry.add_model(
                    model_type='coder',
                    url=url,
                    model_name=model_name,
                    timeout=timeout,
                    set_active=True
                )
                results['coder_migrated'] = True
            except Exception as e:
                error_msg = f"Failed to migrate coder model: {e}"
                results['errors'].append(error_msg)
                capture_exception(e)

    except Exception as e:
        error_msg = f"Migration failed: {e}"
        results['errors'].append(error_msg)
        capture_exception(e)

    return results


def run_migration_if_needed(config_manager: ConfigManager, model_registry: ModelRegistry, verbose: bool = False) -> None:
    """
    Run migration if needed (called on startup).

    Args:
        config_manager: ConfigManager instance
        model_registry: ModelRegistry instance
        verbose: Whether to print verbose output
    """
    import os

    # Check environment variable to skip migration
    if os.getenv('AI_CLI_SKIP_MODEL_MIGRATION', '').lower() == 'true':
        if verbose:
            print("Model migration skipped (AI_CLI_SKIP_MODEL_MIGRATION=true)")
        return

    # Check if using config.yaml only mode
    if os.getenv('AI_CLI_FORCE_CONFIG_YAML', '').lower() == 'true':
        if verbose:
            print("Using config.yaml models only (AI_CLI_FORCE_CONFIG_YAML=true)")
        return

    # Run migration
    results = migrate_models_to_redis(config_manager, model_registry)

    if verbose:
        if results['general_migrated']:
            print("✓ Migrated general model to Redis")
        if results['coder_migrated']:
            print("✓ Migrated coder model to Redis")
        if results['errors']:
            print(f"⚠️  Migration warnings: {', '.join(results['errors'])}")


if __name__ == '__main__':
    """Run migration manually."""
    config = ConfigManager()
    registry = ModelRegistry()

    print("Running model migration...")
    results = migrate_models_to_redis(config, registry)

    print("\nMigration Results:")
    print(f"  General model migrated: {results['general_migrated']}")
    print(f"  Coder model migrated: {results['coder_migrated']}")

    if results['errors']:
        print(f"\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")
    else:
        print("\n✅ Migration completed successfully!")
