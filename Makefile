.PHONY: dev test build clean

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

build: build-adapter

# Cleanup
clean:
docker compose down -v
rm -f test.db
rm -f orchestrator/test.db
