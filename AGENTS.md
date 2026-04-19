# Carbon Agent Platform - Development Guide

**Project:** `C:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform`  
**Architecture:** Self-hosted PaaS with Docker Engine, Traefik, and Clerk  
**Status:** Production-ready for VPS deployment

---

## System Architecture

### Core Components

| Component | Purpose | Port | Docker Image |
|-----------|---------|------|--------------|
| **Orchestrator** | User management, Docker lifecycle, admin API | 8000 | `carbon-orchestrator:latest` |
| **Adapter** | OpenAI API → Agent Zero translation | 8001 | `carbon-agent-adapter:latest` |
| **Open WebUI** | Chat interface with Clerk integration | 3000 | `carbon-webui:latest` |
| **Traefik** | Reverse proxy + SSL termination | 80/443 | `traefik:v3.0` |
| **PostgreSQL** | User data + audit logs | 5432 | `postgres:16-alpine` |
| **Redis** | Caching + rate limiting | 6379 | `redis:7-alpine` |

### Request Flow

```
User → Traefik (agents.carbon.dev)
  ↓
Path-based routing: /agent/{user_id}
  ↓
Docker container: agent-{user_id}
  ↓
Adapter → Agent Zero
```

### User Provisioning Flow

```
Clerk signup → Webhook → Orchestrator
  ↓
Verify Svix signature → Create user record
  ↓
Background task: provision_user_background()
  ↓
DockerServiceManager.ensure_user_service()
  ↓
Create container with:
  - Resource limits (512m RAM, 0.5 CPU)
  - Traefik labels for routing
  - Read-only filesystem + tmpfs
  - Env vars: USER_ID, API_KEY, DISPLAY_NAME
  ↓
Update User.status = ACTIVE
```

---

## Codebase Structure

```
carbon-agent-platform/
├── orchestrator/
│   ├── app/
│   │   ├── docker_manager.py      # Docker Engine integration
│   │   ├── session_manager.py     # Container lifecycle management
│   │   ├── clerk.py               # Webhook handlers (Svix verified)
│   │   ├── clerk_auth.py          # JWT verification
│   │   ├── config.py              # Pydantic settings
│   │   ├── database.py            # SQLAlchemy async setup
│   │   ├── main.py                # FastAPI entrypoint
│   │   ├── models.py              # ORM models (User, Session, AuditLog)
│   │   ├── schemas.py             # Pydantic request/response
│   │   ├── admin.py               # Admin API endpoints
│   │   ├── admin_ui.py            # Admin dashboard (HTML)
│   │   ├── users.py               # User endpoints
│   │   ├── api_key_injection.py   # Auth middleware
│   │   ├── rate_limit.py          # slowapi integration
│   │   └── scheduler.py           # Background tasks
│   ├── alembic/                   # Database migrations
│   ├── tests/                     # pytest test suite
│   └── Dockerfile
├── adapter/                       # OpenAI API translator
├── open-webui/                    # Chat frontend with Clerk
├── traefik/
│   └── dynamic.yml                # Traefik middleware config
├── docker-compose.yml             # Application services
├── docker-compose.infra.yml       # Infrastructure (Traefik, DB, Redis)
└── .env.example                   # Environment template
```

---

## Key Implementation Details

### DockerServiceManager (`docker_manager.py`)

```python
class DockerServiceManager:
    """Manages user agent containers via Docker Engine API."""
    
    async def ensure_user_service(user_id, env_vars):
        # Creates container if missing, starts if stopped
        # Returns: {action, container_id, was_created}
    
    async def spin_down_user_service(user_id):
        # Stops container (preserves for fast restart)
    
    async def destroy_user_service(user_id):
        # Hard delete: force remove container
    
    async def get_container_status(user_id):
        # Returns: 'running', 'stopped', or 'missing'
```

**Traefik Labels Applied:**
```python
{
    "traefik.enable": "true",
    f"traefik.http.routers.{user_id}.rule": f"PathPrefix(`/agent/{user_id}`)",
    f"traefik.http.routers.{user_id}.entrypoints": "websecure",
    f"traefik.http.routers.{user_id}.tls": "true",
    f"traefik.http.middlewares.{user_id}-strip.stripprefix.prefixes": f"/agent/{user_id}",
    f"traefik.http.services.{user_id}.loadbalancer.server.port": "8001",
}
```

