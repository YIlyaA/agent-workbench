---
id: T-007
status: approved          # draft | approved | in-progress | ready-for-review | done | rejected
risk: medium             # changes the read-only script behind headline number 1 (METRICS.md); T-010 re-checks the baseline
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: bugfix             # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 120    # task file not counted
est_hours_old_way: 1     # confirmed by the human 2026-10-17; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true        # disjoint files from T-008; nothing else runs on git_metrics.py
---

# git_metrics.py fixes: author email, merges from all refs, stash, empty repo

## Goal
Fix the 3 bugs that T-003 pinned as strict xfail tests in `scripts/git_metrics.py`, plus a fourth one found while planning (stash commits counted). Traces to headline number 1 in METRICS.md ("git-level output per active day"), which this script computes.

The original request (2026-10-17) had three parts. The human approved splitting them on 2026-10-17 ("approve T-007..T-010"). **This file is part A, and everything below is this builder's task.** Part B (baseline re-check) is [T-010](T-010-baseline-recheck.md); part C (hard diff limit) is [T-008](T-008-diff-limit-check.md) and [T-009](T-009-diff-limit-ci-and-rules.md). The split table is kept in Planning notes as a record.

## Scope (paths the builder may touch)
- `scripts/git_metrics.py`
- `tests/test_git_metrics.py`
- `pyproject.toml`: only the comment on the `per-file-ignores` line for `scripts/git_metrics.py`. It says "AST identical to the original", which stops being true. New text: `# From the reference design (decision 0001); behavior changed by T-007 (author email, merges from all refs, stash excluded).` Keep the ignore list itself unchanged.
- this task file: `status` and the Log section only

Nothing else. `scripts/git_metrics.py` is on the AGENTS.md "Do not touch" list ("changes need a task"). **This is that task.** Do not edit `AGENTS.md`: T-009 rewords that line. Do **not** edit `session-log/tasks.csv`, because the orchestrator writes the row after merge. Do not run the script on any real repo, this one included. Use only `tmp_path` repos.

## Specification
1. **`--author` matches name or email.** Add `%ae` to the non-merge format: `\x1e%H\x1f%ad\x1f%an\x1f%ae\x1f%s\x1f%b\x1f`, then split into 7 fields. A commit is kept when `needle in name.lower() or needle in email.lower()`, where `needle = a.author.lower()`. Match each field on its own and never a joined `"name <email>"` string, so `dev <dev` matches nothing. Put the predicate in one small function, `author_matches(needle, name, email) -> bool`. Commits and merges both use it.
2. **Merges come from all refs, stash excluded.** Both `git log` calls use the same ref set, `ALL_REFS = ("--exclude=refs/stash", "--all")`. This is the constant `historic_baseline.py` already uses. A stash is a merge-shaped commit (`WIP on ...`), and its index and untracked parts are non-merge commits. So the existing non-merge call with bare `--all` already counts stash commits. That is a **fourth bug**, and this task fixes it too, because adding bare `--all` to the merges call would count every stash as a merge. Order matters: `--exclude` must come before `--all`.
3. **Merges follow `--author` (decision).** T-003 pinned that merges ignore `--author`. Change it so that merges are filtered with the same `author_matches`. Reason: with `--author`, each row should describe that author's activity, and a merge made by someone else is not their activity. Without `--author` nothing changes. The merges call becomes `log ALL_REFS --merges --date=short --pretty=format:%ad%x1f%an%x1f%ae`, parsed with `.splitlines()` and then `.split("\x1f")`. Do not use `.split()`, because names contain spaces. The `merges` column is not published in `docs/baseline.md`, so this decision cannot move a published number (T-010 confirms this).
4. **Empty repo.** With `ALL_REFS` on both calls, `git log` on a repo with no refs exits 0 and prints nothing. Expected: `total_commits == 0`, `months == []`, stdout is the header line only, and `--out` JSON is still written. If some git version on CI still exits 128, do not add a `try/except` around everything. Add one guard before the two log calls instead: `git for-each-ref --count=1` (read-only) and, if it prints nothing, take the empty result path. Record this in the Log.
5. **Not a repo** keeps raising `CalledProcessError` (pinned by `test_not_a_repo`, unchanged).
6. **Unchanged:** NOISE, TEST, FIX, FEAT, the author-date (`%ad`) month rule, rounding, the JSON keys, the stdout format, and the rule that a month appears only if it has non-merge commits (merges in a month with no commits are not shown).

