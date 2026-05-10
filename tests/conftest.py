"""Shared pytest fixtures.

Most of these tests are pure unit tests that mock out the database via
`unittest.mock`. The few integration-style tests in this directory are
gated on the `RUN_INTEGRATION_TESTS=1` env var so they only run inside
docker-compose CI.
"""

import os
import sys
from pathlib import Path

import pytest

# Make sure the project root is importable.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _running_integration() -> bool:
    return os.getenv("RUN_INTEGRATION_TESTS", "0") == "1"


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless explicitly opted in."""
    skip_marker = pytest.mark.skip(
        reason="set RUN_INTEGRATION_TESTS=1 to run integration tests"
    )
    if _running_integration():
        return
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)
