"""claims_* tools: the federated claim registries (plan sections 5, 6 and 8).

Every call goes to the registry engine ``academy/registry`` (Group D), in process,
through :class:`RegistryBackend`: the namespaces are those of workspace.json, each
served by its home's profile (fsl-claims for lab/paper rule sets, s1-kb for s1). Read
commands return what the engine's command line prints (the same text as the old
``claims.py`` / ``kb.py`` command lines, which were retired 2026-09-28 in favour of
``scripts/registry.py``).

The backend interface is :class:`ClaimsBackend`. :class:`LegacyCliBackend` (the same
engine through ``scripts/registry.py``, one subprocess per call) is kept as a fallback only: ``$ACADEMY_CLAIMS_BACKEND=legacy``
selects it, and it cannot write.

The grounds rule of plan section 8 is :func:`check_grounds`, the engine's
(``registry.core.grounds``): two agreeing verdicts with distinct run ids, each with the
ref of its landed review record, graded by the basis' reviewers (rigor-reviewer /
experiment-reviewer) and not by the producer, one statement hash (proof) or one commit,
a passed validation case and a matching outcome (computation: supported / refuted /
refuted-as-stated only); or the human's quoted word, which an agent must point at the
ticket or packet holding it. The review records themselves are checked against the rows
(``grounds.check_verdict_refs``): by the engine for lab/paper, here for s1, whose
verdict file is also checked by ``s1kb.verdict_file_problems``. The lifecycle moves
(superseded, dropped) are accepted as targets with a note.
"""

import contextlib
import io
import os
import re
import subprocess
import sys

import academy_common as ac

from . import Tool, ToolError, obj, S, I, B, L
from . import tickets as _tickets

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PLUGIN not in sys.path:
    sys.path.insert(0, _PLUGIN)

from registry.core import grounds as _grounds  # noqa: E402

UNSETTLED = _grounds.UNSETTLED
LIFECYCLE_TARGETS = _grounds.LIFECYCLE_TARGETS
# the registry statuses plus the lifecycle moves, which claims_set_status also makes
TARGETS = tuple(ac.CLAIM_STATUSES) + tuple(t for t in LIFECYCLE_TARGETS
                                           if t not in ac.CLAIM_STATUSES)
PROOF_TARGETS = _grounds.PROOF_TARGETS
COMPUTATION_TARGETS = _grounds.COMPUTATION_TARGETS
PROOF_VERDICTS = _grounds.PROOF_VERDICTS
EXPERIMENT_VERDICTS = _grounds.EXPERIMENT_VERDICTS
RE_CLAIM_ID = re.compile(r"^([a-z0-9]+):(.+)$")


class NotEnabled(ToolError):
    """The operation exists in the contract but the current backend cannot do it."""


def _norm_verdict(v):
    return _grounds.norm_verdict(v)


def check_grounds(new_status, grounds, statement_hash=None, human=False):
    """Plan section 8, from the engine (``registry.core.grounds.check_grounds``), over
    the registry statuses of ``academy_common.CLAIM_STATUSES`` and the lifecycle moves."""
    return _grounds.check_grounds(new_status, grounds, statement_hash, human,
                                  statuses=TARGETS)


def _squash(text):
    return " ".join(str(text or "").replace("\r\n", "\n").split())


def check_human_where(ctx, grounds):
    """``basis: human`` from an agent: the ticket or packet ``where`` names must exist on
    the board and hold the quote verbatim (whitespace aside). Raises ToolError."""
    from . import packets as _packets
    where = str((grounds or {}).get("where") or "")
    quote = _squash((grounds or {}).get("quote"))
    m = _grounds.RE_BOARD_REF.search(where)
    if not m:
        raise ToolError("refused: basis 'human' from an agent needs grounds.where naming "
                        "the ticket or packet that holds the quote")
    ref = m.group(0)
    loader = _tickets.load_ticket if ref.startswith("T-") else _packets.load_packet
    path, _, _ = loader(ctx, ref)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if quote not in _squash(text):
        raise ToolError("refused: %s does not contain the quote %r verbatim" % (ref, quote))


