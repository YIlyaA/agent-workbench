---
id: T-002
status: in-progress         # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # read-only analysis of another repo's git metadata; nothing is written there
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: metrics            # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 350
est_hours_old_way: 5     # confirmed by the human 2026-10-16; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true
---

# Task-level baseline mined from pre-agent git history

## Goal
Replace the hand-timed "old way" tasks in `docs/baseline.md` with a task-level baseline built from real pre-agent git history, and make a blind check of `est_hours_old_way` possible. Traces to `METRICS.md` "Baseline method" step 3 and the rule "my own baseline, not an imaginary average engineer". Direction approved by the human on 2026-10-16.

Source data for the later run (not used by the builder): `YASTUNING` (Django), pre-agent means before 2026-08-01. It has 38 merge commits before the cutoff, 326 non-merge commits and 8 branches. One person commits under three author names. The median gap between consecutive commits on the same day is 32 min (n=186).

## Scope (paths the builder may touch)
- `scripts/historic_baseline.py` (new)
- `tests/test_historic_baseline.py` (new)
- `docs/baseline.md` (replace the section "Task-level baseline in this repo (old way, timed)")
- `METRICS.md` (rewrite "Baseline method" step 3 only, one paragraph)

Nothing else. `scripts/git_metrics.py` must not change (AGENTS.md "Do not touch"). Do not run the script on YASTUNING or any other real repo. That happens in the human-gated calibration step below.

## Specification

### CLI
`uv run python scripts/historic_baseline.py <repo> [--before 2026-08-01] [--json OUT.json] [--blind BLIND.json]`

- `--before`: an ISO date (`YYYY-MM-DD`), default `2026-08-01`. An invalid value is an argparse error (exit 2).
- `--json`: writes the full result (actuals, summary, constants, counts). utf-8, `ensure_ascii=False`, `indent=1`.
- `--blind`: writes **only** the blind sheet to its own file, so the estimating planner never opens a file that contains times. (This is an addition to the brief, made so the check is truly blind.)
- stdout gets only the summary table: numbers, ids and type names. It never prints commit subjects or branch names, because a Windows cp1252 console can fail on Cyrillic text.
- The JSON `repo` field holds the directory name only, never the full path (public repo redaction rule).
- If `<repo>` is not a git work tree, or git fails on a top-level call, print one line to stderr and exit 2. No traceback.

### Rules
- **Stdlib only. Read-only on the target repo.** Only `git log`, `git rev-parse` and `git rev-list` style metadata commands, called with `subprocess.run([...], ...)`, never `shell=True`, always `git -C <repo>`. No file contents, no `checkout`, no `fetch`, no writes. Use `pathlib`, `encoding="utf-8"` and `errors="replace"`. Type hints, small pure functions, ruff and mypy clean.
- **Reuse, do not copy.** Import `NOISE`, `TEST`, `FIX` and `FEAT` from `git_metrics`. The import must work both as `scripts.historic_baseline` (tests) and as `python scripts/historic_baseline.py` (CLI). Use `try: from scripts.git_metrics import ...` `except ImportError: from git_metrics import ...`, plus a narrow `# type: ignore[...]` only if mypy needs it. If that is not possible without changing `git_metrics.py`, stop and ask.
- **Named constants** at module top, listed in the docstring: `SESSION_GAP_MIN = 120`, `LEAD_IN_MIN = 30`, `SIZE_BUCKETS = (100, 500)`, `DEFAULT_BEFORE = "2026-08-01"`.
- **Time source:** author timestamps (`%at`) for all gap math, because rebases and amends keep the author date. Calendar comparisons (cutoff) use the author date in the commit's own UTC offset (`%aI`, date part), the same as `git_metrics.py` (`%ad`).

### Task units
1. List merges: `git log --all --merges --format=%H%x1f%P%x1f%at%x1f%aI%x1f%s`. Keep the ones whose `%aI` date part is **strictly before** `--before`.
2. Skip **sync merges**, whose subject matches `^Merge (remote-tracking )?branch '(origin/)?(main|master)'.* into `, meaning main was merged into a feature branch. Count them in `skipped.sync`.
3. Process the kept merges **oldest first**. For each one, read `git log --no-merges --numstat --format=... <M>^1..<M>`. For a normal merge this is the same set as `M^1..M^2`, and for an octopus merge it is the union over all side parents. A commit that an earlier merge already claimed is dropped, so each commit belongs to at most one task. Nested merges (a branch that contains merges) count in `nested_merges` on the task.
4. A merge whose range is empty after this is not a task. Count it in `skipped.empty`.
5. If a per-merge git call fails (a shallow clone with a missing parent, for example), skip that merge, count it in `skipped.error`, and go on.
6. Non-merge commits before the cutoff that no merge claimed are reported **only as a count**, `direct_commits`. Grouping them into tasks is out of scope.

