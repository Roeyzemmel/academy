#!/usr/bin/env python3
"""Mechanical checks on experiments/ and results/ -- the rules in CLAUDE.md that a
machine can enforce, so that a human review is spent on the mathematics instead.

    py check_experiments.py [--home LAB]                 # everything
    py check_experiments.py [--home LAB] experiments\\foo.py [...]
    py check_experiments.py [--home LAB] --strict        # warnings count as failures

This is the Scientist plugin's copy (plan section 3.6). The rules are the lab's,
unchanged; what differs is where the lab is: ``--home``, else ``$ACADEMY_LAB_HOME``,
else the academy home (``.claude/academy.json``) around the cwd, else the cwd. The
experiments and results directories come from that home's academy.json
(``paths.experiments``, e.g. ``experiments/*.py``, and ``paths.results``), defaulting
to ``experiments`` and ``results``. The lab's ``scripts/check_experiments.py`` is a
shim that sets the home and forwards here, so its tests and hooks keep working.

Output is one finding per line, `file:line: LABEL: [RULE] message`, so an editor
or a hook can jump to it. Exit code 0 when clean, 1 when something failed.

The rules exist because each of them has already gone wrong here:

  E1  filename is not YYYY-MM-DD_<slug>.py
  E2  a mandatory header field is missing
  E3  a header field is still the template's <placeholder>
  E4  the Result line claims a theorem ("true", "proved", "always") instead of
      reporting "no counterexample below bound B over class C"
  E5  the script never calls env.save_result
  E6  the script never calls env.banner, so its output carries no provenance
  E7  a `Claims:` id is not in the claim registry (docs/claims.md); an id in a
      namespace with another rule set (a paper's, a notebook's) is not checked here
  E8  no `Kind:` (search / measure / verify) on a script dated from CUTOVER on, or
      an unknown kind
  E9  a search whose constraint has no [reason] tag, whose Properties name no
      required property, or whose filled Result is neither "found" nor "not found"
  E10 a script with a `Kind:` whose save_result has no outcome= (env.search_outcome /
      measure_outcome / verify_outcome)
  W5  a script with a `Kind:` whose result JSON has no "outcome" block
  W4  a script dated before CUTOVER with no `Claims:` line (back-fill it)
  W1  "Needs Sage: yes" but no env.require_sage guard
  W2  a results/*.json with no experiment script of that name
  W3  the Result field is still empty on a script whose result JSON exists

Pure standard library, Python 3.10, runs on the laptop. Nothing here needs Sage.
"""

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

def _find_home(start):
    """The nearest ancestor of ``start`` holding .claude/academy.json, or None."""
    cur = Path(start).resolve()
    for p in [cur] + list(cur.parents):
        if (p / ".claude" / "academy.json").is_file():
            return p
    return None


def _dirs(root):
    """(experiments dir, results dir) of a lab home, from its academy.json."""
    exp, res = "experiments", "results"
    try:
        cfg = json.loads((root / ".claude" / "academy.json").read_text(encoding="utf-8-sig"))
        paths = cfg.get("paths") or {}
        pat = paths.get("experiments") or exp
        pat = pat[0] if isinstance(pat, list) else pat
        exp = pat.split("*", 1)[0].rstrip("/") or exp
        res = paths.get("results") or res
    except (OSError, ValueError, AttributeError):
        pass
    return root / exp, root / res


def set_home(home=None):
    """Point the checker at a lab home (see the module docstring for the order)."""
    global ROOT, EXPERIMENTS, RESULTS
    if home is None:
        home = os.environ.get("ACADEMY_LAB_HOME") or _find_home(os.getcwd()) or os.getcwd()
    ROOT = Path(home).resolve()
    EXPERIMENTS, RESULTS = _dirs(ROOT)


ROOT = EXPERIMENTS = RESULTS = None
set_home()

# The header contract, per kind (experiments/README.md). Order matters only for the report.
KIND_FIELDS = {
    "search": ("Goal", "Constraints", "Properties", "Certificate", "Validation"),
    "measure": ("Goal", "Class", "Quantity", "Validation"),
    "verify": ("Goal", "Object", "Properties", "Method", "Validation"),
}
# Scripts dated before CUTOVER may use the old falsifier header instead of a Kind.
LEGACY_FIELDS = ("Claim tested", "Refuted by", "Validation", "Search class")
FIELDS = tuple(dict.fromkeys(
    ("Kind", "Claims") + LEGACY_FIELDS + sum(KIND_FIELDS.values(), ()) + ("Needs Sage", "Result")))
