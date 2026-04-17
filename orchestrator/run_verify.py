"""Run verification tests and save results."""
import subprocess
import sys

test_suites = [
    ("test_models", ["python", "-B", "-m", "pytest", "tests/test_models.py", "-v", "--tb=short"]),
    ("test_cors_rate", ["python", "-B", "-m", "pytest", "tests/test_cors_and_rate_limiting.py", "-v", "--tb=short"]),
    ("test_users", ["python", "-B", "-m", "pytest", "tests/test_users.py", "-v", "--tb=short"]),
    ("test_clerk", ["python", "-B", "-m", "pytest", "tests/test_clerk.py", "-v", "--tb=short"]),
    ("test_auth_routes", ["python", "-B", "-m", "pytest", "tests/test_auth_routes.py", "-v", "--tb=short"]),
]

results = []
for name, cmd in test_suites:
    print(f"\n{'='*60}")
    print(f"RUNNING: {name}")
    print(f"{'='*60}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    output = r.stdout + r.stderr
    print(output[-2000:] if len(output) > 2000 else output)
    results.append((name, r.returncode))

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for name, rc in results:
    status = "PASS" if rc == 0 else "FAIL"
    print(f"  {name}: {status} (rc={rc})")
