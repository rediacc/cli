package models

import "time"

// BaseModel contains common fields for all models
type BaseModel struct {
	ID        int       `json:"id" yaml:"id"`
	CreatedAt time.Time `json:"created_at" yaml:"created_at"`
	UpdatedAt time.Time `json:"updated_at" yaml:"updated_at"`
}

// APIResponse represents a generic API response
type APIResponse struct {
	Success bool                     `json:"success"`
	Data    []map[string]interface{} `json:"data"`
	Error   string                   `json:"error,omitempty"`
	Message string                   `json:"message,omitempty"`
	Total   int                      `json:"total,omitempty"`
}

// ErrorDetail provides detailed error information
type ErrorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Field   string `json:"field,omitempty"`
}

// PaginationParams represents pagination parameters
type PaginationParams struct {
	Page     int `json:"page"`
	PageSize int `json:"page_size"`
	Offset   int `json:"offset"`
	Limit    int `json:"limit"`
}

// SortParams represents sorting parameters
type SortParams struct {
	Field string `json:"field"`
	Order string `json:"order"` // "asc" or "desc"
}
