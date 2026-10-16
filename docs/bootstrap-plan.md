# Bootstrap plan: Agents Workbench

Historical record of the first `/bootstrap` run. It was written when the repo was the local folder `ENV_AGENTS`; that name below refers to the folder.

Date: 2026-10-16. Status: **waiting for GATE 1 (`approved`)**. This plan does not authorize implementation.

## 1. What was found (Phase 0)

| Item | Finding | Evidence |
|---|---|---|
| Folder | Empty, not a git repo | `ls -la` → only `.` and `..`; `git rev-parse` → "not a git repository" |
| Reference design | Exists, 25 files, 120 KB, **not under git** | `AI_AGENTS_ANALYSE/work-environment-repo/` (`DESIGN.md`, `METRICS.md`, `AGENTS.md`, `scripts/git_metrics.py`, `templates/`, `docs/baseline.md`, `session-log/tasks.csv` with header only) |
| Global bootstrap skill | Symlink into the reference design | `~/.claude/skills/bootstrap -> …/work-environment-repo/skills/bootstrap` |
| Global guardrails | Active | `~/.claude/settings.json`: PreToolUse hook `block-dangerous-git.sh` (blocks force push, push to main/master, reset --hard, clean -f, branch -D, checkout/restore .) and 8 deny rules (.env, secrets, sudo, rm -rf / and ~) |
| Toolchain | git 2.48, gh 2.102 (authenticated as YIlyaA), uv 0.13.1, python 3.15, pnpm 10, node 25, pre-commit 4.7, jq 1.8.2, docker 29.8 | `--version` output; `gh auth status` → logged in |
| Gaps in toolchain | Docker daemon not running (not needed here); ruff, mypy, pytest not installed yet (installed per project through uv) | `docker info` failed |
| Hardware | Apple M1, 8 GB RAM | `sysctl`; sets the parallel cap below |
| Existing agent files | None in this folder | n/a |

## 2. Answers from the user (Phase 0, question 4)

| Question | Answer |
|---|---|
| Purpose | Agent environment repo: skills, agent templates, hooks, metrics across projects. Python stdlib scripts plus markdown |
| Definition of done | Checks green, separate verifier passes, PR merged by the human |
| Deploy target | None for now. Deployment frequency is counted as merges to `main` |
| Budget per task | 30 min and $5. The agent stops and reports when it hits either |
| Never touch | Live `~/.claude/` and every repo outside `ENV_AGENTS` (including `AI_AGENTS_ANALYSE/`). Agents read them but never write. Installing into them is done by hand |
| Will not delegate | Merge to `main`; changes to guardrails (permissions, hooks, deny rules); approving plans and `est_hours_old_way` |
| Kinds of work | Code, text/docs, data/metrics, market analysis |

## 3. Decisions

### D1. ENV_AGENTS becomes the versioned home of the environment
- **Decision summary:** `git init` here. **Copy** (not move) the reference design in: `DESIGN.md`, `METRICS.md`, `scripts/git_metrics.py`, `templates/`, `skills/bootstrap/`, `docs/baseline.md`, `docs/experiment.md`. The original folder stays untouched.
- **Justification:** the global skill currently points into a folder with no history, so a bad edit cannot be reverted and no metric can be measured on it. Reusing the files follows "reuse it, do not reinvent it".
- **Evidence:** `work-environment-repo` has no `.git`; the symlink is shown above.
- **Assumptions:** you will later re-point the symlink by hand (`ln -sfn …/ENV_AGENTS/skills/bootstrap ~/.claude/skills/bootstrap`). Agents never touch `~/.claude/`.

### D2. Stack: Python stdlib for runtime, uv only for dev tools
- **Decision summary:** `pyproject.toml` with no runtime dependencies and a dev group (`ruff`, `mypy`, `pytest`), managed by `uv`. `pre-commit` runs ruff, ruff-format, mypy, trailing whitespace and detect-secrets.
- **Justification:** the scripts (metrics report, hook logger, validators) must run anywhere with `python3`, and the default toolchain row for Python asks for exactly these checks.
- **Assumptions:** Python 3.12+ is enough; I'll pin `requires-python = ">=3.12"` so the scripts don't depend on 3.15-only features.

### D3. GitHub remote for PRs (needs your action)
- **Decision summary:** your definition of done needs PRs. I'll propose `gh repo create ENV_AGENTS --private --source . --remote origin`, but **you** run it and do the first push of `main`. The global hook blocks agents from pushing to `main`, and creating a remote is outward-facing.
- **Assumptions:** private is fine. CI (GitHub Actions) comes later, in the 60-day bucket, not in this bootstrap.

