# Multi-stage build for CLI application with optimized layer caching
FROM python:3.11-alpine AS base

# ========================================
# Layer 1: System packages (rarely changes)
# ========================================
RUN apk add --no-cache \
    bash \
    git \
    openssh-client \
    rsync \
    curl \
    jq \
    ca-certificates \
    tzdata \
    && rm -rf /var/cache/apk/*

# ========================================
# Layer 2: Build dependencies (sometimes changes)
# ========================================
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    python3-dev \
    && rm -rf /var/cache/apk/*

# ========================================
# Layer 3: GUI dependencies (rarely changes)
# ========================================
RUN apk add --no-cache \
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

# ========================================
# Layer 4: Environment setup (rarely changes)
# ========================================
ENV TZ=UTC
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# ========================================
# Layer 5: User setup (rarely changes)
# ========================================
ARG REDIACC_LINUX_USER=rediacc
ARG REDIACC_LINUX_GROUP=rediacc
ARG REDIACC_USER_UID=7111
ARG REDIACC_USER_GID=7111
RUN addgroup -g $REDIACC_USER_GID -S $REDIACC_LINUX_GROUP && \
    adduser -u $REDIACC_USER_UID -S -G $REDIACC_LINUX_GROUP -h /home/$REDIACC_LINUX_USER -s /bin/bash $REDIACC_LINUX_USER

# ========================================
# Layer 6: Directory structure (rarely changes)
# ========================================
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix && \
    mkdir -p /etc/X11/app-defaults && \
    mkdir -p /home/$REDIACC_LINUX_USER/.ssh && \
    mkdir -p /home/$REDIACC_LINUX_USER/.config && \
    mkdir -p /home/$REDIACC_LINUX_USER/tmp && \
    chown -R $REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP /home/$REDIACC_LINUX_USER && \
    chmod 700 /home/$REDIACC_LINUX_USER/.ssh && \
    chmod 700 /home/$REDIACC_LINUX_USER/.config && \
    chmod 700 /home/$REDIACC_LINUX_USER/tmp

# Configure xterm fonts
RUN echo "XTerm*faceName: DejaVu Sans Mono" > /etc/X11/app-defaults/XTerm && \
    echo "XTerm*faceSize: 10" >> /etc/X11/app-defaults/XTerm && \
    echo "XTerm*renderFont: true" >> /etc/X11/app-defaults/XTerm && \
    echo "XTerm*font: fixed" >> /etc/X11/app-defaults/XTerm

# Configure git globally
RUN git config --global --add safe.directory '*'

WORKDIR /app

# ========================================
# Layer 7: Python dependencies (changes when requirements change)
# ========================================
# Copy only requirements first for better caching
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP requirements.txt* ./

# Install Python dependencies
RUN pip install --no-cache-dir cryptography && \
    if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# ========================================
# Layer 8: Application code (changes frequently)
# ========================================
# Accept version build argument (default to dev)
ARG VERSION=dev

# Copy application code
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP rediacc ./rediacc
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP rediacc.ps1 ./rediacc.ps1
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP src/ ./src/
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP scripts/ ./scripts/
COPY --chown=$REDIACC_LINUX_USER:$REDIACC_LINUX_GROUP docs/ ./docs/

# ========================================
# Layer 9: Version injection and permissions (changes with version)
# ========================================
# Replace version in Python files
RUN find ./src/cli -name "*.py" -exec sed -i "s/__version__ = \"dev\"/__version__ = \"$VERSION\"/g" {} \; && \
    chmod +x rediacc && \
    find ./src/cli/commands -name "*.py" -exec chmod +x {} \; && \
    find ./src/cli/gui -name "*.py" -exec chmod +x {} \;

# ========================================
# Final configuration
# ========================================
USER $REDIACC_LINUX_USER

# Set environment variables
ENV PATH="/app:${PATH}"
ENV PYTHONPATH="/app/src/cli"
ENV PYTHONUNBUFFERED=1
ENV TMPDIR=/home/rediacc/tmp
ENV TERM=xterm-256color
ENV REDIACC_CONFIG_DIR=/home/rediacc/.config
ENV DISPLAY=:0

# Note: Environment variables can be provided at runtime via -e flags
# Example: docker run -e SYSTEM_API_URL=http://api.example.com:7322/api rediacc/cli:latest

# Declare volumes for persistent data
VOLUME ["/home/rediacc/.config", "/home/rediacc/.ssh"]

# Add metadata labels
LABEL org.opencontainers.image.title="Rediacc CLI with GUI"
LABEL org.opencontainers.image.description="Command-line interface and desktop GUI for Rediacc platform"
LABEL org.opencontainers.image.vendor="Rediacc"
LABEL org.opencontainers.image.source="https://github.com/rediacc/monorepo"
LABEL org.opencontainers.image.version="${VERSION}"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.path.insert(0, '/app/src/cli'); from core import config; sys.exit(0)" || exit 1

# Use ENTRYPOINT so arguments are passed correctly
ENTRYPOINT ["./rediacc"]
CMD []