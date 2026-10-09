"""Profile ``fsl-claims``: the lab (``lab:``) and paper (``paper:``) registries.

This is the lab's ``scripts/claims.py`` on the engine core (merge proposal,
phase 2): the same schema (closed field set, evidence rows, history in the
frontmatter, the ten statuses, "proved or supported needs evidence"), the same checks,
back-links, views and command line, with three changes:

* **The dialect.** Records are read with the core parser (kb.py's), which quotes and
  unquotes; the old reader kept quotes literally. A key with no value (``evidence:``
  alone) still reads as empty. A file the dialect rejects but the old reader accepts
  is still loaded (transitional, for homes not yet requoted) and ``check`` warns about
  it. ``new`` and the mutations write the dialect (``evidence: []``, not ``evidence:``).
* **Federation through profiles** (phase 3). ``kb_index`` (a regex over the notebook's files)
  is gone: a foreign id is resolved by loading its home through its own profile
  (``core.federation``), and "refuted" across namespaces is the projection class
  ``false`` instead of the ``Disproved`` special case. Homes come from workspace.json
  (``core.workspace``), not from a hard-coded table, so worktrees resolve each other.
* **Mutations** (phase 4). ``set-status`` (grounds checked by ``core.grounds``, plan
  section 8) and ``evidence`` (append one row), both line-preserving edits that keep
  the file's line endings; ``deps``/``usedby`` over the cross-namespace graph.

The rule set of a namespace (``lab`` or ``paper``) decides the extra rules: a
``paper`` claim names a ``\\label`` of the draft and its status agrees with the colour.

**Schema v2** (R5, ``core/schema.py``). A record with a ``lifecycle`` field is in the
academy object schema: the generic rules come from the core, and this profile keeps
only its home rules (the file path from the id, "proved or supported needs evidence",
evidence refs that must exist, ``where``, the paper's label and colour rules, the lab's
back-links). Both schemas are read, so a v1 home (and the v1 test fixtures) still works;
``new`` writes v2 into a registry that already holds v2 records.
"""

import argparse
import ast
import datetime
import html
import json
import re
import sqlite3
import sys
from pathlib import Path

from ..core import fm, legacy_fm, workspace, federation, projection, schema, grounds as _grounds
from ..core.edit import Doc
from ..core.model import Record, Store, statement_hash_of

#: the repo used when a function is called without one (the shim sets its own lab)
ROOT = Path.cwd()

