"""pinned.py -- the paper's pinned statements: labels a CONFIRMED review has hashed.

    py pinned.py [--home H] [--library L] [--json]     list the pins of an Author home
    py pinned.py --labels                              the pinned labels only, one per line

A statement is **pinned** when the latest review pass of its subject in the library's
``reviews/<ns>/<id-slug>/<pass>/`` (the records ``land_verdict`` writes, one per run) has
at least one run and every landed run is CONFIRMED with a ``statement_hash``:

* ``verified`` -- runs A and B both CONFIRMED on the same hash (the two agreeing reviews);
* ``in-review`` -- run A CONFIRMED and B not landed yet (editing the statement now would
  void the pass).

A later pass that is not all CONFIRMED (a GAP, a DISPROVED) unpins: the statement is
then open to a repair, which is the Researcher's (roster-rules.md, "Role cut"). Passes
without a statement hash (out-of-protocol runs) are ignored.

What a pin protects is the statement's **environment**: from ``\\begin{<env>}`` to its
``\\end{<env>}`` around ``\\label{<label>}``. The proof body after it is free, since the
hash covers the statement only. ``pinned_guard.py`` (PreToolUse) refuses an edit that
changes a pinned environment; writer and editor briefs start from this script's output.

Only the human releases a pin: a label listed in ``<home>/.claude/pinned-release.txt``
(one label per line, ``#`` comments allowed) is not enforced. That file is edited by
hand; the guard refuses a tool edit of it.

The recorded hash was taken by the review-chair on the text it pinned (the registry's
statement, or the environment's text); ``current_hash`` here is the same computation
(sha256 of the whitespace-collapsed text, 16 hex digits) on the environment as it now
stands, so ``matches`` is a hint, not a gate: the guard compares the environment before
and after an edit, never against the recorded hash.

Exit codes: 0 pins listed (possibly none), 2 error.
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

import _author as au  # noqa: E402

ac = au.ac

RELEASE_REL = os.path.join(".claude", "pinned-release.txt")
RE_RUN_FILE = re.compile(r"^([AB])(?:-\d+)?\.md$")
RE_BEGIN_END = re.compile(r"\\(begin|end)\{([A-Za-z*]+)\}")
#: environments that never hold a statement of their own: the label inside them belongs
#: to an enclosing statement (or to no statement)
NON_STATEMENT = {"proof", "sketch", "conjectural", "meta", "added", "enumerate", "itemize",
                 "description", "equation", "equation*", "align", "align*", "gather",
                 "gather*", "multline", "multline*", "tikzcd", "cases", "array",
                 "tabular", "figure", "center", "minipage"}
DEFAULT_STATEMENT_ENVS = ("thm", "prop", "lem", "fact", "cor", "conj", "defn", "rmk", "ex",
                          "exc", "exer", "quest", "claim", "claim*", "problem", "case")


def statement_hash(text):
    """sha256 of the whitespace-collapsed text, first 16 hex digits (the registry's
    ``statement_hash_of``)."""
    norm = re.sub(r"\s+", " ", text or "").strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


# ----------------------------------------------------------------------------
# Where things are
# ----------------------------------------------------------------------------

def _workspace():
    try:
        return ac.load_workspace()
    except ac.AcademyError:
        return None


def library_home(ws=None, library=None):
    """The library (Expert) home: ``library``, ``$ACADEMY_LIBRARY``, or the first Expert
    instance of workspace.json."""
    if library:
        return os.path.abspath(library)
    if os.environ.get("ACADEMY_LIBRARY"):
        return os.path.abspath(os.environ["ACADEMY_LIBRARY"])
    ws = ws if ws is not None else _workspace()
    for _name, inst in sorted(((ws or {}).get("instances") or {}).items()):
        if inst.get("role") == "expert" and inst.get("home"):
            return os.path.abspath(inst["home"])
    return None


def reviews_root(library):
    """``<library>/<paths.reviews>`` (default ``reviews``)."""
    rel = "reviews"
    try:
        cfg = ac.load_config(library)
        val = (cfg.get("paths") or {}).get("reviews")
        if isinstance(val, list):
            val = val[0] if val else None
        rel = val or rel
    except (ac.AcademyError, OSError, ValueError):
        pass
    return os.path.join(library, rel)


def namespace(home, cfg=None, ws=None):
    """The claim namespace of an Author home: its config's ``ns``, else its workspace row's."""
    if cfg and cfg.get("ns"):
        return cfg["ns"]
    ws = ws if ws is not None else _workspace()
    if ws:
        name = ac.instance_for_home(ws, home)
        if name:
            return ws["instances"][name].get("ns") or None
    return None


def released(home):
    """Labels the human released from their pin (``.claude/pinned-release.txt``)."""
    path = os.path.join(home, RELEASE_REL)
    out = set()
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                lab = line.split("#", 1)[0].strip()
                if lab:
                    out.add(lab)
    except OSError:
        pass
    return out


# ----------------------------------------------------------------------------
# Pins from the review records
# ----------------------------------------------------------------------------

def _record(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            meta, _body = ac.read_frontmatter(fh.read())
    except (OSError, ac.AcademyError):
        return None
    return meta if isinstance(meta, dict) else None


def _verdict(v):
    s = " ".join(str(v or "").upper().split())
    for w in ("CONFIRMED", "PLAUSIBLE", "GAP", "DISPROVED"):
        if s == w or s.startswith(w + " ") or s.startswith(w + "(") or s.startswith(w + ","):
            return w
    return ""


def passes(reviews, ns):
    """``{subject: [(pass, [record, ...]), ...]}`` from ``reviews/<ns>/``; a record is
    ``{run, verdict, statement_hash, run_id, file}``."""
    out = {}
    root = os.path.join(reviews, ns)
    if not os.path.isdir(root):
        return out
    for slug in sorted(os.listdir(root)):
        sdir = os.path.join(root, slug)
        if not os.path.isdir(sdir):
            continue
        for pname in sorted(os.listdir(sdir)):
            pdir = os.path.join(sdir, pname)
            if not os.path.isdir(pdir):
                continue
            recs = []
            for f in sorted(os.listdir(pdir)):
                m = RE_RUN_FILE.match(f)
                if not m:
                    continue
                meta = _record(os.path.join(pdir, f))
                if not meta:
                    continue
                recs.append({"run": str(meta.get("run") or m.group(1)).upper()[:1],
                             "verdict": _verdict(meta.get("verdict")),
                             "statement_hash": str(meta.get("statement_hash") or "").strip(),
                             "run_id": str(meta.get("run_id") or ""),
                             "subject": str(meta.get("subject") or "").strip(),
                             "file": os.path.join(pdir, f).replace("\\", "/")})
            if not recs:
                continue
            subject = next((r["subject"] for r in recs if r["subject"]), "")
            if not subject:
                continue
            out.setdefault(subject, []).append((pname, recs))
    return out


def pin_of(pass_list):
    """The pin of one subject from its passes (oldest first), or None."""
    hashed = [(p, rs) for p, rs in pass_list if any(r["statement_hash"] for r in rs)]
    if not hashed:
        return None
    pname, recs = sorted(hashed, key=lambda x: x[0])[-1]
    if not recs or any(r["verdict"] != "CONFIRMED" for r in recs):
        return None
    hashes = {r["statement_hash"] for r in recs if r["statement_hash"]}
    if len(hashes) != 1:
        return None
    runs = {r["run"] for r in recs}
    return {"pass": pname, "hash": hashes.pop(),
            "level": "verified" if {"A", "B"} <= runs else "in-review",
            "records": [r["file"] for r in recs]}


def pins(home, cfg=None, ws=None, library=None):
    """The pins of an Author home: ``[{label, subject, hash, level, pass, records,
    released}]``, sorted by label. Empty when the library or the namespace is unknown."""
    ws = ws if ws is not None else _workspace()
    ns = namespace(home, cfg, ws)
    lib = library_home(ws, library)
    if not ns or not lib:
        return []
    rel = released(home)
    out = []
    for subject, plist in passes(reviews_root(lib), ns).items():
        p = pin_of(plist)
        if not p:
            continue
        label = subject.split(":", 1)[1] if subject.startswith(ns + ":") else subject
        out.append(dict(p, label=label, subject=subject, released=label in rel))
    return sorted(out, key=lambda r: r["label"])


def enforced(home, cfg=None, ws=None, library=None):
    """``{label: pin}`` of the pins the guard enforces (not released)."""
    return {p["label"]: p for p in pins(home, cfg, ws, library) if not p["released"]}


# ----------------------------------------------------------------------------
# The statement environment in the tex
# ----------------------------------------------------------------------------

def statement_envs(cfg=None):
    th = ((au.author_settings(cfg or {}) or {}).get("theorems") or {}).get("all") or []
    return set(th) | set(DEFAULT_STATEMENT_ENVS)


def statement_env(text, label, envs=None):
    """``(start, end)`` of the statement environment that holds ``\\label{label}`` in
    ``text`` (from its ``\\begin`` to the end of its ``\\end``), or None.

    The innermost enclosing environment that is a statement (``envs``, or anything not
    in ``NON_STATEMENT`` when ``envs`` is None) is taken, so a label inside an
    ``enumerate`` of a lemma pins the lemma."""
    key = "\\label{%s}" % label
    pos = text.find(key)
    if pos < 0:
        return None
    stack = []
    target = None
    for m in RE_BEGIN_END.finditer(text):
        if target is None and m.start() > pos:
            for env, start, depth in reversed(stack):
                if (env in envs) if envs else (env not in NON_STATEMENT):
                    target = (env, start, depth)
                    break
            if target is None:
                return None
        kind, env = m.group(1), m.group(2)
        if kind == "begin":
            stack.append((env, m.start(), len(stack)))
        else:
            while stack and stack[-1][0] != env:
                stack.pop()
            if stack:
                top = stack.pop()
                if target is not None and top[1] == target[1]:
                    return (target[1], m.end())
    return None


def env_text(text, label, envs=None):
    span = statement_env(text, label, envs)
    return text[span[0]:span[1]] if span else None


def tex_files(home, cfg=None):
    """The home's tex files (``paths.tex`` patterns, default main.tex and sections/*.tex)."""
    import glob
    pats = ((cfg or {}).get("paths") or {}).get("tex") or ["main.tex", "sections/*.tex"]
    if isinstance(pats, str):
        pats = [pats]
    out = []
    for p in pats:
        out += glob.glob(os.path.join(home, *p.split("/")))
    return sorted(set(out))


