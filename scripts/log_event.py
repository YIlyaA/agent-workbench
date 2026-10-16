#!/usr/bin/env python3
"""Claude Code hook: append one session event to session-log/events.jsonl.

Registered for UserPromptSubmit, Stop, SubagentStop and PostToolUseFailure in .claude/settings.json.
Writes only {timestamp, session_id, event, branch}. Never the prompt text, tool input or output.
Never fails or blocks the session: every error is swallowed and the exit code is always 0.
Stdlib only; works on macOS, Linux and Windows.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

EVENTS_FILE = Path("session-log") / "events.jsonl"
GIT_TIMEOUT_S = 2


def current_branch(project: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def build_record(payload: dict, branch: str) -> dict:
    return {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "session_id": str(payload.get("session_id", "")),
        "event": str(payload.get("hook_event_name", "")),
        "branch": branch,
    }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            return 0
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
        record = build_record(payload, current_branch(project))
        target = project / EVENTS_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:  # noqa: BLE001 - a logging hook must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
