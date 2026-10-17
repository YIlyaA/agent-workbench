---
id: T-003
status: ready-for-review # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # tests only; the script under test is read-only and is not changed
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: tests              # feature | bugfix | docs | skill | metrics | research | tests
diff_limit_lines: 220
est_hours_old_way: 1.5     # confirmed by the human 2026-10-17; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true
---

# Tests for scripts/git_metrics.py on a deterministic temp repo

## Goal
`scripts/git_metrics.py` feeds headline number 1 in METRICS.md ("git-level output per active day"), but it has no tests. Pin its behavior with a fixed fixture repo so a later change (which needs its own task) cannot silently move the baseline. Find and record bugs; do not fix them.

## Scope (paths the builder may touch)
- `tests/test_git_metrics.py` (new)
- this task file: `status` and the Log section only

Nothing else.
- `scripts/git_metrics.py` is on the AGENTS.md "Do not touch" list. **Do not edit it**, not even formatting. If a test exposes a real bug, mark that test `pytest.mark.xfail(strict=True, reason="git_metrics bug: <one line>")`, so it asserts the intended behavior and check.py stays green. Then record the bug in the Log. A follow-up task fixes it.
- Do **not** edit `session-log/tasks.csv`. The orchestrator writes the row after merge.
- Do not run the script on any real repo, including this one. Use only `tmp_path` repos.

## Fixture (exact)
Make one module-level helper that builds this repo in `tmp_path`. Isolate git: `monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")` and `GIT_CONFIG_GLOBAL=<empty file in tmp_path>`, so both the fixture and the script under test inherit it. Then run `git init -b main`, and set `commit.gpgsign=false` and `core.autocrlf=false` locally. Each commit sets `GIT_AUTHOR_DATE`, `GIT_COMMITTER_DATE`, `GIT_AUTHOR_NAME`/`EMAIL` and `GIT_COMMITTER_NAME`/`EMAIL` through `env=`. Write files with `pathlib`, `encoding="utf-8"` and `newline="\n"`. Write the binary file with `write_bytes` and a NUL byte in it. All calls are `subprocess.run([...], check=True)` lists. Use ASCII only: the script decodes git output with the locale encoding on Windows.

| # | Branch | Author date (committer date if different) | Author | Subject / body | Files (lines) |
|---|---|---|---|---|---|
| 1 | main | 2026-01-15T10:00:00+00:00 | Dev `<dev@example.com>` | `feat: add app` | `app.py` (10), `uv.lock` (50), `package-lock.json` (40), `migrations/0001_init.py` (30) |
| 2 | main | 2026-01-15T15:00:00+00:00 | Dev | `fix: off by one` | `tests/test_app.py` (5 new), `app.py` (change 1 line: +1 -1) |
| 3 | main | 2026-01-20T09:00:00+00:00 (committer 2026-03-10T09:00:00+00:00) | Dev | `chore: add logo` | `logo.bin` (binary) |
| 4 | main | 2026-01-31T23:30:00-05:00 (UTC is already 02-01) | Dev | `docs: notes` | `notes.md` (4) |
| 5 | feature | 2026-02-03T11:00:00+00:00 | Other Dev `<other@example.com>` | `feat: widget` + body `Co-Authored-By: Claude <noreply@anthropic.com>` | `widget.py` (6) |
| M | main | 2026-02-04T12:00:00+00:00 | Dev | `git merge --no-ff feature -m "Merge branch 'feature'"` | none |

Expected JSON `months` (from `--out`):

| month | commits | active_days | commits_per_active_day | code_lines | lines_per_active_day | test_share | fix_share | feat_commits | ai_commits | merges |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-01 | 4 | 3 | 1.33 | 21 | 7 | 0.238 | 0.25 | 1 | 0 | 0 |
| 2026-02 | 1 | 1 | 1.0 | 6 | 6 | 0 | 0.0 | 1 | 1 | 1 |

`total_commits` is 5. There is no `2026-03` row (the committer date is ignored). If a number differs, check the fixture first. If the fixture is right, the difference is a finding: record it, do not change the expectation to match.

