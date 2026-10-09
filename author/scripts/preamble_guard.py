"""PreToolUse (Edit|Write|MultiEdit): the preamble changes as the home's policy says.

``author.preamble`` (docs/config.md): ``file`` (default ``author.main``), ``end`` (default
``\\begin{document}``), ``extraFiles`` (e.g. a ``macros.tex``) and ``policy``:

- ``propose`` (default): a tool edit of the preamble region (from the file's start to the
  first ``end``) or of an extra file is denied, with the hint to file the change as a
  proposal (a ticket or packet) for the human;
- ``locked``: denied the same way; the preamble is the human's alone;
- ``free``: no guard.

The edit is simulated on the file as it is on disk (``pinned_guard.after_text``); an edit
below ``end`` passes. The guard holds for every caller, the main session included: the
human releases a file by hand, one home-relative path per line in
``<home>/.claude/preamble-release.txt`` (a tool edit of that file is denied too), and
removes the line afterwards.

Silent outside an Author home and for an edit it cannot simulate. A guard bug never
blocks an edit.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _author as au  # noqa: E402
from pinned_guard import after_text  # noqa: E402

ac = au.ac

RELEASE_REL = os.path.join(".claude", "preamble-release.txt")


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def released(home):
    """The home-relative paths the human released (``/`` separators)."""
    try:
        with open(os.path.join(home, RELEASE_REL), encoding="utf-8") as fh:
            rows = [ln.strip() for ln in fh]
    except OSError:
        return set()
    out = set()
    for r in rows:
        if r and not r.startswith("#"):
            r = r.replace("\\", "/")
            out.add(os.path.normcase(r[2:] if r.startswith("./") else r))
    return out


def preamble_of(text, end):
    """The preamble region of ``text``: up to the first ``end`` (all of it without one)."""
    i = text.find(end)
    return text if i < 0 else text[:i]


def decide(event):
    """``None`` or ``("deny", reason)``."""
    path = ac.edited_path(event)
    if not path:
        return None
    if not os.path.isabs(path):
        path = os.path.join(ac.event_cwd(event), path)
    home, cfg = au.author_home(path)
    if not home:
        return None
    pre = ac.author_tex(cfg, "preamble")
    policy = pre.get("policy") or "propose"
    if policy == "free":
        return None
    full = _norm(path)
    if full == _norm(os.path.join(home, RELEASE_REL)):
        return ("deny", "preamble_guard: %s is the human's release list for the preamble; "
                        "only the human edits it, by hand." % RELEASE_REL)
    rel = os.path.relpath(full, _norm(home)).replace(os.sep, "/")
    main = str(pre.get("file") or "main.tex").replace("\\", "/")
    extras = [str(x).replace("\\", "/") for x in pre.get("extraFiles") or []]
    if os.path.normcase(rel) not in {os.path.normcase(p) for p in [main] + extras}:
        return None
    if os.path.normcase(rel) in released(home):
        return None
    if os.path.normcase(rel) == os.path.normcase(main):
        try:
            with open(path, encoding="utf-8", errors="replace", newline="") as fh:
                before = fh.read()
        except OSError:
            return None                  # a new file: nothing to protect yet
        end = str(pre.get("end") or "\\begin{document}")
        after = after_text(event, before)
        if after is None:
            return None
        if preamble_of(before, end) == preamble_of(after, end):
            return None
        what = "the preamble of %s (everything before %s)" % (rel, end)
    else:
        what = "%s, part of the preamble (author.preamble.extraFiles)" % rel
    _ns, bare = ac.agent_identity(event)
    who = bare or "the main session"
    if policy == "locked":
        hint = "This home's preamble is locked (author.preamble.policy): only the human " \
               "changes it."
    else:
        hint = "This home's preamble policy is `propose`: file the change as a proposal " \
               "for the human (a ticket or a packet with the exact lines), and work in the " \
               "body meanwhile."
    return ("deny", "preamble_guard: %s would change %s. %s The human releases a file by "
                    "hand in %s." % (who, what, hint, RELEASE_REL))


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
