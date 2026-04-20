import subprocess
import sys
import os

os.chdir(
    r"c:\Users\MoonBuggy\Documents\carbon agent v2 rail\carbon-agent-platform\orchestrator"
)

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_cors_and_rate_limiting.py",
        "-v",
        "--tb=short",
    ],
    capture_output=True,
    text=True,
    timeout=60,
)

print("=== STDOUT ===")
print(result.stdout)
print("=== STDERR ===")
print(result.stderr)
print(f"=== RETURN CODE: {result.returncode} ===")

with open("cors_test_results.txt", "w") as f:
    f.write(result.stdout)
    f.write(result.stderr)
