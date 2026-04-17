# Carbon Agent Platform - Production Launch Specification

## Overview

**Mission:** Ship Carbon Agent Platform to production-ready state. Core differentiator: per-user Railway provisioning with chat, session persistence, and admin view.

**Working Directory:** `C:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform`

**Last audited:** 2026-04-17

**Actual state:** ~18/34 features DONE in code, 6 PARTIAL, 10 TODO/WRONG/BLOCKED. 0/91 validator assertions formally run. Prior tracker values were stale — this document reflects the code-level audit.

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

## Milestones — Current Status

Legend: DONE = implemented in code (not yet validator-run), PARTIAL = code exists but has gaps, TODO = not started, WRONG = implemented but does not meet spec, BLOCKED = waits on earlier work.

### M1: Security Hardening
| # | Feature | Status | Evidence |
|---|---------|--------|----------|
| 1 | m1-jwt-signature-verification | DONE | `orchestrator/app/clerk_auth.py` uses RS256 via JWKS; commit `f549d41` |
| 2 | m1-remove-api-key-exposure | DONE | `schemas.py` `UserResponse` has no `api_key`; rotation returns key only via `ApiKeyRotateResponse`; commit `f1ffaad` |
| 3 | m1-svix-webhook-verification | DONE | `clerk.py` uses `svix.webhooks.Webhook.verify()` |
| 4 | m1-cors-env-restriction | DONE | `main.py` reads `settings.cors_allowed_origins`; no hardcoded `*` |
| 5 | m1-rate-limiting | DONE | `slowapi` on `/user/*`, `/api/v1/auth/*`, `/webhooks/clerk` |

### M2: Per-User Railway Provisioning
| # | Feature | Status | Evidence / Gap |
|---|---------|--------|----------------|
| 6 | m2-wire-user-created-webhook | PARTIAL | `clerk.py::_handle_user_created` creates DB user but does NOT call `session_manager.ensure_user_service`. Auto-provisioning missing. |
| 7 | m2-wire-user-deleted-webhook | DONE | `_handle_user_deleted` calls `spin_down_user_service` |
| 8 | m2-fix-lock-race-condition | PARTIAL | `SessionManager` locks per user, but `_remove_lock` only called on spin-down; lock dict grows unbounded |
| 9 | m2-verify-idle-sweep | DONE | `_cleanup_idle_sessions` runs every 60s |
| 10 | m2-api-key-injection-outbound | PARTIAL | Middleware sets `request.state.api_key` but nothing rewrites outbound `Authorization` header |
| 11 | m2-adapter-per-user-routing | DONE | `adapter/app/main.py::_get_agent_base_url` formats Railway URL per user |

