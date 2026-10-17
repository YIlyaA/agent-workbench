---
id: T-010
status: ready-for-review       # draft | approved | in-progress | ready-for-review | done | rejected
risk: low                # one docs subsection; the run is read-only on another repo and done by the orchestrator
autonomy: L1             # L0 observe | L1 recommend | L2 approve-to-execute | L3 guardrailed auto
type: metrics            # feature | bugfix | docs | skill | metrics | research
diff_limit_lines: 40     # task file not counted
est_hours_old_way: 0.5     # confirmed by the human 2026-10-17; frozen
budget_minutes: 30       # builder stops and reports when reached
budget_usd: 5            # checked after the run with `npx ccusage`
blocked_by: [T-007]
parallel_ok: true        # disjoint from T-009; touches docs/baseline.md only
---

# Baseline re-check after the git_metrics.py fixes

## Goal
Part B of the split approved by the human on 2026-10-17 ("approve T-007..T-010"). T-007 fixed four bugs in `scripts/git_metrics.py` (author by name only, merges only from HEAD, empty-repo crash, stash commits counted). Check whether any number published in `docs/baseline.md` moved, including the 2.4x to 2.7x per-active-day comparison (headline number 1, METRICS.md), and record the result, including "no change".

## Two steps, two actors
1. **Run (orchestrator, not the builder).** A read-only run of the old and new script on the author's main backend project, the source of the published table. The human approved this run by approving T-007..T-010 on 2026-10-17; the human gives the source path in the session. The orchestrator writes **aggregates only** into the "Run results" part of the Log below.
2. **Record (builder, or the orchestrator on a `task/T-010-baseline-recheck` branch).** Add one subsection to `docs/baseline.md` from the Run results only. Metrics data is L1: the text is a proposal, and the human confirms it at PR review.

**Never name the source repo** in any file, commit, PR or Log: no name, path, remote URL, author name, email, branch name or commit subject. Call it "the author's main backend project", as `docs/baseline.md` does (AGENTS.md "Public repo").

## Scope (paths the builder may touch)
- `docs/baseline.md`: one new subsection, nothing else in the file changes
- this task file: `status` and the Log section only

Nothing else. Do **not** edit `session-log/tasks.csv` (the orchestrator writes the row after merge) or `scripts/`. The builder does not run anything on the source repo. Nothing from the source repo (JSON output, file lists) enters this repo.

## Run procedure (orchestrator; read-only on the source repo)
Let `<src>` be the path the human gives in session, `<s>` the session scratchpad, and `<c>` the T-007 squash commit on `main`.
1. **Before:** record `git -C <src> rev-parse HEAD`, the line count of `git -C <src> status --porcelain`, and the line count of `git -C <src> for-each-ref`. Also record whether `refs/stash` exists and `git -C <src> stash list` line count (numbers only).
2. **Scripts:** `git show <c>^:scripts/git_metrics.py` into `<s>/gm_old.py` and `git show <c>:scripts/git_metrics.py` into `<s>/gm_new.py`. Both standalone (stdlib only).
3. **Was `--author` used?** Run `uv run python <s>/gm_old.py <src> --out <s>/old.json` (no `--author`). If the closed months 2025-06 to 2026-09 match the published table cell for cell (commits, active days, code lines, lines per day, test share, fix share), `--author` was not used. If not, the human names the alias substrings to try in session. If none reproduces the table, record "not reproducible" plus the size of the gap and stop: no ratio recompute from mixed sources.
4. **Effect of the fix:** run `gm_new.py` with the same arguments into `<s>/new.json`, on the same repo state. Effect = new minus old, per month and per published column. This separates the fix from commits added since 2026-10-10. The published 2026-10 row ("to the 10th") is not compared.
5. **Merges:** totals of the `merges` column before 2026-08 and from 2026-08, old and new.
6. **Repeat** each run once; the JSON must be identical except `generated`.
7. **After:** the three values from step 1 must be identical. If not, stop and report to the human; do not record results.
8. **Recompute only if needed:** if any published cell changes, recompute the "Two periods compared" table and the per-active-day ratio with the new numbers.
9. Write the aggregates into "Run results" below. Delete `<s>/*.json` and the two script copies after the record is merged.

## Specification (the record)
Add `### Re-check after the git_metrics fixes (YYYY-MM-DD)` at the end of the "Two periods compared" section (after its table, before "How to read this"). Content, as a short table or list:
- Arguments: "no `--author`" or "a name substring" (never the name).
- Stash present at run time: yes/no, and the count.
- Published cells changed by the fix: a count (expected 0). If not 0, list month and column with old and new values.
- Merges totals, old and new, for the two periods (aggregates only; the column is not published in the table above).
- The per-active-day ratio: "unchanged (2.4x to 2.7x)" or old and new side by side.
- One sentence: months are by author date in the author's own offset (`%ad`), in both versions. (Line 3 says "commit dates"; do not edit line 3, this sentence clarifies it.)
- If "not reproducible": say so, give the gap, and say the original table stands until the human decides.

Never overwrite the original tables. Old and new values stand side by side only inside the new subsection.

