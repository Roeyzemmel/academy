"""sweep.py -- the deterministic half of the machine-note sweep (#110, #98 point 1).

    py sweep.py [--home DIR] [--board DIR | --workspace FILE] plan [--full] [--limit N]
                                                    [--max-age DAYS] [--json]
    py sweep.py [...] record [--unjudged SIG ...] [--json]
    py sweep.py [...] inventory [--json]

The note-sweeper used to grep every machine note of the paper on every inbox run and judge
each one from the board (about 565 notes, 0-1 deleted a run). This script does what needs
no judgement, and remembers what was judged:

**plan** inventories the machine notes (``machine_notes.py``; typed ``\\Claude[kind]{...}``
or untyped) and sorts the ones that need attention into four lists:

- ``retire``: an ``await`` note whose named ticket (its first ``T-NNNN``) ended with an
  artefact: ``delivered`` or ``closed`` with a non-empty result. ``action`` is ``delete``,
  or ``pointer`` when the result reads as a negative or conditional outcome (a GAP,
  DISPROVED, BROKEN, PLAUSIBLE or MODULO verdict, "refuted", "failed", ...): then
  ``replacement`` is a short untyped pointer note, ``\\<macro>{T-NNNN <status>: <result>}``
  within ``author.notes.maxLines``.
- ``move``: a ``prov`` (provenance) note, proposed for removal; its text is first recorded
  where ``record_to`` says: the thread of the ticket it names, or (no ticket named) a
  record ticket on the agenda entry of the nearest label.
- ``judge``: everything the note-sweeper still decides by its rule (an untyped, ``check``,
  ``human`` or unknown-kind note; an ``await`` whose ticket was rejected, cancelled or
  closed without a result, is not on the board, or that names no ticket: said in
  ``detail``), with ``why``: ``new``, ``ticket moved``, ``context changed`` or ``stale``.
- ``waiting``: ``await`` notes whose ticket is still live (delivered without a result
  included: its sender has not landed it): nothing to do, cached as such.

``human`` lists every ``human`` note of the paper (the weekly review's list), whether or
not it is to be judged. ``retire``, ``move`` and ``judge`` together are capped at
``--limit`` (default 30), in that order; the rest is ``deferred`` to the next sweep. The
plan is written to ``<home>/.academy/note-sweep-plan.json`` for ``record``. A plan with
nothing to do and nothing deferred records itself at once (``recorded``: true).

**What is re-read** (the incremental sweep). The state file
``<home>/.academy/note-sweep.json`` (``.academy/`` ignores itself: machine-local, never
committed) keeps the commit of the last complete sweep and a cache of verdicts:
signature -> {file, kind, ctx, tickets: {id: "status|updated"}, checked}. A sweep reads
the tex files changed since that commit (``git diff`` against it, working tree and
untracked files included), unless ``--full`` or there is no usable recorded commit (then
every file). In a file that was read, a note is skipped when its cache entry matches: same
signature (kind and text), same paragraph around it (``context_hash``: a reply written
next to it brings it back), the same state of every ticket it names, and (with
``--max-age``) checked within that many days. In a file that was not read, only notes with
a cache entry that no longer matches come back (their ticket moved, or the entry is stale).
The whole tex is still parsed, which costs milliseconds; what is saved is the agent's
reading and judging.

**record** runs after the agent's pass: every note of the plan's ``judge`` and ``waiting``
lists still in the tex (minus ``--unjudged`` signatures: the ones the agent did not reach)
is cached as checked and still open, and so is every new note in a file the plan had work
in (a note the agent narrowed, or a pointer it left). Entries of notes no longer in the tex
are dropped. The recorded commit moves to HEAD only when the sweep is complete: nothing
deferred or unjudged, and every retirement and move applied (its note gone from the tex);
otherwise it stays, so the next sweep reads the same files again and the cache skips what
was done. The tex files still uncommitted at a complete record (the checkpoint commits the
sweep's edits after it) are kept by content hash, and are not read again while unchanged.

**inventory** counts the notes per file and kind, over the cap, and naming a ticket
(read-only; no state).

The ticket states come from the board (``--board`` for a file board, else workspace.json's
``board``; one listing). Exit codes: 0 ok; 2 error (one line on stderr).
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import machine_notes as mn  # noqa: E402

STATE = "note-sweep.json"
PLAN = "note-sweep-plan.json"
DEFAULT_LIMIT = 30
#: a result that reads as a negative or conditional outcome leaves a pointer, not nothing
RE_NEGATIVE = re.compile(r"\b(GAP|DISPROVED|BROKEN|PLAUSIBLE|MODULO|REFUTED)\b|"
                         r"(?i:\b(refuted|not confirmed|failed|unfinished|counterexample|"
                         r"partial|incomplete)\b)")
ENDED_WITH_ARTEFACT = ("delivered", "closed")
ENDED_WITHOUT = ("rejected", "cancelled")
RE_LABEL = re.compile(r"\\label\s*\{([^}]*)\}")
TEXT_CLIP = 300


class SweepError(Exception):
    pass


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------

def _dir(home):
    return ac.manifest_dir(home)          # <home>/.academy, ignoring itself


def load_state(home):
    try:
        with open(os.path.join(home, ".academy", STATE), encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    if not isinstance(st, dict):
        st = {}
    st.setdefault("version", 1)
    st.setdefault("commit", None)
    if not isinstance(st.get("cache"), dict):
        st["cache"] = {}
    return st


def _write_json(path, data):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def save_state(home, st):
    _write_json(os.path.join(_dir(home), STATE), st)


# ----------------------------------------------------------------------------
# Git and files
# ----------------------------------------------------------------------------

def _git(home, *args):
    try:
        p = subprocess.run(["git", "-C", home] + list(args), capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode:
        return None
    return p.stdout.decode("utf-8", "replace")


def git_head(home):
    out = _git(home, "rev-parse", "--verify", "HEAD")
    return out.strip() if out else None


def git_changed(home, base):
    """Home-relative paths changed since ``base`` (working tree and untracked included),
    or None when ``base`` is not a commit of this repository."""
    if _git(home, "cat-file", "-e", "%s^{commit}" % base) is None:
        return None
    diff = _git(home, "diff", "--name-only", "--relative", base, "--")
    new = _git(home, "ls-files", "--others", "--exclude-standard")
    if diff is None or new is None:
        return None
    return {ln.strip().replace("\\", "/") for ln in (diff + "\n" + new).splitlines()
            if ln.strip()}


def tex_files(home, cfg):
    """The home's tex files, home-relative with ``/``, sorted."""
    import glob
    pats = ((cfg or {}).get("paths") or {}).get("tex") or ["main.tex", "sections/*.tex"]
    if isinstance(pats, str):
        pats = [pats]
    out = set()
    for p in pats:
        for f in glob.glob(os.path.join(home, *str(p).replace("\\", "/").split("/"))):
            if os.path.isfile(f):
                out.add(os.path.relpath(f, home).replace(os.sep, "/"))
    return sorted(out)


