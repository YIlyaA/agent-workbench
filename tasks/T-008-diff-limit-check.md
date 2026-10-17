---
id: T-008
status: in-progress         # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # new read-only script; turns over-limit branches red in check.py (intended)
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: feature            # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 300    # task file not counted
est_hours_old_way: 2     # confirmed by the human 2026-10-17; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true        # disjoint from T-007 (git_metrics); reads tests/test_git_metrics.py helpers but does not edit it
---

# Hard diff limit: scripts/check_diff_limit.py wired into check.py

## Goal
Make `diff_limit_lines` a mechanical hard stop instead of builder discretion (decision [0003](../docs/decisions/0003-diff-limit-hard-stop.md)). Every builder from T-001 to T-006 hit or passed its limit, and two of them bent code or tests to fit. This task is part C1 of the split approved by the human on 2026-10-17 ("approve T-007..T-010"). The CI job and the rule text are T-009.

## Scope (paths the builder may touch)
- `scripts/check_diff_limit.py` (new)
- `tests/test_check_diff_limit.py` (new)
- `scripts/check.py`: one new entry at the end of `CHECKS`, nothing else
- this task file: `status` and the Log section only

Nothing else. Do **not** edit `session-log/tasks.csv` (the orchestrator writes the row after merge), `tests/test_git_metrics.py` (T-007 owns it; import from it, do not change it), `AGENTS.md` or any rule text (T-009). Tests use `tmp_path` repos only. Never run the script against a repo outside the test fixtures, except the final `check.py` run in your own worktree.

## Specification
Flow: [docs/diagrams/diff-limit-check.md](../docs/diagrams/diff-limit-check.md).

1. **CLI:** `uv run python scripts/check_diff_limit.py [--root DIR] [--branch NAME] [--base REF] [--github]`. Entry point `main(argv: list[str] | None = None) -> int`. Stdlib only, read-only. Every git call is `["git", "-C", str(root), ...]` with list arguments, `capture_output=True`, `text=True`, `encoding="utf-8"`, `errors="replace"`. `--root` defaults to `Path(__file__).resolve().parent.parent`, so inside a worktree it is the worktree.
2. **Constants** (module level, named): `TASK_BRANCH = re.compile(r"^task/(T-\d+)(?:-|$)")`, `DEFAULT_BASE = "main"`, `TOP_FILES = 5`, `BINARY_SNIFF = 8000`.
3. **Branch:** `--branch`, else `git rev-parse --abbrev-ref HEAD`. Not starting with `task/` (`main`, `HEAD` when detached, `feature/x`) prints `diff limit: skip (not on a task branch: <name>)` and exits 0. Starts with `task/` but the regex does not match: exit 1 with the expected pattern, so a typo cannot switch the check off.
4. **Task file:** `tasks/<id>.md` or `tasks/<id>-*.md` under root, the same rule as `validate_agent_layer`. Exactly one, else exit 1 naming what was found. Read `diff_limit_lines` with `parse_frontmatter`, imported from `validate_agent_layer`. It must match `^\d+$` (so `int(value) >= 0`), else exit 1.
5. **Imports:** use the pattern in `historic_baseline.py`: `try: from scripts.x import ...` / `except ImportError: from x import ...  # type: ignore[no-redef]`. Import `parse_frontmatter` and `TEST` (from `git_metrics`). This one suppression is allowed; give it the same reason comment as in `historic_baseline.py`.
6. **Base:** `--base`, default `main`. `git merge-base HEAD <base>`. Failure (unknown ref, shallow clone, unrelated history) exits 1 with a message that mentions `fetch-depth: 0` and `--base origin/main`. Never a silent pass.
7. **Limit raised on the branch does not count.** If `git show <mb>:tasks/<file>` succeeds and its `diff_limit_lines` is lower than the branch value, use the base value and print `note: limit raised on this branch (<branch> -> <base>); using <base>`. If the file does not exist at the merge-base, use the branch value and print `limit source: branch`.
8. **Lines** = insertions + deletions of:
   - `git diff --numstat -z -M <mb>`: committed, staged and unstaged tracked changes. With `-z`, a normal entry is `add\tdel\tpath\0`; a rename is `add\tdel\t\0old\0new\0`. Binary entries (`-\t-`) count 0. Use the new path of a rename.
   - untracked, non-ignored files from `git ls-files --others --exclude-standard -z`, each read as bytes: 0 if a NUL is in the first `BINARY_SNIFF` bytes; else `data.count(b"\n")`, plus 1 if non-empty and not ending in `b"\n"`.
   - minus the task's own file (`tasks/<file>`, compared as a POSIX string, which is what git prints on every OS). Nothing else is excluded: other task files, tests and `session-log/tasks.csv` all count.
9. **Output** (ASCII only; the Windows console can be cp1252):
   - always: `diff limit: <n>/<limit> lines (tests <t>; base <short sha>; task file excluded)`, where `t` is the part of `n` in paths matching `TEST`.
   - over the limit, also the top `TOP_FILES` files by lines (`  <lines>  <path>`) and `Over the limit: stop and report. Do not trim tests, join lines or add lint suppressions to fit (AGENTS.md).` Exit 1.
   - `n == limit` passes.
