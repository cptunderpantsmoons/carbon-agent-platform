"""
push_and_build.py
1. Wait for server (OOM recovery)
2. Upload updated vector-store files (fastembed replaces PyTorch)
3. Launch background build + start script via nohup
4. Poll log until DONE
"""
import io, os, time, paramiko

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
DIR      = "/opt/carbon-agent-platform"
LOG      = "/tmp/pb_deploy.log"
BASE     = os.path.dirname(os.path.abspath(__file__))

REMOTE_SCRIPT = f"""#!/bin/bash
set -e
exec > "{LOG}" 2>&1

echo "=== STEP 1: Build vector-store (fastembed/ONNX, no PyTorch) ===" && date
cd {DIR}
docker compose build --no-cache vector-store
echo "=== vector-store OK ===" && date

echo "=== STEP 2: Build contract-hub ===" && date
docker compose build contract-hub
echo "=== contract-hub OK ===" && date

echo "=== STEP 3: Start stack ===" && date
docker compose up -d --remove-orphans
sleep 25

echo "=== STEP 4: DB setup ===" && date
docker exec carbon-agent-platform-postgres-1 \\
  psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='contracthub'" \\
  | grep -q 1 \\
  || docker exec carbon-agent-platform-postgres-1 \\
     psql -U postgres -c "CREATE DATABASE contracthub"

docker exec carbon-agent-platform-contract-hub-1 \\
  npx drizzle-kit migrate 2>&1 || true

echo "=== STEP 5: Health checks ===" && date
docker ps --format "table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}"
curl -sf http://localhost:8000/health && echo "  Orchestrator  OK" || echo "  Orchestrator  FAIL"
curl -sf http://localhost:3000/health && echo "  Open-WebUI    OK" || echo "  Open-WebUI    FAIL"
wget -qO- http://localhost:3001/ > /dev/null 2>&1 && echo "  Contract-Hub  OK" || echo "  Contract-Hub  FAIL"
STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" \\
  -X POST http://localhost:8000/api/v1/rag/ingest \\
  -H "Content-Type: application/json" \\
  -d '{{"documents":[{{"text":"smoke"}}]}}')
echo "  RAG /ingest HTTP: $STATUS  (401=live+auth)"

echo "=== DONE ===" && date
"""

def connect(max_wait=360):
    deadline = time.time() + max_wait
    attempt  = 0
    while time.time() < deadline:
        attempt += 1
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(HOST, username=USER, password=PASSWORD, timeout=15)
            print(f"[OK] Connected (attempt {attempt})")
            return ssh
        except Exception as exc:
            remaining = int(deadline - time.time())
            print(f"  [{attempt}] Not ready ({type(exc).__name__}). Retrying in 15s... ({remaining}s left)")
            time.sleep(15)
    raise RuntimeError("Server did not respond within timeout")

def rq(ssh, cmd, timeout=20):
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    stdout.channel.recv_exit_status()
    return out.strip()

# ── Connect ───────────────────────────────────────────────────────────────────
print("Waiting for server ...")
ssh = connect()

# ── Upload updated vector-store files ────────────────────────────────────────
print("\n[1/3] Uploading updated vector-store files ...")
sftp = ssh.open_sftp()
for local_rel, remote_rel in [
    ("vector-store/requirements.txt",      "vector-store/requirements.txt"),
    ("vector-store/Dockerfile",            "vector-store/Dockerfile"),
    ("vector-store/app/vector_store.py",   "vector-store/app/vector_store.py"),
    ("vector-store/app/config.py",         "vector-store/app/config.py"),
]:
    local  = os.path.join(BASE, local_rel)
    remote = f"{DIR}/{remote_rel}"
    print(f"  {local_rel} -> {remote}")
    sftp.put(local, remote)

# Kill any previous stuck build / nohup jobs
rq(ssh, "pkill -f deploy_finish 2>/dev/null || true; pkill -f pb_deploy 2>/dev/null || true")
time.sleep(2)

# Upload shell script
with sftp.open("/tmp/pb_deploy.sh", "w") as f:
    f.write(REMOTE_SCRIPT)
sftp.close()
rq(ssh, "chmod +x /tmp/pb_deploy.sh")

# ── Start detached build ──────────────────────────────────────────────────────
print("\n[2/3] Starting detached build (nohup) ...")
rq(ssh, f"nohup bash /tmp/pb_deploy.sh > {LOG} 2>&1 &")
print(f"  Build running. Log: {LOG}")

# ── Poll ──────────────────────────────────────────────────────────────────────
print("\n[3/3] Polling every 20s (max 30 min) ...")
last_line = 0
for tick in range(90):
    time.sleep(20)
    try:
        # Tail new content
        tail = rq(ssh, f"tail -n +{last_line+1} {LOG} 2>/dev/null", timeout=15)
        if tail:
            for ln in tail.split("\n"):
                print(f"  {ln}")
            last_line += len(tail.split("\n"))
        # DONE check using grep -q (exit 0 = found, exit 1 = not found)
        done = rq(ssh, f"grep -q '=== DONE ===' {LOG} 2>/dev/null && echo YES || echo NO")
        if "YES" in done:
            print("\n[OK] Build finished!")
            break
    except Exception as exc:
        print(f"  Poll error: {exc}")
        try:
            ssh = connect(max_wait=60)
        except Exception:
            print("  Still reconnecting...")
        continue

# ── Final output ──────────────────────────────────────────────────────────────
print("\n=== Final 50 log lines ===")
try:
    print(rq(ssh, f"tail -50 {LOG} 2>/dev/null", timeout=20))
except Exception:
    pass

print(f"""
============================================================
  Deployment finished.

  Open WebUI    -> http://{HOST}:3000
  Contract Hub  -> http://{HOST}:3001
  Orchestrator  -> http://{HOST}:8000

  RAG endpoints (Clerk Bearer required):
    POST /api/v1/rag/ingest
    POST /api/v1/rag/query
    GET  /api/v1/rag/stats
============================================================
""")
ssh.close()