### Per task
| Field | Rule |
|---|---|
| `id` | Merge sha, first 10 characters |
| `merged` | Merge author date (`YYYY-MM-DD`). Actuals only |
| `branch` | Parsed from `Merge branch 'X'`, `Merge branch 'X' into Y`, `Merge pull request #N from owner/X`. Otherwise `null` |
| `n_commits` | Non-merge commits in the task |
| `n_parents` | Parents of the merge (more than 2 means octopus) |
| `nested_merges` | Merge commits inside the range |
| `type` | Majority of `feat` (FEAT) / `fix` (FIX) / `other` across commit subjects. Ties go to `feat`, then `fix`, then `other` |
| `code_lines` | Added plus deleted lines in non-NOISE paths |
| `test_share` | Test lines / code lines, rounded to 3 places. 0 when `code_lines` is 0 |
| `files` | Distinct non-NOISE paths, binary files included |
| `binary_files` | Paths whose numstat is `-\t-`. They count in `files` and add 0 lines |
| `authors` | `{author name: commits}`. Actuals only. Other authors are kept and counted, never dropped (the same person has three names) |
| `subjects` | Commit subjects, oldest first. Blind sheet only |
| `sessions`, `low_min`, `high_min`, `mid_min` | See below. Actuals only |

Renamed paths: numstat prints `old => new` or `pre/{a => b}/post`. Resolve each to the **new** path before applying NOISE and TEST. Line counts are what git reports, so a pure rename counts 0 lines.

### Time range
- Sort the task's author timestamps. Start a new session when the gap to the previous commit is **greater than** `SESSION_GAP_MIN` (a gap of exactly 120 min stays in the same session).
- `low_min` = sum of (last minus first) over the sessions. `high_min` = `low_min + LEAD_IN_MIN * sessions`. `mid_min` = (low + high) / 2. All are rounded to whole minutes.
- Sessions use absolute timestamps, not calendar days, so a session can cross midnight or a time-zone change.
- The merge commit's own timestamp is not used, because merges often happen days after the work.
- **Single-commit task:** `low_min = 0`, `high_min = 30`, `sessions = 1`. It is reported like any other task. The summary also counts `zero_low_tasks` so the reader can see how many ranges rest on lead-in alone.

