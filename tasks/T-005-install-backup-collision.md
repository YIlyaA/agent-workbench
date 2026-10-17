---
id: T-005
status: approved # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # installer code, but tests touch only tmp_path; no run against the real home
autonomy: L2             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: bugfix             # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 120
est_hours_old_way: 0.5     # confirmed by the human 2026-10-17; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: []
parallel_ok: true
---

# install.py: backups made in the same second must not collide

## Goal
`scripts/install.py` names backups `<name>.bak-<YYYYmmdd-HHMMSS>`. Two `--apply` runs in the same second collide. A directory rename onto an existing backup fails (or, on POSIX, silently replaces an empty one). A file backup silently overwrites the earlier backup through `shutil.copy2`. The docstring promises "backed up, never deleted". Make that true.

## Scope (paths the builder may touch)
- `scripts/install.py`
- `tests/test_install.py`
- this task file: `status` and the Log section only

Nothing else. Do **not** edit `session-log/tasks.csv` (the orchestrator writes the row after merge).

**Never run `install.py --apply` or `install.py` without `--home` against the real home.** That is an `ask` rule (AGENTS.md autonomy ladder, L2). Tests call `install(REPO, tmp_path, apply=...)` directly, as the existing tests do. Do not call `main()` in tests.

## Specification
- New pure helper `_backup_dest(path: Path, stamp: str) -> Path`. It returns `path.with_name(f"{path.name}.bak-{stamp}")` if that name is free. Otherwise it returns the first free one of `...-1`, `...-2`, and so on.
- A name is **taken** when `candidate.exists() or candidate.is_symlink()`, so a dangling symlink also counts as taken.
- `_backup` calls `_backup_dest(path, _stamp())` once and uses the result for both the action line and the apply step. A dry run therefore prints the same name that `--apply` would use.
- Nothing else in `_backup` changes: symlinks are still unlinked without touching their target, directories are still renamed, files are still copied with `copy2`.
- Update the module docstring: `.bak-<timestamp>` suffix, plus `-N` when that name is taken; never overwritten or deleted.

## Acceptance criteria
- [ ] With `_stamp` monkeypatched to a fixed value and an existing skill dir, two `apply=True` runs leave two directory backups, `bootstrap.bak-S` and `bootstrap.bak-S-1`, each with its own marker file intact.
- [ ] Same for `settings.json`: two backups with the earlier contents intact. To force a settings rewrite, write a settings file without our hook before each run.
- [ ] Each edge-case row below has a test, or is n/a with a reason.
- [ ] Existing tests pass unchanged.
- [ ] Parametrize ids are short (at most 20 characters).
- [ ] Diff at most 120 lines. If you hit the limit, stop and report.
- [ ] `uv run python scripts/check.py` passes.

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| Directory, same second | `_stamp` fixed to `S`; skill dir holds marker `a`; apply; recreate marker `b` in the new skill dir; apply again | `bootstrap.bak-S/` holds `a`, `bootstrap.bak-S-1/` holds `b`; no exception | `test_same_second_dir_backups` |
| File, same second | `_stamp` fixed; settings `{"model": "a"}`, apply; overwrite settings with `{"model": "b"}`, apply | `settings.json.bak-S` has `a`, `settings.json.bak-S-1` has `b` | `test_same_second_file_backups` |
| Third collision | `bak-S` and `bak-S-1` both exist | Uses `bak-S-2` | `test_backup_dest_counts_up` (pure) |
| Gap in the series | `bak-S` and `bak-S-2` exist, `-1` is free | Uses `bak-S-1`; nothing is overwritten | same test, second param |
| Name free | no backup exists | Plain `bak-S`, no suffix (current behavior kept) | same test, first param |
| Taken by a dangling symlink | `bak-S` is a symlink to a missing path | Counts as taken; uses `bak-S-1` | `test_backup_dest_dangling_symlink` (skip if symlinks are not permitted, as the existing symlink test does) |
| Taken by the other kind | a file named `bootstrap.bak-S` when backing up a directory | Counts as taken; uses `-1` | covered by `test_backup_dest_counts_up` (pre-create as a file) |
| Dry run with an existing backup | `bak-S` exists, `apply=False` | Action line names `bak-S-1`; nothing created or renamed | `test_dry_run_names_free_backup` |
| Empty home | no `.claude` | No backup lines (unchanged) | existing `test_apply_into_empty_home` |
| Invalid settings JSON | `{ not json` | Aborts before any backup (unchanged) | existing `test_invalid_settings_json_aborts_without_writing` |
| Retry / duplicate | apply twice | One hook entry (unchanged) | existing `test_apply_is_idempotent` |
| Concurrent installs | two processes back up the same path in the same instant | n/a: the human runs the installer, one run at a time. The check-then-rename window is documented in a code comment | n/a (by design) |
| Permissions | rename fails (read-only `.claude`) | `OSError` propagates as before; nothing is deleted | n/a: chmod is not portable to Windows |
| Maximal | many backups with the same stamp | Linear scan, stops at the first free name | covered by the gap test |

## Test plan
- Tests first. With a fixed stamp, the two same-second tests must fail on `main`: the directory test with an `OSError`/`FileExistsError` (or a lost marker on POSIX), and the file test because the backup is overwritten. Paste the failure lines into the Log.
- Fix the stamp with `monkeypatch.setattr("scripts.install._stamp", lambda: "20261017-120000")`.
- Command: `uv run python scripts/check.py`.

## Planning notes
- **People / Process / Technology:** People: the human can re-run the installer right after a fix (as T-001's post-merge step asks) without losing a backup. Process: none. Technology: about 10 lines.
- **Pareto:** a counter suffix fixes the whole bug. Atomic exclusive creation against concurrent runs is not worth the code for a human-only, single-run tool.
- **Revenue / Risk / Cost:** no revenue. Risk is low, and the change reduces the risk of losing the user's `~/.claude` files. Cost: well under one session.
- **Estimate basis (`est_hours_old_way: 0.5`):** 10 min for the fix, 20 min for the tests on the existing `tmp_path` pattern. Realistic, not generous, per the T-002 calibration.
- **Size basis (120 lines):** about 15 lines in `install.py`, 6 tests at about 10 lines each.

## Log (filled in by the builder and verifier)
- Start / end:
- Checks run (command and real output):
- Verifier verdict and findings:
- Human review (minutes, notes):
