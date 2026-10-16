# CONTEXT.md

## Purpose

Raise verified output per human hour across all my projects, and prove it with numbers. This repo holds the environment that does that (skills, agent roles, guardrails) and the measurement (task log, event log, reports). It is the versioned copy of the reference design in `AI_AGENTS_ANALYSE/work-environment-repo`, which has no git history.

## Architecture

```
skills/bootstrap/        → installs the environment into any project (/bootstrap)
.claude/agents/          → planner, builder, verifier (roles of the loop)
.claude/skills/          → plan-task, implement-task, verify-diff, release (the loop's steps here)
hooks/                   → global guardrail hook (block_dangerous_git.py), installed by scripts/install.py
.claude/hooks/           → project event logger (Phase 3)
tasks/                   → one file per task; _template.md is the contract
session-log/             → tasks.csv (one row per task), events.jsonl (hook events), exported sessions
scripts/                 → validate_agent_layer.py, git_metrics.py, metrics_report.py, check.py, install.py
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

## Current state (2026-10-16)

Bootstrap Phase 2 (agent layer) with the cross-OS amendment (plan D9). Measurement (Phase 3) not built yet. Public GitHub remote not created yet. `~/.claude/skills/bootstrap` still points to the old reference folder until `scripts/install.py --apply` is run.
