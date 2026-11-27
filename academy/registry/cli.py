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
    py -m registry statement <ns:id> --items
                                          ... and, for a structured record (#127), one line
                                          per item: key, status, modulo, item hash
    py -m registry structure <ns:id> [--write]
                                          the `hypotheses` / `items` frontmatter its body
                                          suggests (the `**H<n>.**` / `**C<n>.**` lines; the
                                          paper's `\\label{it:..}` items), each item at the
                                          record's status; --write adds it to the record
                                          (one record, never in bulk: lazy migration, #127)
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
    py -m registry discharge [ID ...] [--all] [--ns NS] [--input ID] [--dry-run] [--json]
                                          the proved-modulo records whose every modulo
                                          input is established now (proved, a card
                                          match, a notation-only definition), each with
                                          why or why not; without --dry-run they become
                                          proved, bottom-up (#127; core/discharge.py).
                                          --all: this repo's namespace; --ns: that one;
                                          --input: those whose modulo names that input,
                                          in every namespace reachable from here
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .core import discharge, federation, graph, stale, structure, workspace
from .profiles import module

ENGINE_COMMANDS = ("graph", "classes", "federation", "requote", "statement", "stale",
                   "discharge", "structure")


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
    st.add_argument("--items", action="store_true",
                    help="also each item's status, modulo and hash (a structured record)")
    su = sub.add_parser("structure")
    su.add_argument("id")
    su.add_argument("--write", action="store_true",
                    help="write the proposal into the record (default: print it)")
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
    d = sub.add_parser("discharge")
    d.add_argument("ids", nargs="*", help="records to assess (ns:id; a bare id is this "
                                          "repo's)")
    d.add_argument("--all", action="store_true",
                   help="every proved-modulo record of this repo's namespace")
    d.add_argument("--ns", action="append", default=[],
                   help="every proved-modulo record of this namespace (repeatable)")
    d.add_argument("--input", action="append", default=[],
                   help="every proved-modulo record whose modulo names this input, in "
                        "every reachable namespace (repeatable): the check after it is "
                        "proved")
    d.add_argument("--dry-run", action="store_true", help="assess only; write nothing")
    d.add_argument("--json", action="store_true")
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
        if a.items:
            s = st.structure(rec.id)
            if s is None:
                print("items: none (not a structured record)")
            else:
                print(f"derived: {s['status'] or '-'}"
                      + (f" modulo {', '.join(s['modulo'])}" if s["modulo"] else ""))
                for k, h in s["hypotheses"].items():
                    print(f"{k}: {' '.join(h.split())}")
                for k, (ist, mod) in s["items"].items():
                    print(f"{k} {ist}{' ' + ', '.join(mod) if mod else ''} "
                          f"hash {s['hashes'].get(k) or '(no text)'}")
        print(st.statement_text(rec.id))
        return 0
    if a.cmd == "structure":
        return _structure_cmd(repo, a)
    if a.cmd == "stale":
        return _stale_cmd(repo, a)
    if a.cmd == "discharge":
        return _discharge_cmd(repo, a)
    if a.cmd == "requote":
        from . import requote
        return requote.main(repo, write=a.write, report=a.report)
    return 1


def _structure_cmd(repo, a):
    """``structure ID [--write]``: the lazy migration of one record (#127)."""
    state, rec, detail = federation.resolve(a.id, repo)
    if rec is None:
        print(f"structure: `{a.id}` does not resolve ({state}{': ' + detail if detail else ''})",
              file=sys.stderr)
        return 1
    st = federation.store_from(rec.ns, repo)
    bh, bi = st.body_parts(rec.id)
    paper = bool(st.paper_items)
    path = Path(rec.file)
    try:
        from .core import fm as _fm
        fields, _body = _fm.split_document(path.read_text(encoding="utf-8"), str(path))
    except Exception as exc:        # noqa: BLE001 -- said as is
        print(f"structure: {path} cannot be read ({exc})", file=sys.stderr)
        return 1
    if not bi:
        print(f"structure: {rec.qid} has no items in its statement ("
              + ("no \\label{it:...} item in its environment" if paper else
                 "no `**C<n>.**` line in its `## Statement`") + "): nothing to propose")
        return 1
    prop = structure.propose(fields, bh, bi, paper=paper)
    from .core.edit import Doc
    fmt = None
    if st.profile == "fsl-claims":
        fmt = _fm.format_scalar_single
    lines = []
    for key in ("hypotheses", "items"):
        if key in prop:
            lines.append(f"{key}:")
            for k, v in prop[key].items():
                kk = _fm.double_quote(k) if (_fm.needs_quotes(k) or ":" in k or "#" in k) else k
                lines.append(f"  {kk}: {_fm.format_list(v) if isinstance(v, list) else (fmt or _fm.format_scalar)(v)}")
    print(f"structure: {rec.qid} ({path})")
    print("\n".join(lines))
    if paper and "hypotheses" not in prop:
        print("# the tex labels no hypothesis: add `hypotheses:` (H<n>: its text) by hand")
    if not a.write:
        print("(dry run: --write adds it to the record)")
        return 0
    before = path.read_bytes()
    old_errs = _record_errors(st, rec, repo)
    doc = Doc(path, fmt)
    for key in ("hypotheses", "items"):
        if key in prop:
            doc.set_map(key, prop[key], after=("id", "kind", "form", "title", "status",
                                               "statement", "modulo"))
    doc.save()
    federation.CACHE.clear()
    added = [e for e in _record_errors(st, rec, repo) if e not in old_errs]
    if added:
        path.write_bytes(before)
        federation.CACHE.clear()
        print("structure: refused, the record would not pass check:\n" + "\n".join(added),
              file=sys.stderr)
        return 1
    print("written")
    return 0


def _record_errors(st, rec, repo):
    """The check errors of one record, read from disk, in its own home."""
    home = Path(st.home)
    if st.profile == "s1-kb":
        from .profiles import s1kb
        kb = s1kb.load_kb(home)
        s1kb.run_check(kb)
        rel = Path(rec.file).resolve().relative_to(home.resolve()).as_posix()
        return [e for e in kb.errors if e.startswith(rel + ":") or e.startswith(rel + " ")]
    from .profiles import fsl
    errs, _w = fsl._check_one(Path(rec.file), home, fsl.registry_root(home))
    return errs


def _board():
    """board.py of this plugin (``<academy>/academy/scripts``), imported late: only the
    stale command touches the board."""
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts")
    if here not in sys.path:
        sys.path.insert(0, here)
    import board
    return board


def _open_verify(bd):
    """The board's non-terminal verify tickets (metas) and the store (raises when the
    board cannot be read)."""
    store = bd.resolve_store()
    return list(bd.list_tickets(store, kind="verify")), store


def _covering(tickets, qid, title):
    """The open verify ticket already covering ``qid``: the one titled ``title``, else
    one whose title or refs name the claim (a blind verify on it); None when none."""
    for m in tickets:
        if m.get("title") == title:
            return m
    for m in tickets:
        refs = m.get("refs") or []
        if qid in str(m.get("title") or "").split() or \
                qid in [str(r).strip() for r in (refs if isinstance(refs, list) else [refs])]:
            return m
    return None


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
    problem = stale.decision_table_problem()
    if problem:
        print(f"stale: {problem}; nothing compared, nothing filed", file=sys.stderr)
        return 1
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
    tickets, store, board_note = [], None, ""
    bd = None
    if items:
        try:
            bd = _board()
            tickets, store = _open_verify(bd)
        except Exception as exc:        # noqa: BLE001 -- the board's error, said as is
            board_note = f"the board could not be read ({exc})"
            if a.file_reword:
                print(f"stale: refused: {board_note}; nothing filed", file=sys.stderr)
                return 1
    as_inst = a.as_instance or expert
    for it in items:
        it["title_to_file"] = stale.ticket_title(it["qid"], it["base_pass"]) \
            if it["kind"] == "stale" else ""
        cov = _covering(tickets, it["qid"], it["title_to_file"])
        it["open_ticket"] = f"{cov.get('id')} {cov.get('title')}" if cov else None
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
            tickets.append(dict(meta))
        except Exception as exc:        # noqa: BLE001 -- a refusal, reported per claim
            it["refused"] = str(exc)
    if a.json:
        print(json.dumps({"items": items, "board": board_note or None}, indent=1,
                         default=sorted))
        return 1 if any(i.get("refused") for i in items) else 0
    n_un = sum(1 for i in items if i["kind"] == "unreviewed")
    print(f"stale: {len(items) - n_un} claim(s) whose statement changed since their last "
          f"positive review pass, {n_un} proved without a positive pass on record "
          f"({', '.join(nss)}){'; ' + board_note if board_note else ''}")
    section = None
    for it in items:
        if it["section"] != section:
            section = it["section"]
            n = sum(1 for i in items if i["section"] == section)
            print(f"\n## {section} ({n})")
        if it["kind"] == "unreviewed":
            print(f"- {it['qid']}  {it['status']}  no positive review pass on record")
        else:
            print(f"- {it['qid']}  {stale.label(it['status'])}  pass {it['pass']} "
                  f"(hash {it['pass_hash']}, now {it['hash']})")
        if it["hold"]:
            print(f"    held, not filed: {it['hold']}")
        elif it["open_ticket"]:
            print(f"    already open: {it['open_ticket']} (covers it; not filed: "
                  f"{it['title_to_file']})")
        elif it["filed"]:
            print(f"    filed: {it['filed']} {it['title_to_file']}")
        elif it.get("refused"):
            print(f"    refused: {it['refused']}")
        else:
            print(f"    to file: {it['title_to_file']}")
    if items and not a.file_reword:
        print("\n(dry run: --file-reword files the tickets listed `to file`)")
    return 1 if any(i.get("refused") for i in items) else 0


def _discharge_cmd(repo, a):
    own = workspace.repo_ns(repo)
    nss = list(a.ns)
    for ns in nss:
        if ns not in workspace.namespaces():
            print(f"discharge: `{ns}` is not a namespace of the workspace", file=sys.stderr)
            return 2
    if a.all:
        if not own:
            print("discharge: --all needs a registry home (or --ns NS)", file=sys.stderr)
            return 2
        nss.append(own)
    if not (a.ids or nss or a.input):
        print("discharge: name records, or --all / --ns NS / --input ID", file=sys.stderr)
        return 2
    ids = discharge.candidates(repo, a.ids, nss, a.input)
    done, refused, results = set(), [], {}
    while True:
        federation.CACHE.clear()
        progressed = False
        for q in ids:
            if q in done:
                continue
            res = discharge.assess(q, repo)
            results[q] = dict(res, applied=False, refused=None)
            if not res["dischargeable"] or a.dry_run:
                continue
            try:
                discharge.apply(q, repo)
            except ValueError as exc:
                results[q]["refused"] = str(exc)
                refused.append(q)
                done.add(q)
                continue
            results[q]["applied"] = True
            done.add(q)
            progressed = True
            if a.input:
                # a chain discharges bottom-up: what rests on this one is next
                ids += [x for x in discharge.candidates(repo, inputs=[q]) if x not in ids]
        if a.dry_run or not progressed:
            break
    items = [results[q] for q in ids if q in results]
    if a.json:
        print(json.dumps({"items": items}, indent=1, ensure_ascii=False))
        return 1 if refused else 0
    n_ok = sum(1 for i in items if i["dischargeable"] or i["applied"])
    print(f"discharge: {len(items)} record(s) assessed, {n_ok} dischargeable"
          + (" (dry run: nothing written)" if a.dry_run else
             f", {sum(1 for i in items if i['applied'])} discharged"))
    for i in items:
        if i["applied"]:
            word = "discharged"
        elif i["refused"]:
            word = "refused"
        else:
            word = "dischargeable" if i["dischargeable"] else "held"
        print(f"- {i['id']}  {i['status'] or '-'}  {word}")
        for x in i["inputs"]:
            print(f"    {'ok ' if x['established'] else 'no '} {discharge.explain(x)}")
        if not i["inputs"] and i["problems"]:
            for p in i["problems"]:
                print(f"    {p}")
        if i["refused"]:
            print(f"    {i['refused']}")
    return 1 if refused else 0


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