### SessionManager (`session_manager.py`)

**Key Methods:**
- `ensure_user_service(db, user_id)`: Creates/starts container with per-user lock
- `provision_user_background(user_id)`: Fire-and-forget from webhook handler
- `spin_down_user_service(db, user_id)`: Stops container, sets status=PENDING
- `spin_down_idle_user(user_id)`: Cleanup task for inactive users
- `get_service_status(db, user_id)`: Returns container status + URL

**Locking Strategy:**
```python
self._spin_locks: weakref.WeakValueDictionary[str, asyncio.Lock]
# Auto-GC'd when no coroutine holds reference
# Prevents race conditions in concurrent provisioning
```

### Clerk Webhook Handler (`clerk.py`)

**Endpoints:**
- `POST /webhooks/clerk` - Svix signature verified
- Rate limited: 30/minute

**Events Handled:**
- `user.created` → Create DB record + schedule provisioning
- `user.updated` → Sync email/display_name
- `user.deleted` → Destroy container + soft-delete user

---

## Database Schema

### User Model
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| clerk_user_id | String(255) | Unique, indexed |
| email | String(255) | Unique, indexed |
| display_name | String(255) | |
| api_key | String(64) | Format: sk-<hex>, unique |
| status | Enum | ACTIVE, SUSPENDED, PENDING |
| config | JSON | User preferences |
| created_at | DateTime | UTC |
| updated_at | DateTime | Auto-updated |

### Session Model
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| status | Enum | ACTIVE, STOPPED, ERROR |
| container_id | String(64) | Docker container ID |
| internal_url | String(512) | Container network URL |
| public_url | String(512) | Traefik-routed URL |
| started_at | DateTime | |
| stopped_at | DateTime | |
| error_message | Text | |

### AuditLog Model
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| user_id | UUID | FK (nullable) |
| action | String(100) | Event type |
| details | JSON | Event data |
| performed_by | String(100) | Actor |
| created_at | DateTime | UTC |

---

## Configuration

### Environment Variables

**Required (Production):**
```env
# Clerk
CLERK_SECRET_KEY=sk_test_...
CLERK_WEBHOOK_SECRET=whsec_...

# Database
DATABASE_URL=postgresql://...

# Docker
AGENT_DOCKER_IMAGE=carbon-agent-adapter:latest
AGENT_MEMORY_LIMIT=512m
AGENT_CPU_NANOS=500000000

# Traefik
AGENT_DOMAIN=agents.carbon.dev
TRAEFIK_ENTRYPOINT=websecure

# Admin
ADMIN_AGENT_API_KEY=<secure-key>

# CORS
CORS_ALLOWED_ORIGINS=https://agents.carbon.dev
```

**Optional:**
```env
AGENT_BASE_PATH=/agent              # Default path prefix
SESSION_IDLE_TIMEOUT_MINUTES=15     # Auto spin-down threshold
REDIS_URL=redis://redis:6379/0      # Production caching
RATE_LIMIT_STORAGE_URI=redis://...  # Production rate limiting
```

### Config Class (`config.py`)

```python
class Settings(BaseSettings):
    docker_network: str = "carbon-agent-net"
    agent_docker_image: str = "carbon-agent-adapter:latest"
    agent_memory_limit: str = "512m"
    agent_cpu_nanos: int = 500000000
    adapter_port: int = 8001
    agent_domain: str = "agents.carbon.dev"
    traefik_entrypoint: str = "websecure"
    agent_base_path: str = "/agent"
    session_idle_timeout_minutes: int = 15
    # ... plus Clerk, DB, Redis, CORS settings
```

---

## Deployment Guide

### VPS Setup

```bash
# 1. Provision VPS (Ubuntu 22.04+)
# Hetzner CPX51 recommended (4 vCPU, 8GB RAM)

# 2. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 3. Configure DNS
# Wildcard: *.agents.carbon.dev → VPS IP

# 4. Clone repo
git clone <repo-url> && cd carbon-agent-platform
```

