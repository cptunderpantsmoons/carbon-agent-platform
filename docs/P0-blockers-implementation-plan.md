# P0 Blockers Implementation Plan

**Goal:** Fix the 5 critical blockers preventing launch  
**Estimated Time:** 2-3 days  
**Priority:** P0 (must complete before launch)

---

## Overview

| # | Blocker | File(s) | Complexity | Est. Time |
|---|---------|---------|------------|-----------|
| 1 | Auto-provision on user.created | `clerk.py` | Low | 2 hrs |
| 2 | Outbound API key injection | `api_key_injection.py` | Low | 2 hrs |
| 3 | Open WebUI config substitution | `open-webui/` | Medium | 4 hrs |
| 4 | Inject clerk-integration.js | `open-webui/Dockerfile` | Medium | 3 hrs |
| 5 | Admin JWT role gating | `admin.py`, `admin_ui.py` | Medium | 4 hrs |

---

## Task 1: Auto-provision on user.created

**Problem:** `_handle_user_created` creates DB user but doesn't call `ensure_user_service` to provision Railway resources.

**Current State:** Lines 287-293 in `clerk.py` show a background task is scheduled, but `provision_user_background` may not exist or may not call `ensure_user_service`.

**Solution:**
1. Verify `SessionManager.provision_user_background()` exists and calls `ensure_user_service`
2. If not, modify `_handle_user_created` to call `ensure_user_service` directly after DB commit
3. Ensure idempotency (duplicate webhooks return "User already exists")
4. Add proper error handling with compensation (delete partial resources on failure)

**Implementation Steps:**
1. Check `session_manager.py` for `provision_user_background` method
2. If missing, add it to call `ensure_user_service` with proper error handling
3. Update `_handle_user_created` to either use background task or synchronous call
4. Add audit log for provisioning success/failure
5. Write test: `test_user_created_triggers_provisioning`

**Verification:**
```bash
pytest orchestrator/tests/test_clerk.py::test_user_created_triggers_provisioning -v
```

---

## Task 2: Outbound API key injection

**Problem:** `ApiKeyInjectionMiddleware` rewrites Authorization header for incoming requests but doesn't forward to adapter with user's API key.

**Current State:** Lines 159-166 show the middleware DOES rewrite the Authorization header with the user's API key. Need to verify this is working correctly.

**Investigation Needed:**
1. Check if middleware is registered in `main.py`
2. Verify the path matching (`/v1/`, `/adapter/`) matches actual adapter routes
3. Check if adapter receives the rewritten header

**If Not Working:**
1. Ensure middleware is added to FastAPI app in correct order
2. Verify path patterns match actual routes
3. Add logging to confirm header rewrite

**Verification:**
```bash
# Manual test: curl with Clerk token, check adapter logs for Bearer <api_key>
curl -H "Authorization: Bearer <clerk_jwt>" http://localhost:8000/v1/chat/completions
```

---

## Task 3: Open WebUI config substitution

**Problem:** `config.json` still has placeholders: `{{USER_API_KEY}}`, `{{CLERK_PUBLISHABLE_KEY}}`, `{{CLERK_FRONTEND_API_URL}}`

**Solution:** Create entrypoint script that substitutes environment variables at container startup.

**Implementation Steps:**
1. Create `open-webui/entrypoint.sh`:
   ```bash
   #!/bin/sh
   # Substitute environment variables in config.json
   envsubst < /app/backend/data/config.json.template > /app/backend/data/config.json
   # Execute original entrypoint
   exec "$@"
   ```
2. Create `config.json.template` with placeholders
3. Update `Dockerfile`:
   - Install `gettext` for `envsubst`
   - Copy template and entrypoint
   - Set entrypoint to custom script
4. Update `docker-compose.yml` to pass required env vars

**Required Env Vars:**
- `CLERK_PUBLISHABLE_KEY`
- `CLERK_FRONTEND_API_URL`
- `USER_API_KEY` (or remove - handled by clerk-integration.js)

**Verification:**
```bash
docker compose up -d open-webui
docker exec open-webui cat /app/backend/data/config.json | grep -E '\{\{.*\}\}'
# Should return empty (no placeholders)
```

---

## Task 4: Inject clerk-integration.js into Open WebUI

