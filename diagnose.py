"""Quick server diagnostic."""
import paramiko

HOST = "187.127.112.59"; USER = "root"; PASSWORD = "Letmein7009??"
DIR  = "/opt/carbon-agent-platform"

def rq(ssh, cmd, timeout=20):
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    stdout.channel.recv_exit_status()
    return out.strip()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=20)

print("=== docker ps -a ===")
print(rq(ssh, "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"))

print("\n=== chromadb logs (last 20 lines) ===")
print(rq(ssh, "docker logs carbon-agent-platform-chromadb-1 --tail 20 2>&1 || echo no container"))

print("\n=== chromadb healthcheck ===")
print(rq(ssh, "docker inspect carbon-agent-platform-chromadb-1 --format '{{json .State.Health}}' 2>/dev/null | python3 -c 'import sys,json; h=json.load(sys.stdin); print(h.get(\"Status\"),\"|\",h.get(\"Log\",[{}])[-1].get(\"Output\",\"\")[:200])' || echo 'no health info'"))

print("\n=== heartbeat test ===")
print(rq(ssh, "docker exec carbon-agent-platform-chromadb-1 python3 -c \"import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/heartbeat').read())\" 2>&1 || echo 'fail'"))

print("\n=== docker-compose.yml services (grep service names) ===")
print(rq(ssh, f"grep -E '^  [a-z]' {DIR}/docker-compose.yml"))

print("\n=== volumes ===")
print(rq(ssh, "docker volume ls | grep carbon"))

ssh.close()
