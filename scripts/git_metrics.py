#!/usr/bin/env python3
"""Read-only git metrics: velocity and throughput per month/week.

Usage:  python3 git_metrics.py /path/to/repo [--author "Name"] [--out metrics.json]
It only runs `git log` (no checkout, no writes to the repo). No file contents are read,
only commit metadata and line counts, so no secrets are touched.

Definitions (see METRICS.md):
  commits        : non-merge commits
  active_days    : distinct calendar days with at least one commit
  code_lines     : added+deleted lines in source files (generated/vendor/data/lock files excluded)
  test_share     : share of changed lines that are in test files
  fix_share      : share of commits whose subject starts with fix/hotfix/revert (rework proxy)
  feat_commits   : commits starting with feat
  ai_commits     : commits carrying a Co-Authored-By trailer (agent-assisted marker)
"""

import argparse, collections, datetime, json, re, subprocess, sys

NOISE = re.compile(
    r"(^|/)(node_modules|staticfiles|static/vendor|media|protected_media|old_data|dump|migrations|\.venv|dist|build)/|"
    r"\.(lock|min\.js|min\.css|map|sql|xlsx|csv|json|mmdb|db|png|jpe?g|gif|svg|ico|woff2?|pdf|log)$|"
    r"(package-lock\.json|poetry\.lock|celerybeat-schedule)$",
    re.I,
)
TEST = re.compile(
    r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*\.py$|_test\.py$|\.(spec|test)\.[jt]sx?$|conftest\.py$", re.I
)
FIX = re.compile(r"^(fix|hotfix|revert|bugfix)(\(|:|!|\s)", re.I)
FEAT = re.compile(r"^feat(\(|:|!|\s)", re.I)
ALL_REFS = ("--exclude=refs/stash", "--all")  # --exclude must come first; a stash is not a commit


def author_matches(needle, name, email):
    return needle in name.lower() or needle in email.lower()


def run(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True, errors="replace"
    ).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--author", default=None, help="substring of author name/email to include")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    fmt = "\x1e%H\x1f%ad\x1f%an\x1f%ae\x1f%s\x1f%b\x1f"
    cmd = ["log", "--no-merges", "--date=short", f"--pretty=format:{fmt}", "--numstat", *ALL_REFS]
    raw = run(a.repo, *cmd)
    needle = (a.author or "").lower()
    mlog = run(a.repo, "log", *ALL_REFS, "--merges", "--date=short", "--pretty=format:%ad%x1f%an%x1f%ae")
    merges = [m[0] for m in (x.split("\x1f") for x in mlog.splitlines()) if author_matches(needle, m[1], m[2])]
    commits = []
    for block in raw.split("\x1e")[1:]:
        h, d, an, ae, subj, body, rest = block.split("\x1f", 6)
        if not author_matches(needle, an, ae):
            continue
        code = test = files = 0
        for line in rest.strip().splitlines():
            p = line.split("\t")
            if len(p) != 3 or p[0] == "-":
                continue
            ad, de, path = int(p[0]), int(p[1]), p[2]
            if NOISE.search(path):
                continue
            n = ad + de
            code += n
            files += 1
            if TEST.search(path):
                test += n
        commits.append(
            dict(h=h, d=d, subj=subj, code=code, test=test, files=files, ai=("co-authored-by" in body.lower()))
        )
    seen = set()
    commits = [c for c in commits if not (c["h"] in seen or seen.add(c["h"]))]
    by = collections.defaultdict(list)
    for c in commits:
        by[c["d"][:7]].append(c)
    rows = []
    for m in sorted(by):
        cs = by[m]
        days = {c["d"] for c in cs}
        code = sum(c["code"] for c in cs)
        test = sum(c["test"] for c in cs)
        rows.append(
            dict(
                month=m,
                commits=len(cs),
                active_days=len(days),
                commits_per_active_day=round(len(cs) / len(days), 2),
                code_lines=code,
                lines_per_active_day=round(code / len(days)),
                test_share=round(test / code, 3) if code else 0,
                fix_share=round(sum(bool(FIX.match(c["subj"])) for c in cs) / len(cs), 3),
                feat_commits=sum(bool(FEAT.match(c["subj"])) for c in cs),
                ai_commits=sum(c["ai"] for c in cs),
                merges=sum(1 for x in merges if x.startswith(m)),
            )
        )
    out = dict(repo=a.repo, total_commits=len(commits), months=rows, generated=datetime.date.today().isoformat())
    txt = json.dumps(out, indent=1)
    if a.out:
        open(a.out, "w").write(txt)
    print(
        f"{'month':8} {'commits':>7} {'days':>5} {'c/day':>6} {'lines':>7} {'l/day':>6} {'test%':>6} {'fix%':>6} {'feat':>5} {'ai':>4} {'merges':>6}"
    )
    for r in rows:
        print(
            f"{r['month']:8} {r['commits']:7} {r['active_days']:5} {r['commits_per_active_day']:6} {r['code_lines']:7} {r['lines_per_active_day']:6} "
            f"{r['test_share'] * 100:5.0f}% {r['fix_share'] * 100:5.0f}% {r['feat_commits']:5} {r['ai_commits']:4} {r['merges']:6}"
        )


if __name__ == "__main__":
    sys.exit(main())
