"""PreToolUse hook (Read|Grep|Glob): keep the experiment-reviewer blind to other runs.

Plan section 8 asks for agent-level independence of the two experiment reviews: run B
must not see run A. land_review.py files every run under
``<researcher home>/<paths.audits>/`` (default ``audits/``), so this denies an
``experiment-reviewer`` (``researcher:experiment-reviewer`` or bare) any Read of a file
there, and any Grep or Glob whose search root is inside an audits folder or contains
one (a search of the whole notebook would sweep the records too; the reviewer narrows
the path instead). The counterpart of the Expert's review_blind_guard.py.

Silent for every other agent, the human, and every path outside the audits folders
of the researcher instances in workspace.json. A hook bug never blocks a read.
"""

import json
import os
import sys

AGENT = "experiment-reviewer"


def _fast_skip(raw):
    """True when the event plainly has no experiment-reviewer in it (this hook sees
    every Read, Grep and Glob of every session, so it exits before importing)."""
    return AGENT not in raw


if __name__ == "__main__":
    _RAW = sys.stdin.read()
    if _fast_skip(_RAW):
        sys.exit(0)
else:
    _RAW = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402

REASON = ("The experiment review records under %s are closed to experiment-reviewer "
          "runs: a run must be blind to every other run's verdict (plan section 8). %s")


def audits_dirs(ws):
    """The audits folder of every researcher instance in ``ws``."""
    out = []
    for name, inst in (ws or {}).get("instances", {}).items():
        if inst.get("role") != "researcher" or not inst.get("home"):
            continue
        home = os.path.abspath(inst["home"])
        cfg = rs._config_or_none(home) if os.path.isfile(
            os.path.join(home, ac.CONFIG_REL)) else None
        out.append(rs.notebook_paths(home, cfg)["audits"])
    return out


def _under(path, root):
    p = os.path.normcase(os.path.abspath(path))
    r = os.path.normcase(os.path.abspath(root))
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def target(event):
    ti = ac.tool_input(event)
    tool = ac.tool_name(event)
    p = ti.get("file_path") if tool == "Read" else ti.get("path")
    if not p:
        return ac.event_cwd(event), True
    if not os.path.isabs(p):
        p = os.path.join(ac.event_cwd(event), p)
    return p, tool != "Read"


def decide(event, ws=None):
    """``None`` or ``("deny", reason)``."""
    _, bare = ac.agent_identity(event)
    if bare != AGENT or ac.tool_name(event) not in ("Read", "Grep", "Glob"):
        return None
    ws = ws if ws is not None else rs.workspace_or_none()
    if not ws:
        return None
    path, is_search = target(event)
    for adir in audits_dirs(ws):
        shown = adir.replace("\\", "/")
        if _under(path, adir):
            return ("deny", REASON % (shown, "Read the script, its header, the result "
                                             "JSON and the report instead."))
        if is_search and _under(adir, path):
            return ("deny", REASON % (shown, "This search root contains them: give a "
                                             "path that does not (experiments/, "
                                             "results/, a report)."))
    return None


def main(raw=None):
    if raw is None:
        event = ac.read_event()
    else:
        try:
            event = json.loads(raw) if raw.strip() else {}
        except ValueError:
            event = {}
        event = event if isinstance(event, dict) else {}
    try:
        verdict = decide(event)
    except Exception:            # a guard bug never blocks a read
        return 0
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(_RAW))
