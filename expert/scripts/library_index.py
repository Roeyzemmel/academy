"""library_index.py -- keep the library's index.md in step with its cached files.

    py library_index.py missing [--home H] [--json]      cached keys with no index row
    py library_index.py propose [--home H]               a draft row per missing key, from its .meta
    py library_index.py apply   [--home H] [--dry-run]   append the draft rows to index.md

The library home is the Expert instance's home (``--home`` overrides it). Cached
files are named by bibliography key (``<key>.pdf``, ``<key>.txt``, ``<key>.meta``,
``<key>.src/``, ``<key>_eprint.tar.gz``; see the home's README.md). ``index.md``
holds one row per cached source in its first table with a ``key`` column; the rows
are parsed by the MCP server's own ``library.parse_index``.

``apply`` is the librarian's tool (plan phase 7, "fill the index"). A drafted row
fills what the ``.meta`` file states and marks every other cell ``to fill``; it
never guesses an author, title or version. Rows are appended after the last row of
the index table, keeping the file's line endings. Exit codes: 0 (``missing``: none
missing), 1 (``missing``: some missing), 2 usage error.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402

SUFFIXES = (".pdf", ".txt", ".meta")
EPRINT = "_eprint.tar.gz"
TO_FILL = "to fill"
IGNORED = ("README", "index")


# ----------------------------------------------------------------------------
# What is cached, what is indexed
# ----------------------------------------------------------------------------

def cached_keys(home):
    """``{key: sorted list of cached artefacts}`` for the files at the top of ``home``."""
    out = {}
    for f in sorted(os.listdir(home)):
        full = os.path.join(home, f)
        key, kind = None, None
        if f.endswith(".src") and os.path.isdir(full):
            key, kind = f[:-4], ".src/"
        elif os.path.isfile(full) and f.endswith(EPRINT):
            key, kind = f[:-len(EPRINT)], EPRINT
        elif os.path.isfile(full) and os.path.splitext(f)[1].lower() in SUFFIXES:
            key, kind = os.path.splitext(f)
            kind = kind.lower()
        if key and key not in IGNORED and not key.startswith("."):
            out.setdefault(key, []).append(kind)
    return {k: sorted(v) for k, v in out.items()}


def index_path(home, cfg=None):
    return ex.home_path(home, cfg, "index", "index.md")


def index_rows(home, cfg=None):
    p = index_path(home, cfg)
    if not os.path.isfile(p):
        return []
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        return ex.library().parse_index(fh.read())


def missing(home, cfg=None):
    """What is out of step: cached keys with no row, and rows with nothing cached."""
    cached = cached_keys(home)
    rows = index_rows(home, cfg)
    indexed = {r["key"] for r in rows}
    return {
        "home": home.replace("\\", "/"),
        "cached_without_index_row": {k: cached[k] for k in sorted(cached) if k not in indexed},
        "indexed_without_files": sorted(k for k in indexed if k not in cached),
        "indexed": len(indexed),
        "cached": len(cached),
    }


# ----------------------------------------------------------------------------
# Drafting rows from .meta
# ----------------------------------------------------------------------------

def read_meta(path):
    """A ``.meta`` file as ``{lower-cased field: value}``; indented lines continue."""
    out, cur = {}, None
    if not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh.read().replace("\r\n", "\n").split("\n"):
            if not ln.strip():
                continue
            m = re.match(r"^([A-Za-z][A-Za-z ()_-]*?)\s*:\s*(.*)$", ln)
            if m and not ln.startswith((" ", "\t")):
                cur = m.group(1).strip().lower()
                out[cur] = m.group(2).strip()
            elif cur:
                out[cur] += " " + ln.strip()
    return out


def _first(meta, *names):
    for n in names:
        for k, v in meta.items():
            if k == n or k.startswith(n):
                if v:
                    return v
    return ""


def _cell(s):
    return " ".join(str(s or "").split()).replace("|", "\\|") or TO_FILL


def draft_row(home, key, kinds):
    """One Markdown row for ``key`` in the index's column order."""
    meta = read_meta(os.path.join(home, key + ".meta"))
    authors = _first(meta, "authors", "author")
    title = _first(meta, "title")
    who = ""
    if authors or title:
        who = "%s, \"%s\"" % (authors or TO_FILL, title or TO_FILL)
    version = _first(meta, "version", "arxiv id")
    source = _first(meta, "source url", "source")
    if source and not source.startswith("`"):
        source = "`%s`" % source.split()[0]
    src_dir = ("`%s.src/`" % key) if ".src/" in kinds else "**no source cached**"
    how = _first(meta, "how read")
    if not how:
        how = "extraction (`.txt`)" if ".txt" in kinds else (
            "PDF only (no `.txt`)" if ".pdf" in kinds else "")
    date = _first(meta, "date fetched", "fetched", "date")
    m = re.search(r"\d{4}-\d{2}-\d{2}", date)
    date = m.group(0) if m else ""
    note = "row drafted by library_index.py from %s; cached: %s" % (
        "%s.meta" % key if meta else "the file listing (no .meta)", ", ".join(kinds))
    cells = [key, who, version, source, src_dir, how, date, note]
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def propose(home, cfg=None):
    gaps = missing(home, cfg)["cached_without_index_row"]
    return [draft_row(home, k, v) for k, v in gaps.items()]


def apply_rows(home, rows, cfg=None):
    """Append ``rows`` after the last row of the index table; returns the new text."""
    p = index_path(home, cfg)
    with open(p, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    parsed = ex.library().parse_index(text)
    if not parsed:
        raise ValueError("%s has no table with a 'key' column" % p)
    last = max(r["_line"] for r in parsed)       # 1-based line of the last row
    new = lines[:last] + list(rows) + lines[last:]
    out = nl.join(new)
    ac.atomic_write(p, out, newline=nl)
    return out


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv=None):
    ex.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("missing", "propose", "apply"))
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    home = ex.expert_home(home=args.home)
    if not home or not os.path.isdir(home):
        sys.stderr.write("library_index: no library home (pass --home)\n")
        return 2
    cfg = ex.expert_config(home)
    if args.cmd == "missing":
        res = missing(home, cfg)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            gaps = res["cached_without_index_row"]
            for k, v in gaps.items():
                print("no index row: %s (%s)" % (k, ", ".join(v)))
            for k in res["indexed_without_files"]:
                print("indexed, nothing cached: %s" % k)
            print("library: %d cached keys, %d index rows, %d without a row"
                  % (res["cached"], res["indexed"], len(gaps)))
        return 1 if res["cached_without_index_row"] else 0
    rows = propose(home, cfg)
    if args.cmd == "propose" or args.dry_run:
        for r in rows:
            print(r)
        if not rows:
            print("nothing to propose: every cached key has an index row")
        return 0
    if not rows:
        print("nothing to apply: every cached key has an index row")
        return 0
    apply_rows(home, rows, cfg)
    print("appended %d row(s) to %s" % (len(rows), index_path(home, cfg).replace("\\", "/")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
