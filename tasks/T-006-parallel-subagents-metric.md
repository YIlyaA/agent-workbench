---
id: T-006
status: ready-for-review # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # read-only on ~/.claude/projects transcripts; prints counts and times only
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: metrics            # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 250
est_hours_old_way: 2     # confirmed by the human 2026-10-17; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true        # disjoint files; the orchestrator runs it 4th because of the 3-builder RAM cap
---

# Metrics report: max concurrent subagents (and builders)

## Goal
"Max parallel sessions" counts top-level Claude Code sessions only. The leverage claim in METRICS.md ("I can run N agent tasks in parallel and still review them all") needs the number of subagents (builders, verifiers) that actually worked at the same time. Report it next to "max parallel sessions", with idle gaps removed so that resumed agents do not inflate the number.

## Scope (paths the builder may touch)
- `scripts/metrics_report.py`
- `tests/test_metrics_report.py`
- this task file: `status` and the Log section only

Nothing else. Do **not** edit `session-log/tasks.csv` (the orchestrator writes the row after merge). Do not read the real `~/.claude/projects` in tests. Tests use `tmp_path` fixtures only. Running the finished report once by hand is fine, but paste only the two new output lines into the Log.

## Facts (orchestrator-verified, 2026-10-17)
- Subagent transcripts: `<projects>/<slug>/<session-id>/subagents/agent-<id>.jsonl`. Each line is a JSON record. Records that carry an ISO `timestamp` are the ones that count.
- Beside it: `agent-<id>.meta.json` with `agentType` (`builder`, `verifier`, `planner`, ...), `description`, `worktreeBranch`, `spawnedWithWorktree`.
- Slug: the absolute project path with every non-alphanumeric character replaced by `-`. Example: `/Users/me/Documents/PROGRAMMING/ENV_AGENTS` gives `-Users-me-Documents-PROGRAMMING-ENV-AGENTS`. The underscore is replaced too, as this session's scratchpad path shows.
- Resumed agents have long idle gaps. One builder spans 11:47 to 12:31 with stops and resumes in between. So first-to-last overstates concurrency.

## Specification
- Constants, listed in the module docstring:
  - `SUBAGENT_IDLE_GAP_MIN = 5`: a gap **greater than** this starts a new active interval. A gap of exactly 5 min stays in the same interval.
  - `CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"`
- `project_slug(path: str) -> str`: `re.sub(r"[^A-Za-z0-9]", "-", path)`. It is pure, takes a string and does not resolve, so tests can pass POSIX and Windows paths on any OS.
- `load_subagents(project_dir: Path) -> list[tuple[str, list[datetime]]]` returns `(agent_type, timestamps)`:
  - It globs `project_dir / "*" / "subagents" / "agent-*.jsonl"`. If `project_dir` is missing or is not a directory, it returns `[]`.
  - Each line is parsed with `json.loads`. The `timestamp` goes through `datetime.fromisoformat(...).astimezone()`. Skip a line on `ValueError`, `KeyError`, `TypeError` or `AttributeError`, as `load_events` does. Read files with `encoding="utf-8", errors="replace"`. On `OSError`, skip the whole file.
  - `agent_type` comes from the sibling `agent-<id>.meta.json` key `agentType`. If the meta file is missing, corrupt, not an object, or the value is not a string, use `"unknown"`.
  - An agent with no valid timestamps is dropped.
  - Never keep `description`, `worktreeBranch` or any record content in memory past parsing.
- `active_intervals(times: list[datetime], gap_min: float = SUBAGENT_IDLE_GAP_MIN) -> list[tuple[datetime, datetime]]`: sort and split. A single timestamp gives a zero-length interval.
- Window: refactor the sweep into `max_overlap(spans) -> tuple[int, datetime | None, datetime | None]`, which returns the max and the window `[from, to]` from the instant the max is first reached to the next point where the count changes. `max_parallel_sessions(spans)` becomes `max_overlap(spans)[0]`, so its existing tests and its touching and zero-length rules stay exactly as they are.
- `subagent_concurrency(agents) -> dict`: builds spans keyed `f"{i}#{j}"` (agent index, interval index) and returns `{"max": n, "window": (a, b), "builders_max": m, "builders_window": (c, d)}`. Builders are `agent_type == "builder"`.
- `report(tasks, events, repo, subagents=None)`: right after the `max parallel sessions` line, add:
  - `max concurrent subagents: N (YYYY-MM-DD HH:MM-HH:MM)` and `max concurrent builders: M (...)`, in local time. If the window crosses midnight, print the end date too.
  - `n/a` for both when `subagents` is `None` or empty. Never crash.
  - Print only counts, agent types and times. Never print descriptions, branches, ids, file paths or content.
