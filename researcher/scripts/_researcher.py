"""_researcher -- helpers shared by the Researcher plugin's scripts and hooks.

Stdlib only; imports the vendored academy lib ``_academy.py`` next to it (never edit
that copy: it is synced from ``academy/lib/academy_common.py``).

Contents
--------
Homes
    workspace_or_none()                 workspace.json, or None when unreadable
    researcher_home(path)               (home, config|None, instance) of the researcher
                                        instance whose home contains ``path``
    notebook_paths(home, cfg)           objects/proofs/journal/audits/views dirs
    registry_homes(ws)                  every instance with a claim namespace
    record_roots(home, cfg)             where that home's registry records live
    record_for(path, ws)                the registry record ``path`` is, or None
Frontmatter (tolerant, line based: registry records are richer than the ticket subset)
    frontmatter_block(text)             the lines between the first two '---' lines
    frontmatter_field(text, key)        (present, value) of one top-level key
    apply_edit(text, old, new, all)     the Edit tool's replacement, simulated
Review records (the experiment-reviewer's final message)
    parse_review(text)                  the '## Review record' fields and problems
    norm_verdict(v)                     'sound-modulo x' -> ('SOUND MODULO', 'x')
    subject_slug(ref)                   'lab:ew-check' -> 'ew-check'
Models (roster-rules.md, "Graders degrade")
    PRIMARY_MODELS                      ('fable', 'opus-5.5'): the default primaries
    primary_models()                    workspace.json grading.primaryModels, else those
    model_label(name)                   'claude-opus-5-5' -> 'opus-5.5', else the family
    is_primary(name)                    the name is one of primary_models()
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402

PLUGIN = os.path.dirname(HERE)
TEMPLATES = os.path.join(PLUGIN, "templates")

#: notebook path keys and their defaults (docs/config.md, researcher block)
NOTEBOOK_DEFAULTS = {"objects": "objects", "proofs": "proofs", "journal": "journal",
                     "audits": "audits", "views": "views"}

#: record roots of a registry home that has no academy.json yet (before its switch-over):
#: the old claims.py layout and the first notebook's layout. Plain folder names, no maths.
LEGACY_RECORD_ROOTS = ("claims", "objects", "assumptions", "examples")

#: agents that change a status in a home not yet switched over (no academy.json):
#: the old plugins' claim-keeper and the first notebook's local status-keeper, whose
#: verify -> status-keeper flow runs until that local roster is retired (plan section 9,
#: phase 6). Once a home has academy.json only ``registry.statusKeeper`` is accepted.
LEGACY_KEEPERS = ("claim-keeper", "status-keeper")

#: files inside a record root that are not records
NOT_RECORDS = ("INDEX.md", "README.md", "OPEN.md", "STATUS.md")

#: statuses a record may be created with by anyone (the unsettled ones, plus legacy words)
UNSETTLED = ("open", "conjectured", "sketch", "not settled", "")

OBJECT_KINDS = ("definition", "claim", "conjecture", "question", "example",
                "assumption", "direction", "approach")
#: an approach's lifecycle (campaign mode): a lifecycle like a direction's, not a status
APPROACH_LIFECYCLES = ("active", "blocked", "delivered", "dropped")
#: the kinds that carry a status (plan section 3.3)
STATUS_KINDS = ("claim", "conjecture", "question")

EXPERIMENT_VERDICTS = ("SOUND", "SOUND MODULO", "GAP", "BROKEN")
POSITIVE = ("SOUND", "SOUND MODULO")

#: the grader primaries, equal in authority, when workspace.json sets no
#: ``grading.primaryModels``. A positive verdict on any other model (Sonnet, Haiku, an
#: older Opus, a bare "opus" that names no version) is capped. Kept in step with expert
#: decision_table.py.
PRIMARY_MODELS = ac.DEFAULT_PRIMARY_MODELS
RE_OPUS_55 = re.compile(r"opus-?5-5(?![0-9])")


def model_label(name):
    """``fable``, ``opus-5.5``, or the family (``opus``/``sonnet``/``haiku``) of any
    other model; the lower-cased name when it names no known family; '' when empty.
    ``claude-opus-5-5[1m]``, ``Opus 5.5`` and ``opus-5.5`` all read as ``opus-5.5``."""
    n = str(name or "").strip().lower()
    if not n:
        return ""
    k = re.sub(r"[\s_.]+", "-", n)
    if "fable" in k:
        return "fable"
    if RE_OPUS_55.search(k):
        return "opus-5.5"
    for fam in ("opus", "sonnet", "haiku"):
        if fam in k:
            return fam
    return n


def primary_models(workspace=None):
    """The configured primaries as model labels (``grading.primaryModels``)."""
    return tuple(model_label(m) for m in ac.primary_models(workspace))


def is_primary(name, workspace=None):
    """True when ``name`` is one of the configured primaries."""
    return model_label(name) in primary_models(workspace)


# ----------------------------------------------------------------------------
# Homes
# ----------------------------------------------------------------------------

def workspace_or_none(path=None):
    try:
        return ac.load_workspace(path)
    except ac.AcademyError:
        return None


def _config_or_none(home):
    try:
        return ac.load_config(home)
    except ac.AcademyError:
        return None


def _contains(home, path):
    return ac._rel_to(home, path) is not None


def researcher_home(path, ws=None):
    """``(home, config_or_None, instance)`` of the researcher instance containing ``path``.

    A home switched over has ``.claude/academy.json`` with role researcher. Before its
    switch-over a home is recognised from workspace.json alone (config None, notebook
    paths at their defaults). Returns ``(None, None, None)`` outside every researcher home.
    """
    if not path:
        return None, None, None
    home = ac.find_home(path)
    if home:
        cfg = _config_or_none(home)
        if cfg and cfg.get("role") == "researcher":
            return cfg["_home"], cfg, cfg.get("instance")
    ws = ws if ws is not None else workspace_or_none()
    if not ws:
        return None, None, None
    best = None
    for name, inst in ws.get("instances", {}).items():
        if inst.get("role") != "researcher" or not inst.get("home"):
            continue
        if _contains(inst["home"], path):
            if best is None or len(inst["home"]) > len(best[0]):
                best = (os.path.abspath(inst["home"]).replace("\\", "/"), name)
    if best is None:
        return None, None, None
    cfg = _config_or_none(best[0]) if os.path.isfile(
        os.path.join(best[0], ac.CONFIG_REL)) else None
    return best[0], cfg, best[1]


def _first(pat):
    if isinstance(pat, (list, tuple)):
        return pat[0] if pat else None
    return pat


def notebook_paths(home, cfg=None):
    """Absolute notebook directories {objects, proofs, journal, audits, views}."""
    paths = (cfg or {}).get("paths") or {}
    out = {}
    for key, default in NOTEBOOK_DEFAULTS.items():
        rel = _first(paths.get(key)) or default
        out[key] = os.path.join(home, rel.replace("/", os.sep))
    return out


def registry_homes(ws):
    """``[(instance, home, ns, config_or_None)]`` for every instance with a namespace."""
    out = []
    for name, inst in (ws or {}).get("instances", {}).items():
        home = inst.get("home")
        if not home or not inst.get("ns"):
            continue
        home = os.path.abspath(home).replace("\\", "/")
        cfg = _config_or_none(home) if os.path.isfile(
            os.path.join(home, ac.CONFIG_REL)) else None
        out.append((name, home, cfg.get("ns") if cfg else inst["ns"], cfg))
    return out


def record_roots(home, cfg):
    """Relative record roots of a registry home: ``registry.root`` and ``paths.records``
    from its academy.json, or LEGACY_RECORD_ROOTS before the switch-over."""
    if not cfg:
        return list(LEGACY_RECORD_ROOTS)
    roots = []
    reg = cfg.get("registry") or {}
    if reg.get("root"):
        roots.append(reg["root"])
    rec = (cfg.get("paths") or {}).get("records")
    for r in ([rec] if isinstance(rec, str) else (rec or [])):
        if r not in roots:
            roots.append(r)
    return roots


def record_for(path, ws=None):
    """If ``path`` is a registry record, ``{instance, home, ns, config, rel, field,
    keeper, keepers}``; else None. ``keepers`` adds LEGACY_KEEPERS for a home that has
    no academy.json yet.

    A record is a ``.md`` file under one of a registry home's record roots, not one of
    NOT_RECORDS, not a template (``_*``), and not a generated view of that home.
    """
    if not path or not str(path).lower().endswith(".md"):
        return None
    base = os.path.basename(str(path))
    if base in NOT_RECORDS or base.startswith("_"):
        return None
    ws = ws if ws is not None else workspace_or_none()
    if not ws:
        return None
    full = os.path.abspath(str(path))
    for name, home, ns, cfg in registry_homes(ws):
        rel = ac._rel_to(home, full)
        if rel is None or rel == "":
            continue
        if any(ac._match_path(rel, r) for r in record_roots(home, cfg)):
            if cfg and ac.path_in_role(full, cfg, "views"):
                return None
            field = ((cfg or {}).get("researcher") or {}).get("statusField") or "status"
            keeper = ((cfg or {}).get("registry") or {}).get("statusKeeper") \
                or "claim-keeper"
            keepers = (keeper,) if cfg else tuple(dict.fromkeys((keeper,) + LEGACY_KEEPERS))
            return {"instance": name, "home": home, "ns": ns, "config": cfg,
                    "rel": rel, "field": field, "keeper": keeper, "keepers": keepers}
    return None


# ----------------------------------------------------------------------------
# Tolerant frontmatter
# ----------------------------------------------------------------------------

def frontmatter_block(text):
    """The frontmatter lines (between a first '---' line and the next), or None."""
    if text is None:
        return None
    lines = text.replace("\r\n", "\n").lstrip("﻿").split("\n")
    if not lines or lines[0].rstrip() != "---":
        return None
    for j in range(1, len(lines)):
        if lines[j].rstrip() == "---":
            return lines[1:j]
    return None


def _unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def frontmatter_field(text, key):
    """``(present, value)`` of the top-level frontmatter key ``key``.

    Only an unindented ``key:`` line counts (a ``status:`` inside a history row or a
    nested map does not). The value is stripped of a trailing comment and of quotes.
    """
    block = frontmatter_block(text)
    if block is None:
        return False, None
    rx = re.compile(r"^%s:(?:\s+(.*))?$" % re.escape(key))
    for ln in block:
        m = rx.match(ln.rstrip())
        if m:
            val = (m.group(1) or "")
            val = re.sub(r"\s+#.*$", "", val) if not val.lstrip().startswith(("'", '"')) \
                else val
            return True, _unquote(val)
    return False, None


def apply_edit(text, old, new, replace_all=False):
    """The Edit tool's replacement on ``text``; None when ``old`` does not occur."""
    if old is None or old == "" or text is None:
        return None
    if old not in text:
        alt = text.replace("\r\n", "\n")
        if old.replace("\r\n", "\n") not in alt:
            return None
        text, old, new = alt, old.replace("\r\n", "\n"), (new or "").replace("\r\n", "\n")
    return text.replace(old, new or "") if replace_all else text.replace(old, new or "", 1)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
            return fh.read()
    except OSError:
        return None


