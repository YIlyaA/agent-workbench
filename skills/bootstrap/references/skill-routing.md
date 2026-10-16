# Standard skill routing

Which skill to use for which kind of work. Copy the relevant rows into the project's `AGENTS.md` routing table and drop the rows the project will not use.
`/name` means the skill is user-invoked only (`disable-model-invocation`): the agent asks me to run it rather than calling it itself.

## Text for people (docs, posts, emails, README, reports)

1. Write the draft.
2. `humanizer`: remove AI-writing patterns.
3. `watermarks-remover:remove-ai-marks`: strip hidden characters and AI watermarks (`watermarks-remover:clean-user-facing-text` for UI strings).
4. Long articles: `/edit-article` for structure.

## Market and competitor analysis

1. `research` (or `anthropic-skills:deep-research` for broad questions): primary sources only, findings saved to a markdown file with links.
2. `marketing-skills:competitor-profiling`: one profile per competitor URL.
3. `solo-founder-superpowers:market-research`: market size and segments; give conservative, expected and optimistic scenarios.
4. Score the opportunity with PPT × Revenue/Risk/Cost (1–10 per cell, max 90: 75+ strong, 55–74 promising, 35–54 marginal, under 35 weak).
5. Stress-test before committing: `grilling`, using red-team questions (what kills this, who says no, what is assumed).
6. Output: a decision record with justification, evidence, assumptions.

## Planning a feature or project

1. Sharpen the goal: `/grill-with-docs` (writes ADRs and glossary as it goes) or `/grill-me`.
2. Domain terms: `domain-modeling` or `ubiquitous-language`.
3. Diagrams (Mermaid, kept in `docs/diagrams/`): system context, the main sequence flow, a state machine for anything with a lifecycle, a data model. For larger systems use `engineering:system-design` or `engineering:architecture`.
4. Edge cases: a table `| Case | Input or state | Expected behavior | Test |` covering empty, maximal, invalid, concurrent, partial failure, retry or duplicate, permissions, time zones or dates, and money rounding where relevant.
5. Spec: `/to-spec`. Tickets: `/to-tickets` (tracer bullets with blocking edges). Work bigger than one session: `/wayfinder`.
6. Order the tickets with Pareto inside 30/60/90 buckets.
7. Unsure about a design: `prototype`, a throwaway build that answers one question.

## Building

- `tdd`: tests first for any behavior change.
- `/implement`: execute a spec or tickets.
- `codebase-design` / `design-an-interface`: module and interface shape.
- `diagnosing-bugs`: hard bugs and regressions.
- `/improve-codebase-architecture`: periodic deepening pass.

## Verifying and shipping

- `code-review`: standards plus spec, run by the verifier agent with fresh context.
- `security-review`: anything touching auth, input parsing, secrets or payments.
- `engineering:deploy-checklist` before a release, then update `docs/release-evidence.md`.
- Once per repo: `git-guardrails-claude-code`. Pre-commit hooks: for JS/TS repos use `setup-pre-commit` (Husky + lint-staged); for Python use the `pre-commit` framework with the hooks from the toolchain below.

## Default toolchain

The fewest tools that give fast, verifiable feedback. Add more only when a task needs them.

| Stack | Env and deps | Lint and format | Types | Tests | Hooks |
|---|---|---|---|---|---|
| Python / Django | `uv` (lockfile, venv) | `ruff check` + `ruff format` | `mypy` (+ `django-stubs`) | `pytest` + `pytest-django`, `pytest-cov` | `pre-commit` (ruff, mypy, trailing whitespace, detect-secrets) |
| TypeScript / Node | `pnpm` or `npm` | `eslint` + `prettier` (or `biome`) | `tsc --noEmit` | `vitest` | Husky + lint-staged |
| Any | `git` worktrees, `gh` (authenticated), Docker Compose for services | | | | `git-guardrails-claude-code` |

Also: Mermaid for diagrams (`docs/diagrams/*.mmd`), `graphify` for large codebases, Python (or optional `jq`) for logs.

## Context and handoff

- `graphify`: knowledge graph of a large codebase or corpus; query it before reading files.
- `handoff`: compact a long session for the next agent.
- `/writing-great-skills`: when creating or editing a skill.
