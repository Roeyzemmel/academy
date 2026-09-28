"""The registry dialect: kb.py's strict frontmatter parser and serializer.

This is the one dialect of every registry (plan section 6, merge proposal "Core").
It is kb.py's code, moved here unchanged except for three parameters:

* ``parse_frontmatter(..., empty=f)``: a profile may accept a key with no value and
  no block (``evidence:`` alone) as that key's empty value ``f(key)``. kb.py rejects it
  (``empty=None``, the default); the fsl-claims profile opts in, because its records
  and its acceptance tests were written that way. The serializer never writes it.
* ``serialize_frontmatter(d, order=..., block=...)``: the canonical field order is the
  profile's, and a profile may write chosen list fields as block lists (one ``- item``
  per line) instead of inline ``[a, b]``.
* ``split_document`` strips a leading BOM (it always did) and keeps CR handling.

Frontmatter subset (anything else is rejected with file:line):
  * the file starts with a line `---` and the frontmatter ends at the next `---`;
  * blank lines and full-line `# comments` are ignored; tabs may not indent;
  * top level: `key: value`, key matching [A-Za-z_][A-Za-z0-9_]*, one space after ':';
  * a value is one of
      - a bare scalar (no leading - [ ] { } ' " # & * ! | > % @ ` ? : ,
        no ': ' and no ' #' inside; a trailing ` # comment` is stripped);
      - a 'single-quoted' ('' = ') or "double-quoted" string (escapes \\\\ \\" \\n \\t \\r \\/);
      - an inline list [a, b, "c, d"] of scalars (no nesting, no trailing comma), or [];
      - {} (the empty map);
      - nothing, followed by either a block list (lines `- scalar`, indented or not)
        or ONE level of nested map (indented `key: value`, value a scalar or inline
        list; the key is bare up to the first ': ' or quoted).
  * every scalar is a string (dates and numbers stay strings).
"""
from __future__ import annotations

import re


class FrontmatterError(ValueError):
    """A frontmatter line outside the supported YAML subset."""

    def __init__(self, text, path=None, lineno=None, msg=None):
        super().__init__(text)
        self.path, self.lineno, self.msg = path, lineno, msg if msg is not None else text


def _fail(path, lineno, msg):
    raise FrontmatterError(f"{path}:{lineno}: {msg}", path, lineno, msg)


def _is_skippable(line: str) -> bool:
    s = line.strip()
    return s == "" or s.startswith("#")


def _expect_end(rest, path, ln):
    r = rest.strip()
    if r and not r.startswith("#"):
        _fail(path, ln, f"unexpected text after value: {r!r}")


ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r", "/": "/"}
BAD_START = set("[]{}&*!|>%@`,?:'\"")


def _parse_quoted(s, pos, path, ln):
    """Parse a quoted string starting at s[pos]; return (value, rest-of-line)."""
    quote, i, out = s[pos], pos + 1, []
    while i < len(s):
        c = s[i]
        if quote == "'" and c == "'":
            if s[i + 1:i + 2] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), s[i + 1:]
        if quote == '"' and c == "\\":
            esc = s[i + 1:i + 2]
            if esc not in ESCAPES:
                _fail(path, ln, f"unsupported escape '\\{esc}' in double-quoted string")
            out.append(ESCAPES[esc])
            i += 2
            continue
        if quote == '"' and c == '"':
            return "".join(out), s[i + 1:]
        out.append(c)
        i += 1
    _fail(path, ln, "unterminated quoted string")


def parse_scalar(s, path, ln):
    s = s.strip()
    if s[:1] in ("'", '"'):
        value, rest = _parse_quoted(s, 0, path, ln)
        _expect_end(rest, path, ln)
        return value
    if s.startswith("- ") or s == "-":
        _fail(path, ln, "a block-list item is not allowed here")
    if s[:1] in BAD_START:
        _fail(path, ln, f"unsupported YAML syntax starting with {s[0]!r}; quote the value")
    s = re.split(r"\s#", s, maxsplit=1)[0].rstrip()
    if s == "":
        _fail(path, ln, "empty value")
    if ": " in s or s.endswith(":"):
        _fail(path, ln, "a bare value may not contain ': ' or end with ':'; quote it")
    return s


_BARE_ITEM = re.compile(r"[^,\[\]{}]*")


