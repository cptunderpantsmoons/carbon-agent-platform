# Corporate Carbon Intelligence Hub v2.0 Master Implementation Spec

> **Version:** 2.0.0  
> **Date:** 2026-04-20  
> **Scope:** Full transformation across `carbon-agent-dashboard`, `contract-hub`, and `carbon-agent-platform`  
> **Baseline:** Pass 1 complete (Clerk auth, model policy backend, dashboard shell, BFF proxying)

---

## 1. Locked Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| L1 | Replace Agent Zero with `pydantic-ai` as primary runtime | Typed deps, structured outputs, MCP first-class, durable execution ready |
| L2 | OpenAI Python SDK as transport layer | Responses API native, compatible with Featherless/DeepSeek via base_url |
| L3 | Keep `contract-hub` as separate deployable | No backend merge in this phase; UX-only alignment to suite taste |
| L4 | v2 IA: Dashboard, Chat, Benchmarks, Contracts, Documents, Skills, Admin | Promote all existing routes into canonical suite nav |
| L5 | Clerk remains real auth provider in both Next.js apps | No auth mock reintroduction; middleware stays `clerkMiddleware()` |
| L6 | `pydantic-ai` + MCP as agent/tooling layer | Canonical tool execution path; keyword augmentation retired |
| L7 | DBOS as durable execution backend | Postgres-centric, pydantic-ai documents first-class wrapping |
| L8 | OpenAI Responses API by default | Chat Completions compatibility only for transition passthroughs |
| L9 | Open WebUI retired as default shell | Retain as fallback/admin-only; patch Dockerfile digest before keeping |

---

## 2. Baseline State (April 20, 2026)

### 2.1 Repositories

```
carbon-agent-platform/       # Backend + infra (this repo)
  adapter/app/               # FastAPI - currently routes to Agent Zero or cloud LLM
  orchestrator/app/          # FastAPI - Clerk webhooks, model policy, session manager
  open-webui/                # Fallback shell (to be patched and retained)
  docker-compose.yml         # Full stack compose
carbon-agent-dashboard/      # Next.js App Router - Intelligence Hub shell (Pass 1 complete)
contract-hub/                # Next.js App Router - Legal ops platform (light slate theme)
```

### 2.2 Verified Existing (Pass 1)

- `middleware.ts` uses `clerkMiddleware()`
- `layout.tsx` has `<ClerkProvider>` inside `<body>`
- `provision_user_background()` exists in `session_manager.py`
- `temperature_detector.py` wired in adapter
- Integration tests: `tests/integration/test_onboarding.py`, `test_lifecycle.py`
- Model policy CRUD exists in orchestrator

### 2.3 Agent Zero Reference Inventory

| File | Reference | Action |
|------|-----------|--------|
| `adapter/app/agent_client.py` | `AgentClient` class, `/api_message` endpoint | **Remove** after parity |
| `adapter/app/llm_provider.py` | `AgentZeroProvider` class | **Remove** after parity |
| `adapter/app/config.py` | `agent_api_url`, `agent_api_key`, `agent_domain`, `default_lifetime_hours`, `default_project_name` | **Deprecate** → remove after cutover |
| `adapter/app/main.py` | `AgentClient` import, `_get_agent_base_url()`, agent-zero routing branch | **Replace** with pydantic-ai runtime |
| `adapter/app/context_store.py` | Redis-backed context_id storage for Agent Zero | **Replace** with explicit conversation state |
| `orchestrator/app/docker_manager.py` | Docker container lifecycle for per-user Agent Zero | **Keep** for legacy container management during transition |
| `orchestrator/app/session_manager.py` | `ensure_user_service()` spins up Agent Zero containers | **Keep** during transition; adapt for new runtime later |
| `docker-compose.yml` | `AGENT_API_URL`, `AGENT_API_KEY`, `AGENT_DOMAIN`, `AGENT_DOCKER_IMAGE` | **Clean** in Wave 5 |
| `.env.example` | `AGENT_API_URL`, `AGENT_API_KEY`, `MODEL_NAME` (legacy) | **Clean** in Wave 5 |
| `adapter/tests/test_llm_provider.py` | `AgentZeroProvider` tests | **Rewrite** after parity |
| `adapter/tests/test_main.py` | Agent Zero routing tests | **Rewrite** after parity |
| `docs/AGENTS.md` | Agent Zero setup instructions | **Archive** after cutover |

