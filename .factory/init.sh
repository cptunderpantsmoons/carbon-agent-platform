#!/usr/bin/env bash
# Idempotent mission environment setup.
# Runs at start of each worker session.

set -euo pipefail

cd "$(dirname "$0")/.."

PY="${PYTHON:-python}"

# Python deps (venv optional; fall back to user site)
if [ -f orchestrator/requirements.txt ]; then
  $PY -m pip install --disable-pip-version-check -q -r orchestrator/requirements.txt || true
fi
if [ -f adapter/requirements.txt ]; then
  $PY -m pip install --disable-pip-version-check -q -r adapter/requirements.txt || true
fi

# Ensure .env.example exists (read by workers for var names); do NOT overwrite real .env files
if [ ! -f .env.example ]; then
  echo "WARN: .env.example missing" >&2
fi

# Seed test integration dir
mkdir -p tests/integration
if [ ! -f tests/integration/__init__.py ]; then
  : > tests/integration/__init__.py
fi

echo "init.sh complete"
