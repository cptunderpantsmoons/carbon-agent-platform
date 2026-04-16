.PHONY: dev test build deploy clean

# Local development
dev:
docker compose up --build

dev-detach:
docker compose up --build -d

dev-down:
docker compose down

dev-logs:
docker compose logs -f

# Testing
test-adapter:
cd adapter && pytest tests/ -v
test-orchestrator:
cd orchestrator && pytest tests/ -v
test: test-adapter test-orchestrator

# Build
build-adapter:
docker build -t carbon-agent-adapter:latest ./adapter
build-orchestrator:
docker build -t carbon-agent-orchestrator:latest ./orchestrator
build: build-adapter build-orchestrator

# Railway
deploy-staging:
railway up --environment staging
deploy-production:
railway up --environment production

# Cleanup
clean:
docker compose down -v
rm -f test.db
