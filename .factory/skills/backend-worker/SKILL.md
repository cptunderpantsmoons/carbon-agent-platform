---
name: backend-worker
description: Implements Python/FastAPI backend features for orchestrator and adapter; SQLAlchemy, Clerk, Railway, tests via pytest.
---

# Backend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for features in `orchestrator/app/` and `adapter/app/` Python code, including:
- FastAPI routes, middleware, dependencies
- SQLAlchemy models, schemas, DB access
- Clerk JWT + webhook verification
- Railway client calls via `orchestrator/app/railway.py`
- Session manager + lock discipline
- Integration tests under `tests/integration/`

## Required Skills

- `test-driven-development` (personal) - invoke at the start of every feature. Red/green discipline is mandatory.
- `systematic-debugging` (personal) - invoke when a test fails unexpectedly or an import error appears.
- `verification-before-completion` (personal) - invoke before claiming the feature done.

## Work Procedure

1. Read the feature's `description`, `preconditions`, `expectedBehavior`, `verificationSteps`, and the claimed `fulfills` assertion IDs from `features.json`. Read each fulfill-ed assertion in `validation-contract.md` to understand what behavior you must make true.
2. Read the relevant source files listed in preconditions. If the feature references files under `orchestrator/app/` or `adapter/app/`, read them fully before editing.
3. Read `.factory/library/architecture.md` for the invariants you must preserve.
4. Check existing tests: find test files that cover the area you're modifying.
5. **Write failing tests first (red).** Each `fulfills` assertion should map to at least one test case. Tests go in the corresponding `tests/` dir. Use `respx` for Railway mocks, `httpx.AsyncClient` for FastAPI test clients, `pytest-asyncio` for async.
6. Run the failing tests: `python -m pytest <file>::<test> -v` - confirm they fail for the expected reason.
7. Implement the minimum change that makes the tests pass. Follow existing conventions (type hints, structlog, Pydantic v2).
8. Run the targeted tests - confirm green.
9. Run the full test module: `python -m pytest orchestrator/tests/<module>.py -v` (or adapter) - no regressions.
10. Manual verification per feature:
    - For API endpoints: start orchestrator locally (`.factory/services.yaml` commands) and `curl` each endpoint listed in `expectedBehavior` with the correct headers. Record exit codes and bodies.
    - For middleware changes: send a request that exercises the middleware and inspect orchestrator logs for the expected log line.
    - For webhook changes: craft a Svix-signed request with `svix.Webhook.sign()` and POST it; verify response + DB state.
11. Run lint: `python -m pyflakes orchestrator/app adapter/app` - fix any new issues in your diff.
12. Ensure no test runners, compose stacks, or bg processes remain running.
13. Commit with message `feat(<area>): <feature-id> - <one-line summary>` referencing the feature id. Push to master.

## Security & Invariants Checklist (MANDATORY)

Before claiming a feature done, verify:
- No new `verify_signature=False` anywhere.
- No new `api_key` field in any Pydantic response model used for `GET /user/me`.
- No hardcoded CORS `*`; no hardcoded secrets.
- Webhook handlers use `svix` library (if touching webhook code).
- Every new endpoint uses appropriate auth dependency (`verify_user_api_key` or `verify_clerk_jwt`).
- Structured logs have no secret values (inspect your new log lines).

## Example Handoff

```json
{
  "salientSummary": "Enabled Clerk RS256 JWT signature verification in auth_routes.py and api_key_injection.py by reusing verify_clerk_jwt. Added 8 new negative-path tests in test_auth_routes.py. Ran pytest orchestrator/tests/test_auth_routes.py -v (12 passed, 0 failed) and manually curl'd /api/v1/auth/get-api-key with tampered, expired, nbf-future, and unknown-kid tokens (all 401).",
  "whatWasImplemented": "Refactored orchestrator/app/auth_routes.py to call verify_clerk_jwt() from clerk_auth.py instead of jwt.decode(..., verify_signature=False). Updated orchestrator/app/api_key_injection.py ApiKeyInjectionMiddleware.dispatch() to call verify_clerk_jwt on the bearer token and reject invalid signatures with 401 before any DB lookup. Added 8 tests in orchestrator/tests/test_auth_routes.py covering: unsigned JWT, tampered signature, expired exp, nbf future, unknown kid, missing Authorization header, suspended user, valid admin path.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "python -m pytest orchestrator/tests/test_auth_routes.py -v", "exitCode": 0, "observation": "12 passed in 0.9s"},
      {"command": "python -m pytest orchestrator/tests/test_api_key_injection.py -v", "exitCode": 0, "observation": "7 passed in 0.4s"},
      {"command": "grep -rn 'verify_signature.*False' orchestrator/app/", "exitCode": 1, "observation": "no matches (good)"},
      {"command": "python -m pyflakes orchestrator/app", "exitCode": 0, "observation": "clean"}
    ],
    "interactiveChecks": [
      {"action": "curl -i -H 'Authorization: Bearer <tampered-jwt>' http://localhost:8000/api/v1/auth/get-api-key", "observed": "HTTP/1.1 401; body.detail='Invalid token'"},
      {"action": "curl -i http://localhost:8000/api/v1/auth/get-api-key (no header)", "observed": "HTTP/1.1 401; body.detail='Missing or invalid Authorization header'"}
    ]
  },
  "tests": {
    "added": [
      {"file": "orchestrator/tests/test_auth_routes.py", "cases": [
        {"name": "test_rejects_unsigned_jwt", "verifies": "VAL-SEC-001"},
        {"name": "test_rejects_tampered_signature", "verifies": "VAL-SEC-002"},
        {"name": "test_accepts_valid_clerk_jwt", "verifies": "VAL-SEC-003"},
        {"name": "test_rejects_expired_jwt", "verifies": "VAL-SEC-004"},
        {"name": "test_rejects_missing_header", "verifies": "VAL-SEC-005"},
        {"name": "test_rejects_nbf_future", "verifies": "VAL-SEC-022"},
        {"name": "test_rejects_unknown_kid", "verifies": "VAL-SEC-023"},
        {"name": "test_rejects_suspended_user", "verifies": "VAL-SEC-021"}
      ]}
    ]
  },
  "discoveredIssues": [
    {"severity": "medium", "description": "orchestrator/app/clerk_auth.py verify_clerk_jwt fallback path uses asyncio.get_event_loop().run_until_complete() which will error if loop already running. Not exercised in this feature but should be fixed.", "suggestedFix": "Refactor to await JWKS fetch directly or cache synchronously on startup."}
  ]
}
```

## When to Return to Orchestrator

- Clerk or Railway credentials needed for validation and not set in env.
- Ambiguity between two assertion requirements that seem to conflict.
- Existing bug in a pre-condition module that blocks this feature.
- Database schema change required but Alembic migrations not yet set up (cross feature dependency).
