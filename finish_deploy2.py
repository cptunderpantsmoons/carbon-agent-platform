"""
finish_deploy2.py
Push a shell script to the server, run it detached (nohup), then poll its log.
This avoids killing long docker builds when our SSH connection times out.
"""
import time
import paramiko

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
DIR      = "/opt/carbon-agent-platform"
LOG      = "/tmp/deploy_finish.log"

SHELL_SCRIPT = f"""#!/bin/bash
set -e
LOG="{LOG}"
exec > "$LOG" 2>&1

echo "=== [1/4] Building vector-store ===" && date
cd {DIR}
docker compose build --no-cache vector-store
echo "=== vector-store OK ===" && date

echo "=== [2/4] Building contract-hub ===" && date
docker compose build contract-hub
echo "=== contract-hub OK ===" && date

echo "=== [3/4] Starting stack ===" && date
docker compose up -d --remove-orphans
sleep 20

echo "=== [4/4] DB setup ===" && date
docker exec carbon-agent-platform-postgres-1 \\
  psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='contracthub'" \\
  | grep -q 1 \\
  || docker exec carbon-agent-platform-postgres-1 \\
     psql -U postgres -c 'CREATE DATABASE contracthub'

docker exec carbon-agent-platform-contract-hub-1 \\
  npx drizzle-kit migrate 2>&1 || true

echo "=== Health checks ===" && date
docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'
curl -sf http://localhost:8000/health && echo '  Orchestrator  OK' || echo '  Orchestrator  FAIL'
curl -sf http://localhost:3000/health && echo '  Open-WebUI    OK' || echo '  Open-WebUI    FAIL'
wget -qO- http://localhost:3001/ > /dev/null 2>&1 && echo '  Contract-Hub  OK' || echo '  Contract-Hub  FAIL'

# RAG smoke-test
STATUS=$(curl -s -o /dev/null -w '%{{http_code}}' \\
  -X POST http://localhost:8000/api/v1/rag/ingest \\
  -H 'Content-Type: application/json' \\
  -d '{{"documents":[{{"text":"smoke-test"}}]}}')
echo "  RAG /ingest HTTP: $STATUS  (401=live)"

echo "=== DONE ===" && date
"""

def connect(max_wait=240):
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
            print(f"  [{attempt}] Not ready. Retrying in 15s... ({remaining}s left)")
            time.sleep(15)
    raise RuntimeError("Server did not respond")

def run_quick(ssh, cmd, timeout=30):
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    stdout.channel.recv_exit_status()
    return out.strip()

print("Connecting ...")
ssh = connect()

# Upload shell script
print("Uploading finish script ...")
sftp = ssh.open_sftp()
with sftp.open("/tmp/deploy_finish.sh", "w") as f:
    f.write(SHELL_SCRIPT)
sftp.close()
run_quick(ssh, "chmod +x /tmp/deploy_finish.sh")

# Kill any stuck previous build
run_quick(ssh, "pkill -f 'docker compose build' 2>/dev/null || true")
time.sleep(3)

# Start the script in background with nohup
print("Starting detached build (nohup) ...")
run_quick(ssh, f"nohup bash /tmp/deploy_finish.sh > {LOG} 2>&1 & echo $!")
print(f"Build started. Log: {LOG}")

# Poll the log every 20 seconds
print("\nPolling log (Ctrl-C safe — build continues on server regardless) ...")
last_line = 0
total_wait = 0
max_wait   = 1200  # 20 minutes

while total_wait < max_wait:
    time.sleep(20)
    total_wait += 20

    try:
        out = run_quick(ssh, f"tail -n +{last_line + 1} {LOG} 2>/dev/null", timeout=15)
        if out:
            lines = out.split("\n")
            for line in lines:
                print(f"  {line}")
            last_line += len(lines)
    except Exception as exc:
        print(f"  [poll error: {exc}]")
        try:
            ssh = connect(max_wait=60)
        except Exception:
            print("  Server unreachable, will retry ...")
        continue

    # Check if done
    try:
        done_check = run_quick(ssh, f"grep -c '=== DONE ===' {LOG} 2>/dev/null || echo 0")
        if done_check.strip() != "0":
            print("\nBuild finished!")
            break
    except Exception:
        pass

# Final summary
try:
    print("\n=== Final log output ===")
    final = run_quick(ssh, f"tail -30 {LOG} 2>/dev/null", timeout=20)
    print(final)
except Exception:
    pass

print(f"""
============================================================
  Stack should be live!

  Open WebUI    -> http://{HOST}:3000
  Contract Hub  -> http://{HOST}:3001
  Orchestrator  -> http://{HOST}:8000
============================================================
""")
ssh.close()
