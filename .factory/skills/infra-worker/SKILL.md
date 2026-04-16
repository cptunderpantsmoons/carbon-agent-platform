---
name: infra-worker
description: Implements infrastructure features - Dockerfiles, compose, Alembic, deploy.sh, Railway config, digest pinning.
---

# Infra Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for features touching:
- `Dockerfile.production`, `orchestrator/Dockerfile`, `adapter/Dockerfile`, `open-webui/Dockerfile`
- `docker-compose.yml` and compose-level concerns (networking, healthchecks, depends_on)
- Alembic: `orchestrator/alembic.ini`, `orchestrator/alembic/env.py`, `orchestrator/alembic/versions/*`
- `scripts/deploy.sh`, `railway.json`, multi-service Railway configs
- `Makefile` targets

## Required Skills

- `systematic-debugging` (personal) - invoke on any docker build failure or compose health failure.
- `verification-before-completion` (personal) - invoke before claiming done.
- `agent-browser` (personal) - required ONLY for VAL-DEPLOY-012 (deployed smoke test).

## Work Procedure

1. Read feature description, preconditions, expectedBehavior, verificationSteps, and fulfilled assertions.
2. Read the current file(s) you'll modify. For Dockerfiles, inspect all RUN/COPY/USER/HEALTHCHECK lines.
3. Read `.factory/library/architecture.md` and `.factory/library/environment.md`.
4. **Make changes additively** where possible. For Dockerfile fixes: change one issue at a time, build after each, so you know which change broke the build.
5. **Build + smoke test locally:**
   - Dockerfile changes: `docker build -f <file> -t carbon-<svc>:test .` - exit 0 required.
   - Compose changes: `docker compose down -v && docker compose up -d --build` - all services healthy within 60s.
   - Alembic: against a clean DB, `alembic upgrade head` then `alembic downgrade base` both succeed; `\dt` output as expected at each step.
   - deploy.sh: run with `--env staging </dev/null` twice in a row, exit 0 both.
6. For assertions claiming grep-style invariants (no `/` continuations, no unpinned FROMs): run the actual grep commands from the assertion's evidence and include output in handoff.
7. For staging-deploy features: ASK orchestrator before spending Railway quota. Only run when feature explicitly authorizes.
8. Revert compose to clean state when done (`docker compose down -v` if you brought it up for verification).
9. Commit with message referencing feature id.

## Dockerfile Rules (MANDATORY)

- Line continuations: `\` ONLY. No trailing ` /`.
- Base images: pinned by `@sha256:<64hex>`. Resolve via `docker buildx imagetools inspect <image>:<tag>` then use the digest.
- Include `curl` in any image whose healthcheck uses curl.
- `USER appuser` (UID 1000) as the final USER directive in every app image. Create group+user in the image; chown app files.
- Keep HEALTHCHECK commands self-contained (no external network dependency).

## Alembic Setup Rules

- `orchestrator/alembic.ini` with `sqlalchemy.url = %(DATABASE_URL)s` (or env-driven).
- `orchestrator/alembic/env.py` imports `from orchestrator.app.models import Base` (or `from app.models` depending on import path) and sets `target_metadata = Base.metadata`.
- First revision: `alembic revision --autogenerate -m "initial schema"`. Review the generated `upgrade()` + `downgrade()` - ensure both are non-trivial and reversible.
- Add `make migrate` = `docker compose exec orchestrator alembic upgrade head` to Makefile.

## Example Handoff

```json
{
  "salientSummary": "Fixed Dockerfile.production line continuations (replaced `/` with `\\` on 6 lines), fixed CMD import path by setting WORKDIR=/app/orchestrator and using `app.main:app`. All three target stages build. Adapter import check passes. Open WebUI image also built cleanly with clerk-integration.js present at /app/static/.",
  "whatWasImplemented": "Dockerfile.production: changed 6 trailing `/` to `\\` in apt-get block and HEALTHCHECK lines; added WORKDIR /app/orchestrator before CMD. adapter/Dockerfile: verified standalone builds. open-webui/Dockerfile: confirmed COPY clerk-integration.js → /app/static/ stays.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "docker build --target orchestrator -t carbon-orch:test -f Dockerfile.production .", "exitCode": 0, "observation": "built in 57s, size 312MB"},
      {"command": "docker build --target adapter -t carbon-adapt:test -f Dockerfile.production .", "exitCode": 0, "observation": "built in 48s, size 298MB"},
      {"command": "docker build -t carbon-webui:test -f open-webui/Dockerfile ./open-webui", "exitCode": 0, "observation": "built in 22s"},
      {"command": "docker run --rm carbon-adapt:test python -c 'import app.main'", "exitCode": 0, "observation": "no output, clean import"},
      {"command": "docker run --rm carbon-webui:test ls /app/static/clerk-integration.js", "exitCode": 0, "observation": "/app/static/clerk-integration.js"},
      {"command": "grep -nE ' /$' Dockerfile.production", "exitCode": 1, "observation": "no matches (good)"}
    ],
    "interactiveChecks": []
  },
  "tests": {"added": []},
  "discoveredIssues": [
    {"severity": "low", "description": "Dockerfile.production lacks USER directive; will be addressed in m5-non-root-user-directives feature.", "suggestedFix": null}
  ]
}
```

## When to Return to Orchestrator

- Railway token or project ID not set when a staging-deploy feature is up.
- docker-compose fails to reach healthy within 120s and cause is infrastructural (image pull, DNS) not Dockerfile content.
- Alembic autogenerate produces a migration that would drop data when run against an existing production DB - flag before proceeding.
- Multi-service Railway config decision (one multi-stage vs per-service) requires architectural direction.
