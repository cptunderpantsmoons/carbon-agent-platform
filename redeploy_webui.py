"""Rebuild and restart Open WebUI only."""
import paramiko, time, sys

HOST='187.127.112.59'; USER='root'; PASSWORD='Letmein7009??'
DIR='/opt/carbon-agent-platform'

def run(ssh, cmd, timeout=300):
    print(f'\n$ {cmd}', flush=True)
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    for line in iter(stdout.readline, ''):
        print(f'  {line}', end='', flush=True)
    return stdout.channel.recv_exit_status()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
print('Connected!')

run(ssh, f'cd {DIR} && git pull origin master', 60)
run(ssh, f'cd {DIR} && docker compose stop open-webui && docker compose rm -f open-webui', 30)
run(ssh, f'cd {DIR} && docker compose build open-webui', 300)
run(ssh, f'cd {DIR} && docker compose up -d open-webui', 60)
print('\nWaiting 45s for WebUI to boot...')
time.sleep(45)
code = run(ssh, 'curl -sf http://localhost:3000/health && echo WEBUI_OK || echo WEBUI_FAIL', 15)
run(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", 15)

print('\n' + '='*60)
if code == 0:
    print(f'  >> ALL 5/5 SERVICES HEALTHY!')
    print(f'  Open WebUI : http://{HOST}:3000')
    print(f'  Orchestrator: http://{HOST}:8000/docs')
    print(f'  Adapter    : http://{HOST}:8001/docs')
else:
    run(ssh, 'docker logs carbon-agent-platform-open-webui-1 --tail 30', 30)
print('='*60)
ssh.close()
