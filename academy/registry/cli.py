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
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import federation, graph, workspace
from .profiles import module

ENGINE_COMMANDS = ("graph", "classes", "federation", "requote", "statement")


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
    if a.cmd == "requote":
        from . import requote
        return requote.main(repo, write=a.write, report=a.report)
    return 1


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
