"""PostToolUse feedback: run ruff on an edited .py file and report violations to Claude.

Exit 2 sends stderr back to Claude so it fixes the lint errors it just introduced.
"""
import json
import subprocess
import sys


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError as e:
        print(f"ruff_check.py: could not parse hook input ({e})", file=sys.stderr)
        return 1
    path = (event.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return 0
    try:
        result = subprocess.run([sys.executable, "-m", "ruff", "check", path], capture_output=True, text=True)
    except OSError as e:
        print(f"ruff_check.py: could not run ruff ({e})", file=sys.stderr)
        return 1
    if result.returncode == 0:
        return 0
    if "No module named ruff" in result.stderr:
        print("ruff_check.py: ruff not installed; run pip install -r requirements.txt", file=sys.stderr)
        return 1
    print(f"ruff found problems in {path}:\n{result.stdout}{result.stderr}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
