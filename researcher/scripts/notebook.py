"""notebook.py -- the Researcher notebook: objects, directions, proof attempts, journal.

Plan section 3.3. Deterministic bookkeeping for the skills; it never sets a status above
the unsettled ones (open, conjectured, sketch): that is claim-keeper's, through
``claims_set_status``.

Usage (from a Researcher home, or with --home):

    py notebook.py ls [--kind K] [--status S] [--json]
    py notebook.py direction ID [--json]            the direction's items with their status
    py notebook.py next ID [--n N] [--json]         the next unsettled items to explore
    py notebook.py new KIND ID --title T [--statement S] [--status S] [--bears-on a,b]
                       [--depends-on a,b] [--falsifier F] [--tags a,b] [--domain D] [--by WHO]
                       [--target ID]  (approach)  [--approach ID]  (direction)
    py notebook.py approach show ID [--json]        lifecycle, target, members (computed)
    py notebook.py approach check [ID] [--campaign TARGET]
                                                    blocked needs blocked_by and reopen_if; a
                                                    lifecycle change needs a history row; a
                                                    direction names one existing approach;
                                                    --campaign: >= 4 approaches, each with a
                                                    direction
    py notebook.py approach set ID LIFECYCLE [--blocked-by ID --reopen-if LINE] [--note WHAT]
                       [--board DIR] [--apply]      blocking lists the approach's open tickets
                                                    and the dead-route moves for them (reopening
                                                    lists the --reopen moves); --apply makes the
                                                    moves of the tickets addressed to this
                                                    instance, the rest stay printed
    py notebook.py approach tickets [ID] [--held] [--board DIR] [--json]
                                                    the approach's tickets by refs, through the
                                                    store; --held: open tickets of a blocked,
                                                    dropped or delivered approach (skip them)
    py notebook.py approach status [--board DIR] [--json]
                                                    per approach: lifecycle, waiting on a
                                                    decision, tickets; whether to pause
    py notebook.py campaign-check --rounds N --agents M [--runs K --profile P] [--cloud]
                                                    validate and normalize the campaign caps
    py notebook.py attempt ID [--create] [--by WHO]  path of the next proof attempt
    py notebook.py journal [--date YYYY-MM-DD] [--create]
    py notebook.py scaffold HOME [--dry-run]         copy templates/notebook into a home
    py notebook.py status [--json]                   counts, attempts, reviews waiting

Ids: an object's file is ``objects/<kind>/<id>.md``; a reference ``<ns>:<id>`` is accepted
wherever an id is, and the namespace is dropped when it is this instance's.

Before a home's switch-over (schema v2, plan section 6, phase R6) the objects may still
live in the legacy folders (``claims/``, ``assumptions/``, ``examples/``); ``ls``,
``direction`` and ``status`` read those too, read-only.

Exit codes: 0 success, 1 nothing found, 2 error.
"""

import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402

SCAFFOLD = os.path.join(rs.TEMPLATES, "notebook")
TEMPLATE_DIR = os.path.join(SCAFFOLD, "_templates")
RE_REF = re.compile(r"`?\b(?:([a-z0-9]+):)?([A-Za-z][A-Za-z0-9._-]*(?::[A-Za-z0-9._-]+)*)`?")
DIRECTION_SECTIONS = ("Questions", "Candidate claims", "Falsifiers", "Next steps")
EXPLORE_SECTIONS = ("Questions", "Candidate claims")
RE_ONE_ID = re.compile(r"^(?:[a-z0-9]+:)?[A-Za-z0-9][A-Za-z0-9._-]*$")
OPEN_STATES = ("open", "accepted", "in-progress")
MIN_APPROACHES = 4
MIN_MECHANISM_WORDS = 3
CLOUD_ENV = ("CLAUDE_CODE_REMOTE", "ACADEMY_CLOUD")


