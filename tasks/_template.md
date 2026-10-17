---
id: T-000
status: draft            # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # low | medium | high  (medium and high: human approves each risky command)
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: feature            # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 300    # hard stop (scripts/check_diff_limit.py); task file not counted
est_hours_old_way:       # set at planning time, before work starts; never edited after approval
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true
---

# <Task title>

## Goal
<One or two sentences. Which objective does this trace to?>

## Scope (paths the builder may touch)
- `<path>`

## Acceptance criteria
- [ ] <observable behavior>
- [ ] `uv run python scripts/check.py` passes

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|

## Test plan
<Which tests are added or changed. Command: `uv run python scripts/check.py`.>

## Log (filled in by the builder and verifier)
- Start / end:
- Checks run (command and real output):
- Verifier verdict and findings:
- Human review (minutes, notes):
