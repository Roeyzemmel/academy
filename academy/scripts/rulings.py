"""rulings.py -- a ruling the human answers files its follow-up by code (#121 item 4).

A **ruling ticket** is a ``decision`` ticket from an Expert instance to the human about
the inputs of one review pass whose two blind runs are both CONFIRMED on one statement
hash (verify's ``disagreement`` on the modulo lists, expert ``conclude.md`` section 4.3).
It is recognised mechanically: the ticket's text (or its parent's pass, ``<date>-<parent>``)
names the pass folder ``reviews/<ns>/<slug>/<pass>/`` in the Expert's home, whose ``A.md``
and ``B.md`` are both CONFIRMED, about one subject, on one hash, with distinct run ids, and
whose modulo lists differ (union != intersection).

When the pass holds the table the settler stage wrote (``S-table.json``, verify.js), the
lists are the table's reduced ones: the intersection is its agreed ``modulo``, the union
adds its ``differing_inputs`` (its ``dropped_inputs`` stay out). When it holds the
dependency-settler's record (``S.json``), its stops are read: case 12 (different readings),
11 (circular) and 7 with no existing result (a hidden step) leave no status to give, so
only (c) re-run after a reword or repair and (d) decline are offered; a case-9 stop
(unverified hypotheses, an open [CHECK]) keeps all four, and its evidence is quoted in the
keeper ticket.

Its options (``options``): (a) the union of the two modulo lists, (b) their intersection,
(c) a re-run, (d) decline. ``decisions.py record`` calls :func:`record` for such a ticket,
and in the same step files the follow-up the answer needs, then delivers the ruling with
the follow-up named in its result and thread:

* (a) / (b): a ``decision`` ticket to the claim-keeper's instance (the rule of the MCP's
  ``claims_propose_status``: the Researcher owning the namespace, else one sharing the
  owner's domains), ``parent`` the ruling, asking to set ``proved-modulo`` the chosen list
  (``proved`` when it is empty), with the pass's two verdict files as ``grounds``
  (``Grounds (JSON):`` line; :func:`grounds_in` reads it back);
* (c): a ``verify`` ticket back to the Expert for a fresh blind pass;
* (d): nothing; the ruling is rejected (as for any ticket).

Idempotent: a ruling that already has a follow-up (a ``keeper follow-up: T-NNNN`` thread
line, a ``decision`` / ``verify`` ticket whose title or ask names the ruling, or a
claim-keeper's line on it) files nothing new; a delivered one writes nothing at all. A
record that was interrupted (the follow-up filed, then the line or the delivery lost)
is completed by the next record: the answer line, the follow-up line and the delivery
are each written when missing. An ``accepted`` ruling without a follow-up (answered
before this existed: the stall of #121) gets it on its next record. ``stalled`` lists
the rulings answered but not delivered.

A bare ``proceed`` names no modulo (T-1521's "proceed" was "repair first"), so a ruling
refuses it and asks for a letter.

**Own options (#125).** A ruling whose ask carries its own lettered options ("(a) accept
...; (b) re-run ...; (c) wait ...", as T-0979's) is read by them (:func:`own_options`,
:func:`classify` by keyword): a letter is the ticket's own, an own accept takes the modulo
list its text names, a wait / split / other files nothing, and ``action`` names the answer
by what it does (refused when it disagrees with the letter). A re-run is filed even when
an earlier, different answer was acted on (T-0979: the keeper set a status on (a)); the
thread says the earlier status stands until the new pass decides. Any other answer over
such an earlier one is refused unless ``force``.
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as boardlib  # noqa: E402

#: a pass folder named in the ticket's text or a ``file:`` ref (``reviews/<ns>/<slug>/<pass>``)
RE_PASS_PATH = re.compile(r"reviews/([a-z0-9][a-z0-9-]*)/([^/\s`'\"()\[\]]+)/"
                          r"(\d{4}-\d{2}-\d{2}-[A-Za-z0-9-]+)")
RE_ABOUT_INPUTS = re.compile(r"(?i)\bmodulo\b|\binputs?\b")
RE_FOLLOW_UP = re.compile(r"\bkeeper follow-up: (T-\d{4,})")
RE_GROUNDS = re.compile(r"^Grounds \(JSON\): (\{.*\})\s*$", re.M)
NONE_WORDS = ("", "none", "-", "n/a", "[]", "null")
#: paper-label prefixes an unqualified modulo input may carry (decision_table.LABEL_PREFIXES)
LABEL_PREFIXES = {"lem", "thm", "defn", "def", "cor", "prop", "fact", "rmk", "obs",
                  "ex", "claim", "conj", "eq", "sec", "nota", "assm", "hyp"}
CHOICES = {"a": "union", "union": "union",
           "b": "intersection", "intersection": "intersection",
           "c": "rerun", "rerun": "rerun", "re-run": "rerun",
           "d": "decline", "decline": "decline", "no": "decline", "n": "decline"}
LETTER = {"union": "a", "intersection": "b", "rerun": "c", "decline": "d"}
#: the kinds a ruling's follow-up has: the keeper's status decision, or a verify re-run
FOLLOW_UP_KINDS = ("decision", "verify")
#: how a human's answer line reads (decisions.py, before and after this change)
RE_ANSWER = re.compile(r"^human decision: (?!decline|\(d\))")
#: the settler's stops that leave no status to give (settle_deps.py): 12 different readings,
#: 11 circular, 7 a hidden step with no existing result
NO_STATUS_CASES = (12, 11, 7)
STOP_NAMES = {12: "different readings", 11: "circular", 9: "unverified hypotheses or an "
              "open [CHECK]", 7: "hidden step with no existing result"}


# ----------------------------------------------------------------------------
# Reading a pass
# ----------------------------------------------------------------------------

def _fields(text):
    """The ``key: value`` fields of a review record: its frontmatter, else the last
    ``VERDICT`` block."""
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    block = []
    if lines and lines[0].strip() == "---":
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            block.append(ln)
    else:
        starts = [i for i, ln in enumerate(lines) if ln.strip() == "VERDICT"]
        if starts:
            for ln in lines[starts[-1] + 1:]:
                if ln.strip().startswith("```") or not ln.strip():
                    break
                block.append(ln)
    out = {}
    for ln in block:
        if ln[:1] in (" ", "\t", "-") or ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k.strip()] = "" if v in ("null", "~") else v
    return out


def _split_top(s):
    """``s`` split on the commas and semicolons outside brackets (#103)."""
    out, depth, cur = [], 0, []
    for ch in str(s):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch in ",;" and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return out


def modulo_list(value, subject="", author_ns=False):
    """A record's ``modulo`` as a list in one spelling: split at top-level commas, quotes
    and spaces collapsed, an unqualified paper label qualified with the subject's
    namespace when an Author owns it, duplicates dropped (registry aliases are not
    resolved: the keeper's ``claims_set_status`` checks the ids)."""
    s = str(value or "").strip()
    if s.lower() in NONE_WORDS:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    ns = str(subject or "").partition(":")[0]
    out = []
    for it in _split_top(s):
        it = " ".join(it.split()).strip("`'\"")
        if not it or it.lower() in NONE_WORDS:
            continue
        head = it.partition("#")[0]
        if (author_ns and ns and " " not in head and not any(c in head for c in "()[]{}")
                and head.partition(":")[0].lower() in LABEL_PREFIXES and ":" in head):
            it = "%s:%s" % (ns, it)
        if it not in out:
            out.append(it)
    return out


def _owner(workspace, ns):
    for name, inst in (workspace or {}).get("instances", {}).items():
        if inst.get("ns") == ns:
            return name, inst
    return None, {}


def keeper_instance(workspace, ns):
    """The claim-keeper's instance for namespace ``ns``: the rule of the MCP tool
    ``claims_propose_status`` (``academy/mcp/tools/claims.py`` ``_keeper_instance``)."""
    insts = (workspace or {}).get("instances", {})
    owner, info = _owner(workspace, ns)
    if owner and info.get("role") == "researcher":
        return owner
    doms = set(info.get("domains") or [])
    cands = [n for n, i in insts.items() if i.get("role") == "researcher"
             and (not doms or doms & set(i.get("domains") or []))]
    cands = cands or [n for n, i in insts.items() if i.get("role") == "researcher"]
    if not cands:
        raise ac.AcademyError("no researcher instance (claim-keeper) in workspace.json")
    return cands[0]


def _read_run(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return _fields(fh.read())
    except OSError:
        return None


def _pass_dirs(home, text, parent, subjects):
    """Candidate pass folders: the paths the ticket's text names, then the parent's pass."""
    seen = []
    for ns, slug, p in RE_PASS_PATH.findall(text):
        d = os.path.join(home, "reviews", ns, slug, p)
        if d not in seen:
            seen.append(d)
    if not seen and parent:
        found = sorted(glob.glob(os.path.join(home, "reviews", "*", "*", "*-" + parent)),
                       reverse=True)
        seen = found
    if len(seen) > 1 and subjects:
        keep = [d for d in seen if (_read_run(os.path.join(d, "A.md")) or {}).get("subject")
                in subjects]
        seen = keep or seen
    return seen


def _json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _item(x):
    return str(x.get("input") if isinstance(x, dict) else x or "").strip()


def settler_stops(record):
    """The stops of a dependency-settler record (``S.json``): ``[{"case", "input",
    "evidence"}]``, the rule of ``settle_deps.apply``."""
    if not isinstance(record, dict):
        return []
    rd = record.get("readings") or {}
    if rd.get("differ"):
        return [{"case": 12, "input": "the statement", "evidence": str(rd.get("evidence") or "")}]
    out = []
    for e in record.get("inputs") or ():
        if not isinstance(e, dict):
            continue
        case = e.get("case")
        if case in (11, 9) or (case == 7 and not str(e.get("chosen") or "").strip()):
            out.append({"case": case, "input": _item(e),
                        "evidence": " ".join(str(e.get("evidence") or "").split())})
    return out


def _uniq(items):
    out = []
    for x in items:
        if x and x not in out:
            out.append(x)
    return out


def find_ruling(board, tid, workspace=None, ticket=None):
    """The ruling ``tid`` is, as a dict, or None when it is not one (module docstring).

    ``ticket``: ``(path, meta, body)`` when already read."""
    ws = workspace if workspace is not None else boardlib._workspace_or_none()
    if not ws:
        return None
    _path, meta, body = ticket or boardlib.get_ticket(board, tid)
    insts = ws.get("instances", {})
    frm = meta.get("from")
    if meta.get("kind") != "decision" or meta.get("to") != ac.HUMAN:
        return None
    if (insts.get(frm) or {}).get("role") != "expert":
        return None
    head = body.split(ac.THREAD_HEADING)[0] if ac.THREAD_HEADING in body else body
    text = " ".join(str(meta.get(k) or "") for k in ("title", "ask", "deliverable")) + "\n" + head
    if not RE_ABOUT_INPUTS.search(text):
        return None
    home = (insts.get(frm) or {}).get("home")
    if not home:
        return None
    refs = [str(r) for r in (meta.get("refs") or [])]
    subjects = [r for r in refs if ":" in r and not r.startswith(("file:", "bib:"))]
    for d in _pass_dirs(home, text + "\n" + " ".join(refs), meta.get("parent"), subjects):
        a, b = _read_run(os.path.join(d, "A.md")), _read_run(os.path.join(d, "B.md"))
        if not a or not b:
            continue
        if any(ac_norm(r.get("verdict")) != "CONFIRMED" for r in (a, b)):
            continue
        subject, h = a.get("subject") or "", a.get("statement_hash") or ""
        if not subject or b.get("subject") != subject or not h or b.get("statement_hash") != h:
            continue
        ids = [a.get("run_id") or "", b.get("run_id") or ""]
        if not all(ids) or ids[0] == ids[1]:
            continue
        ns = subject.partition(":")[0]
        _o, owner = _owner(ws, ns)
        author_ns = owner.get("role") == "author"
        la = modulo_list(a.get("modulo"), subject, author_ns)
        lb = modulo_list(b.get("modulo"), subject, author_ns)
        union, inter = la + [x for x in lb if x not in la], [x for x in la if x in lb]
        table = _json(os.path.join(d, "S-table.json"))
        reduced = isinstance(table, dict) and "differing_inputs" in table
        if reduced:
            inter = _uniq([_item(x) for x in table.get("modulo") or ()])
            union = _uniq(inter + [_item(x) for x in table.get("differing_inputs") or ()])
        if set(union) == set(inter):
            continue            # the lists agree: nothing to rule on
        stops = settler_stops(_json(os.path.join(d, "S.json")))
        rel = os.path.relpath(d, home).replace("\\", "/")
        return {
            "id": meta["id"], "subject": subject, "pass": os.path.basename(d),
            "pass_dir": rel, "expert": frm, "statement_hash": h,
            "producer_role": owner.get("role") or "",
            "modulo_lists": {"A": la, "B": lb},
            "union": union, "intersection": inter,
            "reduced": bool(reduced),
            "dropped": [_item(x) for x in (table.get("dropped_inputs") or ())] if reduced else [],
            "stops": stops,
            "no_status": any(x["case"] in NO_STATUS_CASES for x in stops),
            "verdicts": [{"verdict": "CONFIRMED", "run_id": r.get("run_id"),
                          "statement_hash": h, "grader_role": "expert",
                          "ref": "file:%s/%s/%s.md" % (frm, rel, run)}
                         for run, r in (("A", a), ("B", b))],
            "keeper": keeper_instance(ws, ns),
            "packets": [r for r in refs if ac.RE_PACKET_ID.match(r)],
            "priority": meta.get("priority") or "normal",
        }
    return None


def ac_norm(v):
    return " ".join(str(v or "").replace("_", " ").replace("-", " ").upper().split())


# ----------------------------------------------------------------------------
# Options and the follow-up
# ----------------------------------------------------------------------------

def _fmt(items):
    return "[" + ", ".join(items) + "]" if items else "no inputs"


def _stops_text(r):
    return "; ".join("%s (case %s, %s)%s" % (x["input"], x["case"], STOP_NAMES.get(x["case"], ""),
                                             (": " + x["evidence"]) if x["evidence"] else "")
                     for x in r.get("stops") or ())


def options(r):
    """The options of a ruling, ``{label, description}`` as decisions.py shows them: four,
    or only (c) and (d) when the settler stopped on a case that leaves no status."""
    if r.get("no_status"):
        return [
            {"label": "(c) Re-run", "description": "No status: the dependency-settler stopped "
             "(%s); a verify ticket for a fresh blind pass after the reword or repair goes to %s"
             % (_stops_text(r), r["expert"])},
            {"label": "(d) Decline", "description": "Reject the ruling; nothing is filed."},
        ]
    return [
        {"label": "(a) Union", "description": "%s %s modulo the union of both runs' lists %s; "
         "the keeper ticket is filed now" % (r["subject"], _target(r["union"]), _fmt(r["union"]))},
        {"label": "(b) Intersection", "description": "%s %s modulo what both runs list %s; "
         "the keeper ticket is filed now" % (r["subject"], _target(r["intersection"]),
                                              _fmt(r["intersection"]))},
        {"label": "(c) Re-run", "description": "No status now: a verify ticket for a fresh "
         "blind pass goes to %s" % r["expert"]},
        {"label": "(d) Decline", "description": "Reject the ruling; nothing is filed."},
    ]


def _target(modulo):
    return "proved-modulo" if modulo else "proved"


def parse_choice(choice, r=None):
    c = str(choice or "").strip().lower().strip("()")
    if c in CHOICES:
        if r and r.get("no_status") and CHOICES[c] in ("union", "intersection"):
            raise ac.AcademyError(
                "%s: the dependency-settler stopped (%s): no status can be given; answer "
                "c/re-run or d/decline" % (r["id"], _stops_text(r)))
        return CHOICES[c]
    raise ac.AcademyError(
        "a ruling on the inputs takes a/union, b/intersection, c/re-run or d/decline, not %r "
        "(a bare proceed names no modulo)" % choice)


# ----------------------------------------------------------------------------
# A ticket's own lettered options (#125)
# ----------------------------------------------------------------------------

#: a letter opening an option: ``(a) `` at the start or after a space or ``:;,``
RE_OWN_MARK = re.compile(r"(?:^|(?<=[\s:;,]))\(([a-h])\)\s+(?=\S)")
#: the action an option's text names, by keyword; the earliest keyword in the text wins
ACTION_WORDS = (
    ("rerun", re.compile(r"(?i)\bre-?run\b|\bfresh (?:blind )?pass\b|\bre-?verif")),
    ("split", re.compile(r"(?i)\bsplit\b")),
    ("wait", re.compile(r"(?i)\bwait\b|\bpostpone\b|\bdefer\b")),
    ("decline", re.compile(r"(?i)\bdecline\b|\breject\b|\bdrop\b")),
    ("accept", re.compile(r"(?i)\baccept\b|\bunion\b|\bintersection\b|\bproceed\b|"
                          r"\bproved(?:-modulo)?\b|\bkeeper\b|\bredeploy\b")),
)
ACTION_LABEL = {"accept": "Accept", "rerun": "Re-run", "wait": "Wait", "split": "Split",
                "decline": "Decline", "other": "Other"}
#: ``--action`` words (and words given as ``--choice``) and the answer they name
ACTIONS = {"rerun": "rerun", "re-run": "rerun", "accept": "accept", "wait": "wait",
           "split": "split", "decline": "decline", "no": "decline", "n": "decline",
           "union": "union", "intersection": "intersection"}


def kind_of(which):
    """The action class of an answer: union and intersection are both an accept."""
    return "accept" if which in ("union", "intersection") else which


#: words that present a list of options just before its "(a)"
RE_OPTION_CUE = re.compile(r"(?i)\b(?:options?|choose|choices?|rule|ruling|decide|pick|"
                           r"either|one of)\b")
#: a paragraph break, kept while the text's other whitespace is collapsed
PARA = "\u2029"
#: words too slight to be an option's text on their own
SLIGHT = {"and", "or", "the", "a", "an", "both", "of", "to", "in", "on"}


def _substantial(t):
    return any(len(w) >= 2 and w.lower() not in SLIGHT for w in re.findall(r"[A-Za-z][\w-]*", t))


def _presented(prefix):
    """True when the text before an "(a)" presents options: it ends with ':' or '?', or a
    cue word (Options, Choose, Please rule ...) stands in its last 60 characters."""
    p = prefix.rstrip().rstrip("`*_")
    return p.endswith((":", "?")) or bool(RE_OPTION_CUE.search(p[-60:]))


def _run(text, marks, i):
    """The options of the run starting at ``marks[i]`` (an "(a)"), or {} when it is none."""
    seq, want = [marks[i]], "b"
    for m in marks[i + 1:]:
        if m.group(1) == want:
            seq.append(m)
            want = chr(ord(want) + 1)
    out = {}
    for j, m in enumerate(seq):
        last = j + 1 == len(seq)
        t = text[m.end():len(text) if last else seq[j + 1].start()]
        if last:                                  # the last option ends with its sentence
            t = re.split(r"\.\s|%s" % PARA, t, maxsplit=1)[0]
        t = t.replace(PARA, " ")
        t = re.sub(r"[\s;,.]*(?:\b(?:or|and)\b)?[\s;,.]*$", "", t).strip()
        if not _substantial(t):
            return {}
        out[m.group(1)] = t
    return out if len(out) >= 2 else {}


def _lettered(text):
    """The options "(a) ...; (b) ...[; (c) ...]" a text presents, or {}: a full run from (a)
    on, each option with real text, presented as options (``_presented``); the last such run
    in the text wins (an earlier stray "(a)", a precedent's "D1 (a)", is prose)."""
    paras = re.split(r"\n[ \t]*\n", str(text or "").replace("\r\n", "\n"))
    text = (" %s " % PARA).join(" ".join(p.split()) for p in paras)
    marks = list(RE_OWN_MARK.finditer(text))
    for i in reversed(range(len(marks))):
        if marks[i].group(1) != "a" or not _presented(text[:marks[i].start()]):
            continue
        out = _run(text, marks, i)
        if out:
            return out
    return {}


def own_options(meta, body=None):
    """The ticket's own lettered options ``{letter: text}`` ("(a) ...; (b) ...; (c) ..." in
    its ask, else, when ``body`` is given, in the body's ``## Ask`` section), or ``{}``.
    A ruling is read with its body, in the listing and in ``record`` alike; a plain ticket
    with its ask line only (decisions.py), so the letters listed are the letters recorded."""
    out = _lettered((meta or {}).get("ask"))
    if out or not body:
        return out
    head = body.split(ac.THREAD_HEADING)[0]
    m = re.search(r"^## Ask[ \t]*\n(.*?)(?=^## |\Z)", head, re.M | re.S)
    return _lettered(m.group(1)) if m else {}


#: a negation within two words (one clause) before a keyword: "not proved", "don't take proved"
RE_NEGATED = re.compile(r"(?i)\b(?:not|don't|dont|do not|never|without|no)\b"
                        r"(?:[ \t`]+[\w'-]+){0,2}[ \t`]*$")        # within the clause
RE_NOT_PROVED = re.compile(r"(?i)\b(?:not|don't|dont|do not|never|without|no)\b"
                           r"(?:[ \t`]+[\w'-]+){0,2}?[ \t`]+proved\b")


def _first(rx, text):
    """The start of ``rx``'s first match in ``text`` that is not negated, or None."""
    for m in rx.finditer(text):
        if not RE_NEGATED.search(text[max(0, m.start() - 30):m.start()]):
            return m.start()
    return None


def classify(text):
    """The action an option's text names: rerun, split, wait, decline, accept or other.
    The earliest keyword not negated wins; an accept whose text negates 'proved' ("not
    proved yet") is other, so no status is proposed from it."""
    text = str(text or "")
    best = None
    for name, rx in ACTION_WORDS:
        at = _first(rx, text)
        if at is not None and (best is None or at < best[0]):
            best = (at, name)
    name = best[1] if best else "other"
    return "other" if name == "accept" and RE_NOT_PROVED.search(text) else name


def own_option_dicts(own):
    """The own options as decisions.py shows them (``{label, description}``)."""
    return [{"label": "(%s) %s" % (k, ACTION_LABEL[classify(v)]), "description": v}
            for k, v in own.items()]


def _own_names(own):
    return "; ".join("(%s) %s" % (k, v) for k, v in own.items())


def _action(action):
    if action in (None, ""):
        return None
    a = str(action).strip().lower()
    if a not in ACTIONS:
        raise ac.AcademyError("--action takes rerun, accept, wait, split, decline, union or "
                              "intersection, not %r" % action)
    return ACTIONS[a]


def pick_own(own, choice, action, tid):
    """The ticket's own option an answer names: ``(letter, action class, text, action)``.
    ``choice`` is one of its letters (or an action word); ``action`` an ``--action``; when
    both are given their classes must agree."""
    act = _action(action)
    c = str(choice or "").strip().lower().strip("()")
    names = _own_names(own)
    if c and c not in own:
        if c in ACTIONS and not act:
            act, c = ACTIONS[c], ""
        else:
            raise ac.AcademyError(
                "%s has its own options: %s. --choice takes one of their letters, or give "
                "--action rerun|accept|wait|decline" % (tid, names))
    if c:
        cls = classify(own[c])
        if act and kind_of(act) != cls:
            raise ac.AcademyError(
                "%s: --choice %s is the ticket's own (%s) %r, a %s, but --action %s says "
                "otherwise. The ticket's own options: %s" % (tid, c, c, own[c], cls, act, names))
        return c, cls, own[c], act
    if not act:
        raise ac.AcademyError("%s: name the answer with --choice <letter> or --action. The "
                              "ticket's own options: %s" % (tid, names))
    hits = [k for k in own if classify(own[k]) == kind_of(act)]
    if len(hits) != 1:
        raise ac.AcademyError(
            "%s: %s of the ticket's own options is a %s; name the letter. Its options: %s"
            % (tid, "none" if not hits else "more than one", kind_of(act), names))
    return hits[0], kind_of(act), own[hits[0]], act


def _accept_list(r, text):
    """Which modulo list (union or intersection) an own 'accept' option names."""
    low = text.lower()
    if ("union" in low) != ("intersection" in low):
        return "union" if "union" in low else "intersection"
    if r["union"] and all(x in text for x in r["union"]):
        return "union"
    if r["intersection"] and all(x in text for x in r["intersection"]):
        return "intersection"
    if not r["intersection"] and re.search(r"\bproved\b(?!-)", low):
        return "intersection"                       # "take proved": the empty intersection
    raise ac.AcademyError(
        "%s: the ticket's own option %r does not say which modulo list it takes (union %s, "
        "intersection %s); answer with --action union or --action intersection"
        % (r["id"], text, _fmt(r["union"]), _fmt(r["intersection"])))


def resolve(r, meta, body, choice, action=None):
    """The answer ``choice`` / ``action`` names on ruling ``r``: ``{"letter", "which",
    "option"}``. ``which`` is union, intersection, rerun, decline, or (an own option only)
    wait, split or other; ``option`` the ticket's own option text, else None. With its own
    lettered options the ticket's letters are read (#125); else the generic four."""
    own = own_options(meta, body)
    act = _action(action)
    if (own and choice in (None, "") and act in ("rerun", "decline")
            and not any(classify(v) == act for v in own.values())):
        # a re-run (or a decline) is always an answer to a ruling, even when none of the
        # ticket's own options is one (T-0981); "-" is no letter, so none is misread
        return {"letter": "-", "which": act, "option": None}
    if own:
        letter, cls, text, act = pick_own(own, choice, action, r["id"])
        if cls == "accept":
            which = act if act in ("union", "intersection") else _accept_list(r, text)
        else:
            which = cls
    else:
        if act in ("accept", "wait", "split"):
            raise ac.AcademyError(
                "%s offers (a) union, (b) intersection, (c) re-run, (d) decline: --action %s "
                "is none of them%s" % (r["id"], act, " (name union or intersection)"
                                       if act == "accept" else ""))
        which = parse_choice(choice, r) if choice not in (None, "") else None
        if which and act and which != act:
            raise ac.AcademyError(
                "%s: --choice %s is (%s) %s, but --action says %s; its options are (a) "
                "union, (b) intersection, (c) re-run, (d) decline"
                % (r["id"], choice, LETTER[which], which, act))
        which = which or act
        if not which:
            raise ac.AcademyError("%s: name the answer with --choice or --action" % r["id"])
        letter, text = LETTER[which], None
    if r.get("no_status") and which in ("union", "intersection"):
        parse_choice(which, r)                                  # raises: no status to give
    return {"letter": letter, "which": which, "option": text}


def grounds(r, which, quote=""):
    modulo = list(r[which])
    g = {"basis": "proof", "verdicts": [dict(v) for v in r["verdicts"]],
         "producer_role": r["producer_role"], "statement_hash": r["statement_hash"],
         "note": "the human's ruling %s: (%s) the %s of both runs' modulo lists%s"
                 % (r["id"], LETTER[which], which, (" -- " + quote) if quote else "")}
    if modulo:
        g["modulo"] = modulo
    return g


def grounds_in(body):
    """The grounds a follow-up ticket carries, parsed back (None when it has none)."""
    m = RE_GROUNDS.search(body or "")
    return json.loads(m.group(1)) if m else None


def follow_ups(board, tid, body=None):
    """Every live follow-up of ruling ``tid``: ``[(ref, how, action)]``, the thread's
    ``keeper follow-up:`` lines first (``how`` ``line``), then the tickets naming the ruling
    in their title or ask (``ticket``), then a claim-keeper's line on it (``keeper``; ref
    the speaker). ``action`` is ``rerun`` (a verify ticket) or ``accept`` (a keeper's
    decision ticket, or the keeper's own action). A cancelled or rejected follow-up is not
    live (the way to take an answer back is to cancel its follow-up, then record again)."""
    if body is None:
        body = boardlib.get_ticket(board, tid)[2]
    metas = {m.get("id"): m for m in boardlib.list_tickets(board, include_terminal=True)}
    dead = ("cancelled", "rejected")
    out, keeper = [], None
    for _d, who, text in ac.thread_lines(body):
        m = RE_FOLLOW_UP.search(text)
        if m and not any(o[0] == m.group(1) for o in out):
            k = metas.get(m.group(1))
            if k is None:
                out.append((m.group(1), "line", "rerun" if "re-run" in text else "accept"))
            elif k.get("status") not in dead:
                out.append((m.group(1), "line", "rerun" if k.get("kind") == "verify"
                            else "accept"))
        if keeper is None and str(who).endswith("/claim-keeper"):
            keeper = who
    names = re.compile(r"\b%s\b" % re.escape(tid))
    for m in metas.values():
        if (m.get("kind") in FOLLOW_UP_KINDS and m.get("to") != ac.HUMAN
                and m.get("id") != tid and m.get("status") not in dead
                and not any(o[0] == m.get("id") for o in out)
                and names.search("%s %s" % (m.get("title") or "", m.get("ask") or ""))):
            out.append((m["id"], "ticket", "rerun" if m.get("kind") == "verify" else "accept"))
    if keeper:
        out.append((keeper, "keeper", "accept"))
    return out


def _best(fus):
    """The follow-up to name: the last ``line``, else the first ticket, else the keeper.
    ``fus`` is a :func:`follow_ups` list (or part of one)."""
    lines = [f for f in fus if f[1] == "line"]
    return lines[-1] if lines else (fus[0] if fus else None)


def follow_up_of(board, tid, body=None):
    """The follow-up a ruling already has, as ``(ref, how)``, or None. ``how`` is ``line``
    (a ``keeper follow-up: T-NNNN`` line in its thread; ref the ticket id), ``keeper`` (a
    claim-keeper's line on it: the keeper acted, as on T-0979; ref the speaker) or
    ``ticket`` (a ``decision`` / ``verify`` ticket to a role whose title or ask names the
    ruling, as this code files it: ``... (ruling T-NNNN)``; ref its id). A ticket that
    only lists the ruling in its refs is not one: it may be about something else."""
    f = _best(follow_ups(board, tid, body))
    return (f[0], f[1]) if f else None


def plan(r, which, comment=""):
    """The follow-up ticket's fields for answer ``which`` (no write), or None for decline."""
    quote = " ".join(str(comment or "").split())
    vrefs = [v["ref"] for v in r["verdicts"]]
    refs = [r["subject"], r["id"]] + [p for p in r["packets"] if p not in (r["subject"],)] + vrefs
    if which == "rerun":
        return {"to": r["expert"], "kind": "verify",
                "title": "Re-run the blind pass on %s (ruling %s)" % (r["subject"], r["id"]),
                "ask": "Verify %s in a fresh blind pass: the human ordered a re-run instead of "
                       "ruling on the inputs of pass %s (%s)." % (r["subject"], r["pass"], r["id"]),
                "deliverable": "A new pass with its decision record and packet.",
                "refs": refs,
                "detail": "The human's answer on %s: (c) re-run%s.\n\nThe earlier pass: `%s` "
                          "(A and B CONFIRMED on hash %s, modulo lists differing).%s"
                          % (r["id"], (" -- " + quote) if quote else "", r["pass_dir"],
                             r["statement_hash"],
                             ("\n\nThe dependency-settler stopped (S.json, S.md in the pass "
                              "folder): %s. Re-run once the statement is reworded or the proof "
                              "repaired." % _stops_text(r)) if r.get("stops") else "")}
    if which not in ("union", "intersection"):
        return None
    g = grounds(r, which, quote)
    status = _target(g.get("modulo"))
    return {"to": r["keeper"], "kind": "decision",
            "title": "Status of %s -> %s (ruling %s)" % (r["subject"], status, r["id"]),
            "ask": "Set %s to %s%s (claims_set_status) on the human's ruling %s (%s), with "
                   "the grounds below." % (r["subject"], status,
                                            (" modulo " + _fmt(g["modulo"])) if g.get("modulo") else "",
                                            r["id"], which),
            "deliverable": "The status is set with grounds, or the ticket is rejected with "
                           "the reason.",
            "refs": refs,
            "detail": "\n\n".join(p for p in [
                "The human's answer on %s: (%s) the %s of both runs' modulo lists%s."
                % (r["id"], LETTER[which], which, (" -- \"%s\"" % quote) if quote else ""),
                "Pass `%s` of the Expert %s: A and B CONFIRMED on statement hash %s. "
                "A lists %s; B lists %s." % (r["pass_dir"], r["expert"], r["statement_hash"],
                                            _fmt(r["modulo_lists"]["A"]),
                                            _fmt(r["modulo_lists"]["B"])),
                ("The lists are the decision table's reduced ones (S-table.json): agreed %s; "
                 "differing %s; dropped mechanically %s." % (
                     _fmt(r["intersection"]), _fmt([x for x in r["union"]
                                                    if x not in r["intersection"]]),
                     _fmt(r["dropped"]))) if r.get("reduced") else "",
                ("The dependency-settler's stops (S.json, S.md in the pass folder): %s."
                 % _stops_text(r)) if r.get("stops") else "",
                "If the claim's statement hash is no longer %s (the statement was edited), do "
                "not set it: reject this ticket with that reason, for a re-run. An input that "
                "is itself unsettled stays in the modulo list." % r["statement_hash"],
                "Grounds (JSON): " + json.dumps(g, ensure_ascii=False, separators=(", ", ": ")),
            ] if p)}


def _deliver(board, tid, result, date):
    meta = boardlib.get_ticket(board, tid)[1]
    if meta.get("status") == "open":
        boardlib.transition_ticket(board, tid, "accepted", as_instance=ac.HUMAN, date=date)
        meta = boardlib.get_ticket(board, tid)[1]
    if meta.get("status") == "accepted":
        boardlib.transition_ticket(board, tid, "in-progress", as_instance=ac.HUMAN, date=date)
    boardlib.transition_ticket(board, tid, "delivered", result=result, as_instance=ac.HUMAN,
                               date=date)


#: this code's answer line: ``human decision: (<letter>) <which>``
RE_ANSWER_LINE = re.compile(r"^human decision: \(([a-h-])\) ([a-z-]+)")


def _answers(body):
    """``(letter, which)`` of this code's earlier answer lines on a ruling, in order."""
    out = []
    for _d, w, t in ac.thread_lines(body):
        m = RE_ANSWER_LINE.match(t) if w == ac.HUMAN else None
        if m and (m.group(1), m.group(2)) not in out:
            out.append((m.group(1), m.group(2)))
    return out


def _answered(body, letter, which):
    """True when the thread already holds this code's answer line for this answer."""
    want = "human decision: (%s) %s" % (letter, which)
    return any(w == ac.HUMAN and (t == want or t.startswith(want + " "))
               for _d, w, t in ac.thread_lines(body))


def _earlier(body):
    """The last human answer on the ruling, as ``<date> "<line>"``, or None."""
    rows = [(d, t) for d, w, t in ac.thread_lines(body)
            if w == ac.HUMAN and t.startswith("human decision:")]
    if not rows:
        return None
    d, t = rows[-1]
    t = " ".join(t.split())
    return '%s "%s"' % (d, t if len(t) <= 160 else t[:157] + "...")


def _acted(fus):
    return ", ".join("the claim-keeper's action (%s)" % ref if how == "keeper"
                     else "%s (%s)" % (ref, "a re-run" if act == "rerun" else "the status")
                     for ref, how, act in fus)


def _short(text, n=120):
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[:n - 3] + "..."


def record(board, r, choice, comment="", workspace=None, date=None, ticket=None,
           action=None, force=False):
    """Record the human's answer to ruling ``r`` and file its follow-up in the same step.

    ``choice`` is a letter (the ticket's own when its ask carries lettered options, #125,
    else the generic four) or ``None``; ``action`` (rerun, accept, wait, split, decline,
    union, intersection) names the answer by what it does, and must agree with the letter
    when both are given.

    Returns ``{"ref", "status", "choice", "follow_up", "filed"}``; ``filed`` is True only
    when this call filed the follow-up. Each step is written only when missing (the answer
    line, the follow-up, its ``keeper follow-up:`` line, the delivery), so a second record
    of a delivered ruling writes nothing and one after an interruption completes it.

    A follow-up of the same action is reused. A re-run is filed even when an earlier,
    different answer was acted on (the keeper set a status): a thread line names that
    answer and says its status stands until the new pass decides. Any other answer over an
    earlier, different one that was acted on is refused unless ``force``. A wait, split or
    other own option files nothing."""
    date = date or ac.today()
    tid = r["id"]
    _path, meta, body = ticket or boardlib.get_ticket(board, tid)
    pick = resolve(r, meta, body, choice, action)
    which, letter, own = pick["which"], pick["letter"], pick["option"]
    cls = kind_of(which)
    status = meta.get("status")
    fus = follow_ups(board, tid, body)
    clash = cls == "accept" and any(kind_of(w) == "accept" and w != which
                                    for _l, w in _answers(body))
    match = [] if clash else [f for f in fus if f[2] == cls]
    differing = [f for f in fus if f not in match]
    if status == "delivered" and (match or _answered(body, letter, which)):
        f = _best(match)
        return {"ref": tid, "status": status, "choice": letter,
                "follow_up": f[0] if f else None, "filed": False}
    if status not in ("open", "accepted", "in-progress"):
        raise ac.AcademyError("%s is %s: a finished ruling is not answered again" % (tid, status))
    text = "human decision: (%s) %s" % (letter, which)
    if own:
        text += " [the ticket's own (%s): %s]" % (letter, _short(own))
    elif letter == "-":
        text += " [not one of the ticket's own options]"
    if str(comment).strip():
        text += " -- " + " ".join(str(comment).split())
    if which == "decline":
        if not _answered(body, letter, which):
            boardlib.append_to_ticket(board, tid, text, as_instance=ac.HUMAN, date=date)
        reason = " ".join(str(comment).split()) or "declined via /academy:decide"
        boardlib.transition_ticket(board, tid, "rejected" if status == "open" else "cancelled",
                                   reason=reason, as_instance=ac.HUMAN, date=date)
        have = _best(fus)
        return {"ref": tid, "status": "rejected" if status == "open" else "cancelled",
                "choice": letter, "follow_up": have[0] if have else None, "filed": False}
    over = differing and not match
    if over and cls != "rerun" and not force:
        raise ac.AcademyError(
            "%s was answered before (%s) and that answer was acted on: %s. (%s) %s is not "
            "recorded over it: a re-run is (the earlier status stands until the new pass "
            "decides); for this answer pass --force (what was done stays done), or cancel the "
            "follow-up ticket first, then record again."
            % (tid, _earlier(body) or "the keeper acted on the ruling", _acted(differing),
               letter, which))
    if not _answered(body, letter, which):
        boardlib.append_to_ticket(board, tid, text, as_instance=ac.HUMAN, date=date)
    filed, new, how, to = False, None, None, ""
    if match:
        new, how = _best(match)[:2]
    elif cls in ("accept", "rerun"):
        spec = plan(r, which, comment)
        _p, stored = boardlib.create_ticket(
            board, spec["to"], spec["title"], spec["ask"], spec["deliverable"],
            kind=spec["kind"], priority=r["priority"], refs=spec["refs"], parent=tid,
            budget={"runs": 1}, detail=spec["detail"], as_instance=ac.HUMAN,
            workspace=workspace, date=date, return_meta=True)
        new, how, to, filed = stored["id"], "ticket", spec["to"], True
    if how == "ticket":
        boardlib.append_to_ticket(
            board, tid, "keeper follow-up: %s%s (%s)" % (
                new, (" to " + to) if to else "",
                ("a re-run; no new status until it decides" if over else
                 "a re-run; no status now") if cls == "rerun" else "the status, on this ruling"),
            as_instance=ac.HUMAN, date=date)
    if over:
        boardlib.append_to_ticket(
            board, tid, "earlier ruling: %s, acted on: %s. %s" % (
                _earlier(body) or "none recorded by decisions.py", _acted(differing),
                ("Its status stands until the new pass %s decides." % new) if cls == "rerun"
                else "This answer (%s) %s was recorded over it with --force; what was done on "
                     "the earlier one is not undone." % (letter, which)),
            as_instance=ac.HUMAN, agent="decisions", date=date)
    if how == "keeper":
        result = "Ruling (%s) %s: the claim-keeper acted on it (%s)" % (letter, which, new)
    elif new:
        result = "Ruling (%s) %s: follow-up %s%s" % (
            letter, which, new, " (the earlier ruling's status stands until it decides)"
            if over and cls == "rerun" else "")
    else:
        result = "Ruling (%s) %s: nothing filed (the ticket's own option: %s)" % (
            letter, which, _short(own, 100))
    _deliver(board, tid, result, date)
    return {"ref": tid, "status": "delivered", "choice": letter, "follow_up": new,
            "filed": filed}


# ----------------------------------------------------------------------------
# Stalled rulings
# ----------------------------------------------------------------------------

def stalled(board, workspace=None):
    """Rulings the human answered (a ``human decision:`` line, not a decline) that are not
    delivered: ``[{"id", "subject", "answer", "follow_up"}]``. ``follow_up`` is what
    ``follow_up_of`` found (an interrupted record, or a keeper who acted), or None (the
    stall of #121); ``record <id> --choice <a-c>`` completes either."""
    ws = workspace if workspace is not None else boardlib._workspace_or_none()
    roles = {n: i.get("role") for n, i in (ws or {}).get("instances", {}).items()}
    metas = boardlib.list_tickets(board, include_terminal=True)
    out = []
    for m in metas:
        if (m.get("kind") != "decision" or m.get("to") != ac.HUMAN
                or roles.get(m.get("from")) != "expert"
                or m.get("status") not in ("open", "accepted", "in-progress")):
            continue
        t = boardlib.get_ticket(board, m["id"])
        answers = [x for _d, w, x in ac.thread_lines(t[2]) if w == ac.HUMAN and RE_ANSWER.match(x)]
        if not answers:
            continue
        r = find_ruling(board, m["id"], ws, ticket=t)
        if not r:
            continue
        have = follow_up_of(board, m["id"], t[2])
        out.append({"id": m["id"], "subject": r["subject"], "answer": answers[-1],
                    "follow_up": have[0] if have else None})
    return out
