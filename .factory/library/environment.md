# Environment

Env vars and external dependencies. Service ports live in `.factory/services.yaml`.

## Required Environment Variables (orchestrator)

- `DATABASE_URL` - Postgres DSN (local dev example is in .env.example)
- `REDIS_URL` - Redis URL (local dev example is in .env.example)
- `CLERK_SECRET_KEY` - Clerk backend API key
- `CLERK_PUBLISHABLE_KEY` - Clerk frontend key
- `CLERK_WEBHOOK_SECRET` - Svix webhook secret (Clerk dashboard "Webhooks" section)
- `CLERK_JWT_ISSUER` - Clerk JWKS issuer URL (`https://<tenant>.clerk.accounts.dev`)
- `RAILWAY_API_TOKEN` - Railway API token
- `RAILWAY_PROJECT_ID` - Railway project to provision per-user services in
- `AGENT_DOCKER_IMAGE` - Docker image ref for Agent Zero, pinned by digest
- `CORS_ALLOWED_ORIGINS` - comma-separated (e.g. `https://app.carbonplatform.io,http://localhost:3000`)
- `OPENAI_API_KEY` - upstream LLM (if used)
- `SESSION_IDLE_TIMEOUT_MINUTES` - default 30

## Required Environment Variables (adapter)

- `DATABASE_URL` - same as orchestrator (for api_key -> user lookup)
- `AGENT_API_URL` - fallback; real routing resolves per user
- `AGENT_API_KEY` - fallback for non-user contexts

## Required Environment Variables (open-webui)

- `CLERK_PUBLISHABLE_KEY` - embedded in config.json at container start
- `CLERK_FRONTEND_API_URL` - Clerk frontend API URL
- `ORCHESTRATOR_URL` - http://orchestrator:8000 (or deployed URL)
- `OPENWEBUI_API_KEY` - placeholder template token; replaced runtime with per-user key

## Credentials Policy

- Workers pause and return to orchestrator if required creds missing at validation time.
- Secrets NEVER committed. `.env*` files ignored; only `.env.example` checked in.
- Clerk test tenant credentials + Railway staging token maintained out-of-band by user; pasted on demand.

## Notes

- Python 3.12 runtime for orchestrator + adapter.
- Open WebUI base image: `ghcr.io/open-webui/open-webui` (pin digest before prod).
- Windows dev host: tests invoked via `py -3` or venv `python.exe`; docker-compose requires Docker Desktop.
