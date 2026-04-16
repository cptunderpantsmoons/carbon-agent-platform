# Carbon Agent Platform - Production Launch Plan

## Progress Overview

| Milestone | Features | Completed | In Progress |
|-----------|----------|-----------|-------------|
| M1: Security Hardening | 5 | 1 | 1 |
| M2: Per-User Provisioning | 6 | 0 | 0 |
| M3: Open WebUI Integration | 6 | 0 | 0 |
| M4: Admin View | 6 | 0 | 0 |
| M5: Deployment Ready | 8 | 0 | 0 |
| M6: Cross-Area Integration | 4 | 0 | 0 |
| **Total** | **35** | **1** | **1** |

---

## M1: Security Hardening

### M1.1: m1-jwt-signature-verification (DONE)
**Commit:** f549d41

Replace `verify_signature=False` with real Clerk RS256 JWT verification.

**Files:** `auth_routes.py`, `api_key_injection.py`, `clerk_auth.py`

---

### M1.2: m1-remove-api-key-exposure (IN PROGRESS)
**Next action:** Resume session 8a9a2eae-161f-4a33-9620-9226d9776484

**What needs to be done:**
1. Remove `api_key` field from `UserResponse` in `schemas.py`
2. Ensure `GET /user/me` and `PATCH /user/me` do NOT return `api_key`
3. Keep `POST /user/me/api-key/rotate` returning `new_api_key`
4. Verify rotation invalidates old key
5. Update tests in `test_users.py`

**Verification:**
```bash
pytest orchestrator/tests/test_users.py orchestrator/tests/test_auth_routes.py -v
grep 'api_key' orchestrator/app/schemas.py  # api_key must not appear in UserResponse
```

**Fulfills:** VAL-SEC-006, VAL-SEC-007, VAL-SEC-008, VAL-SEC-024, VAL-SEC-025

---

### M1.3: m1-svix-webhook-verification
**What needs to be done:**
1. Add `svix` to `requirements.txt`
2. Replace custom HMAC `_verify_webhook_signature` with Svix library
3. Verify Svix standard headers (svix-id, svix-timestamp, svix-signature)
4. Reject replay (timestamp outside 5-min tolerance)
5. Enforce 1 MiB max body size
6. Return 400 on malformed JSON, 401 on invalid signature

**Files:** `orchestrator/app/clerk.py`, `orchestrator/requirements.txt`

**Verification:**
```bash
pytest orchestrator/tests/test_clerk.py -v
grep svix orchestrator/requirements.txt
```

**Fulfills:** VAL-SEC-009, VAL-SEC-010, VAL-SEC-011, VAL-SEC-012, VAL-SEC-013

---

### M1.4: m1-cors-env-restriction
**What needs to be done:**
1. Replace hardcoded `allow_origins=["*"]` in `main.py`
2. Read from `CORS_ALLOWED_ORIGINS` env var (comma-separated)
3. Default to safe localhost dev list when empty
4. Keep `allow_credentials=True` only when explicit origins listed
5. Update `docker-compose.yml` and `.env.example`

**Files:** `orchestrator/app/main.py`, `docker-compose.yml`, `.env.example`

**Verification:**
```bash
pytest orchestrator/tests/ -k cors -v
grep 'allow_origins' orchestrator/app/main.py | grep -v CORS_ALLOWED_ORIGINS  # should be empty
```

**Fulfills:** VAL-SEC-014, VAL-SEC-015

---

### M1.5: m1-rate-limiting
**What needs to be done:**
1. Add `slowapi` to `requirements.txt`
2. Apply rate limits: 60/min `/v1/*`, 60/min `/user/me/*`, 30/min `/webhooks/clerk`
3. Key per-user for `/v1/*` and `/user/me/*`
4. Key per-IP for `/webhooks/clerk`
5. Add 429 handler returning `Retry-After`
6. Make limits configurable via env

**Files:** `orchestrator/app/main.py`, `orchestrator/requirements.txt`

