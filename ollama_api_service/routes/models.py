"""
Models endpoint - Ollama /api/tags compatible (OpenWebUI compatible)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
import logging

from models import ModelsResponse, ModelInfo

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tags")
async def list_models(req: Request):
    """
    List available models (Ollama /api/tags endpoint).

    This endpoint is fully compatible with OpenWebUI.
    Returns list of models available in the Ollama instance.
    """
    try:
        from ollama_api_service.app import app_state as state

        # Get models from Ollama
        models_data = await state.ollama_client.list_models()

        # Convert to Ollama format
        models_list = []
        for model_data in models_data.get("models", []):
            # Handle modified_at - convert to string if it's a datetime
            modified_at = model_data.get("modified_at", "")
            if hasattr(modified_at, 'isoformat'):
                modified_at = modified_at.isoformat()
            elif not isinstance(modified_at, str):
                modified_at = str(modified_at)
            
            # Handle details - convert to dict if it's an object
            details = model_data.get("details")
            if details and not isinstance(details, dict):
                details = details.model_dump() if hasattr(details, 'model_dump') else dict(details)
            
            models_list.append(ModelInfo(
                name=model_data.get("name", "unknown"),
                modified_at=modified_at or datetime.utcnow().isoformat() + "Z",
                size=model_data.get("size", 0),
                digest=model_data.get("digest", ""),
                details=details
            ))

        logger.info(f"Listed {len(models_list)} models")

        return ModelsResponse(models=models_list)

    except Exception as e:
        logger.error(f"List models error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version")
async def version():
    """
    Return API version (Ollama compatible).
    """
    return {"version": "0.1.0"}  # Ollama format