### Outputs
- **Blind sheet:** a list of `{id, branch, type, n_commits, files, code_lines, test_share, subjects}` sorted by `id`. Sorting by sha hides the chronological order. It must contain no time, date, author, session or minute field.
- **Actuals:** a list of `{id, merged, n_commits, n_parents, nested_merges, authors, sessions, low_min, high_min, mid_min}`.
- **Summary:** for each group (`all`, each type, and each size bucket `<100`, `100-500`, `>500` with 100 and 500 in the middle bucket): `n` and the median of `low_min`, `high_min` and `mid_min`. Empty groups are left out. It also carries `tasks`, `direct_commits`, `zero_low_tasks`, `skipped {sync, empty, error}`, `constants`, `cutoff` and `generated` (today's date).

## Acceptance criteria
- [ ] `uv run python scripts/historic_baseline.py <tmp repo>` prints the summary. `--json` and `--blind` write the two files described above.
- [ ] The blind file and every blind-sheet entry contain no keys matching `date|merged|time|min|session|author|ts`, and no value matches `\d{4}-\d{2}-\d{2}` (checked in a test on the fixture repo).
- [ ] Every row in the edge-case table has a test, or is marked n/a with a reason.
- [ ] `NOISE`, `TEST`, `FIX` and `FEAT` are imported from `git_metrics`, not copied. `scripts/git_metrics.py` is unchanged.
- [ ] No `shell=True`, no git subcommand other than `log`, `rev-parse` and `rev-list` (the verifier greps for this).
- [ ] `docs/baseline.md`: the section "Task-level baseline in this repo (old way, timed)" is replaced by "Task-level baseline from git history". It gives the method, the constants, the limits (commit time is not hours worked; autocomplete already existed then; author aliases; the result is a range, not a point; uncommitted work before and after a session is invisible; breaks shorter than 120 min count as work) and two `<TODO>` tables: (1) the summary per group: n, median low, high and mid minutes; (2) calibration: tasks estimated, median `actual_mid_min / (estimate_hours * 60)`, p25 to p75, date.
- [ ] `METRICS.md` step 3 says the task-level baseline comes from `scripts/historic_baseline.py`: merges are tasks, sessions split at more than 120 min, the range adds 30 min lead-in per session, and estimates are calibrated blind. No other line in METRICS.md changes.
- [ ] Diff of at most 300 lines in total. If the script and tests together go over this, stop and report with a split proposal: (a) script and tests, (b) docs. Do not drop edge-case tests to fit.
- [ ] `uv run python scripts/check.py` passes on the PR's CI (Linux, macOS, Windows).

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| Empty repo | `git init`, no commits | Exit 0, `tasks: 0`, `direct_commits: 0`, empty blind sheet | `test_empty_repo` |
| Repo with no merges | 3 linear commits before the cutoff | `tasks: 0`, `direct_commits: 3` | `test_no_merges` |
| Not a git repo | plain temp dir; also a missing path | Exit 2, one stderr line, no traceback | `test_not_a_repo` |
| Invalid `--before` | `--before 2026-13-40` | argparse error, exit 2 | `test_bad_cutoff` |
| Merge with zero non-merge commits | `--no-ff` merge of a branch already contained in main (or one whose commits an earlier merge claimed) | Not a task; `skipped.empty += 1` | `test_empty_merge` |
| Octopus merge | `git merge --no-ff b1 b2` | One task, commits from both branches, `n_parents: 3` | `test_octopus` |
| Branch that contains merges | `b` merged into `a`, then `a` into main | Two tasks; `b`'s commits only in the first; second has `nested_merges: 1`; no commit is counted twice | `test_nested_merge_no_double_count` |
| Sync merge | `Merge branch 'main' into feat-x` | Skipped, `skipped.sync += 1`; main's commits are not given to it | `test_sync_merge_skipped` |
| Commits spanning midnight | 23:30 and 00:20 on the next day | One session, `low_min = 50` | `test_sessions_cross_midnight` (pure) |
| Identical timestamps | two commits at the same second | Gap 0, same session, adds 0 | `test_identical_timestamps` (pure) |
| Gap exactly 120 min / 121 min | timestamps 0, 120, 241 min | Sessions `[0,120]`, `[241]`; low 120, high 180 | `test_session_gap_boundary` (pure) |
| Single-commit task | branch with 1 commit | `low 0`, `high 30`, `sessions 1`; `zero_low_tasks` counts it | `test_single_commit_task` |
| Other authors in range | 2 commits by "A", 1 by "B" | All 3 kept; `authors: {A: 2, B: 1}` in actuals, absent from blind | `test_other_authors_counted` |
| Binary files | add a `.bin` file (numstat `-\t-`) | `files` includes it, `binary_files: 1`, 0 lines, no crash | `test_binary_numstat` |
| Renamed files | `git mv src/a.py src/b.py` plus a 1-line edit; also the brace form `pkg/{a => b}/x.py` | Path resolves to the new name; lines as git reports | `test_rename_path` (pure) + fixture |
| Noise excluded | commit touching `migrations/0001.py`, `x.lock`, `app.py` | Only `app.py` lines count | `test_noise_excluded` |
| Test share | 10 lines in `tests/test_x.py`, 30 in `app.py` | `test_share 0.25` | `test_test_share` |
| Cutoff exactly on a merge date | merge at `2026-08-01T00:00:00+03:00` and one at `2026-07-31T23:59:59+03:00` | First excluded (strict `<`), second included | `test_cutoff_boundary` |
| Time zones in commit dates | commits at `+03:00` and `-05:00` in one task | Gaps from unix seconds are correct; cutoff uses each merge's own offset date | `test_mixed_offsets` |
| Commit before cutoff, merge after | branch work in July, merged 2026-08-02 | Not a task; its commits count in `direct_commits` only if no kept merge claims them | `test_merge_after_cutoff` |
| Type majority and tie | 2 `feat:` + 1 `fix:`; 1 `feat:` + 1 `fix:`; `fixed typo` | `feat`; tie gives `feat`; `fixed typo` is `other` (FIX needs `fix:`/`fix(`/`fix `) | `test_type_majority` (pure) |
| Size buckets | 99, 100, 500, 501 lines | `<100`, `100-500`, `100-500`, `>500` | `test_size_bucket` (pure) |
| Blind sheet has no time | full fixture | No forbidden keys or ISO dates; sorted by id | `test_blind_sheet_is_blind` |
| Non-ASCII subjects and branch | Cyrillic subject, path with a space | JSON round-trips utf-8; stdout has no subjects | `test_unicode_and_spaces` |
| Retry / duplicate run | run twice on the same repo | Byte-identical JSON except `generated` | `test_deterministic` |
| Partial failure | one per-merge git call raises (monkeypatched runner) | That merge goes to `skipped.error`, the others are still reported | `test_partial_failure` |
| Maximal | many merges | One git call per merge plus two listing calls; no quadratic loops. 38 merges are trivial | n/a (by design; the verifier checks the call count in code) |
| Concurrent | two runs at once on the same repo | Read-only git calls, no shared state, no temp files in the repo | n/a (by design) |
| Permissions | repo unreadable or git missing on PATH | Exit 2 with one stderr line | covered by `test_not_a_repo` (same path) |
| Target repo untouched | after a full run | `git status --porcelain` and `HEAD` unchanged, no new refs | `test_read_only` |

## Test plan
- Write the pure-function tests first (session split, range math, rename path, type majority, size bucket) and watch them fail. Then write the fixture tests.
- Fixture helper: `git init -b main` in `tmp_path`. Per commit, pass `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` (ISO 8601 with offset) through `env`. Isolate from the user's config with `GIT_CONFIG_GLOBAL=<empty file in tmp_path>` and `GIT_CONFIG_NOSYSTEM=1`, and set `user.name`, `user.email` and `commit.gpgsign=false` locally. Branches with `git switch -c`, merges with `git merge --no-ff -m ...`. All calls are `subprocess.run([...])` lists. Write files with `pathlib` and `encoding="utf-8"`, using `newline="\n"` so Windows line counts match.
- Call `main(argv)` in-process for CLI tests, and use `capsys` for stdout and stderr.
- Command: `uv run python scripts/check.py`.

## Builder notes
- Keep the script near 170 lines. A table of fixture specs (branch, list of `(iso_date, path, lines, subject)`) keeps the tests compact.
- Do not try to cluster direct commits into tasks, add author alias merging, or read file contents. All three are out of scope.
- If the import of `git_metrics` fights mypy or ruff in a way a one-line ignore cannot solve, stop and ask. Do not copy the regexes.

## Calibration (human-gated, after merge; NOT builder scope)
1. The human asks the orchestrator to run `uv run python scripts/historic_baseline.py <YASTUNING> --before 2026-08-01 --json <scratch>/actuals.json --blind <scratch>/blind.json`. The output stays outside this repo. It contains private commit subjects and must not be committed.
2. A **fresh planner** with no access to `actuals.json`, git history or this task's log estimates `est_hours_old_way` for every task, using only `blind.json` and `docs/baseline.md` (with the summary table still `<TODO>`, so it cannot anchor on the medians).
3. The orchestrator computes `ratio = actual_mid_min / (estimate_hours * 60)` per task. It reports the median, p25 to p75, n, and also the share of tasks whose estimate falls inside `[low, high]`.
4. The human records the summary table and the calibration factor in `docs/baseline.md` and adds a sentence to METRICS.md ("planner estimates are multiplied by F"). That is a separate docs task. Metrics data is L1: the agent proposes, the human confirms.
5. Pre-registered before the run: if fewer than 15 tasks remain after skips, or if more than half have `low = 0`, report the factor as indicative only.

## Planning notes
- **People / Process / Technology:** People: the human no longer spends hours timing old-way tasks by hand. Process: blind estimation separates the estimate from the actuals, so the frozen `est_hours_old_way` gets a measured error bar. Technology: one stdlib script that reuses the `git_metrics` regexes.
- **Pareto:** merge = task plus session clustering gives most of the value. Direct-commit grouping, alias merging and per-file churn weighting are the long tail and are left out.
- **Revenue / Risk / Cost:** no revenue impact. It makes the 10x claim checkable, which is the purpose of this repo. Risk is low: read-only, with no guardrail paths. The main risk is a misleading number, and the range, the pre-registered thresholds and the limits section in docs address it. Cost: one builder session plus one calibration session.
- **Estimate basis (`est_hours_old_way: 5`):** a backend Python engineer with autocomplete. About 1.5 h for the script (git parsing, rename forms, session math, CLI), about 2.5 h for tests (a deterministic temp-repo fixture with dates, octopus and nested merges, Windows line endings), about 0.5 h for docs, and about 0.5 h for check.py and CI fixes. T-001 (a hook of similar size, 3 h) is the reference point; this task has more fixture work. The human confirms or changes it at approval.

## Log (filled in by the builder and verifier)
- Start / end: 21:14 / stopped 21:19 (diff limit reached; docs part not done, split proposed)
- Checks run (command and real output): `uv run python scripts/check.py` -> ruff check OK, ruff format OK, mypy OK (17 files), pytest 221 passed, agent layer OK, ALL CHECKS PASSED. Script plus tests alone are over 560 lines (limit 350 / 300), so docs/baseline.md and METRICS.md are left for part (b).
- Verifier verdict and findings:
- Human review (minutes, notes):
