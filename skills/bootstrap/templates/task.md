---
id: T-000
status: draft            # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # low | medium | high  (medium and high: human approves each risky command)
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
diff_limit_lines: 300
est_hours_old_way:       # set at planning time, before work starts; never edited afterwards
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

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|

## Test plan
<Which tests are added or changed, and the command that runs them.>

## Log (filled in by the builder and verifier)
- Checks run (command and real output):
- Verifier verdict and findings:
- Human review:
