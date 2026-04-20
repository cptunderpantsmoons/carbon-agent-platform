"""Integration test fixtures."""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTER_PATH = os.path.join(PROJECT_ROOT, "adapter")
ORCHESTRATOR_PATH = os.path.join(PROJECT_ROOT, "orchestrator")


def setup_adapter_path():
    """Add adapter to sys.path for importing app.* modules."""
    # Remove orchestrator path if present to avoid ambiguity
    if ORCHESTRATOR_PATH in sys.path:
        sys.path.remove(ORCHESTRATOR_PATH)
    if ADAPTER_PATH not in sys.path:
        sys.path.insert(0, ADAPTER_PATH)


def setup_orchestrator_path():
    """Add orchestrator to sys.path for importing app.* modules."""
    # Remove adapter path if present to avoid ambiguity
    if ADAPTER_PATH in sys.path:
        sys.path.remove(ADAPTER_PATH)
    if ORCHESTRATOR_PATH not in sys.path:
        sys.path.insert(0, ORCHESTRATOR_PATH)
