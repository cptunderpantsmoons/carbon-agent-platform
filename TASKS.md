# Tasks

## Active

- [x] **Task 2: Railway API Client**
  - **Status:** ✅ DONE (19/19 tests passing)
  - **Completion Date:** 2026-04-16
  - **Files Created:**
    - orchestrator/app/railway.py - GraphQL client wrapper for Railway API
    - orchestrator/app/schemas.py - Added Railway API response schemas
    - orchestrator/tests/test_railway.py - Tests for Railway API client
- [x] **Task 3: Session Manager (Spin Up/Down Logic)**
  - **Status:** ✅ DONE (17/17 tests passing)
  - **Completion Date:** 2026-04-16
  - **Files Created:**
    - orchestrator/app/session_manager.py - Session management and Railway service lifecycle
    - orchestrator/tests/test_session_manager.py - Tests for session manager
- [x] **Task 4: OpenAI-Compatible Adapter**
  - **Status:** ✅ DONE (Core integration complete)
  - **Completion Date:** 2026-04-16
  - **Files Created:**
    - adapter/app/database.py - Database connection for adapter
    - adapter/app/auth.py - API key authentication middleware
    - adapter/app/models.py - Shared ORM models
    - adapter/app/config.py - Updated for multi-user support
    - adapter/app/main.py - Updated with user authentication and routing
    - adapter/requirements.txt - Updated with database dependencies
    - adapter/tests/test_auth.py - Authentication and routing tests
  - **Note:** Python 3.14 compatibility issues resolved for deployment
- [x] **Task 5: Orchestrator API (Admin & User Endpoints)** ✅ (see Done)
- [x] **Task 6: Docker & Railway Deployment Configs** ✅ (see Done)
- [ ] **Task 7: Admin Agent Scheduler Tasks** — audit-log retention stub needs real DELETE SQL
- [x] **Task 8: Open WebUI Integration Config** ✅ (see Done)
- [ ] **Task 9: Register Admin Scheduler Tasks**
- [ ] **Task 10: Integration Test Suite**

### Code Review Fixes (moon / code-puppy-79601d)

- [x] **Session 1** — Railway mount stub, `clerk_jwt_issuer`, XSS guard, CORS guard, `page.tsx` scaffold
- [x] **Session 2** — Railway provisioning wired (P0), Authorization header rewrite (P0), production config guard (P1), WeakValueDictionary spin-lock fix (P1)
- [x] **Session 3** — Dead `verify_admin_key` removed, open-webui non-root USER, orchestrator + adapter Dockerfile digest pins
- [x] **Session 4** -- open-webui/Dockerfile: pinned FROM to ghcr.io/open-webui/open-webui:main@sha256:b8095f79a6a8ffad8f830bdacc9b5b0aef805689b31bca0b065cc2424d3cfaeb (multi-arch index via docker buildx imagetools inspect)

## Waiting On

## Someday

## Done

- [x] **Task 1: Project Scaffolding & Database Schema**
  - **Status:** ✅ DONE (3/3 tests passing)
  - **Implementer:** ✅ DONE
  - **Spec Reviewer:** ✅ APPROVED
  - **Code Quality Reviewer:** ✅ APPROVED (verdict: excellent implementation)
  - **Completion Date:** 2026-04-16
  - **Files Created:**
    - orchestrator/app/config.py - Pydantic Settings configuration
    - orchestrator/app/database.py - SQLAlchemy async engine & session factory
    - orchestrator/app/models.py - ORM models (User, Session, AuditLog)
    - orchestrator/tests/conftest.py - pytest fixtures with async isolation
    - orchestrator/tests/test_models.py - Test coverage for all models
    - orchestrator/requirements.txt - Dependencies with pinned versions
    - .env.example - Configuration template
    - orchestrator/pytest.ini - pytest-asyncio configuration
    - .gitignore - Python build artifacts exclusion
## Done

- [x] **Task 5: Orchestrator API (Admin & User Endpoints)**
  - **Status:** ✅ DONE (8 user-facing endpoints created)
  - **Completion Date:** 2026-04-16
  - **Files Created:**
    - orchestrator/app/users.py - User-facing API endpoints
    - orchestrator/tests/test_users.py - User API tests
  - **Endpoints:**
    - GET /user/me - User profile
    - PATCH /user/me - Update profile
    - GET /user/me/session - Session info
    - POST /user/me/session/refresh - Refresh session
    - POST /user/me/service/ensure - Ensure service
    - POST /user/me/service/spin-down - Spin down service
    - GET /user/me/service/status - Service status

- [x] **Task 6: Docker & Railway Deployment Configs**
  - **Status:** ✅ DONE
  - **Completion Date:** 2026-04-16
  - **Files Created:**
    - orchestrator/Dockerfile - Production-ready orchestrator container
    - docker-compose.yml - Enhanced with Redis, health checks, resource limits
    - railway.json - Railway deployment configuration
    - Dockerfile.production - Multi-stage production build
    - .env.example - Development environment template
    - .env.production.example - Production environment template
    - Makefile - Comprehensive build/deployment commands
    - scripts/deploy.sh - Railway deployment script
  - **Features:**
    - PostgreSQL 16 with persistent storage
    - Redis 7 for caching and sessions
    - Health checks for all services
    - Resource limits for production stability
    - One-command deployment with Railway CLI

- [x] **Task 8: Open WebUI Integration Config**
  - **Status:** ✅ DONE (35 config tests + 7 auth route tests passing)
  - **Completion Date:** 2026-04-16
  - **Files Created:**
    - open-webui/config.json - Full white-label config with Clerk integration
    - open-webui/clerk-integration.js - Clerk session/API key injection for frontend
    - open-webui/Dockerfile - Custom Open WebUI image with theme CSS and Clerk
    - open-webui/tests/test_config.py - 35 config validation tests
    - orchestrator/app/auth_routes.py - /api/v1/auth/get-api-key endpoint
    - orchestrator/tests/test_auth_routes.py - 7 auth route tests
  - **Features:**
    - White-label branding ("The Intelligence Hub" / "Carbon Agent")
    - Custom CSS theme (dark mode with accent colors)
    - Clerk authentication integration with auto API key injection
    - Pre-configured OpenAI API connection pointing to adapter
    - GET /api/v1/auth/get-api-key - Clerk token to API key retrieval
    - GET /api/v1/auth/clerk-status - Clerk config status check
