"""
OpenAI-compatible endpoints (for broader client compatibility)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
import time
from datetime import datetime
import uuid
import logging

from models import OpenAIChatRequest, OpenAIChatResponse, OpenAIChoice, OpenAIMessage, OpenAIUsage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat/completions")
async def chat_completions(request: OpenAIChatRequest, req: Request):
    """
    OpenAI-compatible chat completions endpoint.

    This allows clients that use OpenAI's API format to work with our service.
    """
    try:
        from app import app_state as state

        # Convert OpenAI messages to Ollama format
        ollama_messages = []
        for msg in request.messages:
            ollama_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Map model name (handle OpenAI model names)
        model = request.model
        if model.startswith("gpt-"):
            # Map GPT models to Ollama model
            model = state.config.get("ollama.model", "llama3.1:8b")
            logger.info(f"Mapped OpenAI model {request.model} to {model}")

        # Prepare options
        options = {
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.max_tokens:
            options["num_predict"] = request.max_tokens

        logger.info(f"OpenAI chat request: model={model}, messages={len(ollama_messages)}, stream={request.stream}")

        # Handle streaming vs non-streaming
        if request.stream:
            return StreamingResponse(
                stream_openai_response(
                    state.ollama_client,
                    model,
                    ollama_messages,
                    options,
                    request.model  # Original model name for response
                ),
                media_type="text/event-stream"
            )
        else:
            # Non-streaming response
            start_time = time.time()
            response = await state.ollama_client.chat(
                model=model,
                messages=ollama_messages,
                stream=False,
                options=options
            )

            # Convert to OpenAI format
            content = response.get("message", {}).get("content", "")

            # Estimate tokens (rough approximation)
            prompt_tokens = sum(len(m.content.split()) for m in request.messages)
            completion_tokens = len(content.split())

            return OpenAIChatResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                object="chat.completion",
                created=int(time.time()),
                model=request.model,  # Return original model name
                choices=[
                    OpenAIChoice(
                        index=0,
                        message=OpenAIMessage(
                            role="assistant",
                            content=content
                        ),
                        finish_reason="stop"
                    )
                ],
                usage=OpenAIUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )

    except Exception as e:
        logger.error(f"OpenAI chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def stream_openai_response(ollama_client, model, messages, options, original_model):
    """
    Stream response in OpenAI SSE format.

    OpenAI uses Server-Sent Events (SSE) with data: prefix.
    """
    try:
        request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())

        async for chunk in ollama_client.chat_stream(
            model=model,
            messages=messages,
            options=options
        ):
            content = chunk.get("message", {}).get("content", "")

            if content or chunk.get("done"):
                # OpenAI streaming format
                response_chunk = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": original_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": content
                            } if content else {},
                            "finish_reason": "stop" if chunk.get("done") else None
                        }
                    ]
                }

                # SSE format: "data: {json}\n\n"
                yield f"data: {json.dumps(response_chunk)}\n\n"

        # Send final [DONE] message
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"OpenAI streaming error: {e}", exc_info=True)
        error_data = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": original_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": f"Error: {str(e)}"},
                    "finish_reason": "error"
                }
            ]
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        yield "data: [DONE]\n\n"


@router.get("/models")
async def list_openai_models(req: Request):
    """
    OpenAI-compatible models list endpoint.
    """
    try:
        from app import app_state as state

        # Get models from Ollama
        models_data = await state.ollama_client.list_models()

        # Convert to OpenAI format
        openai_models = []
        for model_data in models_data.get("models", []):
            openai_models.append({
                "id": model_data.get("name", "unknown"),
                "object": "model",
                "created": int(datetime.fromisoformat(
                    model_data.get("modified_at", datetime.utcnow().isoformat()).replace("Z", "")
                ).timestamp()),
                "owned_by": "ollama"
            })

        return {
            "object": "list",
            "data": openai_models
        }

    except Exception as e:
        logger.error(f"List OpenAI models error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
