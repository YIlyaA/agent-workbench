import json
from pathlib import Path
from typing import Any

import pytest

from scripts.install import HOOK_MARKER, _backup_dest, install

REPO = Path(__file__).resolve().parent.parent


def settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text())


def hook_commands(cfg: dict) -> list[str]:
    out = []
    for group in cfg.get("hooks", {}).get("PreToolUse", []):
        for h in group.get("hooks", []):
            out.append(" ".join([h.get("command", ""), *h.get("args", [])]))
    return out


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    actions = install(REPO, tmp_path, apply=False)
    assert actions
    assert not (tmp_path / ".claude").exists()


def test_apply_into_empty_home(tmp_path: Path) -> None:
    install(REPO, tmp_path, apply=True)
    claude = tmp_path / ".claude"
    assert (claude / "skills" / "bootstrap" / "SKILL.md").is_file()
    assert (claude / "skills" / "bootstrap" / "reference" / "METRICS.md").is_file()
    assert (claude / "skills" / "bootstrap" / "reference" / "git_metrics.py").is_file()
    assert (claude / "hooks" / "block_dangerous_git.py").is_file()
    cmds = hook_commands(settings(tmp_path))
    assert len(cmds) == 1 and HOOK_MARKER in cmds[0]


def test_apply_is_idempotent(tmp_path: Path) -> None:
    install(REPO, tmp_path, apply=True)
    install(REPO, tmp_path, apply=True)
    assert len(hook_commands(settings(tmp_path))) == 1


def test_keeps_other_settings_replaces_old_bash_hook_and_backs_up(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    old: dict[str, Any] = {
        "model": "opus",
        "permissions": {"deny": ["Read(**/.env)"]},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "~/.claude/hooks/block-dangerous-git.sh"}],
                },
                {"matcher": "Edit", "hooks": [{"type": "command", "command": "other-hook"}]},
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "notify"}]}],
        },
    }
    (claude / "settings.json").write_text(json.dumps(old))
    install(REPO, tmp_path, apply=True)
    cfg = settings(tmp_path)
    assert cfg["model"] == "opus"
    assert cfg["permissions"] == {"deny": ["Read(**/.env)"]}
    assert cfg["hooks"]["Stop"] == old["hooks"]["Stop"]
    cmds = hook_commands(cfg)
    assert not any("block-dangerous-git.sh" in c for c in cmds)
    assert "other-hook" in cmds and sum(HOOK_MARKER in c for c in cmds) == 1
    assert list(claude.glob("settings.json.bak-*"))


def test_existing_skill_dir_is_backed_up_not_deleted(tmp_path: Path) -> None:
    skill = tmp_path / ".claude" / "skills" / "bootstrap"
    skill.mkdir(parents=True)
    (skill / "mine.md").write_text("keep me")
    install(REPO, tmp_path, apply=True)
    backups = list((tmp_path / ".claude" / "skills").glob("bootstrap.bak-*"))
    assert len(backups) == 1 and (backups[0] / "mine.md").read_text() == "keep me"


def test_existing_skill_symlink_is_replaced_without_touching_target(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "SKILL.md").write_text("original")
    link = tmp_path / ".claude" / "skills" / "bootstrap"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted on this OS/user")
    install(REPO, tmp_path, apply=True)
    assert not link.is_symlink() and (link / "SKILL.md").is_file()
    assert (target / "SKILL.md").read_text() == "original"


def test_invalid_settings_json_aborts_without_writing(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text("{ not json")
    with pytest.raises(SystemExit):
        install(REPO, tmp_path, apply=True)
    assert (claude / "settings.json").read_text() == "{ not json"
    assert not (claude / "skills").exists()


STAMP = "20261017-120000"


@pytest.fixture
def fixed_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.install._stamp", lambda: STAMP)


def test_same_second_dir_backups(tmp_path: Path, fixed_stamp: None) -> None:
    skill = tmp_path / ".claude" / "skills" / "bootstrap"
    skill.mkdir(parents=True)
    (skill / "marker").write_text("a")
    install(REPO, tmp_path, apply=True)
    (skill / "marker").write_text("b")
    install(REPO, tmp_path, apply=True)
    skills = tmp_path / ".claude" / "skills"
    assert (skills / f"bootstrap.bak-{STAMP}" / "marker").read_text() == "a"
    assert (skills / f"bootstrap.bak-{STAMP}-1" / "marker").read_text() == "b"


def test_same_second_file_backups(tmp_path: Path, fixed_stamp: None) -> None:
    path = tmp_path / ".claude" / "settings.json"
    path.parent.mkdir(parents=True)
    for value in ("a", "b"):
        path.write_text(json.dumps({"model": value}))
        install(REPO, tmp_path, apply=True)
    assert json.loads((path.parent / f"settings.json.bak-{STAMP}").read_text()) == {"model": "a"}
    assert json.loads((path.parent / f"settings.json.bak-{STAMP}-1").read_text()) == {"model": "b"}


@pytest.mark.parametrize(
    ("taken", "kind", "want"),
    [
        ([], "file", "x.bak-S"),
        (["x.bak-S"], "file", "x.bak-S-1"),
        (["x.bak-S", "x.bak-S-1"], "file", "x.bak-S-2"),
        (["x.bak-S", "x.bak-S-2"], "file", "x.bak-S-1"),
        (["x.bak-S"], "dir", "x.bak-S-1"),
    ],
    ids=["free", "one", "two", "gap", "other-kind"],
)
def test_backup_dest_counts_up(tmp_path: Path, taken: list[str], kind: str, want: str) -> None:
    for name in taken:
        if kind == "dir":
            (tmp_path / name).mkdir()
        else:
            (tmp_path / name).write_text("")
    assert _backup_dest(tmp_path / "x", "S").name == want


def test_backup_dest_dangling_symlink(tmp_path: Path) -> None:
    try:
        (tmp_path / "x.bak-S").symlink_to(tmp_path / "missing")
    except OSError:
        pytest.skip("symlinks not permitted on this OS/user")
    assert _backup_dest(tmp_path / "x", "S").name == "x.bak-S-1"


def test_dry_run_names_free_backup(tmp_path: Path, fixed_stamp: None) -> None:
    skills = tmp_path / ".claude" / "skills"
    (skills / "bootstrap").mkdir(parents=True)
    (skills / f"bootstrap.bak-{STAMP}").mkdir()
    actions = install(REPO, tmp_path, apply=False)
    assert any(a.endswith(f"-> bootstrap.bak-{STAMP}-1") for a in actions)
    assert sorted(p.name for p in skills.iterdir()) == ["bootstrap", f"bootstrap.bak-{STAMP}"]
