#!/usr/bin/env python3

from mcp.server.fastmcp import FastMCP
import json
import subprocess

mcp = FastMCP("Radius-FastMCP-Server", description="This MCP Server exposes information that is available via common radius commands for your cluster")

@mcp.tool()
def example_tool():
    """
    This just runs an example tool to get some MCP data for testing
    """
    # Replace with actual logic to get MCP data
    mcp_data = {
        "version": "1.0.0",
        "status": "running",
        "players": 10,
        "worlds": ["world", "nether", "the_end"]
    }
    
    return json.dumps(mcp_data)

@mcp.tool()
def radius_version():
    """
    Get the version of Radius that is running.
    """

    try:
        # Execute the rad version command and capture its output
        result = subprocess.run(["rad", "version", "-o", "json"], capture_output=True, text=True, check=True)
        version_output = result.stdout.strip()
        
        # Parse the version output - this assumes rad version returns something like "v1.2.3"
        # You may need to adjust the parsing based on the actual format of rad version output
        version = version_output.replace("v", "").strip() if version_output.startswith("v") else version_output
        
        # Return the structured data
        mcp_data = {
            "version": version,
            "status": "running"
        }
    except subprocess.SubprocessError as e:
        # Handle any errors running the command
        mcp_data = {
            "error": f"Failed to get Radius version: {str(e)}",
            "status": "error"
        }
    except Exception as e:
        # Handle any other unexpected errors
        mcp_data = {
            "error": f"Unexpected error: {str(e)}",
            "status": "error"
        }
    
    return json.dumps(mcp_data)



@mcp.tool(name="radius_list_apps", description="List applications deployed on Radius, optionally filtered by resource group.")
def radius_list_apps(group_name: str = ""):
    """
    List applications deployed on Radius, optionally filtered by resource group.

    Parameters:
        group_name (str, optional): The name of the resource group to filter applications by.
    """
    try:
        # Prepare the command with optional group filter
        command = ["rad", "app", "list", "-o", "json"]
        if group_name:
            command.extend(["-g", group_name])
        
        # Execute the rad app list command and capture its output
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        apps_output = result.stdout.strip()
        
        # Parse the JSON output
        try:
            apps_data = json.loads(apps_output)
            # Return the structured data
            mcp_data = {
                "applications": apps_data,
                "status": "success",
                "group_filter": group_name if group_name else "all groups"
            }
        except json.JSONDecodeError:
            # If the output is not valid JSON, return it as plain text
            mcp_data = {
                "applications": apps_output,
                "status": "success",
                "format": "text",
                "group_filter": group_name if group_name else "all groups"
            }
    except subprocess.SubprocessError as e:
        # Handle any errors running the command
        mcp_data = {
            "error": f"Failed to list Radius applications: {str(e)}",
            "status": "error",
            "group_filter": group_name if group_name else "all groups"
        }
    except Exception as e:
        # Handle any other unexpected errors
        mcp_data = {
            "error": f"Unexpected error: {str(e)}",
            "status": "error",
            "group_filter": group_name if group_name else "all groups"
        }
    
    return json.dumps(mcp_data)

@mcp.tool()
def radius_version_raw():
    """
    Get the version of Radius that is running.
    """

    try:
        # Execute the rad version command and capture its output
        result = subprocess.run(["rad", "version"], capture_output=True, text=True, check=True)
        version_output = result.stdout.strip()
        
        # Parse the version output - this assumes rad version returns something like "v1.2.3"
        # You may need to adjust the parsing based on the actual format of rad version output
        version = version_output.replace("v", "").strip() if version_output.startswith("v") else version_output
        
        # Return the structured data
        mcp_data = {
            "version": version,
            "status": "running"
        }
    except subprocess.SubprocessError as e:
        # Handle any errors running the command
        mcp_data = {
            "error": f"Failed to get Radius version: {str(e)}",
            "status": "error"
        }
    except Exception as e:
        # Handle any other unexpected errors
        mcp_data = {
            "error": f"Unexpected error: {str(e)}",
            "status": "error"
        }
    
    return mcp_data


if __name__ == "__main__":
    mcp.run()