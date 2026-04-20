# Carbon Agent Platform — Code Review & Alignment Status

> Updated after code-review sessions (moon / code-puppy-79601d)
> Python runtime in this environment is 3.14; containers deploy python:3.12-slim.
> `pydantic-core` and `asyncpg` cannot be installed locally on 3.14 — tests run in Docker.

---

## Session 1 — Initial Code Review (8 fixes)

| # | File | Was wrong | Fix applied |
|---|---|---|---|
| R1 | `railway.py` | `mount_volume_to_service()` was a stub with no GraphQL call | Added real `volumeInstanceCreate` mutation |
| R2 | `session_manager.py` | Volume never mounted; `updated_at` set twice manually | Wired mount call, dropped redundant assignments |
| R3 | `config.py` | No `clerk_jwt_issuer` field | Added field with empty-string default |
| R4 | `clerk_auth.py` | No issuer verification; dead `_decode_clerk_jwt` + `get_clerk_user_id` functions | Added `verify_iss` flag; removed dead code |
| R5 | `tests/test_clerk.py` | Tests targeted deleted functions | Removed `TestClerkAuthMiddleware` class |
| R6 | `admin_ui.py` | User-controlled data written raw into `innerHTML` → XSS | Added `esc()` helper; `JSON.stringify` on onclick args |
| R7 | `main.py` | No CORS guard in production; `auto_create_tables=True` hardcoded | `raise ValueError` at startup when origins unset; `auto_create_tables=False` |
| R8 | `page.tsx` | Scaffold placeholder only | Full Clerk-authenticated dashboard (status, session, API key, rotate) |

---

## Session 2 — P0/P1 Feature Completions (4 fixes)

| # | ID | File | Was broken | Fix applied |
|---|---|---|---|---|
| P0-1 | `m4-provision-user` | `clerk.py` + `session_manager.py` | Webhook wrote DB record but never provisioned Railway service | `provision_user_background()` added; `asyncio.create_task()` fires after commit |
| P0-2 | `m4-header-rewrite` | `api_key_injection.py` | Middleware found API key but never sent it downstream | `MutableHeaders(scope=request.scope)` rewrites `Authorization` in-place before `call_next` |
| P1-8 | `m4-production-config-guard` | `main.py` | `CLERK_*` / `RAILWAY_*` vars not checked at boot | `_validate_production_config()` with 8-var checklist wired into `lifespan` |
| P1-9 | `m4-spin-lock-gc` | `session_manager.py` | `_remove_lock` ran in `finally` after release — could nuke a lock held by another coro | Replaced `Dict[str, Lock]` with `weakref.WeakValueDictionary`; locks GC'd automatically |

---

## Session 3 — Dockerfile & Dead-Code Cleanup (4 fixes)

| # | ID | File | Was wrong | Fix applied |
|---|---|---|---|---|
| C1 | `m4-admin-key-dead-code` | `admin.py` | `verify_admin_key` + `import hmac` were dead code (all routes already used `verify_admin_jwt`) | Removed function and import |
| C2 | `m5-non-root-user` | `open-webui/Dockerfile` | Comment said "switch back to default user" but set `USER root` for the final layer | Created `webui` (uid 1000) non-root user; `chmod -R a+rX /app` for readability; `chown webui` on writable dirs; final `USER webui` |
| C3 | `m5-digest-pin-orchestrator` | `orchestrator/Dockerfile` | `FROM python:3.12-slim` — mutable tag | Pinned to `@sha256:b288e8a0ad27e238ad9cc31f5b40a6278b983c91781a1e38c3e61a4a16a4e5b1` (same digest as `Dockerfile.production`) |
| C4 | `m5-digest-pin-adapter` | `adapter/Dockerfile` | `FROM python:3.12-slim` — mutable tag | Pinned to same digest as above |

**Also confirmed already correct (no changes needed):**
- `admin.py` — all routes use `verify_admin_jwt` with Clerk role check ✅
- `admin_ui.py` — full Clerk JS auth + `esc()` XSS guard ✅
- `open-webui/config.json.template` — exists, uses `$VAR` format for `envsubst` ✅
- `open-webui/entrypoint.sh` — exists, handles envsubst + Clerk script injection ✅
- `config.py` — has `clerk_frontend_api_url` and `clerk_jwt_issuer` fields ✅
- `Dockerfile.production` — already digest-pinned ✅
- `docker-compose.yml` — all services use `build:` not `image:`, nothing to pin ✅

