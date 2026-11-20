"""settle_deps.py -- check and apply a dependency-settler record (#121, the human's design of
2026-11-20).

When two CONFIRMED runs differ in their modulo lists after the mechanical reduction,
``decision_table.py`` returns the outcome ``settle-dependencies`` with one entry per
differing input (``differing_inputs``: input, run, shape, result, pointer, open_check,
exists, cycle). The ``expert:dependency-settler`` agent classifies each one; this script
checks its record against the cases and their fixed order, and applies it.

The cases, in the order they apply (the first that can apply wins):

* stage 0, the statement (the whole pass): 12 different readings of the statement -> stop.
* stage 1, mechanical, in decision_table.py (never in a settler record): 13 carried
  modulo, 4 granularity, notation-only definitions.
* stage 2, admissibility: 11 circular (needs the table's cycle fact) -> stop (a gap);
  9 hypotheses not verified or an open [CHECK] -> stop; 10 missing or unreadable source,
  uncited free text -> a cite ticket, the input stays as a pending modulo input.
* stage 3, is it used: 14 formal input (used only formally: a convention, a notational
  identification, a step true by definition) -> dropped; 6 spurious (unused) -> dropped;
  5 different internal routes -> keep the input of the route the proof writes.
* stage 4, what kind: 7 hidden non-routine step -> enters the declared dependencies (no
  existing result -> a gap, stop); 1 folklore (one run took the step as folklore and
  listed nothing, the other named it) -> keep the named dependency and declare it.
* stage 5, among valid sources for one step: 2 multi-source, same statement -> 'routine',
  every source named in the proof, one modulo input; 3 different settings, all
  applicable -> the best fit, a remark names the rest; 8 stronger than needed -> the
  weakest sufficient result.

The record (``S.json``, the JSON block of the settler's ``S.md``)::

    {"readings": {"differ": false, "evidence": ""},
     "inputs": [{"input": "<as in differing_inputs>", "case": 14,
                 "chosen": "", "sources": [], "line": "<the proof line>",
                 "remark": "", "evidence": "<quote, id, pinpoint>"}]}

``check`` lists the problems (empty: valid); ``apply`` returns the outcome:
``confirmed-settled`` (proposed ``proved-modulo`` the settled list, or ``proved`` when
nothing remains) or ``disagreement`` (a stop), with the declarations to add, the proof
notes and the cite tickets to file. Usage::

    settle_deps.py check S.json --table table.json
    settle_deps.py apply S.json --table table.json
"""
import argparse
import json
import sys

#: case -> stage, in the human's fixed order
STAGE = {12: 0, 11: 2, 9: 2, 10: 2, 14: 3, 6: 3, 5: 3, 7: 4, 1: 4, 2: 5, 3: 5, 8: 5}
#: cases a settler record may use (13 and 4 are mechanical: decision_table.py's)
RECORD_CASES = (11, 9, 10, 14, 6, 5, 7, 1, 2, 3, 8)
MECHANICAL = (13, 4)
#: cases whose input is dropped; cases that keep a dependency
DROPPED = (14, 6)
STOPS = (11, 9)
#: cases whose dependency the proof does not state yet, so the repair declares it:
#: a hidden step (7), the dependency folklore stood for (1), the weaker result (8)
DECLARING = (7, 1, 8)
NAMES = {1: "folklore", 2: "multi-source (routine)", 3: "different settings (best fit)",
         4: "granularity", 5: "different internal routes", 6: "spurious",
         7: "hidden step", 8: "stronger than needed", 9: "hypotheses not verified",
         10: "missing source", 11: "circular", 12: "different readings",
         13: "carried modulo", 14: "formal input"}


def _list(v):
    return list(v) if isinstance(v, (list, tuple)) else []


def _facts(table):
    return {str(d.get("input")): d for d in _list(table.get("differing_inputs"))
            if isinstance(d, dict)}


