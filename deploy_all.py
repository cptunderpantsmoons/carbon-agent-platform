"""
deploy_all.py — Push all Carbon + Contract Hub changes to the production server.

Steps:
  1. Upload updated rag.py (orchestrator ingest endpoint)
  2. Upload updated docker-compose.yml (adds chromadb / vector-store / contract-hub)
  3. Bundle and upload contract-hub source (minus node_modules / .next)
  4. Patch .env with new variables
  5. Build and (re)start the full stack
  6. Health-check all services
"""

import io
import os
import sys
import tarfile
import time
import paramiko

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
DIR      = "/opt/carbon-agent-platform"
HUB_DIR  = "/opt/contract-hub"

BASE = os.path.dirname(os.path.abspath(__file__))
CONTRACT_HUB_LOCAL = r"C:\Users\MoonBuggy\.config\superpowers\worktrees\contract-hub\feat-contract-hub-carbon-rag-deploy"

# Extra env vars to add/update on the server
ENV_UPDATES = {
    "RAG_FIXED_TENANT_ID":      "contract-hub-tenant",
    "VECTOR_STORE_URL":         "http://vector-store:8000",
    "CONTRACT_HUB_PATH":        HUB_DIR,
    "CONTRACT_HUB_PORT":        "3002",
    "CONTRACT_HUB_POSTGRES_PORT":"5433",
    "CONTRACT_HUB_POSTGRES_PASSWORD":"ContractHub2026!",
    "CONTRACT_HUB_TENANT_ID":   "contract-hub-tenant",
    "CORS_ALLOWED_ORIGINS":     "http://187.127.112.59:3000,http://187.127.112.59:3001,http://187.127.112.59:3002,http://187.127.112.59:8000",
}

