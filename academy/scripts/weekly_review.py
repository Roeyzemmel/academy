#!/usr/bin/env python3
"""weekly_review.py -- one week of the academy on one page, for /academy:weekly-review (#107).

    py weekly_review.py [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--ref REF] [--json]
                        [--out FILE] [--no-problems] [--workspace W] [--board B]

Gathers the window (``--since``, default seven days before ``--until``; ``--until``,
default today; both days included, UTC) into one structured record and renders it as
markdown (stdout, or ``--out FILE``; ``--json`` prints the record instead). Sections:

1. **Paper changes by section**: per Author home, the commits of the window on its tex
   files, its registry and its statements view, and the statements added, removed,
   reworded (the registry's statement hash changed), ``note-only`` (the same hash once the
   home's ``author.noteMacros`` calls and ``%`` comments are stripped), ``label-removed``
   (the label left the tex), ``recoloured`` (the draft colour of ``Drafts/statements.md``)
   or with a status change, old and new status, file:line of the label at the head. The registry is read through its own profile (``registry.profiles.store_for``)
   from a snapshot of the home at the last commit before the window and the last commit
   in it (``git archive`` of the registry, tex and config paths into a temp directory);
   every other home with a namespace is compared the same way.
2. **Ready to read**: statements that moved to proved or proved-modulo in the window, apart
   from those added already so, with the latest decided review pass (its date flagged when
   older than the window) (the Expert library's ``reviews/<ns>/<id>/<pass>/
   decision.md``) and its recorded outcome; proof attempts added in Researcher homes
   (``proofs/<object>/attempt-<n>.md``) with their declared inputs and each input's status.
3. **Decisions**: ``decisions.pending_decisions``, counted by kind; the routine kinds
   (``ROUTINE_TICKET_KINDS``, ``ROUTINE_PACKET_KINDS``, after #86) are only counted, the
   rest listed by group (experiments with their "what would refute it" line, proofs,
   rulings, notation and structure, sources), as of now, not as of ``--until``.
4. **Merges waiting**: per repository (the workspace's submodules and every instance home),
   the tips of the stacks of remote work branches ``<YYYY-MM-DD>/<topic>/<role>`` not
   merged into ``origin/main``, with depth, commits ahead and age (UTC), as the last fetch
   left them (nothing is fetched).
5. **Problems**: count and top rows of the consistency audit (``audit.py --json``), the
   reading list (``expert/scripts/reading_list.py --json``) and ``registry.py stale --json``
   per home, each run only when its script exists; tickets delivered with an empty result
   and parked tickets (one board listing); error-class issues of ``errors.repo`` opened in
   the window. Anything not gathered (a missing tool, a
   failed run, an unreadable home or board) is named under "Not gathered", never dropped.

Read-only: git is only read (``log``, ``rev-list``, ``archive``, ``show``, ``for-each-ref``);
the board, the homes and the registries are never written. The script never publishes;
the skill does (``skills/weekly-review/SKILL.md``).
"""

import argparse
import collections
import datetime
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402

POSITIVE = ("proved", "proved-modulo")
#: rows shown per problem source
TOP = 5
#: ticket and packet kinds whose pending decisions are routine (#86): counted, not listed.
#: A ``notation`` ticket is routine (#86: one requested pack edit), while a ``notation``
#: packet is not: it puts a choice of notation to the human, which #107 lists as real.
#: A ``usage`` packet is routine: its decisions are the weekly budget proposals, which the
#: weekly workflow already caps and grades (``academy-weekly``).
ROUTINE_TICKET_KINDS = frozenset({"verify", "review-experiment", "cite", "code", "notation",
                                  "note", "apply"})
ROUTINE_PACKET_KINDS = frozenset({"verification", "citation", "experiment-review", "usage"})
#: experiment decisions whose ticket body is read for its "what would refute it" line
REFUTES_CAP = 10
#: the non-routine groups, in page order, with their headings
GROUPS = (("experiment", "Experiment headers"), ("proof", "Proofs"),
          ("ruling", "Rulings and decisions"),
          ("notation-structure", "Notation and structure choices"),
          ("source", "Sources to read"), ("other", "Other"))
_GROUP_OF = {"experiment": "experiment", "test": "experiment", "experiment-report": "experiment",
             "generalize": "experiment", "generalization": "experiment",
             "prove": "proof", "research": "proof", "proof": "proof",
             "decision": "ruling", "referee": "ruling",
             "notation": "notation-structure", "agenda": "notation-structure",
             "migration": "notation-structure", "write": "notation-structure",
             "build": "notation-structure", "figure": "notation-structure"}

RE_WORK_BRANCH = re.compile(r"^\d{4}-\d{2}-\d{2}/[^/]+/[a-z]+$")
RE_ATTEMPT = re.compile(r"^proofs/(.+)/attempt-\d+\.md$")
RE_QID = re.compile(r"^([a-z0-9]+):(\S+)$")
RE_LABEL = re.compile(r"\\label\{([^}]+)\}")
RE_COMMENT = re.compile(r"(?<!\\)%.*$", re.M)
RE_TICKET_ID = re.compile(r"^T-\d{4,}$")
RE_REFUTES = re.compile(r"(?i)would refute|refut|falsif")
#: what the page never gathers, said on it so it does not look complete
ALWAYS_NOT_GATHERED = (
    "paper: the coloured diff of the tex (latexdiff) is not built",
    "problems: false deliveries are only those delivered with an empty result line; a "
    "delivery whose work is missing or unpushed is not detected",
)


def _reg(sub):
    """``registry.<sub>`` of this plugin (the package beside ``scripts/``). ``scripts/registry.py``
    shares the name, so the package is imported with the plugin first on the path and a
    cached script module set aside."""
    mod = sys.modules.get("registry")
    if mod is not None and not hasattr(mod, "__path__"):
        del sys.modules["registry"]
    sys.path.insert(0, PLUGIN)
    try:
        return importlib.import_module("registry." + sub)
    finally:
        sys.path.remove(PLUGIN)


# ------------------------------------------------------------------------------ pure parts

def window(since=None, until=None, today=None):
    """``(since, until)`` as ISO dates: until defaults to today, since to seven days before
    until. Raises ValueError on a malformed date or since after until."""
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    u = datetime.date.fromisoformat(until) if until else today
    s = datetime.date.fromisoformat(since) if since else u - datetime.timedelta(days=7)
    if s > u:
        raise ValueError("--since %s is after --until %s" % (s, u))
    return s.isoformat(), u.isoformat()