# ----------------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------------

class ClaimsBackend(object):
    """The module boundary Group D swaps (academy/registry). Ids are 'ns:rest'."""

    def show(self, cid, full=False):
        raise NotImplementedError

    def list(self, ns, status=None, where=None, text=None, kind=None):
        raise NotImplementedError

    def query(self, ns, sql):
        raise NotImplementedError

    def deps(self, cid, reverse=False, transitive=False):
        raise NotImplementedError

    def check(self, ns, strict=False):
        raise NotImplementedError

    def new(self, cid, title, status="open", where=None, kind=None):
        raise NotImplementedError

    def attach_evidence(self, cid, row):
        raise NotEnabled("claims_attach_evidence is not yet enabled: the legacy registries "
                         "have no append path; use claim-keeper until academy/registry "
                         "lands (Group D)")

    def set_status(self, cid, status, grounds, note=None):
        raise NotEnabled("not yet enabled: use claim-keeper. The grounds passed, but the "
                         "legacy registries have no uniform set-status; academy/registry "
                         "(Group D) will apply it")

    def statement_hash(self, cid):
        return None


def split_id(cid):
    m = RE_CLAIM_ID.match(str(cid or "").strip())
    if not m:
        raise ToolError("a claim id is '<ns>:<id>' with <ns> an instance's namespace in "
                        "workspace.json, got %r" % cid)
    return m.group(1), m.group(2)


def _readonly_sql(sql):
    s = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql or "", flags=re.S).strip().lower()
    if not (s.startswith("select") or s.startswith("with")) or ";" in s.rstrip(";"):
        raise ToolError("claims_query takes one read-only SELECT statement")


