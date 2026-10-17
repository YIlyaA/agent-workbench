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
| 2026-10-17 | T-003..T-005 built in parallel: max 3 builders at once, 6 subagents at once | `metrics_report.py --transcripts <claude projects dir>` (T-006) | `max concurrent builders: 3 (2026-10-17 10:06-10:07)`, `max concurrent subagents: 6` |
| 2026-10-17 | PRs #11, #13, #14, #12 merged in that order, each with green CI on 3 OSes; #13, #14, #12 needed a merge of main first (task-file add/add conflicts from the shared base commit, no code conflicts) | `gh pr view <n> --json statusCheckRollup,mergedAt` | all SUCCESS; merged 12:36, 12:40, 12:46, 12:47 local |
| 2026-10-17 | The hard diff limit works: it stopped T-008 three times (340/300, 399/350, 407/400); each time the builder stopped without trimming and the human raised the limit on main | `uv run python scripts/check.py` on the T-008 branch; PRs #17, #19, #21 | `diff limit: 407/400 ... FAILED: diff limit`, then `407/420 ... ALL CHECKS PASSED` |
| 2026-10-17 | The CI diff-limit job runs on pull requests | PR #23 checks | `diff-limit=SUCCESS` with `check (ubuntu/macos/windows)=SUCCESS` |
| 2026-10-17 | PRs #18, #20, #22, #23 merged in order with green CI; task files merged first (#16), so no merge conflicts | `gh pr view <n> --json statusCheckRollup,mergedAt` | all SUCCESS; merged 13:50-13:53 local |
