#!/usr/bin/env python3
"""
Example client for the stdio-based Radius MCP Server.
This script demonstrates how to use the stdio MCP server by spawning it as a subprocess
and communicating with it using stdin/stdout pipes.
"""

import json
import subprocess
import sys
import time
import uuid

def main():
    # Start the stdio MCP server as a subprocess
    print("Starting stdio MCP server subprocess...")
    server_process = subprocess.Popen(
        [sys.executable, "/Users/lakshmi/repos/radius-mcp/radius-mcp-server-python/stdio_mcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,  # Redirect server logs to our stderr
        text=True,
        bufsize=1  # Line buffered
    )
    
    # Give the server a moment to initialize
    time.sleep(1)
    
    try:
        # Initialize connection with the server
        print("\nSending initialize request...")
        response = send_request(server_process, {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05"
            }
        })
        print(f"Server initialized: {json.dumps(response, indent=2)}")
        
        # Get metadata about available tools
        print("\nFetching available tools...")
        response = send_request(server_process, {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "getMetadata",
            "params": {}
        })
        print(f"Available tools: {json.dumps(response['result']['tools'], indent=2)}")
        
        # Get the specification for a specific tool
        print("\nFetching tool specification for radius_version...")
        response = send_request(server_process, {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "getToolSpec",
            "params": {
                "toolName": "radius_version"
            }
        })
        print(f"Tool specification: {json.dumps(response.get('result', response), indent=2)}")
        
        # Execute the radius_version tool
        print("\nExecuting radius_version tool...")
        response = send_request(server_process, {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "executeTool",
            "params": {
                "toolName": "radius_version",
                "toolParams": {}
            }
        })
        
        # Check if the result contains an error
        if "error" in response:
            print(f"Error executing tool: {json.dumps(response['error'], indent=2)}")
        else:
            result = response.get("result", {})
            print(f"Tool execution result:")
            print(f"Output: {result.get('output', 'No output')}")
            if "data" in result:
                print(f"Data: {json.dumps(result['data'], indent=2)}")
        
        # Example of executing another tool
        print("\nExecuting radius_list_applications tool...")
        response = send_request(server_process, {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "executeTool",
            "params": {
                "toolName": "radius_list_applications",
                "toolParams": {}
            }
        })
        
        # Check if the result contains an error
        if "error" in response:
            print(f"Error executing tool: {json.dumps(response['error'], indent=2)}")
        else:
            result = response.get("result", {})
            print(f"Tool execution result:")
            print(f"Output: {result.get('output', 'No output')}")
            if "data" in result:
                print(f"Data: {json.dumps(result['data'], indent=2)}")
            
    finally:
        # Clean up and terminate the server process
        print("\nTerminating MCP server subprocess...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Server did not terminate gracefully, forcing kill...")
            server_process.kill()

def send_request(process, request):
    """
    Send a JSON request to the stdio MCP server subprocess and get the response.
    
    Args:
        process: The subprocess.Popen object representing the server
        request: Dictionary containing the request to send
    
    Returns:
        Dictionary containing the parsed JSON response
    """
    # Convert the request to JSON and send it to the server
    request_json = json.dumps(request)
    print(f">> Sending: {request_json}")
    process.stdin.write(request_json + "\n")
    process.stdin.flush()
    
    # Read the response line from the server
    response_line = process.stdout.readline().strip()
    print(f"<< Received: {response_line}")
    
    try:
        response = json.loads(response_line)
        return response
    except json.JSONDecodeError as e:
        print(f"Error decoding response: {e}")
        return {"error": f"Failed to decode response: {e}"}

if __name__ == "__main__":
    main()