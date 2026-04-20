"""Test runner that captures output reliably."""

import subprocess
import sys
import os

os.chdir(
    r"c:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform\orchestrator"
)

cmd = [
    sys.executable,
    "-B",
    "-m",
    "pytest",
    "tests/test_models.py",
    "-x",
    "--tb=short",
    "-p",
    "no:anyio",
    "-q",
]
print(f"CMD: {' '.join(cmd)}")
print(f"CWD: {os.getcwd()}")
proc = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
)
try:
    out, _ = proc.communicate(timeout=60)
    print(out)
    print(f"EXIT: {proc.returncode}")
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
    print(out)
    print("TIMED OUT")