class LegacyCliBackend(ClaimsBackend):
    """Runs ``scripts/registry.py`` by subprocess, one process per call.

    Fallback only (``$ACADEMY_CLAIMS_BACKEND=legacy``), read-only: the namespaces it
    serves are those of the first three instances, so they are named here and nowhere
    else in the plugin. (Before 2026-09-28 it wrapped the lab's ``claims.py`` and
    Slope1's ``kb.py`` shims, which no longer exist.)
    """

    TIMEOUT = 120
    NAMESPACES = ("lab", "paper", "s1")

    def __init__(self, ctx):
        self.ctx = ctx

    def _home_for_ns(self, ns):
        inst = self.ctx.instance_by_ns(ns)
        if not inst:
            raise ToolError("no instance owns namespace %r in workspace.json" % ns)
        return self.ctx.home_of(inst)

    def _run(self, argv, cwd):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        try:
            p = subprocess.run([sys.executable] + argv, cwd=cwd, capture_output=True,
                               timeout=self.TIMEOUT, env=env)
        except subprocess.TimeoutExpired:
            raise ToolError("timed out: %s" % " ".join(argv))
        except OSError as exc:
            raise ToolError("cannot run %s: %s" % (argv[0], exc))
        out = p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
        err = p.stderr.decode("utf-8", "replace").replace("\r\n", "\n")
        shown = " ".join(x.replace("\\", "/") for x in argv)
        return {"command": "py " + shown, "exit": p.returncode,
                "stdout": out, "stderr": err}

    LAUNCHER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "scripts", "registry.py")

    def _registry(self, ns, args):
        """``registry.py --repo <home of ns> ARGS``, run in that home."""
        if not os.path.isfile(self.LAUNCHER):
            raise ToolError("registry.py not found at %s" % self.LAUNCHER)
        home = self._home_for_ns(ns)
        return self._run([self.LAUNCHER, "--repo", home] + args, home)

    def _claims_py(self, ns, args):
        return self._registry(ns, args)

    def _kb_py(self, args):
        return self._registry("s1", args)

    def _route(self, ns, claims_args, kb_args):
        if ns in ("lab", "paper"):
            return self._claims_py(ns, claims_args)
        if ns == "s1":
            if kb_args is None:
                raise NotEnabled("this operation has no kb.py equivalent for s1:")
            return self._kb_py(kb_args)
        raise ToolError("no legacy registry for namespace %r (known: lab, paper, s1)" % ns)

    def show(self, cid, full=False):
        ns, rest = split_id(cid)
        return self._route(ns, ["show", cid],
                           ["show", rest] + (["--full"] if full else []))

    def list(self, ns, status=None, where=None, text=None, kind=None):
        ca = ["list"]
        if status:
            ca += ["--status", status]
        if where:
            ca += ["--where", where]
        if ns in ("lab", "paper"):
            ca += ["--ns", ns]
        ka = ["find"]
        if status:
            ka += ["--status", status]
        if kind:
            ka += ["--kind", kind]
        if text:
            ka += text.split()
        return self._route(ns, ca, ka)

    def query(self, ns, sql):
        _readonly_sql(sql)
        if ns == "s1":
            db = os.path.join(self._home_for_ns("s1"), "kb", "kb.sqlite")
            if not os.path.isfile(db):
                raise ToolError("s1: kb/kb.sqlite is not built; run 'registry.py build' "
                                "in the Slope1 home (the server does not rebuild it, "
                                "because the build rewrites the views)")
        return self._route(ns, ["sql", sql], ["sql", sql])

    def deps(self, cid, reverse=False, transitive=False):
        ns, rest = split_id(cid)
        if ns == "s1":
            return self._kb_py([("usedby" if reverse else "deps"), rest]
                               + (["--transitive"] if transitive else []))
        res = self._claims_py(ns, ["sql", "select src, rel, dst from links"])
        if res["exit"] != 0:
            return res
        edges = []
        for ln in res["stdout"].split("\n")[1:]:
            parts = [p.strip() for p in ln.split(" | ")]
            if len(parts) == 3:
                edges.append(tuple(parts))
        seen, frontier, out = {cid}, [cid], []
        while frontier:
            nxt = []
            for node in frontier:
                for src, rel, dst in edges:
                    a, b = (dst, src) if reverse else (src, dst)
                    if a == node:
                        out.append({"from": src, "rel": rel, "to": dst})
                        if b not in seen:
                            seen.add(b)
                            nxt.append(b)
            frontier = nxt if transitive else []
        return {"id": cid, "direction": "used by" if reverse else "depends on / bears on",
                "transitive": transitive, "edges": out,
                "note": "from the %s registry's links table only" % ns}

    def check(self, ns, strict=False):
        return self._route(ns, ["check"] + (["--strict"] if strict else []), ["check"])

    def new(self, cid, title, status="open", where=None, kind=None):
        ns, rest = split_id(cid)
        ca = ["new", cid, "--title", title, "--status", status]
        if where:
            ca += ["--where", where]
        # kb.py allocates the id itself from a prefix: the id's part after 's1:'
        ka = ["new", rest, "--title", title] + (["--kind", kind] if kind else [])
        return self._route(ns, ca, ka)


S1_WORDS = {"proved": "Proved", "proved-modulo": "Proved modulo stated inputs",
            "refuted": "Disproved", "open": "Not settled", "conjectured": "Not settled",
            "sketch": "Not settled"}


