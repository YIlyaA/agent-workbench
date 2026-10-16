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

## Approach (recommended, builder may refine)
Keep `blocked_reason(command: str) -> str | None` as the public function; tests and `main()` already use it. Stdlib only (`re`, `shlex`, `json`, `sys`, `os.path`/`pathlib` for basename), Python 3.10+ typing, no OS-specific code.

1. **Pre-pass.** Join backslash-newline continuations. Remove heredoc bodies: for each `<<` / `<<-` with delimiter `WORD`, `'WORD'` or `"WORD"`, drop the lines up to the terminator line (leading tabs allowed for `<<-`). For an unquoted delimiter, keep any `$(...)` and backtick bodies from the dropped lines as extra segments, because the shell runs them.
2. **Tokenize** with `shlex.shlex(text, posix=True, punctuation_chars=True)`, `whitespace_split=True`, `commenters="#"`. Split segments on the operator tokens `&&`, `||`, `;`, `|`, `&`, `(`, `)`, and on newlines (split lines before tokenizing, so newlines are separators).
3. **Command substitution.** Extract `$(...)` and backtick bodies from unquoted and double-quoted text and evaluate each as its own command. Single-quoted text is never executed, so it is skipped.
4. **Per segment:** skip leading `NAME=value` assignments and wrappers (`env`, `command`, `exec`, `nohup`, `time`, `sudo`, `xargs`). If argv[0] is a shell interpreter (`bash`, `sh`, `zsh`, `dash`, `ksh`, `fish`, `pwsh`, `powershell`, `cmd`, `eval`) and has a `-c` style flag (`-c`, `-lc`, `-ic`, `/c`, `-Command`, `-command`; for `eval` all args), evaluate the command string recursively (depth limit, for example 5; past the limit fall back to the legacy regex). If the basename of argv[0] is `git` or `git.exe`: skip git global options (`-C <path>`, `-c <k=v>`, `--git-dir=...`, `--work-tree=...`, `--no-pager`, `-P`, `--bare`, ...), take the subcommand and apply the rules to its own args only.
5. **Rules on tokens, not on raw text:**
   - `push`: any of `--force`, `--force-with-lease[=...]`, `--force-if-includes`, `-f`, a short-flag cluster containing `f` (for example `-fu`), or a refspec starting with `+` → "force push". Any refspec whose destination (the part after the last `:`, or the whole refspec if no `:`) is `main`, `master`, `refs/heads/main` or `refs/heads/master` → "push to main/master".
   - `reset` with `--hard`; `clean` with a short-flag cluster containing `f` or `--force`; `branch` with `-D` (or `--delete --force`); `checkout`/`restore` with `.` as the pathspec (optionally after `--`). Same labels as today.
6. **Fail-safe fallback.** If `shlex` raises `ValueError` (unterminated quote, etc.) on a segment, run the legacy `DANGEROUS` regexes on that segment only. If anything else raises inside `blocked_reason`, run the legacy regexes on the whole command. `main()` keeps returning 0 for malformed JSON or a non-string command.

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
- Human review (minutes, notes):
