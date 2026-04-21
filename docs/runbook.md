# Carbon Agent Platform — Operational Runbook

**Environment**: Hostinger Ubuntu VPS + Docker Compose
**Live URL**: `http://187.127.112.59:3001/`
**Last Updated**: 2026-04-21

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [User Management](#user-management)
3. [Container Lifecycle](#container-lifecycle)
4. [Clerk Webhook Operations](#clerk-webhook-operations)
5. [Database Operations](#database-operations)
6. [Deployment & Updates](#deployment--updates)
7. [Troubleshooting](#troubleshooting)
8. [Security Procedures](#security-procedures)

---

## Daily Operations

### Check System Health

```bash
# SSH into the VPS
ssh user@187.127.112.59

# Check all containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Expected output: all containers show "Up" or "healthy"
# carbon_postgres_prod, carbon_redis_prod, carbon_orchestrator_prod,
# carbon_adapter_prod, carbon_chromadb_prod, carbon_vector_store_prod,
# carbon_webui_prod, carbon_dashboard_prod, contract_hub_postgres_prod,
# contract_hub_prod
```

### View Logs

```bash
# Follow orchestrator logs (structured JSON)
docker compose -f docker-compose.prod.yml logs -f --tail=100 orchestrator

# Follow dashboard logs
docker compose -f docker-compose.prod.yml logs -f --tail=100 dashboard

# All services at once
docker compose -f docker-compose.prod.yml logs -f --tail=50

# Filter by time
docker compose -f docker-compose.prod.yml logs --since=1h orchestrator
```

### Check Metrics

```bash
# Prometheus-style metrics from orchestrator
curl http://localhost:8000/metrics

# Health endpoints
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:3001/api/health  # dashboard
```

---

## User Management

### Reprovision a User's Docker Container

If a user's container is missing or failed:

```bash
# Via admin API (requires admin JWT or API key)
curl -X POST http://localhost:8000/user/me/service/ensure \
  -H "Authorization: Bearer <USER_API_KEY>"

# Or spin down and recreate via admin UI
# Visit: http://187.127.112.59:3001/admin/ui
```

### Find a User by Email

```bash
# Connect to PostgreSQL
docker exec -it carbon_postgres_prod psql -U postgres -d carbon_platform

# Query
SELECT id, email, status, clerk_user_id, api_key FROM users WHERE email = 'user@example.com';
\q
```

### Rotate a User's API Key (Admin)

```bash
# As the user (using their current key)
curl -X POST http://localhost:8000/user/me/api-key/rotate \
  -H "Authorization: Bearer <CURRENT_API_KEY>"

# Response: {"new_api_key": "sk-..."}
# The old key is immediately invalidated.
```

---

## Container Lifecycle

### List Active User Containers

```bash
# All Carbon Agent containers
docker ps --filter "name=agent-" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"

# Inspect a specific container
docker inspect agent-<user_id> --format '{{json .State}}' | jq
```

### Manually Stop a User Container

```bash
# Stop (keeps container for fast restart)
docker stop agent-<user_id>

# Remove completely (data in container is lost, user status becomes PENDING)
docker rm -f agent-<user_id>
```

### Check Container Resource Usage

```bash
# Stats for all containers
docker stats --no-stream

# Specific container
docker stats --no-stream agent-<user_id>
```

---

## Clerk Webhook Operations

### Rotate Clerk Webhook Secret

1. Go to [Clerk Dashboard](https://dashboard.clerk.com/) → Webhooks
2. Delete the old endpoint and create a new one
3. Copy the new signing secret
4. Update the VPS:

```bash
# Edit .env file
nano /opt/carbon-agent-platform/.env

# Update CLERK_WEBHOOK_SECRET
# Save and exit

# Restart orchestrator to pick up the new secret
docker compose -f docker-compose.prod.yml restart orchestrator

# Verify: trigger a test webhook from Clerk dashboard
```

### Debug Webhook Failures

```bash
# Check orchestrator webhook logs
docker compose -f docker-compose.prod.yml logs orchestrator | grep -i "webhook"

# Common issues:
# - "Invalid webhook signature" → Secret mismatch or clock skew
# - "Payload too large" → Clerk sending unexpectedly large payloads
# - "Missing Svix signature headers" → Middleware stripping headers

# Test connectivity from Clerk's perspective
curl -I http://187.127.112.59:3000/webhooks/clerk
# Should return 405 (method not allowed) or 400 (missing headers), NOT 404 or timeout
```

### Replay a Webhook

If a webhook was missed (e.g., during downtime):

```bash
# Clerk does not automatically retry. Options:
# 1. Use Clerk Dashboard → Webhooks → Delivery Attempts → Resend
# 2. Or manually create the user via admin API:

curl -X POST http://localhost:8000/admin/users \
  -H "X-Admin-Key: ${ADMIN_AGENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "display_name": "User Name",
    "clerk_user_id": "user_xxx"
  }'
```

---

## Database Operations

### Backup PostgreSQL

```bash
# Full backup
docker exec carbon_postgres_prod pg_dump -U postgres carbon_platform \
  > /backups/carbon_platform_$(date +%Y%m%d_%H%M%S).sql

# Compress backup
docker exec carbon_postgres_prod pg_dump -U postgres carbon_platform | gzip \
  > /backups/carbon_platform_$(date +%Y%m%d_%H%M%S).sql.gz

# Contract Hub backup
docker exec contract_hub_postgres_prod pg_dump -U contracthub contracthub \
  > /backups/contracthub_$(date +%Y%m%d_%H%M%S).sql
```

### Restore PostgreSQL

```bash
# WARNING: This overwrites existing data. Stop services first.
docker compose -f docker-compose.prod.yml stop orchestrator adapter contract-hub

# Restore
docker exec -i carbon_postgres_prod psql -U postgres carbon_platform < backup.sql

# Restart services
docker compose -f docker-compose.prod.yml start orchestrator adapter contract-hub
```

### Run Migrations

```bash
# Enter orchestrator container
docker exec -it carbon_orchestrator_prod bash

# Run Alembic migrations
cd /app && alembic upgrade head

# Check current version
alembic current

# Exit
exit
```

### Recover from Migration Failure

```bash
# If migration fails, check the error
docker compose -f docker-compose.prod.yml logs orchestrator

# Option 1: Fix the migration script and retry
# Option 2: Downgrade to previous version
docker exec -it carbon_orchestrator_prod bash -c "cd /app && alembic downgrade -1"

# Option 3: Mark as resolved manually (dangerous — only if you know the migration already ran)
docker exec -it carbon_orchestrator_prod bash -c \
  "cd /app && alembic stamp <revision_id>"
```

---

## Deployment & Updates

### Full Redeploy

```bash
# 1. Pull latest code
cd /opt/carbon-agent-platform
git pull origin main

# 2. Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build

# 3. Verify health
docker ps
curl -f http://localhost:8000/health || echo "ORCHESTRATOR UNHEALTHY"
curl -f http://localhost:3001/api/health || echo "DASHBOARD UNHEALTHY"

# 4. Clean old images
docker image prune -f
```

### Rolling Update (Zero-Downtime-ish)

```bash
# Update orchestrator only
docker compose -f docker-compose.prod.yml build orchestrator
docker compose -f docker-compose.prod.yml up -d orchestrator

# Update dashboard only
docker compose -f docker-compose.prod.yml build dashboard
docker compose -f docker-compose.prod.yml up -d dashboard
```

### Scale for Load Spike

This stack runs on a single VPS. For load spikes:

```bash
# Option 1: Increase container resource limits in docker-compose.prod.yml
# Edit the deploy.resources.limits section, then:
docker compose -f docker-compose.prod.yml up -d

# Option 2: Vertical scaling — resize the Hostinger VPS plan
# (Requires Hostinger panel action, then restart containers)

# Option 3: Enable swap as emergency buffer
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs --tail=50 <service>

# Check exit code
docker inspect <container_name> --format='{{.State.ExitCode}}'

# Common exit codes:
# 1  → Application error (check logs)
# 137 → OOMKilled (increase memory limit)
# 143 → Graceful shutdown (SIGTERM)
```

### Database Connection Refused

```bash
# Check Postgres is running
docker ps | grep postgres

# Check network connectivity
docker exec carbon_orchestrator_prod ping -c 3 carbon_postgres_prod

# Verify DATABASE_URL in orchestrator env
docker exec carbon_orchestrator_prod env | grep DATABASE_URL

# Check Postgres logs
docker compose -f docker-compose.prod.yml logs postgres
```

### Clerk Auth Fails

```bash
# Verify Clerk keys are set
docker exec carbon_dashboard_prod env | grep CLERK
docker exec carbon_orchestrator_prod env | grep CLERK

# Check JWT verification
curl -X POST http://localhost:8000/v1/auth/verify \
  -H "Authorization: Bearer <JWT_FROM_BROWSER>"

# Common issues:
# - Clock skew: ensure VPS time is correct (sudo timedatectl)
# - Wrong CLERK_JWT_ISSUER: must match your Clerk instance domain
# - CORS mismatch: CORS_ALLOWED_ORIGINS must include the dashboard URL
```

### API Key Injection Fails

```bash
# Verify middleware is running (check logs for "api_key_injected")
docker compose -f docker-compose.prod.yml logs orchestrator | grep -i "api_key"

# Test manually
curl -H "Authorization: Bearer <USER_API_KEY>" http://localhost:8000/v1/chat/completions
# Should proxy to adapter with key injected
```

### High Memory Usage

```bash
# Identify the culprit
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# If Open WebUI is consuming too much:
docker update --memory=3g carbon_webui_prod

# If orchestrator is high:
# - Check active session count: look for "active_sessions" in logs
# - Review idle timeout: SESSION_IDLE_TIMEOUT_MINUTES
```

---

## Security Procedures

### Rotate Admin API Key

```bash
# 1. Generate new key
NEW_KEY=$(openssl rand -hex 32)
echo "New admin key: $NEW_KEY"

# 2. Update .env
sed -i "s/ADMIN_AGENT_API_KEY=.*/ADMIN_AGENT_API_KEY=$NEW_KEY/" .env

# 3. Restart affected services
docker compose -f docker-compose.prod.yml up -d --build orchestrator adapter

# 4. Update any external scripts or CI that use the old key
```

### Rotate Database Password

```bash
# 1. Stop services
docker compose -f docker-compose.prod.yml stop

# 2. Update .env with new POSTGRES_PASSWORD

# 3. Start Postgres only
docker compose -f docker-compose.prod.yml up -d postgres

# 4. Change password inside Postgres
docker exec -it carbon_postgres_prod psql -U postgres -c \
  "ALTER USER postgres WITH PASSWORD 'new-password';"

# 5. Start all services
docker compose -f docker-compose.prod.yml up -d
```

### Firewall Rules

```bash
# UFW status
sudo ufw status verbose

# Recommended rules for Hostinger VPS
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (if using Nginx/Traefik directly)
sudo ufw allow 443/tcp   # HTTPS (if using Nginx/Traefik directly)
sudo ufw allow 3001/tcp  # Dashboard (if exposing directly)
sudo ufw enable

# Note: Internal Docker ports (8000, 8001, 5432, 6379) should NOT be exposed
# to the internet. docker-compose.prod.yml binds them to 127.0.0.1.
```

---

## Contact & Escalation

- **Clerk Issues**: https://clerk.com/support
- **Hostinger Support**: Hostinger hPanel → Support
- **Docker Docs**: https://docs.docker.com/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
