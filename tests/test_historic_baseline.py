"""Tests for scripts/historic_baseline.py. Fixture repos are built in tmp_path with fixed dates."""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from scripts import historic_baseline as hb

D = "2026-06-{:02d}T{}:00+00:00"  # fixed-date helper: D.format(day, "10:00")


class Fx:
    """A throwaway git repo with deterministic dates and an isolated git config."""

    def __init__(self, root: Path, name: str = "repo x") -> None:
        self.root, self.repo = root, root / name
        (root / "gitcfg").write_text("", encoding="utf-8")
        self.repo.mkdir()
        self.git("init", "-b", "main", "-q")

    def git(self, *args: str, date: str | None = None, author: str = "A") -> str:
        env = {**os.environ, "GIT_CONFIG_GLOBAL": str(self.root / "gitcfg"), "GIT_CONFIG_NOSYSTEM": "1"}
        for k, v in (("NAME", author), ("EMAIL", f"{author}@x.test")):
            env[f"GIT_AUTHOR_{k}"] = env[f"GIT_COMMITTER_{k}"] = v
        if date:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
        cmd = ["git", "-C", str(self.repo), "-c", "commit.gpgsign=false", *args]
        return subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", check=True).stdout

    def commit(self, date: str, subject: str, files: dict | None = None, author: str = "A") -> None:
        for path, n in (files or {}).items():
            p = self.repo / path
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(n, bytes):
                p.write_bytes(n)
            else:
                p.write_text("".join(f"{subject}|{path}|{i}\n" for i in range(n)), encoding="utf-8", newline="\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", subject, "--allow-empty", date=date, author=author)

    def merge(self, date: str, *branches: str, msg: str | None = None) -> None:
        self.git("merge", "--no-ff", "-q", "-m", msg or f"Merge branch '{branches[0]}'", *branches, date=date)

    def branch(self, name: str, commits: list, merge_date: str | None = None, base: str = "main") -> None:
        self.git("switch", "-q", "-c", name, base)
        for c in commits:
            self.commit(*c)
        self.git("switch", "-q", "main")
        if merge_date:
            self.merge(merge_date, name)


def base(tmp_path: Path) -> Fx:
    fx = Fx(tmp_path)
    fx.commit(D.format(1, "09:00"), "chore: init", {"app.py": 5})
    return fx


def run(fx: Fx, *extra: str) -> tuple[dict, list]:
    out, blind = fx.root / "out.json", fx.root / "blind.json"
    assert hb.main([str(fx.repo), "--json", str(out), "--blind", str(blind), *extra]) == 0
    return json.loads(out.read_text("utf-8")), json.loads(blind.read_text("utf-8"))


# ---- pure functions ----


@pytest.mark.parametrize(
    ("stamps", "want"),  # (sessions, low, high, mid)
    [
        ([0, 50 * 60], (1, 50, 80, 65)),  # 23:30 -> 00:20, crosses midnight
        ([100, 100], (1, 0, 30, 15)),  # identical timestamps
        ([0, 120 * 60, 241 * 60], (2, 120, 180, 150)),  # gap of exactly 120 stays, 121 splits
    ],
    ids=["midnight", "same", "gap"],
)
def test_time_range(stamps: list[int], want: tuple[int, ...]) -> None:
    r = hb.time_range(stamps)
    assert (r.sessions, r.low, r.high, r.mid) == want


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("src/a.py => src/b.py", "src/b.py"),
        ("pkg/{a => b}/x.py", "pkg/b/x.py"),
        ("pkg/{ => sub}/x.py", "pkg/sub/x.py"),
        ("{old => new}/x.py", "new/x.py"),
        ("plain/x.py", "plain/x.py"),
    ],
    ids=["arrow", "brace", "empty-old", "lead", "plain"],
)
def test_rename_path(raw: str, want: str) -> None:
    assert hb.resolve_path(raw) == want


@pytest.mark.parametrize(
    ("subjects", "want"),
    [
        (["feat: a", "feat: b", "fix: c"], "feat"),
        (["feat: a", "fix: b"], "feat"),
        (["fix: a", "wip"], "fix"),
        (["fixed typo"], "other"),
    ],
    ids=["major", "tie", "tie2", "typo"],
)
def test_type_majority(subjects: list[str], want: str) -> None:
    assert hb.task_type(subjects) == want


