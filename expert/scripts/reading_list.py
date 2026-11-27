"""reading_list.py -- the human's reading list: sources the librarian could not reach (#108).

    py reading_list.py [--workspace W] [--board B] [--write] [--json] [--no-deps]

When a cite ticket parks on the human because its source is unreachable (paywall, image-only
scan, blocked host), cite.js moves it to blocked with ``waiting_on [human]`` and the reason

    source unreachable from this session: <key>; a human with access reads <what> for <relying>

cut to ``REASON_MAX`` characters (cite.js ``why.slice(0, 240)``). This script collects those
tickets (to an Expert instance, blocked, ``human`` in waiting_on, whose LAST move to blocked
carries that reason) into one list, a row per unreachable source: the bib key, the source as
its Expert's index row names it (title, link), what was tried (the index row of an
unreachable source, else the summary of the ticket's last packet), exactly what to read, the
statement relying on it, the claims the ticket names, and how many registry statements rest
on those claims (``depends_on``, transitively) or bear on them or on a dependent
(``bears_on``), computed on the registry's own edges. Rows are sorted by those counts.

A reason the cut reached is marked ``[...]``, never completed by guess. A ticket parked on
an unreachable source whose reason does not parse is listed under "Could not read", never
dropped. ``--write`` writes ``<library home>/views/reading-list.md``, a generated view (do
not edit: the fix for a wrong row is the ticket or the index row, then a rerun); otherwise
the markdown goes to stdout. Read-only on the board and the registry.
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
import library_index as li  # noqa: E402

GENERATOR = "expert/scripts/reading_list.py"
OUT = os.path.join("views", "reading-list.md")
MARK = "source unreachable from this session:"
RE_LINE = re.compile(r"source unreachable from this session: (?P<key>[^;]+); a human with access reads (?P<rest>.+)$")
#: cite.js cuts the reason to 240 characters: one this long may have been cut
REASON_MAX = 240
CUT_AT = REASON_MAX - 4
RE_CLAIM = re.compile(r"^[a-z0-9]+:[A-Za-z0-9][\w.:-]*$")
# " for <claim id>": where the relying part starts (the "what" may itself say "for Prop. 5.6")
RE_FOR_CLAIM = re.compile(r" for (?=[a-z0-9]+:[A-Za-z])")
RE_BIBKEY = re.compile(r"\b[A-Z][A-Za-z-]*\d{2}[a-z]?\b")
RE_URL = re.compile(r"https?://[^\s`)>]+")
RE_DOI = re.compile(r"doi:(10\.[^\s,;`)]+)")
RE_BLOCK = re.compile(r"-> blocked\b")


def last_block(body):
    """The text after the last thread line that moves the ticket to blocked, or ''."""
    hit = ""
    for ln in (body or "").splitlines():
        if RE_BLOCK.search(ln):
            hit = ln
    return hit


def parse_reason(ln):
    """``{"keys", "key_text", "what", "relying", "truncated"}`` from the block line holding
    cite.js's reason, ``None`` when it has no such reason, ``{"unparsed": reason}`` when it
    has one this script cannot read."""
    i = ln.find(MARK)
    if i < 0:
        return None
    reason = ln[i:].strip()
    m = RE_LINE.match(reason)
    if not m:
        return {"unparsed": reason}
    truncated = len(reason) >= CUT_AT
    rest = m.group("rest").strip()
    cuts = list(RE_FOR_CLAIM.finditer(rest))
    if cuts:
        what, relying = rest[:cuts[-1].start()], rest[cuts[-1].end():]
    elif not truncated and " for " in rest:
        # a free-text relying (cite.js allows any): the last " for " starts it
        k = rest.rfind(" for ")
        what, relying = rest[:k], rest[k + len(" for "):]
    else:
        what, relying = rest, ""
    if truncated:
        # the cut fell in the last word: drop it, and a dangling "for"
        tail = relying if relying else what
        tail = re.sub(r"(\s+for)?\s+\S*$", "", tail).rstrip(" ,;") + " [...]"
        relying, what = (tail, what) if relying else ("", tail)
    key_text = m.group("key").strip()
    return {"keys": bib_keys(key_text), "key_text": key_text, "what": what.strip(),
            "relying": relying.strip(), "truncated": truncated}


def bib_keys(text):
    """The bib keys a reason's key part names, in order: "Er13 (Mo77, Th92 unreachable)"
    names three."""
    out = []
    for k in RE_BIBKEY.findall(text):
        if k not in out:
            out.append(k)
    return out or [text.split()[0].strip(",;")]


def claims_of(meta, known=None):
    """The registry ids a ticket's refs name (not tickets, files or bib keys); with
    ``known`` (a callable id -> its canonical id, or None when the registry has no such
    record), ``(canonical ids, unknown refs)``: an old label counts as the record it names."""
    out = []
    for r in meta.get("refs") or []:
        r = str(r).strip()
        if RE_CLAIM.match(r) and not r.startswith(("file:", "bib:")) and r not in out:
            out.append(r)
    if known is None:
        return out
    canon, unknown = [], []
    for c in out:
        q = known(c)
        if not q:
            unknown.append(c)
        elif q not in canon:
            canon.append(q)
    return canon, unknown


def dependents(edge_list, claims):
    """``(rest, bear)`` over ``(src, rel, dst)`` edges: ``rest``, the ids that depend on one of
    ``claims`` through ``depends_on`` chains (``src depends_on dst``); ``bear``, the ids that
    bear on a claim or on one of those (``bears_on``), less ``rest`` and the claims."""
    back_dep, back_bear = {}, {}
    for s, r, d in edge_list:
        if r == "depends_on":
            back_dep.setdefault(d, set()).add(s)
        elif r == "bears_on":
            back_bear.setdefault(d, set()).add(s)
    rest, todo = set(), list(claims)
    while todo:
        n = todo.pop()
        for s in back_dep.get(n, ()):
            if s not in rest:
                rest.add(s)
                todo.append(s)
    rest -= set(claims)
    bear = set()
    for n in set(claims) | rest:
        bear |= back_bear.get(n, set())
    return sorted(rest), sorted(bear - rest - set(claims))


def _link(row):
    m = RE_URL.search(str(row.get("source url") or ""))
    if m:
        return m.group(0)
    for f in ("version", "authors, short title", "source url"):
        m = RE_DOI.search(str(row.get(f) or ""))
        if m:
            return "https://doi.org/" + m.group(1).rstrip(".")
    return ""


def _short(x, n=400):
    x = re.sub(r"\s+", " ", str(x or "")).strip()
    return x if len(x) <= n else x[:n].rsplit(" ", 1)[0] + " [...]"


def _unread(idx):
    return "unreachable" in (str(idx.get("how read") or "") + " " + str(idx.get("source dir") or "")).lower()


def build(tickets, index_for, graph=None, packet_summary=None):
    """``(rows, unparsed)``. ``tickets``: ``(meta, body)`` pairs; ``index_for``: a callable
    ``expert instance -> {key: index row}``; ``graph``: ``(edges, known)`` with ``known`` a
    callable id -> canonical id or None (None: not counted); ``packet_summary``: a callable packet id ->
    its summary text (None: not read)."""
    rows, unparsed = [], []
    for meta, body in tickets:
        hit = parse_reason(last_block(body))
        if hit is None:
            continue
        if "unparsed" in hit:
            unparsed.append({"ticket": meta.get("id"), "reason": hit["unparsed"]})
            continue
        index = index_for(meta.get("to")) or {}
        if graph is not None:
            claims, unknown = claims_of(meta, graph[1])
            rest, bear = dependents(graph[0], claims)
        else:
            claims, unknown, rest, bear = claims_of(meta), [], None, None
        keys = hit["keys"]
        # a line naming several keys: a row for each the index does not show read
        wanted = [k for k in keys if not index.get(k) or _unread(index[k])] or keys[:1]
        packets = list(meta.get("packets") or [])
        for k in wanted:
            idx = index.get(k) or {}
            tried = _short(idx.get("used for")) if idx and _unread(idx) else ""
            if not tried and packets and packet_summary:
                tried = _short(packet_summary(packets[-1]))
            rows.append({
                "ticket": meta.get("id"), "key": k, "key_text": hit["key_text"],
                "title": str(idx.get("authors, short title") or "").strip(), "link": _link(idx),
                "tried": tried, "read": hit["what"], "for": hit["relying"] or str(meta.get("title") or ""),
                "truncated": hit["truncated"], "claims": claims, "unknown_claims": unknown,
                "rests_on_it": rest, "bears_on_it": bear, "packets": packets, "in_index": bool(idx)})
    size = lambda r: (len(r["rests_on_it"]), len(r["bears_on_it"])) if r["rests_on_it"] is not None else (-1, -1)  # noqa: E731
    rows.sort(key=lambda r: (tuple(-x for x in size(r)), str(r["ticket"]), r["key"]))
    return rows, unparsed


def render(rows, unparsed=(), generated=True):
    out = [ex.GENERATED % GENERATOR, ""] if generated else []
    out += ["# Reading list", "",
            "Sources the librarian could not reach. Each row is one source of a parked cite ticket; "
            "reading what *Read* names unblocks it. Hand back the page (a file or the quoted statement) "
            "on the ticket's thread.", ""]
    if not rows and not unparsed:
        return "\n".join(out + ["Nothing to read: no cite ticket waits on an unreachable source.", ""])
    counted = [r for r in rows if r["rests_on_it"] is not None]
    rest = {c for r in counted for c in r["rests_on_it"]}
    bear = {c for r in counted for c in r["bears_on_it"]} - rest
    out += ["%d source(s) to read; on the claims they block, %d registry statement(s) rest (depends_on) "
            "and %d more bear (bears_on)." % (len(rows), len(rest), len(bear)), ""]
    for r in rows:
        n = ("not counted" if r["rests_on_it"] is None else
             "%d rest on them (depends_on), %d more bear on them" % (len(r["rests_on_it"]), len(r["bears_on_it"])))
        out.append("## %s: %s" % (r["key"], r["title"] or "(no index row)"))
        out.append("")
        if r["key_text"] != r["key"]:
            out.append("- **Named as:** %s" % r["key_text"])
        out.append("- **Read:** %s" % r["read"])
        out.append("- **For:** %s" % r["for"])
        out.append("- **Ticket:** %s%s" % (r["ticket"], (" (packets %s)" % ", ".join(r["packets"])) if r["packets"] else ""))
        claims = ", ".join(r["claims"]) or "none named"
        if r["unknown_claims"]:
            claims += "; not in the registry: " + ", ".join(r["unknown_claims"])
        out.append("- **Claims:** %s; registry statements: %s" % (claims, n))
        if r["link"]:
            out.append("- **Link:** %s" % r["link"])
        if r["tried"]:
            out.append("- **Tried:** %s" % r["tried"])
        out.append("")
    if unparsed:
        out += ["## Could not read", ""]
        out += ["- %s: %s" % (u["ticket"], _short(u["reason"], 300)) for u in unparsed]
        out.append("")
    return "\n".join(out)


# ---- gathering (the only part that reads the workspace) ---------------------------------

def gather(workspace, store):
    """``(meta, body)`` of every ticket to an Expert instance, blocked, waiting on the human."""
    bl = ex.base_script("board")
    experts = set(ex.expert_instances(workspace))
    out = []
    for m in bl.list_tickets(store, status="blocked"):
        if m.get("to") not in experts or ac.HUMAN not in (m.get("waiting_on") or []):
            continue
        _ref, meta, body = bl.get_ticket(store, m["id"])
        out.append((meta, body))
    return out


def index_lookup(workspace):
    """``expert instance -> {key: index row}`` of that instance's home (cached)."""
    cache = {}

    def f(inst):
        if inst not in cache:
            home = ((workspace.get("instances") or {}).get(inst) or {}).get("home")
            cache[inst] = {str(r.get("key")).strip(): r for r in li.index_rows(home)} if home else {}
        return cache[inst]
    return f


