"""
Pydantic models for Ollama API compatibility.
These models match the Ollama API specification.
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel


# ============================================================================
# OLLAMA API MODELS (Standard Ollama Compatibility)
# ============================================================================

class Message(BaseModel):
    """Chat message in Ollama format."""
    role: str  # system, user, assistant, tool
    content: str
    images: Optional[List[str]] = None  # Base64 encoded images
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatRequest(BaseModel):
    """Request for /api/chat endpoint (Ollama format)."""
    model: str
    messages: List[Message]
    stream: Optional[bool] = True
    format: Optional[str] = None  # json for structured output
    options: Optional[Dict[str, Any]] = None  # temperature, etc.
    tools: Optional[List[Dict[str, Any]]] = None  # MCP tools
    keep_alive: Optional[str] = "5m"


class ChatResponse(BaseModel):
    """Response for /api/chat endpoint (Ollama format)."""
    model: str
    created_at: str
    message: Message
    done: bool
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None


class GenerateRequest(BaseModel):
    """Request for /api/generate endpoint (Ollama format)."""
    model: str
    prompt: str
    images: Optional[List[str]] = None  # Base64 encoded
    stream: Optional[bool] = True
    format: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    system: Optional[str] = None  # System prompt
    template: Optional[str] = None
    context: Optional[List[int]] = None
    keep_alive: Optional[str] = "5m"


class GenerateResponse(BaseModel):
    """Response for /api/generate endpoint (Ollama format)."""
    model: str
    created_at: str
    response: str
    done: bool
    context: Optional[List[int]] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None


class ModelInfo(BaseModel):
    """Model information for /api/tags endpoint."""
    name: str
    modified_at: str
    size: int
    digest: str
    details: Optional[Dict[str, Any]] = None


class ModelsResponse(BaseModel):
    """Response for /api/tags endpoint (list models)."""
    models: List[ModelInfo]


# ============================================================================
# OPENAI API MODELS (OpenAI Compatibility)
# ============================================================================

class OpenAIMessage(BaseModel):
    """OpenAI format message."""
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class OpenAIFunction(BaseModel):
    """OpenAI function definition."""
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any]


class OpenAITool(BaseModel):
    """OpenAI tool definition."""
    type: str = "function"
    function: OpenAIFunction


class OpenAIChatRequest(BaseModel):
    """Request for /v1/chat/completions (OpenAI format)."""
    model: str
    messages: List[OpenAIMessage]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0
    frequency_penalty: Optional[float] = 0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[List[OpenAITool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


class OpenAIChoice(BaseModel):
    """OpenAI choice object."""
    index: int
    message: OpenAIMessage
    finish_reason: Optional[str] = None


class OpenAIUsage(BaseModel):
    """OpenAI usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIChatResponse(BaseModel):
    """Response for /v1/chat/completions (OpenAI format)."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[OpenAIChoice]
    usage: OpenAIUsage
    system_fingerprint: Optional[str] = None


# ============================================================================
# ENHANCED API MODELS (Custom Extensions)
# ============================================================================

class FileAttachment(BaseModel):
    """File attachment with @ prefix support."""
    filename: str
    content: str
    path: Optional[str] = None  # Virtual path for @ reference
    mime_type: Optional[str] = "text/plain"


class EnhancedChatRequest(ChatRequest):
    """Enhanced chat request with file attachments."""
    files: Optional[List[FileAttachment]] = None
    session_id: Optional[str] = None
    enable_rag: Optional[bool] = True
    enable_tools: Optional[bool] = True


class ToolExecuteRequest(BaseModel):
    """Request for /api/tools/execute endpoint."""
    tool_name: str
    arguments: Dict[str, Any]
    session_id: Optional[str] = None


class ToolExecuteResponse(BaseModel):
    """Response for /api/tools/execute endpoint."""
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float


class ContextAddRequest(BaseModel):
    """Request for /api/context/add endpoint."""
    content: str
    path: str
    session_id: str
    metadata: Optional[Dict[str, Any]] = None


class ContextAddResponse(BaseModel):
    """Response for /api/context/add endpoint."""
    success: bool
    path: str
    embedding_stored: bool


class CodeExecuteRequest(BaseModel):
    """Request for /api/code/execute endpoint."""
    code: str
    language: str = "python"  # python or r
    session_id: Optional[str] = None


class CodeExecuteResponse(BaseModel):
    """Response for /api/code/execute endpoint."""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float


class OrchestrationStep(BaseModel):
    """Single step in orchestration."""
    tool: str
    prompt: str
    arguments: Optional[Dict[str, Any]] = None


class OrchestrationRequest(BaseModel):
    """Request for /api/orchestrate endpoint."""
    prompt: str
    max_steps: Optional[int] = 10
    session_id: Optional[str] = None
    enable_code_generation: Optional[bool] = True


class OrchestrationResponse(BaseModel):
    """Response for /api/orchestrate endpoint."""
    success: bool
    steps: List[Dict[str, Any]]
    final_result: Any
    total_execution_time: float


# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    status_code: int = 500


# ============================================================================
# SESSION MANAGEMENT MODELS
# ============================================================================

class SessionMessage(BaseModel):
    """Message stored in session."""
    role: str
    content: str
    timestamp: Optional[str] = None


class SessionContextItem(BaseModel):
    """Context item stored in session (RAG)."""
    path: str
    content: str
    embedding_stored: bool = False
    timestamp: Optional[str] = None


class SessionData(BaseModel):
    """Complete session data for persistence."""
    session_id: str
    messages: List[SessionMessage] = []
    context_items: List[SessionContextItem] = []
    model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class SessionSaveRequest(BaseModel):
    """Request to save a session."""
    session_id: str
    messages: Optional[List[SessionMessage]] = None
    context_items: Optional[List[SessionContextItem]] = None
    model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionSaveResponse(BaseModel):
    """Response after saving session."""
    success: bool
    session_id: str
    message: str
    saved_at: str


class SessionRestoreResponse(BaseModel):
    """Response when restoring a session."""
    success: bool
    session_data: SessionData
    message: str


class SessionListItem(BaseModel):
    """Summary of a session for listing."""
    session_id: str
    message_count: int
    context_count: int
    model: Optional[str] = None
    created_at: str
    updated_at: str
    last_message_preview: Optional[str] = None


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    success: bool
    sessions: List[SessionListItem]
    total: int


class SessionDeleteResponse(BaseModel):
    """Response after deleting session(s)."""
    success: bool
    message: str
    deleted_count: int = 1