## Acceptance criteria
- [ ] `tests/test_git_metrics.py` builds the fixture above and asserts every cell of the expected table, plus `total_commits`.
- [ ] Every edge-case row below has a test, or is marked n/a with the reason given.
- [ ] Known or suspected bugs are `xfail(strict=True)` tests with a one-line reason and a Log entry. No test asserts buggy output as if it were intended, except rows marked "pin" below, which carry a comment saying "pins current behavior".
- [ ] `git diff main -- scripts/` is empty.
- [ ] Parametrize ids are short (`ids=[...]` with at most 20 characters each). Windows caps env vars, see T-001 attempt 2d.
- [ ] The test file is ruff and mypy clean (it is in mypy's `files`).
- [ ] Diff at most 220 lines. If you hit the limit, stop and report. Do not drop edge-case tests to fit.
- [ ] `uv run python scripts/check.py` passes.

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| Per-month split | full fixture | Two rows, 2026-01 and 2026-02, values as in the table | `test_months_match_fixture` |
| Time zone, month boundary | commit 4 at `2026-01-31T23:30-05:00` (02-01 in UTC) | Counted in 2026-01; day `2026-01-31` is one of the 3 active days | covered by `test_months_match_fixture` (assert `active_days == 3`) |
| Committer date differs | commit 3, committer date in March | Author date wins; no 2026-03 row | `test_author_date_not_committer_date` |
| Same day, two commits | commits 1 and 2 on 01-15 | One active day | covered by `active_days == 3` |
| Noise excluded | `uv.lock`, `package-lock.json`, `migrations/0001_init.py` in commit 1 | Commit 1 adds 10 code lines, not 130 | covered by `code_lines == 21` |
| Test share | 5 test lines of 21 | `0.238` | covered by table |
| Binary file | `logo.bin` with NUL (numstat `-\t-`) | Counted as a commit, 0 lines, no crash | covered by `commits == 4` and `code_lines == 21` |
| Fix / feat regex | `fix: a`, `Fix(x): a`, `hotfix: a`, `revert "x"`, `fixed typo`, `prefix: fix`; `feat: a`, `feature x` | FIX matches the first 4 only; FEAT matches `feat: a` only | `test_fix_feat_regex` (parametrized, ids `fix1`..) |
| Merge commit | merge M | Not in `commits`; `merges == 1` in 2026-02 | covered by table |
| AI marker | commit 5 body `Co-Authored-By:` | `ai_commits == 1` in 2026-02 | covered by table |
| `--author` by name | `--author other` (lower case) | Only commit 5; `total_commits == 1`; months `[2026-02]` | `test_author_filter_name` |
| `--author` ignores merges (pin) | same run | 2026-02 still shows `merges == 1` (merges are not filtered by author) | same test, comment "pins current behavior" |
| `--author` by email | `--author dev@example.com` (help text says "name/email") | Intended: commits 1-4 match. Code compares `%an` only, so it gets 0 | `test_author_filter_email` **xfail strict** (suspected bug) |
| Merge on another branch | after the fixture, merge a branch into `side` (not reachable from HEAD) dated 2026-02-10 | Intended: `merges == 2` in 2026-02 (commits use `--all`, merges do not) | `test_merge_not_on_head` **xfail strict** (suspected bug) |
| `--out` JSON | `--out <tmp>/m.json` | File is valid JSON with keys `repo`, `total_commits`, `months`, `generated`; stdout has a header plus one line per month | `test_out_json_and_stdout` |
| Empty repo | `git init`, no commits | Intended: `total_commits == 0`, no traceback. Code: `git log` exits 128, so `CalledProcessError` | `test_empty_repo` **xfail strict** (suspected bug) |
| Not a repo | plain `tmp_path` dir | Raises `subprocess.CalledProcessError` (pin; acceptable for a read-only CLI) | `test_not_a_repo` |
| Retry / duplicate run | run twice | Same `months` and `total_commits` both times | `test_deterministic` |
| Read-only | after a run | `git status --porcelain` empty and `HEAD` unchanged | `test_repo_untouched` |
| Concurrent | two runs at once | n/a: read-only `git log`, no shared state | n/a (by design) |
| Permissions | unwritable `--out` path | n/a: raises `OSError`; chmod is not portable to Windows | n/a |
| Maximal | thousands of commits | n/a: one `git log` call per run, linear parsing | n/a (by design) |

## Test plan
- Call the script in-process: `from scripts import git_metrics`, then `monkeypatch.setattr(sys, "argv", ["git_metrics.py", str(repo), "--out", str(out)])`, call `git_metrics.main()`, and read `out` with `encoding="utf-8"`. Use `capsys` for stdout. Add no subprocess run of the script; in-process covers the same code.
- Build the fixture once per test, using a function and `tmp_path`. The repo is small, so this is fast enough.
- Write tests first. Most should pass right away, because this is characterization. Confirm that each xfail test really fails for the stated reason: run it once without the marker and paste the assertion line into the Log.
- Command: `uv run python scripts/check.py`.

## Builder notes
- `git_metrics.main()` reads `sys.argv` through argparse. Do not change that; monkeypatch `sys.argv`.
- Compare values as they appear in JSON (the script already rounds). `0`, `0.0`, `1` and `1.0` compare equal in Python, so do not assert types.
- If `core.autocrlf` or a system config still changes line counts on Windows CI, report it in the Log. Do not loosen the expected numbers.

## Planning notes
- **People / Process / Technology:** People: the human trusts the per-day baseline without re-checking it by hand. Process: this turns the "Do not touch" rule into an enforced contract, because any change to the script now has to pass these tests. Technology: one test file, a deterministic temp repo.
- **Pareto:** the monthly table on one fixture covers about 80% of the risk. The xfail rows document the three suspected bugs instead of fixing them.
- **Revenue / Risk / Cost:** no revenue. Risk is low: tests only. Cost: one session.
- **Estimate basis (`est_hours_old_way: 1.5`):** about 45 min to build a deterministic dated fixture with a merge, a binary file and Windows-safe line endings (T-002 reused a similar helper), 30 min of assertions and xfail triage, 15 min for CI. Realistic, not generous, per the T-002 calibration.
- **Size basis (220 lines):** fixture helper about 45 lines, about 14 tests at about 8 lines each, plus the regex parametrization.

## Log (filled in by the builder and verifier)
- Start / end: 10:06 / 10:07 (machine clock)
- Bugs found in `scripts/git_metrics.py` (not fixed), each confirmed with `--runxfail`:
  - `--author` matches `%an` only, not email: `assert 0 == 4` (test_author_filter_email).
  - merges counted without `--all`, so a merge on a non-HEAD branch is missed: `assert 1 == 2` (test_merge_not_on_head).
  - empty repo: `git log --merges` exits 128, `CalledProcessError` (test_empty_repo).
  - Also: merges are not author-filtered (pinned in test_author_filter_name).
- Checks run: `uv run python scripts/check.py` -> ruff, format, mypy OK; `257 passed, 3 xfailed`; ALL CHECKS PASSED.
- Attempt 2 (verifier FAIL on 6f14bc1, isolation): `isolate()` now deletes GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY, GIT_COMMON_DIR, GIT_NAMESPACE, GIT_ALTERNATE_OBJECT_DIRECTORIES and points HOME, USERPROFILE, XDG_CONFIG_HOME into tmp_path. New `test_fixture_ignores_git_dir`. Empty repo built in an `empty` fixture, xfail has `raises=CalledProcessError`. All `type: ignore` removed, tests annotated. Check: `258 passed, 3 xfailed`, ALL CHECKS PASSED. Also ran the file with an external GIT_DIR set: passes, external repo stayed at 0 commits.
- Attempt 3 (verifier FAIL on 9d0c0f2): `clean_env()` deletes every `GIT_*` env var, then sets HOME/XDG and GIT_CONFIG_*. `isolate()` converts setup failures to `pytest.fail` so the empty-repo xfail (`raises=CalledProcessError`) cannot hide them. `test_fixture_ignores_git_env` parametrized over GIT_DIR, GIT_COMMON_DIR, GIT_WORK_TREE, GIT_CONFIG (replaces the single-variable test; compares a full snapshot of the outside repo). `test_not_a_repo` calls `isolate()`. Mutation check: weakening the GIT_ filter makes all 4 params fail. Check: `261 passed, 3 xfailed`, ALL CHECKS PASSED.
- Timing from commit times (`git log --format='%h %ad' --date=format:%H:%M 2cdb273..HEAD`): attempt 1 commit 6f14bc1 at 10:07, attempt 2 commit 9d0c0f2 at 10:12; attempt 3 commit time is in the commit itself (see git log). Attempt 1 start was 10:06 per the task.
- Verifier verdict and findings:
- Human review (minutes, notes):