# Contract-hub directories / files to SKIP when bundling
SKIP_DIRS  = {
    "node_modules", ".next", ".git", "_gen", "mkdir", "echo",
    "Directories created", "prompts", "skills", "tests",
}
SKIP_EXTS  = {".png", ".jpg", ".jpeg", ".log", ".tsbuildinfo"}
SKIP_FILES = {
    "README.md", "DESIGN.md", "AGENTS.md", "CLAUDE.md",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(ssh, cmd, timeout=300):
    print(f"\n$ {cmd}", flush=True)
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = []
    for line in iter(stdout.readline, ""):
        print(f"  {line}", end="", flush=True)
        out.append(line)
    rc = stdout.channel.recv_exit_status()
    return rc, "".join(out)


def sftp_put(sftp, local, remote):
    print(f"  upload: {local} -> {remote}", flush=True)
    sftp.put(local, remote)


def make_contract_hub_tarball() -> bytes:
    """Bundle contract-hub source into an in-memory tar.gz."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for root, dirs, files in os.walk(CONTRACT_HUB_LOCAL):
            # Prune unwanted dirs in-place
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for fname in files:
                _, ext = os.path.splitext(fname)
                if fname in SKIP_FILES or ext in SKIP_EXTS:
                    continue
                full = os.path.join(root, fname)
                rel  = os.path.relpath(full, CONTRACT_HUB_LOCAL)
                arc  = os.path.join("contract-hub", rel).replace("\\", "/")
                tf.add(full, arcname=arc)
    return buf.getvalue()


# ── Main ──────────────────────────────────────────────────────────────────────

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
print("[OK] Connected to server")

sftp = ssh.open_sftp()

# ── Step 1: upload rag.py ────────────────────────────────────────────────────
print("\n[1/6] Uploading orchestrator/app/rag.py ...")
local_rag  = os.path.join(BASE, "orchestrator", "app", "rag.py")
remote_rag = f"{DIR}/orchestrator/app/rag.py"
sftp_put(sftp, local_rag, remote_rag)

# ── Step 1b: upload vector-store Dockerfile (now has build tools) ────────────
print("\n[1b] Uploading vector-store/Dockerfile ...")
sftp_put(sftp,
         os.path.join(BASE, "vector-store", "Dockerfile"),
         f"{DIR}/vector-store/Dockerfile")

# ── Step 2: upload docker-compose.yml ────────────────────────────────────────
print("\n[2/6] Uploading docker-compose.yml ...")
sftp_put(sftp, os.path.join(BASE, "docker-compose.yml"), f"{DIR}/docker-compose.yml")

# ── Step 3: bundle and upload contract-hub ────────────────────────────────────
print("\n[3/6] Bundling contract-hub source (~may take a moment) ...")
tarball = make_contract_hub_tarball()
print(f"  Bundle size: {len(tarball) / 1024 / 1024:.1f} MB")

remote_tar = "/tmp/contract-hub.tar.gz"
with sftp.open(remote_tar, "wb") as fh:
    fh.write(tarball)
print(f"  Uploaded to {remote_tar}")

run(ssh, f"rm -rf {HUB_DIR} && mkdir -p /opt")
run(ssh, f"tar -xzf {remote_tar} -C /opt")
run(ssh, f"rm -f {remote_tar}")
print(f"  Extracted to {HUB_DIR}")

# ── Step 4: patch .env ────────────────────────────────────────────────────────
print("\n[4/6] Patching .env ...")
for key, val in ENV_UPDATES.items():
    run(ssh,
        f"grep -q '^{key}=' {DIR}/.env "
        f"&& sed -i 's|^{key}=.*|{key}={val}|' {DIR}/.env "
        f"|| echo '{key}={val}' >> {DIR}/.env")

# Show RAG-related env vars
run(ssh, f"grep -E 'RAG|VECTOR|CONTRACT_HUB|CORS' {DIR}/.env | grep -v '^#'")

sftp.close()

# ── Step 5: build + start full stack ─────────────────────────────────────────
print("\n[5/6] Building images (this takes a few minutes) ...")
rc, _ = run(ssh, f"cd {DIR} && docker compose build orchestrator vector-store contract-hub", timeout=900)
if rc != 0:
    print("[FAIL] Build failed -- check output above.")
    ssh.close()
    sys.exit(1)

print("\n  Starting full stack ...")
run(ssh,
    f"cd {DIR} && docker compose up -d --remove-orphans",
    timeout=120)

# Run Contract Hub DB migrations
print("\n  Running contract-hub DB migrations ...")
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

# ── Step 6: health checks ─────────────────────────────────────────────────────
print("\n[6/6] Waiting 45 s then health-checking ...")
time.sleep(45)

checks = [
    ("Orchestrator",  "curl -sf http://localhost:8000/health"),
    ("Vector-store",  "curl -sf http://localhost:8000/health"),   # same port, routed by name internally
    ("Open-WebUI",    "curl -sf http://localhost:3000/health"),
    ("Contract-Hub",  "wget -qO- http://localhost:3002/api/health > /dev/null 2>&1 && echo ok"),
]

# Use docker inspect for internal services
run(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
run(ssh, "curl -sf http://localhost:8000/health    && echo '  Orchestrator  OK' || echo '  Orchestrator  FAIL'")
run(ssh, "curl -sf http://localhost:3000/health    && echo '  Open-WebUI    OK' || echo '  Open-WebUI    FAIL'")
run(ssh, "wget -qO- http://localhost:3002/api/health > /dev/null 2>&1 && echo '  Contract-Hub  OK' || echo '  Contract-Hub  FAIL'")

print(f"""
============================================================
  Deployment complete!
------------------------------------------------------------
  Open WebUI    -> http://{HOST}:3000
  Contract Hub  -> http://{HOST}:3002
  Orchestrator  -> http://{HOST}:8000
------------------------------------------------------------
  RAG endpoint  -> POST /api/v1/rag/ingest
                   POST /api/v1/rag/query
                   GET  /api/v1/rag/stats
============================================================
""")

ssh.close()
