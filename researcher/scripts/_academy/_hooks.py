"""Claude Code hook I/O, and the shell-command parser behind every commit gate.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import json
import os
import re
import sys

from ._base import AcademyError

# ----------------------------------------------------------------------------
# Hook I/O (Claude Code conventions)
# ----------------------------------------------------------------------------
#
# A hook reads one JSON event on stdin and exits 0. To speak it prints one JSON
# object on stdout:
#   PreToolUse   {"hookSpecificOutput": {"hookEventName": "PreToolUse",
#                  "permissionDecision": "allow"|"deny"|"ask",
#                  "permissionDecisionReason": "..."}}
#   PostToolUse / SessionStart / UserPromptSubmit / SubagentStart
#                {"hookSpecificOutput": {"hookEventName": ..., "additionalContext": "..."}}
#   Stop / SubagentStop / PostToolUse (block)   {"decision": "block", "reason": "..."}
# Silence (no output, exit 0) means "no opinion". A gate never fails a tool call
# because of its own bug: malformed events read as {}.

def read_event(stream=None):
    """Parse the hook event from ``stream`` (default stdin). Never raises; bad input -> {}.

    Claude Code writes the event as UTF-8. A text stream's own decoding is bypassed
    (its ``buffer`` is read): on Windows, Python decodes a piped stdin with the ANSI
    codepage, which mangles non-ASCII arguments. A leading BOM is dropped.
    """
    stream = stream or sys.stdin
    try:
        raw = getattr(stream, "buffer", stream).read()
    except Exception:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", "replace")
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def event_cwd(event):
    """The event's ``cwd`` if it is a directory, else the process cwd."""
    root = event.get("cwd") if isinstance(event, dict) else None
    return root if root and os.path.isdir(root) else os.getcwd()


def tool_name(event):
    """The event's ``tool_name`` or ''."""
    name = event.get("tool_name") if isinstance(event, dict) else None
    return name if isinstance(name, str) else ""


def mcp_tool(event, server="academy"):
    """For ``mcp__<server>__<tool>`` return '<tool>', else ''.

    Plugin-provided servers may appear as ``mcp__plugin_<plugin>_<server>__<tool>``;
    any server segment ending in ``server`` is accepted.
    """
    name = tool_name(event)
    m = re.match(r"^mcp__([A-Za-z0-9_-]+)__(.+)$", name)
    if not m:
        return ""
    srv = m.group(1)
    if srv == server or srv.endswith("_" + server):
        return m.group(2)
    return ""


def tool_input(event):
    ti = event.get("tool_input") if isinstance(event, dict) else None
    return ti if isinstance(ti, dict) else {}


def edited_path(event):
    """The file an Edit/Write/MultiEdit/NotebookEdit event touches, or None."""
    ti = tool_input(event)
    path = ti.get("file_path") or ti.get("notebook_path")
    return path if isinstance(path, str) and path else None


def shell_command(event):
    """The command of a Bash or PowerShell event, or ''."""
    cmd = tool_input(event).get("command")
    return cmd if isinstance(cmd, str) else ""


def is_git_commit(command):
    """True when some segment of a shell command (bash or PowerShell) runs git commit.

    Errs towards True (``git log --grep commit`` matches): a false positive costs a
    checker run, a false negative lets a commit through ungated. PowerShell's ``;``
    and newlines separate segments as in bash; ``git.exe`` and ``& git`` count.
    """
    return re.search(r"\bgit(?:\.exe)?\b[^;&|\n]*\bcommit\b", command or "") is not None


# ----------------------------------------------------------------------------
# Shell commands: which repository a ``git commit`` runs in
# ----------------------------------------------------------------------------
# One parser for every commit gate (author, scientist). The command is split into
# segments (``;``, newlines, ``&&``, ``||``, ``|``) with quotes respected, and walked
# in order while tracking the directory:
#   - ``cd``/``chdir``/``pushd``/``popd`` (bash) and ``Set-Location``/``sl``/
#     ``Push-Location``/``Pop-Location`` (PowerShell) move the tracked directory;
#   - ``git -C <dir>`` (repeatable) and ``--work-tree``/``--git-dir`` name the repo
#     of that one git call;
#   - Git Bash drive paths (``/c/Work``) resolve to ``C:/Work`` on Windows;
#   - ``bash -c "..."`` and ``powershell -Command "..."`` are parsed recursively;
#   - bash heredocs and PowerShell here-strings are data, not commands.

SHELL_CD = {"cd", "chdir", "set-location", "sl"}
SHELL_PUSHD = {"pushd", "push-location"}
SHELL_POPD = {"popd", "pop-location"}
SHELL_PREFIX_WORDS = {"command", "exec", "time", "nohup", "env", "&", "."}
GIT_OPTS_WITH_ARG = {"-c", "--namespace", "--super-prefix", "--config-env",
                     "--git-dir", "--work-tree", "--exec-path"}
