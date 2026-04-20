"""
Carbon Agent Platform - VPS Deployment Script
Connects via SSH and deploys the full stack
"""

import paramiko
import time
import sys
import secrets
import os
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HOST = "187.127.112.59"
USER = "root"
PASSWORD = "Letmein7009??"
REPO = "https://github.com/cptunderpantsmoons/carbon-agent-platform.git"
DIR = "/opt/carbon-agent-platform"
HUB_DIR = "/opt/carbon-agent-dashboard"
BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_BASE_DIR = BASE_DIR.parent / "carbon-agent-dashboard"

SYNC_FILES = [
    "docker-compose.yml",
    "docker-compose.dev.yml",
    "docker-compose.prod.yml",
    "README.md",
    ".env.example",
    ".env.production.example",
    "adapter/app/config.py",
    "adapter/requirements.txt",
    "open-webui/Dockerfile",
    "open-webui/entrypoint.sh",
    "adapter/app/main.py",
]

DASHBOARD_SYNC_FILES = [
    "Dockerfile",
    ".dockerignore",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "eslint.config.mjs",
    "postcss.config.mjs",
    "next-env.d.ts",
    "next.config.ts",
    "middleware.ts",
    "app/layout.tsx",
    "app/page.tsx",
    "app/globals.css",
    "app/health/route.ts",
    "app/dashboard/page.tsx",
    "app/chat/page.tsx",
    "app/benchmarks/page.tsx",
    "app/admin/page.tsx",
    "app/sign-in/page.tsx",
    "app/sign-up/page.tsx",
    "app/components/shell/sidebar.tsx",
    "app/components/shell/top-bar.tsx",
    "app/components/shell/app-shell.tsx",
    "app/components/theme-toggle.tsx",
    "app/lib/admin-agent.js",
    "app/lib/model-catalog.js",
    "app/api/admin-agent/route.ts",
    "app/api/chat/route.ts",
    "app/api/benchmarks/route.ts",
    "app/api/documents/route.ts",
    "app/api/orchestrator/[...path]/route.ts",
    "app/contracts/page.tsx",
    "app/documents/page.tsx",
    "app/skills/page.tsx",
    "app/lib/theme/provider.tsx",
    "app/lib/theme/engine.ts",
    "app/lib/theme/tokens.ts",
    "app/lib/theme/telemetry.ts",
    "public/.gitkeep",
    "tests/admin-agent.test.mjs",
    "tests/model-catalog.test.mjs",
    "tests/auth-smoke.test.mjs",
    "tests/chat-route.test.mjs",
]

ORCHESTRATOR_SYNC_FILES = [
    "orchestrator/app/models.py",
    "orchestrator/app/schemas.py",
    "orchestrator/app/main.py",
    "orchestrator/app/model_policy.py",
    "orchestrator/tests/test_model_policy.py",
]

# ── Colours (ANSI, safe for Linux terminal via SSH) ──────────────────────────
G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
B = "\033[94m"  # blue
E = "\033[0m"  # reset


