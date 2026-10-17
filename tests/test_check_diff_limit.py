import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import check
from scripts.check_diff_limit import count_untracked, main, parse_numstat_z, task_id
from tests.test_git_metrics import git, isolate

D = "2026-01-01T00:00:00"
TASK = "tasks/T-001-x.md"
Capsys = pytest.CaptureFixture[str]
MP = pytest.MonkeyPatch


def task_md(limit: str = "10", extra: int = 0) -> str:
    return f"---\nid: T-001\ndiff_limit_lines: {limit}\n---\n" + "log\n" * extra


def put(repo: Path, files: dict[str, Any]) -> None:
    for name, body in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, bytes):
            p.write_bytes(body)
        else:
            p.write_text(body, encoding="utf-8", newline="\n")


def save(repo: Path, files: dict[str, Any], msg: str = "c") -> None:
    put(repo, files)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg, date=D)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = isolate(tmp_path, monkeypatch, "r")
    save(r, {TASK: task_md(), "app.py": "a\n"}, "base")
    git(r, "checkout", "-q", "-b", "task/T-001-x")
    return r


def run(repo: Path, capsys: Capsys, *extra: str) -> tuple[int, str]:
    capsys.readouterr()
    code = main(["--root", str(repo), *extra])
    return code, capsys.readouterr().out


def n_of(out: str) -> int:
    return int(out.split("diff limit: ")[1].split("/")[0])


def test_pure_helpers() -> None:
    assert task_id("task/T-12-a-b") == "T-12"
    assert task_id("task/T-12") == "T-12"
    assert task_id("task/T-12x") is None
    assert [count_untracked(b) for b in (b"a\nb\n", b"a\nb", b"a\r\nb\r\n", b"", b"a\0b\n")] == [2, 2, 2, 0, 0]
    assert parse_numstat_z("1\t2\ta.py\0-\t-\tb.bin\x000\t0\t\0old\0new\0") == [(3, "a.py"), (0, "b.bin"), (0, "new")]


@pytest.mark.parametrize("branch", ["main", "feature/x", "HEAD"], ids=["main", "feature", "detached"])
def test_skip_non_task(repo: Path, capsys: Capsys, branch: str) -> None:
    code, out = run(repo, capsys, "--branch", branch)
    assert code == 0 and out.startswith("diff limit: skip")


def test_skip_real_detached(repo: Path, capsys: Capsys) -> None:
    git(repo, "checkout", "-q", "--detach")
    assert run(repo, capsys)[0] == 0


@pytest.mark.parametrize("branch", ["task/t-001-x", "task/foo"], ids=["lower", "noid"])
def test_bad_task_branch(repo: Path, capsys: Capsys, branch: str) -> None:
    code, out = run(repo, capsys, "--branch", branch)
    assert code == 1 and "task/T-<digits>-<slug>" in out


@pytest.mark.parametrize(
    ("branch", "name"), [("task/T-9-x", "T-001-x"), ("task/T-001-x", "T-0010-y")], ids=["none", "prefix"]
)
def test_task_file_missing(tmp_path: Path, monkeypatch: MP, capsys: Capsys, branch: str, name: str) -> None:
    r = isolate(tmp_path, monkeypatch, "m")
    save(r, {f"tasks/{name}.md": task_md()})
    assert run(r, capsys, "--branch", branch)[0] == 1


def test_task_file_ambiguous(repo: Path, capsys: Capsys) -> None:
    put(repo, {"tasks/T-001-b.md": task_md()})
    code, out = run(repo, capsys)
    assert code == 1 and "T-001-x.md" in out and "T-001-b.md" in out


@pytest.mark.parametrize("limit", ["", "abc", "-5", "300.0"], ids=["empty", "text", "neg", "float"])
def test_bad_limit(repo: Path, capsys: Capsys, limit: str) -> None:
    save(repo, {TASK: task_md(limit)})
    assert run(repo, capsys)[0] == 1


@pytest.mark.parametrize(("added", "code"), [(9, 0), (10, 0), (11, 1)], ids=["under", "equal", "over"])
@pytest.mark.parametrize("branch", ["task/T-001-x", "task/T-001"], ids=["slug", "bare"])
def test_limit_boundary(repo: Path, capsys: Capsys, added: int, code: int, branch: str) -> None:
    save(repo, {"big.py": "x\n" * added})
    first = run(repo, capsys, "--branch", branch)
    assert first == run(repo, capsys, "--branch", branch)
    assert first[0] == code and n_of(first[1]) == added
    assert ("Over the limit: stop and report." in first[1]) == bool(code)
    assert ("big.py" in first[1]) == bool(code)


@pytest.mark.parametrize(("other", "n", "code"), [(0, 5, 0), (8, 13, 1)], ids=["own", "other"])
def test_task_file_excluded(repo: Path, capsys: Capsys, other: int, n: int, code: int) -> None:
    save(repo, {"tasks/T-002-y.md": "y\n" * other} if other else {"z.txt": ""})
    save(repo, {TASK: task_md(extra=50), "app.py": "a\n" + "b\n" * 5})
    out = run(repo, capsys)
    assert out[0] == code and n_of(out[1]) == n


