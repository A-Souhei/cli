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
        from app import app_state as state

        # Get models from Ollama
        models_data = await state.ollama_client.list_models()

        # Convert to Ollama format
        models_list = []
        for model_data in models_data.get("models", []):
            models_list.append(ModelInfo(
                name=model_data.get("name", "unknown"),
                modified_at=model_data.get("modified_at", datetime.utcnow().isoformat() + "Z"),
                size=model_data.get("size", 0),
                digest=model_data.get("digest", ""),
                details=model_data.get("details")
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
