"""machine_notes -- the machine margin notes of an Author home's tex, parsed.

A machine note is a call of one of the home's machine-note macros
(``author.noteMacros.machine``, default ``\\Claude`` and ``\\cl``) with one braced
argument. It may carry an optional **kind** (#110), in brackets before the argument::

    \\Claude{an untyped note}            today's form: judged as before
    \\Claude[prov]{T-0123: from ...}     provenance
    \\Claude[await]{T-0456 re-verify}    waits on the ticket it names
    \\Claude[human]{which convention?}   a question for the human
    \\Claude[check]{unverified step}     an unverified step

``KINDS`` are the kinds the sweep acts on; any other bracket value is kept as written and
reported as an unknown kind (the note is then treated as untyped). The typed form needs
the paper's preamble to give the macro an optional argument (``O{}``); whether a paper
does that is its human's decision, so the untyped form stays valid everywhere.

What this module gives (no I/O beyond reading a file's text):

    machine_macros(cfg)        the bare macro names of a home's config
    scan(text, macros)         every note outside comments, with its position and kind
    tickets(body)              the ticket ids a note names, in order
    plain(body)                the note's text with the TeX markup stripped (an estimate
                               of what the margin prints)
    estimate_lines(body, n)    margin lines at ``n`` characters a line
    signature(note)            a short hash of kind and text (stable when lines move)
    context_hash(text, note)   a hash of the paragraph around the note (changes when a
                               human reply is written next to it)
    note_limits(cfg)           (maxLines, lineChars) of ``author.notes``

The line estimate is characters, not typesetting: ``author.notes.lineChars`` (default
``DEFAULT_LINE_CHARS``) characters of plain text make one margin line.
"""

import hashlib
import math
import re

DEFAULT_MACHINE_MACROS = ("\\Claude", "\\cl")
#: the kinds the sweep acts on (#110)
KINDS = ("prov", "await", "human", "check")
DEFAULT_MAX_LINES = 3
#: plain-text characters per margin line: a \scriptsize \marginpar of an amsart page
#: holds about 26-32 (90pt column); an estimate, configurable as author.notes.lineChars
DEFAULT_LINE_CHARS = 30

RE_TICKET = re.compile(r"(?<![\w-])T-\d{4,}(?![\w])")
_RE_NAME_CHAR = re.compile(r"[A-Za-z@]")
_RE_CMD = re.compile(r"\\(?:[A-Za-z@]+\*?|.)")


def machine_macros(cfg=None):
    """The bare names (no backslash) of the home's machine-note macros."""
    a = (cfg or {}).get("author") if isinstance(cfg, dict) else None
    a = a if isinstance(a, dict) else {}
    nm = a.get("noteMacros") if isinstance(a.get("noteMacros"), dict) else {}
    names = [str(m).strip().lstrip("\\") for m in (nm.get("machine")
                                                   or DEFAULT_MACHINE_MACROS)]
    return tuple(n for n in names if n)


def note_limits(cfg=None):
    """``(maxLines, lineChars)`` from ``author.notes`` (defaults 3 and 30)."""
    a = (cfg or {}).get("author") if isinstance(cfg, dict) else None
    notes = (a or {}).get("notes") if isinstance((a or {}).get("notes"), dict) else {}

    def pos(v, d):
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 1 else d
    return (pos(notes.get("maxLines"), DEFAULT_MAX_LINES),
            pos(notes.get("lineChars"), DEFAULT_LINE_CHARS))


def _escaped(text, i):
    """Is the character at ``i`` escaped (an odd run of backslashes before it)?"""
    n, j = 0, i - 1
    while j >= 0 and text[j] == "\\":
        n += 1
        j -= 1
    return n % 2 == 1


def _match_braces(text, i):
    """The index just past the ``}`` closing the ``{`` at ``i``, or -1. Escaped braces
    and ``%`` comments (to the end of the line) do not count."""
    depth, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "%" and not _escaped(text, i):
            nl = text.find("\n", i)
            if nl < 0:
                return -1
            i = nl + 1
            continue
        if ch == "{" and not _escaped(text, i):
            depth += 1
        elif ch == "}" and not _escaped(text, i):
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _line_of(starts, offset):
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


