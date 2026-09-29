"""library_* tools: the Expert's paper cache (plan sections 3.4, 5, 6 and 8).

The library home is the Expert instance's home (the ``expert@...`` home of workspace.json): files
named by bibliography key (``<key>.txt`` extraction, ``<key>.pdf``, ``<key>.src/``,
``<key>.meta``), ``index.md`` (one table row per cached source) and, once they
exist, ``cards/<key>/<pinpoint>.md``.

Derived state lives in ``<library home>/.academy/`` (created with its own
``.gitignore`` of ``*``, so it is ignored whatever the home's git setup):

    academy.sqlite   FTS5 index over the .txt pages, the index rows and the cards,
                     refreshed incrementally (mtime + size) before each search
    access.log       one tab-separated line per access, feeding hot.md:
                     <iso time>  <tool>  <caller>  <key or query>

Everything here is read-only on the library's own files.
"""

import datetime
import os
import re
import sqlite3
import unicodedata

import academy_common as ac

from . import Tool, ToolError, obj, S, I, B

DERIVED = ".academy"
CHUNK = 3000
STOP = set("a an the of in on to and or for is are be by with as at that this it its "
           "from what does do which who whom how".split())
RE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")


# ----------------------------------------------------------------------------
# Paths, access log
# ----------------------------------------------------------------------------

def library_home(ctx):
    experts = ctx.instances_by_role("expert", ctx.my_domains() or None) \
        or ctx.instances_by_role("expert")
    if not experts:
        raise ToolError("no expert instance (library home) in workspace.json")
    home = ctx.home_of(experts[0])
    if not os.path.isdir(home):
        raise ToolError("library home %s does not exist" % home)
    return home


def derived_dir(home):
    d = os.path.join(home, DERIVED)
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    gi = os.path.join(d, ".gitignore")
    if not os.path.isfile(gi):
        ac.atomic_write(gi, "# derived by the academy MCP server; never committed\n*\n")
    return d


DEFAULT_ACCESS_LOG = DERIVED + "/access.log"


def access_log_path(home):
    """The access log of a library home: ``expert.accessLog`` of its academy.json
    (relative to the home), else ``.academy/access.log``. ``hot.py`` reads this
    path (plus the default one), so the writer and the reader agree."""
    rel = DEFAULT_ACCESS_LOG
    cfg = None
    if os.path.isfile(os.path.join(home, ".claude", "academy.json")):
        try:
            cfg = ac.load_config(home)
        except ac.AcademyError:
            cfg = None
    if cfg and cfg.get("role") == "expert":
        rel = (cfg.get("expert") or {}).get("accessLog") or rel
    return os.path.join(home, rel)


def log_access(ctx, home, tool, what):
    who = ctx.agent or ac.HUMAN
    line = "%s\t%s\t%s\t%s\n" % (datetime.datetime.now().isoformat(timespec="seconds"),
                                 tool, who, " ".join(str(what).split()))
    derived_dir(home)                   # keeps .academy/ and its .gitignore in place
    path = access_log_path(home)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)


def _check_key(key):
    if not key or not RE_KEY.match(key):
        raise ToolError("a library key looks like ABC21 or ABC21-published (a references.bib key), got %r" % key)
    return key


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ----------------------------------------------------------------------------
# index.md
# ----------------------------------------------------------------------------

def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_index(text):
    """Rows of the first Markdown table whose header has a 'key' column.

    Returns a list of dicts keyed by the lower-cased header names, plus ``_line``
    (1-based) and ``_raw``.
    """
    rows, header = [], None
    lines = text.replace("\r\n", "\n").split("\n")
    for i, ln in enumerate(lines, 1):
        if not ln.strip().startswith("|"):
            if rows:
                break                   # the end of the first keyed table
            continue
        cells = _cells(ln)
        if header is None:
            low = [c.lower() for c in cells]
            if "key" in low:
                header = low
            continue
        if all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
            continue
        row = {header[j] if j < len(header) else "col%d" % j: c for j, c in enumerate(cells)}
        row["key"] = row.get("key", "").strip("`* ")
        row["_line"], row["_raw"] = i, ln
        if row["key"]:
            rows.append(row)
    return rows


