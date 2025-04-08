#!/usr/bin/env python3

from mcp.client import Client
import asyncio
import sys
import os

async def main():
    try:
        server_name = "Example-FastMCP-Server"
        print(f"Connecting to {server_name}...")
        
        # Print the environment variables for debugging
        print("Environment variables:")
        print(f"MCP_SERVER_NAME: {os.environ.get('MCP_SERVER_NAME')}")
        print(f"MCP_SERVER_PATH: {os.environ.get('MCP_SERVER_PATH')}")
        
        # Connect to the MCP server with explicit connection options
        async with Client(
            server_name, 
            connect_timeout=30,
            verbose=True,
            retry_delay=1,
            max_retries=5
        ) as client:
            print("Connected successfully")
            # Call the exampletool and print the result
            print("Calling exampletool...")
            result = await client.call_tool("exampletool")
            print("Example tool result:", result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))