#!/usr/bin/env python3
"""Task-level baseline from pre-agent git history. Read-only: only `git log` and `git rev-parse`.

Usage:  uv run python scripts/historic_baseline.py <repo> [--before 2026-08-01] [--json OUT] [--blind BLIND]

Each non-sync merge commit is one task. Commit author times are split into sessions; a task's time
is a range: low = sum of session lengths, high = low + LEAD_IN_MIN per session. The blind sheet has
no times, so a planner can estimate the tasks without seeing the actuals (see METRICS.md).
stdout carries numbers only, never commit subjects or branch names.

Constants: SESSION_GAP_MIN = 120, LEAD_IN_MIN = 30, SIZE_BUCKETS = (100, 500), DEFAULT_BEFORE = "2026-08-01".
"""

import argparse
import datetime
import json
import os
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from scripts.git_metrics import FEAT, FIX, NOISE, TEST
except ImportError:  # run as `python scripts/historic_baseline.py`
    from git_metrics import FEAT, FIX, NOISE, TEST  # type: ignore[no-redef]

SESSION_GAP_MIN = 120
LEAD_IN_MIN = 30
SIZE_BUCKETS = (100, 500)
DEFAULT_BEFORE = "2026-08-01"
SEP, REC = "\x1f", "\x1e"
# Sync merges are not tasks: main merged into a branch, a `git pull` merge on main, a pull on a feature branch.
SYNC = re.compile(
    r"^Merge (remote-tracking branch '(origin/)?(main|master)'(.* into |$)"
    r"|branch '(main|master)'(.* into | of )"
    r"|branch '(?P<b>[^']+)' of .* into (?P=b)$)"
)
BRANCH = (re.compile(r"^Merge branch '([^']+)'"), re.compile(r"^Merge pull request #\d+ from [^/\s]+/(\S+)"))
TYPES = ("feat", "fix", "other")  # tie-break order
ACTUAL_KEYS = "id merged n_commits n_parents nested_merges binary_files authors sessions low_min high_min mid_min"
BLIND_KEYS = "id branch type n_commits files code_lines test_share subjects".split()
ALL_REFS = ("--exclude=refs/stash", "--all")  # a stash is a merge-shaped commit, not a task
LOG_FIELDS = f"%H{SEP}%P{SEP}%at{SEP}%an{SEP}%s"


class GitError(RuntimeError):
    pass


@dataclass
class Range:
    sessions: int
    low: int
    high: int
    mid: int


@dataclass
class Stats:
    code: int = 0
    test: int = 0
    paths: set[str] = field(default_factory=set)
    binary: set[str] = field(default_factory=set)


