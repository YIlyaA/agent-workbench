---
id: T-001
status: ready-for-review  # draft | approved | in-progress | ready-for-review | done | rejected
risk: medium             # low | medium | high  (medium and high: human approves each risky command)
autonomy: L1             # guardrail code: builder implements after approval, human applies settings change and merges
type: bugfix             # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 250
est_hours_old_way: 3     # confirmed by the human 2026-10-16; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true
---

# Git guardrail hook: evaluate each command segment on its own

## Goal
Stop false positives in `hooks/block_dangerous_git.py` without weakening it. Today the regexes run over the whole Bash string, so `.*` spans `&&` into the next command and text inside heredocs or quoted arguments is matched. Two real blocks on 2026-10-16:

1. `git push -q -u origin docs/rename-agents-workbench && gh pr create --base main ...` was blocked as "push to main/master".
2. `cat > f <<'EOF' ... "Bash(git push origin main *)" ... EOF` (writing a JSON file) was blocked.

Traces to the guardrails objective in `AGENTS.md`: the hook must block real dangerous git calls and nothing else, or agents and the human learn to route around it.

## Preconditions (human, before the builder starts)
- [ ] Set `status: approved` and confirm `est_hours_old_way`.
- [ ] Temporarily remove the single line `"Edit(./hooks/**)",` from the `deny` list in the project `.claude/settings.json` (currently line 23). Leave `"Edit(./.claude/hooks/**)"` in place. Agents may not do this themselves.
- [ ] After merge: restore that exact line and confirm `.claude/settings.json` matches `main` (`git diff main -- .claude/settings.json` is empty).
- [ ] After merge: run `uv run python scripts/install.py` (dry run), then `--apply`, so the global copy in `~/.claude` picks up the fix. Until then the old hook stays active everywhere.

## Scope (paths the builder may touch)
- `hooks/block_dangerous_git.py`
- `tests/test_block_dangerous_git.py`

Nothing else. If another path is needed, stop and ask.

## Approach (REVISED 2026-10-16 after verifier FAIL; human chose "invert the design")

Attempt 1, a parser that allows whatever it does not understand, failed verification: 8 findings and regressions against the old hook (see Log). Revised rule: **the old regex stays the judge. A command the old patterns flag is allowed only when one of two narrow, provable exceptions applies. Anything unusual stays blocked.**

1. `legacy_reason(cmd)`: the old patterns, unchanged in what they block. Extend only so that git global options before the subcommand are also caught: `git -C <dir> push --force`, `git -c k=v push -f`, `git --git-dir=x push origin main`. More blocking is allowed; less is not.
2. `blocked_reason(cmd)`:
   - `legacy_reason` is None → None.
   - Exception A or B applies → None.
   - Otherwise → the legacy reason.
3. **Exception A, a quoted heredoc written to a file.** The whole command must exactly match one line `cat` or `tee`, optionally `-a`, a redirect or path made only of `[\w./-]` characters, and `<<'WORD'` or `<<"WORD"` (a quoted literal `\w+` delimiter, so the shell does not expand the body), then the body, then a line that is exactly `WORD`, and then **nothing after it** (trailing whitespace only). The first line, without the heredoc operator, must be clean under `legacy_reason`. An unquoted delimiter (`<<EOF`, `<<\EOF`, `<<E"O"F`) is never an exception.
4. **Exception B, chained commands where the match crosses commands.** Tokenize with `shlex.shlex(cmd, posix=True, punctuation_chars="();<>|&\n")`, so an unquoted newline separates commands. Any tokenizer error means no exception. There is also no exception if the raw command contains `$`, a backtick, `<<`, `<(`, `>(`, a backslash before a newline, or a token `(` or `)`. Split segments on `&&`, `||`, `;`, `|`, `&` and newline tokens. Every segment's first token must be in `SAFE_FIRST = {"git", "gh", "echo", "printf", "cd", "ls", "pwd", "true"}`. For each `git` segment, run `legacy_reason` on its tokens joined by spaces; any hit means no exception. Segments that start with anything else in `SAFE_FIRST` are inert text. A pipe into any command not in `SAFE_FIRST` (`| bash`, `| sh`) fails the first-token rule, so it stays blocked.
5. **Input cap:** if `len(cmd) > MAX_LEN` (100_000), return a block reason when `git` appears in it, otherwise None. This stops the 71 s regex stall.
6. Malformed hook JSON still exits 0. Stdlib only. Target diff is **at most 150 lines**.

