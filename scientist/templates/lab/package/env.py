"""Which environment is this, and how do we record it?

Scaffolded by `/academy:init scientist@<name>` from the Scientist plugin's
`templates/lab/`; the lab owns its copy from then on. The experiment checker
(`check_experiments.py`) requires every experiment to call `env.banner` (E6) and
`env.save_result` (E5), and a script with a `Kind:` header to pass `outcome=` built
by one of the `*_outcome` helpers below (E10).

Every experiment starts with `banner(__file__)`, so the printed output (and the JSON
written by `save_result`) carries the date, the git commit, the interpreter and the
library versions. That is what makes a result citable later. The commit is stamped
`dirty`, with the files named, when the code that ran is not all in it: a tracked file
changed, the running script not tracked, or an untracked file under `CODE_DIRS`.

    from <package> import env
    env.banner(__file__)                 # provenance header
    if env.have_sage(): ...              # branch on capability
    env.require_sage()                   # or refuse to run without it
    env.save_result("my_experiment", raw, script=__file__, claims=[...],
                    outcome=env.search_outcome(examples, constraints))

Pure standard library: importable on any interpreter, with or without the lab's
heavy libraries.
"""

import datetime
import importlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
# Interactive snapshots live apart from experiment results: a snapshot is a picture
# someone was looking at, a result is evidence for a claim.
SESSIONS = ROOT / "sessions"

#: the libraries whose versions every result records, as {name: module}. The module's
#: ``__version__`` (or ``version.version``) is read; ``sage`` is special-cased. Edit for
#: this lab (the domain pack's computation/README.md names the usual ones).
LIBRARIES = {"sage": "sage"}

OUTCOME_KINDS = ("search", "measure", "verify")


def have_sage():
    """True if SageMath is importable in this interpreter."""
    try:
        import sage.all  # noqa: F401
        return True
    except ImportError:
        return False


def require_sage(what="this experiment"):
    """Exit with a pointer to the runner instead of a long traceback."""
    if not have_sage():
        sys.exit(f"{what} needs SageMath. Run it through the lab's environment profile, "
                 "e.g. `env.py run test experiments/<script>.py` (the Scientist's "
                 "/scientist:env and /scientist:queue).")


def _version(module):
    if module == "sage":
        try:
            from sage.version import version
            return version
        except ImportError:
            return None
    try:
        mod = importlib.import_module(module)
    except Exception:  # an absent or broken library is recorded as absent
        return None
    v = getattr(mod, "__version__", None)
    if v is None:
        v = getattr(getattr(mod, "version", None), "version", None)
    return str(v) if v is not None else "unknown"


def versions():
    """Interpreter and library versions, None for anything absent."""
    v = {"python": platform.python_version(), "platform": platform.platform()}
    for name, module in LIBRARIES.items():
        v[name] = _version(module)
    return v


#: Untracked (non-ignored) files under these directories make the tree dirty: they
#: are code a run may import or read that the recorded commit does not contain.
#: Untracked files elsewhere (results being written, notes) do not. The second entry
#: is this package's own directory, whatever the lab named it.
CODE_DIRS = ("experiments", Path(__file__).resolve().parent.name)


def _git_lines(root, *args):
    """NUL-separated output of a git command as a list of paths."""
    out = subprocess.check_output(["git", *args], cwd=root,
                                  stderr=subprocess.DEVNULL)
    return [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]


def git_state(script=None, root=None):
    """The commit a result can be reproduced from, or None outside git.

    Returns {"commit", "dirty", "modified", "untracked"}: `modified` lists tracked
    files that differ from HEAD (staged or not); `untracked` lists the running
    `script` unless the repo's index tracks it (so also when it is gitignored, e.g.
    under scratch/, inside a nested checkout such as .worktrees/<w>/, or outside the
    repo; the last is recorded as an absolute path) and every untracked,
    non-ignored file under CODE_DIRS of `root`. `dirty` is true when either list is
    non-empty. `root` (default: the lab root) may lie below the git top level;
    paths are relative to the top level, '/'-separated, sorted.
    """
    root = Path(root or ROOT).resolve()
    try:
        h = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                                    text=True, stderr=subprocess.DEVNULL).strip()
        top = Path(subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=root, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()).resolve()
        sub = root.relative_to(top).as_posix()
        dirs = [d if sub == "." else f"{sub}/{d}" for d in CODE_DIRS]
        modified = _git_lines(top, "diff", "--name-only", "-z", "HEAD")
        untracked = set(_git_lines(top, "ls-files", "--others", "--exclude-standard",
                                   "-z", "--", *dirs))
        if script is not None:
            s = Path(script).resolve()
            try:
                rel = s.relative_to(top).as_posix()
            except ValueError:   # outside the repo: no commit of it holds the script
                untracked.add(s.as_posix())
            else:
                # Ask "is it tracked?", not "is it listed as other?": ls-files
                # --others skips ignored files and does not descend into a nested
                # repository, and either would pass an uncommitted script as clean.
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", "--", ":(literal)" + rel],
                    cwd=top, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                ).returncode == 0
                if not tracked:
                    untracked.add(rel)
        modified, untracked = sorted(set(modified)), sorted(untracked)
        return {"commit": h, "dirty": bool(modified or untracked),
                "modified": modified, "untracked": untracked}
    except (OSError, subprocess.CalledProcessError):
        return None