def _hash(text):
    import hashlib
    return hashlib.sha1(text.encode("utf-8", "surrogateescape")).hexdigest()


def _read(home, rel):
    try:
        with open(os.path.join(home, *rel.split("/")), encoding="utf-8", errors="replace",
                  newline="") as fh:
            return fh.read()
    except OSError:
        return ""


# ----------------------------------------------------------------------------
# Notes and tickets
# ----------------------------------------------------------------------------

def _label_before(text, offset):
    last = None
    for m in RE_LABEL.finditer(text, 0, offset):
        last = m.group(1).strip()
    return last


def entry(rel, text, note, line_chars):
    body = note["body"]
    t = mn.plain(body)
    return {"file": rel, "line": note["line"], "end_line": note["end_line"],
            "macro": note["macro"], "kind": note["kind"], "sig": mn.signature(note),
            "ctx": mn.context_hash(text, note), "tickets": mn.tickets(body),
            "lines": mn.estimate_lines(body, line_chars),
            "label": _label_before(text, note["start"]),
            "text": t if len(t) <= TEXT_CLIP else t[:TEXT_CLIP - 3] + "...",
            "raw": note["raw"]}


def parse_home(home, cfg, files=None):
    """``[(rel, text, [entry...])]`` for the home's tex files, and the anomalies."""
    macros = mn.machine_macros(cfg)
    _max, line_chars = mn.note_limits(cfg)
    out, anomalies = [], []
    for rel in (files if files is not None else tex_files(home, cfg)):
        text = _read(home, rel)
        rows = []
        for n in mn.scan(text, macros):
            if n.get("body") is None:
                anomalies.append("%s:%d: a \\%s note whose brace never closes"
                                 % (rel, n["line"], n["macro"]))
                continue
            rows.append(entry(rel, text, n, line_chars))
        out.append((rel, text, rows))
    return out, anomalies


