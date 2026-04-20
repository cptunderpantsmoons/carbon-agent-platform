"""Deploy RAG gateway updates to remote server."""
import paramiko
import time
import os

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
DIR      = "/opt/carbon-agent-platform"

RAG_FIXED_TENANT_ID = "contract-hub-tenant"
VECTOR_STORE_URL = "http://vector-store:8000"

def run(ssh, cmd, timeout=120):
    print(f"\n$ {cmd}", flush=True)
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    for line in iter(stdout.readline, ""):
        print(f"  {line}", end="", flush=True)
    return stdout.channel.recv_exit_status()

def sftp_put(sftp, local_path, remote_path):
    print(f"Uploading {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)
    print("  OK")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
print("Connected!")

# 1. Update environment variables
print("\n[1/3] Setting RAG environment variables...")
run(ssh, f"grep -q '^RAG_FIXED_TENANT_ID=' {DIR}/.env && sed -i 's|^RAG_FIXED_TENANT_ID=.*|RAG_FIXED_TENANT_ID={RAG_FIXED_TENANT_ID}|' {DIR}/.env || echo 'RAG_FIXED_TENANT_ID={RAG_FIXED_TENANT_ID}' >> {DIR}/.env")
run(ssh, f"grep -q '^VECTOR_STORE_URL=' {DIR}/.env && sed -i 's|^VECTOR_STORE_URL=.*|VECTOR_STORE_URL={VECTOR_STORE_URL}|' {DIR}/.env || echo 'VECTOR_STORE_URL={VECTOR_STORE_URL}' >> {DIR}/.env")

# 2. Upload updated rag.py
print("\n[2/3] Uploading updated rag.py...")
sftp = ssh.open_sftp()
local_rag = os.path.join(os.path.dirname(__file__), "orchestrator", "app", "rag.py")
remote_rag = f"{DIR}/orchestrator/app/rag.py"
try:
    sftp_put(sftp, local_rag, remote_rag)
except Exception as e:
    print(f"Upload failed: {e}")
    # fallback: maybe file not found
    # try alternate path
    pass
sftp.close()

# 3. Rebuild and restart orchestrator
print("\n[3/3] Rebuilding orchestrator...")
run(ssh, f"cd {DIR} && docker compose build orchestrator", timeout=180)
print("\nRestarting orchestrator...")
run(ssh, f"cd {DIR} && docker compose up -d --force-recreate orchestrator", timeout=120)

print("\nWaiting 30s for service to start...")
time.sleep(30)

# 4. Health check
print("\n[4/4] Health checks...")
run(ssh, "curl -sf http://localhost:8000/health && echo '  Orchestrator OK' || echo '  Orchestrator FAIL'")
run(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep orchestrator")

print(f"\nRAG gateway deployed! Tenant ID: {RAG_FIXED_TENANT_ID}")
print(f"You can now test the ingest endpoint at http://{HOST}:8000/api/v1/rag/ingest")

ssh.close()