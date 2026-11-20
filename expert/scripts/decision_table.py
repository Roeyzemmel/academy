"""decision_table.py -- the proof-review decision table, applied mechanically.

    py decision_table.py A.md [B.md|-] [--established id1,id2] [--primary M1,M2] [--json]
    py decision_table.py canon [--subject S] ITEM...   # each input in canonical spelling

Takes the verdict records of run A and (optionally) run B -- files landed by
``land_verdict.py`` under ``<expert home>/reviews/<ns>/<id>/<pass>/`` or any text
ending in a ``VERDICT`` block -- and prints the outcome. The review-chair runs it
and follows it; it never substitutes its own reading (roster-rules.md, rule 3).

The table (from the old /paper:verify, in the academy's verdict words):

| Run A | Run B | Outcome |
|---|---|---|
| CONFIRMED | not yet run | ``awaiting-b``: launch B with the identical brief |
| CONFIRMED | CONFIRMED, no inputs on either | ``confirmed``: propose ``proved``; recolour earned |
| CONFIRMED modulo X | CONFIRMED modulo X (same set) | ``confirmed-modulo``: propose ``proved-modulo``; recolour only if every input in X is established |
| CONFIRMED (modulo X) | CONFIRMED modulo Y, X and Y differ only in definitions | a definition tagged ``notation-only`` in its registry record is dropped (``dropped_definitions``); any other is an input of both runs (``kept_definitions``), so ``confirmed-modulo`` (#103) |
| CONFIRMED (modulo X) | CONFIRMED modulo Y, still different after the mechanical reduction, no blocking step | ``settle-dependencies``: no status yet; the dependency-settler classifies each differing input (``differing_inputs``), ``settle_deps.py`` checks and applies it (#121) |
| CONFIRMED (modulo X) | CONFIRMED modulo Y, a run naming a blocking step | ``disagreement`` |
| CONFIRMED | GAP | ``disagreement``: no status; file the weaker run's blocking step |
| DISPROVED (either run) | any | ``disproved``: no status; the counterexample goes to the human at once |
| GAP | not run | ``single-negative``: no status; A's blocking step is the repair item; B skipped by design |
| PLAUSIBLE (either run) | any non-DISPROVED | ``degraded``: a fallback verdict never counts; re-run that run on a primary |
| two CONFIRMED with a shared run id, differing statement hashes or subjects | | ``invalid-pair``: no status; the pair is not two independent reviews of one statement |
| anything else | | ``no-change``: report the union of the findings (a fallback: with the four verdict words and the sequencing rule no input reaches it) |
| run A missing or unreadable | | ``incomplete`` |

A **reword run** (T-0347, the human's decision of 2026-10-12: a statement reworded after a CONFIRMED x2
pass gets one informed run, not a new blind pair) is a record with ``mode: reword``,
``base_pass``, ``base_hash`` and ``reword_scope`` (equivalent / weaker / covered /
exceeds). Given as run A, it is decided by ``decide_reword`` against the base pass's
A and B (found beside the reword pass, or ``--base-dir``): R CONFIRMED with scope
equivalent / weaker / covered on a base the table confirms on ``base_hash`` gives
``confirmed`` / ``confirmed-modulo`` (the base's modulo plus R's), with grounds of
``mode: reword``; R GAP or ``exceeds`` gives ``full-pass-needed`` (no status; a fresh
blind pass); a missing, abandoned or unconfirmed base, another hash, subject or pass, a
shared run id or an unchanged statement gives ``invalid-base``. A reword record given as
run B is an ``invalid-pair``: it is never half of a blind pair.

A reword run on a **renamed** record (T-0476) names ``base_subject``: the superseded id
whose reviews folder holds the base pass. The base is then read from
``<reviews>/<ns>/<dir of base_subject>/<base_pass>/`` and its runs must be about
``base_subject``; the result and its grounds (top level and every row) carry
``base_subject``. Whether the claim supersedes that id is checked where the status is
set (``registry.core.grounds.check_verdict_refs``) and when the pass is opened
(``reviews.py new-pass --base-subject``), not here.

Mechanical rules applied before the table:

* The primaries are workspace.json's ``grading.primaryModels``, equal in authority
  (``PRIMARY_MODELS``, Fable and Opus 5.5, when the workspace sets none); ``--primary``
  takes a comma-separated list instead. A CONFIRMED given on any other model (Sonnet,
  Haiku, an older Opus, a bare ``opus`` that names no version, or no model at all) is
  read as PLAUSIBLE (roster-rules.md, "Graders degrade"). Every run's recorded model is kept
  in ``runs[].model``.
* The definition rule (the human's ruling of 2026-11-20 on #103, replacing T-0148's
  unconditional drop, which gave the wrong ``proved`` on T-1475): a definition listed in
  a CONFIRMED run's modulo stays an input, giving ``proved-modulo``, unless its registry
  record is tagged ``notation-only`` (``tags: [notation-only]``; a reviewer's own
  ``(notation only)`` mark is read past, never trusted). A tagged definition is dropped
  from both lists (``dropped_definitions``); any other definition either run lists is an
  input of both (``kept_definitions``), mechanically, so it never reaches the
  dependency-settler. Both are named in the grounds' note. An id is a definition when
  its registry record's kind is a definition (``definition`` / ``def`` / ``defn``,
  looked up through the registry engine), or, when the registry cannot be read or has
  no such record, when its label starts with ``defn:`` / ``def:`` or its id with
  ``DEF-``. A ``bib:`` input is never one.
* One input, one spelling (#103): before any comparison every modulo list (and
  ``--established``) is normalised by ``normalise_modulo``: split only on top-level
  commas (a list landed split inside brackets is rejoined), a pointer's trailing text
  dropped, an unqualified label qualified with the subject's namespace, an alias
  resolved to its record id, and a pinpoint's punctuation between word and number
  removed (``#Thm-2.6`` = ``#Thm2.6``). A ``disagreement`` that remains carries
  ``modulo_options``: the union and the intersection, the ruling's two options.
* Differing inputs are not a conflict (#121; the human's design of 2026-11-20): two
  CONFIRMED runs, neither naming a blocking step, whose modulo lists differ are first
  reduced mechanically, stage 1 of the human's fixed order, only where the registry shows
  it (``links_of``, qid -> ``{depends_on, cites, modulo}``; the CLI passes
  ``registry_links``): the definition rule above; case 13, a shared input that is itself proved-modulo carries its modulo; case
  4, an input only one run lists is dropped when another listed input reaches it through
  ``depends_on`` (transitively, never through the subject) or, for a card
  ``bib:KEY[#PIN]``, ``cites`` KEY. What still differs gives ``settle-dependencies``:
  ``differing_inputs`` each with its admissibility facts (``input_facts``: an open
  [CHECK], registry existence with an unknown namespace counted as not shown, a cycle
  back to the subject), both runs' lists in ``modulo_lists``, the drops in
  ``dropped_inputs``, and ``grounds_template`` (both verdict rows, no modulo, no note:
  ``grounds`` itself stays None). The settler and ``settle_deps.py`` take it from there.
* B present after a non-CONFIRMED A is a process anomaly (B should not have run);
  it is reported, and the outcome is taken from A alone.

Every item to file (``file_items``) carries its ``route``, from ``follow_up`` (the role
cut, academy/references/roster-rules.md): a finding classed ``hypothesis`` or
``statement`` (the VERDICT block's ``gap_class``; without one, a blocking step that
names a hypothesis, an assumption or the statement, or asks to strengthen a hypothesis
or weaken the claim), and any missing proof step, is a ``prove`` ticket to the
Researcher with the falsifier -- never an Author ``apply`` / ``write`` ticket. Only a
``wording`` finding goes back to the statement's owner as a ``question``.

Exit code: 0 on an outcome, 2 on a usage error. The JSON carries ``grounds`` in the
shape ``claims_propose_status`` / ``check_grounds`` expect.
"""

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402

VERDICTS = ("CONFIRMED", "PLAUSIBLE", "GAP", "DISPROVED")
#: the reword run's own fields (T-0347): blank on every blind run
REWORD_FIELDS = ("mode", "base_pass", "base_hash", "reword_scope", "base_subject")
#: the dependency amendment (the human's design, 2026-11-20): ``add_dependency`` is a
#: reviewer's suggestion (inputs the proof relies on but does not list); ``amended_with``
#: is an amend run's list of the dependencies the amendment added (``mode: amend``, with
#: ``base_pass`` and ``base_hash`` naming run A of the same pass)
AMEND_FIELDS = ("add_dependency", "amended_with")
FIELDS = ("subject", "pass", "run", "run_id", "verdict", "modulo", "model",
          "statement_hash", "blocking", "ticket", "gap_class") + REWORD_FIELDS + AMEND_FIELDS
LIST_FIELDS = ("modulo",) + AMEND_FIELDS
#: a reword run's reading of the new wording against the proof as reviewed: ``equivalent``
#: (the same content), ``weaker`` (implied by the old statement), ``covered`` (claims more
#: than the old statement, but only what the reviewed proof already shows), ``exceeds``
#: (claims more than the proof gives: a full blind pass)
REWORD_SCOPES = ("equivalent", "weaker", "covered", "exceeds")
REWORD_CARRIES = ("equivalent", "weaker", "covered")
#: a finding's class (VERDICT ``gap_class``): what it touches decides who repairs it
GAP_CLASSES = ("hypothesis", "statement", "proof", "wording")
RE_HYPOTHESIS = re.compile(r"(?i)hypothes|assum|\bstatement\b|STRENGTHEN_HYPOTHESIS|"
                           r"WEAKEN_CLAIM|OVERSTATED|falsifi|counterexample to the statement")
NONE_WORDS = ("", "none", "-", "n/a", "[]", "null")
#: a registry namespace: the only shape joined into a reviews path (``base_subject``)
RE_NS = re.compile(r"^[a-z0-9][a-z0-9-]*$")

OUTCOMES = ("awaiting-b", "confirmed", "confirmed-modulo", "disagreement", "disproved",
            "single-negative", "degraded", "invalid-pair", "no-change", "incomplete",
            "full-pass-needed", "invalid-base", "awaiting-amendment", "invalid-amend",
            "new-pass-after-amendment", "settle-dependencies")


# ----------------------------------------------------------------------------
# Statement hash
# ----------------------------------------------------------------------------

_CACHE = {}


def _engine_statement_hash_of():
    """``registry.core.model.statement_hash_of``, imported so this hash is always the
    engine's own -- the text ``py -m registry statement <ns:id>`` hashes -- rather than
    a reimplementation that could silently drift from it. Falls back to an identical
    local copy if the registry package cannot be found on this machine."""
    if "fn" not in _CACHE:
        try:
            plugin = os.path.join(ac.repo_root(), "academy")
            if plugin not in sys.path:
                sys.path.insert(0, plugin)
            from registry.core.model import statement_hash_of as fn
        except ImportError:
            def fn(text):
                norm = " ".join(str(text or "").split())
                return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
        _CACHE["fn"] = fn
    return _CACHE["fn"]


def statement_hash(text):
    """sha256 of the statement with all whitespace collapsed, first 16 hex digits --
    the same computation as ``py -m registry statement <ns:id>``, imported from the
    registry engine when it can be found (see ``_engine_statement_hash_of``)."""
    return _engine_statement_hash_of()(text)


# ----------------------------------------------------------------------------
# Parsing a verdict
# ----------------------------------------------------------------------------

RE_FIELD = re.compile(r"^\s*([A-Za-z_]+)\s*:\s*(.*?)\s*$")


def _split_list(v):
    if isinstance(v, list):
        items = _rejoin(v)
    else:
        s = str(v or "").strip()
        if s.lower() in NONE_WORDS:
            return []
        if s.startswith("[") and s.endswith("]"):     # a flow list [a, b], not a pinpoint "x [Thm 11]"
            s = s[1:-1]
        items = _split_top(s)
    out = []
    for it in items:
        it = str(it).strip().strip("`'\"")
        if it and it.lower() not in NONE_WORDS:
            out.append(it)
    return out


_OPEN, _CLOSE = "([{", ")]}"