class Tickets(object):
    """Ticket id -> meta, from one listing of the board, made on the first question."""

    def __init__(self, store):
        self.store = store
        self.by_num = None

    @staticmethod
    def _num(tid):
        m = re.search(r"\d+", str(tid))
        return int(m.group()) if m else str(tid)

    def meta(self, tid):
        if self.by_num is None:
            self.by_num = {}
            if self.store is not None:
                for _ref, m in self.store.iter_meta():
                    if m and m.get("id"):
                        self.by_num[self._num(m["id"])] = m
        return self.by_num.get(self._num(tid))

    def state(self, tid):
        m = self.meta(tid)
        if not m:
            return "missing"
        return "%s|%s" % (m.get("status") or "", m.get("updated") or "")


def _result(meta):
    r = (meta or {}).get("result")
    return " ".join(str(r).split()) if r not in (None, "") else ""


TEX_ESCAPES = {"\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "_": "\\_", "%": "\\%",
               "&": "\\&", "#": "\\#", "$": "\\$", "~": "\\textasciitilde{}",
               "^": "\\textasciicircum{}"}


def pointer(macro, tid, status, result, max_lines, line_chars):
    """A short untyped note naming the ended ticket and its result, within the cap."""
    head = "%s %s: " % (tid, status)
    room = max(0, max_lines * line_chars - len(head))
    res = result if len(result) <= room else result[:max(0, room - 3)].rstrip() + "..."
    return "\\%s{%s%s}" % (macro, head, "".join(TEX_ESCAPES.get(c, c) for c in res))


def _stale(cached, today, max_age):
    if not max_age:
        return False
    try:
        checked = datetime.date.fromisoformat(str(cached.get("checked")))
    except ValueError:
        return True
    return (today - checked).days > int(max_age)


# ----------------------------------------------------------------------------
# plan / record / inventory
# ----------------------------------------------------------------------------

def _today(today):
    if isinstance(today, datetime.date):
        return today
    return datetime.date.fromisoformat(today) if today else datetime.date.today()


