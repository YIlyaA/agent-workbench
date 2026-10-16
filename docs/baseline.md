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
