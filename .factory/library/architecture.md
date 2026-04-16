# Carbon Agent Platform - Architecture

Per-user Railway-provisioned Agent Zero instances behind an OpenAI-compatible HTTP surface, with Clerk identity and Open WebUI as the chat client.

## Components

- **Open WebUI** (port 3000) - browser chat client. Loads Clerk JS, receives per-user `api_key` from orchestrator, uses it on chat calls.
- **Orchestrator** (port 8000, FastAPI) - Clerk identity bridge + platform plane. Routers:
  - `/webhooks/clerk` - user lifecycle (Svix-signed)
  - `/api/v1/auth/*` - get-api-key for browser after Clerk sign-in
  - `/user/me/*` - user self-service (rotate key, session state)
  - `/admin/*` - admin UI + API
  - `/v1/*` - middleware resolves Clerk JWT, injects per-user `api_key`, proxies to adapter
- **Adapter** (port 8001, FastAPI) - OpenAI-compatible surface (`/v1/chat/completions`, `/v1/models`). Resolves user's Railway service URL by api_key, forwards to Agent Zero instance.
- **Postgres** (5432) - users, audit_log, sessions.
- **Redis** (6379) - session manager cache, rate limit store.
- **Railway API** - external; orchestrator `RailwayClient` creates/deletes per-user service + volume + deployment.
- **Clerk** - external; identity + JWT issuer + Svix-signed webhooks.

## Data Flows

### New user onboarding
Browser -> Clerk sign-up -> Clerk fires `user.created` Svix webhook -> orchestrator verifies signature, creates `users` row with `sk-<48hex>` api_key, calls `SessionManager.ensure_user_service` -> `RailwayClient` creates volume + service + deployment -> persists `railway_service_id` + `volume_id`. Browser (post-sign-in) -> `GET /api/v1/auth/get-api-key` with Clerk JWT -> orchestrator verifies RS256 sig, returns api_key -> stored in sessionStorage.

### Chat
Browser -> `POST /v1/chat/completions` with `Authorization: Bearer sk-*` -> orchestrator `ApiKeyInjectionMiddleware` resolves user, records activity -> proxies to adapter -> adapter resolves user's `railway_service_id` -> Railway service URL -> forwards to Agent Zero -> streams response back.

### Idle sweep
Background task `_cleanup_idle_sessions` (interval 60s) scans `_active_sessions`, calls `spin_down_idle_user` for users past `session_idle_timeout_minutes`. Delete_service + delete_volume; null IDs; audit.

### User deletion
Clerk `user.deleted` webhook (Svix-verified) -> `_handle_user_deleted` -> `SessionManager.spin_down_user_service` -> Railway deletes -> DB status=SUSPENDED + ids null + audit row.

## Invariants

- **Authorization everywhere**: every /v1/*, /user/me/*, /admin/*, /api/v1/auth/* endpoint verifies either a platform api_key (sk-*) via `verify_user_api_key` or a Clerk RS256 JWT via `verify_clerk_jwt`. NEVER `verify_signature=False`.
- **api_key never leaves server except**: `GET /api/v1/auth/get-api-key` (to authenticated Clerk user only) and `POST /user/me/api-key/rotate` response body. It is NEVER in `UserResponse` for `GET /user/me`.
- **Webhook signatures**: always verified via Svix library before any DB write. Unsigned or replayed -> 401, no side effects.
- **Per-user isolation**: each user has own `railway_service_id`, own volume, own api_key. Adapter routes to user's service URL, never a shared endpoint.
- **Lock discipline**: `SessionManager._get_lock` + `_remove_lock` must not delete a lock while waiters exist. `ensure_user_service` serializes per user_id.
- **Idempotent webhooks**: user.created delivered twice -> one service provisioned. user.deleted delivered twice -> one spin-down.
- **CORS**: `allow_origins` read from `CORS_ALLOWED_ORIGINS` env (comma-separated); never hardcoded `*` with credentials.
- **Rate limits**: per-user on /v1/* + /user/me/*; per-IP on /webhooks/clerk.
- **Non-root containers**: every application image has a `USER` directive with UID >= 1000.
- **Digest-pinned base images**: all FROM lines and compose `image:` entries pinned by `@sha256:<64-hex>`.

## External Dependencies

- Clerk (api.clerk.com) - JWKS, Backend API for user management, Svix webhook delivery.
- Railway (backboard.railway.app GraphQL) - service/volume/deployment provisioning.
- Agent Zero Docker image - spawned per user on Railway.

## Deployment Topology

- Local: docker-compose spins postgres + redis + 3 app services.
- Staging/Prod: Railway hosts orchestrator + adapter + open-webui as separate services (3 Dockerfiles or one multi-stage with target). Per-user Agent Zero services created dynamically by orchestrator via Railway GraphQL.

## Module Boundaries

- `orchestrator/app/` owns identity, provisioning, admin, middleware.
- `adapter/app/` owns OpenAI-compatible surface + per-user Railway URL routing.
- `open-webui/` owns browser UX + Clerk integration JS + config templating.
- `scripts/deploy.sh` owns Railway deploy orchestration.
- `alembic/` owns schema migrations.
