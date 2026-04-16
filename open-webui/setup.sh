#!/bin/bash
set -e
echo "Setting up Carbon Agent Multi-User Platform..."
command -v docker >/dev/null 2>&1 || { echo "Docker is required"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "Docker Compose is required"; exit 1; }
[ ! -f .env ] && cp .env.example .env && echo "Created .env from template"
echo "Starting services..."
docker compose up --build -d
echo "Waiting for orchestrator..."
until curl -sf http://localhost:8000/health >/dev/null; do sleep 2; done
echo "Orchestrator is healthy"
echo "Waiting for Open WebUI..."
until curl -sf http://localhost:3000 >/dev/null; do sleep 2; done
echo "Open WebUI is running"
echo ""
echo "Platform is ready!"
echo "   Open WebUI:    http://localhost:3000"
echo "   Orchestrator:  http://localhost:8000"
echo "   Adapter:       http://localhost:8001"
