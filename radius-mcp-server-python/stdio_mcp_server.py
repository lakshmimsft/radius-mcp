#!/usr/bin/env python3
"""
Radius MCP Server using stdio (standard input/output) for communication.

This implementation provides the same Radius CLI tool functionality as the HTTP/SSE versions
but communicates through stdin/stdout, making it suitable for direct process-to-process
communication without requiring HTTP.
"""

import json
import logging
import os
import subprocess
import sys
import traceback
import shutil
from pathlib import Path
import platform
import time

# Configure logging to stderr
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG level for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

logger = logging.getLogger(__name__)

# Search for rad command in common locations if not in PATH
def find_rad_command():
    """Find the 'rad' command executable in common locations."""
    rad_path = shutil.which("rad")
    if rad_path:
        return rad_path
    
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
    """Define a Radius CLI tool with metadata."""
    def __init__(self, name, description, command, args, schema=None):
        self.name = name
        self.description = description
        self.command = command
        self.args = args
        self.schema = schema or {}

# Define available Radius tools
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
    "title": "Radius MCP Server (stdio)",
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
    """Execute a Radius CLI command and return the result."""
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
        if params.get("namespace"):
            command_args.extend(["-n", params["namespace"]])
            
    elif tool_name == "radius_show_application":
        name = params.get("name")
        if not name:
            return {"error": "Application name is required"}
        command_args.append(name)
        
        if params.get("namespace"):
            command_args.extend(["-n", params["namespace"]])
            
    elif tool_name == "radius_deploy_application":
        file_path = params.get("file")
        if not file_path:
            return {"error": "Bicep file path is required"}
        command_args.append(file_path)
        
        if params.get("name"):
            command_args.extend(["-n", params["name"]])
        
        if params.get("namespace"):
            command_args.extend(["--namespace", params["namespace"]])
    
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

def announce_capabilities():
    """Log the server's capabilities to stderr."""
    logger.info("Radius MCP Server (stdio) is ready")
    logger.info(f"Server supports the following tools:")
    for name, tool in TOOLS.items():
        logger.info(f"  - {name}: {tool.description}")
    if not RAD_AVAILABLE:
        logger.warning("NOTE: The 'rad' command is not available in the PATH. Tool calls will return mock responses.")
    logger.info("Waiting for JSON input on stdin, one request per line...")

def handle_request(request_data):
    """Process a single MCP request and return a response."""
    try:
        # Check if it's a JSON-RPC 2.0 request
        if request_data.get("jsonrpc") == "2.0":
            request_id = request_data.get("id")
            method = request_data.get("method", "")
            params = request_data.get("params", {})
            
            logger.info(f"Handling JSON-RPC 2.0 request - method: {method}, id: {request_id}")
            
            # If this is a notification (no 'id'), we don't need to send a response
            if request_id is None and method.startswith("notifications/"):
                logger.info(f"Handling notification: {method}")
                return None  # No response needed for notifications
            
            # Initialize response with jsonrpc and id fields
            response = {
                "jsonrpc": "2.0",
                "id": request_id
            }
            
            if method == "initialize":
                # Handle initialization request
                response["result"] = {
                    "protocolVersion": params.get("protocolVersion", "2023-07-01"),  # Changed to an older protocol version for compatibility
                    "capabilities": {
                        "schema": "2023-07-01"
                    },
                    "serverInfo": {
                        "name": "Radius MCP Server (stdio)",
                        "version": "1.0.0"
                    },
                    # Include metadata in initialize response to make it discoverable
                    "metadata": {
                        "title": METADATA["title"],
                        "description": METADATA["description"],
                        "tools": METADATA["tools"]
                    }
                }
                logger.debug(f"Sending initialize response with {len(METADATA['tools'])} tools: {json.dumps(response)}")
            elif method == "getMetadata":
                # Get metadata about available tools
                # Make sure we're returning the correct format for the MCP protocol
                response["result"] = METADATA
                logger.debug(f"Sending metadata response: {json.dumps(response)}")
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
                            
                    response["result"] = {
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
                else:
                    response["error"] = {
                        "code": -32602,
                        "message": f"Unknown tool: {tool_name}"
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
                            # This allows the client to see the error and explain it properly
                            if not RAD_AVAILABLE:
                                response["result"] = result
                            else:
                                response["error"] = {
                                    "code": -32000,
                                    "message": result["error"]
                                }
                        else:
                            response["result"] = result
                    else:
                        response["error"] = {
                            "code": -32602,
                            "message": f"Unknown tool: {tool_name}"
                        }
                except Exception as e:
                    logger.error(f"Error executing tool: {str(e)}")
                    logger.error(traceback.format_exc())
                    response["error"] = {
                        "code": -32000,
                        "message": f"Error executing tool: {str(e)}"
                    }
            else:
                response["error"] = {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
        else:
            # Legacy MCP format
            message_type = request_data.get("messageType")
            logger.info(f"Handling legacy MCP request - messageType: {message_type}")
            
            if message_type == "getMeta":
                # Handle metadata request in legacy format
                response = {"title": METADATA["title"], "description": METADATA["description"], "tools": METADATA["tools"]}
            elif message_type == "toolExecution":
                tool_name = request_data.get("toolName")
                tool_params = request_data.get("parameters", {})
                
                if tool_name in TOOLS:
                    response = execute_radius_command(tool_name, tool_params)
                else:
                    response = {"error": f"Unknown tool: {tool_name}"}
            else:
                response = {"error": f"Unknown message type: {message_type}"}
        
        return response
        
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {"error": error_msg}

def main():
    """Main function to run the stdio MCP server."""
    try:
        # Announce capabilities
        announce_capabilities()
        
        # Process requests from stdin
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
                
            try:
                # Parse JSON request from stdin
                request_data = json.loads(line)
                logger.debug(f"Received request: {json.dumps(request_data)}")
                
                # Process the request
                response = handle_request(request_data)
                
                # Write response to stdout
                if response is not None:  # Only send response if it's not a notification
                    response_json = json.dumps(response)
                    logger.debug(f"Sending response: {response_json}")
                    print(response_json, flush=True)
                
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in request: {str(e)}"
                logger.error(error_msg)
                error_response = {"error": error_msg}
                if isinstance(request_data, dict) and "id" in request_data and "jsonrpc" in request_data:
                    error_response = {
                        "jsonrpc": request_data["jsonrpc"],
                        "id": request_data["id"],
                        "error": {
                            "code": -32700,
                            "message": error_msg
                        }
                    }
                print(json.dumps(error_response), flush=True)
                
            except Exception as e:
                error_msg = f"Error handling request: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                error_response = {"error": error_msg}
                if isinstance(request_data, dict) and "id" in request_data and "jsonrpc" in request_data:
                    error_response = {
                        "jsonrpc": request_data["jsonrpc"],
                        "id": request_data["id"],
                        "error": {
                            "code": -32603,
                            "message": error_msg
                        }
                    }
                print(json.dumps(error_response), flush=True)
                
    except KeyboardInterrupt:
        logger.info("Server shutting down due to keyboard interrupt...")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())