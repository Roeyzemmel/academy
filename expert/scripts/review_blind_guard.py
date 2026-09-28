"""PreToolUse hook (Read|Grep|Glob): keep the rigor-reviewer blind to other reviews.

Run B must not see run A (plan section 8: "each fresh and blind to the other"). The
records live in ``<expert home>/reviews/``, so this denies a ``rigor-reviewer``
(``expert:rigor-reviewer`` or bare) any Read of a file there, and any Grep or Glob
whose search root is inside ``reviews/`` or contains it (a search of the whole
library home would sweep the records too; the reviewer narrows the path instead).
Silent for every other agent, the human, and every path outside the Expert homes.
"""

import json
import os
import sys

AGENT = "rigor-reviewer"


def _fast_skip(raw):
    """True when the event plainly has no rigor-reviewer in it (the common case: this
    hook sees every Read, Grep and Glob of every session, so it exits before
    importing anything)."""
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

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
REASON = ("The review records under %s are closed to rigor-reviewer runs: a run must be "
          "blind to every other run's verdict. %s")


def reviews_dirs(workspace):
    out = []
    for name in ex.expert_instances(workspace):
        home = workspace["instances"][name]["home"]
        out.append(ex.home_path(home, ex.expert_config(home), "reviews", "reviews"))
    return out


def target(event):
    ti = ac.tool_input(event)
    tool = ac.tool_name(event)
    p = ti.get("file_path") if tool == "Read" else ti.get("path")
    if not p:
        return ac.event_cwd(event), True
    if not os.path.isabs(p):
        p = os.path.join(ac.event_cwd(event), p)
    return p, tool != "Read"


def main(raw=None):
    if raw is None:
        event = ac.read_event()
    else:
        try:
            event = json.loads(raw) if raw.strip() else {}
        except ValueError:
            event = {}
        event = event if isinstance(event, dict) else {}
    if not ex.is_expert_agent(event, AGENT):
        return 0
    ws = ex.load_workspace_or_none()
    if not ws:
        return 0
    path, is_search = target(event)
    for rdir in reviews_dirs(ws):
        if ex.is_under(path, rdir):
            return ac.emit_permission("deny", REASON % (
                rdir.replace("\\", "/"), "Read the statement, its proof and its sources "
                "instead."))
        if is_search and ex.is_under(rdir, path):
            return ac.emit_permission("deny", REASON % (
                rdir.replace("\\", "/"), "This search root contains them: give a path "
                "that does not (a cached file, a .src/ folder, a section file)."))
    return 0


if __name__ == "__main__":
    sys.exit(main(_RAW))