@pytest.mark.parametrize(("n", "want"), [(99, "<100"), (100, "100-500"), (500, "100-500"), (501, ">500")])
def test_size_bucket(n: int, want: str) -> None:
    assert hb.size_bucket(n) == want


# ---- CLI and fixture repos ----


def test_empty_repo(tmp_path: Path) -> None:
    data, blind = run(Fx(tmp_path))
    assert data["summary"]["tasks"] == 0 and data["summary"]["direct_commits"] == 0 and blind == []


def test_no_merges(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.commit(D.format(2, "09:00"), "feat: b", {"b.py": 1})
    fx.commit(D.format(3, "09:00"), "feat: c", {"c.py": 1})
    s = run(fx)[0]["summary"]
    assert (s["tasks"], s["direct_commits"]) == (0, 3)


def test_not_a_repo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "w").mkdir()
    fx = base(tmp_path / "w")
    sub = fx.repo / "sub"
    sub.mkdir()
    plain = tmp_path / "plain"
    plain.mkdir()
    for p in (plain, tmp_path / "missing", sub):
        assert hb.main([str(p)]) == 2
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 3 and "Traceback" not in err and "repository root" in err


def test_unwritable_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fx = base(tmp_path)
    for flag in ("--json", "--blind"):
        assert hb.main([str(fx.repo), flag, str(tmp_path / "nodir" / "o.json")]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_stash_is_not_a_task(tmp_path: Path) -> None:
    fx = base(tmp_path)
    (fx.repo / "app.py").write_text("changed\n", encoding="utf-8", newline="\n")
    fx.git("stash", "push", "-q", date=D.format(2, "09:00"))
    s = run(fx)[0]["summary"]
    assert (s["tasks"], s["direct_commits"]) == (0, 1)


def test_root_commit_in_range(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.git("switch", "-q", "--orphan", "o")
    fx.commit(D.format(2, "09:00"), "feat: root", {"r.py": 2})
    fx.git("switch", "-q", "main")
    fx.git(
        "merge",
        "--no-ff",
        "-q",
        "--allow-unrelated-histories",
        "-m",
        "Merge branch 'o'",
        "o",
        date=D.format(3, "09:00"),
    )
    assert [t["n_commits"] for t in run(fx)[0]["actuals"]] == [1]


def test_bad_cutoff(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as e:
        hb.main([str(tmp_path), "--before", "2026-13-40"])
    assert e.value.code == 2


def test_empty_merge(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.branch("b", [(D.format(2, "09:00"), "feat: b", {"b.py": 2})], D.format(3, "09:00"))
    tree, head = fx.git("rev-parse", "HEAD^{tree}").strip(), fx.git("rev-parse", "HEAD").strip()
    old = fx.git("rev-parse", "HEAD~1").strip()
    sha = fx.git("commit-tree", tree, "-p", head, "-p", old, "-m", "Merge branch 'old'", date=D.format(4, "09:00"))
    fx.git("update-ref", "refs/heads/main", sha.strip())
    s = run(fx)[0]["summary"]
    assert s["tasks"] == 1 and s["skipped"]["empty"] == 1


def test_octopus(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.branch("b1", [(D.format(2, "09:00"), "feat: one", {"one.py": 2})])
    fx.branch("b2", [(D.format(2, "10:00"), "feat: two", {"two.py": 2})])
    fx.merge(D.format(5, "09:00"), "b1", "b2", msg="Merge branches 'b1' and 'b2'")
    t = run(fx)[0]["actuals"]
    assert len(t) == 1 and (t[0]["n_commits"], t[0]["n_parents"]) == (2, 3)


@pytest.mark.parametrize("inner_day", [3, 9], ids=["early", "late"])  # late: inner merge dated after the outer
def test_nested_merge_no_double_count(tmp_path: Path, inner_day: int) -> None:
    fx = base(tmp_path)
    fx.git("switch", "-q", "-c", "a")
    fx.commit(D.format(2, "09:00"), "feat: a1", {"a.py": 2})
    fx.branch("b", [(D.format(2, "10:00"), "feat: b1", {"b.py": 2})], base="a")
    fx.git("switch", "-q", "a")
    fx.merge(D.format(inner_day, "09:00"), "b", msg="Merge branch 'b' into a")
    fx.git("switch", "-q", "main")
    fx.merge(D.format(4, "09:00"), "a")
    t = run(fx)[0]["actuals"]
    assert [(x["n_commits"], x["nested_merges"]) for x in t] == [(1, 0), (1, 1)]


def test_sync_merge_skipped(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.git("switch", "-q", "-c", "feat-x")
    fx.commit(D.format(2, "09:00"), "feat: f1", {"f.py": 2})
    fx.git("switch", "-q", "main")
    fx.commit(D.format(3, "09:00"), "feat: m1", {"m.py": 2})
    fx.git("switch", "-q", "feat-x")
    fx.merge(D.format(4, "09:00"), "main", msg="Merge branch 'main' into feat-x")
    fx.git("switch", "-q", "main")
    fx.merge(D.format(5, "09:00"), "feat-x")
    data, _ = run(fx)
    assert data["summary"]["skipped"]["sync"] == 1
    assert [(t["n_commits"], t["nested_merges"]) for t in data["actuals"]] == [(1, 0)]


def test_pull_merge_is_sync(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.branch("b", [(D.format(2, "09:00"), "feat: b", {"b.py": 1})], D.format(3, "09:00"))
    fx.branch("c", [(D.format(4, "09:00"), "feat: c", {"c.py": 1})])
    fx.merge(D.format(5, "09:00"), "c", msg="Merge branch 'main' of example.test:x/y")
    s = run(fx)[0]["summary"]
    assert (s["tasks"], s["skipped"]["sync"]) == (1, 1)


def test_single_commit_task(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.branch("b", [(D.format(2, "09:00"), "feat: b", {"b.py": 2})], D.format(3, "09:00"))
    data, _ = run(fx)
    t = data["actuals"][0]
    assert (t["low_min"], t["high_min"], t["sessions"]) == (0, 30, 1) and data["summary"]["zero_low_tasks"] == 1


def test_other_authors_counted(tmp_path: Path) -> None:
    fx = base(tmp_path)
    cs = [(D.format(2, "09:00"), "feat: 1", {"1.py": 1}), (D.format(2, "09:10"), "feat: 2", {"2.py": 1})]
    fx.branch("b", [*cs, (D.format(2, "09:20"), "feat: 3", {"3.py": 1}, "B")], D.format(3, "09:00"))
    data, blind = run(fx)
    assert data["actuals"][0]["authors"] == {"A": 2, "B": 1} and "authors" not in blind[0]


def test_binary_numstat(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.branch("b", [(D.format(2, "09:00"), "feat: bin", {"d.bin": b"\x00\x01\x02\xff"})], D.format(3, "09:00"))
    data, blind = run(fx)
    assert (blind[0]["files"], blind[0]["code_lines"], data["actuals"][0]["binary_files"]) == (1, 0, 1)
    assert hb.parse_stats("-\t-\td.bin\n3\t1\ta.py\n").binary == {"d.bin"}


def test_rename_in_repo(tmp_path: Path) -> None:
    fx = Fx(tmp_path)
    fx.commit(D.format(1, "09:00"), "chore: init", {"src/a.py": 10})
    fx.git("switch", "-q", "-c", "b")
    fx.git("mv", "src/a.py", "src/b.py")
    with (fx.repo / "src" / "b.py").open("a", encoding="utf-8", newline="\n") as f:
        f.write("extra\n")
    fx.commit(D.format(2, "09:00"), "feat: move")
    fx.git("switch", "-q", "main")
    fx.merge(D.format(3, "09:00"), "b")
    t = run(fx)[1][0]
    assert (t["files"], t["code_lines"]) == (1, 1)


def test_noise_and_test_share(tmp_path: Path) -> None:
    fx = base(tmp_path)
    files = {"migrations/0001.py": 7, "x.lock": 5, "pkg/app.py": 30, "tests/test_x.py": 10}
    fx.branch("b", [(D.format(2, "09:00"), "feat: n", files)], D.format(3, "09:00"))
    t = run(fx)[1][0]
    assert (t["files"], t["code_lines"], t["test_share"]) == (2, 40, 0.25)


def test_cutoff_boundary(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.branch("b1", [(D.format(2, "09:00"), "feat: 1", {"1.py": 1})], "2026-07-31T23:59:59+03:00")
    fx.branch("b2", [(D.format(2, "09:00"), "feat: 2", {"2.py": 1})], "2026-08-01T00:00:00+03:00")
    fx.branch("b3", [("2026-07-20T09:00:00+00:00", "feat: 3", {"3.py": 1})], "2026-08-02T09:00:00+00:00")
    s = run(fx)[0]["summary"]
    assert (s["tasks"], s["direct_commits"]) == (1, 3)  # init, b2 and b3 commits are unclaimed


def test_mixed_offsets(tmp_path: Path) -> None:
    fx = base(tmp_path)
    cs = [("2026-06-02T10:00:00+03:00", "feat: 1", {"1.py": 1}), ("2026-06-02T02:30:00-05:00", "feat: 2", {"2.py": 1})]
    fx.branch("b", cs, D.format(3, "09:00"))
    t = run(fx)[0]["actuals"][0]
    assert (t["sessions"], t["low_min"], t["high_min"]) == (1, 30, 60)


def test_blind_sheet_is_blind(tmp_path: Path) -> None:
    fx = base(tmp_path)
    for i, name in enumerate(("zz", "aa", "mm")):
        fx.branch(name, [(D.format(2 + i, "09:00"), f"feat: {name}", {f"{name}.py": 3})], D.format(7 + i, "09:00"))
    _, blind = run(fx)
    text = (fx.root / "blind.json").read_text("utf-8")
    keys = {"id", "branch", "type", "n_commits", "files", "code_lines", "test_share", "subjects"}
    values = json.dumps([{k: v for k, v in e.items() if k != "id"} for e in blind])  # a sha prefix may be digits
    assert all(set(e) == keys for e in blind) and not re.search(r"\d{4}-\d{2}-\d{2}", text)
    assert not re.search(r"\d{9,11}", values)  # unix seconds
    assert [e["id"] for e in blind] == sorted(e["id"] for e in blind) and len(blind) == 3


def test_unicode_and_spaces(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fx = base(tmp_path)
    fx.branch("фича", [(D.format(2, "09:00"), "feat: добавить поле", {"my dir/файл.py": 3})], D.format(3, "09:00"))
    capsys.readouterr()
    blind = run(fx)[1][0]
    out = capsys.readouterr().out
    assert blind["subjects"] == ["feat: добавить поле"] and blind["branch"] == "фича" and blind["files"] == 1
    assert out and "добавить" not in out and "фича" not in out


def test_deterministic_and_read_only(tmp_path: Path) -> None:
    fx = base(tmp_path)
    fx.branch("b", [(D.format(2, "09:00"), "feat: b", {"b.py": 3})], D.format(3, "09:00"))

    def snap() -> tuple[str, ...]:
        return tuple(fx.git(*a) for a in (("status", "--porcelain"), ("rev-parse", "HEAD"), ("for-each-ref",)))

    before = snap()
    a, b = run(fx)[0], run(fx)[0]
    a["summary"].pop("generated"), b["summary"].pop("generated")
    assert a == b and a["repo"] == "repo x" and snap() == before


def test_partial_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = base(tmp_path)
    fx.branch("b1", [(D.format(2, "09:00"), "feat: 1", {"1.py": 1})], D.format(3, "09:00"))
    fx.branch("b2", [(D.format(4, "09:00"), "feat: 2", {"2.py": 1})], D.format(5, "09:00"))
    first = run(fx)[0]["actuals"][0]["id"]
    real = hb.run_git

    def flaky(repo: str, *args: str) -> str:
        if any(a.startswith(first) for a in args):
            raise hb.GitError("boom")
        return real(repo, *args)

    monkeypatch.setattr(hb, "run_git", flaky)
    s = run(fx)[0]["summary"]
    assert (s["tasks"], s["skipped"]["error"]) == (1, 1)