### 2.4 Environment Inventory

**Dashboard (`carbon-agent-dashboard`)**
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `CARBON_ORCHESTRATOR_URL`
- `CARBON_ADAPTER_URL`
- `ADMIN_AGENT_ENABLED`, `ADMIN_AGENT_CONTROL_TOKEN`, etc.
- ✅ **No provider keys** in dashboard env (already fixed in Pass 1)

**Platform (`carbon-agent-platform`)**
- Adapter: `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME`
- Adapter legacy: `AGENT_API_URL`, `AGENT_API_KEY`, `AGENT_DOMAIN`
- Orchestrator: `CLERK_*`, `DATABASE_URL`, `REDIS_URL`, `AGENT_DOCKER_IMAGE`
- Contract Hub bridge: `CONTRACT_HUB_TENANT_ID`, `RAG_FIXED_TENANT_ID`

**Contract Hub (`contract-hub`)**
- `DATABASE_URL` (SQLite fallback in dev, Postgres in prod)
- `CLERK_SECRET_KEY`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`
- `CARBON_RAG_BASE_URL`, `CARBON_RAG_TENANT_ID`
- `DOCASSEMBLE_URL`, `DOCASSEMBLE_API_KEY`
- `OPENCODE_SERVER_URL`, `OPENCODE_API_KEY`

---

## 3. Target Architecture

### 3.1 Agent Runtime (Adapter)

```
adapter/app/
  runtime/
    __init__.py
    agents.py          # pydantic-ai agent factories (chat, benchmark, task)
    dependencies.py    # Typed dependency containers
    tools.py           # MCP + custom tool registration
    state.py           # Conversation/session state (Redis/Postgres)
    providers.py       # OpenAI SDK provider wrappers
    responses.py       # Responses API request/response models
    normalize.py       # Response normalization (internal -> stable payload)
  main.py              # FastAPI app - compatibility + new paths
```

### 3.2 Normalized Internal Models

**Request (`adapter/app/runtime/responses.py`)**
```python
class AgentExecutionRequest(BaseModel):
    user_id: str
    tenant_id: str = "default"
    conversation_id: str | None = None
    routing_mode: Literal["auto", "force_premium", "block_premium"] = "auto"
    provider: str | None = None          # "openai", "featherless", "deepseek", "anthropic"
    model: str | None = None
    task_type: Literal["chat", "benchmark", "task"] = "chat"
    temperature: float | None = None
    tool_policy: Literal["auto", "disabled", "require_approval"] = "auto"
    messages: list[ChatMessage] | None = None
    input_items: list[dict] | None = None   # Responses API style
```

**Result (`adapter/app/runtime/responses.py`)**
```python
class AgentExecutionResult(BaseModel):
    output_text: str
    structured_output: dict | None = None
    tool_calls: list[ToolCallResult]
    citations: list[Citation]
    latency_ms: int
    token_usage: TokenUsage
    provider: str
    model: str
    conversation_id: str
    trace_id: str
```

### 3.3 Frontend Suite IA

```
carbon-agent-dashboard/
  app/
    page.tsx                 # Landing (AIDA, suite positioning)
    dashboard/page.tsx       # Hub overview
    chat/page.tsx            # Chat workspace
    benchmarks/page.tsx      # Benchmark lab
    documents/page.tsx       # Document hub
    skills/page.tsx          # Skills registry
    admin/page.tsx           # Policy, audit, ops
    contracts/page.tsx       # Entry surface to Contract Hub
