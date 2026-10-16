# Project bootstrap prompt

The canonical version is now the skill in [`skills/bootstrap/`](../skills/bootstrap/SKILL.md). `~/.claude/skills/bootstrap` is a symlink to it, so there is one source of truth.

- **In Claude Code:** run `/bootstrap` as the first message in a new project.
- **In another tool** (Codex, Cursor, Antigravity): paste the body of `skills/bootstrap/SKILL.md` (everything after the frontmatter) as the first message, and give the agent the path to `skills/bootstrap/` so it can read `references/` and `templates/`.