class RegistryBackend(ClaimsBackend):
    """The registry engine (academy/registry), in process. Every workspace namespace."""

    NAMESPACES = None       # all of workspace.json's

    def __init__(self, ctx):
        self.ctx = ctx
        import registry
        from registry.core import federation, graph, workspace
        from registry.profiles import fsl, s1kb
        self.registry, self.federation, self.graph = registry, federation, graph
        self.workspace, self.fsl, self.s1kb = workspace, fsl, s1kb
        federation.CACHE.clear()        # files may have changed since the last call

    # -- plumbing ----------------------------------------------------------
    def _home(self, ns):
        inst = self.ctx.instance_by_ns(ns)
        if not inst:
            raise ToolError("no instance owns namespace %r in workspace.json" % ns)
        return self.ctx.home_of(inst)

    def _profile(self, ns):
        return self.workspace.engine_profile(ns, self._home(ns))

    def _cli(self, ns, argv):
        """Run ``registry --repo <home> <argv>`` in process; the legacy result shape."""
        from registry import cli
        home = self._home(ns)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = cli.main(["--repo", home] + list(argv))
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else 1
        self.federation.CACHE.clear()
        return {"command": "registry --repo %s %s" % (home.replace("\\", "/"),
                                                      " ".join(argv)),
                "exit": rc or 0, "stdout": out.getvalue().replace("\r\n", "\n"),
                "stderr": err.getvalue().replace("\r\n", "\n")}

    def _store(self, ns):
        from pathlib import Path
        return self.federation.store(ns, Path(self._home(ns)))

    # -- reads -------------------------------------------------------------
    def show(self, cid, full=False):
        ns, rest = split_id(cid)
        if self._profile(ns) == "s1-kb":
            return self._cli(ns, ["show", rest] + (["--full"] if full else []))
        return self._cli(ns, ["show", cid])

    def list(self, ns, status=None, where=None, text=None, kind=None):
        if self._profile(ns) == "s1-kb":
            a = ["find"]
            if status:
                a += ["--status", status]
            if kind:
                a += ["--kind", kind]
            if text:
                a += text.split()
            return self._cli(ns, a)
        a = ["list", "--ns", ns]
        if status:
            a += ["--status", status]
        if where:
            a += ["--where", where]
        return self._cli(ns, a)

    def query(self, ns, sql):
        _readonly_sql(sql)
        return self._cli(ns, ["sql", sql])

    def deps(self, cid, reverse=False, transitive=False):
        from pathlib import Path
        ns, _ = split_id(cid)
        edges = self.graph.walk(cid, Path(self._home(ns)), reverse=reverse,
                                transitive=transitive)
        return {"id": cid, "direction": "used by" if reverse else "depends on / bears on",
                "transitive": transitive, "edges": edges,
                "note": "the registry engine's graph across every namespace reachable "
                        "from %s (relations: %s)" % (ns, ", ".join(self.graph.DEP_RELS))}

    def check(self, ns, strict=False):
        strict_arg = ["--strict"] if strict and self._profile(ns) != "s1-kb" else []
        return self._cli(ns, ["check"] + strict_arg)

    def statement_hash(self, cid):
        ns, rest = split_id(cid)
        try:
            st = self._store(ns)
        except ToolError:
            return None
        rid, _ = st.lookup(rest)
        return st.statement_hash(rid) if rid else None

    # -- writes ------------------------------------------------------------
    def new(self, cid, title, status="open", where=None, kind=None):
        ns, rest = split_id(cid)
        if self._profile(ns) == "s1-kb":
            return self._cli(ns, ["new", rest, "--title", title]
                             + (["--kind", kind] if kind else []))
        return self._cli(ns, ["new", cid, "--title", title, "--status", status]
                         + (["--where", where] if where else []))

    @staticmethod
    def row_text(row):
        """An evidence row object -> the schema-v2 row ``type | ref | verdict | run_id |
        note``. The engine writes it as is into a v2 record, and folds the run id into
        the note (``run X; ...``, the old form) for a v1 record."""
        kind = str(row.get("type") or row.get("kind") or "").strip()
        ref = str(row.get("ref") or "").strip()
        verdict = str(row.get("verdict") or "-").strip() or "-"
        run = str(row.get("run_id") or "").strip() or "-"
        bits = []
        if row.get("grader_role"):
            bits.append("grader %s" % str(row["grader_role"]).strip())
        if row.get("note"):
            bits.append(str(row["note"]).strip())
        cells = [kind, ref, verdict, run, "; ".join(bits)]
        if any("|" in c for c in cells):
            raise ToolError("an evidence cell may not contain '|'")
        return " | ".join(cells)

    def _s1_is_v2(self, home, rest):
        kb = self.s1kb.load_kb(home)
        eid, _ = self.s1kb.lookup(kb, rest)
        return eid is not None and kb.entities[eid].v2 is not None

    def attach_evidence(self, cid, row):
        if not isinstance(row, dict):
            raise ToolError("row must be an object: {type, ref, verdict, run_id, note}")
        ns, rest = split_id(cid)
        home = self._home(ns)
        if self._profile(ns) == "s1-kb":
            kind = str(row.get("type") or row.get("kind") or "")
            if kind != "verdict" and self._s1_is_v2(home, rest):
                text = self.row_text(row)
                try:
                    eid = self.s1kb.attach_row(home, rest, text)
                except ValueError as exc:
                    raise ToolError("refused: %s" % exc)
                finally:
                    self.federation.CACHE.clear()
                return {"id": "%s:%s" % (ns, eid), "attached": text, "field": "evidence"}
            if kind != "verdict":
                raise NotEnabled("s1 records carry evidence only as verdict files "
                                 "(cleared_by) until schema v2 (R5): give type 'verdict' "
                                 "and a ref under computation/verdicts/")
            try:
                eid, vrel = self.s1kb.attach_verdict(home, rest, str(row.get("ref") or ""))
            except ValueError as exc:
                raise ToolError("refused: %s" % exc)
            return {"id": "%s:%s" % (ns, eid), "attached": vrel, "field": "cleared_by"}
        text = self.row_text(row)
        try:
            self.fsl.attach_evidence(home, cid, text)
        except self.fsl.Refused as exc:
            raise ToolError("refused: %s" % exc)
        finally:
            self.federation.CACHE.clear()
        return {"id": cid, "attached": text, "field": "evidence"}

    def _evidence_from(self, grounds):
        """Evidence rows implied by the grounds: each verdict with a ``ref``, and the
        human's word."""
        rows = []
        g = grounds or {}
        if g.get("basis") == "human":
            who = ((self.ctx.workspace.get("human") or {}).get("name")) or "human"
            rows.append(self.row_text({"type": "hand", "ref": g.get("where") or who,
                                       "verdict": "%s's word" % who,
                                       "note": '"%s"' % str(g.get("quote")).strip()}))
        kind = "verdict" if g.get("basis") == "proof" else "audit"
        for v in g.get("verdicts") or []:
            if isinstance(v, dict) and v.get("ref"):
                rows.append(self.row_text(dict(v, type=v.get("type") or kind,
                                               verdict=_norm_verdict(v.get("verdict")))))
        return rows

    def set_status(self, cid, status, grounds, note=None):
        ns, rest = split_id(cid)
        home = self._home(ns)
        if self._profile(ns) == "s1-kb":
            # a schema-v2 record takes the one vocabulary as is (R5); a v1 one its label
            label = status if self._s1_is_v2(home, rest) else S1_WORDS.get(status)
            if label is None:
                raise NotEnabled("%r has no s1 word until schema v2 (R5); Slope1 records "
                                 "Proved, Proved modulo stated inputs, Disproved, Not "
                                 "settled" % status)
            return self._s1_set_status(ns, home, rest, status, label, grounds or {}, note)
        if status in LIFECYCLE_TARGETS and (grounds or {}).get("superseded_by"):
            note = "; ".join(x for x in (note, "superseded by %s"
                                         % grounds["superseded_by"]) if x)
        try:
            old = self.fsl.set_status(home, cid, status, grounds, note,
                                      evidence=self._evidence_from(grounds),
                                      human=self.ctx.is_human)
        except self.fsl.Refused as exc:
            raise ToolError("refused: %s" % exc)
        finally:
            self.federation.CACHE.clear()
        return {"id": cid, "old": old, "new": status,
                "check": self._cli(ns, ["check", self.fsl.file_for(
                    self.fsl.registry_root(__import__("pathlib").Path(home)), cid).as_posix()])}


    def _s1_verdict_refs(self, home, grounds):
        """The s1 verdict refs of the grounds: home paths (``audits/...`` or
        ``computation/verdicts/...``, bare or as ``<home dir>:path``) and Expert review
        refs (``file:expert@<name>/reviews/...``, phase 7)."""
        out = []
        name = os.path.basename(os.path.normpath(home))
        for v in (grounds or {}).get("verdicts") or []:
            ref = str((v or {}).get("ref") or "").replace("\\", "/") \
                if isinstance(v, dict) else ""
            m = re.match(r"^([A-Za-z0-9_\-]+):(?![\\/])(.+)$", ref)
            if m and (m.group(1) == name or name.startswith(m.group(1) + "-")):
                ref = m.group(2)
            if ref.startswith(("computation/verdicts/", "audits/"))                     or self.s1kb.RE_REVIEW_REF.match(ref):
                out.append(ref)
        return out

    def _s1_set_status(self, ns, home, rest, status, label, g, note):
        """s1: the change is anchored on a verdict file of the home. The grounds' review
        records are checked against their rows, the verdict file against the claim and
        the target (``s1kb.verdict_file_problems``), before the engine writes."""
        from pathlib import Path
        refs = self._s1_verdict_refs(home, g)
        vfile = str(g.get("verdict_file") or "").replace("\\", "/") or \
            (refs[0] if refs else "")
        if vfile and refs and vfile not in refs:
            raise ToolError("refused: grounds.verdict_file %s is none of the verdicts' "
                            "refs (%s)" % (vfile, ", ".join(refs)))
        human = g.get("basis") == "human"
        settling = status not in UNSETTLED + LIFECYCLE_TARGETS
        why = _grounds.check_verdict_refs(
            g, lambda ref: self.fsl.resolve_ref(ref, Path(home)), "%s:%s" % (ns, rest))
        if why:
            raise ToolError("refused: the review records do not match the grounds:\n- %s"
                            % "\n- ".join(why))
        if not vfile and (settling or not self._s1_is_v2(home, rest)):
            raise ToolError("refused: the s1 profile records a status change against "
                            "a verdict file: give grounds.verdict_file (a file under "
                            "computation/verdicts/ or audits/ of the s1 home, or an "
                            "Expert review ref file:expert@<name>/reviews/...)")
        kb = self.s1kb.load_kb(home)
        eid, _ = self.s1kb.lookup(kb, rest)
        if eid is None:
            raise ToolError("refused: no s1 entity or alias matches %r" % rest)
        if vfile:
            vrel = self.s1kb._verdict_relpath(kb.root, vfile)
            if vrel is None:
                raise ToolError("refused: %r is not an existing file under "
                                "computation/verdicts/ or audits/ of the s1 home, nor an "
                                "Expert review ref (file:expert@<name>/reviews/...)" % vfile)
            probs = self.s1kb.verdict_file_problems(kb, vrel, eid, label, human=human)
            if probs:
                raise ToolError("refused: the verdict file does not carry %s to %s:\n- %s"
                                % (eid, status, "\n- ".join(probs)))
        why_note = note or str(g.get("note") or "").strip() or \
            ("the human's word" if human else None)
        if status in LIFECYCLE_TARGETS and g.get("superseded_by"):
            why_note = "; ".join(x for x in (why_note, "superseded by %s"
                                             % g["superseded_by"]) if x)
        argv = ["set-status", rest, label]
        if vfile:
            argv += ["--verdict", vfile]
        if why_note:
            argv += ["--note", why_note]
        if human and self._s1_is_v2(home, rest):
            argv += ["--human", str(g.get("quote")).strip()]
        if status == "superseded" and g.get("superseded_by"):
            new = str(g["superseded_by"]).strip()
            argv += ["--superseded-by", new[3:] if new.startswith("s1:") else new]
        res = self._cli(ns, argv)
        if res["exit"] != 0:
            raise ToolError("refused: %s" % (res["stderr"] or res["stdout"]).strip())
        return res


