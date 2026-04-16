# Carbon Agent Multi-User Platform

A multi-user AI workspace platform built on Carbon Agent, Railway, and Open WebUI.

## Architecture

```
Open WebUI -> Orchestrator -> Per-User Agent Instances
    ^              |
    |        Railway API
    |              v
    +-- Admin Agent (Carbon Agent)
```

## Quick Start

```bash
git clone <repo> && cd carbon-agent-platform
./open-webui/setup.sh

# Create users via admin API
curl -X POST http://localhost:8000/admin/users \
  -H 'X-Admin-Key: dev-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "display_name": "Alice"}'

# Configure Open WebUI at http://localhost:3000 -> Settings -> Connections
# Set API base: http://localhost:8000/v1
# Set API key: (from the user creation response)
```

## Railway Deployment

```bash
npm install -g @railway/cli
railway login
railway link
railway up
railway variables set ADMIN_AGENT_API_KEY=your-key
railway variables set RAILWAY_API_TOKEN=your-token
```

## Carbon Agent Admin

Scheduled tasks keep the admin agent in the loop:
- Health checks every 5 min
- Idle cleanup every 5 min
- Daily reports at 9 AM
- Weekly volume audit Mondays at 2 AM

## Cost Estimation

| Scenario | Monthly Cost |
|---|---|
| 15 users, 5 concurrent | ~$65 |
| 15 users, all idle | ~$20 |
| 50 users, 10 concurrent | ~$130 |

## Development

```bash
make dev         # Start local stack
make test        # Run all tests
make build       # Build Docker images
```
