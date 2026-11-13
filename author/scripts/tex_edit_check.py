"""PostToolUse (Edit|Write|MultiEdit): after an edit to one of an Author home's .tex
files, run the checker and hand its findings back as context.

Scope: the edited path must lie in an Author home (its ``.claude/academy.json`` has
``role: author``) and match that home's ``paths.tex``. Anything else is a silent
no-op. An edit to the home's ``paths.bib`` only marks the build dirty (a bib change
is owed a build too; build_gate counts librarian as a writer for that reason).

Advisory: it never blocks an edit. It leaves ``<build.dir>/.dirty`` so the
SubagentStop gate (build_gate) knows a build is owed.

**Only what changed is handed back** (2026-11-13). The first check in a build directory
gives the checker's findings in full (at most ``MAX_LINES``). Every later one gives the
counts, the findings that are new since the previous check and how many went away, and
counts the rest: a writer making twenty edits used to be sent the same forty lines of
other people's findings twenty times. Findings are compared without their line numbers,
which move with every edit (``_author.findings``). The previous check's findings are kept
in ``<build.dir>/.last-check.json``; without it, or when it cannot be read, the check is
a first one.
"""

import json
import os
import sys

import _author as au

ac = au.ac
MAX_LINES = 40
STATE = ".last-check.json"


def norm(line):
    """What makes two finding lines the same finding: ``file|label|rule`` for a finding
    (no line number), else the line's own text."""
    hit = au.findings(line)
    return next(iter(hit)) if hit else " ".join(line.split())


def load_seen(home, cfg):
    try:
        with open(os.path.join(au.build_dir(home, cfg), STATE), encoding="utf-8") as fh:
            seen = json.load(fh)
        return set(seen) if isinstance(seen, list) else None
    except (OSError, ValueError):
        return None


def save_seen(home, cfg, seen):
    try:
        d = au.build_dir(home, cfg)
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, STATE + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(sorted(seen), fh, ensure_ascii=False)
        os.replace(tmp, os.path.join(d, STATE))
    except OSError:
        pass


def changed_only(keep, seen):
    """``(lines, new, gone, same)``: the section and count lines (not indented) as they
    are, of the indented ones only those not in ``seen``; how many are new, how many of
    ``seen`` are gone, how many are as before."""
    detail = [ln for ln in keep if ln[:1].isspace()]
    now = {norm(ln) for ln in detail}
    out, new = [], 0
    for ln in keep:
        if not ln[:1].isspace():
            out.append(ln)
        elif norm(ln) not in seen:
            out.append(ln)
            new += 1
    return out, new, len(seen - now), len(now & seen)


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
    seen = load_seen(home, cfg)
    save_seen(home, cfg, {norm(ln) for ln in keep if ln[:1].isspace()})
    rel = ac._rel_to(home, path) or path
    verdict = "clean" if code == 0 else "violations"
    if seen is None:
        tail = "Fix what your edit caused; pre-existing findings are not yours to fix here."
    else:
        keep, new, gone, same = changed_only(keep, seen)
        if not new and not gone:
            ac.emit_context("PostToolUse", (
                "check_paper.py after your edit to %s: %s, nothing new (%d finding line(s) "
                "as at the previous check)." % (rel, verdict, same)))
            return 0
        tail = ("Since the previous check: %d new (listed above), %d gone, %d as before (not "
                "listed; run the checker for all). Fix what your edit caused."
                % (new, gone, same))
    if len(keep) > MAX_LINES:
        dropped = len(keep) - MAX_LINES
        keep = keep[:MAX_LINES] + ["... (%d more lines; run the checker for all)" % dropped]
    ac.emit_context("PostToolUse", (
        "check_paper.py after your edit to %s: %s.\n%s\n%s"
        % (rel, verdict, "\n".join(keep), tail)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