def plan(home, cfg, store, full=False, limit=DEFAULT_LIMIT, max_age=None, today=None):
    day = _today(today)
    st = load_state(home)
    cache = st["cache"]
    head = git_head(home)
    base = st.get("commit")
    mode, reason, changed = "incremental", "", None
    if full:
        mode, reason = "full", "--full"
    elif not head:
        mode, reason = "full", "not a git repository (or no commit yet)"
    elif not base:
        mode, reason = "full", "no sweep recorded"
    else:
        changed = git_changed(home, base)
        if changed is None:
            mode, reason = "full", "the recorded commit %s not found" % str(base)[:12]
        else:
            # a file the last sweep left uncommitted (the checkpoint commits after the
            # record) is unchanged when its content is what the record saw
            for rel, h in (st.get("dirty") or {}).items():
                if rel in changed and _hash(_read(home, rel)) == h:
                    changed.discard(rel)
    max_lines, line_chars = mn.note_limits(cfg)
    ns = str((cfg or {}).get("ns") or "paper")
    tickets = Tickets(store)
    parsed, anomalies = parse_home(home, cfg)
    retire, move, judge, waiting, human = [], [], [], [], []
    skipped = {"cached": 0, "unread_file": 0}
    counts = {"notes": 0, "by_kind": {}, "by_file": {}, "over_max_lines": 0}
    states = {}
    for rel, _text, rows in parsed:
        read = mode == "full" or rel in (changed or ())
        for e in rows:
            kind = e["kind"] or "untyped"
            counts["notes"] += 1
            counts["by_kind"][kind] = counts["by_kind"].get(kind, 0) + 1
            counts["by_file"][rel] = counts["by_file"].get(rel, 0) + 1
            counts["over_max_lines"] += e["lines"] > max_lines
            if e["kind"] == "human":
                human.append(e)
            cached = cache.get(e["sig"])
            if not read and not cached:
                skipped["unread_file"] += 1
                continue
            e["states"] = {t: tickets.state(t) for t in e["tickets"]}
            states.update(e["states"])
            if cached:
                if (cached.get("ctx") == e["ctx"] and cached.get("tickets") == e["states"]
                        and not _stale(cached, day, max_age)):
                    skipped["cached"] += 1
                    continue
                if cached.get("tickets") != e["states"]:
                    e["why"] = "ticket moved"
                elif cached.get("ctx") != e["ctx"]:
                    if not read:          # an unread file cannot have changed around it
                        skipped["cached"] += 1
                        continue
                    e["why"] = "context changed"
                else:
                    e["why"] = "stale"
            else:
                e["why"] = "new"
            where = "%s:%d" % (rel, e["line"])
            if e["kind"] == "prov":
                e["record_to"] = ({"ticket": e["tickets"][0]} if e["tickets"] else
                                  {"record_ticket": True,
                                   "agenda": "%s:%s" % (ns, e["label"]) if e["label"] else ""})
                move.append(e)
            elif e["kind"] == "await":
                if not e["tickets"]:
                    anomalies.append("%s: an await note that names no ticket" % where)
                    e["detail"] = "names no ticket"
                    judge.append(e)
                    continue
                tid = e["tickets"][0]
                meta = tickets.meta(tid)
                status = (meta or {}).get("status")
                res = _result(meta)
                if status in ENDED_WITH_ARTEFACT and res:
                    neg = bool(RE_NEGATIVE.search(res))
                    e.update(action="pointer" if neg else "delete", status=status, result=res,
                             replacement=pointer(e["macro"], tid, status, res, max_lines,
                                                 line_chars) if neg else "")
                    retire.append(e)
                elif meta is None or status in ENDED_WITHOUT or status == "closed":
                    e["detail"] = ("%s is not on the board" % tid if meta is None else
                                   "%s was closed without a result" % tid
                                   if status == "closed" else "%s was %s" % (tid, status))
                    judge.append(e)
                else:
                    waiting.append(e)
            else:
                if e["kind"] and e["kind"] not in mn.KINDS:
                    anomalies.append("%s: unknown note kind [%s] (kinds: %s); judged as an "
                                     "untyped note" % (where, e["kind"], ", ".join(mn.KINDS)))
                judge.append(e)
    work = retire + move + judge
    cap = max(0, int(limit)) if limit is not None else len(work)
    taken, rest = work[:cap], work[cap:]
    keep = {id(x) for x in taken}
    p = {"home": home, "mode": mode, "reason": reason, "base": base, "head": head,
         "changed_files": sorted(f for f in (changed or ()) if f in {r for r, _t, _x in parsed}),
         "today": day.isoformat(), "limit": cap,
         "retire": [x for x in retire if id(x) in keep],
         "move": [x for x in move if id(x) in keep],
         "judge": [x for x in judge if id(x) in keep],
         "waiting": waiting, "human": human,
         "deferred": len(rest), "deferred_sigs": [x["sig"] for x in rest],
         "skipped": skipped, "counts": counts, "anomalies": anomalies,
         "ticket_states": states,
         "seen": {rel: [e["sig"] for e in rows] for rel, _t, rows in parsed},
         "recorded": False}
    p["todo"] = len(taken)
    _write_json(os.path.join(_dir(home), PLAN), p)
    if not p["todo"] and not p["deferred"] and head:
        record(home, cfg, store, today=day)
        p["recorded"] = True
    return p