### M3: Open WebUI Integration
| # | Feature | Status | Evidence / Gap |
|---|---------|--------|----------------|
| 12 | m3-openwebui-config-substitution | TODO | `open-webui/config.json` still has literal `{{USER_API_KEY}}`, `{{CLERK_PUBLISHABLE_KEY}}`, `{{CLERK_FRONTEND_API_URL}}` |
| 13 | m3-inject-clerk-integration-script | PARTIAL | `clerk-integration.js` copied to `/app/static/` but NOT injected into Open WebUI `index.html` |
| 14 | m3-signin-fetch-and-store-key | DONE (blocked by #13) | `clerk-integration.js` implements token extraction + `/api/v1/auth/get-api-key` call |
| 15 | m3-chat-flow-send-receive | BLOCKED | Depends on #12/#13 |
| 16 | m3-session-persist-and-edge-cases | BLOCKED | Open WebUI native; cannot verify without #12/#13 |
| 17 | m3-user-isolation-and-admin-nav | TODO | No admin-nav injection for admin Clerk users in Open WebUI |

### M4: Admin View
| # | Feature | Status | Evidence / Gap |
|---|---------|--------|----------------|
| 18 | m4-admin-jwt-role-gating | WRONG | `admin.py::verify_admin_key` uses `X-Admin-Key` HMAC, not Clerk JWT + role claim |
| 19 | m4-admin-users-endpoint | DONE | `/admin/users` CRUD |
| 20 | m4-admin-sessions-endpoint | DONE | `/admin/sessions` |
| 21 | m4-admin-metrics-endpoint | DONE | `/admin/metrics` |
| 22 | m4-admin-ui-page | DONE (wrong auth) | `admin_ui.py` serves `/dashboard`; uses sessionStorage X-Admin-Key |
| 23 | m4-admin-user-status-action | DONE | PATCH `/admin/users/{id}` with `status` |

### M5: Deployment Ready
| # | Feature | Status | Evidence / Gap |
|---|---------|--------|----------------|
| 24 | m5-fix-dockerfiles | DONE | All Dockerfiles use `\` continuations + curl + HEALTHCHECK |
| 25 | m5-non-root-user-directives | PARTIAL | Orchestrator + adapter run as `appuser`; `open-webui/Dockerfile` ends with `USER root` |
| 26 | m5-alembic-migrations | DONE | `alembic/versions/e2eec18c30fa_initial_schema.py` with upgrade+downgrade; Dockerfile runs `alembic upgrade head` on start |
| 27 | m5-digest-pin-base-images | PARTIAL | Only `Dockerfile.production` pins by SHA; plain `orchestrator/Dockerfile`, `adapter/Dockerfile`, `open-webui/Dockerfile` are unpinned |
| 28 | m5-compose-stack-healthy | DONE | Healthchecks + `depends_on: service_healthy` on all services |
| 29 | m5-startup-config-validation | TODO | `main.py` lifespan does not validate required env vars |
| 30 | m5-deploy-script-idempotent | DONE | `scripts/deploy.sh` has `ensure_service` guard |
| 31 | m5-staging-deploy-smoke-test | TODO | No smoke test script/action |

### M6: Cross-Area Integration
| # | Feature | Status | Gap |
|---|---------|--------|-----|
| 32 | m6-onboarding-and-webhook-strict | BLOCKED | Needs M2 #6 auto-provisioning |
| 33 | m6-session-lifecycle-flows | BLOCKED | Needs M2 + M3 |
| 34 | m6-admin-visibility-isolation-routing | BLOCKED | Needs M4 JWT role gating |
| 35 | m6-resilience-and-multi-tab | BLOCKED | Needs M3 end-to-end |

---

## Aggregate Scoreboard (code-level, 2026-04-17)

| Milestone | DONE | PARTIAL | TODO / WRONG / BLOCKED |
|-----------|------|---------|------------------------|
| M1 Security | 5 | 0 | 0 |
| M2 Provisioning | 3 | 3 | 0 |
| M3 Open WebUI | 1 | 1 | 4 |
| M4 Admin | 5 | 0 | 1 (wrong) |
| M5 Deploy | 4 | 2 | 2 |
| M6 Cross-area | 0 | 0 | 4 (blocked) |
| **TOTAL (34)** | **18** | **6** | **10** |

Validator-run assertions: **0 / 91 passed** (`validation-state.json` untouched).

---

## Open Tasks (priority order)

### P0 — Unblock end-to-end flow

1. **Auto-provision on user.created** (`m2-wire-user-created-webhook`)
   - In `orchestrator/app/clerk.py::_handle_user_created`, after creating the DB user, call `session_manager.ensure_user_service(db, user.id)` (or enqueue for async provisioning).
   - Keep idempotent on webhook retries.
   - Fulfills VAL-PROV-001/002/004.

2. **Outbound API-key injection** (`m2-api-key-injection-outbound`)
   - `api_key_injection.py` currently stashes `request.state.api_key`. Either:
     - (a) rewrite scope headers so the forwarded `Authorization` carries the user's API key, or
     - (b) route adapter requests through a reverse-proxy handler that calls the adapter with the new header.
   - Cache invalidation on rotate is already wired in `users.py::rotate_my_api_key`.

3. **Open WebUI config substitution** (`m3-openwebui-config-substitution`)
   - Replace `{{USER_API_KEY}}`, `{{CLERK_PUBLISHABLE_KEY}}`, `{{CLERK_FRONTEND_API_URL}}` in `open-webui/config.json` at container start (entrypoint `envsubst`), or drop the placeholders and let `clerk-integration.js` inject at runtime.

4. **Inject clerk-integration.js into Open WebUI** (`m3-inject-clerk-integration-script`)
   - Add a post-copy step in `open-webui/Dockerfile` (or entrypoint) that patches `index.html` with `<script src="/static/clerk-integration.js"></script>`.
   - Verify via agent-browser that the script loads and extracts the Clerk session token.

5. **Admin JWT role gating** (`m4-admin-jwt-role-gating`)
   - Replace `X-Admin-Key` HMAC on `/admin/*` and `/dashboard` with Clerk JWT dependency (`verify_clerk_jwt` from `clerk_auth.py`) that requires `public_metadata.role == "admin"` (or equivalent claim).
   - Keep a narrow bootstrap key only for initial setup / CI.
   - Fulfills VAL-ADMIN-001/002/012.

### P1 — Security / deploy hardening

6. **Open WebUI non-root** (`m5-non-root-user-directives`)
   - End `open-webui/Dockerfile` with a non-root `USER`. Fix ownership of copied files.

7. **Digest-pin all base images** (`m5-digest-pin-base-images`)
   - Pin `python:3.12-slim@sha256:...` in `orchestrator/Dockerfile` and `adapter/Dockerfile`.
   - Pin `ghcr.io/open-webui/open-webui:main@sha256:...`.

8. **Startup config validation** (`m5-startup-config-validation`)
   - In `main.py::lifespan`, validate required env vars for the runtime mode. Fail-fast with a single structured error listing all missing keys.
   - Fulfills VAL-CROSS-008.

9. **Lock cleanup** (`m2-fix-lock-race-condition` polish)
   - Call `_remove_lock` in `ensure_user_service` finally clause, or switch to `WeakValueDictionary`.

### P2 — Validation & smoke

10. **Staging deploy smoke test** (`m5-staging-deploy-smoke-test`)
    - Script that runs `deploy.sh`, waits for health, curls `/health` on orchestrator + adapter, and exercises one Clerk-authenticated chat call. Gated by explicit user go-ahead.

11. **Run validators** on M1 + M4 + M5 features already coded; mark passed assertions in `validation-state.json` to reconcile tracker with reality.

12. **M3 end-to-end agent-browser flow** after #3 and #4: sign-in → key fetch → chat → logout → re-sign-in.

13. **M6 cross-area flows** after M1–M5 green.

---

## Security Requirements (NON-NEGOTIABLE)

1. **JWT verification MUST be enabled** - Never `verify_signature=False` ✓ (M1 done)
2. **Never expose api_key** - GET /user/me must NOT return api_key ✓ (M1 done)
3. **Use Svix library** for webhook verification - not custom HMAC ✓ (M1 done)
4. **CORS from env** - Never hardcode `allow_origins=["*"]` ✓ (M1 done)
5. **Rate limit** `/v1/*` and `/webhooks/clerk` ✓ (M1 done)

---

## Key Files

| Path | Purpose | State |
|------|---------|-------|
| `orchestrator/app/main.py` | FastAPI app, CORS, rate limiting | wired |
| `orchestrator/app/clerk.py` | Webhook handlers, user lifecycle | needs provisioning call |
| `orchestrator/app/session_manager.py` | Per-user Railway provisioning | wired |
| `orchestrator/app/auth_routes.py` | Auth endpoints | wired |
| `orchestrator/app/api_key_injection.py` | Middleware for key injection | validates; outbound header rewrite missing |
| `orchestrator/app/admin.py` | Admin API endpoints | auth model wrong (X-Admin-Key vs Clerk JWT role) |
| `orchestrator/app/admin_ui.py` | Admin dashboard HTML | same auth problem |
| `adapter/app/main.py` | Adapter FastAPI app | wired |
| `adapter/app/agent_client.py` | Per-user routing to Railway | wired |
| `open-webui/clerk-integration.js` | Frontend Clerk integration | written, not loaded |
| `open-webui/config.json` | Open WebUI config | placeholders unsubstituted |
| `open-webui/Dockerfile` | Image build | `USER root` violates policy |
| `scripts/deploy.sh` | Railway deploy | idempotent |

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

- **Unit/Integration:** `pytest` from `orchestrator/` or `adapter/` directory
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

91 assertions across 6 areas (see `../Project Plan and Agents tasks/validation-contract.md`):

- Security: 25 (VAL-SEC-001..025)
- Provisioning: 13 (VAL-PROV-001..013)
- UI: 15 (VAL-UI-001..015)
- Admin: 12 (VAL-ADMIN-001..012)
- Deployment: 14 (VAL-DEPLOY-001..014)
- Cross-Area: 12 (VAL-CROSS-001..012)

All 91 currently `pending` in `validation-state.json` — validator sweeps have not been run yet even for completed M1 features.

---

## Critical Blockers (audit 2026-04-17)

| # | Issue | File | Status |
|---|-------|------|--------|
| B1 | JWT `verify_signature=False` | auth_routes.py, api_key_injection.py | FIXED |
| B2 | `api_key` in UserResponse | schemas.py | FIXED |
| B3 | CORS `allow_origins=["*"]` + credentials | main.py | FIXED |
| B4 | Webhook uses custom HMAC, not Svix | clerk.py | FIXED |
| B5 | No rate limiting | everywhere | FIXED |
| B6 | Auto-provisioning missing on user.created | clerk.py | **OPEN (P0)** |
| B7 | User delete doesn't spin down | clerk.py | FIXED |
| B8 | clerk-integration.js not loaded | open-webui/Dockerfile | **OPEN (P0)** |
| B9 | config.json placeholders unsubstituted | open-webui/config.json | **OPEN (P0)** |
| B10 | Dockerfile.production bugs | Dockerfile.production | FIXED |
| B11 | Admin UI not implemented | admin_ui.py | FIXED |
| B12 | Admin auth uses X-Admin-Key not Clerk JWT role | admin.py | **OPEN (P0)** |
| B13 | Outbound Authorization header not rewritten | api_key_injection.py | **OPEN (P0)** |
| B14 | Open WebUI Dockerfile ends USER root | open-webui/Dockerfile | **OPEN (P1)** |
| B15 | Unpinned base images in plain Dockerfiles | orchestrator, adapter, open-webui | **OPEN (P1)** |
| B16 | No startup config validation | main.py | **OPEN (P1)** |

---

## Resume Point

Next actionable feature: **m2-wire-user-created-webhook** (P0 #1 above). Worker session `8a9a2eae-161f-4a33-9620-9226d9776484` for `m1-remove-api-key-exposure` can be marked COMPLETE since code already satisfies it — close it out and move on.