## Acceptance criteria
- [ ] Only the new subsection is added to `docs/baseline.md`; `git diff` shows no deleted lines in that file.
- [ ] Every number in the subsection appears in the "Run results" Log entry.
- [ ] The diff contains no path, repo name, remote URL, author name, email, branch name or commit subject from the source repo. The verifier greps the added lines for `/Users/`, `C:\`, `@`, `github.com` and the words the human lists in session (not written down).
- [ ] Before and after values in the Log are identical (read-only proof).
- [ ] Diff at most 40 lines (insertions plus deletions against the merge-base with `main`, not counting this task file). **If you reach the limit, stop and report.**
- [ ] `uv run python scripts/check.py` passes on CI (Linux, macOS, Windows).

## Edge cases
| Case | Input or state | Expected behavior | Test |
|---|---|---|---|
| No change (expected) | no stash, `--author` not used | Closed months reproduce exactly; new minus old is 0 in every published column; only `merges` differs | Run steps 3 and 4; subsection says "0 cells changed" and gives the merges totals |
| Stash present | `refs/stash` exists | Commits and lines drop in the stash's months (its index and untracked commits no longer count) | Step 4 lists changed cells; step 8 recomputes; old and new side by side |
| Empty stash list | `refs/stash` absent | Recorded as "no", count 0 | Step 1 |
| `--author` used with a name | old without `--author` does not match the closed months | Try the human's alias substrings; use the set that reproduces the table for both runs | Arguments recorded as "a name substring" |
| Author email now matches | the fix adds commits whose email matches but name does not | Shows up as positive new minus old in commits | Step 4 per-month diff |
| Not reproducible | no argument set matches | Record the gap; no recompute; original table stands | Subsection wording (human confirms) |
| Source repo moved since 2026-10-10 | new commits, maybe new branches | Only new(now) minus old(now) is used; 2026-10 row not compared | Built into step 4 |
| Merges from other refs | merges on branches not reachable from HEAD | Only the `merges` totals change; no published cell | Step 5 |
| Time zone / month boundary | a commit at 23:30 -05:00 on the last day of a month | Both versions use `%ad` in the author's offset, so no month shift. A shift in a boundary month is a finding | Step 4 per-month diff |
| Retry / duplicate | each version run twice | Identical JSON except `generated` | Step 6 |
| Partial failure | either run raises, or the source changes during the run | Stop and report; no docs edit | Steps 4 and 7 |
| Read-only / permissions | source repo | HEAD, status count and ref count unchanged; output only in the scratchpad | Steps 1 and 7 |
| Privacy | committed text | Aggregates only | Verifier grep (acceptance) |
| Concurrent | a builder runs in this repo during the run | n/a: the run touches only the source repo (read) and the scratchpad | n/a (by design) |
| Maximal | full history of the source repo | n/a: two `git log` calls per run (three with the empty-repo guard) | n/a (by design) |
| Empty | source repo with no commits | n/a: the published table proves it has commits | n/a |

## Test plan
No code. The checks are the run steps above, the verifier's privacy grep, and `uv run python scripts/check.py` (which includes the `diff limit: n/40` line when T-008 is merged).

## Log (filled in by the orchestrator, builder and verifier)
- Run results (orchestrator; aggregates only):
  - Date and time of run: 2026-10-17
  - Before / after: identical: yes (HEAD, status --porcelain count 0, for-each-ref count 168)
  - `refs/stash` present, stash count: present, stash list count 0
  - Arguments: no `--author`. Old = main's script before T-007; new = T-007 branch version 69594a1 (PR #18 not yet merged)
  - Closed months reproduced by old(now): 2025-06..2026-07 yes except 2026-05 (published 10 commits, today 9). 2026-08+ no: commits published vs today 2026-08 70 vs 115, 2026-09 31 vs 4, 2026-10 (to the 10th) 44 vs none; total 472 vs 445; 19 published cells differ. Human decision 2026-10-17: record "not reproducible", recompute nothing.
  - Published cells changed by the fix: 0 for 2025-06..2026-07; 2026-08+ not assessable. Only 2026-08 moves: commits 115->113, commits/day 10.45->10.27, code lines 59762->58895, lines/day 5433->5354, test share 0.383->0.380, fix share 0.374->0.381 (2 removed = stash commits)
  - Merges totals: before 2026-08 old 38 / new 38; 2026-08..09 old 1 / new 1
  - Ratio: unverified (not recomputed)
  - Repeat runs identical: yes (except `generated`)
- Start / end (record):
- Checks run (command and real output):
- Diff size (insertions + deletions vs merge-base, task file excluded):
- Verifier verdict and findings:
- Human review (minutes, notes):

## Planning notes
- **People / Process / Technology:** People: the human confirms the wording (L1). Process: a fix to headline-number code gets an explicit re-check instead of an assumption. Technology: two runs of a standalone script and a JSON diff.
- **Pareto:** steps 3 and 4 answer the question. The stash check is the only part that can plausibly move a published cell.
- **Revenue / Risk / Cost:** no revenue. Risks: privacy (aggregates only, verifier grep); the source repo changed since 2026-10-10 (handled by comparing old and new on the same state). Cost: one orchestrator run plus a short record session.
- **Estimate basis (`est_hours_old_way: 0.5`):** two runs, a per-month diff and one subsection. Planning aid only.
- **Size basis (40):** a heading, a 6-to-8-row table or list and one sentence: about 15 lines; up to about 30 if cells changed and the two-period numbers are shown side by side.
- **Assumptions:** the old script at `<c>^` is the version that produced the published table (it was unchanged in behavior from the reference design until T-007, decision 0001). The human remembers or can supply the `--author` value if one was used.
