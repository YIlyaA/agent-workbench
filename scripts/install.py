#!/usr/bin/env python3
"""Install the agent environment into ~/.claude on macOS, Linux or Windows.

Usage:  uv run python scripts/install.py            # dry run: print what would change
        uv run python scripts/install.py --apply    # do it

What it does:
  1. copies skills/bootstrap to ~/.claude/skills/bootstrap, plus reference files
     (DESIGN.md, METRICS.md, scripts/git_metrics.py) into its reference/ folder
  2. copies hooks/block_dangerous_git.py to ~/.claude/hooks/
  3. registers that hook in ~/.claude/settings.json (PreToolUse, matcher Bash),
     replacing the old bash version and keeping every other setting
Existing files are backed up with a .bak-<timestamp> suffix, never deleted.
Copies, not symlinks: Windows symlinks need admin or developer mode.
Stdlib only. Run by the human; agents never write to ~/.claude.
"""

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

HOOK_MARKER = "block_dangerous_git.py"
OLD_HOOK_MARKERS = ("block-dangerous-git.sh", HOOK_MARKER)
REFERENCE_FILES = ("DESIGN.md", "METRICS.md", "scripts/git_metrics.py")


def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _hook_entry(hook_path: Path) -> dict:
    # Exec form (command + args): no shell quoting, works with spaces in paths on every OS.
    return {"type": "command", "command": "uv", "args": ["run", "--no-project", "python", str(hook_path)]}


def _is_ours(handler: dict) -> bool:
    text = " ".join([str(handler.get("command", "")), *map(str, handler.get("args", []))])
    return any(m in text for m in OLD_HOOK_MARKERS)


def merge_settings(cfg: dict, hook_path: Path) -> dict:
    """Return settings with exactly one copy of our hook; everything else untouched."""
    cfg = json.loads(json.dumps(cfg))
    groups = cfg.setdefault("hooks", {}).setdefault("PreToolUse", [])
    kept = []
    for group in groups:
        handlers = [h for h in group.get("hooks", []) if not _is_ours(h)]
        if handlers:
            kept.append({**group, "hooks": handlers})
    kept.append({"matcher": "Bash", "hooks": [_hook_entry(hook_path)]})
    cfg["hooks"]["PreToolUse"] = kept
    return cfg


def _backup(path: Path, actions: list[str], apply: bool) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    if path.is_symlink():
        actions.append(f"remove symlink {path} (its target is not touched)")
        if apply:
            path.unlink()
        return
    dest = path.with_name(f"{path.name}.bak-{_stamp()}")
    actions.append(f"back up {path} -> {dest.name}")
    if apply:
        if path.is_dir():
            path.rename(dest)
        else:
            shutil.copy2(path, dest)


def install(repo: Path, home: Path, apply: bool) -> list[str]:
    claude = home / ".claude"
    settings_path = claude / "settings.json"
    actions: list[str] = []

    cfg: dict = {}
    if settings_path.exists():
        try:
            cfg = json.loads(settings_path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise SystemExit(f"{settings_path} is not valid JSON ({e}); fix it first. Nothing was changed.") from e
        if not isinstance(cfg, dict):
            raise SystemExit(f"{settings_path} must contain a JSON object. Nothing was changed.")

    skill_dst = claude / "skills" / "bootstrap"
    _backup(skill_dst, actions, apply)
    actions.append(f"copy {repo / 'skills/bootstrap'} -> {skill_dst}")
    for rel in REFERENCE_FILES:
        actions.append(f"copy {rel} -> {skill_dst / 'reference' / Path(rel).name}")
    if apply:
        shutil.copytree(repo / "skills" / "bootstrap", skill_dst)
        (skill_dst / "reference").mkdir(exist_ok=True)
        for rel in REFERENCE_FILES:
            shutil.copy2(repo / rel, skill_dst / "reference" / Path(rel).name)

    hook_dst = claude / "hooks" / HOOK_MARKER
    actions.append(f"copy hooks/{HOOK_MARKER} -> {hook_dst}")
    if apply:
        hook_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / "hooks" / HOOK_MARKER, hook_dst)

    new_cfg = merge_settings(cfg, hook_dst)
    if new_cfg != cfg:
        _backup(settings_path, actions, apply)
        actions.append(f"register PreToolUse hook in {settings_path}")
        if apply:
            settings_path.write_text(json.dumps(new_cfg, indent=2) + "\n", encoding="utf-8")
    return actions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    ap.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    a = ap.parse_args()
    repo = Path(__file__).resolve().parent.parent
    for line in install(repo, a.home, a.apply):
        print(("" if a.apply else "[dry run] ") + line)
    print("Done. Restart Claude Code to load the hook." if a.apply else "Nothing changed. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