def _split_top(s):
    """Split ``s`` on the commas and semicolons outside brackets (#103: a pointer
    ``lem:x (lifting, for covers)`` is one input, not two)."""
    out, depth, cur = [], 0, []
    for ch in str(s):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth = max(0, depth - 1)
        elif ch in ",;" and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    if depth:            # an unclosed bracket: no nesting to respect, split flat
        return re.split(r"[,;]", str(s))
    return out


def _rejoin(items):
    """A list landed before #103 was split inside brackets: put the pieces of one
    bracketed pointer back together (``['x (a', 'b)']`` -> ``['x (a, b)']``)."""
    out, cur, depth = [], None, 0
    for it in items:
        t = str(it)
        cur = t if cur is None else cur + ", " + t.strip()
        depth += sum(t.count(c) for c in _OPEN) - sum(t.count(c) for c in _CLOSE)
        if depth <= 0:
            out.append(cur)
            cur, depth = None, 0
    if cur is not None:  # an unclosed bracket: leave the list as it was landed
        return [str(it) for it in items]
    return out


def norm_verdict(v):
    """One of VERDICTS, or '' if ``v`` is not a verdict word.

    Accepts the word alone or followed by commentary (``CONFIRMED (on fable)``);
    the old six statuses are *not* accepted: a reviewer must use the four words.
    """
    s = " ".join(str(v or "").upper().replace("_", " ").split())
    for w in VERDICTS:
        if s == w or s.startswith(w + " ") or s.startswith(w + "(") or s.startswith(w + ","):
            return w
    return ""


def parse_verdict_block(text):
    """The fields of the last ``VERDICT`` block in ``text`` (a dict), or None.

    The block is a line reading ``VERDICT`` followed by ``key: value`` lines, up
    to a blank line, a code fence or the end. Keys are lower-cased.
    """
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().strip("`*#: ").upper() == "VERDICT":
            start = i
    if start is None:
        return None
    out = {}
    for ln in lines[start + 1:]:
        if not ln.strip() or ln.strip().startswith("```"):
            if out:
                break
            continue
        m = RE_FIELD.match(ln)
        if not m:
            break
        out[m.group(1).lower()] = m.group(2)
    return out or None


def parse_record(text):
    """A verdict record from a landed file (frontmatter) or a raw report (VERDICT block).

    Returns a dict with the FIELDS (``modulo`` a list, ``verdict`` normalised, ''
    when missing) plus ``problems`` (list of strings) and ``raw_verdict``.
    """
    fields = None
    if str(text or "").lstrip().startswith("---"):
        try:
            meta, _body = ac.read_frontmatter(text)
            fields = {k: meta.get(k) for k in FIELDS if k in meta}
        except ac.AcademyError:
            fields = None
    if fields is None or not fields.get("verdict"):
        block = parse_verdict_block(text)
        if block is not None:
            fields = dict(fields or {})
            fields.update(block)
    elif any(not fields.get(k) for k in ("gap_class",) + AMEND_FIELDS):
        # a landed record keeps the report (and its VERDICT block) as its body
        block = parse_verdict_block(text) or {}
        for k in ("gap_class",) + AMEND_FIELDS:
            if not fields.get(k) and block.get(k):
                fields[k] = block[k]
    rec = {k: "" for k in FIELDS}
    for k in LIST_FIELDS:
        rec[k] = []
    rec["problems"] = []
    if not fields:
        rec["problems"].append("no VERDICT block or verdict record found")
        rec["raw_verdict"] = ""
        return rec
    for k in FIELDS:
        v = fields.get(k)
        if k in LIST_FIELDS:
            rec[k] = _split_list(v)
        else:
            rec[k] = "" if v is None else str(v).strip()
    rec["raw_verdict"] = rec["verdict"]
    rec["verdict"] = norm_verdict(rec["verdict"])
    if not rec["verdict"]:
        rec["problems"].append("verdict %r is not one of %s"
                               % (rec["raw_verdict"], ", ".join(VERDICTS)))
    if rec["blocking"].lower() in NONE_WORDS:
        rec["blocking"] = ""
    gc = rec["gap_class"].strip().lower()
    rec["gap_class"] = gc if gc in GAP_CLASSES else ""
    rec["mode"] = rec["mode"].strip().lower()
    sc = rec["reword_scope"].strip().lower()
    rec["reword_scope"] = sc if sc in REWORD_SCOPES else ""
    return rec


def is_reword(rec):
    """True when ``rec`` is a reword run's record (``mode: reword``, T-0347)."""
    return bool(rec) and str(rec.get("mode") or "").strip().lower() == "reword"


def is_amend(rec):
    """True when ``rec`` is an amend run's record (``mode: amend``, 2026-11-20): run B
    reviewing the proof amended with the dependencies run A suggested."""
    return bool(rec) and str(rec.get("mode") or "").strip().lower() == "amend"


# ----------------------------------------------------------------------------
# Who repairs a finding (the role cut)
# ----------------------------------------------------------------------------

def gap_class(rec):
    """The class of a run's blocking finding: the VERDICT's ``gap_class`` when given,
    else ``hypothesis`` when the blocking step names a hypothesis, an assumption or the
    statement (or asks to strengthen a hypothesis / weaken the claim), else ``proof``.
    '' when the run names no blocking step. Unclassified is never read as wording: a
    wording finding must say so."""
    if not rec:
        return ""
    if rec.get("gap_class"):
        return rec["gap_class"]
    text = rec.get("blocking") or ""
    if not text:
        return ""
    return "hypothesis" if RE_HYPOTHESIS.search(text) else "proof"


def follow_up(item, subject="", producer_role="", rec=None):
    """The ticket a ``file_items`` entry becomes: ``{kind, to_role, final_to, gap_class,
    why}``. roster-rules.md "Role cut", rule 3: hypothesis-level findings, statement
    changes and missing arguments go to the Researcher as ``prove`` tickets with the
    falsifier; a counterexample goes to the human; a ``wording`` finding alone goes back
    to the statement's owner."""
    kind = item.get("kind")
    gc = item.get("gap_class") or gap_class(rec)
    if kind == "counterexample":
        return {"kind": "decision", "to_role": "human", "final_to": None, "gap_class": gc,
                "why": "a counterexample goes to the human at once"}
    if kind == "verify-input":
        return {"kind": "verify", "to_role": "expert", "final_to": None, "gap_class": gc,
                "why": "an input that is itself a proof to review"}
    if kind == "inputs":
        return {"kind": "decision", "to_role": "human", "final_to": None, "gap_class": gc,
                "why": "the runs disagree on the inputs: a ruling or a re-run"}
    if kind == "add-dependency":
        # 2026-11-20: the producer adds exactly these to the proof and its depends_on; the
        # verify ticket waits on it, and run B then reviews the amended proof (amend mode)
        return {"kind": "prove", "to_role": "researcher",
                "final_to": "scientist" if producer_role == "scientist" else None,
                "mode": "repair", "gap_class": "proof",
                "why": "a dependency the proof relies on but does not list: the producer "
                       "adds it to the proof and to depends_on (prove ticket, mode repair)"}
    if producer_role == "scientist":
        return {"kind": "question", "to_role": "researcher", "final_to": "scientist",
                "gap_class": gc, "why": "a lab claim: the Scientist repairs, through "
                                        "the Researcher (not a neighbour of the Expert)"}
    if gc == "wording":
        owner = producer_role or "author"
        return {"kind": "question", "to_role": owner, "final_to": None, "gap_class": gc,
                "why": "wording only: the statement's owner, in its next wording batch "
                       "(a pinned statement waits for the human's release)"}
    return {"kind": "prove", "to_role": "researcher", "final_to": None,
            "gap_class": gc or "proof",
            "why": "a %s finding: the Researcher repairs it (prove ticket with the "
                   "falsifier), never an Author apply or write ticket"
                   % (gc or "proof-step")}


# ----------------------------------------------------------------------------
# Which inputs are definitions (the definition rule, #103; T-0148 is replaced)
# ----------------------------------------------------------------------------

DEFINITION_KINDS = ("definition", "def", "defn")
RE_DEF_LABEL = re.compile(r"^(?:defn?:|DEF-)")


def registry_kind(qid):
    """The registry kind of ``qid`` (``ns:id``): the record's ``kind`` field, else its
    entity type; None when the registry engine, the namespace's home or the record
    cannot be found. Loaded through the engine (``registry.core.federation``), never by
    reading files."""
    ns, _, name = str(qid or "").partition(":")
    if not name or ns == "bib":
        return None
    try:
        plugin = os.path.join(ac.repo_root(), "academy")
        if plugin not in sys.path:
            sys.path.insert(0, plugin)
        from registry.core import federation, workspace as rws
        info = rws.namespaces().get(ns)
        home = info and info.get("home")
        if not home or not os.path.isdir(str(home)):
            return None
        rec = federation.store(ns, home).get(name)
    except Exception:        # an unreadable registry falls back to the label
        return None
    if rec is None:
        return None
    return str(rec.fields.get("kind") or rec.type or "").strip().lower() or None


def is_definition(qid, kind_of=None):
    """True when the input ``qid`` names a definition: by its registry kind when the
    registry knows it (``kind_of``, default ``registry_kind``), else by its label
    (``ns:defn:...``, ``ns:def:...``, ``ns:DEF-...``). A ``bib:`` input never is."""
    q = str(qid or "").strip()
    if not q or q.startswith("bib:"):
        return False
    kind = (kind_of or registry_kind)(q)
    if kind:
        return kind.lower() in DEFINITION_KINDS
    _ns, _, name = q.partition(":")
    return bool(RE_DEF_LABEL.match(name or q))


# The definition rule (the human's ruling of 2026-11-20 on #103, replacing T-0148's drop):
# a definition listed in a modulo stays an input, of both runs, unless it is marked
# notation-only on the registry record (a reviewer's own mark is not trusted). T-0148 dropped every definition one run
# listed, which turned a pair that differed on a definition the argument relies on into a
# wrong ``proved`` (T-1475, #103's third comment).

#: the reviewer's mark: the modulo entry ends with ``(notation only)`` (any case, a hyphen
#: or a space between the words)
RE_NOTATION_MARK = re.compile(r"(?i)\s*\(\s*notation[\s-]+only\s*\)\s*$")
#: the registry's mark: the definition record's ``tags`` include this tag
NOTATION_TAG = "notation-only"


def registry_tags(qid):
    """The ``tags`` of the record ``qid`` (``ns:id``), lower-cased; None when the registry,
    the home or the record cannot be found."""
    ns, _, name = str(qid or "").partition(":")
    if not name or ns == "bib":
        return None
    try:
        plugin = os.path.join(ac.repo_root(), "academy")
        if plugin not in sys.path:
            sys.path.insert(0, plugin)
        from registry.core import federation, workspace as rws
        info = rws.namespaces().get(ns)
        home = info and info.get("home")
        if not home or not os.path.isdir(str(home)):
            return None
        rec = federation.store(ns, home).get(name)
    except Exception:        # an unreadable registry marks nothing
        return None
    if rec is None:
        return None
    raw = (getattr(rec, "fields", None) or {}).get("tags") or []
    return [str(t).strip().lower() for t in ([raw] if isinstance(raw, str) else raw)]


def notation_only(item, kind_of=None, tags_of=None):
    """The definition id ``item`` names when it is marked notation-only, else None: the
    registry record's ``tags`` (``tags_of``, default ``registry_tags``) include
    ``notation-only``, and it is a definition (``is_definition``). A reviewer's
    ``(notation only)`` on the entry is read past, never trusted on its own. Anything
    else stays an input."""
    s = str(item or "").strip()
    head = RE_NOTATION_MARK.sub("", s)
    if not _bare_id(head):
        return None
    if not is_definition(head, kind_of):
        return None
    # the reviewer's own mark is not trusted (review of e9a0272: a run could mark a
    # definition the argument relies on): only the registry record's tag drops it
    tags = (tags_of or registry_tags)(head) or ()
    return head if NOTATION_TAG in [str(t).strip().lower() for t in tags] else None


