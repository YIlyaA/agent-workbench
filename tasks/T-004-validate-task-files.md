---
id: T-004
status: approved # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # read-only validator; a too-strict rule would turn check.py red for every branch
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: feature            # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 160
est_hours_old_way: 1     # confirmed by the human 2026-10-17; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true
---

# Validate every task file, not only the template

## Goal
`scripts/validate_agent_layer.py` checks `tasks/_template.md` but not the real task files. A task with a missing key, a typo in `status`, or an approved task with no `est_hours_old_way` breaks the metrics silently. Make `check.py` catch these. Traces to METRICS.md "How the numbers are collected": `est_hours_old_way` is written at planning time and frozen at approval.

## Scope (paths the builder may touch)
- `scripts/validate_agent_layer.py`
- `tests/test_validate_agent_layer.py`
- this task file: `status` and the Log section only

Nothing else. Do **not** edit `session-log/tasks.csv` (the orchestrator writes the row after merge). Do **not** edit any other `tasks/T-*.md` to make it pass. If a real task file fails the new rules, stop and report: either the rule or that file is wrong, and the human decides which.

## Specification
- Add `"type"` to `REQUIRED_TASK_KEYS`, so the tuple equals the template's frontmatter keys. The template already has `type`, so the template check still passes.
- New constant `TASK_STATUSES = ("draft", "approved", "in-progress", "ready-for-review", "done", "rejected")`, the same list as the template comment.
- For each `sorted((root / "tasks").glob("T-*.md"))`, report one line per problem, prefixed with the relative path (same style as now):
  1. no frontmatter block → `no frontmatter block` (then skip the other checks for that file)
  2. each missing key in `REQUIRED_TASK_KEYS` → `missing frontmatter key '<k>'`
  3. `status` not in `TASK_STATUSES` → `status '<value>' is not one of ...`
  4. `status` is not `draft` and `est_hours_old_way` is empty → `est_hours_old_way is empty but status is '<value>'`
  5. the file name must be `<id>.md` or start with `<id>-` → otherwise `id '<id>' does not match file name`
  6. the same `id` in two files → one line naming both files
- Values are read through the existing `parse_frontmatter`, which already strips `# comments`. So `est_hours_old_way:       # set at planning time` counts as empty.
- `_template.md` is not matched by `T-*.md` and keeps its existing check.
- Every `read_text()` in the file gets `encoding="utf-8"`. The task files contain non-ASCII text (`×`, `→`), and Windows defaults to cp1252.
- Do not validate the values of `type`, `risk` or `autonomy`, and do not require `est_hours_old_way` to be numeric. That is out of scope.

