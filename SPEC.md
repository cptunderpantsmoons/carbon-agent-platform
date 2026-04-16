# Carbon Agent Platform - Production Launch Specification

## Overview

**Mission:** Ship Carbon Agent Platform to production-ready state. Core differentiator: per-user Railway provisioning with chat, session persistence, and admin view.

**Working Directory:** `C:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform`

**Status:** 1/34 features completed. M1-jwt-signature-verification done. M1-remove-api-key-exposure in progress.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Clerk Auth                               │
│              (JWT verification, Webhooks)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Orchestrator (:8000)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ Auth Routes │  │ Session Mgr  │  │     Admin API           │  │
│  │ /user/me    │  │ (per-user    │  │  /admin/users           │  │
│  │ /v1/*       │  │  Railway)    │  │  /admin/sessions        │  │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────────┐
        │ Railway  │    │ Adapter  │    │  PostgreSQL  │
        │ API      │    │ (:8001)  │    │  (port 5432) │
        └──────────┘    └──────────┘    └──────────────┘
              │               │
              │               ▼
              │        ┌──────────────────┐
              │        │ Per-user Agent  │
              │        │ Zero services   │
              │        │ (Railway)       │
              │        └──────────────────┘
              │
┌──────────────┴──────────────────────────────────────────────────┐
│                        Open WebUI (:3000)                         │
│               Clerk JS + clerk-integration.js                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Infrastructure

### Ports (NEVER USE ELSEWHERE)
| Service | Port |
|---------|------|
| Open WebUI | 3000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Orchestrator | 8000 |
| Adapter | 8001 |

### External Services
- **Clerk** - Auth provider (test tenant, user provides CLERK_* keys)
- **Railway** - Per-user service provisioning (staging project only)
- **Redis/Postgres** - Local via docker-compose

---

## Milestones

### M1: Security Hardening
| # | Feature | Status |
|---|---------|--------|
| 1 | m1-jwt-signature-verification | **DONE** |
| 2 | m1-remove-api-key-exposure | IN PROGRESS |
| 3 | m1-svix-webhook-verification | pending |
| 4 | m1-cors-env-restriction | pending |
| 5 | m1-rate-limiting | pending |

### M2: Per-User Railway Provisioning
| # | Feature | Status |
|---|---------|--------|
| 6 | m2-wire-user-created-webhook | pending |
| 7 | m2-wire-user-deleted-webhook | pending |
| 8 | m2-fix-lock-race-condition | pending |
| 9 | m2-verify-idle-sweep | pending |
| 10 | m2-api-key-injection-outbound | pending |
| 11 | m2-adapter-per-user-routing | pending |

### M3: Open WebUI Integration
| # | Feature | Status |
|---|---------|--------|
| 12 | m3-openwebui-config-substitution | pending |
| 13 | m3-inject-clerk-integration-script | pending |
| 14 | m3-signin-fetch-and-store-key | pending |
| 15 | m3-chat-flow-send-receive | pending |
| 16 | m3-session-persist-and-edge-cases | pending |
| 17 | m3-user-isolation-and-admin-nav | pending |

### M4: Admin View
| # | Feature | Status |
|---|---------|--------|
| 18 | m4-admin-jwt-role-gating | pending |
| 19 | m4-admin-users-endpoint | pending |
| 20 | m4-admin-sessions-endpoint | pending |
| 21 | m4-admin-metrics-endpoint | pending |
| 22 | m4-admin-ui-page | pending |
| 23 | m4-admin-user-status-action | pending |

### M5: Deployment Ready
| # | Feature | Status |
|---|---------|--------|
| 24 | m5-fix-dockerfiles | pending |
| 25 | m5-non-root-user-directives | pending |
| 26 | m5-alembic-migrations | pending |
| 27 | m5-digest-pin-base-images | pending |
| 28 | m5-compose-stack-healthy | pending |
| 29 | m5-startup-config-validation | pending |
| 30 | m5-deploy-script-idempotent | pending |
| 31 | m5-staging-deploy-smoke-test | pending |

### M6: Cross-Area Integration
| # | Feature | Status |
|---|---------|--------|
| 32 | m6-onboarding-and-webhook-strict | pending |
| 33 | m6-session-lifecycle-flows | pending |
| 34 | m6-admin-visibility-isolation-routing | pending |
| 35 | m6-resilience-and-multi-tab | pending |

---

## Security Requirements (NON-NEGOTIABLE)

1. **JWT verification MUST be enabled** - Never `verify_signature=False`
2. **Never expose api_key** - GET /user/me must NOT return api_key
3. **Use Svix library** for webhook verification - not custom HMAC
4. **CORS from env** - Never hardcode `allow_origins=["*"]`
5. **Rate limit** `/v1/*` and `/webhooks/clerk`

---

## Key Files

| Path | Purpose |
|------|---------|
| `orchestrator/app/main.py` | FastAPI app, CORS, rate limiting |
| `orchestrator/app/clerk.py` | Webhook handlers, user lifecycle |
| `orchestrator/app/session_manager.py` | Per-user Railway provisioning |
| `orchestrator/app/auth_routes.py` | Auth endpoints |
| `orchestrator/app/api_key_injection.py` | Middleware for key injection |
| `orchestrator/app/admin.py` | Admin API endpoints |
| `adapter/app/main.py` | Adapter FastAPI app |
| `adapter/app/agent_client.py` | Per-user routing to Railway |
| `open-webui/clerk-integration.js` | Frontend Clerk integration |

---

## Required Environment Variables

When a worker needs these, pause and request from user:
- `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `CLERK_WEBHOOK_SECRET`, `CLERK_JWT_ISSUER`
- `RAILWAY_API_TOKEN`, `RAILWAY_PROJECT_ID`
- `OPENAI_API_KEY`
- `DATABASE_URL`, `REDIS_URL`
- `CORS_ALLOWED_ORIGINS`

---

## Testing

- **Unit/Integration:** `pytest` from orchestrator/ or adapter/ directory
- **E2E:** agent-browser against local docker-compose
- **Smoke:** agent-browser against Railway staging
- **No mocks for** Clerk, Railway, DB - use real services when creds available

---

## Commit Policy

- Direct push to master authorized
- No force push, no rebase of pushed commits
- Commit messages must reference feature ID
- Never commit `.env` files or secrets

---

## Validation Contract

91 assertions across 6 areas:
- Security: 25 (VAL-SEC-001..025)
- Provisioning: 13 (VAL-PROV-001..013)
- UI: 15 (VAL-UI-001..015)
- Admin: 12 (VAL-ADMIN-001..012)
- Deployment: 14 (VAL-DEPLOY-001..014)
- Cross-Area: 12 (VAL-CROSS-001..012)

---

## Critical Blockers (Found in Baseline)

| # | Issue | File |
|---|-------|------|
| B1 | JWT `verify_signature=False` | auth_routes.py:44, api_key_injection.py:86 |
| B2 | `api_key` in UserResponse | schemas.py:18 |
| B3 | CORS `allow_origins=["*"]` + credentials | main.py:66 |
| B4 | Webhook uses custom HMAC, not Svix | clerk.py:20-43 |
| B5 | No rate limiting | everywhere |
| B6 | Auto-provisioning missing on user.created | clerk.py |
| B7 | User delete doesn't spin down | clerk.py |
| B8 | clerk-integration.js not loaded | open-webui/Dockerfile |
| B9 | config.json placeholders unsubstituted | open-webui/config.json |
| B10 | Dockerfile.production bugs | / vs \ + import path |
| B11 | Admin UI not implemented | missing |

---

## Next Feature to Resume

**m1-remove-api-key-exposure** (paused, session 8a9a2eae-161f-4a33-9620-9226d9776484)

Description: Remove api_key from UserResponse. Ensure GET /user/me does NOT return api_key. POST /user/me/api-key/rotate returns new_api_key. Rotation invalidates old key.