def backend(ctx):
    """The active backend: the registry engine, or the legacy command lines when
    ``$ACADEMY_CLAIMS_BACKEND`` is ``legacy``."""
    if os.environ.get("ACADEMY_CLAIMS_BACKEND", "").lower() == "legacy":
        return LegacyCliBackend(ctx)
    return BACKEND_FACTORY(ctx)


BACKEND_FACTORY = RegistryBackend


# ----------------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------------

def _show(ctx, a):
    return backend(ctx).show(a["id"], bool(a.get("full")))


def check_ns(ctx, ns):
    """``ns`` must be owned by a workspace instance and served by the active backend."""
    owned = sorted(i.get("ns") for i in ctx.instances().values() if i.get("ns"))
    if ns not in owned:
        raise ToolError("ns must be a namespace owned by a workspace instance (%s), got %r"
                        % (", ".join(owned) or "none", ns))
    cls = LegacyCliBackend if os.environ.get("ACADEMY_CLAIMS_BACKEND", "").lower() \
        == "legacy" else BACKEND_FACTORY
    served = getattr(cls, "NAMESPACES", None)
    if served is not None and ns not in served:
        raise ToolError("namespace %r is not served by the %s backend yet"
                        % (ns, cls.__name__))
    return ns


def _list(ctx, a):
    ns = check_ns(ctx, a.get("ns"))
    return backend(ctx).list(ns, a.get("status"), a.get("where"), a.get("text"),
                             a.get("kind"))


