"""Delivery artefacts (#100 part 1, the human's ruling of 2026-11-20): what a ``delivered``
ticket of each kind must leave behind that a script can check. ``inbox.py --check``
refuses a delivery without it (``inbox_core.artefact_problem``); a ticket whose work was
done but whose deliverable was not met is ``partial`` instead.

One table, ``ARTEFACTS``: kind -> (what is needed, the check). A check takes the ticket
(meta, the texts that may name the artefact, the workspace) and returns ``(found, why)``:
``found`` the artefact (a path, a commit) or None. A kind not in the table passes.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import glob
import os
import re
import subprocess

from ._base import HUMAN, ROLES
from ._files import read_frontmatter
from ._tickets import find_packet, role_of

#: attempt outcomes (the attempt's frontmatter ``outcome:``) that are not a proof delivered
NOT_DELIVERED_OUTCOMES = ("incomplete", "failed", "in-progress")
#: where a path token ends: whitespace, separators, quotes, brackets
_RE_TOKEN = re.compile(r"[^\s;,'\"()\[\]<>`]+")
_RE_FILE_REF = re.compile(r"^file:([^/\s]+)/(.+)$")
_RE_SHA = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,40}(?![0-9A-Za-z])")
_RE_PACKET = re.compile(r"(?<![A-Za-z0-9])P-\d{4,}(?![0-9])")
#: a bib key as the library names its card folders (``Ve89``, ``LMW16``, ``Fil16b``)
_RE_KEY = re.compile(r"(?<![A-Za-z0-9])(?:bib:)?([A-Z][A-Za-z]*\d{2}[a-z]?(?:-published)?)(?![A-Za-z0-9])")
#: a bare ``attempt-<n>`` in prose (T-0059: "proved (sketch) in <claim>, attempt-1")
_RE_ATTEMPT_N = re.compile(r"(?<![\w/])attempt-(\d+)(?![\w.])")
_RE_ID = re.compile(r"(?<![\w:/-])((?:[a-z][a-z0-9]*:)?[A-Za-z][\w.-]*(?::[\w.-]+)*)")

#: #100 review: a delivery with no artefact on purpose says so at the very start of its
#: result, as ``<marker>: <why>``, and only for a kind where "nothing to do" is legitimate
#: (re-review of ca04c0e, finding A). kind -> the colon markers it may use.
EDIT_KINDS = ("apply", "write", "copy", "figure")
MARKERS = {k: ("declined", "no change", "superseded", "not needed") for k in EDIT_KINDS}
MARKERS["prove"] = ("already proved",)
MARKERS["experiment"] = MARKERS["test"] = ("dropped", "no search")
#: the wordings delivered before the colon form (the board up to 2026-11-20), matched as
#: they are: kind -> [(regex at the start of the result, the marker it stands for)]
LEGACY = {k: [(r"declined, ", "declined"), (r"(?:both|all) edits declined, ", "declined"),
              (r"no tex change[.:] ", "no change"), (r"no edits made: ", "no change"),
              (r"nothing applied, tex untouched", "no change"),
              (r"not applied \(stale\): ", "superseded")] for k in EDIT_KINDS}
LEGACY["figure"] = LEGACY["figure"] + [(r"already in the file \(from T-\d+\)", "no change")]
LEGACY["prove"] = [(r"\S+ is already proved: nothing to attempt$", "already proved")]
LEGACY["experiment"] = LEGACY["test"] = [
    (r"no search run \(", "no search"), (r"no search \(", "no search"),
    (r"no computation \(", "no search")]
#: words that say the work failed: a marker beside one of them is no reason (finding A).
#: Phrases about the work, not bare "fails" or "limit", which a mathematical result uses
#: ("fails at a = b = 1", T-1154)
FAILURE_WORDS = re.compile(
    r"\b(?:(?:attempt|run|job|script|build|check|step|edit|search|computation)s? "
    r"(?:has |was |had )?failed|failed to|crash(?:ed|es)?|budget|errors?|incomplete|"
    r"timed out|time-?out|usage limit|(?:hit|reached|exceeded) (?:a|its|the) (?:\w+ )?limit)\b",
    re.I)
#: a decision word of the human's quoted decision
DECISION_WORDS = (r"decided|decides|ruled|rules|declined?|satisfied|drop(?:ped)?|keep|kept|"
                  r"accepts?|accepted|close|closed|cancel(?:led)?|approved?")
#: kinds whose delivery may rest on the human's quoted decision instead of an artefact
HUMAN_KINDS = EDIT_KINDS + ("experiment", "test")


def _texts(meta, body):
    """The places a ticket names its artefact: result, refs, the ## Result section."""
    out = [str(meta.get("result") or "")]
    out += [str(r) for r in (meta.get("refs") or [])]
    if body:
        m = re.search(r"(?ms)^## Result[ \t]*\n(.*?)(?=^## |\Z)", body)
        if m:
            out.append(m.group(1))
    return out


