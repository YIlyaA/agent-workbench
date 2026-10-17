# 0003: The diff limit is a hard stop, checked by check.py and CI

- Date: 2026-10-17
- Status: accepted (the human approved the T-007..T-010 split, 2026-10-17)
- Value stream: Risk

## decision_summary
`diff_limit_lines` stops being builder discretion. `scripts/check_diff_limit.py` (T-008) fails `scripts/check.py` when a `task/<id>-...` branch passes its task's limit, and a `diff-limit` CI job (T-009) runs the same check on every PR. The count is insertions plus deletions against the merge-base with the base branch, including uncommitted and untracked files. Only the task's own file is excluded. A limit raised on the branch does not count; only the human raises a limit, on `main`. Lint suppressions are not banned mechanically; the verifier reviews each new one. Flow: [docs/diagrams/diff-limit-check.md](../diagrams/diff-limit-check.md).

## justification
- Every builder so far hit or passed its limit, and the text rule did not hold: builders either went over and asked for a waiver, or bent the code to fit. Both hide review load, which is what the limit exists to cap.
- **Hard stop, not a warning.** A warning is the current state. A red check means a builder cannot report green over the limit, and the waiver becomes the human's merge decision, which is visible and logged.
- **Exclude only the task's own file.** Builders may change only its `status` and Log, and an honest Log grows with every attempt (T-003 has 4). Counting it would reward short logs. Everything else counts, tests included, because review time covers tests too. Rejected: excluding tests (they were half or more of every overrun) and a path allowlist (each entry is a way around the limit).
- **Base version of the limit wins.** Otherwise a builder could raise its own limit in the same branch. Rejected: trusting the branch value.
- **Local check plus CI.** Every builder and verifier already runs `check.py`, so the local step does most of the work. The CI job closes the gap where `check.py` was skipped or the branch was pushed by hand. CI runs on one OS, because the script's own tests run on all three in the `check` job.
- **Suppressions are reviewed, not banned.** Some suppressions are legitimate (the import pattern in `historic_baseline.py`). A mechanical ban would block those and invite worse workarounds. The verifier greps added lines for `noqa`, `type: ignore`, `fmt: skip` and `fmt: off` and treats one added to fit the limit as a finding.
- PPT: People: the human decides each overrun at merge time instead of mid-session. Process: one more line in the `check.py` output; one more verifier step. Technology: one stdlib script, one CI job.

## evidence
From the task Logs on `main` (2026-10-16 to 2026-10-17):

| Task | Limit | Result |
|---|---:|---|
| T-001 | 250 | 306 lines, over; flagged to the human |
| T-002 | 350, raised to 600 | 713 lines, over; waived by the human. Post-mortem proposed "stop at the limit even after it is raised" and "about 8 lines per edge-case row" |
| T-003 | 220 | exactly 220, reached by joining a line and adding `# fmt: skip  # noqa: E501` |
| T-004 | 160 | exactly 160, after trimming tests to fit |
| T-005 | 120 | 95, under |
| T-006 | 250 | 293 to 294 lines, over; accepted by the human's merge approval |

5 of 6 tasks were over the limit or reached it by bending code or tests. The one that stayed under (T-005) had the smallest scope.

## assumptions
- Builders keep naming branches `task/<id>-<slug>` (builder.md step 2). Any other name skips the local check; the verifier and the CI skip line make that visible.
- Approved task files are on `main` before a builder starts. If a task file is new on the branch, the base-version protection cannot apply, and the script prints `limit source: branch` so the verifier sees it.
- git >= 2.20 on every runner. CI checks out with `fetch-depth: 0`; a shallow clone fails loudly instead of passing.
- Revisit if the hard stop blocks honest work more than once a week, or if the human makes `diff-limit` a required check (then a waiver needs an admin merge or a limit raised on `main`).
