# Obot MCP Integration Guide

**Document:** MCP Registry Setup and Integration with Carbon Agent Platform  
**Version:** 1.0.0  
**Date:** April 20, 2026  
**Status:** Draft  

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Step-by-Step Setup](#step-by-step-setup)
5. [Configuration Parameters](#configuration-parameters)
6. [Network Topology](#network-topology)
7. [Integration Testing](#integration-testing)
8. [Troubleshooting](#troubleshooting)
9. [Security Considerations](#security-considerations)
10. [Performance Optimization](#performance-optimization)

---

## Overview

This guide covers the integration of **obot** (an open-source MCP platform) with the Carbon Agent Platform to enable tool-augmented AI agent capabilities. The integration allows Agent Zero to leverage external tools (web search, browser automation, code execution, etc.) through the Model Context Protocol (MCP).

### What is MCP?

**Model Context Protocol (MCP)** is an open standard that enables AI models to interact with external tools and data sources through a standardized interface. MCP provides:

- **Tool Discovery** — Agents can list available tools and their parameters
- **Tool Execution** — Agents can call tools with structured parameters
- **Standardized Communication** — JSON-RPC based protocol for tool interactions

### Why obot?

obot is a complete MCP platform that provides:

- **MCP Gateway** — Single entry point for all tool interactions
- **MCP Registry** — Central catalog of available tools
- **Tool Hosting** — Run MCP servers in Docker or Kubernetes
- **Access Control** — OAuth 2.1 authentication and authorization
- **Audit Logging** — Complete request/response logging

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CARBON AGENT PLATFORM                                 │
│                                                                             │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────────────┐   │
│  │  Open WebUI     │    │  Orchestrator    │    │  Adapter              │   │
│  │  (Port 3000)    │    │  (Port 8000)     │    │  (Port 8001)          │   │
│  │                 │    │                  │    │                       │   │
│  │  - Chat UI      │    │  - User mgmt     │    │  - MCP Client         │   │
│  │  - Clerk Auth   │    │  - Docker prov.  │    │  - Tool routing       │   │
│  │  - Session mgmt │    │  - Session mgmt  │    │  - Agent Zero proxy   │   │
│  └────────┬────────┘    └────────┬─────────┘    └───────────┬───────────┘   │
│           │                      │                          │                │
└───────────┼──────────────────────┼──────────────────────────┼────────────────┘
            │                      │                          │
            └──────────────────────┼──────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    PostgreSQL + Redis        │
                    │    (Shared infrastructure)   │
                    └──────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    obot MCP Gateway          │
                    │    (Port 8080)               │
                    │                              │
                    │  - MCP Registry              │
                    │  - Tool hosting              │
                    │  - Access control            │
                    │  - Audit logging             │
                    └──────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    MCP Servers (Tools)       │
                    │                              │
                    │  - Web Search                │
                    │  - Browser Automation        │
                    │  - Code Execution            │
                    │  - Document Processing       │
                    └──────────────────────────────┘
```

### Request Flow

1. **User sends message** in Open WebUI: _"Search for Python async best practices"_
2. **Adapter intercepts** the request at `/v1/chat/completions`
3. **MCP client checks** if message requires tool use (keyword detection)
4. **Tool discovery**: Adapter calls obot gateway `/api/tools` to list available tools
5. **Tool selection**: Adapter selects `web_search` tool based on message content
6. **Tool execution**: Adapter calls obot gateway `/api/tools/web_search` with query
7. **Result augmentation**: Adapter appends tool results to original message
8. **Agent Zero processing**: Augmented message sent to Agent Zero for response generation
9. **Response returned** to user via Open WebUI

---

## Prerequisites

### Required Infrastructure

- **Docker** (v24.0+) and Docker Compose (v2.20+)
- **PostgreSQL** 16+ (already part of Carbon Agent Platform)
- **Redis** 7+ (already part of Carbon Agent Platform)
- **At least 1 CPU core** and **1GB RAM** for obot gateway
- **OpenAI API key** or **Anthropic API key** (for obot's LLM features)

### Required Accounts

- **OpenAI API key** — https://platform.openai.com/api-keys
- **Anthropic API key** (optional) — https://console.anthropic.com/settings/keys
- **Domain name** (optional, for production) — e.g., `agents.carbon.dev`

### Existing Carbon Agent Platform

Ensure your Carbon Agent Platform is already deployed and functional:

```bash
cd carbon-agent-platform
docker compose up -d
docker compose ps
```

All services should show `healthy` status.

---

## Step-by-Step Setup

### Step 1: Create `.env.production` Configuration

Add the following to your `.env.production` file:

```bash
# ─── Obot MCP Gateway ───────────────────────────────────────────────────────

# MCP Gateway Configuration
OBOT_PORT=8080
MCP_ENABLED=true
MCP_GATEWAY_URL=http://obot-gateway:8080
MCP_TIMEOUT_SECONDS=30
MCP_MAX_RETRIES=3

# LLM Provider (at least one required)
OPENAI_API_KEY=sk-your-openai-api-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here

# Security (CHANGE IN PRODUCTION)
OBOT_ENCRYPTION_KEY=generate-a-secure-256-bit-key-here

# Database (uses shared PostgreSQL)
POSTGRES_PASSWORD=your-postgres-password
```

**Generate a secure encryption key:**

```bash
# Linux/macOS
openssl rand -base64 32

# Windows PowerShell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

### Step 2: Add obot Service to Docker Compose

Create or update `docker-compose.obot.yml`:

```yaml
services:
  obot-gateway:
    image: ghcr.io/obot-platform/obot:latest
    container_name: carbon-obot-gateway
    ports:
      - "${OBOT_PORT:-8080}:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - obot-data:/data
    environment:
      # LLM Providers
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      
      # Database (shared postgres instance)
      - OBOT_SERVER_DSN=postgres://postgres:${POSTGRES_PASSWORD}@postgres:5432/obot?sslmode=disable
      
      # Security
      - OBOT_ENCRYPTION_KEY=${OBOT_ENCRYPTION_KEY}
      
      # Feature flags
      - OBOT_MCP_ENABLED=true
      - OBOT_MCP_REGISTRY_ENABLED=true
      
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 1G
    networks:
      - default

  # Add MCP environment variables to adapter
  adapter:
    environment:
      - MCP_GATEWAY_URL=${MCP_GATEWAY_URL:-http://obot-gateway:8080}
      - MCP_ENABLED=${MCP_ENABLED:-false}
      - MCP_TIMEOUT_SECONDS=${MCP_TIMEOUT_SECONDS:-30}
      - MCP_MAX_RETRIES=${MCP_MAX_RETRIES:-3}

volumes:
  obot-data:
```

### Step 3: Deploy obot Gateway

```bash
# Start obot gateway alongside existing services
docker compose -f docker-compose.yml -f docker-compose.obot.yml up -d obot-gateway

# Verify deployment
docker compose ps obot-gateway

# Check logs
docker compose logs -f obot-gateway
```

### Step 4: Verify obot Gateway Health

```bash
# Health check endpoint
curl http://localhost:8080/health

# Expected response:
# {"status": "ok", "version": "x.x.x"}
```

### Step 5: Configure MCP Client in Adapter

Update `adapter/app/config.py` (already done in code):

```python
# MCP (Model Context Protocol) — obot integration
mcp_enabled: bool = True  # Change to True to enable
mcp_gateway_url: str = "http://obot-gateway:8080"
mcp_timeout_seconds: float = 30.0
mcp_max_retries: int = 3
```

### Step 6: Enable MCP in Adapter

Set the environment variable:

```bash
export MCP_ENABLED=true
```

Or in `.env.production`:

```bash
MCP_ENABLED=true
```

### Step 7: Restart Adapter Service

```bash
docker compose -f docker-compose.yml -f docker-compose.obot.yml up -d --build adapter
```

### Step 8: Test MCP Integration

```bash
# Check adapter logs for MCP initialization
docker compose logs adapter | grep -i mcp

# Expected: No errors, MCP client initialized (disabled by default until env var set)
```

---

## Configuration Parameters

### obot Gateway Configuration

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `OBOT_PORT` | Port for MCP gateway | `8080` | Yes |
| `OPENAI_API_KEY` | OpenAI API key for LLM features | - | Yes* |
| `ANTHROPIC_API_KEY` | Anthropic API key (alternative) | - | Yes* |
| `OBOT_SERVER_DSN` | PostgreSQL connection string | - | Yes |
| `OBOT_ENCRYPTION_KEY` | Encryption key for secrets | - | Yes |
| `OBOT_MCP_ENABLED` | Enable MCP features | `true` | No |
| `OBOT_MCP_REGISTRY_ENABLED` | Enable tool registry | `true` | No |

*At least one LLM provider key is required.

### Carbon Agent Adapter Configuration

| Parameter | Description | Default | Environment Variable |
|-----------|-------------|---------|---------------------|
| `mcp_enabled` | Enable MCP tool routing | `False` | `MCP_ENABLED` |
| `mcp_gateway_url` | obot gateway URL | `http://obot-gateway:8080` | `MCP_GATEWAY_URL` |
| `mcp_timeout_seconds` | Request timeout | `30.0` | `MCP_TIMEOUT_SECONDS` |
| `mcp_max_retries` | Retry attempts | `3` | `MCP_MAX_RETRIES` |

---

## Network Topology

### Docker Networks

All services run on the same Docker network `carbon_platform_network`:

```bash
docker network inspect carbon_platform_network
```

### Service Communication

```
Open WebUI (3000)
    ↓ HTTP
Adapter (8001)
    ↓ HTTP
    ├─→ obot Gateway (8080) — MCP tool calls
    └─→ Agent Zero (5000) — LLM responses
    ↓
PostgreSQL (5432) — Shared database
    ↓
Redis (6379) — Caching & context
```

### Firewall Rules (Production)

If deploying on a VPS, ensure these ports are open:

| Port | Service | External | Internal |
|------|---------|----------|----------|
| 3000 | Open WebUI | ✅ Yes | ✅ Yes |
| 8000 | Orchestrator | ❌ No | ✅ Yes |
| 8001 | Adapter | ❌ No | ✅ Yes |
| 8080 | obot Gateway | ❌ No | ✅ Yes |
| 5432 | PostgreSQL | ❌ No | ✅ Yes |
| 6379 | Redis | ❌ No | ✅ Yes |

**Only port 3000 should be externally accessible.**

---

## Integration Testing

### Test 1: MCP Gateway Health

```bash
curl -s http://localhost:8080/health | jq
```

Expected output:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### Test 2: MCP Tool Discovery

```bash
curl -s http://localhost:8080/api/tools | jq
```

Expected output (tools may vary):

```json
{
  "tools": [
    {
      "name": "web_search",
      "description": "Search the web",
      "parameters": {
        "query": "string",
        "max_results": "integer"
      }
    }
  ]
}
```

### Test 3: MCP Tool Execution

```bash
curl -X POST http://localhost:8080/api/tools/web_search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python async best practices"}' | jq
```

Expected output:

```json
{
  "success": true,
  "result": ["result1", "result2", "result3"]
}
```

### Test 4: End-to-End Chat with Tools

```bash
# Send a message that should trigger MCP tool use
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "carbon-agent",
    "messages": [
      {"role": "user", "content": "Search for Python async best practices"}
    ],
    "stream": false
  }' | jq
```

Expected: Response should include tool-augmented results.

### Test 5: Graceful Degradation

Disable MCP and verify chat still works:

```bash
# Temporarily disable MCP
export MCP_ENABLED=false
docker compose up -d adapter

# Send normal chat request (should work without tools)
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "carbon-agent",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "stream": false
  }' | jq
```

Expected: Normal chat response without tool augmentation.

---

## Troubleshooting

### Issue 1: obot Gateway Won't Start

**Symptoms:**

```
ERROR: obot-gateway exited with code 1
```

**Diagnosis:**

```bash
docker compose logs obot-gateway
```

**Common causes:**

1. **Missing LLM API key:**
   ```bash
   # Check env vars
   docker compose exec obot-gateway env | grep API_KEY
   ```

2. **Database connection failure:**
   ```bash
   # Test PostgreSQL connection
   docker compose exec postgres pg_isready -U postgres
   ```

3. **Docker socket permission denied:**
   ```bash
   # Fix permissions
   sudo chmod 666 /var/run/docker.sock
   ```

**Solutions:**

```bash
# Verify .env.production has required keys
cat .env.production | grep -E "OPENAI_API_KEY|POSTGRES_PASSWORD"

# Restart obot
docker compose down obot-gateway
docker compose up -d obot-gateway
```

---

### Issue 2: MCP Client Not Connecting

**Symptoms:**

```
WARNING: mcp_health_check_failed error="Connection refused"
```

**Diagnosis:**

```bash
# Test network connectivity
docker compose exec adapter curl -v http://obot-gateway:8080/health
```

**Common causes:**

1. **Wrong gateway URL:**
   ```bash
   # Check adapter env
   docker compose exec adapter env | grep MCP_GATEWAY_URL
   ```

2. **Network isolation:**
   ```bash
   # Verify both services on same network
   docker network inspect carbon_platform_network | grep -A 5 obot-gateway
   docker network inspect carbon_platform_network | grep -A 5 adapter
   ```

**Solutions:**

```bash
# Update .env.production
MCP_GATEWAY_URL=http://obot-gateway:8080

# Restart adapter
docker compose up -d --build adapter
```

---

### Issue 3: Tool Execution Timeout

**Symptoms:**

```
ERROR: mcp_tool_call_timeout tool="web_search" timeout=30.0
```

**Diagnosis:**

```bash
# Check obot gateway logs
docker compose logs obot-gateway | grep -i timeout
```

**Common causes:**

1. **Tool server slow/unavailable**
2. **Network latency**
3. **Insufficient timeout**

**Solutions:**

```bash
# Increase timeout in .env.production
MCP_TIMEOUT_SECONDS=60

# Restart adapter
docker compose up -d adapter
```

---

### Issue 4: No Tools Available

**Symptoms:**

```
INFO: mcp_no_tools_available user_id="user-123"
```

**Diagnosis:**

```bash
# Check if tools are registered
curl http://localhost:8080/api/tools | jq
```

**Common causes:**

1. **MCP servers not deployed**
2. **Registry not enabled**
3. **Access control blocking discovery**

**Solutions:**

```bash
# Enable MCP registry in .env.production
OBOT_MCP_REGISTRY_ENABLED=true

# Deploy MCP servers (see obot docs)
# Restart obot gateway
docker compose down obot-gateway
docker compose up -d obot-gateway
```

---

### Issue 5: Chat Works But No Tool Augmentation

**Symptoms:**

- Chat responses are normal
- No tool results in response

**Diagnosis:**

```bash
# Check adapter logs for MCP activity
docker compose logs adapter | grep -i mcp

# Verify MCP is enabled
docker compose exec adapter env | grep MCP_ENABLED
```

**Common causes:**

1. **MCP_ENABLED=false**
2. **Message doesn't match tool keywords**
3. **Tool selection logic not matching**

**Solutions:**

```bash
# Enable MCP
export MCP_ENABLED=true

# Test with tool-triggering message
# Should contain: "search", "find", "browse", "execute code"
```

---

## Security Considerations

### 1. API Key Management

- **Never commit API keys** to version control
- **Use environment variables** or secret management (HashiCorp Vault, AWS Secrets Manager)
- **Rotate keys** every 90 days

### 2. Network Isolation

- **No external access** to obot gateway (port 8080)
- **Use Docker networks** for service isolation
- **Firewall rules** to restrict access

### 3. Access Control

- **OAuth 2.1** for obot admin access
- **User ID tracking** in tool calls (X-User-ID header)
- **Audit logging** for all tool executions

### 4. Data Privacy

- **No PII in logs** — only user_id, not email/content
- **Encryption at rest** for obot data volume
- **TLS in production** for all external communication

---

## Performance Optimization

### 1. Connection Pooling

MCP client uses connection pooling by default:

```python
limits = httpx.Limits(
    max_connections=10,
    max_keepalive_connections=5
)
```

### 2. Timeout Tuning

```bash
# Low-latency environment
MCP_TIMEOUT_SECONDS=10
MCP_MAX_RETRIES=2

# High-reliability environment
MCP_TIMEOUT_SECONDS=60
MCP_MAX_RETRIES=5
```

### 3. Caching Strategy

Future enhancement: Cache tool results to reduce redundant calls

```python
# Example: Cache search results for 5 minutes
@cache(ttl=300)
async def cached_tool_call(tool_name, params):
    return await mcp.call_tool(tool_name, params)
```

### 4. Resource Limits

```yaml
# docker-compose.obot.yml
deploy:
  resources:
    limits:
      memory: 2G  # Increase for heavy tool usage
      cpus: "2.0"
```

---

## Next Steps

### 1. Deploy MCP Servers

Follow obot documentation to deploy specific MCP servers:

- **Web Search MCP** — https://github.com/obot-platform/mcp-search
- **Browser MCP** — https://github.com/obot-platform/mcp-browser
- **Code Execution MCP** — https://github.com/obot-platform/mcp-code

### 2. Enhance Tool Selection

Current implementation uses keyword matching. Future improvements:

- **LLM-based tool selection** — Use Agent Zero to select best tool
- **Tool chaining** — Execute multiple tools in sequence
- **Parameter extraction** — Use regex/LLM to extract tool params

### 3. Add MCP Metrics

```python
# Track MCP usage in Prometheus metrics
mcp_tool_calls_total = Counter('mcp_tool_calls_total', 'Total MCP tool calls', ['tool_name', 'status'])
mcp_tool_duration = Histogram('mcp_tool_duration_seconds', 'MCP tool execution time', ['tool_name'])
```

### 4. Enable MCP in Production

```bash
# .env.production
MCP_ENABLED=true
MCP_GATEWAY_URL=https://mcp.carbon.dev  # TLS-enabled endpoint
MCP_TIMEOUT_SECONDS=30
MCP_MAX_RETRIES=3
```

---

## References

- **obot Documentation:** https://docs.obot.ai
- **MCP Specification:** https://modelcontextprotocol.io
- **Carbon Agent Platform:** See `SYSTEM_ARCHITECTURE.md`
- **MCP Client Code:** `adapter/app/mcp_client.py`
- **Unit Tests:** `adapter/tests/test_mcp_client.py`

---

**End of Document**
