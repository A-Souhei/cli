"""
Generate endpoint - Ollama /api/generate compatible (OpenWebUI compatible)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
from datetime import datetime
import logging

from models import GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate")
async def generate(request: GenerateRequest, req: Request):
    """
    Ollama-compatible generate endpoint with streaming support.

    This endpoint is fully compatible with OpenWebUI and standard Ollama clients.
    """
    try:
        # Get app state
        from app import app_state as state

        # Get model
        model = request.model or state.config.get("ollama.model", "llama3.1:8b")

        # Prepare options
        options = request.options or {}
        if "temperature" not in options:
            options["temperature"] = state.config.get("chat.temperature", 0.7)

        logger.info(f"Generate request: model={model}, stream={request.stream}")

        # Handle streaming vs non-streaming
        if request.stream:
            return StreamingResponse(
                stream_generate_response(
                    state.ollama_client,
                    model,
                    request.prompt,
                    request.system,
                    options,
                    request.format,
                    request.images,
                    request.context
                ),
                media_type="application/x-ndjson"
            )
        else:
            # Non-streaming response
            response = await state.ollama_client.generate(
                model=model,
                prompt=request.prompt,
                system=request.system,
                stream=False,
                format=request.format,
                options=options,
                images=request.images,
                context=request.context
            )

            return GenerateResponse(
                model=model,
                created_at=datetime.utcnow().isoformat() + "Z",
                response=response.get("response", ""),
                done=True,
                context=response.get("context"),
                total_duration=response.get("total_duration"),
                load_duration=response.get("load_duration"),
                prompt_eval_count=response.get("prompt_eval_count"),
                prompt_eval_duration=response.get("prompt_eval_duration"),
                eval_count=response.get("eval_count"),
                eval_duration=response.get("eval_duration")
            )

    except Exception as e:
        logger.error(f"Generate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def stream_generate_response(
    ollama_client,
    model,
    prompt,
    system=None,
    options=None,
    format=None,
    images=None,
    context=None
):
    """
    Stream generate response in Ollama format (compatible with OpenWebUI).
    """
    try:
        async for chunk in ollama_client.generate_stream(
            model=model,
            prompt=prompt,
            system=system,
            options=options,
            format=format,
            images=images,
            context=context
        ):
            # Ollama streaming format
            response_chunk = {
                "model": model,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "response": chunk.get("response", ""),
                "done": chunk.get("done", False)
            }

            # Add metrics and context on final chunk
            if chunk.get("done"):
                response_chunk.update({
                    "context": chunk.get("context"),
                    "total_duration": chunk.get("total_duration"),
                    "load_duration": chunk.get("load_duration"),
                    "prompt_eval_count": chunk.get("prompt_eval_count"),
                    "prompt_eval_duration": chunk.get("prompt_eval_duration"),
                    "eval_count": chunk.get("eval_count"),
                    "eval_duration": chunk.get("eval_duration")
                })

            yield json.dumps(response_chunk) + "\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        error_chunk = {
            "model": model,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "response": f"Error: {str(e)}",
            "done": True,
            "error": str(e)
        }
        yield json.dumps(error_chunk) + "\n"
