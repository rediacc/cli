package api

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/rediacc/cli/internal/config"
)

// Client represents the API client
type Client struct {
	BaseURL    string
	HTTPClient *http.Client
	config     *config.Config
}

// NewClient creates a new API client
func NewClient(baseURL string) *Client {
	return &Client{
		BaseURL: baseURL,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		config: config.Get(),
	}
}

// Request represents an API request
type Request struct {
	Method     string                 `json:"method"`
	Procedure  string                 `json:"procedure"`
	Parameters map[string]interface{} `json:"parameters"`
}

// Response represents an API response
type Response struct {
	Success bool                     `json:"success"`
	Data    []map[string]interface{} `json:"data"`
	Error   string                   `json:"error,omitempty"`
	Message string                   `json:"message,omitempty"`
}

// AuthResponse represents an authentication response
type AuthResponse struct {
	Success           bool   `json:"success"`
	SessionToken      string `json:"session_token"`
	RequestCredential string `json:"request_credential"`
	Message           string `json:"message"`
	Error             string `json:"error,omitempty"`
}

// MiddlewareResponse represents the middleware API response format
type MiddlewareResponse struct {
	Failure int                    `json:"failure"`
	Errors  []string               `json:"errors"`
	Tables  []MiddlewareTable      `json:"tables"`
	Outputs map[string]interface{} `json:"outputs"`
}

// MiddlewareTable represents a result set from stored procedure
type MiddlewareTable struct {
	ResultSetIndex int                      `json:"resultSetIndex"`
	Data           []map[string]interface{} `json:"data"`
}

// ExecuteStoredProcedure executes a stored procedure via the middleware API
func (c *Client) ExecuteStoredProcedure(procedure string, params map[string]interface{}) (*Response, error) {
	// Convert parameters to JSON
	jsonData, err := json.Marshal(params)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal parameters: %w", err)
	}

	// Create HTTP request using the correct endpoint format
	url := fmt.Sprintf("%s/api/StoredProcedure/%s", c.BaseURL, procedure)
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	c.setAuthHeaders(req)

	// Execute request
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Read response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Parse middleware response
	var middlewareResp MiddlewareResponse
	if err := json.Unmarshal(body, &middlewareResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	// Handle HTTP errors
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP error: %d", resp.StatusCode)
	}

	// Check for API errors
	if middlewareResp.Failure != 0 {
		if len(middlewareResp.Errors) > 0 {
			return nil, fmt.Errorf("API error: %s", middlewareResp.Errors[0])
		}
		return nil, fmt.Errorf("API error: failure code %d", middlewareResp.Failure)
	}

	// Check for token refresh (nextReqeustCredential in response)
	c.updateTokenFromResponse(&middlewareResp)

	// Convert to old Response format for compatibility
	response := &Response{
		Success: middlewareResp.Failure == 0,
		Data:    []map[string]interface{}{},
	}
	
	// Flatten all table data into the Data field
	for _, table := range middlewareResp.Tables {
		response.Data = append(response.Data, table.Data...)
	}

	return response, nil
}

// Login authenticates the user and stores the session information
func (c *Client) Login(email, password string) (*AuthResponse, error) {
	params := map[string]interface{}{
		"name": "{ }",  // Required parameter for CreateAuthenticationRequest
	}

	// Execute login procedure (this will be routed to protected_CreateAuthenticationRequest)
	response, err := c.executeAuthProcedure("CreateAuthenticationRequest", params, email, password)
	if err != nil {
		return nil, err
	}

	// Update configuration with auth info
	if response.Success {
		if err := config.UpdateAuth(email, response.SessionToken, response.RequestCredential); err != nil {
			return nil, fmt.Errorf("failed to save authentication info: %w", err)
		}

		// Update client config reference
		c.config = config.Get()
	}

	return response, nil
}

// Logout logs out the current user session
func (c *Client) Logout() error {
	if c.config.Auth.RequestCredential == "" {
		return fmt.Errorf("not logged in")
	}

	// Call LogoutUserSession procedure - this is public, so no params needed
	_, err := c.ExecuteStoredProcedure("LogoutUserSession", map[string]interface{}{})
	if err != nil {
		return err
	}

	// Clear auth info
	return config.ClearAuth()
}

// RefreshToken refreshes the authentication token
func (c *Client) RefreshToken() error {
	if c.config.Auth.Email == "" {
		return fmt.Errorf("no email configured for token refresh")
	}

	// For now, we don't have a specific refresh endpoint
	// This would need to be implemented based on the middleware API
	return fmt.Errorf("token refresh not implemented")
}

// executeAuthProcedure executes an authentication-related procedure  
func (c *Client) executeAuthProcedure(procedure string, params map[string]interface{}, email, password string) (*AuthResponse, error) {
	jsonData, err := json.Marshal(params)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal parameters: %w", err)
	}

	url := fmt.Sprintf("%s/api/StoredProcedure/%s", c.BaseURL, procedure)
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	
	// Set authentication headers for protected procedures
	if email != "" && password != "" {
		req.Header.Set("Rediacc-UserEmail", email)
		// Calculate SHA-256 hash of password (matching sfHash function)
		hash := sha256.Sum256([]byte(password))
		// Encode as base64 like in the tutorial examples
		req.Header.Set("Rediacc-UserHash", base64.StdEncoding.EncodeToString(hash[:]))
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Parse middleware response
	var middlewareResp MiddlewareResponse
	if err := json.Unmarshal(body, &middlewareResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP error: %d", resp.StatusCode)
	}

	// Check for API errors
	if middlewareResp.Failure != 0 {
		if len(middlewareResp.Errors) > 0 {
			return nil, fmt.Errorf("API error: %s", middlewareResp.Errors[0])
		}
		return nil, fmt.Errorf("API error: failure code %d", middlewareResp.Failure)
	}

	// Extract the nextReqeustCredential from the first table
	authResponse := &AuthResponse{Success: true}
	if len(middlewareResp.Tables) > 0 && len(middlewareResp.Tables[0].Data) > 0 {
		if cred, ok := middlewareResp.Tables[0].Data[0]["nextReqeustCredential"]; ok {
			if credStr, ok := cred.(string); ok {
				authResponse.RequestCredential = credStr
				authResponse.SessionToken = credStr // Use the same for both for now
			}
		}
	}

	return authResponse, nil
}

// updateTokenFromResponse updates the stored token from API response
func (c *Client) updateTokenFromResponse(resp *MiddlewareResponse) {
	// Look for nextReqeustCredential in any table data
	for _, table := range resp.Tables {
		for _, row := range table.Data {
			if cred, ok := row["nextReqeustCredential"]; ok {
				if credStr, ok := cred.(string); ok {
					// Update both session token and request credential
					if err := config.UpdateAuth(c.config.Auth.Email, credStr, credStr); err == nil {
						// Refresh client config reference
						c.config = config.Get()
					}
					return
				}
			}
		}
	}
}

// setAuthHeaders sets the authentication headers based on the middleware requirements
func (c *Client) setAuthHeaders(req *http.Request) {
	// Use RequestToken header for authenticated requests
	if c.config.Auth.RequestCredential != "" {
		req.Header.Set("Rediacc-RequestToken", c.config.Auth.RequestCredential)
	}
}

// IsAuthenticated checks if the client has valid authentication
func (c *Client) IsAuthenticated() bool {
	return c.config.Auth.Email != "" && c.config.Auth.SessionToken != ""
}
