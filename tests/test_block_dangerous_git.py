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
    # Verifier findings from attempt 1: things a parser did not understand must stay blocked.
    nl("cat > notes.txt <<\\EOF", "hello", "EOF", "git reset --hard"),
    nl('cat > notes.txt <<E"O"F', "hello", "EOF", "git reset --hard"),
    nl('cat > notes.txt <<"E"OF', "hello", "EOF", "git reset --hard"),
    nl("cat > notes.txt <<\\EOF", "hello", "EOF", "git push -f"),
    nl("cat > notes.txt <<'EOF'", "hello", "EOF", "git push -f"),
    "echo $(true)#; git push -f",
    "x=$(pwd)#; git push -f origin x",
    "echo $(( 1 ))#; git push -f",
    "stdbuf -o0 git push -f",
    "caffeinate git push -f",
    "builtin command git push -f",
    "find . -name git -o -exec git push -f \\;",
    'env -S "git push --force"',
    "sudo -u git git push -f",
    "coproc git push -f",
    "ssh host git push --force",
    "docker exec c git push --force",
    "bash -c -- 'git push --force'",
    'eval -- "git push --force"',
    'cmd /C "git push --force"',
    "cmd.exe /C git push --force",
    'pwsh -NonInteractive -Command "git push --force"',
    'powershell -ExecutionPolicy Bypass -Command "git push --force"',
    'fish --command "git push --force"',
    'echo "git push --force" | bash',
    "echo git push -f | sh",
    "python3 -c \"import subprocess; subprocess.run('git push --force', shell=True)\"",
    "node -e \"require('child_process').execSync('git push --force')\"",
    nl("cat <<EOF |", "git push -f", "EOF", "bash"),
    "echo $'\\'' ; git push -f # '",
    nl("(( a = 1 <<EOF ))", "git push -f"),
    "echo x &>/dev/null; git push -f",
    "echo a ;>f git push -f",
    # Acceptable false positives of the strict design (the old hook blocked these too).
    'grep -rn "git reset --hard" docs/',
    'git commit -m "never git push -f to main"',
    nl("cat <<-EOF", "\tgit push -f origin main", "\tEOF"),
    "git status # git push -f",
    nl("cat <<EOF", "git push -f"),
    'gh pr create --body "$(cat f)" && git push -f',
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
    # The two real false positives of 2026-10-16.
    'git push -q -u origin docs/rename-agents-workbench && gh pr create --base main --title "x" --body "y"',
    nl("cat > f.json <<'EOF'", '{"allow": ["Bash(git push origin main *)"]}', "EOF"),
    nl("cat > f.json <<'EOF'", '{"allow": ["Bash(git push origin main *)"]}', "EOF", ""),
    nl('git commit -qam "msg', "", 'Co-Authored-By: x" && git push -q -u origin feat/x && gh pr create --base main'),
    'echo "git push -f"',
    'gh pr create --base main --body "merge to main after git push --force review"',
    "git push origin main-fix",
    "   \n\t  ",
    'echo "hello',
]


@pytest.mark.parametrize("cmd", BLOCKED)
def test_blocks_dangerous(cmd: str) -> None:
    assert blocked_reason(cmd) is not None
    assert blocked_reason(cmd) == blocked_reason(cmd)


@pytest.mark.parametrize("cmd", ALLOWED)
def test_allows_safe(cmd: str) -> None:
    assert blocked_reason(cmd) is None


def test_large_input() -> None:
    for cmd in ["echo a && " * 20000 + "git push -f", "git push -f " * 20000, "git -C " * 30000, "a" * 200_000]:
        start = time.monotonic()
        assert (blocked_reason(cmd) is None) == ("git" not in cmd)
        assert time.monotonic() - start < 2.0


def test_slow_input_below_cap() -> None:
    for cmd in ["git push " * 11000, "git -C -C " * 9000 + "push", "git push -f " * 8000 + "x" * 100]:
        assert len(cmd) <= block_dangerous_git.MAX_LEN
        start = time.monotonic()
        blocked_reason(cmd)
        assert time.monotonic() - start < 2.0


def test_internal_error_never_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(block_dangerous_git.shlex, "shlex", boom)
    assert blocked_reason("git push -f") == "force push"
    # Without the tokenizer the chained-command exception cannot apply, so the legacy block stands.
    assert blocked_reason("git push -q -u origin x && gh pr create --base main") == "push to main/master"


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
