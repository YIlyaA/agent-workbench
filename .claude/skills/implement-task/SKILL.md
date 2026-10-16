---
name: implement-task
description: Run approved task files through builder agents in isolated worktrees, up to 3 in parallel, test-first. Use when one or more tasks in tasks/ have status approved.
when-to-use: After plan-task, once the human approved the tasks.
---

# Implement Task Skill

## Purpose
Turn approved tasks into verified branches as fast as possible without agents stepping on each other.

## Agent Instructions

### Step 1: Pick runnable tasks
List `tasks/T-*.md` with `status: approved` whose `blocked_by` tasks are all `done`. Take at most 3 with `parallel_ok: true`; a task with `parallel_ok: false` runs alone.

### Step 2: Start builders
Set each picked task to `status: in-progress` and record the start time. Spawn one `builder` agent per task in the same message, so they run concurrently (each gets its own worktree from `isolation: worktree`). Pass only the task file path.

### Step 3: Collect results
For each builder: check it reports `uv run python scripts/check.py` output ending in `ALL CHECKS PASSED`. If not, or if it stopped on budget or diff limit, mark the task `in-progress` with the blocker noted and report it. Do not retry silently.

### Step 4: Hand off to verification
For each green branch, run the `verify-diff` skill.

## Expected Output
`| id | branch | checks | minutes | stopped early? |`, then what goes to verification.

## Guardrails
- Only `approved` tasks. Max 3 parallel builders (8 GB RAM).
- Builders never merge, never push to `main`, never touch guardrail files.
