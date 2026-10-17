"""Tests for scripts/git_metrics.py on a deterministic temp repo (characterization)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import git_metrics

DEV = ("Dev", "dev@example.com")
OTHER = ("Other Dev", "other@example.com")
MONTHS = [
    dict(month="2026-01", commits=4, active_days=3, commits_per_active_day=1.33, code_lines=21,
         lines_per_active_day=7, test_share=0.238, fix_share=0.25, feat_commits=1, ai_commits=0, merges=0),
    dict(month="2026-02", commits=1, active_days=1, commits_per_active_day=1.0, code_lines=6,
         lines_per_active_day=6, test_share=0, fix_share=0.0, feat_commits=1, ai_commits=1, merges=1),
]  # fmt: skip


def git(repo: Path, *args: str, date: str = "", who: tuple[str, str] = DEV, cdate: str = "") -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": who[0], "GIT_AUTHOR_EMAIL": who[1]}
    env |= {"GIT_COMMITTER_NAME": who[0], "GIT_COMMITTER_EMAIL": who[1]}
    if date:
        env |= {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": cdate or date}
    cmd = ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def commit(repo: Path, files: dict, msg: str, date: str, **kw) -> None:  # type: ignore[no-untyped-def,type-arg]
    for name, body in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, bytes):
            p.write_bytes(body)
        else:
            p.write_text(body, encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg, date=date, **kw)


def lines(n: int, tag: str = "x") -> str:
    return "".join(f"{tag}{i}\n" for i in range(n))


def isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> Path:
    cfg = tmp_path / "gitcfg"
    cfg.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "config", "core.autocrlf", "false")
    return repo


def build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = isolate(tmp_path, monkeypatch, "repo")
    one = {"app.py": lines(10, "a"), "uv.lock": lines(50), "package-lock.json": lines(40)}
    one["migrations/0001_init.py"] = lines(30)
    commit(repo, one, "feat: add app", "2026-01-15T10:00:00+00:00")
    two = {"tests/test_app.py": lines(5, "t"), "app.py": lines(10, "a").replace("a0", "b0")}
    commit(repo, two, "fix: off by one", "2026-01-15T15:00:00+00:00")
    commit(repo, {"logo.bin": b"\x00\x01\x02"}, "chore: add logo", "2026-01-20T09:00:00+00:00",
           cdate="2026-03-10T09:00:00+00:00")  # fmt: skip
    commit(repo, {"notes.md": lines(4, "n")}, "docs: notes", "2026-01-31T23:30:00-05:00")
    git(repo, "branch", "side", "HEAD~3")
    git(repo, "checkout", "-q", "-b", "feature")
    commit(repo, {"widget.py": lines(6, "w")}, "feat: widget\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
           "2026-02-03T11:00:00+00:00", who=OTHER)  # fmt: skip
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "--no-ff", "feature", "-m", "Merge branch 'feature'", date="2026-02-04T12:00:00+00:00")
    return repo


def run(repo: Path, mp: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *extra: str) -> dict:  # type: ignore[type-arg]
    out = repo.parent / "m.json"
    mp.setattr(sys, "argv", ["git_metrics.py", str(repo), "--out", str(out), *extra])
    git_metrics.main()
    capsys.readouterr()
    return json.loads(out.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture
def fx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return build(tmp_path, monkeypatch)


def test_months_match_fixture(fx, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    res = run(fx, monkeypatch, capsys)
    assert res["total_commits"] == 5
    assert res["months"] == MONTHS  # 01-31T23:30-05:00 stays in 2026-01; 3 active days; no 2026-03


def test_author_date_not_committer_date(fx, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    res = run(fx, monkeypatch, capsys)
    assert [m["month"] for m in res["months"]] == ["2026-01", "2026-02"]


@pytest.mark.parametrize(
    ("subject", "fix", "feat"),
    [("fix: a", 1, 0), ("Fix(x): a", 1, 0), ("hotfix: a", 1, 0), ('revert "x"', 1, 0),
     ("fixed typo", 0, 0), ("prefix: fix", 0, 0), ("feat: a", 0, 1), ("feature x", 0, 0)],
    ids=["fix1", "fix2", "fix3", "fix4", "nofix1", "nofix2", "feat1", "nofeat1"],
)  # fmt: skip
def test_fix_feat_regex(subject, fix, feat):  # type: ignore[no-untyped-def]
    assert bool(git_metrics.FIX.match(subject)) == bool(fix)
    assert bool(git_metrics.FEAT.match(subject)) == bool(feat)


def test_author_filter_name(fx, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    res = run(fx, monkeypatch, capsys, "--author", "other")
    assert res["total_commits"] == 1
    assert [m["month"] for m in res["months"]] == ["2026-02"]
    assert res["months"][0]["merges"] == 1  # pins current behavior: merges are not author-filtered


@pytest.mark.xfail(strict=True, reason="git_metrics bug: --author compares %an only, not email")
def test_author_filter_email(fx, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    assert run(fx, monkeypatch, capsys, "--author", "dev@example.com")["total_commits"] == 4


@pytest.mark.xfail(strict=True, reason="git_metrics bug: merges counted from HEAD only, commits use --all")
def test_merge_not_on_head(fx, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    git(fx, "checkout", "-q", "side")
    git(fx, "merge", "--no-ff", "feature", "-m", "Merge to side", date="2026-02-10T12:00:00+00:00")
    git(fx, "checkout", "-q", "main")
    assert run(fx, monkeypatch, capsys)["months"][1]["merges"] == 2


def test_out_json_and_stdout(fx, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    out = fx.parent / "m.json"
    monkeypatch.setattr(sys, "argv", ["git_metrics.py", str(fx), "--out", str(out)])
    git_metrics.main()
    rows = capsys.readouterr().out.strip().splitlines()
    assert rows[0].startswith("month") and len(rows) == 3
    assert set(json.loads(out.read_text(encoding="utf-8"))) == {"repo", "total_commits", "months", "generated"}


@pytest.mark.xfail(strict=True, reason="git_metrics bug: empty repo makes git log exit 128")
def test_empty_repo(tmp_path, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    repo = isolate(tmp_path, monkeypatch, "empty")
    assert run(repo, monkeypatch, capsys)["total_commits"] == 0


def test_not_a_repo(tmp_path, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    d = tmp_path / "plain"
    d.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    with pytest.raises(subprocess.CalledProcessError):  # pins current behavior
        run(d, monkeypatch, capsys)


def test_deterministic(fx, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    a, b = run(fx, monkeypatch, capsys), run(fx, monkeypatch, capsys)
    assert (a["months"], a["total_commits"]) == (b["months"], b["total_commits"])


def test_repo_untouched(fx, monkeypatch, capsys):  # type: ignore[no-untyped-def]
    head = git(fx, "rev-parse", "HEAD")
    run(fx, monkeypatch, capsys)
    assert git(fx, "status", "--porcelain") == "" and git(fx, "rev-parse", "HEAD") == head