### D4. Guardrail files are drafted by me and applied by you
- **Decision summary:** I write `.claude/settings.json` (deny rules, allowed check commands, event-log hooks) as a diff for GATE 2. Changing guardrails is on your will-not-delegate list, and auto mode already blocked me from editing `~/.claude/settings.json`. So if auto mode also blocks the project file, you apply it with one `cp`.
- **Evidence:** auto mode returned "Self-Modification" denials earlier in this session.

### D5. Baseline from two sources
- **Decision summary:** use your existing production baseline (`docs/baseline.md`, copied from the reference design) for git-level numbers, plus 2–3 tasks in this repo done the old way and timed, to calibrate `est_hours_old_way`.
- **Justification:** this repo has no history, so its git metrics would be empty. The production baseline is your real number, about 2.4–2.7x per active day after 2026-08.
- **Assumptions:** task difficulty in this repo is close enough to compare. The report states the sample size and gives a range, not a single ratio.

### D6. Parallel cap: 3 builders
- **Justification:** 8 GB RAM. Each Claude Code session plus a worktree with tests stays under about 1 GB, and the planner, verifier, editor and browser need the rest. Raise the cap only if review wait and change failure rate stay flat.

### D7. Budget is documented, then checked after the fact
- **Decision summary:** the task template gets `budget_minutes: 30` and `budget_usd: 5`. The builder stops at the time cap. Cost is checked afterwards with `npx ccusage`.
- **Assumption / `<TODO>`:** there is no hard $ enforcement in interactive sessions yet. It's listed as a gap, not claimed as done.

### D8. Skill-routing rows
All four kinds of work were selected, so `AGENTS.md` gets these rows from `references/skill-routing.md`: Text for people, Market and competitor analysis, Planning, Building, Verifying and shipping, Context and handoff. Python is the only stack row (no TS).

### D9. Amendment (2026-10-16, during GATE 2): public repo, environment setup for any project on any OS
- **Decision summary:** the repo is public and must set up the agent environment for a project on macOS, Linux and Windows. One runtime everywhere: **Python ≥ 3.12 stdlib, run through `uv`** (uv ships native installers for all three OSes). No bash, jq, `ln -s` or `python3` in any command an agent or user must run.
- **Changes:**
  1. `scripts/check.sh` → `scripts/check.py`. The one command everywhere is `uv run python scripts/check.py`.
  2. Every `python3 …` → `uv run python …` (on Windows, `python3` is usually missing or the Store stub).
  3. The global git guardrail is ported from bash+jq to `hooks/block_dangerous_git.py` (stdlib, with tests), shipped in this repo.
  4. `scripts/install.py` installs into `~/.claude/`: copies `skills/bootstrap` and the hook (a copy, not a symlink, because Windows symlinks need admin or developer mode) and merges the hook into `~/.claude/settings.json` with a backup. `--dry-run` is the default. **The human runs it**; agents never write to `~/.claude/`.
  5. `docs/setup.md`: the toolchain install per OS (macOS `brew`, Linux `apt`/`dnf` plus the uv installer, Windows `winget`; Git for Windows is required by Claude Code on Windows).
  6. `.gitattributes` (`* text=auto eol=lf`) so Windows checkouts don't break the scripts or tests.
  7. **CI moved up from the 60-day bucket:** GitHub Actions runs `scripts/check.py` on `ubuntu-latest`, `macos-latest` and `windows-latest`. Public repos get free minutes. This proves the cross-OS claim instead of asserting it.
  8. Machine-specific bits are removed. The `AI_AGENTS_ANALYSE` deny rule moves out of project settings and into your own `settings.local.json`. `skills/bootstrap` stops pointing at the old reference folder, because this repo is now the reference.
  9. The `/bootstrap` toolchain check becomes OS-aware: it detects the OS and proposes install commands for it. `jq` becomes optional, since Python reads the JSONL.
- **Justification:** a public "env setup for every OS" claim that only runs on macOS would fail on its first outside user. CI on three OSes is the cheapest evidence.
- **Evidence:** `grep` found 12 files with Unix-only commands or a machine-specific path (Phase 2 review, 2026-10-16).
- **Assumptions:** Windows users run Claude Code with Git for Windows installed, which Claude Code requires. WSL also works and behaves like Linux. Claude Code hook commands run in a shell where `uv` is on PATH.

## 4. File tree to create (Phase 2 and 3, after the gates)

