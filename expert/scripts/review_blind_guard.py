"""PreToolUse hook (Read|Grep|Glob): keep the rigor-reviewer blind to other reviews.

Run B must not see run A (plan section 8: "each fresh and blind to the other"). The
records live in ``<expert home>/reviews/``, so this denies a ``rigor-reviewer``
(``expert:rigor-reviewer`` or bare) any Read of a file there, and any Grep or Glob
whose search root is inside ``reviews/`` or contains it (a search of the whole
library home would sweep the records too; the reviewer narrows the path instead).
The ``dependency-settler`` (#121) is closed off the same way, with one opening: a Read
of ``A.md``, ``B.md`` or ``S-table.json`` in an open pass folder (a folder named for a
pass, ``YYYY-MM-DD[-...]``, with neither ``decision.md`` nor ``abandoned.md``): the two
verdicts and the table of the pass it settles. No search under ``reviews/`` and no other
file there (another pass's decision, a closed pass's verdicts).
Silent for every other agent, the human, and every path outside the Expert homes.
"""

import json
import os
import re
import sys

AGENT = "rigor-reviewer"
SETTLER = "dependency-settler"
#: what the settler may read in its open pass folder
SETTLER_FILES = ("A.md", "B.md", "S-table.json")
RE_PASS = re.compile(r"^\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?$")
CLOSERS = ("decision.md", "abandoned.md")


def _fast_skip(raw):
    """True when the event plainly has no rigor-reviewer or dependency-settler in it (the
    common case: this hook sees every Read, Grep and Glob of every session, so it exits
    before importing anything)."""
    return AGENT not in raw and SETTLER not in raw


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
REASON = ("The review records under %s are closed to %s runs: a run must be "
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


def settler_may_read(path, is_search):
    """True for a settler's Read of one of ``SETTLER_FILES`` in an open pass folder."""
    if is_search or os.path.basename(path) not in SETTLER_FILES:
        return False
    real = os.path.realpath(path)
    if os.path.normcase(real) != os.path.normcase(os.path.abspath(path)):
        return False                     # a symlink could point anywhere (review of 39de757)
    d = os.path.dirname(real)
    if not RE_PASS.match(os.path.basename(d)):
        return False
    # the pass being settled: open, laid out reviews/<ns>/<subject>/<pass>, and holding
    # the table the workflow writes just before it launches the settler (S-table.json);
    # another subject's open pass holds none (review of 39de757)
    subject_dir = os.path.dirname(d)
    ns_dir = os.path.dirname(subject_dir)
    if os.path.basename(os.path.dirname(ns_dir)) != "reviews":
        return False
    if not os.path.exists(os.path.join(d, "S-table.json")):
        return False
    return not any(os.path.exists(os.path.join(d, c)) for c in CLOSERS)


def main(raw=None):
    if raw is None:
        event = ac.read_event()
    else:
        try:
            event = json.loads(raw) if raw.strip() else {}
        except ValueError:
            event = {}
        event = event if isinstance(event, dict) else {}
    settler = ex.is_expert_agent(event, SETTLER)
    if not (settler or ex.is_expert_agent(event, AGENT)):
        return 0
    ws = ex.load_workspace_or_none()
    if not ws:
        return 0
    path, is_search = target(event)
    who = SETTLER if settler else AGENT
    for rdir in reviews_dirs(ws):
        if ex.is_under(path, rdir):
            if settler and settler_may_read(path, is_search):
                return 0
            return ac.emit_permission("deny", REASON % (
                rdir.replace("\\", "/"), who, "Read the statement, its proof and its sources "
                "instead."))
        if is_search and ex.is_under(rdir, path):
            return ac.emit_permission("deny", REASON % (
                rdir.replace("\\", "/"), who, "This search root contains them: give a path "
                "that does not (a cached file, a .src/ folder, a section file)."))
    return 0


if __name__ == "__main__":
    sys.exit(main(_RAW))
