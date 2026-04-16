"""Admin UI page served as inline HTML."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

admin_ui_router = APIRouter(tags=["admin-ui"])

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carbon Agent - Admin Dashboard</title>
<style>
  :root { --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6; --red: #ef4444; --green: #22c55e; --yellow: #eab308; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  .header { background: var(--card); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 20px; font-weight: 600; }
  .header .status { font-size: 13px; color: var(--muted); }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
  .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .metric-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .metric-card .label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .metric-card .value { font-size: 28px; font-weight: 700; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
  .card h2 { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px 12px; color: var(--muted); font-weight: 500; border-bottom: 1px solid var(--border); text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
  td { padding: 8px 12px; border-bottom: 1px solid var(--border); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
  .badge-active { background: rgba(34,197,94,0.15); color: var(--green); }
  .badge-suspended { background: rgba(239,68,68,0.15); color: var(--red); }
  .badge-pending { background: rgba(234,179,8,0.15); color: var(--yellow); }
  .actions { display: flex; gap: 8px; }
  .btn { padding: 4px 12px; border-radius: 4px; border: 1px solid var(--border); background: var(--card); color: var(--text); cursor: pointer; font-size: 12px; }
  .btn:hover { background: var(--border); }
  .btn-danger { border-color: var(--red); color: var(--red); }
  .btn-danger:hover { background: rgba(239,68,68,0.15); }
  .login-prompt { text-align: center; padding: 80px 20px; }
  .login-prompt h2 { margin-bottom: 16px; }
  input, select { background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 6px 10px; border-radius: 4px; font-size: 13px; }
  .loading { color: var(--muted); text-align: center; padding: 40px; }
</style>
</head>
<body>
<div class="header">
  <h1>Carbon Agent - Admin Dashboard</h1>
  <div class="status" id="connection-status">Connecting...</div>
</div>
<div class="container" id="app">
  <div class="loading">Loading dashboard...</div>
</div>

<script>
const API_BASE = window.location.origin;
let adminKey = '';

function getStoredKey() {
  return sessionStorage.getItem('admin_key') || '';
}

function setStoredKey(key) {
  if (key) sessionStorage.setItem('admin_key', key);
  else sessionStorage.removeItem('admin_key');
  adminKey = key;
}

function apiHeaders() {
  return { 'X-Admin-Key': adminKey, 'Content-Type': 'application/json' };
}

async function api(endpoint, opts = {}) {
  const res = await fetch(API_BASE + endpoint, { headers: apiHeaders(), ...opts });
  if (res.status === 403) { setStoredKey(''); renderLogin(); throw new Error('Auth failed'); }
  return res.json();
}

function statusBadge(status) {
  const cls = { active: 'badge-active', suspended: 'badge-suspended', pending: 'badge-pending' }[status] || 'badge-pending';
  return `<span class="badge ${cls}">${status}</span>`;
}

function renderLogin() {
  document.getElementById('app').innerHTML = `
    <div class="login-prompt">
      <h2>Admin Authentication Required</h2>
      <p style="color:var(--muted);margin-bottom:20px">Enter your admin API key to access the dashboard</p>
      <input type="password" id="key-input" placeholder="Admin API Key" style="width:300px;margin-bottom:12px" />
      <br/><button class="btn" onclick="doLogin()" style="padding:8px 24px">Sign In</button>
    </div>`;
  document.getElementById('connection-status').textContent = 'Not authenticated';
}

async function doLogin() {
  const key = document.getElementById('key-input').value.trim();
  if (!key) return;
  setStoredKey(key);
  try {
    await api('/admin/health');
    renderDashboard();
  } catch(e) {
    alert('Invalid admin key');
    setStoredKey('');
  }
}

async function renderDashboard() {
  document.getElementById('connection-status').textContent = 'Authenticated';
  document.getElementById('app').innerHTML = `
    <div class="metrics" id="metrics"></div>
    <div class="card">
      <h2>Users</h2>
      <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
        <input id="new-email" placeholder="Email" style="width:220px" />
        <input id="new-name" placeholder="Display Name" style="width:180px" />
        <button class="btn" onclick="createUser()" style="background:var(--accent);color:#fff;border-color:var(--accent)">Create User</button>
      </div>
      <table><thead><tr><th>Email</th><th>Name</th><th>Status</th><th>Service</th><th>Created</th><th>Actions</th></tr></thead>
      <tbody id="users-table"></tbody></table>
    </div>
    <div class="card">
      <h2>Active Sessions</h2>
      <table><thead><tr><th>Email</th><th>Name</th><th>Service ID</th><th>Volume ID</th><th>Last Updated</th><th>Actions</th></tr></thead>
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
      <div class="metric-card"><div class="label">Active Users</div><div class="value" style="color:var(--green)">${m.active_users}</div></div>
      <div class="metric-card"><div class="label">Active Services</div><div class="value" style="color:var(--accent)">${m.active_services}</div></div>
      <div class="metric-card"><div class="label">Suspended</div><div class="value" style="color:var(--red)">${m.suspended_users}</div></div>
      <div class="metric-card"><div class="label">Pending</div><div class="value" style="color:var(--yellow)">${m.pending_users}</div></div>
      <div class="metric-card"><div class="label">Volumes</div><div class="value">${m.total_volumes}</div></div>`;
  } catch(e) { console.error(e); }
}

async function loadUsers() {
  try {
    const users = await api('/admin/users');
    const tbody = document.getElementById('users-table');
    tbody.innerHTML = users.map(u => `<tr>
      <td>${u.email}</td><td>${u.display_name}</td><td>${statusBadge(u.status)}</td>
      <td>${u.railway_service_id ? 'Yes' : 'No'}</td>
      <td>${new Date(u.created_at).toLocaleDateString()}</td>
      <td class="actions">
        ${u.status === 'active' ? `<button class="btn" onclick="suspendUser('${u.id}')">Suspend</button>` : ''}
        ${u.status === 'suspended' ? `<button class="btn" onclick="activateUser('${u.id}')">Activate</button>` : ''}
        <button class="btn btn-danger" onclick="deleteUser('${u.id}','${u.email}')">Delete</button>
      </td></tr>`).join('');
  } catch(e) { console.error(e); }
}

async function loadSessions() {
  try {
    const data = await api('/admin/sessions');
    const tbody = document.getElementById('sessions-table');
    if (!data.sessions || data.sessions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted)">No active sessions</td></tr>';
      return;
    }
    tbody.innerHTML = data.sessions.map(s => `<tr>
      <td>${s.email}</td><td>${s.display_name}</td>
      <td style="font-family:monospace;font-size:11px">${s.service_id || '-'}</td>
      <td style="font-family:monospace;font-size:11px">${s.volume_id || '-'}</td>
      <td>${s.updated_at ? new Date(s.updated_at).toLocaleString() : '-'}</td>
      <td><button class="btn btn-danger" onclick="spinDownUser('${s.user_id}')">Spin Down</button></td>
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
  if (!confirm('Spin down this service?')) return;
  try { await api(`/user/me/service/spin-down`, { method: 'POST', headers: { ...apiHeaders(), 'Authorization': '' } }); alert('Not supported via admin API - use user endpoint'); } catch(e) { alert('Failed'); }
}

// Init
adminKey = getStoredKey();
if (adminKey) {
  api('/admin/health').then(() => renderDashboard()).catch(() => renderLogin());
} else {
  renderLogin();
}
</script>
</body>
</html>"""


@admin_ui_router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin dashboard HTML page."""
    return HTMLResponse(content=ADMIN_HTML)
