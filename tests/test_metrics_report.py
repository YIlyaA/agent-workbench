import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.metrics_report import (
    CLAUDE_PROJECTS,
    ROOT,
    Task,
    active_intervals,
    active_minutes,
    curve_shape,
    default_transcripts_dir,
    load_subagents,
    max_overlap,
    max_parallel_sessions,
    percentile,
    project_slug,
    report,
    subagent_concurrency,
    summarize,
)

TZ = timezone(timedelta(hours=2))


def t(h: int, m: int, day: int = 16) -> datetime:
    return datetime(2026, 10, day, h, m, tzinfo=TZ)


def task(**kw: object) -> Task:
    base: dict = dict(
        id="T-1",
        date="2026-10-16",
        type="feature",
        method="agent",
        est_hours_old_way=2.0,
        my_active_minutes=20.0,
        agent_runtime_minutes=30.0,
        start=t(10, 0),
        end=t(11, 0),
        tests_green=True,
        review_findings=1,
        rolled_back=False,
        outcome="x",
    )
    base.update(kw)
    return Task(**base)


# active minutes: gaps between consecutive human events, each capped at 10
def test_active_minutes_caps_gaps() -> None:
    events = [t(10, 0), t(10, 3), t(10, 30), t(10, 35)]
    assert active_minutes(events, cap=10) == 3 + 10 + 5


def test_active_minutes_unsorted_and_duplicates() -> None:
    assert active_minutes([t(10, 5), t(10, 0), t(10, 5)], cap=10) == 5


@pytest.mark.parametrize("events", [[], [t(10, 0)]])
def test_active_minutes_needs_two_events(events: list[datetime]) -> None:
    assert active_minutes(events, cap=10) == 0


def test_percentile_median_and_p90() -> None:
    xs = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert percentile(xs, 50) == 55
    assert percentile(xs, 90) == pytest.approx(91)
    assert percentile([], 50) is None


def test_max_parallel_sessions() -> None:
    spans = {
        "a": (t(10, 0), t(11, 0)),
        "b": (t(10, 30), t(12, 0)),
        "c": (t(11, 30), t(13, 0)),
        "d": (t(14, 0), t(15, 0)),
    }
    assert max_parallel_sessions(spans) == 2


def test_max_parallel_sessions_touching_spans_do_not_overlap() -> None:
    assert max_parallel_sessions({"a": (t(10, 0), t(11, 0)), "b": (t(11, 0), t(12, 0))}) == 1
    assert max_parallel_sessions({}) == 0


def test_summarize_core_numbers() -> None:
    tasks = [
        task(id="T-1", my_active_minutes=20, est_hours_old_way=2, tests_green=True, review_findings=2),
        task(
            id="T-2", my_active_minutes=40, est_hours_old_way=1, tests_green=False, review_findings=0, rolled_back=True
        ),
        task(id="T-3", method="old", my_active_minutes=60, est_hours_old_way=1),
    ]
    s = summarize(tasks)
    assert s["agent_tasks"] == 2 and s["old_tasks"] == 1
    assert s["multiplier_median"] == pytest.approx((6.0 + 1.5) / 2)
    assert s["first_pass_green_pct"] == 50
    assert s["review_findings_per_task"] == 1
    assert s["change_failure_pct"] == 50
    assert s["lead_time_median_min"] == 60


def test_summarize_skips_zero_active_minutes_in_multiplier() -> None:
    s = summarize([task(my_active_minutes=0)])
    assert s["multiplier_median"] is None


def test_summarize_empty() -> None:
    s = summarize([])
    assert s["agent_tasks"] == 0 and s["multiplier_median"] is None and s["first_pass_green_pct"] is None


@pytest.mark.parametrize(
    ("series", "shape"),
    [
        ([1, 3, 5, 5.2, 5.1], "rise-taper-flat (success)"),
        ([1, 4, 6, 3, 2], "rise-then-decline (adoption or quality problem)"),
        ([3, 3.1, 2.9, 3], "flat (wrong use case or no effect)"),
        ([1, 2, 4, 8, 16], "rising, no taper yet (check the measurement)"),
        ([1, 2], "not enough data (need 3+ weeks)"),
    ],
)
def test_curve_shape(series: list[float], shape: str) -> None:
    assert curve_shape(series) == shape