def diff_records(old, new):
    """The changed records between two ``{id: {"status", "hash", "norm"?}}`` maps, sorted by
    id (``norm``: the hash without margin notes and comments, when known):
    ``{"id", "changes": [added|removed|reworded|note-only|status], "old_status", "new_status",
    "old_hash", "new_hash"}``; an unchanged record is left out."""
    out = []
    for rid in sorted(set(old) | set(new)):
        o, n = old.get(rid), new.get(rid)
        if o is None:
            changes = ["added"]
        elif n is None:
            changes = ["removed"]
        else:
            changes = []
            if (o.get("hash") or None) != (n.get("hash") or None):
                # the same text once the margin notes and comments are gone: note-only
                same = o.get("norm") is not None and o.get("norm") == n.get("norm")
                changes.append("note-only" if same else "reworded")
            if (o.get("status") or "") != (n.get("status") or ""):
                changes.append("status")
            if not changes:
                continue
        out.append({"id": rid, "changes": changes,
                    "old_status": (o or {}).get("status") if o else None,
                    "new_status": (n or {}).get("status") if n else None,
                    "old_hash": (o or {}).get("hash"), "new_hash": (n or {}).get("hash")})
    return out


def note_macros(cfg):
    """Every margin-note macro of a home's ``author.noteMacros`` (sorted, deduplicated)."""
    nm = ((cfg or {}).get("author") or {}).get("noteMacros") or {}
    vals = nm.values() if isinstance(nm, dict) else [nm]
    out = set()
    for v in vals:
        for m in ([v] if isinstance(v, str) else v or []):
            if isinstance(m, str) and m.startswith("\\") and len(m) > 1:
                out.add(m)
    return sorted(out)


def _skip_group(text, i, open_, close):
    """The index after the balanced group opening at ``text[i]`` (or len(text))."""
    depth = 0
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == open_:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def strip_notes(text, macros):
    """``text`` without ``%`` comments and without each note macro's call (``\\m[opt]{arg}``,
    the argument's braces balanced). A macro name only matches whole (``\\cl`` is not
    ``\\claim``); a macro with no ``{`` after it is left alone."""
    text = RE_COMMENT.sub("", text or "")
    for m in sorted(macros, key=len, reverse=True):
        pat = re.compile(re.escape(m) + r"(?![A-Za-z@])")
        out, pos = [], 0
        for hit in pat.finditer(text):
            if hit.start() < pos:
                continue
            j = hit.end()
            while j < len(text) and text[j] in " \t":
                j += 1
            if j < len(text) and text[j] == "[":
                j = _skip_group(text, j, "[", "]")
            if j < len(text) and text[j] == "{":
                out.append(text[pos:hit.start()])
                pos = _skip_group(text, j, "{", "}")
        out.append(text[pos:])
        text = "".join(out)
    return text


def refutation_line(text):
    """The first line of ``text`` saying what would refute the experiment (``refute``,
    ``falsifier``), without its list or heading marker; else its ``Goal:`` line; else None."""
    goal = None
    for line in (text or "").splitlines():
        t = line.strip().lstrip("-*#> ").strip()
        if not t:
            continue
        if RE_REFUTES.search(t):
            return t[:300]
        if goal is None and t.startswith("Goal:"):
            goal = t[:300]
    return goal


def stack_tips(rows, unique):
    """The tips of the stacks among unmerged branches ``rows`` (``{"branch", "sha", ...}``):
    a branch is a tip when no other one contains its commit (``unique[branch]``: the commits
    of the branch not on main). Two names on one commit are one tip, the later name. Each tip
    gets ``depth`` (the branches of its stack, itself included), ``ahead`` (its commits not
    on main) and ``same_commit`` (the other names of its commit)."""
    tips = []
    for b in rows:
        covered = any(c is not b and b["sha"] in unique.get(c["branch"], ()) and
                      (c["sha"] != b["sha"] or c["branch"] > b["branch"]) for c in rows)
        if covered:
            continue
        mine = unique.get(b["branch"], set())
        t = dict(b)
        t["depth"] = sum(1 for c in rows if c["sha"] in mine or c["sha"] == b["sha"])
        t["ahead"] = len(mine)
        t["same_commit"] = sorted(c["branch"] for c in rows
                                  if c is not b and c["sha"] == b["sha"])
        tips.append(t)
    return sorted(tips, key=lambda t: t["branch"])


def _utc_date(ts):
    """A unix timestamp (str or int) as its UTC ISO date, or None."""
    try:
        return datetime.datetime.fromtimestamp(int(str(ts).strip()),
                                               datetime.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _in_window(date, since, until):
    return bool(date) and since <= str(date)[:10] <= until


def ticket_problems(metas, since, until):
    """``{"delivered_no_result": [rows], "parked": {"count", "new", "by_wait", "top"}}`` of a
    board listing: delivered with an empty result line (#100), and parked (blocked) tickets
    by what they wait on (human, a ticket, an instance), ``new`` = updated in the window."""
    bad, parked = [], []
    for m in metas:
        st = m.get("status")
        row = {"id": m.get("id"), "to": m.get("to"), "title": m.get("title"),
               "updated": str(m.get("updated") or "")[:10]}
        if st == "delivered" and not str(m.get("result") or "").strip():
            bad.append(row)
        elif st == "blocked":
            w = [str(x) for x in (m.get("waiting_on") or [])]
            row["wait"] = ("human" if ac.HUMAN in w else
                           "ticket" if any(RE_TICKET_ID.match(x) for x in w) else
                           "instance" if any("@" in x for x in w) else "other")
            row["waiting_on"] = w
            parked.append(row)
    parked.sort(key=lambda r: (r["updated"], str(r["id"])), reverse=True)
    return {"delivered_no_result": bad,
            "parked": {"count": len(parked),
                       "new": sum(1 for r in parked if _in_window(r["updated"], since, until)),
                       "by_wait": dict(sorted(collections.Counter(r["wait"] for r in parked)
                                              .items())),
                       "top": parked[:TOP]}}


def label_lines(texts):
    """``{label: (path, line)}`` of every ``\\label{...}`` in ``{path: text}`` (paths in sorted
    order; the first occurrence wins)."""
    out = {}
    for path in sorted(texts):
        for n, line in enumerate(texts[path].splitlines(), 1):
            for m in RE_LABEL.finditer(line):
                out.setdefault(m.group(1), (path, n))
    return out


def decision_group(item):
    """``"routine"`` or the item's non-routine group (``GROUPS``)."""
    kind, source = item.get("item_kind"), item.get("source")
    if item.get("ruling"):
        return "ruling"
    if kind == "cite" and source == "ticket-blocked":
        return "source"                     # a cite parked on the human: a source to read
    if source == "packet":
        if kind in ROUTINE_PACKET_KINDS:
            return "routine"
    elif kind in ROUTINE_TICKET_KINDS:
        return "routine"
    return _GROUP_OF.get(kind, "other")


def summarise_decisions(items):
    """``{"total", "by_kind": {"ticket:<kind>"|"packet:<kind>": n}, "routine": n,
    "real": {group: [items]}}``."""
    by_kind = collections.Counter()
    real = collections.OrderedDict((g, []) for g, _ in GROUPS)
    routine = 0
    for i in items:
        src = "packet" if i.get("source") == "packet" else "ticket"
        by_kind["%s:%s" % (src, i.get("item_kind") or "?")] += 1
        g = decision_group(i)
        if g == "routine":
            routine += 1
        else:
            real[g].append(i)
    return {"total": len(items), "by_kind": dict(sorted(by_kind.items())), "routine": routine,
            "real": {g: rows for g, rows in real.items() if rows}}


def parse_refs(text, today):
    """Rows ``{"branch", "sha", "date", "age_days"}`` of a ``for-each-ref`` listing
    (``origin/<branch> US sha US committer unix time``), work branches only; the date is
    the commit's UTC date, so the age does not depend on the committer's zone."""
    rows = []
    for line in text.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        name, sha, date = parts
        branch = name.split("/", 1)[1] if "/" in name else name
        if not RE_WORK_BRANCH.match(branch):
            continue
        day = _utc_date(date)
        age = (today - datetime.date.fromisoformat(day)).days if day else None
        rows.append({"branch": branch, "sha": sha, "date": day or "", "age_days": age})
    return sorted(rows, key=lambda r: (r["date"], r["branch"]))


# ------------------------------------------------------------------------------- git, read

def _git(repo, *args, binary=False):
    """git's stdout; any failure, git missing included, is a RuntimeError."""
    try:
        p = subprocess.run(["git", "-C", repo, *args], capture_output=True, timeout=300,
                           stdin=subprocess.DEVNULL,
                           env=dict(os.environ, GIT_PAGER="cat", GIT_TERMINAL_PROMPT="0"))
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("git %s: %s" % (" ".join(args[:3]), exc)) from exc
    if p.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(args[:3]),
                                           p.stderr.decode("utf-8", "replace").strip()[:200]))
    return p.stdout if binary else p.stdout.decode("utf-8", "replace").strip()


