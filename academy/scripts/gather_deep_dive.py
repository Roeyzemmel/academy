"""gather_deep_dive.py -- collect the input bundle for /academy:deep-dive. Read-only.

Usage:

    py gather_deep_dive.py SUBJECT [--kind K] [--out FILE] [--depth N] [--cli]
                           [--workspace FILE] [--board DIR]

SUBJECT is one of

    <ns>:<id>              a registry object (claim, definition, direction, ...),
                           e.g. paper:lem:strip-bound, lab:ew-check, s1:BOUND-2
    bib:<key>[#pinpoint]   a cited paper (a bare key found in the library works too)
    <path>.json            a lab result, relative to the Scientist home or absolute
                           (also file:<instance>/<path>)
    concept:<term>         a concept by name: matching definitions plus domain-pack text

The kind (concept | claim | paper | experiment | direction) is inferred and can be
forced with --kind. The bundle (format in render_packets.py) holds the object, its
dependency closure (depends_on and modulo, transitively, up to --depth), the
statements that rest on it or bear on it, the library cards and cached source for the
bib keys involved, proof and experiment reviews, the board's report packets and, for
an experiment, the result JSON. The explainer adds its prose as ``sections``.

Records are read straight from each home's registry directory (``registry.root`` of
its ``.claude/academy.json``, else ``claims/`` or ``objects/``) with a lenient
frontmatter reader, so both the paper/lab and the older notebook formats load. With
--cli, the registry command line of each home (``registry.legacy.claims`` or
``.kb``) is also run as ``<cmd> show <id>`` for the subject, and its output is
attached. The script writes nothing except --out.
"""

import argparse
import glob
import json
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))

import academy_common as ac  # noqa: E402

MAX_TEXT = 6000          # characters kept of any one text in the bundle
MAX_RESULT = 20000       # characters kept of a result JSON
LINK_FIELDS = ("depends_on", "modulo", "bears_on", "supersedes")


def _read(path, limit=None):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    if limit and len(text) > limit:
        text = text[:limit] + "\n[... truncated at %d characters]" % limit
    return text


# ----------------------------------------------------------------------------
# Lenient record reader
# ----------------------------------------------------------------------------

def _scalar(v):
    v = v.strip()
    if v in ("", "~", "null"):
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        if v[0] == '"':
            try:
                return json.loads(v)
            except ValueError:
                pass
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in re.split(r",\s*(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", inner)
                if x.strip()] if inner else []
    return v


def parse_record(text):
    """(meta, body) of a Markdown record; strict subset first, then a lenient reading.

    The lenient reading keeps top-level ``key: value`` scalars, inline lists and
    block lists (each ``- item`` line, with its indented continuation joined); nested
    maps under a list item come back as their raw text.
    """
    try:
        return ac.read_frontmatter(text)
    except ac.FrontmatterError:
        pass
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((j for j in range(1, len(lines)) if lines[j].strip() == "---"), None)
    if end is None:
        return {}, text
    meta, key = {}, None
    for ln in lines[1:end]:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$", ln)
        if m and not ln.startswith(" "):
            key = m.group(1)
            meta[key] = _scalar(m.group(2) or "")
            if meta[key] is None:
                meta[key] = None
            continue
        if key is None:
            continue
        s = ln.strip()
        if s.startswith("- "):
            if not isinstance(meta.get(key), list):
                meta[key] = []
            meta[key].append(_scalar(s[2:]) if ":" not in s[2:] or s[2:].startswith(
                ("\"", "'")) else s[2:])
        elif isinstance(meta.get(key), list) and meta[key]:
            meta[key][-1] = "%s %s" % (meta[key][-1], s)
        elif meta.get(key) is None:
            meta[key] = s
        else:
            meta[key] = "%s %s" % (meta[key], s)
    return meta, "\n".join(lines[end + 1:])


def _section(body, name):
    m = re.search(r"^## %s\s*\n(.*?)(?=^## |\Z)" % re.escape(name), body, re.M | re.S)
    return m.group(1).strip() if m else ""


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if x not in (None, "")]
    return [x.strip() for x in str(v).split(",") if x.strip()]


def _qualify(ref, ns):
    ref = str(ref).strip()
    if not ref:
        return ref
    if re.match(r"^[a-z][a-z0-9]*:", ref) and not re.match(
            r"^(lem|thm|prop|cor|conj|defn|def|rmk|ex|claim|quest|fact|sec|eq):", ref):
        return ref
    return "%s:%s" % (ns, ref)