```

**Nav order:** Dashboard, Chat, Benchmarks, Contracts, Documents, Skills, Admin

---

## 4. Execution Waves

### Wave 0: Baseline (This Spec)
- [x] Freeze architecture decisions
- [x] Create master tracking document
- [x] Inventory Agent Zero references
- [x] Audit dashboard and Contract Hub routes
- [x] Record env/contracts

### Wave 1: Agent Runtime Replacement
1. Add `pydantic-ai`, `openai>=1.75`, `dbos` to `adapter/requirements.txt`
2. Create `adapter/app/runtime/` submodule
3. Define `dependencies.py` with typed containers:
   - `UserContext` (user_id, tenant_id, api_key)
   - `TenantContext` (tenant_id, policy)
   - `ModelPolicyContext` (routing_mode, allowed_providers, default_provider)
   - `ToolRegistryContext` (available tools, approval gates)
   - `ObservabilityContext` (trace_id, request_id, logger)
4. Implement `providers.py`:
   - `OpenAIProvider` (native Responses API)
   - `OpenAICompatibleProvider` (Featherless, DeepSeek via base_url)
   - `AnthropicAdapter` (translation layer, keep existing)
5. Implement `agents.py` factories:
   - `create_chat_agent()` - general Hub chat
   - `create_benchmark_agent()` - single-run evaluation
   - `create_task_agent()` - MCP/tool-enabled workflows
6. Implement `state.py` - explicit conversation storage keyed by `(user_id, conversation_id)` in Redis/Postgres
7. Implement `normalize.py` - stable payload shape regardless of provider
8. Replace `AgentClient`-driven flow in `main.py`:
   - Keep `/v1/chat/completions` as compatibility surface
   - Add new internal execution path (`POST /v1/agent/run`)
9. Move temperature selection to runtime-level model settings composition
10. Deprecate Agent Zero config fields; add temporary aliases

### Wave 2: Policy, Tooling, MCP
1. Update adapter to fetch model policy from orchestrator before run creation
2. Pass resolved provider into `pydantic-ai` model selection
3. Replace keyword MCP augmentation with explicit tool registration:
   - obot tools via MCP gateway
   - `accu_mcp_server`
   - `n8n_workflow`
   - Future: `accu_graphrag_query`, `fullcam_query`, `ep_forecast`
4. Add approval boundaries for sensitive tool calls (legal, financial, regulatory, CER)
5. Emit structured traces with: user_id, tenant_id, conversation_id, trace_id, agent_name, provider, model, duration_ms
6. Design DBOS durability boundaries:
   - Wrap long-running agent runs
   - Wrap MCP communication steps
   - Decorate non-deterministic I/O tools

### Wave 3: Dashboard to Intelligence Hub Shell
1. Refactor folder conventions:
   - Move `app/components/shell/` to `components/shell/`
   - Add `lib/` for BFF calls, model catalog, policy handling
2. Add suite-grade screens:
   - `/dashboard` - recent sessions, benchmark summary, policy badge, provider health, contracts CTA
   - `/chat` - model/provider selector, routing badge, streaming/thread UX, citations
   - `/benchmarks` - multi-run config, results matrix, cost/latency/tokens, export
   - `/documents` - promoted first-class
   - `/skills` - promoted first-class
   - `/admin` - provider/routing/policy management, audit views
3. Add `/contracts` route as first-class entry to Contract Hub
4. Update landing page copy for suite positioning
5. Align to carbon void editorial taste (dark theme, see Wave 4 design contract)

### Wave 4: Contract Hub UX Pass
1. Keep backend, Clerk, routes intact
2. Rewrite design system to match suite-aligned visual family:
   - Dark void background (`--carbon-void: #0a0a0b`)
   - Warm editorial accent (`--accent: #e8e4dc`)
   - Geist typography, mono labels, massive spacing
