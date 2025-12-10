"""Integration tests for the tester MCP server."""

import pytest
import asyncio
import json
import sys
from pathlib import Path

# Add the CLI root to path
cli_root = Path(__file__).parent.parent
sys.path.insert(0, str(cli_root))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tester_mcp_server_starts():
    """Test that tester MCP server can be started."""
    from src.mcp import MCPClient
    
    mcp_client = MCPClient(
        system_mcps_dir=cli_root / "system_mcps",
        postgres_url="http://localhost:15000",
        verbose=True
    )
    
    # Try to start the tester MCP server
    started = await mcp_client.start_server("tester")
    
    # Clean up
    if "tester" in mcp_client.servers:
        process = mcp_client.servers["tester"]
        process.terminate()
        await process.wait()
    
    assert started, "Tester MCP server should start successfully"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tester_mcp_list_tools():
    """Test that tester MCP server can list its tools."""
    from src.mcp import MCPClient
    
    mcp_client = MCPClient(
        system_mcps_dir=cli_root / "system_mcps",
        postgres_url="http://localhost:15000",
        verbose=True
    )
    
    # Start the server
    started = await mcp_client.start_server("tester")
    assert started, "Server should start"
    
    try:
        # Get tools
        tools = await mcp_client.get_tools("tester")
        
        assert tools is not None, "Should return tools list"
        assert len(tools) > 0, "Should have at least one tool"
        
        # Check for expected tools
        tool_names = [tool.get('name') for tool in tools]
        assert 'plan_mode' in tool_names, "Should have plan_mode tool"
        assert 'run_pytest' in tool_names, "Should have run_pytest tool"
        assert 'create_pytest_test' in tool_names, "Should have create_pytest_test tool"
        assert 'validate_with_test' in tool_names, "Should have validate_with_test tool"
        
    finally:
        # Clean up
        if "tester" in mcp_client.servers:
            process = mcp_client.servers["tester"]
            process.terminate()
            await process.wait()


@pytest.mark.unit
def test_tester_mcp_in_system_mcps():
    """Test that tester MCP is discoverable in system_mcps."""
    # Check manually by looking at the directory
    system_mcps_dir = cli_root / "system_mcps"
    tester_dir = system_mcps_dir / "tester"
    
    assert tester_dir.exists(), "Tester directory should exist"
    assert (tester_dir / "server.py").exists(), "Tester server.py should exist"
    
    # Also verify it's in the list of MCPs
    mcps = []
    for item in system_mcps_dir.iterdir():
        if item.is_dir():
            server_file = item / "server.py"
            if server_file.exists():
                mcps.append(item.name)
    
    assert 'tester' in mcps, "Tester MCP should be in system_mcps list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
