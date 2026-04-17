#!/usr/bin/env python
"""Run tests with output captured."""
import subprocess
import sys
import os

# Change to the orchestrator directory
os.chdir(r"c:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform\orchestrator")

# Run pytest with subprocess
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-x"],
    capture_output=True,
    text=True,
    timeout=300
)

# Write to file
with open("final_test_results.txt", "w") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write(f"\n=== RETURN CODE: {result.returncode} ===\n")

print("Results written to final_test_results.txt")
print(f"Return code: {result.returncode}")
