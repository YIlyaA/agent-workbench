---
name: verify-diff
description: Independent review of a builder's branch by the verifier agent in a fresh context; records the verdict and finding count in the task file. Use when a task is ready-for-review.
when-to-use: After implement-task produced a green branch, or before any PR in Agents Workbench.
---

# Verify Diff Skill

## Purpose
The builder never judges its own work. A fresh-context verifier reruns the checks and tries to break the change.

## Agent Instructions

### Step 1: Spawn the verifier
Spawn the `verifier` agent (never reuse the builder's context) with the task file path and branch name.

### Step 2: Escalate risky diffs
If the diff touches hooks, permissions, anything that reads files outside the repo, or event logging, also run `security-review`.

### Step 2b: Guardrail code needs an old-vs-new probe
For any change to `hooks/` or other code that blocks or allows actions, the orchestrator also runs a probe that executes nothing:
1. Write a script in the scratchpad that imports the decision function (for example `blocked_reason`) from both the `main` version and the branch version.
2. Run both on every test command, plus the attack forms the verifier proposes.
3. Report every command that is blocked on `main` and allowed on the branch. Each one must be an intended, documented exception.

Keep the command text inside the script file, never in the Bash command line, because the live hook reads command text. Never redirect the probe's errors to `/dev/null`: a crashed probe prints nothing, which looks the same as "no regressions" (2026-10-16, T-001).

### Step 3: Record the verdict
Write the verdict, finding count and the top findings (file:line) into the task's Log.
- `PASS` or `PASS WITH NITS` (nits fixed) → ready for `release`.
- `FAIL` → back to a builder with the findings as the task's new acceptance criteria. Count it as not first-pass green.

## Expected Output
Verdict, finding count by severity, and the next step.

## Guardrails
- The verifier is read-only. It never fixes what it finds.
