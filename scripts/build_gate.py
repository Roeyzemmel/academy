"""SubagentStop gate: a writing agent does not finish on a broken build.

Fires only when the agent edited one of the paper's .tex files during its run (the
PostToolUse gate left .build/.dirty behind). It blocks the stop on a build error, on
a "??" in the PDF, or on a checker finding outside the recorded baseline -- never on
the draft's known open state, which would block every writing agent forever.
"""

import os
import re
import subprocess
import sys

import _common as c

WRITERS = {
    "math-writer", "copy-editor", "latex-fixer", "note-sweeper",
    "figure-maker", "source-checker",
}
BUILD_TIMEOUT = 280
ERROR_LINE = re.compile(r"^(?:!|[^ ]+\.tex:\d+:)")
UNRESOLVED = re.compile(r"\?\?\s+([1-9]\d*)")


def build(root):
    try:
        proc = subprocess.run(
            ["latexmk", "-pdf", "main.tex"], cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=BUILD_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None, "latexmk timed out"
    except OSError as exc:
        return None, "latexmk could not run: %s" % exc
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def main():
    event = c.read_event()
    root = c.project_root(event)
    if not c.is_paper_repo(root):
        return 0
    if event.get("stop_hook_active"):
        return 0
    if event.get("agent_type") not in WRITERS:
        return 0
    if not c.gate_config(root).get("build", True):
        return 0
    if not os.path.isfile(os.path.join(root, c.DIRTY)):
        return 0

    code, output = build(root)
    if code is None:                      # no latexmk here: not this gate's problem
        c.clear_dirty(root)
        return 0

    problems = []
    if code != 0:
        errors = [ln for ln in output.splitlines() if ERROR_LINE.match(ln)]
        problems.append("latexmk exited %d.\n%s"
                        % (code, "\n".join(errors[:20]) or output[-1200:]))

    chk_code, chk_output = c.run_checker(root)
    if chk_code is not None:
        new = c.new_findings(root, chk_output)
        if new:
            problems.append("%d checker finding(s) outside the baseline:\n%s"
                            % (len(new), "\n".join(sorted(new.values()))))
        unresolved = UNRESOLVED.search(chk_output)
        if unresolved:
            problems.append("the PDF contains %s unresolved cross-reference(s) ('??')."
                            % unresolved.group(1))

    c.clear_dirty(root)
    if not problems:
        return 0

    sys.stderr.write(
        "You edited the paper's .tex in this run and left it not clean.\n\n%s\n\n"
        "Fix what your edits broke before finishing, then stop again. Findings already "
        "in .claude/paper-gate-baseline.txt are not yours and are not reported here.\n"
        % "\n\n".join(problems)
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
