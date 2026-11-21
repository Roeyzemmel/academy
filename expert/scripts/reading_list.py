"""reading_list.py -- the human's reading list: sources the librarian could not reach (#108).

    py reading_list.py [--home H] [--workspace W] [--write] [--json] [--no-deps]

When a cite ticket parks on the human because its source is unreachable (paywall, image-only
scan, blocked host), cite.js writes one thread line

    source unreachable from this session: <key>; a human with access reads <what> for <relying>

and blocks the ticket on ``human``. This script collects those tickets (to an Expert
instance, blocked, ``human`` in waiting_on) into one list, a row per ticket: the bib key,
the source as the library's index row names it (title, link, what was tried), exactly what
to read, the statement relying on it, the claims the ticket names, and how many registry
statements rest on those claims (``depends_on``, transitively), so the cost of each unread
page is visible. The list is sorted by that count, largest first.

``--write`` writes it to ``<library home>/reading-list.md``, a generated view (do not
edit: the fix for a wrong row is the ticket or the index row, then a rerun). Without it the
markdown goes to stdout. Read-only on the board.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
import library_index as li  # noqa: E402

GENERATOR = "expert/scripts/reading_list.py"
OUT = "reading-list.md"
RE_LINE = re.compile(r"source unreachable from this session: (?P<key>[^;]+); a human with access reads (?P<rest>.+)$")
RE_CLAIM = re.compile(r"^[a-z0-9]+:[A-Za-z0-9][\w.:-]*$")
# " for <claim id>": where the relying part starts (the "what" may itself say "for Prop. 5.6")
RE_FOR = re.compile(r" for (?=[a-z0-9]+:[A-Za-z])")
RE_EDGE = re.compile(r"^(?P<ind>\s*)(?P<id>\S+) \((?P<edge>depends_on|bears_on)\)")
RE_URL = re.compile(r"https?://[^\s`)>]+")
#: the board keeps a thread line to about this many characters: a longer one was cut
CUT = 240


def unreachable_line(body):
    """The last 'source unreachable' thread line of a ticket body, parsed, or None."""
    hit = None
    for ln in (body or "").splitlines():
        i = ln.find("source unreachable from this session:")
        if i < 0:
            continue
        line = ln[i:].strip()
        m = RE_LINE.match(line)
        if not m:
            continue
        rest = m.group("rest").strip()
        cuts = list(RE_FOR.finditer(rest))
        what, relying = (rest[:cuts[-1].start()], rest[cuts[-1].end():]) if cuts else (rest, "")
        # a line the board cut short ends in a fragment ("... for pap"): say so, keep no fragment
        truncated = len(ln) >= CUT and not relying
        if truncated:
            what = re.sub(r"\s+for\s+\S{0,20}$", "", what).rstrip() + " [...]"
        hit = {"key": m.group("key").strip(), "what": what.strip(), "relying": relying.strip(), "truncated": truncated}
    return hit


def claims_of(meta):
    """The registry ids a ticket's refs name (not tickets, files or bib keys)."""
    out = []
    for r in meta.get("refs") or []:
        r = str(r).strip()
        if RE_CLAIM.match(r) and not r.startswith(("file:", "bib:")) and r not in out:
            out.append(r)
    return out


def _link(row):
    m = RE_URL.search(str(row.get("source url") or ""))
    if m:
        return m.group(0)
    m = re.search(r"doi:(10\.\S+?)[,;\s]*$", str(row.get("version") or "") + " " + str(row.get("authors, short title") or ""))
    return "https://doi.org/" + m.group(1) if m else ""


def build(tickets, index, dependents=None):
    """Rows of the list. ``tickets``: ``(meta, body)`` pairs; ``index``: parsed index rows;
    ``dependents``: a callable ``claim id -> (ids resting on it, ids only bearing on it)``
    (None: not counted)."""
    by_key = {str(r.get("key")).strip(): r for r in index}
    rows = []
    for meta, body in tickets:
        hit = unreachable_line(body)
        if not hit:
            continue
        key = hit["key"]
        idx = by_key.get(key.split()[0].strip(",;")) or {}
        unread = "unreachable" in (str(idx.get("how read") or "") + str(idx.get("source dir") or "")).lower()
        claims = claims_of(meta)
        rest, bear, counted = set(), set(), dependents is not None
        if counted:
            for c in claims:
                try:
                    d, b = dependents(c)
                    rest |= set(d)
                    bear |= set(b)
                except Exception:                   # a failed count is said, not guessed
                    counted = False
        rows.append({
            "ticket": meta.get("id"), "key": key, "title": str(idx.get("authors, short title") or "").strip(),
            "link": _link(idx), "tried": _short(idx.get("used for")) if unread else "",
            "read": hit["what"], "for": hit["relying"] or meta.get("title") or "", "claims": claims,
            "rests_on_it": sorted(rest - set(claims)) if counted else None,
            "bears_on_it": sorted(bear - rest - set(claims)) if counted else None,
            "packets": list(meta.get("packets") or []), "in_index": bool(idx)})
    size = lambda r: (len(r["rests_on_it"]), len(r["bears_on_it"])) if r["rests_on_it"] is not None else (-1, -1)  # noqa: E731
    rows.sort(key=lambda r: (tuple(-x for x in size(r)), str(r["ticket"])))
    return rows


