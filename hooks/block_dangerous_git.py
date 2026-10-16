#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher: Bash): block destructive git commands.

Cross-platform port of the bash+jq script from the git-guardrails-claude-code skill.
Normal pushes to feature branches stay allowed (needed for PRs); force pushes and
direct pushes to main/master are blocked. Exit 2 + stderr message = blocked.
Malformed input never blocks (the hook must not break every Bash call).

Design: the regex patterns judge the whole command. A flagged command is let through
only by one of two narrow, provable exceptions (see _heredoc_to_file_ok and _chained_ok).
Anything the exceptions do not clearly understand stays blocked.
"""

import json
import re
import shlex
import sys

GIT = r"\bgit(?:\.exe)?"
# (head, tail, label): a line is flagged when `head` matches and `tail` matches later on the same
# line. Same meaning as `head.*tail`, but linear time (a single `.*` regex is quadratic on
# inputs with many `git push` occurrences).
DANGEROUS = [
    (rf"{GIT}\s+push\b", r"--force|\s-[a-zA-Z]*f|\s\+", "force push"),
    (rf"{GIT}\s+push\b", r"(?:[\s:\"']|refs/heads/)(?:main|master)(?![\w./-])", "push to main/master"),
    (rf"{GIT}\s+reset\s", r"--hard", "reset --hard"),
    (rf"{GIT}\s+clean\s", r"-[a-zA-Z]*f", "clean -f"),
    (rf"{GIT}\s+branch\s", r"-D\b", "branch -D"),
    (rf"{GIT}\s+(?:checkout|restore)\s+(?:--\s+)?\.(?![\w./-])", r"", "discard all changes"),
]
COMPILED = [(re.compile(head), re.compile(tail), label) for head, tail, label in DANGEROUS]
# Git global options before the subcommand (`git -C dir push -f`); values never start with "-"
# so the alternatives cannot overlap and backtracking stays linear.
GIT_OPTIONS = re.compile(
    rf"{GIT}((?:\s+(?:-[Cc]\s+[^\s-]\S*|--(?:git-dir|work-tree|namespace|exec-path)\s+[^\s-]\S*"
    r"|--?[A-Za-z][\w-]*(?:=\S+)?))+)(?=\s+[A-Za-z])"
)
HEREDOC_FILE = re.compile(r"(?:cat|tee)(?:[ \t]+(?:>>?|[\w./-]+))*[ \t]+<<(['\"])(\w+)\1[ \t]*")
SAFE_FIRST = {"git", "gh", "echo", "printf", "cd", "ls", "pwd", "true"}
MAX_LEN = 100_000  # longer commands are not inspected: blocked if they mention git
PUNCTUATION = "();<>|&\n"
SEPARATORS = set("&|;\n")
SHELL_SYNTAX = ("$", "`", "<<", "<(", ">(", "\\\n")


def legacy_reason(cmd: str) -> str | None:
    cmd = GIT_OPTIONS.sub("git", cmd.replace("\\\n", " "))
    for line in cmd.split("\n"):
        for head, tail, label in COMPILED:
            found = head.search(line)
            if found and tail.search(line, found.end()):
                return label
    return None


def _heredoc_to_file_ok(cmd: str) -> bool:
    """Exception A: `cat > file <<'WORD'`, literal body, closing WORD, nothing after it."""
    lines = cmd.rstrip().split("\n")
    match = HEREDOC_FILE.fullmatch(lines[0])
    if not match or len(lines) < 2 or lines[-1] != match[2] or match[2] in lines[1:-1]:
        return False
    return legacy_reason(lines[0]) is None


def _chained_ok(cmd: str) -> bool:
    """Exception B: simple chained commands; the match only crossed a separator or sat in inert text."""
    if any(marker in cmd for marker in SHELL_SYNTAX):
        return False
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=PUNCTUATION)
        lex.whitespace, lex.whitespace_split, lex.commenters = " \t\r", True, ""
        segments: list[list[str]] = [[]]
        for token in lex:
            if "(" in token or ")" in token:
                return False
            if set(token) <= set(PUNCTUATION) and set(token) & SEPARATORS:
                segments.append([])
            else:
                segments[-1].append(token)
    except Exception:  # noqa: BLE001 - any tokenizer problem means no exception
        return False
    for segment in segments:
        if segment and (segment[0] not in SAFE_FIRST or (segment[0] == "git" and legacy_reason(" ".join(segment)))):
            return False
    return True


def blocked_reason(cmd: str) -> str | None:
    try:
        if len(cmd) > MAX_LEN:
            return "command too long to inspect" if "git" in cmd else None
        reason = legacy_reason(cmd)
        if reason is None or _heredoc_to_file_ok(cmd) or _chained_ok(cmd):
            return None
        return reason
    except Exception:  # noqa: BLE001 - never fail open
        return "hook error"


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
        command = data["tool_input"]["command"]
    except (ValueError, KeyError, TypeError):
        return 0
    if not isinstance(command, str):
        return 0
    reason = blocked_reason(command)
    if reason:
        print(f"BLOCKED ({reason}): '{command}'. The user has prevented you from doing this.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
