package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
)

type MCPRequest struct {
	Version     string                 `json:"version"`
	MessageType string                 `json:"messageType"`
	Message     map[string]interface{} `json:"message"`
}

type MCPResponse struct {
	Version     string                 `json:"version"`
	MessageType string                 `json:"messageType"`
	Message     map[string]interface{} `json:"message"`
}

func main() {
	serverURL := "http://localhost:8085/mcp2"
	if len(os.Args) > 1 {
		serverURL = os.Args[1]
	}

	// Initialize the server
	initResponse, err := sendInitializeRequest(serverURL)
	if err != nil {
		fmt.Printf("Error initializing server: %v\n", err)
		os.Exit(1)
	}

	tools := initResponse.Message["tools"].([]interface{})
	fmt.Println("Available tools:")
	for _, t := range tools {
		tool := t.(map[string]interface{})
		fmt.Printf("- %s: %s\n", tool["name"], tool["description"])
	}
	fmt.Println()

	// Example: Call the version tool
	versionResponse, err := sendToolCallRequest(serverURL, "radius_version", map[string]interface{}{})
	if err != nil {
		fmt.Printf("Error calling version tool: %v\n", err)
	} else {
		printToolResponse("radius_version", versionResponse)
	}

	// Example: List applications
	listAppsResponse, err := sendToolCallRequest(serverURL, "radius_list_applications", map[string]interface{}{
		"namespace": "default",
	})
	if err != nil {
		fmt.Printf("Error listing applications: %v\n", err)
	} else {
		printToolResponse("radius_list_applications", listAppsResponse)
	}
}

func sendInitializeRequest(serverURL string) (*MCPResponse, error) {
	req := MCPRequest{
		Version:     "0.1",
		MessageType: "initializeRequest",
		Message:     map[string]interface{}{},
	}

	return sendRequest(serverURL, req)
}

func sendToolCallRequest(serverURL, toolName string, parameters map[string]interface{}) (*MCPResponse, error) {
	req := MCPRequest{
		Version:     "0.1",
		MessageType: "toolCallRequest",
		Message: map[string]interface{}{
			"toolCalls": []map[string]interface{}{
				{
					"toolCallId": "call-" + toolName,
					"name":       toolName,
					"parameters": parameters,
				},
			},
		},
	}

	return sendRequest(serverURL, req)
}

func sendRequest(serverURL string, req MCPRequest) (*MCPResponse, error) {
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("error marshaling request: %v", err)
	}

	resp, err := http.Post(serverURL, "application/json", bytes.NewBuffer(reqBody))
	if err != nil {
		return nil, fmt.Errorf("error sending request: %v", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading response: %v", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("server returned error: %s - %s", resp.Status, string(body))
	}

	var mcpResponse MCPResponse
	if err := json.Unmarshal(body, &mcpResponse); err != nil {
		return nil, fmt.Errorf("error unmarshaling response: %v", err)
	}

	return &mcpResponse, nil
}

func printToolResponse(toolName string, response *MCPResponse) {
	fmt.Printf("Results for %s:\n", toolName)

	if response.MessageType != "toolCallResponse" {
		fmt.Printf("Unexpected message type: %s\n", response.MessageType)
		return
	}

	toolCallResponses := response.Message["toolCallResponses"].([]interface{})
	for _, tcr := range toolCallResponses {
		resp := tcr.(map[string]interface{})

		if errorMsg, hasError := resp["error"]; hasError {
			fmt.Printf("Error: %s\n", errorMsg)
			continue
		}

		results := resp["results"].(map[string]interface{})
		output := results["output"].(string)
		fmt.Printf("Output:\n%s\n", output)

		if data, hasData := results["data"]; hasData {
			fmt.Println("Structured data:")
			prettyData, _ := json.MarshalIndent(data, "", "  ")
			fmt.Println(string(prettyData))
		}
	}
	fmt.Println()
}