# ----------------------------------------------------------------------------
# Review records
# ----------------------------------------------------------------------------

REVIEW_FIELDS = ("subject", "run", "verdict", "result", "commit", "validation",
                 "outcome", "model", "reproduction", "ticket")
REQUIRED_REVIEW_FIELDS = ("subject", "run", "verdict", "validation", "outcome")
RE_FIELD = re.compile(r"^\s*(?:[-*]\s+)?\**(%s)\**\s*:\s*(.*?)\s*$"
                      % "|".join(f.capitalize() for f in REVIEW_FIELDS), re.IGNORECASE)
VALIDATION = ("passed", "failed", "not run", "unknown")
OUTCOMES = ("supports", "refutes", "inconclusive")


def norm_verdict(v):
    """``(VERDICT, assumption)``; VERDICT is one of EXPERIMENT_VERDICTS or ''."""
    s = " ".join(str(v or "").replace("_", " ").replace("-", " ").split()).strip("`* ")
    up = s.upper()
    if up.startswith("SOUND MODULO"):
        return "SOUND MODULO", s[len("SOUND MODULO"):].strip(" :;,.-")
    for verdict in ("SOUND", "GAP", "BROKEN"):
        if up == verdict or up.startswith(verdict + " ") or up.startswith(verdict + ":"):
            return verdict, ""
    return "", ""