def _homes(workspace, role=None, first=None):
    """The homes of the workspace's instances (of ``role``), ``first``'s home first."""
    insts = (workspace or {}).get("instances") or {}
    homes = []
    if first in insts and insts[first].get("home"):
        homes.append(insts[first]["home"])
    for name in sorted(insts):
        h = insts[name].get("home")
        if h and h not in homes and (role is None or insts[name].get("role") == role):
            homes.append(h)
    return homes


def _named(texts, pattern):
    """``[(instance or None, path)]``: the tokens of ``texts`` holding ``pattern`` (cut
    after its match, so trailing punctuation goes), a ``file:<instance>/`` prefix split off."""
    rx = re.compile(r"^(.*?%s)" % pattern)
    out = []
    for t in texts:
        for tok in _RE_TOKEN.findall(t):
            m = rx.match(tok)
            if not m:
                continue
            p, inst = m.group(1), None
            f = _RE_FILE_REF.match(p)
            if f:
                inst, p = f.group(1), f.group(2)
            if (inst, p) not in out:
                out.append((inst, p))
    return out


def _resolve(workspace, inst, path, homes):
    """The first existing file ``path`` names: absolute as is, else under ``inst``'s home
    or one of ``homes``; None when none exists."""
    if os.path.isabs(path):
        return path if os.path.isfile(path) else None
    cands = _homes(workspace, first=inst)[:1] if inst else []
    for h in cands + list(homes):
        full = os.path.join(h, path)
        if os.path.isfile(full):
            return full
    return None


def _named_file(meta, texts, workspace, pattern, role):
    """``(path, why)`` of a file of ``pattern`` the ticket names that exists, searched in the
    receiver's home and the homes of ``role``."""
    named = _named(texts, pattern)
    homes = _homes(workspace, role, first=meta.get("to"))
    missing = []
    for inst, p in named:
        full = _resolve(workspace, inst, p, homes)
        if full:
            return full, "named and present"
        missing.append(p)
    return None, ("named but not found: %s" % ", ".join(missing) if missing
                  else "none named in the result, refs or ## Result")


def _human_decision(result, name):
    """Whether ``result`` quotes the human's decision: ``<name> <date>: <decision word>...``
    or ``(<name>[,] <date>: "<... decision word ...>")``, the decision word within the
    quoted clause; or one of the two legacy forms the board holds (``<name> replied '...'``
    at the start, ``(<name> accepts it as the falsifier``)."""
    n = re.escape(name)
    date = r"\d{4}-\d{2}-\d{2}"
    forms = (r"^%s,? %s: [^.;]{0,40}?\b(?:%s)\b" % (n, date, DECISION_WORDS),
             r"\(%s,? %s: [\"'][^\"']{0,80}?\b(?:%s)\b" % (n, date, DECISION_WORDS),
             r"^%s replied '[^']+'" % n,
             r"\(%s accepts it as the falsifier" % n)
    return any(re.search(f, result, re.I) for f in forms)


