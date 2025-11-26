"""
File upload and @ prefix handling (Enhanced feature)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
import logging
import tempfile
import os
import hashlib

from models import (
    FileAttachment,
    ContextAddRequest,
    ContextAddResponse,
    EnhancedChatRequest,
    ChatResponse,
    Message
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/files/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
    auto_inject: bool = Form(True),
    req: Request = None
):
    """
    Upload files and optionally inject into RAG context.

    This allows files to be referenced via @ prefix in subsequent messages.
    Similar to the CLI's @ prefix autocomplete feature.

    Returns:
        List of uploaded file metadata with @ reference paths
    """
    try:
        from ollama_api_service.app import app_state as state

        if not session_id:
            # Create new session if not provided
            session_id = state.session_manager.create_session()

        uploaded_files = []

        for upload_file in files:
            # Read file content
            content = await upload_file.read()
            content_str = content.decode("utf-8", errors="ignore")

            # Create @ reference path
            file_hash = hashlib.md5(upload_file.filename.encode()).hexdigest()[:8]
            at_path = f"@{upload_file.filename}"

            # Store in session context if auto_inject enabled
            if auto_inject and state.mcp_client:
                try:
                    # Use the add_file_context tool from MCP
                    # This is similar to what the CLI does with @ prefix
                    result = await state.mcp_client.call_tool(
                        "coder",
                        "add_file_context",
                        {
                            "file_path": at_path,
                            "session_id": session_id,
                            "content": content_str[:10000]  # Limit size
                        }
                    )
                    logger.info(f"File context added: {at_path}")
                except Exception as e:
                    logger.warning(f"Failed to add file context: {e}")

            uploaded_files.append({
                "filename": upload_file.filename,
                "at_reference": at_path,
                "size": len(content),
                "content_type": upload_file.content_type,
                "session_id": session_id,
                "auto_injected": auto_inject
            })

        logger.info(f"Uploaded {len(uploaded_files)} files to session {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "files": uploaded_files,
            "usage_example": f"Now you can reference these files in chat with their @ paths, e.g., '{uploaded_files[0]['at_reference']}'"
        }

    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context/add")
async def add_context(request: ContextAddRequest, req: Request):
    """
    Manually add content to RAG context for a session.

    This is useful for injecting context without uploading files.
    """
    try:
        from ollama_api_service.app import app_state as state

        # Use MCP client to add context
        result = await state.mcp_client.call_tool(
            "coder",
            "add_file_context",
            {
                "file_path": request.path,
                "session_id": request.session_id,
                "content": request.content
            }
        )

        logger.info(f"Context added: {request.path} for session {request.session_id}")

        return ContextAddResponse(
            success=True,
            path=request.path,
            embedding_stored=True
        )

    except Exception as e:
        logger.error(f"Add context error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/with-files")
async def chat_with_files(
    message: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    model: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    stream: bool = Form(True),
    temperature: Optional[float] = Form(None),
    req: Request = None
):
    """
    Chat endpoint with file upload support.

    This combines file upload + context injection + chat in one request.
    Files are automatically injected into the context and can be referenced
    via @ prefix in the message.

    Example:
        POST /api/chat/with-files
        - message: "Analyze the data in @data.csv and create a visualization"
        - files: [data.csv]
    """
    try:
        from ollama_api_service.app import app_state as state
        from routes.chat import stream_chat_response

        # Create session if needed
        if not session_id:
            session_id = state.session_manager.create_session()

        # Process uploaded files
        file_contexts = []
        if files:
            for upload_file in files:
                content = await upload_file.read()
                content_str = content.decode("utf-8", errors="ignore")

                # Add to context
                at_path = f"@{upload_file.filename}"
                try:
                    await state.mcp_client.call_tool(
                        "coder",
                        "add_file_context",
                        {
                            "file_path": at_path,
                            "session_id": session_id,
                            "content": content_str[:10000]
                        }
                    )
                    file_contexts.append({
                        "path": at_path,
                        "filename": upload_file.filename,
                        "size": len(content_str)
                    })
                except Exception as e:
                    logger.warning(f"Failed to add file context for {upload_file.filename}: {e}")

        # Build message with file references
        full_message = message
        if file_contexts:
            file_list = ", ".join([f['path'] for f in file_contexts])
            full_message = f"{message}\n\n[Attached files: {file_list}]"

        # Get model
        model = model or state.config.get_ollama_model()

        # Prepare messages
        messages = [{"role": "user", "content": full_message}]

        # Prepare options
        options = {}
        if temperature is not None:
            options["temperature"] = temperature
        else:
            options["temperature"] = state.config.get_temperature()

        # Stream response
        if stream:
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                stream_chat_response(
                    state.ollama_client,
                    model,
                    messages,
                    options
                ),
                media_type="application/x-ndjson"
            )
        else:
            response = await state.ollama_client.chat(
                model=model,
                messages=messages,
                stream=False,
                options=options
            )

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
        logger.error(f"Chat with files error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