STATUSES = (
    "refuted", "refuted-as-stated", "open", "conjectured", "sketch",
    "supported", "proved-modulo", "proved", "superseded", "dropped",
)
STATUS_BLURB = {
    "refuted": "false; a counterexample or disproof is recorded",
    "refuted-as-stated": "false as written; the repaired statement is `superseded_by`",
    "open": "not settled; may have partial or unrecorded evidence",
    "conjectured": "believed, stated as a conjecture",
    "sketch": "an argument exists but has not been verified",
    "supported": "a bounded computation found no counterexample; not a proof",
    "proved-modulo": "proved, assuming the inputs listed under `open`",
    "proved": "proved and verified",
    "superseded": "replaced by `superseded_by`; kept for history",
    "dropped": "no longer pursued",
}
EVIDENCE_KINDS = ("experiment", "audit", "verdict", "hand", "citation", "note")
LIST_FIELDS = ("bears_on", "depends_on", "evidence", "history", "open", "tags")
SCALAR_FIELDS = ("id", "title", "status", "where", "supersedes", "superseded_by")
REQUIRED = ("id", "title", "status", "history")
ID_RE = re.compile(r"^[a-z0-9]+:[A-Za-z0-9:_.\-]+$")
#: an id of another namespace: its own profile decides what it may contain
FOREIGN_ID_RE = re.compile(r"^[a-z0-9]+:\S+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
#: the canonical field order and the fields written as block lists
FIELD_ORDER = ("id", "title", "status", "where", "supersedes", "superseded_by",
               "bears_on", "depends_on", "evidence", "history", "open", "tags")
BLOCK_FIELDS = LIST_FIELDS
#: schema v2: the v1 blurbs, with `modulo` for `open` and the lifecycle words
STATUS_BLURB_V2 = dict(STATUS_BLURB, **{
    "proved-modulo": "proved, assuming the inputs listed under `modulo`",
    "refuted-as-stated": "false as written; the repaired statement supersedes it",
    "superseded": "lifecycle superseded: replaced by a record that `supersedes` it; kept for history",
    "dropped": "lifecycle dropped: no longer pursued",
})
#: paper records keep a status on every kind (the colour rule); lab records are claims
V2_STATUS_KINDS = {"paper": schema.KINDS, "lab": schema.STATUS_KINDS}
#: the lab/paper profile's own field in schema v2: ``open``, the caveats and next steps
#: of a record (v1's ``open:`` less the missing inputs, which are ``modulo``)
V2_EXTRA = ("open",)
V2_ORDER = schema.FIELD_ORDER[:-2] + V2_EXTRA + ("evidence", "history")
V2_BLOCK = schema.BLOCK_FIELDS + V2_EXTRA
V2_AFTER = ("id", "kind", "form", "title", "status", "statement", "modulo", "depends_on",
            "bears_on", "supersedes", "lifecycle", "aliases", "domain", "tags", "proof",
            "where", "open")

_cache = federation.CACHE


def set_default_repo(repo):
    """The repo a function uses when it is given none (the shim's lab)."""
    global ROOT
    ROOT = Path(repo)


def _repo(repo):
    return Path(repo) if repo is not None else ROOT


def _empty(key):
    return [] if key in LIST_FIELDS else ""


def format_scalar(s):
    return fm.format_scalar_single(s)


def serialize(fields):
    """The frontmatter of ``fields`` in the dialect (without fences)."""
    return fm.serialize_frontmatter(fields, FIELD_ORDER, BLOCK_FIELDS, fm.format_scalar_single)


# ---------------------------------------------------------------------- paths

def registry_root(repo=None):
    repo = _repo(repo)
    rel = "claims"
    cfg = workspace.read_config(repo)
    croot = ((cfg or {}).get("registry") or {}).get("root")
    qcfg = repo / "queue" / "config.json"
    if isinstance(croot, str) and croot:
        rel = croot
    elif qcfg.exists():
        try:
            rel = json.loads(qcfg.read_text(encoding="utf-8")).get("claimsRoot", rel)
        except ValueError:
            pass
    p = Path(rel)
    return p if p.is_absolute() else (repo / p).resolve()


def file_for(root, cid):
    ns, name = cid.split(":", 1)
    return root / ns / (name.replace(":", "__") + ".md")


# ------------------------------------------------------------------ federation

class _Homes(dict):
    """{ns: home directory name}, from workspace.json (read on each access)."""

    def _fresh(self):
        return {ns: info["name"] for ns, info in workspace.namespaces().items()}

    def __getitem__(self, k):
        return self._fresh()[k]

    def get(self, k, d=None):
        return self._fresh().get(k, d)

    def __contains__(self, k):
        return k in self._fresh()

    def __iter__(self):
        return iter(self._fresh())

    def items(self):
        return self._fresh().items()

    def keys(self):
        return self._fresh().keys()

    def values(self):
        return self._fresh().values()

    def __len__(self):
        return len(self._fresh())

    def __repr__(self):
        return repr(self._fresh())


HOMES = _Homes()


def home(ns, repo=None):
    """The home repo of namespace `ns`, or None when it is not beside `repo`."""
    return workspace.home_of(ns, _repo(repo))


def _cached(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def paper_labels(base):
    """Every \\label in base/sections/*.tex."""
    def scan():
        out = set()
        for p in sorted((base / "sections").glob("*.tex")):
            out.update(re.findall(r"\\label\{([^}]+)\}", p.read_text(encoding="utf-8", errors="replace")))
        return out
    return _cached(("labels", base), scan)


def paper_colours(base):
    """{label: colour} from the generated Drafts/statements.md (established = black)."""
    def scan():
        p = base / "Drafts" / "statements.md"
        if not p.exists():
            return {}
        row = re.compile(r"^\|\s*`([^`]+)`\s*\|[^|]*\|[^|]*\|\s*([a-z]+)\s*\|", re.M)
        return dict(row.findall(p.read_text(encoding="utf-8", errors="replace")))
    return _cached(("colours", base), scan)


def _is_foreign(ns, repo):
    return ns in workspace.namespaces() and ns != workspace.repo_ns(repo)


def _resolve_foreign(cid, repo):
    """(state, detail, class) of an id owned by another repo; state is ok, missing or
    unchecked; detail is the status when ok, else the reason."""
    ns, name = cid.split(":", 1)
    state, rec, detail = federation.resolve(cid, repo)
    if state == "unchecked":
        return "unchecked", detail, projection.NA
    if state == "ok":
        return "ok", rec.status, rec.cls
    s = federation.store_from(ns, repo)
    if state == "alias":
        if s.profile == "s1-kb":
            if name in s.aliases(rec.id):
                return "missing", f"`{name}` is an old label of {HOMES[ns]}; the id is `{rec.qid}`", None
            return "missing", f"`{name}` is not the id; the id is `{rec.qid}`", None
        return "missing", f"`{name}` is not the id; the id is `{rec.qid}`", None
    if s.profile == "s1-kb":
        return "missing", f"no such id in {HOMES[ns]} (registry.py resolve <text>)", None
    if workspace.rule_set(ns, s.home) == "paper":
        if name in paper_labels(s.home):
            return "ok", "", projection.NA
        return "missing", f"`{name}` is not a \\label in {HOMES[ns]}/sections", None
    return "missing", f"not in {registry_root(s.home)}", None


def foreign(cid, repo=None):
    """Resolve an id owned by another repo. Returns (state, detail):
    ("ok", status), ("missing", hint), or ("unchecked", reason)."""
    state, detail, _ = _resolve_foreign(cid, _repo(repo))
    return state, detail


# --------------------------------------------------------------------- parsing

class Claim:
    def __init__(self, path, fields, body):
        self.path, self.fields, self.body = path, fields, body
        #: the dialect's error when the file was read by the old reader (transitional)
        self.dialect_error = None

    def __getattr__(self, k):
        f = self.__dict__.get("fields", {})
        if k == "superseded_by" and schema.is_v2(f):
            return ", ".join(self.__dict__.get("derived_superseded_by") or [])
        if k in f:
            return f[k]
        if k in LIST_FIELDS or k in schema.LIST_FIELDS:
            return []
        if k in SCALAR_FIELDS or k in schema.SCALAR_FIELDS:
            return ""
        raise AttributeError(k)

    @property
    def ns(self):
        return self.id.split(":", 1)[0]

    @property
    def v2(self):
        return schema.is_v2(self.fields)

    @property
    def state(self):
        """What the record is now: the status, or (v2) the lifecycle when not active."""
        return schema.state(self.fields) if self.v2 else self.status

    @property
    def open_items(self):
        """What is still open: v1 ``open``; v2 ``modulo`` (missing inputs) then ``open``
        (caveats and next steps)."""
        if not self.v2:
            v = self.fields.get("open")
            return v if isinstance(v, list) else []
        out = []
        for k in ("modulo", "open"):
            v = self.fields.get(k)
            out += v if isinstance(v, list) else []
        return out

    @property
    def modulo(self):
        v = self.fields.get("modulo") if self.v2 else None
        return v if isinstance(v, list) else []

    def evidence_cells(self, ev):
        """``(type, ref, verdict, run_id, note)`` of one of this record's rows."""
        if self.v2:
            return schema.evidence_cells(ev)
        k, ref, verdict, note = split_row(ev, 4)
        return k, ref, verdict, "", note

    def links(self):
        out = [("bears_on", t) for t in self.bears_on]
        out += [("depends_on", t) for t in self.depends_on]
        if self.v2:
            sup = self.fields.get("supersedes")
            out += [("supersedes", t) for t in (sup if isinstance(sup, list) else [sup] if sup else [])]
            out += [("modulo", t) for t in self.modulo if schema.looks_like_id(t)]
            return out
        for rel in ("supersedes", "superseded_by"):
            if self.fields.get(rel):
                out.append((rel, self.fields[rel]))
        return out


def parse_strict(text, path=None):
    """``(fields, body)`` in the dialect; ValueError with a claims.py-style message."""
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter: the file must start with a line `---`")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("frontmatter is not closed by a line `---`")
    try:
        fields = fm.parse_frontmatter(lines[1:end], str(path or "<string>"), 2, _empty)
    except fm.FrontmatterError as exc:
        raise ValueError(f"line {exc.lineno}: {exc.msg}")
    body = "\n".join(lines[end + 1:]).strip()
    return fields, body


def parse_text(text, path=None, fallback=True):
    """A :class:`Claim` from a record's text (the dialect; see the module docstring
    for the transitional fallback to the old reader)."""
    try:
        fields, body = parse_strict(text, path)
        return Claim(path, fields, body)
    except ValueError as strict_err:
        if not fallback:
            raise
        try:
            fields, body = legacy_fm.parse(text, LIST_FIELDS)
        except ValueError:
            raise strict_err
        c = Claim(path, fields, body)
        c.dialect_error = str(strict_err)
        return c


def split_row(item, n):
    parts = [p.strip() for p in item.split("|", n - 1)]
    return parts + [""] * (n - len(parts))


def load(root):
    claims, errors = [], []
    if not root.exists():
        return claims, errors
    for p in sorted(root.rglob("*.md")):
        if p.name in ("INDEX.md", "README.md"):
            continue
        try:
            claims.append(parse_text(p.read_text(encoding="utf-8"), p))
        except ValueError as e:
            errors.append(f"{p}: ERROR: {e}")
    derived = schema.derived_superseded_by(
        (c.fields.get("id", ""), c.fields) for c in claims if c.v2)
    for c in claims:
        if c.v2:
            c.derived_superseded_by = derived.get(c.fields.get("id", ""), [])
    return claims, errors


# ---------------------------------------------------------------------- checks

#: `file:<instance>/<path>`, a file in another instance's home (docs/protocol.md, ref forms)
RE_INSTANCE_FILE = re.compile(r"^file:([a-z]+@[a-z0-9][a-z0-9-]*)/(.+)$")


def resolve_ref(ref, repo=None):
    """`path`, `Repo:path` or `file:<instance>/path` (the protocol's form, e.g. an
    expert review `file:expert@main/reviews/...`). Returns a Path to test, or None when it
    cannot be checked."""
    repo = _repo(repo)
    if ref.startswith(("http://", "https://")):
        return None
    m = RE_INSTANCE_FILE.match(ref)
    if m:
        home = workspace.instance_home(m.group(1), repo)
        return None if home is None else home / m.group(2).split("#")[0]
    m = re.match(r"^([A-Za-z0-9_\-]+):(.+)$", ref)
    if m and not re.match(r"^[A-Za-z]:[\\/]", ref):
        name, rest = m.group(1), m.group(2)
        # a worktree (<lab>-academy) sees the sibling of its own suffix first, as
        # core/workspace.home_of does for namespaces (R6: a notebook's audits/ exists only in
        # its migration worktree until that branch is merged)
        _, suffix = workspace._by_name(repo)
        cands = [repo] if name == repo.name else \
            ([repo.parent / (name + suffix)] if suffix else []) + [repo.parent / name]
        base = next((c for c in cands if c.exists()), None)
        if base is None:
            return None
        return base / rest.split("#")[0]
    return repo / ref.split("#")[0]


def _false_word(status):
    """How a refuted target is named in the depends_on warning (claims.py's words)."""
    return status if status in ("refuted", "refuted-as-stated") else "refuted"


def check(claims, repo=None, root=None, only=None):
    """Return (errors, warnings) as `path: LEVEL: message` strings."""
    repo = _repo(repo)
    root = root or registry_root(repo)
    own_ns = workspace.repo_ns(repo)
    known = workspace.namespaces()
    errs, warns = [], []
    by_id = {}
    for c in claims:
        by_id.setdefault(c.fields.get("id", ""), []).append(c)
    for c in claims:
        if only and c.path.resolve() not in only:
            continue
        where = c.path
        e = lambda m: errs.append(f"{where}: ERROR: {m}")
        w = lambda m: warns.append(f"{where}: WARN: {m}")
        if c.dialect_error:
            w(f"not in the registry dialect ({c.dialect_error}); read with the old parser. "
              "Requote it: py -m registry requote")
        if c.v2:
            if _check_v2(c, repo, root, by_id, e, w):
                _check_common(c, repo, own_ns, known, by_id, e, w)
            continue
        missing = [k for k in REQUIRED if not c.fields.get(k)]
        if missing:
            e("missing field(s): " + ", ".join(missing))
            continue
        unknown = set(c.fields) - set(LIST_FIELDS) - set(SCALAR_FIELDS)
        if unknown:
            e("unknown field(s): " + ", ".join(sorted(unknown)))
        if not ID_RE.match(c.id):
            e(f"id `{c.id}` is not `<ns>:<name>`")
            continue
        if len(by_id[c.id]) > 1:
            e(f"id `{c.id}` is used by {len(by_id[c.id])} files")
        if c.path.resolve() != file_for(root, c.id).resolve():
            e(f"id `{c.id}` belongs in {file_for(root, c.id).relative_to(root)}")
        if c.status not in STATUSES:
            e(f"status `{c.status}` is not one of: " + ", ".join(STATUSES))
        if c.status in ("refuted-as-stated", "superseded") and not c.superseded_by:
            e(f"status `{c.status}` needs `superseded_by`")
        # history: newest first, dated, and it ends where the status is
        dates = []
        for h in c.history:
            d, s, _ = split_row(h, 3)
            if not DATE_RE.match(d):
                e(f"history line `{h}` does not start with YYYY-MM-DD |")
            else:
                dates.append(d)
            if s and s not in STATUSES:
                e(f"history status `{s}` is not in the vocabulary")
        if dates != sorted(dates, reverse=True):
            e("history is not newest first")
        if c.history and split_row(c.history[0], 3)[1] != c.status:
            e(f"latest history status `{split_row(c.history[0], 3)[1]}` != status `{c.status}`")
        for ev in c.evidence:
            kind, ref, verdict, _ = split_row(ev, 4)
            if kind not in EVIDENCE_KINDS:
                e(f"evidence kind `{kind}` is not one of: " + ", ".join(EVIDENCE_KINDS))
            if not ref:
                e(f"evidence `{ev}` has no ref")
                continue
            if kind in ("experiment", "audit", "verdict"):
                p = resolve_ref(ref, repo)
                if p is not None and not p.exists():
                    e(f"evidence ref `{ref}` does not exist")
        if c.where:
            p = resolve_ref(c.where, repo)
            if p is not None and not p.exists() and not c.where.startswith("paper:"):
                w(f"`where` path `{c.where}` does not exist")
        if c.status in ("proved", "supported") and not c.evidence:
            e(f"status `{c.status}` with no evidence")
        _check_common(c, repo, own_ns, known, by_id, e, w)
    return errs, warns


def _cls(c):
    return schema.project(c.fields) if c.v2 else projection.project(c.status, projection.FSL)


def _check_common(c, repo, own_ns, known, by_id, e, w):
    """The home rules both schemas share: the namespace, the paper's rules, the links."""
    if c.ns in known and c.ns != own_ns:
        e(f"`{c.ns}:` claims live in {known[c.ns]['name']}, not here")
    elif workspace.rule_set(c.ns, repo) == "paper":
        check_paper_claim(c, repo, e, w)
    for rel, tgt in c.links():
        ns = tgt.split(":", 1)[0]
        if tgt in by_id:
            status = by_id[tgt][0].status
            cls = _cls(by_id[tgt][0])
        elif FOREIGN_ID_RE.match(tgt) and _is_foreign(ns, repo):
            state, status, cls = _resolve_foreign(tgt, repo)
            if state == "missing":
                e(f"{rel} `{tgt}`: {status}")
                continue
        else:
            e(f"{rel} `{tgt}` is not a claim in the registry")
            continue
        if rel == "depends_on" and cls == projection.FALSE:
            w(f"depends on `{tgt}`, which is {_false_word(status)}")


def _check_v2(c, repo, root, by_id, e, w):
    """A schema-v2 record: the core's generic rules, then this home's. False when the
    record is too broken to check further (no id, a bad id)."""
    cid = c.fields.get("id")
    rules = workspace.rule_set(cid.split(":", 1)[0], repo) \
        if isinstance(cid, str) and ":" in cid else None
    for level, msg in schema.check_record(
            c.fields, extra_fields=V2_EXTRA,
            status_kinds=V2_STATUS_KINDS.get(rules, schema.STATUS_KINDS)):
        (e if level == "error" else w)(msg)
    if not isinstance(cid, str) or not ID_RE.match(cid):
        if isinstance(cid, str):
            e(f"id `{cid}` is not `<ns>:<name>`")
        return False
    if len(by_id[cid]) > 1:
        e(f"id `{cid}` is used by {len(by_id[cid])} files")
    if c.path.resolve() != file_for(root, cid).resolve():
        e(f"id `{cid}` belongs in {file_for(root, cid).relative_to(root)}")
    if c.status == "refuted-as-stated" and not c.superseded_by:
        e("status `refuted-as-stated` needs a record that `supersedes` it")
    if c.fields.get("lifecycle") == "superseded" and not c.superseded_by:
        e("lifecycle `superseded` needs a record that `supersedes` it")
    for ev in c.evidence:
        kind, ref = schema.evidence_cells(ev)[:2]
        if ref and kind in ("experiment", "audit", "verdict"):
            p = resolve_ref(ref, repo)
            if p is not None and not p.exists():
                e(f"evidence ref `{ref}` does not exist")
    if c.where:
        p = resolve_ref(c.where, repo)
        if p is not None and not p.exists() and not c.where.startswith("paper:"):
            w(f"`where` path `{c.where}` does not exist")
    if c.status in ("proved", "supported") and not c.evidence \
            and c.fields.get("lifecycle", "active") == "active":
        e(f"status `{c.status}` with no evidence")
    return True


def check_paper_claim(c, repo, e, w):
    """A `paper:` claim names a \\label, and its status agrees with the draft colour.
    Black (established) needs `proved` or `proved-modulo`, so a refuted statement cannot
    be black; a black statement backed by neither a verdict nor a citation is a warning
    (the worklist of statements never verified)."""
    name = c.id.split(":", 1)[1]
    if name not in paper_labels(repo):
        e(f"`{name}` is not a \\label in sections/")
        return
    colour = paper_colours(repo).get(name)
    if colour == "established":
        if c.status not in ("proved", "proved-modulo"):
            e(f"black in the draft, but status is `{c.status}`")
        elif not any(c.evidence_cells(ev)[0] in ("verdict", "citation") for ev in c.evidence):
            w("black in the draft with no verdict or citation behind it")


# --------------------------------------------------------------- back-links

def experiment_claims(repo=None):
    """{experiment path: [claim ids]} from the `Claims:` header line."""
    repo = _repo(repo)
    out = {}
    for p in sorted((repo / "experiments").glob("*.py")):
        try:
            doc = ast.get_docstring(ast.parse(p.read_text(encoding="utf-8"))) or ""
        except SyntaxError:
            continue
        m = re.search(r"^Claims:\s*(.+)$", doc, re.M)
        if m:
            out[p.relative_to(repo).as_posix()] = [t.strip() for t in m.group(1).split(",") if t.strip()]
    return out


def result_claims(repo=None):
    repo = _repo(repo)
    out = {}
    for p in sorted((repo / "results").rglob("*.json")):
        try:
            with p.open(encoding="utf-8") as f:
                head = f.read(4096)
            if '"claims"' not in head:
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        o = d.get("outcome") or {}
        summary = " ".join(str(x) for x in (o.get("kind"), o.get("status"),
                                            o.get("count") if o.get("kind") == "search" else None)
                           if x is not None)
        out[p.relative_to(repo).as_posix()] = (d.get("claims") or [], summary)
    return out


def backlinks(cid, claims, repo=None):
    repo = _repo(repo)
    lines = []
    for c in claims:
        for rel, tgt in c.links():
            if tgt == cid:
                lines.append(f"  {c.id} {rel} this   [{c.state}]")
    for path, ids in experiment_claims(repo).items():
        if cid in ids:
            lines.append(f"  experiment {path}")
    for path, (ids, summary) in result_claims(repo).items():
        if cid in ids:
            lines.append(f"  result {path}" + (f"   [{summary}]" if summary else ""))
    return lines


# ---------------------------------------------------------------------- sql

def to_sqlite(claims):
    db = sqlite3.connect(":memory:")
    db.executescript("""
        create table claims (id text primary key, ns text, status text, title text,
                             "where" text, file text, body text, kind text,
                             lifecycle text);
        create table evidence (claim text, kind text, ref text, verdict text, note text,
                               run_id text);
        create table history (claim text, date text, status text, note text);
        create table links (src text, rel text, dst text);
        create table open_items (claim text, item text);
    """)
    for c in claims:
        if not c.fields.get("id"):
            continue
        db.execute("insert or replace into claims values (?,?,?,?,?,?,?,?,?)",
                   (c.id, c.ns, c.status, c.title, c.where, str(c.path), c.body,
                    c.fields.get("kind") if c.v2 else None,
                    c.fields.get("lifecycle") if c.v2 else None))
        for ev in c.evidence:
            k, ref, verdict, run, note = c.evidence_cells(ev)
            db.execute("insert into evidence values (?,?,?,?,?,?)",
                       (c.id, k, ref, verdict, note, run or None))
        for h in c.history:
            db.execute("insert into history values (?,?,?,?)", (c.id, *split_row(h, 3)))
        for rel, tgt in c.links():
            db.execute("insert into links values (?,?,?)", (c.id, rel, tgt))
        for o in c.open_items:
            db.execute("insert into open_items values (?,?)", (c.id, o))
    return db


# ------------------------------------------------------------------- render

def _blurbs(claims):
    return STATUS_BLURB_V2 if any(c.v2 for c in claims) else STATUS_BLURB


def render_index(claims):
    order = {s: i for i, s in enumerate(STATUSES)}
    blurb = _blurbs(claims)
    out = ["# Claims index", "",
           "Generated by `registry.py render`; do not edit. One line per claim, "
           "grouped by status. `registry.py show <id>` gives the evidence.", ""]
    counts = {s: sum(c.state == s for c in claims) for s in STATUSES}
    out.append(" · ".join(f"{s} {n}" for s, n in counts.items() if n))
    for s in sorted({c.state for c in claims}, key=lambda s: order.get(s, 99)):
        out += ["", f"## {s} — {blurb.get(s, '')}", ""]
        for c in sorted((c for c in claims if c.state == s), key=lambda c: c.id):
            extra = f" → `{c.superseded_by}`" if c.superseded_by else ""
            sup = f" (bears on {', '.join('`%s`' % x for x in c.bears_on)})" if c.bears_on else ""
            out.append(f"- `{c.id}` {c.title}{extra}{sup}")
    return "\n".join(out) + "\n"


def render_html(claims):
    order = {s: i for i, s in enumerate(STATUSES)}
    rows = []
    for c in sorted(claims, key=lambda c: (order.get(c.state, 99), c.id)):
        ev = "<br>".join(html.escape(e) for e in c.evidence) or "&mdash;"
        hist = "<br>".join(html.escape(h) for h in c.history)
        opn = "<br>".join(html.escape(o) for o in c.open_items)
        links = "<br>".join(html.escape(f"{r} {t}") for r, t in c.links())
        st = c.state
        rows.append(
            f'<tr data-status="{html.escape(st)}"><td><code>{html.escape(c.id)}</code></td>'
            f'<td><span class="st st-{html.escape(st)}">{html.escape(st)}</span></td>'
            f'<td>{html.escape(c.title)}<details><summary>details</summary>'
            f'<p><b>where</b> {html.escape(c.where or "—")}</p><p><b>links</b><br>{links or "—"}</p>'
            f'<p><b>evidence</b><br>{ev}</p><p><b>{"modulo / open" if c.v2 else "open"}</b><br>{opn or "—"}</p>'
            f'<p><b>history</b><br>{hist}</p></details></td></tr>')
    opts = "".join(f'<option value="{s}">{s}</option>' for s in STATUSES)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claims index</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#1d1d1b; --muted:#6b6a66; --line:#e3e1db; --chip:#efede7;
  --bad:#b3261e; --warn:#9a6700; --ok:#1a7f37; --info:#0b5cad; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#161615; --fg:#ecebe7; --muted:#a3a19b; --line:#34332f; --chip:#262522;
  --bad:#f2786e; --warn:#e3b341; --ok:#56d364; --info:#79b8ff; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.45 system-ui, sans-serif;
  margin:0 auto; max-width:1100px; padding:24px 16px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} p.sub {{ color:var(--muted); margin:0 0 16px; }}
.bar {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }}
input, select {{ background:var(--chip); color:var(--fg); border:1px solid var(--line);
  border-radius:6px; padding:6px 8px; font:inherit; }} input {{ flex:1; min-width:180px; }}