def no_artefact_marker(meta, workspace=None):
    """The marker of a delivery with no artefact on purpose, or None (finding A of the
    re-review of ca04c0e): the result opens with ``<marker>:`` of its kind (``MARKERS``), or
    with a legacy wording of its kind (``LEGACY``), or quotes the human's decision (a kind of
    ``HUMAN_KINDS``; the workspace's ``human.name``); and no word of the result says the
    work failed (``FAILURE_WORDS``). A cite or verify ticket never passes so."""
    kind = meta.get("kind")
    result = " ".join(str(meta.get("result") or "").split())
    if not result or FAILURE_WORDS.search(result):
        return None
    for m in MARKERS.get(kind, ()):
        if result.lower().startswith(m + ":"):
            return m
    for rx, m in LEGACY.get(kind, ()):
        if re.match(rx, result, re.I):
            return m
    name = str(((workspace or {}).get("human") or {}).get("name") or "").strip()
    if name and kind in HUMAN_KINDS and _human_decision(result, name):
        return "the decision of %s" % name
    return None


def _bare_attempts(texts, workspace, homes):
    """The attempt files a result names as ``<id>, attempt-<n>`` or ``attempt-<n>`` beside an
    id of its refs: ``proofs/<id>/attempt-<n>.md`` (the id as is, then without namespace)."""
    nums = sorted({n for t in texts for n in _RE_ATTEMPT_N.findall(t)})
    if not nums:
        return []
    # the ids of the result first: an attempt of an id the result names is the one meant
    # (T-1180: "<claim> (...; attempt-1 in-progress)", its refs naming another claim)
    found = _bare_attempts_of(texts[:1], nums, homes)
    return found or _bare_attempts_of(texts[1:], nums, homes)


def _bare_attempts_of(texts, nums, homes):
    ids = []
    for t in texts:
        for x in _RE_ID.findall(t):
            for cand in (x, x.split(":", 1)[1] if ":" in x else x):
                cand = cand.rstrip(".:")
                if cand and cand not in ids and not cand.startswith("attempt-"):
                    ids.append(cand)
    out = []
    for i in ids:
        for n in nums:
            for h in homes:
                p = os.path.join(h, "proofs", i, "attempt-%s.md" % n)
                if os.path.isfile(p) and p not in out:
                    out.append(p)
    return out


def check_prove(meta, texts, workspace):
    """A proof attempt (``proofs/<ID>/attempt-<n>.md``) named and present, whose
    frontmatter ``outcome:`` (when it has one) is not incomplete, failed or in-progress."""
    homes = _homes(workspace, "researcher", first=meta.get("to"))
    bad, missing = [], []
    named = _named(texts, r"proofs/.+?/attempt-\d+\.md")
    if not named:
        named = [(None, p) for p in _bare_attempts(texts, workspace, homes)]
    for inst, p in named:
        full = _resolve(workspace, inst, p, homes)
        if not full:
            missing.append(p)
            continue
        try:
            with open(full, encoding="utf-8") as fh:
                fm, _ = read_frontmatter(fh.read())
        except Exception:                            # noqa: BLE001 -- no frontmatter: no outcome
            fm = {}
        outcome = str((fm or {}).get("outcome") or "").strip().lower()
        if outcome in NOT_DELIVERED_OUTCOMES:
            bad.append("%s is %s" % (p, outcome))
            continue
        return full, "attempt present" + (" (outcome %s)" % outcome if outcome else "")
    why = "; ".join(bad + (["named but not found: %s" % ", ".join(missing)] if missing else []))
    return None, why or "no attempt named in the result, refs or ## Result"