def kept_definitions(items, kind_of=None):
    """``{entry as written: definition id}`` for every entry of ``items`` (modulo entries
    already past ``notation_only``) that names a definition (``is_definition``): the
    definition rule keeps it as an input of both runs, spelled without a reviewer's
    ``(notation only)`` mark, which is read past and never trusted. An entry with other
    pointer text is kept as written (the pointer can restrict the input)."""
    out = {}
    for item in items:
        s = str(item or "").strip()
        head = RE_NOTATION_MARK.sub("", s)
        if head and is_definition(head, kind_of):
            out[s] = head
    return out


# ----------------------------------------------------------------------------
# One spelling per input (#103): the runs' modulo lists are compared canonically
# ----------------------------------------------------------------------------

# the label prefixes of a paper's statements: ``lem:y`` written without its namespace
LABEL_PREFIXES = {"lem", "thm", "defn", "def", "cor", "prop", "fact", "rmk", "obs",
                  "ex", "claim", "conj", "eq", "sec", "nota", "assm", "hyp"}


def _registry_lookup(qid):
    """``(readable, record id or None)`` for ``qid`` (``ns:name``): ``readable`` is False
    when the registry, the home or the store cannot be read (the id is then unknown, not
    absent)."""
    ns, _, name = str(qid or "").partition(":")
    if not name or ns == "bib":
        return False, None
    try:
        plugin = os.path.join(ac.repo_root(), "academy")
        if plugin not in sys.path:
            sys.path.insert(0, plugin)
        from registry.core import federation, workspace as rws
        spaces = rws.namespaces()
        if spaces and ns not in spaces:
            # no registry namespace of the workspace (check:, tex:, uncited:): read, and no
            # record (#121: not shown to exist, never "may exist")
            return True, None
        info = spaces.get(ns)
        home = info and info.get("home")
        if not home or not os.path.isdir(str(home)):
            return False, None
        store = federation.store(ns, home)
        rid, exact = store.lookup(name)
        # only the id itself or a registered alias: a profile's normalisation (case,
        # a trailing sub-item letter: CRIT-3a -> CRIT-3) is not the same input
        if rid and not exact and name not in [str(a) for a in (store.aliases(rid) or ())]:
            rid = None
    except Exception:        # an unreadable registry leaves the spelling as written
        return False, None
    return True, ("%s:%s" % (ns, rid) if rid else None)


def registry_canonical(qid):
    """The record id ``qid`` (``ns:name``) resolves to in the registry, aliases
    included; None when the registry, the home or the record cannot be found."""
    return _registry_lookup(qid)[1]


def registry_exists(qid):
    """True / False: the registry (readable) has / lacks the record ``qid`` (False too for
    a namespace the workspace has none of: ``check:``, ``tex:``, ``uncited:``); None when
    it cannot be read. For a differing input None is "not shown to exist", like False
    (``input_facts``); only an add_dependency suggestion reads it as "may exist"."""
    readable, rid = _registry_lookup(qid)
    return (rid is not None) if readable else None


RE_DEP_ID = re.compile(r"^[a-z0-9][a-z0-9-]*:[^\s()\[\]{}<>,;#]+$")
RE_DEP_BIB = re.compile(r"^bib:[A-Za-z0-9][A-Za-z0-9_:.+/-]*$")
#: an open check mark (``[CHECK]``, ``[CHECK T-1144]``, any case): what it marks is not
#: verified, so it is never a dependency (#121, case 9)
RE_OPEN_CHECK = re.compile(r"(?i)\[\s*check\b")
#: one word of a pinpoint: a slug with a digit (``Thm2.6``, ``2-3``, ``Lem4.2-reading``),
#: a section sign, or a pinpoint word (``Assumption 3.2``, ``§2.3 Example``)
RE_PIN_TOKEN = re.compile(r"^(?:[\w.'+/:§-]*\d[\w.'+/:§-]*|§[\w.'+/:§-]*)$")
PIN_WORDS = {
    "thm", "thms", "theorem", "theorems", "lem", "lemma", "lemmas", "prop", "props",
    "proposition", "propositions", "cor", "corollary", "corollaries", "def", "defn",
    "definition", "definitions", "rmk", "rem", "remark", "remarks", "sec", "sect",
    "section", "sections", "item", "items", "p", "p.", "pp", "pp.", "page", "pages", "ex",
    "example", "examples", "exercise", "eq", "equation", "fig", "figure", "tab", "table",
    "claim", "step", "fact", "obs", "observation", "ch", "chapter", "app", "appendix",
    "assumption", "assumptions", "part", "case", "line", "lines", "para", "paragraph",
    "conj", "conjecture", "notation", "construction", "proof", "statement"}
RE_PIN_SLUG = re.compile(r"^[\w.'+/:§-]+$")


def has_open_check(item):
    """True when ``item`` carries an open check mark (``[CHECK ...]``)."""
    return bool(RE_OPEN_CHECK.search(str(item or "")))


def pinpoint_ok(pin):
    """True when ``pin`` (the text after ``#``) is a pinpoint, not free text: one slug
    with no brackets (``Thm2.6``, ``labelled-points``), or a few words each a pinpoint
    word or carrying a number (``Assumption 3.2``, ``§2.3 Example``, ``items 2-3``)."""
    words = str(pin or "").split()
    if not words:
        return False
    if len(words) == 1:
        return bool(RE_PIN_SLUG.match(words[0]))
    return all(RE_PIN_TOKEN.match(w) or w.lower() in PIN_WORDS for w in words)


def dependency_ok(item, exists=None):
    """True when ``item`` (in canonical spelling) names an existing result, as a suggested
    dependency must (2026-11-20 review): a registry id ``ns:id`` (known to the registry
    when ``exists``, qid -> True / False / None for unreadable, can tell) or a
    ``bib:KEY``, either with an optional ``#pinpoint`` (``pinpoint_ok``: a pinpoint, never
    free text after it). A statement in words, a bare unqualified id, a pointer phrase or
    anything carrying an open ``[CHECK ...]`` is not a dependency: a lemma that remains to
    be proved is a GAP (#121: the 93e5325 report)."""
    s = " ".join(str(item or "").split()).strip("`'\"")
    if has_open_check(s):
        return False
    head, hash_, pin = s.partition("#")
    if hash_ and not pinpoint_ok(pin):
        return False
    if head.startswith("bib:"):
        return bool(RE_DEP_BIB.match(head))
    if not RE_DEP_ID.match(head):
        return False
    if exists is not None and exists(head) is False:
        return False
    return True


def _check_deps(rec, exists, notes):
    """``rec`` with a suggestion that names no existing result made GAP-equivalent for
    the amend route: the verdict GAP, the blocking step the suggestion, no
    add_dependency (an anomaly in ``notes``)."""
    if not rec or rec.get("problems") or not rec.get("add_dependency"):
        return rec
    bad = [d for d in rec["add_dependency"] if not dependency_ok(d, exists)]
    if not bad:
        return rec
    out = dict(rec)
    out["add_dependency"] = []
    out["dependencies_not_results"] = bad
    notes.append("run %s suggests add_dependency %s, which is not an existing result (a "
                 "registry id ns:id, or bib:KEY[#pinpoint]): not a dependency; the run "
                 "counts as GAP for the amend route (a lemma that remains to be proved is "
                 "a GAP)" % (rec.get("run") or "?", ", ".join(bad)))
    if str(rec.get("verdict") or "").upper().startswith("CONFIRMED"):
        out["verdict_as_written"] = rec.get("verdict")
        out["verdict"] = "GAP"
        out["blocking"] = ("the proof relies on %s, which is not an existing result: it "
                           "remains to be proved" % "; ".join(bad))
    return out


def canon_input(item, subject="", canon=None):
    """One modulo input in its canonical spelling, never merging two different inputs:
    whitespace collapsed and quotes stripped; a ``#`` pinpoint's punctuation between a
    theorem-style word and its number removed (``#Thm-2.6`` -> ``#Thm2.6``); and, for a
    bare id only (no space or bracket before the ``#``), an unqualified paper label
    qualified (``lem:y`` -> ``paper:lem:y``: with the subject's namespace when that is
    an Author's, or when the registry knows the qualified id) and an alias resolved to
    its record id (``canon``, default ``registry_canonical``: exact ids and registered
    aliases only). Pointer text (``lem:y (first clause)``) is kept as written: it may
    restrict the input."""
    s = " ".join(str(item or "").split()).strip("`'\"")
    if not s:
        return s
    head, hash_, pin = s.partition("#")
    if hash_:
        pin = _norm_pinpoint(pin)
    if " " in head or any(c in head for c in _OPEN + _CLOSE) or head.startswith("bib:"):
        return head + hash_ + pin
    lookup = canon or registry_canonical
    sub_ns = str(subject or "").partition(":")[0]
    if ":" not in head:
        # a bare notebook id (OBS-3): qualified only when the registry knows it
        got = lookup("%s:%s" % (sub_ns, head)) if sub_ns else None
        return (got or head) + hash_ + pin
    if head.partition(":")[0].lower() in LABEL_PREFIXES:
        q = "%s:%s" % (sub_ns, head) if sub_ns else ""
        if not q or not (producer_role_for(subject) == "author" or lookup(q)):
            return head + hash_ + pin
        head = q
    got = lookup(head)
    return (got or head) + hash_ + pin


RE_PIN_GLUE = re.compile(
    r"(?i)(\b(?:thm|theorem|lem|lemma|prop|proposition|cor|corollary|defn?|definition|rmk|"
    r"rem|remark|sect?|section|item|pp?|ex|example|eq|fig|figure|tab|table|claim|step|"
    r"fact|obs|ch|chapter|app|appendix)|§)[\s.\-]+(?=\d)")


def _norm_pinpoint(pin):
    """A pinpoint without the punctuation between a word and its number:
    ``Thm-2.6``, ``Thm 2.6`` -> ``Thm2.6``; ``item-4`` -> ``item4``; ``p. 2`` -> ``p2``."""
    return RE_PIN_GLUE.sub(r"\1", pin.strip())


def normalise_modulo(items, subject="", canon=None):
    """``items`` in canonical spelling, duplicates dropped, order kept."""
    out = []
    for it in items or ():
        c = canon_input(it, subject, canon)
        if c and c not in out:
            out.append(c)
    return out


# ----------------------------------------------------------------------------
# Two CONFIRMED runs' differing inputs (#121): the mechanical part, through the registry
# ----------------------------------------------------------------------------

#: a card pinpoint as one mechanical input: ``bib:KEY`` or ``bib:KEY#PIN``, the pinpoint
#: with no pointer text (no space, no bracket) that could restrict it
RE_CARD = re.compile(r"^bib:([A-Za-z0-9][A-Za-z0-9_:.+/-]*)(?:#[^\s()\[\]{}]+)?$")
#: the most records one closure walks (a guard, never reached by a real registry)
CLOSURE_CAP = 5000


def registry_links(qid):
    """``{"depends_on": [qid...], "modulo": [qid...], "cites": [KEY...]}`` of the record
    ``qid`` (``ns:name``), read through the registry engine: its ``depends_on`` and
    ``modulo`` links qualified (with the record's namespace when they name none) and
    resolved to record ids, its ``cites`` bibkeys bare; None when the registry, the home
    or the record cannot be found."""
    ns, _, name = str(qid or "").partition(":")
    if not name or ns == "bib":
        return None
    try:
        plugin = os.path.join(ac.repo_root(), "academy")
        if plugin not in sys.path:
            sys.path.insert(0, plugin)
        from registry.core import federation, workspace as rws
        spaces = rws.namespaces()
        info = spaces.get(ns)
        home = info and info.get("home")
        if not home or not os.path.isdir(str(home)):
            return None
        rec = federation.store(ns, home).get(name)
    except Exception:        # an unreadable registry normalises nothing
        return None
    if rec is None:
        return None
    got = {"depends_on": [], "modulo": []}
    for rel, tgt in getattr(rec, "links", None) or ():
        t = str(tgt or "").strip()
        if rel not in got or not t:
            continue
        if t.partition(":")[0] not in spaces or not t.partition(":")[2]:
            t = "%s:%s" % (ns, t)
        t = registry_canonical(t) or t
        if t not in got[rel]:
            got[rel].append(t)
    cites = []
    raw = (getattr(rec, "fields", None) or {}).get("cites") or []
    for k in ([raw] if isinstance(raw, str) else raw):
        k = str(k).strip()
        k = (k[4:] if k.startswith("bib:") else k).partition("#")[0].strip()
        if k and k not in cites:
            cites.append(k)
    return {"depends_on": got["depends_on"], "modulo": got["modulo"], "cites": cites}