def _exists(fact):
    """True when the table shows the input's result exists (a registry id it found, or a
    card: the library is the settler's to read, so a card is taken as named)."""
    return bool(fact.get("result")) and (fact.get("exists") is True
                                         or str(fact.get("result")).startswith("bib:"))


def _known_results(table):
    """Results the record may choose: the agreed modulo and every differing input's
    result."""
    out = set(str(x) for x in _list(table.get("modulo")))
    for d in _facts(table).values():
        if d.get("result"):
            out.add(str(d["result"]))
        out.add(str(d.get("input")))
    return out


def first_case(fact):
    """The case the table's facts force, or None when the settler must judge: a cycle is
    case 11 and an open [CHECK] case 9 (stage 2, before anything the settler sees); an
    input with no shown result (free text, an unknown namespace) is at best case 10 (or
    9 / 11 before it)."""
    if fact.get("cycle"):
        return 11
    if fact.get("open_check"):
        return 9
    return None


def check(record, table):
    """The problems of ``record`` against ``table`` (a ``settle-dependencies`` result);
    [] when it is valid."""
    probs = []
    if not isinstance(table, dict):
        return ["the table is not a JSON object"]
    if table.get("outcome") != "settle-dependencies":
        return ["the table's outcome is %r, not settle-dependencies: nothing to settle"
                % table.get("outcome")]
    if not isinstance(record, dict):
        return ["the record is not a JSON object"]
    readings = record.get("readings") or {}
    if not isinstance(readings, dict):
        return ["readings is not an object"]
    if readings.get("differ"):
        if not str(readings.get("evidence") or "").strip():
            probs.append("case 12 (different readings) names no evidence (quote both "
                         "readings)")
        return probs                       # stage 0 stops the pass: inputs are moot
    facts = _facts(table)
    entries = record.get("inputs")
    if not isinstance(entries, list):
        return ["inputs is not a list"]
    seen = {}
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            probs.append("inputs[%d] is not an object" % i)
            continue
        name = str(e.get("input") or "")
        if name not in facts:
            probs.append("inputs[%d] %r is not a differing input of the table" % (i, name))
            continue
        if name in seen:
            probs.append("%r is classified twice" % name)
            continue
        seen[name] = e
        probs += _check_entry(name, e, facts[name], table)
    for name in facts:
        if name not in seen:
            probs.append("%r is not classified (one record per differing input)" % name)
    if not probs:
        probs += _check_groups(seen, facts)
    return probs


