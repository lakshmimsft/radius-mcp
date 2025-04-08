#!/usr/bin/env python3

import json
import logging
import os
import subprocess
import queue
import threading
import time
from typing import Dict, List, Any, Optional

from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
from mcp.server.fastmcp import FastMCP, Context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Create FastMCP Server instance
mcp = FastMCP("Radius MCP Server")

# Create SSE message queue for clients
sse_queues = {}
sse_queue_lock = threading.Lock()

# Define Radius Tool class (for organization of tool definitions)
class RadiusTool:
    def __init__(self, name: str, description: str, command: str, args: List[str], parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.command = command
        self.args = args
        self.parameters = parameters

# Define available Radius tools
radius_tools = [
    RadiusTool(
        name="radius_version",
        description="Get the Radius CLI version",
        command="rad",
        args=["version"],
        parameters={
            "type": "object",
            "properties": {}
        }
    ),
    RadiusTool(
        name="radius_list_applications",
        description="List all Radius applications",
        command="rad",
        args=["app", "list"],
        parameters={
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace"
                }
            }
        }
    ),
    RadiusTool(
        name="radius_show_application",
        description="Get details of a Radius application",
        command="rad",
        args=["app", "show"],
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Application name"
                },
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace"
                }
            },
            "required": ["name"]
        }
    ),
    RadiusTool(
        name="radius_deploy_application",
        description="Deploy a Radius application",
        command="rad",
        args=["deploy"],
        parameters={
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Path to the Bicep file"
                },
                "name": {
                    "type": "string",
                    "description": "Application name"
                },
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace"
                }
            },
            "required": ["file"]
        }
    ),
]

