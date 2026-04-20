# Corporate Carbon Intelligence Hub — Pass 1 Design Spec

> **Pass 1: Rectification + Rebrand + Foundation**
> **Date:** 2026-04-20
> **Scope:** Auth fix, middleware fix, Carbon backend integration, QoderWork-branded UI with gpt-taste design system, model policy backend, tests.
> **Out of scope:** Knowledge base (RAG), collaboration spaces, ACCU dashboards, HR modules — these are Pass 2+.

---

## 1. Context & Problem Statement

The existing `carbon-agent-dashboard` is deployed and functional at `:3001/dashboard`, but has critical architectural and security flaws:

1. **Fake Clerk auth** — `app/lib/clerk.tsx` mocks all Clerk components; anyone can access the dashboard.
2. **No-op middleware** — `middleware.ts` does not use `clerkMiddleware()`; zero route protection.
3. **Chat bypasses Carbon backend** — `provider-exec.js` hits LLM providers directly with env vars instead of proxying through the Carbon adapter.
4. **No backend model policy** — Routing mode (`auto`/`block_premium`/`force_premium`) is client-side only; orchestrator has no policy concept.
5. **Zero tests** — No smoke, API, integration, or E2E tests exist.
6. **31KB monolith** — `intelligence-hub.tsx` contains all UI logic in one file.

This spec defines the rectification and rebrand to transform the dashboard into the **Corporate Carbon Intelligence Hub**: the primary user-facing shell for the Carbon Agent Platform, replacing Agent Zero and Open WebUI.

---

## 2. Architecture & Auth

### 2.1 Clerk Integration (Real Auth)

- `middleware.ts` uses `clerkMiddleware()` from `@clerk/nextjs/server` — protects all routes except static assets.
- `layout.tsx` imports from `@clerk/nextjs` (not the fake fallback).
- `CLERK_SECRET_KEY` added to dashboard Docker service environment.
- Admin routes (`/admin`) use `auth()` + `sessionClaims?.metadata?.role === "admin"` — returns 403 for non-admins.

### 2.2 Auth Flow

```
User → clerkMiddleware() → signed-in? → yes → route handler
                                    → no → redirect to / (landing with SignIn modal)
```

### 2.3 Route Protection Map

| Route | Auth Required | Admin Required |
|---|---|---|
| `/` | No | No |
| `/dashboard`, `/chat`, `/benchmarks` | Yes | No |
| `/admin` | Yes | Yes |

### 2.4 Backend Model Policy Enforcement

- New `orchestrator/app/model_policy.py` — stores policy in DB.
- Policy fields: `routing_mode` (`auto` | `force_premium` | `block_premium`), `default_provider`, `allowed_providers[]`.
- Chat proxy in dashboard reads policy from orchestrator before forwarding to adapter.
- Adapter validates provider against policy before executing.

---

## 3. Page Structure & Navigation

### 3.1 Navigation Pattern: Persistent Sidebar + Top Bar

- **Left sidebar** (collapsible, 240px expanded / 64px collapsed) — primary navigation with icon + label.
- **Top bar** — page title, global search, user button (Clerk `<UserButton />`), dev-auth badge if fallback.
- **Main content** — massive padding (`px-8 py-10`), gapless bento-grid cards on hub, full-bleed workspaces on focused pages.

### 3.2 Sidebar Nav Items

```
/dashboard     → Hub (overview cards, quick stats)
/chat          → Chat Workspace (model selector, thread, composer)
/benchmarks    → Benchmark Lab (prompt input, side-by-side table)
/admin         → Admin Controls (policy, model catalog, audit)
```

### 3.3 Page Layouts

| Page | Layout | Key Elements |
|---|---|---|
| `/dashboard` | Bento grid (2-col desktop, 1-col mobile) | Recent chat snippets, benchmark summary card, active policy badge, provider health status, "New Chat" CTA |
| `/chat` | Full workspace (sidebar threads list + main chat area) | Model/provider selector in top bar, message thread with code block rendering, multiline composer with send |
| `/benchmarks` | Split pane (left: prompt + config, right: results table) | Provider/model multi-select, temperature slider, run button, comparison table with latency badges |
| `/admin` | Settings-style stacked sections | Routing mode radio group, allowed providers checklist, default provider dropdown, model catalog table |

### 3.4 Responsive Behavior

- Sidebar collapses to icon-only at `< 1024px`.
- At `< 768px`, sidebar becomes a bottom sheet / drawer.
- Chat workspace stacks vertically (thread above composer).

### 3.5 URL Deep-Linking

- Every page is a real App Router page with `page.tsx`.
- Chat threads eventually get `/chat?thread=abc123` (Pass 2).
- Benchmark runs get shareable `/benchmarks?run=xyz789` (Pass 2).

