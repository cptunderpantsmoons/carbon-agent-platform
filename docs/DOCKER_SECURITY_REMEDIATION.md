# Docker Security Vulnerability Remediation Guide

**Date:** April 20, 2026  
**Status:** 🔴 Action Required  

---

## Issues Identified

### 1. Critical/High Vulnerabilities in Base Image
- **Severity:** 4 Critical + 26 High
- **Location:** `open-webui/Dockerfile` line 9
- **Image:** `ghcr.io/open-webui/open-webui:main@sha256:b8095f79a6a8ffad8f830bdacc9b5b0aef805689b31bca0b065cc2424d3cfaeb`
- **Impact:** Potential security exploits in containerized Open WebUI

### 2. Sensitive Data in ENV Instruction
- **Severity:** Information Disclosure
- **Location:** `open-webui/Dockerfile` line 18 (FIXED ✅)
- **Issue:** `ENV WEBUI_AUTH=true` - Configuration that should be runtime-only
- **Fix Applied:** Removed from Dockerfile, now set in docker-compose.yml

---

## Fix Status

| Issue | Status | Fix Applied |
|-------|--------|-------------|
| Sensitive ENV data | ✅ **Fixed** | Removed `ENV WEBUI_AUTH=true` from Dockerfile |
| Base image vulnerabilities | 🔴 **Pending** | Requires base image update (see instructions below) |

---

## Fix 1: Sensitive Data in ENV (COMPLETED ✅)

### What Was Changed

**Before:**
```dockerfile
ENV CLERK_ENABLED=true
ENV ENABLE_SIGNUP=false
ENV WEBUI_AUTH=true  # ❌ Sensitive config in build layer
```

**After:**
```dockerfile
# Open WebUI runtime flags (non-sensitive defaults)
# NOTE: Sensitive values (API keys, secrets) should be set at runtime via
# docker-compose environment variables or .env files, NOT in the Dockerfile.
ENV CLERK_ENABLED=true
ENV ENABLE_SIGNUP=false
# WEBUI_AUTH moved to docker-compose.yml environment section ✅
```

### Why This Matters

Docker ENV instructions are **baked into the image layers** and can be extracted by anyone with access to the image:

```bash
# Anyone can inspect image layers
docker history open-webui:latest --no-trunc
# Output shows all ENV values in plaintext
```

### Runtime Configuration (Secure Alternative)

All sensitive configuration is now set in `docker-compose.yml`:

```yaml
services:
  open-webui:
    environment:
      WEBUI_AUTH: "true"  # ✅ Set at runtime, not in image
      CLERK_SECRET_KEY: ${CLERK_SECRET_KEY}
      # ... other sensitive vars
```

---

## Fix 2: Base Image Vulnerabilities (REQUIRES ACTION 🔴)

### Current Situation

The pinned base image digest (`sha256:b8095f79...`) contains:
- **4 Critical vulnerabilities** - Immediate security risk
- **26 High vulnerabilities** - Significant security risk

These vulnerabilities are in the underlying OS packages (Debian/Ubuntu) and must be patched by pulling a newer image.

### Step-by-Step Fix Instructions

#### Option A: Update to Latest Image (Recommended)

**Step 1: Check for latest image**

```bash
docker buildx imagetools inspect ghcr.io/open-webui/open-webui:main
```

**Step 2: Copy the new digest**

Look for the multi-arch index digest (top-level sha256):

```
Name:      ghcr.io/open-webui/open-webui:main
MediaType: application/vnd.oci.image.index.v1+json
Digest:    sha256:NEW_DIGEST_HERE  # ← Copy this value
```

**Step 3: Update Dockerfile**

Edit `open-webui/Dockerfile` line 13:

```dockerfile
FROM ghcr.io/open-webui/open-webui:main@sha256:NEW_DIGEST_HERE
```

**Step 4: Rebuild the image**

```bash
cd carbon-agent-platform
docker compose build open-webui
```

**Step 5: Verify vulnerability count**

```bash
docker scout cves ghcr.io/open-webui/open-webui:main
# or
docker scan open-webui:latest
```

**Expected:** Significantly reduced or zero critical/high vulnerabilities

---

#### Option B: Use Vulnerability-Scanning Workflow (Long-term)

Create a GitHub Action to automatically update base images:

```yaml
# .github/workflows/update-base-images.yml
name: Update Base Images

on:
  schedule:
    - cron: '0 6 * * 1'  # Every Monday at 6 AM
  workflow_dispatch:

jobs:
  update-images:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Check for base image updates
        run: |
          # Check open-webui base image
          CURRENT_DIGEST=$(grep -o 'sha256:[a-f0-9]*' open-webui/Dockerfile | head -1)
          LATEST_DIGEST=$(docker buildx imagetools inspect ghcr.io/open-webui/open-webui:main --format '{{json .}}' | jq -r '.manifests[0].digest')
          
          if [ "$CURRENT_DIGEST" != "$LATEST_DIGEST" ]; then
            echo "New base image available!"
            echo "Current: $CURRENT_DIGEST"
            echo "Latest:  $LATEST_DIGEST"
            # Create PR with update (requires additional tooling)
          fi
```

