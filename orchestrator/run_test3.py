"""Test runner that writes to file."""

import subprocess
import sys
import os

os.chdir(
    r"c:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform\orchestrator"
)

# First test imports
print("Testing imports...")
try:
    exec("from app.models import User, Session, SessionStatus, AuditLog, UserStatus")
    print("  models import: OK")
except Exception as e:
    print(f"  models import: FAIL - {e}")

# Run test_models
outfile = r"c:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform\orchestrator\test_output.txt"
cmd = [
    sys.executable,
    "-B",
    "-m",
    "pytest",
    "tests/test_models.py",
    "-v",
    "--tb=short",
    "-p",
    "no:anyio",
]
proc = subprocess.Popen(
    cmd, stdout=open(outfile, "w"), stderr=subprocess.STDOUT, text=True
)
try:
    proc.wait(timeout=60)
    print(f"test_models exit: {proc.returncode}")
except subprocess.TimeoutExpired:
    proc.kill()
    print("test_models: TIMED OUT")
print(f"Output written to {outfile}")