---

## 4. Backend Integration

### 4.1 Chat Proxy (`/api/chat`)

```ts
POST /api/chat
Body: { model, messages, temperature?, max_tokens?, stream? }
```

Flow:
1. Dashboard `route.ts` receives request.
2. Fetches user's model policy from `orchestrator:8000/admin/model-policy`.
3. Validates requested provider/model against policy (e.g., `block_premium` rejects OpenAI/Anthropic).
4. Forwards to `adapter:8000/v1/chat/completions` with user's API key injected by adapter middleware.
5. Returns streaming response to UI.

### 4.2 Model Policy API (Orchestrator)

```
GET  /admin/model-policy        → Read policy (admin only)
PUT  /admin/model-policy        → Update policy (admin only)
GET  /v1/model-policy/me        → Read own policy (any signed-in user)
```

### 4.3 Policy Schema (Orchestrator DB)

```python
class ModelPolicy(Base):
    id: str (PK)
    tenant_id: str (index)          # "default" for now, per-org in Pass 2
    routing_mode: str               # "auto" | "force_premium" | "block_premium"
    default_provider: str           # "featherless" | "deepseek" | ...
    allowed_providers: list[str]    # ["featherless", "deepseek"]
    benchmark_mode: bool            # enable benchmark comparisons
    created_at, updated_at
```

### 4.4 Benchmark Proxy (`/api/benchmarks`)

- Dashboard receives `{ prompt, runs[] }`.
- For each run, calls adapter directly (bypasses policy since admin triggers benchmarks).
- Returns `{ prompt, results[] }` with latency, token count, success/failure.

### 4.5 Admin Agent (`/api/admin-agent`)

- Keep existing SSH-based admin agent but move token check to middleware layer.
- Restrict to `/admin` page only.

### 4.6 Error Handling

- Policy violation → `403` with `{ error: "Provider blocked by policy" }`.
- Adapter unavailable → `503` with retry prompt.
- Auth failure → `401` from clerkMiddleware.

---

## 5. UI Design System (GPT-Taste + Carbon)

### 5.1 Design Philosophy

Fuse the existing dark industrial-brutalist surface (rigid grids, carbon void, utilitarian color) with `gpt-taste` editorial motion principles. The result: a dashboard that feels like a declassified operations terminal rebuilt by a high-end editorial studio.

### 5.2 Color Palette

```css
--carbon-void: #0a0a0b        /* Deep black, page background */
--carbon-surface: #131315     /* Card/panel background */
--carbon-deep: #1a1a1d        /* Elevated sections */
--carbon-border: #2a2a2e      /* Subtle dividers */
--text-primary: #f0f0f5       /* Near-white headings */
--text-secondary: #a0a0ab     /* Muted body text */
--text-tertiary: #6b6b78      /* Labels, captions */
--accent: #e8e4dc             /* Warm editorial accent (not neon) */
--success: #4ade80
--warning: #facc15
--error: #f87171
```

### 5.3 Typography (Editorial Wide)

- Headings: `Geist` (already installed), `font-weight: 600`, tight tracking (`tracking-tight`).
- Body: `Geist`, `font-weight: 400`, generous line-height (`leading-relaxed`).
- Labels: `Geist Mono`, `uppercase`, `tracking-[0.2em]`, `text-xs`.
- **Rule:** No heading exceeds 4 lines; no body paragraph exceeds 6 lines (gpt-taste wrap ban).

### 5.4 Spacing (Massive Sections)

- Page padding: `px-8 py-12` (desktop), `px-4 py-8` (mobile).
- Section gap: `gap-8` minimum between major regions.
- Card internal padding: `p-6` (generous breathing room).

### 5.5 Bento Grid (Gapless)

- Dashboard cards use CSS Grid with `gap-0` and internal borders (`border-r`, `border-b`) to create seamless tile surfaces.
- Cards have no external shadow; depth comes from surface elevation (`--carbon-surface` vs `--carbon-deep`).

### 5.6 Motion (GSAP + Hardware Acceleration)

- Page transitions: `opacity` + `translateY(12px)` fade-in, `duration: 0.3`, `ease: power2.out`.
- Sidebar collapse: `width` tween with `will-change: transform`.
- Dashboard cards: staggered entrance `0.05s` per card on load.
- Chat messages: `translateY(8px)` + `opacity` on new message append.
- **No layout thrashing:** All animations use `transform` and `opacity` only.

### 5.7 Component Primitives

```tsx
<Card />          /* gapless bento tile, border-based separation */
<Button />        /* minimal border, hover:bg-carbon-deep, no radius inflation */
<Input />         /* 1px border, focus:border-accent, bg-transparent */
<Select />        /* native-styled custom, monochrome */
<Badge />         /* mono uppercase, tight tracking */
```

