# 0001: Versioned environment repo, stdlib runtime, uv dev tools

- Date: 2026-10-16
- Status: accepted (GATE 1, docs/bootstrap-plan.md D1–D2)
- Value stream: Risk

## decision_summary
Agents Workbench (local folder `ENV_AGENTS`) is a git repo holding a copy of the reference design (`AI_AGENTS_ANALYSE/work-environment-repo`). Runtime scripts use the Python stdlib only; `uv` manages dev tools (ruff, mypy, pytest) and `pre-commit` runs them.

## justification
- The global `/bootstrap` skill pointed into a folder with no git history: a bad edit could not be reverted and changes could not be measured. A versioned copy fixes both. Copy rather than move, because agents must not write outside this repo.
- Stdlib-only scripts run in any project with `python3`, so other repos do not need to install anything to use the metrics. Rejected: a pip package (install friction), TypeScript (my main stack is Python).
- PPT: People: me only. Process: every change to the environment now goes through task → verifier → PR. Technology: git, uv, pre-commit.

## evidence
- `work-environment-repo` has no `.git` directory; `~/.claude/skills/bootstrap` is a symlink into it (Phase 0, docs/bootstrap-plan.md §1).
- `diff -rq` between the reference and `skills/bootstrap/` showed no differences after the copy.
- `scripts/git_metrics.py` was reformatted by `ruff format` during setup. Comparing `ast.dump` of the original and the copy gave `AST identical (formatting only): True`, so its behavior is unchanged.

## assumptions
- I re-point `~/.claude/skills/bootstrap` to this repo by hand; until then the two copies can drift.
- Python ≥ 3.12 is available where the scripts run. Revisit if a project pins an older Python.
