# Carbon Agent Platform - Docker Compose Configuration Guide

## Overview

This directory contains Docker Compose configurations for the Carbon Agent Platform:

- **docker-compose.yml** - Default development configuration (for backward compatibility)
- **docker-compose.dev.yml** - Development configuration with local rebuilds
- **docker-compose.prod.yml** - Production-ready configuration with strict security and resource constraints
- **docker-compose.infra.yml** - Infrastructure only (Traefik, PostgreSQL, Redis) for local agent deployment

## Quick Start - Development

```bash
# Start all services
docker compose -f docker-compose.dev.yml up --build

# Or use the default compose file
docker compose up --build

# View logs
docker compose logs -f orchestrator

# Stop all services
docker compose down
```

## Production Deployment

### Prerequisites

1. VPS with Docker and Docker Compose installed
2. Environment variables configured in `.env.production`
3. Database and Redis credentials set
4. Clerk authentication secrets configured
5. Agent Zero API configured and accessible

### Setup

```bash
# Copy production environment template
cp .env.production.example .env.production

# Edit with your production secrets
nano .env.production

# Verify all required variables are set
grep "error - set" docker-compose.prod.yml | grep -oP '(?<=set )\w+' | sort -u

# Start production stack
docker compose -f docker-compose.prod.yml up -d --build

# Monitor logs
docker compose -f docker-compose.prod.yml logs -f
```

### Required Environment Variables

**Database:**
- `POSTGRES_PASSWORD` - PostgreSQL password (required, must be strong)
- `POSTGRES_USER` - PostgreSQL username (default: postgres)
- `POSTGRES_DB` - Database name (default: carbon_platform)

**Redis:**
- `REDIS_PASSWORD` - Redis password (required, must be strong)

**Clerk Authentication:**
- `CLERK_SECRET_KEY` - Clerk secret key
- `CLERK_PUBLISHABLE_KEY` - Clerk publishable key
- `CLERK_WEBHOOK_SECRET` - Clerk webhook secret (Svix)
- `CLERK_JWT_PUBLIC_KEY` - Clerk JWT public key

**Admin API:**
- `ADMIN_AGENT_API_KEY` - Admin API key for orchestrator

**Agent Configuration:**
- `AGENT_DOCKER_IMAGE` - Docker image for agent containers (must be built and pushed to registry)
- `AGENT_API_URL` - Agent Zero API base URL
- `AGENT_API_KEY` - Agent Zero API key
- `AGENT_DOMAIN` - Domain for agent routing (e.g., agents.example.com)