## Acceptance criteria
- [ ] Both real false positives from the Goal pass (exit 0).
- [ ] Every row in the edge-case table is a parametrized test and passes.
- [ ] All cases already in `tests/test_block_dangerous_git.py` keep their current result (no row moves from BLOCKED to ALLOWED).
- [ ] `blocked_reason` never raises for any `str` input (test with a short fuzz list: lone quotes, lone `<<`, `$(`, `` ` ``, `\`, very long input).
- [ ] Hook process: exit 2 + `BLOCKED` on stderr when blocked; exit 0 and empty stderr when allowed; exit 0 on malformed JSON (existing tests).
- [ ] Stdlib only; no shell, no `os.sep` assumptions; ruff and mypy clean.
- [ ] Diff at most 250 lines across both files.
- [ ] `uv run python scripts/check.py` passes.

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| Real FP 1: push then PR to main | `git push -q -u origin docs/rename-agents-workbench && gh pr create --base main --title x` | Allowed | `ALLOWED` param |
| Real FP 2: heredoc body | `cat > f <<'EOF'` / `{"allow": ["Bash(git push origin main *)"]}` / `EOF` (newline separated) | Allowed | `ALLOWED` param |
| Quoted arg to echo | `echo "git push -f"` | Allowed | `ALLOWED` param |
| Quoted arg to gh | `gh pr create --base main --body "merge to main after git push --force review"` | Allowed | `ALLOWED` param |
| Quoted arg to grep | `grep -rn "git reset --hard" docs/` | Allowed | `ALLOWED` param |
| Git message mentions push | `git commit -m "never git push -f to main"` | Allowed (subcommand is `commit`) | `ALLOWED` param |
| Tab heredoc `<<-` | `cat <<-EOF` / `\tgit push -f origin main` / `\tEOF` | Allowed | `ALLOWED` param |
| Heredoc then real command | `cat > f <<'EOF'` / `x` / `EOF` / `git push -f` | Blocked (force push) | `BLOCKED` param |
| Unquoted heredoc runs substitution | `cat <<EOF` / `$(git push -f)` / `EOF` | Blocked (fail-safe: shell executes it) | `BLOCKED` param |
| Branch name contains main | `git push origin feature/main-menu` | Allowed | existing `ALLOWED` |
| Branch name starts with main | `git push origin main-fix` | Allowed | `ALLOWED` param |
| Normal feature push | `git push -u origin my-branch` | Allowed | existing `ALLOWED` |
| Checkout main (not a push) | `git checkout main` | Allowed | existing `ALLOWED` |
| Segment after cd | `cd x && git push -f` | Blocked (force push) | `BLOCKED` param |
| Env var prefix | `GIT_TRACE=1 git push --force` | Blocked (force push) | `BLOCKED` param |
| Shell interpreter string | `bash -c "git push -f"` | Blocked (force push) | `BLOCKED` param |
| Interpreter, combined flag, nested segments | `sh -lc 'cd x && git push origin main'` | Blocked (push to main/master) | `BLOCKED` param |
| eval | `eval "git reset --hard"` | Blocked (reset --hard) | `BLOCKED` param |
| Command substitution | `echo "$(git push -f)"` | Blocked (force push) | `BLOCKED` param |
| Refspec to main | `git push origin HEAD:main` | Blocked (push to main/master) | `BLOCKED` param |
| Refspec main:main | `git push origin main:main` | Blocked (push to main/master) | `BLOCKED` param |
| Full ref name | `git push origin refs/heads/main` | Blocked (new: not caught today) | `BLOCKED` param |
| Force via `+` refspec | `git push origin +x` | Blocked (force push) | existing `BLOCKED` |
| Short flag cluster | `git push -fu origin x` | Blocked (new: not caught today) | `BLOCKED` param |
| Git global option `-C` | `git -C repo push --force` | Blocked (new: not caught today, regex needs `git\s+push`) | `BLOCKED` param |
| Git global option `-c` | `git -c core.pager=cat push -f` | Blocked (new) | `BLOCKED` param |
| Absolute path / Windows exe | `/usr/bin/git push -f`; `git.exe push --force` | Blocked | `BLOCKED` param |
| Wrapper command | `env FOO=1 git push -f`; `nohup git clean -fd` | Blocked | `BLOCKED` param |
| Other separators | `ls; git reset --hard`; `git status \|\| git branch -D x`; `git status & git push -f`; `true \| git clean -fd` | Blocked | `BLOCKED` param |
| Newline separator | `git status` + newline + `git push -f` | Blocked (force push) | `BLOCKED` param |
| Line continuation | `git push \` + newline + `--force` | Blocked (force push) | `BLOCKED` param |
| Subshell parens | `(cd x && git push -f)` | Blocked (force push) | `BLOCKED` param |
| Shell comment | `git status # git push -f` | Allowed | `ALLOWED` param |
| Empty command | `""` | Allowed, no exception | existing `ALLOWED` |
| Only whitespace | `"   \n\t  "` | Allowed, no exception | `ALLOWED` param |
| Unterminated quote, dangerous | `git push -f "oops` | Blocked via legacy-regex fallback, no exception | `BLOCKED` param |
| Unterminated quote, harmless | `echo "hello` | Allowed, no exception | `ALLOWED` param |
| Unterminated heredoc | `cat <<EOF` + newline + `git push -f` (no terminator) | Allowed (shell treats the rest as body); no exception | `ALLOWED` param |
| Maximal input | 200 KB command of repeated `echo a && ` ending in `git push -f` | Blocked, returns in under 1 s | `test_large_input` |
| Deep interpreter nesting | `bash -c "bash -c \"...\""` past depth limit with `git push -f` inside | Blocked (fallback to legacy regex past limit) | `BLOCKED` param |
| Invalid input to hook | stdin `""`, `not json`, `[]`, `{"tool_input": null}`, non-string command | Exit 0 | existing `test_hook_malformed_input_does_not_block` |
| Unexpected parser error | monkeypatched tokenizer raises `RuntimeError` on `git push -f` | Blocked via whole-command legacy regex | `test_internal_error_falls_back` |
| Retry / duplicate | same command evaluated twice | Same result both times (pure function, no state) | covered by parametrized tests |
| Concurrent | many hook processes at once | No shared state, no files read or written; no interaction | n/a (by design, note in review) |
| Permissions | hook runs as a plain user | Reads only stdin; needs no file or network access | n/a |

## Test plan
- Extend `BLOCKED` and `ALLOWED` lists in `tests/test_block_dangerous_git.py` with every row above. Use `"\n".join([...])` for multi-line commands so the file stays cross-platform.
- Add `test_large_input`, `test_internal_error_falls_back`, and a small no-raise fuzz test.
- Write the tests first and confirm the two real false positives and the three "new" cases fail for the right reason before changing the hook.
- Command: `uv run python scripts/check.py`.
- Security: verifier runs `security-review` (this touches a guardrail). The verifier should try to find a dangerous command that now passes.

## Builder notes
- The old hook is still active in your session. Run `git push -u origin T-001-...` and `gh pr create --base main ...` as two separate Bash calls, or the hook will block you with the bug this task fixes.
- If the design does not fit in 250 lines, stop and report. Do not drop fail-safe cases to fit.

## Planning notes
- People / Process / Technology: the human loses time on false blocks and is tempted to weaken the rule; process needs a temporary settings change (precondition); technology is a tokenizer instead of whole-string regex.
- Pareto: per-segment splitting plus heredoc stripping fixes both observed false positives. Interpreter recursion, `$(...)` and git global options are the extra 20% that keeps the hook from getting weaker.
- Revenue / Risk / Cost: no revenue impact. Risk is the main concern: a parser can miss a dangerous form that the old regex caught. The fallbacks and the "no existing BLOCKED case changes" criterion cover this. Cost: one builder session.

## Log (filled in by the builder and verifier)
- Start / end: 2026-10-16 13:47 / 14:06 local (includes a pause from 13:51 while the human reviewed a rejected write)
- Diff size: 306 lines changed across the two files (hook +228 net, tests +79), over the 250 limit; flagged to the human, no fail-safe cases dropped. Split proposal: (1) per-segment + heredoc + quoting core, (2) interpreter/wrapper/substitution recursion.
- Tests-first: before the hook change 22 new cases failed for the expected reasons (both real false positives and the "new" cases).
- Checks run (command and real output): `uv run python scripts/check.py`
  ruff check: All checks passed! / ruff format: 52 files already formatted / mypy: Success: no issues found in 15 source files / pytest: 137 passed in 1.51s / agent layer: OK / ALL CHECKS PASSED
- Verifier verdict and findings (2026-10-16, fresh context + security review): **FAIL**, 8 findings (1 blocker, 4 major, 3 minor). First pass not green.
  - Blocker: a heredoc delimiter written `<<\EOF`, `<<E"O"F` or `<<"E"OF` is parsed wrong, so nothing after it is checked (`hooks/block_dangerous_git.py:39`, `:83`).
  - Major: `$(...)#` is treated as a comment (`:125`); wrappers not on the list (`stdbuf`, `caffeinate`, `find -exec`, `sudo -u git`) hide git (`:33`, `:216-229`); interpreter flags are missed (`bash -c --`, `eval --`, `cmd /C`, `pwsh -NonInteractive -Command`, `fish --command`); code piped into a shell (`echo … | bash`) or run by `python3 -c` / `node -e` is not checked.
  - Minor: `$'...'` quoting and `<<` inside `(( ))` confuse the scanner; the old-regex fallback takes 71 s on 200 KB of input; the diff is 306 lines against a limit of 250.
  - Root cause: when the parser meets something it does not model, it allows the command instead of falling back to the old regex.
- Attempt 2 (revised approach: old regex judges, exceptions A and B), 2026-10-16 14:14 to 14:21 local. Every verifier regression command is now a BLOCKED test; the two real false positives and the multi-line commit-then-push-then-PR chain are ALLOWED tests. Rows that went back to BLOCKED (acceptable false positives, marked in the tests): grep of a dangerous string, `git commit -m "...git push -f..."`, unquoted `<<-` heredoc, trailing `# git push -f` comment, unterminated heredoc. Extra change: the regexes are split into head and tail searched per line, because the single `.*` form took 18 s on 100 KB with many `git push` words (quadratic); now 0.04 s. `uv run python scripts/check.py` tail: ruff check: All checks passed! / ruff format: 52 files already formatted / mypy: Success: no issues found in 15 source files / pytest: 174 passed in 0.73s / agent layer: OK / ALL CHECKS PASSED
- Human review (minutes, notes):
