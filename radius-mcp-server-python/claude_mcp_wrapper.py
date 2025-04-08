#!/usr/bin/env python3
"""
Wrapper script for Radius MCP Server to be used with Claude Desktop.
This script implements a simplified MCP server that directly executes Radius commands
and formats responses according to the MCP protocol expectations.
"""

import sys
import os
import json
import logging
import subprocess
import threading
import traceback
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import time
import platform
from pathlib import Path

# Configure logging to stderr with more detail
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

logger = logging.getLogger(__name__)

# Get the current directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Search for rad command in common locations if not in PATH
def find_rad_command():
    # Check if rad is in PATH
    rad_path = shutil.which("rad")
    if rad_path:
        return rad_path
    
    # Try common locations
    common_locations = [
        "/usr/local/bin/rad",
        "/usr/bin/rad",
        str(Path.home() / "bin" / "rad"),
        "/opt/homebrew/bin/rad"
    ]
    
    for location in common_locations:
        if os.path.isfile(location) and os.access(location, os.X_OK):
            logger.info(f"Found rad command at {location}")
            return location
    
    return None

# Find rad command
RAD_PATH = find_rad_command()
RAD_AVAILABLE = RAD_PATH is not None
logger.info(f"Radius CLI ('rad') found: {RAD_AVAILABLE}, path: {RAD_PATH}")

