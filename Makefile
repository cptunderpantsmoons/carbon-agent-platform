.PHONY: dev test build clean deploy help

# ===========================================
# Carbon Agent Platform - Makefile
# ===========================================

help:
	@echo "Carbon Agent Platform - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Start development stack"
	@echo "  make dev-detach       Start development stack in background"
	@echo "  make dev-down         Stop development stack"
	@echo "  make dev-logs         View development logs"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-adapter     Run adapter tests"
	@echo "  make test-orchestrator  Run orchestrator tests"
	@echo ""
	@echo "Production:"
	@echo "  make prod             Start production stack"
	@echo "  make prod-detach      Start production stack in background"
	@echo "  make prod-down        Stop production stack"
	@echo "  make prod-logs        View production logs"
	@echo ""
	@echo "Docker:"
	@echo "  make build-adapter    Build adapter image"
	@echo "  make build-orchestrator  Build orchestrator image"
	@echo "  make build-all        Build all images"
	@echo "  make push             Push images to registry"
	@echo ""
	@echo "Railway:"
	@echo "  make deploy-railway   Deploy to Railway"
	@echo "  make railway-status   Check Railway deployment status"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Clean up containers and volumes"
	@echo "  make migrate          Run database migrations"

# Development
dev:
	docker compose up --build

dev-detach:
	docker compose up --build -d

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f

# Production
prod:
	docker compose -f docker-compose.yml --env-file .env.production up --build

prod-detach:
	docker compose -f docker-compose.yml --env-file .env.production up --build -d

prod-down:
	docker compose -f docker-compose.yml --env-file .env.production down

prod-logs:
	docker compose -f docker-compose.yml --env-file .env.production logs -f

# Testing
test-adapter:
	cd adapter && pytest tests/ -v

test-orchestrator:
	cd orchestrator && pytest tests/ -v

test: test-adapter test-orchestrator

# Docker Builds
build-adapter:
	docker build -t carbon-agent-adapter:latest ./adapter

build-orchestrator:
	docker build -t carbon-agent-orchestrator:latest ./orchestrator

build-all: build-adapter build-orchestrator

push:
	@echo "Push to registry (configure in .env)"
	@echo "Example: docker push ghcr.io/your-org/carbon-agent-adapter:latest"

# Railway Deployment
deploy-railway:
	@echo "Deploying to Railway..."
	@echo "Ensure RAILWAY_API_TOKEN is set in environment"
	railway login
	railway link
	railway up

railway-status:
	railway status

# Maintenance
clean:
	docker compose down -v
	rm -f test.db
	rm -f orchestrator/test.db

migrate:
	@echo "Running database migrations..."
	@echo "Use: alembic upgrade head"