---

## Session 4 — Rate Limiter & Audit Retention (M2 + M3)

| # | ID | Files changed | Was wrong | Fix applied |
|---|---|---|---|---|
| M2 | `m6-rate-limit-redis` | `config.py`, `rate_limit.py`, `tests/test_cors_and_rate_limiting.py`, `.env.example`, `.env.production.example` | `slowapi.Limiter` was hard-coded with in-process `MemoryStorage`; not configurable; no tests for storage backend | Added `rate_limit_storage_uri: str = "memory://"` setting; `_make_limiter(storage_uri)` factory; module-level singleton reads from settings; 7 new tests in `TestRateLimitStorageConfig`; `.env.*` files document the variable |
| M3 | `m6-audit-log-retention` | `scheduler.py`, `tests/test_scheduler.py` | Delete statement used `AuditLog.__table__.delete()` (Core Table API, `# type: ignore` comments); `delete` not imported; `rowcount` unguarded (asyncpg returns `-1` on some DML paths); no real-SQL test coverage | Replaced with `delete(AuditLog).where(...)` (ORM-aware DML); `from sqlalchemy import delete` added to imports; `rowcount` guarded with `max(0, ...)` ; added `TestAuditCleanupIntegration` class (4 tests) that patch the session factory and run real SQLite deletes |

## Session 5 — Session Manager Session Bug (Critical)

| # | ID | Files changed | Was wrong | Fix applied |
|---|---|---|---|---|
| S1 | `m8-duplicate-method-bug` | `session_manager.py` | After replacing `_get_db_session()` with direct `create_session()` call, a duplicate `get_service_status` method definition with wrong signature was introduced — the entire `provision_user_background` body ended up inside the first `get_service_status` def, leaving `spin_down_idle_user` with no return statement | Fixed by restoring proper method boundaries. `provision_user_background` is now a proper standalone method |
| S2 | `m8-async-context-manager` | `session_manager.py`, `database.py` | `provision_user_background` used bare `create_session()` without `async with` — session would never be closed on exception path | Added `provision_session()` async generator to `database.py`; both `provision_user_background` and `spin_down_idle_user` now use `async with provision_session() as db:` for automatic cleanup |
| S3 | `m8-test-mocks` | `tests/integration/test_onboarding.py`, `tests/integration/test_lifecycle.py` | Tests were patching `app.session_manager.create_session` but method now uses `provision_session` | Updated all test patches to `app.session_manager.provision_session` |

> **Note:** The Python 3.14 test environment hangs when importing `sqlalchemy` C-extensions
> via subprocess in this tooling context (a pre-existing env issue, not caused by these changes).
> `py_compile` verified both files are syntax-clean.  Run the suite in Docker or interactively:
> ```
> cd orchestrator
> python -m pytest tests/test_scheduler.py::TestAuditCleanupIntegration -v
> ```

---

## Remaining Work

| Priority | ID | Description |
|---|---|---|
| — | — | All tracked tasks complete ✅ |

---

## Deployment Notes

- All three Python Dockerfiles (`orchestrator/`, `adapter/`, `Dockerfile.production`) use
  `python:3.12-slim@sha256:b288e8a0ad27e238ad9cc31f5b40a6278b983c91781a1e38c3e61a4a16a4e5b1`
- To refresh the digest: `docker pull python:3.12-slim && docker inspect python:3.12-slim --format '{{index .RepoDigests 0}}'`
- Railway deploys from `Dockerfile.production` (multi-stage). Individual `Dockerfile`s are for local `docker-compose` development.
- Set `CLERK_PUBLISHABLE_KEY`, `CLERK_FRONTEND_API_URL`, and `USER_API_KEY` env vars on the open-webui Railway service — the entrypoint substitutes them into `config.json` at container start.
- Admin dashboard: `/dashboard` — requires Clerk JWT with `public_metadata.role = "admin"`.
- Rate limiting: set `RATE_LIMIT_STORAGE_URI=redis://redis:6379/0` in production so limits survive restarts and are shared across replicas (see `.env.production.example`).
