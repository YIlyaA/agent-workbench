import json
from pathlib import Path
from typing import Any

import pytest

from scripts.install import HOOK_MARKER, install

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
