"""PreToolUse (Edit|Write|MultiEdit): a machine note is written no longer than
``author.notes.maxLines`` (#110 point 5: the cap enforced at write time, not only by the
checker's R7 after a build).

The edit is simulated on the file as it is on disk (``pinned_guard.after_text``); the
machine notes before and after are compared by signature (``machine_notes.py``). Only the
notes the edit **adds** are judged, so a writer never answers for a long note it did not
write:

- a note passing through the edit unchanged is not judged, and neither is a note whose
  signature already occurs anywhere in the home's ``paths.tex`` before the edit (a
  statement moved or copied with its note: insert the new copy before deleting the old);
- a new note of at most ``maxLines`` margin lines passes;
- a new note over the cap passes only when the edit removes an over-cap note at least as
  long (narrowing a long note is progress); otherwise the edit is denied, with the way
  out: keep the margin note to a pointer (the ticket id and a few words) and put the long
  text in the ticket thread it belongs to (or the home's margin-notes file).

Margin lines are estimated as plain characters over ``author.notes.lineChars`` (default
``machine_notes.DEFAULT_LINE_CHARS``). The guard is **opt-in**: it acts only when
``author.notes.enforce`` is ``true``. Scope: the home's ``paths.tex`` files of an Author home, every caller.
Silent outside an Author home and for an edit it cannot simulate; a guard bug never
blocks an edit (the dispatcher skips a guard that raises).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _author as au  # noqa: E402
import machine_notes as mn  # noqa: E402
from pinned_guard import after_text  # noqa: E402

ac = au.ac


def _sized(text, macros, line_chars):
    """``{signature: [lines, ...]}`` of the closed notes of ``text``."""
    out = {}
    for n in mn.scan(text or "", macros):
        if n.get("body") is None:
            continue
        out.setdefault(mn.signature(n), []).append(mn.estimate_lines(n["body"], line_chars))
    return out


def existing_signatures(home, cfg, macros, path, before):
    """The signatures of every machine note in the home's tex files as they are before the
    edit (the edited file as ``before``): a note copied or moved from anywhere in the paper
    is not a new note (review of 38e8803: statements move with their notes)."""
    import glob
    pats = ((cfg or {}).get("paths") or {}).get("tex") or ["main.tex", "sections/*.tex"]
    if isinstance(pats, str):
        pats = [pats]
    me = os.path.normcase(os.path.abspath(path))
    sigs = set(_sized(before, macros, 1))
    for p in pats:
        for f in glob.glob(os.path.join(home, *str(p).replace("\\", "/").split("/"))):
            if os.path.normcase(os.path.abspath(f)) == me or not os.path.isfile(f):
                continue
            try:
                with open(f, encoding="utf-8", errors="replace", newline="") as fh:
                    sigs.update(_sized(fh.read(), macros, 1))
            except OSError:
                continue
    return sigs


def added_and_removed(before, after, macros, line_chars, exempt=None):
    """``(added, removed)``: the margin-line sizes of the notes the edit adds and removes
    (a multiset difference by signature). ``exempt`` (a function returning a set of
    signatures, called only when an over-cap note is added) names notes that are not new:
    an added note whose signature is in it is not counted."""
    b, a = _sized(before, macros, line_chars), _sized(after, macros, line_chars)
    added, removed = [], []
    for sig in set(a) | set(b):
        na, nb = a.get(sig, []), b.get(sig, [])
        if len(na) > len(nb):
            added += [(sig, n) for n in na[len(nb):]]
        elif len(nb) > len(na):
            removed += nb[len(na):]
    if exempt is not None and added:
        known = exempt()
        added = [(sig, n) for sig, n in added if sig not in known]
    return sorted((n for _s, n in added), reverse=True), sorted(removed, reverse=True)


def too_long(added, removed, max_lines):
    """The added over-cap sizes that no removed over-cap note at least as long pays for."""
    pool = [r for r in removed if r > max_lines]
    left = []
    for size in (s for s in added if s > max_lines):
        k = next((i for i, r in enumerate(pool) if r >= size), None)
        if k is None:
            left.append(size)
        else:
            pool.pop(k)
    return left


def decide(event):
    """``None`` or ``("deny", reason)``."""
    path = ac.edited_path(event)
    if not path or ac.tool_name(event) not in ("Edit", "Write", "MultiEdit"):
        return None
    if not os.path.isabs(path):
        path = os.path.join(ac.event_cwd(event), path)
    home, cfg = au.author_home(path)
    if not home:
        return None
    notes = ac.author_tex(cfg, "notes")
    if notes.get("enforce") is not True:            # opt-in (review of 38e8803)
        return None
    if not ac.path_in_role(path, dict(cfg, _home=home), "tex"):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            before = fh.read()
    except OSError:
        before = ""                       # a new file: every note in it is new
    after = after_text(event, before)
    if after is None:
        return None
    max_lines, line_chars = mn.note_limits(cfg)
    macros = mn.machine_macros(cfg)
    added, removed = added_and_removed(before, after, macros, line_chars, exempt=lambda: (
        existing_signatures(home, cfg, macros, path, before)))
    over = too_long(added, removed, max_lines)
    if not over:
        return None
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(home)).replace(os.sep, "/")
    _ns, bare = ac.agent_identity(event)
    drafts = str(((cfg.get("paths") or {}).get("drafts")) or "Drafts").rstrip("/")
    return ("deny", (
        "note_length_guard: %s would write %d machine note(s) in %s longer than "
        "author.notes.maxLines (%d margin lines; this one is about %s, at %d characters a "
        "line, author.notes.lineChars). Keep the margin note to a pointer: the ticket id "
        "and a few words (e.g. \\Claude{T-NNNN: unverified step, see the thread}); put the "
        "long text in the thread of the ticket it belongs to (or %s/margin_notes.md), then "
        "write the edit again. Narrowing an existing long note passes, and so does a note "
        "moved or copied from elsewhere in the paper: insert the new copy before deleting "
        "the old one." % (
            bare or "the main session", len(over), rel, max_lines,
            ", ".join(str(s) for s in over), line_chars, drafts)))


def main():
    try:
        verdict = decide(ac.read_event())
    except Exception:            # a guard bug never blocks an edit
        return 0
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