def registry_graph(repo):
    """``(edges, known)`` from the registry engine, seen from ``repo``: ``known(id)`` is the
    record's canonical qid (an alias resolved), or None."""
    plugin = ex.academy_plugin()
    if plugin not in sys.path:
        sys.path.insert(0, plugin)
    from registry.core import graph  # noqa: E402
    es = graph.edges(repo)
    canon = {}

    def known(cid):
        if cid not in canon:
            rec = graph.record(cid, repo)
            canon[cid] = rec.qid if rec is not None else None
        return canon[cid]
    return [(s, r, d) for s, r, d in es], known


def packet_summaries(board):
    pk = ex.base_script("packets")

    def f(pid):
        try:
            path = pk.find_packet(board, pid) if hasattr(pk, "find_packet") else ac.find_packet(board, pid)
            if not path:
                return ""
            _meta, body = pk.read_packet(path)
        except Exception:
            return ""
        m = re.search(r"^## Summary\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
        return m.group(1).strip() if m else ""
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--home", help="the library home that --write writes to (default: the first Expert instance's)")
    ap.add_argument("--workspace")
    ap.add_argument("--board", help="a file board directory (default: workspace.json's board.backend)")
    ap.add_argument("--write", action="store_true", help="write <home>/views/reading-list.md instead of stdout")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-deps", action="store_true", help="do not count the statements resting on each claim")
    a = ap.parse_args(argv)
    ws = ac.load_workspace(a.workspace)
    home = ex.expert_home(ws, a.home)
    bl = ex.base_script("board")
    store = bl.resolve_store(a.board, a.workspace)
    graph = None if a.no_deps else registry_graph(home)
    rows, unparsed = build(gather(ws, store), index_lookup(ws), graph,
                           packet_summaries(bl.resolve_board(a.board, a.workspace)))
    if a.json:
        ex.utf8_stdout()
        print(json.dumps({"rows": rows, "could_not_read": unparsed}, indent=2, ensure_ascii=False))
        return 0
    text = render(rows, unparsed)
    if a.write:
        path = os.path.join(home, OUT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ac.atomic_write(path, text)
        print("wrote %s (%d row(s))" % (path, len(rows)))
    else:
        ex.utf8_stdout()
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
