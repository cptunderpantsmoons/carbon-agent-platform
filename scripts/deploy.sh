#!/bin/bash
# Carbon Agent Platform - Railway Deployment Script

set -e

echo "🚀 Carbon Agent Platform - Railway Deployment"
echo "============================================="

# Check prerequisites
command -v railway >/dev/null 2>&1 || {
    echo "❌ Railway CLI not found. Install with: npm i -g @railway/cli"
    exit 1
}

command -v docker >/dev/null 2>&1 || {
    echo "❌ Docker not found. Please install Docker."
    exit 1
}

# Check for .env.production file
if [ ! -f .env.production ]; then
    echo "❌ .env.production not found. Copy .env.production.example and configure it."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Login to Railway
echo ""
echo "🔐 Logging into Railway..."
railway login

# Link to project
echo ""
echo "🔗 Linking to Railway project..."
railway link

# Load environment variables
echo ""
echo "📦 Loading environment variables..."
export $(grep -v '^#' .env.production | xargs)

# Deploy services
echo ""
echo "🎛️  Deploying orchestrator..."
railway up --service orchestrator --detach

echo ""
echo "🔌 Deploying adapter..."
railway up --service adapter --detach

echo ""
echo "🌐 Deploying Open WebUI..."
railway service create --name open-webui

echo ""
echo "🗄️  Setting up PostgreSQL..."
railway service create --name postgres --template postgresql

echo ""
echo "⚡ Setting up Redis..."
railway service create --name redis --template redis

# Wait for deployment
echo ""
echo "⏳ Waiting for deployment to complete..."
sleep 30

# Get deployment status
echo ""
echo "📊 Deployment Status:"
railway status

echo ""
echo "✅ Deployment complete!"
echo "📝 Check Railway dashboard for service URLs and status"
