"""Upload updated files + kick off a nohup build. Returns in < 60 s."""
import os, time, paramiko

HOST = "187.127.112.59"; USER = "root"; PASSWORD = "Letmein7009??"
DIR  = "/opt/carbon-agent-platform"; LOG = "/tmp/pb_deploy.log"
BASE = os.path.dirname(os.path.abspath(__file__))

SCRIPT = f"""#!/bin/bash
exec > "{LOG}" 2>&1
set -e
echo "BUILD_STARTED" && date
cd {DIR}
echo "=== Building vector-store ===" && date
docker compose build --no-cache vector-store
echo "=== vector-store OK ===" && date
echo "=== Building contract-hub ===" && date
docker compose build contract-hub
echo "=== contract-hub OK ===" && date
echo "=== Starting stack ===" && date
docker compose up -d --remove-orphans
sleep 25
echo "=== DB setup ===" && date
docker exec carbon-agent-platform-postgres-1 psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='contracthub'" | grep -q 1 || docker exec carbon-agent-platform-postgres-1 psql -U postgres -c "CREATE DATABASE contracthub"
docker exec carbon-agent-platform-contract-hub-1 npx drizzle-kit migrate 2>&1 || true
echo "=== Health ===" && date
docker ps --format "table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}"
curl -sf http://localhost:8000/health && echo "Orch OK" || echo "Orch FAIL"
curl -sf http://localhost:3000/health && echo "WebUI OK" || echo "WebUI FAIL"
wget -qO- http://localhost:3001/ >/dev/null 2>&1 && echo "Hub OK" || echo "Hub FAIL"
S=$(curl -s -o /dev/null -w "%{{http_code}}" -X POST http://localhost:8000/api/v1/rag/ingest -H "Content-Type: application/json" -d '{{"documents":[{{"text":"smoke"}}]}}')
echo "RAG ingest HTTP: $S"
echo "=== DONE ===" && date
"""

def rq(ssh, cmd, timeout=20):
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    stdout.channel.recv_exit_status()
    return out.strip()

print("Connecting...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=20)
print("Connected")

sftp = ssh.open_sftp()
for local_rel, remote_rel in [
    ("vector-store/requirements.txt",    "vector-store/requirements.txt"),
    ("vector-store/Dockerfile",          "vector-store/Dockerfile"),
    ("vector-store/app/vector_store.py", "vector-store/app/vector_store.py"),
    ("vector-store/app/config.py",       "vector-store/app/config.py"),
]:
    sftp.put(os.path.join(BASE, local_rel), f"{DIR}/{remote_rel}")
    print(f"  uploaded {local_rel}")

rq(ssh, "pkill -f pb_deploy 2>/dev/null || true; sleep 1")
with sftp.open("/tmp/pb_deploy.sh", "w") as f:
    f.write(SCRIPT)
sftp.close()
rq(ssh, "chmod +x /tmp/pb_deploy.sh")
rq(ssh, f"nohup bash /tmp/pb_deploy.sh > {LOG} 2>&1 &")
print(f"Build started (nohup). Log: {LOG}")
# Verify it started
time.sleep(3)
started = rq(ssh, f"head -3 {LOG} 2>/dev/null")
print(f"Log first lines: {started}")
ssh.close()
print("Done. Run check_build.py in ~15 min to see results.")
