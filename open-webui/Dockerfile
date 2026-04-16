# Custom Open WebUI Dockerfile for The Intelligence Hub
# Extends the official Open WebUI image with Clerk integration

FROM ghcr.io/open-webui/open-webui:main

# Labels
LABEL maintainer="Carbon Agent Platform"
LABEL description="The Intelligence Hub - Open WebUI with Clerk Integration"

# Set environment variables for Clerk integration
ENV CLERK_ENABLED=true
ENV ENABLE_SIGNUP=false
ENV WEBUI_AUTH=true

# Switch to root for file operations
USER root

# Create directory for custom scripts
RUN mkdir -p /app/static \
    && mkdir -p /app/backend/data

# Copy Clerk integration script
COPY clerk-integration.js /app/static/clerk-integration.js
RUN chmod 644 /app/static/clerk-integration.js

# Copy custom configuration
COPY config.json /app/backend/data/config.json
RUN chmod 644 /app/backend/data/config.json

# Create custom theme CSS for white-label branding
RUN cat > /app/static/custom-theme.css << 'EOF'
/* The Intelligence Hub - Custom Theme */
:root {
  --primary-color: #00D4AA;
  --secondary-color: #1A1A2E;
  --accent-color: #16213E;
  --background-color: #0F0F23;
  --text-color: #E0E0E0;

  /* Open WebUI specific variables */
  --color-surface-primary: var(--primary-color);
  --color-background: var(--background-color);
  --color-text: var(--text-color);
}

/* Branding overrides */
.header-logo img {
  content: url('/static/logo.png');
}

/* Custom scrollbars */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: var(--secondary-color);
}

::-webkit-scrollbar-thumb {
  background: var(--primary-color);
  border-radius: 4px;
}

/* Typography */
body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

/* Button styling */
.btn-primary {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
  color: var(--secondary-color);
}

.btn-primary:hover {
  background-color: #00B894;
  border-color: #00B894;
}

/* Card and container styling */
.card {
  background-color: var(--accent-color);
  border: 1px solid rgba(0, 212, 170, 0.1);
}

/* Chat interface */
.chat-message.user {
  background-color: var(--accent-color);
}

.chat-message.assistant {
  background-color: var(--secondary-color);
}

/* Input area */
.chat-input {
  background-color: var(--accent-color);
  border: 1px solid var(--primary-color);
}

/* Sidebar */
.sidebar {
  background-color: var(--secondary-color);
  border-right: 1px solid rgba(0, 212, 170, 0.1);
}

/* Loading states */
.loading-spinner {
  color: var(--primary-color);
}
EOF

# Set proper ownership
RUN chown -R root:root /app/static \
    && chown -R root:root /app/backend/data

# Switch back to the default user
USER root

# Expose the default port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# The entrypoint remains the same as the base image
# CMD is inherited from the base image
