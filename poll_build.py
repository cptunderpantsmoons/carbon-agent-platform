"""Poll /tmp/deploy_finish.log on the server until the build finishes."""
import time
import paramiko

HOST     = "187.127.112.59"
USER     = "root"
PASSWORD = "Letmein7009??"
LOG      = "/tmp/deploy_finish.log"

def connect():
    for _ in range(20):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(HOST, username=USER, password=PASSWORD, timeout=15)
            return ssh
        except Exception:
            time.sleep(15)
    raise RuntimeError("Cannot connect")

def rq(ssh, cmd, timeout=20):
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    stdout.channel.recv_exit_status()
    return out.strip()

print("Connecting ...")
ssh = connect()
print("[OK] Connected")

last_line = 0
for _ in range(90):    # up to 90 x 20s = 30 min
    time.sleep(20)
    try:
        # Tail new lines
        tail = rq(ssh, f"tail -n +{last_line+1} {LOG} 2>/dev/null")
        if tail:
            for ln in tail.split("\n"):
                print(f"  {ln}")
            last_line += len(tail.split("\n"))
        # Check for DONE using grep -q (exit 0 = found)
        rc_raw = rq(ssh, f"grep -q '=== DONE ===' {LOG} 2>/dev/null && echo YES || echo NO")
        if "YES" in rc_raw:
            print("\n[OK] Remote build finished!")
            break
        # Also check for error marker
        err_raw = rq(ssh, f"grep -q 'ERROR\\|failed' {LOG} 2>/dev/null && tail -5 {LOG} || echo ''")
        if err_raw.strip():
            print(f"\n[WARN] Possible error in log:\n{err_raw}")
    except Exception as exc:
        print(f"  Poll error: {exc}")
        try:
            ssh = connect()
        except Exception:
            pass
        continue

# Final summary
print("\n=== Final 40 log lines ===")
try:
    print(rq(ssh, f"tail -40 {LOG} 2>/dev/null"))
except Exception:
    pass

# Health checks
print("\n=== Health checks ===")
for label, cmd in [
    ("Orchestrator", "curl -sf http://localhost:8000/health && echo OK || echo FAIL"),
    ("Open-WebUI",   "curl -sf http://localhost:3000/health && echo OK || echo FAIL"),
    ("Contract-Hub", "wget -qO- http://localhost:3001/ >/dev/null 2>&1 && echo OK || echo FAIL"),
]:
    try:
        result = rq(ssh, cmd, timeout=10)
        print(f"  {label:15s}: {result}")
    except Exception as e:
        print(f"  {label:15s}: error ({e})")

# RAG smoke-test
try:
    status = rq(ssh,
        "curl -s -o /dev/null -w '%{http_code}' "
        "-X POST http://localhost:8000/api/v1/rag/ingest "
        "-H 'Content-Type: application/json' "
        "-d '{\"documents\":[{\"text\":\"smoke\"}]}'")
    verdict = "live+auth" if status == "401" else ("missing" if status == "404" else status)
    print(f"  RAG /ingest      : HTTP {status} ({verdict})")
except Exception as e:
    print(f"  RAG /ingest      : error ({e})")

ssh.close()
