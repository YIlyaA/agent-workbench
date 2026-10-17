#!/usr/bin/env python3
"""Hard diff limit: fail when a task branch changes more lines than its task file allows. Read-only.

Usage:  uv run python scripts/check_diff_limit.py [--root DIR] [--branch NAME] [--base REF] [--github]

Lines = insertions + deletions against the merge-base with the base ref (committed, staged, unstaged
and untracked files), minus the task's own file. Binary files count 0. See decision 0003.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    from scripts.git_metrics import TEST
    from scripts.validate_agent_layer import parse_frontmatter
except ImportError:  # run as `python scripts/check_diff_limit.py`
    from git_metrics import TEST  # type: ignore[no-redef]
    from validate_agent_layer import parse_frontmatter  # type: ignore[no-redef]

TASK_BRANCH = re.compile(r"^task/(T-\d+)(?:-|$)")
DEFAULT_BASE = "main"
TOP_FILES = 5
BINARY_SNIFF = 8000
NO_BASE_HINT = "In CI use actions/checkout with `fetch-depth: 0`; locally pass `--base origin/main`."


class Stop(Exception):
    """A reason to exit 1, shown to the builder."""


def git(root: Path, *args: str) -> str:
    cmd = ["git", "-C", str(root), *args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if p.returncode != 0:
        raise Stop(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def task_id(branch: str) -> str | None:
    m = TASK_BRANCH.match(branch)
    return m.group(1) if m else None


def find_task_file(root: Path, tid: str) -> Path:
    found = sorted({*(root / "tasks").glob(f"{tid}.md"), *(root / "tasks").glob(f"{tid}-*.md")})
    if len(found) != 1:
        raise Stop(f"expected exactly one task file for {tid}, found {[p.name for p in found]}")
    return found[0]


def read_limit(text: str) -> int | None:
    value = (parse_frontmatter(text) or {}).get("diff_limit_lines", "")
    return int(value) if re.fullmatch(r"\d+", value) else None


def count_untracked(data: bytes) -> int:
    if b"\0" in data[:BINARY_SNIFF]:
        return 0
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def parse_numstat_z(out: str) -> list[tuple[int, str]]:
    parts, rows, i = out.split("\0"), [], 0
    while i + 1 < len(parts):
        add, dele, path = parts[i].split("\t", 2)
        i += 1
        if path == "":  # rename: old and new paths follow as separate entries
            path, i = parts[i + 1], i + 2
        rows.append((0 if add == "-" else int(add) + int(dele), path))
    return rows


def resolve_refs(args: argparse.Namespace, root: Path) -> tuple[str, str]:
    if args.github:
        head, base = os.environ.get("GITHUB_HEAD_REF", ""), os.environ.get("GITHUB_BASE_REF", "")
        if not head or not base:
            raise Stop("--github needs GITHUB_HEAD_REF and GITHUB_BASE_REF")
        return head, f"origin/{base}"
    return args.branch or git(root, "rev-parse", "--abbrev-ref", "HEAD").strip(), args.base


def effective_limit(root: Path, mb: str, tid: str, limit: int) -> int:
    """The base version of the task (found by id, so a rename cannot hide it) caps a raised limit."""
    names = git(root, "ls-tree", "--name-only", "-z", mb, "tasks/").split("\0")
    base = [n for n in names if re.fullmatch(rf"tasks/{tid}(-[^/]*)?\.md", n)]
    if not base:
        print("limit source: branch")
        return limit
    if len(base) > 1:
        raise Stop(f"{len(base)} task files for {tid} at the merge-base: {base}")
    old = read_limit(git(root, "show", f"{mb}:{base[0]}"))
    if old is None:
        raise Stop(f"{base[0]} at the merge-base: diff_limit_lines must be a non-negative integer")
    if old < limit:
        print(f"note: limit raised on this branch ({limit} -> {old}); using {old}")
        return old
    return limit


def say(text: str) -> None:
    """Print one ASCII line (Windows consoles can be cp1252). Escapes newlines too: no output spoofing."""
    print(ascii(text)[1:-1])


def line_count(path: Path) -> int:
    if path.is_symlink():  # git stores a link as one line; never follow it (dir or broken)
        return 1
    return count_untracked(path.read_bytes()) if path.is_file() else 0  # nested repos list as dirs


def count_lines(root: Path, mb: str) -> list[tuple[int, str]]:
    rows = parse_numstat_z(git(root, "diff", "--numstat", "-z", "-M", mb))
    for name in git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if name:
            rows.append((line_count(root / name), name))
    return rows


def check(args: argparse.Namespace, root: Path) -> int:
    branch, base = resolve_refs(args, root)
    if not branch.startswith("task/"):
        say(f"diff limit: skip (not on a task branch: {branch})")
        return 0
    tid = task_id(branch)
    if tid is None:
        raise Stop(f"bad task branch name {branch!r}; expected task/T-<digits>-<slug>")
    tfile = find_task_file(root, tid)
    limit = read_limit(tfile.read_text(encoding="utf-8"))
    if limit is None:
        raise Stop(f"{tfile.name}: diff_limit_lines must be a non-negative integer")
    try:
        mb = git(root, "merge-base", "HEAD", base).strip()
    except Stop as e:
        raise Stop(f"{e} {NO_BASE_HINT}") from e
    rel = f"tasks/{tfile.name}"
    limit = effective_limit(root, mb, tid, limit)
    rows = sorted((r for r in count_lines(root, mb) if r[1] != rel), reverse=True)
    total, tests = sum(n for n, _ in rows), sum(n for n, p in rows if TEST.search(p))
    print(f"diff limit: {total}/{limit} lines (tests {tests}; base {mb[:7]}; task file excluded)")
    if total <= limit:
        return 0
    for n, path in rows[:TOP_FILES]:
        say(f"  {n}  {path}")
    print("Over the limit: stop and report. Do not trim tests, join lines or add lint suppressions to fit (AGENTS.md).")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--branch", help="selects the task id only; lines are always counted from HEAD")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--github", action="store_true")
    args = ap.parse_args(argv)
    try:
        return check(args, args.root)
    except Stop as e:
        say(f"diff limit: ERROR {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
