"""Sentry error handler configuration utility."""

import os
import sentry_sdk
from typing import Optional


def configure_sentry(service_name: str = "unknown-service") -> None:
    """
    Configure Sentry error tracking for the application.
    
    Args:
        service_name: Name of the service for tagging in Sentry
    """
    # Get configuration from environment variables
    sentry_dsn = os.getenv('SENTRY_DSN', '')
    environment = os.getenv('ENVIRONMENT', 'DEV')
    
    # Only configure Sentry if DSN is provided
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            traces_sample_rate=1.0 if environment == 'DEV' else 0.1,
            profiles_sample_rate=1.0 if environment == 'DEV' else 0.1,
            enable_tracing=True,
            _experiments={
                "profiles_sample_rate": 1.0 if environment == 'DEV' else 0.1,
            },
        )
        
        # Set service tag
        sentry_sdk.set_tag("service", service_name)
        
        print(f"Sentry configured for {service_name} in {environment} environment")
    else:
        print(f"Sentry not configured (no DSN provided) for {service_name}")


def get_environment() -> str:
    """Get the current environment (DEV/PROD)."""
    return os.getenv('ENVIRONMENT', 'DEV')


def is_dev_environment() -> bool:
    """Check if running in development environment."""
    return get_environment() == 'DEV'
