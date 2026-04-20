# Docker Containerization - Deployment Checklist

## Pre-Deployment Verification

### Code & Files
- [x] Dockerfiles created for all services
  - [x] orchestrator/Dockerfile (already exists, pinned digest)
  - [x] adapter/Dockerfile (already exists, pinned digest)
  - [x] vector-store/Dockerfile (updated with best practices)
  - [x] carbon-agent-dashboard/Dockerfile (created)
  - [x] open-webui/Dockerfile (already exists)

- [x] .dockerignore files created
  - [x] orchestrator/.dockerignore
  - [x] adapter/.dockerignore
  - [x] vector-store/.dockerignore
  - [x] carbon-agent-dashboard/.dockerignore

- [x] Docker Compose files created
  - [x] docker-compose.dev.yml (7.5 KB)
  - [x] docker-compose.prod.yml (9.4 KB)
  - [x] docker-compose.yml (original, unchanged)
  - [x] docker-compose.infra.yml (original, unchanged)

- [x] Configuration files
  - [x] .env.production.example (template with all required variables)

- [x] Documentation
  - [x] DOCKER_COMPOSE_GUIDE.md (comprehensive operations guide)
  - [x] DOCKER_BEST_PRACTICES.md (best practices explanation)
  - [x] CONTAINERIZATION_SUMMARY.md (overview and next steps)

### Build Verification
- [x] orchestrator image builds successfully
- [x] adapter image builds successfully
- [x] vector-store Dockerfile valid
- [x] dashboard Dockerfile valid
- [x] open-webui image exists

### Configuration Validation
- [x] docker-compose.dev.yml is valid
- [x] docker-compose.prod.yml is valid (with .env.production.example)
- [x] All healthchecks configured properly
- [x] All resource limits configured
- [x] All ports properly bound

## Development Deployment (Local Testing)

### Prerequisites
- [x] Docker Desktop installed and running
- [x] docker-compose available
- [x] Sufficient disk space (minimum 10GB recommended)
- [x] Sufficient memory (minimum 8GB recommended)

### Steps
1. **Start the stack**
   ```bash
   docker compose -f docker-compose.dev.yml up --build
   ```
   - Expected time: 5-15 minutes (first run with npm install)
   - All services should reach "healthy" status

2. **Verify services**
   ```bash
   docker compose ps
   curl http://localhost:8000/health        # orchestrator
   curl http://localhost:8001/health        # adapter
   curl http://localhost:3000              # open-webui
   open http://localhost:3001              # dashboard
   ```

3. **Test functionality**
   - [ ] Create user via admin API: `POST /admin/users`
   - [ ] Verify database: `docker exec carbon_postgres psql -U postgres -d carbon_platform -c "\dt"`
   - [ ] Check logs: `docker compose logs -f orchestrator`

4. **Cleanup**
   ```bash
   docker compose down -v  # Remove volumes to reset
   ```

## Production Deployment (VPS)

