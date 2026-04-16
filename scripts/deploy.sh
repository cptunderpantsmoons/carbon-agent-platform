#!/bin/bash
# Carbon Agent Platform - Railway Deployment Script
# Idempotent: safe to re-run; skips already-created services.

set -euo pipefail

echo "Carbon Agent Platform - Railway Deployment"
echo "============================================="

# Check prerequisites
command -v railway >/dev/null 2>&1 || {
    echo "ERROR: Railway CLI not found. Install with: npm i -g @railway/cli"
    exit 1
}

command -v docker >/dev/null 2>&1 || {
    echo "ERROR: Docker not found. Please install Docker."
    exit 1
}

# Check for .env.production file
if [ ! -f .env.production ]; then
    echo "ERROR: .env.production not found. Copy .env.production.example and configure it."
    exit 1
fi

echo "Prerequisites check passed"

# Login to Railway (idempotent — no-op if already logged in)
echo ""
echo "Verifying Railway authentication..."
railway whoami 2>/dev/null || railway login

# Link to project (interactive only if not already linked)
echo ""
echo "Linking to Railway project..."
railway link --environment production 2>/dev/null || true

# Load environment variables from .env.production
set -a
source <(grep -v '^\s*#' .env.production)
set +a

# Helper: create a Railway service only if it doesn't already exist
ensure_service() {
    local name="$1"
    if railway service list 2>/dev/null | grep -q "$name"; then
        echo "  Service '$name' already exists — skipping"
    else
        echo "  Creating service '$name'..."
        railway service create --name "$name"
    fi
}

# Deploy infrastructure services
echo ""
echo "Setting up infrastructure services..."
ensure_service postgres
ensure_service redis

# Deploy application services
echo ""
echo "Setting up application services..."
ensure_service orchestrator
ensure_service adapter
ensure_service open-webui

# Deploy orchestrator
echo ""
echo "Deploying orchestrator..."
railway up --service orchestrator --detach

# Deploy adapter
echo ""
echo "Deploying adapter..."
railway up --service adapter --detach

# Deploy Open WebUI
echo ""
echo "Deploying Open WebUI..."
railway up --service open-webui --detach

# Wait for orchestrator to be ready before running migrations
echo ""
echo "Waiting for orchestrator to start (30s)..."
sleep 30

# Run Alembic migrations via the orchestrator service
echo ""
echo "Running database migrations..."
railway run --service orchestrator python -m alembic upgrade head 2>/dev/null || {
    echo "WARNING: Migration via Railway run failed."
    echo "Migrations should run automatically on orchestrator startup."
}

# Get deployment status
echo ""
echo "Deployment Status:"
railway status 2>/dev/null || true

echo ""
echo "Deployment complete!"
echo "Check Railway dashboard for service URLs and status."