10. **`--github`:** branch from env `GITHUB_HEAD_REF`, base `origin/<GITHUB_BASE_REF>`. If either is missing or empty, exit 1. Values come from `os.environ` only, never through a shell.
11. **`scripts/check.py`:** append `("diff limit", [PY, "scripts/check_diff_limit.py"])` as the **last** entry of `CHECKS`, so a builder sees every other result first. In CI the PR checkout is a detached `HEAD`, so this step skips there; CI enforcement is T-009.
12. Keep the functions small and pure where possible: `task_id(branch) -> str | None`, `find_task_file(root, tid) -> Path` (raises or returns), `count_untracked(data: bytes) -> int`, `parse_numstat_z(out: str) -> list[tuple[int, str]]`. Tests may call them directly.

## Acceptance criteria
- [ ] Every edge-case row below has a test, or is n/a with a reason.
- [ ] Tests import `clean_env`, `git` and `commit` from `tests.test_git_metrics` instead of copying them. One local fixture helper builds the base repo (`main` with `tasks/T-001-x.md` holding `diff_limit_lines: 10` and one source file), then creates `task/T-001-x`.
- [ ] `scripts/check.py` runs `diff limit` last; a test asserts `CHECKS[-1][0] == "diff limit"`.
- [ ] Running `uv run python scripts/check.py` in your worktree on `task/T-008-diff-limit-check` prints a `diff limit: n/300` line. Paste it into the Log.
- [ ] No new `# noqa`, `# type: ignore`, `# fmt: skip` or `# fmt: off`, except the one import suppression in spec item 5.
- [ ] Parametrize ids are at most 20 characters.
- [ ] Diff at most 300 lines (insertions plus deletions against the merge-base with `main`, not counting this task file). **If you reach the limit, stop and report. Do not trim tests or join lines to fit.** The proposed fallback is moving `--github` mode and `test_github_mode` into a follow-up task; the human decides.
- [ ] `uv run python scripts/check.py` passes on CI (Linux, macOS, Windows).

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| Not a task branch | `--branch main`, `--branch feature/x`, detached `HEAD` (`git checkout --detach`) | `diff limit: skip ...`, exit 0 | `test_skip_non_task` (ids `main`, `feature`, `detached`) |
| Bad task branch name | `task/t-001-x`, `task/foo` | Exit 1, message shows `task/T-<digits>-<slug>` | `test_bad_task_branch` (ids `lower`, `noid`) |
| No task file | branch `task/T-009-x`, no `tasks/T-009*.md` | Exit 1 | `test_task_file_missing` |
| Two task files | `T-001-a.md` and `T-001-b.md` | Exit 1, names both | `test_task_file_ambiguous` |
| Id prefix trap | branch `task/T-001-x`, only `tasks/T-0010-y.md` exists | Not matched, exit 1 | `test_task_file_missing` (id `prefix`) |
| Bare id branch | `task/T-001` | Matches `T-001-x.md`, runs normally | `test_limit_boundary` (id `bare`) |
| Bad limit | `diff_limit_lines:` empty, `abc`, `-5`, `300.0` | Exit 1 | `test_bad_limit` (ids `empty`, `text`, `neg`, `float`) |
| Under / equal / over by one | limit 10; committed diffs of 9, 10, 11 lines | Exit 0, 0, 1; over prints the top files and the stop text | `test_limit_boundary` (ids `under`, `equal`, `over`) |
| Retry / duplicate | same call twice | Identical stdout and exit code | `test_limit_boundary` (each param calls `main` twice) |
| Task file excluded | Log grows 50 lines, code 5 lines, limit 10 | Exit 0, counts 5 | `test_task_file_excluded` (id `own`) |
| Other task file counted | branch also edits `tasks/T-002-y.md` by 8 lines | Counts 13, exit 1 | `test_task_file_excluded` (id `other`) |
| Limit raised on branch | base has 10, branch sets 100, diff 20 | Uses 10, prints the note, exit 1 | `test_raised_limit_ignored` (id `raised`) |
| Task file new on branch | task file absent at merge-base, branch adds it with 100 | Uses 100, prints `limit source: branch`, exit 0 | `test_raised_limit_ignored` (id `new`) |
| Uncommitted tracked change | edit 4 lines, not staged | Counted | `test_working_tree_counted` |
| Untracked files | 7-line file; 3-line file with no final newline; 2-line CRLF file written as bytes | Counts 7, 3 and 2 on every OS | same test |
| Ignored file | `coverage.json` and `.venv/x` listed in `.gitignore` | Not counted | `test_working_tree_counted` (id `ignored`) |
| Binary file | tracked `a.bin` and untracked `b.bin`, both containing NUL | 0 lines, no crash | `test_binary_zero` |
| Rename | `git mv a.py b.py`, no edit | 0 lines | `test_rename_zero` |
| Main moved ahead | 30 lines committed on `main` after branching | Not counted (merge-base) | `test_merge_base_not_tip` (id `ahead`) |
| Main merged into branch | branch merges the moved `main` | Only the branch's own lines | `test_merge_base_not_tip` (id `merged`) |
| No base | `--base nope` | Exit 1, message mentions `fetch-depth: 0`; never exit 0 | `test_no_merge_base` |
| CI mode | `--github`, env `GITHUB_HEAD_REF=task/T-001-x`, `GITHUB_BASE_REF=main`, an `origin/main` ref made with `git update-ref refs/remotes/origin/main main` | Same count as local mode | `test_github_mode` (id `ok`) |
| CI mode, env missing | `--github`, `GITHUB_BASE_REF` unset (monkeypatch.delenv) | Exit 1 | `test_github_mode` (id `noenv`) |
| Hostile branch name | `GITHUB_HEAD_REF='task/T-001-x;echo pwned'` | Treated as a plain string: id `T-001` parsed, no shell, no extra output | `test_github_mode` (id `meta`) |
| Worktree | `git worktree add <tmp>/wt task/T-001-x`, `--root <tmp>/wt` | Same count as in the main checkout | `test_worktree` |
| Wiring | `scripts.check.CHECKS` | Last entry is `diff limit` running `scripts/check_diff_limit.py` | `test_check_py_runs_last` |
| Concurrent | 3 builders in 3 worktrees | n/a: read-only, per-worktree state, no temp files | n/a (by design) |
| Permissions | unreadable untracked file | n/a: `OSError` propagates and check.py fails loudly (a hard stop must not undercount); chmod is not portable to Windows | n/a |
| Maximal | a 10,000-line diff | n/a: one `diff` call plus one `ls-files`, linear | n/a (by design) |
| Partial failure | a git call fails mid-run | Exit 1 with git's stderr; never prints a pass line | covered by `test_no_merge_base` |