def run(ssh, cmd, timeout=300, show=True, check=True):
    """Run a command over SSH, stream output, return (exit_code, stdout_str)."""
    if show:
        print(f"\n{B}$ {cmd}{E}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    buf = ""
    for line in iter(stdout.readline, ""):
        buf += line
        if show:
            print(f"  {line}", end="", flush=True)
    code = stdout.channel.recv_exit_status()
    if code != 0 and show:
        err = stderr.read().decode().strip()
        if err:
            print(f"  {R}[err]{E} {err}")
    if check and code != 0:
        raise RuntimeError(f"Command failed (exit {code}): {cmd}")
    return code, buf


def step(n, total, msg):
    print(f"\n{Y}[{n}/{total}] {msg}{E}")


def ok(msg):
    print(f"  {G}[OK]{E} {msg}")


def warn(msg):
    print(f"  {Y}[WARN]{E} {msg}")


def sync_files(ssh, files):
    """Upload local workspace files to the remote checkout."""
    sftp = ssh.open_sftp()
    try:
        for rel_path in files:
            local_path = BASE_DIR / rel_path
            remote_path = f"{DIR}/{rel_path.replace(os.sep, '/')}"
            if not local_path.exists():
                raise FileNotFoundError(f"Missing local file: {local_path}")

            remote_dir = os.path.dirname(remote_path)
            run(ssh, f"mkdir -p {remote_dir}", timeout=30, show=False)
            content = local_path.read_text(encoding="utf-8")
            content = content.replace("\r\n", "\n")
            with sftp.file(remote_path, "w") as remote_file:
                remote_file.write(content)
    finally:
        sftp.close()


def sync_dashboard_files(ssh, files):
    """Upload local dashboard files to the remote checkout."""
    sftp = ssh.open_sftp()
    try:
        for rel_path in files:
            local_path = DASHBOARD_BASE_DIR / rel_path
            remote_path = f"{HUB_DIR}/{rel_path.replace(os.sep, '/')}"
            if not local_path.exists():
                raise FileNotFoundError(f"Missing local dashboard file: {local_path}")

            remote_dir = os.path.dirname(remote_path)
            run(ssh, f"mkdir -p {remote_dir}", timeout=30, show=False)
            content = local_path.read_text(encoding="utf-8")
            content = content.replace("\r\n", "\n")
            with sftp.file(remote_path, "w") as remote_file:
                remote_file.write(content)
    finally:
        sftp.close()


def sync_orchestrator_files(ssh, files):
    """Upload local orchestrator files to the remote platform checkout."""
    sftp = ssh.open_sftp()
    try:
        for rel_path in files:
            local_path = BASE_DIR / rel_path
            remote_path = f"{DIR}/{rel_path.replace(os.sep, '/')}"
            if not local_path.exists():
                raise FileNotFoundError(
                    f"Missing local orchestrator file: {local_path}"
                )

            remote_dir = os.path.dirname(remote_path)
            run(ssh, f"mkdir -p {remote_dir}", timeout=30, show=False)
            content = local_path.read_text(encoding="utf-8")
            content = content.replace("\r\n", "\n")
            with sftp.file(remote_path, "w") as remote_file:
                remote_file.write(content)
    finally:
        sftp.close()


def cleanup_deleted_dashboard_files(ssh):
    """Remove legacy files that no longer exist in the new architecture."""
    deleted = [
        "app/components/intelligence-hub.tsx",
        "app/lib/clerk.tsx",
        "app/lib/provider-exec.js",
    ]
    for rel_path in deleted:
        remote_path = f"{HUB_DIR}/{rel_path}"
        run(ssh, f"rm -f {remote_path}", timeout=30, show=False)


def parse_env_text(env_text):
    """Parse simple KEY=VALUE lines into a dictionary."""
    parsed = {}
    for raw_line in env_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key] = value
    return parsed


def serialize_env(env_map):
    """Serialize an environment mapping as KEY=VALUE lines."""
    return "\n".join(f"{key}={value}" for key, value in env_map.items()) + "\n"


def _resolve_value(name, *candidates):
    """Return the first non-empty candidate or raise for missing required values."""
    for candidate in candidates:
        value = (candidate or "").strip()
        if value:
            return value
    raise RuntimeError(f"Missing required value for {name}")


def _is_local_or_placeholder_url(url):
    """Reject localhost and placeholder Clerk URLs for deployed environments."""
    if not url:
        return True
    lowered = url.strip().lower()
    return (
        lowered.startswith("http://localhost")
        or lowered.startswith("https://localhost")
        or lowered.startswith("http://127.")
        or lowered.startswith("https://127.")
        or lowered.startswith("http://0.0.0.0")
        or lowered in {"pk_test_dummy", "sk_test_dummy"}
    )


