#!/usr/bin/env python3
"""Velocity and quality report from session-log/tasks.csv, session-log/events.jsonl and git.

Usage:  uv run python scripts/metrics_report.py                      # full report
        uv run python scripts/metrics_report.py --active FROM TO     # human active minutes in a window
                                                                     # (ISO times, e.g. 2026-10-16T10:00)
Definitions are in METRICS.md. Stdlib only, read-only.

Active minutes: sum of gaps between consecutive human events (UserPromptSubmit),
each gap capped at ACTIVE_GAP_CAP_MIN. Speed only counts if the quality numbers stay flat or improve.
"""

import argparse
import csv
import json
import statistics
import subprocess
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS_CSV = ROOT / "session-log" / "tasks.csv"
EVENTS_JSONL = ROOT / "session-log" / "events.jsonl"
COVERAGE_JSON = ROOT / "coverage.json"
ACTIVE_GAP_CAP_MIN = 10
HUMAN_EVENTS = {"UserPromptSubmit"}
ESCAPED_DEFECT_TYPE = "escaped-defect"  # tasks.csv `type` for a bug found after merge
FLAT_RANGE_RATIO = 0.15  # weekly series whose range is under 15% of its mean counts as flat
TAPER_RATIO = 0.25  # late growth under 25% of early growth counts as tapering
DECLINE_RATIO = 0.8  # last week under 80% of the peak counts as declining


@dataclass
class Task:
    id: str
    date: str
    type: str
    method: str
    est_hours_old_way: float
    my_active_minutes: float
    agent_runtime_minutes: float
    start: datetime | None
    end: datetime | None
    tests_green: bool
    review_findings: int
    rolled_back: bool
    outcome: str

    @property
    def lead_minutes(self) -> float | None:
        if self.start and self.end and self.end >= self.start:
            return (self.end - self.start).total_seconds() / 60
        return None

    @property
    def multiplier(self) -> float | None:
        if self.my_active_minutes > 0 and self.est_hours_old_way > 0:
            return self.est_hours_old_way * 60 / self.my_active_minutes
        return None


# ---------- pure calculations ----------


def active_minutes(events: list[datetime], cap: float = ACTIVE_GAP_CAP_MIN) -> float:
    ts = sorted(set(events))
    return sum(min((b - a).total_seconds() / 60, cap) for a, b in zip(ts, ts[1:], strict=False))


def percentile(xs: Sequence[float], p: float) -> float | None:
    """Linear interpolation between closest ranks (same as numpy's default)."""
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def max_parallel_sessions(spans: dict[str, tuple[datetime, datetime]]) -> int:
    # At the same instant: ends of real spans (0), then starts (1), then ends of zero-length spans (2),
    # so touching sessions do not overlap but a session whose events share one second still counts.
    points: list[tuple[datetime, int, int]] = []
    for start, end in spans.values():
        points += [(start, 1, 1), (end, 2 if end == start else 0, -1)]
    best = cur = 0
    for _, _, delta in sorted(points, key=lambda p: (p[0], p[1])):
        cur += delta
        best = max(best, cur)
    return best


def _pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def summarize(tasks: list[Task]) -> dict:
    agent = [t for t in tasks if t.method == "agent"]
    leads = [x for t in agent if (x := t.lead_minutes) is not None]
    mults = [x for t in agent if (x := t.multiplier) is not None]
    return {
        "agent_tasks": len(agent),
        "old_tasks": sum(t.method == "old" for t in tasks),
        "lead_time_median_min": _median(leads),
        "lead_time_p90_min": percentile(leads, 90),
        "active_minutes_median": _median([t.my_active_minutes for t in agent]),
        "multiplier_median": _median(mults),
        "multiplier_range": (min(mults), max(mults)) if mults else None,
        "first_pass_green_pct": _pct(sum(t.tests_green for t in agent), len(agent)),
        "review_findings_per_task": statistics.mean(t.review_findings for t in agent) if agent else None,
        "change_failure_pct": _pct(sum(t.rolled_back for t in agent), len(agent)),
        "defect_escape_pct": _pct(sum(t.type == ESCAPED_DEFECT_TYPE for t in tasks), len(tasks)),
    }


def curve_shape(series: list[float]) -> str:
    if len(series) < 3:
        return "not enough data (need 3+ weeks)"
    mean = statistics.mean(series)
    if mean and (max(series) - min(series)) / mean < FLAT_RANGE_RATIO:
        return "flat (wrong use case or no effect)"
    peak_i = series.index(max(series))
    if peak_i < len(series) - 1 and series[-1] < DECLINE_RATIO * series[peak_i]:
        return "rise-then-decline (adoption or quality problem)"
    early, late = series[2] - series[0], series[-1] - series[-3]
    if early > 0 and late < TAPER_RATIO * early:
        return "rise-taper-flat (success)"
    if early > 0:
        return "rising, no taper yet (check the measurement)"
    return "mixed (read the weekly table)"


# ---------- loading ----------


def _local(date: str, hhmm: str) -> datetime | None:
    try:
        return datetime.fromisoformat(f"{date}T{hhmm}").astimezone()
    except ValueError:
        return None


def _num(x: str) -> float:
    try:
        return float(x)
    except ValueError:
        return 0.0