## Test plan
- Tests first. Write `tests/test_check_diff_limit.py` against the spec, run `uv run pytest tests/test_check_diff_limit.py` and paste the first failure (`ModuleNotFoundError` is the expected reason) into the Log.
- Fixture: call `clean_env` from `tests.test_git_metrics`, `git init -q -b main`, commit `tasks/T-001-x.md` (`---\nid: T-001\ndiff_limit_lines: 10\n---\n`) and `app.py`, then `git checkout -q -b task/T-001-x`. Call `main([...,"--root", str(repo)])` and read output with `capsys`.
- Write files with `encoding="utf-8", newline="\n"`, or as bytes for the CRLF and binary cases, so line counts are the same on Windows.
- Command: `uv run python scripts/check.py`.

## Builder notes
- After this merges, every open `task/...` branch is checked when it runs `check.py`. The orchestrator merges this when no builder is mid-run (decision 0003, risk 2).
- `git show <mb>:tasks/<file>` needs the POSIX path; build it as a string, not with `Path`.
- Do not add an allowlist of excluded paths. Only the task's own file is excluded, on purpose (decision 0003).

## Log (filled in by the builder and verifier)
- Start / end: 13:08 / stopped 13:11 at 340/300 (hard stop, not trimmed)
- Failing tests before the code (first line):
- Checks run (command and real output, including the `diff limit:` line):
- Diff size: 340 (tests 189, script 150, check.py 1) vs limit 300. Stopped; human decides (fallback: split --github).
- Verifier verdict and findings:
- Human review (minutes, notes):

## Planning notes
- **People / Process / Technology:** People: the human stops waiving size overruns one by one; a red check moves the waiver to the merge decision. Process: every builder and verifier already runs `check.py`, so the limit is checked without a new step. Technology: one stdlib script, about 100 lines, read-only git.
- **Pareto:** the local `check.py` step is the 20% that does 80% of the work. CI (T-009) only closes the gap where a builder skips `check.py`.
- **Revenue / Risk / Cost:** no revenue. Risks: an in-flight branch turns red after merge (intended; merge when no builder runs); a wrong count blocks honest work (boundary tests pin `n == limit` as a pass). Cost: one session.
- **Estimate basis (`est_hours_old_way: 2`):** 45 min for the script (merge-base, `-z` numstat, untracked bytes, base-version limit), 75 min for about 25 fixture-based tests. Realistic per the T-002 calibration. Planning aid only.
- **Size basis (300):** about 100 to 120 script lines, 1 line in `check.py`, a 20-line fixture helper, and about 25 rows at about 6 lines each (parametrized, shared helpers imported) is about 270 to 290. Tight on purpose; the builder stops if it goes over.
- **Assumptions:** git >= 2.20 on all runners. Builders name branches `task/<id>-<slug>` (builder.md step 2). `clean_env`, `git` and `commit` in `tests/test_git_metrics.py` keep their names and signatures through T-007 (T-007's builder notes say so).