def load_index(home):
    p = os.path.join(home, "index.md")
    if not os.path.isfile(p):
        return []
    return parse_index(_read(p))


# ----------------------------------------------------------------------------
# Quote normalisation (library_verify_quote)
# ----------------------------------------------------------------------------

SOFT = "\x00"   # marks a line-end hyphen removed from the extraction
FOLD = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-",
        "\u2014": "-", "\u2212": "-", "\u00a0": " ", "\u00ad": ""}


def _fold(s):
    s = unicodedata.normalize("NFKC", s)
    return "".join(FOLD.get(c, c) for c in s)


def normalise_text(s):
    """Extraction text -> one-space text; a hyphen at a line end becomes SOFT."""
    s = _fold(s.replace("\r\n", "\n"))
    s = re.sub(r"-[ \t]*\n[ \t\f]*", SOFT, s)
    return re.sub(r"\s+", " ", s)


def normalise_quote(q):
    return re.sub(r"\s+", " ", _fold(q)).strip()


def quote_regex(q):
    """A regex matching ``q`` in normalised text, across removed line-end hyphens.

    A SOFT mark may sit between any two characters (a word broken over a line:
    'exam-/ple' matches 'example'), and a '-' in the quote also matches a
    SOFT mark (a real hyphen at a line end: 'non-/trivial' matches 'non-trivial').
    """
    parts = []
    for c in q:
        parts.append("(?:-|%s)" % SOFT if c == "-" else re.escape(c))
    return re.compile(("%s?" % SOFT).join(parts))


def find_quote(text, quote):
    """(page or None, context) of ``quote`` in extraction ``text``, or None."""
    q = normalise_quote(quote)
    if not q:
        return None
    rx = quote_regex(q)
    pages = text.split("\f")
    for n, page in enumerate(pages, 1):
        m = rx.search(normalise_text(page))
        if m:
            t = normalise_text(page)
            return (n if len(pages) > 1 else None,
                    t[max(0, m.start() - 80):m.end() + 80].replace(SOFT, "-"))
    t = normalise_text(text)
    m = rx.search(t)
    if m:
        return (None, t[max(0, m.start() - 80):m.end() + 80].replace(SOFT, "-"))
    return None


# ----------------------------------------------------------------------------
# FTS5 index
# ----------------------------------------------------------------------------

SCHEMA = """
create table if not exists files (path text primary key, mtime real, size integer);
create virtual table if not exists docs using fts5(
    path unindexed, key, kind, loc, text, tokenize = 'porter unicode61');
"""


def _sources(home):
    out = []
    idx = os.path.join(home, "index.md")
    if os.path.isfile(idx):
        out.append(("index.md", idx))
    for f in sorted(os.listdir(home)):
        if f.endswith(".txt") and os.path.isfile(os.path.join(home, f)):
            out.append((f, os.path.join(home, f)))
    cards = os.path.join(home, "cards")
    if os.path.isdir(cards):
        for dp, dn, fn in os.walk(cards):
            for f in sorted(fn):
                if f.endswith(".md"):
                    full = os.path.join(dp, f)
                    out.append((os.path.relpath(full, home).replace("\\", "/"), full))
    return out


