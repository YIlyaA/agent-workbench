from pathlib import Path

import pytest

from scripts.validate_agent_layer import REQUIRED_TASK_KEYS, TASK_STATUSES, parse_frontmatter, validate

REPO = Path(__file__).resolve().parent.parent


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def task_file(root: Path, name: str, **overrides: str | None) -> None:
    fields: dict[str, str | None] = {k: "x" for k in REQUIRED_TASK_KEYS}
    fields.update(id=name[:5], status="draft", est_hours_old_way="")
    fields.update(overrides)
    body = "".join(f"{k}: {v}\n" for k, v in fields.items() if v is not None)
    write(root, f"tasks/{name}", f"---\n{body}---\n# body \u00d7 \u2192\n")


def minimal_layer(root: Path) -> None:
    write(
        root, ".claude/agents/builder.md", "---\nname: builder\ndescription: d\ntools: Read\nmodel: sonnet\n---\nbody\n"
    )
    write(root, ".claude/skills/plan-task/SKILL.md", "---\nname: plan-task\ndescription: d\n---\nbody\n")
    keys = "".join(f"{k}: x\n" for k in REQUIRED_TASK_KEYS)
    write(root, "tasks/_template.md", f"---\n{keys}---\n# t\n")
    task_file(root, "T-001-x.md")
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


def errs(root: Path, name: str) -> list[str]:
    return [e for e in validate(root) if name in e]


def bad(root: Path, name: str, **overrides: str | None) -> list[str]:
    minimal_layer(root)
    task_file(root, name, **overrides)
    return errs(root, name)


def test_task_statuses_match_template() -> None:
    text = (REPO / "tasks/_template.md").read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if x.startswith("status:"))
    assert TASK_STATUSES == tuple(v.strip() for v in line.split("#", 1)[1].split("|"))


def test_no_task_files_is_valid(tmp_path: Path) -> None:
    minimal_layer(tmp_path)
    (tmp_path / "tasks/T-001-x.md").unlink()
    assert validate(tmp_path) == []


CASES: dict[str, tuple[str, dict[str, str | None], str, int]] = {
    "empty_id": ("T-002-x.md", {"id": "  # todo"}, "id is empty", 1),
    "lower_name": ("t-002-x.md", {"id": "t-002", "budget_usd": None}, "must start with T-", 2),
    "upper_ext": ("T-002-x.MD", {"budget_usd": None}, "budget_usd", 1),
    "approved_empty": ("T-002-x.md", {"status": "approved"}, "est_hours_old_way is empty", 1),
    "approved_absent": ("T-002-x.md", {"status": "approved", "est_hours_old_way": None}, "missing frontmatter key", 1),
    "no_budget": ("T-002-x.md", {"budget_usd": None}, "missing frontmatter key 'budget_usd'", 1),
    "no_type": ("T-002-x.md", {"type": None}, "missing frontmatter key 'type'", 1),
    "st_space": ("T-002-x.md", {"status": "in progress", "est_hours_old_way": "1"}, "status 'in progress'", 1),
    "st_case": ("T-002-x.md", {"status": "Done", "est_hours_old_way": "1"}, "status 'Done'", 1),
    "st_empty": ("T-002-x.md", {"status": "", "est_hours_old_way": "1"}, "status '' is not one of", 1),
    "id_other": ("T-007-x.md", {"id": "T-008"}, "does not match file name", 1),
    "id_prefix": ("T-0010-x.md", {"id": "T-001"}, "does not match file name", 2),
}


@pytest.mark.parametrize("case", CASES)
def test_task_file_errors(tmp_path: Path, case: str) -> None:
    name, overrides, expected, count = CASES[case]
    errors = bad(tmp_path, name, **overrides)
    assert any(expected in e for e in errors)
    assert len(errors) == count


def test_task_draft_empty_estimate_ok(tmp_path: Path) -> None:
    minimal_layer(tmp_path)
    task_file(tmp_path, "T-002-x.md", est_hours_old_way="   # comment")
    task_file(tmp_path, "T-009.md", id="T-009")
    task_file(tmp_path, "T-003-x.md", status="done  # draft | approved", est_hours_old_way="5  # confirmed")
    assert validate(tmp_path) == []


def test_task_duplicate_id(tmp_path: Path) -> None:
    minimal_layer(tmp_path)
    task_file(tmp_path, "T-005-a.md", id="T-005")
    task_file(tmp_path, "T-005-b.md", id="T-005")
    e = [x for x in validate(tmp_path) if "T-005-a.md" in x and "T-005-b.md" in x]
    assert len(e) == 1 and len(validate(tmp_path)) == 1


@pytest.mark.parametrize("text", ["just body\n", "---\nid: T-010\nstatus: draft\n"], ids=["body", "unclosed"])
def test_task_no_frontmatter(tmp_path: Path, text: str) -> None:
    minimal_layer(tmp_path)
    write(tmp_path, "tasks/T-010-x.md", text)
    e = errs(tmp_path, "T-010-x.md")
    assert len(e) == 1 and "no frontmatter block" in e[0]


def test_task_crlf_ok(tmp_path: Path) -> None:
    minimal_layer(tmp_path)
    task_file(tmp_path, "T-002-x.md")
    p = tmp_path / "tasks/T-002-x.md"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert validate(tmp_path) == []


def test_real_repo_agent_layer_is_valid() -> None:
    assert validate(REPO) == []


@pytest.mark.parametrize("rel", ["AGENTS.md", ".claude/agents/builder.md", "tasks/T-001-x.md"])
def test_non_utf8_doc_or_agent(tmp_path: Path, rel: str) -> None:
    minimal_layer(tmp_path)
    (tmp_path / rel).write_bytes(b"---\ncaf\xe9\n")
    assert any(rel in e and "not valid UTF-8" in e for e in validate(tmp_path))