table {{ width:100%; border-collapse:collapse; }}
td {{ border-top:1px solid var(--line); padding:8px 6px; vertical-align:top; }}
td:first-child {{ width:30%; word-break:break-all; }} td:nth-child(2) {{ width:120px; }}
code {{ font-size:13px; }} details {{ color:var(--muted); font-size:13px; }}
.st {{ font-size:12px; padding:2px 8px; border-radius:10px; background:var(--chip); white-space:nowrap; }}
.st-refuted, .st-refuted-as-stated {{ color:var(--bad); }}
.st-open, .st-conjectured, .st-sketch {{ color:var(--warn); }}
.st-supported, .st-proved-modulo, .st-proved {{ color:var(--ok); }}
.st-superseded, .st-dropped {{ color:var(--muted); }}
@media (max-width:640px) {{ td:first-child {{ width:auto; }} }}
</style></head><body>
<h1>Claims</h1>
<p class="sub">Generated by <code>registry.py render</code> on {datetime.date.today()}; {len(claims)} claims.</p>
<div class="bar"><input id="q" placeholder="filter by id, title, evidence…">
<select id="s"><option value="">all statuses</option>{opts}</select></div>
<table><tbody id="t">{''.join(rows)}</tbody></table>
<script>
const q=document.getElementById('q'), s=document.getElementById('s');
function f(){{ const t=q.value.toLowerCase(), st=s.value;
  for (const r of document.querySelectorAll('#t tr')) {{
    r.style.display = (!st || r.dataset.status===st) && r.textContent.toLowerCase().includes(t) ? '' : 'none'; }} }}