def load_plan(home):
    try:
        with open(os.path.join(home, ".academy", PLAN), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        raise SweepError("no sweep plan in %s/.academy: run `sweep.py plan` first" % home)


def record(home, cfg, store, unjudged=(), today=None):
    day = _today(today).isoformat()
    p = load_plan(home)
    st = load_state(home)
    cache = st["cache"]
    parsed, _anomalies = parse_home(home, cfg)
    now = {}
    for rel, _text, rows in parsed:
        for e in rows:
            now.setdefault(e["sig"], e)
    unj = set(unjudged or ())
    tickets = Tickets(store)
    known = dict(p.get("ticket_states") or {})

    def state(t):
        if t not in known:
            known[t] = tickets.state(t)
        return known[t]

    def put(e, states):
        cache[e["sig"]] = {"file": e["file"], "kind": e["kind"], "ctx": e["ctx"],
                           "tickets": states, "checked": day}

    cached = narrowed = 0
    for x in (p.get("judge") or []) + (p.get("waiting") or []):
        if x["sig"] in unj or x["sig"] not in now:
            continue
        put(now[x["sig"]], x.get("states") or {t: state(t) for t in x["tickets"]})
        cached += 1
    worked = {x["file"] for x in (p.get("retire") or []) + (p.get("move") or [])
              + (p.get("judge") or [])}
    seen = {s for sigs in (p.get("seen") or {}).values() for s in sigs}
    for rel, _text, rows in parsed:
        if rel not in worked:
            continue
        for e in rows:
            if e["sig"] in seen or e["sig"] in cache or e["sig"] in unj:
                continue
            put(e, {t: state(t) for t in e["tickets"]})
            narrowed += 1
    gone = [s for s in cache if s not in now]
    for s in gone:
        del cache[s]
    pending = [{"file": x["file"], "line": x["line"], "sig": x["sig"], "text": x["text"]}
               for x in (p.get("retire") or []) + (p.get("move") or []) if x["sig"] in now]
    left = sorted(s for s in unj if s in now)
    why = []
    if p.get("deferred"):
        why.append("%d note(s) deferred" % p["deferred"])
    if left:
        why.append("%d note(s) left unjudged" % len(left))
    if pending:
        why.append("%d retirement(s) or move(s) not applied" % len(pending))
    head = git_head(home)
    if not why and not head:
        why.append("not a git repository")
    advanced = not why
    if advanced:
        st["commit"] = head
        st["swept"] = day
        texs = set(tex_files(home, cfg))
        st["dirty"] = {rel: _hash(_read(home, rel))
                       for rel in sorted((git_changed(home, head) or set()) & texs)}
    save_state(home, st)
    return {"cached": cached, "narrowed": narrowed, "pruned": len(gone), "pending": pending,
            "unjudged": left, "advanced": advanced, "commit": st.get("commit"),
            "why": "; ".join(why), "cache_size": len(cache)}


def inventory(home, cfg):
    max_lines, _lc = mn.note_limits(cfg)
    parsed, anomalies = parse_home(home, cfg)
    by_kind = {k: 0 for k in ("untyped",) + mn.KINDS}
    by_file, n, over, named = {}, 0, 0, 0
    for rel, _text, rows in parsed:
        for e in rows:
            n += 1
            k = e["kind"] or "untyped"
            by_kind[k] = by_kind.get(k, 0) + 1
            by_file[rel] = by_file.get(rel, 0) + 1
            over += e["lines"] > max_lines
            named += bool(e["tickets"])
    return {"notes": n, "by_kind": by_kind, "by_file": by_file, "over_max_lines": over,
            "max_lines": max_lines, "naming_a_ticket": named, "anomalies": anomalies}


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _line(x):
    extra = ""
    if x.get("action"):
        extra = " -> %s" % x["action"]
    elif x.get("record_to"):
        extra = " -> record in %s" % (x["record_to"].get("ticket")
                                      or "a record ticket (%s)" % x["record_to"].get("agenda"))
    elif x.get("why"):
        extra = " (%s%s)" % (x["why"], "; " + x["detail"] if x.get("detail") else "")
    return "  %s:%d [%s] %s%s: %s" % (x["file"], x["line"], x.get("kind") or "untyped",
                                      x["sig"], extra, x["text"][:120])


def summary(p):
    s = ("sweep: todo %d (retire %d, move %d, judge %d), deferred %d, waiting %d, cached %d; "
         "mode %s%s; for the human %d" % (
             p["todo"], len(p["retire"]), len(p["move"]), len(p["judge"]), p["deferred"],
             len(p["waiting"]), p["skipped"]["cached"], p["mode"],
             " (%s)" % p["reason"] if p["reason"] else "", len(p["human"])))
    if p.get("recorded"):
        s += "; nothing to do: recorded"
    return s


def _store(args):
    if args.board:
        return ac.FileBoardStore(os.path.abspath(args.board))
    return ac.open_store(ac.load_workspace(args.workspace))


def parser():
    ap = argparse.ArgumentParser(prog="sweep.py", description=__doc__.split("\n")[0])
    ap.add_argument("--home", default=None, help="the Author home (default: the cwd's)")
    ap.add_argument("--board", default=None, help="a file board (default: workspace.json's)")
    ap.add_argument("--workspace", default=None)
    ap.add_argument("--today", default=None, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--full", action="store_true", help="read every tex file")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--max-age", type=int, default=None, dest="max_age",
                   help="re-judge cached verdicts older than this many days")
    p.add_argument("--json", action="store_true")
    r = sub.add_parser("record")
    r.add_argument("--unjudged", nargs="*", default=[], help="signatures not reached")
    r.add_argument("--json", action="store_true")
    i = sub.add_parser("inventory")
    i.add_argument("--json", action="store_true")
    return ap


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parser().parse_args(argv)
    try:
        home = ac.find_home(os.path.abspath(args.home or os.getcwd()))
        if not home:
            raise SweepError("no academy home at or above %s" % (args.home or os.getcwd()))
        cfg = ac.load_config(home)
        if cfg.get("role") != "author":
            raise SweepError("%s is not an Author home" % home)
        if args.cmd == "inventory":
            inv = inventory(home, cfg)
            if args.json:
                print(json.dumps(inv, indent=1, ensure_ascii=False))
                return 0
            print("%d machine notes; by kind: %s; over %d lines: %d; naming a ticket: %d"
                  % (inv["notes"], ", ".join("%s %d" % kv for kv in inv["by_kind"].items()),
                     inv["max_lines"], inv["over_max_lines"], inv["naming_a_ticket"]))
            for rel, k in sorted(inv["by_file"].items()):
                print("  %s: %d" % (rel, k))
            for a in inv["anomalies"]:
                print("ANOMALY: " + a)
            return 0
        store = _store(args)
        if args.cmd == "plan":
            p = plan(home, cfg, store, full=args.full, limit=args.limit,
                     max_age=args.max_age, today=args.today)
            if args.json:
                print(json.dumps(p, indent=1, ensure_ascii=False))
                return 0
            print(summary(p))
            if p["changed_files"]:
                print("changed since the last sweep: " + ", ".join(p["changed_files"]))
            for name in ("retire", "move", "judge", "human"):
                if p[name]:
                    print(name.upper())
                    for x in p[name]:
                        print(_line(x))
            for a in p["anomalies"]:
                print("ANOMALY: " + a)
            return 0
        r = record(home, cfg, store, unjudged=args.unjudged, today=args.today)
        if args.json:
            print(json.dumps(r, indent=1, ensure_ascii=False))
            return 0
        print("sweep recorded: %d cached, %d narrowed, %d pruned (cache %d); commit %s"
              % (r["cached"], r["narrowed"], r["pruned"], r["cache_size"],
                 "advanced to %s" % str(r["commit"])[:12] if r["advanced"]
                 else "not advanced (%s)" % r["why"]))
        for x in r["pending"]:
            print("  pending %s:%d %s: %s" % (x["file"], x["line"], x["sig"], x["text"][:100]))
        return 0
    except (SweepError, ac.AcademyError, OSError, ValueError) as exc:
        sys.stderr.write("sweep.py: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
