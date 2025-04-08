package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

func main() {
	fmt.Println("Testing MCP connection...")

	// Test initialize request
	req := map[string]interface{}{
		"version":     "0.1",
		"messageType": "initializeRequest",
		"message":     map[string]interface{}{},
	}

	resp, err := sendRequest("http://localhost:8085/mcp2", req)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}

	fmt.Println("Connection successful!")
	fmt.Println("Available tools:")

	if tools, ok := resp["message"].(map[string]interface{})["tools"].([]interface{}); ok {
		for _, tool := range tools {
			t := tool.(map[string]interface{})
			fmt.Printf("- %s: %s\n", t["name"], t["description"])
		}
	}
}

func sendRequest(url string, req map[string]interface{}) (map[string]interface{}, error) {
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("error marshaling request: %v", err)
	}

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(reqBody))
	if err != nil {
		return nil, fmt.Errorf("error sending request: %v", err)
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading response: %v", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("server returned error: %s - %s", resp.Status, string(body))
	}

	var respMap map[string]interface{}
	if err := json.Unmarshal(body, &respMap); err != nil {
		return nil, fmt.Errorf("error unmarshaling response: %v", err)
	}

	return respMap, nil
}