### Prerequisites
- [ ] Ubuntu 22.04+ VPS with at least 4GB RAM, 20GB disk
- [ ] Docker installed: `curl -fsSL https://get.docker.com | sh`
- [ ] Docker Compose installed: `docker-compose --version`
- [ ] Domain with wildcard DNS (e.g., *.agents.example.com)
- [ ] Clerk account configured with webhooks
- [ ] Agent Zero API endpoint available
- [ ] SSL/TLS certificate ready (or Let's Encrypt setup)

### Configuration Steps
1. **Copy environment template**
   ```bash
   cp .env.production.example .env.production
   ```

2. **Edit with your values**
   ```bash
   nano .env.production
   ```
   
   Required variables to fill:
   - [ ] POSTGRES_PASSWORD (generate: `openssl rand -base64 32`)
   - [ ] REDIS_PASSWORD (generate: `openssl rand -base64 32`)
   - [ ] ADMIN_AGENT_API_KEY (generate: `openssl rand -base64 32`)
   - [ ] CLERK_SECRET_KEY
   - [ ] CLERK_PUBLISHABLE_KEY
   - [ ] CLERK_WEBHOOK_SECRET
   - [ ] CLERK_JWT_PUBLIC_KEY
   - [ ] CLERK_FRONTEND_API_URL
   - [ ] AGENT_API_URL
   - [ ] AGENT_API_KEY
   - [ ] AGENT_DOMAIN
   - [ ] CORS_ALLOWED_ORIGINS
   - [ ] OPENWEBUI_API_KEY
   - [ ] WEBUI_SECRET (generate: `openssl rand -base64 32`)
   - [ ] WEBUI_CORS_ORIGIN

3. **Verify configuration**
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production config | head -50
   ```

### Deployment Steps
1. **Pull latest images**
   ```bash
   docker compose -f docker-compose.prod.yml pull
   ```

2. **Start services**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

3. **Monitor startup**
   ```bash
   docker compose -f docker-compose.prod.yml logs -f
   # Wait for all services to reach 'healthy' status
   ```

4. **Verify deployment**
   ```bash
   docker compose -f docker-compose.prod.yml ps
   
   # Test endpoints
   curl http://localhost:8000/health           # Should return 200
   curl http://localhost:8001/health           # Should return 200
   ```

5. **Configure reverse proxy** (nginx example)
   ```nginx
   # Redirect HTTP to HTTPS
   server {
       listen 80;
       server_name agents.example.com *.agents.example.com;
       return 301 https://$server_name$request_uri;
   }
   
   # HTTPS configuration
   server {
       listen 443 ssl http2;
       server_name agents.example.com *.agents.example.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://127.0.0.1:8001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

## Post-Deployment Verification

### Health Checks
- [ ] All containers running: `docker compose ps`
- [ ] Database is healthy: `docker exec carbon_postgres_prod pg_isready -U postgres`
- [ ] Redis is healthy: `docker exec carbon_redis_prod redis-cli ping`
- [ ] Services respond to health endpoints
- [ ] No error logs in any service

### Functionality Tests
- [ ] User creation via admin API
- [ ] Clerk webhook integration
- [ ] API key generation
- [ ] Chat functionality in open-webui
- [ ] Dashboard loads and displays correctly
- [ ] Vector embeddings working

### Performance Baseline
- [ ] Monitor resource usage: `docker stats --no-stream`
- [ ] Check response times with `curl -w @curl-format.txt`
- [ ] Load test with concurrent requests

### Security Verification
- [ ] Docker socket is read-only: `ls -l /var/run/docker.sock`
- [ ] Secrets are not in logs: `docker compose logs | grep -i password`
- [ ] CORS is properly restricted
- [ ] HTTPS/TLS is enabled on reverse proxy
- [ ] No exposed sensitive data in environment

## Monitoring & Maintenance

### Daily
- [ ] Check `docker compose ps` for any stopped containers
- [ ] Monitor disk usage: `df -h`
- [ ] Review application logs for errors

### Weekly
- [ ] Run vulnerability scan: `docker scout cves`
- [ ] Check for base image updates
- [ ] Review database size: `docker exec carbon_postgres_prod du -sh /var/lib/postgresql/data`
- [ ] Verify backups are running

### Monthly
- [ ] Update all base images
- [ ] Review and update dependencies
- [ ] Performance analysis and capacity planning
- [ ] Security audit of configuration

### Quarterly
- [ ] Full stack health check
- [ ] Disaster recovery drill
- [ ] Architecture review for scaling

## Backup & Recovery

### Database Backup
```bash
# Create backup
docker exec carbon_postgres_prod pg_dump -U postgres carbon_platform > backup.sql

# Restore from backup
docker exec -i carbon_postgres_prod psql -U postgres carbon_platform < backup.sql
```

### Volume Backups
```bash
# Backup pgdata volume
docker run --rm -v pgdata:/data -v $(pwd):/backup \
  alpine tar czf /backup/pgdata.tar.gz -C /data .

# Restore pgdata volume
docker run --rm -v pgdata:/data -v $(pwd):/backup \
  alpine tar xzf /backup/pgdata.tar.gz -C /data
```

## Troubleshooting

### Service won't start
```bash
docker compose -f docker-compose.prod.yml logs orchestrator | tail -50
```

### Database connection errors
```bash
docker compose -f docker-compose.prod.yml logs postgres
docker exec carbon_postgres_prod psql -U postgres -c "SELECT version();"
```

### Memory exhaustion
```bash
docker stats --no-stream
# Increase limits in docker-compose.prod.yml and restart
docker compose -f docker-compose.prod.yml up -d
```

### Disk space issues
```bash
docker system df
docker system prune -a  # Remove unused images/containers/networks
```

See **DOCKER_COMPOSE_GUIDE.md** for detailed troubleshooting.

## Rollback Plan

If deployment fails or issues occur:

1. **Stop new version**
   ```bash
   docker compose -f docker-compose.prod.yml down
   ```

2. **Restore database from backup**
   ```bash
   docker exec -i carbon_postgres_prod psql -U postgres carbon_platform < backup.sql
   ```

3. **Redeploy previous version**
   ```bash
   git checkout <previous-commit>
   docker compose -f docker-compose.prod.yml up -d --build
   ```

## Success Criteria

✅ Deployment is successful when:
- [ ] All containers are running and healthy
- [ ] Database migrations completed successfully
- [ ] Users can sign up via Clerk
- [ ] API endpoints respond with proper status codes
- [ ] No error logs indicating critical issues
- [ ] Resource usage is within expected ranges
- [ ] SSL/TLS certificate is valid and trusted
- [ ] All monitoring and logging is operational

## Documentation References

- **CONTAINERIZATION_SUMMARY.md** - High-level overview
- **DOCKER_COMPOSE_GUIDE.md** - Detailed operations guide
- **DOCKER_BEST_PRACTICES.md** - Best practices explanation
- **.env.production.example** - Environment template
- **README.md** - Project overview
- **SYSTEM_ARCHITECTURE.md** - Architecture details

---

**Ready for Deployment** ✅

Your project is fully containerized and ready for development and production deployment.
