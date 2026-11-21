#!/usr/bin/env python3
"""weekly_review.py -- one week of the academy on one page, for /academy:weekly-review (#107).

    py weekly_review.py [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--ref REF] [--json]
                        [--out FILE] [--no-problems] [--workspace W] [--board B]

Gathers the window (``--since``, default seven days before ``--until``; ``--until``,
default today; both days included, UTC) into one structured record and renders it as
markdown (stdout, or ``--out FILE``; ``--json`` prints the record instead). Sections:

1. **Paper changes by section**: per Author home, the commits of the window on its tex
   files and its registry, and the statements added, removed, reworded (the registry's
   statement hash changed) or with a status change, old and new status, file:line of the
   label. The registry is read through its own profile (``registry.profiles.store_for``)
   from a snapshot of the home at the last commit before the window and the last commit
   in it (``git archive`` of the registry, tex and config paths into a temp directory);
   every other home with a namespace is compared the same way.
2. **Ready to read**: statements that became proved or proved-modulo in the window, with
   the latest decided review pass (the Expert library's ``reviews/<ns>/<id>/<pass>/
   decision.md``) and its recorded outcome; proof attempts added in Researcher homes
   (``proofs/<object>/attempt-<n>.md``) with their declared inputs and each input's status.
3. **Decisions**: ``decisions.pending_decisions``, counted by kind; the routine kinds
   (``ROUTINE_TICKET_KINDS``, ``ROUTINE_PACKET_KINDS``, after #86) are only counted, the
   rest listed by group (experiments, proofs, rulings, notation and structure, sources).
4. **Merges waiting**: per repository (the workspace's submodules and every instance home),
   the remote work branches ``<YYYY-MM-DD>/<topic>/<role>`` not merged into ``origin/main``,
   tip and age, as the last fetch left them (nothing is fetched).
5. **Problems**: count and top rows of the consistency audit (``audit.py --json``), the
   reading list (``expert/scripts/reading_list.py --json``) and ``registry.py stale --json``
   per home, each run only when its script exists. Anything not gathered (a missing tool, a
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
#: ticket and packet kinds whose pending decisions are routine (#86): counted, not listed
ROUTINE_TICKET_KINDS = frozenset({"verify", "review-experiment", "cite", "code", "notation",
                                  "note", "apply"})
ROUTINE_PACKET_KINDS = frozenset({"verification", "citation", "experiment-review", "usage"})
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
    """The changed records between two ``{id: {"status", "hash", ...}}`` maps, sorted by id:
    ``{"id", "changes": [added|removed|reworded|status], "old_status", "new_status",
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
                changes.append("reworded")
            if (o.get("status") or "") != (n.get("status") or ""):
                changes.append("status")
            if not changes:
                continue
        out.append({"id": rid, "changes": changes,
                    "old_status": (o or {}).get("status") if o else None,
                    "new_status": (n or {}).get("status") if n else None,
                    "old_hash": (o or {}).get("hash"), "new_hash": (n or {}).get("hash")})
    return out


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
    (``origin/<branch> US sha US committer date``), work branches only."""
    rows = []
    for line in text.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        name, sha, date = parts
        branch = name.split("/", 1)[1] if "/" in name else name
        if not RE_WORK_BRANCH.match(branch):
            continue
        try:
            age = (today - datetime.date.fromisoformat(date[:10])).days
        except ValueError:
            age = None
        rows.append({"branch": branch, "sha": sha, "date": date[:10], "age_days": age})
    return sorted(rows, key=lambda r: (r["date"], r["branch"]))


# ------------------------------------------------------------------------------- git, read

def _git(repo, *args, binary=False):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, timeout=300,
                       stdin=subprocess.DEVNULL,
                       env=dict(os.environ, GIT_PAGER="cat", GIT_TERMINAL_PROMPT="0"))
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
    out = _git(repo, "log", "--format=%H%x1f%cs%x1f%s", "--since=" + _since_arg(since),
               "--until=" + _until_arg(until), ref, "--", *paths)
    rows = []
    for line in out.splitlines():
        sha, date, subject = (line.split("\x1f") + ["", ""])[:3]
        rows.append({"sha": sha, "date": date, "subject": subject})
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


def _snapshot_paths(cfg):
    """The top-level paths a registry store needs from a home (config, records, tex)."""
    tops = {".claude/academy.json", "sections"} | set(_record_paths(cfg))
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
        try:
            tar.extractall(dest, filter="data")
        except TypeError:                   # a Python without extraction filters
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


def _load_records(ns, snap, cfg):
    """``{id: {"status", "hash", "title", "file", "where_field"}}`` of the registry in the
    snapshot ``snap``, read through its profile."""
    store_for = _reg("profiles").store_for
    if not os.path.isfile(os.path.join(snap, ".claude", "academy.json")):
        return {}
    st = store_for(ns, snap)
    out = {}
    for rid, r in st.records.items():
        out[rid] = {"status": r.status or "", "hash": st.statement_hash(rid),
                    "title": r.title, "where_field": str(r.fields.get("where") or ""),
                    "file": os.path.relpath(r.file, snap).replace(os.sep, "/")
                    if r.file else ""}
    return out


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
        if not home or not os.path.isdir(os.path.join(home, ".git")) and \
                not os.path.isfile(os.path.join(home, ".git")):
            notes.append("%s: home %s is not a git checkout here; its registry changes not "
                         "gathered" % (name, home))
            continue
        cfg = _read_cfg(home)
        tmp = tempfile.mkdtemp(prefix="weekly-review-")
        try:
            base, head = _bounds(home, ref, since, until)
            paths = _record_paths(cfg) + (_tex_globs(cfg) if role == "author" else [])
            commits = _commits(home, ref, since, until, paths) if head else []
            old_snap = _snapshot(home, base, cfg, os.path.join(tmp, "old"))
            new_snap = _snapshot(home, head, cfg, os.path.join(tmp, "new"))
            changes = []
            new = {}
            if commits:
                old = _load_records(ns, old_snap, cfg)
                new = _load_records(ns, new_snap, cfg)
                locs_new = label_lines(_texts(new_snap, cfg)) if role == "author" else {}
                locs_old = label_lines(_texts(old_snap, cfg)) if role == "author" else {}
                for c in diff_records(old, new):
                    rec = new.get(c["id"]) or old.get(c["id"])
                    loc = locs_new.get(c["id"]) or locs_old.get(c["id"])
                    c.update({"qid": "%s:%s" % (ns, c["id"]), "title": rec.get("title") or "",
                              "section": _section_of(rec, loc) if role == "author" else None,
                              "where": ("%s:%d" % loc) if loc else rec.get("file") or ""})
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
                       "--format=%x1e%H%x1f%cs", "--since=" + _since_arg(since),
                       "--until=" + _until_arg(until), ref, "--", "proofs")
            _base, head = _bounds(home, ref, since, until)
        except RuntimeError as exc:
            notes.append("%s: proof attempts not gathered (%s)" % (name, exc))
            continue
        for chunk in log.split("\x1e"):
            lines = [x for x in chunk.strip().splitlines() if x.strip()]
            if not lines:
                continue
            sha, date = (lines[0].split("\x1f") + [""])[:2]
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
                    st = statuses.get(q.group(1), {}).get(q.group(2)) if q else None
                    rows.append({"ref": ref_, "status": st or None})
                out.append({"instance": name, "path": path.strip(),
                            "object": obj or "%s:%s" % (inst.get("ns"), m.group(1)),
                            "outcome": str(meta.get("outcome") or "") or None,
                            "date": date, "commit": sha, "inputs": rows})
    return sorted(out, key=lambda a: (a["date"], a["path"]))


def ready_to_read(ws, changes, since, until, notes, ref="HEAD"):
    """``{"statements": [...], "attempts": [...]}``: the statements of ``changes``
    (``registry_changes``) that became proved or proved-modulo, with their review pass,
    and the new proof attempts."""
    root = reviews_root(ws)
    if root is None:
        notes.append("review passes: no Expert library reviews/ folder here")
    rows = []
    for h in changes:
        for c in h["changes"]:
            if c["new_status"] in POSITIVE and c["old_status"] != c["new_status"]:
                row = {"qid": c["qid"], "instance": h["instance"], "title": c["title"],
                       "old_status": c["old_status"], "new_status": c["new_status"],
                       "where": c["where"], "pass": None, "decision": None, "outcome": None}
                row.update(review_pass(root, c["qid"], until) or {})
                rows.append(row)
    statuses = {h["ns"]: h.get("_statuses") or {} for h in changes}
    return {"statements": rows,
            "attempts": new_attempts(ws, since, until, statuses, notes, ref)}


# ---------------------------------------------------------------------------- 3. decisions

def decisions_section(board, ws, notes, pending=None):
    """``summarise_decisions`` of the board's pending decisions, or None (named in notes)."""
    if pending is None:
        import decisions as dc
        pending = dc.pending_decisions
    try:
        items = pending(board, workspace=ws)
    except Exception as exc:                # noqa: BLE001 -- named, never dropped
        notes.append("decisions: the board could not be read (%s)" % exc)
        return None
    return summarise_decisions(items)


# --------------------------------------------------------------------------- 4. merges

def _repos(ws, ws_path):
    """``[(name, path)]``: the workspace's submodules (its .gitmodules), the workspace repo
    itself when it is one, then every instance home not already listed."""
    out, seen = [], set()
    root = os.path.dirname(os.path.abspath(ws_path)) if ws_path else None
    if root and os.path.isfile(os.path.join(root, ".gitmodules")):
        p = subprocess.run(["git", "config", "-f", os.path.join(root, ".gitmodules"),
                            "--get-regexp", r"^submodule\..*\.path$"], capture_output=True,
                           text=True, stdin=subprocess.DEVNULL)
        for line in p.stdout.splitlines():
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
    """Per repository, ``{"repo", "path", "branches": [{"branch", "sha", "date",
    "age_days"}]}``: its remote work branches not merged into origin/main."""
    out = []
    for name, path in _repos(ws, ws_path):
        if not os.path.exists(os.path.join(path, ".git")):
            notes.append("merges: %s (%s) is not a git checkout here" % (name, path))
            continue
        try:
            _git(path, "rev-parse", "--verify", "-q", "refs/remotes/origin/main")
        except RuntimeError:
            notes.append("merges: %s has no origin/main" % name)
            continue
        try:
            text = _git(path, "for-each-ref", "--no-merged=refs/remotes/origin/main",
                        "--format=%(refname:lstrip=2)%1f%(objectname)%1f%(committerdate:short)",
                        "refs/remotes/origin")
        except RuntimeError as exc:
            notes.append("merges: %s not read (%s)" % (name, exc))
            continue
        out.append({"repo": name, "path": path, "branches": parse_refs(text, today)})
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
            out["reading_list"] = {"count": len(rows), "top": rows[:TOP],
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
    merges = merges_waiting(ws, ws_path, today, notes)
    if problems:
        prob = gather_problems(ws, ws_path, notes, tools=tools)
    else:
        prob = {"audit": None, "reading_list": None, "stale": None}
        notes.append("problems not gathered (--no-problems)")
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
    data["counts"] = {
        "paper_changes": sum(len(h["changes"]) for h in paper),
        "paper_commits": sum(len(h["commits"]) for h in paper),
        "registry_changes": sum(len(h["changes"]) for h in data["registries"]),
        "ready_statements": len(ready["statements"]),
        "new_attempts": len(ready["attempts"]),
        "decisions": dec["total"] if dec else None,
        "decisions_routine": dec["routine"] if dec else None,
        "decisions_real": (dec["total"] - dec["routine"]) if dec else None,
        "merges_waiting": sum(len(r["branches"]) for r in merges),
        "audit_findings": (prob["audit"] or {}).get("count"),
        "reading_list": (prob["reading_list"] or {}).get("count"),
        "stale": (prob["stale"] or {}).get("count"),
        "not_gathered": len(notes),
    }
    return _strip_private(data)


# --------------------------------------------------------------------------------- render

def _short(sha):
    return (sha or "")[:10] or "-"


def _status_cell(c):
    if "status" in c["changes"] or "added" in c["changes"] or "removed" in c["changes"]:
        return "%s -> %s" % (c["old_status"] or "(none)", c["new_status"] or "(none)")
    return c["new_status"] or "-"


def render(data):
    w = data["window"]
    L = ["# Weekly review, %s to %s" % (w["since"], w["until"]), ""]
    c = data["counts"]
    L.append("Paper: %d change(s) in %d commit(s); ready to read: %d statement(s), %d new "
             "attempt(s); decisions: %s (%s real); merges waiting: %d; not gathered: %d."
             % (c["paper_changes"], c["paper_commits"], c["ready_statements"],
                c["new_attempts"], "-" if c["decisions"] is None else c["decisions"],
                "-" if c["decisions_real"] is None else c["decisions_real"],
                c["merges_waiting"], c["not_gathered"]))
    L += ["", "## 1. Paper changes by section", ""]
    if not data["paper"]:
        L.append("No Author home was read.")
    for h in data["paper"]:
        L.append("### %s (`%s` at %s, %s..%s)" % (h["instance"], h["branch"] or h["ref"],
                                                   _short(h["head"]), _short(h["base"]),
                                                   _short(h["head"])))
        L.append("")
        L.append("%d commit(s) on the tex files and the registry." % len(h["commits"]))
        if not h["changes"]:
            L += ["", "No statement added, reworded or with a status change.", ""]
            continue
        by = collections.OrderedDict()
        for ch in sorted(h["changes"], key=lambda x: (x["section"] or "", x["id"])):
            by.setdefault(ch["section"] or "(no section)", []).append(ch)
        for sec, rows in by.items():
            L += ["", "**%s**" % sec, "", "| statement | change | status | where |",
                  "|---|---|---|---|"]
            for ch in rows:
                L.append("| `%s` | %s | %s | %s |" % (ch["qid"], ", ".join(ch["changes"]),
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
        L += ["| statement | status | pass | outcome |", "|---|---|---|---|"]
        for r in st:
            L.append("| `%s` | %s -> %s | %s | %s |" % (
                r["qid"], r["old_status"] or "(new)", r["new_status"], r["pass"] or "none found",
                r["outcome"] or "-"))
    else:
        L.append("No statement became proved or proved-modulo.")
    L += ["", "New proof attempts:", ""]
    at = data["ready"]["attempts"]
    if not at:
        L.append("None.")
    for a in at:
        ins = ", ".join("%s (%s)" % (i["ref"], i["status"] or "?") for i in a["inputs"]) or "none"
        L.append("- `%s` %s (%s, %s): inputs %s" % (a["object"], a["path"], a["outcome"] or "?",
                                                    a["date"], ins))
    L += ["", "## 3. Decisions", ""]
    d = data["decisions"]
    if d is None:
        L.append("Not gathered (see below).")
    else:
        L.append("%d pending, %d routine (counted only). By kind: %s." % (
            d["total"], d["routine"],
            ", ".join("%s %d" % kv for kv in d["by_kind"].items()) or "none"))
        for g, head in GROUPS:
            rows = d["real"].get(g)
            if not rows:
                continue
            L += ["", "**%s**" % head, ""]
            for i in rows:
                L.append("- `%s` %s: %s" % (i["id"], i.get("instance") or "-",
                                            (i.get("question") or i.get("title") or "")[:200]))
    L += ["", "## 4. Merges waiting", ""]
    any_b = False
    for r in data["merges"]:
        for b in r["branches"]:
            if not any_b:
                L += ["| repo | branch | tip | age (days) |", "|---|---|---|---|"]
                any_b = True
            L.append("| %s | `%s` | %s | %s |" % (r["repo"], b["branch"], _short(b["sha"]),
                                                  "-" if b["age_days"] is None else b["age_days"]))
    if not any_b:
        L.append("No unmerged work branch (as of the last fetch).")
    else:
        L += ["", "As of each checkout's last fetch; nothing was fetched."]
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
            L.append("  - " + "; ".join("%s" % x for x in row.values() if x not in (None, "")))
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