# ----------------------------------------------------------------------------
# The federated index
# ----------------------------------------------------------------------------

class Home(object):
    def __init__(self, name, spec):
        self.name = name
        self.role = spec.get("role")
        self.path = spec.get("home")
        self.ns = spec.get("ns")
        self.domains = spec.get("domains") or []
        self.config = None
        if self.path:
            try:
                self.config = ac.load_config(self.path)
            except (ac.AcademyError, OSError):
                self.config = None

    def registry_root(self):
        if self.config and self.config.get("registry", {}).get("root"):
            return os.path.join(self.path, self.config["registry"]["root"])
        for cand in ("claims", "objects"):
            p = os.path.join(self.path or "", cand)
            if os.path.isdir(p):
                return p
        return None

    def rule_set(self):
        """The home's rule set (``registry.profile``, old aliases resolved), else its ns."""
        prof = ((self.config or {}).get("registry") or {}).get("profile")
        return ac.registry_rule_set(prof) or ac.registry_rule_set(self.ns)

    def cli(self):
        if not self.config:
            return None
        legacy = self.config.get("registry", {}).get("legacy") or {}
        return legacy.get("claims") or legacy.get("kb")


def load_index(workspace):
    """{full id: record} across every registry of the workspace.

    A record is ``{"id", "ns", "home", "path", "meta", "body"}``.
    """
    index = {}
    for name, spec in workspace["instances"].items():
        h = Home(name, spec)
        if not h.ns:
            continue
        root = h.registry_root()
        if not root:
            continue
        for p in glob.glob(os.path.join(root, "**", "*.md"), recursive=True):
            if os.path.basename(p).upper() in ("INDEX.MD", "README.MD"):
                continue
            text = _read(p)
            if not text:
                continue
            meta, body = parse_record(text)
            rid = meta.get("id")
            if not rid:
                continue
            full = _qualify(rid, h.ns)
            index[full] = {"id": full, "ns": h.ns, "home": h, "path": p, "meta": meta,
                           "body": body}
            for al in _as_list(meta.get("aliases")):
                index.setdefault("alias:" + str(al), index[full])
    return index


def _links(rec, field):
    return [_qualify(x, rec["ns"]) for x in _as_list(rec["meta"].get(field))]


def _latex_env(path, label, limit=MAX_TEXT):
    """The LaTeX environment carrying ``\\label{label}`` in ``path``, or ''."""
    text = _read(path)
    if not text:
        return ""
    i = text.find("\\label{%s}" % label)
    if i < 0:
        return ""
    starts = [m for m in re.finditer(r"\\begin\{([A-Za-z*]+)\}", text[:i])]
    for m in reversed(starts):
        env = m.group(1)
        if env in ("equation", "align", "enumerate", "itemize", "equation*", "align*"):
            continue
        end = text.find("\\end{%s}" % env, i)
        if end < 0:
            return ""
        out = text[m.start():end + len("\\end{%s}" % env)]
        return out[:limit]
    return ""


def statement_source(rec):
    """(statement text, raw source) of a record: field, body section, or LaTeX source.

    The raw source is the LaTeX environment when the statement came from the paper,
    so citations can be read from it before latex_to_prose rewrites them.
    """
    meta = rec["meta"]
    for key in ("statement", "summary"):
        if meta.get(key):
            return str(meta[key]), str(meta[key])
    sec = _section(rec["body"], "Statement")
    if sec:
        return sec[:MAX_TEXT], sec
    where = meta.get("where")
    home = rec["home"].path
    if where and str(where).endswith(".tex") and home:
        label = rec["id"].split(":", 1)[1]
        env = _latex_env(os.path.join(home, str(where)), label)
        if env:
            return latex_to_prose(env), env
    return "", ""


def statement_of(rec):
    return statement_source(rec)[0]


