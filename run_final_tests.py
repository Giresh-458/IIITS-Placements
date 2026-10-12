import subprocess
import sys


def run_tests() -> int:
    """Run the repository's default pytest suite and propagate its exit code.

    pytest.ini controls collection and excludes tests marked live_integration
    from the default suite. This helper deliberately does not run persistence
    scripts, which may write to a configured database.
    """
    command = [sys.executable, "-m", "pytest"]
    print(f"RUNNING: {' '.join(command)}", flush=True)
    result = subprocess.run(command, check=False)
    if result.returncode == 0:
        print("PYTEST_RESULT = PASS")
    else:
        print(f"PYTEST_RESULT = FAIL (exit_code={result.returncode})")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(run_tests())