SHELLS_C = {"bash": "-c", "sh": "-c", "bash.exe": "-c", "sh.exe": "-c"}
SHELLS_PS = {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}
RE_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
RE_GITBASH_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")
RE_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


class ShellParseFailure(AcademyError):
    """The command could not be tokenised (e.g. an unbalanced quote)."""


def _skip_heredocs(command):
    """Blank out bash heredoc bodies (they are data, not commands)."""
    out, pending = [], []
    for line in command.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            out.append("")
            continue
        out.append(line)
        pending.extend(m.group(2) for m in RE_HEREDOC.finditer(line))
    return "\n".join(out)


def split_segments(command):
    """Split a shell command into segments of tokens, honouring quotes.

    Returns a list of token lists. Single quotes are literal; double quotes allow
    ``\\"`` (bash) and a backtick escape (PowerShell). Outside quotes a backslash
    escapes only a space, a quote, a backslash or a separator character, so a
    Windows path such as ``C:\\Work\\Math`` survives. PowerShell here-strings
    (``@'`` ... ``'@``) become one token. A lone ``&`` at the start of a segment
    is PowerShell's call operator and is dropped; elsewhere it separates.
    Raises ShellParseFailure on an unbalanced quote or here-string.
    """
    command = _skip_heredocs(command or "")
    segments, tokens, cur = [], [], []
    state = {"have": False}
    i, n = 0, len(command)

    def end_token():
        if state["have"]:
            tokens.append("".join(cur))
        del cur[:]
        state["have"] = False

    def end_segment():
        end_token()
        if tokens:
            segments.append(list(tokens))
        del tokens[:]

    while i < n:
        ch = command[i]
        two = command[i:i + 2]
        if two in ("@'", '@"') and command[i + 2:i + 3] in ("\n", "\r"):
            close = "\n" + two[1] + "@"
            j = command.find(close, i + 2)
            if j < 0:
                raise ShellParseFailure("unterminated here-string")
            cur.append(command[i + 3:j])
            state["have"] = True
            i = j + len(close)
            continue
        if ch == "'":
            j = command.find("'", i + 1)
            if j < 0:
                raise ShellParseFailure("unbalanced single quote")
            cur.append(command[i + 1:j])
            state["have"] = True
            i = j + 1
            continue
        if ch == '"':
            j = i + 1
            buf = []
            while j < n and command[j] != '"':
                if command[j] in "\\`" and j + 1 < n and command[j + 1] in '"\\`$':
                    buf.append(command[j + 1])
                    j += 2
                    continue
                buf.append(command[j])
                j += 1
            if j >= n:
                raise ShellParseFailure("unbalanced double quote")
            cur.append("".join(buf))
            state["have"] = True
            i = j + 1
            continue
        if ch == "\\" and i + 1 < n and command[i + 1] in " \t'\"\\;&|":
            cur.append(command[i + 1])
            state["have"] = True
            i += 2
            continue
        if two in ("&&", "||"):
            end_segment()
            i += 2
            continue
        if ch in ";|\n\r":
            end_segment()
            i += 1
            continue
        if ch == "&":
            end_token()
            if not tokens:            # PowerShell call operator: `& git commit`
                i += 1
                continue
            end_segment()             # bash background
            i += 1
            continue
        if ch in " \t":
            end_token()
            i += 1
            continue
        if ch in "()" and not state["have"]:
            end_token()               # subshell / grouping parentheses
            i += 1
            continue
        if ch == ")":
            end_token()
            i += 1
            continue
        cur.append(ch)
        state["have"] = True
        i += 1
    end_segment()
    return segments


def resolve_dir(base, path):
    """``path`` as the shell would resolve it from ``base`` (Windows-aware).

    ``~``/``$HOME`` expand; on Windows a Git Bash drive path ``/c/Work`` becomes
    ``C:/Work`` (the Bash tool is Git Bash, so this is how agents name the lab).
    """
    p = (path or "").strip()
    if not p:
        return base
    if p == "~" or p.startswith("~/") or p.startswith("~\\"):
        p = os.path.expanduser("~") + p[1:]
    for var in ("$HOME", "$env:USERPROFILE", "$env:HOME", "${HOME}"):
        if p.startswith(var):
            p = os.path.expanduser("~") + p[len(var):]
    if os.name == "nt":
        m = RE_GITBASH_DRIVE.match(p.replace("\\", "/"))
        if m:                                   # Git Bash: /c/Work -> C:/Work
            p = m.group(1).upper() + ":/" + p.replace("\\", "/")[3:]
    if os.path.isabs(p) or re.match(r"^[A-Za-z]:", p):
        return os.path.normpath(p)
    return os.path.normpath(os.path.join(base, p))


def _cd_target(args):
    """The directory argument of a cd-like command, skipping PowerShell switches."""
    k = 0
    while k < len(args):
        low = args[k].lower()
        if low in ("-path", "-literalpath"):
            return args[k + 1] if k + 1 < len(args) else None
        if low.startswith("-") and low != "-":   # bash -L/-P, PowerShell switches
            k += 1
            continue
        return args[k]
    return None


