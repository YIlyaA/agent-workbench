---
name: plan-task
description: Turn a goal for Agents Workbench into one or more task files in tasks/ with a frozen est_hours_old_way, then stop for approval. Use when the user states a goal, feature, fix or research question for this repo.
when-to-use: Start of any change to scripts, skills, agents, docs or metrics in Agents Workbench.
---

# Plan Task Skill

## Purpose
Every change starts as a small, checkable task file. The estimate is frozen before work begins, so the speed multiplier can be trusted.

## Agent Instructions

### Step 1: Delegate to the planner
Spawn the `planner` agent with the goal. It reads `CONTEXT.md` → `AGENTS.md` → only the files the goal touches.

### Step 2: Check the task files
For each `tasks/T-<nnn>-*.md`, confirm:
- the scope lists exact paths, with none under `.claude/settings.json`, `.claude/hooks/`, `~/.claude/` or other repos (guardrail paths are L2: allowed only when the human asked for that change)
- the acceptance criteria include `uv run python scripts/check.py` passing
- the edge-case table has a test per row
- `est_hours_old_way` is filled, and `budget_minutes`/`budget_usd` are within 30 min / $5
- `blocked_by` and `parallel_ok` are set; no more than 3 tasks are parallel at once
- `diff_limit_lines` fits the sizing rule (about 8 lines per edge-case row, about 30 per new fixture helper, plus the code); over 300 means split

Run `uv run python scripts/validate_agent_layer.py` (it checks the template contract).

### Step 3: Stop at the gate
Show the task list, dependency order and estimates. Wait for the human to set `status: approved` (or say `approved`). Do not start building.

## Expected Output
A table: `| id | title | est_hours_old_way | parallel_ok | blocked_by | risk |`, then open questions.

## Guardrails
- A plan never authorizes implementation.
- Never edit `est_hours_old_way` after approval.