def check_verify(meta, texts, workspace):
    """A review pass folder holding ``decision.md``, under an Expert library's
    ``reviews/``: the folder named for the ticket (``<date>-T-NNNN[-...]``) or named."""
    tid = str(meta.get("id") or "")
    word = re.compile(r"(?<![A-Za-z0-9])%s(?![0-9])" % re.escape(tid)) if tid else None
    homes = _homes(workspace, "expert", first=meta.get("to"))
    for h in homes:
        for d in sorted(glob.glob(os.path.join(h, "reviews", "*", "*", "*"))):
            if word and word.search(os.path.basename(d)) and \
                    os.path.isfile(os.path.join(d, "decision.md")):
                return os.path.join(d, "decision.md"), "the pass of %s" % tid
    found, why = _named_file(meta, texts, workspace, r"reviews/.+?/decision\.md", "expert")
    if found:
        return found, why
    return None, "no reviews/<ns>/<claim>/<date>-%s/decision.md in the library" % tid


def check_cite(meta, texts, workspace):
    """A library card: a ``cards/<key>/<slug>.md`` named and present, else a card file in
    ``cards/<key>/`` (not ``_intro.md``) of a key the refs (``bib:<key>``) or the result
    name (the cite workflow's result leads with the key and the pinpoint, #100 review)."""
    found, why = _named_file(meta, texts, workspace, r"cards/.+?\.md", "expert")
    if found:
        return found, why
    keys = []
    for t in texts:
        for k in _RE_KEY.findall(t):
            if k not in keys:
                keys.append(k)
    for h in _homes(workspace, "expert", first=meta.get("to")):
        for k in keys:
            d = os.path.join(h, "cards", k)
            cards = sorted(n for n in os.listdir(d) if n.endswith(".md") and n != "_intro.md") \
                if os.path.isdir(d) else []
            if cards:
                return os.path.join(d, cards[-1]), "a card of %s in the library" % k
    return None, ("no card of %s in the library" % ", ".join(keys) if keys
                  else "no card path and no bib key named")


def check_experiment(meta, texts, workspace):
    """An experiment header (``experiments/<stem>.py``) or a result JSON
    (``results/....json``) of the lab, named and present; else a report packet
    (``P-NNNN``) the result names that exists on the board (the experiment workflow's
    "report P-NNNN; review ticket T-..."), else an ``experiments/*.py`` whose header (its
    first 4 KB) names the ticket."""
    found, why = _named_file(meta, texts, workspace,
                             r"(?:experiments/.+?\.py|results/.+?\.json)", "scientist")
    if found:
        return found, why
    board = (workspace or {}).get("board")
    if board:
        for t in texts:
            for pid in _RE_PACKET.findall(t):
                try:
                    path = find_packet(board, pid)
                except Exception:                    # noqa: BLE001 -- twins: it exists
                    path = pid
                if path:
                    return path, "the report packet %s" % pid
    tid = str(meta.get("id") or "")
    word = re.compile(r"(?<![A-Za-z0-9])%s(?![0-9])" % re.escape(tid)) if tid else None
    for h in _homes(workspace, "scientist", first=meta.get("to")):
        for f in sorted(glob.glob(os.path.join(h, "experiments", "*.py"))):
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    head = fh.read(4096)
            except OSError:
                continue
            if word and word.search(head):
                return f, "an experiment header naming %s" % tid
    return None, why + "; no report packet named, no experiment header names %s" % tid