3. Redesign tier-1 screens:
   - Landing/sign-in
   - Dashboard home
   - Contracts list/detail
   - Documents list/detail/edit/sign
   - Approvals, Matters, Settings
4. Add suite-consistent shell: nav rhythm, title framing, status semantics, table/form patterns
5. Add explicit return paths between Hub and Contract Hub

### Wave 5: Security, Compose, Deployment
1. Remove provider API keys from dashboard service env in all compose variants
2. Verify dashboard only receives: Clerk keys, orchestrator URL, adapter URL, admin-agent config
3. Refresh `open-webui/Dockerfile` to current safe digest
4. Rename dashboard service concepts to "hub-ui" where safe
5. Remove obsolete Agent Zero env/config keys
6. Update `.env.example` and production examples
7. Validate production boot-time config checks
8. Ensure non-root, digest pinning, health checks intact

### Wave 6: Validation, Parity, Observability
1. Audit integration tests against current validation assertions
2. Expand coverage:
   - Clerk sign-up → provisioning
   - Idempotent webhook handling
   - Invalid webhook rejection
   - Adapter chat E2E through policy + provider
   - MCP enabled/disabled graceful behavior
   - API key rotation
   - User deletion propagation
3. Add structured logging with request context
4. Add Prometheus metrics endpoint
5. Run full validation suite

---

## 5. Design Contract (Suite-Wide)

### 5.1 Color Tokens

```css
--carbon-void: #0a0a0b
--carbon-surface: #131315
--carbon-deep: #1a1a1d
--carbon-border: #2a2a2e
--text-primary: #f0f0f5
--text-secondary: #a0a0ab
--text-tertiary: #6b6b78
--accent: #e8e4dc
--status-success: #4ade80
--status-warning: #facc15
--status-error: #f87171
```

### 5.2 Typography

- Headings: Geist, 600 weight, `tracking-tight`, max 4 lines
- Body: Geist, 400 weight, `leading-relaxed`, max 6 lines
- Labels: Geist Mono, uppercase, `tracking-[0.2em]`, `text-xs`

### 5.3 Spacing

- Page padding: `px-8 py-12` desktop, `px-4 py-8` mobile
- Section gap: `gap-8` minimum
- Card padding: `p-6`

### 5.4 Motion

- Page transitions: opacity + translateY(12px), 0.3s, power2.out
- Sidebar collapse: width tween, `will-change: transform`
- Cards: staggered entrance 0.05s per card
- Chat messages: translateY(8px) + opacity on append
- **Hardware accel only:** transform + opacity

### 5.5 Shell Behaviors

- Persistent sidebar (240px expanded / 64px collapsed)
- Top bar: page title + global search + user button
- Status badges: mono uppercase, tight tracking
- Tables: border-based separation, no external shadows
- Forms: 1px border, focus:border-accent, bg-transparent

---

## 6. Constraints & Non-Goals

- **No Contract Hub backend migration** - UX-only in this phase
- **No real-time collaboration** (cursors, live typing) - Pass 3
- **No mobile-native app** - responsive web only
- **No billing/subscription UI** - backend-only
- **No shared npm package** in this phase - copy primitives by documentation

---

## 7. Success Criteria

| Criterion | Target |
|-----------|--------|
| Agent Zero runtime fully replaced | `/v1/chat/completions` routes through pydantic-ai |
| Model policy enforced end-to-end | Orchestrator policy → adapter provider selection → execution |
| MCP tools registered explicitly | No keyword-based augmentation remains |
| Dashboard v2 IA complete | 7 top-level nav items, all functional |
| Contract Hub visual family aligned | Dark theme, same tokens, separate app feel |
| All Agent Zero env keys removed | `.env.example` clean, compose clean |
| Integration tests passing | >80% coverage of critical paths |
| Production config validates | Boot-time checks pass with new vars |
