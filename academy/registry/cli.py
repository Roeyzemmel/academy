"""``py -m registry``: the one command line for every registry.

    py -m registry [--repo PATH] <command> ...

The repo (default: the current directory; ``--root`` is accepted as a synonym, as
kb.py spells it) decides the namespace and so the profile, and the command goes to
that profile's command line, which is the union of the old two:

* fsl-claims (lab, paper): show, list, grep, sql, check [files], render (= build),
  ledger, new, set-status, evidence, deps, usedby   -- claims.py's commands plus the
  mutations and the graph;
* s1-kb (notebook): check [files], build, show, find, deps, usedby, sql, new, set-status,
  resolve   -- kb.py's commands.

Commands of the engine itself, for every repo:

    py -m registry graph deps|usedby <ns:id> [--transitive]   the cross-namespace graph
    py -m registry classes [--ns NS]      every record with its projection class
    py -m registry federation             which home serves each namespace from here
    py -m registry statement <ns:id>      the statement text a review is given on, and its
                                          hash (the one claims_set_status compares)
    py -m registry requote [--write] [--report FILE]   the R2 requote (fsl-claims only)
    py -m registry stale [--ns NS] [--section S] [--json]
                                          the proved / proved-modulo claims whose statement
                                          changed since their last positive review pass,
                                          grouped by section, with the reword verify
                                          ticket each needs (#109; core/stale.py)
    py -m registry stale ... --file-reword [--as INSTANCE]
                                          file those tickets on the board (one per claim,
                                          ``Verify <claim> (reword of <pass>)``, to the
                                          Expert; none while one with that title is open);
                                          filed as the Expert's review-chair, or --as human
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .core import federation, graph, stale, workspace
from .profiles import module

ENGINE_COMMANDS = ("graph", "classes", "federation", "requote", "statement", "stale")


def _pop_repo(argv):
    """Remove ``--repo X`` / ``--root X`` (anywhere) from argv; return (repo, rest)."""
    repo, rest, i = None, [], 0
    while i < len(argv):
        a = argv[i]
        if a in ("--repo", "--root") and i + 1 < len(argv):
            repo = argv[i + 1]
            i += 2
            continue
        if a.startswith(("--repo=", "--root=")):
            repo = a.split("=", 1)[1]
            i += 1
            continue
        rest.append(a)
        i += 1
    return Path(repo or ".").resolve(), rest


def _engine(repo, argv):
    ap = argparse.ArgumentParser(prog="registry")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("graph")
    g.add_argument("direction", choices=("deps", "usedby"))
    g.add_argument("id")
    g.add_argument("--transitive", action="store_true")
    c = sub.add_parser("classes")
    c.add_argument("--ns")
    sub.add_parser("federation")
    st = sub.add_parser("statement")
    st.add_argument("id")
    sl = sub.add_parser("stale")
    sl.add_argument("--ns", help="one namespace (default: this repo's own, else every "
                                 "namespace reachable from it)")
    sl.add_argument("--section", help="only the claims whose section (where:) is this")
    sl.add_argument("--file-reword", action="store_true",
                    help="file the reword verify tickets (default: list them only)")
    sl.add_argument("--as", dest="as_instance", default=None,
                    help="the filing instance: the Expert instance (default; as its "
                         "review-chair) or human")
    sl.add_argument("--json", action="store_true")
    r = sub.add_parser("requote")
    r.add_argument("--write", action="store_true", help="rewrite the files (default: dry run)")
    r.add_argument("--report", help="write the data-equality report (Markdown) here")
    a = ap.parse_args(argv)
    if a.cmd == "graph":
        edges = graph.walk(a.id, repo, reverse=a.direction == "usedby", transitive=a.transitive)
        for e in edges:
            node = e["from"] if a.direction == "usedby" else e["to"]
            print(f"{'  ' * (e['depth'] - 1)}{node} ({e['rel']}) "
                  f"[{e['status'] or '-'} / {e['class'] or '?'}]")
        if not edges:
            print("(none)")
        return 0
    if a.cmd == "classes":
        for ns, st in sorted(federation.reachable(repo).items()):
            if a.ns and ns != a.ns:
                continue
            for rid in sorted(st.records):
                r = st.records[rid]
                print(f"{r.qid}\t{r.type}\t{r.status or '-'}\t{r.cls}")
        return 0
    if a.cmd == "federation":
        own = workspace.repo_ns(repo)
        for ns in workspace.namespaces():
            h = workspace.home_of(ns, repo)
            prof = workspace.engine_profile(ns, h) if h else "-"
            print(f"{ns}\t{'(this repo) ' if ns == own else ''}{h or 'not beside this repo'}\t{prof}")
        return 0
    if a.cmd == "statement":
        state, rec, detail = federation.resolve(a.id, repo)
        if rec is None:
            print(f"statement: `{a.id}` does not resolve ({state}{': ' + detail if detail else ''})",
                  file=sys.stderr)
            return 1
        st = federation.store_from(rec.ns, repo)
        print(f"hash: {st.statement_hash(rec.id)}")
        print(st.statement_text(rec.id))
        return 0
    if a.cmd == "stale":
        return _stale_cmd(repo, a)
    if a.cmd == "requote":
        from . import requote
        return requote.main(repo, write=a.write, report=a.report)
    return 1


def _board():
    """board.py of this plugin (``<academy>/academy/scripts``), imported late: only the
    stale command touches the board."""
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts")
    if here not in sys.path:
        sys.path.insert(0, here)
    import board
    return board


def _open_titles(bd):
    """{title: ticket id} of the board's non-terminal verify tickets (raises when the
    board cannot be read)."""
    store = bd.resolve_store()
    return {m.get("title"): m.get("id") for m in bd.list_tickets(store, kind="verify")}, store


def _stale_cmd(repo, a):
    own = workspace.repo_ns(repo)
    if a.ns:
        if a.ns not in workspace.namespaces():
            print(f"stale: `{a.ns}` is not a namespace of the workspace", file=sys.stderr)
            return 2
        nss = [a.ns]
    else:
        nss = [own] if own else sorted(federation.reachable(repo))
    root = stale.reviews_root(repo)
    if root is None:
        print("stale: no library reviews/ folder beside this repo (no Expert instance home "
              "here): nothing can be compared", file=sys.stderr)
        return 2
    items = []
    for ns in nss:
        st = federation.store_from(ns, repo)
        if st is None:
            print(f"stale: the home of `{ns}:` is not beside this repo; skipped", file=sys.stderr)
            continue
        items += stale.find(st, root)
    if a.section:
        items = [i for i in items if i["section"] == a.section]
    expert = stale.expert_instance()
    titles, store, board_note = {}, None, ""
    bd = None
    if items:
        try:
            bd = _board()
            titles, store = _open_titles(bd)
        except Exception as exc:        # noqa: BLE001 -- the board's error, said as is
            board_note = f"the board could not be read ({exc})"
            if a.file_reword:
                print(f"stale: refused: {board_note}; nothing filed", file=sys.stderr)
                return 1
    as_inst = a.as_instance or expert
    for it in items:
        it["title_to_file"] = stale.ticket_title(it["qid"], it["base_pass"])
        it["open_ticket"] = titles.get(it["title_to_file"])
        it["filed"] = None
        if it["hold"] or it["open_ticket"] or not a.file_reword:
            continue
        if not expert:
            it["hold"] = "the workspace names no Expert instance to file to"
            continue
        try:
            _path, meta = bd.create_ticket(
                store, expert, it["title_to_file"], stale.ticket_ask(it),
                "A verification packet with the reword run's verdict, or the blind pass "
                "it calls for.", kind="verify", refs=stale.ticket_refs(it, expert),
                as_instance=as_inst, agent="" if as_inst == "human" else "review-chair",
                return_meta=True)
            it["filed"] = meta.get("id")
            titles[it["title_to_file"]] = it["filed"]
        except Exception as exc:        # noqa: BLE001 -- a refusal, reported per claim
            it["refused"] = str(exc)
    if a.json:
        print(json.dumps({"items": items, "board": board_note or None}, indent=1,
                         default=sorted))
        return 1 if any(i.get("refused") for i in items) else 0
    print(f"stale: {len(items)} claim(s) whose statement changed since their last positive "
          f"review pass ({', '.join(nss)}){'; ' + board_note if board_note else ''}")
    section = None
    for it in items:
        if it["section"] != section:
            section = it["section"]
            n = sum(1 for i in items if i["section"] == section)
            print(f"\n## {section} ({n})")
        print(f"- {it['qid']}  {stale.label(it['status'])}  pass {it['pass']} "
              f"(hash {it['pass_hash']}, now {it['hash']})")
        if it["hold"]:
            print(f"    held, not filed: {it['hold']}")
        elif it["open_ticket"]:
            print(f"    already open: {it['open_ticket']} {it['title_to_file']}")
        elif it["filed"]:
            print(f"    filed: {it['filed']} {it['title_to_file']}")
        elif it.get("refused"):
            print(f"    refused: {it['refused']}")
        else:
            print(f"    to file: {it['title_to_file']}")
    if items and not a.file_reword:
        print("\n(dry run: --file-reword files the tickets listed `to file`)")
    return 1 if any(i.get("refused") for i in items) else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    repo, rest = _pop_repo(argv)
    if rest and rest[0] in ENGINE_COMMANDS:
        return _engine(repo, rest)
    if not rest or rest[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    ns = workspace.repo_ns(repo)
    if ns is None:
        print(f"registry: {repo} is not a registry home (no academy.json ns, no workspace "
              "home of that name, no known layout); pass --repo", file=sys.stderr)
        return 2
    prof = workspace.engine_profile(ns, repo)
    mod = module(prof)
    if prof == "s1-kb":
        if rest[0] == "render":
            rest[0] = "build"
        return mod.main(rest + ["--root", str(repo)])
    mod.set_default_repo(repo)
    return mod.main(["--repo", str(repo)] + rest)


if __name__ == "__main__":
    sys.exit(main())
