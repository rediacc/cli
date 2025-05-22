# Production Dockerfile for Rediacc CLI
FROM golang:1.22-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata

# Set working directory
WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s -X main.version=1.0.0" \
    -a -installsuffix cgo \
    -o bin/rediacc main.go

# Production image
FROM alpine:latest

# Install runtime dependencies
RUN apk --no-cache add ca-certificates openssh-client

# Create non-root user
RUN addgroup -g 1001 -S rediacc && \
    adduser -u 1001 -S rediacc -G rediacc

# Set working directory
WORKDIR /home/rediacc

# Copy binary from builder
COPY --from=builder /app/bin/rediacc /usr/local/bin/rediacc

# Note: README.md and other docs are not needed in production image

# Change ownership
RUN chown -R rediacc:rediacc /home/rediacc

# Switch to non-root user
USER rediacc

# Set up config directory
RUN mkdir -p /home/rediacc/.config

# Expose any ports if needed (none for CLI)
# EXPOSE 8080

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD rediacc --version || exit 1

# Default command
ENTRYPOINT ["rediacc"]
CMD ["--help"]