def parse_review(text):
    """Parse the ``## Review record`` block of an experiment-reviewer's report.

    Returns ``(fields, problems)``. Fields are lower-case keys of REVIEW_FIELDS; the
    first occurrence of each wins (the block comes first in the report). ``verdict``
    is normalised and ``assumption`` added for SOUND MODULO.
    """
    fields, probs = {}, []
    lines = (text or "").replace("\r\n", "\n").split("\n")
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().lower().lstrip("#").strip() == "review record":
            start = i + 1
            break
    for ln in lines[start:]:
        m = RE_FIELD.match(ln)
        if m:
            key = m.group(1).lower()
            if key not in fields:
                fields[key] = m.group(2).strip().strip("`")
    for key in REQUIRED_REVIEW_FIELDS:
        if not fields.get(key):
            probs.append("missing '%s:'" % key.capitalize())
    if fields.get("run"):
        run = fields["run"].strip().upper()[:1]
        if run not in ("A", "B"):
            probs.append("Run must be A or B")
        fields["run"] = run
    if fields.get("verdict"):
        v, assumption = norm_verdict(fields["verdict"])
        if not v:
            probs.append("Verdict must be one of %s" % " / ".join(EXPERIMENT_VERDICTS))
        elif v == "SOUND MODULO" and not assumption:
            probs.append("SOUND MODULO must name its assumption")
        fields["verdict"], fields["assumption"] = v, assumption
    if fields.get("validation"):
        val = fields["validation"].lower().strip(" .")
        fields["validation"] = next((x for x in VALIDATION if val.startswith(x)), val)
        if fields["validation"] not in VALIDATION:
            probs.append("Validation must be one of %s" % " / ".join(VALIDATION))
    if fields.get("outcome"):
        out = fields["outcome"].lower().strip(" .")
        fields["outcome"] = next((x for x in OUTCOMES if out.startswith(x)), out)
        if fields["outcome"] not in OUTCOMES:
            probs.append("Outcome must be one of %s" % " / ".join(OUTCOMES))
    if fields.get("subject") and not re.match(r"^[a-z0-9]+:\S+$", fields["subject"]):
        probs.append("Subject must be a claim id '<ns>:<id>'")
    return fields, probs


def subject_slug(ref):
    """Folder name of a subject under audits/: 'lab:ew-check' -> 'ew-check';
    another namespace keeps it as a prefix ('s1:Q-2' -> 's1-q-2')."""
    ref = str(ref or "").strip()
    ns, _, rest = ref.partition(":")
    if not rest:
        ns, rest = "", ref
    slug = ac.slugify(rest, maxlen=80, default="subject")
    return slug if ns in ("", "lab") else "%s-%s" % (ac.slugify(ns), slug)