## Acceptance criteria
- [ ] The rules above are implemented, and each one has a test on a `tmp_path` layer.
- [ ] `test_real_repo_agent_layer_is_valid` still passes on the real repo, which includes T-001, T-002 (`done`, values followed by long comments) and T-003 to T-006 (`draft` at planning time, then `approved` and `in-progress` while builders run).
- [ ] `minimal_layer` in the tests also writes one valid `tasks/T-001-x.md`, so every existing test runs with a task file present.
- [ ] Error messages are asserted by file name and key word, not by full path, because Windows prints `\`.
- [ ] Parametrize ids are short (at most 20 characters).
- [ ] Diff at most 160 lines. If you hit the limit, stop and report.
- [ ] `uv run python scripts/check.py` passes (it runs this validator as its last step).

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| No task files | `tasks/` holds only `_template.md` | No task errors | `test_minimal_layer_is_valid` (existing, with the T-file removed) |
| Valid draft, empty estimate | `status: draft`, `est_hours_old_way:   # comment` | Valid | `test_task_draft_empty_estimate_ok` |
| Approved, empty estimate | `status: approved`, `est_hours_old_way:` | One error naming `est_hours_old_way` | `test_task_status_needs_estimate` (param over `approved`, `done`) |
| Done with value and comment | `status: done  # draft \| approved`, `est_hours_old_way: 5     # confirmed` | Valid (comment stripped) | `test_task_done_with_comments_ok` |
| Missing key | file without `budget_usd` | `missing frontmatter key 'budget_usd'` | `test_task_missing_key` |
| Missing `type` | file without `type` | Error for `type`; the template without `type` also errors | `test_task_missing_type` |
| Unknown status | `status: in progress`, `status: Done`, `status:` (empty) | One status error each (case-sensitive, exact) | `test_task_bad_status` (ids `space`, `case`, `empty`) |
| Id does not match file | `T-007-x.md` with `id: T-008` | Error naming the file | `test_task_id_mismatch` |
| Id prefix trap | `T-0010-x.md` with `id: T-001` | Error (`T-0010-x` does not start with `T-001-`) | same test, second param |
| Id equals stem | `T-009.md` with `id: T-009` | Valid | `test_task_id_equals_stem_ok` |
| Duplicate id | `T-005-a.md` and `T-005-b.md`, both `id: T-005` | One error naming both files | `test_task_duplicate_id` |
| No frontmatter | `T-010-x.md` with body only, or no closing `---` | `no frontmatter block`, no other errors for that file | `test_task_no_frontmatter` |
| CRLF line endings | file written with `\r\n` | Valid (as with LF) | `test_task_crlf_ok` |
| Non-ASCII content | body with `×` and `→`, read as UTF-8 | Valid on every OS | covered by `test_real_repo_agent_layer_is_valid` + `test_task_crlf_ok` body |
| UTF-8 BOM | file starts with BOM | Reported as `no frontmatter block`, no crash (explicit, not silent) | n/a: no BOM files in the repo; behavior noted in code comment |
| Real repo | T-001 to T-006 as committed | No errors | `test_real_repo_agent_layer_is_valid` (existing) |
| Concurrent | parallel builders edit their own task file status | Validator is read-only; each branch is validated on its own | n/a (by design) |
| Permissions | unreadable task file | `OSError` fails check.py loudly (acceptable for files in this repo) | n/a: chmod is not portable to Windows |
| Retry / duplicate run | validate twice | Same list | n/a (pure function of the files) |

## Test plan
- Tests first: add the new task-file tests, watch them fail because no task files are checked, then implement.
- Add a `task_file(root, name, **overrides)` helper that writes a valid frontmatter from `REQUIRED_TASK_KEYS`, with `status: draft`, and applies overrides (a value of `None` drops the key). It keeps each test at 3 to 5 lines.
- Command: `uv run python scripts/check.py`.

## Builder notes
- Other builders run at the same time (T-003, T-005), and later T-006. They change only their own task file's `status`. The values they use must be in `TASK_STATUSES`. A builder that writes `status: blocked` or `status: stopped` would turn check.py red after this merges. That is intended: it is exactly the kind of drift this catches.
- Keep `validate()` returning `list[str]`, so `main()` and the existing tests do not change.

## Planning notes
- **People / Process / Technology:** People: the human stops checking frontmatter by eye at approval. Process: the frozen-estimate rule gets a mechanical check ("not draft" means an estimate exists). Technology: about 30 lines in an existing stdlib script.
- **Pareto:** required keys, the status set, and estimate-when-approved catch the drift that hurts the metrics. Value typing and cross-checks against `tasks.csv` are the long tail and left out.
- **Revenue / Risk / Cost:** no revenue. The risk is a rule that is too strict and blocks every branch. The real-repo test is the guard. Cost: one session.
- **Estimate basis (`est_hours_old_way: 1`):** 20 min of code, 30 min of tests with a helper, 10 min to check against the real files. Realistic, not generous, per the T-002 calibration.
- **Size basis (160 lines):** about 35 lines of code, about 14 tests at about 6 lines each, plus the helper.

## Log (filled in by the builder and verifier)
- Start / end:
- Checks run (command and real output):
- Verifier verdict and findings:
- Human review (minutes, notes):
