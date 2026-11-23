import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, ".claude", "hooks")


def run_hook(name, event):
    return subprocess.run([sys.executable, os.path.join(HOOKS, name)], input=json.dumps(event),
                          capture_output=True, text=True)


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": ROOT}


@pytest.mark.parametrize("cmd", [
    "rm -rf /", "rm -rf ~", "rm -fr .", "rm -r -f *", "cd x && rm -rf ..",
    "git push --force", "git push -f origin main", "git reset --hard HEAD~1", "git clean -fd",
])
def test_guard_blocks_destructive(cmd):
    r = run_hook("guard.py", bash(cmd))
    assert r.returncode == 2 and "Blocked" in r.stderr


@pytest.mark.parametrize("cmd", [
    "rm -rf build dist", "rm -rf ./build", "git push --force-with-lease", "git push origin main",
    "git reset --soft HEAD~1", "python -m pytest",
])
def test_guard_allows_safe(cmd):
    assert run_hook("guard.py", bash(cmd)).returncode == 0


@pytest.mark.parametrize("path, code", [
    (os.path.join(ROOT, "dist", "Img2Bambu", "x.py"), 2),
    (os.path.join(ROOT, "build", "x.txt"), 2),
    (os.path.join(ROOT, "img2bambu", "build_info.py"), 0),
])
def test_guard_artifact_dirs(path, code):
    event = {"tool_name": "Write", "tool_input": {"file_path": path}, "cwd": ROOT}
    assert run_hook("guard.py", event).returncode == code


def test_guard_fails_open_on_bad_input():
    r = subprocess.run([sys.executable, os.path.join(HOOKS, "guard.py")], input="not json",
                       capture_output=True, text=True)
    assert r.returncode == 0 and "could not parse" in r.stderr


def test_ruff_hook_reports_lint_errors(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("import os\n")
    r = run_hook("ruff_check.py", {"tool_input": {"file_path": str(bad)}})
    assert r.returncode == 2 and "F401" in r.stderr


def test_ruff_hook_passes_clean_and_non_python(tmp_path):
    good = tmp_path / "good.py"
    good.write_text("x = 1\n")
    assert run_hook("ruff_check.py", {"tool_input": {"file_path": str(good)}}).returncode == 0
    assert run_hook("ruff_check.py", {"tool_input": {"file_path": str(tmp_path / "a.md")}}).returncode == 0
