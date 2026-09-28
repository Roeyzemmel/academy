"""hot.py -- build hot.md, the clerk's digest of the most-accessed sources and claims.

    py hot.py [--home H] [--log FILE ...] [--size N] [--out FILE] [--stdout]

Reads the access log the academy MCP server appends to on every ``library_*`` call
(``<library home>/.academy/access.log``; one tab-separated line
``<iso time> <tool> <caller> <key or query>``) and, when present, the log named by
the home's ``expert.accessLog``. Counts accesses per bibliography key (lookups,
quote checks, and search hits are not counted -- the key of a search is unknown),
per search query, and per claim id (any ``claims_*`` line), and writes the top
``--size`` (default ``expert.hotSize``, else 50) as ``hot.md``: for each key its
index row and its cards, so the clerk answers the common questions from one file.

``hot.md`` is a generated view (docs/protocol.md section 7.1): it carries the
do-not-edit marker, and the fix for a wrong line is a better card or index row,
then a rerun. Deterministic: ties are broken by the latest access, then the name.
"""

import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
import cards as cardlib  # noqa: E402

KEY_TOOLS = ("library_lookup", "library_verify_quote")
QUERY_TOOLS = ("library_search",)
DEFAULT_SIZE = 50
GENERATOR = "expert/scripts/hot.py"


def default_logs(home, cfg):
    logs = [os.path.join(home, ".academy", "access.log")]
    extra = ((cfg or {}).get("expert") or {}).get("accessLog")
    if extra:
        p = os.path.join(home, extra)
        if os.path.normcase(os.path.abspath(p)) != os.path.normcase(os.path.abspath(logs[0])):
            logs.append(p)
    return logs


def read_log(paths):
    """Yield ``(time, tool, caller, what)`` from each existing log, skipping bad lines."""
    for p in paths:
        if not os.path.isfile(p):
            continue
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                parts = ln.rstrip("\r\n").split("\t")
                if len(parts) < 4 or not parts[0]:
                    continue
                yield parts[0], parts[1], parts[2], "\t".join(parts[3:]).strip()


def tally(entries):
    """Counters for keys, queries and claims: ``{name: [count, last time, callers]}``."""
    keys, queries, claims = {}, {}, {}

    def bump(d, name, t, who):
        rec = d.setdefault(name, [0, "", collections.Counter()])
        rec[0] += 1
        rec[1] = max(rec[1], t)
        rec[2][who] += 1

    for t, tool, who, what in entries:
        if not what or what == "-":
            continue
        if tool in KEY_TOOLS:
            bump(keys, what.split()[0], t, who)
        elif tool in QUERY_TOOLS:
            bump(queries, what, t, who)
        elif tool.startswith("claims_"):
            bump(claims, what.split()[0], t, who)
    return keys, queries, claims


def top(d, n):
    items = sorted(d.items(), key=lambda kv: (-kv[1][0], _neg(kv[1][1]), kv[0]))
    return items[:n]


def _neg(s):
    # sort latest first without parsing: invert each character code
    return "".join(chr(0x10FFFF - ord(c)) for c in s)


def _cell(s):
    return " ".join(str(s or "").split())


def key_section(home, key, rec, rows_by_key):
    count, last, who = rec
    out = ["### %s" % key, "",
           "- accessed %d time(s), last %s; by %s" % (
               count, last, ", ".join("%s (%d)" % kv for kv in who.most_common(3)))]
    row = rows_by_key.get(key)
    if row:
        for col in ("authors, short title", "version", "how read", "source dir"):
            if row.get(col):
                out.append("- %s: %s" % (col, _cell(row[col])))
    else:
        out.append("- **no index row** (the librarian fills it: /expert:library-index)")
    cards = list(cardlib.iter_cards(home, key))
    if cards:
        out.append("- cards:")
        for p in cards:
            try:
                meta, body = cardlib.read_card(p)
            except (OSError, ac.AcademyError, UnicodeDecodeError):
                continue
            stmt = cardlib.sections(body).get("## Statement", "")
            first = _cell(stmt.split("\n\n")[0])[:220]
            rel = os.path.relpath(p, home).replace("\\", "/")
            out.append("  - **%s** (%s, %s%s) `%s`: %s" % (
                meta.get("pinpoint"), meta.get("version") or "version?",
                meta.get("read_from") or "?",
                (", " + meta["verdict"]) if meta.get("verdict") else "", rel, first))
    else:
        out.append("- cards: none yet")
    out.append("")
    return out


def build(home, logs, size):
    keys, queries, claims = tally(read_log(logs))
    rows = {r["key"]: r for r in ex.library().load_index(home)}
    lines = [ex.GENERATED % GENERATOR, "", "# Hot: the most-accessed sources and claims", "",
             "Built from %s. Top %d by access count. Statuses are not stored here: ask "
             "`claims_show` for a claim's current status." % (
                 ", ".join("`%s`" % os.path.relpath(p, home).replace("\\", "/")
                           for p in logs if os.path.isfile(p)) or "no access log yet",
                 size), ""]
    lines += ["## Sources", ""]
    tk = top(keys, size)
    if not tk:
        lines += ["None accessed yet.", ""]
    for key, rec in tk:
        lines += key_section(home, key, rec, rows)
    lines += ["## Claims", ""]
    tc = top(claims, size)
    lines += (["| claim | accesses | last |", "|---|---|---|"] +
              ["| `%s` | %d | %s |" % (c, r[0], r[1]) for c, r in tc] + [""]) if tc \
        else ["None accessed yet.", ""]
    lines += ["## Searches", ""]
    tq = top(queries, min(size, 20))
    lines += (["| query | times | last |", "|---|---|---|"] +
              ["| %s | %d | %s |" % (_cell(q).replace("|", "\\|"), r[0], r[1])
               for q, r in tq] + [""]) if tq else ["None yet.", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv=None):
    ex.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home")
    ap.add_argument("--log", action="append")
    ap.add_argument("--size", type=int)
    ap.add_argument("--out")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = ap.parse_args(argv)
    home = ex.expert_home(home=args.home)
    if not home or not os.path.isdir(home):
        sys.stderr.write("hot: no library home (pass --home)\n")
        return 2
    cfg = ex.expert_config(home)
    size = args.size or ((cfg or {}).get("expert") or {}).get("hotSize") or DEFAULT_SIZE
    logs = args.log or default_logs(home, cfg)
    text = build(home, logs, int(size))
    if args.stdout:
        print(text, end="")
        return 0
    out = args.out or ex.home_path(home, cfg, "hot", "hot.md")
    ac.atomic_write(out, text)
    print("wrote %s" % out.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