def _strip_prefix(tokens):
    k = 0
    while k < len(tokens) and (tokens[k].lower() in SHELL_PREFIX_WORDS
                               or RE_ASSIGN.match(tokens[k])):
        k += 1
    return tokens[k:]


def _is_git(token):
    base = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return base in ("git", "git.exe")


def git_commit_dir(tokens, cwd):
    """For a ``git ... commit`` token list, the repo directory; else None."""
    if not tokens or not _is_git(tokens[0]):
        return None
    repo, work_tree, git_dir = cwd, None, None
    k = 1
    while k < len(tokens):
        t = tokens[k]
        low = t.lower()
        if t == "-C":
            if k + 1 >= len(tokens):
                return None
            repo = resolve_dir(repo, tokens[k + 1])
            k += 2
            continue
        if low.startswith("--work-tree="):
            work_tree = t.split("=", 1)[1]
            k += 1
            continue
        if low.startswith("--git-dir="):
            git_dir = t.split("=", 1)[1]
            k += 1
            continue
        if low in GIT_OPTS_WITH_ARG:
            if low == "--work-tree" and k + 1 < len(tokens):
                work_tree = tokens[k + 1]
            if low == "--git-dir" and k + 1 < len(tokens):
                git_dir = tokens[k + 1]
            k += 2
            continue
        if t.startswith("-"):
            k += 1
            continue
        if low != "commit":
            return None
        if work_tree:
            return resolve_dir(repo, work_tree)
        if git_dir:
            gd = resolve_dir(repo, git_dir)
            return os.path.dirname(gd) if os.path.basename(gd).lower() == ".git" else repo
        return repo
    return None


def commit_targets(command, cwd, _depth=0):
    """Every directory a ``git commit`` in ``command`` commits in, in order.

    Raises ShellParseFailure when the command cannot be tokenised; a gate then falls
    back to ``[cwd] if is_git_commit(command) else []``.
    """
    out = []
    here = cwd
    stack = []
    for seg in split_segments(command):
        toks = _strip_prefix(seg)
        if not toks:
            continue
        head = toks[0].lower()
        if head in SHELL_CD:
            tgt = _cd_target(toks[1:])
            if tgt is None and head == "cd" and len(toks) == 1:
                here = os.path.expanduser("~")      # bash: cd alone goes home
            elif tgt and tgt != "-":
                here = resolve_dir(here, tgt)
            continue
        if head in SHELL_PUSHD:
            tgt = _cd_target(toks[1:])
            if tgt:
                stack.append(here)
                here = resolve_dir(here, tgt)
            continue
        if head in SHELL_POPD:
            if stack:
                here = stack.pop()
            continue
        if _depth < 3 and head in SHELLS_C and len(toks) >= 3 and toks[1] == SHELLS_C[head]:
            out.extend(commit_targets(toks[2], here, _depth + 1))
            continue
        if _depth < 3 and head in SHELLS_PS:
            for k, t in enumerate(toks[1:], 1):
                if t.lower() in ("-command", "-c") and k + 1 < len(toks):
                    out.extend(commit_targets(" ".join(toks[k + 1:]), here, _depth + 1))
                    break
            continue
        d = git_commit_dir(toks, here)
        if d:
            out.append(d)
    return out


def commit_targets_or_cwd(command, cwd):
    """``commit_targets``, falling back to ``[cwd]`` (or ``[]`` when the command is no
    commit at all) when it cannot be tokenised -- a gate errs towards checking."""
    try:
        return commit_targets(command, cwd)
    except ShellParseFailure:
        return [cwd] if is_git_commit(command) else []


def emit(payload, stream=None):
    """Write ``payload`` as one JSON object to ``stream`` (default stdout); return 0."""
    (stream or sys.stdout).write(json.dumps(payload, ensure_ascii=False))
    return 0


def emit_permission(decision, reason="", stream=None):
    """PreToolUse decision: 'allow', 'deny' or 'ask', with a reason shown to the model."""
    if decision not in ("allow", "deny", "ask"):
        raise ValueError("decision must be allow, deny or ask")
    block = {"hookEventName": "PreToolUse", "permissionDecision": decision}
    if reason:
        block["permissionDecisionReason"] = reason
    return emit({"hookSpecificOutput": block}, stream)


def emit_context(event_name, text, stream=None):
    """Add ``text`` to the model's context (PostToolUse, SessionStart, UserPromptSubmit...)."""
    return emit({"hookSpecificOutput": {"hookEventName": event_name,
                                        "additionalContext": text}}, stream)


def emit_block(reason, stream=None):
    """Block a Stop/SubagentStop (the agent must continue) or flag a PostToolUse result."""
    return emit({"decision": "block", "reason": reason}, stream)
