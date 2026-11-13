"""On-disk formats: the frontmatter YAML subset, atomic writes, and id allocation
under ``board/.ids``.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import json
import os
import re
import tempfile
import time

from ._base import AcademyError, FrontmatterError, LockTimeout

# ----------------------------------------------------------------------------
# Frontmatter: the simple YAML subset
# ----------------------------------------------------------------------------
#
# Supported (docs/protocol.md, "Frontmatter subset"):
#   key: scalar                 str | int | float | true/false | null (~, null, empty)
#   key: [a, "b, c", 3]         inline list of scalars
#   key: {a: 1, b: x}           inline one-level map (read only; written as a block)
#   key:                        block map, one level, 2-space indented scalars
#     sub: scalar
#   key:                        block list of scalars (read only; written inline)
#     - a
# Keys match [A-Za-z_][A-Za-z0-9_-]*. Comments (' #...' outside quotes) are dropped.

RE_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$")
RE_INT = re.compile(r"^-?\d+$")
RE_FLOAT = re.compile(r"^-?\d+\.\d+$")
_SPECIAL_START = set("[]{}\"'!&*?|>%@`#,-")


def _strip_comment(s):
    out, q, i = [], None, 0
    while i < len(s):
        ch = s[i]
        if q:
            out.append(ch)
            if ch == "\\" and q == '"' and i + 1 < len(s):
                out.append(s[i + 1])
                i += 1
            elif ch == q:
                q = None
        elif ch in "\"'" and (i == 0 or s[i - 1] in " \t[{,:"):
            q = ch                      # an apostrophe inside a word is not a quote
            out.append(ch)
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _parse_scalar(s):
    s = s.strip()
    if s in ("", "~", "null", "Null", "NULL"):
        return None
    if s.startswith('"'):
        try:
            val, end = json.JSONDecoder().raw_decode(s)
        except ValueError:
            raise FrontmatterError("bad double-quoted string: %s" % s)
        if s[end:].strip():
            raise FrontmatterError("trailing text after string: %s" % s)
        return val
    if s.startswith("'"):
        if len(s) < 2 or not s.endswith("'"):
            raise FrontmatterError("bad single-quoted string: %s" % s)
        return s[1:-1].replace("''", "'")
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if RE_INT.match(s):
        return int(s)
    if RE_FLOAT.match(s):
        return float(s)
    return s


def _split_flow(s):
    """Split the inside of [..] / {..} on top-level commas, respecting quotes."""
    parts, cur, q, depth, i = [], [], None, 0, 0
    while i < len(s):
        ch = s[i]
        if q:
            cur.append(ch)
            if ch == "\\" and q == '"' and i + 1 < len(s):
                cur.append(s[i + 1])
                i += 1
            elif ch == q:
                q = None
        elif ch in "\"'" and not "".join(cur).strip():
            q = ch                      # a quote opens only at the start of an item
            cur.append(ch)
        elif ch in "[{":
            depth += 1
            cur.append(ch)
        elif ch in "]}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    if q:
        raise FrontmatterError("unterminated quote in: %s" % s)
    tail = "".join(cur)
    if tail.strip() or parts:
        parts.append(tail)
    return [p.strip() for p in parts]


def _parse_value(s):
    s = s.strip()
    if s.startswith("["):
        if not s.endswith("]"):
            raise FrontmatterError("unterminated list: %s" % s)
        items = _split_flow(s[1:-1])
        if any(p.startswith(("[", "{")) for p in items):
            raise FrontmatterError("nested collections are not supported: %s" % s)
        return [_parse_scalar(p) for p in items if p != ""]
    if s.startswith("{"):
        if not s.endswith("}"):
            raise FrontmatterError("unterminated map: %s" % s)
        out = {}
        for p in _split_flow(s[1:-1]):
            if not p:
                continue
            k, sep, v = p.partition(":")
            if not sep or not RE_KEY.match(k.strip() + ":"):
                raise FrontmatterError("bad map entry %r in: %s" % (p, s))
            if v.strip().startswith(("[", "{")):
                raise FrontmatterError("nested collections are not supported: %s" % s)
            out[k.strip()] = _parse_scalar(v)
        return out
    return _parse_scalar(s)


def _parse_yaml(lines):
    meta, i = {}, 0
    while i < len(lines):
        raw = lines[i]
        line = _strip_comment(raw)
        if not line.strip():
            i += 1
            continue
        if line[0] in " \t":
            raise FrontmatterError("unexpected indentation: %r" % raw)
        m = RE_KEY.match(line)
        if not m:
            raise FrontmatterError("not a 'key: value' line: %r" % raw)
        key, rest = m.group(1), (m.group(2) or "").strip()
        if key in meta:
            raise FrontmatterError("duplicate key %r" % key)
        i += 1
        if rest:
            meta[key] = _parse_value(rest)
            continue
        block = []
        while i < len(lines):
            nxt = _strip_comment(lines[i])
            if not nxt.strip():
                i += 1
                continue
            if nxt[0] not in " \t":
                break
            block.append(nxt.strip())
            i += 1
        if not block:
            meta[key] = None
        elif all(b.startswith("- ") or b == "-" for b in block):
            meta[key] = [_parse_scalar(b[1:]) for b in block]
        else:
            sub = {}
            for b in block:
                mm = RE_KEY.match(b)
                if not mm:
                    raise FrontmatterError("bad entry under %r: %r" % (key, b))
                sk, sv = mm.group(1), (mm.group(2) or "")
                if sv.strip().startswith(("[", "{")):
                    raise FrontmatterError("nested collections are not supported under %r"
                                           % key)
                if sk in sub:
                    raise FrontmatterError("duplicate key %r under %r" % (sk, key))
                sub[sk] = _parse_scalar(sv)
            meta[key] = sub
    return meta


def read_frontmatter(text):
    """Split a Markdown file into ``(meta, body)``.

    The frontmatter is the block between a first line ``---`` and the next line
    ``---``. CRLF input is accepted and normalised to LF. Without frontmatter the
    result is ``({}, text)``. ``body`` is everything after the closing ``---`` line,
    exactly (so ``write_frontmatter(*read_frontmatter(t)) == t`` for canonical files).
    Raises FrontmatterError for YAML outside the subset described above.
    """
    text = text.replace("\r\n", "\n")
    if text.startswith("\ufeff"):
        text = text[1:]
    if not (text.startswith("---\n") or text == "---"):
        return {}, text
    lines = text.split("\n")
    for j in range(1, len(lines)):
        if lines[j].rstrip() == "---":
            meta = _parse_yaml(lines[1:j])
            return meta, "\n".join(lines[j + 1:])
    raise FrontmatterError("frontmatter is not closed by a '---' line")


def _needs_quotes(s, in_flow):
    if s == "":
        return True
    if "'" in s or '"' in s:
        return True
    if s != s.strip() or "\n" in s or "\r" in s or "\t" in s:
        return True
    if s[0] in _SPECIAL_START:
        return True
    if ": " in s or s.endswith(":") or " #" in s:
        return True
    if s in ("~", "null", "Null", "NULL", "true", "True", "false", "False"):
        return True
    if RE_INT.match(s) or RE_FLOAT.match(s):
        return True
    if in_flow and any(c in s for c in ",[]{}"):
        return True
    return False


def _fmt_scalar(v, in_flow=False):
    if v is None:
        return "null" if in_flow else ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if not isinstance(v, str):
        raise FrontmatterError("unsupported value type %s" % type(v).__name__)
    return json.dumps(v, ensure_ascii=False) if _needs_quotes(v, in_flow) else v


def write_frontmatter(meta, body=""):
    """Render ``meta`` (insertion order kept) and ``body`` as a Markdown file with LF.

    Scalars are written bare unless they would read back differently, then as a
    JSON double-quoted string. Lists are written inline (``[a, b]``), dicts as a
    one-level block map indented by two spaces, None as an empty value.
    Nested collections raise FrontmatterError.
    """
    out = ["---"]
    for key, val in meta.items():
        if not RE_KEY.match(str(key) + ":"):
            raise FrontmatterError("bad key %r" % key)
        if isinstance(val, (list, tuple)):
            if any(isinstance(x, (list, tuple, dict)) for x in val):
                raise FrontmatterError("nested collections are not supported (%s)" % key)
            out.append("%s: [%s]" % (key, ", ".join(_fmt_scalar(x, True) for x in val)))
        elif isinstance(val, dict):
            if not val:
                out.append("%s: {}" % key)
                continue
            out.append("%s:" % key)
            for sk, sv in val.items():
                if not RE_KEY.match(str(sk) + ":"):
                    raise FrontmatterError("bad key %r under %r" % (sk, key))
                if isinstance(sv, (list, tuple, dict)):
                    raise FrontmatterError("nested collections are not supported (%s.%s)"
                                           % (key, sk))
                s = _fmt_scalar(sv)
                out.append(("  %s: %s" % (sk, s)) if s != "" else ("  %s:" % sk))
        else:
            s = _fmt_scalar(val)
            out.append(("%s: %s" % (key, s)) if s != "" else ("%s:" % key))
    out.append("---")
    return "\n".join(out) + "\n" + body.replace("\r\n", "\n")


# ----------------------------------------------------------------------------
# Files and ids
# ----------------------------------------------------------------------------

def atomic_write(path, text, newline="\n"):
    """Write ``text`` (UTF-8, no BOM) to ``path`` atomically.

    Line endings are normalised to LF and then written as ``newline`` ('\\n' for
    every academy file; '\\r\\n' only for a home file that is CRLF, e.g. a paper's
    sections). The data goes to a temporary file in the same directory which then
    replaces ``path``; the replace is retried briefly because Windows refuses it
    while an editor or indexer holds the target open.
    """
    path = os.path.abspath(str(path))
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    data = text.replace("\r\n", "\n")
    if newline != "\n":
        data = data.replace("\n", newline)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".part", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp, path)
                return path
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


ID_KINDS = {"ticket": "T", "packet": "P"}
IDS_DIR = ".ids"
LOCK_NAME = "lock"
LOCK_STALE_SECONDS = 30.0


class IdLock(object):
    """Exclusive lock on ``<board>/.ids/lock`` (O_CREAT|O_EXCL), a context manager.

    The lock file holds 'pid timestamp'. A lock older than LOCK_STALE_SECONDS is
    taken to belong to a crashed process and is broken. Raises LockTimeout after
    ``timeout`` seconds.
    """

    def __init__(self, board, timeout=10.0):
        self.path = os.path.join(str(board), IDS_DIR, LOCK_NAME)
        self.timeout = timeout

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
                    fh.write("%d %f\n" % (os.getpid(), time.time()))
                return self
            except FileExistsError:
                try:
                    age = time.time() - os.path.getmtime(self.path)
                    if age > LOCK_STALE_SECONDS:
                        os.remove(self.path)
                        continue
                except OSError:
                    continue
                if time.monotonic() > deadline:
                    raise LockTimeout("could not lock %s" % self.path)
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except OSError:
            pass
        return False


def _max_id_on_disk(board, prefix):
    rx = re.compile(r"^%s-(\d+)(?:-.*)?\.md$" % prefix)
    best = 0
    for dirpath, dirnames, filenames in os.walk(str(board)):
        dirnames[:] = [d for d in dirnames if d not in (".git", IDS_DIR)]
        for f in filenames:
            m = rx.match(f)
            if m:
                best = max(best, int(m.group(1)))
    return best


def format_id(prefix, n):
    """'T', 7 -> 'T-0007' (at least four digits, never truncated)."""
    return "%s-%04d" % (prefix, n)


def allocate_id(board, kind):
    """Allocate the next id of ``kind`` ('ticket'|'packet', or 'T'|'P') on ``board``.

    Under the lock: read ``<board>/.ids/next-<kind>`` (the next free number, one
    integer and a newline), take the maximum of it and one past the highest id
    already on disk (so a lost or stale counter can never reissue an id), write
    back that number plus one, and return the formatted id ('T-0001').
    """
    kind = {"T": "ticket", "P": "packet"}.get(kind, kind)
    if kind not in ID_KINDS:
        raise AcademyError("unknown id kind %r" % kind)
    prefix = ID_KINDS[kind]
    counter = os.path.join(str(board), IDS_DIR, "next-" + kind)
    with IdLock(board):
        n = 1
        try:
            with open(counter, "r", encoding="utf-8") as fh:
                n = int(fh.read().strip() or "1")
        except (OSError, ValueError):
            n = 1
        n = max(n, _max_id_on_disk(board, prefix) + 1)
        atomic_write(counter, "%d\n" % (n + 1))
    return format_id(prefix, n)