def test_load_tasks_parses_and_tolerates_bad_numbers(tmp_path) -> None:
    from scripts.metrics_report import load_tasks

    p = tmp_path / "tasks.csv"
    p.write_text(
        "id,date,type,method,est_hours_old_way,my_active_minutes,agent_runtime_minutes,start,end,"
        "tests_green,review_findings,rolled_back,outcome\n"
        "T-1,2026-10-16,feature,Agent,1.5,30,40,10:00,11:30,yes,2,no,done\n"
        "T-2,2026-10-16,docs,old,,abc,0,bad,11:00,no,,yes,x\n"
        ",,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    a, b = load_tasks(p)
    assert a.method == "agent" and a.lead_minutes == 90 and a.multiplier == 3.0 and a.tests_green
    assert b.est_hours_old_way == 0 and b.my_active_minutes == 0 and b.start is None and b.rolled_back
    assert b.lead_minutes is None and b.multiplier is None


def test_load_tasks_missing_file(tmp_path) -> None:
    from scripts.metrics_report import load_tasks

    assert load_tasks(tmp_path / "nope.csv") == []


def test_load_events_skips_corrupt_lines(tmp_path) -> None:
    from scripts.metrics_report import load_events

    p = tmp_path / "events.jsonl"
    p.write_text(
        '{"timestamp":"2026-10-16T10:00:00+02:00","session_id":"a","event":"UserPromptSubmit","branch":"main"}\n'
        "not json\n"
        '{"timestamp":"yesterday","session_id":"a","event":"Stop"}\n'
        '{"session_id":"b"}\n'
        '{"timestamp":"0001-01-01T00:00:00+05:00"}\n'
        '{"timestamp":"2026-10-16T10:05:00+02:00","session_id":"a","event":"UserPromptSubmit","branch":"main"}\n',
        encoding="utf-8",
    )
    ev = load_events(p)
    assert len(ev) == 2


def test_max_parallel_sessions_zero_length_session_counts_as_one() -> None:
    assert max_parallel_sessions({"a": (t(10, 0), t(10, 0))}) == 1
    assert max_parallel_sessions({"a": (t(10, 0), t(10, 0)), "b": (t(10, 0), t(11, 0))}) == 2


# ---------- subagent concurrency ----------

SECRETS = ("SECRET-DESC", "SECRET-BODY", "secret-branch")
LEAKY_META = {"description": "SECRET-DESC", "worktreeBranch": "secret-branch"}


def agent(base, session, agent_id, agent_type, stamps, meta="default", extra_lines=()):
    d = base / session / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"timestamp": s.isoformat() if isinstance(s, datetime) else s}) for s in stamps]
    (d / f"agent-{agent_id}.jsonl").write_text("\n".join([*lines, *extra_lines]) + "\n", encoding="utf-8")
    if meta == "default":
        meta = json.dumps({"agentType": agent_type, **LEAKY_META})
    if meta is not None:
        (d / f"agent-{agent_id}.meta.json").write_text(meta, encoding="utf-8")


def every(a: datetime, b: datetime, step: int = 4) -> list[datetime]:
    out = [a]
    while out[-1] + timedelta(minutes=step) < b:
        out.append(out[-1] + timedelta(minutes=step))
    return [*out, b]


def local(d: datetime, fmt: str = "%H:%M") -> str:
    return d.astimezone().strftime(fmt)


@pytest.mark.parametrize(
    "path,slug",
    [("/Users/a/ENV_AGENTS", "-Users-a-ENV-AGENTS"), ("C:\\Users\\a\\my proj", "C--Users-a-my-proj")],
    ids=["posix", "win"],
)
def test_project_slug(path: str, slug: str) -> None:
    assert project_slug(path) == slug


def test_default_transcripts_dir() -> None:
    assert default_transcripts_dir() == CLAUDE_PROJECTS / project_slug(str(ROOT))


def test_active_intervals_split() -> None:
    times = [t(11, 47), t(11, 50), *every(t(12, 20), t(12, 31))]
    assert active_intervals(times) == [(t(11, 47), t(11, 50)), (t(12, 20), t(12, 31))]


def test_active_intervals_boundary() -> None:
    late = t(10, 10) + timedelta(seconds=1)
    assert active_intervals([late, t(10, 5), t(10, 0)]) == [(t(10, 0), t(10, 5)), (late, late)]
    assert active_intervals([]) == []


def test_max_overlap_window() -> None:
    assert max_overlap({}) == (0, None, None)
    assert max_overlap({"a": (t(10, 0), t(10, 0))}) == (1, t(10, 0), t(10, 0))
    spans = {"a": (t(10, 0), t(10, 20)), "b": (t(10, 10), t(10, 30))}
    assert max_overlap(spans) == (2, t(10, 10), t(10, 20))


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_subagents_missing_dir(tmp_path, kind: str) -> None:
    p = tmp_path / "x"
    if kind == "file":
        p.write_text("hi", encoding="utf-8")
    assert load_subagents(p) == []
    out = report([], [], tmp_path, subagents=load_subagents(p))
    assert "max concurrent subagents: n/a" in out
    assert "max concurrent builders: n/a" in out


