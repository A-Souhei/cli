"""
Chat endpoint - Ollama /api/chat compatible (OpenWebUI compatible)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
from datetime import datetime
import logging

from models import ChatRequest, ChatResponse, Message, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest, req: Request):
    """
    Ollama-compatible chat endpoint with streaming support.

    This endpoint is fully compatible with OpenWebUI and standard Ollama clients.
    """
    try:
        # Get app state
        from ollama_api_service.app import app_state as state

        # Get model (use from request or default from config)
        model = request.model or state.config.get_ollama_model()

        # Convert messages to Ollama format
        ollama_messages = []
        for msg in request.messages:
            ollama_messages.append({
                "role": msg.role,
                "content": msg.content,
                "images": msg.images if msg.images else None
            })

        # Prepare options (temperature, etc.)
        options = request.options or {}
        if "temperature" not in options:
            options["temperature"] = state.config.get_temperature()

        logger.info(f"Chat request: model={model}, messages={len(ollama_messages)}, stream={request.stream}")

        # Handle streaming vs non-streaming
        if request.stream:
            return StreamingResponse(
                stream_chat_response(
                    state.ollama_client,
                    model,
                    ollama_messages,
                    options,
                    request.format
                ),
                media_type="application/x-ndjson"
            )
        else:
            # Non-streaming response
            response = await state.ollama_client.chat(
                model=model,
                messages=ollama_messages,
                stream=False,
                format=request.format,
                options=options
            )

            # Convert to Ollama format
            return ChatResponse(
                model=model,
                created_at=datetime.utcnow().isoformat() + "Z",
                message=Message(
                    role="assistant",
                    content=response.get("message", {}).get("content", "")
                ),
                done=True,
                total_duration=response.get("total_duration"),
                load_duration=response.get("load_duration"),
                prompt_eval_count=response.get("prompt_eval_count"),
                prompt_eval_duration=response.get("prompt_eval_duration"),
                eval_count=response.get("eval_count"),
                eval_duration=response.get("eval_duration")
            )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def stream_chat_response(ollama_client, model, messages, options, format=None):
    """
    Stream chat response in Ollama format (compatible with OpenWebUI).

    Each chunk is a JSON object followed by newline.
    """
    try:
        async for chunk in ollama_client.chat_stream(
            model=model,
            messages=messages,
            options=options,
            format=format
        ):
            # Ollama streaming format: each chunk is a complete JSON object
            # OpenWebUI expects this exact format
            response_chunk = {
                "model": model,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "message": {
                    "role": "assistant",
                    "content": chunk.get("message", {}).get("content", "")
                },
                "done": chunk.get("done", False)
            }

            # Add metrics on final chunk
            if chunk.get("done"):
                response_chunk.update({
                    "total_duration": chunk.get("total_duration"),
                    "load_duration": chunk.get("load_duration"),
                    "prompt_eval_count": chunk.get("prompt_eval_count"),
                    "prompt_eval_duration": chunk.get("prompt_eval_duration"),
                    "eval_count": chunk.get("eval_count"),
                    "eval_duration": chunk.get("eval_duration")
                })

            # Send as NDJSON (newline-delimited JSON)
            yield json.dumps(response_chunk) + "\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        # Send error as final chunk
        error_chunk = {
            "model": model,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "message": {
                "role": "assistant",
                "content": f"Error: {str(e)}"
            },
            "done": True,
            "error": str(e)
        }
        yield json.dumps(error_chunk) + "\n"
