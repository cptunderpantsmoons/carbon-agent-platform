# Carbon Agent Platform

A self-hosted PaaS for managing per-user AI agent containers with Clerk authentication, Traefik routing, and Docker Engine integration.

## Architecture

```
User Request → Traefik (Reverse Proxy + SSL)
                  ↓
         agents.carbon.dev/agent/{user_id}
                  ↓
         Docker Container (agent-{user_id})
                  ↓
         Adapter → Agent Zero (/api_message)

Orchestrator (user management, Docker lifecycle, admin API)
   ↓
PostgreSQL (user data) + Redis (caching/rate limiting)
   ↓
Clerk (authentication) + Docker Engine (container management)
```

### Key Components

- **Orchestrator**: User management, API key provisioning, Docker container lifecycle, admin commands
- **Adapter**: Translates OpenAI chat completions API to Agent Zero's `/api_message` endpoint
- **Docker Engine**: Direct container management with resource limits and Traefik routing
- **Traefik**: Automatic SSL termination and path-based routing to user containers
- **Clerk**: User authentication and webhook provisioning
- **Agent Zero**: The actual AI agent backend

## Self-Hosted Deployment

### Prerequisites

1. **VPS**: Ubuntu 22.04+ (e.g., Hetzner CPX51 or similar)
2. **Docker**: Install via `curl -fsSL https://get.docker.com | sh`
3. **Domain**: Wildcard DNS configured (e.g., `*.agents.carbon.dev`)
4. **Clerk Account**: Configure webhooks with Svix integration

### Deployment Steps

```bash
# 1. Clone and configure
git clone <repo> && cd carbon-agent-platform
cp .env.example .env
# Edit .env with your configuration

# 2. Create Docker network
docker network create carbon-agent-net

# 3. Deploy infrastructure (Traefik, PostgreSQL, Redis)
docker compose -f docker-compose.infra.yml up -d

# 4. Deploy application
docker compose up -d --build

# Contract Hub starts alongside Carbon at http://localhost:3002
# Both apps reuse the same Clerk instance and Carbon RAG service

# 5. Verify deployment
 docker ps  # Should show orchestrator, adapter, open-webui, contract-hub, and their databases
curl http://localhost:8000/health
```

### Environment Configuration

Create a `.env` file with:

```env
# Clerk Authentication
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_WEBHOOK_SECRET=whsec_...

# Database
POSTGRES_PASSWORD=your-secure-password
DATABASE_URL=postgresql://postgres:password@postgres:5432/carbon_platform

# Docker Configuration
AGENT_DOCKER_IMAGE=carbon-agent-adapter:latest
AGENT_MEMORY_LIMIT=512m
AGENT_CPU_NANOS=500000000

# Traefik Routing
AGENT_DOMAIN=agents.carbon.dev
TRAEFIK_ENTRYPOINT=websecure
AGENT_BASE_PATH=/agent

# Admin
ADMIN_AGENT_API_KEY=your-admin-key

# CORS
CORS_ALLOWED_ORIGINS=https://agents.carbon.dev,https://contract-hub.example.com

# Contract Hub
CONTRACT_HUB_PATH=../contract-hub
CONTRACT_HUB_PORT=3002
CONTRACT_HUB_POSTGRES_PORT=5433
CONTRACT_HUB_POSTGRES_PASSWORD=your-contract-hub-db-password
CONTRACT_HUB_TENANT_ID=contract-hub-tenant
CONTRACT_HUB_DOCASSEMBLE_URL=
CONTRACT_HUB_DOCASSEMBLE_API_KEY=
CONTRACT_HUB_OPENCODE_SERVER_URL=
CONTRACT_HUB_OPENCODE_API_KEY=
```

## Quick Start (Development)

```bash
# Start services
docker compose up --build

# Contract Hub is available at http://localhost:3002

# Create a user via admin API
curl -X POST http://localhost:8000/admin/users \
  -H 'X-Admin-Key: dev-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "display_name": "Alice"}'

# Configure Open WebUI at http://localhost:3000
# Settings -> Connections -> OpenAI API
# Base URL: http://localhost:8001/v1
# API Key: (from user creation response)

# On a fresh deploy, Open WebUI boots with the admin account from
# WEBUI_ADMIN_EMAIL / WEBUI_ADMIN_PASSWORD so the first login can happen
# without reopening public sign-up.
```

## User Provisioning Flow

1. **User signs up** via Clerk web UI
2. **Clerk sends webhook** to `/webhooks/clerk`
3. **Orchestrator verifies** Svix signature and creates user record
4. **Background task provisions** Docker container:
   - Creates container with resource limits (512MB RAM, 0.5 CPU)
   - Injects environment variables (USER_ID, API_KEY, DISPLAY_NAME)
   - Configures Traefik labels for automatic routing
   - Updates user status to ACTIVE