**Verification:**
```bash
pytest orchestrator/tests/ -k rate_limit -v
grep slowapi orchestrator/requirements.txt
```

**Fulfills:** VAL-SEC-016, VAL-SEC-017, VAL-SEC-018

---

## M2: Per-User Railway Provisioning

### M2.1: m2-wire-user-created-webhook
**Preconditions:** M1 complete, `session_manager.ensure_user_service` exists

**What needs to be done:**
1. Modify `_handle_user_created` to call `SessionManager.ensure_user_service`
2. Handle Railway API errors with compensation (delete partial volume/service)
3. Set `status='pending'` on failure, write `audit user.provision_failed`
4. Ensure idempotency (duplicate webhook returns "User already exists")
5. Wrap in user-level lock

**Files:** `orchestrator/app/clerk.py`, `orchestrator/app/session_manager.py`

**Verification:**
```bash
pytest orchestrator/tests/test_clerk.py orchestrator/tests/test_session_manager.py -v
```

**Fulfills:** VAL-PROV-001, VAL-PROV-002, VAL-PROV-004

---

### M2.2: m2-wire-user-deleted-webhook
**Preconditions:** M2.1 complete

**What needs to be done:**
1. Modify `_handle_user_deleted` to call `spin_down_user_service`
2. Call `RailwayClient.delete_service` and `delete_volume`
3. Set `users.status=SUSPENDED`, null `railway_service_id` + `volume_id`
4. Handle idempotent redelivery ("User already deleted")
5. Handle partial failure (volume delete fails -> surface error + audit)

**Files:** `orchestrator/app/clerk.py`, `orchestrator/app/session_manager.py`

**Verification:**
```bash
pytest orchestrator/tests/test_clerk.py::test_handle_user_deleted -v
pytest orchestrator/tests/test_session_manager.py -v
```

**Fulfills:** VAL-PROV-003, VAL-PROV-011, VAL-PROV-012

---

### M2.3: m2-fix-lock-race-condition
**What needs to be done:**
1. Fix race in `session_manager._remove_lock`
2. Don't delete lock while other coroutines await it
3. Use waiter count or only remove when unlocked and no pending acquisitions
4. Add stress test: 100 iterations of 2 parallel `ensure_user_service` calls

**Files:** `orchestrator/app/session_manager.py`

**Verification:**
```bash
pytest orchestrator/tests/test_session_manager.py::test_ensure_user_service_race -v
# Run stress test 10 times
```

**Fulfills:** VAL-PROV-005

---

### M2.4: m2-verify-idle-sweep
**What needs to be done:**
1. Verify `_cleanup_idle_sessions` spins down users past `idle_timeout`
2. Verify `record_activity` invoked on every `/v1/*` request
3. Test: idle user spun down, non-idle untouched

**Files:** `orchestrator/app/session_manager.py`, `orchestrator/app/api_key_injection.py`

**Verification:**
```bash
pytest orchestrator/tests/test_session_manager.py -k cleanup -v
# Manual: set idle_timeout=1min, wait 90s, confirm spin down
```

**Fulfills:** VAL-PROV-006, VAL-PROV-009

---

### M2.5: m2-api-key-injection-outbound
**What needs to be done:**
1. Modify `ApiKeyInjectionMiddleware` to inject `Authorization` header
2. Forward `Authorization: Bearer <user.api_key>` on requests to adapter
3. Call `invalidate_api_key_cache(clerk_user_id)` on rotation
4. Unknown Clerk user -> 401/404, no adapter call

**Files:** `orchestrator/app/api_key_injection.py`, `orchestrator/app/users.py`

**Verification:**
```bash
pytest orchestrator/tests/test_api_key_injection.py -v
# Manual: curl /v1/chat/completions, inspect adapter log for bearer header
```

**Fulfills:** VAL-PROV-007, VAL-PROV-008, VAL-PROV-013

---

### M2.6: m2-adapter-per-user-routing
**What needs to be done:**
1. Resolve user's Railway service URL from `users.railway_service_id`
2. Proxy `/v1/chat/completions` to that URL
3. Fall back to `settings.agent_api_url` when no `railway_service_id`
4. Two users must see requests land on two different hosts

