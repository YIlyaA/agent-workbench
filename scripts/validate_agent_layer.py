#!/usr/bin/env python3
"""Validate the agent layer: agent and skill frontmatter, task template keys, relative links.

Usage:  uv run python scripts/validate_agent_layer.py [repo_root]
Exit 0 when valid, 1 with one line per problem otherwise. Stdlib only, read-only.
"""

import re
import sys
from pathlib import Path

REQUIRED_AGENT_KEYS = ("name", "description", "tools", "model")
REQUIRED_SKILL_KEYS = ("name", "description")
REQUIRED_TASK_KEYS = (
    "id",
    "status",
    "risk",
    "autonomy",
    "diff_limit_lines",
    "est_hours_old_way",
    "budget_minutes",
    "budget_usd",
    "blocked_by",
    "parallel_ok",
)
LINKED_DOCS = ("AGENTS.md", "CLAUDE.md", "CONTEXT.md", "README.md")
LINK = re.compile(r"\]\(([^)\s]+)\)")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return the `key: value` pairs of a leading `---` block, or None if there is none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fm: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            fm[key.strip()] = value.split("#", 1)[0].strip()
    return None


def _check_keys(path: Path, root: Path, required: tuple[str, ...]) -> list[str]:
    rel = path.relative_to(root)
    fm = parse_frontmatter(path.read_text())
    if fm is None:
        return [f"{rel}: no frontmatter block"]
    return [f"{rel}: missing frontmatter key '{k}'" for k in required if k not in fm]


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    for agent in sorted((root / ".claude/agents").glob("*.md")):
        errors += _check_keys(agent, root, REQUIRED_AGENT_KEYS)

    for skill in sorted((root / ".claude/skills").glob("*/SKILL.md")):
        errors += _check_keys(skill, root, REQUIRED_SKILL_KEYS)
        fm = parse_frontmatter(skill.read_text()) or {}
        if fm.get("name") and fm["name"] != skill.parent.name:
            errors.append(f"{skill.relative_to(root)}: name '{fm['name']}' does not match folder '{skill.parent.name}'")

    template = root / "tasks/_template.md"
    if template.exists():
        errors += _check_keys(template, root, REQUIRED_TASK_KEYS)
    else:
        errors.append("tasks/_template.md: missing")

    if not (root / "AGENTS.md").exists():
        errors.append("AGENTS.md: missing")
    for doc in LINKED_DOCS:
        path = root / doc
        if not path.exists():
            continue
        for target in LINK.findall(path.read_text()):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if not (path.parent / target.split("#", 1)[0]).exists():
                errors.append(f"{doc}: broken link '{target}'")
    return errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    errors = validate(root)
    for e in errors:
        print(e)
    print(f"agent layer: {'OK' if not errors else f'{len(errors)} problem(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