### Infrastructure Deployment

```bash
# Create network
docker network create carbon-agent-net

# Deploy infrastructure
docker compose -f docker-compose.infra.yml up -d

# Verify
docker ps  # Should show: traefik, postgres, redis
```

### Application Deployment

```bash
# Configure environment
cp .env.example .env
# Edit .env with your values

# Build and deploy
docker compose up -d --build

# Verify
curl http://localhost:8000/health
docker ps  # Should show: orchestrator, adapter, open-webui
```

### First User Signup

1. Visit `https://agents.carbon.dev`
2. Sign up via Clerk
3. Webhook triggers provisioning
4. Wait ~5 seconds for container creation
5. User can now access `/agent/{user_id}`

---

## Testing

### Run Tests

```bash
cd orchestrator

# All tests
pytest tests/ -v

# Specific file
pytest tests/test_session_manager.py -v

# Filter by keyword
pytest tests/ -k "provision"

# With coverage
pytest tests/ --cov=app --cov-report=html
```

### Test Structure

| File | Coverage |
|------|----------|
| `test_session_manager.py` | Container lifecycle, locking, cleanup |
| `test_clerk.py` | Webhook events, signatures, idempotency |
| `test_admin.py` | Admin endpoints, JWT gating |
| `test_users.py` | User CRUD, API key rotation |
| `test_scheduler.py` | Background tasks, health checks |
| `test_models.py` | ORM constraints, defaults |
| `integration/test_onboarding.py` | End-to-end provisioning |
| `integration/test_lifecycle.py` | Idle spin-down, deletion |

### Mocking Docker in Tests

```python
from unittest.mock import patch, MagicMock

mock_docker = MagicMock()
mock_docker.ensure_user_service = AsyncMock(
    return_value={"action": "created", "container_id": "abc123", "was_created": True}
)

with patch("app.session_manager.DockerServiceManager", return_value=mock_docker):
    # Run test
```

---

## Database Migrations

```bash
cd orchestrator

# Apply all migrations
alembic upgrade head

# Rollback one
alembic downgrade -1

# Create new migration
alembic revision --autogenerate -m "description"

# Check current revision
alembic current

# List all migrations
alembic history
```

### Migration History

| Revision | Description | Date |
|----------|-------------|------|
| `remove_railway_fields` | Remove Railway cols, add container_id | 2026-04-18 |
| `e2eec18c30fa` | Initial schema | 2026-04-17 |

---

## Security

### Authentication Flow

1. **Clerk JWT**: RS256 verified with `verify_iss=True`
2. **API Keys**: Format `sk-<hex>`, injected into upstream requests
3. **Admin Access**: `public_metadata.role == "admin"` check
4. **Webhooks**: Svix signature verification

### Container Isolation

- Read-only root filesystem
- tmpfs for `/tmp` (50MB, noexec/nosuid)
- Memory limit: 512MB per container
- CPU limit: 0.5 cores per container
- Network: isolated `carbon-agent-net` bridge
- Restart policy: unless-stopped

### Rate Limiting

| Endpoint | Limit | Key |
|----------|-------|-----|
| `/webhooks/clerk` | 30/min | IP |
| `/admin/*` | 60/min | Admin JWT |
| `/user/*` | 60/min | API key |
| `/health` | None | Public |

---

## Monitoring

### Health Checks

```bash
# Orchestrator
curl http://localhost:8000/health

# Adapter
curl http://localhost:8001/health

# PostgreSQL
docker exec postgres pg_isready -U carbon_admin

# Redis
docker exec redis redis-cli ping

# Container status
docker inspect agent-{user_id} --format='{{.State.Status}}'
```

### Logs

All services use structured JSON logging via `structlog`:

```json
{
  "event": "user_provisioned_successfully",
  "user_id": "uuid-here",
  "timestamp": "2026-04-18T12:00:00Z",
  "level": "info"
}
```

### Key Metrics to Track