def latex_to_prose(env):
    """The body of a LaTeX environment as Markdown-ish prose, math left for KaTeX."""
    t = re.sub(r"^\\begin\{[^}]*\}(\[[^\]]*\])?", "", env.strip())
    t = re.sub(r"\\end\{[^}]*\}$", "", t.strip())
    t = re.sub(r"\\label\{[^}]*\}", "", t)
    t = re.sub(r"(?<!\\)%.*", "", t)
    t = re.sub(r"\\(?:emph|textit)\{([^{}]*)\}", r"*\1*", t)
    t = re.sub(r"\\textbf\{([^{}]*)\}", r"**\1**", t)
    t = re.sub(r"\\(?:begin|end)\{(?:enumerate|itemize)\}(\[[^\]]*\])?", "\n", t)
    t = re.sub(r"\\item\s*", "\n- ", t)
    t = re.sub(r"\\(?:c|C)?ref\{([^}]*)\}", r"`\1`", t)
    t = re.sub(r"\\cite[tp]?\*?(?:\[([^\]]*)\])?\{([^}]*)\}",
               lambda m: "[%s%s]" % (m.group(2), (", " + m.group(1)) if m.group(1) else ""), t)
    out = []
    for ln in (x.strip() for x in t.split("\n")):
        if ln.startswith("- ") or not out or not ln or not out[-1]:
            out.append(ln)
        else:
            out[-1] += " " + ln
    return "\n".join(out).strip()


RE_NEWCMD = re.compile(r"\\(?:re)?newcommand\*?\{?(\\[A-Za-z]+)\}?(?:\[(\d)\])?\{")
RE_MATHOP = re.compile(r"\\DeclareMathOperator\*?\{(\\[A-Za-z]+)\}\{([^{}]*)\}")


def _balanced(text, i):
    """The contents of the brace group whose '{' is at text[i-1], and the end index."""
    depth, j = 1, i
    while j < len(text) and depth:
        if text[j] == "\\":
            j += 2
            continue
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
    return text[i:j - 1], j


def latex_macros(home):
    """KaTeX macros from a home's top-level .tex files (newcommand, DeclareMathOperator)."""
    macros = {}
    for p in sorted(glob.glob(os.path.join(home or "", "*.tex")))[:10]:
        text = _read(p) or ""
        for m in RE_NEWCMD.finditer(text):
            body, _end = _balanced(text, m.end())
            if len(body) < 300:
                macros[m.group(1)] = body
        for m in RE_MATHOP.finditer(text):
            macros[m.group(1)] = "\\operatorname{%s}" % m.group(2)
    return macros


#: kinds that carry no status in schema v2 (a definition is not true or false): their
#: statements get this badge instead of none, so the page renders (render_packets
#: refuses a statement with no status)
NO_STATUS_KINDS = {"definition": "definition", "def": "definition", "example": "example",
                   "direction": "direction"}


def status_of(meta):
    """The record's status, or ``n/a — <kind>`` for a kind that has none."""
    st = meta.get("status")
    if st in (None, ""):
        kind = NO_STATUS_KINDS.get(str(meta.get("kind") or "").strip().lower())
        if kind:
            return "n/a — " + kind
    return st


def stmt(rec, role, depth=1):
    meta = rec["meta"]
    out = {"id": rec["id"], "title": meta.get("title") or rec["id"],
           "status": status_of(meta), "kind": meta.get("kind"),
           "statement": "", "role": role, "depth": depth,
           "where": str(meta.get("where") or os.path.relpath(rec["path"], rec["home"].path)
                        ).replace("\\", "/"),
           "source": rec["path"].replace("\\", "/")}
    out["statement"], raw = statement_source(rec)
    cites = bib_keys_in(raw) + bib_keys_in(rec["body"]) + [
        str(k).split("#")[0].replace("bib:", "") for k in _as_list(meta.get("cites"))]
    if cites:
        out["cites"] = list(dict.fromkeys(cites))
    mod = _links(rec, "modulo")
    if mod:
        out["modulo"] = mod
    for f in ("evidence", "history", "open"):
        if meta.get(f):
            out[f] = meta[f]
    return out


def closure(index, start, depth=6):
    """[(id, depth, via)] reachable from ``start`` through depends_on / modulo."""
    seen, out, frontier = {start}, [], [(start, 0)]
    while frontier:
        cur, d = frontier.pop(0)
        rec = index.get(cur)
        if not rec or d >= depth:
            continue
        for field in ("modulo", "depends_on"):
            for nxt in _links(rec, field):
                if nxt in seen:
                    continue
                seen.add(nxt)
                out.append((nxt, d + 1, field))
                frontier.append((nxt, d + 1))
    return out


