# User Testing

Validation surface + tools + concurrency for this mission.

## Validation Surface

Three surfaces:

1. **HTTP API (curl)** - orchestrator :8000, adapter :8001. Use for VAL-SEC-*, VAL-PROV-*, VAL-ADMIN-001..005/012, VAL-DEPLOY-008/010, VAL-CROSS-004/005/008/009/011/012 backend checks.
2. **Browser (agent-browser)** - Open WebUI :3000 and admin UI at orchestrator :8000/admin. Use for all VAL-UI-*, VAL-ADMIN-006..011, VAL-CROSS-001/002/003/006/007/010 UI signals.
3. **Shell (docker/compose/grep/alembic)** - container inspection, Dockerfile lint, migration runs. Use for VAL-DEPLOY-001..007/011/013/014.

## Required Testing Skills/Tools

- `agent-browser` - MANDATORY for any browser-surfaced assertion. Validators must invoke it via Skill tool.
- `curl` - HTTP verification.
- `docker` + `docker-compose` - local stack.
- `alembic` - migration checks.
- `pytest` - unit/integration test runs.
- `jq` - JSON assertion helpers.

## Validation Concurrency

Windows 10 dev host. Check memory + cores before finalizing. Conservative defaults:

- **HTTP API validators**: max 5 concurrent (lightweight curl; orchestrator + adapter each ~200MB).
- **Browser validators (agent-browser vs Open WebUI)**: max 3 concurrent. Each browser session ~300-500MB; webui + adapter + orchestrator stack ~800MB baseline. Keep headroom.
- **Shell validators**: max 5 concurrent (build-only validators can be parallelized, but docker build single-tracks on the Docker daemon; batch them 2-wide).

If memory tight on this host, drop browser validators to 2.

## Setup Notes

- Workers must start services via `.factory/services.yaml` (defines compose-based start/stop/healthcheck).
- Clerk test tenant required for end-to-end assertions. Workers pause + request creds if unset.
- Railway staging project required for VAL-DEPLOY-009/012/013. Workers pause if `RAILWAY_TOKEN` unset.
- Rate-limit assertions (VAL-SEC-016..018, VAL-CROSS-009) need short test limits; workers should configure `RATE_LIMIT_*` env vars at 5 req/min during validation runs.

## Known Constraints

- Windows line endings: scripts must use LF; commit with `.gitattributes` enforcing.
- PowerShell does not support `&&`; use `;` or split commands.
- `rg`/`wget`/`ffmpeg` not installed on host.