def is_declared(item, declared):
    """True when the proof declares ``item``: ``declared`` is the subject's
    ``registry_links``; an id (its ``#pinpoint`` or pointer text aside) in its
    ``depends_on`` or ``modulo``, a ``bib:KEY[#PIN]`` whose KEY it ``cites``."""
    if not declared:
        return False
    head = re.split(r"[\s#(\[{]", str(item or ""), maxsplit=1)[0]
    if head.startswith("bib:"):
        return head[4:] in (declared.get("cites") or ())
    return head in (declared.get("depends_on") or ()) or head in (declared.get("modulo") or ())


def _bare_id(item):
    """A registry id with no pinpoint and no pointer text (``ns:id``), not a ``bib:``."""
    s = str(item or "")
    return not s.startswith("bib:") and bool(RE_DEP_ID.match(s))


def _closure(qid, links_of, memo, stop=None):
    """``(ids, keys)``: every record ``qid`` reaches through its registry links, as
    ``{id: how}`` (``depends_on``, transitively; ``modulo`` once the path has crossed a
    ``modulo`` link: a carried modulo, #121 case 13), and every bibkey ``qid`` or one of
    those records ``cites``."""
    key = (qid, stop)
    if key in memo:
        return memo[key]
    ids, keys, todo, seen = {}, set(), [(qid, "depends_on")], {qid}
    while todo and len(seen) <= CLOSURE_CAP:
        node, how = todo.pop(0)
        got = links_of(node) or {}
        keys.update(got.get("cites") or ())
        for rel in ("depends_on", "modulo"):
            step = "modulo" if rel == "modulo" else how
            for d in got.get(rel) or ():
                ids.setdefault(d, step)
                if d not in seen and d != stop:      # never walk through the subject
                    seen.add(d)
                    todo.append((d, step))
    memo[key] = (ids, keys)
    return memo[key]


def reduce_differing(ma, mb, links_of=None, declared=None, subject=""):
    """The mechanical stage of two CONFIRMED runs' differing modulo lists (#121, stage 1):
    ``{dropped, differing, agreed}``. ``dropped``: ``[{"input", "via", "how", "case"}]``,
    an input only one run lists that ``via`` reaches through the registry (``links_of``):
    ``how`` ``modulo`` (``via`` carries it as a modulo, at any depth: case 13),
    ``depends_on`` (transitively) or ``cites`` (a card pinpoint ``bib:KEY[#PIN]`` whose
    KEY ``via`` or a record it reaches cites): case 4, granularity. ``via`` is a bare
    registry id both runs list, or one only the other run lists that the proof declares
    (``declared``, the subject's ``registry_links``: the more direct input); two inputs
    that reach each other drop neither. ``differing``: what is left for the
    dependency-settler, sorted. ``agreed``: what both runs list plus each declared input
    that covers the other run's (sorted). Without the registry nothing is dropped. The
    notation-only definitions are dropped and every other definition is put in both lists
    before this (``notation_only``, ``kept_definitions``): no definition differs here."""
    ma, mb = set(ma), set(mb)
    shared = ma & mb
    only_a, only_b = ma - mb, mb - ma
    dropped, memo = [], {}
    if links_of is not None:
        heads = sorted(y for y in shared if _bare_id(y))
        for x in sorted(only_a | only_b):
            if has_open_check(x):
                continue          # an open [CHECK] is held to case 9, never case 4
            other = only_b if x in only_a else only_a
            vias = heads + sorted(y for y in other if _bare_id(y) and is_declared(y, declared))
            card = RE_CARD.match(x)
            for y in vias:
                ids, keys = _closure(y, links_of, memo, subject or None)
                if subject and (y == subject or subject in ids):
                    continue      # a via that is circular through the subject drops nothing
                if _bare_id(x) and x in ids and y not in _closure(x, links_of, memo)[0]:
                    how = ids[x]
                    dropped.append({"input": x, "via": y, "how": how,
                                    "case": 13 if how == "modulo" else 4})
                    break
                if card and card.group(1) in keys:
                    dropped.append({"input": x, "via": y, "how": "cites", "case": 4})
                    break
    gone = {d["input"] for d in dropped}
    covering = {d["via"] for d in dropped} - shared - gone
    differing = sorted((only_a | only_b) - gone - covering)
    return {"dropped": dropped, "differing": differing, "agreed": sorted(shared | covering)}


def _result_head(item, subject="", canon=None):
    """``(head, pointer)``: the existing-result part of an input, in canonical spelling, and
    whether pointer text follows it. ``lem:y (first clause)`` under ``paper:lem:x`` ->
    ``("paper:lem:y", True)`` (a pointer restricts an existing result: its id is
    normalised, #103, before anything is looked up); ``bib:LMW16#§2.3 Example`` is whole
    (a pinpoint of words); free text gives ``("", False)``. The open-check mark is not
    looked at here (``has_open_check``)."""
    s = " ".join(str(item or "").split()).strip("`'\"")
    if dependency_ok(s):
        return s, False
    tok = re.split(r"\s|\(|\[", s, maxsplit=1)[0]
    if tok and tok != s and dependency_ok(tok):
        return canon_input(tok, subject, canon), True
    if ":" not in tok and tok and tok != s:
        # an unqualified paper label with pointer text (``lem:y`` has its colon; ``OBS-3``
        # with pointer text is qualified only when the registry knows it)
        got = canon_input(tok, subject, canon)
        if got != tok and dependency_ok(got):
            return got, True
    return "", False


def input_facts(item, run, subject="", exists=None, links_of=None, canon=None):
    """The admissibility facts of one differing input (#121), what the dependency-settler
    needs and cannot work out itself: ``{input, run, shape, result, pointer, open_check,
    exists, cycle}``.

    * ``open_check``: the input carries an open ``[CHECK ...]``; it never passes
      ``dependency_ok`` and is held to case 9 (``shape`` ``check`` whatever else it is).
    * ``result``: the existing result it names (``_result_head``: a registry id or a
      ``bib:`` card pinpoint, normalised, pointer text after it allowed, ``pointer`` then
      True), or ``""`` for free text (``shape`` ``text``).
    * ``exists`` (a registry id only): True when the registry (``exists``) shows the
      record; False when it does not show it: a record it lacks, a namespace the
      workspace has none of (``check:``, ``tex:``, ``uncited:``), or a registry that
      cannot be read (``shape`` ``unshown``). Never "may exist". None when the caller
      gave no registry check, and for a card (the library is not read here); False for
      free text.
    * ``cycle``: the result is the subject, or its registry links (``depends_on`` and
      ``modulo``, transitively) reach the subject: circular, case 11 (``shape``
      ``cycle``).
    ``shape`` is the first of ``check``, ``text``, ``card``, ``unshown``, ``cycle``,
    ``id`` that holds."""
    s = str(item or "")
    check = has_open_check(s)
    head, pointer = _result_head(s, subject, canon)
    rid = head.partition("#")[0]
    is_card = head.startswith("bib:")
    known = None
    if not head:
        known = False
    elif not is_card and exists is not None:
        known = exists(rid) is True
    cycle = bool(head) and not is_card and bool(subject) and (
        rid == subject or (links_of is not None
                           and subject in _closure(rid, links_of, {})[0]))
    if check:
        shape = "check"
    elif not head:
        shape = "text"
    elif is_card:
        shape = "card"
    elif known is False:
        shape = "unshown"
    elif cycle:
        shape = "cycle"
    else:
        shape = "id"
    return {"input": s, "run": run, "shape": shape, "result": head, "pointer": pointer,
            "open_check": check, "exists": known, "cycle": cycle}


def missing_verdict(path, a, b):
    """What to say when a verdict file is not there. It is nearly always one of two
    things (the ledger, five times in five weeks): the run has not ended, so the
    ``land_verdict`` hook has not filed its verdict yet, or the folder is not the pass
    folder (a path relative to another directory, a pass of another statement)."""
    run = "A" if path == a else "B" if path == b else "the base pass"
    folder = os.path.dirname(os.path.abspath(path)) if path else "?"
    there = sorted(os.listdir(folder)) if os.path.isdir(folder) else None
    if there is None:
        what = ("the folder %s does not exist: `reviews.py dir <id> <pass>` prints the pass "
                "folder (an absolute path), `reviews.py list <id>` the passes" % folder)
    else:
        what = ("the pass folder holds %s: the land_verdict hook files a run's verdict when "
                "the reviewer ends, so the run is still going, ended without a VERDICT "
                "block, or landed elsewhere (`reviews.py list <id>`)"
                % (", ".join(there) or "nothing yet"))
    return ("decision_table: run %s's verdict is not at %s; %s. Nothing to decide yet.\n"
            % (run, path, what))


def read_record(path):
    if path in (None, "", "-"):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        rec = parse_record(fh.read())
    rec["file"] = path
    return rec


# ----------------------------------------------------------------------------
# The table
# ----------------------------------------------------------------------------

#: the primaries when workspace.json sets no ``grading.primaryModels`` (docs/config.md)
PRIMARY_MODELS = ac.DEFAULT_PRIMARY_MODELS


def configured_primaries(workspace=None):
    """The grading primaries of the workspace (``grading.primaryModels``)."""
    return ac.primary_models(workspace)



def model_label(name):
    """A model name reduced to the label the roster rules use: ``fable``, ``opus-5.5``,
    or the family (``opus``, ``sonnet``, ``haiku``) of any other model; the name itself
    (lower-cased) when it names no known family, '' when empty.

    ``claude-opus-5-5``, ``claude-opus-5-5[1m]``, ``Opus 5.5`` and ``opus-5.5`` all
    read as ``opus-5.5``; a bare ``opus`` names no version and reads as ``opus``."""
    return ac.model_label(name)  # the one copy, academy_common (T-0350)


def _primaries(primary=None):
    if primary is None:
        primary = configured_primaries()
    if isinstance(primary, str):
        primary = [p for p in re.split(r"[,;]", primary) if p.strip()]
    return tuple(sorted({model_label(p) for p in primary if model_label(p)}))


def is_primary(model, primary=None):
    """True when ``model`` is one of the primaries (default: the configured ones)."""
    lab = model_label(model)
    return bool(lab) and lab in _primaries(primary)


def effective(rec, primary=None):
    """(verdict, note): CONFIRMED on a non-primary model reads as PLAUSIBLE."""
    v = rec["verdict"]
    if v == "CONFIRMED" and not is_primary(rec.get("model"), primary):
        return "PLAUSIBLE", ("run %s: CONFIRMED on %r, not a primary (%s): read as "
                             "PLAUSIBLE" % (rec.get("run") or "?", rec.get("model") or "an "
                                            "unnamed model", ", ".join(_primaries(primary))))
    return v, ""


def should_launch_b(rec_a, primary=None):
    """Run B is launched only after a positive run A (CONFIRMED on a primary)."""
    if not rec_a or rec_a["problems"]:
        return False
    return effective(rec_a, primary)[0] == "CONFIRMED"


GRADER_ROLE = "expert"    # every proof review here is run by an Expert instance


def producer_role_for(subject, override=None, workspace=None):
    """The role of the instance that produced the reviewed proof: the role that owns
    ``subject``'s namespace in workspace.json (``paper:`` -> ``author``, ``nb:`` ->
    ``researcher``, ``lab:`` -> ``scientist``). ``override`` (a CLI flag) always wins;
    '' when the namespace has no owning instance or workspace.json cannot be read."""
    if override:
        return override
    ns = str(subject or "").split(":", 1)[0].strip()
    if not ns:
        return ""
    try:
        ws = workspace if workspace is not None else ac.load_workspace()
    except ac.AcademyError:
        return ""
    for inst in ws.get("instances", {}).values():
        if inst.get("ns") == ns:
            return inst.get("role") or ""
    return ""