**Problem:** `clerk-integration.js` is copied to container but not injected into Open WebUI's `index.html`.

**Solution:** Patch `index.html` during container build or startup to include the script.

**Implementation Steps:**
1. Find Open WebUI's `index.html` location in base image
2. Create patch script `open-webui/patch-html.sh`:
   ```bash
   #!/bin/sh
   INDEX_HTML="/app/build/index.html"  # or correct path
   if [ -f "$INDEX_HTML" ]; then
     # Inject script before closing </head> or </body>
     sed -i 's|</head>|<script src="/static/clerk-integration.js"></script></head>|' "$INDEX_HTML"
   fi
   ```
3. Update `Dockerfile`:
   - Run patch script after copying clerk-integration.js
   - Or add to entrypoint to patch at runtime
4. Alternative: Mount custom `index.html` if Open WebUI supports it

**Verification:**
```bash
curl -s http://localhost:3000/ | grep clerk-integration.js
# Should find the script tag
```

---

## Task 5: Admin JWT role gating

**Problem:** `admin.py` uses `X-Admin-Key` HMAC verification instead of Clerk JWT with role claim.

**Current State:** Lines 25-29 show `verify_admin_key` using HMAC comparison.

**Solution:** Replace with Clerk JWT verification that checks for admin role in token claims.

**Implementation Steps:**
1. Create new dependency `verify_admin_jwt` in `admin.py`:
   ```python
   async def verify_admin_jwt(
       authorization: str = Header(...),
       db: AsyncSession = Depends(get_session),
   ) -> User:
       # Verify Clerk JWT
       # Check public_metadata.role == "admin"
       # Return user object
   ```
2. Update all admin endpoints to use `verify_admin_jwt` instead of `verify_admin_key`
3. Update `admin_ui.py` to use Clerk JS for authentication
4. Keep `verify_admin_key` as fallback for bootstrap/CI scenarios

**Clerk JWT Role Claim:**
- Clerk tokens include `public_metadata` claim
- Check: `payload.get("public_metadata", {}).get("role") == "admin"`

**Verification:**
```bash
pytest orchestrator/tests/test_admin.py -v
# Test with: valid admin JWT, valid non-admin JWT, invalid JWT, missing JWT
```

---

## Execution Order

**Phase 1: Core Functionality (Day 1)**
1. Task 1: Auto-provision on user.created
2. Task 2: Outbound API key injection (verify/fix)

**Phase 2: Open WebUI Integration (Day 2)**
3. Task 3: Open WebUI config substitution
4. Task 4: Inject clerk-integration.js

**Phase 3: Admin Security (Day 2-3)**
5. Task 5: Admin JWT role gating

**Phase 4: Integration Testing (Day 3)**
- Run full integration tests
- Verify end-to-end flow: sign-up → provision → chat

---

## Dependencies

- **Task 1** depends on: `session_manager.py` having `ensure_user_service`
- **Task 3** depends on: None
- **Task 4** depends on: Task 3 (config must work first)
- **Task 5** depends on: `clerk_auth.py` having JWT verification

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Open WebUI HTML structure changes | Use sed with flexible pattern, test after base image updates |
| Clerk role claim format different | Log full JWT payload during testing to verify claim path |
| Railway provisioning fails | Add compensation logic to clean up partial resources |
| Config substitution breaks | Keep template version controlled, test substitution locally |

---

## Success Criteria

- [ ] User sign-up triggers Railway service provisioning within 60 seconds
- [ ] API requests to `/v1/*` include user's API key in Authorization header to adapter
- [ ] Open WebUI loads with substituted config (no `{{placeholders}}`)
- [ ] `clerk-integration.js` loads in browser and initializes Clerk
- [ ] Admin endpoints accept Clerk JWT with admin role, reject without
- [ ] All P0 validator assertions pass (VAL-PROV-001/002/004, VAL-PROV-007/008, VAL-UI-001/002/003, VAL-ADMIN-001/002/012)

---

## Notes

- The SPEC.md audit shows Task 2 (API key injection) may already be implemented - verify before coding
- Task 1 shows background task is already scheduled at line 290-293 - verify `provision_user_background` exists
- Consider running validator assertions after each task to track progress