```
ENV_AGENTS/
├── .gitignore                         # ignore .venv, __pycache__, .env*, worktrees
├── .pre-commit-config.yaml            # ruff, ruff-format, mypy, whitespace, detect-secrets (D2)
├── pyproject.toml                     # stdlib runtime; dev group ruff/mypy/pytest; tool configs (D2)
├── README.md                          # what this repo is, how to install the skill (adapted from reference README)
├── AGENTS.md                          # single source of truth: commands (verified), workflow, autonomy ladder, never-run, routing
├── CLAUDE.md                          # "See AGENTS.md" + Claude-only notes (worktrees, parallel cap 3)
├── CONTEXT.md                         # purpose, ~10-line architecture, data flow, glossary, current state
├── DESIGN.md                          # copied from reference (D1)
├── METRICS.md                         # copied; add the active-minutes rule (gaps >10 min count as 10)
├── .claude/
│   ├── settings.json                  # deny destructive/secrets, allow check commands, event hooks (D4)
│   ├── agents/planner.md              # from template, commands and paths adapted
│   ├── agents/builder.md              # from template; worktree isolation, 30 min stop
│   ├── agents/verifier.md             # from template; fresh context, runs `make check`-style command
│   ├── hooks/log_event.py             # appends {timestamp, session_id, event, branch} to events.jsonl; never prompt text
│   └── skills/
│       ├── plan-task/SKILL.md         # goal → tasks/T-xxx.md with frozen estimate, blocked_by, parallel_ok
│       ├── implement-task/SKILL.md    # tests first, scope check, real output into the task log
│       ├── verify-diff/SKILL.md       # checks + code-review skill against the task file
│       └── release/SKILL.md           # PR → human merge → tasks.csv row → metrics report → release-evidence
├── skills/bootstrap/                  # copied global skill, now versioned (D1)
├── templates/                         # copied (task-log, weekly-report, post-mortem) (D1)
├── tasks/_template.md                 # from templates/task.md + budget fields (D7)
├── docs/
│   ├── bootstrap-plan.md              # this file
│   ├── baseline.md                    # copied production baseline + section for local old-way tasks (D5)
│   ├── experiment.md                  # copied
│   ├── agent-readiness.md             # Phase 4 score with file:line evidence
│   ├── release-evidence.md            # verified things only (command, output, date)
│   └── decisions/0001-stack-and-layout.md   # D1 + D2 as the first decision record
├── scripts/
│   ├── git_metrics.py                 # copied unchanged (D1)
│   └── metrics_report.py              # stdlib; daily/weekly report from tasks.csv + events.jsonl + git
├── tests/
│   ├── test_metrics_report.py         # active-minutes rule, multiplier, median/p90, empty input
│   └── test_log_event.py              # writes one valid JSON line, never includes prompt text
└── session-log/
    ├── tasks.csv                      # header from the skill
    └── events.jsonl                   # created by the hook (gitignored or committed: decided at GATE 3)
```

No `prompts/` folder yet. There's no repeated prompt, so creating one would be speculative.

## 5. Gaps against the Phase 4 readiness checklist (today)

| Check | Today | After bootstrap (target) | How |
|---|---|---|---|
| AGENTS / CLAUDE / CONTEXT | 0 | 2 | Phase 2.1–2.3, commands verified by running them |
| Skills and routing | 0 | 2 | 4 repo skills + routing table |
| Tests on critical logic | 0 | 2 | pytest for metrics_report and log_event; one command |
| Delegation seams | 0 | 2 | task template + autonomy level per work type |
| Guardrails | 1 (global hook only) | 2 | project settings + pre-commit; CI later |
| Verification | 0 | 2 | verifier agent with fresh context |
| Measurement | 0 | 2 | hooks + report + baseline |
| Decision traceability | 0 | 2 | `docs/decisions/` |

Target: **16/16**. Guardrails could stay at 1–2 until CI exists, so a realistic floor is 14/16.

## 6. Proposed autonomy per kind of work (for AGENTS.md)

| Work | Level | Why |
|---|---|---|
| Docs, skills text, research notes | L2 | Low risk, reviewed in PR |
| Scripts and tests | L2 | Tests decide; verifier reviews |
| Metrics data (`tasks.csv`) | L1 | Agent proposes the row; you confirm the frozen estimate |
| Guardrails (`.claude/settings.json`, hooks) | L1 | Will-not-delegate: agent drafts, you apply |
| Anything in `~/.claude/` or other repos | L0 | Read only |

## 7. Order of work after approval (Pareto)

1. **GATE 2 – agent layer:** git init, copies (D1), AGENTS/CLAUDE/CONTEXT, agents, task template, 4 skills, settings draft, pyproject + pre-commit. Then the diff summary.
2. **GATE 3 – measurement:** hook logger, tasks.csv, metrics_report.py with tests, baseline section. Then the real report output.
3. Phase 4 score → Phase 5 first real loop (proposed first task: "metrics_report prints week-over-week change", small and testable).

Estimated effort for you: about 15 min reviewing at each gate, plus the `gh repo create` / first push (D3).

---
Reply **`approved`** to start Phase 2, or name the decisions you want changed.