def researcher_for(subject, workspace, bears_on=(), parties=()):
    """``(instance, why)``: the Researcher a claim's falsifier request goes to (review V1
    #5), or ``("human", why)`` when the rule names none or several. In order: the
    Researcher instance owning ``subject``'s namespace; else the one Researcher instance
    owning the namespace of an id in the claim's ``bears_on``; else the one Researcher
    instance among ``parties`` (the verify ticket's and its parent chain's ``from`` and
    ``to``). A step naming several stops at the human: nobody guesses between them."""
    insts = (workspace or {}).get("instances", {}) or {}

    def researcher_of_ns(ns):
        return sorted(n for n, i in insts.items()
                      if i.get("ns") == ns and i.get("role") == "researcher")

    ns = str(subject or "").split(":", 1)[0].strip()
    own = researcher_of_ns(ns) if ns else []
    if len(own) == 1:
        return own[0], "the Researcher owning the namespace %s" % ns
    if len(own) > 1:
        return "human", ("several Researchers own the namespace %s (%s): the human decides"
                         % (ns, ", ".join(own)))
    steps = (
        ("bears_on", sorted({r for b in bears_on or ()
                             for r in researcher_of_ns(str(b).split(":", 1)[0].strip())
                             if ":" in str(b)})),
        ("the ticket's parent chain", sorted({str(p) for p in parties or ()
                                              if (insts.get(str(p)) or {}).get("role")
                                              == "researcher"})))
    for name, found in steps:
        if len(found) == 1:
            return found[0], "the one Researcher named by %s of %s" % (name, subject)
        if len(found) > 1:
            return "human", ("%s of %s names several Researchers (%s): the human decides"
                             % (name, subject, ", ".join(found)))
    return "human", ("no Researcher owns %s's namespace, and neither its bears_on nor the "
                     "ticket's parent chain names one: the human decides" % subject)


def _grounds(recs, modulo, note, producer_role=""):
    rows = [{"verdict": r["_eff"], "run_id": r.get("run_id") or "",
             "statement_hash": r.get("statement_hash") or "",
             "grader_role": GRADER_ROLE,
             "ref": r.get("file") or ""} for r in recs]
    g = {"basis": "proof", "verdicts": rows, "note": note}
    if producer_role:
        g["producer_role"] = producer_role
    hashes = {r.get("statement_hash") for r in recs if r.get("statement_hash")}
    if len(hashes) == 1:
        g["statement_hash"] = hashes.pop()
    if modulo:
        g["modulo"] = list(modulo)
    return g


def _canon_rec(rec, canon):
    if not rec or not any(rec.get(k) for k in LIST_FIELDS):
        return rec
    out = dict(rec)
    for k in LIST_FIELDS:
        if rec.get(k):
            out[k] = normalise_modulo(rec[k], rec.get("subject"), canon)
    if out.get("modulo") != list(rec.get("modulo") or []):
        out["modulo_as_written"] = list(rec["modulo"])
    return out


def decide(rec_a, rec_b=None, established=(), primary=None, producer_role=None,
           kind_of=None, base=None, base_notes=(), canon=None, exists=None, links_of=None,
           tags_of=None):
    """Apply the table (``_decide``) and give every item to file its ``route``
    (``follow_up``). ``kind_of`` (qid -> registry kind or None) replaces the registry
    lookup that decides which inputs are definitions, ``tags_of`` (qid -> the record's
    tags or None) the one that reads a definition's ``notation-only`` tag.

    A reword run's record as ``rec_a`` goes to :func:`decide_reword`, with ``base`` the
    base pass's ``(A, B)`` records (``base_records`` finds them) and ``base_notes`` what
    finding them turned up.

    Every modulo list (and ``established``) is first put in canonical spelling
    (``normalise_modulo``, #103), so two runs that name one input two ways agree;
    ``canon`` (qid -> record id or None) replaces the registry's alias lookup.

    A suggested dependency (``add_dependency``) must name an existing result
    (``dependency_ok``; ``exists``, qid -> True / False / None, checks a registry id: the
    CLI passes ``registry_exists``); a run whose suggestion does not is GAP-equivalent
    for the amend route, with an anomaly.

    ``links_of`` (qid -> ``{depends_on, modulo, cites}`` or None; the CLI passes
    ``registry_links``) is the registry's reach for two CONFIRMED runs' differing inputs
    (#121): ``reduce_differing`` drops what it shows mechanically, and ``input_facts``
    gives what is left its admissibility facts (``exists`` reads existence there, and a
    None from it is "not shown"); without it nothing is dropped."""
    rec_a = _canon_rec(rec_a, canon)
    rec_b = _canon_rec(rec_b, canon)
    dep_notes = []
    rec_a = _check_deps(rec_a, exists, dep_notes)
    rec_b = _check_deps(rec_b, exists, dep_notes)
    res = _decide_canon(rec_a, rec_b, established, primary, producer_role, kind_of, base,
                        base_notes, canon, links_of, exists, tags_of)
    res["anomalies"] = dep_notes + list(res.get("anomalies") or [])
    return res


def _decide_canon(rec_a, rec_b, established, primary, producer_role, kind_of, base,
                  base_notes, canon, links_of=None, exists=None, tags_of=None):
    if base:
        base = tuple(_canon_rec(r, canon) for r in base)
    subj = (rec_a or {}).get("subject") or ""
    established = normalise_modulo(established, subj, canon)
    if is_reword(rec_a):
        ba, bb = tuple(base or (None, None))[:2]
        notes = list(base_notes)
        if rec_b is not None:
            notes.append("a second record was given with a reword run: ignored (a reword "
                         "pass has one run, R)")
        return decide_reword(rec_a, ba, bb, established, primary, producer_role, kind_of,
                             notes)
    if is_amend(rec_b) or is_amend(rec_a) or _suggests(rec_a, primary) \
            or _suggests(rec_b, primary):
        res = decide_amend(rec_a, rec_b, established, primary, producer_role, kind_of)
        _route_items(res, rec_a, rec_b, producer_role)
        return res
    res = _decide(rec_a, rec_b, established, primary, producer_role, kind_of, links_of,
                  exists, canon, tags_of)
    for r in (rec_a, rec_b):
        if r and r.get("add_dependency"):
            res["anomalies"].append("run %s suggests add_dependency %s on a %s verdict: "
                                    "ignored (a dependency is suggested only with CONFIRMED)"
                                    % (r.get("run") or "?", ", ".join(r["add_dependency"]),
                                       r.get("verdict") or "missing"))
    _route_items(res, rec_a, rec_b, producer_role)
    return res


def _suggests(rec, primary=None):
    """A readable CONFIRMED (on a primary) that suggests dependencies to add."""
    return bool(rec) and not rec["problems"] and bool(rec.get("add_dependency")) \
        and effective(rec, primary)[0] == "CONFIRMED"


def _route_items(res, rec_a, rec_b, producer_role):
    if res.get("file_items"):
        subject = (rec_a or {}).get("subject") or ""
        prod = producer_role_for(subject, producer_role)
        by_run = {str(r.get("run") or "").upper(): r for r in (rec_a, rec_b) if r}
        for it in res["file_items"]:
            run = str(it.get("run") or "")
            rec = by_run.get(run.upper()[:1]) if len(run) == 1 else None
            if rec is None and it.get("kind") == "repair":
                rec = next((r for r in (rec_b, rec_a) if r and r.get("blocking")), None)
            it["gap_class"] = gap_class(rec) if it.get("kind") == "repair" else ""
            it["route"] = follow_up(it, subject, prod, rec)
    return res


def _new_result():
    return {"outcome": "", "launch_b": False, "proposed_status": None, "recolour": False,
            "needs_human": False, "modulo": [], "pending_inputs": [], "file_items": [],
            "anomalies": [], "grounds": None, "summary": "", "runs": [],
            "dropped_definitions": [], "kept_definitions": [], "modulo_options": []}


