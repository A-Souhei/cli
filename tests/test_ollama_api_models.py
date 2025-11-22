"""
Unit tests for Ollama API service models.

Tests Pydantic model validation and serialization.
"""

import pytest
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ollama_api_service.models import (
    Message,
    ChatRequest,
    ChatResponse,
    GenerateRequest,
    GenerateResponse,
    ModelInfo,
    ModelsResponse,
    OpenAIMessage,
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIChoice,
    OpenAIUsage,
    ToolExecuteRequest,
    ToolExecuteResponse,
    CodeExecuteRequest,
    CodeExecuteResponse,
    FileAttachment,
    ContextAddRequest,
    ContextAddResponse,
    ErrorResponse,
)


class TestMessage:
    """Test Message model."""

    def test_valid_message(self):
        """Test creating a valid message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.images is None
        assert msg.tool_calls is None

    def test_message_with_images(self):
        """Test message with images."""
        msg = Message(
            role="user",
            content="What's in this image?",
            images=["base64_image_data"]
        )
        assert len(msg.images) == 1
        assert msg.images[0] == "base64_image_data"

    def test_assistant_message(self):
        """Test assistant message."""
        msg = Message(role="assistant", content="I can help you with that.")
        assert msg.role == "assistant"


class TestChatRequest:
    """Test ChatRequest model."""

    def test_valid_chat_request(self):
        """Test creating a valid chat request."""
        req = ChatRequest(
            model="llama3.1:8b",
            messages=[
                Message(role="user", content="Hello")
            ]
        )
        assert req.model == "llama3.1:8b"
        assert len(req.messages) == 1
        assert req.stream is True  # Default value

    def test_chat_request_with_options(self):
        """Test chat request with options."""
        req = ChatRequest(
            model="llama3.1:8b",
            messages=[Message(role="user", content="Hello")],
            stream=False,
            options={"temperature": 0.9, "top_p": 0.95}
        )
        assert req.stream is False
        assert req.options["temperature"] == 0.9
        assert req.options["top_p"] == 0.95

    def test_chat_request_with_tools(self):
        """Test chat request with tools."""
        req = ChatRequest(
            model="llama3.1:8b",
            messages=[Message(role="user", content="Run code")],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "run_python_code",
                        "description": "Execute Python code"
                    }
                }
            ]
        )
        assert len(req.tools) == 1
        assert req.tools[0]["function"]["name"] == "run_python_code"


class TestChatResponse:
    """Test ChatResponse model."""

    def test_valid_chat_response(self):
        """Test creating a valid chat response."""
        resp = ChatResponse(
            model="llama3.1:8b",
            created_at=datetime.utcnow().isoformat() + "Z",
            message=Message(role="assistant", content="Hello!"),
            done=True
        )
        assert resp.model == "llama3.1:8b"
        assert resp.message.role == "assistant"
        assert resp.done is True

    def test_chat_response_with_metrics(self):
        """Test chat response with performance metrics."""
        resp = ChatResponse(
            model="llama3.1:8b",
            created_at=datetime.utcnow().isoformat() + "Z",
            message=Message(role="assistant", content="Response"),
            done=True,
            total_duration=1500000000,  # nanoseconds
            eval_count=50
        )
        assert resp.total_duration == 1500000000
        assert resp.eval_count == 50


class TestGenerateRequest:
    """Test GenerateRequest model."""

    def test_valid_generate_request(self):
        """Test creating a valid generate request."""
        req = GenerateRequest(
            model="llama3.1:8b",
            prompt="Why is the sky blue?"
        )
        assert req.model == "llama3.1:8b"
        assert req.prompt == "Why is the sky blue?"
        assert req.stream is True  # Default

    def test_generate_request_with_system(self):
        """Test generate request with system prompt."""
        req = GenerateRequest(
            model="llama3.1:8b",
            prompt="Hello",
            system="You are a helpful assistant."
        )
        assert req.system == "You are a helpful assistant."


class TestOpenAIModels:
    """Test OpenAI compatibility models."""

    def test_openai_message(self):
        """Test OpenAI message format."""
        msg = OpenAIMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_openai_chat_request(self):
        """Test OpenAI chat request."""
        req = OpenAIChatRequest(
            model="gpt-4",
            messages=[
                OpenAIMessage(role="user", content="Hello")
            ],
            temperature=0.7,
            max_tokens=100
        )
        assert req.model == "gpt-4"
        assert req.temperature == 0.7
        assert req.max_tokens == 100

    def test_openai_chat_response(self):
        """Test OpenAI chat response."""
        resp = OpenAIChatResponse(
            id="chatcmpl-123",
            created=1234567890,
            model="gpt-4",
            choices=[
                OpenAIChoice(
                    index=0,
                    message=OpenAIMessage(role="assistant", content="Hi!"),
                    finish_reason="stop"
                )
            ],
            usage=OpenAIUsage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )
        )
        assert resp.id == "chatcmpl-123"
        assert len(resp.choices) == 1
        assert resp.usage.total_tokens == 15


class TestToolModels:
    """Test tool-related models."""

    def test_tool_execute_request(self):
        """Test tool execute request."""
        req = ToolExecuteRequest(
            tool_name="run_python_code",
            arguments={"code": "print('hello')"}
        )
        assert req.tool_name == "run_python_code"
        assert req.arguments["code"] == "print('hello')"

    def test_tool_execute_response_success(self):
        """Test successful tool execution response."""
        resp = ToolExecuteResponse(
            success=True,
            result={"output": "hello\n"},
            execution_time=0.5
        )
        assert resp.success is True
        assert resp.error is None
        assert resp.execution_time == 0.5

    def test_tool_execute_response_failure(self):
        """Test failed tool execution response."""
        resp = ToolExecuteResponse(
            success=False,
            result=None,
            error="Code execution failed",
            execution_time=0.1
        )
        assert resp.success is False
        assert resp.error == "Code execution failed"


class TestCodeExecutionModels:
    """Test code execution models."""

    def test_code_execute_request_python(self):
        """Test Python code execution request."""
        req = CodeExecuteRequest(
            code="print(2 + 2)",
            language="python"
        )
        assert req.language == "python"
        assert req.code == "print(2 + 2)"

    def test_code_execute_request_r(self):
        """Test R code execution request."""
        req = CodeExecuteRequest(
            code="print(2 + 2)",
            language="r"
        )
        assert req.language == "r"

    def test_code_execute_response(self):
        """Test code execution response."""
        resp = CodeExecuteResponse(
            success=True,
            output="4\n",
            execution_time=0.2
        )
        assert resp.success is True
        assert resp.output == "4\n"


class TestFileModels:
    """Test file-related models."""

    def test_file_attachment(self):
        """Test file attachment model."""
        file = FileAttachment(
            filename="test.txt",
            content="This is a test file",
            path="@test.txt",
            mime_type="text/plain"
        )
        assert file.filename == "test.txt"
        assert file.path == "@test.txt"

    def test_context_add_request(self):
        """Test context add request."""
        req = ContextAddRequest(
            content="Important context",
            path="@context.txt",
            session_id="session-123"
        )
        assert req.session_id == "session-123"
        assert req.path == "@context.txt"

    def test_context_add_response(self):
        """Test context add response."""
        resp = ContextAddResponse(
            success=True,
            path="@context.txt",
            embedding_stored=True
        )
        assert resp.success is True
        assert resp.embedding_stored is True


class TestModelInfo:
    """Test model info models."""

    def test_model_info(self):
        """Test model info."""
        info = ModelInfo(
            name="llama3.1:8b",
            modified_at=datetime.utcnow().isoformat() + "Z",
            size=4661224384,
            digest="sha256:abc123"
        )
        assert info.name == "llama3.1:8b"
        assert info.size == 4661224384

    def test_models_response(self):
        """Test models response."""
        resp = ModelsResponse(
            models=[
                ModelInfo(
                    name="llama3.1:8b",
                    modified_at=datetime.utcnow().isoformat() + "Z",
                    size=4661224384,
                    digest="sha256:abc123"
                )
            ]
        )
        assert len(resp.models) == 1


class TestErrorResponse:
    """Test error response model."""

    def test_error_response(self):
        """Test error response."""
        err = ErrorResponse(
            error="Something went wrong",
            detail="Detailed error message",
            status_code=500
        )
        assert err.error == "Something went wrong"
        assert err.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