def deploy():
    STEPS = 12
    print(f"\n{'=' * 60}")
    print("  Carbon Agent Platform -- VPS Deployment")
    print(f"  Target : {HOST}")
    print(f"{'=' * 60}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    step(1, STEPS, f"Connecting to {HOST} ...")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    ok("Connected!")

    # ── 2. Docker ────────────────────────────────────────────────────────────
    step(2, STEPS, "Ensuring Docker is installed ...")
    run(
        ssh,
        "apt-get update -qq && apt-get install -y -qq curl git ca-certificates",
        timeout=180,
        show=False,
    )
    code, _ = run(ssh, "docker --version", show=False, check=False)
    if code != 0:
        print("  Installing Docker ...")
        run(ssh, "curl -fsSL https://get.docker.com | sh", timeout=300)
        run(ssh, "systemctl enable docker && systemctl start docker")
    ok("Docker ready")

    # ── 3. Repo ──────────────────────────────────────────────────────────────
    step(3, STEPS, "Cloning / updating repo ...")
    code, _ = run(ssh, f"test -d {DIR}/.git", show=False, check=False)
    BRANCH = "feat/corporate-carbon-hub-pass-1"
    if code == 0:
        run(
            ssh,
            f"cd {DIR} && git fetch origin && git reset --hard origin/{BRANCH}",
            timeout=60,
        )
    else:
        run(ssh, f"git clone -b {BRANCH} {REPO} {DIR}", timeout=120)
    ok("Repo up to date")

    step(4, STEPS, "Syncing local fix files to the VPS checkout ...")
    sync_files(ssh, SYNC_FILES)
    ok("Workspace files uploaded")

    step(5, STEPS, "Syncing Intelligence Hub files to the VPS checkout ...")
    run(ssh, f"mkdir -p {HUB_DIR}", timeout=30, show=False)
    sync_dashboard_files(ssh, DASHBOARD_SYNC_FILES)
    cleanup_deleted_dashboard_files(ssh)
    ok("Dashboard workspace files uploaded")

    step(5, STEPS, "Syncing orchestrator policy files to the VPS checkout ...")
    sync_orchestrator_files(ssh, ORCHESTRATOR_SYNC_FILES)
    ok("Orchestrator policy files uploaded")

    # ── 4. Env file ──────────────────────────────────────────────────────────
    step(6, STEPS, "Writing .env ...")

    # Read existing server env first (needed for fallbacks)
    existing_env = {}
    code, existing_text = run(ssh, f"cat {DIR}/.env", show=False, check=False)
    if code == 0:
        existing_env = parse_env_text(existing_text)

    webui_admin_email = "admin@carbon.local"
    webui_admin_password = secrets.token_urlsafe(20)
    admin_agent_control_token = os.environ.get(
        "ADMIN_AGENT_CONTROL_TOKEN", ""
    ).strip() or secrets.token_urlsafe(24)
    admin_agent_ssh_target = (
        os.environ.get("ADMIN_AGENT_SSH_TARGET", "").strip()
        or "64Hk1NNpE19r6RaiWdwE7Pk7MgNThWKo@ssh.app.daytona.io"
    )
    deepseek_api_key = _resolve_value(
        "DEEPSEEK_API_KEY",
        os.environ.get("DEEPSEEK_API_KEY"),
        os.environ.get("LLM_API_KEY"),
        existing_env.get("DEEPSEEK_API_KEY"),
        existing_env.get("LLM_API_KEY"),
    )

    local_dashboard_env = DASHBOARD_BASE_DIR / ".env.local"
    local_env = {}
    if local_dashboard_env.exists():
        local_env = parse_env_text(local_dashboard_env.read_text(encoding="utf-8"))
    # Read Clerk settings from local dashboard .env.local, env vars, or existing server env.
    clerk_publishable_key = _resolve_value(
        "CLERK_PUBLISHABLE_KEY",
        os.environ.get("CLERK_PUBLISHABLE_KEY"),
        local_env.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"),
        local_env.get("CLERK_PUBLISHABLE_KEY"),
        existing_env.get("CLERK_PUBLISHABLE_KEY"),
    )
    clerk_secret_key = _resolve_value(
        "CLERK_SECRET_KEY",
        os.environ.get("CLERK_SECRET_KEY"),
        local_env.get("CLERK_SECRET_KEY"),
        existing_env.get("CLERK_SECRET_KEY"),
    )
    clerk_frontend_api_url = _resolve_value(
        "CLERK_FRONTEND_API_URL",
        os.environ.get("CLERK_FRONTEND_API_URL"),
        local_env.get("NEXT_PUBLIC_CLERK_FRONTEND_API_URL"),
        local_env.get("CLERK_FRONTEND_API_URL"),
        existing_env.get("CLERK_FRONTEND_API_URL"),
    )
    # Override localhost placeholder with derived Clerk domain for test keys
    if _is_local_or_placeholder_url(
        clerk_frontend_api_url
    ) and clerk_publishable_key.startswith("pk_test_"):
        import base64

        domain = (
            base64.b64decode(clerk_publishable_key.split("_", 2)[2])
            .decode()
            .rstrip("$")
        )
        clerk_frontend_api_url = f"https://{domain}"

    if _is_local_or_placeholder_url(clerk_publishable_key):
        raise RuntimeError(
            "Set a real CLERK_PUBLISHABLE_KEY before running deploy_to_server.py"
        )
    if _is_local_or_placeholder_url(clerk_secret_key):
        raise RuntimeError(
            "Set a real CLERK_SECRET_KEY before running deploy_to_server.py"
        )
    if _is_local_or_placeholder_url(clerk_frontend_api_url):
        raise RuntimeError(
            "Set a real CLERK_FRONTEND_API_URL before running deploy_to_server.py"
        )

    desired_env = {
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "CarbonDB2024!",
        "POSTGRES_DB": "carbon_platform",
        "DATABASE_URL": "postgresql://postgres:CarbonDB2024!@postgres:5432/carbon_platform",
        "REDIS_URL": "redis://redis:6379/0",
        "RATE_LIMIT_STORAGE_URI": "redis://redis:6379/0",
        "ORCHESTRATOR_PORT": "8000",
        "ADAPTER_PORT": "8001",
        "WEBUI_PORT": "3000",
        "AGENT_DOCKER_IMAGE": "carbon-agent-adapter:latest",
        "AGENT_MEMORY_LIMIT": "512m",
        "AGENT_CPU_NANOS": "500000000",
        "DOCKER_NETWORK": "carbon-agent-net",
        "AGENT_DOMAIN": HOST,
        "TRAEFIK_ENTRYPOINT": "web",
        "AGENT_BASE_PATH": "/agent",
        "ADMIN_AGENT_API_KEY": "dev-admin-key-2024",
        "SESSION_IDLE_TIMEOUT_MINUTES": "15",
        "SESSION_MAX_LIFETIME_HOURS": "24",
        "SESSION_SPINUP_TIMEOUT_SECONDS": "120",
        "CLERK_PUBLISHABLE_KEY": clerk_publishable_key,
        "CLERK_SECRET_KEY": clerk_secret_key,
        "CLERK_FRONTEND_API_URL": clerk_frontend_api_url,
        "CORS_ALLOWED_ORIGINS": f"http://{HOST}:3000,http://{HOST}:3001,http://{HOST}:3002,http://{HOST}:8000,http://{HOST}",
        "AUTO_CREATE_TABLES": "true",
        "WEBUI_SECRET": "dev-webui-secret-2024",
        "OPENWEBUI_API_KEY": "sk-dev-test-key",
        "OPENWEBUI_CLERK_ENABLED": "true",
        "WEBUI_ADMIN_EMAIL": webui_admin_email,
        "WEBUI_ADMIN_PASSWORD": webui_admin_password,
        "WEBUI_ADMIN_NAME": "Carbon Admin",
        "DASHBOARD_PORT": "3001",
        "AGENT_API_URL": "",
        "AGENT_API_KEY": "",
        "MODEL_NAME": "deepseek-chat",
        "LLM_PROVIDER": "deepseek",
        "LLM_BASE_URL": "https://api.deepseek.com/v1",
        "LLM_API_KEY": deepseek_api_key,
        "DEEPSEEK_API_KEY": deepseek_api_key,
        "LLM_MODEL_NAME": "deepseek-chat",
        "FEATHERLESS_API_KEY": "",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "ADMIN_AGENT_ENABLED": "true",
        "ADMIN_AGENT_SSH_TARGET": admin_agent_ssh_target,
        "ADMIN_AGENT_CONTROL_TOKEN": admin_agent_control_token,
        "ADMIN_AGENT_TIMEOUT_SECONDS": "90",
        "ADMIN_AGENT_REMOTE_DIR": DIR,
        "ADMIN_AGENT_ALLOWED_SERVICES": "orchestrator,adapter,open-webui,dashboard,vector-store,contract-hub,contract-hub-postgres,postgres,redis,chromadb",
    }

    existing_env.update(desired_env)

    sftp = ssh.open_sftp()
    try:
        with sftp.file(f"{DIR}/.env", "w") as env_file:
            env_file.write(serialize_env(existing_env))
    finally:
        sftp.close()
    ok(".env written")

    # ── 5. Docker network ────────────────────────────────────────────────────
    step(7, STEPS, "Docker network ...")
    code, _ = run(
        ssh, "docker network inspect carbon-agent-net", show=False, check=False
    )
    if code != 0:
        run(ssh, "docker network create carbon-agent-net")
    ok("Network carbon-agent-net ready")

    # ── 6. Infrastructure (postgres + redis) ─────────────────────────────────
    step(8, STEPS, "Starting PostgreSQL + Redis ...")
    run(
        ssh,
        f"cd {DIR} && docker compose -f docker-compose.infra.yml up -d postgres redis",
        timeout=120,
    )
    print("  Waiting 15s for DB ...")
    time.sleep(15)
    code, _ = run(
        ssh,
        "docker exec $(docker ps -qf 'name=.*postgres.*' | head -1) pg_isready -U postgres",
        check=False,
    )
    if code == 0:
        ok("PostgreSQL ready")
    else:
        warn("PostgreSQL not yet ready — continuing anyway")

    # ── 7. Build + start app ─────────────────────────────────────────────────
    step(9, STEPS, "Building images (grab a coffee, this takes ~5 min) ...")
    run(
        ssh,
        f"cd {DIR} && docker compose build orchestrator adapter dashboard open-webui",
        timeout=900,
    )
    ok("Images built")

    step(10, STEPS, "Starting services ...")
    run(
        ssh,
        f"cd {DIR} && docker compose up -d orchestrator adapter dashboard",
        timeout=120,
    )
    print("  Waiting 30s for orchestrator + adapter + dashboard ...")
    time.sleep(30)
    run(ssh, f"cd {DIR} && docker compose up -d open-webui", timeout=60)
    ok("Services started")

    # ── 8. Migrations ────────────────────────────────────────────────────────
    step(11, STEPS, "Running Alembic migrations ...")
    # Get the actual container name
    code, orch_id = run(
        ssh,
        "docker ps --filter 'name=orchestrator' --format '{{.Names}}' | head -1",
        show=False,
        check=False,
    )
    orch_id = orch_id.strip()
    if orch_id:
        code, _ = run(
            ssh,
            f"docker exec {orch_id} python -m alembic upgrade head",
            timeout=60,
            check=False,
        )
        if code == 0:
            ok("Migrations applied")
        else:
            warn("Migrations may have already run (AUTO_CREATE_TABLES=true) -- OK")
    else:
        warn(
            "Orchestrator container not found for migration -- AUTO_CREATE_TABLES=true will handle it"
        )

    # ── 9. Health checks ─────────────────────────────────────────────────────
    step(12, STEPS, "Health checks ...")
    time.sleep(15)

    results = {}

    # Orchestrator
    code, _ = run(ssh, "curl -sf http://localhost:8000/health", check=False, show=False)
    results["Orchestrator :8000"] = code == 0

    # Adapter
    code, _ = run(ssh, "curl -sf http://localhost:8001/health", check=False, show=False)
    results["Adapter     :8001"] = code == 0

    # Open WebUI
    code, _ = run(ssh, "curl -sf http://localhost:3000/health", check=False, show=False)
    results["Open WebUI  :3000"] = code == 0

    # Dashboard
    code, _ = run(ssh, "curl -sf http://localhost:3001/health", check=False, show=False)
    results["Dashboard   :3001"] = code == 0

    # PostgreSQL
    code, _ = run(
        ssh,
        "docker exec $(docker ps -qf 'name=.*postgres.*' | head -1) pg_isready -U postgres",
        check=False,
        show=False,
    )
    results["PostgreSQL       "] = code == 0

    # Redis
    code, _ = run(
        ssh,
        "docker exec $(docker ps -qf 'name=.*redis.*' | head -1) redis-cli ping",
        check=False,
        show=False,
    )
    results["Redis            "] = code == 0

    for name, passed in results.items():
        icon = f"{G}[OK]{E}" if passed else f"{R}[FAIL]{E}"
        print(f"  {icon} {name}")

    # Show containers
    print(f"\n{B}-- Running containers --{E}")
    run(
        ssh,
        "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
        check=False,
    )

    all_ok = all(results.values())
    print(f"\n{'=' * 60}")
    if all_ok:
        print(f"  {G}>> DEPLOYMENT SUCCESSFUL!{E}")
    else:
        print(f"  {Y}>> DEPLOYMENT COMPLETE (check any FAIL above){E}")

    print(f"\n  Open WebUI admin email    : {webui_admin_email}")
    print(f"  Open WebUI admin password : {webui_admin_password}")
    print(f"  Admin Agent SSH target    : {admin_agent_ssh_target}")
    print(f"  Admin Agent token         : {admin_agent_control_token}")

    print(f"\n  Orchestrator : http://{HOST}:8000")
    print(f"  Adapter      : http://{HOST}:8001")
    print(f"  Open WebUI   : http://{HOST}:3000")
    print(f"  Admin UI     : http://{HOST}:8000/dashboard")
    print(f"  API Docs     : http://{HOST}:8000/docs")
    print(f"{'=' * 60}\n")

    ssh.close()


if __name__ == "__main__":
    deploy()
