"""Admin UI page served as inline HTML."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import get_settings

admin_ui_router = APIRouter(tags=["admin-ui"])

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Agent Platform | Admin Dashboard</title>
<script async crossorigin="anonymous" data-clerk-publishable-key="{{CLERK_PUBLISHABLE_KEY}}" src="{{CLERK_FRONTEND_API_URL}}/npm/@clerk/clerk-js@latest/dist/clerk.browser.js" type="text/javascript"></script>
<style>
  /* Carbon Agent Brand System */
  :root {
    --carbon-void: #0a0a0f;
    --carbon-deep: #111118;
    --carbon-surface: #1a1a24;
    --carbon-elevated: #22222e;
    --carbon-border: rgba(255, 255, 255, 0.08);
    --carbon-border-strong: rgba(255, 255, 255, 0.12);
    --accent-primary: #00d4aa;
    --accent-primary-dim: rgba(0, 212, 170, 0.1);
    --accent-primary-glow: rgba(0, 212, 170, 0.3);
    --accent-secondary: #00b894;
    --status-success: #22c55e;
    --status-warning: #f59e0b;
    --status-error: #ef4444;
    --status-info: #3b82f6;
    --text-primary: #fafafa;
    --text-secondary: #a1a1aa;
    --text-tertiary: #71717a;
    --text-muted: #52525b;
    --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
    --duration-fast: 150ms;
    --duration-normal: 250ms;
  }
  
  * { margin: 0; padding: 0; box-sizing: border-box; }
  
  body { 
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
    background: var(--carbon-void); 
    color: var(--text-primary); 
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  
  /* Header */
  .header { 
    background: var(--carbon-void); 
    border-bottom: 1px solid var(--carbon-border); 
    padding: 16px 24px; 
    display: flex; 
    align-items: center; 
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(12px);
  }
  
  .header-brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .header-logo {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 20px var(--accent-primary-glow);
  }
  
  .header-logo::after {
    content: '';
    width: 16px;
    height: 16px;
    background: var(--carbon-void);
    border-radius: 4px;
    clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
  }
  
  .header h1 { 
    font-size: 18px; 
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  
  .header h1 span {
    color: var(--text-tertiary);
    font-weight: 400;
  }
  
  .header .status { 
    font-size: 13px; 
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-muted);
  }
  
  .status-dot.online {
    background: var(--status-success);
    box-shadow: 0 0 8px var(--status-success);
  }
  
  .container { 
    max-width: 1400px; 
    margin: 0 auto; 
    padding: 32px 24px; 
  }
  
  /* Metrics Grid */
  .metrics { 
    display: grid; 
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
    gap: 16px; 
    margin-bottom: 32px; 
  }
  
  .metric-card { 
    background: var(--carbon-surface); 
    border: 1px solid var(--carbon-border); 
    border-radius: 12px; 
    padding: 20px;
    transition: all var(--duration-normal) var(--ease-out-expo);
  }
  
  .metric-card:hover {
    border-color: var(--carbon-border-strong);
    transform: translateY(-2px);
  }
  
  .metric-card .label { 
    font-size: 12px; 
    color: var(--text-tertiary); 
    text-transform: uppercase; 
    letter-spacing: 0.05em; 
    margin-bottom: 8px;
    font-weight: 500;
  }
  
  .metric-card .value { 
    font-size: 32px; 
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text-primary);
  }
  
  .metric-card .value.success { color: var(--status-success); }
  .metric-card .value.warning { color: var(--status-warning); }
  .metric-card .value.error { color: var(--status-error); }
  .metric-card .value.info { color: var(--accent-primary); }
  
  /* Cards */
  .card { 
    background: var(--carbon-surface); 
    border: 1px solid var(--carbon-border); 
    border-radius: 12px; 
    padding: 24px; 
    margin-bottom: 24px;
    transition: all var(--duration-normal) var(--ease-out-expo);
  }
  
  .card:hover {
    border-color: var(--carbon-border-strong);
  }
  
  .card h2 { 
    font-size: 16px; 
    font-weight: 600; 
    margin-bottom: 20px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  .card h2::before {
    content: '';
    width: 4px;
    height: 20px;
    background: var(--accent-primary);
    border-radius: 2px;
  }
  
  /* Tables */
  table { 
    width: 100%; 
    border-collapse: collapse; 
    font-size: 14px;
  }
  
  th { 
    text-align: left; 
    padding: 12px 16px; 
    color: var(--text-tertiary); 
    font-weight: 500; 
    border-bottom: 1px solid var(--carbon-border); 
    text-transform: uppercase; 
    font-size: 11px; 
    letter-spacing: 0.05em;
  }
  
  td { 
    padding: 14px 16px; 
    border-bottom: 1px solid var(--carbon-border);
    color: var(--text-secondary);
  }
  
  tr:hover td {
    background: var(--carbon-elevated);
    color: var(--text-primary);
  }
  
  /* Badges */
  .badge { 
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px; 
    border-radius: 9999px; 
    font-size: 12px; 
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  
  .badge::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
  
  .badge-active { 
    background: rgba(34, 197, 94, 0.1); 
    color: var(--status-success); 
  }
  .badge-active::before { background: var(--status-success); }
  
  .badge-suspended { 
    background: rgba(239, 68, 68, 0.1); 
    color: var(--status-error); 
  }
  .badge-suspended::before { background: var(--status-error); }
  
  .badge-pending { 
    background: rgba(245, 158, 11, 0.1); 
    color: var(--status-warning); 
  }
  .badge-pending::before { background: var(--status-warning); }
  
  /* Buttons */
  .actions { 
    display: flex; 
    gap: 8px; 
  }
  
  .btn { 
    padding: 8px 16px; 
    border-radius: 8px; 
    border: 1px solid var(--carbon-border); 
    background: var(--carbon-elevated); 
    color: var(--text-secondary); 
    cursor: pointer; 
    font-size: 13px;
    font-weight: 500;
    transition: all var(--duration-fast) var(--ease-out-expo);
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  
  .btn:hover { 
    background: var(--carbon-surface); 
    border-color: var(--carbon-border-strong);
    color: var(--text-primary);
  }
  
  .btn:active {
    transform: scale(0.98);
  }
  
  .btn-primary {
    background: var(--accent-primary);
    border-color: var(--accent-primary);
    color: var(--carbon-void);
  }
  
  .btn-primary:hover {
    background: var(--accent-secondary);
    box-shadow: 0 0 20px var(--accent-primary-glow);
  }
  
  .btn-danger { 
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.2);
    color: var(--status-error); 
  }
  
  .btn-danger:hover { 
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.3);
  }
  
  /* Form Elements */
  input, select { 
    background: var(--carbon-deep); 
    border: 1px solid var(--carbon-border); 
    color: var(--text-primary); 
    padding: 10px 14px; 
    border-radius: 8px; 
    font-size: 14px;
    transition: all var(--duration-fast) var(--ease-out-expo);
  }
  
  input:focus, select:focus {
    outline: none;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 3px var(--accent-primary-dim);
  }
  
  input::placeholder {
    color: var(--text-tertiary);
  }
  
  /* Login Prompt */
  .login-prompt { 
    text-align: center; 
    padding: 120px 20px;
    max-width: 400px;
    margin: 0 auto;
  }
  
  .login-prompt .logo {
    width: 64px;
    height: 64px;
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
    border-radius: 16px;
    margin: 0 auto 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 40px var(--accent-primary-glow);
  }
  
  .login-prompt .logo::after {
    content: '';
    width: 28px;
    height: 28px;
    background: var(--carbon-void);
    border-radius: 6px;
    clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
  }
  
  .login-prompt h2 { 
    margin-bottom: 12px;
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  
  .login-prompt p {
    color: var(--text-tertiary);
    margin-bottom: 32px;
  }
  
  /* Loading */
  .loading { 
    color: var(--text-tertiary); 
    text-align: center; 
    padding: 60px;
    font-size: 15px;
  }
  
  .loading::after {
    content: '';
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid var(--carbon-border);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    margin-left: 12px;
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  #clerk-sign-in { 
    display: inline-block;
    margin-top: 8px;
  }
  
  /* Scrollbar */
  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  
  ::-webkit-scrollbar-track {
    background: var(--carbon-deep);
  }
  
  ::-webkit-scrollbar-thumb {
    background: var(--carbon-elevated);
    border-radius: 4px;
  }
  
  ::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
  }
  
  /* Selection */
  ::selection {
    background: var(--accent-primary-dim);
    color: var(--accent-primary);
  }
</style>
</head>
<body>
<div class="header">
  <div class="header-brand">
    <div class="header-logo"></div>
    <h1>AI Agent Platform <span>| Admin Dashboard</span></h1>
  </div>
  <div class="status" id="connection-status">
    <span class="status-dot"></span>
    Initializing...
  </div>
</div>
<div class="container" id="app">
  <div class="loading">Loading dashboard</div>
</div>

<script>
const API_BASE = window.location.origin;
let clerkSessionToken = null;

// Escape user-controlled strings before inserting into innerHTML
function esc(s) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(s ?? ''));
  return d.innerHTML;
}

async function getClerkToken() {
  if (window.Clerk && window.Clerk.session) {
    try {
      const token = await window.Clerk.session.getToken();
      return token;
    } catch (e) {
      console.error('Failed to get Clerk token:', e);
      return null;
    }
  }
  return null;
}

function apiHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (clerkSessionToken) {
    headers['Authorization'] = 'Bearer ' + clerkSessionToken;
  }
  return headers;
}

async function api(endpoint, opts = {}) {
  // Refresh token before each API call
  clerkSessionToken = await getClerkToken();
  const res = await fetch(API_BASE + endpoint, { headers: apiHeaders(), ...opts });
  if (res.status === 401 || res.status === 403) { 
    clerkSessionToken = null;
    renderLogin(); 
    throw new Error('Auth failed'); 
  }
  return res.json();
}

function statusBadge(status) {
  const cls = { active: 'badge-active', suspended: 'badge-suspended', pending: 'badge-pending' }[status] || 'badge-pending';
  return `<span class="badge ${cls}">${status}</span>`;
}

function renderLogin() {
  document.getElementById('app').innerHTML = `
    <div class="login-prompt">
      <div class="logo"></div>
      <h2>Admin Authentication Required</h2>
      <p>Please sign in with your Clerk admin account to access the dashboard</p>
      <div id="clerk-sign-in"></div>
    </div>`;
  document.getElementById('connection-status').innerHTML = '<span class="status-dot"></span>Not authenticated';
  
  // Mount Clerk sign-in component
  if (window.Clerk) {
    window.Clerk.mountSignIn(document.getElementById('clerk-sign-in'));
  }
}

async function checkAdminAccess() {
  try {
    await api('/admin/health');
    renderDashboard();
  } catch(e) {
    if (e.message === 'Auth failed') {
      renderLogin();
    } else {
      document.getElementById('app').innerHTML = `<div class="loading">Error loading dashboard: ${esc(e.message)}</div>`;
    }
  }
}

async function renderDashboard() {
  document.getElementById('connection-status').innerHTML = '<span class="status-dot online"></span>Authenticated';
  document.getElementById('app').innerHTML = `
    <div class="metrics" id="metrics"></div>
    <div class="card">
      <h2>Users</h2>
      <div style="margin-bottom:20px;display:flex;gap:12px;align-items:center">
        <input id="new-email" placeholder="Email" style="width:240px" />
        <input id="new-name" placeholder="Display Name" style="width:200px" />
        <button class="btn btn-primary" onclick="createUser()">Create User</button>
      </div>
      <table><thead><tr><th>Email</th><th>Name</th><th>Status</th><th>Service</th><th>Created</th><th>Actions</th></tr></thead>
      <tbody id="users-table"></tbody></table>
    </div>
    <div class="card">
      <h2>Active Sessions</h2>
      <table><thead><tr><th>Email</th><th>Name</th><th>Status</th><th>Last Updated</th><th>Actions</th></tr></thead>
      <tbody id="sessions-table"></tbody></table>
    </div>`;

  await loadMetrics();
  await loadUsers();
  await loadSessions();
}

async function loadMetrics() {
  try {
    const m = await api('/admin/metrics');
    document.getElementById('metrics').innerHTML = `
      <div class="metric-card"><div class="label">Total Users</div><div class="value">${m.total_users}</div></div>
      <div class="metric-card"><div class="label">Active Users</div><div class="value success">${m.active_users}</div></div>
      <div class="metric-card"><div class="label">Active Services</div><div class="value info">${m.active_services}</div></div>
      <div class="metric-card"><div class="label">Suspended</div><div class="value error">${m.suspended_users}</div></div>
      <div class="metric-card"><div class="label">Pending</div><div class="value warning">${m.pending_users}</div></div>
      <div class="metric-card"><div class="label">Volumes</div><div class="value">${m.total_volumes}</div></div>`;
  } catch(e) { console.error(e); }
}

async function loadUsers() {
  try {
    const users = await api('/admin/users');
    const tbody = document.getElementById('users-table');
    tbody.innerHTML = users.map(u => `<tr>
      <td>${esc(u.email)}</td><td>${esc(u.display_name)}</td><td>${statusBadge(u.status)}</td>
      <td>${u.status === 'active' ? 'Yes' : 'No'}</td>
      <td>${new Date(u.created_at).toLocaleDateString()}</td>
      <td class="actions">
        ${u.status === 'active' ? `<button class="btn" onclick="suspendUser(${JSON.stringify(u.id)})">Suspend</button>` : ''}
        ${u.status === 'suspended' ? `<button class="btn" onclick="activateUser(${JSON.stringify(u.id)})">Activate</button>` : ''}
        <button class="btn btn-danger" onclick="deleteUser(${JSON.stringify(u.id)},${JSON.stringify(u.email)})">Delete</button>
      </td></tr>`).join('');
  } catch(e) { console.error(e); }
}

async function loadSessions() {
  try {
    const data = await api('/admin/sessions');
    const tbody = document.getElementById('sessions-table');
    if (!data.sessions || data.sessions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted)">No active sessions</td></tr>';
      return;
    }
    tbody.innerHTML = data.sessions.map(s => `<tr>
      <td>${esc(s.email)}</td><td>${esc(s.display_name)}</td>
      <td>${s.status ? statusBadge(s.status) : '-'}</td>
      <td>${s.updated_at ? new Date(s.updated_at).toLocaleString() : '-'}</td>
      <td><button class="btn btn-danger" onclick="spinDownUser(${JSON.stringify(s.user_id)})">Spin Down</button></td>
    </tr>`).join('');
  } catch(e) { console.error(e); }
}

async function createUser() {
  const email = document.getElementById('new-email').value.trim();
  const name = document.getElementById('new-name').value.trim();
  if (!email || !name) { alert('Email and name required'); return; }
  try {
    const result = await api('/admin/users', { method: 'POST', body: JSON.stringify({ email, display_name: name }) });
    alert(`User created! API Key: ${result.api_key}`);
    document.getElementById('new-email').value = '';
    document.getElementById('new-name').value = '';
    await loadUsers(); await loadMetrics();
  } catch(e) { alert('Failed to create user'); }
}

async function suspendUser(id) {
  if (!confirm('Suspend this user?')) return;
  try { await api(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'suspended' }) }); await loadUsers(); await loadMetrics(); } catch(e) { alert('Failed'); }
}

async function activateUser(id) {
  try { await api(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'active' }) }); await loadUsers(); await loadMetrics(); } catch(e) { alert('Failed'); }
}

async function deleteUser(id, email) {
  if (!confirm(`Delete user ${email}? This cannot be undone.`)) return;
  try { await api(`/admin/users/${id}`, { method: 'DELETE' }); await loadUsers(); await loadMetrics(); await loadSessions(); } catch(e) { alert('Failed'); }
}

async function spinDownUser(id) {
  if (!confirm('Spin down this service? The Railway service will be stopped.')) return;
  try {
    await api(`/admin/users/${id}/spin-down`, { method: 'POST' });
    await loadSessions(); await loadMetrics(); await loadUsers();
  } catch(e) { alert('Failed to spin down service'); }
}

// Init - Wait for Clerk to load
window.addEventListener('load', async () => {
  if (!window.Clerk) {
    document.getElementById('app').innerHTML = '<div class="loading">Failed to load Clerk authentication</div>';
    return;
  }
  
  try {
    await window.Clerk.load();
    
    if (window.Clerk.user) {
      // User is signed in, check if they're an admin
      document.getElementById('connection-status').textContent = 'Checking admin access...';
      await checkAdminAccess();
    } else {
      // User is not signed in
      renderLogin();
    }
    
    // Listen for auth state changes
    window.Clerk.addListener(({ user }) => {
      if (user) {
        checkAdminAccess();
      } else {
        renderLogin();
      }
    });
  } catch (e) {
    console.error('Clerk initialization failed:', e);
    document.getElementById('app').innerHTML = '<div class="loading">Authentication initialization failed</div>';
  }
});
</script>
</body>
</html>"""


@admin_ui_router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin dashboard HTML page."""
    settings = get_settings()
    
    # Substitute Clerk configuration into the HTML template
    html_content = ADMIN_HTML.replace(
        "{{CLERK_PUBLISHABLE_KEY}}", 
        settings.clerk_publishable_key or ""
    ).replace(
        "{{CLERK_FRONTEND_API_URL}}",
        settings.clerk_frontend_api_url or "https://api.clerk.com"
    )
    
    return HTMLResponse(content=html_content)