def _check_entry(name, e, fact, table):
    probs = []
    case = e.get("case")
    if isinstance(case, bool) or not isinstance(case, int):
        return ["%r: case %r is not a case number" % (name, case)]
    if case in MECHANICAL:
        return ["%r: case %d (%s) is mechanical, decision_table.py's, never a settler's"
                % (name, case, NAMES[case])]
    if case == 12:
        return ["%r: case 12 is a pass-level stop (readings.differ), not an input's case"
                % name]
    if case not in RECORD_CASES:
        return ["%r: case %d is not one of the cases" % (name, case)]
    forced = first_case(fact)
    if forced is not None and case != forced:
        return ["%r: the table shows %s, so case %d (%s) applies first, not case %d (the "
                "fixed order)" % (name, "a cycle back to the subject" if forced == 11
                                  else "an open [CHECK]", forced, NAMES[forced], case)]
    if case == 11 and not fact.get("cycle"):
        probs.append("%r: case 11 (circular) needs the registry cycle; the table found "
                     "none" % name)
    if case == 9 and not (fact.get("open_check") or str(e.get("evidence") or "").strip()):
        probs.append("%r: case 9 names neither an open [CHECK] nor the unverified "
                     "hypothesis (evidence)" % name)
    if not _exists(fact) and case not in (11, 9, 10, 14, 6):
        probs.append("%r: its result is not shown to exist (%s), so case 10 (missing "
                     "source) applies before case %d (the fixed order)"
                     % (name, fact.get("shape") or "?", case))
    for field in ("chosen", "line", "remark", "evidence"):
        if e.get(field) is not None and not isinstance(e.get(field), str):
            probs.append("%r: %s must be a string" % (name, field))
    if e.get("sources") is not None and not isinstance(e.get("sources"), list):
        probs.append("%r: sources must be a list" % name)
    if probs:
        return probs
    chosen = str(e.get("chosen") or "")
    sources = [str(x) for x in e.get("sources") or ()]
    known = _known_results(table)
    own = {name, str(fact.get("result") or "")} - {""}
    if case == 10 and fact.get("exists") is True:
        probs.append("%r: the registry shows its result, so it is not a missing source "
                     "(case 10)" % name)
    if case in DROPPED and chosen:
        probs.append("%r: case %d drops the input; chosen must be empty" % (name, case))
    if case in (14, 6, 5) and not str(e.get("line") or "").strip():
        probs.append("%r: case %d needs the proof line that shows it (line)" % (name, case))
    if case == 5 and chosen not in ("", name, fact.get("result") or name):
        probs.append("%r: case 5 keeps the input (chosen = it) or drops it (empty)" % name)
    if case == 7 and chosen and chosen not in known:
        probs.append("%r: case 7 chose %r, which no run lists" % (name, chosen))
    if case == 1 and chosen not in own:
        probs.append("%r: case 1 (folklore: one run took the step as folklore and named "
                     "nothing, this run named it) keeps this input; chosen %r is not it"
                     % (name, chosen))
    if case in (2, 3):
        if not own & set(sources):
            probs.append("%r: case %d's sources include the input itself" % (name, case))
        unknown = [x for x in sources if x not in known]
        if unknown:
            probs.append("%r: case %d names sources no run lists: %s"
                         % (name, case, ", ".join(unknown)))
        if len(sources) < 2:
            probs.append("%r: case %d names every source (sources, at least two)"
                         % (name, case))
        if chosen and chosen not in sources:
            probs.append("%r: case %d chose %r, which is not among its sources"
                         % (name, case, chosen))
        if not chosen:
            probs.append("%r: case %d keeps one source as the modulo input (chosen)"
                         % (name, case))
    if case == 3 and not str(e.get("remark") or "").strip():
        probs.append("%r: case 3 needs the remark naming the other sources" % name)
    if case == 8 and (not chosen or chosen in own or chosen not in known):
        probs.append("%r: case 8 chooses another listed result, the weaker sufficient "
                     "one, not the input itself (chosen %r)" % (name, chosen))
    if case == 10 and chosen:
        probs.append("%r: case 10 chooses nothing (a cite ticket; the input stays "
                     "pending)" % name)
    return probs


def _check_groups(seen, facts):
    """Checks across entries: inputs that are sources of one step (case 2/3, any input
    another entry names among its sources) keep one source between them; nothing kept by
    one entry is dropped by another; case 5 keeps at least one route."""
    probs = []
    kept, dropped = {}, {}
    for n, e in seen.items():
        c, ch = e.get("case"), str(e.get("chosen") or "")
        if c in DROPPED or (c == 5 and not ch):
            dropped[n] = c
            res = str(facts.get(n, {}).get("result") or "")
            if res:
                dropped[res] = c
        elif c not in STOPS and c != 10 and not (c == 7 and not ch):
            kept[n] = ch or str(facts.get(n, {}).get("result") or n)
    for n, dep in kept.items():
        if dep in dropped and dep != n:
            probs.append("%r keeps %r, which another entry drops (case %s)"
                         % (n, dep, dropped[dep]))
    # one step's sources keep one source
    steps = []
    for n, e in seen.items():
        if e.get("case") in (2, 3):
            steps.append(set(str(x) for x in e.get("sources") or ()) | {n})
    groups = []
    for st in steps:                    # merge the steps that share a source
        for g in [g for g in groups if g & st]:
            st |= g
            groups.remove(g)
        groups.append(st)
    for group in groups:
        chosen = {kept[m] for m in group if m in kept}
        if len(chosen) > 1:
            probs.append("the sources %s are one step but keep %s: keep one"
                         % (", ".join(sorted(group)), ", ".join(sorted(chosen))))
    routes = [n for n, e in seen.items() if e.get("case") == 5]
    if routes and not any(str(seen[n].get("chosen") or "") for n in routes):
        probs.append("case 5 keeps the route the proof writes; every case-5 entry drops "
                     "its input (%s)" % ", ".join(routes))
    return probs


