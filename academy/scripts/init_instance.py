"""init_instance.py -- scaffold a new academy instance (behind /academy:init).

Usage:

    py init_instance.py <role>@<name> --home PATH --domain D [--domain D2 ...]
                        [--ns NS] [--expert INST] [--scientist INST]
                        [--workspace PATH] [--no-board] [--force] [--dry-run]

Steps (each reported on stdout, nothing committed):

1. Build ``<home>/.claude/academy.json`` from ``templates/academy-json/<role>.json``
   (docs/config.md): ``{{instance}}``, ``{{ns}}``, ``{{noteMacro}}``, ``{{expert}}``,
   ``{{scientist}}`` are filled in and ``domains`` is set. ``ns`` defaults to the
   instance name for the roles with a registry; Expert has none. The result must
   pass ``validate_config``. An existing academy.json is refused unless ``--force``.
2. Register the instance in ``workspace.json`` (role, home, domains, ns). An
   existing row with a different home is refused; the same row is left alone.
   Write ``<home>/.gitattributes`` (LF everywhere; for an author, LF only for the
   ledgers and the registry) unless the home already has one.
3. For a researcher, scaffold the notebook of plan section 3.3:
   ``objects/<kind>/`` for every object kind, ``proofs/``, ``journal/``,
   ``audits/``, ``views/``, each with a ``.gitkeep``, plus a short
   ``objects/README.md``. Existing files are never overwritten.
4. Unless ``--no-board``, create the board folder ``<board>/<instance>/`` with a
   ``.gitkeep``, so tickets can be addressed to it.

``--dry-run`` prints the config and the plan and writes nothing.
"""

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

try:
    import academy_common as ac  # noqa: E402
except ImportError:  # vendored copy
    import _academy as ac  # noqa: E402

TEMPLATES = os.path.join(PLUGIN, "templates", "academy-json")
OBJECT_KINDS = ("definition", "claim", "conjecture", "question", "example",
                "assumption", "direction")
NOTEBOOK_DIRS = ("proofs", "journal", "audits", "views")
NOTEBOOK_README = """# Notebook objects

One typed object store (plan section 3.3). Each object is `objects/<kind>/<id>.md`
with one frontmatter schema: id, kind, title, status, statement, depends_on,
bears_on, domain, tags, evidence[], history[] (status only for claim, conjecture and
question). Proof attempts live in `proofs/<id>/attempt-<n>.md`; failed attempts are
kept. `journal/YYYY-MM-DD.md` is working memory and is never graded. `views/` is
generated; do not edit it. Only claim-keeper changes a status.
"""
# Git for Windows ships core.autocrlf=true; without these, files are committed with
# whatever endings the writer used (a stray CR even makes git call a .md binary).
GITATTRIBUTES = """# Store and check out text files with LF line endings on every platform.
* text=auto eol=lf
# Windows scripts keep CRLF.
*.ps1 text eol=crlf
*.bat text eol=crlf
*.cmd text eol=crlf
"""
# An Author home's tex may come from Overleaf or a coauthor: leave its endings alone.
GITATTRIBUTES_AUTHOR = """* text=auto
# The ledgers are LF; without this, core.autocrlf=true checks them out as CRLF.
Drafts/*.md text eol=lf
# The claim registry is LF (academy registry engine).
claims/** text eol=lf
"""