def provenance(script=None):
    """Date, script, commit, arguments and versions, as one dict."""
    if script:
        try:
            shown = Path(script).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            shown = Path(script).as_posix()
    else:
        shown = None
    p = {"date": datetime.datetime.now().isoformat(timespec="seconds"),
         "script": shown, "git": git_state(script), "argv": sys.argv[1:]}
    p.update(versions())
    return p


def banner(script=None):
    """Print the provenance header. Returns the dict for reuse."""
    p = provenance(script)
    g = p["git"]
    gs = "no git" if g is None else g["commit"] + (" (dirty)" if g["dirty"] else "")
    libs = ", ".join("%s %s" % (k, p[k]) for k in LIBRARIES if p.get(k)) \
        or "none of %s" % ", ".join(LIBRARIES)
    print("=" * 72)
    print(f"{p['script'] or '<interactive>'}   {p['date']}   commit {gs}")
    print(f"python {p['python']}   {libs}")
    if p["argv"]:
        print(f"args: {p['argv']}")
    if g is not None and g["dirty"]:
        for what in ("modified", "untracked"):
            if g[what]:
                print(f"{what} (not in commit {g['commit']}): " + ", ".join(g[what]))
    print("=" * 72)
    return p


def search_outcome(examples, constraints):
    """The outcome block of a `search` (experiments/README.md).

    `examples` lists what was found, each a dict with a "certificate" (enough to
    recheck the example without the search) and optionally "recorded" (the recorded
    properties). `constraints` is the dict of parameters the search actually ran under.
    An empty `examples` means "not found" -- under these constraints and nothing more.
    """
    for e in examples:
        if "certificate" not in e:
            raise ValueError("every example needs a 'certificate'")
    return {"kind": "search", "status": "found" if examples else "not found",
            "count": len(examples), "constraints": constraints, "examples": examples}


def measure_outcome(values, cls):
    """The outcome block of a `measure`: `values` computed over the class `cls`."""
    return {"kind": "measure", "status": "measured", "class": cls, "values": values}


def verify_outcome(obj, properties, routes=1):
    """The outcome block of a `verify`: `properties` maps each property to True (holds)
    or False (fails); `routes` is how many independent methods decided them (two
    before the result is cited)."""
    props = {k: ("holds" if v else "fails") for k, v in properties.items()}
    status = "holds" if all(properties.values()) else "fails"
    return {"kind": "verify", "status": status, "object": obj, "properties": props,
            "routes": routes}


def save_result(name, data, script=None, subdir=None, base=None, claims=None,
                outcome=None):
    """Write results/[subdir/]<name>.json with provenance attached; returns the path.

    `claims` lists the registry ids this result bears on; `outcome` is the block built
    by search_outcome / measure_outcome / verify_outcome, written first so a reader
    gets the answer without the raw `result`. `data` must be JSON-serialisable:
    convert exact numbers (fractions, library integers) explicitly first. `base`
    overrides the root directory (SESSIONS for interactive snapshots).
    """
    root = Path(base) if base else RESULTS
    d = root / subdir if subdir else root
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.json"
    head = {}
    if claims:
        head["claims"] = list(claims)
    if outcome is not None:
        if outcome.get("kind") not in OUTCOME_KINDS:
            raise ValueError("outcome must come from search_outcome / measure_outcome / "
                             "verify_outcome")
        head["outcome"] = outcome
    payload = {**head, "provenance": provenance(script), "result": data}
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    try:
        shown = path.relative_to(ROOT)
    except ValueError:
        shown = path
    print(f"saved {shown}")
    return path
