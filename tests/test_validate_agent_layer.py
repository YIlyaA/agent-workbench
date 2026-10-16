from pathlib import Path

import pytest

from scripts.validate_agent_layer import REQUIRED_TASK_KEYS, parse_frontmatter, validate

REPO = Path(__file__).resolve().parent.parent


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def minimal_layer(root: Path) -> None:
    write(
        root, ".claude/agents/builder.md", "---\nname: builder\ndescription: d\ntools: Read\nmodel: sonnet\n---\nbody\n"
    )
    write(root, ".claude/skills/plan-task/SKILL.md", "---\nname: plan-task\ndescription: d\n---\nbody\n")
    keys = "".join(f"{k}: x\n" for k in REQUIRED_TASK_KEYS)
    write(root, "tasks/_template.md", f"---\n{keys}---\n# t\n")
    write(root, "AGENTS.md", "See [context](CONTEXT.md).\n")
    write(root, "CONTEXT.md", "ctx\n")


def test_parse_frontmatter_reads_keys_and_ignores_comments() -> None:
    fm = parse_frontmatter("---\nname: a\nrisk: low   # low | high\n---\nbody")
    assert fm == {"name": "a", "risk": "low"}


def test_parse_frontmatter_without_block_is_none() -> None:
    assert parse_frontmatter("# no frontmatter") is None


def test_minimal_layer_is_valid(tmp_path: Path) -> None:
    minimal_layer(tmp_path)
    assert validate(tmp_path) == []


@pytest.mark.parametrize("missing", ["name", "description", "tools", "model"])
def test_agent_missing_required_key(tmp_path: Path, missing: str) -> None:
    minimal_layer(tmp_path)
    fields = {"name": "builder", "description": "d", "tools": "Read", "model": "sonnet"}
    del fields[missing]
    body = "".join(f"{k}: {v}\n" for k, v in fields.items())
    write(tmp_path, ".claude/agents/builder.md", f"---\n{body}---\n")
    errors = validate(tmp_path)
    assert any(missing in e and "builder.md" in e for e in errors)


def test_skill_name_must_match_folder(tmp_path: Path) -> None:
    minimal_layer(tmp_path)
    write(tmp_path, ".claude/skills/plan-task/SKILL.md", "---\nname: other\ndescription: d\n---\n")
    assert any("plan-task" in e and "name" in e for e in validate(tmp_path))


def test_task_template_missing_budget_key(tmp_path: Path) -> None:
    minimal_layer(tmp_path)
    keys = "".join(f"{k}: x\n" for k in REQUIRED_TASK_KEYS if k != "budget_usd")
    write(tmp_path, "tasks/_template.md", f"---\n{keys}---\n")
    assert any("budget_usd" in e for e in validate(tmp_path))


def test_broken_relative_link_is_reported(tmp_path: Path) -> None:
    minimal_layer(tmp_path)
    write(tmp_path, "AGENTS.md", "See [gone](docs/missing.md) and [web](https://x.y) and [anchor](#a).\n")
    errors = validate(tmp_path)
    assert len(errors) == 1 and "docs/missing.md" in errors[0]


def test_empty_root_reports_missing_files(tmp_path: Path) -> None:
    errors = validate(tmp_path)
    assert any("AGENTS.md" in e for e in errors)
    assert any("_template.md" in e for e in errors)


def test_real_repo_agent_layer_is_valid() -> None:
    assert validate(REPO) == []
