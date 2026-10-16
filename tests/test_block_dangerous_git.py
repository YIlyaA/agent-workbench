import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hooks import block_dangerous_git
from hooks.block_dangerous_git import blocked_reason

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "block_dangerous_git.py"


def nl(*lines: str) -> str:
    return "\n".join(lines)


def nested_bash(depth: int, inner: str) -> str:
    cmd = inner
    for _ in range(depth):
        cmd = "bash -c " + shlex.quote(cmd)
    return cmd


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
    nl("cat > f <<'EOF'", "x", "EOF", "git push -f"),
    nl("cat <<EOF", "$(git push -f)", "EOF"),
    "GIT_TRACE=1 git push --force",
    'bash -c "git push -f"',
    "sh -lc 'cd x && git push origin main'",
    'eval "git reset --hard"',
    'echo "$(git push -f)"',
    "echo `git push -f`",
    "git push origin HEAD:main",
    "git push origin main:main",
    "git push origin refs/heads/main",
    "git push -fu origin x",
    "git -C repo push --force",
    "git -c core.pager=cat push -f",
    "/usr/bin/git push -f",
    "git.exe push --force",
    "env FOO=1 git push -f",
    "nohup git clean -fd",
    "ls; git reset --hard",
    "git status || git branch -D x",
    "git status & git push -f",
    "true | git clean -fd",
    nl("git status", "git push -f"),
    nl("git push \\", "--force"),
    "(cd x && git push -f)",
    'git push -f "oops',
    nested_bash(7, "git push -f"),
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
    "git push -q -u origin docs/rename-agents-workbench && gh pr create --base main --title x",
    nl("cat > f <<'EOF'", '{"allow": ["Bash(git push origin main *)"]}', "EOF"),
    'echo "git push -f"',
    'gh pr create --base main --body "merge to main after git push --force review"',
    'grep -rn "git reset --hard" docs/',
    'git commit -m "never git push -f to main"',
    nl("cat <<-EOF", "\tgit push -f origin main", "\tEOF"),
    "git push origin main-fix",
    "git status # git push -f",
    "   \n\t  ",
    'echo "hello',
    nl("cat <<EOF", "git push -f"),
]


@pytest.mark.parametrize("cmd", BLOCKED)
def test_blocks_dangerous(cmd: str) -> None:
    assert blocked_reason(cmd) is not None
    assert blocked_reason(cmd) == blocked_reason(cmd)


@pytest.mark.parametrize("cmd", ALLOWED)
def test_allows_safe(cmd: str) -> None:
    assert blocked_reason(cmd) is None


def test_large_input() -> None:
    cmd = "echo a && " * 20000 + "git push -f"
    start = time.monotonic()
    assert blocked_reason(cmd) == "force push"
    assert time.monotonic() - start < 1.0


def test_internal_error_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(block_dangerous_git.shlex, "shlex", boom)
    assert blocked_reason("git push -f") == "force push"


FUZZ = ['"', "'", "<<", "<<-", "<<'", "$(", "`", "\\", "$(`", "git push <<", "bash -c", "git", "git -C"]
FUZZ += ["a" * 100000, "$(" * 5000, "(" * 5000, "`" * 5001]


@pytest.mark.parametrize("cmd", FUZZ)
def test_never_raises(cmd: str) -> None:
    assert blocked_reason(cmd) == blocked_reason(cmd)


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
