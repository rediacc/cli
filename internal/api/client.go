package api

import (
	"bytes"
	"crypto/sha256"
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

// ExecuteStoredProcedure executes a stored procedure via the middleware API
func (c *Client) ExecuteStoredProcedure(procedure string, params map[string]interface{}) (*Response, error) {
	// Prepare request
	request := Request{
		Method:     "POST",
		Procedure:  procedure,
		Parameters: params,
	}

	// Convert to JSON
	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	req, err := http.NewRequest("POST", c.BaseURL+"/api/execute", bytes.NewBuffer(jsonData))
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

	// Parse response
	var response Response
	if err := json.Unmarshal(body, &response); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	// Handle HTTP errors
	if resp.StatusCode != http.StatusOK {
		if response.Error != "" {
			return nil, fmt.Errorf("API error (%d): %s", resp.StatusCode, response.Error)
		}
		return nil, fmt.Errorf("HTTP error: %d", resp.StatusCode)
	}

	// Handle API errors
	if !response.Success && response.Error != "" {
		return nil, fmt.Errorf("API error: %s", response.Error)
	}

	return &response, nil
}

// Login authenticates the user and stores the session information
func (c *Client) Login(email, password string) (*AuthResponse, error) {
	params := map[string]interface{}{
		"UserEmail":    email,
		"UserPassword": password,
	}

	// Execute login procedure
	response, err := c.executeAuthProcedure("web.protected_CreateAuthenticationRequest", params)
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
	if c.config.Auth.SessionToken == "" {
		return fmt.Errorf("not logged in")
	}

	params := map[string]interface{}{
		"session_id": c.config.Auth.SessionToken,
	}

	_, err := c.ExecuteStoredProcedure("web.public_LogoutUserSession", params)
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
func (c *Client) executeAuthProcedure(procedure string, params map[string]interface{}) (*AuthResponse, error) {
	request := Request{
		Method:     "POST",
		Procedure:  procedure,
		Parameters: params,
	}

	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequest("POST", c.BaseURL+"/api/execute", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var response AuthResponse
	if err := json.Unmarshal(body, &response); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		if response.Error != "" {
			return nil, fmt.Errorf("API error (%d): %s", resp.StatusCode, response.Error)
		}
		return nil, fmt.Errorf("HTTP error: %d", resp.StatusCode)
	}

	return &response, nil
}

// setAuthHeaders sets the authentication headers based on the middleware requirements
func (c *Client) setAuthHeaders(req *http.Request) {
	if c.config.Auth.Email != "" {
		req.Header.Set("UserEmail", c.config.Auth.Email)

		// Create hash from email
		hash := sha256.Sum256([]byte(c.config.Auth.Email))
		req.Header.Set("UserHash", fmt.Sprintf("%x", hash))
	}

	if c.config.Auth.RequestCredential != "" {
		req.Header.Set("RequestCredential", c.config.Auth.RequestCredential)
	}

	// TODO: Implement verification header based on middleware requirements
	// This might involve combining various fields and creating a signature
}

// IsAuthenticated checks if the client has valid authentication
func (c *Client) IsAuthenticated() bool {
	return c.config.Auth.Email != "" && c.config.Auth.SessionToken != ""
}
