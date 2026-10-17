# Diff limit check (T-008, decision 0003)

How `scripts/check_diff_limit.py` decides. Local runs come through `scripts/check.py` (last check). CI runs it with `--github` in the `diff-limit` job (T-009).

```mermaid
flowchart TD
  A[branch name: --branch, GITHUB_HEAD_REF, or rev-parse --abbrev-ref HEAD] -->|does not start with task/| S[print skip, exit 0]
  A -->|task/ but regex ^task/T-digits- or end fails| E[exit 1: bad task branch name]
  A -->|task/T-nnn-...| F{exactly one tasks/T-nnn.md or tasks/T-nnn-*.md?}
  F -->|none or two+| E2[exit 1, names the files]
  F -->|one| P[parse diff_limit_lines: int >= 0, else exit 1]
  P --> M[merge-base HEAD base]
  M -->|fails| E3[exit 1: no merge-base, mention fetch-depth: 0; never a silent pass]
  M --> L{task file at merge-base has a lower limit?}
  L -->|yes| LB[use base limit, print note]
  L -->|no or file new on branch| LN[use branch limit, print limit source]
  LB --> D[numstat -M vs merge-base incl. working tree + untracked non-ignored files, minus this task's own file]
  LN --> D
  D -->|n > limit| X[exit 1: top 5 files + stop-and-report text]
  D -->|n <= limit| OK[exit 0: print n/limit, tests share, base sha]
```

In CI the checkout is GitHub's test merge commit, so the diff against the merge-base with `origin/<base>` is exactly what the PR would add to the base.