- Active container count
- User registration rate
- API request rate (per user)
- Error rate (4xx/5xx)
- Average container spin-up time
- Idle spin-down frequency

---

## Troubleshooting

### Container Not Starting

```bash
# Check logs
docker logs agent-{user_id}

# Inspect container
docker inspect agent-{user_id}

# Verify image exists
docker images | grep carbon-agent-adapter

# Check resource availability
docker stats
free -h
```

### Traefik Routing Issues

```bash
# Verify labels
docker inspect agent-{user_id} | jq '.[0].Config.Labels'

# Check Traefik logs
docker logs traefik 2>&1 | grep {user_id}

# Test routing directly
curl -H "Host: agents.carbon.dev" http://localhost/agent/{user_id}/health
```

### Webhook Not Triggering

```bash
# Check Clerk dashboard for webhook delivery status
# Verify Svix secret matches
echo $CLERK_WEBHOOK_SECRET

# Test webhook endpoint manually
curl -X POST http://localhost:8000/webhooks/clerk \
  -H "Content-Type: application/json" \
  -d '{"type":"user.created","data":{...}}'
```

### Database Migration Issues

```bash
# Check current version
alembic current

# Force to specific version
alembic stamp head

# Show migration SQL
alembic upgrade head --sql
```

---

## Development Workflow

### Local Development

```bash
# Start infrastructure
docker compose -f docker-compose.infra.yml up -d

# Run orchestrator locally
cd orchestrator
uvicorn app.main:app --reload --port 8000

# Run adapter locally
cd adapter
uvicorn app.main:app --reload --port 8001
```

### Code Style

- **Formatting**: Black (line length 88)
- **Imports**: isort (profile=black)
- **Type hints**: Required for all public APIs
- **Docstrings**: Google style for public methods

### Pre-commit (Recommended)

```yaml
repos:
  - repo: https://github.com/psf/black
    hooks: [{id: black}]
  - repo: https://github.com/pycqa/isort
    hooks: [{id: isort}]
  - repo: https://github.com/pycqa/flake8
    hooks: [{id: flake8}]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks: [{id: mypy}]
```

---

## Migration from Railway

### Steps

1. **Backup database**:
   ```bash
   docker exec postgres pg_dump -U carbon_admin carbon_platform > backup.sql
   ```

2. **Run migration**:
   ```bash
   alembic upgrade head
   ```

3. **Update environment**:
   - Remove: `RAILWAY_API_TOKEN`, `RAILWAY_PROJECT_ID`, `RAILWAY_TEAM_ID`, `RAILWAY_ENVIRONMENT_ID`
   - Add: `AGENT_DOCKER_IMAGE`, `AGENT_MEMORY_LIMIT`, `AGENT_CPU_NANOS`, `AGENT_DOMAIN`

4. **Deploy infrastructure**:
   ```bash
   docker compose -f docker-compose.infra.yml up -d
   ```

5. **Re-provision users**:
   - Existing users will get containers created on next activity
   - Or trigger manually via admin API: `POST /admin/users/{user_id}/spin-up`

6. **Update DNS**:
   - Point `*.agents.carbon.dev` to VPS IP
   - Wait for Traefik to obtain SSL certificates

### Breaking Changes

- `User.railway_service_id` → removed (use `User.status == ACTIVE`)
- `User.volume_id` → removed
- `Session.railway_deployment_id` → replaced with `Session.container_id`
- Service URL pattern: `https://agents.carbon.dev/agent/{user_id}`

---

## Useful Commands

```bash
# List all user containers
docker ps --filter "label=carbon.type=agent-instance"

# Get container for specific user
docker ps --filter "name=agent-{user_id}"

# Restart all containers
docker compose restart

# View resource usage
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Clean up stopped containers
docker container prune --filter "label=carbon.type=agent-instance"

# Backup database
docker exec postgres pg_dump -U carbon_admin carbon_platform > backup.sql

# Restore database
cat backup.sql | docker exec -i postgres psql -U carbon_admin carbon_platform
```

---

*Last updated: 2026-04-18 | Architecture: Docker Engine + Traefik + Clerk*
