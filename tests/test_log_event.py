import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.log_event import EVENTS_FILE, build_record

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "log_event.py"


def run(stdin: str, project: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=stdin, env=env, capture_output=True, text=True, check=False
    )


def lines(project: Path) -> list[dict]:
    return [json.loads(x) for x in (project / EVENTS_FILE).read_text(encoding="utf-8").splitlines()]


def test_record_has_exactly_the_allowed_keys() -> None:
    rec = build_record({"session_id": "s1", "hook_event_name": "Stop", "prompt": "secret"}, branch="main")
    assert set(rec) == {"timestamp", "session_id", "event", "branch"}
    assert rec["session_id"] == "s1" and rec["event"] == "Stop" and rec["branch"] == "main"


def test_prompt_text_is_never_written(tmp_path: Path) -> None:
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "my password is hunter2"}
    assert run(json.dumps(payload), tmp_path).returncode == 0
    raw = (tmp_path / EVENTS_FILE).read_text(encoding="utf-8")
    assert "hunter2" not in raw and 'prompt"' not in raw
    assert lines(tmp_path)[0]["event"] == "UserPromptSubmit"


def test_appends_one_line_per_call(tmp_path: Path) -> None:
    for ev in ("UserPromptSubmit", "Stop", "PostToolUseFailure"):
        run(json.dumps({"session_id": "s", "hook_event_name": ev}), tmp_path)
    assert [r["event"] for r in lines(tmp_path)] == ["UserPromptSubmit", "Stop", "PostToolUseFailure"]


def test_timestamp_is_timezone_aware_iso(tmp_path: Path) -> None:
    run(json.dumps({"session_id": "s", "hook_event_name": "Stop"}), tmp_path)
    ts = lines(tmp_path)[0]["timestamp"]
    assert ts[-6] in "+-" or ts.endswith("Z")


@pytest.mark.parametrize("stdin", ["", "garbage", "[1,2]", "null"])
def test_bad_input_never_fails_the_session(tmp_path: Path, stdin: str) -> None:
    r = run(stdin, tmp_path)
    assert r.returncode == 0 and r.stdout == ""


def test_unwritable_target_never_fails_the_session(tmp_path: Path) -> None:
    (tmp_path / "session-log").write_text("a file, not a dir")
    r = run(json.dumps({"session_id": "s", "hook_event_name": "Stop"}), tmp_path)
    assert r.returncode == 0
