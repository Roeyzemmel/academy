"""PostToolUse gate (``Edit|Write|MultiEdit``): after an experiment script in a
Scientist home is written or edited, run the header checker on that one file and
hand its findings back as context.

Advisory only -- the edit has already happened and this never undoes it. Its job
is to catch the header contract slipping (an unfilled placeholder, a Result line
that reads as a theorem, a missing save_result) while the script is still being
written, instead of at commit time or, worse, after a queue run.

Scoped by the **edited path**, not the session cwd: the file must lie in a
Scientist home (``_common.lab_config``) and match its ``paths.experiments``.
Anywhere else, silent.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _common as c  # noqa: E402
from _common import ac  # noqa: E402

MAX_LINES = 20


def main():
    event = ac.read_event()
    path = ac.edited_path(event)
    if not path:
        return 0
    if not os.path.isabs(path):
        path = os.path.join(ac.event_cwd(event), path)
    cfg = c.lab_config(path)
    if cfg is None or not c.is_experiment(cfg, path) or not os.path.isfile(path):
        return 0
    code, output = c.run_checker(cfg, [path])
    if code in (None, 0):
        return 0
    lines = [ln for ln in output.splitlines() if ln.strip()]
    if not lines:
        return 0
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + ["... (%d more; run the checker for all)"
                                     % (len(lines) - MAX_LINES)]
    return c.speak(
        "check_experiments.py on %s:\n%s\n"
        "Fix these before the script is run or queued. The header is written before "
        "computing, not after." % (c.relative(cfg["_home"], path), "\n".join(lines)))


if __name__ == "__main__":
    sys.exit(main())