def reverse_links(index, target):
    """[(id, field)] of records naming ``target`` in a link field."""
    out = []
    for rid, rec in index.items():
        if rid.startswith("alias:") or rid == target:
            continue
        for f in LINK_FIELDS:
            if target in _links(rec, f):
                out.append((rid, f))
                break
    return sorted(out)


# ----------------------------------------------------------------------------
# Library, reviews, board
# ----------------------------------------------------------------------------

def expert_homes(workspace):
    return [Home(n, s) for n, s in workspace["instances"].items() if s.get("role") == "expert"]


def author_homes(workspace):
    return [Home(n, s) for n, s in workspace["instances"].items() if s.get("role") == "author"]


RE_BIB = re.compile(r"bib:([A-Za-z0-9_.+-]+)(?:#([A-Za-z0-9_.:-]+))?")
RE_CITE = re.compile(r"\\cite[tp]?\*?(?:\[[^\]]*\])?\{([^}]+)\}")


def bib_keys_in(text):
    keys = [m.group(1) for m in RE_BIB.finditer(text or "")]
    for m in RE_CITE.finditer(text or ""):
        keys += [k.strip() for k in m.group(1).split(",") if k.strip()]
    return list(dict.fromkeys(keys))


def cards_for(workspace, key, pinpoint=None, excerpt=False):
    """Library material for a bib key: cards, index row, meta, bib entry, excerpt."""
    out = []
    for h in expert_homes(workspace):
        if not h.path or not os.path.isdir(h.path):
            continue
        for p in sorted(glob.glob(os.path.join(h.path, "**", "cards", key, "*.md"),
                                  recursive=True)):
            pin = os.path.splitext(os.path.basename(p))[0]
            if pinpoint and pin != pinpoint:
                continue
            out.append({"key": key, "pinpoint": pin, "path": p.replace("\\", "/"),
                        "text": _read(p, MAX_TEXT)})
        idx = _read(os.path.join(h.path, "index.md")) or ""
        rows = [ln for ln in idx.split("\n") if re.search(r"\b%s\b" % re.escape(key), ln)]
        if rows:
            out.append({"key": key, "pinpoint": "index", "path": "index.md",
                        "text": "\n".join(rows[:5])})
        meta = _read(os.path.join(h.path, key + ".meta"), MAX_TEXT)
        if meta:
            out.append({"key": key, "pinpoint": "meta", "path": key + ".meta",
                        "text": meta, "raw": True})
        if excerpt:
            txt = _read(os.path.join(h.path, key + ".txt"), 3000)
            if txt:
                out.append({"key": key, "pinpoint": "extraction (first page, not the text)",
                            "path": key + ".txt", "text": txt, "raw": True})
    for h in author_homes(workspace):
        bib = "references.bib"
        if h.config:
            bib = h.config.get("paths", {}).get("bib") or bib
        text = _read(os.path.join(h.path or "", bib)) or ""
        m = re.search(r"@\w+\{\s*%s\s*,.*?\n\}" % re.escape(key), text, re.S)
        if m:
            out.append({"key": key, "pinpoint": "bib", "path": "%s:%s" % (h.name, bib),
                        "text": m.group(0), "raw": True})
    return out


def reviews_for(workspace, full_id):
    ns, _, local = full_id.partition(":")
    out = []
    for h in expert_homes(workspace):
        if not h.path:
            continue
        for cand in {local.replace(":", "-"), local, local.replace(":", "__")}:
            d = os.path.join(h.path, "reviews", ns, cand)
            for p in sorted(glob.glob(os.path.join(d, "**", "*.md"), recursive=True)):
                out.append({"path": p.replace("\\", "/"), "text": _read(p, MAX_TEXT)})
    for name, spec in workspace["instances"].items():
        if spec.get("role") != "researcher" or not spec.get("home"):
            continue
        for cand in (local, local.replace(":", "-")):
            d = os.path.join(spec["home"], "audits", cand)
            for p in sorted(glob.glob(os.path.join(d, "**", "*.md"), recursive=True)):
                out.append({"path": p.replace("\\", "/"), "text": _read(p, MAX_TEXT)})
    return out