def test_subagents_empty_dir(tmp_path) -> None:
    (tmp_path / "s1").mkdir()
    assert load_subagents(tmp_path) == []
    assert "max concurrent subagents: n/a" in report([], [], tmp_path, subagents=[])
    assert "max concurrent builders: n/a" in report([], [], tmp_path)


def test_subagents_corrupt_lines(tmp_path) -> None:
    bad = ["not json", "[]", '{"timestamp": 5}', '{"timestamp": "yesterday"}', "{}", '{"timestamp": "2026-10-16T10:0']
    bad.append('{"timestamp": "0001-01-01T00:00:00+05:00"}')
    agent(tmp_path, "s", "a1", "builder", [t(10, 0), t(10, 3)], extra_lines=bad)
    agent(tmp_path, "s", "a2", "builder", [], extra_lines=bad)
    agent(tmp_path, "s", "a3", "builder", [])
    got = load_subagents(tmp_path)
    assert len(got) == 1
    assert got[0][0] == "builder"
    assert got[0][1] == [t(10, 0), t(10, 3)]


@pytest.mark.parametrize(
    "meta",
    [None, "{bad", "[]", '{"agentType": 3}'],
    ids=["none", "bad", "list", "int"],
)
def test_subagents_meta_fallback(tmp_path, meta) -> None:
    agent(tmp_path, "s", "a1", "builder", [t(10, 0)], meta=meta)
    subs = load_subagents(tmp_path)
    assert [a[0] for a in subs] == ["unknown"]
    assert "max concurrent builders: 0" in report([], [], tmp_path, subagents=subs)


def test_subagents_unreadable_file(tmp_path, monkeypatch) -> None:
    agent(tmp_path, "s", "bad", "builder", [t(10, 0)])
    agent(tmp_path, "s", "ok", "verifier", [t(10, 0)])
    real = Path.open

    def fake(self, *a, **k):
        if self.name == "agent-bad.jsonl":
            raise OSError("denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "open", fake)
    assert [a[0] for a in load_subagents(tmp_path)] == ["verifier"]


def test_subagents_mixed_offsets(tmp_path) -> None:
    utc = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)
    naive = "2026-10-16T10:00:00"
    agent(tmp_path, "s", "a", "builder", [utc.isoformat().replace("+00:00", "Z"), naive])
    agent(tmp_path, "s", "b", "verifier", [t(10, 0)])  # +02:00, same instant as utc 08:00
    got = dict(load_subagents(tmp_path))
    assert got["builder"][0] == utc
    assert got["builder"][1] == datetime.fromisoformat(naive).astimezone()
    assert got["verifier"] == [utc]


def test_resume_gap_not_counted() -> None:
    a = ("builder", [t(11, 47), t(11, 50), *every(t(12, 20), t(12, 31))])
    b = ("builder", every(t(12, 0), t(12, 10)))
    assert subagent_concurrency([a, b])["builders_max"] == 1


def test_concurrency_window() -> None:
    agents = [
        ("builder", every(t(10, 0), t(10, 20))),
        ("builder", every(t(10, 5), t(10, 25))),
        ("builder", every(t(10, 10), t(10, 30))),
        ("verifier", [t(10, 12), t(10, 14)]),
    ]
    r = subagent_concurrency(agents)
    assert (r["max"], r["window"]) == (4, (t(10, 12), t(10, 14)))
    assert (r["builders_max"], r["builders_window"]) == (3, (t(10, 10), t(10, 20)))


def test_concurrency_touching() -> None:
    r = subagent_concurrency([("builder", every(t(10, 0), t(10, 10))), ("builder", every(t(10, 10), t(10, 12)))])
    assert r["max"] == 1


def test_window_crosses_midnight(tmp_path) -> None:
    a, b = t(23, 58), t(0, 3, day=17)
    agent(tmp_path, "s", "a", "builder", [a, b])
    out = report([], [], tmp_path, subagents=load_subagents(tmp_path))
    assert f"max concurrent builders: 1 ({local(a, '%Y-%m-%d %H:%M')}-{local(b, '%Y-%m-%d %H:%M')})" in out


def test_report_prints_no_content(tmp_path) -> None:
    body = '{"timestamp": "2026-10-16T10:01:00+02:00", "message": "SECRET-BODY"}'
    agent(tmp_path, "s", "a", "builder", [t(10, 0)], extra_lines=[body])
    out = report([], [], tmp_path, subagents=load_subagents(tmp_path))
    day = local(t(10, 0), "%Y-%m-%d")
    assert f"max concurrent subagents: 1 ({day} {local(t(10, 0))}-{local(t(10, 1))})" in out
    assert not any(s in out for s in SECRETS)