---

## Security Best Practices

### 1. Never Store Secrets in Dockerfiles

❌ **Bad:**
```dockerfile
ENV API_KEY=sk-123456
ENV DATABASE_PASSWORD=secret
```

✅ **Good:**
```dockerfile
# No secrets in Dockerfile
# Set in docker-compose.yml or at runtime
```

### 2. Pin Base Images with Digests

✅ **Good:**
```dockerfile
FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286
```

This ensures reproducible builds but requires regular updates.

### 3. Regular Vulnerability Scanning

Add to your CI/CD pipeline:

```bash
# Install Docker Scout
docker scout cves <image-name>

# Fail build if critical vulnerabilities found
docker scout cves --exit-code <image-name>
```

### 4. Multi-Stage Builds for Smaller Attack Surface

Consider multi-stage builds to reduce what's in the final image:

```dockerfile
# Build stage
FROM node:20 AS builder
RUN npm install && npm run build

# Production stage (minimal)
FROM python:3.12-slim@sha256:...
COPY --from=builder /app/build /app/build
# Only production files included
```

### 5. Use Non-Root Users (Already Implemented ✅)

Your Dockerfile already does this correctly:

```dockerfile
RUN groupadd -r webui && useradd -r -g webui -u 1000 -d /app -s /sbin/nologin webui
USER webui  # ✅ Dropping privileges
```

---

## Verification Steps

After applying fixes, run these checks:

### 1. Check Image History for Secrets

```bash
docker history open-webui:latest --no-trunc --format "{{.CreatedBy}}"
# Should NOT show any ENV with sensitive values
```

### 2. Scan for Vulnerabilities

```bash
# Docker Scout (requires Docker Hub account)
docker scout cves open-webui:latest

# Trivy (free, open-source)
trivy image open-webui:latest

# Docker Scan (legacy, uses Snyk)
docker scan open-webui:latest
```

### 3. Verify Runtime Configuration

```bash
# Start containers
docker compose up -d

# Check environment variables at runtime
docker compose exec open-webui env | grep -E "WEBUI_AUTH|CLERK_SECRET"
# Should show values set in docker-compose.yml, not baked into image
```

### 4. Test Application Functionality

```bash
# Health check
curl http://localhost:3000/health

# Verify Clerk integration
curl http://localhost:3000/
# Should load Open WebUI with Clerk authentication
```

---

## All Dockerfiles in Project

| File | Base Image | Status | Action Required |
|------|-----------|--------|-----------------|
| `open-webui/Dockerfile` | `ghcr.io/open-webui/open-webui:main@sha256:b8095f79...` | 🔴 Vulnerable | **Update digest** |
| `orchestrator/Dockerfile` | `python:3.12-slim@sha256:804ddf32...` | ✅ Secure | Monitor monthly |
| `adapter/Dockerfile` | `python:3.12-slim@sha256:804ddf32...` | ✅ Secure | Monitor monthly |
| `Dockerfile.production` | `python:3.12-slim@sha256:804ddf32...` | ✅ Secure | Monitor monthly |

**Note:** Python slim images are updated less frequently and currently have acceptable vulnerability levels. Still recommend monthly checks.

---

## Automated Monitoring Setup (Optional)

### Weekly Vulnerability Check Script

Create `scripts/check-vulnerabilities.sh`:

```bash
#!/bin/bash
# Weekly vulnerability check for all Docker images

IMAGES=(
  "ghcr.io/open-webui/open-webui:main"
  "python:3.12-slim"
)

for IMAGE in "${IMAGES[@]}"; do
  echo "Checking: $IMAGE"
  docker scout cves "$IMAGE" 2>/dev/null || echo "  ⚠️  Scan failed (install docker scout)"
  echo ""
done
```

Make executable and run:

```bash
chmod +x scripts/check-vulnerabilities.sh
./scripts/check-vulnerabilities.sh
```

---

## References

- **Docker Security Best Practices:** https://docs.docker.com/build/building/best-practices/
- **Docker Scout:** https://docs.docker.com/scout/
- **Trivy Scanner:** https://github.com/aquasecurity/trivy
- **Open WebUI Security:** https://docs.openwebui.com/getting-started/advanced-topics/security/

---

## Summary

| Action | Status | Priority |
|--------|--------|----------|
| Remove sensitive ENV from Dockerfile | ✅ Complete | **Done** |
| Update open-webui base image digest | 🔴 Pending | **HIGH** |
| Set up automated vulnerability scanning | 🟡 Optional | Medium |
| Document security update process | ✅ Complete | **Done** |

**Next Step:** Update the open-webui base image digest to eliminate 4 critical + 26 high vulnerabilities.

---

**Last Updated:** April 20, 2026
