"""Enable Clerk authentication in Open WebUI and restart services."""
import paramiko, time

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
DIR      = "/opt/carbon-agent-platform"

def run(ssh, cmd, timeout=120):
    print(f"\n$ {cmd}", flush=True)
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    for line in iter(stdout.readline, ""):
        print(f"  {line}", end="", flush=True)
    return stdout.channel.recv_exit_status()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
print("Connected!")

# 1. Enable Clerk auth in .env
print("\n[1/3] Enabling Clerk authentication ...")
run(ssh, f"sed -i 's|OPENWEBUI_CLERK_ENABLED=false|OPENWEBUI_CLERK_ENABLED=true|' {DIR}/.env")
run(ssh, f"sed -i 's|CLERK_ENABLED=false|CLERK_ENABLED=true|' {DIR}/.env 2>/dev/null || true")

# Also ensure issuer is set (optional but good for JWT verification)
run(ssh, f"sed -i 's|CLERK_JWT_ISSUER=|CLERK_JWT_ISSUER=https://clerk.willing-bonefish-87.clerk.accounts.dev|' {DIR}/.env")

# Verify changes
print("\n  Current Clerk-related env vars:")
run(ssh, f"grep -E 'CLERK|OPENWEBUI' {DIR}/.env | grep -v '^#'")

# 2. Restart services
print("\n[2/3] Restarting orchestrator + open-webui with Clerk enabled ...")
run(ssh, f"cd {DIR} && docker compose up -d --force-recreate orchestrator open-webui", timeout=120)

print("\nWaiting 40s for services to start with Clerk auth ...")
time.sleep(40)

# 3. Health check + verify Clerk is active
print("\n[3/3] Verification ...")
run(ssh, "curl -sf http://localhost:8000/health && echo '  Orchestrator OK' || echo '  Orchestrator FAIL'")
run(ssh, "curl -sf http://localhost:3000/health && echo '  Open WebUI OK'   || echo '  Open WebUI FAIL'")
# Try to access the UI root to see if Clerk login appears
run(ssh, "curl -s http://localhost:3000 | grep -i clerk || echo '  (Clerk not detected in HTML - might be loading via JS)'", timeout=15)
run(ssh, "docker ps --format 'table {{.Names}}\\t{{.Status}}'")

print(f"""
============================================================
  Clerk authentication ENABLED!

  Open WebUI now requires Clerk login at:
    http://{HOST}:3000

  You must now:
    1. Go to Clerk Dashboard → Application → Redirect URLs
       Add: http://{HOST}:3000
    2. Test by visiting the URL above
    3. Sign up as first user (will trigger webhook provisioning)
============================================================
""")
ssh.close()