def _query(ctx, a):
    return backend(ctx).query(check_ns(ctx, a.get("ns")), a["sql"])


def _deps(ctx, a):
    return backend(ctx).deps(a["id"], bool(a.get("reverse")), bool(a.get("transitive")))


def _check(ctx, a):
    return backend(ctx).check(check_ns(ctx, a.get("ns")), bool(a.get("strict")))


def _own_ns_ok(ctx, ns):
    if ctx.is_human or ctx.agent == "claim-keeper":
        return True
    inst = ctx.instances().get(ctx.home_instance() or "", {})
    return inst.get("ns") == ns


def _new(ctx, a):
    ns, _ = split_id(a["id"])
    status = a.get("status") or ("conjectured" if a.get("kind") == "conjecture" else "open")
    if status not in UNSETTLED:
        raise ToolError("claims_new creates only unsettled claims (%s), not %r"
                        % (", ".join(UNSETTLED), status))
    if not _own_ns_ok(ctx, ns):
        raise ToolError("%s may create claims only in its own instance's namespace, not %r"
                        % (ctx.agent, ns))
    return backend(ctx).new(a["id"], a["title"], status, a.get("where"), a.get("kind"))


def _attach(ctx, a):
    ns, _ = split_id(a["id"])
    check_ns(ctx, ns)
    return backend(ctx).attach_evidence(a["id"], a["row"])


