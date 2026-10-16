# Experiment: measured throughput with the agent environment

Goal: get an honest throughput and leverage number in a few days, using real tasks.

## Setup (before starting, write it down)

1. **Pick the task set.** 8 to 12 real tasks from one backlog, each sized between 30 minutes and 3 hours of normal work. Mix: feature, bug with regression test, migration, refactor, test-writing, docs.
2. **Estimate the old way.** For each task, write my honest estimate of hours without agents, from similar past tasks in git (not from hope). This is the baseline column.
3. **Define acceptance checks.** Each task has a check that can fail.
4. **Fix the quality guard.** Tests green, verifier agent review done, no hotfix within the experiment window.

## Run

- Alternate: tasks 1, 3, 5... use the agent environment (DESIGN.md loop). Tasks 2, 4, 6... are done with the old method (me, editor autocomplete only), timed. This gives a within-person comparison on similar tasks.
- Then run a **parallel batch**: 4 to 6 independent tasks at the same time, each in its own worktree.
- Log every task in `session-log/tasks.csv` (columns in templates/task-log.md).

## Measure

| Number | How |
|---|---|
| Throughput | accepted outcomes divided by my active hours |
| Cycle time | approved to merged, median per method |
| Leverage | sum of agent runtime that produced accepted work divided by my active hours |
| Review wait | median time from "agent done" to "I reviewed" |
| Quality | tests green, review findings, rollbacks |
| Plan accuracy | estimated hours versus actual, both methods |

## Report

One table: old method versus agent method versus parallel batch, with medians, ranges and sample size. One paragraph in plain words: what is the ratio, how sure am I, what limits it, and what I change next week. If the ratio is below 10, say so and name the bottleneck (usually specs or review).

## Daily schedule (8 hours)

| Block | Work |
|---|---|
| 1 hour | Choose tasks, estimates, acceptance checks, set up worktrees and AGENTS.md |
| 3 hours | Alternating tasks (agent and old method), logging |
| 2 hours | Parallel batch and review |
| 1 hour | Metrics, post-mortem, skill updates |
| 1 hour | Write the report and rehearse the explanation out loud |