- CLI: `--transcripts DIR`, default `CLAUDE_PROJECTS / project_slug(str(ROOT))`. The `--active` path is unchanged.

## Acceptance criteria
- [ ] The two new lines appear in the report, and `n/a` appears when the directory is missing.
- [ ] Every edge-case row below has a test on a `tmp_path` fixture or a pure function, or is n/a with a reason.
- [ ] All existing tests in `tests/test_metrics_report.py` pass unchanged.
- [ ] A test asserts that `report(...)` output contains neither `SECRET-DESC` (meta `description`) nor `SECRET-BODY` (record content) nor `secret-branch` (`worktreeBranch`).
- [ ] Stdlib only. `pathlib` everywhere. No `/` assumptions except inside `project_slug` test inputs.
- [ ] Parametrize ids are short (at most 20 characters).
- [ ] Diff at most 250 lines. If you hit the limit, stop and report.
- [ ] `uv run python scripts/check.py` passes.

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| Missing directory | `--transcripts` points to a path that does not exist | `load_subagents` returns `[]`; report prints `n/a` twice | `test_subagents_missing_dir` |
| Path is a file | `project_dir` is a regular file | `[]`, no crash | same test, second param |
| Empty directory | dir exists, no `*/subagents/` | `[]`, `n/a` | `test_subagents_empty_dir` |
| Corrupt lines | `not json`, `[]`, `{"timestamp": 5}`, `{"timestamp": "yesterday"}`, `{}` among 2 valid lines | Only the 2 valid timestamps are kept | `test_subagents_corrupt_lines` |
| No valid timestamps | jsonl with only corrupt lines; also an empty file | Agent dropped | same test, extra file |
| Meta missing or corrupt | no `.meta.json`; `{bad`; `[]`; `{"agentType": 3}` | `agent_type == "unknown"` | `test_subagents_meta_fallback` (ids `none`, `bad`, `list`, `int`) |
| Idle gap split | one builder at 11:47, 11:50, then every 4 min from 12:20 to 12:31 | Intervals `[11:47,11:50]`, `[12:20,12:31]` (gap 11:50 to 12:20 is over 5 min) | `test_active_intervals_split` (pure) |
| Gap exactly 5 min / just over | 10:00, 10:05, 10:10:01 | `[10:00,10:05]`, `[10:10:01,10:10:01]` | `test_active_intervals_boundary` (pure) |
| Resume does not inflate | builder A as above; builder B active 12:00 to 12:10 only (in A's idle gap) | `builders_max == 1`, not 2 | `test_resume_gap_not_counted` |
| Three builders overlap | A, B, C active 10:00 to 10:20, 10:05 to 10:25, 10:10 to 10:30 (records at most 5 min apart, so each is one interval); one verifier 10:12 to 10:14 | `max == 4` window 10:12-10:14; `builders_max == 3` window 10:10-10:20 | `test_concurrency_window` |
| Touching intervals | A ends 10:10, B starts 10:10 | `max == 1` (reuses the sweep rule) | `test_concurrency_touching` |
| Single-record agent | one timestamp only | Counted as 1 at that instant (zero-length rule) | covered by the boundary test plus `max_overlap` on one zero span |
| Time zones | records in `Z` and `+02:00` for the same instant | Treated as the same instant; overlap correct | `test_subagents_mixed_offsets` |
| Naive timestamp | `2026-10-16T10:00:00` (no offset) | Read as local time via `.astimezone()`; no naive-vs-aware `TypeError` | same test, extra line |
| Day boundary | intervals from 23:58 to 00:03 the next day | One interval; window prints both dates | `test_window_crosses_midnight` |
| Privacy | meta `description: SECRET-DESC`, `worktreeBranch: secret-branch`, record `{"timestamp":..., "message": "SECRET-BODY"}` | None of them appears in the report | `test_report_prints_no_content` |
| Slug | `/Users/a/ENV_AGENTS`, `C:\Users\a\my proj` | `-Users-a-ENV-AGENTS`, `C--Users-a-my-proj` | `test_project_slug` (ids `posix`, `win`) |
| Default dir | no `--transcripts` | `CLAUDE_PROJECTS / project_slug(str(ROOT))` | `test_default_transcripts_dir` (assert the constructed path, not its existence) |
| `max_parallel_sessions` unchanged | existing spans tests | Same results | existing tests |
| Unreadable file | `OSError` on open (monkeypatched `Path.read_text` or `open` for one file) | That file is skipped, the others count | `test_subagents_unreadable_file` |
| Maximal | a transcript of 10,000 lines | One pass per file; sort once per agent | n/a (by design; the verifier checks for loops nested over all timestamps) |
| Concurrent | Claude Code appends to a transcript while the report reads it | A half-written last line is a corrupt line and is skipped | covered by `test_subagents_corrupt_lines` |
| Retry / duplicate | run the report twice | Same lines | n/a (pure function of the files) |

## Test plan
- Tests first: pure functions (`project_slug`, `active_intervals`, `max_overlap`), then the fixture loader, then `report`.
- Fixture helper `agent(dir, session, agent_id, agent_type, stamps, meta=..., extra_lines=...)` writes `dir/<session>/subagents/agent-<id>.jsonl` and `.meta.json` with `encoding="utf-8"`. Build times with the existing `t(h, m)` helper and `.isoformat()`.
- Call `report(...)` directly with `tasks=[]`, `events=[]` and `repo=tmp_path` (a non-repo path; `main_commits_per_week` already returns `{}`).
- Command: `uv run python scripts/check.py`.

## Builder notes
- Parse only `timestamp` from each record. Do not build objects that hold content.
- When the orchestrator runs this from a worktree, the default slug is the worktree path, not the main repo, so the result is `n/a`. That is expected; pass `--transcripts` explicitly in that case. Do not add git calls to find the main worktree; that is out of scope.
- Keep the window format short and ASCII (use `-`, not an en dash). The Windows console can be cp1252.

## Planning notes
- **People / Process / Technology:** People: the human sees whether the 3-builder cap is actually used. Process: makes the leverage claim checkable from data that already exists. Technology: a read-only loader for an undocumented, internal transcript format, so failures degrade to `n/a`.
- **Pareto:** max overlap with idle-gap splitting plus a builders-only count answers "did I run 3 in parallel". Per-day series, agent runtime minutes and charts are left for later.
- **Revenue / Risk / Cost:** no revenue. Risks: the transcript format can change without notice (mitigated by `n/a` and skipping); the gap constant is a judgment call (5 min, named, easy to tune); privacy (only counts and times are printed). Cost: one session.
- **Estimate basis (`est_hours_old_way: 2`):** 30 min to look at the transcript layout and slug rule, 40 min for the code (loader, intervals, sweep refactor, CLI), 50 min for fixture tests. Realistic, not generous, per the T-002 calibration.
- **Size basis (250 lines):** about 80 lines of code, about 18 tests at about 8 lines each with a shared fixture helper.

## Log (filled in by the builder and verifier)
- Start / end: 2026-10-17 10:07 - 10:10 CEST (builder). Attempt 2 (verifier nits: OverflowError, zero builders prints 0, builder spans by type, merged tests, spec example fixed). Diff vs 2cdb273: 293 changed lines (280 insertions, 13 deletions) vs limit 250; tests 179+ of them. Over the limit, goes to the human. Attempt 3 (CI timezone): test_window_crosses_midnight now builds its fixture in local time; tests pass under TZ=UTC, America/Los_Angeles, Europe/Berlin.
- Checks run (command and real output): `uv run python scripts/check.py` -> ruff check OK, ruff format OK, mypy OK, 263 passed, agent layer OK, ALL CHECKS PASSED. Real run: `max concurrent subagents: 5 (2026-10-17 10:07-10:08)`, `max concurrent builders: 3 (2026-10-17 10:06-10:07)`
- Verifier verdict and findings:
- Human review (minutes, notes):