def _decide(rec_a, rec_b=None, established=(), primary=None, producer_role=None,
            kind_of=None, links_of=None, exists=None, canon=None, tags_of=None):
    """Apply the table. ``rec_a`` / ``rec_b`` come from ``parse_record``; ``rec_b``
    may be None (not launched). ``established`` lists the modulo inputs known to be
    established (registry ``proved`` or a verified citation card). ``producer_role``
    overrides the namespace-owner lookup (``producer_role_for``) when given."""
    res = _new_result()
    established = set(established or ())

    if rec_a is None or rec_a["problems"]:
        res["outcome"] = "incomplete"
        res["summary"] = "run A has no readable verdict: nothing to conclude"
        if rec_a:
            res["anomalies"].extend("run A: " + p for p in rec_a["problems"])
        return res

    rw = [r for r in (rec_a, rec_b) if is_reword(r)]
    if rw:
        res["outcome"] = "invalid-pair"
        res["anomalies"].extend("run %s is a reword run (mode: reword): it is not blind and "
                                "is never half of a blind pair" % (r.get("run") or "?")
                                for r in rw)
        res["summary"] = "the two runs are not two blind reviews of one statement"
        return res

    prod_role = producer_role_for(rec_a.get("subject"), producer_role)

    recs = [rec_a] + ([rec_b] if rec_b is not None else [])
    for r in recs:
        eff, note = effective(r, primary)
        r["_eff"] = eff
        if note:
            res["anomalies"].append(note)
    if rec_b is not None and rec_b["problems"]:
        res["anomalies"].extend("run B: " + p for p in rec_b["problems"])
    for r in recs:
        res["runs"].append({k: r.get(k) for k in ("run", "run_id", "verdict", "model",
                                                   "modulo", "statement_hash", "blocking",
                                                   "file")})
        if r.get("modulo_as_written"):
            res["runs"][-1]["modulo_as_written"] = r["modulo_as_written"]
        res["runs"][-1]["effective"] = r["_eff"]

    a = rec_a["_eff"]
    b = rec_b["_eff"] if rec_b is not None and not rec_b["problems"] else None

    if rec_b is not None and a != "CONFIRMED":
        res["anomalies"].append("run B was launched after a non-positive run A (%s); "
                                "the outcome is taken from A alone" % a)
        b = None
        recs = [rec_a]

    # DISPROVED dominates.
    if a == "DISPROVED" or b == "DISPROVED":
        res["outcome"] = "disproved"
        res["needs_human"] = True
        who = [r for r in recs if r["_eff"] == "DISPROVED"]
        res["file_items"] = [{"run": r.get("run"), "kind": "counterexample",
                              "text": r.get("blocking") or "see the run's report"}
                             for r in who]
        if len(recs) == 2 and a == b == "DISPROVED" and _pair_ok(rec_a, rec_b, res):
            res["proposed_status"] = "refuted"
            res["grounds"] = _grounds(recs, [], "two DISPROVED verdicts", prod_role)
            res["summary"] = "both runs DISPROVED: propose refuted"
        else:
            res["summary"] = ("DISPROVED by run %s: no status change; the counterexample "
                              "goes to %s at once"
                              % (", ".join(r.get("run") or "?" for r in who),
                                 ac.human_name()))
        return res

    if b is None:
        if a == "CONFIRMED":
            if rec_b is not None:        # B present but unreadable
                res["outcome"] = "incomplete"
                res["summary"] = "run B has no readable verdict: conclude nothing yet"
                return res
            res["outcome"] = "awaiting-b"
            res["launch_b"] = True
            res["summary"] = "A is CONFIRMED: launch run B with the identical brief"
            return res
        if a == "PLAUSIBLE":
            res["outcome"] = "degraded"
            res["summary"] = ("A is PLAUSIBLE (fallback or reduced strength): it never "
                              "counts; re-run A on a primary model (%s)"
                              % ", ".join(_primaries(primary)))
            return res
        res["outcome"] = "single-negative"
        res["file_items"] = [{"run": rec_a.get("run") or "A", "kind": "repair",
                              "text": rec_a.get("blocking") or "see run A's report"}]
        res["summary"] = "A is GAP: no status change; file A's blocking step; B skipped by design"
        return res

    if "PLAUSIBLE" in (a, b):
        res["outcome"] = "degraded"
        res["summary"] = ("a PLAUSIBLE verdict never counts toward two agreeing verdicts: "
                          "re-run the PLAUSIBLE run on a primary model (%s)"
                          % ", ".join(_primaries(primary)))
        return res

    if a == b == "CONFIRMED":
        if not _pair_ok(rec_a, rec_b, res):
            res["outcome"] = "invalid-pair"
            res["summary"] = "the two runs are not independent reviews of one statement"
            return res
        # the definition rule (the human's ruling of 2026-11-20, #103): a definition either
        # run lists is an input of both, unless its registry record is tagged notation-only
        defs = sorted({h for h in (notation_only(i, kind_of, tags_of)
                                   for i in rec_a["modulo"] + rec_b["modulo"]) if h})
        res["dropped_definitions"] = defs
        la = [i for i in rec_a["modulo"] if not notation_only(i, kind_of, tags_of)]
        lb = [i for i in rec_b["modulo"] if not notation_only(i, kind_of, tags_of)]
        kept = kept_definitions(la + lb, kind_of)
        res["kept_definitions"] = sorted(set(kept.values()))
        ma = {kept.get(i, i) for i in la} | set(kept.values())
        mb = {kept.get(i, i) for i in lb} | set(kept.values())
        dnote = ("; notation-only definitions dropped from the modulo lists (not inputs, "
                 "the definition rule, #103): %s" % ", ".join(defs)) if defs else ""
        if res["kept_definitions"]:
            dnote += ("; definitions kept as inputs of both runs (no notation-only tag on "
                      "their records, the definition rule, #103): %s"
                      % ", ".join(res["kept_definitions"]))
        if ma != mb and not (rec_a.get("blocking") or rec_b.get("blocking")):
            subject = rec_a.get("subject") or ""
            declared = links_of(subject) if links_of is not None and subject else None
            red = reduce_differing(ma, mb, links_of, declared, subject)
            res["modulo_lists"] = {"A": list(rec_a["modulo"]), "B": list(rec_b["modulo"])}
            res["dropped_inputs"] = red["dropped"]
            if red["differing"]:
                _settle_dependencies(res, red, ma, subject, exists, links_of, canon, dnote)
                # the grounds settle_deps.py completes (modulo, note) once the record is
                # applied: the concluder proposes with grounds made in code (#121 part 3)
                res["grounds_template"] = _grounds(recs, [], "", prod_role)
                return res
            ma = mb = set(red["agreed"])
            dnote += ("; the runs' lists (A %s, B %s) differ only mechanically (#121, stage "
                      "1), dropped: %s" % (
                          ", ".join(rec_a["modulo"]) or "none",
                          ", ".join(rec_b["modulo"]) or "none",
                          ", ".join("%s (reached through %s, registry %s, case %d)"
                                    % (d["input"], d["via"], d["how"], d["case"])
                                    for d in red["dropped"])))
        if ma != mb:
            res["outcome"] = "disagreement"
            res["modulo"] = sorted(ma | mb)
            res["file_items"] = [{"run": "A+B", "kind": "inputs",
                                  "text": "the runs name different inputs: A %s, B %s "
                                          "(differing: %s)"
                                          % (sorted(ma) or "none", sorted(mb) or "none",
                                             ", ".join(sorted(ma ^ mb)))}]
            # the ruling's two real options (#103)
            res["modulo_options"] = [
                {"label": "union", "modulo": sorted(ma | mb),
                 "means": "proved-modulo every input either run named"},
                {"label": "intersection", "modulo": sorted(ma & mb),
                 "means": "proved-modulo only the inputs both runs named"}]
            res["summary"] = ("both CONFIRMED but on different inputs (%s), with a blocking "
                              "step named: no status change; the ruling is union or "
                              "intersection" % ", ".join(sorted(ma ^ mb)))
            return res
        if not ma:
            res["outcome"] = "confirmed"
            res["proposed_status"] = "proved"
            res["recolour"] = True
            res["grounds"] = _grounds(recs, [], "two CONFIRMED verdicts, no open inputs"
                                      + dnote, prod_role)
            res["summary"] = "CONFIRMED x2: propose proved; recolour earned" + dnote
            return res
        res["outcome"] = "confirmed-modulo"
        res["modulo"] = sorted(ma)
        res["pending_inputs"] = sorted(ma - established)
        res["proposed_status"] = "proved-modulo"
        res["recolour"] = not res["pending_inputs"]
        res["grounds"] = _grounds(recs, sorted(ma), "two CONFIRMED verdicts modulo %s"
                                  % ", ".join(sorted(ma)) + dnote, prod_role)
        res["file_items"] = [{"run": "A+B", "kind": "verify-input", "text": i}
                             for i in res["pending_inputs"]]
        res["summary"] = ("CONFIRMED x2 modulo %s: propose proved-modulo; %s"
                          % (", ".join(sorted(ma)),
                             "recolour earned (every input established)" if res["recolour"]
                             else "stays sketch until %s are established"
                             % ", ".join(res["pending_inputs"])) + dnote)
        return res

    if a == "CONFIRMED" and b == "GAP":
        res["outcome"] = "disagreement"
        res["file_items"] = [{"run": rec_b.get("run") or "B", "kind": "repair",
                              "text": rec_b.get("blocking") or "see run B's report"}]
        res["summary"] = ("A CONFIRMED, B GAP: no status change; relay both reports and "
                          "file B's blocking step")
        return res

    res["outcome"] = "no-change"
    res["file_items"] = [{"run": r.get("run"), "kind": "repair", "text": r.get("blocking")}
                         for r in recs if r.get("blocking")]
    res["summary"] = "no status change; report the union of the findings"
    return res


def _settle_dependencies(res, red, ma, subject, exists, links_of, canon, dnote=""):
    """#121: two CONFIRMED runs, no blocking step, whose modulo lists still differ after
    the mechanical reduction (``red``, from ``reduce_differing``): ``res`` filled as
    ``settle-dependencies``. No status and no ticket: the dependency-settler classifies
    each differing input. ``modulo`` is what the runs agree on; ``differing_inputs`` each
    differing input with its run and its admissibility facts (``input_facts``); both
    runs' lists stay in ``modulo_lists``."""
    res["outcome"] = "settle-dependencies"
    res["modulo"] = list(red["agreed"])
    res["differing_inputs"] = [input_facts(x, "A" if x in ma else "B", subject, exists,
                                           links_of, canon) for x in red["differing"]]
    lists = res.get("modulo_lists") or {}
    gone = ("; dropped mechanically: %s" % ", ".join(
        "%s (reached through %s, case %d)" % (d["input"], d["via"], d["case"])
        for d in red["dropped"])) if red["dropped"] else ""
    res["summary"] = (
        "CONFIRMED x2 on differing modulo lists (A %s, B %s): after the mechanical "
        "reduction (#121, stage 1) %s still differ%s: no status yet; the "
        "dependency-settler classifies each differing input%s%s"
        % (", ".join(lists.get("A") or []) or "none",
           ", ".join(lists.get("B") or []) or "none",
           ", ".join("%s (run %s, %s)" % (d["input"], d["run"], d["shape"])
                     for d in res["differing_inputs"]),
           "s" if len(res["differing_inputs"]) == 1 else "", gone, dnote))
    return res


# ----------------------------------------------------------------------------
# The reword pass (T-0347, the human's decision of 2026-10-12): one informed run on a reworded statement
# ----------------------------------------------------------------------------

def slug_id(cid):
    """A registry id as one path segment (``_expert.slug_id``, repeated here so the
    table needs only ``_academy``): ``lem:strip-bound`` -> ``lem-strip-bound``."""
    s = "".join(c if (c.isalnum() or c in "-_.") else "-" for c in str(cid))
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-.") or "item"


def base_records(r_path, base_pass, base_dir=None, base_subject=None):
    """``(A, B, notes)``: the base pass's run records for the reword record at
    ``r_path``. The base pass is the sibling folder ``base_pass`` of the reword pass
    (``<subject dir>/<base_pass>/``), or, when the reword run names ``base_subject``
    (T-0476, a renamed record), ``<reviews>/<ns>/<dir of base_subject>/<base_pass>/``
    beside the reword pass's own subject folder; ``base_dir`` overrides both. An
    abandoned base pass, or a missing folder or run, gives None in its place and a note
    saying why."""
    if not base_dir and not base_pass:
        return None, None, ["the reword run names no base_pass: its base is missing"]
    if base_dir:
        d = base_dir
    elif base_subject:
        ns, _, cid = str(base_subject).strip().partition(":")
        if not RE_NS.match(ns) or not cid:
            return None, None, ["base_subject %r is not a namespaced id (ns:id)"
                                % base_subject]
        # <reviews>/<ns>/<subject dir>/<pass>/R.md -> <reviews>
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(r_path)))))
        d = os.path.join(root, ns, slug_id(cid), base_pass)
    else:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(r_path))),
                         base_pass)
    shown = d.replace("\\", "/")
    if not os.path.isdir(d):
        return None, None, ["the base pass folder %s is missing" % shown]
    if os.path.isfile(os.path.join(d, "abandoned.md")):
        return None, None, ["the base pass %s was abandoned, so its decision is missing"
                            % shown]
    notes = []
    if not os.path.isfile(os.path.join(d, "decision.md")):
        notes.append("the base pass %s has no decision.md: its table is recomputed from "
                      "its runs" % shown)
    recs = []
    for run in ("A", "B"):
        p = os.path.join(d, run + ".md")
        recs.append(read_record(p) if os.path.isfile(p) else None)
    return recs[0], recs[1], notes


def _base_problems(rec_r, base_a, base_b):
    """Why the base records cannot carry the reword run (a list of anomalies)."""
    if base_a is None or base_b is None or base_a["problems"] or base_b["problems"]:
        return ["the base pass %s is missing or unreadable (its runs A and B)"
                % (rec_r.get("base_pass") or "?")]
    probs = []
    for b in (base_a, base_b):
        if is_reword(b):
            probs.append("the base run %s is a reword record: a base pass must be a blind "
                         "pair" % (b.get("run") or "?"))
    if probs:
        return probs
    bh, new = rec_r.get("base_hash") or "", rec_r.get("statement_hash") or ""
    if not bh:
        probs.append("the reword run names no base_hash")
    for b in (base_a, base_b):
        if bh and (b.get("statement_hash") or "") != bh:
            probs.append("base_hash %s is not the base run %s's statement_hash %s"
                         % (bh, b.get("run") or "?", b.get("statement_hash") or "(none)"))
    if not new:
        probs.append("the reword run has no statement_hash")
    elif bh and new == bh:
        probs.append("the statement did not change (statement_hash = base_hash): the base "
                     "pass's own decision applies, not a reword")
    subj, bsubj = rec_r.get("subject"), rec_r.get("base_subject") or ""
    for b in (base_a, base_b):
        if bsubj and b.get("subject") != bsubj:
            probs.append("the base pass reviewed subject %s, not the reword run's "
                         "base_subject %s" % (b.get("subject") or "(none)", bsubj))
            break
        if not bsubj and subj and b.get("subject") and b["subject"] != subj:
            probs.append("the base pass reviewed subject %s, the reword run %s (a base "
                         "pass of a superseded id needs base_subject)"
                         % (b["subject"], subj))
            break
    for b in (base_a, base_b):
        bp = b.get("pass") or ""
        if bp and rec_r.get("base_pass") and bp != rec_r["base_pass"]:
            probs.append("the base run %s belongs to pass %s, not base_pass %s"
                         % (b.get("run") or "?", bp, rec_r["base_pass"]))
    rid = rec_r.get("run_id") or ""
    if not rid or rid in (base_a.get("run_id"), base_b.get("run_id")):
        probs.append("the reword run's run id %s is not distinct from the base runs'"
                     % (rid or "(none)"))
    return probs


def _reword_grounds(rec_r, base_recs, modulo, note, prod_role):
    g = _grounds([rec_r] + list(base_recs), modulo, note, prod_role)
    g["verdicts"][0].update({"mode": "reword", "base_hash": rec_r.get("base_hash") or "",
                             "reword_scope": rec_r.get("reword_scope") or ""})
    g.update({"mode": "reword", "base_pass": rec_r.get("base_pass") or "",
              "base_hash": rec_r.get("base_hash") or "",
              "statement_hash": rec_r.get("statement_hash") or ""})
    bsubj = rec_r.get("base_subject") or ""
    if bsubj:
        g["base_subject"] = bsubj
        for row in g["verdicts"]:
            row["base_subject"] = bsubj
    return g