def fm_edit(text, updates, drops=(), history_row=None):
    """``text`` with top-level frontmatter keys set (``updates``, placed after ``lifecycle``
    when new), dropped (``drops``), and ``history_row`` put first in the ``history:`` block
    list. Only the touched lines change: the other keys, the body and the older history
    rows stay byte for byte (the library writer would flatten ``history`` to one inline
    list). Rows are written JSON-quoted, as the object templates do."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise ac.AcademyError("no frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ac.AcademyError("unterminated frontmatter")
    entries = []                       # [key or None, [lines]]
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w-]*):", ln)
        if m or not entries:
            entries.append([m.group(1) if m else None, [ln]])
        else:
            entries[-1][1].append(ln)
    entries = [e for e in entries if e[0] not in drops]
    for k, v in updates.items():
        line = "%s: %s" % (k, ac._fmt_scalar(v))
        hit = [e for e in entries if e[0] == k]
        if hit:
            hit[0][1] = [line]
        else:
            at = next((i + 1 for i, e in enumerate(entries) if e[0] == "lifecycle"),
                      len(entries))
            entries.insert(at, [k, [line]])
    if history_row is not None:
        row = "  - " + json.dumps(history_row, ensure_ascii=False)
        hit = [e for e in entries if e[0] == "history"]
        if not hit:
            entries.append(["history", ["history:", row]])
        else:
            head = hit[0][1][0]
            inline = re.match(r"^history:\s*\[(.*)\]\s*$", head)
            old = hit[0][1][1:]
            if inline:               # a legacy inline list becomes a block list
                meta, _ = ac.read_frontmatter("---\n%s\n---\n" % head)
                old = ["  - " + json.dumps(str(r), ensure_ascii=False)
                       for r in meta.get("history") or []]
            hit[0][1] = ["history:", row] + old
    out = ["---"] + [ln for e in entries for ln in e[1]] + lines[end:]
    return "\n".join(out)


class Notebook(object):
    def __init__(self, home):
        home_, cfg, inst = rs.researcher_home(home)
        if not home_:
            raise ac.AcademyError("not in a Researcher home (give --home)")
        self.home, self.cfg, self.instance = home_, cfg, inst
        self.paths = rs.notebook_paths(home_, cfg)
        ws = rs.workspace_or_none()
        winst = (ws or {}).get("instances", {}).get(inst or "", {})
        self.ns = (cfg or {}).get("ns") or winst.get("ns") or ""
        doms = (cfg or {}).get("domains") or winst.get("domains") or [""]
        self.domain = doms[0]
        self.budget = ((cfg or {}).get("budget") or {}).get("itemsPerRun", 3)

    # -- ids ---------------------------------------------------------------
    def bare(self, ref):
        ref = str(ref).strip().strip("`")
        ns, sep, rest = ref.partition(":")
        if sep and ns == self.ns:
            return rest
        return ref

    def ref(self, oid):
        return "%s:%s" % (self.ns, oid) if self.ns else oid

    # -- objects -----------------------------------------------------------
    def object_files(self):
        """[(kind_folder, path)] for every object file, new layout first, then legacy."""
        out = []
        objs = self.paths["objects"]
        if os.path.isdir(objs):
            for kind in sorted(os.listdir(objs)):
                d = os.path.join(objs, kind)
                if not os.path.isdir(d):
                    continue
                for f in sorted(os.listdir(d)):
                    if f.endswith(".md") and not f.startswith("_") and f not in rs.NOT_RECORDS:
                        out.append((kind, os.path.join(d, f)))
        for legacy in ("claims", "assumptions", "examples"):
            d = os.path.join(self.home, legacy)
            if os.path.isdir(d) and os.path.abspath(d) != os.path.abspath(objs):
                for f in sorted(os.listdir(d)):
                    if f.endswith(".md") and not f.startswith("_") and f not in rs.NOT_RECORDS:
                        out.append((legacy, os.path.join(d, f)))
        return out

    def read_object(self, path, folder=None):
        text = rs.read_text(path) or ""
        get = lambda k: rs.frontmatter_field(text, k)[1]  # noqa: E731
        oid = get("id") or os.path.splitext(os.path.basename(path))[0]
        return {"id": oid, "ref": self.ref(oid), "kind": get("kind") or folder,
                "status": get("status"), "title": get("title"),
                "lifecycle": get("lifecycle") or "active", "proof": get("proof"),
                "approach": get("approach") or None, "target": get("target") or None,
                "blocked_by": get("blocked_by") or None,
                "reopen_if": get("reopen_if") or None,
                "path": path.replace("\\", "/")}

    def objects(self, kind=None, status=None):
        out = []
        for folder, path in self.object_files():
            o = self.read_object(path, folder)
            if kind and o["kind"] != kind:
                continue
            if status and (o["status"] or "").lower() != status.lower():
                continue
            out.append(o)
        return out

    def find(self, ref):
        oid = self.bare(ref)
        for folder, path in self.object_files():
            if os.path.splitext(os.path.basename(path))[0] == oid:
                return self.read_object(path, folder)
        return None

    # -- directions --------------------------------------------------------
    def direction(self, ref):
        d = self.find(ref)
        if not d or d["kind"] != "direction":
            raise ac.AcademyError("no direction object %s" % ref)
        text = rs.read_text(d["path"]) or ""
        items, section = [], None
        in_comment = False
        for ln in text.replace("\r\n", "\n").split("\n"):
            s = ln.strip()
            if "<!--" in s and "-->" not in s:
                in_comment = True
                continue
            if in_comment:
                if "-->" in s:
                    in_comment = False
                continue
            if s.startswith("## "):
                section = s[3:].strip()
                continue
            if section in DIRECTION_SECTIONS and s.startswith(("- ", "* ")):
                body = s[2:].strip()
                m = RE_REF.match(body)
                if not m:
                    continue
                ns, oid = m.group(1), m.group(2)
                if ns and ns != self.ns:
                    ref_ = "%s:%s" % (ns, oid)
                    obj = None
                else:
                    ref_ = self.ref(oid)
                    obj = self.find(oid)
                text_ = body[m.end():].strip(" -—:")
                items.append({"section": section, "ref": ref_, "text": text_,
                              "exists": obj is not None or bool(ns and ns != self.ns),
                              "kind": obj and obj["kind"], "status": obj and obj["status"],
                              "lifecycle": obj and obj["lifecycle"]})
        return d, items

    def next_items(self, ref, n=None):
        """The first ``n`` unsettled question / candidate-claim items of a direction."""
        n = min(n or self.budget, self.budget, 3)
        d, items = self.direction(ref)
        if self.approach_gate(d)[1]:
            return []       # a blocked, dropped or delivered approach gets no work
        out = []
        for it in items:
            if it["section"] not in EXPLORE_SECTIONS:
                continue
            if it["lifecycle"] and it["lifecycle"] != "active":
                continue
            st = (it["status"] or "").lower()
            if it["exists"] and st and st not in rs.UNSETTLED:
                continue
            out.append(it)
            if len(out) >= n:
                break
        return out

    # -- approaches (campaign mode) ------------------------------------------
    def approach(self, ref):
        a = self.find(ref)
        if not a or a["kind"] != "approach":
            raise ac.AcademyError("no approach object %s" % ref)
        return a

    def approach_members(self, ref):
        """The directions naming this approach in their ``approach:`` field. Computed,
        never hand-kept."""
        oid = self.bare(ref)
        return [d for d in self.objects("direction")
                if d["approach"] and self.bare(d["approach"]) == oid]

    def direction_approach_problem(self, d):
        """Why a direction's ``approach:`` is not one existing approach object of this
        notebook (None when it is, or when the direction names none). A direction belongs
        to exactly one approach: a list or a second id is a problem, not a silent miss."""
        raw = d.get("approach")
        if not raw:
            return None
        raw = str(raw).strip()
        if not RE_ONE_ID.match(raw):
            return ("%s: approach %r is not a single approach id (a direction belongs to "
                    "exactly one approach)" % (d["id"], raw))
        ns = raw.partition(":")[0] if ":" in raw else ""
        if ns and ns != self.ns:
            return "%s: approach %s is in another notebook (namespace %s)" % (d["id"], raw, ns)
        obj = self.find(raw)
        if not obj:
            return "%s: approach %s does not exist (no objects/approach file)" % (d["id"], raw)
        if obj["kind"] != "approach":
            return "%s: approach %s is a %s, not an approach object" % (d["id"], raw,
                                                                        obj["kind"])
        return None

    def direction_problems(self):
        """Every direction whose ``approach:`` is malformed, dangling or not an approach."""
        return [p for p in (self.direction_approach_problem(d)
                            for d in self.objects("direction")) if p]

    def approach_gate(self, d):
        """``(approach or None, reason or None)`` for a direction: the reason is why no work
        is to be taken (only an ``active`` approach gives work; a blocked or dropped one is
        suspended, a delivered one has nothing new). A malformed or dangling ``approach:`` is
        an error, never a silent lift of the block."""
        prob = self.direction_approach_problem(d)
        if prob:
            raise ac.AcademyError(prob)
        if not d.get("approach"):
            return None, None
        a = self.find(d["approach"])
        if a["lifecycle"] == "active":
            return a, None
        why = {"blocked": "is blocked (%s; reopen if %s)" % (a["blocked_by"], a["reopen_if"]),
               "dropped": "is dropped",
               "delivered": "is delivered: nothing new to explore"}.get(
                   a["lifecycle"], "is %s" % a["lifecycle"])
        return a, "approach %s %s" % (a["ref"], why)

    def _approach_file(self, ref):
        a = self.approach(ref)
        meta, body = ac.read_frontmatter(rs.read_text(a["path"]) or "")
        return a, meta, body

    @staticmethod
    def _history_rows(meta):
        rows = []
        for r in meta.get("history") or []:
            parts = [x.strip() for x in str(r).split("|", 2)]
            parts += [""] * (3 - len(parts))
            rows.append(tuple(parts))
        return rows        # newest first

    def _blocked_by_problem(self, a_id, target, blocked_by):
        """Why ``blocked_by`` cannot be the theorem-strength lemma of this approach."""
        bb = " ".join(str(blocked_by or "").split())
        if not ac.RE_BLOCKED_BY.match(bb):
            return ("blocked_by must be a registry id (GEO-31, paper:lem:x), not %r" % bb)
        if self.bare(bb) in (self.bare(target or ""), a_id):
            return ("blocked_by %s is the target or the approach itself: a route is blocked "
                    "by a lemma as strong as the target, not by the target" % bb)
        return None

    def approach_problems(self, ref=None):
        """Rule violations of one approach (or, without ``ref``, of all approaches and of
        every direction's ``approach:``): ``blocked`` is a dead route (``ac.is_dead_route``:
        ``blocked_by`` and ``reopen_if``) with ``blocked_by`` a registry id other than the
        target; the lifecycle must be the newest history row's; a reopening (blocked to
        active) needs a row that says what changed."""
        refs = [ref] if ref else [a["id"] for a in self.objects("approach")]
        probs = []
        for r in refs:
            a, meta, _ = self._approach_file(r)
            lc = str(meta.get("lifecycle") or "active")
            if lc not in rs.APPROACH_LIFECYCLES:
                probs.append("%s: lifecycle %r is not one of %s"
                             % (a["id"], lc, ", ".join(rs.APPROACH_LIFECYCLES)))
            if lc == "blocked":
                if not ac.is_dead_route(meta):
                    for f in ("blocked_by", "reopen_if"):
                        if not str(meta.get(f) or "").strip():
                            probs.append("%s: blocked without %s" % (a["id"], f))
                if str(meta.get("blocked_by") or "").strip():
                    bad = self._blocked_by_problem(a["id"], meta.get("target"),
                                                   meta["blocked_by"])
                    if bad:
                        probs.append("%s: %s" % (a["id"], bad))
            elif meta.get("blocked_by") or meta.get("reopen_if"):
                probs.append("%s: blocked_by / reopen_if left set on a %s approach"
                             % (a["id"], lc))
            rows = self._history_rows(meta)
            if not rows:
                probs.append("%s: no history row" % a["id"])
                continue
            if rows[0][1] != lc:
                probs.append("%s: lifecycle is %s but the newest history row says %s "
                             "(a change needs a row naming what changed)"
                             % (a["id"], lc, rows[0][1] or "nothing"))
            for newer, older in zip(rows, rows[1:]):
                if older[1] == "blocked" and newer[1] == "active" and not newer[2]:
                    probs.append("%s: reopened on %s without naming the new mechanism"
                                 % (a["id"], newer[0]))
        if not ref:
            probs.extend(self.direction_problems())
        return probs

    def campaign_problems(self, target):
        """Seeding check (campaign design section 4): at least ``MIN_APPROACHES`` approach
        objects aim at ``target``, each with at least one direction."""
        aps = [a for a in self.objects("approach")
               if a["target"] and self.bare(a["target"]) == self.bare(target)]
        probs = []
        if len(aps) < MIN_APPROACHES:
            probs.append("campaign %s: %d approach(es) aim at it, at least %d are needed"
                         % (target, len(aps), MIN_APPROACHES))
        for a in aps:
            if not self.approach_members(a["id"]):
                probs.append("%s: no direction names this approach (approach: %s)"
                             % (a["id"], a["id"]))
        return probs

    def set_approach(self, ref, lifecycle, blocked_by=None, reopen_if=None, note="",
                     by="lead-researcher"):
        """Move an approach to ``lifecycle`` and add the history row. Returns the path.

        - to ``blocked``: ``blocked_by`` (a registry id that is not the target) and
          ``reopen_if`` are required (the same fields and words as a dead-route ticket);
        - to ``active`` from ``blocked``: ``note`` names the new mechanism, invariant or
          construction (a phrase, recorded as ``reopened: ...``); nothing else reopens;
        - to ``delivered`` from ``blocked``: ``note`` says what delivered it;
        - to ``dropped``: an ordinary ``note``, or none.
        """
        if lifecycle not in rs.APPROACH_LIFECYCLES:
            raise ac.AcademyError("lifecycle must be one of %s"
                                  % ", ".join(rs.APPROACH_LIFECYCLES))
        a, meta, _body = self._approach_file(ref)
        old = str(meta.get("lifecycle") or "active")
        note = " ".join((note or "").split())
        bb = " ".join(str(blocked_by or "").split())
        ri = " ".join((reopen_if or "").split())
        updates, drops = {"lifecycle": lifecycle}, []
        if lifecycle == "blocked":
            if not bb or not ri:
                raise ac.AcademyError("%s: blocked needs blocked_by (the theorem-strength "
                                      "lemma) and reopen_if" % a["id"])
            bad = self._blocked_by_problem(a["id"], meta.get("target"), bb)
            if bad:
                raise ac.AcademyError("%s: %s" % (a["id"], bad))
            bb = self.bare(bb)
            updates["blocked_by"], updates["reopen_if"] = bb, ri
            note = note or "blocked by %s" % bb
        else:
            if bb or ri:
                raise ac.AcademyError("blocked_by and reopen_if belong to a move to blocked")
            if old == "blocked" and lifecycle == "active":
                if len(note.split()) < MIN_MECHANISM_WORDS:
                    raise ac.AcademyError(
                        "%s: reopening needs --note naming the new mechanism, invariant or "
                        "construction (a phrase of at least %d words); nothing else reopens "
                        "it" % (a["id"], MIN_MECHANISM_WORDS))
                note = "reopened: " + note
            elif old == "blocked" and lifecycle == "delivered" and not note:
                raise ac.AcademyError("%s: blocked -> delivered needs --note saying what "
                                      "delivered it" % a["id"])
            note = note or "set %s" % lifecycle
            drops = ["blocked_by", "reopen_if"]
        row = "%s | %s | %s (%s)" % (ac.today(), lifecycle, note, by)
        text = rs.read_text(a["path"]) or ""
        ac.atomic_write(a["path"], fm_edit(text, updates, drops, row))
        return a["path"]

    # -- tickets of an approach, through the board store ---------------------
    def _approach_names(self, ref):
        a = self.approach(ref)
        return {a["id"]} | {m["id"] for m in self.approach_members(ref)}

    def _refs_of(self, meta):
        return {self.bare(x) for x in (meta.get("refs") or [])}

    def approach_tickets(self, ref, store, states=OPEN_STATES):
        """Tickets naming this approach or one of its directions in ``refs``, in one of
        ``states``: ``[{id, to, status, refs, blocked_by, reopen_if, waiting_on}]``. Read
        through the board store, so a github board is read as the file board is."""
        names = self._approach_names(ref)
        return self._tickets(store, lambda m: bool(self._refs_of(m) & names)
                             and m.get("status") in states)

    @staticmethod
    def _tickets(store, keep):
        out = []
        for _r, m in ac.as_store(store).iter_meta():
            if keep(m):
                out.append({k: m.get(k) for k in ("id", "to", "status", "refs", "blocked_by",
                                                   "reopen_if", "waiting_on")})
        return sorted(out, key=lambda t: t["id"])

    def held_tickets(self, store):
        """Open tickets naming a non-active approach (or a direction of one): what dispatch
        must skip, because the shared inbox does not know approaches."""
        held = {}
        for a in self.objects("approach"):
            if a["lifecycle"] != "active":
                for n in self._approach_names(a["id"]):
                    held[n] = a
        out = []
        for t in self._tickets(store, lambda m: m.get("status") in OPEN_STATES):
            hit = sorted({held[n]["ref"] for n in self._refs_of(t) if n in held})
            if hit:
                out.append(dict(t, approach=hit[0]))
        return out

    def approach_status(self, store):
        """Per approach: lifecycle, directions, open tickets and ``waiting_on_decision``:
        true when any of its tickets is blocked with ``human`` in ``waiting_on`` (derived
        from the tickets, never hand-kept). ``pause`` is true when there is an active
        approach and every active approach waits on a decision."""
        rows = []
        for a in self.objects("approach"):
            ts = self.approach_tickets(a["id"], store, OPEN_STATES + ("blocked",))
            wait = [t["id"] for t in ts if t["status"] == "blocked"
                    and "human" in [str(w) for w in (t["waiting_on"] or [])]]
            rows.append({"approach": a["ref"], "lifecycle": a["lifecycle"],
                         "directions": [m["ref"] for m in self.approach_members(a["id"])],
                         "open_tickets": [t["id"] for t in ts if t["status"] in OPEN_STATES],
                         "waiting_on_decision": bool(wait), "decision_tickets": wait})
        active = [r for r in rows if r["lifecycle"] == "active"]
        return {"approaches": rows,
                "pause": bool(active) and all(r["waiting_on_decision"] for r in active)}

    # -- writing -----------------------------------------------------------
    def _render(self, name, values):
        with open(os.path.join(TEMPLATE_DIR, name), "r", encoding="utf-8") as fh:
            text = fh.read()
        for k, v in values.items():
            text = text.replace("{{%s}}" % k, v)
        return text

    def new_object(self, kind, oid, title, statement="", status=None, bears_on=(),
                   depends_on=(), falsifier="", tags=(), domain=None, by="researcher",
                   target="", approach=""):
        if kind not in rs.OBJECT_KINDS:
            raise ac.AcademyError("kind must be one of %s" % ", ".join(rs.OBJECT_KINDS))
        oid = self.bare(oid)
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", oid):
            raise ac.AcademyError("bad object id %r" % oid)
        if self.find(oid):
            raise ac.AcademyError("%s already exists" % self.ref(oid))
        if kind in rs.STATUS_KINDS:
            status = status or ("conjectured" if kind == "conjecture" else "open")
            if status not in ("open", "conjectured", "sketch"):
                raise ac.AcademyError("a new object starts unsettled (open, conjectured, "
                                      "sketch); %r is set only by claim-keeper" % status)
        elif status:
            raise ac.AcademyError("a %s carries no status" % kind)
        q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
        fmt_list = lambda xs: ", ".join(x for x in xs if x)  # noqa: E731
        vals = {"id": oid, "kind": kind, "title": q(title), "status": status or "",
                "statement": q(statement or ""), "statement_body": statement or "",
                "depends_on": fmt_list(depends_on), "bears_on": fmt_list(bears_on),
                "tags": fmt_list(tags), "domain": domain or self.domain,
                "date": ac.today(), "ns": self.ns, "falsifier": falsifier or "",
                "created": "created by %s" % by}
        if kind == "approach":
            if not target:
                raise ac.AcademyError("an approach names its target (--target, a registry id)")
            vals["target"] = target
            text = self._render("approach.md", vals)
        elif kind == "direction":
            vals["approach"] = self.bare(approach) if approach else ""
            text = self._render("direction.md", vals)
            if not approach:
                text = text.replace("approach: \n", "", 1)
        else:
            text = self._render("object.md", vals)
            if kind not in rs.STATUS_KINDS:
                text = text.replace("status: \n", "", 1)
                text = text.replace('"%s |  | ' % vals["date"], '"%s | | ' % vals["date"], 1)
            if not falsifier:
                text = text.replace("## Falsifier\n\n\n\n", "", 1)
        path = os.path.join(self.paths["objects"], kind, oid + ".md")
        ac.atomic_write(path, text)
        return path

    def attempt_path(self, ref, create=False, by="prover"):
        oid = self.bare(ref)
        d = os.path.join(self.paths["proofs"], oid)
        n = 1
        if os.path.isdir(d):
            nums = [int(m.group(1)) for f in os.listdir(d)
                    for m in [re.match(r"^attempt-(\d+)\.md$", f)] if m]
            n = max(nums) + 1 if nums else 1
        path = os.path.join(d, "attempt-%d.md" % n)
        if create:
            ac.atomic_write(path, self._render("attempt.md", {
                "ref": self.ref(oid), "n": str(n), "by": by, "date": ac.today()}))
        return path, n

    def journal_path(self, date=None, create=False):
        date = date or ac.today()
        if not ac.RE_DATE.match(date):
            raise ac.AcademyError("date must be YYYY-MM-DD")
        path = os.path.join(self.paths["journal"], date + ".md")
        if create and not os.path.exists(path):
            ac.atomic_write(path, self._render("journal.md", {"date": date}))
        return path

    def status(self):
        counts = {}
        for o in self.objects():
            key = (o["kind"] or "?", o["status"] or "-")
            counts[key] = counts.get(key, 0) + 1
        attempts = {}
        if os.path.isdir(self.paths["proofs"]):
            for oid in sorted(os.listdir(self.paths["proofs"])):
                d = os.path.join(self.paths["proofs"], oid)
                if os.path.isdir(d):
                    files = sorted(f for f in os.listdir(d) if f.startswith("attempt-"))
                    if files:
                        last = rs.read_text(os.path.join(d, files[-1])) or ""
                        attempts[oid] = {"attempts": len(files),
                                         "latest": rs.frontmatter_field(last, "outcome")[1]}
        import reviews  # local: reviews imports this module's siblings only
        waiting = reviews.pending(self.paths["audits"])
        return {"instance": self.instance, "home": self.home,
                "objects": [{"kind": k, "status": s, "count": c}
                            for (k, s), c in sorted(counts.items())],
                "attempts": attempts, "reviews_waiting_for_B": waiting}


def scaffold(home, dry_run=False):
    """Copy templates/notebook into ``home`` (never overwriting; ``_templates`` stays in
    the plugin). Returns the list of files created (or that would be)."""
    made = []
    for dirpath, dirnames, filenames in os.walk(SCAFFOLD):
        dirnames[:] = [d for d in dirnames if d != "_templates"]
        rel = os.path.relpath(dirpath, SCAFFOLD)
        for f in filenames:
            dst = os.path.normpath(os.path.join(home, rel, f))
            if os.path.exists(dst):
                continue
            made.append(dst.replace("\\", "/"))
            if not dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(os.path.join(dirpath, f), dst)
    return made


def _csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _board_module():
    """academy/scripts/board.py (the one place a ticket is moved), found as
    ``claims_edit_check.engine_dir`` finds the engine: ``$ACADEMY_ROOT/academy``, then
    beside this plugin."""
    import importlib.util
    cands = [os.path.join(os.environ["ACADEMY_ROOT"], "academy")] \
        if os.environ.get("ACADEMY_ROOT") else []
    cands.append(os.path.join(os.path.dirname(os.path.dirname(HERE)), "academy"))
    for c in cands:
        path = os.path.join(c, "scripts", "board.py")
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location("_academy_board", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise ac.AcademyError("academy/scripts/board.py not found (set ACADEMY_ROOT); run the "
                          "printed commands instead of --apply")


def _moves(nb, args, old_row, note):
    """The ticket moves that follow an approach move, as ``[(ticket, argv tail, kwargs)]``.
    Blocking: every open ticket of the approach becomes a dead-route block with the
    approach's ``blocked_by`` / ``reopen_if`` and a ``tried:`` line. Reopening (``blocked``
    to ``active``): every ticket blocked that way, with the approach's old fields, goes back
    to ``accepted`` with ``--reopen``. Other moves leave the tickets alone."""
    store = _store(args)
    a = nb.approach(args.id)
    if args.lifecycle == "blocked":
        bb, ri = nb.bare(args.blocked_by), " ".join(args.reopen_if.split())
        why = "approach %s blocked by %s (%s): its route is dead" % (a["ref"], bb, args.by)
        return [(t, "blocked --blocked-by %s --reopen-if %s --reason %s"
                 % (bb, json.dumps(ri), json.dumps(why)),
                 dict(new="blocked", blocked_by=bb, reopen_if=ri, reason=why))
                for t in nb.approach_tickets(args.id, store)]
    if args.lifecycle == "active" and old_row.get("lifecycle") == "blocked":
        names = nb._approach_names(args.id)
        out = []
        for t in nb._tickets(store, lambda m: m.get("status") == "blocked"
                             and ac.is_dead_route(m) and m.get("blocked_by") == old_row["blocked_by"]
                             and m.get("reopen_if") == old_row["reopen_if"]
                             and bool(nb._refs_of(m) & names)):
            out.append((t, "accepted --reopen %s" % json.dumps(note),
                        dict(new="accepted", reopen=note)))
        return out
    return []


def _do_moves(nb, args, moves):
    board = None
    for t, tail, kw in moves:
        cmd = "py academy/scripts/board.py transition %s %s --as %s" % (t["id"], tail, t["to"])
        if args.apply and t["to"] == nb.instance:
            board = board or _board_module()
            try:
                board.transition_ticket(_store(args), t["id"], kw["new"], kw.get("reason", ""),
                                        as_instance=nb.instance, agent=args.by,
                                        blocked_by=kw.get("blocked_by"),
                                        reopen_if=kw.get("reopen_if"), reopen=kw.get("reopen"))
                print("  %s (%s, %s): moved to %s" % (t["id"], t["to"], t["status"], kw["new"]))
                continue
            except Exception as exc:          # the board's own AcademyError is another class
                print("  %s: NOT moved (%s)" % (t["id"], exc))
        print("  %s (%s, %s): %s" % (t["id"], t["to"], t["status"], cmd))


def _store(args):
    return ac.open_store(board=args.board) if args.board else ac.open_store()


def _approach_cmd(nb, args):
    if args.action == "check":
        probs = nb.approach_problems(args.id)
        if args.campaign:
            probs += nb.campaign_problems(args.campaign)
        for p_ in probs:
            print(p_)
        return 2 if probs else 0
    if args.action == "status":
        st = nb.approach_status(_store(args))
        if args.json:
            print(json.dumps(st, ensure_ascii=False, indent=1))
        else:
            for r in st["approaches"]:
                print("%-14s %-10s waiting-on-decision: %-3s open tickets: %s"
                      % (r["approach"], r["lifecycle"],
                         "yes" if r["waiting_on_decision"] else "no",
                         ", ".join(r["open_tickets"]) or "-"))
            if st["pause"]:
                print("PAUSE: every active approach waits on a human decision "
                      "(/academy:decide)")
        return 0
    if args.action == "tickets":
        if args.held:
            rows = nb.held_tickets(_store(args))
        elif args.id:
            rows = nb.approach_tickets(args.id, _store(args),
                                       OPEN_STATES + ("blocked",))
        else:
            raise ac.AcademyError("give the approach id, or --held")
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
        else:
            for t in rows:
                print("%s %s %s%s" % (t["id"], t["to"], t["status"],
                                      "  (approach %s)" % t["approach"]
                                      if t.get("approach") else ""))
        return 0
    if not args.id:
        raise ac.AcademyError("give the approach id")
    if args.action == "set":
        if not args.lifecycle:
            raise ac.AcademyError("give the lifecycle")
        a = nb.approach(args.id)
        old_row = {"lifecycle": a["lifecycle"], "blocked_by": a["blocked_by"],
                   "reopen_if": a["reopen_if"]}
        nb.set_approach(args.id, args.lifecycle, args.blocked_by, args.reopen_if, args.note,
                        args.by)
        print("%s -> %s" % (a["ref"], args.lifecycle))
        note = " ".join(args.note.split())
        # a ticket is blocked only by its receiver (or the human): --apply moves the tickets
        # addressed to this instance, the others are printed for their receiver
        _do_moves(nb, args, _moves(nb, args, old_row, note))
        return 0
    a = nb.approach(args.id)
    info = {"approach": a, "members": [m["ref"] for m in nb.approach_members(args.id)],
            "problems": nb.approach_problems(args.id)}
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=1))
    else:
        print("%s  %s  [%s]  target %s" % (a["ref"], a["title"] or "", a["lifecycle"],
                                          a["target"] or "?"))
        if a["blocked_by"]:
            print("  blocked_by %s; reopen_if %s" % (a["blocked_by"], a["reopen_if"]))
        for m in info["members"]:
            print("  direction %s" % m)
        for p_ in info["problems"]:
            print("  PROBLEM " + p_)
    return 0


def campaign_caps(rounds=None, agents=None, runs=None, profile="", cloud=False, env=None):
    """The normalized caps of a campaign, or an AcademyError naming the missing one.

    Only validation: nothing here counts rounds, agents or runs, or ends a campaign; the
    driver (the main session) enforces the caps it is given. ``cloud`` (or one of
    ``CLOUD_ENV`` set) forces ``runs`` to 0; ``runs`` > 0 needs ``profile``."""
    env = os.environ if env is None else env
    for name, v in (("--rounds", rounds), ("--agents", agents)):
        if v is None:
            raise ac.AcademyError("%s is required: stop and ask (suggest 3 rounds, 4 agents)"
                                  % name)
        if v < 1:
            raise ac.AcademyError("%s must be at least 1" % name)
    runs = 0 if runs is None else runs
    if runs < 0:
        raise ac.AcademyError("--runs must not be negative")
    in_cloud = bool(cloud) or any(str(env.get(k, "")).lower() in ("1", "true", "yes")
                                  for k in CLOUD_ENV)
    forced = in_cloud and runs > 0
    if forced:
        runs = 0
    if runs > 0 and not profile:
        raise ac.AcademyError("--runs %d needs --profile (the one lab profile to queue on)"
                              % runs)
    return {"rounds": rounds, "agents": agents, "runs": runs,
            "profile": profile or None, "cloud": in_cloud, "runs_forced_to_zero": forced}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ls"); p.add_argument("--kind"); p.add_argument("--status")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("direction"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("next"); p.add_argument("id"); p.add_argument("--n", type=int)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("new"); p.add_argument("kind"); p.add_argument("id")
    p.add_argument("--title", required=True); p.add_argument("--statement", default="")
    p.add_argument("--status"); p.add_argument("--bears-on"); p.add_argument("--depends-on")
    p.add_argument("--falsifier", default=""); p.add_argument("--tags")
    p.add_argument("--domain"); p.add_argument("--by", default="researcher")
    p.add_argument("--target", default=""); p.add_argument("--approach", default="")
    p = sub.add_parser("approach")
    p.add_argument("action", choices=("show", "check", "set", "tickets", "status"))
    p.add_argument("id", nargs="?"); p.add_argument("lifecycle", nargs="?")
    p.add_argument("--blocked-by"); p.add_argument("--reopen-if"); p.add_argument("--note", default="")
    p.add_argument("--board"); p.add_argument("--by", default="lead-researcher")
    p.add_argument("--json", action="store_true"); p.add_argument("--apply", action="store_true")
    p.add_argument("--held", action="store_true"); p.add_argument("--campaign")
    p = sub.add_parser("campaign-check")
    p.add_argument("--rounds", type=int); p.add_argument("--agents", type=int)
    p.add_argument("--runs", type=int); p.add_argument("--profile", default="")
    p.add_argument("--cloud", action="store_true"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("attempt"); p.add_argument("id"); p.add_argument("--create", action="store_true")
    p.add_argument("--by", default="prover")
    p = sub.add_parser("journal"); p.add_argument("--date"); p.add_argument("--create", action="store_true")
    p = sub.add_parser("scaffold"); p.add_argument("target"); p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("status"); p.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "scaffold":
            made = scaffold(os.path.abspath(args.target), args.dry_run)
            print("%s %d file(s)" % ("would create" if args.dry_run else "created", len(made)))
            for m in made:
                print("  " + m)
            return 0
        if args.cmd == "campaign-check":
            caps = campaign_caps(args.rounds, args.agents, args.runs, args.profile, args.cloud)
            if args.json:
                print(json.dumps(caps, indent=1))
            else:
                print("rounds=%d agents=%d runs=%d profile=%s cloud=%s%s"
                      % (caps["rounds"], caps["agents"], caps["runs"], caps["profile"] or "-",
                         "yes" if caps["cloud"] else "no",
                         "  (runs forced to 0 in a cloud session)"
                         if caps["runs_forced_to_zero"] else ""))
            return 0
        nb = Notebook(args.home or os.getcwd())
        if args.cmd == "ls":
            objs = nb.objects(args.kind, args.status)
            if args.json:
                print(json.dumps(objs, ensure_ascii=False, indent=1))
            else:
                for o in objs:
                    print("%-28s %-11s %-18s %s" % (o["ref"], o["kind"] or "?",
                                                    o["status"] or "-", o["title"] or ""))
            return 0 if objs else 1
        if args.cmd == "direction":
            d, items = nb.direction(args.id)
            if args.json:
                print(json.dumps({"direction": d, "items": items}, ensure_ascii=False, indent=1))
            else:
                print("%s  %s" % (d["ref"], d["title"] or ""))
                for it in items:
                    print("  [%s] %-24s %-12s %s" % (it["section"], it["ref"],
                                                     it["status"] or ("-" if it["exists"]
                                                                      else "(no object)"),
                                                     it["text"]))
            return 0
        if args.cmd == "next":
            d, _items = nb.direction(args.id)
            items = nb.next_items(args.id, args.n)
            why = nb.approach_gate(d)[1]
            if args.json:
                print(json.dumps(items, ensure_ascii=False, indent=1))
            else:
                for it in items:
                    print("%-24s %-12s %s" % (it["ref"], it["status"] or
                                              ("-" if it["exists"] else "(no object)"), it["text"]))
                if not items:
                    print("(%s)" % (why or "nothing unsettled left in %s" % args.id))
            return 0 if items else 1
        if args.cmd == "new":
            path = nb.new_object(args.kind, args.id, args.title, args.statement, args.status,
                                 _csv(args.bears_on), _csv(args.depends_on), args.falsifier,
                                 _csv(args.tags), args.domain, args.by, args.target,
                                 args.approach)
            print(path.replace("\\", "/"))
            return 0
        if args.cmd == "approach":
            return _approach_cmd(nb, args)
        if args.cmd == "attempt":
            path, n = nb.attempt_path(args.id, args.create, args.by)
            print(path.replace("\\", "/"))
            return 0
        if args.cmd == "journal":
            print(nb.journal_path(args.date, args.create).replace("\\", "/"))
            return 0
        if args.cmd == "status":
            st = nb.status()
            if args.json:
                print(json.dumps(st, ensure_ascii=False, indent=1))
            else:
                print("%s (%s)" % (st["instance"], st["home"]))
                for row in st["objects"]:
                    print("  %-11s %-18s %d" % (row["kind"], row["status"], row["count"]))
                for oid, a in st["attempts"].items():
                    print("  proof %s: %d attempt(s), latest %s" % (oid, a["attempts"], a["latest"]))
                print("  reviews waiting for run B: %s" % (", ".join(st["reviews_waiting_for_B"])
                                                          or "none"))
            return 0
    except (ac.AcademyError, OSError) as exc:
        sys.stderr.write("notebook.py: %s\n" % exc)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