def _docs_for(rel, full):
    text = _read(full)
    if rel == "index.md":
        return [(r["key"], "index", "index.md:%d" % r["_line"], r["_raw"])
                for r in parse_index(text)]
    if rel.startswith("cards/"):
        parts = rel.split("/")
        key = parts[1] if len(parts) > 2 else os.path.splitext(parts[-1])[0]
        return [(key, "card", rel, text)]
    key = os.path.splitext(rel)[0]
    out = []
    pages = text.split("\f")
    if len(pages) > 1:
        for n, p in enumerate(pages, 1):
            if p.strip():
                out.append((key, "text", "p.%d" % n, p))
    else:
        for n in range(0, len(text), CHUNK):
            out.append((key, "text", "chunk %d" % (n // CHUNK + 1), text[n:n + CHUNK]))
    return out


def open_index(home, refresh=True):
    """Open (and incrementally refresh) ``.academy/academy.sqlite``."""
    db = sqlite3.connect(os.path.join(derived_dir(home), "academy.sqlite"))
    db.executescript(SCHEMA)
    if not refresh:
        return db, 0
    known = dict((p, (m, s)) for p, m, s in db.execute("select path, mtime, size from files"))
    seen, changed = set(), 0
    with db:
        for rel, full in _sources(home):
            st = os.stat(full)
            seen.add(rel)
            if known.get(rel) == (st.st_mtime, st.st_size):
                continue
            db.execute("delete from docs where path = ?", (rel,))
            db.executemany("insert into docs (path, key, kind, loc, text) values (?,?,?,?,?)",
                           [(rel,) + d for d in _docs_for(rel, full)])
            db.execute("insert or replace into files values (?,?,?)",
                       (rel, st.st_mtime, st.st_size))
            changed += 1
        for rel in set(known) - seen:
            db.execute("delete from docs where path = ?", (rel,))
            db.execute("delete from files where path = ?", (rel,))
            changed += 1
    return db, changed


def fts_query(q):
    """Natural-language text -> an FTS5 OR-query of its content words."""
    words = [w for w in re.findall(r"\w+", q.lower()) if w not in STOP and len(w) > 1]
    if not words:
        raise ToolError("the query has no searchable words")
    return " OR ".join('"%s"' % w.replace('"', "") for w in dict.fromkeys(words))


# ----------------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------------

def _lookup(ctx, a):
    home = library_home(ctx)
    key = _check_key(a.get("key"))
    rows = [r for r in load_index(home) if r["key"] == key]
    files = {ext: os.path.exists(os.path.join(home, key + ext))
             for ext in (".txt", ".pdf", ".meta", ".src")}
    out = {"key": key, "home": home.replace("\\", "/"),
           "index_row": {k: v for k, v in rows[0].items() if not k.startswith("_")}
           if rows else None, "files": files}
    if files[".meta"]:
        out["meta"] = _read(os.path.join(home, key + ".meta"))[:4000]
    src = os.path.join(home, key + ".src")
    if os.path.isdir(src):
        out["src_tex"] = sorted(os.path.relpath(os.path.join(dp, f), home).replace("\\", "/")
                                for dp, dn, fn in os.walk(src) for f in fn
                                if f.endswith(".tex"))[:50]
    cards = os.path.join(home, "cards", key)
    out["cards"] = sorted(os.listdir(cards)) if os.path.isdir(cards) else []
    if not rows and not any(files.values()):
        out["note"] = "not in the library (no index row, no cached file)"
    log_access(ctx, home, "library_lookup", key)
    return out


def _search(ctx, a):
    home = library_home(ctx)
    q = str(a.get("query") or "").strip()
    if not q:
        raise ToolError("query is required")
    limit = max(1, min(int(a.get("limit") or 10), 50))
    match = q if a.get("raw") else fts_query(q)
    db, changed = open_index(home)
    try:
        sql = ("select key, kind, loc, snippet(docs, 4, '[', ']', ' ... ', 16), bm25(docs) "
               "from docs where docs match ?")
        params = [match]
        if a.get("kind"):
            sql += " and kind = ?"
            params.append(a["kind"])
        if a.get("key"):
            sql += " and key = ?"
            params.append(a["key"])
        sql += " order by bm25(docs) limit ?"
        params.append(limit)
        try:
            rows = db.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            raise ToolError("bad FTS query %r: %s" % (match, exc))
    finally:
        db.close()
    log_access(ctx, home, "library_search", q)
    return {"query": q, "fts": match, "reindexed_files": changed,
            "hits": [{"key": k, "kind": kd, "loc": loc, "snippet": " ".join(sn.split()),
                      "score": round(sc, 3)} for k, kd, loc, sn, sc in rows],
            "note": "text hits come from pdftotext extractions: quote them as extraction, "
                    "and confirm pinpoints against the source"}


def _verify_quote(ctx, a):
    home = library_home(ctx)
    key = _check_key(a.get("key"))
    quote = a.get("quote") or ""
    if not normalise_quote(quote):
        raise ToolError("quote is required")
    path = os.path.join(home, key + ".txt")
    if not os.path.isfile(path):
        raise ToolError("%s.txt is not cached in %s; nothing to verify against" % (key, home))
    hit = find_quote(_read(path), quote)
    log_access(ctx, home, "library_verify_quote", key)
    res = {"key": key, "match": hit is not None, "source": "%s.txt (extraction)" % key,
           "normalised_quote": normalise_quote(quote)}
    if hit:
        res["page"], res["context"] = hit
    else:
        res["note"] = ("no whitespace/hyphenation-normalised match in the extraction; "
                       "the quote is not verified")
    return res


def _bib_keys(ctx):
    bibs = []
    for name in ctx.instances_by_role("author"):
        p = os.path.join(ctx.home_of(name), "references.bib")
        if os.path.isfile(p):
            bibs.append((name, p))
    out = {}
    for name, p in bibs:
        keys = re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", _read(p))
        out["%s:references.bib" % name] = keys
    return out


def _missing(ctx, a):
    home = library_home(ctx)
    rows = load_index(home)
    indexed = {r["key"] for r in rows}
    cached = set()
    for f in os.listdir(home):
        full = os.path.join(home, f)
        if f.endswith(".src") and os.path.isdir(full):
            cached.add(f[:-4])
        elif os.path.isfile(full) and os.path.splitext(f)[1] in (".txt", ".pdf", ".meta"):
            cached.add(os.path.splitext(f)[0])
    out = {
        "cached_without_index_row": sorted(cached - indexed),
        "indexed_without_txt": sorted(k for k in indexed
                                      if not os.path.isfile(os.path.join(home, k + ".txt"))),
        "indexed_without_meta": sorted(k for k in indexed
                                       if not os.path.isfile(os.path.join(home, k + ".meta"))),
    }
    if a.get("bib", True):
        out["bib_keys_not_in_library"] = {
            bib: sorted(set(keys) - indexed - cached) for bib, keys in _bib_keys(ctx).items()}
    log_access(ctx, home, "library_missing", "-")
    return out


TOOLS = [
    Tool("library_lookup", "What the library holds for one key: index row, cached files, "
         "meta, source .tex files, cards. Access-logged.",
         obj({"key": S}, ["key"]), _lookup),
    Tool("library_search", "Full-text (FTS5) search over the cached extractions, index "
         "rows and cards; natural-language query, or raw FTS5 syntax with raw=true. "
         "Access-logged.",
         obj({"query": S, "limit": I, "kind": {"type": "string",
                                               "enum": ["text", "index", "card"]},
              "key": S, "raw": B}, ["query"]), _search),
    Tool("library_verify_quote", "Check that a quote occurs in <key>.txt, normalising "
         "whitespace, line-end hyphenation, ligatures and typographic quotes/dashes "
         "(case-sensitive). Access-logged.",
         obj({"key": S, "quote": S}, ["key", "quote"]), _verify_quote),
    Tool("library_missing", "Gaps in the library: cached files with no index row, rows "
         "with no .txt or .meta, and bibliography keys with nothing cached.",
         obj({"bib": B}), _missing),
]