def load_tasks(path: Path) -> list[Task]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Task(
                id=r["id"],
                date=r["date"],
                type=r["type"],
                method=r["method"].strip().lower(),
                est_hours_old_way=_num(r["est_hours_old_way"]),
                my_active_minutes=_num(r["my_active_minutes"]),
                agent_runtime_minutes=_num(r["agent_runtime_minutes"]),
                start=_local(r["date"], r["start"]),
                end=_local(r["date"], r["end"]),
                tests_green=r["tests_green"].strip().lower() == "yes",
                review_findings=int(_num(r["review_findings"])),
                rolled_back=r["rolled_back"].strip().lower() == "yes",
                outcome=r["outcome"],
            )
            for r in csv.DictReader(f)
            if r.get("id")
        ]


def load_events(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
            e["ts"] = datetime.fromisoformat(e["timestamp"]).astimezone()
            out.append(e)
        except (ValueError, KeyError, TypeError):
            continue  # a corrupt line must not hide the rest of the log
    return out


def session_spans(events: list[dict]) -> dict[str, tuple[datetime, datetime]]:
    spans: dict[str, tuple[datetime, datetime]] = {}
    for e in events:
        sid, ts = e.get("session_id", ""), e["ts"]
        lo, hi = spans.get(sid, (ts, ts))
        spans[sid] = (min(lo, ts), max(hi, ts))
    return spans


def human_times(events: list[dict], start: datetime | None = None, end: datetime | None = None) -> list[datetime]:
    return [
        e["ts"]
        for e in events
        if e.get("event") in HUMAN_EVENTS and (start is None or e["ts"] >= start) and (end is None or e["ts"] <= end)
    ]


def main_commits_per_week(repo: Path) -> dict[str, int]:
    """Deployment frequency proxy: first-parent commits on main (each merged PR is one)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--first-parent", "main", "--date=short", "--pretty=%ad"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return {}
    weeks: dict[str, int] = defaultdict(int)
    for d in out:
        y, w, _ = datetime.fromisoformat(d).isocalendar()
        weeks[f"{y}-W{w:02d}"] += 1
    return dict(sorted(weeks.items()))


def coverage_pct(path: Path) -> float | None:
    try:
        return round(json.loads(path.read_text(encoding="utf-8"))["totals"]["percent_covered"], 1)
    except (OSError, ValueError, KeyError):
        return None


# ---------- report ----------


def _fmt(x: object, unit: str = "") -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.1f}{unit}"
    return f"{x}{unit}"


def week_of(t: Task) -> str:
    y, w, _ = datetime.fromisoformat(t.date).isocalendar()
    return f"{y}-W{w:02d}"


def report(tasks: list[Task], events: list[dict], repo: Path) -> str:
    s = summarize(tasks)
    agent = [t for t in tasks if t.method == "agent"]
    days = sorted({t.date for t in agent})
    out = [
        "# Metrics report",
        f"tasks.csv: {len(tasks)} rows ({s['agent_tasks']} agent, {s['old_tasks']} old way) · "
        f"events.jsonl: {len(events)} events, {len(session_spans(events))} sessions",
        "",
        "## Flow",
        f"tasks merged per active day: {_fmt(len(agent) / len(days) if days else None)}",
        f"lead time median / p90: {_fmt(s['lead_time_median_min'], ' min')} / {_fmt(s['lead_time_p90_min'], ' min')}",
        f"max parallel sessions: {max_parallel_sessions(session_spans(events))}",
        "",
        "## Human time and leverage",
        f"active minutes per task (median): {_fmt(s['active_minutes_median'])}",
        f"multiplier est_hours_old_way*60/active (median): {_fmt(s['multiplier_median'], 'x')}"
        + (f"  range {s['multiplier_range'][0]:.1f}x-{s['multiplier_range'][1]:.1f}x" if s["multiplier_range"] else ""),
        f"human active minutes in all logged events: {_fmt(active_minutes(human_times(events)))}",
        "",
        "## Quality (speed only counts if these hold)",
        f"first-pass green: {_fmt(s['first_pass_green_pct'], '%')}",
        f"review findings per task: {_fmt(s['review_findings_per_task'])}",
        f"change failure (rolled back): {_fmt(s['change_failure_pct'], '%')}",
        f"defect escape (type={ESCAPED_DEFECT_TYPE}): {_fmt(s['defect_escape_pct'], '%')}",
        f"test coverage (coverage.json): {_fmt(coverage_pct(COVERAGE_JSON), '%')}",
        "",
        "## Weekly trend",
        "| week | agent tasks | active h | tasks per active h | change vs last week | merges to main |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    by_week: dict[str, list[Task]] = defaultdict(list)
    for t in agent:
        by_week[week_of(t)].append(t)
    deploys = main_commits_per_week(repo)
    series: list[float] = []
    for wk in sorted(set(by_week) | set(deploys)):
        ts = by_week.get(wk, [])
        hours = sum(t.my_active_minutes for t in ts) / 60
        rate = len(ts) / hours if hours else 0.0
        change = f"{(rate / series[-1] - 1) * 100:+.0f}%" if series and series[-1] else "n/a"
        series.append(rate)
        out.append(f"| {wk} | {len(ts)} | {hours:.1f} | {rate:.2f} | {change} | {deploys.get(wk, 0)} |")
    out += ["", f"curve shape: {curve_shape(series)}", "", "Baseline: docs/baseline.md. Definitions: METRICS.md."]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--active", nargs=2, metavar=("FROM", "TO"), help="human active minutes between two ISO times")
    a = ap.parse_args()
    events = load_events(EVENTS_JSONL)
    if a.active:
        start, end = (datetime.fromisoformat(x).astimezone() for x in a.active)
        print(f"{active_minutes(human_times(events, start, end)):.0f}")
        return 0
    print(report(load_tasks(TASKS_CSV), events, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
