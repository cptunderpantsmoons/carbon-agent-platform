"""
finish_deploy.py
Waits for the server to come back online, then:
  1. Builds vector-store  (sequential — avoids OOM)
  2. Builds contract-hub  (sequential)
  3. Starts all services
  4. Creates contracthub DB + runs migrations
  5. Health checks + RAG smoke-test
"""
import time
import paramiko

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
DIR      = "/opt/carbon-agent-platform"

def connect(max_wait=300):
    """Retry SSH connection every 15 s for up to max_wait seconds."""
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
            print(f"  [{attempt}] Not ready ({exc}). Retrying in 15 s ... ({remaining}s left)")
            time.sleep(15)
    raise RuntimeError("Server did not come back within timeout")

def run(ssh, cmd, timeout=600):
    print(f"\n$ {cmd}", flush=True)
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = []
    for line in iter(stdout.readline, ""):
        print(f"  {line}", end="", flush=True)
        out.append(line)
    rc = stdout.channel.recv_exit_status()
    return rc, "".join(out)

# ── Wait for server ────────────────────────────────────────────────────────────
print("Waiting for server to come back online ...")
ssh = connect(max_wait=360)

# ── Step 1: build SEQUENTIALLY to avoid OOM ───────────────────────────────────
print("\n[1/5] Building vector-store (C++ compile, ~5-8 min) ...")
rc, _ = run(ssh,
    f"cd {DIR} && docker compose build --no-cache vector-store",
    timeout=600)
if rc != 0:
    print("[FAIL] vector-store build failed — see above")
    ssh.close()
    raise SystemExit(1)
print("  vector-store built OK")

print("\n[2/5] Building contract-hub (Next.js, ~3-5 min) ...")
rc, _ = run(ssh,
    f"cd {DIR} && docker compose build contract-hub",
    timeout=480)
if rc != 0:
    print("[FAIL] contract-hub build failed — see above")
    ssh.close()
    raise SystemExit(1)
print("  contract-hub built OK")

# ── Step 2: start all services ────────────────────────────────────────────────
print("\n[3/5] Starting full stack ...")
run(ssh, f"cd {DIR} && docker compose up -d --remove-orphans", timeout=120)

# ── Step 3: DB setup ──────────────────────────────────────────────────────────
print("\n[4/5] Waiting for contract-hub-postgres and running migrations ...")
time.sleep(15)   # let postgres settle
run(ssh, f"""bash -lc '
if docker exec -e PGPASSWORD="ContractHub2026!" carbon-agent-platform-contract-hub-postgres-1 \
  psql -U contracthub -d contracthub -tAc "select to_regclass(\\$\\$public.documents\\$\\$)" | grep -q documents; then
  echo "  Contract Hub schema already present, skipping bootstrap migrations."
else
  for migration in 0000_violet_slipstream.sql 0001_document_storage_fallback.sql 0002_anthropic_oauth.sql 0003_glossy_fixer.sql; do
    echo "  Applying $migration"
    cat {DIR}/lib/db/migrations/$migration | docker exec -i -e PGPASSWORD="ContractHub2026!" carbon-agent-platform-contract-hub-postgres-1 \
      psql -U contracthub -d contracthub -v ON_ERROR_STOP=1
  done
fi
'""", timeout=1200)

# ── Step 4: health checks ─────────────────────────────────────────────────────
print("\n[5/5] Waiting 45 s for services to become healthy ...")
time.sleep(45)

run(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
run(ssh, "curl -sf http://localhost:8000/health && echo '  Orchestrator  OK' || echo '  Orchestrator  FAIL'")
run(ssh, "curl -sf http://localhost:3000/health && echo '  Open-WebUI    OK' || echo '  Open-WebUI    FAIL'")
run(ssh, "wget -qO- http://localhost:3002/api/health > /dev/null 2>&1 && echo '  Contract-Hub  OK' || echo '  Contract-Hub  FAIL'")

# RAG smoke-test
_, out = run(ssh,
    "curl -s -o /dev/null -w '%{http_code}' "
    "-X POST http://localhost:8000/api/v1/rag/ingest "
    "-H 'Content-Type: application/json' "
    "-d '{\"documents\":[{\"text\":\"test\"}]}'")
status = out.strip()
verdict = "live + auth enforced" if status == "401" else ("endpoint missing" if status == "404" else status)
print(f"\n  RAG /ingest smoke-test: HTTP {status} ({verdict})")

print(f"""
============================================================
  Deployment complete!

  Open WebUI    -> http://{HOST}:3000
  Contract Hub  -> http://{HOST}:3002
  Orchestrator  -> http://{HOST}:8000

  RAG endpoints (need Clerk Bearer token):
    POST /api/v1/rag/ingest
    POST /api/v1/rag/query
    GET  /api/v1/rag/stats
============================================================
""")
ssh.close()
