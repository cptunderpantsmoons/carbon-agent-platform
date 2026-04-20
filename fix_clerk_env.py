"""Fix missing Clerk env vars and restart open-webui."""
import paramiko, time

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
DIR      = "/opt/carbon-agent-platform"

CLERK_FRONTEND_API_URL = "https://willing-bonefish-87.clerk.accounts.dev"
CLERK_PUBLISHABLE_KEY  = "pk_test_d2lsbGluZy1ib25lZmlzaC04Ny5jbGVyay5hY2NvdW50cy5kZXYk"

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

# 1. Check logs first
print("\n[1/4] Checking open-webui logs ...")
run(ssh, "docker logs carbon-agent-platform-open-webui-1 --tail 30", timeout=30)

# 2. Add missing env vars
print("\n[2/4] Adding missing Clerk env vars ...")
run(ssh, f"sed -i 's|CLERK_FRONTEND_API_URL=|CLERK_FRONTEND_API_URL={CLERK_FRONTEND_API_URL}|' {DIR}/.env")
run(ssh, f"grep -q '^CLERK_FRONTEND_API_URL' {DIR}/.env || echo 'CLERK_FRONTEND_API_URL={CLERK_FRONTEND_API_URL}' >> {DIR}/.env")

# Also ensure publishable key is correct
run(ssh, f"sed -i 's|CLERK_PUBLISHABLE_KEY=.*|CLERK_PUBLISHABLE_KEY={CLERK_PUBLISHABLE_KEY}|' {DIR}/.env")

print("\n  Updated env:")
run(ssh, f"grep -E 'CLERK|OPENWEBUI' {DIR}/.env | grep -v '^#'")

# 3. Restart open-webui
print("\n[3/4] Restarting open-webui ...")
run(ssh, f"cd {DIR} && docker compose up -d --force-recreate open-webui", timeout=90)

print("\nWaiting 30s ...")
time.sleep(30)

# 4. Verify
print("\n[4/4] Verification ...")
run(ssh, "curl -sf http://localhost:3000/health && echo '  Open WebUI OK' || echo '  Open WebUI FAIL'", timeout=15)
run(ssh, "docker ps --format 'table {{.Names}}\\t{{.Status}}'", timeout=15)

# Check logs again
print("\n  Final logs tail:")
run(ssh, "docker logs carbon-agent-platform-open-webui-1 --tail 10", timeout=20)

print(f"""
============================================================
  Clerk frontend URL set: {CLERK_FRONTEND_API_URL}

  If Open WebUI still fails, check Clerk Dashboard:
    - Redirect URL: http://{HOST}:3000
    - Allowed origins: http://{HOST}:3000
    - Ensure webhook URL: http://{HOST}:8000/webhooks/clerk
============================================================
""")
ssh.close()