**Application:**
- `CORS_ALLOWED_ORIGINS` - Comma-separated CORS origins (e.g., https://dashboard.example.com)
- `OPENWEBUI_API_KEY` - OpenWebUI API key
- `WEBUI_SECRET` - Open WebUI secret key
- `WEBUI_CORS_ORIGIN` - CORS origin for Open WebUI
- `CLERK_FRONTEND_API_URL` - Clerk frontend URL

**Optional:**
- `MODEL_NAME` - LLM model name (default: carbon-agent)
- `EMBEDDING_MODEL` - Embedding model name (default: all-MiniLM-L6-v2)
- `SESSION_IDLE_TIMEOUT_MINUTES` - Session timeout (default: 15)
- `SESSION_MAX_LIFETIME_HOURS` - Max session lifetime (default: 24)

## Service Architecture

### Core Services

| Service | Port | Purpose |
|---------|------|---------|
| **orchestrator** | 8000 | User management, Docker lifecycle, admin API |
| **adapter** | 8001 | OpenAI-compatible chat API, Agent Zero translation |
| **open-webui** | 3000 | Web UI for chat interface |
| **dashboard** | 3001 | Admin dashboard (Next.js) |

### Supporting Services

| Service | Port | Purpose |
|---------|------|---------|
| **postgres** | 5432 | User data, sessions, audit logs |
| **redis** | 6379 | Caching, rate limiting, context store |
| **chromadb** | 8002 | Vector database for embeddings |
| **vector-store** | 8003 | Embedding and retrieval service |

## Health Checks

All services include health checks with appropriate timeouts:

```bash
# Check service health
docker compose ps

# View detailed health status
docker inspect carbon_orchestrator_prod --format='{{json .State.Health}}'

# Manual service health checks
curl http://localhost:8000/health           # orchestrator
curl http://localhost:8001/health           # adapter
curl http://localhost:3000/                 # open-webui
curl http://localhost:8002/api/v1/heartbeat # chromadb
curl http://localhost:8003/health           # vector-store
```

## Resource Limits

Production configuration includes memory limits to prevent resource exhaustion:

- **postgres**: 1GB limit, 512MB reservation
- **redis**: 512MB limit, 256MB reservation
- **orchestrator**: 1GB limit, 512MB reservation
- **adapter**: 1GB limit, 512MB reservation
- **chromadb**: 2GB limit, 1GB reservation
- **vector-store**: 2GB limit, 1GB reservation
- **open-webui**: 2GB limit, 1GB reservation
- **dashboard**: 512MB limit, 256MB reservation

Monitor resource usage with:
```bash
docker compose ps --no-trunc
docker stats
```

## Database Setup

### Initial Setup

```bash
# Migrations run automatically on orchestrator startup
# Verify database is initialized
docker exec carbon_postgres_prod psql -U postgres -d carbon_platform -c "\dt"
```

### Backup

```bash
# Backup database
docker exec carbon_postgres_prod pg_dump -U postgres carbon_platform > backup.sql

# Restore database
docker exec -i carbon_postgres_prod psql -U postgres carbon_platform < backup.sql
```

## Troubleshooting

### Service won't start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs orchestrator

# Verify environment variables
grep -E '^\w+=' .env.production

# Check Docker socket permissions
ls -l /var/run/docker.sock
```

### Database connection errors

```bash
# Test database connectivity
docker exec carbon_orchestrator_prod python -c \
  "import asyncpg; print('Database OK')"

# Check PostgreSQL logs
docker compose -f docker-compose.prod.yml logs postgres
```

### Memory issues

```bash
# Monitor memory usage
docker stats

# Increase limits in docker-compose.prod.yml
# Update deploy.resources.limits.memory values
# Restart services: docker compose -f docker-compose.prod.yml up -d
```

## Networking

Services communicate via the `carbon_network` bridge network. To access services from the host:

- Development: `localhost:PORT` (ports exposed on 0.0.0.0)
- Production: `127.0.0.1:PORT` (ports exposed on loopback for reverse proxy only)

Inter-service communication uses service names:
- Orchestrator → Redis: `redis://redis:6379`
- Adapter → ChromaDB: `http://chromadb:8000`

## Logging

All services use `json-file` driver with rotation:

```bash
# View logs
docker compose logs -f orchestrator

# Follow logs with timestamps
docker compose logs -f --timestamps orchestrator

# Show last 100 lines
docker compose logs --tail=100 orchestrator

# View logs since timestamp
docker compose logs --since 2024-01-01T00:00:00 orchestrator
```

## Volumes

| Volume | Purpose | Persistence |
|--------|---------|-------------|
| **pgdata** | PostgreSQL data directory | Production essential |
| **redis_data** | Redis append-only file | Production recommended |
| **openwebui** | Open WebUI settings and data | Application data |
| **vector_data** | ChromaDB embeddings | Production essential |

Backup volumes:

```bash
# Backup named volumes
docker run --rm -v pgdata:/data -v $(pwd):/backup \
  alpine tar czf /backup/pgdata.tar.gz -C /data .

# Restore volumes
docker run --rm -v pgdata:/data -v $(pwd):/backup \
  alpine tar xzf /backup/pgdata.tar.gz -C /data
```

## Scaling Considerations

For production deployments beyond 50 concurrent users:

1. **Database**: Use managed PostgreSQL service (RDS, Cloud SQL)
2. **Redis**: Use managed Redis service (ElastiCache, Memorystore)
3. **Adapter**: Scale horizontally with load balancer
4. **Vector Store**: Separate infrastructure with dedicated resources

## Security Best Practices

1. **Environment Variables**: Store sensitive values in `.env.production`, never in compose files
2. **Network Access**: Bind services to 127.0.0.1 in production, use reverse proxy for public access
3. **Docker Socket**: Mount read-only where possible (`/var/run/docker.sock:ro`)
4. **Image Scanning**: Regularly scan images for vulnerabilities with `docker scout`
5. **Updates**: Keep base images (python:3.12-slim, node:20-alpine) updated monthly
6. **Secrets Management**: Use Docker secrets or external secret management for production

## Updates and Maintenance

### Weekly

```bash
# Check for base image updates
docker pull python:3.12-slim
docker pull node:20-alpine

# Rebuild affected services
docker compose -f docker-compose.prod.yml build --no-cache adapter
```

### Monthly

```bash
# Scan images for vulnerabilities
docker scout cves carbon_orchestrator_prod:latest

# Update dependencies in requirements.txt and package.json
# Rebuild and test in staging
```

### Quarterly

```bash
# Full stack health check and performance review
# Update all base images to latest minor version
# Review resource allocations based on metrics
```
