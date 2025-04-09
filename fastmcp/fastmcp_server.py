#!/usr/bin/env python3

from mcp.server.fastmcp import FastMCP
import json
import subprocess
import os

mcp = FastMCP("Radius-FastMCP-Server", description="This MCP Server exposes information that is available via common Radius commands for your cluster")

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
    Get the version of Radius that is running locally.
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



@mcp.tool(name="radius_list_apps", description="List applications deployed using Radius, optionally this may be filtered by resource group.")
def radius_list_apps(group_name: str = ""):
    """
    List applications deployed on Radius, optionally filtered by resource group.

    Parameters:
        group_name (str, optional): The name of the resource group, a filter for the list of applications.
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


@mcp.tool(name="radius_list_resource", description="List details of resources deployed using Radius for a input resource-type. Possible values of input resource-type are 'containers' or 'rediscaches'.")
def radius_list_resource(resource_type: str = ""):
    """
    List details of resources deployed using Radius for a required input resource-type. Possible values of input resource-type are 'containers' or 'rediscaches'.

    Parameters:
        resource_type (str): The name of the resource-type, we need retrieve details for resources of the resource-type.
    """
    try:
        if not resource_type:
            raise ValueError("Please specify which resource-type we need details for. Currently supported values are 'containers' or 'rediscaches'.")
            
        if resource_type not in ["containers", "rediscaches"]:
            raise ValueError(f"Unsupported resource type: {resource_type}. Currently supported values are 'containers' or 'rediscaches'.")

        # Prepare the command with resource type
        command = ["rad", "resource", "list", "-o", "json", resource_type]
        
        # Execute the rad resource list command and capture its output
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        resources_output = result.stdout.strip()
        
        # Parse the JSON output
        try:
            resources_data = json.loads(resources_output)
            # Return the structured data
            mcp_data = {
                "resources": resources_data,
                "status": "success",
                "resource_type": resource_type
            }
        except json.JSONDecodeError:
            # If the output is not valid JSON, return it as plain text
            mcp_data = {
                "resources": resources_output,
                "status": "success",
                "format": "text",
                "resource_type": resource_type
            }
    except subprocess.SubprocessError as e:
        # Handle any errors running the command
        mcp_data = {
            "error": f"Failed to list Radius {resource_type}: {str(e)}",
            "status": "error",
            "resource_type": resource_type
        }
    except ValueError as e:
        # Handle validation errors
        mcp_data = {
            "error": str(e),
            "status": "error",
            "resource_type": resource_type
        }
    except Exception as e:
        # Handle any other unexpected errors
        mcp_data = {
            "error": f"Unexpected error: {str(e)}",
            "status": "error",
            "resource_type": resource_type
        }
    
    return json.dumps(mcp_data)

#@mcp.tool(name="radius_deploy", description="Deploy a Bicep file using Radius.")
#def radius_deploy(bicep_file: str = ""):
#    """
#    Deploy a Bicep file using Radius and return the deployment results.

#   Parameters:
#        bicep_file (str): The path to the Bicep file (.bicep extension) to deploy.
#    """
#    try:
#        if not bicep_file:
#            raise ValueError("Please specify the path to the Bicep file to deploy.")
            
#        if not bicep_file.endswith('.bicep'):
#            raise ValueError(f"Invalid file format. Expected a file with .bicep extension, got: {bicep_file}")

#        if not os.path.exists(bicep_file):
#            raise ValueError(f"Bicep file not found: {bicep_file}")

#        # Prepare the command to deploy the Bicep file
#        command = ["rad", "deploy", "-o", "json", bicep_file]
        
        # Execute the rad deploy command and capture its output
        # Note: This will wait for the deployment to complete
#        result = subprocess.run(command, capture_output=True, text=True, check=True)
#        deploy_output = result.stdout.strip()
        
        # Parse the JSON output
#        try:
#            deploy_data = json.loads(deploy_output)
#            # Return the structured data
#            mcp_data = {
#                "deployment": deploy_data,
#                "status": "success",
#                "bicep_file": bicep_file
#            }
#        except json.JSONDecodeError:
#            # If the output is not valid JSON, return it as plain text
#            mcp_data = {
#                "deployment": deploy_output,
#                "status": "success",
#                "format": "text",
#                "bicep_file": bicep_file
#            }
#    except subprocess.SubprocessError as e:
#        # Handle any errors running the command
#        mcp_data = {
#            "error": f"Failed to deploy Bicep file: {str(e)}",
#            "stderr": e.stderr if hasattr(e, 'stderr') else None,
#            "status": "error",
#            "bicep_file": bicep_file
#        }
#    except ValueError as e:
        # Handle validation errors
#        mcp_data = {
#            "error": str(e),
#            "status": "error",
#            "bicep_file": bicep_file
#        }
#    except Exception as e:
#        # Handle any other unexpected errors
#        mcp_data = {
#            "error": f"Unexpected error: {str(e)}",
#            "status": "error",
#            "bicep_file": bicep_file
#        }
    
#    return json.dumps(mcp_data)

if __name__ == "__main__":
    mcp.run()