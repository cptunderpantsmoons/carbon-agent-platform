---
name: frontend-worker
description: Implements browser-facing features for Open WebUI integration and the admin UI; vanilla JS + Clerk browser SDK; verified via agent-browser.
---

# Frontend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for features touching:
- `open-webui/clerk-integration.js` and companion static assets
- Any HTML/CSS/vanilla JS served directly by Open WebUI or the orchestrator at `/admin`
- Browser-side auth flows, sessionStorage handling, fetch interception
- Admin dashboard UI (Clerk sign-in + tables + buttons)

## Required Skills

- `agent-browser` (personal) - MANDATORY for verifying every browser flow. Use it to navigate, click, fill, assert selectors, capture network, and screenshot.
- `test-driven-development` (personal) - where automated tests are feasible (e.g., DOM-level tests via Playwright or manual scripts), follow red/green.
- `verification-before-completion` (personal) - invoke before claiming feature done.

## Work Procedure

1. Read feature description, `fulfills` IDs, and each fulfilled assertion in `validation-contract.md`. Note the required evidence (screenshots, console-errors, network captures, DOM assertions).
2. Read `open-webui/clerk-integration.js` and `open-webui/config.json` as authoritative reference for existing behavior.
3. Read `.factory/library/architecture.md` and `.factory/library/user-testing.md` for surface + tooling expectations.
4. For Open WebUI features:
   - Bring up the stack: `docker compose up -d postgres redis orchestrator adapter open-webui`.
   - Wait for `curl -sf http://localhost:3000/health` to return 200.
5. For admin UI features:
   - Bring up orchestrator + deps. Admin UI served at `http://localhost:8000/admin`.
6. **Plan your change:**
   - If editing `clerk-integration.js`: preserve existing fetch/XHR interceptors; add new logic additively. Never remove token refresh or event dispatches.
   - If creating admin UI: keep it vanilla (no new build step). Inline JS in a single HTML file is acceptable for MVP. Include Clerk browser SDK via `<script src>` from `CLERK_FRONTEND_API_URL`.
7. **Write the code** and rebuild affected container (`docker compose up -d --build open-webui` or restart orchestrator).
8. **Verify with agent-browser:** for each assertion, run a scripted flow and capture:
   - screenshot (save to `.factory/artifacts/<feature-id>/<assertion-id>.png` or worker temp)
   - network log (all relevant requests with status + headers)
   - DOM assertions (selectors present/absent)
   - sessionStorage / cookie state
   - console errors (none at level=error allowed)
9. Fix any failure and re-verify.
10. Commit with message referencing feature id + pushed assertions.

## Assertion -> Evidence Mapping

Every VAL-UI-* or VAL-ADMIN-UI assertion requires at minimum:
- 1 screenshot at the decisive moment
- 1 network capture line proving the HTTP call
- 1 DOM or sessionStorage assertion proving state

Record these in your handoff's `interactiveChecks` array.

## Example Handoff

```json
{
  "salientSummary": "Added <script src=\"/static/clerk-integration.js\"> injection into Open WebUI's served index.html via Dockerfile sed-patch. Rebuilt image, restarted compose, and verified with agent-browser that the script loads on first page load, Clerk SDK initializes, and unauthenticated landing shows Clerk sign-in widget.",
  "whatWasImplemented": "Modified open-webui/Dockerfile to add 'RUN sed -i -e \"s|</body>|<script src=\\\"/static/clerk-integration.js\\\"></script></body>|\" /app/backend/static/index.html' after the static assets copy step. Verified that the override persists across container restart.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "docker compose build open-webui", "exitCode": 0, "observation": "build succeeded in 42s"},
      {"command": "docker compose up -d open-webui", "exitCode": 0, "observation": "healthy within 30s"},
      {"command": "curl -s http://localhost:3000/ | grep -c 'clerk-integration.js'", "exitCode": 0, "observation": "1"}
    ],
    "interactiveChecks": [
      {"action": "agent-browser navigate http://localhost:3000/, wait for network idle", "observed": "Network log shows GET /static/clerk-integration.js -> 200; GET https://<clerk-api>/v1/client -> 200; Clerk sign-in widget visible via selector .cl-signIn-root"},
      {"action": "agent-browser screenshot to landing-signin.png", "observed": "screenshot shows sign-in form, no chat composer"},
      {"action": "agent-browser console.log check", "observed": "0 errors at level=error"}
    ]
  },
  "tests": {"added": []},
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Seeded Clerk test users not available (you cannot mint them yourself).
- Open WebUI upstream image changed between build and verify, breaking your patch.
- Backend endpoint claimed to exist in preconditions is missing or returns 500.
- Admin UI feature requires backend data that isn't exposed yet.