# Scripts dated before this predate the kinds and the claim registry.
CUTOVER = "2026-09-25"
CONSTRAINT_TAG_RE = re.compile(r"\[(feasibility|setting|excludes\b[^\]]*)\]", re.IGNORECASE)

NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[A-Za-z0-9][A-Za-z0-9_]*\.py$")
PLACEHOLDER_RE = re.compile(r"<[A-Za-z][^<>=]*>")   # not `<= x ... ->`, which is maths
# Wording that turns a search into a theorem. "no counterexample" is the escape
# hatch: a sentence that already says it is allowed to use the other words.
OVERCLAIM_RE = re.compile(
    r"\b(is true|holds always|always holds|proves?|proved|proven|theorem|"
    r"confirmed the claim|verified the claim)\b",
    re.IGNORECASE,
)
HEDGED_RE = re.compile(r"\bno counterexample\b", re.IGNORECASE)

# Files under experiments/ that are not experiments.
EXEMPT = {"_template.py", "smoke_sage.py", "__init__.py"}

NO_DOC = "<no module docstring>"


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, path, line, rule, message):
        self.errors.append(_fmt(path, line, "ERROR", rule, message))

    def warn(self, path, line, rule, message):
        self.warnings.append(_fmt(path, line, "WARN", rule, message))


def _fmt(path, line, label, rule, message):
    try:
        shown = Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        shown = str(path)
    return "%s:%d: %s: [%s] %s" % (shown, line, label, rule, message)


def parse_header(text):
    """Map field name -> (value, 1-based line) from the module docstring.

    A field's value may wrap onto following indented lines; they are joined.
    Returns None when the file does not parse and NO_DOC when it has no module
    docstring at all -- both distinct from {}, "a docstring with no known fields".
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    doc = ast.get_docstring(tree, clean=False)
    if doc is None:
        return NO_DOC

    # Line of the docstring's first character, so reported lines land in the file.
    offset = 0
    for i, raw in enumerate(text.splitlines(), start=1):
        if raw.lstrip().startswith(('"""', "'''", 'r"""')):
            offset = i
            break

    fields = {}
    current = None
    for i, raw in enumerate(doc.splitlines()):
        m = re.match(r"^([A-Z][A-Za-z ]*?):\s*(.*)$", raw)
        if m and m.group(1).strip() in FIELDS:
            current = m.group(1).strip()
            fields[current] = [m.group(2).strip(), offset + i]
        elif current and raw.startswith((" ", "\t")) and raw.strip():
            fields[current][0] = (fields[current][0] + " " + raw.strip()).strip()
        elif not raw.strip():
            current = None
    return {k: tuple(v) for k, v in fields.items()}


def calls(text):
    """Set of dotted call names used in the file, e.g. {"env.save_result"}."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                names.add("%s.%s" % (f.value.id, f.attr))
            elif isinstance(f, ast.Name):
                names.add(f.id)
    return names


def _rule_set_of(ns):
    """The rule set (``lab``, ``paper``, ``notebook``) of namespace ``ns``: its instance's
    ``registry.profile`` in workspace.json, else the namespace's own name read as a rule
    set (``paper``; ``s1`` is an alias of ``notebook``), else ``lab``."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import _academy as ac
    except ImportError:  # the checker must not fail over its own tooling
        return "lab"
    try:
        ws = ac.load_workspace()
    except Exception:
        ws = {}
    for inst in (ws.get("instances") or {}).values():
        if isinstance(inst, dict) and inst.get("ns") == ns and inst.get("home"):
            try:
                prof = ac.load_config(inst["home"]).get("registry", {}).get("profile")
            except Exception:
                break
            return ac.registry_rule_set(prof) or "lab"
    return ac.registry_rule_set(ns) or "lab"