def reports_for(board, ids, needles=()):
    """Board packets whose subject names one of ``ids`` (or whose text has a needle)."""
    out = []
    root = os.path.join(board or "", "packets")
    if not board or not os.path.isdir(root):
        return out
    ids = set(ids)
    for p in sorted(glob.glob(os.path.join(root, "**", "P-*.md"), recursive=True)):
        text = _read(p) or ""
        try:
            meta, body = ac.read_frontmatter(text)
        except ac.FrontmatterError:
            continue
        subj = set(str(s) for s in (meta.get("subject") or []))
        if not (subj & ids) and not any(n and n in text for n in needles):
            continue
        keep = []
        for name in ("Summary", "Established vs assumed", "Conclusion", "Question", "Class",
                     "Validation", "Raw outcome"):
            s = _section(body, name)
            if s:
                keep.append("#### %s\n\n%s" % (name, s))
        out.append({"packet": meta.get("packet"), "title": meta.get("title"),
                    "kind": meta.get("kind"), "state": meta.get("state"),
                    "status_proposed": meta.get("status_proposed"),
                    "path": p.replace("\\", "/"), "text": "\n\n".join(keep)[:MAX_TEXT]})
    return out


def run_cli(home, full_id):
    cmd = home.cli()
    if not cmd:
        return None
    # the notebook rule set's command line takes the bare id; lab and paper the full one
    local = full_id.split(":", 1)[1] if home.rule_set() == "notebook" else full_id
    try:
        args = shlex.split(cmd, posix=False) + ["show", local]
        r = subprocess.run(args, cwd=home.path, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return (r.stdout or r.stderr)[:MAX_TEXT]
    except (OSError, subprocess.SubprocessError) as e:
        return "cli failed: %s" % e


# ----------------------------------------------------------------------------
# Subjects
# ----------------------------------------------------------------------------

CONCEPT_PREFIXES = ("defn:", "def:", "definition:")


def infer_kind(subject, rec=None):
    if subject.startswith("bib:"):
        return "paper"
    if subject.startswith("concept:"):
        return "concept"
    if subject.endswith(".json") or subject.startswith("file:"):
        return "experiment"
    if rec is not None:
        k = str(rec["meta"].get("kind") or "").lower()
        if k == "direction":
            return "direction"
        if k in ("definition", "defn", "def"):
            return "concept"
        local = rec["id"].split(":", 1)[1]
        if local.startswith(CONCEPT_PREFIXES):
            return "concept"
        if rec["ns"] == "lab":
            return "experiment"
    return "claim"


def _base_bundle(subject, kind):
    return {"schema": 1, "kind": kind, "subject": subject, "title": subject,
            "generated": ac.today(), "object": {}, "statements": [], "sections": [],
            "cards": [], "reviews": [], "reports": [], "results": [], "notes": [],
            "sources": []}


def _add_graph(bundle, index, rid, depth):
    seen = {s["id"] for s in bundle["statements"]}
    for nid, d, via in closure(index, rid, depth):
        if nid in seen:
            continue
        rec = index.get(nid)
        if rec:
            bundle["statements"].append(stmt(rec, "modulo" if via == "modulo" and d == 1
                                             else "dependency", d))
        else:
            bundle["statements"].append({"id": nid, "title": nid, "status": None,
                                         "role": "dependency", "depth": d})
            bundle["notes"].append("%s is named in a %s list but has no record" % (nid, via))
        seen.add(nid)
    for nid, field in reverse_links(index, rid):
        if nid in seen:
            continue
        rec = index[nid]
        role = "rests_on"
        if field == "bears_on":
            role = "evidence_for" if rec["ns"] == "lab" else "bears_on_subject"
        if str(rec["meta"].get("kind") or "").lower() == "example":
            role = "example"
        bundle["statements"].append(stmt(rec, role, 1))
        seen.add(nid)
    for b in _links(index[rid], "bears_on"):
        if b not in seen:
            rec = index.get(b)
            bundle["statements"].append(stmt(rec, "bears_on", 1) if rec else
                                        {"id": b, "title": b, "status": None,
                                         "role": "bears_on", "depth": 1})
            seen.add(b)


def gather(subject, workspace, board=None, kind=None, depth=6, use_cli=False, index=None):
    """Build the bundle dict for ``subject``. Reads only."""
    index = index if index is not None else load_index(workspace)
    board = board or workspace.get("board")
    rec = None
    subj = subject
    if subject.startswith("file:"):
        subj = subject
    elif not subject.startswith(("bib:", "concept:")) and not subject.endswith(".json"):
        rec = index.get(subject) or index.get("alias:" + subject)
        if rec is None and ":" not in subject:
            subj = "bib:" + subject
    kind = kind or infer_kind(subj, rec)
    bundle = _base_bundle(subj, kind)

    if rec is not None:
        rid = rec["id"]
        bundle["subject"] = rid
        bundle["title"] = str(rec["meta"].get("title") or rid)
        bundle["object"] = stmt(rec, "subject", 0)
        bundle["statements"].append(bundle["object"])
        bundle["sources"].append(rec["path"].replace("\\", "/"))
        _add_graph(bundle, index, rid, depth)
        if kind == "direction":
            for s in bundle["statements"]:
                if s["role"] in ("rests_on", "bears_on_subject"):
                    s["role"] = "member"
        bundle["reviews"] = reviews_for(workspace, rid)
        ids = [s["id"] for s in bundle["statements"]]
        needles = [str(rec["meta"].get("where") or "")] if rec["ns"] == "lab" else []
        bundle["reports"] = reports_for(board, ids, [n for n in needles if n])
        keys = []
        for s in bundle["statements"]:
            keys += s.get("cites") or []
        for k in list(dict.fromkeys(keys))[:12]:
            bundle["cards"] += cards_for(workspace, k)
        if use_cli:
            out = run_cli(rec["home"], rid)
            if out:
                bundle["object"]["cli_show"] = out
        if kind == "experiment" and rec["meta"].get("where"):
            bundle["results"] += _results_for_script(rec, workspace)
    elif kind == "paper":
        m = RE_BIB.match(subj if subj.startswith("bib:") else "bib:" + subj)
        key, pin = (m.group(1), m.group(2)) if m else (subj[4:], None)
        bundle["subject"] = "bib:%s" % key + ("#%s" % pin if pin else "")
        bundle["title"] = key
        bundle["cards"] = cards_for(workspace, key, pin, excerpt=True)
        if not bundle["cards"]:
            bundle["notes"].append("no card, index row, meta or bib entry found for %s" % key)
        rx = re.compile(r"(bib:%s\b|\\cite[tp]?\*?(?:\[[^\]]*\])?\{[^}]*\b%s\b)"
                        % (re.escape(key), re.escape(key)))
        for rid, r in sorted(index.items()):
            if rid.startswith("alias:"):
                continue
            text = r["body"] + " " + json.dumps(r["meta"], default=str)
            st = stmt(r, "cites", 1)
            if rx.search(text) or key in (st.get("cites") or []):
                bundle["statements"].append(st)
        bundle["reviews"] = []
    elif kind == "experiment":
        bundle.update(_gather_result(subj, workspace, index, board))
    elif kind == "concept":
        term = subj.split(":", 1)[1] if subj.startswith("concept:") else subj
        bundle["subject"] = "concept:%s" % term
        bundle["title"] = term
        rx = re.compile(re.escape(term), re.I)
        for rid, r in sorted(index.items()):
            if rid.startswith("alias:"):
                continue
            k = str(r["meta"].get("kind") or "").lower()
            local = rid.split(":", 1)[1]
            is_def = k in ("definition", "defn", "def") or local.startswith(CONCEPT_PREFIXES)
            if is_def and (rx.search(str(r["meta"].get("title") or "")) or rx.search(local)):
                bundle["statements"].append(stmt(r, "definition", 1))
        bundle["cards"] = _pack_snippets(workspace, term)
        if not bundle["statements"]:
            bundle["notes"].append("no definition in any registry matches %r" % term)
    else:
        bundle["notes"].append("no registry record for %s" % subject)
    macros, seen_ns = {}, set()
    for s in bundle["statements"]:
        ns = str(s.get("id", "")).split(":", 1)[0]
        if ns in seen_ns:
            continue
        seen_ns.add(ns)
        for h in author_homes(workspace):
            if h.ns == ns and h.path:
                macros.update(latex_macros(h.path))
    if macros:
        bundle["macros"] = macros
    for s in bundle["statements"]:
        if "source" in s and s["source"] not in bundle["sources"]:
            bundle["sources"].append(s["source"])
    return bundle


def _scientist(workspace):
    for n, s in workspace["instances"].items():
        if s.get("role") == "scientist":
            return Home(n, s)
    return None


def _results_for_script(rec, workspace):
    """Result JSONs whose name starts like the experiment script's (the lab convention)."""
    sci = rec["home"]
    stem = os.path.splitext(os.path.basename(str(rec["meta"].get("where"))))[0]
    out = []
    for p in sorted(glob.glob(os.path.join(sci.path or "", "results", stem + "*.json")))[:3]:
        out.append({"path": p.replace("\\", "/"), "text": _read(p, MAX_RESULT), "raw": True})
    return out


def _gather_result(subj, workspace, index, board):
    sci = _scientist(workspace)
    rel = subj
    if subj.startswith("file:"):
        inst, _, rel = subj[5:].partition("/")
        sci = Home(inst, workspace["instances"].get(inst, {})) if inst in \
            workspace["instances"] else sci
    path = rel if os.path.isabs(rel) else os.path.join((sci.path if sci else "") or "", rel)
    out = {"subject": subj, "title": os.path.basename(rel), "results": [], "statements": [],
           "reports": [], "reviews": [], "notes": []}
    text = _read(path, MAX_RESULT)
    if text is None:
        out["notes"].append("result file not found: %s" % path)
        return out
    out["results"].append({"path": path.replace("\\", "/"), "text": text, "raw": True})
    name = os.path.basename(path)
    try:
        data = json.loads(_read(path) or "{}")
    except ValueError:
        data = {}
    script = ""
    if isinstance(data, dict):
        for k in ("script", "experiment", "source"):
            if isinstance(data.get(k), str):
                script = data[k]
                break
    stem = os.path.splitext(name)[0]
    claims = []
    for rid, r in sorted(index.items()):
        if rid.startswith("alias:") or r["ns"] != (sci.ns if sci else r["ns"]):
            continue
        blob = json.dumps(r["meta"], default=str) + r["body"]
        where = str(r["meta"].get("where") or "")
        wstem = os.path.splitext(os.path.basename(where))[0]
        if name in blob or (script and script in blob) or (wstem and stem.startswith(wstem)):
            claims.append(r)
    ids = []
    for r in claims:
        out["statements"].append(stmt(r, "subject" if not ids else "related", 0 if not ids
                                      else 1))
        ids.append(r["id"])
        for b in _links(r, "bears_on"):
            br = index.get(b)
            out["statements"].append(stmt(br, "bears_on", 1) if br else
                                     {"id": b, "title": b, "status": None, "role": "bears_on"})
        out["reviews"] += reviews_for(workspace, r["id"])
    if claims:
        out["object"] = out["statements"][0]
    else:
        out["notes"].append("no lab claim names %s" % name)
    out["reports"] = reports_for(board, ids, [name])
    return out


def _pack_snippets(workspace, term, limit=5):
    """Paragraphs mentioning ``term`` in the domain packs of the workspace's domains."""
    domains = set()
    for s in workspace["instances"].values():
        domains.update(s.get("domains") or [])
    root = os.path.dirname(workspace.get("_path") or "")
    out = []
    rx = re.compile(re.escape(term), re.I)
    for d in sorted(domains):
        for p in sorted(glob.glob(os.path.join(root, "domains", d, "**", "*.md"),
                                  recursive=True)):
            text = _read(p) or ""
            for para in re.split(r"\n\s*\n", text):
                if rx.search(para):
                    out.append({"key": d, "pinpoint": os.path.relpath(p, root).replace(
                        "\\", "/"), "path": p.replace("\\", "/"), "text": para[:1500]})
                    if len(out) >= limit:
                        return out
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gather_deep_dive.py",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("subject")
    ap.add_argument("--kind", choices=("concept", "claim", "paper", "experiment", "direction"))
    ap.add_argument("--out"); ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--cli", action="store_true", help="also attach '<registry cli> show'")
    ap.add_argument("--workspace"); ap.add_argument("--board")
    a = ap.parse_args(argv)
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    try:
        ws = ac.load_workspace(a.workspace)
    except ac.ConfigError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    bundle = gather(a.subject, ws, a.board, a.kind, a.depth, a.cli)
    text = json.dumps(bundle, indent=2, ensure_ascii=False, default=str) + "\n"
    if a.out:
        ac.atomic_write(a.out, text)
        print(os.path.abspath(a.out))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