# Print environment info
logger.info(f"OS: {platform.system()} {platform.release()}")
logger.info(f"Python: {sys.version}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"PATH: {os.environ.get('PATH')}")
logger.info(f"Home directory: {Path.home()}")

class RadiusTool:
    def __init__(self, name, description, command, args, schema=None):
        self.name = name
        self.description = description
        self.command = command
        self.args = args
        self.schema = schema or {}

# Define available tools
TOOLS = {
    "radius_version": RadiusTool(
        name="radius_version",
        description="Get the Radius CLI version" if RAD_AVAILABLE else "Get the Radius CLI version (UNAVAILABLE: 'rad' command not found)",
        command=RAD_PATH if RAD_PATH else "rad",
        args=["version"]
    ),
    "radius_list_applications": RadiusTool(
        name="radius_list_applications",
        description="List all Radius applications" if RAD_AVAILABLE else "List all Radius applications (UNAVAILABLE: 'rad' command not found)",
        command=RAD_PATH if RAD_PATH else "rad",
        args=["app", "list"]
    ),
    "radius_show_application": RadiusTool(
        name="radius_show_application",
        description="Get details of a Radius application" if RAD_AVAILABLE else "Get details of a Radius application (UNAVAILABLE: 'rad' command not found)",
        command=RAD_PATH if RAD_PATH else "rad",
        args=["app", "show"]
    ),
    "radius_deploy_application": RadiusTool(
        name="radius_deploy_application", 
        description="Deploy a Radius application" if RAD_AVAILABLE else "Deploy a Radius application (UNAVAILABLE: 'rad' command not found)",
        command=RAD_PATH if RAD_PATH else "rad",
        args=["deploy"]
    )
}

# Create standard metadata structure
METADATA = {
    "title": "Radius MCP Server",
    "description": "Access Radius CLI tools for managing applications" if RAD_AVAILABLE else "Access Radius CLI tools for managing applications (NOTE: 'rad' command not found in PATH)",
    "tools": [
        {
            "name": tool_name,
            "description": tool.description
        } for tool_name, tool in TOOLS.items()
    ],
    "version": "1.0.0"
}

def execute_radius_command(tool_name, params=None):
    """Execute a Radius CLI command and return the result"""
    params = params or {}
    
    if tool_name not in TOOLS:
        return {"error": f"Unknown tool: {tool_name}"}
    
    # If Radius CLI is not available, return a mock response
    if not RAD_AVAILABLE:
        logger.warning(f"Cannot execute {tool_name} because 'rad' command is not available")
        return {
            "output": f"ERROR: Cannot execute {tool_name} because 'rad' command is not available in PATH.\n"
                     f"Please make sure the Radius CLI is installed and in your PATH.",
            "error": "Radius CLI ('rad') not found"
        }
    
    tool = TOOLS[tool_name]
    command_args = [tool.command] + tool.args.copy()
    
    # Add parameters based on the tool
    if tool_name == "radius_list_applications":
        if params.get("group"):
            command_args.extend(["-g", params["group"]])
            
    elif tool_name == "radius_show_application":
        if not params.get("application"):
            return {"error": "Application name is required"}
        command_args.append(params["application"])
        
        if params.get("application"):
            command_args.extend(["-a", params["application"]])
            
    elif tool_name == "radius_deploy_application":
        if not params.get("file"):
            return {"error": "File path is required"}
        command_args.append(params["file"])
        
        if params.get("application"):
            command_args.extend(["-a", params["application"]])
        
        if params.get("environment"):
            command_args.extend(["-e", params["environment"]])
    
    logger.info(f"Executing command: {' '.join(command_args)}")
    
    try:
        result = subprocess.run(
            command_args,
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        
        if result.returncode != 0:
            error_msg = f"Command failed with exit code {result.returncode}: {result.stderr.strip()}"
            logger.error(error_msg)
            return {"output": error_msg, "error": error_msg}
        
        output = result.stdout.strip()
        response = {"output": output}
        
        # Try to parse output as JSON for certain commands
        if tool_name in ["radius_list_applications", "radius_show_application"]:
            if output and (output.startswith('{') or output.startswith('[')):
                try:
                    response["data"] = json.loads(output)
                except json.JSONDecodeError:
                    pass
                    
        return response
        
    except Exception as e:
        error_msg = f"Error executing command: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {"output": error_msg, "error": error_msg}

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    daemon_threads = True

class MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MCP protocol"""
    protocol_version = 'HTTP/1.1'  # Use HTTP/1.1 for keep-alive
    
    def log_message(self, format, *args):
        """Override to log to our logger instead of stderr directly"""
        logger.info(format % args)
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        logger.debug("Received OPTIONS request")
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')  # 24 hours
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests for SSE stream"""
        logger.debug(f"Received GET request for path: {self.path}")
        if self.path.startswith('/mcp') or self.path.startswith('/mcp2'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache, no-transform')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Send initial connection event
            client_id = f"client-{threading.get_ident()}"
            logger.info(f"Setting up SSE stream for client {client_id}")
            self.wfile.write(f'event: connection\ndata: {{"status":"connected","clientId":"{client_id}"}}\n\n'.encode())
            self.wfile.flush()
            
            # Keep the connection open
            try:
                while True:
                    # Send keep-alive comment every 15 seconds
                    self.wfile.write(':\n\n'.encode())
                    self.wfile.flush()
                    time.sleep(15)
            except (ConnectionError, BrokenPipeError):
                logger.info(f"Client {client_id} disconnected")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not found')
    
    def do_POST(self):
        """Handle POST requests for MCP commands"""
        if self.path.startswith('/mcp') or self.path.startswith('/mcp2'):
            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            logger.debug(f"Received POST request with body: {body}")
            
            # Set response headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            try:
                request = json.loads(body)
                logger.debug(f"Parsed request: {json.dumps(request)}")
                
                # Handle MCP protocol requests
                if request.get("jsonrpc") == "2.0":
                    # Handle JSON-RPC 2.0 requests
                    request_id = request.get("id")
                    method = request.get("method", "")
                    params = request.get("params", {})
                    
                    logger.info(f"Handling JSON-RPC 2.0 request - method: {method}, id: {request_id}")
                    
                    if method == "initialize":
                        # Handle initialization request
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                                "capabilities": {
                                    "schema": "2024-11-05"
                                },
                                "serverInfo": {
                                    "name": "Radius MCP Server",
                                    "version": "1.0.0"
                                }
                            }
                        }
                    elif method == "getMetadata":
                        # Get metadata about available tools
                        response = {
                            "jsonrpc": "2.0", 
                            "id": request_id,
                            "result": METADATA
                        }
                        logger.info(f"Sending metadata with {len(METADATA['tools'])} tools")
                    elif method == "getToolSpec":
                        # Get specification for a specific tool
                        tool_name = params.get("toolName", "")
                        logger.info(f"Providing spec for tool: {tool_name}")
                        
                        if tool_name in TOOLS:
                            tool = TOOLS[tool_name]
                            
                            # Create parameter schema based on tool
                            param_schema = {"type": "object", "properties": {}, "additionalProperties": False}
                            if tool_name == "radius_list_applications":
                                param_schema["properties"]["namespace"] = {
                                    "type": "string",
                                    "description": "Kubernetes namespace"
                                }
                            elif tool_name == "radius_show_application":
                                param_schema["properties"]["name"] = {
                                    "type": "string", 
                                    "description": "Application name"
                                }
                                param_schema["properties"]["namespace"] = {
                                    "type": "string",
                                    "description": "Kubernetes namespace"
                                }
                                param_schema["required"] = ["name"]
                            elif tool_name == "radius_deploy_application":
                                param_schema["properties"]["file"] = {
                                    "type": "string",
                                    "description": "Path to the Bicep file"
                                }
                                param_schema["properties"]["name"] = {
                                    "type": "string",
                                    "description": "Application name"
                                }
                                param_schema["properties"]["namespace"] = {
                                    "type": "string",
                                    "description": "Kubernetes namespace"
                                }
                                param_schema["required"] = ["file"]
                                
                            response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {
                                    "name": tool_name,
                                    "description": tool.description,
                                    "inputSchema": param_schema,
                                    "outputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "output": {
                                                "type": "string",
                                                "description": "Command output"
                                            },
                                            "data": {
                                                "type": ["object", "array", "null"],
                                                "description": "Parsed JSON data (if available)"
                                            }
                                        }
                                    }
                                }
                            }
                        else:
                            response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32602,
                                    "message": f"Unknown tool: {tool_name}"
                                }
                            }
                    elif method == "executeTool":
                        # Execute a tool
                        tool_name = params.get("toolName", "")
                        tool_params = params.get("toolParams", {})
                        
                        logger.info(f"Executing tool {tool_name} with params {tool_params}")
                        
                        try:
                            if tool_name in TOOLS:
                                result = execute_radius_command(tool_name, tool_params)
                                logger.debug(f"Tool execution result: {result}")
                                
                                if "error" in result:
                                    # For Radius CLI unavailable, return as a successful result but with an error message
                                    # This allows Claude to see the error and explain it properly
                                    if not RAD_AVAILABLE:
                                        response = {
                                            "jsonrpc": "2.0",
                                            "id": request_id,
                                            "result": result
                                        }
                                    else:
                                        response = {
                                            "jsonrpc": "2.0",
                                            "id": request_id,
                                            "error": {
                                                "code": -32000,
                                                "message": result["error"]
                                            }
                                        }
                                else:
                                    response = {
                                        "jsonrpc": "2.0",
                                        "id": request_id,
                                        "result": result
                                    }
                            else:
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {
                                        "code": -32602,
                                        "message": f"Unknown tool: {tool_name}"
                                    }
                                }
                        except Exception as e:
                            logger.error(f"Error executing tool: {str(e)}")
                            logger.error(traceback.format_exc())
                            response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32000,
                                    "message": f"Error executing tool: {str(e)}"
                                }
                            }
                    else:
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32601,
                                "message": f"Method not found: {method}"
                            }
                        }
                else:
                    # Non JSON-RPC format, try to handle legacy MCP protocol
                    message_type = request.get("messageType")
                    logger.info(f"Handling legacy MCP request - messageType: {message_type}")
                    
                    if message_type == "registerSSEClient":
                        response = {"status": "registered"}
                    elif message_type == "getMeta":
                        # Handle metadata request in legacy format
                        response = {"title": METADATA["title"], "tools": METADATA["tools"]}
                    elif message_type == "toolExecution":
                        tool_name = request.get("toolName")
                        tool_params = request.get("parameters", {})
                        
                        if tool_name in TOOLS:
                            response = execute_radius_command(tool_name, tool_params)
                        else:
                            response = {"error": f"Unknown tool: {tool_name}"}
                    else:
                        response = {"error": f"Unknown message type: {message_type}"}
                
                # Send response
                response_json = json.dumps(response)
                logger.info(f"Sending response: {response_json[:200]}...")
                logger.debug(f"Full response: {response_json}")
                
                self.wfile.write(response_json.encode('utf-8'))
                self.wfile.flush()
                
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in request body: {str(e)}"
                logger.error(error_msg)
                self.wfile.write(json.dumps({"error": error_msg}).encode('utf-8'))
            except Exception as e:
                error_msg = f"Error processing request: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                self.wfile.write(json.dumps({"error": error_msg}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not found')