def _keeper_instance(ctx, ns):
    owner = ctx.instance_by_ns(ns)
    doms = ctx.instances().get(owner or "", {}).get("domains")
    cands = ctx.instances_by_role("researcher", doms) or ctx.instances_by_role("researcher")
    if not cands:
        raise ToolError("no researcher instance (claim-keeper) in workspace.json")
    return cands[0]


def _propose(ctx, a):
    cid = a["id"]
    ns, _ = split_id(cid)
    if a["status"] not in TARGETS:
        raise ToolError("%r is not a registry status or lifecycle move" % a["status"])
    to = _keeper_instance(ctx, ns)
    ask = "Set %s to %s (claims_set_status)." % (cid, a["status"])
    detail = (a.get("reason") or "").strip()
    return _tickets.create_ticket(ctx, {
        "title": "Status of %s -> %s" % (cid, a["status"]),
        "kind": "decision", "to": to, "ask": ask,
        "deliverable": "The status is set with grounds, or the ticket is rejected "
                       "with the reason.",
        "refs": [cid] + list(a.get("refs") or []),
        "ask_detail": detail + ("\n\nGrounds offered: %s" % a["grounds"]
                                if a.get("grounds") else ""),
    }, clerical=True)


def _set_status(ctx, a):
    cid, status = a["id"], a["status"]
    ns, _ = split_id(cid)
    check_ns(ctx, ns)
    if not ctx.is_human and ctx.agent != "claim-keeper":
        raise ToolError("refused: only claim-keeper or the human sets a status")
    be = backend(ctx)
    ok, reasons = check_grounds(status, a.get("grounds"), be.statement_hash(cid),
                                human=ctx.is_human)
    if not ok:
        raise ToolError("refused: the grounds do not support %s -> %s:\n- %s"
                        % (cid, status, "\n- ".join(reasons)))
    g = a.get("grounds") or {}
    if g.get("basis") == "human" and not ctx.is_human:
        check_human_where(ctx, g)
    return be.set_status(cid, status, a.get("grounds"), a.get("note"))


