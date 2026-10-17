# Backlog

Known gaps, not yet tasks.

- `scripts/check_diff_limit.py`: an untracked file with a carriage return (`\r`) in its name counts 0 lines. `git()` runs with `text=True`, which turns `\r` into `\n`, so the path is not found. Staged or committed files are counted correctly. (T-008 verifier, 2026-10-17)
- `scripts/check_diff_limit.py`: a `.gitattributes` line such as `*.py -diff` makes git report those files as binary, which count 0 lines. The change is visible in the PR, but it bypasses a check meant to be mechanical. (T-008 verifier, 2026-10-17)