def unchecked_namespace(ns, _cache={}):
    """True when ``ns`` is another kind of registry (rule set ``paper`` or ``notebook``),
    whose ids this checker does not validate."""
    if ns not in _cache:
        _cache[ns] = _rule_set_of(ns) in ("paper", "notebook")
    return _cache[ns]


def registry_ids():
    """Ids in the claim registry, or None when the registry cannot be read."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("claims", ROOT / "scripts" / "claims.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        cs, _ = mod.load(mod.registry_root(ROOT))
    except Exception:  # the checker must not fail over its own tooling
        return None
    return {c.fields.get("id") for c in cs}


def passes_outcome(text):
    """True when some save_result call in the file passes outcome=."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if name == "save_result" and any(k.arg == "outcome" for k in node.keywords):
                return True
    return False


def result_has_outcome(stem):
    """None when there is no results/<stem>.json, else whether it has an outcome block."""
    p = RESULTS / (stem + ".json")
    if not p.exists():
        return None
    try:
        return "outcome" in json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def check_search(path, header, report):
    """The shape rules of a search (experiments/README.md): every constraint says why
    it is there, a required property decides "found", and the Result says which
    outcome it was."""
    if "Constraints" in header:
        value, line = header["Constraints"]
        if value and not PLACEHOLDER_RE.search(value):
            items = [i.strip() for i in re.split(r"(?:^|\s)-\s+", value) if i.strip()]
            for item in items:
                if not CONSTRAINT_TAG_RE.search(item):
                    report.error(path, line, "E9",
                                 "constraint without a reason tag [feasibility | setting | "
                                 "excludes ...]: %s" % item)
    if "Properties" in header:
        value, line = header["Properties"]
        if value and not PLACEHOLDER_RE.search(value) and "required" not in value.lower():
            report.error(path, line, "E9", "Properties names no `required:` property, so "
                                            "nothing decides what counts as found")
    if "Result" in header:
        value, line = header["Result"]
        if value and not PLACEHOLDER_RE.search(value) and \
                not re.match(r"(not )?found\b", value, re.IGNORECASE):
            report.error(path, line, "E9", "a search's Result starts with \"found\" or "
                                            "\"not found\": %s" % value)