def scan(text, macros=None):
    """Every machine note of ``text`` outside ``%`` comments, in order.

    Each is a dict: ``macro`` (bare name), ``kind`` (the bracket value lower-cased, or
    None), ``start`` / ``end`` (offsets of the whole call, ``\\`` to the closing brace),
    ``body`` (the braced argument, raw), ``line`` / ``end_line`` (1-based), ``raw`` (the
    call as written). A call whose brace never closes is returned with ``end`` -1 and
    ``body`` None (``unclosed``: True) and ends the scan of that call only.
    """
    names = sorted(set(macros or machine_macros()), key=len, reverse=True)
    out, n, i = [], len(text), 0
    starts = [0] + [m.end() for m in re.finditer("\n", text)]
    while i < n:
        ch = text[i]
        if ch == "%" and not _escaped(text, i):
            nl = text.find("\n", i)
            if nl < 0:
                break
            i = nl + 1
            continue
        if ch != "\\" or _escaped(text, i):
            i += 1
            continue
        name = next((m for m in names if text.startswith(m, i + 1)
                     and not _RE_NAME_CHAR.match(text[i + 1 + len(m):i + 2 + len(m)] or " ")),
                    None)
        if not name:
            i += 1
            continue
        j = i + 1 + len(name)
        while j < n and text[j] in " \t":
            j += 1
        kind = None
        if j < n and text[j] == "[":
            close = text.find("]", j)
            nl = text.find("\n", j)
            if close < 0 or (0 <= nl < close):
                i = j
                continue
            kind = text[j + 1:close].strip().lower()
            j = close + 1
            while j < n and text[j] in " \t":
                j += 1
        if j >= n or text[j] != "{":
            i = j
            continue
        end = _match_braces(text, j)
        note = {"macro": name, "kind": kind or None, "start": i,
                "line": _line_of(starts, i)}
        if end < 0:
            note.update(end=-1, body=None, raw=text[i:i + 80], unclosed=True,
                        end_line=note["line"])
            out.append(note)
            i = j + 1
            continue
        note.update(end=end, body=text[j + 1:end - 1], raw=text[i:end],
                    end_line=_line_of(starts, end - 1))
        out.append(note)
        i = end
    return out


def tickets(body):
    """The ticket ids ``body`` names, in order of first mention."""
    seen = []
    for m in RE_TICKET.finditer(body or ""):
        if m.group() not in seen:
            seen.append(m.group())
    return seen


def _strip_comments(body):
    out = []
    for ln in (body or "").split("\n"):
        k = 0
        while True:
            k = ln.find("%", k)
            if k < 0 or not _escaped(ln, k):
                break
            k += 1
        out.append(ln if k < 0 else ln[:k])
    return "\n".join(out)


def plain(body):
    """The note's text without TeX markup: comments, command names, braces, math
    shifts and ties dropped, whitespace collapsed. An estimate of what is printed."""
    s = _strip_comments(body)
    s = s.replace("\\\\", " ").replace("~", " ")
    s = _RE_CMD.sub(lambda m: m.group()[1:] if len(m.group()) == 2
                    and not m.group()[1].isalnum() and m.group()[1] not in " \n" else " ", s)
    s = s.replace("{", "").replace("}", "").replace("$", "")
    return " ".join(s.split())


def estimate_lines(body, line_chars=DEFAULT_LINE_CHARS):
    """Margin lines the note takes, at ``line_chars`` plain characters a line (>= 1)."""
    return max(1, int(math.ceil(len(plain(body)) / float(max(1, line_chars)))))


def _h(s, n=12):
    return hashlib.sha1(s.encode("utf-8", "surrogateescape")).hexdigest()[:n]


def signature(note):
    """A short hash of the note's kind and whitespace-normalised text: the same note
    keeps its signature when lines above it move, or the macro's alias changes."""
    body = " ".join((note.get("body") or "").split())
    return _h("%s\x00%s" % (note.get("kind") or "", body))


def paragraph(text, note):
    """``(start, end)`` of the paragraph holding the note: from the blank line before it
    to the blank line after it (or the text's ends)."""
    a = text.rfind("\n\n", 0, note["start"])
    a = 0 if a < 0 else a + 2
    stop = note["end"] if note.get("end", -1) >= 0 else note["start"]
    b = text.find("\n\n", stop)
    return a, (len(text) if b < 0 else b)


def context_hash(text, note):
    """A hash of the note's paragraph with the note itself cut out, whitespace
    normalised: a reply written next to the note (a human macro in the same paragraph)
    changes it, the note's own line moving does not."""
    a, b = paragraph(text, note)
    stop = note["end"] if note.get("end", -1) >= 0 else note["start"]
    around = text[a:note["start"]] + "\x00" + text[stop:b]
    return _h(" ".join(around.split()))
