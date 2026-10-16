#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher: Bash): block destructive git commands.

Cross-platform port of the bash+jq script from the git-guardrails-claude-code skill.
Normal pushes to feature branches stay allowed (needed for PRs); force pushes and
direct pushes to main/master are blocked. Exit 2 + stderr message = blocked.
Malformed input never blocks (the hook must not break every Bash call).
"""

import json
import re
import sys

DANGEROUS = [
    (r"\bgit\s+push\b.*(--force|\s-f(\s|$)|\s\+)", "force push"),
    (r"\bgit\s+push\b.*(\s|:)(main|master)(\s|$)", "push to main/master"),
    (r"\bgit\s+reset\s.*--hard", "reset --hard"),
    (r"\bgit\s+clean\s.*-[a-zA-Z]*f", "clean -f"),
    (r"\bgit\s+branch\s.*-D\b", "branch -D"),
    (r"\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)", "discard all changes"),
]


def blocked_reason(command: str) -> str | None:
    for pattern, label in DANGEROUS:
        if re.search(pattern, command):
            return label
    return None


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
