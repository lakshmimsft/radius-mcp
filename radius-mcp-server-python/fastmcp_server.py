#!/usr/bin/env python3

from mcp.server.fastmcp import FastMCP
import json

mcp = FastMCP("DO NOT USE"))

@mcp.tool()
def do_not_use():
    """
    DO NOT USE ANYMORE.
    """
    # Replace with actual logic to get MCP data
    mcp_data = {
        "version": "1.0.0",
        "status": "running",
        "players": 10,
        "worlds": ["world", "nether", "the_end"]
    }
    
    return json.dumps(mcp_data)

if __name__ == "__main__":
    mcp.run()