def announce_mcp_capabilities():
    logger.info(f"Server supports the following tools:")
    for name, tool in TOOLS.items():
        logger.info(f"  - {name}: {tool.description}")
    if not RAD_AVAILABLE:
        logger.warning("NOTE: The 'rad' command is not available in the PATH. Tool calls will return mock responses.")

def run_server(port=8085):
    """Run the MCP server on the specified port"""
    try:
        if not RAD_AVAILABLE:
            logger.warning("Radius CLI ('rad') is not available in the PATH.")
            logger.warning("The server will start, but tool executions will return error messages.")
            logger.warning("Make sure the Radius CLI is installed and in the PATH if you want to use these tools.")
            logger.warning("Known locations to look for: /usr/local/bin/rad, /usr/bin/rad, ~/bin/rad")
            logger.warning("You can confirm the location with 'which rad' in your terminal.")
            
            # Check if we're in a virtual environment
            if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
                logger.info("Running in a Python virtual environment.")
                logger.warning("Note that the virtual environment might have a different PATH than your regular shell.")
        else:
            logger.info(f"Using Radius CLI at: {RAD_PATH}")
            # Try running a simple command to verify
            try:
                result = subprocess.run(
                    [RAD_PATH, "version"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    logger.info(f"Radius CLI test successful: {result.stdout.strip()}")
                else:
                    logger.warning(f"Radius CLI test failed: {result.stderr.strip()}")
            except Exception as e:
                logger.error(f"Error testing Radius CLI: {str(e)}")
        
        # Print available tools
        announce_mcp_capabilities()
        
        # Start the server
        server = ThreadedHTTPServer(('0.0.0.0', port), MCPRequestHandler)
        logger.info(f"Starting Radius MCP server on port {port} (endpoints: /mcp and /mcp2)")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
    return 0

if __name__ == "__main__":
    logger.info("Starting Claude MCP wrapper with debugging enabled")
    sys.exit(run_server())