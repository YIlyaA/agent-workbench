# Baseline: one production project

Source: `scripts/git_metrics.py` run read-only on my main backend project (a Django + Celery + Postgres platform, one main developer). Generated and data files are excluded. Dates are commit dates, 2025-06 to 2026-10.

| Month | Commits | Active days | Commits / day | Code lines | Lines / day | Test share | Fix share |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-06 | 3 | 2 | 1.5 | 1,634 | 817 | 0% | 0% |
| 2025-07 | 3 | 1 | 3.0 | 3,229 | 3,229 | 0% | 0% |
| 2025-08 | 67 | 25 | 2.7 | 79,319 | 3,173 | 2% | 18% |
| 2025-09 | 136 | 27 | 5.0 | 48,223 | 1,786 | 0% | 29% |
| 2025-10 | 23 | 12 | 1.9 | 9,281 | 773 | 0% | 17% |
| 2025-11 | 12 | 9 | 1.3 | 516 | 57 | 0% | 8% |
| 2025-12 | 2 | 1 | 2.0 | 42 | 42 | 0% | 50% |
| 2026-02 | 36 | 9 | 4.0 | 12,454 | 1,384 | 0% | 36% |
| 2026-03 | 5 | 4 | 1.3 | 864 | 216 | 4% | 0% |
| 2026-04 | 5 | 2 | 2.5 | 499 | 250 | 0% | 20% |
| 2026-05 | 10 | 6 | 1.7 | 3,268 | 545 | 0% | 30% |
| 2026-06 | 2 | 2 | 1.0 | 59 | 30 | 0% | 0% |
| 2026-07 | 23 | 12 | 1.9 | 8,396 | 700 | 1% | 4% |
| 2026-08 | 70 | 11 | 6.4 | 41,545 | 3,777 | 36% | 29% |
| 2026-09 | 31 | 5 | 6.2 | 18,630 | 3,726 | 22% | 42% |
| 2026-10 (to the 10th) | 44 | 5 | 8.8 | 24,051 | 4,810 | 24% | 20% |

## Two periods compared

| | Before 2026-08 | 2026-08 onward |
|---|---:|---:|
| Commits | 327 | 145 |
| Active days | 112 | 21 |
| Commits per active day | 2.9 | 6.9 |
| Code lines per active day | about 1,500 | about 4,000 |
| Test share of changed lines | about 1% | about 29% |

## How to read this

- Per active day, output is **about 2.4x to 2.7x higher** in the second period. That is a real, measured improvement. It is **not** 10x.
- The biggest quality change is the test share: from almost none to about a quarter of changed lines. Speed went up while testing went up too.
- The fix share did not fall (it stayed around 20 to 40 percent in busy months). Fast output also means more follow-up fixes, and I should reduce that with better specs and a verifier agent.
- The first period includes a very busy start (2025-08 and 2025-09) and several quiet months, so "before" is not one clean level. Ranges matter more than the average.
- Active days are days with at least one commit, not hours worked. Hours are not in git, so the experiment (docs/experiment.md) records them.

## What to do with it

This is the baseline for the next measurements: throughput per active day and per human hour, plus test share and fix share as quality guards. The 10x question is answered by the experiment, not by this table.

## Task-level baseline from git history

The production numbers above are git-level. The task-level baseline is mined from pre-agent history by `scripts/historic_baseline.py` (read-only, stdlib only), so nobody has to time old-way tasks by hand.

**Method.**
- Each merge commit before the cutoff is one task. Merges of main into a feature branch and `git pull` merges on main are skipped. Stashes are ignored.
- A task is the non-merge commits the merge brought in. A commit belongs to at most one task. Commits no merge claimed are only counted (`direct_commits`).
- Commit author times are sorted and split into sessions wherever the gap is more than `SESSION_GAP_MIN = 120` minutes.
- `low_min` is the sum of the session lengths (first to last commit). `high_min` is `low_min + LEAD_IN_MIN * sessions` with `LEAD_IN_MIN = 30`, for the work before the first commit of each session. `mid_min` is the average of the two.
- A single-commit task has low 0 and high 30. These tasks are counted as `zero_low_tasks`.
- Size buckets use `SIZE_BUCKETS = (100, 500)` code lines: `<100`, `100-500`, `>500`.

**Calibration.** The script writes a blind sheet (no times, dates or authors). A fresh planner estimates `est_hours_old_way` for each task from the blind sheet alone. The ratio `actual_mid_min / (estimate_hours * 60)` then gives a correction factor for planner estimates. Pre-registered before the run: if fewer than 15 tasks remain after skips, or more than half have `low = 0`, the factor is reported as indicative only.

**Limits.**
- Commit time is not hours worked. The result is a range, not a point.
- Work done before the first commit or after the last one, and uncommitted work, is invisible. The lead-in only partly covers it.
- Breaks shorter than 120 minutes count as work. Parallel tasks on different branches overlap, so their times are not additive.
- Autocomplete already existed then, so this is the old way with autocomplete only.
- One person commits under several author names. All authors are kept and counted.
- Commit subjects may contain dates or numbers. The blind sheet still carries subjects, so a planner could read a date from one.
- Merges that are not real tasks (a long-lived branch, a release merge) are included. Check the largest tasks by hand.

Run it outside this repo and keep the output out of it: the files contain private commit subjects.

| group | n | median low_min | median high_min | median mid_min |
|---|---:|---:|---:|---:|
| all | <TODO> | <TODO> | <TODO> | <TODO> |
| feat / fix / other | <TODO> | <TODO> | <TODO> | <TODO> |
| `<100` / `100-500` / `>500` lines | <TODO> | <TODO> | <TODO> | <TODO> |

| calibration | tasks estimated | median actual_mid / estimate | p25 to p75 | share inside [low, high] | date |
|---|---:|---:|---|---:|---|
| first run | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
