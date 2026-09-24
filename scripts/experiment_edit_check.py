"""PostToolUse gate: after writing or editing an experiment script, run the
mechanical checker on that one file and hand its findings back as context.

Advisory only -- the edit has already happened and this never undoes it. Its job
is to catch the header contract slipping (an unfilled placeholder, a Result line
that reads as a theorem, a missing save_result) while the script is still being
written, instead of at commit time or, worse, after a queue run.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _common as c  # noqa: E402

MAX_LINES = 20


def main():
    event = c.read_event()
    root = c.project_root(event)
    if not c.is_flatsurflab(root):
        return 0
    path = c.edited_path(event)
    if not c.is_experiment(root, path):
        return 0
    if not os.path.isfile(path):
        return 0

    code, output = c.run_checker(root, [path])
    if code in (None, 0):
        return 0

    lines = [ln for ln in output.splitlines() if ln.strip()]
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + ["... (%d more; run the checker for all)"
                                     % (len(lines) - MAX_LINES)]
    return c.speak(
        "check_experiments.py on %s:\n%s\n"
        "Fix these before the script is run or queued. The header is written "
        "before computing, not after." % (c.relative(root, path), "\n".join(lines)))


if __name__ == "__main__":
    sys.exit(main())
