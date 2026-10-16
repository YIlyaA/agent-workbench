import json
import subprocess
import sys
from pathlib import Path

import pytest

from hooks.block_dangerous_git import blocked_reason

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "block_dangerous_git.py"

BLOCKED = [
    "git push --force origin x",
    "git push --force-with-lease",
    "git push -f",
    "git push origin +x",
    "git push origin main",
    "git push origin HEAD:master",
    "git reset --hard HEAD~1",
    "git clean -fd",
    "git clean -xdf",
    "git branch -D old",
    "git checkout .",
    "git restore -- .",
    "cd repo && git push -f",
    "GIT_TRACE=1 git  push   --force",
]
ALLOWED = [
    "git push origin feature/x",
    "git push -u origin my-branch",
    "git push origin feature/main-menu",
    "git reset --soft HEAD~1",
    "git clean -n",
    "git branch -d old",
    "git checkout main",
    "git checkout ./src/file.py",
    "git status",
    "echo 'git' && ls -f",
    "",
]


@pytest.mark.parametrize("cmd", BLOCKED)
def test_blocks_dangerous(cmd: str) -> None:
    assert blocked_reason(cmd) is not None


@pytest.mark.parametrize("cmd", ALLOWED)
def test_allows_safe(cmd: str) -> None:
    assert blocked_reason(cmd) is None


def run_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=False)


def test_hook_exit_2_and_stderr_when_blocked() -> None:
    r = run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push -f"}}))
    assert r.returncode == 2
    assert "BLOCKED" in r.stderr


def test_hook_exit_0_when_allowed() -> None:
    r = run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}))
    assert r.returncode == 0 and r.stderr == ""


@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_input": null}', '{"tool_input": {"command": 5}}'])
def test_hook_malformed_input_does_not_block(stdin: str) -> None:
    assert run_hook(stdin).returncode == 0
