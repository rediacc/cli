package models

// User represents a user in the system
type User struct {
	BaseModel
	Email        string `json:"email" yaml:"email"`
	Name         string `json:"name" yaml:"name"`
	Status       string `json:"status" yaml:"status"`
	LastLoginAt  string `json:"last_login_at" yaml:"last_login_at"`
	Is2FAEnabled bool   `json:"is_2fa_enabled" yaml:"is_2fa_enabled"`
}

// LoginRequest represents a login request
type LoginRequest struct {
	Email     string `json:"email" yaml:"email"`
	Password  string `json:"password" yaml:"password"`
	TwoFACode string `json:"2fa_code,omitempty" yaml:"2fa_code,omitempty"`
}

// LoginResponse represents a login response
type LoginResponse struct {
	Success           bool   `json:"success"`
	SessionToken      string `json:"session_token"`
	RequestCredential string `json:"request_credential"`
	Message           string `json:"message"`
	Error             string `json:"error,omitempty"`
	User              *User  `json:"user,omitempty"`
}

// UserSession represents a user session
type UserSession struct {
	BaseModel
	UserEmail         string `json:"user_email" yaml:"user_email"`
	SessionToken      string `json:"session_token" yaml:"session_token"`
	RequestCredential string `json:"request_credential" yaml:"request_credential"`
	ExpiresAt         string `json:"expires_at" yaml:"expires_at"`
	IsActive          bool   `json:"is_active" yaml:"is_active"`
}

// TwoFASecret represents a 2FA secret
type TwoFASecret struct {
	Secret string `json:"secret" yaml:"secret"`
	QRCode string `json:"qr_code" yaml:"qr_code"`
}
