"""PostToolUse (Edit|Write|MultiEdit): after an edit to one of an Author home's .tex
files, run the checker and hand its findings back as context.

Scope: the edited path must lie in an Author home (its ``.claude/academy.json`` has
``role: author``) and match that home's ``paths.tex``. Anything else is a silent
no-op. An edit to the home's ``paths.bib`` only marks the build dirty (a bib change
is owed a build too; build_gate counts librarian as a writer for that reason).

Advisory: it never blocks an edit. It leaves ``<build.dir>/.dirty`` so the
SubagentStop gate (build_gate) knows a build is owed.
"""

import sys

import _author as au

ac = au.ac
MAX_LINES = 40


def main():
    event = ac.read_event()
    path = ac.edited_path(event)
    home, cfg = au.author_home(path)
    if not home:
        return 0
    if ac.path_in_role(path, cfg, "bib"):
        au.mark_dirty(home, cfg, "bib edited")
        return 0
    if not ac.path_in_role(path, cfg, "tex"):
        return 0

    au.mark_dirty(home, cfg)
    code, output = au.run_checker(home, cfg)
    if code is None:
        return 0
    keep = [ln for ln in output.splitlines()
            if ln.strip() and not ln.startswith("Registry written")]
    if len(keep) > MAX_LINES:
        dropped = len(keep) - MAX_LINES
        keep = keep[:MAX_LINES] + ["... (%d more lines; run the checker for all)" % dropped]
    rel = ac._rel_to(home, path) or path
    verdict = "clean" if code == 0 else "violations"
    ac.emit_context("PostToolUse", (
        "check_paper.py after your edit to %s: %s.\n%s\n"
        "Fix what your edit caused; pre-existing findings are not yours to fix here."
        % (rel, verdict, "\n".join(keep))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
