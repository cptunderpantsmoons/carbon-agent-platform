# Intelligence Hub MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a custom Intelligence Hub web app by morning that replaces Open WebUI as the primary shell, keeps the Carbon backend intact, and gives admins a first pass at model-policy and benchmarking controls.

**Architecture:** The existing Carbon backbone stays in place: Clerk auth, orchestrator, adapter, Redis, PostgreSQL, vector/RAG, Contract Hub, and deploy tooling. The new `hub-ui` app becomes the front door on port `3000`, talks to Carbon through same-origin proxy routes, and exposes three initial areas: chat, admin policy, and benchmark comparison. Open WebUI remains as a fallback profile only, not the default path.

**Tech Stack:** Next.js App Router, Clerk, TypeScript, React, route handlers, Docker Compose, FastAPI backend endpoints, Playwright smoke tests.

---

### Task 1: Create the custom `hub-ui` app shell

**Files:**
- Create: `hub-ui/package.json`
- Create: `hub-ui/next.config.ts`
- Create: `hub-ui/middleware.ts`
- Create: `hub-ui/app/layout.tsx`
- Create: `hub-ui/app/page.tsx`
- Create: `hub-ui/app/chat/page.tsx`
- Create: `hub-ui/components/app-shell.tsx`
- Create: `hub-ui/components/sidebar.tsx`
- Create: `hub-ui/components/topbar.tsx`
- Create: `hub-ui/app/globals.css`
- Test: `hub-ui/tests/smoke/home.spec.ts`

- [ ] **Step 1: Scaffold the app and lock the project shape**

Run:

```bash
cd hub-ui
npx create-next-app@latest . --ts --eslint --app --src-dir=false --import-alias="@/*" --use-pnpm --yes
```

Expected: a Next.js App Router app with `app/`, `package.json`, and `next.config.*`.

- [ ] **Step 2: Add Clerk middleware and provider**

Create `middleware.ts`:

```ts
import { clerkMiddleware } from '@clerk/nextjs/server'

export default clerkMiddleware()

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
```

Create `app/layout.tsx`:

```tsx
import { ClerkProvider, Show, SignInButton, SignUpButton, UserButton } from '@clerk/nextjs'
import './globals.css'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ClerkProvider>
          <header>
            <Show when="signed-out">
              <SignInButton />
              <SignUpButton />
            </Show>
            <Show when="signed-in">
              <UserButton />
            </Show>
          </header>
          {children}
        </ClerkProvider>
      </body>
    </html>
  )
}
```

- [ ] **Step 3: Build the shell navigation**

`app/page.tsx` should redirect signed-in users to `/chat` and show a simple marketing-style landing state for signed-out users. `components/app-shell.tsx` should render the Intelligence Hub nav:

```tsx
const nav = [
  { href: '/chat', label: 'Chat' },
  { href: '/benchmarks', label: 'Benchmarks' },
  { href: '/admin', label: 'Admin' },
  { href: '/contracts', label: 'Contract Hub' },
]
```

Keep the first pass visually strong but minimal: dark industrial surface, clear hierarchy, no extra product areas yet.

- [ ] **Step 4: Verify the shell builds**

Run:

```bash
cd hub-ui
pnpm install
pnpm build
pnpm lint
```

Expected: build succeeds and the Clerk wrapper compiles without App Router errors.

---

### Task 2: Add Carbon chat proxy and workspace page

**Files:**
- Create: `hub-ui/app/api/chat/route.ts`
- Create: `hub-ui/lib/carbon-client.ts`
- Create: `hub-ui/lib/types.ts`
- Create: `hub-ui/app/chat/page.tsx`
- Create: `hub-ui/components/chat-panel.tsx`
- Create: `hub-ui/components/message-list.tsx`
- Test: `hub-ui/tests/api/chat-route.spec.ts`

- [ ] **Step 1: Write the failing proxy test**

```ts
import { describe, it, expect } from 'vitest'

describe('chat route proxy', () => {
  it('forwards openai-compatible payloads to Carbon', async () => {
    const payload = {
      model: 'carbon-agent',
      messages: [{ role: 'user', content: 'hello' }],
      stream: false,
    }

    expect(payload.messages[0].role).toBe('user')
  })
})
```

The test intent is simple: the app owns UI, Carbon owns inference, and the UI never talks directly to provider keys.

- [ ] **Step 2: Implement the same-origin proxy**

`app/api/chat/route.ts` should forward to the adapter’s OpenAI-compatible endpoint on the Carbon network, translating UI form state into `POST /v1/chat/completions`.