5. **Traefik automatically routes** `agents.carbon.dev/agent/{user_id}` to the container

## Container Lifecycle

### Spin-Up
- Triggered by Clerk `user.created` webhook
- Container created with:
  - Read-only filesystem + tmpfs for /tmp
  - Resource limits (configurable via env vars)
  - Traefik path-based routing labels
  - Restart policy: unless-stopped

### Spin-Down
- Triggered by idle timeout (default: 15 minutes)
- Container stopped (not deleted) for fast restart
- User status set to PENDING

### User Deletion
- Triggered by Clerk `user.deleted` webhook
- Container hard-deleted (force remove)
- User record soft-deleted (status=SUSPENDED)

## Traefik Routing

Path-based routing automatically directs traffic to user containers:

```
agents.carbon.dev/agent/{user_id}/*
  ↓
Traefik strips /agent/{user_id} prefix
  ↓
Routes to container on port 8001
```

### Traefik Labels (Applied Automatically)

```python
labels = {
    "traefik.enable": "true",
    f"traefik.http.routers.{user_id}.rule": f"PathPrefix(`/agent/{user_id}`)",
    f"traefik.http.routers.{user_id}.entrypoints": "websecure",
    f"traefik.http.routers.{user_id}.tls": "true",
    f"traefik.http.routers.{user_id}.middlewares": f"{user_id}-strip",
    f"traefik.http.middlewares.{user_id}-strip.stripprefix.prefixes": f"/agent/{user_id}",
    f"traefik.http.services.{user_id}.loadbalancer.server.port": "8001",
}
```

## Agent Zero API

The adapter calls Agent Zero's REST endpoint:
- **POST** `/api_message`
- Body: `{"message": "...", "context_id": "...", "lifetime_hours": 24}`
- Response: `{"context_id": "uuid", "response": "..."}`
- No REST streaming; context_id persisted for multi-turn conversations

## Security Features

- **Clerk Authentication**: RS256 JWT verification with iss validation
- **Webhook Verification**: Svix signature validation prevents spoofing
- **API Key Injection**: Middleware rewrites Authorization headers before upstream calls
- **CORS Restriction**: Configurable allowed origins (required in production)
- **Rate Limiting**: Configurable via Redis or in-memory storage
- **Container Isolation**: Read-only filesystem, resource limits, network segmentation

## Development

```bash
make test        # Run all tests
make test-adapter   # Adapter tests only
make test-orchestrator  # Orchestrator tests only
make dev         # Start local stack
```

### Running Tests

```bash
cd orchestrator
pytest tests/ -v  # All tests
pytest tests/test_session_manager.py -v  # Specific test file
pytest tests/ -k "provision"  # Filter by keyword
```

## Monitoring & Observability

### Health Checks

- **Orchestrator**: `GET /health`
- **Adapter**: `GET /health`
- **PostgreSQL**: `pg_isready`
- **Redis**: `redis-cli ping`
- **Traefik**: Dashboard at `traefik.domain.com` (if configured)

### Logs

All containers use structured JSON logging with:
- `user_id`: User identifier
- `request_id`: Request correlation ID
- `action`: Operation performed
- `duration`: Operation duration (where applicable)

### Metrics

- Active container count
- User registration rate
- API request rate
- Error rate (4xx/5xx)

## Database Migrations

```bash
cd orchestrator
alembic upgrade head  # Apply all migrations
alembic downgrade -1  # Rollback one migration
alembic revision --autogenerate -m "description"  # Create new migration
```

## Troubleshooting

### Container Not Starting

```bash
# Check Docker logs
docker logs agent-{user_id}

# Check resource limits
docker inspect agent-{user_id} | grep -i memory

# Verify network
docker network inspect carbon-agent-net
```

### Traefik Routing Issues

```bash
# Check Traefik dashboard
# Enable with: --api.insecure=true

# Verify labels
docker inspect agent-{user_id} | grep -A 20 Labels

# Check Traefik logs
docker logs traefik | grep {user_id}
```

### Database Issues

```bash
# Connect to PostgreSQL
docker exec -it postgres psql -U postgres -d carbon_platform

# Check user table
\dt users
SELECT id, email, status FROM users;
```

## Migration from Railway

If migrating from the previous Railway-based architecture:

1. **Run migration**: `alembic upgrade head` (removes Railway fields, adds container_id)
2. **Update env vars**: Remove `RAILWAY_*` variables, add `AGENT_*` variables
3. **Deploy infrastructure**: `docker compose -f docker-compose.infra.yml up -d`
4. **Re-provision users**: Existing users will need containers created on next activity
5. **Update DNS**: Point wildcard subdomain to VPS IP for Traefik routing

## License

[Your License Here]
