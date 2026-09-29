"""claims_edit_check -- PostToolUse (Edit|Write|MultiEdit): check a registry record after an edit.

The one record hook of every registry (merge proposal phase 4, plan section 6 R4). It
replaces the old lab plugin's ``claims_edit_check.py`` and the first notebook's local
record hook (``tools/kb_hook.py``).
After an edit of a record of any registry home in workspace.json it runs the registry
engine (``academy/registry``) on that home:

1. ``check <file>``: the file's findings. Error lines (at most 20) go back to the model
   as a PostToolUse block (advisory; the edit stands).
2. ``build --quiet``, when the home's profile asks for it (``registry.hook_policy``:
   the s1-kb profile does, as the local hook did): a failed build exits 2 with the
   output on stderr, which blocks as that hook did.

Which files are records: ``_researcher.record_for`` (the home's ``registry.root`` and
``paths.records``, or the legacy folders before a switch-over), plus the directories
the home's profile watches (the first notebook's ledgers under ``computation/``).

**Who owns a home not yet switched over** (no ``.claude/academy.json``): a legacy hook
still registered there does, and this hook stays silent so nothing is reported twice.
The legacy owners are the old lab plugin's hook (the home's old plugin config,
``LEGACY_PLUGIN_CONFIG``, names ``claims.py`` as its registry tool) and the local record
hook (``LEGACY_LOCAL_HOOK``, named in the home's ``.claude/settings.json`` or
``settings.local.json``). Once a home drops its legacy hook, this one fires there.

The engine is found at ``$ACADEMY_ROOT/academy``, then beside this plugin
(``<academy repo>/academy``). A home's
academy.json may name its own command as ``registry.check`` (``{file}`` is replaced by
the record's path, else the path is appended); it then replaces step 1 and step 2 is
skipped. A missing engine, a timeout or a hook bug is silent.
"""

import json
import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402

MAX_LINES = 20
TIMEOUT = 60
PLUGIN = os.path.dirname(HERE)
#: the old lab plugin's per-home config file, and the first notebook's own record hook
LEGACY_PLUGIN_CONFIG = "flat" "surf.json"
LEGACY_LOCAL_HOOK = "kb_hook"


def engine_dir():
    """The directory holding the ``registry`` package, or None."""
    cands = []
    if os.environ.get("ACADEMY_ROOT"):
        cands.append(os.path.join(os.environ["ACADEMY_ROOT"], "academy"))
    cands.append(os.path.join(os.path.dirname(PLUGIN), "academy"))
    for c in cands:
        if os.path.isfile(os.path.join(c, "registry", "__init__.py")):
            return os.path.abspath(c)
    return None


def _split(cmd):
    parts = shlex.split(cmd.replace("\\", "/"))
    if parts and parts[0].lower() in ("py", "py.exe", "python", "python3"):
        parts[0] = sys.executable
    return parts


def check_command(rec, path):
    """The argv that checks record ``path``: the home's ``registry.check`` when it names
    one, else the engine's ``check <file>``; None when neither exists."""
    reg = (rec.get("config") or {}).get("registry") or {}
    full = os.path.abspath(path).replace("\\", "/")
    if isinstance(reg.get("check"), str) and reg["check"].strip():
        cmd = reg["check"]
        if "{file}" in cmd:
            return _split(cmd.replace("{file}", '"%s"' % full))
        return _split(cmd) + [full]
    if not engine_dir():
        return None
    return [sys.executable, "-m", "registry", "--repo", rec["home"], "check", full]


def build_command(rec):
    if not engine_dir():
        return None
    return [sys.executable, "-m", "registry", "--repo", rec["home"], "build", "--quiet"]