def locate(home, cfg=None, labels=()):
    """``{label: {file, current_hash}}`` for the labels found in the home's tex."""
    envs = statement_envs(cfg)
    out = {}
    for path in tex_files(home, cfg):
        try:
            with open(path, encoding="utf-8", errors="replace", newline="") as fh:
                text = fh.read()
        except OSError:
            continue
        for lab in labels:
            if lab in out:
                continue
            t = env_text(text, lab, envs)
            if t is not None:
                out[lab] = {"file": os.path.relpath(path, home).replace("\\", "/"),
                            "current_hash": statement_hash(t)}
    return out


def changed(before, after, labels, envs=None):
    """The labels among ``labels`` whose statement environment in ``before`` is changed or
    gone in ``after`` (whitespace-insensitive). A label not in ``before`` is not checked."""
    out = []
    for lab in labels:
        old = env_text(before or "", lab, envs)
        if old is None:
            continue
        new = env_text(after or "", lab, envs)
        if new is None or norm(new) != norm(old):
            out.append(lab)
    return out


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home", default=None)
    ap.add_argument("--library", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--labels", action="store_true")
    a = ap.parse_args(argv)
    home, cfg = au.author_home(a.home or os.getcwd())
    if not home:
        if a.home and os.path.isdir(a.home):
            home, cfg = os.path.abspath(a.home), {}
        else:
            sys.stderr.write("pinned: not in an Author home (give --home)\n")
            return 2
    rows = pins(home, cfg, library=a.library)
    where = locate(home, cfg, [r["label"] for r in rows])
    for r in rows:
        w = where.get(r["label"]) or {}
        r["file"] = w.get("file")
        r["current_hash"] = w.get("current_hash")
        r["matches"] = bool(w) and w.get("current_hash") == r["hash"]
    if a.labels:
        for r in rows:
            if not r["released"]:
                print(r["label"])
        return 0
    if a.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        return 0
    for r in rows:
        print("%-44s %-9s pass %-22s hash %s%s  %s%s" % (
            r["label"], r["level"], r["pass"], r["hash"],
            "" if r["matches"] else " (text hash %s)" % (r["current_hash"] or "not found"),
            r["file"] or "-", "  [released by the human]" if r["released"] else ""))
    print("%d pinned statement(s); the statement environment of each is not edited "
          "(the proof is free). A change goes to the Researcher as a ticket."
          % sum(1 for r in rows if not r["released"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