def _since_arg(since):
    return "%s 00:00:00 +0000" % since


def _until_arg(until):
    return "%s 23:59:59 +0000" % until


def _bounds(repo, ref, since, until):
    """``(base, head)``: the last commit of ``ref`` before the window ('' when none) and the
    last one in it or before it."""
    base = _git(repo, "rev-list", "-1", "--before=" + _since_arg(since), ref) or ""
    # rev-list --before uses the committer date, as log --since/--until does
    head = _git(repo, "rev-list", "-1", "--before=" + _until_arg(until), ref) or ""
    return base, head


def _commits(repo, ref, since, until, paths):
    out = _git(repo, "log", "--format=%H%x1f%ct%x1f%s", "--since=" + _since_arg(since),
               "--until=" + _until_arg(until), ref, "--", *paths)
    rows = []
    for line in out.splitlines():
        sha, ts, subject = (line.split("\x1f") + ["", ""])[:3]
        rows.append({"sha": sha, "date": _utc_date(ts) or "", "subject": subject})
    return rows


def _read_cfg(home):
    try:
        with open(os.path.join(home, ".claude", "academy.json"), encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def _tex_globs(cfg):
    tex = ((cfg.get("paths") or {}).get("tex")) or ["main.tex", "sections/*.tex"]
    return [tex] if isinstance(tex, str) else list(tex)


def _registry_rel(cfg):
    reg = cfg.get("registry") or {}
    root = reg.get("root") or (cfg.get("paths") or {}).get("records") or "claims"
    return root if isinstance(root, str) else "claims"


def _record_paths(cfg):
    """Where a home's registry records live: its registry root, and the notebook folders."""
    return sorted({_registry_rel(cfg), "objects", "claims", "assumptions", "examples"})


#: the generated view the draft colours are read from (``registry.profiles.fsl.paper_colours``)
COLOURS_VIEW = "Drafts/statements.md"


def _snapshot_paths(cfg):
    """The top-level paths a registry store needs from a home (config, records, tex)."""
    tops = {".claude/academy.json", "sections", COLOURS_VIEW} | set(_record_paths(cfg))
    for g in _tex_globs(cfg):
        tops.add(g.split("/", 1)[0] if "/" in g else g)
    return sorted(t for t in tops if "*" not in t)


def _snapshot(repo, commit, cfg, dest):
    """Extract the registry's paths of ``repo`` at ``commit`` into ``dest`` (read-only on the
    repo: ``git archive`` to memory)."""
    os.makedirs(dest, exist_ok=True)
    if not commit:
        return dest
    present = [p for p in _snapshot_paths(cfg)
               if _git(repo, "ls-tree", "--name-only", commit, "--", p)]
    if not present:
        return dest
    data = _git(repo, "archive", "--format=tar", commit, "--", *present, binary=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:                               # a Python without extraction filters
            tar.extractall(dest)           # noqa: S202 -- our own repo's archive
    return dest


def _texts(snap, cfg):
    import glob as _glob
    out = {}
    for g in _tex_globs(cfg):
        for p in sorted(_glob.glob(os.path.join(snap, g))):
            rel = os.path.relpath(p, snap).replace(os.sep, "/")
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    out[rel] = fh.read()
            except OSError:
                pass
    return out


def _load_records(ns, snap, cfg, macros=None):
    """``{id: {"status", "hash", "norm", "title", "file", "where_field"}}`` of the registry in
    the snapshot ``snap``, read through its profile. ``norm`` (only with ``macros``, an
    Author home's note macros): the statement hash once the notes and comments are gone."""
    store_for = _reg("profiles").store_for
    hash_of = _reg("core.model").statement_hash_of
    if not os.path.isfile(os.path.join(snap, ".claude", "academy.json")):
        return {}
    st = store_for(ns, snap)
    out = {}
    for rid, r in st.records.items():
        text = st.statement_text(rid)
        out[rid] = {"status": r.status or "", "hash": hash_of(text) if text is not None else None,
                    "norm": hash_of(strip_notes(text, macros))
                    if macros is not None and text is not None else None,
                    "title": r.title, "where_field": str(r.fields.get("where") or ""),
                    "file": os.path.relpath(r.file, snap).replace(os.sep, "/")
                    if r.file else ""}
    return out


def _colours(snap):
    """``{label: draft colour}`` of the snapshot's generated statements view (the registry's
    own reader, ``fsl.paper_colours``; its per-path cache is cleared around the call, as the
    snapshot directories are temporary)."""
    from pathlib import Path
    fsl = _reg("profiles.fsl")
    key = ("colours", Path(snap))
    fsl._cache.pop(key, None)
    try:
        return dict(fsl.paper_colours(Path(snap)))
    finally:
        fsl._cache.pop(key, None)


def _section_of(rec, loc):
    where = (rec or {}).get("where_field") or ""
    if where.endswith(".tex"):
        return os.path.splitext(os.path.basename(where))[0]
    if loc:
        return os.path.splitext(os.path.basename(loc[0]))[0]
    return "(no section)"


# -------------------------------------------------------------------- 1. registry changes

def _homes(ws, roles=None):
    for name, inst in sorted((ws.get("instances") or {}).items()):
        if roles and inst.get("role") not in roles:
            continue
        yield name, inst


def _is_shallow(home):
    try:
        return _git(home, "rev-parse", "--is-shallow-repository") == "true"
    except RuntimeError:
        return False


def _paper_changes(ns, old, new, old_snap, new_snap, cfg):
    """``diff_records`` of an Author home, with the label's place at the head, the section,
    a label gone from the tex (``label-removed``) and the draft colour (``recoloured``)."""
    locs_new = label_lines(_texts(new_snap, cfg))
    locs_old = label_lines(_texts(old_snap, cfg))
    col_old, col_new = _colours(old_snap), _colours(new_snap)
    changes = {c["id"]: c for c in diff_records(old, new)}
    for rid in set(col_old) & set(col_new):
        if col_old[rid] != col_new[rid] and rid in new:
            c = changes.setdefault(rid, {
                "id": rid, "changes": [], "old_status": old.get(rid, {}).get("status"),
                "new_status": new[rid]["status"], "old_hash": old.get(rid, {}).get("hash"),
                "new_hash": new[rid]["hash"]})
            c["changes"].append("recoloured")
    out = []
    for rid in sorted(changes):
        c = changes[rid]
        rec = new.get(rid) or old.get(rid)
        # a label that left the tex is said so: the statement text then falls back to the
        # record's own, so its hash changes without any rewording
        if rid in new and rid in old and rid in locs_old and rid not in locs_new:
            c["changes"] = ["label-removed" if x in ("reworded", "note-only") else x
                            for x in c["changes"]]
        loc = locs_new.get(rid) if rid in new else None
        c.update({"qid": "%s:%s" % (ns, rid), "title": rec.get("title") or "",
                  "section": _section_of(rec, loc or locs_old.get(rid)),
                  "where": ("%s:%d" % loc) if loc else rec.get("file") or "",
                  "old_colour": col_old.get(rid), "new_colour": col_new.get(rid)})
        out.append(c)
    return out


def registry_changes(ws, since, until, notes, ref="HEAD"):
    """One entry per home with a namespace: ``{"instance", "role", "ns", "home", "ref",
    "base", "head", "commits", "changes", "_statuses"}`` (``_statuses``: the head's
    ``{id: status}``, for the ready section; not printed). A home that cannot be read is
    named in ``notes``."""
    out = []
    for name, inst in _homes(ws):
        ns, home, role = inst.get("ns"), inst.get("home"), inst.get("role")
        if not ns:
            continue
        if not home or not os.path.exists(os.path.join(home, ".git")):
            notes.append("%s: home %s is not a git checkout here; its registry changes not "
                         "gathered" % (name, home))
            continue
        cfg = _read_cfg(home)
        macros = note_macros(cfg) if role == "author" else None
        tmp = tempfile.mkdtemp(prefix="weekly-review-")
        try:
            base, head = _bounds(home, ref, since, until)
            if not base and head and _is_shallow(home):
                notes.append("%s: a shallow clone with no commit before %s here: every record "
                             "at the window's head counts as added" % (name, since))
            paths = _record_paths(cfg) + (_tex_globs(cfg) + [COLOURS_VIEW]
                                          if role == "author" else [])
            commits = _commits(home, ref, since, until, paths) if head else []
            old_snap = _snapshot(home, base, cfg, os.path.join(tmp, "old"))
            new_snap = _snapshot(home, head, cfg, os.path.join(tmp, "new"))
            changes = []
            new = {}
            if commits:
                old = _load_records(ns, old_snap, cfg, macros)
                new = _load_records(ns, new_snap, cfg, macros)
                if role == "author":
                    changes = _paper_changes(ns, old, new, old_snap, new_snap, cfg)
                else:
                    for c in diff_records(old, new):
                        rec = new.get(c["id"]) or old.get(c["id"])
                        c.update({"qid": "%s:%s" % (ns, c["id"]), "title": rec.get("title") or "",
                                  "section": None, "where": rec.get("file") or ""})
                        changes.append(c)
            elif head:
                new = _load_records(ns, new_snap, cfg)
            branch = ""
            try:
                branch = _git(home, "rev-parse", "--abbrev-ref", ref)
            except RuntimeError:
                pass
            out.append({"instance": name, "role": role, "ns": ns, "home": home, "ref": ref,
                        "branch": branch, "base": base, "head": head, "commits": commits,
                        "changes": changes,
                        "_statuses": {k: v["status"] for k, v in new.items()}})
        except Exception as exc:            # noqa: BLE001 -- named, never dropped
            notes.append("%s: registry changes not gathered (%s)" % (name, exc))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return out


# ------------------------------------------------------------------------ 2. ready to read

def reviews_root(ws):
    """The first Expert home's ``paths.reviews`` (default ``reviews``), or None."""
    for _name, inst in _homes(ws, roles=("expert",)):
        home = inst.get("home")
        if not home:
            continue
        rel = ((_read_cfg(home).get("paths") or {}).get("reviews")) or "reviews"
        if isinstance(rel, list):
            rel = rel[0]
        root = os.path.join(home, rel)
        if os.path.isdir(root):
            return root
    return None


def review_pass(root, qid, until):
    """``{"pass", "decision", "outcome"}`` of the latest decided pass of ``qid`` dated on or
    before ``until``, or None."""
    stale = _reg("core.stale")
    if not root:
        return None
    d = stale.subject_dir(root, qid)
    if not d.is_dir():
        return None
    names = sorted(n for n in os.listdir(d) if n[:1] not in ("_", ".")
                   and (d / n / "decision.md").is_file() and n[:10] <= until)
    if not names:
        return None
    p = d / names[-1] / "decision.md"
    try:
        m = stale.RE_RECORDED.search(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        m = None
    return {"pass": names[-1], "decision": str(p).replace(os.sep, "/"),
            "outcome": m.group(1).lower() if m else None}


def _attempt_meta(home, path, commits):
    fm = _reg("core.fm")
    for c in commits:
        try:
            text = _git(home, "show", "%s:%s" % (c, path))
        except RuntimeError:
            continue
        try:
            meta, _body = fm.split_document(text, path)
            return meta
        except Exception:                   # noqa: BLE001 -- unreadable frontmatter
            return {}
    return None


def new_attempts(ws, since, until, statuses, notes, ref="HEAD"):
    """Proof attempts added in the window in every Researcher home: ``{"instance", "path",
    "object", "outcome", "date", "commit", "inputs": [{"ref", "status"}]}``."""
    out = []
    for name, inst in _homes(ws, roles=("researcher",)):
        home = inst.get("home")
        if not home or not os.path.exists(os.path.join(home, ".git")):
            notes.append("%s: home %s is not a git checkout here; its proof attempts not "
                         "gathered" % (name, home))
            continue
        try:
            log = _git(home, "log", "--diff-filter=A", "--name-only",
                       "--format=%x1e%H%x1f%ct", "--since=" + _since_arg(since),
                       "--until=" + _until_arg(until), ref, "--", "proofs")
            _base, head = _bounds(home, ref, since, until)
        except RuntimeError as exc:
            notes.append("%s: proof attempts not gathered (%s)" % (name, exc))
            continue
        for chunk in log.split("\x1e"):
            lines = [x for x in chunk.strip().splitlines() if x.strip()]
            if not lines:
                continue
            sha, ts = (lines[0].split("\x1f") + [""])[:2]
            date = _utc_date(ts) or ""
            for path in lines[1:]:
                m = RE_ATTEMPT.match(path.strip())
                if not m:
                    continue
                meta = _attempt_meta(home, path.strip(), [head, sha]) or {}
                obj = str(meta.get("object") or "")
                if obj and not RE_QID.match(obj):
                    obj = "%s:%s" % (inst.get("ns"), obj)
                inputs = meta.get("inputs") or []
                if not isinstance(inputs, list):
                    inputs = [inputs]
                rows = []
                for ref_ in inputs:
                    ref_ = str(ref_)
                    q = RE_QID.match(ref_)
                    if q and q.group(1) in statuses:
                        st = statuses[q.group(1)].get(q.group(2))
                    else:                   # a bare id: the home's own namespace's
                        st = statuses.get(inst.get("ns"), {}).get(ref_.strip())
                    rows.append({"ref": ref_, "status": st or None})
                out.append({"instance": name, "path": path.strip(),
                            "object": obj or "%s:%s" % (inst.get("ns"), m.group(1)),
                            "outcome": str(meta.get("outcome") or "") or None,
                            "date": date, "commit": sha, "inputs": rows})
    return sorted(out, key=lambda a: (a["date"], a["path"]))


def ready_to_read(ws, changes, since, until, notes, ref="HEAD"):
    """``{"statements", "added_proved", "attempts"}``: the statements of ``changes``
    (``registry_changes``) that moved to proved or proved-modulo in the window, apart from
    those added already proved (``added_proved``), each with its latest review pass (its
    date flagged when it is older than ``since``); and the new proof attempts."""
    root = reviews_root(ws)
    if root is None:
        notes.append("review passes: no Expert library reviews/ folder here")
    moved, added = [], []
    for h in changes:
        for c in h["changes"]:
            if c["new_status"] not in POSITIVE or c["old_status"] == c["new_status"]:
                continue
            row = {"qid": c["qid"], "instance": h["instance"], "title": c["title"],
                   "old_status": c["old_status"], "new_status": c["new_status"],
                   "where": c["where"], "pass": None, "decision": None, "outcome": None}
            row.update(review_pass(root, c["qid"], until) or {})
            row["pass_date"] = row["pass"][:10] if row["pass"] else None
            row["pass_before_window"] = bool(row["pass_date"]) and row["pass_date"] < since
            (added if c["old_status"] is None else moved).append(row)
    statuses = {h["ns"]: h.get("_statuses") or {} for h in changes}
    return {"statements": moved, "added_proved": added,
            "attempts": new_attempts(ws, since, until, statuses, notes, ref)}


# ---------------------------------------------------------------------------- 3. decisions

def _ticket_body(board, tid):
    import board as boardlib
    return boardlib.get_ticket(board, tid)[2]


def decisions_section(board, ws, notes, pending=None, reader=None):
    """``summarise_decisions`` of the board's pending decisions, or None (named in notes).
    Each experiment decision on a ticket gets ``refutes``: its "what would refute it" line,
    read from the ticket (at most ``REFUTES_CAP`` reads)."""
    if pending is None:
        import decisions as dc
        pending = dc.pending_decisions
    reader = reader or _ticket_body
    try:
        items = pending(board, workspace=ws)
    except Exception as exc:                # noqa: BLE001 -- named, never dropped
        notes.append("decisions: the board could not be read (%s)" % exc)
        return None
    out = summarise_decisions(items)
    exp = out["real"].get("experiment") or []
    read = 0
    for i in exp:
        i["refutes"] = None
        if i.get("source") == "packet":
            continue
        if read >= REFUTES_CAP:
            continue
        read += 1
        try:
            i["refutes"] = refutation_line(reader(board, i["id"]))
        except Exception as exc:            # noqa: BLE001
            notes.append("decisions: %s not read for what would refute it (%s)" % (i["id"], exc))
    if any(i.get("source") == "packet" for i in exp):
        notes.append("decisions: what would refute it is read from tickets only, not from "
                     "experiment packets")
    if sum(1 for i in exp if i.get("source") != "packet") > REFUTES_CAP:
        notes.append("decisions: what would refute it read for the first %d experiment "
                     "tickets only" % REFUTES_CAP)
    return out


# --------------------------------------------------------------------------- 4. merges

def _repos(ws, ws_path, notes):
    """``[(name, path)]``: the workspace's submodules (its .gitmodules), the workspace repo
    itself when it is one, then every instance home not already listed."""
    out, seen = [], set()
    root = os.path.dirname(os.path.abspath(ws_path)) if ws_path else None
    if root and os.path.isfile(os.path.join(root, ".gitmodules")):
        try:
            p = subprocess.run(["git", "config", "-f", os.path.join(root, ".gitmodules"),
                                "--get-regexp", r"^submodule\..*\.path$"], capture_output=True,
                               text=True, stdin=subprocess.DEVNULL, timeout=60)
            lines = p.stdout.splitlines()
        except (OSError, subprocess.SubprocessError) as exc:
            notes.append("merges: the workspace's submodules not read (%s)" % exc)
            lines = []
        for line in lines:
            rel = line.split(None, 1)[1].strip() if " " in line else ""
            if rel:
                out.append((rel, os.path.join(root, rel)))
    if root and os.path.exists(os.path.join(root, ".git")):
        out.append(("workspace", root))
    for path in [p for _n, p in out]:
        seen.add(os.path.realpath(path))
    for name, inst in _homes(ws):
        h = inst.get("home")
        if h and os.path.realpath(h) not in seen:
            seen.add(os.path.realpath(h))
            out.append((name, h))
    return out


def merges_waiting(ws, ws_path, today, notes):
    """Per repository, ``{"repo", "path", "unmerged", "tips", "branches"}``: its remote work
    branches not merged into origin/main (``branches``) and the tips of their stacks
    (``stack_tips``), as the last fetch left them."""
    out = []
    for name, path in _repos(ws, ws_path, notes):
        if not os.path.exists(os.path.join(path, ".git")):
            notes.append("merges: %s (%s) is not a git checkout here" % (name, path))
            continue
        try:
            _git(path, "rev-parse", "--verify", "-q", "refs/remotes/origin/main")
            text = _git(path, "for-each-ref", "--no-merged=refs/remotes/origin/main",
                        "--format=%(refname:lstrip=2)%1f%(objectname)%1f%(committerdate:unix)",
                        "refs/remotes/origin")
            rows = parse_refs(text, today)
            unique = {r["branch"]: set(_git(path, "rev-list", r["sha"], "--not",
                                            "refs/remotes/origin/main").split())
                      for r in rows}
        except RuntimeError as exc:
            notes.append("merges: %s not read (%s)" % (name, exc))
            continue
        out.append({"repo": name, "path": path, "unmerged": len(rows),
                    "tips": stack_tips(rows, unique), "branches": rows})
    notes.append("merges: the review state, the push gate and the strict gate of each tip are "
                 "not gathered (no cheap source here)")
    return out


# --------------------------------------------------------------------------- 5. problems

def default_tools():
    return {"audit": os.path.join(HERE, "audit.py"),
            "reading_list": os.path.join(REPO, "expert", "scripts", "reading_list.py")}


def _runner(ws_path):
    env = dict(os.environ)
    if ws_path:
        env["ACADEMY_WORKSPACE"] = os.path.abspath(ws_path)

    def run(argv, cwd=None):
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, stdin=subprocess.DEVNULL, timeout=600)
        return p.returncode, p.stdout, p.stderr
    return run


def _json_of(label, run, argv, notes, cwd=None):
    try:
        rc, out, err = run(argv, cwd=cwd)
    except (OSError, subprocess.SubprocessError) as exc:
        notes.append("%s: could not run (%s)" % (label, exc))
        return None
    if rc != 0:
        notes.append("%s: exit %d: %s" % (label, rc, (err or "").strip()[:300] or "no message"))
        return None
    try:
        return json.loads(out or "")
    except ValueError:
        notes.append("%s: printed no JSON" % label)
        return None


def gather_problems(ws, ws_path, notes, tools=None, run=None):
    """``{"audit", "reading_list", "stale"}``, each ``{"count", "top", ...}`` or None when
    not gathered (the reason in ``notes``)."""
    tools = tools or default_tools()
    run = run or _runner(ws_path)
    wsarg = ["--workspace", os.path.abspath(ws_path)] if ws_path else []
    out = {"audit": None, "reading_list": None, "stale": None}
    path = tools.get("audit")
    if path and os.path.isfile(path):
        d = _json_of("audit", run, [sys.executable, path, "--json"] + wsarg, notes)
        if isinstance(d, dict):
            f = d.get("findings") or []
            out["audit"] = {"count": len(f), "counts": d.get("counts") or {},
                            "top": [{k: x.get(k) for k in ("class", "id", "detail", "fix")}
                                    for x in f[:TOP]]}
            for p in d.get("not_audited") or []:
                notes.append("audit: not audited: %s" % p)
    else:
        notes.append("audit: the consistency audit (%s) is not present in this checkout"
                     % os.path.relpath(path or "audit.py", REPO))
    path = tools.get("reading_list")
    if path and os.path.isfile(path):
        d = _json_of("reading_list", run, [sys.executable, path, "--json"] + wsarg, notes)
        if isinstance(d, dict):
            rows = d.get("rows") or []
            keep = ("ticket", "key", "title", "read", "for")
            out["reading_list"] = {"count": len(rows),
                                   "top": [{k: r.get(k) for k in keep if k in r}
                                           for r in rows[:TOP] if isinstance(r, dict)],
                                   "could_not_read": len(d.get("could_not_read") or [])}
    else:
        notes.append("reading_list: the reading list (%s) is not present in this checkout"
                     % os.path.relpath(path or "reading_list.py", REPO))
    reg = os.path.join(HERE, "registry.py")
    items, homes = [], 0
    for name, inst in _homes(ws):
        home = inst.get("home")
        if not inst.get("ns") and inst.get("role") != "author":
            continue
        if not home or not os.path.isdir(home):
            notes.append("stale: %s home %s missing" % (name, home))
            continue
        d = _json_of("stale (%s)" % name, run, [sys.executable, reg, "stale", "--json"],
                     notes, cwd=home)
        if isinstance(d, dict):
            homes += 1
            items += d.get("items") or []
            if d.get("board"):
                notes.append("stale (%s): %s" % (name, d["board"]))
    out["stale"] = {"count": len(items), "homes": homes,
                    "top": [{k: i.get(k) for k in ("kind", "qid", "status", "section")}
                            for i in items[:TOP]]}
    return out


def board_problems(board, since, until, notes, lister=None):
    """``ticket_problems`` of the board's non-terminal tickets (one listing), or None."""
    if lister is None:
        import board as boardlib
        lister = boardlib.list_tickets
    try:
        return ticket_problems(list(lister(board)), since, until)
    except Exception as exc:                # noqa: BLE001 -- named, never dropped
        notes.append("problems: the board's tickets could not be listed (%s)" % exc)
        return None


def error_classes(ws, since, until, notes, lister=None):
    """The error-class issues of workspace.json's ``errors.repo`` (#95): ``{"repo", "open",
    "new": [{"number", "title", "state", "created"}]}`` (new: opened in the window), or None."""
    import error_ledger as el
    repo = el.errors_repo(ws)
    if not repo:
        notes.append("problems: error-class issues not gathered: workspace.json names no "
                     "errors.repo")
        return None
    if lister is None:
        import error_issues as ei

        def lister(r):
            return ei.list_classes(ei.transport(r))
    try:
        issues = list(lister(repo))
    except Exception as exc:                # noqa: BLE001
        notes.append("problems: error-class issues of %s not read (%s)" % (repo, exc))
        return None
    new = [{"number": i.get("number"), "title": i.get("title"), "state": i.get("state"),
            "created": str(i.get("created_at") or "")[:10]} for i in issues
           if _in_window(str(i.get("created_at") or "")[:10], since, until)]
    return {"repo": repo, "open": sum(1 for i in issues if i.get("state") == "open"),
            "new": sorted(new, key=lambda r: -(r["number"] or 0))}


# --------------------------------------------------------------------------------- gather

def _strip_private(x):
    if isinstance(x, dict):
        return {k: _strip_private(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, list):
        return [_strip_private(v) for v in x]
    return x


def gather(ws, ws_path, since, until, today=None, board=None, problems=True, ref="HEAD",
           tools=None):
    """The whole record (see the module docstring)."""
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    notes = []
    changes = registry_changes(ws, since, until, notes, ref)
    ready = ready_to_read(ws, changes, since, until, notes, ref)
    if board is None:
        try:
            import board as boardlib
            board = boardlib.resolve_store(None, ws_path)
        except Exception as exc:            # noqa: BLE001
            notes.append("decisions: the board could not be opened (%s)" % exc)
    dec = decisions_section(board, ws, notes) if board is not None else None
    if dec is not None:
        dec["as_of"] = today.isoformat()
    merges = merges_waiting(ws, ws_path, today, notes)
    if problems:
        prob = gather_problems(ws, ws_path, notes, tools=tools)
    else:
        prob = {"audit": None, "reading_list": None, "stale": None}
        notes.append("problems not gathered (--no-problems)")
    # the board's tickets and the error classes are one listing each: always gathered
    prob["tickets"] = board_problems(board, since, until, notes) if board is not None else None
    prob["errors"] = error_classes(ws, since, until, notes)
    notes.extend(ALWAYS_NOT_GATHERED)
    paper = [h for h in changes if h["role"] == "author"]
    data = {
        "window": {"since": since, "until": until},
        "generated": today.isoformat(),
        "paper": paper,
        "registries": [h for h in changes if h["role"] != "author"],
        "ready": ready,
        "decisions": dec,
        "merges": merges,
        "problems": prob,
        "not_gathered": notes,
    }
    tk = prob["tickets"] or {}
    data["counts"] = {
        "paper_changes": sum(len(h["changes"]) for h in paper),
        "paper_commits": sum(len(h["commits"]) for h in paper),
        "registry_changes": sum(len(h["changes"]) for h in data["registries"]),
        "ready_statements": len(ready["statements"]),
        "ready_added_proved": len(ready["added_proved"]),
        "new_attempts": len(ready["attempts"]),
        "decisions": dec["total"] if dec else None,
        "decisions_routine": dec["routine"] if dec else None,
        "decisions_real": (dec["total"] - dec["routine"]) if dec else None,
        "merges_unmerged": sum(r["unmerged"] for r in merges),
        "merge_tips": sum(len(r["tips"]) for r in merges),
        "audit_findings": (prob["audit"] or {}).get("count"),
        "reading_list": (prob["reading_list"] or {}).get("count"),
        "stale": (prob["stale"] or {}).get("count"),
        "delivered_no_result": len(tk["delivered_no_result"]) if tk else None,
        "parked": tk["parked"]["count"] if tk else None,
        "error_classes_new": len(prob["errors"]["new"]) if prob["errors"] else None,
        "not_gathered": len(notes),
    }
    return _strip_private(data)


# --------------------------------------------------------------------------------- render

def _clip(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 3] + "..."


def _short(sha):
    return (sha or "")[:10] or "-"


def _change_cell(c):
    out = []
    for x in c["changes"]:
        if x == "label-removed":
            out.append("label removed from tex")
        elif x == "recoloured":
            out.append("recoloured %s -> %s" % (c.get("old_colour") or "?",
                                                c.get("new_colour") or "?"))
        else:
            out.append(x)
    return ", ".join(out)


def _status_cell(c):
    if set(c["changes"]) & {"status", "added", "removed"}:
        return "%s -> %s" % (c["old_status"] or "(none)", c["new_status"] or "(none)")
    return c["new_status"] or "-"


def _dash(v):
    return "-" if v is None else v


def _pass_cells(r):
    date = r.get("pass_date")
    if not date:
        return "none found", "-", r.get("outcome") or "-"
    return (r["pass"], date + (" (before the window)" if r.get("pass_before_window") else ""),
            r.get("outcome") or "-")


def render(data):
    w = data["window"]
    L = ["# Weekly review, %s to %s" % (w["since"], w["until"]), ""]
    c = data["counts"]
    L.append("Paper: %d change(s) in %d commit(s); ready to read: %d statement(s) moved to "
             "proved or proved-modulo, %d added already so, %d new attempt(s); decisions: %s "
             "(%s real); merges waiting: %d stack tip(s) of %d unmerged branch(es); not "
             "gathered: %d."
             % (c["paper_changes"], c["paper_commits"], c["ready_statements"],
                c["ready_added_proved"], c["new_attempts"], _dash(c.get("decisions")),
                _dash(c.get("decisions_real")), c["merge_tips"], c["merges_unmerged"],
                c["not_gathered"]))
    L += ["", "## 1. Paper changes by section", ""]
    if not data["paper"]:
        L.append("No Author home was read.")
    for h in data["paper"]:
        L.append("### %s (`%s` at %s, %s..%s)" % (h["instance"], h["branch"] or h["ref"],
                                                   _short(h["head"]), _short(h["base"]),
                                                   _short(h["head"])))
        L.append("")
        L.append("%d commit(s) on the tex files, the registry and the statements view. "
                 "\"note-only\": only margin notes or comments changed."
                 % len(h["commits"]))
        if not h["changes"]:
            L += ["", "No statement added, reworded, recoloured or with a status change.", ""]
            continue
        by = collections.OrderedDict()
        for ch in sorted(h["changes"], key=lambda x: (x["section"] or "", x["id"])):
            by.setdefault(ch["section"] or "(no section)", []).append(ch)
        for sec, rows in by.items():
            L += ["", "**%s**" % sec, "", "| statement | change | status | where |",
                  "|---|---|---|---|"]
            for ch in rows:
                L.append("| `%s` | %s | %s | %s |" % (ch["qid"], _change_cell(ch),
                                                     _status_cell(ch), ch["where"] or "-"))
        L.append("")
    others = [(h, ch) for h in data.get("registries") or [] for ch in h["changes"]
              if "status" in ch["changes"] or "added" in ch["changes"]]
    if others:
        L += ["**Other registries: status changes and new records**", "",
              "| statement | change | status |", "|---|---|---|"]
        for _h, ch in others:
            L.append("| `%s` | %s | %s |" % (ch["qid"], ", ".join(ch["changes"]), _status_cell(ch)))
        L.append("")
    L += ["## 2. Ready to read", ""]
    st = data["ready"]["statements"]
    if st:
        L += ["| statement | status | pass | pass date | outcome |", "|---|---|---|---|---|"]
        for r in st:
            L.append("| `%s` | %s -> %s | %s | %s | %s |" % ((r["qid"], r["old_status"],
                                                             r["new_status"]) + _pass_cells(r)))
    else:
        L.append("No statement moved to proved or proved-modulo.")
    added = data["ready"].get("added_proved") or []
    if added:
        L += ["", "Added already proved or proved-modulo (new records, not transitions):", "",
              "| statement | status | pass | pass date | outcome |", "|---|---|---|---|---|"]
        for r in added:
            L.append("| `%s` | %s | %s | %s | %s |" % ((r["qid"], r["new_status"]) + _pass_cells(r)))
    L += ["", "New proof attempts:", ""]
    at = data["ready"]["attempts"]
    if not at:
        L.append("None.")
    for a in at:
        ins = ", ".join("%s (%s)" % (_clip(i["ref"], 80), i["status"] or "?")
                        for i in a["inputs"]) or "none"
        L.append("- `%s` %s (%s, %s): inputs %s" % (a["object"], a["path"], a["outcome"] or "?",
                                                    a["date"], ins))
    L += ["", "## 3. Decisions", ""]
    d = data["decisions"]
    if d is None:
        L.append("Not gathered (see below).")
    else:
        L.append("Pending decisions as of %s, not as of --until: %d, %d routine (counted only). "
                 "By kind: %s." % (d.get("as_of") or data["generated"], d["total"], d["routine"],
                                   ", ".join("%s %d" % kv for kv in d["by_kind"].items())
                                   or "none"))
        for g, head in GROUPS:
            rows = d["real"].get(g)
            if not rows:
                continue
            L += ["", "**%s**" % head, ""]
            for i in rows:
                L.append("- `%s` %s: %s" % (i["id"], i.get("instance") or "-",
                                            _clip(i.get("question") or i.get("title") or "", 200)))
                if g == "experiment":
                    L.append("  - what would refute it: %s" % (
                        _clip(i["refutes"], 200) if i.get("refutes") else "not stated"))
    L += ["", "## 4. Merges waiting", ""]
    tips = [(r, t) for r in data["merges"] for t in r["tips"]]
    if tips:
        L += ["| repo | stack tip | tip | depth | ahead | age (days) |",
              "|---|---|---|---|---|---|"]
        for r, t in tips:
            L.append("| %s | `%s` | %s | %d | %d | %s |" % (
                r["repo"], t["branch"], _short(t["sha"]), t["depth"], t["ahead"],
                _dash(t["age_days"])))
        L += ["", "Depth: the unmerged branches of the stack, the tip included; ahead: its "
              "commits not on origin/main. As of each checkout's last fetch; nothing was "
              "fetched."]
    else:
        L.append("No unmerged work branch (as of the last fetch).")
    L += ["", "## 5. Problems", ""]
    p = data["problems"]
    for key, head in (("audit", "Consistency audit"), ("reading_list", "Reading list"),
                      ("stale", "Stale statements (registry.py stale)")):
        v = p.get(key)
        if v is None:
            L.append("- %s: not gathered." % head)
            continue
        L.append("- %s: %d." % (head, v["count"]))
        for row in v["top"]:
            L.append("  - " + "; ".join(_clip(x, 120) for x in row.values()
                                        if x not in (None, "")))
    tk = p.get("tickets")
    if tk is None:
        L.append("- Board tickets: not gathered.")
    else:
        L.append("- Delivered with an empty result line: %d." % len(tk["delivered_no_result"]))
        for r in tk["delivered_no_result"][:TOP]:
            L.append("  - %s %s: %s" % (r["id"], r.get("to") or "-", _clip(r.get("title") or "", 100)))
        pk = tk["parked"]
        L.append("- Parked (blocked): %d, %d updated in the window; waiting on %s." % (
            pk["count"], pk["new"], ", ".join("%s %d" % kv for kv in pk["by_wait"].items())
            or "nothing"))
        for r in pk["top"]:
            L.append("  - %s %s (%s): %s" % (r["id"], r.get("to") or "-",
                                             ", ".join(r.get("waiting_on") or []) or "-",
                                             _clip(r.get("title") or "", 100)))
    er = p.get("errors")
    if er is None:
        L.append("- Error-class issues: not gathered.")
    else:
        L.append("- Error-class issues of %s: %d open, %d new in the window." % (
            er["repo"], er["open"], len(er["new"])))
        for r in er["new"][:TOP]:
            L.append("  - #%s (%s) %s" % (r["number"], r["state"], _clip(r["title"] or "", 100)))
    L += ["", "## Not gathered", ""]
    L += ["- " + n for n in data["not_gathered"]] or ["Nothing: every source was read."]
    L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------------------------ CLI

def _workspace_file(explicit):
    for c in (explicit, os.environ.get("ACADEMY_WORKSPACE"),
              os.path.join(ac.repo_root(), "workspace.json"),
              os.path.join(ac.repo_root(), os.pardir, "workspace.json")):
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="weekly_review.py", description=__doc__.split("\n")[0])
    ap.add_argument("--since"); ap.add_argument("--until")
    ap.add_argument("--ref", default="HEAD", help="the ref of each home's history (default HEAD)")
    ap.add_argument("--json", action="store_true", help="print the record as JSON")
    ap.add_argument("--out", help="also write the markdown to this file")
    ap.add_argument("--no-problems", action="store_true", help="skip section 5's tools")
    ap.add_argument("--workspace"); ap.add_argument("--board")
    a = ap.parse_args(argv)
    try:
        since, until = window(a.since, a.until)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    try:
        ws_path = _workspace_file(a.workspace)
        ws = ac.load_workspace(ws_path)
    except ac.AcademyError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    board = None
    if a.board:
        import board as boardlib
        board = boardlib.resolve_store(a.board, ws_path)
    data = gather(ws, ws_path, since, until, board=board, problems=not a.no_problems, ref=a.ref)
    md = render(data)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(md)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.json:
        print(json.dumps(data, indent=1, ensure_ascii=False, default=str))
    elif a.out:
        print("wrote %s (%s)" % (a.out, ", ".join("%s %s" % kv for kv in data["counts"].items())))
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
