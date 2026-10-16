---
name: release
description: Open the PR for a verified task branch, and after the human merges it, log the tasks.csv row, run the metrics report and update release evidence. Use when a task's verifier verdict is PASS.
when-to-use: A verified branch is ready to go to main. There is no deploy target; a merge to main is the release.
disable-model-invocation: true
---

# Release Skill

## Purpose
Close the loop so every merged task is measured. No log, no credit.

## Agent Instructions

### Step 1: Open the PR
Push the task branch (never `main`): `git push -u origin task/<id>-<slug>`. Then `gh pr create --base main --title "<id>: <title>" --body-file <tmp>`. The body has the goal, acceptance criteria checked off, the check output and the verifier verdict.

### Step 2: Merge on request
Ask the human to review the PR and report their review minutes. Merge only when they ask for it: `gh pr merge <n> --squash --delete-branch` (an `ask` rule, so they confirm in the permission prompt). Never merge with failing CI.

### Step 3: Log the task
After the merge, propose one row for `session-log/tasks.csv`:
`id,date,type,method,est_hours_old_way,my_active_minutes,agent_runtime_minutes,start,end,tests_green,review_findings,rolled_back,outcome`
- `est_hours_old_way` is copied from the task file, unchanged.
- `my_active_minutes` comes from `scripts/metrics_report.py` (event gaps capped at 10 min) plus the review minutes.
- `tests_green` is `yes` only if the first verifier run passed.
The human confirms the row; then append it. Set the task to `status: done`.

### Step 4: Report and evidence
Run `uv run python scripts/metrics_report.py` and show the real output. Add one line to `docs/release-evidence.md` (date, claim, command, output excerpt).

## Expected Output
PR URL, the confirmed CSV row, and the report excerpt.

## Guardrails
- Merge only on the human's request and only with green CI. Never push directly to `main`, never force push.
- Never edit an existing `tasks.csv` row; corrections are a new note in the task file.
