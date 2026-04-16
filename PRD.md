# Product Requirements Document (PRD)
# Carbon Agent Platform

**Version:** 2.0
**Date:** April 16, 2026
**Status:** In Development
**Repository:** https://github.com/cptunderpantsmoons/carbon-agent-platform.git

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision](#2-product-vision)
3. [Problem Statement](#3-problem-statement)
4. [Target Users & Scale](#4-target-users--scale)
5. [System Architecture](#5-system-architecture)
6. [Component Specifications](#6-component-specifications)
7. [User Journey & Workflows](#7-user-journey--workflows)
8. [Database Schema](#8-database-schema)
9. [API Specifications](#9-api-specifications)
10. [Security Requirements](#10-security-requirements)
11. [Performance & Scalability](#11-performance--scalability)
12. [Deployment Architecture](#12-deployment-architecture)
13. [Infrastructure & Resource Planning](#13-infrastructure--resource-planning)
14. [Development Roadmap](#14-development-roadmap)
15. [Testing Strategy](#15-testing-strategy)
16. [Monitoring & Observability](#16-monitoring--observability)
17. [Cost Estimation](#17-cost-estimation)
18. [Risk Assessment](#18-risk-assessment)
19. [Success Metrics](#19-success-metrics)
20. [Appendices](#20-appendices)

---

## 1. Executive Summary

### 1.1 Overview

The Carbon Agent Platform is a multi-user, white-labeled AI agent platform that takes **Agent Zero** (a powerful AI agent framework) and transforms it into **"Carbon Agent"** - a production-ready, scalable service capable of supporting approximately **70 registered users** with **25-30 concurrent users**. The platform uses **Open WebUI** (white-labeled as **"The Intelligence Hub"**) as the frontend interface, all containerized with **Docker** and deployed on **Railway**.

### 1.2 Key Differentiators

- **Per-User Isolation**: Each user gets their own dedicated Agent Zero instance running as an isolated Railway service
- **OpenAI-Compatible API**: Full compatibility with OpenAI clients, tools, and libraries via the adapter layer
- **Automatic Lifecycle Management**: Services spin up on demand and spin down when idle to optimize costs
- **White-Label Branding**: Both Agent Zero and Open WebUI are rebranded under the "Carbon Agent" / "Intelligence Hub" identity
- **Multi-Tenant Architecture**: Shared infrastructure with per-user isolation for security and performance
- **Clerk Authentication**: Enterprise-grade authentication with social logins, email/password, and automatic user provisioning via webhooks

### 1.3 Current Status

- **Tasks Completed**: 6 of 10 (Tasks 1-6)
- **Development Phase**: Active development
- **Core Infrastructure**: Implemented and tested
- **Production Readiness**: Requires fixes for Tasks 7-10 before production deployment

---

## 2. Product Vision

### 2.1 Long-Term Vision

Create a scalable, multi-tenant AI agent platform that provides each user with a personalized, isolated AI agent experience while maintaining cost efficiency through intelligent resource management and auto-scaling.

### 2.2 Product Goals

1. **User Experience**: Provide a seamless, ChatGPT-like experience through The Intelligence Hub (white-labeled Open WebUI)
2. **Scalability**: Support 70 users with 25-30 concurrent without degradation
3. **Cost Efficiency**: Minimize infrastructure costs through on-demand service provisioning and idle timeout
4. **Security**: Ensure complete data isolation between users
5. **Developer Experience**: Simple deployment, monitoring, and maintenance

### 2.3 Non-Goals

- Real-time streaming from Agent Zero (Agent Zero does not support REST streaming; adapter fakes SSE streaming)
- Multi-model support (platform is designed specifically for Agent Zero)
- Mobile native applications (web-only for v2)
- Custom LLM training or fine-tuning

---

## 3. Problem Statement

### 3.1 The Problem

Agent Zero is a powerful AI agent framework, but it has several limitations for multi-user production deployment:

1. **Single-User Design**: Agent Zero is designed for single-user deployment
2. **No Built-In User Management**: No authentication, authorization, or user isolation
3. **No OpenAI Compatibility**: Cannot be used with standard OpenAI clients or tools
4. **Resource Inefficiency**: Running 70 persistent Agent Zero instances is prohibitively expensive
5. **No Frontend Integration**: Requires custom frontend or manual API interaction

### 3.2 The Solution

The Carbon Agent Platform solves these problems through a four-layer architecture:

1. **Clerk Authentication**: Handles user registration, login (email/password, OAuth), and automatic user provisioning via webhooks
2. **Orchestrator**: Handles user management, API key provisioning, and Railway service lifecycle
3. **Adapter**: Translates OpenAI-compatible API calls to Agent Zero's native API
4. **Open WebUI (The Intelligence Hub)**: Provides a polished, ChatGPT-like frontend (auth replaced by Clerk)

### 3.3 Value Proposition

- **For Users**: A personal AI agent experience with a familiar, polished interface
- **For Administrators**: Easy user management, monitoring, and cost control
- **For the Business**: Scalable infrastructure that grows with demand while controlling costs

---

## 4. Target Users & Scale

### 4.1 User Profile

- **Total Registered Users**: ~70 users
- **Concurrent Active Users**: 25-30 users at peak
- **User Type**: Internal team members, clients, or subscribers
- **Technical Skill**: Varies; interface must be intuitive for non-technical users

### 4.2 Usage Patterns

| Metric | Value | Notes |
|--------|-------|-------|
| Peak concurrent sessions | 25-30 | Estimated 40% of total users active simultaneously |
| Average session duration | 30-60 minutes | Based on typical AI chat usage |
| Idle timeout threshold | 15 minutes | Configurable; services spin down after inactivity |
| Max session lifetime | 24 hours | Services are recycled daily for freshness |
| Messages per session | 10-50 | Typical conversation length |
| Average response time target | <5 seconds | Perceived latency including spin-up |

### 4.3 Capacity Planning

| Resource | Per Instance | Max Concurrent | Total Required |
|----------|--------------|----------------|----------------|
| Memory (Agent Zero) | 1 GB | 30 | 30 GB |
| CPU (Agent Zero) | 1 vCPU | 30 | 30 vCPU |
| PostgreSQL | 512 MB | 1 | 512 MB |
| Redis | 256 MB | 1 | 256 MB |
| Orchestrator | 512 MB | 1 | 512 MB |
| Adapter | 512 MB | 1 | 512 MB |
| Open WebUI | 2 GB | 1 | 2 GB |
| **Total (peak)** | | | **~36 GB / 32 vCPU** |

**Note**: Railway's resource limits and pricing will dictate the final deployment strategy. See [Section 17: Cost Estimation](#17-cost-estimation).

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Clerk Authentication                        │
│              (User Registration, Login, Session Mgmt)               │
│                                                                     │
│  - Email/Password, OAuth (Google, GitHub, etc.)                    │
│  - Session management & token validation                           │
│  - Webhooks for user lifecycle events                              │
└───────────────┬──────────────────────────┬──────────────────────────┘
                │                          │
                │ Clerk Session Token       │ Clerk Webhook
                │ (for frontend)            │ (user.created, user.deleted)
                ▼                          ▼
┌──────────────────────────┐    ┌──────────────────────────────────────┐
│  The Intelligence Hub    │    │        Orchestrator Service          │
│  (Open WebUI + Clerk)    │    │        (User Management & API)       │
│  Port 3000               │    │        Port 8000                     │
│                          │    │                                      │
│  - Clerk handles auth    │    │  - Receives webhooks from Clerk     │
│  - API key auto-injected │    │  - Creates/deletes Carbon Agent users│
│  - No manual config      │    │  - Generates API keys                │
└──────────┬───────────────┘    │  - Manages Railway service lifecycle │
           │                    └──────────────┬───────────────────────┘
           │ OpenAI API calls                 │
           │ (API key auto-injected)          │ Service lifecycle commands
           ▼                                  │ (GraphQL API)
┌──────────────────────────┐                  ▼
│   Adapter Service        │    ┌──────────────────────────────────────┐
│ (OpenAI → Agent Zero)    │    │       Agent Zero Instances           │
│  Port 8001               │    │     (Railway Services - Per User)    │
│                          │    │                                      │
│  - Authenticates via      │    │  User 1: user-{id}-service          │
│    API key (service-to-   │    │  User 2: user-{id}-service          │
│    service)               │    │  User N: user-{id}-service          │
│  - Translates OpenAI API  │    │                                      │
│    to Agent Zero API      │    │  Each instance has:                  │
│  - Fakes SSE streaming    │    │  - Dedicated memory (1 GB)           │
└──────────┬───────────────┘    │  - Dedicated volume (/data)           │
           │                    │  - Unique API key                     │
           │ POST /api_message  │  - Auto-spun down after 15 min idle  │
           ▼                    └──────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 16          Redis 7                     │
│                 (User data, audit)     (Session cache)               │
└──────────────────────────────────────────────────────────────────────┘
```
│  - API key generation & rotation                                    │
│  - Railway service spin-up/spin-down                               │
│  - Session management & idle cleanup                               │
│  - Admin endpoints                                                  │
│  - Audit logging                                                    │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           │ SQL Queries
                           ▼
┌──────────────────────┐          ┌──────────────────────┐
│    PostgreSQL 16     │          │      Redis 7         │
│  (User data, audit)  │          │  (Session cache)     │
└──────────────────────┘          └──────────────────────┘
```

### 5.2 Data Flow

#### User Sends a Message

```
1. User types message in The Intelligence Hub (Open WebUI)
2. Open WebUI sends POST /v1/chat/completions to Adapter
   - Headers: Authorization: Bearer sk-user-api-key
   - Body: {model: "carbon-agent", messages: [...], stream: true}
3. Adapter authenticates user via API key (database lookup)
4. Adapter checks if user has active Railway service
   - If no: calls Orchestrator to spin up service (first request delay ~60s)
   - If yes: proceeds immediately
5. Adapter calls user's Agent Zero instance: POST /api_message
   - Body: {message: "user message", context_id: "uuid", lifetime_hours: 24}
6. Agent Zero processes and returns response
7. Adapter formats response as OpenAI ChatCompletionResponse
   - If stream=true: fakes SSE streaming by word chunks
   - If stream=false: returns complete response
8. Open WebUI displays response to user
9. Session Manager records activity (resets idle timer)
```

#### Idle Session Cleanup

```
1. Session Manager runs background cleanup task (every 60 seconds)
2. Checks all active sessions for idle time > 15 minutes
3. For idle users:
   - Calls Railway API to delete user's service and volume
   - Updates user record (railway_service_id = null, status = pending)
   - Removes from active sessions
4. Next user request will trigger automatic spin-up
```

### 5.3 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Authentication** | Clerk | Latest | User auth, session management, webhooks |
| **Frontend** | Open WebUI | Latest (ghcr.io/open-webui/open-webui:main) | User interface (Clerk-protected) |
| **API Layer** | FastAPI | 0.115.0 | REST API framework |
| **Web Server** | Uvicorn | 0.30.6 | ASGI server |
| **Database** | PostgreSQL | 16 (Alpine) | Primary data store |
| **Cache** | Redis | 7 (Alpine) | Session caching |
| **ORM** | SQLAlchemy | 2.0.35 | Database ORM |
| **Validation** | Pydantic | 2.9.2 | Data validation & settings |
| **HTTP Client** | HTTPX | 0.27.2 | Async HTTP requests |
| **GraphQL** | gql | 3.5.0 | Railway API client |
| **Logging** | structlog | 24.4.0 | Structured logging |
| **Containerization** | Docker + Compose | 3.8 | Deployment |
| **Cloud Platform** | Railway | N/A | Hosting |
| **Python Runtime** | Python | 3.12-slim | Application runtime |
| **Testing** | pytest + pytest-asyncio | 8.3.3 / 0.24.0 | Test framework |
| **Migrations** | Alembic | 1.13.2 | Database migrations |

---

## 6. Component Specifications

### 6.1 Orchestrator Service

**Purpose**: Central management service for users, API keys, sessions, and Railway service lifecycle.

**Port**: 8000

**Key Responsibilities**:
- User CRUD operations (create, read, update, delete)
- API key generation, validation, and rotation
- Railway service/volume lifecycle management (spin-up/spin-down)
- Session tracking and idle timeout enforcement
- Admin operations via protected endpoints
- Audit logging for all administrative actions
- Health monitoring

**Endpoints**:

#### Admin Endpoints (protected by X-Admin-Key header)
- `POST /admin/users` - Create new user
- `GET /admin/users` - List all users
- `GET /admin/users/{user_id}` - Get user details
- `PATCH /admin/users/{user_id}` - Update user
- `DELETE /admin/users/{user_id}` - Delete user
- `POST /admin/agent` - Send command to admin agent
- `GET /admin/health` - Platform health check

#### User Endpoints (protected by Bearer API key)
- `GET /user/me` - Get current user profile
- `PATCH /user/me` - Update current user profile
- `GET /user/me/session` - Get session info
- `POST /user/me/session/refresh` - Refresh session (prevent timeout)
- `POST /user/me/service/ensure` - Ensure user has active service (spin up if needed)
- `POST /user/me/service/spin-down` - Spin down user's service
- `GET /user/me/service/status` - Get service status
- `POST /user/me/api-key/rotate` - Rotate API key

**Lifecycle**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

**Dependencies**: PostgreSQL, Redis, Railway API

### 6.1.1 Clerk Authentication Service

**Purpose**: Enterprise-grade authentication layer providing user registration, login, session management, and automatic user provisioning via webhooks.

**Integration Model**: SaaS (Clerk-hosted)

**Key Responsibilities**:
- User registration and authentication (email/password, OAuth providers)
- Session management and token generation
- Automatic user provisioning to Carbon Agent Platform via webhooks
- Role-based access control (admin vs. user roles)
- Password reset and account recovery
- Multi-factor authentication (optional)

**Authentication Flows**:

#### User Login Flow
```
1. User navigates to The Intelligence Hub (https://hub.platform-url.com)
2. Clerk intercepts unauthenticated request
3. Clerk shows login/signup page (branded as Carbon Agent)
4. User authenticates via:
   - Email + password, OR
   - OAuth provider (Google, GitHub, etc.)
5. Clerk validates credentials and creates session
6. Clerk issues session token (JWT)
7. Clerk middleware calls Orchestrator to:
   - Check if Carbon Agent user exists for this Clerk user ID
   - If not: triggers user creation (webhook or API call)
   - If yes: retrieves user's API key
8. Clerk redirects to The Intelligence Hub with API key auto-injected
9. User can now chat without manual API key configuration
```

#### Admin Login Flow
```
1. Admin navigates to Admin Dashboard (https://admin.platform-url.com)
2. Clerk authenticates admin (same as user flow)
3. Clerk checks user role (admin role required)
4. Admin Dashboard loads with Clerk session token
5. Admin can:
   - View platform metrics
   - Create/suspend/delete users
   - View audit logs
   - Trigger manual operations (service spin-up/down)
```

**Webhook Events**:

The Orchestrator exposes a webhook endpoint that Clerk calls for user lifecycle events:

| Event | Trigger | Action |
|-------|---------|--------|
| `user.created` | New user signs up via Clerk | Create Carbon Agent user record, generate API key, assign to default plan |
| `user.updated` | User profile updated in Clerk | Sync email, display name to Carbon Agent user record |
| `user.deleted` | User deleted from Clerk | Spin down Railway service, delete volume, soft-delete Carbon Agent user record |

**Webhook Endpoint**:
```
POST /webhooks/clerk
Content-Type: application/json
Headers:
  - X-Clerk-Secret: {webhook_secret}  // Verification
  - x-clerk-webhook-signature: {signature}  // HMAC signature verification

Body (user.created example):
{
  "data": {
    "id": "user_2abc123...",
    "email_addresses": [{"email_address": "user@company.com"}],
    "first_name": "John",
    "last_name": "Doe",
    "created_at": 1700000000000
  },
  "type": "user.created"
}
```

**Environment Variables**:
| Variable | Description | Example |
|----------|-------------|---------|
| `CLERK_SECRET_KEY` | Clerk API secret key | `sk_test_abc123...` |
| `CLERK_PUBLISHABLE_KEY` | Clerk frontend publishable key | `pk_test_abc123...` |
| `CLERK_WEBHOOK_SECRET` | Webhook verification secret | `whsec_abc123...` |
| `CLERK_JWT_AUTHORIZED_ORIGINS` | Allowed origins for JWT validation | `https://hub.platform-url.com` |

**Security**:
- Webhook signature verification using HMAC
- JWT validation for frontend requests
- Rate limiting on authentication endpoints (Clerk handles this)
- Session timeout: configurable (default 24 hours)

**Dependencies**: None (SaaS service)

### 6.2 Adapter Service

**Purpose**: Translates OpenAI-compatible API calls to Agent Zero's native `/api_message` endpoint.

**Port**: 8000 (container), 8001 (host mapping)

**Key Responsibilities**:
- Accept OpenAI Chat Completions API requests
- Authenticate users via Bearer API key
- Translate OpenAI message format to Agent Zero format
- Call user's Agent Zero instance
- Format Agent Zero response as OpenAI response
- Fake SSE streaming (word-by-word chunks) if requested
- Route to user-specific Railway service URL

**Endpoints**:
- `GET /health` - Health check
- `GET /v1/models` - List available models (returns "carbon-agent")
- `POST /v1/chat/completions` - Chat completion (streaming and non-streaming)
- `GET /v1/user` - Get current user info

**Agent Zero API Contract**:
```
POST /api_message
Body: {
  "message": "user's message text",
  "context_id": "uuid-for-conversation-thread",
  "lifetime_hours": 24
}
Response: {
  "context_id": "uuid",
  "response": "agent's response text"
}
```

**Streaming Implementation**:
Since Agent Zero does not support streaming, the adapter:
1. Calls Agent Zero synchronously (waits for complete response)
2. Splits response into word chunks
3. Sends each word as SSE `data:` event with small delay
4. Sends `[DONE]` event at end

**Lifecycle**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

**Dependencies**: PostgreSQL (for user auth), Agent Zero instances

### 6.3 The Intelligence Hub (Open WebUI)

**Purpose**: White-labeled frontend providing a ChatGPT-like interface for users.

**Port**: 8080 (container), 3000 (host mapping)

**Configuration**:
```json
{
  "openai": {
    "api_base_url": "http://adapter:8000/v1",
    "api_key": "{{USER_API_KEY}}",
    "model_name": "carbon-agent"
  },
  "ui": {
    "title": "Carbon Agent",
    "description": "Your personal AI workspace",
    "logo": "/static/logo.png"
  },
  "features": {
    "signup_enabled": true,
    "default_user_role": "user",
    "admin_only": false
  },
  "auth": {
    "type": "database",
    "admin_email": "admin@example.com"
  }
}
```

**White-Label Customization**:
- Application title: "Carbon Agent" or "The Intelligence Hub"
- Description: "Your personal AI workspace"
- Logo: Custom Carbon Agent branding
- Model name displayed: "carbon-agent"
- Connection: Points to adapter service, not directly to OpenAI

**User Provisioning Flow**:
1. Admin creates user via Orchestrator admin API
2. User receives API key from admin
3. User logs into Open WebUI
4. User configures OpenAI API connection:
   - Base URL: `http://adapter:8000/v1` (or production URL)
   - API Key: their personal API key
5. User can now chat with Carbon Agent

### 6.4 Railway Services (Per-User Agent Zero Instances)

**Purpose**: Dedicated Agent Zero instance for each user, created on demand and destroyed when idle.

**Service Naming Convention**:
- Service: `user-{user_id}-service`
- Volume: `user-{user_id}-volume`

**Service Configuration**:
- Memory: 1 GB (configurable)
- CPU: 1 vCPU (configurable)
- Docker Image: `carbon-agent-adapter:latest` (or configured image)
- Volume Mount: `/data` (persistent storage)
- Environment Variables:
  - `USER_ID`: User's unique identifier
  - `API_KEY`: User's API key
  - `DISPLAY_NAME`: User's display name

**Lifecycle**:
1. **Spin-Up**: Triggered by first user request or manual API call
   - Create volume (persistent storage)
   - Create service (compute)
   - Deploy with environment variables
   - Update user record with service/volume IDs
2. **Active**: User interacts with their Agent Zero instance
   - Each interaction records activity timestamp
3. **Idle Detection**: Background task checks every 60 seconds
   - If no activity for 15 minutes: mark for cleanup
4. **Spin-Down**: Service and volume are deleted
   - Delete Railway service
   - Delete Railway volume
   - Update user record (service_id = null, status = pending)

### 6.5 PostgreSQL Database

**Purpose**: Persistent storage for users, sessions, audit logs, and platform metadata.

**Version**: PostgreSQL 16 (Alpine)

**Tables**:

#### users
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | UUID |
| clerk_user_id | VARCHAR(255) | UNIQUE, INDEX, NULLABLE | Clerk user ID (user_2abc...) |
| email | VARCHAR(255) | UNIQUE, INDEX | User email |
| display_name | VARCHAR(255) | NOT NULL | Display name |
| api_key | VARCHAR(64) | UNIQUE, INDEX | API key (sk-...) |
| status | ENUM | active/suspended/pending | Account status |
| railway_service_id | VARCHAR(36) | NULLABLE | Current Railway service ID |
| volume_id | VARCHAR(36) | NULLABLE | Current Railway volume ID |
| config | JSON | NULLABLE | User-specific configuration |
| created_at | DATETIME (TZ) | NOT NULL | Creation timestamp |
| updated_at | DATETIME (TZ) | NOT NULL | Last update timestamp |

#### audit_logs
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | UUID |
| user_id | VARCHAR(36) | FOREIGN KEY (users.id), NULLABLE | Related user |
| action | VARCHAR(100) | NOT NULL | Action performed |
| details | JSON | NULLABLE | Action details |
| performed_by | VARCHAR(100) | NOT NULL | Who performed action |
| created_at | DATETIME (TZ) | NOT NULL | Timestamp |

**Storage**: Persistent volume (`pgdata`) for data durability

**Connection**: `postgresql://postgres:{password}@postgres:5432/carbon_platform`

### 6.6 Redis

**Purpose**: Session caching, rate limiting (future), and performance optimization.

**Version**: Redis 7 (Alpine)

**Current Usage**:
- Session state caching (future enhancement)
- Rate limiting counters (future enhancement)

**Configuration**:
- URL: `redis://redis:6379/0`
- Persistent volume: `redis_data`

---

## 7. User Journey & Workflows

### 7.1 User Registration & Provisioning (Clerk Webhook)

#### New User Signs Up via Clerk

```
1. User navigates to The Intelligence Hub (https://hub.platform-url.com)
2. Clerk shows signup page (branded as Carbon Agent)
3. User signs up with email/password or OAuth provider
4. Clerk creates user account and sends webhook to Orchestrator:
   POST /webhooks/clerk
   Body: {
     "type": "user.created",
     "data": {
       "id": "user_2abc123...",
       "email_addresses": [{"email_address": "user@company.com"}],
       "first_name": "John",
       "last_name": "Doe"
     }
   }

5. Orchestrator webhook handler:
   - Verifies webhook signature (HMAC)
   - Generates unique user ID (UUID)
   - Generates API key (sk-{random_hex_48_chars})
   - Creates user record in PostgreSQL with clerk_user_id
   - Creates audit log entry ("user.created via Clerk webhook")
   - Returns 200 OK

6. User is redirected to The Intelligence Hub
7. Clerk middleware retrieves user's API key from Orchestrator
8. API key is automatically injected into Open WebUI configuration
9. User can start chatting immediately (no manual config needed)
```

### 7.2 Admin Workflow

#### Creating a New User (Manual - Alternative to Self-Signup)

```
1. Admin logs into Admin Dashboard (Clerk-authenticated)
2. Admin clicks "Create User"
3. Admin enters:
   - Email: user@company.com
   - Display Name: John Doe

4. Admin Dashboard calls: POST /admin/users
   Headers: Authorization: Bearer {clerk_admin_token}
   Body: {
     "email": "user@company.com",
     "display_name": "John Doe"
   }

5. Orchestrator:
   - Validates admin Clerk token (role = admin)
   - Generates unique user ID (UUID)
   - Generates API key (sk-{random_hex_48_chars})
   - Creates user record in PostgreSQL
   - Creates audit log entry
   - Returns user object with API key

6. Admin Dashboard displays user with API key
7. Admin can share API key with user (if needed for external tools)
```

#### Managing Users (via Clerk-Protected Admin Dashboard)

```
- List all users: GET /admin/users
- View user details: GET /admin/users/{user_id}
- Update user: PATCH /admin/users/{user_id}
- Suspend user: PATCH /admin/users/{user_id} {"status": "suspended"}
- Delete user: DELETE /admin/users/{user_id}
  - Automatically spins down user's Railway service
  - Deletes user's volume
  - Removes user record
```

#### Platform Monitoring

```
- Platform health: GET /admin/health
  Returns: {
    "status": "healthy",
    "service": "orchestrator",
    "total_users": 45,
    "active_services": 23,
    "total_volumes": 23
  }
- Admin agent commands: POST /admin/agent
  Sends natural language commands to admin agent for platform management
```

### 7.2 User Workflow

#### First-Time Setup (Self-Signup via Clerk)

```
1. User navigates to The Intelligence Hub (https://hub.platform-url.com)
2. Clerk intercepts and shows signup/login page
3. User creates account via email/password or OAuth
4. Clerk webhook automatically provisions Carbon Agent user:
   - Creates user record in PostgreSQL
   - Generates API key
   - Links Clerk user ID to Carbon Agent user
5. User is redirected to The Intelligence Hub
6. Clerk middleware automatically injects API key into Open WebUI
7. User sees welcome message and can start chatting immediately
   - No manual API key configuration needed
   - No need to configure OpenAI API connection
   - Everything is pre-configured
```

#### First-Time Setup (Admin-Created User)

```
1. Admin creates user via Admin Dashboard or API
2. User receives welcome email with platform URL
3. User navigates to The Intelligence Hub
4. User clicks "Sign Up" and uses the same email
5. Clerk links to existing Carbon Agent user record (via email match)
6. User can start chatting immediately
```

#### Daily Usage

```
1. User opens The Intelligence Hub (https://hub.platform-url.com)
2. Clerk automatically logs in user (persistent session)
3. User sees their chat history and starts conversation
4. On first message:
   - Clerk session provides API key to Open WebUI
   - Adapter authenticates user via API key
   - Session Manager checks for active Railway service
   - If no service: spins up new service (60-120 second delay)
   - If service exists: routes immediately
5. User sends message
6. Adapter translates to Agent Zero API call
7. Agent Zero processes and responds
8. Adapter returns formatted response (with fake streaming if enabled)
9. User sees response in The Intelligence Hub
10. Session activity is recorded (resets idle timer)
11. Repeat steps 5-10 for conversation duration
```

#### Session Timeout & Recovery

```
1. User stops interacting for 15 minutes
2. Session Manager background task detects idle session
3. Session Manager spins down user's Railway service
   - Deletes service and volume
   - Updates user record (status = pending)
4. User returns and sends new message
5. Service is automatically spun up again
   - Brief delay (60-120 seconds)
   - Conversation context is lost (new session)
   - User is notified via UI toast/message
```

#### User Account Management (via Clerk)

```
1. User clicks "Account Settings" in The Intelligence Hub
2. Clerk Account modal opens (or redirects to Clerk-hosted page)
3. User can:
   - Change password
   - Update email address
   - Enable/disable MFA
   - Manage connected OAuth providers
   - View active sessions
   - Delete account
4. Changes sync automatically to Carbon Agent platform via webhooks
```

### 7.3 Admin Workflow (Clerk-Protected)

#### Admin Dashboard Access

```
1. Admin navigates to https://admin.platform-url.com
2. Clerk authenticates admin (same login page as users)
3. Clerk checks admin role:
   - If admin has "admin" role: grant access
   - If not: redirect to "Access Denied" page
4. Admin Dashboard loads with platform metrics:
   - Total users
   - Active services
   - Recent activity
   - Platform health status
```

#### Admin Operations

```
All admin operations can be performed via:
1. Admin Dashboard UI (Clerk-protected)
2. Admin API (X-Admin-Key for automation/scripts)

Both methods are supported simultaneously.
```

### 7.4 API Key Rotation

```
1. User or admin triggers API key rotation:
   - Via Admin Dashboard, OR
   - Via API: POST /user/me/api-key/rotate

2. Orchestrator:
   - Validates request (Clerk token or API key)
   - Generates new API key (sk-{new_random_hex})
   - Updates user record
   - Creates audit log entry (records last 4 chars of old key)
   - Returns new API key

3. Clerk middleware updates API key in Open WebUI automatically
4. Old API key is immediately invalid
5. User's active sessions continue (API key refreshed in background)
```

---

## 8. Database Schema

### 8.1 Entity Relationship Diagram

```
┌──────────────────────────────────┐
│           users                   │
│───────────────────────────────────│
│ id (PK)                           │
│ clerk_user_id (unique, index)     │  ← NEW: Links to Clerk user
│ email                             │
│ display_name                      │
│ api_key                           │
│ status                            │
│ railway_service_id                │
│ volume_id                         │
│ config (JSON)                     │
│ created_at                        │
│ updated_at                        │
└────────┬──────────────────────────┘
         │
         │ 1:N
         │
┌────────▼──────────────────────────┐
│        audit_logs                  │
│───────────────────────────────────│
│ id (PK)                           │
│ user_id (FK)                      │
│ action                            │
│ details (JSON)                    │
│ performed_by                      │
│ created_at                        │
└───────────────────────────────────┘

External System (Clerk):
┌──────────────────────────────────┐
│        Clerk Users (SaaS)        │
│───────────────────────────────────│
│ id: user_2abc123...              │
│ email_addresses[]                 │
│ first_name, last_name             │
│ created_at                        │
│ last_sign_in_at                   │
│ password_enabled                  │
│ oauth_connections[]               │
└──────────────────────────────────┘
         │
         │ Webhook sync
         ▼
    Carbon Agent users table
    (clerk_user_id links to Clerk id)
```

### 8.2 Enumerations

#### UserStatus
- `active`: User can authenticate and use services
- `suspended`: User cannot authenticate (admin action)
- `pending`: User has no active Railway service (normal state when spun down)

### 8.3 Indexes

- `users.email` (unique, indexed) - Fast email lookup
- `users.api_key` (unique, indexed) - Fast API key authentication
- `audit_logs.user_id` (indexed) - Fast audit queries per user

### 8.4 Migration Strategy

**Tool**: Alembic 1.13.2

**Current State**: Using `create_tables()` for initial schema. Needs Alembic migration setup for production.

**Migration Plan**:
1. Initialize Alembic with current schema as baseline
2. Create migration for any schema changes
3. Run `alembic upgrade head` during deployment
4. Support rollback with `alembic downgrade -1`

---

## 9. API Specifications

### 9.1 Authentication Methods

#### Clerk Authentication (Frontend & Admin Dashboard)
- **Type**: JWT session tokens (managed by Clerk)
- **Used for**: 
  - Frontend access (The Intelligence Hub)
  - Admin Dashboard access
  - User account management
- **Flow**: 
  1. User logs in via Clerk (email/password or OAuth)
  2. Clerk issues JWT session token
  3. Token is sent with requests to protected endpoints
  4. Backend validates token using Clerk's public key
- **Configuration**: `CLERK_PUBLISHABLE_KEY` (frontend), `CLERK_SECRET_KEY` (backend)
- **Role-Based Access**: Admin endpoints require Clerk user with "admin" role

#### Admin Authentication (API Automation)
- **Header**: `X-Admin-Key: {admin_api_key}`
- **Used for**: Admin API endpoints (for scripts, automation, CI/CD)
- **Configuration**: `ADMIN_AGENT_API_KEY` environment variable
- **Note**: Both Clerk and X-Admin-Key are supported. Clerk for human admins, X-Admin-Key for automation.

#### User API Key Authentication (Service-to-Service)
- **Header**: `Authorization: Bearer {api_key}`
- **Used for**: All `/user/*` and `/v1/*` endpoints
- **Key Format**: `sk-{48_hex_characters}`
- **Validation**: Database lookup in `users` table
- **Note**: API keys are automatically injected by Clerk middleware (users don't manually configure them)

#### Webhook Authentication
- **Header**: `x-clerk-webhook-signature: {hmac_signature}`
- **Used for**: `/webhooks/clerk` endpoint
- **Verification**: HMAC-SHA256 signature using `CLERK_WEBHOOK_SECRET`

### 9.2 Admin API Reference

#### POST /admin/users - Create User

**Request**:
```http
POST /admin/users
X-Admin-Key: dev-admin-key
Content-Type: application/json

{
  "email": "user@company.com",
  "display_name": "John Doe",
  "config": {}
}
```

**Response** (201):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@company.com",
  "display_name": "John Doe",
  "status": "pending",
  "api_key": "sk-abc123...",
  "created_at": "2026-04-16T12:00:00Z",
  "updated_at": "2026-04-16T12:00:00Z"
}
```

#### GET /admin/users - List Users

**Response** (200):
```json
{
  "users": [
    {
      "id": "...",
      "email": "...",
      "display_name": "...",
      "status": "active",
      "created_at": "..."
    }
  ],
  "total": 45
}
```

#### GET /admin/health - Platform Health

**Response** (200):
```json
{
  "status": "healthy",
  "service": "orchestrator",
  "total_users": 45,
  "active_services": 23,
  "total_volumes": 23
}
```

### 9.3 Webhook API Reference

#### POST /webhooks/clerk - Clerk Webhook Handler

**Purpose**: Receives user lifecycle events from Clerk and automatically provisions/deprovisions Carbon Agent users.

**Request**:
```http
POST /webhooks/clerk
Content-Type: application/json
x-clerk-webhook-signature: hmac_sha256_signature

{
  "data": {
    "id": "user_2abc123def456",
    "email_addresses": [
      {"email_address": "user@company.com", "id": "idn_abc123"}
    ],
    "first_name": "John",
    "last_name": "Doe",
    "created_at": 1700000000000,
    "updated_at": 1700000000000
  },
  "object": "event",
  "type": "user.created"
}
```

**Supported Event Types**:

| Event | Action |
|-------|--------|
| `user.created` | Create Carbon Agent user, generate API key, link clerk_user_id |
| `user.updated` | Sync email and display name to Carbon Agent user |
| `user.deleted` | Spin down Railway service, delete volume, soft-delete user record |

**Response** (200):
```json
{
  "status": "success",
  "message": "Webhook processed successfully",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error Response** (400):
```json
{
  "status": "error",
  "message": "Invalid webhook signature"
}
```

**Security**:
- HMAC-SHA256 signature verification using `CLERK_WEBHOOK_SECRET`
- Replay attack prevention (timestamp validation)
- Idempotent processing (duplicate events handled safely)

### 9.4 User API Reference

#### GET /user/me - Get Profile

**Request**:
```http
GET /user/me
Authorization: Bearer sk-user-api-key
```

**Response** (200):
```json
{
  "id": "...",
  "email": "user@company.com",
  "display_name": "John Doe",
  "status": "active",
  "api_key": "sk-user-api-key",
  "created_at": "...",
  "updated_at": "..."
}
```

#### POST /user/me/service/ensure - Spin Up Service

**Response** (200):
```json
{
  "status": "created",
  "message": "Service spun up successfully"
}
```
or
```json
{
  "status": "existing",
  "message": "Service already active"
}
```

#### GET /user/me/service/status - Service Status

**Response** (200):
```json
{
  "active": true,
  "service_id": "svc-123",
  "volume_id": "vol-123",
  "status": "running",
  "updated_at": "...",
  "instances": [...]
}
```

### 9.4 Adapter API Reference

#### GET /v1/models - List Models

**Response** (200):
```json
{
  "object": "list",
  "data": [
    {
      "id": "carbon-agent",
      "object": "model",
      "created": 1700000000,
      "owned_by": "carbon-agent"
    }
  ]
}
```

#### POST /v1/chat/completions - Chat

**Request** (non-streaming):
```http
POST /v1/chat/completions
Authorization: Bearer sk-user-api-key
Content-Type: application/json

{
  "model": "carbon-agent",
  "messages": [
    {"role": "user", "content": "Hello, who are you?"}
  ],
  "stream": false
}
```

**Response** (200):
```json
{
  "model": "carbon-agent",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "I am Carbon Agent, your personal AI assistant."
      }
    }
  ]
}
```

**Request** (streaming):
```json
{
  "model": "carbon-agent",
  "messages": [...],
  "stream": true
}
```

**Response** (200, text/event-stream):
```
data: {"choices": [{"delta": {"content": "I"}}]}

data: {"choices": [{"delta": {"content": " am"}}]}

data: {"choices": [{"delta": {"content": " Carbon"}}]}

data: [DONE]
```

---

## 10. Security Requirements

### 10.1 Authentication & Authorization

| Requirement | Implementation | Status |
|------------|----------------|--------|
| Clerk authentication (frontend) | JWT session tokens via Clerk | Planned (Task 11) |
| Clerk role-based access | Admin vs. user roles in Clerk | Planned (Task 11) |
| Admin API key authentication | `X-Admin-Key` header (for automation) | ✅ Implemented |
| User API key authentication | `Authorization: Bearer` header (service-to-service) | ✅ Implemented |
| API key format | `sk-{48_hex_chars}` | ✅ Implemented |
| User status enforcement | Reject inactive/suspended users | ✅ Implemented |
| Per-user service isolation | Dedicated Railway service per user | ✅ Implemented |
| Webhook signature verification | HMAC-SHA256 for Clerk webhooks | Planned (Task 11) |

### 10.2 Data Protection

| Requirement | Implementation | Status | Priority |
|------------|----------------|--------|----------|
| CORS restriction | Limit to known origins | ❌ Currently allows all (*) | CRITICAL |
| API key exposure | Hide from responses after creation | ❌ Currently exposed in all UserResponse | CRITICAL |
| Password hashing | Clerk handles password security (bcrypt, argon2) | ✅ Via Clerk | ✅ |
| SQL injection prevention | SQLAlchemy ORM (parameterized queries) | ✅ Implemented | ✅ |
| Secrets management | Environment variables + Clerk vault | ✅ Partially (Clerk adds security) | MEDIUM |
| Webhook replay prevention | Timestamp validation + nonce | Planned (Task 11) | HIGH |

### 10.3 Rate Limiting

| Endpoint | Limit | Status | Priority |
|----------|-------|--------|----------|
| `/v1/chat/completions` | TBD (per user per minute) | ❌ Not implemented | HIGH |
| `/user/me/api-key/rotate` | 1 per hour per user | ❌ Not implemented | MEDIUM |
| `/admin/users` | 10 per minute | ❌ Not implemented | MEDIUM |

### 10.4 Audit Logging

All administrative actions are logged in `audit_logs` table:
- User creation, update, deletion
- API key rotation
- Service spin-up/spin-down
- Admin commands

**Audit Log Fields**:
- `id`: Unique log ID
- `user_id`: Affected user (nullable)
- `action`: Action identifier (e.g., "user.created", "user.api_key_rotated")
- `details`: JSON with action-specific details
- `performed_by`: Email or identifier of actor
- `created_at`: Timestamp

### 10.5 Known Security Issues (Must Fix Before Production)

1. **CORS allows all origins with credentials** (`orchestrator/app/main.py`)
   - Risk: CSRF attacks, credential theft
   - Fix: Restrict `allow_origins` to known frontend URLs

2. **API key in every user response** (`orchestrator/app/schemas.py`)
   - Risk: Increased exposure surface
   - Fix: Return API key only on creation/rotation, use separate schema for profile

3. **No rate limiting**
   - Risk: API abuse, resource exhaustion, brute force
   - Fix: Implement rate limiting middleware (Redis-backed)

4. **Admin key in plain text**
   - Risk: If database is compromised, admin keys are readable
   - Fix: Hash admin keys with bcrypt (Note: Clerk authentication eliminates this risk for human admins; X-Admin-Key remains for automation)

### 10.6 Clerk Security Benefits

By integrating Clerk, the platform gains:

| Benefit | Description |
|---------|-------------|
| **Password Security** | Clerk handles password hashing (bcrypt/argon2), breach detection, and password policies |
| **MFA Support** | Multi-factor authentication available out-of-the-box |
| **Session Management** | Secure JWT sessions with configurable timeout, refresh, and revocation |
| **OAuth Security** | Secure OAuth flows with Google, GitHub, etc. handled by Clerk |
| **Brute Force Protection** | Built-in rate limiting and account lockout |
| **Audit Trail** | Clerk logs all authentication events (logins, failures, password changes) |
| **Compliance** | SOC 2 Type II certified, GDPR compliant |

---

## 11. Performance & Scalability

### 11.1 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| API response time (no spin-up) | <2 seconds | Adapter → Agent Zero round trip |
| API response time (with spin-up) | <120 seconds | First request after idle timeout |
| Concurrent users supported | 30 | Peak load target |
| Database query time | <50 ms | User authentication, profile lookup |
| Session cleanup interval | 60 seconds | Background task frequency |
| Idle timeout | 15 minutes | Configurable per deployment |

### 11.2 Scalability Strategy

#### Current Architecture (v2)
- **Vertical scaling**: Each user gets dedicated Railway service (1GB, 1 vCPU)
- **Horizontal scaling**: Single orchestrator, single adapter, single Open WebUI
- **Database**: Single PostgreSQL instance
- **Limitation**: 30 concurrent users = 30 Railway services = high cost

#### Future Architecture (v3 - Post-70 Users)
- **Connection pooling**: PgBouncer for database connections
- **Read replicas**: PostgreSQL read replicas for user queries
- **Redis caching**: Cache user profiles, API keys in Redis
- **Service pooling**: Pre-warm a pool of Agent Zero instances instead of per-user
- **Load balancing**: Multiple adapter instances behind a load balancer
- **Message queue**: Celery/RQ for background jobs

### 11.3 Bottleneck Analysis

| Component | Current Capacity | Bottleneck at | Mitigation |
|-----------|-----------------|---------------|------------|
| PostgreSQL | ~500 concurrent connections | ~200 concurrent queries | Connection pooling |
| Adapter | ~100 req/sec | ~50 concurrent streaming responses | Horizontal scaling |
| Orchestrator | ~50 req/sec | ~30 concurrent service operations | Async operations |
| Railway API | Rate limited by Railway | 100 req/min (Railway limit) | Request queuing |
| Open WebUI | ~100 concurrent users | Memory (2GB limit) | Horizontal scaling |

### 11.4 Concurrency Model

For 25-30 concurrent users:
- 25-30 Railway services active (1GB each = 25-30GB)
- 25-30 active sessions in memory
- ~50-100 database connections (with connection pooling)
- ~10-20 req/sec to adapter at peak

---

## 12. Deployment Architecture

### 12.1 Deployment Target: Railway

Railway is the primary deployment platform. The platform leverages Railway's:
- Container hosting (Docker)
- PostgreSQL add-on
- Redis add-on
- Automatic HTTPS
- Service networking
- Environment variable management
- GitHub integration for CI/CD

### 12.2 Railway Service Layout

```
Carbon Platform Project (Railway)
├── PostgreSQL (Railway managed)
│   Database: carbon_platform
│   Plan: Pro (for 50GB storage)
│
├── Redis (Railway managed)
│   Plan: Standard
│
├── Orchestrator
│   Dockerfile: orchestrator/Dockerfile
│   Port: 8000
│   Domain: orchestrator.platform-url.railway.app
│   Resources: 512MB, 0.5 vCPU
│
├── Adapter
│   Dockerfile: adapter/Dockerfile
│   Port: 8000
│   Domain: adapter.platform-url.railway.app
│   Resources: 512MB, 0.5 vCPU
│
├── Open WebUI (The Intelligence Hub)
│   Image: ghcr.io/open-webui/open-webui:main
│   Port: 8080
│   Domain: hub.platform-url.railway.app
│   Resources: 2GB, 1 vCPU
│
└── User Services (Dynamically Created)
    user-{id}-service (x25-30 active)
    user-{id}-volume (x25-30 active)
    Each: 1GB, 1 vCPU
```

### 12.3 Deployment Process

#### Local Development
```bash
# 1. Clone repository
git clone https://github.com/cptunderpantsmoons/carbon-agent-platform.git
cd carbon-agent-platform

# 2. Configure environment
cp .env.example .env
# Edit .env with local development values

# 3. Start stack
make dev
# or: docker compose up --build

# 4. Run tests
make test
```

#### Production Deployment (Railway)
```bash
# 1. Configure production environment
cp .env.production.example .env.production
# Edit .env.production with production values

# 2. Deploy
make deploy-railway
# or: bash scripts/deploy.sh

# 3. Verify deployment
make railway-status
```

#### CI/CD Pipeline (Recommended)
```yaml
# .github/workflows/deploy.yml (to be created)
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.12"
      - run: pip install -r orchestrator/requirements.txt
      - run: cd orchestrator && pytest tests/ -v
      - run: cd adapter && pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: railwayapp/cli@v1
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN }}
      - run: railway up
```

### 12.4 Docker Compose Services

| Service | Image | Ports | Volumes | Health Check |
|---------|-------|-------|---------|--------------|
| postgres | postgres:16-alpine | 5432 | pgdata | pg_isready |
| redis | redis:7-alpine | 6379 | redis_data | redis-cli ping |
| orchestrator | Build (./orchestrator) | 8000 | - | curl /health |
| adapter | Build (./adapter) | 8001 | - | curl /health |
| open-webui | ghcr.io/open-webui/open-webui:main | 3000 | openwebui | curl /health |

### 12.5 Resource Limits (Docker Compose)

| Service | Memory Limit | CPU Limit |
|---------|-------------|-----------|
| postgres | 512MB | - |
| redis | 256MB | - |
| orchestrator | 512MB | - |
| adapter | 512MB | - |
| open-webui | 2GB | - |

---

## 13. Infrastructure & Resource Planning

### 13.1 Railway Cost Estimation (25-30 Concurrent Users)

#### Base Services (Always Running)
| Service | RAM | Cost/Month |
|---------|-----|------------|
| PostgreSQL (Pro) | 1GB | ~$20 |
| Redis (Standard) | 256MB | ~$5 |
| Orchestrator | 512MB | ~$5 |
| Adapter | 512MB | ~$5 |
| Open WebUI | 2GB | ~$10 |
| **Base Total** | | **~$45/month** |

#### Clerk Authentication
| Plan | MAUs (Monthly Active Users) | Cost/Month |
|------|----------------------------|------------|
| Starter (free tier) | Up to 10,000 MAUs | $0 |
| Pro (if needed) | Up to 50,000 MAUs | ~$25 |

**Note**: For 70 users, the free tier is more than sufficient.

#### Dynamic User Services (25-30 Concurrent)
| Resource | Per Instance | Instances | Hours/Day | Cost/Month |
|----------|-------------|-----------|-----------|------------|
| User Service (1GB) | 1GB | 30 | 12 | ~$130 |
| User Volume (5GB) | 5GB | 30 | 24 | ~$15 |
| **Dynamic Total** | | | | **~$145/month** |

#### Total Estimated Cost
| Component | Cost/Month |
|-----------|-----------|
| Base Services | $45 |
| Clerk (free tier) | $0 |
| Dynamic User Services | $145 |
| Buffer (20%) | $38 |
| **Total** | **~$228/month** |

**Note**: Costs vary based on actual usage patterns, idle timeout settings, and Railway pricing changes. The 15-minute idle timeout significantly reduces costs vs. persistent services.

### 13.2 Storage Planning

| Component | Storage | Growth Rate | Notes |
|-----------|---------|-------------|-------|
| PostgreSQL | 1-5 GB | ~100MB/month | User records, audit logs |
| User Volumes | 5GB x 30 = 150GB | Varies | Created/deleted dynamically |
| Open WebUI | 500MB | ~50MB/month | User preferences, chat history |
| Redis | 100MB | Minimal | Session cache only |

### 13.3 Network Planning

| Traffic | Direction | Bandwidth | Notes |
|---------|-----------|-----------|-------|
| User → Open WebUI | Ingress | ~1MB/session | UI assets, messages |
| Open WebUI → Adapter | Internal | ~500KB/message | API calls |
| Adapter → Agent Zero | Internal | ~500KB/message | Internal API |
| Agent Zero → Adapter | Internal | ~500KB/message | Responses |
| Adapter → Open WebUI | Egress | ~500KB/message | Formatted responses |

---

## 14. Development Roadmap

### 14.1 Current Status (Tasks 1-6 Complete)

| Task | Description | Status | Date |
|------|------------|--------|------|
| Task 1 | Project Scaffolding & Database Schema | ✅ DONE | 2026-04-16 |
| Task 2 | Railway API Client | ✅ DONE (19/19 tests) | 2026-04-16 |
| Task 3 | Session Manager | ✅ DONE (17/17 tests) | 2026-04-16 |
| Task 4 | OpenAI-Compatible Adapter | ✅ DONE | 2026-04-16 |
| Task 5 | Orchestrator API | ✅ DONE (8 endpoints) | 2026-04-16 |
| Task 6 | Docker & Railway Deployment | ✅ DONE | 2026-04-16 |

### 14.2 Remaining Tasks (Tasks 7-11)

#### Task 7: Admin Agent Scheduler Tasks
**Objective**: Implement scheduled background tasks for platform management.

**Requirements**:
- [ ] Idle session cleanup (currently broken - needs DB session injection)
- [ ] Service health monitoring
- [ ] Database backup scheduling
- [ ] Usage analytics aggregation
- [ ] Stale data cleanup (old audit logs)

**Technical Approach**:
- Option A: Use asyncio background tasks (current approach, limited)
- Option B: Integrate Celery + Celery Beat (recommended for production)
- Option C: Use Railway's cron job feature (simplest)

**Recommendation**: Option C for simplicity, Option B for scale beyond 70 users.

#### Task 8: Open WebUI Integration Config
**Objective**: Complete Open WebUI white-labeling and user provisioning automation.

**Requirements**:
- [ ] Automated Open WebUI configuration on user creation
- [ ] White-label branding (logo, title, colors)
- [ ] Pre-configured OpenAI API connection template
- [ ] User onboarding flow documentation
- [ ] Custom CSS/theme for Carbon Agent branding

**Current State**: `open-webui/config.json` exists but needs integration with user provisioning.

**Note**: With Clerk integration (Task 11), Open WebUI configuration will be automated via Clerk middleware (API key auto-injection).

#### Task 9: Register Admin Scheduler Tasks
**Objective**: Wire up scheduled tasks to orchestrator lifecycle.

**Requirements**:
- [ ] Replace broken `_cleanup_idle_sessions()` with working implementation
- [ ] Register tasks on orchestrator startup
- [ ] Graceful shutdown of scheduled tasks
- [ ] Task execution monitoring and logging
- [ ] Manual task trigger endpoints (for admin debugging)

**Critical Fix**: The current session cleanup task cannot spin down idle users because it lacks database session access. This must be redesigned.

#### Task 10: Integration Test Suite
**Objective**: End-to-end tests covering full user lifecycle.

**Requirements**:
- [ ] Full user lifecycle test (create → spin up → chat → spin down → delete)
- [ ] Concurrent user simulation (10+ users simultaneously)
- [ ] API error handling tests (invalid keys, missing headers, etc.)
- [ ] Railway API failure simulation (service creation fails)
- [ ] Database failure recovery tests
- [ ] Load testing (25-30 concurrent users simulation)

**Current State**: Basic integration tests exist in `tests/test_integration.py` (4 tests for adapter flow).

#### Task 11: Clerk Authentication Integration ⭐ NEW
**Objective**: Integrate Clerk for user authentication, session management, and automatic user provisioning via webhooks.

**Requirements**:

**Webhook Handler**:
- [ ] Create `/webhooks/clerk` endpoint in orchestrator
- [ ] Implement HMAC-SHA256 signature verification
- [ ] Handle `user.created` event (auto-provision Carbon Agent user)
- [ ] Handle `user.updated` event (sync user profile)
- [ ] Handle `user.deleted` event (spin down service, soft-delete user)
- [ ] Idempotent event processing (handle duplicate webhooks safely)
- [ ] Replay attack prevention (timestamp validation)

**Authentication Middleware**:
- [ ] Add Clerk JWT validation middleware to orchestrator
- [ ] Add Clerk session validation to Open WebUI proxy
- [ ] Implement role-based access control (admin vs. user roles)
- [ ] Create `/auth/clerk-status` endpoint for frontend auth checks

**API Key Injection**:
- [ ] Create middleware that retrieves user's API key from database using Clerk user ID
- [ ] Automatically inject API key into Open WebUI configuration
- [ ] Cache API key in Redis for performance (with TTL)
- [ ] Handle API key rotation (update cache on rotation)

**Admin Dashboard**:
- [ ] Build simple admin dashboard UI (FastAPI + HTML or lightweight framework)
- [ ] Protect with Clerk authentication (admin role required)
- [ ] Display platform metrics (total users, active services, health)
- [ ] User management CRUD (create, view, suspend, delete)
- [ ] Audit log viewer
- [ ] Manual service operations (spin-up/spin-down for specific users)

**Database Migration**:
- [ ] Add `clerk_user_id` column to `users` table (unique, nullable, indexed)
- [ ] Create migration for existing users (link by email matching)

**Testing**:
- [ ] Unit tests for webhook handler (mock Clerk signatures)
- [ ] Integration tests for Clerk auth flow
- [ ] Tests for webhook event idempotency
- [ ] Tests for API key injection middleware

**Environment Variables Required**:
```bash
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_WEBHOOK_SECRET=whsec_...
CLERK_JWT_AUTHORIZED_ORIGINS=https://hub.platform-url.com
```

**Technical Stack**:
- Clerk Python SDK: `clerk-backend-api` or direct HTTP calls
- JWT validation: `PyJWT` library
- Webhook verification: `hmac` + `hashlib` (standard library)

**Dependencies**: Clerk account setup, Clerk application creation

**Estimated Effort**: 3-5 days of development

### 14.3 Task Priority & Order

Recommended implementation order:
1. **Task 9** (Fix session cleanup) - Critical bug fix
2. **Task 11** (Clerk integration) - Transforms user experience
3. **Task 8** (Open WebUI config) - Simplified by Clerk
4. **Task 7** (Scheduler tasks) - Production readiness
5. **Task 10** (Integration tests) - Final validation

### 14.4 Post-v2 Roadmap (Future Enhancements)

| Feature | Priority | Description |
|---------|----------|-------------|
| Rate Limiting | HIGH | Redis-backed rate limiting for all endpoints |
| Usage Analytics Dashboard | MEDIUM | Admin dashboard for usage metrics |
| WebSocket Streaming | MEDIUM | Real streaming from Agent Zero (if supported) |
| Multi-Model Support | LOW | Support multiple LLM backends |
| Mobile App | LOW | Native iOS/Android app |
| SSO Integration | ✅ DONE (via Clerk) | OAuth/SAML through Clerk (Google, GitHub, etc.) |
| API Usage Billing | LOW | Per-token or per-message billing |
| Service Pooling | HIGH (for scale) | Pre-warmed pool instead of per-user services |

---

## 15. Testing Strategy

### 15.1 Test Pyramid

```
                    ┌─────────┐
                   │  E2E     │  ~5 tests (manual + automated)
                  │  Tests   │
                 ─────────────
                │ Integration │  ~10 tests (API flow tests)
               │   Tests     │
              ───────────────────
             │    Unit Tests     │  ~50+ tests (component tests)
            ─────────────────────────
```

### 15.2 Current Test Coverage

| Component | Test File | Test Count | Status |
|-----------|-----------|------------|--------|
| Models | `orchestrator/tests/test_models.py` | 3 | ✅ Passing |
| Railway Client | `orchestrator/tests/test_railway.py` | 19 | ✅ Passing |
| Session Manager | `orchestrator/tests/test_session_manager.py` | 17 | ✅ Passing |
| User API | `orchestrator/tests/test_users.py` | 13 | ⚠️ Some skipped |
| Admin API | `orchestrator/tests/test_admin.py` | ~5 | ✅ Passing |
| Adapter Auth | `adapter/tests/test_auth.py` | ~5 | ✅ Passing |
| Adapter Main | `adapter/tests/test_main.py` | ~5 | ✅ Passing |
| Adapter Schemas | `adapter/tests/test_schemas.py` | ~3 | ✅ Passing |
| Adapter Streaming | `adapter/tests/test_streaming.py` | ~3 | ✅ Passing |
| Integration | `tests/test_integration.py` | 4 | ✅ Passing |
| **Total** | | **~77** | |

### 15.3 Test Infrastructure

- **Framework**: pytest + pytest-asyncio
- **Database**: SQLite (aiosqlite) for local testing, PostgreSQL for CI/CD
- **Mocking**: unittest.mock for external services (Railway API, Agent Zero)
- **HTTP Testing**: FastAPI TestClient

### 15.4 Test Execution

```bash
# All tests
make test

# Component-specific
make test-adapter      # Adapter tests only
make test-orchestrator # Orchestrator tests only

# With coverage (future)
pytest --cov=app --cov-report=html
```

### 15.5 CI/CD Testing (Recommended)

```yaml
# GitHub Actions workflow
- name: Run tests
  run: |
    cd orchestrator && pytest tests/ -v --cov=app
    cd adapter && pytest tests/ -v --cov=app

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

### 15.6 Testing Gaps

| Gap | Priority | Description |
|-----|----------|-------------|
| Load testing | HIGH | Simulate 25-30 concurrent users |
| Failure injection | MEDIUM | Test Railway API failures, DB disconnections |
| Security testing | HIGH | Penetration testing, OWASP checks |
| API contract testing | MEDIUM | Verify OpenAI compatibility |
| Migration testing | LOW | Test Alembic migrations up/down |

---

## 16. Monitoring & Observability

### 16.1 Current Logging

**Framework**: structlog (structured JSON logging)

**Log Examples**:
```json
{"event": "authenticated_user", "user_id": "...", "email": "user@company.com"}
{"event": "chat_request", "user_id": "...", "user_email": "...", "stream": true}
{"event": "Created Railway service", "service_id": "svc-123"}
{"event": "User idle for 900, spinning down service", "user_id": "..."}
```

### 16.2 Health Checks

| Service | Endpoint | Interval | Timeout | Retries |
|---------|----------|----------|---------|---------|
| Orchestrator | GET /health | 30s | 10s | 3 |
| Adapter | GET /health | 30s | 10s | 3 |
| Open WebUI | GET /health | 30s | 10s | 3 |
| PostgreSQL | pg_isready | 10s | 5s | 5 |
| Redis | redis-cli ping | 10s | 5s | 5 |

### 16.3 Recommended Monitoring (Post-Production)

| Metric | Tool | Alert Threshold |
|--------|------|-----------------|
| API response time | Railway metrics / Datadog | >5s for 5 minutes |
| Error rate | Railway metrics / Sentry | >1% for 10 minutes |
| Active services count | Custom metric | >35 (unexpected spike) |
| Database connections | PostgreSQL stats | >80% of max |
| Memory usage | Railway metrics | >90% for 5 minutes |
| Disk usage | Railway metrics | >80% of allocated |
| Idle session count | Custom metric | >40 (cleanup not working) |

### 16.4 Audit Trail

All administrative actions are logged in `audit_logs` table. Recommended queries:

```sql
-- Recent user creations
SELECT * FROM audit_logs WHERE action = 'user.created' ORDER BY created_at DESC LIMIT 10;

-- API key rotations
SELECT * FROM audit_logs WHERE action = 'user.api_key_rotated' ORDER BY created_at DESC;

-- User deletions
SELECT * FROM audit_logs WHERE action = 'user.deleted' ORDER BY created_at DESC;

-- Failed operations
SELECT * FROM audit_logs WHERE action LIKE '%error%' ORDER BY created_at DESC;
```

---

## 17. Cost Estimation

### 17.1 Railway Hosting Costs (Monthly)

| Component | Specification | Cost/Month |
|-----------|--------------|------------|
| **PostgreSQL** | Pro plan (50GB) | $20 |
| **Redis** | Standard plan | $5 |
| **Orchestrator** | 512MB, 0.5 vCPU | $5 |
| **Adapter** | 512MB, 0.5 vCPU | $5 |
| **Open WebUI** | 2GB, 1 vCPU | $10 |
| **User Services** | 30 x 1GB (12 hrs/day avg) | $130 |
| **User Volumes** | 30 x 5GB | $15 |
| **Network Egress** | ~10GB/month | Included |
| **Buffer (20%)** | | $38 |
| **TOTAL** | | **~$228/month** |

### 17.2 Cost Optimization Strategies

| Strategy | Savings | Complexity |
|----------|---------|------------|
| Reduce idle timeout to 10 min | 15-20% | Low |
| Reduce user service memory to 512MB | 30-40% | Medium (test performance) |
| Pre-warm service pool (10 instances) | 20-30% | High (architectural change) |
| Use Railway hobby plan for base | $10-15 | Low (if eligible) |
| Aggregate small users into shared service | 40-50% | Very High (security trade-off) |

### 17.3 Cost Per User

| Metric | Value |
|--------|-------|
| Total monthly cost | ~$228 |
| Total users | 70 |
| Cost per user per month | ~$3.26 |
| Active users per month (est. 80%) | 56 |
| Cost per active user per month | ~$4.07 |

---

## 18. Risk Assessment

### 18.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Railway API rate limiting | Medium | High | Request queuing, exponential backoff |
| Service spin-up failure | Low | High | Retry logic, fallback to shared service |
| Database connection exhaustion | Medium | High | Connection pooling (PgBouncer) |
| Memory leak in long-running services | Low | Medium | Service recycling (24hr max lifetime) |
| Adapter bottleneck at peak load | Medium | Medium | Horizontal scaling, load balancing |
| Open WebUI compatibility breaking change | Low | Medium | Pin to specific version, test updates |

### 18.2 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Railway pricing changes | Medium | Medium | Multi-cloud deployment option |
| Data loss (no backups) | Low | Critical | Automated PostgreSQL backups |
| Credential leak | Low | Critical | Secret scanning, environment variable rotation |
| User data cross-contamination | Low | Critical | Per-user isolation, integration tests |
| Downtime during deployment | Medium | Low | Rolling deployments, health checks |

### 18.3 Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent Zero license changes | Low | High | Monitor upstream, have fallback LLM |
| Cost exceeds budget | Medium | Medium | Usage monitoring, auto-scaling limits |
| User adoption lower than expected | Medium | Low | Phased rollout, feedback collection |
| Competing internal solutions | Low | Low | Clear value proposition, documentation |

---

## 19. Success Metrics

### 19.1 Key Performance Indicators (KPIs)

| KPI | Target | Measurement |
|-----|--------|-------------|
| User adoption | 70% of registered users active monthly | User activity logs |
| Concurrent capacity | 25-30 users without degradation | Load testing, monitoring |
| Response time | <2s (no spin-up), <120s (with spin-up) | Adapter metrics |
| Service reliability | 99.5% uptime | Railway metrics |
| Cost per user | <$5/month active user | Railway billing / active users |
| Error rate | <1% of requests | Application logs |

### 19.2 User Satisfaction Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| User satisfaction | >4/5 | Post-deployment survey |
| Feature requests | Track and prioritize | Feedback collection |
| Support tickets | <5/week | Admin monitoring |
| Session duration | >15 minutes average | Session tracking |

### 19.3 Technical Health Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Test coverage | >80% | <70% |
| Build success rate | >95% | <90% |
| Deployment frequency | As needed | Failed deployments >2/week |
| Mean time to recovery | <30 minutes | >1 hour |

---

## 20. Appendices

### 20.1 Glossary

| Term | Definition |
|------|-----------|
| **Carbon Agent** | White-labeled name for Agent Zero instances |
| **The Intelligence Hub** | White-labeled name for Open WebUI frontend |
| **Orchestrator** | Management service for users, API keys, and service lifecycle |
| **Adapter** | OpenAI-compatible API translator for Agent Zero |
| **Clerk** | Authentication-as-a-Service platform (user auth, sessions, webhooks) |
| **Railway** | Cloud hosting platform for containerized services |
| **Agent Zero** | Open-source AI agent framework (the actual AI backend) |
| **Spin-Up** | Process of creating a Railway service for a user |
| **Spin-Down** | Process of deleting a Railway service after idle timeout |
| **Session** | Period of user activity, tracked for idle timeout |
| **API Key** | Bearer token for user authentication (format: sk-...) |
| **Webhook** | HTTP callback from Clerk to Orchestrator for user lifecycle events |
| **MAU** | Monthly Active Users (Clerk pricing metric) |
| **JWT** | JSON Web Token (Clerk session token format) |

### 20.2 Environment Variables Reference

#### Orchestrator

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `REDIS_URL` | Yes | - | Redis connection string |
| `RAILWAY_API_TOKEN` | Yes | - | Railway API authentication token |
| `RAILWAY_PROJECT_ID` | Yes | - | Railway project identifier |
| `RAILWAY_TEAM_ID` | Yes | - | Railway team identifier |
| `RAILWAY_ENVIRONMENT_ID` | No | - | Railway environment identifier |
| `ADMIN_AGENT_API_KEY` | Yes | - | Admin API key for protected endpoints |
| `SESSION_IDLE_TIMEOUT_MINUTES` | No | 15 | Minutes before idle session cleanup |
| `SESSION_MAX_LIFETIME_HOURS` | No | 24 | Maximum session duration before recycle |
| `SESSION_SPINUP_TIMEOUT_SECONDS` | No | 120 | Timeout for service spin-up |
| `VOLUME_SIZE_GB` | No | 5 | Size of user volumes in GB |
| `VOLUME_MOUNT_PATH` | No | /data | Mount path for user volumes |
| `AGENT_DOCKER_IMAGE` | No | carbon-agent-adapter:latest | Docker image for user services |
| `AGENT_DEFAULT_MEMORY` | No | 1GB | Default memory allocation |
| `AGENT_DEFAULT_CPU` | No | 1 | Default CPU allocation |

#### Adapter

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `AGENT_API_URL` | Yes | http://localhost:5000 | Agent Zero API endpoint |
| `AGENT_API_KEY` | No | - | Agent Zero API key |
| `MODEL_NAME` | No | carbon-agent | Model name returned to clients |
| `DEFAULT_LIFETIME_HOURS` | No | 24 | Default context lifetime |
| `PORT` | No | 8000 | Server port |
| `HOST` | No | 0.0.0.0 | Server host |

#### Open WebUI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_BASE_URL` | Yes | - | Adapter API URL |
| `OPENAI_API_KEY` | Yes | - | API key for adapter (auto-injected by Clerk) |
| `WEBUI_SECRET_KEY` | Yes | - | WebUI encryption key |

#### Clerk

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLERK_SECRET_KEY` | Yes | - | Clerk backend API secret key |
| `CLERK_PUBLISHABLE_KEY` | Yes | - | Clerk frontend publishable key |
| `CLERK_WEBHOOK_SECRET` | Yes | - | Webhook HMAC verification secret |
| `CLERK_JWT_AUTHORIZED_ORIGINS` | Yes | - | Allowed origins for JWT validation |
| `CLERK_ADMIN_ROLE_ID` | No | admin | Clerk role ID for admin access |
| `CLERK_API_URL` | No | https://api.clerk.com/v1 | Clerk API base URL |

### 20.3 API Key Format

```
Format: sk-{48_hex_characters}
Example: sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234
Length: 50 characters total (3 prefix + 48 random)
Generation: secrets.token_hex(24)
```

### 20.4 Railway GraphQL API Reference

The platform uses Railway's GraphQL API for service management. Key operations:

| Operation | Mutation/Query | Description |
|-----------|---------------|-------------|
| Create service | `serviceCreate` | Create new Railway service |
| Delete service | `serviceDelete` | Delete Railway service |
| Get service | `service(id)` | Query service details |
| List services | `project(id).services` | List all services in project |
| Create volume | `volumeCreate` | Create new Railway volume |
| Delete volume | `volumeDelete` | Delete Railway volume |
| Get volume | `volume(id)` | Query volume details |
| Set env vars | `serviceVariablesUpsert` | Update service environment |
| Redeploy service | `serviceRedeploy` | Trigger new deployment |

### 20.5 File Structure

```
carbon-agent-platform/
├── .env.example                          # Development environment template
├── .env.production.example               # Production environment template
├── .gitignore                            # Git ignore rules
├── docker-compose.yml                    # Docker Compose configuration
├── Dockerfile.production                 # Multi-stage production Dockerfile
├── Makefile                              # Build and deployment commands
├── railway.json                          # Railway deployment configuration
├── README.md                             # Project documentation
├── TASKS.md                              # Task tracking document
├── PRD.md                                # Product Requirements Document (this file)
│
├── orchestrator/                         # Orchestrator service
│   ├── Dockerfile                        # Orchestrator Docker image
│   ├── requirements.txt                  # Python dependencies
│   ├── pytest.ini                        # Pytest configuration
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI application entry point
│   │   ├── config.py                     # Pydantic settings
│   │   ├── database.py                   # SQLAlchemy engine & sessions
│   │   ├── models.py                     # ORM models (User, AuditLog)
│   │   ├── schemas.py                    # Pydantic request/response schemas
│   │   ├── admin.py                      # Admin API endpoints
│   │   ├── users.py                      # User API endpoints
│   │   ├── railway.py                    # Railway GraphQL client
│   │   ├── session_manager.py            # Session management & service lifecycle
│   │   ├── clerk.py                      # Clerk webhook handler & auth middleware (NEW - Task 11)
│   │   └── clerk_admin.py                # Clerk-protected admin endpoints (NEW - Task 11)
│   └── tests/
│       ├── conftest.py                   # Test fixtures
│       ├── test_models.py                # Model tests
│       ├── test_admin.py                 # Admin API tests
│       ├── test_users.py                 # User API tests
│       ├── test_railway.py               # Railway client tests
│       ├── test_session_manager.py       # Session manager tests
│       └── test_clerk.py                 # Clerk webhook & auth tests (NEW - Task 11)
│
├── adapter/                              # Adapter service
│   ├── Dockerfile                        # Adapter Docker image
│   ├── requirements.txt                  # Python dependencies
│   └── app/
│       ├── __init__.py
│       ├── main.py                       # FastAPI application entry point
│       ├── config.py                     # Pydantic settings
│       ├── database.py                   # Database connection
│       ├── models.py                     # Shared ORM models
│       ├── schemas.py                    # OpenAI-compatible schemas
│       ├── auth.py                       # API key authentication
│       ├── agent_client.py               # Agent Zero HTTP client
│       └── streaming.py                  # SSE streaming implementation
│   └── tests/
│       ├── test_main.py                  # Main app tests
│       ├── test_auth.py                  # Authentication tests
│       ├── test_schemas.py               # Schema tests
│       └── test_streaming.py             # Streaming tests
│
├── open-webui/                           # Open WebUI configuration
│   ├── config.json                       # White-label configuration
│   ├── setup.sh                          # Setup script
│   └── clerk-middleware.js               # Clerk auth + API key injection (NEW - Task 11)
│
├── admin-dashboard/                      # Admin Dashboard UI (NEW - Task 11)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                       # FastAPI admin dashboard
│   │   ├── templates/                    # HTML templates
│   │   └── static/                       # CSS/JS assets
│   └── tests/
│       └── test_admin_dashboard.py
│
├── tests/                                # Integration tests
│   ├── conftest.py                       # Shared fixtures
│   └── test_integration.py               # End-to-end tests
│
└── scripts/                              # Deployment scripts
    ├── deploy.sh                         # Railway deployment script
    └── setup-clerk.sh                    # Clerk setup script (NEW - Task 11)
```

### 20.6 Known Issues & Technical Debt

| Issue | Component | Severity | Fix Priority | Description |
|-------|-----------|----------|--------------|-------------|
| Session cleanup broken | Session Manager | Critical | Task 9 | Cleanup task cannot spin down idle users (no DB session) |
| CORS allows all origins | Orchestrator | Critical | Before prod | `allow_origins=["*"]` with credentials is dangerous |
| API key in all responses | Schemas | Critical | Before prod | API key exposed in every UserResponse |
| No rate limiting | Both services | High | Task 10 | No protection against API abuse |
| Python 3.14 compatibility | Models | Medium | Before prod | `str | None` syntax causes SQLAlchemy errors |
| Adapter Dockerfile missing curl | Docker | Medium | Before prod | Health check will fail |
| Duplicate TASKS.md sections | Documentation | Low | Low | "Done" section duplicated |
| No Alembic migrations | Database | Medium | Task 9 | Schema changes not versioned |
| Test database files in repo | Git | Low | Low | `test.db`, `test_users.db` not in .gitignore |
| Admin key in plain text | Security | Medium | Mitigated by Clerk | X-Admin-Key for automation; Clerk for human admins |
| **Clerk integration not started** | Architecture | High | Task 11 | Major feature addition, transforms auth model |
| No Alembic migrations | Database | Medium | Task 9 | Schema changes not versioned |
| Test database files in repo | Git | Low | Low | `test.db`, `test_users.db` not in .gitignore |
| Admin key in plain text | Security | Medium | Future | Should be hashed with bcrypt |

### 20.7 Change Log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-04-16 | 2.0 | Initial PRD creation | AI Assistant |
| 2026-04-16 | 2.0 | Tasks 1-6 completed | Development Team |

### 20.8 References

- **Agent Zero**: https://github.com/frdel/agent-zero
- **Open WebUI**: https://github.com/open-webui/open-webui
- **Railway**: https://railway.app/
- **Clerk**: https://clerk.com/
- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy**: https://www.sqlalchemy.org/
- **Pydantic**: https://docs.pydantic.dev/
- **Docker**: https://www.docker.com/
- **PostgreSQL**: https://www.postgresql.org/
- **Redis**: https://redis.io/

---

### 20.9 Change Log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-04-16 | 2.0 | Initial PRD creation | AI Assistant |
| 2026-04-16 | 2.0 | Tasks 1-6 completed | Development Team |
| 2026-04-16 | 2.1 | Added Clerk integration architecture (Task 11) | AI Assistant |
| 2026-04-16 | 2.1 | Updated architecture diagrams with Clerk layer | AI Assistant |
| 2026-04-16 | 2.1 | Added Clerk webhook specifications | AI Assistant |
| 2026-04-16 | 2.1 | Updated security section with Clerk benefits | AI Assistant |
| 2026-04-16 | 2.1 | Updated user journeys with Clerk flows | AI Assistant |
| 2026-04-16 | 2.1 | Added database schema changes (clerk_user_id) | AI Assistant |

---

**Document End**

*This PRD is a living document and should be updated as the product evolves. Last updated: April 16, 2026. Version: 2.1*
