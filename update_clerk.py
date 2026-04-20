"""Push Clerk keys to server and restart affected services."""
import paramiko, time

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
DIR      = "/opt/carbon-agent-platform"

CLERK_PUBLISHABLE_KEY = "pk_test_d2lsbGluZy1ib25lZmlzaC04Ny5jbGVyay5hY2NvdW50cy5kZXYk"
CLERK_SECRET_KEY      = "sk_test_4OdakR2ssaWOA254JVBEIr5c7Yaek8h28D8JHJgCAr"

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

# 1. Patch the .env file — update Clerk keys in-place using sed
print("\n[1/3] Updating Clerk keys in .env ...")
run(ssh, f"sed -i 's|^CLERK_PUBLISHABLE_KEY=.*|CLERK_PUBLISHABLE_KEY={CLERK_PUBLISHABLE_KEY}|' {DIR}/.env")
run(ssh, f"sed -i 's|^NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=.*|NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY={CLERK_PUBLISHABLE_KEY}|' {DIR}/.env")
run(ssh, f"sed -i 's|^CLERK_SECRET_KEY=.*|CLERK_SECRET_KEY={CLERK_SECRET_KEY}|' {DIR}/.env")

# Also add NEXT_PUBLIC_ prefix if not present (for open-webui)
run(ssh, f"grep -q 'NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY' {DIR}/.env || echo 'NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY={CLERK_PUBLISHABLE_KEY}' >> {DIR}/.env")

# Verify the keys are set
print("\n  Verifying keys in .env:")
run(ssh, f"grep 'CLERK' {DIR}/.env | grep -v '^#'")

# 2. Restart orchestrator and open-webui (they consume Clerk keys)
print("\n[2/3] Restarting orchestrator + open-webui with new Clerk keys ...")
run(ssh, f"cd {DIR} && docker compose up -d --force-recreate orchestrator open-webui", timeout=120)

print("\nWaiting 30s for services ...")
time.sleep(30)

# 3. Health check
print("\n[3/3] Health checks ...")
run(ssh, "curl -sf http://localhost:8000/health && echo '  Orchestrator OK' || echo '  Orchestrator FAIL'")
run(ssh, "curl -sf http://localhost:3000/health && echo '  Open WebUI OK'   || echo '  Open WebUI FAIL'")
run(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}'")

print(f"""
============================================================
  Clerk keys deployed!

  Publishable : {CLERK_PUBLISHABLE_KEY[:30]}...
  Secret      : {CLERK_SECRET_KEY[:20]}...

  Next step: add this to your Clerk dashboard:
    Redirect URL : http://{HOST}:3000
    Webhook URL  : http://{HOST}:8000/webhooks/clerk
============================================================
""")
ssh.close()