def check_script(path, report, results_index, known_ids=None):
    text = path.read_text(encoding="utf-8", errors="replace")

    if not NAME_RE.match(path.name):
        report.error(path, 1, "E1", "filename should be YYYY-MM-DD_<slug>.py")

    header = parse_header(text)
    if header is None:
        report.error(path, 1, "E2", "file does not parse; header cannot be checked")
        return
    if header == NO_DOC:
        report.error(path, 1, "E2",
                     "no module docstring: the header (claim, refuting outcome, "
                     "validation, search class) is mandatory")
        return
    contract = [f for f in FIELDS if f not in ("Needs Sage", "Result")]
    if not any(f in header for f in contract):
        report.error(path, 1, "E2",
                     "the docstring uses none of the header fields -- prose is not the "
                     "contract; copy the field names from experiments/_template.py")
        return

    legacy = path.name[:10] < CUTOVER
    kind = header["Kind"][0].split()[0].lower() if header.get("Kind", ("",))[0] else None
    if kind is None:
        if not legacy:
            report.error(path, 1, "E8", "no `Kind:` line (search / measure / verify; "
                                        "see experiments/README.md)")
            return
        mandatory = ("Claims",) + LEGACY_FIELDS
    elif kind not in KIND_FIELDS:
        report.error(path, header["Kind"][1], "E8",
                     "unknown Kind %r; one of %s" % (kind, ", ".join(KIND_FIELDS)))
        return
    else:
        mandatory = ("Claims",) + KIND_FIELDS[kind]

    for field in mandatory:
        if field not in header:
            if field == "Claims" and legacy:
                report.warn(path, 1, "W4", "no `Claims:` line; back-fill it with registry ids "
                                           "(docs/claims.md)")
                continue
            report.error(path, 1, "E2", "header has no %r field" % field)
            continue
        value, line = header[field]
        if not value:
            report.error(path, line, "E2", "header field %r is empty" % field)
        elif PLACEHOLDER_RE.search(value):
            report.error(path, line, "E3",
                         "header field %r is still the template placeholder: %s"
                         % (field, value))

    if "Claims" in header and known_ids is not None:
        value, line = header["Claims"]
        for cid in (t.strip() for t in value.split(",")):
            if not cid or PLACEHOLDER_RE.search(cid):
                continue
            if ":" in cid and unchecked_namespace(cid.split(":", 1)[0]):
                continue
            if cid not in known_ids:
                report.error(path, line, "E7",
                             "claim %r is not in the registry; create it with "
                             "`registry.py new %s --title ...` (academy/scripts/registry.py)"
                             % (cid, cid))

    if kind == "search":
        check_search(path, header, report)
    if kind is not None:
        if not passes_outcome(text):
            report.error(path, 1, "E10", "save_result is never given outcome= (build it with "
                                         "env.search_outcome / measure_outcome / verify_outcome)")
        if result_has_outcome(path.stem) is False:
            report.warn(path, 1, "W5", "results/%s.json has no \"outcome\" block; it predates "
                                       "the Kind header, so rerun it" % path.stem)

    if "Result" in header:
        value, line = header["Result"]
        if value and not PLACEHOLDER_RE.search(value):
            if OVERCLAIM_RE.search(value) and not HEDGED_RE.search(value):
                report.error(path, line, "E4",
                             "Result reads as a theorem; say \"no counterexample "
                             "below bound B over class C\": %s" % value)
        elif path.stem in results_index:
            report.warn(path, line, "W3",
                        "results/%s.json exists but the Result field is unfilled"
                        % path.stem)

    used = calls(text)
    if "env.save_result" not in used and "save_result" not in used:
        report.error(path, 1, "E5", "never calls env.save_result, so the run leaves "
                                    "no provenance-stamped record")
    if "env.banner" not in used and "banner" not in used:
        report.error(path, 1, "E6", "never calls env.banner, so its output carries "
                                    "no commit hash or library versions")

    needs_sage = header.get("Needs Sage", ("", 1))[0].strip().lower().startswith("y")
    if needs_sage and "env.require_sage" not in used and "require_sage" not in used:
        report.warn(path, header.get("Needs Sage", ("", 1))[1], "W1",
                    "declares Needs Sage: yes but has no env.require_sage guard, so "
                    "it fails with a traceback instead of a pointer to the runner")


def check_results(report, scripts):
    stems = {p.stem for p in scripts}
    index = set()
    if not RESULTS.is_dir():
        return index
    for path in sorted(RESULTS.glob("*.json")):
        index.add(path.stem)
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            report.warn(path, 1, "W2", "not readable as JSON: %s" % exc)
            continue
        if path.stem not in stems:
            report.warn(path, 1, "W2",
                        "no experiments/%s.py: a result nobody can rerun" % path.stem)
    return index


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", help="scripts to check (default: all of experiments/)")
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    ap.add_argument("--quiet", action="store_true", help="findings only, no summary")
    ap.add_argument("--home", help="the lab home (default: $ACADEMY_LAB_HOME, the academy "
                    "home around the cwd, the cwd)")
    args = ap.parse_args(argv)
    if args.home:
        set_home(args.home)

    if args.paths:
        scripts = [Path(p).resolve() for p in args.paths]
        scripts = [p for p in scripts if p.suffix == ".py" and p.name not in EXEMPT]
    else:
        scripts = [p for p in sorted(EXPERIMENTS.glob("*.py")) if p.name not in EXEMPT]

    report = Report()
    if args.paths:
        # Checking named scripts: index results/ but do not report on files the
        # caller did not ask about.
        results_index = {p.stem for p in RESULTS.glob("*.json")} if RESULTS.is_dir() else set()
    else:
        all_scripts = [p for p in sorted(EXPERIMENTS.glob("*.py")) if p.name not in EXEMPT]
        results_index = check_results(report, all_scripts)

    known_ids = registry_ids()
    for path in scripts:
        if not path.is_file():
            report.error(path, 1, "E0", "no such file")
            continue
        check_script(path, report, results_index, known_ids)

    for line in report.errors + report.warnings:
        print(line)

    failed = bool(report.errors) or (args.strict and bool(report.warnings))
    if not args.quiet:
        print("%d error(s), %d warning(s) over %d script(s)%s"
              % (len(report.errors), len(report.warnings), len(scripts),
                 " -- strict" if args.strict else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