def load_template(role):
    path = os.path.join(TEMPLATES, "%s.json" % role)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _fill(obj, subs):
    if isinstance(obj, dict):
        return {k: _fill(v, subs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fill(v, subs) for v in obj]
    if isinstance(obj, str):
        for k, v in subs.items():
            obj = obj.replace("{{%s}}" % k, v)
        return obj
    return obj


def _first(workspace, role):
    for name in sorted((workspace or {}).get("instances", {})):
        if name.startswith(role + "@"):
            return name
    return ""


def build_config(instance, domains, ns=None, workspace=None, expert=None, scientist=None):
    """The academy.json dict for a new instance (validated; raises ConfigError)."""
    if not ac.RE_INSTANCE.match(instance or ""):
        raise ac.ConfigError("bad instance name %r (want <role>@<name>)" % instance)
    if not domains:
        raise ac.ConfigError("at least one --domain is required")
    role, name = instance.split("@", 1)
    tpl = load_template(role)
    human = ((workspace or {}).get("human") or {})
    subs = {
        "instance": instance,
        "ns": ns or name,
        "domain": domains[0],
        "noteMacro": human.get("noteMacro") or "\\Human",
        "expert": expert or _first(workspace, "expert"),
        "scientist": scientist or _first(workspace, "scientist"),
    }
    cfg = _fill(copy.deepcopy(tpl), subs)
    cfg["domains"] = list(domains)
    if role == "expert":
        cfg.pop("ns", None)
    probs = ac.validate_config(cfg)
    if probs:
        raise ac.ConfigError("; ".join(probs))
    return cfg


def register(workspace_path, instance, home, domains, ns):
    """Add the instance to workspace.json; returns 'added' or 'present'."""
    with open(workspace_path, "r", encoding="utf-8-sig") as fh:
        ws = json.load(fh)
    rows = ws.setdefault("instances", {})
    row = {"role": instance.split("@", 1)[0], "home": home, "domains": list(domains)}
    if ns:
        row["ns"] = ns
    old = rows.get(instance)
    if old is not None:
        if ac._norm(old.get("home", "")) != ac._norm(home):
            raise ac.ConfigError("%s is already registered at %s" % (instance, old.get("home")))
        if old == row:
            return "present"
        raise ac.ConfigError("%s is registered with different settings: %r" % (instance, old))
    rows[instance] = row
    ac.atomic_write(workspace_path, json.dumps(ws, indent=2, ensure_ascii=False) + "\n")
    return "added"


def _touch(path, text=""):
    if os.path.exists(path):
        return False
    ac.atomic_write(path, text)
    return True


def scaffold_notebook(home):
    """Create the researcher notebook layout; returns the list of files created."""
    made = []
    for kind in OBJECT_KINDS:
        p = os.path.join(home, "objects", kind, ".gitkeep")
        if _touch(p):
            made.append(p)
    p = os.path.join(home, "objects", "README.md")
    if _touch(p, NOTEBOOK_README):
        made.append(p)
    for d in NOTEBOOK_DIRS:
        p = os.path.join(home, d, ".gitkeep")
        if _touch(p):
            made.append(p)
    return made


def init_instance(instance, home, domains, ns=None, workspace_path=None, board=True,
                  force=False, dry_run=False, expert=None, scientist=None):
    """Run the four steps; returns a list of report lines."""
    home = os.path.abspath(home).replace("\\", "/")
    ws = ac.load_workspace(workspace_path)
    cfg = build_config(instance, domains, ns, ws, expert, scientist)
    cfg_path = os.path.join(home, ac.CONFIG_REL)
    lines = []
    if os.path.exists(cfg_path) and not force:
        raise ac.ConfigError("%s exists (use --force to overwrite)" % cfg_path)
    role = cfg["role"]
    board_dir = os.path.join(ws["board"], instance)
    if dry_run:
        lines.append("would write %s:" % cfg_path.replace("\\", "/"))
        lines.append(json.dumps(cfg, indent=2))
        lines.append("would register %s in %s" % (instance, ws["_path"]))
        if not os.path.exists(os.path.join(home, ".gitattributes")):
            lines.append("would write %s/.gitattributes" % home)
        if role == "researcher":
            lines.append("would scaffold the notebook under %s" % home)
        if board:
            lines.append("would create %s" % board_dir.replace("\\", "/"))
        return lines
    if not os.path.isdir(home):
        raise ac.ConfigError("home %s does not exist" % home)
    ac.atomic_write(cfg_path, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    lines.append("wrote %s" % cfg_path.replace("\\", "/"))
    state = register(ws["_path"], instance, home, cfg["domains"], cfg.get("ns"))
    lines.append("workspace: %s %s" % (instance, state))
    attrs = GITATTRIBUTES_AUTHOR if role == "author" else GITATTRIBUTES
    if _touch(os.path.join(home, ".gitattributes"), attrs):
        lines.append("wrote %s/.gitattributes" % home)
    else:
        lines.append(".gitattributes: present, left alone")
    if role == "researcher":
        made = scaffold_notebook(home)
        lines.append("notebook: %d file(s) created" % len(made))
    if board:
        if _touch(os.path.join(board_dir, ".gitkeep")):
            lines.append("board: created %s" % board_dir.replace("\\", "/"))
        else:
            lines.append("board: %s present" % board_dir.replace("\\", "/"))
    if not os.path.isdir(os.path.join(home, ".git")):
        lines.append("note: %s is not a git repository" % home)
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("instance")
    ap.add_argument("--home", required=True)
    ap.add_argument("--domain", action="append", required=True)
    ap.add_argument("--ns")
    ap.add_argument("--expert")
    ap.add_argument("--scientist")
    ap.add_argument("--workspace")
    ap.add_argument("--no-board", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        for line in init_instance(a.instance, a.home, a.domain, a.ns, a.workspace,
                                  not a.no_board, a.force, a.dry_run, a.expert, a.scientist):
            print(line)
    except (ac.AcademyError, OSError, ValueError) as exc:
        print("init_instance: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