# Execute Radius tool and return results
def execute_radius_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    # Find the requested tool
    selected_tool = None
    for tool in radius_tools:
        if tool.name == tool_name:
            selected_tool = tool
            break
    
    if not selected_tool:
        raise ValueError(f"Tool not found: {tool_name}")
    
    # Copy the base args
    args = selected_tool.args.copy()
    
    # Add parameters to the command based on the tool
    if tool_name == "radius_list_applications":
        if params.get("namespace"):
            args.extend(["-n", params["namespace"]])
    
    elif tool_name == "radius_show_application":
        name = params.get("name")
        if not name:
            raise ValueError("Application name is required")
        args.append(name)
        
        if params.get("namespace"):
            args.extend(["-n", params["namespace"]])
    
    elif tool_name == "radius_deploy_application":
        file_path = params.get("file")
        if not file_path:
            raise ValueError("Bicep file path is required")
        args.append(file_path)
        
        if params.get("name"):
            args.extend(["-n", params["name"]])
        
        if params.get("namespace"):
            args.extend(["--namespace", params["namespace"]])
    
    # Log the command being executed
    cmd_str = f"{selected_tool.command} {' '.join(args)}"
    logger.info(f"Executing command: {cmd_str}")
    
    try:
        # Execute the command
        result = subprocess.run(
            [selected_tool.command] + args,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Process output
        output = result.stdout
        response = {"output": output}
        
        # For certain commands, try to parse output as JSON
        if tool_name in ["radius_list_applications", "radius_show_application"]:
            output_stripped = output.strip()
            if output_stripped.startswith('{') or output_stripped.startswith('['):
                try:
                    parsed_data = json.loads(output_stripped)
                    response["data"] = parsed_data
                except json.JSONDecodeError:
                    pass  # If not valid JSON, just return the raw output
        
        return response
    
    except subprocess.CalledProcessError as e:
        error_msg = f"Command execution failed: {e} - {e.stderr}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

# Set up MCP tool handlers using the FastMCP framework
@mcp.tool()
def radius_version() -> Dict[str, Any]:
    """Get the Radius CLI version"""
    return execute_radius_tool("radius_version", {})

@mcp.tool()
def radius_list_applications(namespace: Optional[str] = None) -> Dict[str, Any]:
    """List all Radius applications"""
    return execute_radius_tool("radius_list_applications", {"namespace": namespace})

@mcp.tool()
def radius_show_application(name: str, namespace: Optional[str] = None) -> Dict[str, Any]:
    """Get details of a Radius application"""
    return execute_radius_tool("radius_show_application", {"name": name, "namespace": namespace})

@mcp.tool()
def radius_deploy_application(file: str, name: Optional[str] = None, namespace: Optional[str] = None) -> Dict[str, Any]:
    """Deploy a Radius application"""
    return execute_radius_tool("radius_deploy_application", {"file": file, "name": name, "namespace": namespace})

# Integrate FastMCP with Flask
@app.route('/mcp', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/mcp2', methods=['GET', 'POST', 'OPTIONS'])
def handle_mcp_request():
    # Set CORS headers for all requests
    response_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no'
    }
    
    # Log request details
    logger.info(f"Request from: {request.remote_addr} {request.method} {request.path}")
    
    # Handle OPTIONS requests (preflight)
    if request.method == 'OPTIONS':
        return '', 200, response_headers
    
    # Handle GET requests for SSE - use Flask's native streaming response
    if request.method == 'GET':
        logger.info(f"Handling SSE connection request from {request.remote_addr}")
        
        # Set headers for SSE
        sse_headers = {
            **response_headers,
            'Content-Type': 'text/event-stream',
            'Connection': 'keep-alive',
        }
        
        def generate_sse_events():
            """Generator function to produce SSE events using Flask's streaming response"""
            # Generate a unique client ID
            client_id = request.args.get('client_id', f"flask-client-{id(request)}")
            logger.info(f"Setting up SSE stream for client {client_id}")
            
            # Create a queue for this client
            message_queue = queue.Queue()
            
            # Register the client's queue
            with sse_queue_lock:
                sse_queues[client_id] = message_queue
            
            try:
                # Send an initial connection event
                yield 'event: connection\ndata: {"status":"connected","clientId":"' + client_id + '"}\n\n'
                
                # Keep the connection open and yield messages as they come
                while True:
                    try:
                        # Get next message with a timeout (so we can send keep-alive periodically)
                        message = message_queue.get(block=True, timeout=30)
                        
                        if message is None:  # None is used as a sentinel to end the stream
                            logger.info(f"Closing SSE stream for client {client_id}")
                            break
                        
                        # Format as SSE
                        if isinstance(message, dict):
                            message = json.dumps(message)
                        
                        logger.debug(f"Sending SSE message to client {client_id}: {message[:100]}...")
                        yield f'data: {message}\n\n'
                        
                    except queue.Empty:
                        # Send keep-alive comment to prevent connection timeout
                        yield ':\n\n'  # SSE comment for keep-alive
            
            except Exception as e:
                logger.error(f"SSE stream error for client {client_id}: {str(e)}")
                # Send error message
                yield f'event: error\ndata: {{"error": "{str(e)}"}}\n\n'
            
            finally:
                # Clean up client queue
                with sse_queue_lock:
                    if client_id in sse_queues:
                        del sse_queues[client_id]
                logger.info(f"SSE stream closed for client {client_id}")
        
        return Response(
            stream_with_context(generate_sse_events()),
            headers=sse_headers
        )
    
    # Handle POST requests for regular API calls
    elif request.method == 'POST':
        logger.info(f"Handling POST request from {request.remote_addr}")
        
        # Get the request data
        request_data = request.get_json(silent=True)
        if not request_data:
            error_msg = "Invalid JSON in request body"
            logger.error(error_msg)
            return {"error": error_msg}, 400, response_headers
        
        message_type = request_data.get("messageType")
        logger.info(f"Received {message_type} request")
        
        # Set response content type
        response_headers['Content-Type'] = 'application/json'
        
        # Handle SSE client registration
        if message_type == "registerSSEClient" and "clientId" in request_data:
            client_id = request_data["clientId"]
            logger.info(f"Registering SSE client: {client_id}")
            
            # Make sure the client has a queue
            with sse_queue_lock:
                if client_id not in sse_queues:
                    sse_queues[client_id] = queue.Queue()
            
            return {"status": "registered"}, 200, response_headers
        
        # Handle tool execution - use FastMCP to process the request
        try:
            # Process the request with FastMCP
            response_data = mcp.handle_message(request_data)
            
            # If this is a streaming response (like for tools that produce incremental output)
            # send updates to the appropriate SSE client
            if "clientId" in request_data and request_data.get("streaming", False):
                client_id = request_data["clientId"]
                with sse_queue_lock:
                    if client_id in sse_queues:
                        # Send response through SSE
                        sse_queues[client_id].put(response_data)
                        # Return a simple acknowledgment via HTTP
                        return {"status": "streaming"}, 200, response_headers
            
            # Otherwise just return the response directly
            logger.info(f"Successfully processed {message_type} request")
            return response_data, 200, response_headers
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}, 500, response_headers

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8085))
    logger.info(f"Starting Radius MCP server on port {port} (endpoints: /mcp and /mcp2)...")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)