def decide_reword(rec_r, base_a=None, base_b=None, established=(), primary=None,
                  producer_role=None, kind_of=None, base_notes=()):
    """The reword table (T-0347). ``rec_r`` is the reword run's record (``mode:
    reword``); ``base_a`` / ``base_b`` the base pass's runs, both CONFIRMED on
    ``base_hash`` for the reword to carry anything.

    | Reword run R | Base pass | Outcome |
    |---|---|---|
    | DISPROVED | any | ``disproved``: the counterexample to the new wording goes to the human |
    | PLAUSIBLE (or CONFIRMED on a non-primary) | any | ``degraded``: re-run R on a primary |
    | GAP, or CONFIRMED with ``reword_scope: exceeds`` | any | ``full-pass-needed``: no status; open a fresh blind pass (run A) on the new statement |
    | CONFIRMED with no ``reword_scope`` | any | ``incomplete``: relaunch R |
    | CONFIRMED, scope equivalent / weaker / covered | missing, abandoned, not CONFIRMED x2, other hash / subject / pass, shared run id, or an unchanged statement | ``invalid-base``: no status |
    | CONFIRMED, scope equivalent / weaker / covered | CONFIRMED x2 on base_hash (modulo X) | ``confirmed`` / ``confirmed-modulo`` on X plus R's modulo: propose proved / proved-modulo; recolour as the normal table |
    """
    res = _new_result()
    res.update({"mode": "reword", "launch_full_pass": False, "base_outcome": None,
                "base_pass": (rec_r or {}).get("base_pass") or "",
                "base_hash": (rec_r or {}).get("base_hash") or "",
                "base_subject": (rec_r or {}).get("base_subject") or "",
                "reword_finding": ""})
    res["anomalies"].extend(base_notes or ())
    established = set(established or ())
    if rec_r is None or rec_r["problems"]:
        res["outcome"] = "incomplete"
        res["summary"] = "the reword run has no readable verdict: nothing to conclude"
        if rec_r:
            res["anomalies"].extend("run R: " + p for p in rec_r["problems"])
        return res
    prod_role = producer_role_for(rec_r.get("subject"), producer_role)
    eff, note = effective(rec_r, primary)
    rec_r["_eff"] = eff
    if note:
        res["anomalies"].append(note)
    row = {k: rec_r.get(k) for k in ("run", "run_id", "verdict", "model", "modulo",
                                     "statement_hash", "blocking", "file", "base_hash",
                                     "reword_scope", "base_subject")}
    row["effective"] = eff
    res["runs"].append(row)
    scope = rec_r.get("reword_scope") or ""

    if eff == "DISPROVED":
        res["outcome"] = "disproved"
        res["needs_human"] = True
        res["file_items"] = [{"run": rec_r.get("run") or "R", "kind": "counterexample",
                              "text": rec_r.get("blocking") or "see the reword run's report"}]
        res["summary"] = ("the reword run DISPROVED the new wording: no status change; the "
                          "counterexample goes to %s at once" % ac.human_name())
        _route_items(res, rec_r, None, producer_role)
        return res
    if eff == "PLAUSIBLE":
        res["outcome"] = "degraded"
        res["summary"] = ("the reword run is PLAUSIBLE (fallback or reduced strength): it "
                          "never counts; re-run it on a primary model (%s)"
                          % ", ".join(_primaries(primary)))
        return res
    if eff == "GAP" or scope == "exceeds":
        res["outcome"] = "full-pass-needed"
        res["launch_full_pass"] = True
        res["reword_finding"] = rec_r.get("blocking") or ""
        res["summary"] = ("the reword run finds the new wording %s (%s): no status change; "
                          "open a fresh blind pass (run A) on the new statement"
                          % ("claims more than the proof as reviewed gives"
                             if scope == "exceeds" else "not covered by the proof as "
                             "reviewed", res["reword_finding"] or "see its report"))
        return res
    if scope not in REWORD_CARRIES:
        res["outcome"] = "incomplete"
        res["anomalies"].append("the reword run is CONFIRMED but gives no reword_scope (%s): "
                                "relaunch it" % ", ".join(REWORD_SCOPES))
        res["summary"] = "the reword run gives no reword_scope: relaunch it"
        return res

    bad = _base_problems(rec_r, base_a, base_b)
    base_res = None
    if not bad:
        base_res = _decide(base_a, base_b, established, primary, producer_role, kind_of)
        res["base_outcome"] = base_res["outcome"]
        res["anomalies"].extend("base pass: " + a for a in base_res["anomalies"])
        if base_res["outcome"] not in ("confirmed", "confirmed-modulo"):
            bad.append("the base pass %s is not confirmed (its table gives %s)"
                       % (rec_r.get("base_pass") or "?", base_res["outcome"]))
    if bad:
        res["outcome"] = "invalid-base"
        res["anomalies"].extend(bad)
        res["summary"] = ("no status change: the base pass does not carry a CONFIRMED x2 "
                          "decision on base_hash for this reword run; fix the base in the "
                          "brief, or open a fresh blind pass")
        return res

    res["dropped_definitions"] = base_res.get("dropped_definitions") or []
    res["kept_definitions"] = base_res.get("kept_definitions") or []
    mod = sorted(set(base_res["modulo"]) | set(rec_r["modulo"]))
    base_recs = [base_a, base_b]
    how = ("reword run CONFIRMED (%s) on base pass %s%s, CONFIRMED x2 on %s"
           % (scope, rec_r.get("base_pass"),
              (" of %s" % rec_r["base_subject"]) if rec_r.get("base_subject") else "",
              rec_r.get("base_hash")))
    if not mod:
        res["outcome"] = "confirmed"
        res["proposed_status"] = "proved"
        res["recolour"] = True
        res["grounds"] = _reword_grounds(rec_r, base_recs, [], how + ", no open inputs",
                                         prod_role)
        res["summary"] = "%s: propose proved; recolour earned" % how
        return res
    res["outcome"] = "confirmed-modulo"
    res["modulo"] = mod
    res["pending_inputs"] = sorted(set(mod) - established)
    res["proposed_status"] = "proved-modulo"
    res["recolour"] = not res["pending_inputs"]
    res["grounds"] = _reword_grounds(rec_r, base_recs, mod, "%s, modulo %s"
                                     % (how, ", ".join(mod)), prod_role)
    res["file_items"] = [{"run": "R", "kind": "verify-input", "text": i}
                         for i in res["pending_inputs"]]
    res["summary"] = ("%s, modulo %s: propose proved-modulo; %s"
                      % (how, ", ".join(mod), "recolour earned (every input established)"
                         if res["recolour"] else "stays sketch until %s are established"
                         % ", ".join(res["pending_inputs"])))
    _route_items(res, rec_r, None, producer_role)
    return res


# ----------------------------------------------------------------------------
# The dependency amendment (the human's design, 2026-11-20): A CONFIRMED with a suggested
# dependency, the producer adds it, B reviews the amended proof informed of the suggestion
# ----------------------------------------------------------------------------

def _amend_problems(rec_a, rec_b):
    """Why ``rec_b`` is not an amend run of ``rec_a``'s suggestion (a list of anomalies)."""
    probs = []
    if is_amend(rec_a):
        probs.append("run A is an amend record: an amend run is only ever run B")
    if not rec_a.get("add_dependency"):
        probs.append("run A suggested nothing (no add_dependency): an amend B has no base; "
                     "the blind pair applies")
        return probs
    if not is_amend(rec_b):
        probs.append("run A suggested dependencies %s, but run B is not an amend run "
                     "(mode: amend) of the amended proof: a blind B on the unamended proof "
                     "is not the second verdict" % ", ".join(rec_a["add_dependency"]))
        return probs
    pa = rec_a.get("pass") or ""
    if (rec_b.get("base_pass") or "") != pa or (rec_b.get("pass") or "") != pa:
        probs.append("the amend run's base_pass %s (pass %s) is not run A's pass %s"
                     % (rec_b.get("base_pass") or "(none)", rec_b.get("pass") or "(none)",
                        pa or "(none)"))
    ha = rec_a.get("statement_hash") or ""
    if (rec_b.get("base_hash") or "") != ha:
        probs.append("the amend run's base_hash %s is not run A's statement_hash %s"
                     % (rec_b.get("base_hash") or "(none)", ha or "(none)"))
    if not ha or (rec_b.get("statement_hash") or "") != ha:
        probs.append("the statement changed (A %s, B %s): an amendment adds dependencies "
                     "to the proof, never rewords the statement (a reword pass does)"
                     % (ha or "(none)", rec_b.get("statement_hash") or "(none)"))
    ia, ib = rec_a.get("run_id") or "", rec_b.get("run_id") or ""
    if not ia or not ib or ia == ib:
        probs.append("the runs' run ids (A %s, B %s) are not two distinct runs"
                     % (ia or "(none)", ib or "(none)"))
    sa, sb = rec_a.get("subject"), rec_b.get("subject")
    if sa and sb and sa != sb:
        probs.append("subjects differ (A %s, B %s)" % (sa, sb))
    want, got = set(rec_a["add_dependency"]), set(rec_b.get("amended_with") or ())
    if want != got:
        probs.append("the amend run reviewed other dependencies (amended_with %s) than "
                     "run A suggested (%s): it must list exactly those"
                     % (", ".join(sorted(got)) or "none", ", ".join(sorted(want))))
    return probs