def legacy_owner(home):
    """The legacy hook that still owns record checks in ``home``, or None."""
    try:
        with open(os.path.join(home, ".claude", LEGACY_PLUGIN_CONFIG), encoding="utf-8") as fh:
            if ((json.load(fh).get("registry") or {}).get("tool")) == "claims.py":
                return "the old lab plugin's claims check (.claude/%s)" % LEGACY_PLUGIN_CONFIG
    except (OSError, ValueError, AttributeError):
        pass
    for name in ("settings.json", "settings.local.json"):
        try:
            with open(os.path.join(home, ".claude", name), encoding="utf-8") as fh:
                if LEGACY_LOCAL_HOOK in fh.read():
                    return "the local record hook (.claude/%s)" % name
        except OSError:
            pass
    return None


def policy(home, ns):
    """The engine's hook policy for ``home`` (registry.hook_policy), or None."""
    d = engine_dir()
    if not d:
        return None
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        import registry
        return registry.hook_policy(home, ns)
    except Exception:
        return None


def find_record(path, ws=None):
    """``_researcher.record_for``, widened by the directories the home's profile watches."""
    rec = rs.record_for(path, ws)
    if rec or not path or not str(path).lower().endswith(".md"):
        return rec
    ws = ws if ws is not None else rs.workspace_or_none()
    if not ws or os.path.basename(str(path)) in rs.NOT_RECORDS:
        return None
    full = os.path.abspath(str(path))
    for name, home, ns, cfg in rs.registry_homes(ws):
        rel = ac._rel_to(home, full)
        if not rel:
            continue
        pol = policy(home, ns) or {}
        if any(ac._match_path(rel, w) for w in pol.get("watched", [])):
            return {"instance": name, "home": home, "ns": ns, "config": cfg, "rel": rel}
    return None


def _run(argv, home):
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    d = engine_dir()
    if d:
        env["PYTHONPATH"] = d + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(argv, cwd=home, capture_output=True, timeout=TIMEOUT, env=env)
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")


def error_lines(output, returncode):
    lines = [ln for ln in output.splitlines() if "error" in ln.lower()]
    if not lines and returncode != 0:
        lines = [ln for ln in output.splitlines() if ln.strip()][-MAX_LINES:]
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + ["... (%d more)" % (len(lines) - MAX_LINES)]
    return lines


def run(event, ws=None):
    """``(kind, text)``: ``("block", reason)`` for the model, ``("fail", stderr)`` for a
    failed blocking build (exit 2), or None."""
    path = ac.edited_path(event)
    rec = find_record(path, ws)
    if not rec or not os.path.isfile(path):
        return None
    if not rec.get("config") and legacy_owner(rec["home"]):
        return None
    argv = check_command(rec, path)
    if not argv:
        return None
    try:
        rc, out = _run(argv, rec["home"])
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    lines = error_lines(out, rc) if rc != 0 else []
    explicit = bool(((rec.get("config") or {}).get("registry") or {}).get("check"))
    pol = None if explicit else policy(rec["home"], rec["ns"])
    if pol and pol.get("build") and any(ac._match_path(rec["rel"], w)
                                        for w in pol.get("watched", [])):
        bargv = build_command(rec)
        try:
            brc, bout = _run(bargv, rec["home"]) if bargv else (0, "")
        except (OSError, subprocess.SubprocessError, ValueError):
            brc, bout = 0, ""
        if brc != 0:
            head = ("registry check on %s (%s):\n%s\n" % (rec["rel"], rec["ns"], "\n".join(lines))
                    if lines else "")
            return ("fail", "%sregistry build failed after editing %s:\n%s"
                    % (head, rec["rel"], bout))
    if not lines:
        return None
    return ("block", "registry check on %s (%s):\n%s\nFix the record; a status line is "
                     "changed only by claim-keeper." % (rec["rel"], rec["ns"], "\n".join(lines)))


def main():
    event = ac.read_event()
    try:
        res = run(event)
    except Exception:
        return 0
    if not res:
        return 0
    kind, text = res
    if kind == "fail":
        sys.stderr.write(text)
        return 2
    ac.emit_block(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
