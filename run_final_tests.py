import subprocess

def run_cmd(cmd):
    print(f"\n======================================")
    print(f"RUNNING: {cmd}")
    print(f"======================================\n")
    subprocess.run(cmd, shell=True)

if __name__ == "__main__":
    run_cmd("python -m pytest tests/unit/test_batch_9.py tests/unit/test_api.py")
    run_cmd("python run_batch_9.py")
    run_cmd("python -m pytest")
    run_cmd("python -m pytest tests/unit -v")
