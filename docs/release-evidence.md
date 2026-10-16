# Release evidence

Verified facts only: date, command, real output. Plans and intentions go elsewhere.

| Date | Claim | Command | Output (excerpt) |
|---|---|---|---|
| 2026-10-16 | CI passes on Linux, macOS and Windows for every merged PR (#1–#5) | `gh pr checks <n>` | `check (ubuntu-latest) pass`, `check (macos-latest) pass`, `check (windows-latest) pass` |
| 2026-10-16 | The cross-OS claim is real: Windows-only CI caught a bug that macOS and Linux tests did not (PYTEST_CURRENT_TEST over the 32,767-char env var limit) | PR #5 run 38900664432 | `check (windows-latest) fail` → fixed in `21cd948` → `pass` |
| 2026-10-16 | T-001: the live global hook allows this morning's false-positive chain and still blocks a force push | `git status --short && echo "...--base main" && echo "text: git push origin main"`; `git push -f origin nonexistent-test-branch-xyz` | first: ran and printed both lines; second: `BLOCKED (force push)` |
| 2026-10-16 | T-001: no command the old hook blocked is allowed by the new one, except 7 intended exceptions | old vs new `blocked_reason` on every test command (`cmp.py`) | 7 `old-blocked new-allowed` lines, all in ALLOWED; 0 from BLOCKED |
| 2026-10-16 | **Not verified:** that `ask` rules prompt the human. The PR #4/#5 merges and `install.py --apply` ran while the session was in bypass-permissions mode, which does not show `ask` prompts | session mode notice: "bypass permissions mode is active" | open: see decision 0002 assumptions |
| 2026-10-16 | T-002 is read-only on the target repo | `git rev-parse HEAD` and `git status --porcelain` before and after the run | HEAD same=yes; dirty files before=0, after=0 |
| 2026-10-16 | Calibration: blind planner estimates are about 10 times the commit-visible time | `compare.py` (scratchpad) on 32 tasks | median actual_mid/estimate 0.10 (p25 to p75 0.05 to 0.46); 8 of 32 inside [low, high]; multi-session tasks 0.08, 1 of 10 inside |
| 2026-10-16 | Session log exported and redacted (Phase 6) | `export_session.py` on the Claude Code transcript | 22 human turns; redacted: 48 home paths, 20 other-project names, 19 scratchpad paths; 0 emails/tokens found |
