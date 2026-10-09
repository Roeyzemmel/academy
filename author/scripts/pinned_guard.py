"""PreToolUse (Edit|Write|MultiEdit): nobody edits a pinned statement's environment.

roster-rules.md, "Role cut", rule 2. A statement is pinned when a CONFIRMED review run
recorded its hash in the library (``pinned.py``). In an Author home, an edit of a tex file
(``paths.tex``, default ``main.tex`` and ``sections/*.tex``) is simulated on the file as it
is on disk; when the text of a pinned statement's environment (``\\begin`` to ``\\end``
around its ``\\label``) changes or disappears, the edit is denied. The proof body, and
everything outside the environment, stays free.

The guard holds for every caller, the main session included: a pinned statement changes
only when the human releases it by hand, in ``<home>/.claude/pinned-release.txt``. A tool
edit of that file is denied too. A repair of the statement is the Researcher's: file a
``research`` ticket (``final_to: researcher``) with the finding and its falsifier.

Silent outside an Author home and for an edit it cannot simulate. A guard bug never
blocks an edit.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _author as au  # noqa: E402
import pinned as pn  # noqa: E402

ac = au.ac


def apply_edit(text, old, new, replace_all=False):
    if text is None or not isinstance(old, str) or not isinstance(new, str) or not old:
        return None
    if old not in text:
        return None
    return text.replace(old, new) if replace_all else text.replace(old, new, 1)


def after_text(event, before):
    """The file's text after the tool call, or None when it cannot be simulated."""
    name = ac.tool_name(event)
    ti = ac.tool_input(event)
    if name == "Write":
        c = ti.get("content")
        return c if isinstance(c, str) else None
    if name == "Edit":
        return apply_edit(before, ti.get("old_string"), ti.get("new_string"),
                          bool(ti.get("replace_all")))
    if name == "MultiEdit":
        text = before
        for e in ti.get("edits") or []:
            if not isinstance(e, dict):
                return None
            text = apply_edit(text, e.get("old_string"), e.get("new_string"),
                              bool(e.get("replace_all")))
            if text is None:
                return None
        return text
    return None


def _is_tex(path, home, cfg):
    if ac.path_in_role(path, dict(cfg or {}, _home=home), "tex"):
        return True
    return path.lower().endswith(".tex")


def decide(event, ws=None, library=None):
    """``None`` or ``("deny", reason)``."""
    path = ac.edited_path(event)
    if not path:
        return None
    if not os.path.isabs(path):
        path = os.path.join(ac.event_cwd(event), path)
    home, cfg = au.author_home(path)
    if not home:
        return None
    full = os.path.normcase(os.path.abspath(path))
    if full == os.path.normcase(os.path.abspath(os.path.join(home, pn.RELEASE_REL))):
        return ("deny", "pinned_guard: %s is the human's release list of pinned statements; "
                        "only the human edits it, by hand." % pn.RELEASE_REL)
    if not _is_tex(path, home, cfg):
        return None
    pins = pn.enforced(home, cfg, ws, library)
    if not pins:
        return None
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            before = fh.read()
    except OSError:
        return None                      # a new file holds no pinned statement yet
    after = after_text(event, before)
    if after is None:
        return None
    hit = pn.changed(before, after, sorted(pins), pn.statement_envs(cfg))
    if not hit:
        return None
    ns_, bare = ac.agent_identity(event)
    rows = ["%s (%s, pass %s)" % (lab, pins[lab]["level"], pins[lab]["pass"]) for lab in hit]
    return ("deny", "pinned_guard: %s would change the statement of %s, pinned by a "
                    "CONFIRMED review (its hash is recorded in the library; editing it voids "
                    "the verdict). Leave the statement environment byte for byte; the proof "
                    "body is free. A change of hypothesis, wording or formulation is the "
                    "Researcher's: file a `research` ticket (final_to: researcher) with the "
                    "finding; wording waits for the human's batch. Only the human releases a "
                    "pin (%s). Pins: py <author plugin>/scripts/pinned.py"
                    % (bare or "the main session", "; ".join(rows), pn.RELEASE_REL))


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