def _short(x, n=400):
    x = re.sub(r"\s+", " ", str(x or "")).strip()
    return x if len(x) <= n else x[:n].rsplit(" ", 1)[0] + " [...]"


def depends_tree(text):
    """The ids reached from the root through ``depends_on`` edges only, read from the
    indented ``graph usedby --transitive`` listing, and the ids that bear directly on one
    of those (a ``bears_on`` edge is a bearing, not a dependency, and nothing below it is
    counted)."""
    out, near, stack = set(), set(), []             # stack of (indent, reached by depends_on only)
    for ln in text.splitlines():
        m = RE_EDGE.match(ln)
        if not m:
            continue
        ind = len(m.group("ind"))
        while stack and stack[-1][0] >= ind:
            stack.pop()
        ok = m.group("edge") == "depends_on" and (not stack or stack[-1][1])
        if ok:
            out.add(m.group("id"))
        elif not stack or stack[-1][1]:     # bears directly on the claim or on a dependent of it
            near.add(m.group("id"))
        stack.append((ind, ok))
    return out, near - out


def render(rows, generated=True):
    out = [ex.GENERATED % GENERATOR, ""] if generated else []
    out += ["# Reading list", "",
            "Sources the librarian could not reach. Each row is one parked cite ticket; reading the "
            "page named under *Read* unblocks it. Hand back the page (a file or the quoted statement) "
            "on the ticket's thread.", ""]
    if not rows:
        return "\n".join(out + ["Nothing to read: no cite ticket waits on an unreachable source.", ""])
    total = {c for r in rows for c in (r["rests_on_it"] or [])}
    near = {c for r in rows for c in (r["bears_on_it"] or [])} - total
    out += ["%d source(s) to read; on the claims they block, %d registry statement(s) rest (depends_on) "
            "and %d more bear (bears_on)." % (len(rows), len(total), len(near)), ""]
    for r in rows:
        n = ("? (the registry graph could not be read)" if r["rests_on_it"] is None else
             "%d rest on them (depends_on), %d more bear on them" % (len(r["rests_on_it"]), len(r["bears_on_it"])))
        out.append("## %s: %s" % (r["key"], r["title"] or "(no index row)"))
        out.append("")
        out.append("- **Read:** %s" % r["read"])
        out.append("- **For:** %s" % r["for"])
        out.append("- **Ticket:** %s%s" % (r["ticket"], (" (packets %s)" % ", ".join(r["packets"])) if r["packets"] else ""))
        out.append("- **Claims:** %s; registry statements: %s" % (", ".join(r["claims"]) or "none named", n))
        if r["link"]:
            out.append("- **Link:** %s" % r["link"])
        if r["tried"]:
            out.append("- **Tried:** %s" % r["tried"])
        out.append("")
    return "\n".join(out)


def registry_dependents(cwd):
    """``claim -> ids resting on it`` through ``registry.py graph usedby --transitive``."""
    reg = os.path.join(ex.academy_plugin(), "scripts", "registry.py")
    cache = {}

    def f(cid):
        if cid not in cache:
            p = subprocess.run([sys.executable, reg, "graph", "usedby", cid, "--transitive"], cwd=cwd,
                               capture_output=True, text=True, encoding="utf-8", timeout=120)
            if p.returncode != 0:
                raise RuntimeError(p.stderr.strip()[:200])
            cache[cid] = depends_tree(p.stdout)
        return cache[cid]
    return f


def gather(workspace, store):
    """``(meta, body)`` of every ticket to an Expert instance, blocked, waiting on the human."""
    bl = ex.base_script("board")
    experts = set(ex.expert_instances(workspace))
    out = []
    for m in bl.list_tickets(store, status="blocked"):
        if m.get("to") not in experts or ac.HUMAN not in (m.get("waiting_on") or []):
            continue
        _ref, meta, body = store.get(m["id"]) if hasattr(store, "get") else bl.get_ticket(store, m["id"])
        out.append((meta, body))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--home", help="the library home (default: the first Expert instance's)")
    ap.add_argument("--workspace")
    ap.add_argument("--board", help="a file board directory (default: workspace.json's board.backend)")
    ap.add_argument("--write", action="store_true", help="write <home>/reading-list.md instead of stdout")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-deps", action="store_true", help="do not count the statements resting on each claim")
    a = ap.parse_args(argv)
    ws = ac.load_workspace(a.workspace)
    home = ex.expert_home(ws, a.home)
    store = ex.base_script("board").resolve_store(a.board, a.workspace)
    deps = None if a.no_deps else registry_dependents(home)
    rows = build(gather(ws, store), li.index_rows(home), deps)
    if a.json:
        ex.utf8_stdout()
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    text = render(rows)
    if a.write:
        ac.atomic_write(os.path.join(home, OUT), text)
        print("wrote %s (%d row(s))" % (os.path.join(home, OUT), len(rows)))
    else:
        ex.utf8_stdout()
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
