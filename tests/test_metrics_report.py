from datetime import datetime, timedelta, timezone

import pytest

from scripts.metrics_report import (
    Task,
    active_minutes,
    curve_shape,
    max_parallel_sessions,
    percentile,
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
        '{"timestamp":"2026-10-16T10:05:00+02:00","session_id":"a","event":"UserPromptSubmit","branch":"main"}\n',
        encoding="utf-8",
    )
    ev = load_events(p)
    assert len(ev) == 2


def test_max_parallel_sessions_zero_length_session_counts_as_one() -> None:
    assert max_parallel_sessions({"a": (t(10, 0), t(10, 0))}) == 1
    assert max_parallel_sessions({"a": (t(10, 0), t(10, 0)), "b": (t(10, 0), t(11, 0))}) == 2