**Files:** `adapter/app/main.py`, `adapter/app/agent_client.py`

**Verification:**
```bash
pytest adapter/tests/ -v
# Manual: two curl with different api_keys, check adapter logs
```

**Fulfills:** VAL-PROV-010

---

## M3: Open WebUI Integration

### M3.1: m3-openwebui-config-substitution
**What needs to be done:**
1. Add entrypoint script to Dockerfile that substitutes placeholders
2. Replace `{{CLERK_PUBLISHABLE_KEY}}`, `{{CLERK_FRONTEND_API_URL}}` from env
3. `{{USER_API_KEY}}` handled by clerk-integration.js (not substituted)
4. Add HEALTHCHECK
5. Pin image base by digest

**Files:** `open-webui/Dockerfile`, `open-webui/config.json`

**Verification:**
```bash
docker compose up -d open-webui
docker exec open-webui cat /app/backend/data/config.json | grep '{{CLERK'  # should be empty
curl -sf http://localhost:3000/health
```

**Fulfills:** VAL-UI-001, VAL-UI-002

---

### M3.2: m3-inject-clerk-integration-script
**Preconditions:** M3.1 complete, `clerk-integration.js` exists

**What needs to be done:**
1. Inject `<script src='/static/clerk-integration.js'>` into served HTML
2. Approaches: override index.html, sed-patch bundle, or custom HTML pattern
3. Verify script loads and Clerk SDK initializes

**Files:** `open-webui/Dockerfile`, `open-webui/clerk-integration.js`

**Verification:**
```bash
curl -s http://localhost:3000/ | grep clerk-integration.js
# Manual: agent-browser navigate, confirm sign-in rendered
```

**Fulfills:** VAL-UI-003, VAL-UI-015

---

### M3.3: m3-signin-fetch-and-store-key
**Preconditions:** M3.2 complete

**What needs to be done:**
1. After Clerk sign-in, call `GET /api/v1/auth/get-api-key`
2. Store `api_key` in `sessionStorage` under `openwebui_api_key`
3. Fire `clerk-integration-ready` CustomEvent with `hasApiKey:true`
4. On returning visit with valid Clerk cookie, refetch without re-auth

**Files:** `open-webui/clerk-integration.js`

**Verification:**
```bash
# Manual: agent-browser sign in, inspect sessionStorage
```

**Fulfills:** VAL-UI-004, VAL-UI-014

---

### M3.4: m3-chat-flow-send-receive
**Preconditions:** M3.3, M2.5, M2.6 complete

**What needs to be done:**
1. Configure Open WebUI `openai.api_base_url` to orchestrator
2. Clerk-integration.js fetch hook injects `Authorization: Bearer <api_key>`
3. Verify: POST /v1/chat/completions -> SSE -> assistant bubble renders

**Files:** `open-webui/config.json`, `open-webui/clerk-integration.js`

**Verification:**
```bash
# Manual: agent-browser send 'ping respond pong', confirm 'pong' in response
```

**Fulfills:** VAL-UI-005, VAL-UI-006

---

### M3.5: m3-session-persist-and-edge-cases
**Preconditions:** M3.4 complete

**What needs to be done:**
1. Hard reload shows prior chat history
2. Sign-out clears api_key + `/v1/*` returns 401
3. Token refresh interval refetches api_key
4. Multi-tab shares session
5. Orchestrator outage -> 3-attempt retry -> error banner + recovery

**Verification:**
```bash
# Manual: agent-browser scripted flow for each case
```

**Fulfills:** VAL-UI-007, VAL-UI-008, VAL-UI-011, VAL-UI-012, VAL-UI-013

---

### M3.6: m3-user-isolation-and-admin-nav
**Preconditions:** M3.4 complete, two seeded Clerk test users

**What needs to be done:**
1. User A and B see disjoint chat history
2. Admin role: Clerk JS reads role claim, exposes `[data-role='admin']`
3. Non-admin lacks selector