def _parse_inline_list(s, path, ln):
    """Parse '[a, b, "c"]' at the start of s; return (items, rest-of-line)."""
    i, items = 1, []
    while True:
        while i < len(s) and s[i] == " ":
            i += 1
        if i >= len(s):
            _fail(path, ln, "unterminated inline list")
        if s[i] == "]" and not items:
            return items, s[i + 1:]
        if s[i] in "[{":
            _fail(path, ln, "nested lists or maps are not supported")
        if s[i] in "'\"":
            val, rest = _parse_quoted(s, i, path, ln)
            i = len(s) - len(rest)
        else:
            m = _BARE_ITEM.match(s, i)
            val, i = m.group(0).strip(), m.end()
            if not val:
                _fail(path, ln, "empty item in inline list")
            if val[0] in "&*!|>%@`#":
                _fail(path, ln, f"unsupported syntax in list item {val!r}; quote it")
        items.append(val)
        while i < len(s) and s[i] == " ":
            i += 1
        if i < len(s) and s[i] == ",":
            i += 1
            continue
        if i < len(s) and s[i] == "]":
            return items, s[i + 1:]
        _fail(path, ln, "expected ',' or ']' in inline list")


def parse_value(s, path, ln):
    s = s.strip()
    if s.startswith("["):
        items, rest = _parse_inline_list(s, path, ln)
    elif s.startswith("{"):
        if not s.startswith("{}"):
            _fail(path, ln, "flow maps {...} are not supported; use an indented block")
        items, rest = {}, s[2:]
    else:
        return parse_scalar(s, path, ln)
    _expect_end(rest, path, ln)
    return items


def _indent_of(line, path, ln):
    ws = line[:len(line) - len(line.lstrip(" \t"))]
    if "\t" in ws:
        _fail(path, ln, "tabs may not be used for indentation")
    return len(ws)


def _parse_nested_entry(line, path, ln):
    s = line.strip()
    if s[:1] in ("'", '"'):
        key, rest = _parse_quoted(s, 0, path, ln)
        if not rest.startswith(": "):
            _fail(path, ln, "expected ': value' after quoted key")
        value = rest[2:]
    else:
        idx = s.find(": ")
        if idx <= 0:
            _fail(path, ln, "expected '  key: value' in nested map")
        key, value = s[:idx].rstrip(), s[idx + 2:]
        if "#" in key or key[0] in BAD_START or key.startswith("- "):
            _fail(path, ln, f"unsupported nested key {key!r}; quote it")
    parsed = parse_value(value, path, ln)
    if isinstance(parsed, dict):
        _fail(path, ln, "maps nested more than one level are not supported")
    return key, parsed


def _parse_block(block, path, first_ln, key, empty=None):
    items = [(first_ln + k, l) for k, l in enumerate(block) if not _is_skippable(l)]
    if not items:
        if empty is not None:
            return empty(key)
        _fail(path, first_ln - 1, f"'{key}' has no value; write \"\" or [] or {{}}")
    if items[0][1].lstrip().startswith("-"):
        out = []
        for ln, line in items:
            _indent_of(line, path, ln)
            s = line.strip()
            if not s.startswith("- "):
                _fail(path, ln, "expected '- item' in block list")
            out.append(parse_scalar(s[2:], path, ln))
        return out
    out, indent = {}, None
    for ln, line in items:
        ind = _indent_of(line, path, ln)
        if ind == 0 or (indent is not None and ind != indent):
            _fail(path, ln, "nested map entries must share one indentation")
        indent = ind
        k, v = _parse_nested_entry(line, path, ln)
        if k in out:
            _fail(path, ln, f"duplicate nested key '{k}'")
        out[k] = v
    return out


def _block_end(lines, j):
    while j < len(lines):
        line = lines[j]
        if _is_skippable(line) or line[:1] in (" ", "\t") or line.startswith("-"):
            j += 1
        else:
            break
    return j


_KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")


def parse_frontmatter(lines, path="<string>", first_lineno=1, empty=None) -> dict:
    """Parse frontmatter lines (without the --- fences) into a dict.

    ``empty(key)``, when given, is the value of a key with neither a value nor a block
    (kb.py rejects that; the default)."""
    data, i = {}, 0
    while i < len(lines):
        line, ln = lines[i], first_lineno + i
        if _is_skippable(line):
            i += 1
            continue
        if line[:1] in (" ", "\t"):
            _fail(path, ln, "unexpected indentation")
        m = _KEY_LINE.match(line)
        if not m:
            _fail(path, ln, f"expected 'key: value', got {line!r}")
        key, rest = m.group(1), m.group(2)
        if key in data:
            _fail(path, ln, f"duplicate key '{key}'")
        if rest and not rest[0].isspace():
            _fail(path, ln, "a space is required after ':'")
        if _is_skippable(rest):
            j = _block_end(lines, i + 1)
            data[key] = _parse_block(lines[i + 1:j], path, ln + 1, key, empty)
            i = j
        else:
            data[key] = parse_value(rest, path, ln)
            i += 1
    return data