---

## 6. Component Structure

```
carbon-agent-dashboard/
├── app/
│   ├── layout.tsx              # ClerkProvider, sidebar shell, top bar
│   ├── page.tsx                # Landing (AIDA marketing shell)
│   ├── globals.css             # CSS vars, base styles
│   ├── middleware.ts           # clerkMiddleware()
│   ├── dashboard/
│   │   └── page.tsx            # Hub overview (bento grid)
│   ├── chat/
│   │   └── page.tsx            # Chat workspace
│   ├── benchmarks/
│   │   └── page.tsx            # Benchmark lab
│   ├── admin/
│   │   └── page.tsx            # Admin controls
│   └── api/
│       ├── chat/route.ts
│       ├── benchmarks/route.ts
│       ├── orchestrator/[...path]/route.ts
│       └── admin-agent/route.ts
├── components/
│   ├── shell/
│   │   ├── sidebar.tsx         # Persistent nav, collapsible
│   │   ├── top-bar.tsx         # Title, search, user button
│   │   └── page-wrapper.tsx    # Animated page transition wrapper
│   ├── ui/                     # Primitives (card, button, input, select, badge)
│   ├── chat/
│   │   ├── model-selector.tsx
│   │   ├── message-thread.tsx
│   │   └── composer.tsx
│   ├── benchmarks/
│   │   ├── prompt-panel.tsx
│   │   └── results-table.tsx
│   └── admin/
│       ├── policy-form.tsx
│       └── model-catalog-table.tsx
└── lib/
    ├── clerk.ts                # Re-exports from @clerk/nextjs (no fallback)
    ├── carbon-client.ts        # Orchestrator/adapter HTTP helpers
    └── model-catalog.ts        # Client-side catalog + tier logic
```

**Key Boundary:** `intelligence-hub.tsx` (31KB monolith) is **deleted**. Its logic is split into page components and reusable sub-components.

---

## 7. Testing Strategy

| Test Type | File | What It Verifies |
|---|---|---|
| **Smoke** | `tests/smoke/auth.spec.ts` | Clerk sign-in flow, route protection, admin gate |
| **API** | `tests/api/chat-route.spec.ts` | Chat proxy forwards to adapter, policy enforcement |
| **API** | `tests/api/benchmarks.spec.ts` | Benchmark suite runs, handles failures gracefully |
| **API** | `tests/api/admin-agent.spec.ts` | Token auth rejects bad tokens, accepts good ones |
| **Integration** | `orchestrator/tests/test_model_policy.py` | Policy CRUD, enforcement on chat completion |
| **E2E** | `tests/e2e/onboarding.spec.ts` | Sign up → dashboard → chat → send message |

**Tools:** Playwright for E2E, `vitest` for unit, `pytest` for orchestrator.

---

## 8. Deployment & Docker

### 8.1 Dashboard Service Changes

- Add `CLERK_SECRET_KEY` to `docker-compose.yml` dashboard env.
- Keep `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.
- Remove `FEATHERLESS_API_KEY`, `OPENAI_API_KEY`, etc. from dashboard (moved to adapter/orchestrator).
- Add `CARBON_ADAPTER_URL`, `CARBON_ORCHESTRATOR_URL` env vars.

### 8.2 Build Verification

```bash
docker compose build dashboard
docker compose up -d
curl -f http://localhost:3001/health
curl -f http://localhost:3001/api/health
```

### 8.3 Contract Hub Isolation

- No changes to `contract-hub/` service, Dockerfile, or routes.
- Contract Hub remains on its own port/context.

---

## 9. Long-Term Vision (Pass 2+)

The full Corporate Carbon Intelligence Hub includes 24 features across 6 domains (see `intelligence_hub_features.html`). Pass 1 builds the foundation that enables these:

| Pass 2 Feature | Pass 1 Foundation |
|---|---|
| Document hub / AI Q&A | Chat workspace + orchestrator proxy |
| Shared knowledge base (RAG) | Auth system + backend integration |
| Collaboration spaces | Clerk orgs + page structure |
| ACCU project dashboard | Admin controls + policy system |
| Task board / Agent queue | Component system + API patterns |
| Executive dashboard | Bento grid + data visualization primitives |

---

## 10. Constraints & Non-Goals

- **Contract Hub is immutable** for this pass.
- **Agent Zero and Open WebUI are retired** — no migration paths needed.
- **No real-time collaboration** (cursors, live typing) — Pass 3.
- **No mobile-native app** — responsive web only.
- **No billing/subscription UI** — remains backend-only.
