# Setup on macOS, Linux and Windows

One runtime everywhere: Python 3.12+ through `uv`. Every command in this repo is `uv run python …`, so it is the same on all three systems.

## 1. Install the toolchain

| Tool | Why | macOS | Linux (Debian/Ubuntu; Fedora in brackets) | Windows (PowerShell) |
|---|---|---|---|---|
| git | worktrees, history | `brew install git` | `sudo apt install git` (`sudo dnf install git`) | `winget install Git.Git` (Claude Code needs Git for Windows) |
| uv | Python + dev tools | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `winget install astral-sh.uv` |
| gh | PRs, `/to-tickets` | `brew install gh` | `sudo apt install gh` (`sudo dnf install gh`) | `winget install GitHub.cli` |
| Claude Code | the agents | see [the official install page](https://code.claude.com/docs/en/setup) | same | same |
| pre-commit | commit-time checks | `uv tool install pre-commit` | same | same |
| docker | only if a project needs services | Docker Desktop | `docker.io` / Docker Engine | Docker Desktop (WSL 2 backend) |

`uv` downloads Python itself if none is installed. `jq` is optional; the scripts read JSON with Python.

Then authenticate: `gh auth login`.

WSL on Windows behaves like Linux; use the Linux column inside it.

## 2. Get the repo and check it

```
git clone https://github.com/YIlyaA/agent-workbench.git
cd agent-workbench
uv sync
uv run python scripts/check.py
```

The last line must be `ALL CHECKS PASSED`.

## 3. Install into Claude Code (global)

```
uv run python scripts/install.py           # dry run: shows every change
uv run python scripts/install.py --apply   # copies the skill and the git guardrail hook into ~/.claude
```

Existing files are backed up with a `.bak-<timestamp>` suffix. Restart Claude Code afterwards.

## 4. Use it in a project

Open Claude Code in the project folder and run `/bootstrap` as the first message. It works in gated phases and stops for your `approved` at each gate.