def apply(record, table):
    """The outcome of a valid ``record`` (call ``check`` first): ``{outcome,
    proposed_status, modulo, declarations, dropped, notes, cite, stops, summary}``."""
    agreed = [str(x) for x in _list(table.get("modulo"))]
    out = {"outcome": "", "proposed_status": None, "modulo": [], "declarations": [],
           "dropped": [], "notes": [], "cite": [], "stops": [], "summary": ""}
    readings = record.get("readings") or {}
    if readings.get("differ"):
        out.update(outcome="disagreement", stops=[{"case": 12, "evidence":
                                                   readings.get("evidence")}],
                   summary="the runs read the statement differently (case 12): reword "
                           "the statement and open a new pass")
        return out
    facts = _facts(table)
    kept = list(agreed)

    def keep(x):
        if x and x not in kept:
            kept.append(x)

    for e in record.get("inputs") or ():
        name, case = str(e.get("input")), e.get("case")
        chosen = str(e.get("chosen") or "")
        fact = facts.get(name, {})
        if case in STOPS or (case == 7 and not chosen):
            out["stops"].append({"input": name, "case": case, "name": NAMES[case],
                                 "evidence": e.get("evidence") or ""})
            continue
        if case in DROPPED or (case == 5 and not chosen):
            out["dropped"].append({"input": name, "case": case, "line": e.get("line")})
            continue
        if case == 10:
            keep(name)
            out["cite"].append({"input": name, "evidence": e.get("evidence") or ""})
            continue
        dep = chosen or fact.get("result") or name
        keep(dep)
        if dep not in agreed and case in DECLARING:
            out["declarations"].append({"dependency": dep, "case": case,
                                        "from": name})
        if case == 2:
            out["notes"].append({"kind": "routine", "dependency": dep,
                                 "sources": list(e.get("sources") or ())})
        if case == 3:
            out["notes"].append({"kind": "remark", "dependency": dep,
                                 "sources": list(e.get("sources") or ()),
                                 "text": e.get("remark") or ""})
    if out["stops"]:
        out["outcome"] = "disagreement"
        out["summary"] = "not settled: %s" % "; ".join(
            "%s (case %s, %s)" % (s.get("input", "the pass"), s["case"], s.get("name", ""))
            for s in out["stops"])
        return out
    # a declaration and a note per dependency, once
    seen, decl = set(), []
    for d in out["declarations"]:
        if d["dependency"] not in seen:
            seen.add(d["dependency"])
            decl.append(d)
    out["declarations"] = decl
    out["modulo"] = kept
    out["outcome"] = "confirmed-settled"
    out["proposed_status"] = "proved-modulo" if kept else "proved"
    out["summary"] = ("settled: %s%s%s" % (
        ("proved-modulo " + ", ".join(kept)) if kept else "proved",
        ("; declare " + ", ".join(d["dependency"] for d in decl)) if decl else "",
        ("; cite tickets for " + ", ".join(c["input"] for c in out["cite"]))
        if out["cite"] else ""))
    return out


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=("check", "apply"))
    ap.add_argument("record", help="the settler's record (JSON)")
    ap.add_argument("--table", required=True, help="decision_table.py --json output")
    a = ap.parse_args(argv)
    try:
        record, table = _load(a.record), _load(a.table)
    except (OSError, ValueError) as e:
        print(json.dumps({"ok": False, "problems": ["cannot read: %s" % e]}))
        return 2
    probs = check(record, table)
    if a.action == "check" or probs:
        print(json.dumps({"ok": not probs, "problems": probs}, indent=1))
        return 0 if not probs else 1
    print(json.dumps(apply(record, table), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
