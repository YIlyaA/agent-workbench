# Metrics: what "10x" means and how I measure it

"10x engineer" is a slogan. To prove or disprove it I need numbers that someone else can check. This file defines them before I look at results.

## Definitions

| Metric | Definition | Unit |
|---|---|---|
| **Velocity** | Work items accepted per week. An item counts only when its acceptance check passes and it is merged | items / week |
| **Throughput** | Verified outcomes shipped per human hour (or per active day) | outcomes / human hour |
| **Cycle time** | Time from "task approved" to "merged and passing" | hours |
| **Lead time** | Time from idea to running in production | hours or days |
| **Leverage** | Agent working hours that produced accepted work divided by my own hours spent on it | ratio |
| **Review wait** | Time a finished task waits for my review | hours |
| **Change failure rate** | Share of merged changes that needed a hotfix or rollback within 7 days | % |
| **Rework share** | Share of commits that are fixes or reverts | % |
| **Test share** | Share of changed lines that are in test files | % |

An **outcome** is something a user or the business can notice: a feature, a bug fix with a regression test, a migration, a documented runbook. A commit is not an outcome. Lines of code are not an outcome.

## 10x, stated precisely

> My throughput with the agent environment is at least 10 times my own baseline throughput, measured on the same kind of tasks, with change failure rate not worse than the baseline.

Three parts matter: (1) **my own baseline**, not an imaginary average engineer; (2) **same kind of tasks**, so I do not compare a hard task with an easy one; (3) **quality guard**, so speed cannot be bought with bugs.

A related claim is easier to verify: "I can run N agent tasks in parallel and still review them all." That is the leverage ratio. If leverage is 8 and review wait stays low, then one person really does the work of several.

## Baseline method

1. Take my git history before I used agents seriously (the date is stated in `docs/baseline.md`).
2. Compute commits, active days, code lines (generated, vendor and data files excluded), test share and fix share per month with `scripts/git_metrics.py`.
3. For a task-level baseline, run `scripts/historic_baseline.py` on the pre-agent history: each merge is a task, sessions split at gaps of more than 120 minutes, and the time is a range that adds 30 minutes of lead-in per session. Planner estimates are calibrated blind against it (method and limits in `docs/baseline.md`).
4. Write the baseline down before the experiment starts, so I cannot move the goalposts.

## Weekly tracking (rate of improvement)

Following the "rate of improvement" idea: the level matters less than how it changes.

- Week 0: baseline value of the chosen metric and a target.
- Each week: value, improvement versus baseline in %, change versus last week.
- After four weeks: look at the curve. Fast rise then flattening is healthy. Flat means the design does not work and must change. A rise then a decline means a problem with adoption or quality.

I track three headline numbers: **throughput**, **cycle time**, **change failure rate**.

## Experiment protocol (summary, details in `docs/experiment.md`)

- Pick a fixed set of tasks (a backlog slice) in advance.
- Split them: some done the old way (me, with only autocomplete), some with the agent environment. Alternate so that task difficulty is balanced.
- Log start, end, my own active minutes, agent runtime, tests, review findings, rollbacks.
- Report medians and ranges, not the best day.

## What this does not prove

- Git history shows activity, not value. A big diff can be bad.
- Before and after comparisons are confounded: I also got better, the project changed, and tasks differ in difficulty.
- A small sample (one engineer, a few tasks) cannot support a precise ratio. I report a range and the sample size.
- Lines of code reward verbosity. I use them only next to quality guards.
- Agent-written commits are not always marked, so I do not claim a number for "share of AI code" from git alone.

If the honest result is 3x, I write 3x, and I write what would be needed to reach 10x (more parallelism, better specs, faster review).

## How the numbers are collected (this repo)

| Number | Source | Rule |
|---|---|---|
| `est_hours_old_way` | task file, at planning time | Written by the planner, confirmed by the human at approval, never edited after. Calibrated against `docs/baseline.md` |
| `my_active_minutes` | `session-log/events.jsonl` | Sum of gaps between consecutive human events (`UserPromptSubmit`) in the task's start–end window, **each gap capped at 10 minutes**, plus review minutes timed by hand. Command: `metrics_report.py --active FROM TO`. Parallel tasks share the same human minutes, so the multiplier is conservative |
| Events | `scripts/log_event.py` hook on `UserPromptSubmit`, `Stop`, `SubagentStop`, `PostToolUseFailure` | Only `{timestamp, session_id, event, branch}`. Never prompt text. The raw file stays local (gitignored) |
| Deployment frequency | git | First-parent commits on `main` per week (each merged PR is one) |
| Change failure | `tasks.csv` `rolled_back` | Share of agent tasks rolled back or hot-fixed within 7 days |
| Defect escape | `tasks.csv` `type=escaped-defect` | A bug found after merge is logged as its own row with that type |
| Coverage | `coverage.json` from `pytest --cov` | Critical paths are `scripts/` and `hooks/` |
