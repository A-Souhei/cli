"""
MCP Tools endpoints (Enhanced feature)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request
import logging
import time

from models import (
    ToolExecuteRequest,
    ToolExecuteResponse,
    CodeExecuteRequest,
    CodeExecuteResponse,
    OrchestrationRequest,
    OrchestrationResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list")
async def list_tools(req: Request):
    """
    List all available MCP tools.

    Returns all tools from the MCP server with their descriptions and parameters.
    """
    try:
        from app import app_state as state

        tools = await state.mcp_client.list_tools()

        return {
            "success": True,
            "tools": [
                {
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "mcp_server": tool.get("mcp_name", "coder"),
                    "parameters": tool.get("inputSchema", {})
                }
                for tool in tools
            ],
            "count": len(tools)
        }

    except Exception as e:
        logger.error(f"List tools error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_tool(request: ToolExecuteRequest, req: Request):
    """
    Execute an MCP tool by name.

    This allows direct execution of any MCP tool (code execution, file operations, etc.)
    """
    try:
        from app import app_state as state

        start_time = time.time()

        # Execute tool via MCP client
        result = await state.mcp_client.call_tool(
            "coder",  # MCP server name
            request.tool_name,
            request.arguments
        )

        execution_time = time.time() - start_time

        logger.info(f"Tool {request.tool_name} executed in {execution_time:.2f}s")

        return ToolExecuteResponse(
            success=True,
            result=result,
            execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"Tool execution error: {e}", exc_info=True)
        return ToolExecuteResponse(
            success=False,
            result=None,
            error=str(e),
            execution_time=time.time() - start_time
        )


@router.post("/retrieve")
async def retrieve_tools(
    prompt: str,
    top_k: int = 3,
    threshold: float = 0.5,
    req: Request = None
):
    """
    Retrieve relevant tools based on semantic search.

    Uses embeddings to find the most relevant tools for a given prompt.
    This is the same intelligent tool matching used by the CLI.
    """
    try:
        from app import app_state as state

        # Use the retrieve_all_tools MCP tool
        result = await state.mcp_client.call_tool(
            "coder",
            "retrieve_all_tools",
            {
                "prompts": [prompt],
                "top_k": top_k,
                "threshold": threshold
            }
        )

        return {
            "success": True,
            "query": prompt,
            "tools": result.get("tools", []),
            "count": len(result.get("tools", []))
        }

    except Exception as e:
        logger.error(f"Tool retrieval error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code/execute")
async def execute_code(request: CodeExecuteRequest, req: Request):
    """
    Execute Python or R code in a sandbox.

    This uses the MCP run_python_code or run_r_code tools.
    """
    try:
        from app import app_state as state

        start_time = time.time()

        # Select appropriate tool based on language
        tool_name = f"run_{request.language}_code"

        # Execute code
        result = await state.mcp_client.call_tool(
            "coder",
            tool_name,
            {
                "code": request.code,
                "session_id": request.session_id
            }
        )

        execution_time = time.time() - start_time

        logger.info(f"Code executed ({request.language}) in {execution_time:.2f}s")

        # Parse result
        if isinstance(result, dict):
            return CodeExecuteResponse(
                success=result.get("success", True),
                output=result.get("output", str(result)),
                error=result.get("error"),
                execution_time=execution_time
            )
        else:
            return CodeExecuteResponse(
                success=True,
                output=str(result),
                execution_time=execution_time
            )

    except Exception as e:
        logger.error(f"Code execution error: {e}", exc_info=True)
        return CodeExecuteResponse(
            success=False,
            output="",
            error=str(e),
            execution_time=time.time() - start_time
        )


@router.post("/orchestrate")
async def orchestrate(request: OrchestrationRequest, req: Request):
    """
    Orchestrate multi-step task execution.

    This uses the CLI's "roll_the_dice" or "spin_the_roulette" functionality
    to break down complex tasks into steps and execute them.
    """
    try:
        from app import app_state as state

        start_time = time.time()

        # Use spin_the_roulette for complex text-to-sequence conversion
        result = await state.mcp_client.call_tool(
            "coder",
            "spin_the_roulette",
            {
                "complex_text": request.prompt,
                "session_id": request.session_id,
                "max_iterations": min(request.max_steps, 10)
            }
        )

        execution_time = time.time() - start_time

        logger.info(f"Orchestration completed in {execution_time:.2f}s")

        return OrchestrationResponse(
            success=True,
            steps=result.get("steps", []),
            final_result=result.get("final_result"),
            total_execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"Orchestration error: {e}", exc_info=True)
        return OrchestrationResponse(
            success=False,
            steps=[],
            final_result=None,
            total_execution_time=time.time() - start_time
        )


@router.get("/health")
async def tools_health(req: Request):
    """
    Check health of MCP tools system.
    """
    try:
        from app import app_state as state

        tools = await state.mcp_client.list_tools()

        return {
            "status": "healthy",
            "mcp_connected": True,
            "tools_available": len(tools),
            "tools": [t.get("name") for t in tools]
        }

    except Exception as e:
        logger.error(f"Tools health check error: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "mcp_connected": False,
            "error": str(e)
        }
