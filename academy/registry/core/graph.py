"""The graph across namespaces: every link of every reachable record, as qualified ids.

Edges come from each store's records (``Record.links``); a target written as an alias
or a normalised form is replaced by the id it resolves to in its own namespace, so
``lab:x depends_on nb:N8`` and ``nb:CEX-1`` meet. ``deps`` follows the dependency
relations (``depends_on``, ``bears_on``, ``implies``); ``usedby`` follows them backwards.
Both are breadth-first; with ``transitive`` they close over every namespace.
"""
from __future__ import annotations

from collections import deque

from . import federation, workspace

DEP_RELS = ("depends_on", "bears_on", "implies")


def _canon(target, repo):
    """The qualified id ``target`` resolves to (``ns:id``), else ``target`` itself."""
    ns, _ = federation.split(target)
    if ns not in workspace.namespaces():
        return target
    state, rec, _ = federation.resolve(target, repo)
    return rec.qid if rec is not None else target


def edges(repo, rels=DEP_RELS):
    """[(src, rel, dst)] over every reachable namespace, qualified and resolved."""
    out = []
    for ns, st in federation.reachable(repo).items():
        for rid, rec in st.records.items():
            for rel, tgt in rec.links:
                if rels and rel not in rels:
                    continue
                if ":" not in tgt:
                    continue
                out.append((rec.qid, rel, _canon(tgt, repo)))
    return out


def record(qid, repo):
    state, rec, _ = federation.resolve(qid, repo)
    return rec


def walk(qid, repo, reverse=False, transitive=False, rels=DEP_RELS):
    """Edges reached from ``qid``: ``[{"from", "rel", "to", "depth", "status", "class"}]``.
    Forward: what ``qid`` rests on; ``reverse``: what rests on it."""
    start = _canon(qid, repo)
    es = edges(repo, rels)
    fwd, back = {}, {}
    for s, r, d in es:
        fwd.setdefault(s, []).append((s, r, d))
        back.setdefault(d, []).append((s, r, d))
    seen, out, q = {start}, [], deque([(start, 0)])
    while q:
        node, depth = q.popleft()
        for s, r, d in (back if reverse else fwd).get(node, []):
            nxt = s if reverse else d
            rec = record(nxt, repo)
            out.append({"from": s, "rel": r, "to": d, "depth": depth + 1,
                        "status": rec.status if rec else None,
                        "class": rec.cls if rec else None})
            if nxt not in seen:
                seen.add(nxt)
                if transitive:
                    q.append((nxt, depth + 1))
    return out
