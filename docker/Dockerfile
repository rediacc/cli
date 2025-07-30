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
    tk \
    tcl \
    xvfb \
    xauth \
    xhost \
    fontconfig \
    ttf-dejavu \
    xterm \
    font-misc-misc \
    font-cursor-misc \
    font-adobe-100dpi \
    font-adobe-75dpi \
    && rm -rf /var/cache/apk/*

# Set timezone and locale
ENV TZ=UTC
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Set up non-root user following monorepo security pattern
ARG REDIACC_LINUX_USER=rediacc
ARG REDIACC_LINUX_GROUP=rediacc
ARG REDIACC_USER_UID=7111
ARG REDIACC_USER_GID=7111
RUN addgroup -g $REDIACC_USER_GID -S $REDIACC_LINUX_GROUP && \
    adduser -u $REDIACC_USER_UID -S -G $REDIACC_LINUX_GROUP -h /home/$REDIACC_LINUX_USER -s /bin/bash $REDIACC_LINUX_USER

# Create X11 unix socket directory
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix

# Configure xterm to use available fonts
RUN mkdir -p /etc/X11/app-defaults && \
    echo "XTerm*faceName: DejaVu Sans Mono" > /etc/X11/app-defaults/XTerm && \
    echo "XTerm*faceSize: 10" >> /etc/X11/app-defaults/XTerm && \
    echo "XTerm*renderFont: true" >> /etc/X11/app-defaults/XTerm && \
    echo "XTerm*font: fixed" >> /etc/X11/app-defaults/XTerm

# Create working directory
WORKDIR /app

# Accept version build argument
ARG VERSION=dev

# Copy directory structure
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP rediacc ./rediacc
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP rediacc.ps1 ./rediacc.ps1
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP src/ ./src/
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP scripts/ ./scripts/
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP docs/ ./docs/

# Replace version in Python files
RUN find ./src/cli -name "*.py" -exec sed -i "s/__version__ = \"dev\"/__version__ = \"$VERSION\"/g" {} \;

# Make scripts executable
RUN chmod +x rediacc src/cli/*

# Note: This image includes GUI support. To use Rediacc Desktop (GUI functionality via --gui flag):
# - Linux/macOS: Use X11 forwarding with -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw
# - Windows: Use X server (e.g., VcXsrv) with -e DISPLAY=host.docker.internal:0

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

# Create .config directory
RUN mkdir -p /home/$REDIACC_LINUX_USER/.config && \
    chown -R $REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP /home/$REDIACC_LINUX_USER/.config && \
    chmod 700 /home/$REDIACC_LINUX_USER/.config

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
ENV REDIACC_CONFIG_DIR=/home/rediacc/.config
ENV DISPLAY=:0

# Note: Environment variables can be provided at runtime via -e flags
# Example: docker run -e SYSTEM_API_URL=http://api.example.com:7322/api rediacc/cli:latest
# Default values are built into the application

# Declare volumes for persistent data
VOLUME ["/home/rediacc/.config", "/home/rediacc/.ssh"]

# Add metadata labels following OCI conventions
LABEL org.opencontainers.image.title="Rediacc CLI with GUI"
LABEL org.opencontainers.image.description="Command-line interface and desktop GUI for Rediacc platform"
LABEL org.opencontainers.image.vendor="Rediacc"
LABEL org.opencontainers.image.source="https://github.com/rediacc/monorepo"

# Health check - verify CLI is responsive
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.path.insert(0, '/app/src/modules'); import rediacc_cli_core; sys.exit(0)" || exit 1

# Use ENTRYPOINT so arguments are passed correctly
ENTRYPOINT ["./rediacc"]
# Default command if no arguments provided
CMD []