**Files:** `open-webui/clerk-integration.js`

**Verification:**
```bash
# Manual: agent-browser two-context isolation test
```

**Fulfills:** VAL-UI-009, VAL-UI-010

---

## M4: Admin View

### M4.1: m4-admin-jwt-role-gating
**Preconditions:** M1.1 complete

**What needs to be done:**
1. Refactor `admin.py` to use Clerk JWT with `role=admin` claim
2. Add `require_admin_jwt` dependency
3. All admin endpoints adopt this dependency
4. Expired/invalid/missing JWT -> 401
5. Valid JWT without admin role -> 403

**Files:** `orchestrator/app/admin.py`

**Verification:**
```bash
pytest orchestrator/tests/test_admin.py -v
# Manual: curl with three JWT states
```

**Fulfills:** VAL-ADMIN-001, VAL-ADMIN-002, VAL-ADMIN-012

---

### M4.2: m4-admin-users-endpoint
**Preconditions:** M4.1 complete

**What needs to be done:**
1. Extend `GET /admin/users` to return: id, email, status, created_at, service_status
2. `service_status` derived from `SessionManager.get_service_status`

**Files:** `orchestrator/app/admin.py`

**Verification:**
```bash
pytest orchestrator/tests/test_admin.py::test_list_users -v
curl /admin/users | jq 'all(.[]; has("service_status"))'
```

**Fulfills:** VAL-ADMIN-003

---

### M4.3: m4-admin-sessions-endpoint
**What needs to be done:**
1. Add `GET /admin/sessions` returning: user_id, email, last_activity, idle_seconds, railway_service_id, service_state
2. State mapping: active/idle/stopped

**Files:** `orchestrator/app/admin.py`

**Verification:**
```bash
pytest orchestrator/tests/test_admin.py::test_list_sessions -v
```

**Fulfills:** VAL-ADMIN-004, VAL-ADMIN-010

---

### M4.4: m4-admin-metrics-endpoint
**What needs to be done:**
1. Add `GET /admin/metrics` returning: total_users, active_services, spun_down_services, requests_24h

**Files:** `orchestrator/app/admin.py`

**Verification:**
```bash
pytest orchestrator/tests/test_admin.py::test_metrics -v
```

**Fulfills:** VAL-ADMIN-005

---

### M4.5: m4-admin-ui-page
**Preconditions:** M4.2, M4.3, M4.4 complete

**What needs to be done:**
1. Create minimal single-page admin UI at `GET /admin`
2. Vanilla HTML + Clerk JS + fetch to admin API
3. Show sign-in when unauthenticated
4. Show "Admin access required" for non-admin (403)
5. Refresh button re-fetches data

**Files:** `orchestrator/app/admin.py`, `orchestrator/app/templates/`

**Verification:**
```bash
# Manual: agent-browser /admin flows
```

**Fulfills:** VAL-ADMIN-006, VAL-ADMIN-007, VAL-ADMIN-009, VAL-ADMIN-011

---

### M4.6: m4-admin-user-status-action
**Preconditions:** M4.5 complete

**What needs to be done:**
1. Add `POST /admin/users/{id}/status` accepting `{status: 'active'|'suspended'}`
2. Update `users.status`, write audit log
3. Admin UI renders Suspend/Activate button

**Files:** `orchestrator/app/admin.py`

**Verification:**
```bash
pytest orchestrator/tests/test_admin.py::test_update_status -v
```

**Fulfills:** VAL-ADMIN-008

---

## M5: Deployment Ready

