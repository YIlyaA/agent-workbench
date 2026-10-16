# 0002: Merges and guardrail changes move from human-only to approve-to-execute

- Date: 2026-10-16
- Status: accepted (requested by the human in session, 2026-10-16)
- Value stream: Cost

## decision_summary
Merging PRs, editing guardrail files and installing into `~/.claude/` move from `deny` (human does it by hand) to `ask` in `.claude/settings.json`. The agent does them when the human asks for that specific action. Claude Code then shows a permission prompt, and the action only runs if the human accepts it.

## justification
- The human had to paste commands for every merge and settings change. That cost more human minutes than reviewing the work, which hurts the multiplier this repo exists to measure.
- Rejected: "do whatever I say, even against the rules". If one sentence can switch every rule off, the same sentence in a PR comment, file or web page becomes dangerous, and this repo is public. Auto mode's own self-modification check also cannot be lifted by a rule.
- `ask` keeps the human as the only one who can approve, because only the human can accept the prompt. Text cannot accept it.
- Kept as `deny`: reading secrets, and direct pushes to `main`. Merging through a PR does the same job, and CI checks it on three OSes first.

## evidence
- Before this change, 4 of today's steps needed the human to paste commands: settings applied twice, the PR merges, and the install.
- Claude Code docs (permissions): rules are evaluated deny → ask → allow, and `ask` always prompts.

## assumptions
- The permission prompt still appears in auto mode for `ask` rules. Verify this the first time an `ask` action runs, and record the result in `docs/release-evidence.md`.
- Revisit if an `ask` action is ever accepted by mistake. Moving it back to `deny` is a one-line change.
