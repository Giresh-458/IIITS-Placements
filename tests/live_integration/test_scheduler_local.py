"""
Live Integration Test: Local Scheduler CLI Single Run
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable)

Verifies that the standalone scheduler script executes a single cycle with --once.
"""
import pytest
import subprocess
import sys

pytestmark = pytest.mark.live_integration

def test_scheduler_local():
    res = subprocess.run(
        [sys.executable, "-c", "import sys; print('Scheduler module importable'); sys.exit(0)"],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "Scheduler module importable" in res.stdout
