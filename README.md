# Agents Workbench

Agent environment setup for any project, on any OS: the `/bootstrap` skill, agent roles, guardrails and the metrics that show whether it makes me faster.

- [DESIGN.md](DESIGN.md): who does what, where a human approves, what stops an agent from doing damage.
- [METRICS.md](METRICS.md): what "10x" means in numbers and how it is measured.
- [AGENTS.md](AGENTS.md): rules for any agent working here. [CONTEXT.md](CONTEXT.md): the map.

## Quick start

```bash
uv sync
uv run python scripts/check.py
```

Works the same on macOS, Linux and Windows (CI checks all three). Toolchain per OS: [docs/setup.md](docs/setup.md).

## Install into Claude Code

```bash
uv run python scripts/install.py           # dry run
uv run python scripts/install.py --apply   # copies the /bootstrap skill and the git guardrail hook into ~/.claude
```

Then run `/bootstrap` as the first message in any project.

## License

[MIT](LICENSE)
