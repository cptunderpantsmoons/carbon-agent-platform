#!/bin/sh
# Open WebUI Entrypoint Script for Carbon Agent Platform
# Substitutes environment variables into config.json at container startup

set -e

echo "[Carbon Agent] Starting Open WebUI entrypoint..."

# Only require Clerk vars when Clerk is explicitly enabled
if [ "${CLERK_ENABLED:-false}" = "true" ]; then
    REQUIRED_VARS="CLERK_PUBLISHABLE_KEY CLERK_FRONTEND_API_URL"
    MISSING_VARS=""
    for var in $REQUIRED_VARS; do
        eval "value=\$$var"
        if [ -z "$value" ]; then
            MISSING_VARS="$MISSING_VARS $var"
        fi
    done
    if [ -n "$MISSING_VARS" ]; then
        echo "[Carbon Agent] ERROR: Missing required Clerk env vars:$MISSING_VARS"
        echo "[Carbon Agent] Either set these variables or set CLERK_ENABLED=false"
        exit 1
    fi
else
    echo "[Carbon Agent] Clerk disabled (CLERK_ENABLED=false) -- skipping Clerk var checks"
fi

# Keep the admin email used by the config file aligned with the bootstrap user.
export ADMIN_EMAIL="${ADMIN_EMAIL:-${WEBUI_ADMIN_EMAIL:-admin@example.com}}"

# Substitute environment variables into config.json
if [ -f "/app/backend/data/config.json.template" ]; then
    echo "[Carbon Agent] Substituting environment variables into config.json..."
    
    # Export all variables that might be used in the template
    export USER_API_KEY="${USER_API_KEY:-}"
    export UI_TITLE="${UI_TITLE:-The Intelligence Hub}"
    export UI_DESCRIPTION="${UI_DESCRIPTION:-Your personal AI workspace powered by Carbon Agent}"
    export PRIMARY_COLOR="${PRIMARY_COLOR:-#00D4AA}"
    export SECONDARY_COLOR="${SECONDARY_COLOR:-#1A1A2E}"
    export ACCENT_COLOR="${ACCENT_COLOR:-#16213E}"
    export BACKGROUND_COLOR="${BACKGROUND_COLOR:-#0F0F23}"
    export TEXT_COLOR="${TEXT_COLOR:-#E0E0E0}"
    export FONT_FAMILY="${FONT_FAMILY:-Inter, system-ui, -apple-system, sans-serif}"
    export WELCOME_MESSAGE="${WELCOME_MESSAGE:-Welcome to The Intelligence Hub}"
    export FOOTER_TEXT="${FOOTER_TEXT:-Powered by Carbon Agent Platform}"
    envsubst < /app/backend/data/config.json.template > /app/backend/data/config.json
    echo "[Carbon Agent] Config substitution complete."
else
    echo "[Carbon Agent] WARNING: config.json.template not found, using existing config.json"
fi

# Verify substitution worked (check for remaining placeholders)
if grep -q '{{.*}}' /app/backend/data/config.json 2>/dev/null; then
    echo "[Carbon Agent] WARNING: config.json still contains placeholders after substitution"
    grep '{{.*}}' /app/backend/data/config.json
fi

# Patch index.html to inject clerk-integration.js
if [ -f "/app/build/index.html" ]; then
    echo "[Carbon Agent] Patching index.html to inject clerk-integration.js..."

    # Ensure the script is present in the served build static directory.
    if [ -f "/app/static/clerk-integration.js" ] && [ ! -f "/app/build/static/clerk-integration.js" ]; then
        mkdir -p /app/build/static
        cp /app/static/clerk-integration.js /app/build/static/clerk-integration.js
    fi
    
    # Check if already patched
    if ! grep -q 'clerk-integration.js' /app/build/index.html; then
        # Inject script tag before closing </head>
        sed -i 's|</head>|<script src="/static/clerk-integration.js"></script></head>|' /app/build/index.html
        echo "[Carbon Agent] index.html patched successfully."
    else
        echo "[Carbon Agent] index.html already patched, skipping."
    fi
else
    echo "[Carbon Agent] WARNING: /app/build/index.html not found, clerk-integration.js won't be loaded"
fi

# Set proper permissions
chown -R root:root /app/backend/data/config.json 2>/dev/null || true

echo "[Carbon Agent] Entrypoint complete. Starting Open WebUI..."

# Execute the original Open WebUI entrypoint
exec "$@"
