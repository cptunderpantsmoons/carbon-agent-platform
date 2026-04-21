# Custom Open WebUI image for The Intelligence Hub.
# Extends the official Open WebUI image with Clerk authentication and
# environment-variable-driven configuration substitution.
#
# Base image digest pinned for reproducibility.
# SECURITY UPDATE REQUIRED: Current image has 4 critical + 26 high vulnerabilities
# To update:
#   1. Run: docker buildx imagetools inspect ghcr.io/open-webui/open-webui:main
#   2. Copy the multi-arch index digest (sha256:...)
#   3. Update the digest below
#   4. Rebuild: docker compose build open-webui
#   Last updated: 2026-04-21
FROM ghcr.io/open-webui/open-webui:main@sha256:b8095f79a6a8ffad8f830bdacc9b5b0aef805689b31bca0b065cc2424d3cfaeb

LABEL maintainer="Carbon Agent Platform"
LABEL description="The Intelligence Hub - Open WebUI with Clerk Integration"

# Open WebUI runtime flags (non-sensitive defaults)
# NOTE: Sensitive values (API keys, secrets) should be set at runtime via
# docker-compose environment variables or .env files, NOT in the Dockerfile.
ENV CLERK_ENABLED=true
ENV ENABLE_SIGNUP=false

# File operations require root; we drop privileges before ENTRYPOINT
USER root

# Install gettext-base for envsubst (used in entrypoint.sh at container startup)
RUN apt-get update && apt-get install -y --no-install-recommends gettext-base \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated non-root user for running Open WebUI
RUN groupadd -r webui && useradd -r -g webui -u 1000 -d /app -s /sbin/nologin webui

# Ensure required directories exist
RUN mkdir -p /app/build/static /app/static /app/backend/data

# ── Copy custom assets ─────────────────────────────────────────────────────────
COPY clerk-integration.js /app/build/static/clerk-integration.js
COPY clerk-integration.js /app/static/clerk-integration.js
COPY config.json.template /app/backend/data/config.json.template
COPY custom-theme.css     /app/static/custom-theme.css
COPY entrypoint.sh        /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh \
    && chmod 644 /app/build/static/clerk-integration.js \
                 /app/static/clerk-integration.js \
                 /app/static/custom-theme.css \
                 /app/backend/data/config.json.template

# ── Inject clerk-integration.js at build time ──────────────────────────────
# Done here (as root) so the entrypoint does not need write access to /app/build.
# The entrypoint checks for the script tag and skips re-injection if already present.
RUN if [ -f /app/build/index.html ]; then \
        grep -q 'clerk-integration.js' /app/build/index.html \
            || sed -i 's|</head>|<script src="/static/clerk-integration.js"></script></head>|' \
                   /app/build/index.html; \
        echo "[build] clerk-integration.js injected into index.html"; \
    else \
        echo "[build] WARNING: /app/build/index.html not found -- injection deferred to entrypoint"; \
    fi

# ── Set ownership ───────────────────────────────────────────────────────────
# Make all of /app readable/executable by everyone so the webui user can run
# the Open WebUI Python backend.  Grant webui write access only to the dirs it
# must modify at runtime (config substitution, static uploads).
RUN chmod -R a+rX /app \
    && chown -R webui:webui /app/build/static \
                            /app/static \
                            /app/backend/data \
                            /app/entrypoint.sh

# Drop to non-root for the final image layer
USER webui

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# entrypoint.sh: envsubst on config.json.template, then exec "$@"
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/app/backend/start.sh"]