q.oninput=f; s.onchange=f;
</script></body></html>
"""


# ------------------------------------------------------ experiments ledger

def experiment_kind(repo, script):
    p = repo / script
    if not p.exists():
        return ""
    try:
        doc = ast.get_docstring(ast.parse(p.read_text(encoding="utf-8"))) or ""
    except SyntaxError:
        return ""
    m = re.search(r"^Kind:\s*(\w+)", doc, re.M)
    return m.group(1) if m else ""


def queue_jobs(repo, script):
    """'done ok x2, running 1' for the jobs of `script` in repo/queue (local state)."""
    counts = {}
    for d in ("pending", "running", "done", "parked"):
        for p in sorted((repo / "queue" / d).glob("*.json")):
            try:
                j = json.loads(p.read_text(encoding="utf-8-sig"))
            except (ValueError, OSError):
                continue
            if j.get("script") == script:
                st = j.get("status")
                k = f"{d} {st}" if d == "done" and st and st != "done" else d
                counts[k] = counts.get(k, 0) + 1
    return ", ".join(f"{k} ×{n}" if n > 1 else k for k, n in counts.items())


def _lab_ns():
    for ns in workspace.namespaces():
        if workspace.rule_set(ns) == "lab":
            return ns
    return "lab"


def render_experiments(repo):
    """Drafts/experiments.md for the paper repo: every lab claim that bears on a paper label."""
    repo = Path(repo)
    lab_home = home(_lab_ns(), repo)
    if lab_home is None:
        raise SystemExit("the lab registry is not beside this repo")
    paper_ns = workspace.repo_ns(repo) or "paper"
    labs = [c for c in load(registry_root(lab_home))[0] if c.fields.get("id")]
    order = {lab: i for i, lab in enumerate(paper_colours(repo))}
    rows = []
    for c in labs:
        for t in c.bears_on:
            if t.startswith(paper_ns + ":"):
                rows.append((t.split(":", 1)[1], c))
    rows.sort(key=lambda r: (order.get(r[0], len(order)), r[0], r[1].id))
    cell = lambda s: s.replace("|", "\\|").replace("\n", " ")
    out = ["<!-- GENERATED by registry.py ledger (academy) -- do not edit -->", "",
           "# Experiments ledger", "",
           "Every computation that bears on a statement of the paper, one row per (label, lab claim),",
           "in the order of `Drafts/statements.md`. Generated from the lab's claim registry",
           "(`claims/lab/`), its result JSON and its local queue; regenerate with",
           "`registry.py --repo . ledger` (the academy's `scripts/registry.py`). To change a row, change the lab claim",
           "(`registry.py show lab:<name>`). The standard examples are in `.claude/rules/notation-decisions.md`;",
           "the hand-kept ledger this replaced is `Drafts/archive/experiments-2026-09.md`.", "",
           "Status is the lab claim's (`supported` is a bounded computation, not a proof). Evidence",
           "shows each result with its audit state; a result is cited only once it is `cleared`.", "",
           "| Label | Lab claim | Status | Kind | Script (lab) | Jobs | Evidence | Open |",
           "|---|---|---|---|---|---|---|---|"]
    for label, c in rows:
        cells = [c.evidence_cells(e) for e in c.evidence]
        ev = "<br>".join(f"`{x[1]}` ({x[2] or '-'}): {x[4]}"
                         for x in cells if x[0] in ("experiment", "audit", "verdict"))
        script = c.where if c.where.startswith("experiments/") else ""
        out.append("| " + " | ".join(cell(x) for x in (
            f"`{label}`", f"`{c.id}`", c.state, experiment_kind(lab_home, script) if script else "",
            f"`{script}`" if script else c.where, queue_jobs(lab_home, script) if script else "",
            ev or "—", str(len(c.open_items)) if c.open_items else "")) + " |")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------- the store

def _paper_statement(home_, label):
    """The LaTeX environment that carries ``\\label{label}`` in sections/*.tex, or None."""
    for p in sorted((home_ / "sections").glob("*.tex")):
        text = p.read_text(encoding="utf-8", errors="replace")
        i = text.find("\\label{%s}" % label)
        if i < 0:
            continue
        begins = list(re.finditer(r"\\begin\{([A-Za-z*]+)\}", text[:i]))
        if not begins:
            return None
        b = begins[-1]
        env = b.group(1)
        end = text.find("\\end{%s}" % env, i)
        return text[b.start():(end + len(env) + 6) if end >= 0 else i]
    return None


class FslStore(Store):
    profile = "fsl-claims"

    def __init__(self, ns, home_):
        super().__init__(ns, home_)
        self.root = registry_root(home_)
        self.claims, self.errors = load(self.root)
        for c in self.claims:
            cid = c.fields.get("id") or ""
            if not cid.startswith(ns + ":"):
                continue
            name = cid.split(":", 1)[1]
            self.records[name] = Record(
                ns=ns, type="claim", id=name, fields=c.fields, body=c.body,
                file=str(c.path), status=c.state,
                cls=_cls(c), title=c.title,
                links=c.links())
        self.claim_by_name = {c.fields.get("id", "").split(":", 1)[-1]: c for c in self.claims}

    def statement_text(self, rid):
        """paper: the LaTeX environment carrying the label (the statement as the draft
        states it); lab, or a label not found: the title and the body."""
        r = self.records.get(rid)
        if r is None:
            return None
        if workspace.rule_set(self.ns, self.home) == "paper":
            env = _paper_statement(self.home, rid)
            if env:
                return env
        return r.title + "\n" + r.body


# --------------------------------------------------------------- mutations

class Refused(Exception):
    """A mutation refused, with the reason."""


def today():
    return datetime.date.today().isoformat()


def _human_name():
    ws = workspace.load_workspace() or {}
    return ((ws.get("human") or {}).get("name")) or "the human"


def _history_note(note, g):
    basis = _grounds.summary(g, _human_name())
    parts = [x for x in ((note or "").strip(), basis) if x]
    return "; ".join(parts).replace("|", "/")


def _check_one(path, repo, root):
    """The (errors, warnings) of one record, read from disk, in its registry."""
    claims, perrs = load(root)
    mine = [e for e in perrs if e.startswith(str(path))]
    errs, warns = check(claims, repo=repo, root=root, only={Path(path).resolve()})
    return mine + errs, warns


def _apply(path, repo, root, edit):
    """Apply ``edit(doc)`` to the record at ``path``; refuse (and leave the file as it
    was) when the edit adds a check error. Returns the new errors (none)."""
    before = path.read_bytes()
    old_errs, _ = _check_one(path, repo, root)
    doc = Doc(path, fm.format_scalar_single)
    edit(doc)
    doc.save()
    _cache.clear()
    try:
        new_errs, _ = _check_one(path, repo, root)
    except Exception:
        path.write_bytes(before)
        raise
    added = [e for e in new_errs if e not in old_errs]
    if added:
        path.write_bytes(before)
        _cache.clear()
        raise Refused("the edit would leave the record inconsistent:\n" + "\n".join(added))


def find_claim(repo, cid):
    root = registry_root(repo)
    p = file_for(root, cid)
    if not p.exists():
        raise Refused(f"no claim `{cid}` in {root}")
    return p, root


def statement_hash(repo, cid):
    ns, name = cid.split(":", 1)
    st = federation.store(ns, Path(repo))
    return st.statement_hash(name)


def set_status(repo, cid, status, grounds=None, note=None, evidence=(), human=False,
               date=None):
    """Set ``cid``'s status: the one mutation path for lab/paper records.

    ``grounds`` is checked by :func:`core.grounds.check_grounds` (plan section 8) against
    the claim's current statement hash; ``evidence`` rows (``kind | ref | verdict |
    note``) are appended first. Writes the status line and a history row (newest first)
    and nothing else. Refuses, leaving the file untouched, when the grounds fail or the
    result would not pass ``check``. Returns the old status."""
    repo = Path(repo)
    if status not in STATUSES:
        raise Refused(f"status must be one of: {', '.join(STATUSES)}")
    path, root = find_claim(repo, cid)
    claim = parse_text(path.read_text(encoding="utf-8"), path, fallback=False)
    if claim.dialect_error:
        raise Refused("requote the file first")
    lifecycle = status in ("superseded", "dropped")
    if lifecycle and grounds and grounds.get("basis") != "human":
        ok, why = bool(str(grounds.get("note") or note or "").strip()), \
            ["superseded/dropped needs a note"]
    else:
        ok, why = _grounds.check_grounds(status, grounds, statement_hash(repo, cid), human=human)
    if ok and not lifecycle:
        why = _grounds.check_verdict_refs(grounds, lambda ref: resolve_ref(ref, repo), cid)
        ok = not why
    if not ok:
        raise Refused("the grounds do not support %s -> %s:\n- %s"
                      % (cid, status, "\n- ".join(why)))
    held = [str(r) for r in (claim.fields.get("evidence") or [])]
    evidence = list(evidence) + _verdict_rows(grounds, list(evidence) + held)
    evidence = [_row_for(claim, r) for r in evidence]
    for row in evidence:
        _validate_row(row, repo, claim.v2)
    old = claim.state
    row = f"{date or today()} | {status} | {_history_note(note, grounds)}"
    ev_after = V2_AFTER if claim.v2 else ("where", "supersedes", "superseded_by",
                                          "bears_on", "depends_on")

    def edit(doc):
        for ev in evidence:
            doc.add_item("evidence", ev, after=ev_after)
        if claim.v2 and lifecycle:
            doc.set_scalar("lifecycle", status, after=V2_AFTER[:V2_AFTER.index("lifecycle")])
        else:
            doc.set_scalar("status", status, after=("form", "title") if claim.v2 else ("title",))
        if claim.v2 and not lifecycle:
            # the record's `modulo` is the grounds' missing inputs: written with
            # proved-modulo, dropped with proved (the schema refuses either without it)
            if status == "proved-modulo":
                doc.set_list("modulo", [str(m) for m in (grounds or {}).get("modulo") or []],
                             after=V2_AFTER[:V2_AFTER.index("modulo")])
            elif status == "proved":
                doc.remove("modulo")
        doc.add_item("history", row, first=True, after=("evidence",))
        if status == "superseded" and new_id and not claim.v2:
            doc.set_scalar("superseded_by", new_id, after=FIELD_ORDER[:5])

    # superseded: the link is written where the schema keeps it -- v1 on this record
    # (`superseded_by`), v2 on the replacing record (`supersedes`, one-way), which is
    # put back if this record's edit is refused
    new_id = str((grounds or {}).get("superseded_by") or "").strip() \
        if status == "superseded" else ""
    undo = None
    if new_id and claim.v2:
        npath, nroot = find_claim(repo, new_id)
        nclaim = parse_text(npath.read_text(encoding="utf-8"), npath, fallback=False)
        if not nclaim.v2:
            raise Refused(f"`{new_id}` is not a schema-v2 record: it cannot carry `supersedes`")
        sup = nclaim.fields.get("supersedes") or []
        sup = sup if isinstance(sup, list) else [sup]
        if cid not in sup:
            undo = (npath, npath.read_bytes())

            def link(doc):
                doc.add_item("supersedes", cid, after=V2_AFTER[:V2_AFTER.index("supersedes")])
                doc.add_item("history", f"{date or today()} | {nclaim.state} | supersedes "
                             f"{cid}", first=True, after=("evidence",))
            _apply(npath, repo, nroot, link)
    try:
        _apply(path, repo, root, edit)
    except Exception:
        if undo:
            undo[0].write_bytes(undo[1])
            _cache.clear()
        raise
    return old


def _verdict_rows(grounds, given=()):
    """Evidence rows for the grounds' verdicts whose ref no ``given`` row carries: a
    status change always leaves the review records it rests on in the record."""
    g = grounds or {}
    if g.get("basis") not in ("proof", "computation"):
        return []
    have = {(str(r).split("|") + ["", ""])[1].strip() for r in given}
    kind = "verdict" if g["basis"] == "proof" else "audit"
    rows = []
    for v in g.get("verdicts") or []:
        ref = str(v.get("ref") or "").strip() if isinstance(v, dict) else ""
        if not ref or ref in have or "|" in ref:
            continue
        have.add(ref)
        grader = str(v.get("grader_role") or "").strip()
        rows.append(schema.evidence_row(kind, ref, _grounds.norm_verdict(v.get("verdict")),
                                        str(v.get("run_id") or "").strip(),
                                        ("grader %s" % grader) if grader else ""))
    return rows


def _row_for(claim, row):
    """An evidence row in the record's schema: a v2 record takes ``type | ref | verdict |
    run_id | note`` (a four-cell v1 row gets ``-`` for its run id); a v1 record takes
    ``kind | ref | verdict | note`` (a five-cell row's run id goes into the note)."""
    cells = [c.strip() for c in str(row).split("|")]
    if claim.v2:
        if len(cells) == 4:
            return schema.evidence_row(cells[0], cells[1], cells[2], "", cells[3])
        return str(row)
    if len(cells) >= 5:
        t, ref, verdict, run, note = schema.evidence_cells(row)
        if run not in schema.NONE:
            note = f"run {run}" + (f"; {note}" if note else "")
        return " | ".join([t, ref, verdict, note])
    return str(row)


def _validate_row(row, repo, v2=False):
    kind, ref = (schema.evidence_cells(row) if v2 else split_row(row, 4))[:2]
    if kind not in EVIDENCE_KINDS:
        raise Refused(f"evidence kind `{kind}` is not one of: " + ", ".join(EVIDENCE_KINDS))
    if not ref:
        raise Refused(f"evidence `{row}` has no ref")
    if kind in ("experiment", "audit", "verdict"):
        p = resolve_ref(ref, repo)
        if p is not None and not p.exists():
            raise Refused(f"evidence ref `{ref}` does not exist")


def attach_evidence(repo, cid, row):
    """Append one evidence row ``kind | ref | verdict | note`` (append-only)."""
    repo = Path(repo)
    path, root = find_claim(repo, cid)
    claim = parse_text(path.read_text(encoding="utf-8"), path, fallback=False)
    row = _row_for(claim, row)
    _validate_row(row, repo, claim.v2)
    if row in claim.evidence:
        raise Refused("that evidence row is already recorded")
    _apply(path, repo, root, lambda doc: doc.add_item(
        "evidence", row, after=V2_AFTER if claim.v2 else (
            "where", "supersedes", "superseded_by", "bears_on", "depends_on")))


#: the paper's label prefixes and the kind each is (schema v2)
PAPER_KINDS = {"thm": "claim", "prop": "claim", "lem": "claim", "cor": "claim",
               "fact": "claim", "rmk": "claim", "claim": "claim", "conj": "conjecture",
               "defn": "definition", "def": "definition", "ex": "example",
               "question": "question", "q": "question"}


def kind_of(cid, rules):
    """The schema-v2 kind of record ``cid`` (paper: from its label's prefix)."""
    if rules == "paper":
        label = cid.split(":", 1)[1]
        return PAPER_KINDS.get(label.split(":", 1)[0], "claim")
    return "claim"


def registry_is_v2(root):
    """Whether the registry at ``root`` already holds schema-v2 records."""
    for p in sorted(Path(root).rglob("*.md")):
        if p.name in ("INDEX.md", "README.md"):
            continue
        try:
            return parse_text(p.read_text(encoding="utf-8"), p).v2
        except ValueError:
            continue
    return False


def new_claim(repo, cid, title, status="open", where="", kind=None):
    """Create a record in the dialect (schema v2 when the registry is); returns its path."""
    repo = Path(repo)
    if not ID_RE.match(cid):
        raise Refused(f"id `{cid}` is not `<ns>:<name>`")
    root = registry_root(repo)
    v2 = registry_is_v2(root)
    allowed = schema.STATUSES if v2 else STATUSES
    if status not in allowed:
        raise Refused(f"status must be one of: {', '.join(allowed)}")
    p = file_for(root, cid)
    if p.exists():
        raise Refused(f"{p} exists")
    p.parent.mkdir(parents=True, exist_ok=True)
    if v2:
        ns = cid.split(":", 1)[0]
        kind = kind or kind_of(cid, workspace.rule_set(ns, repo))
        if kind not in schema.KINDS:
            raise Refused(f"kind must be one of: {', '.join(schema.KINDS)}")
        fields = {"id": cid, "kind": kind, "title": title, "status": status,
                  "lifecycle": "active", "evidence": [],
                  "history": [schema.history_row(today(), status, "created")]}
        if where:
            fields["where"] = where
        doms = [d for info in (workspace.load_workspace() or {}).get("instances", {}).values()
                if info.get("ns") == ns for d in (info.get("domains") or [])]
        if doms:
            fields["domain"] = doms[0]
        text = fm.serialize_frontmatter(fields, V2_ORDER, V2_BLOCK, fm.format_scalar_single)
    else:
        fields = {"id": cid, "title": title, "status": status, "where": where,
                  "evidence": [], "history": [f"{today()} | {status} | created"], "open": []}
        text = serialize(fields)
    p.write_text("---\n" + text + "---\n", encoding="utf-8", newline="\n")
    return p


# ---------------------------------------------------------------------- main

def _print_walk(qid, repo, reverse, transitive):
    from ..core import graph
    edges = graph.walk(qid, Path(repo), reverse=reverse, transitive=transitive)
    for e in edges:
        print(f"{'  ' * (e['depth'] - 1)}{e['to'] if not reverse else e['from']} "
              f"({e['rel']}) [{e.get('status') or '-'}]")
    if not edges:
        print("(none)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="The claim registry: one short text file per "
                                             "claim, queried from here.")
    ap.add_argument("--repo", default=str(ROOT), help="the repo whose registry to use (default: this one)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("show"); p.add_argument("id")
    p = sub.add_parser("list")
    p.add_argument("--status"); p.add_argument("--ns"); p.add_argument("--where")
    p = sub.add_parser("grep"); p.add_argument("text")
    p = sub.add_parser("sql"); p.add_argument("query")
    p = sub.add_parser("check"); p.add_argument("--strict", action="store_true")
    p.add_argument("files", nargs="*")
    sub.add_parser("render")
    sub.add_parser("build", help="the same as render")
    p = sub.add_parser("ledger", help="write <repo>/Drafts/experiments.md (the paper repo)")
    p.add_argument("--stdout", action="store_true")
    p = sub.add_parser("new"); p.add_argument("id"); p.add_argument("--title", required=True)
    p.add_argument("--status", default="open"); p.add_argument("--where", default="")
    p = sub.add_parser("set-status", help="change a status, with grounds (plan section 8)")
    p.add_argument("id"); p.add_argument("status")
    p.add_argument("--human", dest="human", metavar="QUOTE",
                   help="the human's words, verbatim")
    p.add_argument("--where-said", default="", help="where and when the human said it")
    p.add_argument("--grounds", metavar="JSON", help="a grounds object (JSON text or @file)")
    p.add_argument("--evidence", action="append", default=[], metavar="ROW",
                   help="append this evidence row first: 'kind | ref | verdict | note'")
    p.add_argument("--note", default="")
    p = sub.add_parser("evidence", help="append one evidence row (append-only)")
    p.add_argument("id"); p.add_argument("row")
    for name in ("deps", "usedby"):
        p = sub.add_parser(name, help="what the claim rests on / what rests on it, "
                                      "across namespaces")
        p.add_argument("id"); p.add_argument("--transitive", action="store_true")
    a = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    repo = Path(a.repo).resolve()
    root = registry_root(repo)
    claims, perrs = load(root)
    by_id = {c.fields.get("id"): c for c in claims}

    if a.cmd == "show":
        c = by_id.get(a.id)
        ns = a.id.split(":", 1)[0]
        if not c and FOREIGN_ID_RE.match(a.id) and _is_foreign(ns, repo):
            state, detail = foreign(a.id, repo)
            where = HOMES[ns]
            base = home(ns, repo)
            st = federation.store(ns, base) if base else None
            p = file_for(registry_root(base), a.id) if st is not None and st.profile == "fsl-claims" else None
            if p and p.exists():
                print(p.read_text(encoding="utf-8").rstrip())
                bl = backlinks(a.id, claims, repo) + backlinks(a.id, load(registry_root(base))[0], base)
                print("\ncited by:" if bl else "\ncited by: nothing")
                print("\n".join(bl)) if bl else None
                return 0
            if st is not None and st.profile == "s1-kb" or (st is None and workspace.rule_set(ns) == "notebook"):
                print(f"`{a.id}` is {where}'s ({state}{': ' + detail if detail else ''}). "
                      f"Run `registry.py show {a.id.split(':', 1)[1]}` in {where}.")
            else:
                print(f"`{a.id}` is owned by {where} ({state}{': ' + detail if detail else ''}). "
                      f"Run `registry.py --repo ..\\{where} show {a.id}`.")
            bl = backlinks(a.id, claims, repo)
            print("\ncited here by:" if bl else "\ncited here by: nothing")
            print("\n".join(bl)) if bl else None
            return 0 if state != "missing" else 1
        if not c:
            hits = [i for i in by_id if i and a.id in i]
            print(f"no claim `{a.id}`" + (". Did you mean: " + ", ".join(hits[:10]) if hits else ""))
            return 1
        print(c.path.read_text(encoding="utf-8").rstrip())
        bl = backlinks(a.id, claims, repo)
        print("\ncited by:" if bl else "\ncited by: nothing")
        print("\n".join(bl)) if bl else None
        return 0
    if a.cmd == "list":
        sel = [c for c in claims if c.fields.get("id")
               and (not a.status or a.status in (c.status, c.state))
               and (not a.ns or c.ns == a.ns)
               and (not a.where or a.where in c.where)]
        w = max((len(c.id) for c in sel), default=0)
        for c in sorted(sel, key=lambda c: c.id):
            print(f"{c.id:<{w}}  {c.state:<17} {c.title}")
        print(f"({len(sel)} claims)")
        return 0
    if a.cmd == "grep":
        t = a.text.lower()
        for c in claims:
            for line in c.path.read_text(encoding="utf-8").splitlines():
                if t in line.lower():
                    print(f"{c.fields.get('id')}: {line.strip()}")
        return 0
    if a.cmd == "sql":
        db = to_sqlite(claims)
        try:
            cur = db.execute(a.query)
        except sqlite3.Error as e:
            print(f"sql error: {e}")
            return 1
        cols = [d[0] for d in cur.description or []]
        print(" | ".join(cols))
        for row in cur:
            print(" | ".join("" if v is None else str(v) for v in row))
        return 0
    if a.cmd == "check":
        only = {Path(f).resolve() for f in a.files} or None
        errs, warns = check(claims, repo=repo, root=root, only=only)
        if only:
            perrs = [m for m in perrs if Path(m.split(": ERROR: ", 1)[0]).resolve() in only]
        errs = perrs + errs
        for m in errs + warns:
            print(m)
        print(f"{len(claims)} claims: {len(errs)} error(s), {len(warns)} warning(s)")
        return 1 if errs or (a.strict and warns) else 0
    if a.cmd in ("render", "build"):
        root.mkdir(parents=True, exist_ok=True)
        (root / "INDEX.md").write_text(render_index(claims), encoding="utf-8", newline="\n")
        (root / "index.html").write_text(render_html(claims), encoding="utf-8", newline="\n")
        print(f"wrote {root / 'INDEX.md'} and {root / 'index.html'} ({len(claims)} claims)")
        return 0
    if a.cmd == "ledger":
        text = render_experiments(repo)
        if a.stdout:
            print(text)
            return 0
        p = repo / "Drafts" / "experiments.md"
        p.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {p} ({text.count(chr(10) + '| `')} rows)")
        return 0
    if a.cmd == "new":
        try:
            p = new_claim(repo, a.id, a.title, a.status, a.where)
        except Refused as exc:
            print(str(exc))
            return 1
        print(f"created {p}")
        return 0
    if a.cmd == "set-status":
        g = None
        if a.human:
            g = {"basis": "human", "quote": a.human, "where": a.where_said}
        elif a.grounds:
            src = a.grounds
            if src.startswith("@"):
                src = Path(src[1:]).read_text(encoding="utf-8")
            try:
                g = json.loads(src)
            except ValueError as exc:
                print(f"set-status: --grounds is not JSON: {exc}", file=sys.stderr)
                return 1
        try:
            # the command line cannot tell who runs it: --human claims the human's voice,
            # as the old claims.py did (not hooked; see the migration log's known limits)
            old = set_status(repo, a.id, a.status, g, a.note, a.evidence, human=bool(a.human))
        except Refused as exc:
            print(f"set-status: refused: {exc}", file=sys.stderr)
            return 1
        print(f"{a.id}: status {old} → {a.status}")
        return 0
    if a.cmd == "evidence":
        try:
            attach_evidence(repo, a.id, a.row)
        except Refused as exc:
            print(f"evidence: refused: {exc}", file=sys.stderr)
            return 1
        print(f"{a.id}: evidence added: {a.row}")
        return 0
    if a.cmd in ("deps", "usedby"):
        return _print_walk(a.id, repo, a.cmd == "usedby", a.transitive)
    return 1


if __name__ == "__main__":
    sys.exit(main())