ID = {"type": "string", "description": "Claim id '<ns>:<id>', e.g. lab:ew-check, "
                                       "paper:lem:strip-bound, s1:BOUND-1"}
NS = {"type": "string", "description": "A claim namespace: the 'ns' of an instance in "
                                       "workspace.json"}
GROUNDS = {"type": "object", "description": "See check_grounds: basis (proof | "
                                            "computation | human), verdicts[] (verdict, "
                                            "run_id, grader_role, statement_hash, commit, "
                                            "ref), producer_role, statement_hash, commit, "
                                            "validation_passed, outcome, modulo, note; "
                                            "every verdict's ref is its landed review "
                                            "record; superseded: superseded_by; "
                                            "human: quote, where (an agent: the T-/P- "
                                            "id holding the quote); s1: verdict_file"}

TOOLS = [
    Tool("claims_show", "Show one claim (any namespace) with its evidence and back-links.",
         obj({"id": ID, "full": B}, ["id"]), _show),
    Tool("claims_list", "List claims of one namespace, filtered by status / where / kind "
         "/ free text (s1: kb.py find).",
         obj({"ns": NS, "status": S, "where": S, "kind": S, "text": S}, ["ns"]), _list),
    Tool("claims_query", "One read-only SQL SELECT on a namespace's derived registry "
         "tables (lab/paper: claims, evidence, history, links, open_items).",
         obj({"ns": NS, "sql": S}, ["ns", "sql"]), _query),
    Tool("claims_deps", "What a claim depends on / bears on, or with reverse=true what "
         "rests on it; transitive for the closure.",
         obj({"id": ID, "reverse": B, "transitive": B}, ["id"]), _deps),
    Tool("claims_check", "Run the registry's consistency check for a namespace.",
         obj({"ns": NS, "strict": B}, ["ns"]), _check),
    Tool("claims_new", "Create a claim with an unsettled status (open, conjectured, "
         "sketch), in the caller's own namespace. For s1 the id part is kb.py's prefix.",
         obj({"id": ID, "title": S, "status": {"type": "string", "enum": list(UNSETTLED)},
              "where": S, "kind": S}, ["id", "title"]), _new, write=True),
    Tool("claims_attach_evidence", "Append one evidence row {type, ref, verdict, run_id, "
         "note} to a claim (append-only). s1: a verdict file, appended to cleared_by.",
         obj({"id": ID, "row": {"type": "object"}}, ["id", "row"]), _attach, write=True),
    Tool("claims_propose_status", "Propose a status change: files a decision ticket to "
         "the claim-keeper's instance; changes nothing itself.",
         obj({"id": ID, "status": S, "reason": S, "grounds": GROUNDS, "refs": L},
             ["id", "status"]), _propose, write=True),
    Tool("claims_set_status", "Set a claim's status, or move its lifecycle (superseded, "
         "dropped; with a note), as claim-keeper or the human. The server re-checks the "
         "grounds (plan section 8) and the review records they cite, and refuses without "
         "them.",
         obj({"id": ID, "status": S, "grounds": GROUNDS, "note": S}, ["id", "status"]),
         _set_status, write=True),
]