def _git(repo, *args):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat")
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(k, None)
    try:
        p = subprocess.run(["git", "--no-optional-locks", "-C", repo] + list(args),
                           capture_output=True, text=True, env=env,
                           stdin=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return p.returncode, p.stdout


def _repos(root, workspace=None):
    """The workspace's superproject, its checked-out submodules (``.gitmodules``) and the
    instances' homes (an attached checkout outside the root), each once."""
    out = [root]
    try:
        with open(os.path.join(root, ".gitmodules"), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"\s*path\s*=\s*(.+?)\s*$", line)
                if m:
                    out.append(os.path.join(root, m.group(1)))
    except OSError:
        pass
    out += _homes(workspace)
    seen, repos = set(), []
    for r in out:
        k = os.path.realpath(r)
        if k not in seen and os.path.exists(os.path.join(r, ".git")):
            seen.add(k)
            repos.append(r)
    return repos


def check_commit(meta, texts, workspace):
    """A commit of the ticket's work in the workspace: one whose message names the ticket
    (the checkpoint's ``<id>: checkpoint``, #101) on any ref, or a commit the result
    names by its hash. Outside a workspace it is not checked."""
    if not workspace or not workspace.get("_path"):
        return "", "not checked (no workspace)"
    root = os.path.dirname(os.path.realpath(workspace["_path"]))
    repos = _repos(root, workspace)
    if not repos:
        return "", "not checked (the workspace is no git checkout)"
    tid = str(meta.get("id") or "")
    shas = [s for t in texts for s in _RE_SHA.findall(t)]
    grep = r"(^|[^A-Za-z0-9])%s([^0-9]|$)" % re.escape(tid)
    for repo in repos:
        if tid:
            rc, out = _git(repo, "log", "--all", "-E", "--format=%h", "-n", "1", "--grep", grep)
            if not rc and out.strip():
                return "%s@%s" % (os.path.relpath(repo, root), out.strip()), "a commit names it"
        for s in shas:
            rc, _ = _git(repo, "cat-file", "-e", s + "^{commit}")
            if not rc:
                return "%s@%s" % (os.path.relpath(repo, root), s), "the commit it names"
    return None, "no commit names %s in the workspace's repos" % tid


#: kind -> (what is needed, check); a kind not here needs nothing beyond its result
ARTEFACTS = {
    "prove": ("a proof attempt (proofs/<ID>/attempt-<n>.md, not incomplete or failed)",
              check_prove),
    "verify": ("a review pass with decision.md under the library's reviews/", check_verify),
    "cite": ("a library card (cards/<key>/<slug>.md)", check_cite),
    "experiment": ("an experiment header (experiments/*.py) or a result JSON (results/*.json)",
                   check_experiment),
    "test": ("an experiment header (experiments/*.py) or a result JSON (results/*.json)",
             check_experiment),
}
for _k in ("code", "build", "write", "apply", "figure", "copy"):
    ARTEFACTS[_k] = ("a commit naming the ticket (its checkpoint) or named in its result",
                     check_commit)


def _relays(meta, workspace):
    """Whether the ticket is a relay parent: its ``final_to`` lies beyond its receiver's role
    (a ``research`` ticket to an Expert reads as ``final_to: researcher``), so its child
    carries the artefact and was checked at its own --check."""
    ft = meta.get("final_to")
    final = (ft if ft in ROLES else role_of(ft, workspace)) if ft else None
    receiver = role_of(meta.get("to"), workspace)
    if meta.get("kind") == "research" and receiver == "expert" and final in (None, "expert"):
        final = "researcher"
    return final is not None and final != receiver


def delivery_artefact(meta, body=None, workspace=None):
    """``{"ok", "kind", "need", "found", "why"}``: whether the delivered ticket ``meta``
    (``body`` its text, for ## Result) has the artefact its kind needs (``ARTEFACTS``).
    Only ``delivered`` is checked; a ticket to the human, a relay parent and a kind not in
    the table pass."""
    kind = meta.get("kind")
    need, fn = ARTEFACTS.get(kind, ("", None))
    res = {"ok": True, "kind": kind, "need": need, "found": None, "why": "", "marker": None}
    if meta.get("status") != "delivered":
        res["why"] = "not delivered: not checked"
    elif fn is None:
        res["why"] = "no artefact for a %s ticket" % kind
    elif meta.get("to") == HUMAN:
        res["why"] = "a ticket to the human: not checked"
    elif _relays(meta, workspace):
        res["why"] = "a relay: its child carries the artefact"
    else:
        found, why = fn(meta, _texts(meta, body), workspace)
        res.update(ok=found is not None, found=found or None, why=why)
        if not res["ok"]:
            marker = no_artefact_marker(meta, workspace)
            if marker:
                res.update(ok=True, marker=marker,
                           why="no artefact, on purpose: the result says %r (%s)" % (marker, why))
    return res
