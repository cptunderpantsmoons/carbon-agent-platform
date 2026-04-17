#!/usr/bin/env python
"""Run tests and capture output."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
    capture_output=True,
    text=True,
    cwd=r"c:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform\orchestrator"
)

print("=== STDOUT ===")
print(result.stdout)
print("=== STDERR ===")
print(result.stderr)
print("=== RETURN CODE ===")
print(result.returncode)