@pytest.mark.parametrize(("base", "code"), [("raised", 1), ("new", 0)], ids=["raised", "new"])
def test_raised_limit_ignored(tmp_path: Path, monkeypatch: MP, capsys: Capsys, base: str, code: int) -> None:
    r = isolate(tmp_path, monkeypatch, "q")
    save(r, {TASK: task_md()} if base == "raised" else {"app.py": "a\n"}, "base")
    git(r, "checkout", "-q", "-b", "task/T-001-x")
    save(r, {TASK: task_md("100"), "big.py": "x\n" * 20})
    out = run(r, capsys)
    assert out[0] == code
    assert ("note: limit raised on this branch (100 -> 10); using 10" in out[1]) == (base == "raised")
    assert ("limit source: branch" in out[1]) == (base == "new")


def test_working_tree_counted(repo: Path, capsys: Capsys) -> None:
    put(repo, {".gitignore": "coverage.json\n.venv/\n", "coverage.json": "x\n" * 9, ".venv/x": "x\n" * 9})
    put(repo, {"u7.py": "x\n" * 7, "u3.py": "x\nx\nx", "crlf.py": b"x\r\nx\r\n", "app.py": "z\n"})
    assert n_of(run(repo, capsys)[1]) == 2 + 7 + 3 + 2 + 2  # .gitignore, u7, u3, crlf, app.py (1 add + 1 del)


def test_rename_cannot_raise_limit(repo: Path, capsys: Capsys) -> None:
    git(repo, "mv", TASK, "tasks/T-001-y.md")
    save(repo, {"tasks/T-001-y.md": task_md("100"), "big.py": "x\n" * 20})
    code, out = run(repo, capsys)
    assert code == 1 and "using 10" in out


def test_base_limit_not_integer(tmp_path: Path, monkeypatch: MP, capsys: Capsys) -> None:
    r = isolate(tmp_path, monkeypatch, "b")
    save(r, {TASK: task_md("abc")})
    git(r, "checkout", "-q", "-b", "task/T-001-x")
    save(r, {TASK: task_md("100")})
    assert run(r, capsys)[0] == 1


@pytest.mark.parametrize("kind", ["nested", "dirlink", "broken"])
def test_untracked_odd_entries(repo: Path, capsys: Capsys, kind: str) -> None:
    if kind == "nested":
        (repo / "sub").mkdir()
        git(repo / "sub", "init", "-q")
        put(repo, {"sub/f.py": "x\n"})
    else:
        target = repo / ("tasks" if kind == "dirlink" else "missing")
        try:
            (repo / "ln").symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("symlinks not permitted")
    code, out = run(repo, capsys)
    assert code == 0 and n_of(out) == (0 if kind == "nested" else 1)


def test_ascii_output_on_cp1252(repo: Path, tmp_path: Path) -> None:
    put(repo, {"漢字.py": "x\n" * 11})
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    cmd = [sys.executable, "scripts/check_diff_limit.py", "--root", str(repo)]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="ascii", check=False)
    assert p.returncode == 1 and "\\u6f22\\u5b57.py" in p.stdout


def test_binary_zero(repo: Path, capsys: Capsys) -> None:
    save(repo, {"a.bin": b"\0\1\2"})
    put(repo, {"a.bin": b"\0\3", "b.bin": b"\0\0"})
    code, out = run(repo, capsys)
    assert code == 0 and n_of(out) == 0


def test_rename_zero(repo: Path, capsys: Capsys) -> None:
    git(repo, "mv", "app.py", "b.py")
    assert n_of(run(repo, capsys)[1]) == 0


@pytest.mark.parametrize("merge", [False, True], ids=["ahead", "merged"])
def test_merge_base_not_tip(repo: Path, capsys: Capsys, merge: bool) -> None:
    save(repo, {"mine.py": "x\n" * 2})
    git(repo, "checkout", "-q", "main")
    save(repo, {"theirs.py": "x\n" * 30}, "ahead")
    git(repo, "checkout", "-q", "task/T-001-x")
    if merge:
        git(repo, "merge", "-q", "main", "-m", "m", date=D)
    assert n_of(run(repo, capsys)[1]) == 2


def test_no_merge_base(repo: Path, capsys: Capsys) -> None:
    code, out = run(repo, capsys, "--base", "nope")
    assert code == 1 and "fetch-depth: 0" in out and " lines (" not in out


@pytest.mark.parametrize("env", ["ok", "noenv", "meta"])
def test_github_mode(repo: Path, capsys: Capsys, monkeypatch: pytest.MonkeyPatch, env: str) -> None:
    git(repo, "update-ref", "refs/remotes/origin/main", "main")
    save(repo, {"big.py": "x\n" * 4})
    monkeypatch.setenv("GITHUB_HEAD_REF", "task/T-001-x;echo pwned" if env == "meta" else "task/T-001-x")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    if env == "noenv":
        monkeypatch.delenv("GITHUB_BASE_REF")
    code, out = run(repo, capsys, "--github")
    assert code == (1 if env == "noenv" else 0)
    if code == 0:
        assert n_of(out) == 4


def test_worktree(repo: Path, tmp_path: Path, capsys: Capsys) -> None:
    save(repo, {"big.py": "x\n" * 4})
    git(repo, "checkout", "-q", "main")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "task/T-001-x")
    assert n_of(run(wt, capsys)[1]) == 4


def test_check_py_runs_last() -> None:
    name, cmd = check.CHECKS[-1]
    assert name == "diff limit" and cmd[-1] == "scripts/check_diff_limit.py"
