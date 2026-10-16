#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher: Bash): block destructive git commands.

Cross-platform port of the bash+jq script from the git-guardrails-claude-code skill.
Normal pushes to feature branches stay allowed (needed for PRs); force pushes and
direct pushes to main/master are blocked. Exit 2 + stderr message = blocked.
Malformed input never blocks (the hook must not break every Bash call).

Each command segment is checked on its own, so quoted text, heredoc bodies and
neighbouring commands (`git push x && gh pr create --base main`) cannot trigger a block.
Anything the parser cannot understand falls back to the legacy whole-text regexes.
"""

import json
import re
import shlex
import sys

DANGEROUS = [
    (r"\bgit\s+push\b.*(--force|\s-f(\s|$)|\s\+)", "force push"),
    (r"\bgit\s+push\b.*(\s|:)(main|master)(\s|$)", "push to main/master"),
    (r"\bgit\s+reset\s.*--hard", "reset --hard"),
    (r"\bgit\s+clean\s.*-[a-zA-Z]*f", "clean -f"),
    (r"\bgit\s+branch\s.*-D\b", "branch -D"),
    (r"\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)", "discard all changes"),
]

MAX_DEPTH = 5  # nested interpreter / substitution levels before the legacy fallback
MIN_FORCE_ABBREV = 5  # git accepts unambiguous long-option prefixes; "--for" is the shortest
MAIN_REFS = {"main", "master", "refs/heads/main", "refs/heads/master"}
FORCE_LONG = ("--force", "--force-with-lease", "--force-if-includes")
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"}
WRAPPERS = {"env", "command", "exec", "nohup", "time", "sudo", "doas", "xargs", "find", "timeout", "nice", "watch"}
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}"}
POSIX_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
WIN_SHELLS = {"pwsh", "powershell", "cmd"}
CMD_FLAGS = {"-c", "/c", "-Command", "-command"}
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")
HEREDOC = re.compile(r"<<(-?)[ \t]*([\"']?)([^\s\"'<>|&;()]+)\2")
RUNS_SHELL = re.compile(r"(?<![\w.])(?:bash|sh|zsh|dash|ksh|fish|pwsh|powershell|cmd|eval|source)\b")
OPERATOR_CHARS = set("&|;()")
REDIRECT_CHARS = set("<>")


def _legacy(text: str, strip_quotes: bool = False) -> str | None:
    if strip_quotes:
        text = re.sub(r"""['"\\`]""", " ", text)
    for pattern, label in DANGEROUS:
        if re.search(pattern, text):
            return label
    return None


def _substitution(text: str, i: int) -> tuple[str, int] | None:
    """Body and end index of a backtick or $(...) substitution starting at i, else None."""
    if text[i] == "`":
        start = i + 1
        end = text.find("`", start)
        return (text[start:], len(text)) if end < 0 else (text[start:end], end + 1)
    if not text.startswith("$(", i):
        return None
    start, depth, end = i + 2, 1, i + 2
    while end < len(text):
        depth += (text[end] == "(") - (text[end] == ")")
        if depth == 0:
            break
        end += 1
    return text[start:end], end + 1


Heredoc = list[tuple[str, bool, bool]]  # (delimiter, strip leading tabs, body is expanded)


def _heredoc_bodies(text: str, i: int, pending: Heredoc, runs_shell: bool) -> tuple[int, list[str]]:
    """Consume heredoc bodies starting at i; return the new index and the code the shell would run."""
    code: list[str] = []
    for delim, strip_tabs, expands in pending:
        body: list[str] = []
        while i < len(text):
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            line, i = text[i:end], end + 1
            if (line.lstrip("\t") if strip_tabs else line) == delim:
                break
            body.append(line)
        joined = "\n".join(body)
        if runs_shell:
            code.append(joined)
        elif expands:
            j = 0
            while j < len(joined):
                sub = _substitution(joined, j) if joined[j] in "`$" else None
                code.extend([sub[0]] if sub else [])
                j = sub[1] if sub else j + 1
    return i, code


def _prepare(text: str) -> tuple[str, list[str]]:
    """Strip comments and heredoc bodies, turn unquoted newlines into `;`, lift out substitutions."""
    out: list[str] = []
    extra: list[str] = []
    pending: Heredoc = []
    quote, i, line_start = "", 0, 0
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'":
            if text[i + 1 : i + 2] != "\n":
                out.append(text[i : i + 2])
            i += 2
            continue
        if quote == "'":
            quote = "" if c == "'" else quote
        elif c == "'" and not quote:
            quote = "'"
        elif c == '"':
            quote = "" if quote else '"'
        elif c == "`" or text.startswith("$(", i):
            sub = _substitution(text, i)
            if sub:
                extra.append(sub[0])
                out.append("x")
                i = sub[1]
                continue
        elif not quote:
            if c == "#" and (i == 0 or text[i - 1] in " \t\n;&|()"):
                end = text.find("\n", i)
                i = len(text) if end < 0 else end
                continue
            if text.startswith("<<<", i):
                out.append("<<<")
                i += 3
                continue
            match = HEREDOC.match(text, i) if c == "<" else None
            if match:
                pending.append((match[3], bool(match[1]), not match[2]))
                out.append("<<")
                i = match.end()
                continue
            if c == "\n":
                runs_shell = bool(RUNS_SHELL.search("".join(out[line_start:])))
                i, code = _heredoc_bodies(text, i + 1, pending, runs_shell)
                extra.extend(code)
                pending = []
                out.append(";")
                line_start = len(out)
                continue
        out.append(c)
        i += 1
    return "".join(out), extra


def _segments(clean: str) -> list[list[str]]:
    lex = shlex.shlex(clean, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    segments: list[list[str]] = [[]]
    for token in lex:
        chars = set(token)
        if chars <= REDIRECT_CHARS:
            continue
        if chars <= OPERATOR_CHARS | REDIRECT_CHARS:
            segments.append([])
        else:
            segments[-1].append(token)
    return segments


def _base(word: str) -> str:
    return re.split(r"[\\/]", word)[-1].lower().removesuffix(".exe")


def _git(args: list[str]) -> str | None:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_VALUE_OPTS else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1 :]
    dd = rest.index("--") if "--" in rest else len(rest)
    opts = [a for a in rest[:dd] if a.startswith("-")]
    pos = [a for a in rest[:dd] if not a.startswith("-")] + rest[dd + 1 :]
    shorts = "".join(a[1:] for a in opts if not a.startswith("--"))
    longs = {a.split("=")[0] for a in opts if a.startswith("--")}

    def long_is(full: str, minimum: int) -> bool:
        return any(len(name) >= minimum and full.startswith(name) for name in longs)

    if sub == "push":
        forced = any(long_is(f, MIN_FORCE_ABBREV) for f in FORCE_LONG)
        if "f" in shorts or forced or any(p.startswith("+") for p in pos):
            return "force push"
        if any(p.rsplit(":", 1)[-1].lstrip("+") in MAIN_REFS for p in pos):
            return "push to main/master"
    elif sub == "reset" and long_is("--hard", 4):
        return "reset --hard"
    elif sub == "clean" and ("f" in shorts or long_is("--force", 3)):
        return "clean -f"
    elif sub == "branch":
        deleting = "d" in shorts or "--delete" in longs
        if "D" in shorts or (deleting and ("f" in shorts or "--force" in longs)):
            return "branch -D"
    elif sub in ("checkout", "restore") and "." in pos:
        staged = "--staged" in longs or "S" in shorts
        worktree = "--worktree" in longs or "W" in shorts
        unstage_only = sub == "restore" and staged and not worktree
        return None if unstage_only else "discard all changes"
    return None


def _check(argv: list[str], depth: int) -> str | None:
    while argv and (argv[0] in KEYWORDS or ASSIGNMENT.match(argv[0])):
        argv = argv[1:]
    if not argv:
        return None
    name = _base(argv[0])
    if name in WRAPPERS:
        targets = POSIX_SHELLS | WIN_SHELLS | {"git", "eval"}
        target = next((k for k in range(1, len(argv)) if _base(argv[k]) in targets), 0)
        return _check(argv[target:], depth) if target else None
    if name == "eval":
        return _scan(" ".join(argv[1:]), depth + 1)
    if name in POSIX_SHELLS | WIN_SHELLS:
        for k, arg in enumerate(argv[1:], 1):
            if arg in CMD_FLAGS or re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", arg):
                code = argv[k + 1 :] if name in WIN_SHELLS else argv[k + 1 : k + 2]
                return _scan(" ".join(code), depth + 1)
        # no -c flag: a here-string (`bash <<< "..."`) lands in argv, so scan the arguments as code
        return _scan(" ".join(argv[1:]), depth + 1)
    return _git(argv[1:]) if name == "git" else None


def _scan(text: str, depth: int) -> str | None:
    if depth > MAX_DEPTH:
        return _legacy(text, strip_quotes=True)
    clean, extra = _prepare(text)
    try:
        segments = _segments(clean)
    except ValueError:  # unterminated quote and similar: fail safe on the raw text
        return _legacy(text)
    for argv in segments:
        reason = _check(argv, depth)
        if reason:
            return reason
    for code in extra:
        reason = _scan(code, depth + 1)
        if reason:
            return reason
    return None


def blocked_reason(command: str) -> str | None:
    try:
        return _scan(command, 0)
    except Exception:  # noqa: BLE001 - any parser surprise must fail safe, not open
        return _legacy(command)


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