def decide_amend(rec_a, rec_b=None, established=(), primary=None, producer_role=None,
                 kind_of=None):
    """The amend table (the human's design, 2026-11-20). ``rec_a`` is run A, CONFIRMED
    with ``add_dependency`` X; ``rec_b`` run B in amend mode (``mode: amend``,
    ``base_pass`` A's pass, ``base_hash`` A's statement hash, ``amended_with`` X), the
    informed review of the proof amended with X. The two count as the two agreeing
    verdicts, and X enters the modulo list until it is established.

    | Run A | Run B | Outcome |
    |---|---|---|
    | CONFIRMED + add_dependency X | not yet run | ``awaiting-amendment``: no B yet; the producer adds X to the proof and depends_on (``add-dependency`` item, a prove ticket, mode repair) |
    | CONFIRMED + X | amend, CONFIRMED, amended_with X, modulo Y | ``confirmed-modulo`` on A's modulo, Y and X (propose proved-modulo); ``confirmed`` (proved) when every one is established |
    | CONFIRMED + X | amend, GAP | ``disagreement``: no status; file B's blocking step |
    | CONFIRMED + X | amend, DISPROVED | ``disproved``: no status; the counterexample goes to the human |
    | CONFIRMED, no X | blind (not amend), CONFIRMED + add_dependency Z | ``new-pass-after-amendment``: no status; Z to the producer (``add-dependency`` item, as A's suggestion), then a new pass |
    | either PLAUSIBLE (or CONFIRMED off a primary) | | ``degraded`` |
    | no X, or B not amend, or amended_with != X, another pass / hash / statement / subject, a shared run id, or B suggesting further dependencies | | ``invalid-amend``: no status |
    """
    res = _new_result()
    rb = rec_b or {}
    res.update({"mode": "amend", "base_pass": rb.get("base_pass") or (rec_a or {}).get("pass") or "",
                "base_hash": rb.get("base_hash") or (rec_a or {}).get("statement_hash") or "",
                "add_dependency": list((rec_a or {}).get("add_dependency") or []),
                "added_dependencies": []})
    established = set(established or ())
    if rec_a is None or rec_a["problems"]:
        res["outcome"] = "incomplete"
        res["summary"] = "run A has no readable verdict: nothing to conclude"
        if rec_a:
            res["anomalies"].extend("run A: " + p for p in rec_a["problems"])
        return res
    prod_role = producer_role_for(rec_a.get("subject"), producer_role)
    recs = [rec_a] + ([rec_b] if rec_b is not None else [])
    for r in recs:
        eff, note = effective(r, primary) if not r["problems"] else ("", "")
        r["_eff"] = eff
        if note:
            res["anomalies"].append(note)
        row = {k: r.get(k) for k in ("run", "run_id", "verdict", "model", "modulo",
                                     "statement_hash", "blocking", "file", "mode",
                                     "add_dependency", "amended_with")}
        row["effective"] = eff
        res["runs"].append(row)
    if rec_b is not None and rec_b["problems"]:
        res["outcome"] = "incomplete"
        res["anomalies"].extend("run B: " + p for p in rec_b["problems"])
        res["summary"] = "run B has no readable verdict: conclude nothing yet"
        return res
    a = rec_a["_eff"]
    b = rec_b["_eff"] if rec_b is not None else None

    if rec_b is None:
        if is_amend(rec_a):
            res["outcome"] = "invalid-amend"
            res["anomalies"].append("run A is an amend record: an amend run is only ever "
                                    "run B")
            res["summary"] = "no status change: run A cannot be an amend run"
            return res
        # only reached for a CONFIRMED A (on a primary) that suggests dependencies
        deps = rec_a["add_dependency"]
        res["outcome"] = "awaiting-amendment"
        res["file_items"] = [{"run": rec_a.get("run") or "A", "kind": "add-dependency",
                              "text": ", ".join(deps)}]
        res["summary"] = ("A is CONFIRMED and suggests adding %s: no B yet; the producer adds "
                          "exactly that to the proof and to depends_on, then run B reviews "
                          "the amended proof (amend mode)" % ", ".join(deps))
        return res

    if b == "DISPROVED" or a == "DISPROVED":
        res["outcome"] = "disproved"
        res["needs_human"] = True
        res["file_items"] = [{"run": r.get("run"), "kind": "counterexample",
                              "text": r.get("blocking") or "see the run's report"}
                             for r in recs if r["_eff"] == "DISPROVED"]
        res["summary"] = ("DISPROVED in the amend pass: no status change; the counterexample "
                          "goes to %s at once" % ac.human_name())
        return res
    if "PLAUSIBLE" in (a, b):
        res["outcome"] = "degraded"
        res["summary"] = ("a PLAUSIBLE verdict never counts toward two agreeing verdicts: "
                          "re-run the PLAUSIBLE run on a primary model (%s)"
                          % ", ".join(_primaries(primary)))
        return res
    if not is_amend(rec_a) and not is_amend(rec_b) and not rec_a.get("add_dependency") \
            and rec_b.get("add_dependency") and a == "CONFIRMED" and b == "CONFIRMED":
        # 2026-11-20 review: the blind B (not A) suggests a dependency. Nothing to pair: A
        # reviewed the proof as it stands and B the same proof, so neither saw the amended
        # one. The producer adds it (as A's suggestion is routed), then a new pass.
        deps = rec_b["add_dependency"]
        res["outcome"] = "new-pass-after-amendment"
        res["add_dependency"] = list(deps)
        res["file_items"] = [{"run": rec_b.get("run") or "B", "kind": "add-dependency",
                              "text": ", ".join(deps)}]
        res["summary"] = ("no status change: run B (not run A) is CONFIRMED and suggests "
                          "adding %s; the producer adds it to the proof and to depends_on, "
                          "and a new pass (a fresh blind A) is needed after the repair: "
                          "this pair has no amend run to count" % ", ".join(deps))
        return res
    bad = _amend_problems(rec_a, rec_b)
    if not bad and a != "CONFIRMED":
        bad.append("run A is %s: an amend run follows only a CONFIRMED A" % a)
    if not bad and b == "CONFIRMED" and rec_b.get("add_dependency"):
        bad.append("the amend run suggests further dependencies (%s): the amended proof "
                   "still does not list its inputs; amend it again and rerun B"
                   % ", ".join(rec_b["add_dependency"]))
    if bad:
        res["outcome"] = "invalid-amend"
        res["anomalies"].extend(bad)
        res["summary"] = ("no status change: run B is not a valid amend run of run A's "
                          "suggestion")
        return res
    added = sorted(rec_a["add_dependency"])
    res["added_dependencies"] = added
    if b == "GAP":
        res["outcome"] = "disagreement"
        res["file_items"] = [{"run": rec_b.get("run") or "B", "kind": "repair",
                              "text": rec_b.get("blocking") or "see run B's report"}]
        res["summary"] = ("A CONFIRMED with %s suggested, the amend run B GAP on the amended "
                          "proof: no status change; file B's blocking step" % ", ".join(added))
        return res
    if b != "CONFIRMED":
        res["outcome"] = "no-change"
        res["summary"] = "no status change: run B is %s" % (b or "missing")
        return res
    mod = sorted(set(rec_a["modulo"]) | set(rec_b["modulo"]) | set(added))
    res["modulo"] = mod
    res["pending_inputs"] = sorted(set(mod) - established)
    how = ("run A CONFIRMED (%s) suggesting %s, run B (amend, %s) CONFIRMED on the proof "
           "amended with it, pass %s" % (rec_a.get("run_id") or "?", ", ".join(added),
                                         rec_b.get("run_id") or "?", rec_a.get("pass") or "?"))
    if not res["pending_inputs"]:
        res["outcome"] = "confirmed"
        res["proposed_status"] = "proved"
        res["recolour"] = True
        res["grounds"] = _amend_grounds(rec_a, rec_b, [], added, how + "; every input (%s) "
                                        "established" % ", ".join(mod), prod_role)
        res["summary"] = "%s; every input established: propose proved; recolour earned" % how
        return res
    res["outcome"] = "confirmed-modulo"
    res["proposed_status"] = "proved-modulo"
    res["grounds"] = _amend_grounds(rec_a, rec_b, mod, added, "%s, modulo %s"
                                    % (how, ", ".join(mod)), prod_role)
    res["file_items"] = [{"run": "A+B", "kind": "verify-input", "text": i}
                         for i in res["pending_inputs"]]
    res["summary"] = ("%s: propose proved-modulo %s; stays sketch until %s are established"
                      % (how, ", ".join(mod), ", ".join(res["pending_inputs"])))
    return res


def _amend_grounds(rec_a, rec_b, modulo, added, note, prod_role):
    g = _grounds([rec_a, rec_b], modulo, note, prod_role)
    g["verdicts"][1].update({"mode": "amend", "base_hash": rec_b.get("base_hash") or ""})
    g.update({"mode": "amend", "base_pass": rec_b.get("base_pass") or "",
              "added_dependencies": list(added)})
    return g


def _pair_ok(ra, rb, res):
    ok = True
    ia, ib = ra.get("run_id"), rb.get("run_id")
    if not ia or not ib:
        res["anomalies"].append("a run has no run_id")
        ok = False
    elif ia == ib:
        res["anomalies"].append("runs A and B share the run id %s" % ia)
        ok = False
    ha, hb = ra.get("statement_hash"), rb.get("statement_hash")
    if not ha or not hb:
        res["anomalies"].append("a run has no statement_hash")
        ok = False
    elif ha != hb:
        res["anomalies"].append("statement hashes differ (A %s, B %s): the statement "
                                "changed between the runs" % (ha, hb))
        ok = False
    sa, sb = ra.get("subject"), rb.get("subject")
    if sa and sb and sa != sb:
        res["anomalies"].append("subjects differ (A %s, B %s)" % (sa, sb))
        ok = False
    return ok


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _text(res):
    out = ["outcome: %s" % res["outcome"], "summary: %s" % res["summary"]]
    if res.get("mode") == "reword":
        out.append("mode: reword (base pass %s, base_hash %s, base outcome %s%s)"
                   % (res.get("base_pass") or "?", res.get("base_hash") or "?",
                      res.get("base_outcome") or "not read",
                      (", base_subject %s" % res["base_subject"])
                      if res.get("base_subject") else ""))
    if res["launch_b"]:
        out.append("next: launch run B")
    if res.get("mode") == "amend":
        out.append("mode: amend (pass %s, suggested %s, added %s)"
                   % (res.get("base_pass") or "?",
                      ", ".join(res.get("add_dependency") or []) or "none",
                      ", ".join(res.get("added_dependencies") or []) or "none"))
    if res.get("launch_full_pass"):
        out.append("next: open a fresh blind pass (run A) on the new statement")
    if res["proposed_status"]:
        out.append("propose: %s" % res["proposed_status"])
    out.append("recolour: %s" % ("yes" if res["recolour"] else "no"))
    if res["modulo"]:
        out.append("modulo: %s" % ", ".join(res["modulo"]))
    if res["pending_inputs"]:
        out.append("pending inputs: %s" % ", ".join(res["pending_inputs"]))
    for opt in res.get("modulo_options") or ():
        out.append("option %s: modulo %s" % (opt["label"],
                                             ", ".join(opt["modulo"]) or "none"))
    for run, lst in sorted((res.get("modulo_lists") or {}).items()):
        out.append("run %s listed: %s" % (run, ", ".join(lst) or "none"))
    for g in res.get("dropped_inputs") or ():
        out.append("dropped: %s (reached through %s, registry %s, case %d)"
                   % (g["input"], g["via"], g["how"], g["case"]))
    for d in res.get("differing_inputs") or ():
        facts = ["result %s%s" % (d["result"], " with pointer text" if d["pointer"] else "")
                 if d["result"] else "no existing result named"]
        if d["open_check"]:
            facts.append("open [CHECK]")
        if d["exists"] is not None and d["result"]:
            facts.append("in the registry" if d["exists"] else "not shown to exist")
        if d["cycle"]:
            facts.append("reaches the subject")
        out.append("differing input (run %s, %s): %s  [%s]"
                   % (d["run"], d["shape"], d["input"], "; ".join(facts)))
    if res.get("dropped_definitions"):
        out.append("dropped definitions (notation only, not inputs): %s"
                   % ", ".join(res["dropped_definitions"]))
    if res.get("kept_definitions"):
        out.append("kept definitions (inputs of both runs, no notation-only tag): %s"
                   % ", ".join(res["kept_definitions"]))
    for it in res["file_items"]:
        r = it.get("route") or {}
        out.append("file (%s, run %s%s): %s%s" % (
            it["kind"], it["run"], (", %s" % it["gap_class"]) if it.get("gap_class") else "",
            it["text"], ("  -> %s ticket to %s%s" % (r["kind"], r["to_role"],
                                                     (" (final_to %s)" % r["final_to"])
                                                     if r.get("final_to") else ""))
            if r else ""))
    for an in res["anomalies"]:
        out.append("anomaly: %s" % an)
    return "\n".join(out)


def main_canon(argv):
    """``decision_table.py canon --subject S ITEM...``: each input in canonical spelling
    (``canon_input``), one per line (the verify workflow compares suggested dependencies
    with a claim's declared inputs in it)."""
    ap = argparse.ArgumentParser(prog="decision_table.py canon")
    ap.add_argument("--subject", default="")
    ap.add_argument("items", nargs="*")
    args = ap.parse_args(argv)
    for it in args.items:
        print(canon_input(it, args.subject))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "canon":
        return main_canon(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("a", help="run A's verdict file")
    ap.add_argument("b", nargs="?", default=None, help="run B's verdict file, or - / omitted")
    ap.add_argument("--established", default="",
                    help="comma-separated modulo inputs known to be established")
    ap.add_argument("--primary", default=None,
                    help="comma-separated primary models (default: workspace.json "
                         "grading.primaryModels, else %s)" % ",".join(PRIMARY_MODELS))
    ap.add_argument("--producer-role", default=None,
                    help="override the namespace-owner lookup for grounds.producer_role")
    ap.add_argument("--base-dir", default=None,
                    help="a reword run (mode: reword): the base pass folder (default: the "
                         "sibling folder its base_pass names, under its base_subject's "
                         "folder when it names one)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        ra = read_record(args.a)
        rb = read_record(args.b)
        base, notes = None, ()
        if is_reword(ra):
            ba, bb, notes = base_records(args.a, ra.get("base_pass"), args.base_dir,
                                         ra.get("base_subject"))
            base = (ba, bb)
    except FileNotFoundError as exc:
        sys.stderr.write(missing_verdict(exc.filename or "", args.a, args.b))
        return 2
    except OSError as exc:
        sys.stderr.write("decision_table: %s\n" % exc)
        return 2
    res = decide(ra, rb, _split_list(args.established), args.primary, args.producer_role,
                 base=base, base_notes=notes, exists=registry_exists,
                 links_of=registry_links)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(json.dumps(res, indent=2, ensure_ascii=False) if args.json else _text(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
