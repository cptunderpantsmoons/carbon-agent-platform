# Tasks

## Active

- [ ] **Task 2: Railway API Client**
  - **Status:** pending
  - **Context:** Follows Task 1 foundation, implements GraphQL client for Railway service/volume/deployment management using httpx and gql libraries
  - **Plan File:** docs/superpowers/plans/2026-04-16-carbon-agent-multiuser-platform.md
  - **Files to Implement:**
    - orchestrator/app/railway.py - GraphQL client wrapper for Railway API
    - orchestrator/app/schemas.py - Pydantic models for Railway API responses
    - orchestrator/tests/test_railway.py - Tests for Railway API client
- [ ] **Task 3: Session Manager (Spin Up/Down Logic)**
- [ ] **Task 4: OpenAI-Compatible Adapter**
- [ ] **Task 5: Orchestrator API (Admin & User Endpoints)**
- [ ] **Task 6: Docker & Railway Deployment Configs**
- [ ] **Task 7: Admin Agent Scheduler Tasks**
- [ ] **Task 8: Open WebUI Integration Config**
- [ ] **Task 9: Register Admin Scheduler Tasks**
- [ ] **Task 10: Integration Test Suite**

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

