"""PostToolUse gate: after an edit to one of the paper's .tex files, run the
project's checker and hand its findings back as context.

Advisory only -- it never blocks an edit. It also marks the build dirty so the
SubagentStop gate knows a build is owed.
"""

import sys

import _common as c

MAX_LINES = 40


def main():
    event = c.read_event()
    root = c.project_root(event)
    if not c.is_paper_repo(root):
        return 0
    path = c.edited_path(event)
    if not c.is_paper_tex(root, path):
        return 0

    c.mark_dirty(root)
    code, output = c.run_checker(root)
    if code is None:
        return 0

    keep = [ln for ln in output.splitlines()
            if ln.strip() and not ln.startswith("Registry written")]
    if len(keep) > MAX_LINES:
        dropped = len(keep) - MAX_LINES
        keep = keep[:MAX_LINES] + ["... (%d more lines; run the checker for all)" % dropped]

    verdict = "clean" if code == 0 else "violations"
    context = (
        "check_paper.py after your edit to %s: %s.\n%s\n"
        "Fix what your edit caused; pre-existing findings are not yours to fix here."
        % (c.relative(root, path), verdict, "\n".join(keep))
    )
    c.emit("PostToolUse", {"additionalContext": context})
    return 0


if __name__ == "__main__":
    sys.exit(main())
