---
id: T-009
status: done          # draft | approved | in-progress | ready-for-review | done | rejected
risk: medium             # edits .github/workflows/ci.yml, an `ask` guardrail path (decision 0002)
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: docs               # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 80     # task file not counted; enforced on this branch by T-008's check
est_hours_old_way: 0.75     # confirmed by the human 2026-10-17; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: [T-008]
parallel_ok: true        # disjoint from T-010 (docs/baseline.md only)
---

# Hard diff limit: CI job and rule text

## Goal
Part C2 of the split approved by the human on 2026-10-17 ("approve T-007..T-010"). T-008 made the diff limit a hard stop in `check.py`. This task (1) adds a CI job so a PR from a `task/` branch is checked even if the builder skipped `check.py`, and (2) writes the rule into the files agents read. It also rewords the AGENTS.md "Do not touch" line about `scripts/git_metrics.py`, which stops being accurate after T-007 (decision [0003](../docs/decisions/0003-diff-limit-hard-stop.md), note in decision 0001).

## Scope (paths the builder may touch)
- `.github/workflows/ci.yml` (an `ask` path: see "Guardrail path" below)
- `AGENTS.md`
- `CONTEXT.md`
- `.claude/agents/builder.md`
- `.claude/agents/planner.md`
- `.claude/skills/plan-task/SKILL.md`
- `.claude/skills/verify-diff/SKILL.md`
- `tasks/_template.md`
- this task file: `status` and the Log section only

Nothing else. Do **not** edit `session-log/tasks.csv` (the orchestrator writes the row after merge), `scripts/`, `tests/`, `pyproject.toml`, `docs/` or `.claude/settings.json`. Only the lines named below change; do not reflow paragraphs.

## Guardrail path
`.github/workflows/**` is under `ask` in `.claude/settings.json`. The human's approval of this task is the request for this one change (decision 0002); Claude Code's permission prompt still confirms it. Use the Edit tool only. **Never write `ci.yml` through Bash, Python or any other tool that skips the prompt.** If the edit is denied or no prompt can be shown to you, stop and report: the orchestrator then applies the exact YAML below in the main session.

## Specification
1. **`.github/workflows/ci.yml`:** add a second job after `check`. Leave `on:`, `permissions:` and the `check` job unchanged.
   ```yaml
     diff-limit:
       if: github.event_name == 'pull_request'
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
           with:
             fetch-depth: 0
         - uses: astral-sh/setup-uv@v6
         - run: uv run python scripts/check_diff_limit.py --github
   ```
   One OS is enough: the script's tests run on all three in `check`. No `${{ ... }}` inside `run:`; the script reads `GITHUB_HEAD_REF` and `GITHUB_BASE_REF` from env. Never `pull_request_target`. Making the job a required check is a GitHub setting for the human, not this task.