## Acceptance criteria
- [ ] The three `xfail` markers are removed. `test_author_filter_email`, `test_merge_not_on_head` and `test_empty_repo` pass as normal tests, with the intended assertions T-003 wrote (extended as in the table below).
- [ ] `test_author_filter_name` now asserts `merges == 0` in 2026-02, with the comment `# T-007: merges follow --author`.
- [ ] `test_months_match_fixture`, `MONTHS` and the fixture builder are unchanged. The no-argument output on the T-003 fixture is identical before and after.
- [ ] The helpers `git`, `commit`, `clean_env` and `isolate` in `tests/test_git_metrics.py` keep their names and signatures (T-008 imports them).
- [ ] Every edge-case row below has a test, or is n/a with a reason.
- [ ] Each new test fails on `main` for the stated reason before the fix. Paste one failure line per test into the Log.
- [ ] No new `# noqa`, `# type: ignore`, `# fmt: skip` or `# fmt: off` to save lines. Any suppression needs a one-line reason, and the verifier must agree it is not there to fit the limit.
- [ ] Parametrize ids are at most 20 characters.
- [ ] Diff at most 120 lines (insertions plus deletions against the merge-base with `main`, not counting this task file). **If you reach the limit, stop and report. Do not trim tests or join lines to fit.** If T-008 is already on `main` when you run `check.py`, it enforces this for you.
- [ ] `uv run python scripts/check.py` passes on CI (Linux, macOS, Windows).

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| Author by email | `--author dev@example.com` | `total_commits == 4`; months `["2026-01"]`; 2026-01 `merges == 0`. Merge M (Dev, 2026-02) is not shown because Dev has no 2026-02 commits (pinned month rule) | `test_author_filter_email` (xfail removed, asserts extended) |
| Email, other case | `--author DEV@EXAMPLE.COM` | Same as above | same test, parametrized (ids `lower`, `upper`) |
| Shared domain | `--author example.com` | All 5 commits; 2026-02 `merges == 1` | `test_author_filter_domain` |
| No cross-field match | `--author "dev <dev"` | `total_commits == 0`, `months == []`, no crash | `test_author_no_match` (ids `joined`, `nobody`) |
| No match at all | `--author nobody` | `total_commits == 0`, `months == []` | same test, second param |
| Merges follow `--author` (decision) | `--author other` | Commit 5 only; 2026-02 `merges == 0` (M is by Dev) | `test_author_filter_name` (assertion changed from 1 to 0) |
| Merge not reachable from HEAD | after the fixture, `side` merges `feature` with author `Other Dev`, dated `2026-02-28T23:30:00-05:00` (UTC is already March) | No args: 2026-02 `merges == 2`; no 2026-03 row. With `--author "other dev"`: 2026-02 `merges == 1` (a name with a space parses) | `test_merge_not_on_head` (xfail removed; date changed to the boundary value; one extra assert) |
| Time zone, month boundary for merges | same merge as above | Counted in the month of its own offset date (2026-02), the same rule as commits | covered by `test_merge_not_on_head` |
| Stash is not a commit or a merge | fixture, then change `app.py`, add an untracked `scratch.py`, run `git stash push -u` | Output equals the fixture output: `total_commits == 5`, `MONTHS` unchanged. Fails on `main` (the stash index and untracked commits are counted) | `test_stash_ignored` |
| Read-only with a stash | same run | `git stash list` still has 1 entry; HEAD unchanged | same test |
| Empty repo | `git init`, no commits | `total_commits == 0`, `months == []`, stdout is 1 header line, JSON has the 4 keys | `test_empty_repo` (xfail removed) |
| Unborn HEAD, other refs exist | fixture, then `git checkout -q --orphan fresh` (no commit) | Same `months` as the fixture | `test_unborn_head` |
| Not a repo | plain dir | `CalledProcessError` (pin, unchanged) | `test_not_a_repo` (unchanged) |
| No args unchanged | full fixture | `MONTHS` and `total_commits == 5` exactly as before | `test_months_match_fixture` (unchanged) |
| Retry / duplicate | run twice | Same output | `test_deterministic` (unchanged) |
| Concurrent | two runs at once | n/a: read-only `git log`, no shared state | n/a (by design) |
| Permissions | unwritable `--out` | n/a: raises `OSError` as before; chmod is not portable to Windows | n/a |
| Maximal | thousands of commits | n/a: still two `git log` calls (three with the empty-repo guard), linear parsing | n/a (by design) |