```ts
export async function POST(req: Request) {
  const body = await req.json()
  const upstream = await fetch(`${process.env.CARBON_ADAPTER_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  return new Response(upstream.body, {
    status: upstream.status,
    headers: upstream.headers,
  })
}
```

- [ ] **Step 3: Build the chat workspace**

`app/chat/page.tsx` should render:
- a model selector that shows only allowed policy-backed choices
- a message list
- a composer
- a right rail for session info and the active routing mode

The first cut can use the current Carbon model names and should default to the configured provider, not user selection.

- [ ] **Step 4: Verify the chat loop**

Run:

```bash
cd hub-ui
pnpm test -- tests/api/chat-route.spec.ts
pnpm build
```

Expected: the route handler compiles and the page renders against mocked responses.

---

### Task 3: Add admin model policy and benchmark comparison

**Files:**
- Create: `orchestrator/app/model_policy.py`
- Modify: `orchestrator/app/admin.py`
- Modify: `orchestrator/app/models.py`
- Modify: `orchestrator/app/schemas.py`
- Create: `hub-ui/app/admin/page.tsx`
- Create: `hub-ui/app/benchmarks/page.tsx`
- Create: `hub-ui/app/api/admin/model-policy/route.ts`
- Create: `hub-ui/app/api/benchmarks/route.ts`
- Test: `orchestrator/tests/test_model_policy.py`

- [ ] **Step 1: Write the failing policy test**

```python
def test_admin_can_set_block_premium_policy():
    policy = {"routing_mode": "block_premium", "default_provider": "featherless"}
    assert policy["routing_mode"] == "block_premium"
```

The real test later should assert the policy is persisted and enforced, but the first pass keeps the shape explicit.

- [ ] **Step 2: Implement policy persistence**

Add a small table or JSON field on the orchestrator side for:
- `routing_mode`: `auto | force_premium | block_premium`
- `default_provider`
- `allowed_providers`
- `benchmark_mode`

Keep admin ownership in the orchestrator, not the UI.
Use `auth()` from `@clerk/nextjs/server` in the UI route handlers and the orchestrator admin endpoints so only admins can read or mutate policy.

- [ ] **Step 3: Implement benchmark compare mode**

The benchmark endpoint should accept one prompt and a set of comparison configs:

```json
{
  "prompt": "Summarize the contract risk in this clause",
  "runs": [
    { "label": "glm-fast", "provider": "featherless", "model": "GLM-4.7" },
    { "label": "deepseek-reasoning", "provider": "deepseek", "model": "deepseek-chat" },
    { "label": "premium-claude", "provider": "anthropic", "model": "claude-3-5-sonnet-latest" }
  ]
}
```

Return one record per run with:
- output text
- latency
- token count if available
- success or failure

- [ ] **Step 4: Build the admin and benchmark screens**

The UI should let an admin:
- flip routing mode
- choose default provider sets
- queue a benchmark
- compare outputs side-by-side

The first pass can be table-driven instead of graph-heavy. The value is comparison, not decoration.

- [ ] **Step 5: Verify policy and benchmark endpoints**

Run:

```bash
pytest orchestrator/tests/test_model_policy.py -v
cd hub-ui
pnpm build
```

Expected: policy changes persist and benchmark responses render in the admin UI.

---

### Task 4: Swap deployment to the custom hub and keep Open WebUI as fallback

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.prod.yml`
- Modify: `.env.example`
- Modify: `.env.production.example`
- Modify: `deploy_to_server.py`
- Modify: `README.md`
- Test: `tests/deploy/test_hub_smoke.py`

- [ ] **Step 1: Add the new `hub-ui` service**

The compose files should run `hub-ui` on port `3000` and keep the existing Carbon backend services unchanged. Open WebUI should stay available only as a fallback profile or explicit flag, not the default user-facing shell.

- [ ] **Step 2: Add the UI-specific env vars**

Document:

```env
HUB_UI_URL=http://hub-ui:3000
CARBON_ADAPTER_URL=http://adapter:8000
CARBON_ORCHESTRATOR_URL=http://orchestrator:8000
HUB_DEFAULT_ROUTING_MODE=auto
```

- [ ] **Step 3: Update deploy automation**

`deploy_to_server.py` should build and start the new UI service, then verify:
- `GET /health` on the hub
- `GET /health` on orchestrator
- `GET /health` on adapter
- a real browser smoke check on `/chat`

- [ ] **Step 4: Add a deploy smoke test**

```python
def test_hub_is_reachable():
    response = requests.get("http://127.0.0.1:3000")
    assert response.status_code == 200
```

If the test runner supports browser automation, add one Playwright check that signs in, opens `/chat`, and renders the composer.

- [ ] **Step 5: Verify the morning cut**

Run:

```bash
docker compose config
docker compose build hub-ui orchestrator adapter
docker compose up -d
curl -f http://localhost:3000
curl -f http://localhost:8000/health
curl -f http://localhost:8001/health
```

Expected: the custom hub is live, chat opens, and the Carbon backend remains intact.

---

### Out Of Scope For This Pass

- Full desktop app packaging
- Multi-agent orchestration editor
- Advanced workflow builder
- Deep benchmark analytics and charts
- Replacing Contract Hub
- Replacing Spark/vLLM infrastructure once the DGX boxes arrive
