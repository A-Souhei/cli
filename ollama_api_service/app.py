"""
Ollama API Service - FastAPI Application

This service provides an Ollama-compatible API with enhanced features:
- Standard Ollama endpoints (/api/chat, /api/generate, /api/tags)
- OpenAI-compatible endpoint (/v1/chat/completions)
- Enhanced features (file upload with @ prefix, RAG, MCP tools, code execution)

GOLDEN RULE: This service ONLY imports from src/ - it does NOT modify CLI code.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import time
from typing import Optional, List
import uvicorn

# Import from existing src/ (mounted in Docker)
from src.config.manager import ConfigManager
from src.chat.manager import ChatManager
from src.session.manager import SessionManager
from src.mcp.client import MCPClient

# Import our adapter for Ollama client
from utils.ollama_adapter import OllamaAPIAdapter

# Import routes (to be created)
from routes import chat, generate, models, tools, files, openai

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

class AppState:
    """Application state container."""
    config: ConfigManager = None
    ollama_client: OllamaAPIAdapter = None
    chat_manager: ChatManager = None
    session_manager: SessionManager = None
    mcp_client: MCPClient = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown."""
    # Startup
    logger.info("Starting Ollama API Service...")

    try:
        # Load configuration
        config_path = Path("/app/config.yaml")  # Mounted in Docker
        if not config_path.exists():
            config_path = Path(__file__).parent.parent / "config.yaml"

        logger.info(f"Loading config from: {config_path}")
        app_state.config = ConfigManager(str(config_path))

        # Initialize Ollama client adapter - prefer env var over config file
        ollama_url = os.environ.get("OLLAMA_API_URL") or app_state.config.get_ollama_url()
        ollama_timeout = app_state.config.get_ollama_timeout()
        logger.info(f"Connecting to Ollama at: {ollama_url}")
        app_state.ollama_client = OllamaAPIAdapter(
            base_url=ollama_url,
            timeout=ollama_timeout
        )

        # Initialize chat manager - use ConfigManager's methods
        system_prompt = app_state.config.get_system_prompt()
        max_context_length = app_state.config.get_max_context_length()
        app_state.chat_manager = ChatManager(
            system_prompt=system_prompt,
            max_context_length=max_context_length
        )

        # Initialize session manager
        app_state.session_manager = SessionManager()

        # Initialize MCP client
        logger.info("Initializing MCP client...")
        system_mcps_dir = Path("/app/system_mcps")
        if not system_mcps_dir.exists():
            system_mcps_dir = Path(__file__).parent.parent / "system_mcps"
        postgres_api_url = os.environ.get("POSTGRES_API_URL", "http://postgres-api:5000")
        app_state.mcp_client = MCPClient(
            system_mcps_dir=system_mcps_dir,
            postgres_url=postgres_api_url,
            verbose=os.environ.get("MCP_DEBUG", "false").lower() == "true"
        )

        logger.info("✅ Ollama API Service started successfully!")

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Ollama API Service...")
    # MCPClient doesn't have a cleanup method - servers are managed per-request
    logger.info("✅ Shutdown complete")


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Ollama++ API",
    description="Ollama-compatible API with enhanced features (RAG, MCP tools, code execution)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - service info."""
    return {
        "service": "Ollama++ API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "ollama_compatible": [
                "/api/chat",
                "/api/generate",
                "/api/tags"
            ],
            "openai_compatible": [
                "/v1/chat/completions"
            ],
            "enhanced": [
                "/api/tools/list",
                "/api/tools/execute",
                "/api/context/add",
                "/api/code/execute",
                "/api/files/upload",
                "/api/orchestrate"
            ]
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        # Check if Ollama is accessible
        models = await app_state.ollama_client.list_models()
        return {
            "status": "healthy",
            "ollama": "connected",
            "models_available": len(models),
            "mcp_tools": len(await app_state.mcp_client.list_tools()) if app_state.mcp_client else 0
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# ============================================================================
# INCLUDE ROUTERS
# ============================================================================

# Standard Ollama endpoints
app.include_router(chat.router, prefix="/api", tags=["Ollama Chat"])
app.include_router(generate.router, prefix="/api", tags=["Ollama Generate"])
app.include_router(models.router, prefix="/api", tags=["Ollama Models"])

# OpenAI compatible
app.include_router(openai.router, prefix="/v1", tags=["OpenAI Compatible"])

# Enhanced endpoints
app.include_router(tools.router, prefix="/api/tools", tags=["Enhanced - Tools"])
app.include_router(files.router, prefix="/api", tags=["Enhanced - Files"])


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "status_code": 500
        }
    )


# ============================================================================
# MAIN (for local testing)
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