## Test plan
- Tests first: remove the three xfail markers, extend them as in the table, add `test_author_filter_domain`, `test_author_no_match`, `test_stash_ignored` and `test_unborn_head`. Run `uv run pytest tests/test_git_metrics.py` on the unchanged script and paste one failure line per test into the Log. `test_author_no_match` may pass on `main`. Note that in the Log, since it guards the fix against a joined-string implementation.
- Reuse the existing `git`, `commit` and `run` helpers. The stash needs a committer identity, and `git()` already sets one through `env`.
- Command: `uv run python scripts/check.py`.

## Builder notes
- Keep the script's style (it is excluded from E401/I001/E501/B007/UP). Make the smallest change that works, and do not reformat untouched lines.
- `install.py` copies `scripts/git_metrics.py` into the bootstrap `reference/` folder. The fix reaches other projects only when the human runs the installer again. That is not in scope.
- T-008 runs in parallel and imports helpers from `tests/test_git_metrics.py`. Do not rename or move them.

## Log (filled in by the builder and verifier)
- Start / end:
- Failing tests before the fix (one line each):
- Checks run (command and real output):
- Diff size (insertions + deletions vs merge-base, task file excluded):
- Verifier verdict and findings:
- Human review (minutes, notes):

## Planning notes
- **People / Process / Technology:** People: the baseline the 10x answer rests on gets an explicit re-check (T-010). Process: a fix to headline-number code ships with a follow-up check instead of an assumption. Technology: about 15 changed lines in `git_metrics.py`.
- **Pareto:** cheap, and closes the known correctness gaps in the headline script.
- **Revenue / Risk / Cost:** no revenue. Risk: this changes headline-number code, so T-010 exists. Cost: one session.
- **Split record** (approved by the human 2026-10-17, "approve T-007..T-010"). Run order: T-007 and T-008 in parallel; then T-009 (after T-008) and T-010 (after T-007), at most 2 at once.

| id | part | scope (exact paths) | blocked_by | parallel_ok | diff_limit_lines | est_hours_old_way | risk |
|---|---|---|---|---|---:|---:|---|
| T-007 (this file) | A: git_metrics fixes | `scripts/git_metrics.py`, `tests/test_git_metrics.py`, `pyproject.toml` (one comment), this task file (status, Log) | none | yes | 120 | 1 | medium |
| T-008 | C1: `check_diff_limit.py` + `check.py` | `scripts/check_diff_limit.py` (new), `tests/test_check_diff_limit.py` (new), `scripts/check.py`, its task file (status, Log) | none | yes | 300 | 2 | low |
| T-009 | C2: CI job + rule text | `.github/workflows/ci.yml` (ask path), `AGENTS.md`, `CONTEXT.md`, `.claude/agents/builder.md`, `.claude/agents/planner.md`, `.claude/skills/plan-task/SKILL.md`, `.claude/skills/verify-diff/SKILL.md`, `tasks/_template.md`, its task file (status, Log) | T-008 | yes | 80 | 0.75 | medium (guardrail path) |
| T-010 | B: baseline re-check | `docs/baseline.md` (one new subsection), its task file. The run itself is an orchestrator step, approved by the split approval | T-007 | yes | 40 | 0.5 | low |

  Total: about 4.25 h (old way). Unsplit, the work came to about 450 lines and did not fit one session.
- **Estimate basis (`est_hours_old_way: 1`):** 15 min to confirm the git behaviours (stash shape, `--all` on an empty repo, `--exclude` order), 15 min for the code, 30 min for the four new tests and the three converted ones on the existing fixture. Realistic per the T-002 calibration. Planning aid only (METRICS.md headline note).
- **Size basis (120 lines):** about 30 lines changed in the script (insertions and deletions), about 55 in tests (4 new tests at about 8 lines, 3 converted ones at about 5, plus parametrize), and 2 in `pyproject.toml`. About 87, leaving a margin of about 30%.
- **Decisions recorded:** [0003](../docs/decisions/0003-diff-limit-hard-stop.md) (diff limit hard stop) and a note in [0001](../docs/decisions/0001-stack-and-layout.md) that `git_metrics.py` now differs from the reference design in behavior, not only formatting.
- **Assumptions:** git >= 2.20 on all CI runners (for `--exclude` with `--all`). `--all` on an empty repo exits 0 on every OS's git; spec item 4 gives the fallback.
- **Open risks:** the AGENTS.md "copied unchanged" line is inaccurate between this merge and T-009's merge (T-009 rewords it). If T-010 finds a stash in the source repo, the 2.4x to 2.7x ratio is recomputed there.