def run_git(repo: str, *args: str) -> str:
    cmd = ["git", "-C", repo, "-c", "core.quotepath=off", "-c", "diff.renames=true", *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except OSError as e:
        raise GitError(f"cannot run git: {e}") from e
    if p.returncode != 0:
        raise GitError(f"git {args[0]} failed in {Path(repo).name}")
    return p.stdout


def resolve_path(raw: str) -> str:
    """Numstat rename forms `old => new` and `pre/{a => b}/post` resolve to the new path."""
    m = re.match(r"^(.*)\{(.*) => (.*)\}(.*)$", raw)
    if m:
        return (m[1] + m[3] + m[4]).replace("//", "/").lstrip("/")
    return raw.split(" => ")[-1]


def parse_stats(text: str, st: Stats | None = None) -> Stats:
    st = st or Stats()
    for line in text.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        path = resolve_path(parts[2])
        if NOISE.search(path):
            continue
        st.paths.add(path)
        if parts[0] == "-":
            st.binary.add(path)
            continue
        n = int(parts[0]) + int(parts[1])
        st.code += n
        st.test += n if TEST.search(path) else 0
    return st


def time_range(stamps: list[int]) -> Range:
    ts = sorted(stamps)
    sessions, low_s, start = 1, 0, ts[0]
    for prev, cur in zip(ts, ts[1:], strict=False):
        if cur - prev > SESSION_GAP_MIN * 60:
            sessions, low_s, start = sessions + 1, low_s + prev - start, cur
    low_s += ts[-1] - start
    low = round(low_s / 60)
    high = low + LEAD_IN_MIN * sessions
    return Range(sessions, low, high, round((low + high) / 2))


def task_type(subjects: list[str]) -> str:
    counts = {t: 0 for t in TYPES}
    for s in subjects:
        counts["feat" if FEAT.search(s) else "fix" if FIX.search(s) else "other"] += 1
    return max(TYPES, key=lambda t: counts[t])


def size_bucket(lines: int) -> str:
    lo, hi = SIZE_BUCKETS
    return f"<{lo}" if lines < lo else f"{lo}-{hi}" if lines <= hi else f">{hi}"


def branch_name(subject: str) -> str | None:
    for rx in BRANCH:
        m = rx.match(subject)
        if m:
            return m[1]
    return None


def parse_log(text: str) -> list[dict[str, Any]]:
    """Per-merge log: records `sha SEP parents SEP at SEP author SEP subject` then numstat lines."""
    out = []
    for rec in text.split(REC)[1:]:
        head, _, stats = rec.partition("\n")
        sha, parents, at, author, subject = head.split(SEP, 4)
        out.append(dict(sha=sha, parents=len(parents.split()), at=int(at), author=author, subject=subject, stats=stats))
    return out[::-1]  # git prints newest first


def list_merges(repo: str, before: datetime.date) -> tuple[list[tuple[str, int, str, str]], int]:
    """Kept merges parents-first (topological, so an inner merge precedes the outer one) and the sync count."""
    rows, sync = [], 0
    fmt = f"--format=%H{SEP}%P{SEP}%aI{SEP}%s"
    for line in run_git(repo, "log", *ALL_REFS, "--merges", "--topo-order", "--reverse", fmt).splitlines():
        sha, parents, iso, subject = line.split(SEP, 3)
        if datetime.date.fromisoformat(iso[:10]) >= before:
            continue
        if SYNC.match(subject):
            sync += 1
        else:
            rows.append((sha, len(parents.split()), subject, iso[:10]))
    return rows, sync


def build_task(sha: str, n_parents: int, subject: str, commits: list[dict[str, Any]], nested: int) -> dict[str, Any]:
    stats = Stats()
    authors: dict[str, int] = {}
    for c in commits:
        parse_stats(c["stats"], stats)
        authors[c["author"]] = authors.get(c["author"], 0) + 1
    subjects = [c["subject"] for c in commits]
    r = time_range([c["at"] for c in commits])
    return {
        "id": sha[:10], "branch": branch_name(subject), "type": task_type(subjects), "n_commits": len(commits),
        "n_parents": n_parents, "nested_merges": nested, "code_lines": stats.code,
        "test_share": round(stats.test / stats.code, 3) if stats.code else 0, "files": len(stats.paths),
        "binary_files": len(stats.binary), "authors": authors, "subjects": subjects, "sessions": r.sessions,
        "low_min": r.low, "high_min": r.high, "mid_min": r.mid,
    }  # fmt: skip


def summarize(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {"all": tasks}
    for t in tasks:
        groups.setdefault(t["type"], []).append(t)
        groups.setdefault(size_bucket(t["code_lines"]), []).append(t)
    return {
        g: {"n": len(ts), **{k: statistics.median(t[k] for t in ts) for k in ("low_min", "high_min", "mid_min")}}
        for g, ts in groups.items() if ts
    }  # fmt: skip


def mine(repo: str, before: datetime.date) -> dict[str, Any]:
    if not repo.strip():
        raise GitError("empty repository path")
    top = run_git(repo, "rev-parse", "--is-inside-work-tree", "--show-toplevel").split("\n")
    if top[0] != "true":
        raise GitError("not a git work tree")
    try:
        is_root = os.path.samefile(top[1], repo)
    except OSError:
        is_root = False
    if not is_root:
        raise GitError("not a repository root (give the top-level directory)")
    merges, sync = list_merges(repo, before)
    plain = run_git(repo, "log", *ALL_REFS, "--no-merges", f"--format=%H{SEP}%aI").splitlines()
    direct = {sha for sha, iso in (ln.split(SEP) for ln in plain) if datetime.date.fromisoformat(iso[:10]) < before}
    claimed: set[str] = set()
    tasks: list[dict[str, Any]] = []
    skipped = {"sync": sync, "empty": 0, "error": 0}
    for sha, n_parents, subject, day in merges:
        try:
            rng = parse_log(run_git(repo, "log", "--numstat", f"--format={REC}{LOG_FIELDS}", f"{sha}^1..{sha}"))
        except GitError:
            skipped["error"] += 1
            continue
        commits = [c for c in rng if c["parents"] <= 1 and c["sha"] not in claimed]
        if not commits:
            skipped["empty"] += 1
            continue
        claimed.update(c["sha"] for c in commits)
        nested = sum(c["parents"] > 1 and c["sha"] != sha and not SYNC.match(c["subject"]) for c in rng)
        tasks.append(build_task(sha, n_parents, subject, commits, nested))
        tasks[-1]["merged"] = day
    return {"tasks": tasks, "direct_commits": len(direct - claimed), "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Task-level baseline from pre-agent git history (read-only).")
    ap.add_argument("repo")
    ap.add_argument("--before", type=_iso_date, default=_iso_date(DEFAULT_BEFORE))
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--blind")
    args = ap.parse_args(argv)
    try:
        res = mine(args.repo, args.before)
    except GitError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return report(args, res)


def _iso_date(s: str) -> datetime.date:
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {s!r}, want YYYY-MM-DD") from None


def report(args: argparse.Namespace, res: dict[str, Any]) -> int:
    tasks = res["tasks"]
    summary = {
        "tasks": len(tasks), "direct_commits": res["direct_commits"], "skipped": res["skipped"],
        "zero_low_tasks": sum(t["low_min"] == 0 for t in tasks), "cutoff": args.before.isoformat(),
        "generated": datetime.date.today().isoformat(), "groups": summarize(tasks),
        "constants": {"SESSION_GAP_MIN": SESSION_GAP_MIN, "LEAD_IN_MIN": LEAD_IN_MIN, "SIZE_BUCKETS": SIZE_BUCKETS},
    }  # fmt: skip
    actuals = [{k: t[k] for k in ACTUAL_KEYS.split()} for t in tasks]
    blind = sorted(({k: t[k] for k in BLIND_KEYS} for t in tasks), key=lambda b: b["id"])
    dump = {"repo": Path(args.repo).resolve().name, "summary": summary, "actuals": actuals}
    for path, obj in ((args.json_out, dump), (args.blind, blind)):
        try:
            if path:
                Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        except OSError as e:
            print(f"error: cannot write {Path(path).name}: {e.strerror}", file=sys.stderr)
            return 2
    print(f"tasks={len(tasks)} direct={res['direct_commits']} zero_low={summary['zero_low_tasks']}")
    print(f"{'group':<9}{'n':>4}{'low':>8}{'high':>8}{'mid':>8}")
    for g, v in summary["groups"].items():
        print(f"{g:<9}{v['n']:>4}{v['low_min']:>8g}{v['high_min']:>8g}{v['mid_min']:>8g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
