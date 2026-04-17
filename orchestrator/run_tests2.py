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

with open("test_results_output.txt", "w") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write("\n=== RETURN CODE ===\n")
    f.write(str(result.returncode))

print("Done - check test_results_output.txt")