### M5.1: m5-fix-dockerfiles
**What needs to be done:**
1. Fix `Dockerfile.production` line continuations (`\` not `/`)
2. Fix CMD module path to match package layout
3. Verify orchestrator, adapter, open-webui images build cleanly
4. Standalone adapter import check: `python -c 'import app.main'`

**Files:** `Dockerfile.production`, `orchestrator/Dockerfile`, `adapter/Dockerfile`, `open-webui/Dockerfile`

**Verification:**
```bash
docker build --target orchestrator -t carbon-orch:test -f Dockerfile.production .
docker build --target adapter -t carbon-adapt:test -f Dockerfile.production .
docker build -t carbon-webui:test -f open-webui/Dockerfile ./open-webui
docker run --rm carbon-adapt:test python -c 'import app.main'
```

**Fulfills:** VAL-DEPLOY-001, VAL-DEPLOY-002, VAL-DEPLOY-003

---

### M5.2: m5-non-root-user-directives
**Preconditions:** M5.1 complete

**What needs to be done:**
1. Add `USER appuser` (UID 1000) to all Dockerfiles
2. Create appuser group+user
3. Ensure app files owned by appuser

**Files:** All Dockerfiles

**Verification:**
```bash
grep -nE '^USER ' Dockerfile.production open-webui/Dockerfile adapter/Dockerfile
docker inspect --format '{{.Config.User}}' $(docker compose ps -q orchestrator)
```

**Fulfills:** VAL-DEPLOY-005

---

### M5.3: m5-alembic-migrations
**What needs to be done:**
1. Set up Alembic for orchestrator
2. Create `alembic.ini`, `alembic/env.py`
3. Create initial revision covering all current tables
4. `make migrate` = `alembic upgrade head`
5. Downgrade must be reversible

**Files:** `orchestrator/alembic.ini`, `orchestrator/alembic/`

**Verification:**
```bash
DATABASE_URL=test docker compose exec orchestrator alembic upgrade head
DATABASE_URL=test docker compose exec orchestrator alembic downgrade base
```

**Fulfills:** VAL-DEPLOY-006, VAL-DEPLOY-007

---

### M5.4: m5-digest-pin-base-images
**What needs to be done:**
1. Pin every FROM line with `@sha256:<64hex>`
2. Pin every docker-compose `image:` entry

**Files:** All Dockerfiles, `docker-compose.yml`

**Verification:**
```bash
grep -nE '^FROM ' *Dockerfile* **/Dockerfile | grep -v '@sha256:'
grep -nE '^\s*image:' docker-compose.yml | grep -v '@sha256:'
```

**Fulfills:** VAL-DEPLOY-011

---

### M5.5: m5-compose-stack-healthy
**Preconditions:** M5.1, M5.2, M5.3 complete

**What needs to be done:**
1. Verify `docker-compose.yml` brings full stack to healthy within 60s
2. Health endpoints all return 200
3. Fix compose service definitions, depends_on, environment

**Verification:**
```bash
docker compose down -v && docker compose up -d --build
# Wait 60s, then:
curl -sf http://localhost:8000/health
curl -sf http://localhost:8001/health
curl -sf http://localhost:3000/health
```

**Fulfills:** VAL-DEPLOY-004, VAL-DEPLOY-008

---

### M5.6: m5-startup-config-validation
**What needs to be done:**
1. Require CLERK_SECRET_KEY, CLERK_WEBHOOK_SECRET, CLERK_JWT_ISSUER, RAILWAY_API_TOKEN, DATABASE_URL
2. On missing, log ERROR/CRITICAL and exit non-zero or return 503 on /health
3. Never 200 a webhook with empty secret

**Files:** `orchestrator/app/config.py`, `orchestrator/app/main.py`

**Verification:**
```bash
# Manual: unset one var, check logs + health
```

**Fulfills:** VAL-CROSS-008

---

### M5.7: m5-deploy-script-idempotent
**Preconditions:** M5.1 complete

**What needs to be done:**
1. Rewrite `scripts/deploy.sh` for non-interactive CI use
2. Authenticate via `RAILWAY_TOKEN` env var
3. Detect existing services, skip create (idempotent)
4. Support `--env staging|production` flag

**Files:** `scripts/deploy.sh`, `railway.json`

**Verification:**
```bash
bash scripts/deploy.sh --env staging </dev/null  # exit 0
# Re-run, exit 0, no "service already exists" errors
```

**Fulfills:** VAL-DEPLOY-013, VAL-DEPLOY-014

---

### M5.8: m5-staging-deploy-smoke-test
**Preconditions:** M5.7, M5.5, M3.4 complete + Railway staging available

**What needs to be done:**
1. Execute `scripts/deploy.sh` to Railway staging
2. Verify `/health` returns 200 within 5 min
3. Verify CORS env-driven (unlisted origin rejected)
4. Run agent-browser E2E smoke test

**Verification:**
```bash
RAILWAY_TOKEN=$T bash scripts/deploy.sh --env staging
# Manual: agent-browser smoke test
```

**Fulfills:** VAL-DEPLOY-009, VAL-DEPLOY-010, VAL-DEPLOY-012

---

## M6: Cross-Area Integration

### M6.1: m6-onboarding-and-webhook-strict
**Preconditions:** All of M1-M5 complete

**What needs to be done:**
1. Full new-user onboarding within 60s: sign-up -> webhook -> provision -> first chat
2. Verify unsigned webhook returns 401 with 0 DB writes
3. Returning user reuses existing service_id

**Verification:**
```bash
pytest tests/integration/test_onboarding.py -v
# Manual: agent-browser timed flow
```

**Fulfills:** VAL-CROSS-001, VAL-CROSS-002, VAL-CROSS-011

---

### M6.2: m6-session-lifecycle-flows
**Preconditions:** All of M1-M5 complete

**What needs to be done:**
1. Idle sweep + resume re-warm
2. Clerk user deletion propagates (DB suspended + `/v1/*` 401/403)
3. API key rotation invalidates old + authorizes new

**Verification:**
```bash
pytest tests/integration/test_lifecycle.py -v
```

**Fulfills:** VAL-CROSS-003, VAL-CROSS-004, VAL-CROSS-005

---

### M6.3: m6-admin-visibility-isolation-routing
**Preconditions:** All of M1-M5 complete, M4.5 complete

**What needs to be done:**
1. Admin view reflects reality within 5s
2. Two users fully isolated (distinct service_ids, disjoint chats)
3. Per-user routing confirmed (A -> S_A, B -> S_B)

**Verification:**
```bash
pytest tests/integration/test_isolation_and_admin.py -v
```

**Fulfills:** VAL-CROSS-006, VAL-CROSS-007, VAL-CROSS-012

---

### M6.4: m6-resilience-and-multi-tab
**Preconditions:** M1.5 complete, M3.5 complete

**What needs to be done:**
1. Rate limit burst recovery
2. Multi-tab session persistence

**Verification:**
```bash
pytest tests/integration/test_resilience.py -v
```

**Fulfills:** VAL-CROSS-009, VAL-CROSS-010

---

## Credentials Request Template

When a feature requires credentials, return:

```
PAUSED: Feature requires credentials
Feature: <feature-id>
Missing:
- [ ] CLERK_SECRET_KEY
- [ ] CLERK_PUBLISHABLE_KEY
- [ ] CLERK_WEBHOOK_SECRET
- [ ] CLERK_JWT_ISSUER
- [ ] RAILWAY_API_TOKEN
- [ ] RAILWAY_PROJECT_ID
- [ ] OPENAI_API_KEY
- [ ] DATABASE_URL
- [ ] REDIS_URL
- [ ] CORS_ALLOWED_ORIGINS
- [ ] Test Clerk users (admin + standard)
- [ ] Railway staging project + RAILWAY_STAGING_TOKEN
```

---

## Handoff Template

Every worker returns:

```json
{
  "salientSummary": "1-4 sentence narrative",
  "whatWasImplemented": "specific files/functions",
  "whatWasLeftUndone": "list or empty string",
  "verification": {
    "commandsRun": [{"cmd": "...", "exit": 0, "obs": "..."}],
    "interactiveChecks": [{"step": "...", "outcome": "..."}]
  },
  "testsAdded": [{"file": "...", "cases": ["..."]}],
  "discoveredIssues": [{"issue": "...", "file": "..."}]
}
```