def fence_lines(text):
    """(lines, close) of a document: its lines split on LF (CR kept) and the index of
    the closing fence, or (lines, None) when there is no frontmatter."""
    lines = text.lstrip("\ufeff").split("\n")
    if lines[0].rstrip("\r") != "---":
        return lines, None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") == "---":
            return lines, i
    return lines, -1


def split_document(text, path="<string>", empty=None):
    """Split a markdown file into (frontmatter dict, body text)."""
    lines = text.lstrip("\ufeff").split("\n")
    if lines[0].rstrip("\r") != "---":
        _fail(path, 1, "file must start with a '---' frontmatter line")
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") == "---":
            meta = parse_frontmatter([l.rstrip("\r") for l in lines[1:i]], path, 2, empty)
            return meta, "\n".join(lines[i + 1:])
    _fail(path, 1, "frontmatter is not closed by a '---' line")


def needs_quotes(s: str) -> bool:
    if s == "" or s != s.strip() or s[0] in "-[]{}'\"#&*!|>%@`?:,":
        return True
    if any(t in s for t in (": ", " #", "\n", "\t", "\r", ",", "[", "]", "{", "}")):
        return True
    return s.endswith(":")


_needs_quotes = needs_quotes


def double_quote(s: str) -> str:
    s = (s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
         .replace("\t", "\\t").replace("\r", "\\r"))
    return f'"{s}"'


_double_quote = double_quote


def format_scalar(s) -> str:
    if not isinstance(s, str):
        raise TypeError(f"frontmatter scalars must be strings, got {type(s).__name__}")
    return double_quote(s) if needs_quotes(s) else s


def needs_quotes_outside_flow(s: str) -> bool:
    """Whether a scalar needs quotes where it is not an item of an inline list (a
    top-level value or a block-list item): there, commas and inner brackets are plain
    text to :func:`parse_scalar`, so only the starts, ': ', ' #', a trailing ':' and
    control characters need quotes."""
    if s == "" or s != s.strip() or s[0] in "-[]{}'\"#&*!|>%@`?:,":
        return True
    if any(t in s for t in (": ", " #", "\n", "\t", "\r")):
        return True
    return s.endswith(":")


def format_scalar_single(s) -> str:
    """The fsl-claims profile's scalar style: quotes only where :func:`parse_scalar`
    needs them outside an inline list (:func:`needs_quotes_outside_flow`), and a value
    that needs quotes and holds a backslash or a double quote (LaTeX) is single-quoted,
    which keeps it as written; a value with a newline, tab or CR is double-quoted. Same
    dialect, easier to read. Never used for inline-list items."""
    if not isinstance(s, str):
        raise TypeError(f"frontmatter scalars must be strings, got {type(s).__name__}")
    if not needs_quotes_outside_flow(s):
        return s
    if ("\\" in s or '"' in s) and not any(c in s for c in "\n\t\r"):
        return "'" + s.replace("'", "''") + "'"
    return double_quote(s)


def format_list(items, fmt=None) -> str:
    """An inline list; its items always in kb.py's style (``fmt`` is ignored: commas and
    brackets are syntax inside a flow list)."""
    return "[" + ", ".join(format_scalar(x) for x in items) + "]"


def format_value(v, fmt=None) -> str:
    return format_list(v) if isinstance(v, list) else (fmt or format_scalar)(v)


_format_value = format_value


def ordered_keys(d, order=()):
    return [k for k in order if k in d] + sorted(k for k in d if k not in order)


def serialize_frontmatter(d: dict, order=(), block=(), fmt=None) -> str:
    """Serialize a dict to frontmatter lines (without fences), in the field order
    ``order`` (then the other keys sorted). List fields named in ``block`` are written
    one ``  - item`` per line (``[]`` when empty); every other list inline. ``fmt``
    formats a scalar (default :func:`format_scalar`, kb.py's)."""
    fmt = fmt or format_scalar
    out = []
    for key in ordered_keys(d, order):
        v = d[key]
        if isinstance(v, dict):
            if not v:
                out.append(f"{key}: {{}}")
                continue
            out.append(f"{key}:")
            for k, sub in v.items():
                kk = double_quote(k) if (needs_quotes(k) or ":" in k or "#" in k) else k
                out.append(f"  {kk}: {format_value(sub, fmt)}")
        elif isinstance(v, list) and key in block and v:
            out.append(f"{key}:")
            out += [f"  - {fmt(x)}" for x in v]
        else:
            out.append(f"{key}: {format_value(v, fmt)}")
    return "\n".join(out) + "\n"


def serialize_document(meta: dict, body: str, order=(), block=(), fmt=None) -> str:
    return "---\n" + serialize_frontmatter(meta, order, block, fmt) + "---\n" + body
