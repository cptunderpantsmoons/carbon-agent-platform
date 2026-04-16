# Carbon Agent Platform

An OpenAI-compatible adapter for Agent Zero with user management.

## Architecture

```
Open WebUI -> Adapter (OpenAI translator) -> Agent Zero (/api_message)
                                                  ^
Orchestrator (user management / admin API) --------+
```

- **Adapter**: Translates OpenAI chat completions API to Agent Zero's `/api_message` endpoint. Fakes SSE streaming for OpenAI-compatible clients.
- **Orchestrator**: User management, API key provisioning, admin commands.
- **Agent Zero**: The actual AI agent backend.

## Quick Start

```bash
git clone <repo> && cd carbon-agent-platform

# Start services
docker compose up --build

# Create a user via admin API
curl -X POST http://localhost:8000/admin/users \
  -H 'X-Admin-Key: dev-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "display_name": "Alice"}'

# Configure Open WebUI at http://localhost:3000
# Settings -> Connections -> OpenAI API
# Base URL: http://localhost:8001/v1
# API Key: (from user creation response)
```

## Agent Zero API

The adapter calls Agent Zero's REST endpoint:
- **POST** `/api_message`
- Body: `{"message": "...", "context_id": "...", "lifetime_hours": 24}`
- Response: `{"context_id": "uuid", "response": "..."}`
- No REST streaming; context_id persisted for multi-turn conversations

## Development

```bash
make test        # Run all tests
make test-adapter   # Adapter tests only
make test-orchestrator  # Orchestrator tests only
make dev         # Start local stack
```