2. **`AGENTS.md`** (exact text in the quote blocks; keep the file's existing Markdown style):
   - Workflow step 5 becomes:
     > 5. Stay inside the budget (`budget_minutes`, `budget_usd`). The diff limit is a hard stop: `scripts/check_diff_limit.py` fails `check.py` and CI when a `task/` branch passes `diff_limit_lines` (task file not counted). Over the limit, stop and report. Never trim tests, join lines or add lint suppressions to fit. Only the human raises a limit, on `main`.
   - Commands table: add a row after "Agent layer contracts":
     > | Diff limit for the current task branch | `uv run python scripts/check_diff_limit.py` |
   - "Do not touch": replace the `scripts/git_metrics.py` line ("copied unchanged from the reference design") with:
     > - `scripts/git_metrics.py`: derived from the reference design, with bug fixes from T-007 (decision 0001). It computes headline number 1, so changes need a task.
3. **`CONTEXT.md`:**
   - Architecture `scripts/` line: add `check_diff_limit.py` after `check.py`.
   - Key decisions: add
     > - [0003: diff limit is a hard stop](docs/decisions/0003-diff-limit-hard-stop.md): checked by check.py and CI; only the task file is excluded; only the human raises a limit.
4. **`.claude/agents/builder.md`** step 7 becomes:
   > 7. The diff limit is a hard stop: `check.py` fails when the branch passes `diff_limit_lines`. Then stop and report; never trim tests, join lines or add lint suppressions to fit. Stop and report too when you hit `budget_minutes`.
5. **`.claude/agents/planner.md`** step 4, append:
   > Size tests at about 8 lines per edge-case row with a real fixture, plus about 30 for a new fixture helper, plus the code. Split when the total is over 300.
6. **`.claude/skills/plan-task/SKILL.md`** Step 2: add a bullet:
   > - `diff_limit_lines` fits the sizing rule (about 8 lines per edge-case row, about 30 per new fixture helper, plus the code); over 300 means split
7. **`.claude/skills/verify-diff/SKILL.md`:** add `### Step 2c: Size and suppressions` before Step 3, with three bullets: the `diff limit:` line in the check output is under the limit; grep the added lines for `noqa|type: ignore|fmt: skip|fmt: off` and judge each one (a suppression added to fit the limit is a finding); the task file changed only in `status` and the Log (it is excluded from the count, so the verifier checks it).
8. **`tasks/_template.md`:** the `diff_limit_lines` line becomes:
   > diff_limit_lines: 300    # hard stop (scripts/check_diff_limit.py); task file not counted

   Nothing else changes; the `status:` line must stay byte-identical.

## Acceptance criteria
- [ ] Every edge-case row below has a check, or is n/a with a reason.
- [ ] The `check` job and the workflow's `on:` and `permissions:` blocks are unchanged (`git diff` shows only added lines in `ci.yml`).
- [ ] `ci.yml` contains no `${{` on a `run:` line and no `pull_request_target`.
- [ ] `uv run python scripts/validate_agent_layer.py` prints `agent layer: OK` (the CONTEXT.md link to 0003 resolves; template keys parse).
- [ ] `uv run python scripts/check.py` locally prints a `diff limit: n/80` line for this branch. Paste it into the Log.
- [ ] On this task's PR, the `diff-limit` job runs and is green. Paste its last line into the Log.
- [ ] Diff at most 80 lines (insertions plus deletions against the merge-base with `main`, not counting this task file). **If you reach the limit, stop and report. Do not shorten the rule text to fit.**
- [ ] `uv run python scripts/check.py` passes on CI (Linux, macOS, Windows).

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| Template comment parses | `diff_limit_lines: 300    # hard stop ...` | `parse_frontmatter` strips the comment; template still has every key | `test_real_repo_agent_layer_is_valid` (existing) |
| Template status line | unchanged `status:` line | Status list still matches `TASK_STATUSES` | `test_task_statuses_match_template` (existing) |
| New CONTEXT.md link | link to `docs/decisions/0003-diff-limit-hard-stop.md` | Link check passes (the file is on `main` before this branch) | `test_real_repo_agent_layer_is_valid` (existing) |
| PR from a task branch, under limit | this task's own PR, limit 80 | `diff-limit` job green, prints `diff limit: n/80` | this PR's CI run (Log) |
| PR from a task branch, over limit | branch over `diff_limit_lines` | Job red with the top files | T-008 `test_github_mode` + `test_limit_boundary` |
| PR from a non-task branch | e.g. `docs/x`, a Dependabot branch | Job green with a visible `skip` line | T-008 `test_skip_non_task`; first such PR (Log note, n/a here) |
| Push to `main` | merge commit pushed | `diff-limit` job does not run (`if:`); `check` still runs | Actions run of this task's merge (orchestrator notes it in the Log) |
| PR to a base other than `main` | base `release` | Uses `origin/release` | T-008 `test_github_mode` (env-driven base) |
| Shallow checkout | `fetch-depth: 0` removed by mistake | Job red with a `fetch-depth` message, never a silent pass | T-008 `test_no_merge_base`; verifier reads the YAML |
| Hostile fork branch name | head ref `task/T-1-$(id)` | Read from env by Python, never by the shell | T-008 `test_github_mode` (id `meta`); verifier greps `run:` lines for `${{` |
| Fork PR permissions | PR from a fork | Read-only token (`permissions: contents: read`), no secrets, no `pull_request_target` | verifier reads the YAML |
| Limit raised in the PR | PR edits its own `diff_limit_lines` upward | Base value used; job red if over it | T-008 `test_raised_limit_ignored` |
| Guardrail edit denied | permission prompt rejected or not shown | Builder stops and reports; orchestrator applies spec item 1 in the main session | process (Log) |
| Concurrent | up to 3 open task PRs | Each run is independent and read-only | n/a (by design) |
| Retry | job re-run | Same result | n/a (deterministic; T-008 retry test) |
| Cross-OS | job runs on `ubuntu-latest` only | The script itself is tested on all three OSes by `check` | existing `check` matrix |

## Test plan
- No new code or tests. Run `uv run python scripts/validate_agent_layer.py` and `uv run python scripts/check.py`; paste both outputs into the Log.
- After the PR opens, paste the `diff-limit` job's final line into the Log.
- Command: `uv run python scripts/check.py`.

## Log (filled in by the builder and verifier)
- Start / end: 2026-10-17 13:32 to ~13:38 CEST (stacked on origin/task/T-008-diff-limit-check)
- Guardrail edit (prompt shown and accepted, or applied by the orchestrator): ci.yml edited with the Edit tool; accepted, no denial.
- Checks run (command and real output, including the `diff limit:` line): validate_agent_layer: `agent layer: OK`. check.py: 352 passed, 3 xfailed; `diff limit: 452/80 lines` FAILED as expected on the stacked branch (it counts T-008's 407 plus T-009 vs main merge-base); resolves after #22 merges.
- CI `diff-limit` job result on the PR:
- Diff size (insertions + deletions vs merge-base, task file excluded): vs T-008 branch, 23 insertions + 5 deletions outside tasks/, plus 1+1 in tasks/_template.md = 30 (limit 80).
- Verifier verdict and findings:
- Human review (minutes, notes):

## Planning notes
- **People / Process / Technology:** People: the human approves one guardrail edit in a prompt. Process: the rule moves from "stop if you notice" to "the check stops you"; the verifier gets an explicit suppression check. Technology: one 10-line CI job, text in 7 files.
- **Pareto:** the AGENTS.md and builder.md lines carry most of the value, because builders read them. The CI job only closes the "skipped check.py" gap.
- **Revenue / Risk / Cost:** no revenue. Risks: a guardrail path (prompt required); a required-check setting later would need an admin merge or a limit raise on `main` to waive an overrun (decision 0003). Cost: one short session.
- **Estimate basis (`est_hours_old_way: 0.75`):** 15 min of YAML and checking the GitHub env vars, 30 min of rule text in 7 files. Planning aid only.
- **Size basis (80):** about 10 YAML lines, 6 in AGENTS.md, 3 in CONTEXT.md, 2 each in builder.md and planner.md, 2 in plan-task, about 6 in verify-diff, 2 in the template: about 35 insertions plus deletions, so 80 leaves room for wording.
- **Assumptions:** T-008 is merged, so this branch is checked by its own rule. Decision 0003 is on `main` before this branch starts (it is committed with the task files). `GITHUB_HEAD_REF` and `GITHUB_BASE_REF` are set for `pull_request` events (GitHub docs, default env vars).
- Release (2026-10-17): PR #23 squash-merged. Final verdict: PASS, 0 findings; the new diff-limit CI job passed on its own PR. review_findings 0. Diff 30/80. my_active_minutes 0: the human did not review line by line; the orchestrator merged on the human's 'finish what's open' instruction after green CI on 3 OSes.
