"""Check the background build log. Run this after start_build.py."""
import paramiko, time

HOST = "187.127.112.59"; USER = "root"; PASSWORD = "Letmein7009??"
LOG  = "/tmp/pb_deploy.log"

def rq(ssh, cmd, timeout=15):
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    stdout.channel.recv_exit_status()
    return out.strip()

print("Connecting...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=20)
print("Connected\n")

log_tail = rq(ssh, f"cat {LOG} 2>/dev/null | tail -60")
print(log_tail)

done   = rq(ssh, f"grep -q '=== DONE ===' {LOG} 2>/dev/null && echo YES || echo NO")
failed = rq(ssh, f"grep -cE '(failed|ERROR|exit code)' {LOG} 2>/dev/null || echo 0")
running = rq(ssh, "pgrep -f pb_deploy.sh 2>/dev/null && echo YES || echo NO")

print(f"\n--- Status ---")
print(f"DONE marker : {done}")
print(f"Error count : {failed}")
print(f"Still running: {running}")

if done == "YES":
    print("\n--- Service status ---")
    print(rq(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}'"))
    for label, cmd in [
        ("Orchestrator", "curl -sf http://localhost:8000/health && echo OK || echo FAIL"),
        ("Open-WebUI",   "curl -sf http://localhost:3000/health && echo OK || echo FAIL"),
        ("Contract-Hub", "wget -qO- http://localhost:3001/ >/dev/null 2>&1 && echo OK || echo FAIL"),
    ]:
        result = rq(ssh, cmd, timeout=10)
        print(f"  {label:15s}: {result}")
    status = rq(ssh,
        "curl -s -o /dev/null -w '%{http_code}' "
        "-X POST http://localhost:8000/api/v1/rag/ingest "
        "-H 'Content-Type: application/json' "
        "-d '{\"documents\":[{\"text\":\"smoke\"}]}'")
    print(f"  RAG /ingest      : HTTP {status} (401=live)")

ssh.close()
