# CLAUDE.md

See [AGENTS.md](AGENTS.md). Every rule there applies to Claude Code.

Claude-only notes:
- Subagents live in `.claude/agents/` (`planner`, `builder`, `verifier`). Spawn builders with worktree isolation, at most 3 at a time.
- The verifier always runs in a fresh context, never the session that built the change.
- Guardrail files, `gh pr merge` and `install.py --apply` are `ask` rules: do them only when the human asks for that action; the permission prompt is the approval.
- Cost check after a task: `npx ccusage` (budget per task: $5, 30 min).
