# CONTEXT.md

## Purpose

Raise verified output per human hour across all my projects, and prove it with numbers. This repo holds the environment that does that (skills, agent roles, guardrails) and the measurement (task log, event log, reports). It is the versioned copy of the reference design in `AI_AGENTS_ANALYSE/work-environment-repo`, which has no git history.

## Architecture

```
skills/bootstrap/        → installs the environment into any project (/bootstrap)
.claude/agents/          → planner, builder, verifier (roles of the loop)
.claude/skills/          → plan-task, implement-task, verify-diff, release (the loop's steps here)
hooks/                   → global guardrail hook (block_dangerous_git.py), installed by scripts/install.py
tasks/                   → one file per task; _template.md is the contract
session-log/             → tasks.csv (one row per task), events.jsonl (hook events), exported sessions
scripts/                 → check.py, install.py, validate_agent_layer.py, log_event.py (hook), metrics_report.py, git_metrics.py
docs/                    → plan, baseline, decisions, readiness score, release evidence
```

## Data flow

Goal → `planner` writes `tasks/T-xxx.md` (frozen `est_hours_old_way`) → human approves → `builder`s in worktrees → `uv run python scripts/check.py` → `verifier` → PR → human merges → row in `tasks.csv`. Hooks append session events to `events.jsonl`. `metrics_report.py` joins `tasks.csv`, `events.jsonl` and git history into daily and weekly numbers.

## Glossary

| Term | Meaning |
|---|---|
| Outcome | Something a user or the business can notice. Not a commit, not lines |
| Active minutes | Human time on a task: gaps between consecutive human events, each capped at 10 min, plus timed review |
| Multiplier | `est_hours_old_way * 60 / my_active_minutes` |
| Old way | Me with autocomplete only, no agents |
| Gate | A stop where the human replies `approved` |

## Key decisions

- [0001: stack and layout](docs/decisions/0001-stack-and-layout.md): versioned copy of the reference design; stdlib runtime, uv dev tools.
- [0002: approve-to-execute](docs/decisions/0002-approve-to-execute.md): merges and guardrail changes run on the human's request, confirmed in the permission prompt.

## Current state (2026-10-16)

Bootstrap Phases 0–3 done: agent layer, cross-OS support (plan D9) and measurement are merged and public at https://github.com/YIlyaA/agent-workbench, with CI on Linux, macOS and Windows. Event logging is live. Merges and guardrail changes are approve-to-execute (decision 0002). Next: Phase 4 readiness score, then T-001 as the first measured loop.
