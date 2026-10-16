# Agent-readiness score

Date: 2026-10-16. Scored after Bootstrap Phases 0–3 and decision 0002 were merged (`main` at `b0d0ec6`). Each check is 0–2. Evidence is given as file:line. A check that is set up but has never been used scores 1.

| Check | Score | Evidence | Fix to reach 2 |
|---|:-:|---|---|
| AGENTS / CLAUDE / CONTEXT | **2** | `AGENTS.md:9` commands, each run during setup; `AGENTS.md:14` one check command; `CLAUDE.md:3` points to AGENTS.md; `CONTEXT.md:7` architecture | none |
| Skills and routing | **2** | `AGENTS.md:60` routing table for all four kinds of work; `.claude/skills/{plan-task,implement-task,verify-diff,release}` use this repo's commands and paths | none |
| Tests on critical logic | **1** | 79 tests, one command (`AGENTS.md:14`). Covered by tests: git guardrail hook (32 cases), installer (87% line coverage), report (66%), validator (85%), event logger (tested as a subprocess). **`scripts/git_metrics.py` has 0% coverage.** Total line coverage is 59%, understated because tests that run scripts as subprocesses are not counted | Add tests for `git_metrics.py` on a temporary git repo, and measure coverage of subprocess runs |
| Delegation seams | **2** | `tasks/_template.md:5` autonomy level per task; `AGENTS.md:42` level per kind of work; scope, diff limit and budget fields in the template | none |
| Guardrails | **2** | `.claude/settings.json:17` `ask` and `:27` `deny` rules; global `block_dangerous_git.py` hook (it blocked real commands twice today); `.pre-commit-config.yaml:9` detect-secrets; `.github/workflows/ci.yml:16` CI on 3 OSes | none. Known gap: T-001 fixes the hook's false positives |
| Verification | **1** | `.claude/agents/verifier.md:3` is a separate verifier with fresh context, plus the `verify-diff` skill. **It has not run on a real task yet** | Run the verifier on T-001 |
| Measurement | **1** | `.claude/settings.json:21`–`:47` event hooks are live (`session-log/events.jsonl` is filling); `scripts/metrics_report.py:256` report; git-level baseline in `docs/baseline.md`. **Task-level baseline is empty** (`docs/baseline.md:52` TODO) and `tasks.csv` has no rows | Log T-001; time 2–3 small tasks done the old way |
| Decision traceability | **2** | `docs/decisions/0001-stack-and-layout.md`, `docs/decisions/0002-approve-to-execute.md:7` (decision_summary, justification, evidence, assumptions) | none |

**Total: 13 / 16.**

## Fixes, in Pareto order

1. **Run T-001 through the full loop.** That moves Verification to 2 and puts the first real row in `tasks.csv`.
2. **Time 2–3 small tasks the old way** and fill the `docs/baseline.md` table. Measurement goes to 2; without this, the "10×" question can't be answered.
3. **Write tests for `git_metrics.py`** (temporary repo, known commits). Tests go to 2.
