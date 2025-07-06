# Multi-stage build for CLI application
FROM python:3.11-alpine AS base

# Install system dependencies
RUN apk add --no-cache \
    bash \
    git \
    openssh-client \
    rsync \
    curl \
    jq \
    build-base \
    libffi-dev \
    openssl-dev \
    python3-dev \
    ca-certificates \
    tzdata \
    ncurses \
    && rm -rf /var/cache/apk/*

# Set timezone and locale
ENV TZ=UTC
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Set up non-root user following monorepo security pattern
ARG REDIACC_LINUX_USER=rediacc
ARG REDIACC_LINUX_GROUP=rediacc
RUN addgroup -g 111 -S $REDIACC_LINUX_GROUP && \
    adduser -u 111 -S -G $REDIACC_LINUX_GROUP -h /home/$REDIACC_LINUX_USER -s /bin/bash $REDIACC_LINUX_USER

# Create working directory
WORKDIR /app

# Copy directory structure
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP rediacc ./rediacc
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP rediacc.ps1 ./rediacc.ps1
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP src/ ./src/
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP scripts/ ./scripts/
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP docs/ ./docs/

# Make scripts executable
RUN chmod +x rediacc src/cli/*

# Note: Rediacc Desktop (GUI functionality via --gui flag) requires X11 display and won't work in standard Docker containers
# For Rediacc Desktop support, use X11 forwarding or run on the host system

# Copy requirements if exists
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP requirements.txt ./

# Install Python dependencies
# Install cryptography for vault encryption support
RUN pip install --no-cache-dir cryptography

# Install from requirements.txt if it exists
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Create SSH directory for the user
RUN mkdir -p /home/$REDIACC_LINUX_USER/.ssh && \
    chown -R $REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP /home/$REDIACC_LINUX_USER/.ssh && \
    chmod 700 /home/$REDIACC_LINUX_USER/.ssh

# Create .rediacc config directory
RUN mkdir -p /home/$REDIACC_LINUX_USER/.rediacc && \
    chown -R $REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP /home/$REDIACC_LINUX_USER/.rediacc && \
    chmod 700 /home/$REDIACC_LINUX_USER/.rediacc

# Configure git to handle mounted directories safely
RUN git config --global --add safe.directory '*'

# Create tmp directory for the user
RUN mkdir -p /home/$REDIACC_LINUX_USER/tmp && \
    chown $REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP /home/$REDIACC_LINUX_USER/tmp && \
    chmod 700 /home/$REDIACC_LINUX_USER/tmp

# Switch to non-root user
USER $REDIACC_LINUX_USER

# Set environment variables
ENV PATH="/app:${PATH}"
ENV PYTHONPATH="/app/src/modules:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1
ENV TMPDIR=/home/rediacc/tmp
ENV TERM=xterm-256color

# Note: Environment variables should be provided at runtime via --env-file or -e flags
# Example: docker run --env-file .env rediacc/cli:latest
# See .env.example for required configuration

# Declare volumes for persistent data
VOLUME ["/home/rediacc/.rediacc", "/home/rediacc/.ssh"]

# Add metadata labels following OCI conventions
LABEL org.opencontainers.image.title="Rediacc CLI"
LABEL org.opencontainers.image.description="Command-line interface for Rediacc platform"
LABEL org.opencontainers.image.vendor="Rediacc"
LABEL org.opencontainers.image.source="https://github.com/rediacc/monorepo"

# Health check - verify CLI is responsive
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.path.insert(0, '/app/src/modules'); import rediacc_cli_core; sys.exit(0)" || exit 1

# Default command - show help
CMD ["./rediacc", "help"]