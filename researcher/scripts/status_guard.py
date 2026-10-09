"""status_guard -- PreToolUse (Edit|Write|MultiEdit): only the status keeper changes a status.

Plan sections 3.3 and 8; permissions.json ``files.registry_status_field``.

A registry record is a ``.md`` file under a record root of any home in workspace.json
that has a claim namespace (``_researcher.record_for``): ``registry.root`` and
``paths.records`` from the home's academy.json, or the legacy roots before the home is
switched over. The guard is not limited to the Researcher's own home: claim-keeper is
the only agent that changes a status in any namespace.

The edit is simulated on the file as it is on disk, and the top-level status field
(``researcher.statusField``, default ``status``) is compared before and after:

* unchanged -> silent;
* changed, or added / removed -> denied unless the caller is the status keeper
  (``registry.statusKeeper``, default ``claim-keeper``, namespace stripped) or the human
  (the main session). In a home not yet switched over (no academy.json) the legacy
  keepers ``_researcher.LEGACY_KEEPERS`` pass too -- a notebook's local
  ``status-keeper`` keeps its verify flow until its roster is retired in phase 6;
* a new record (the file does not exist yet) may be written with an unsettled status
  (open / conjectured / sketch, or the legacy "Not settled") or none; a settled status
  is denied to everyone but the keeper and the human.

Known limit: the matcher is Edit|Write|MultiEdit. A shell edit (sed, Set-Content) of a
status line is not intercepted here; claims_edit_check and the registry's check report
the drift afterwards (recorded in docs/migration-log.md, Group B).

Silent for every path that is not a registry record, and for an edit it cannot
simulate (the Edit tool then fails on its own). A hook bug never blocks an edit.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402


def _after(event, before):
    """The file's text after the tool call, or None when it cannot be simulated."""
    name = ac.tool_name(event)
    ti = ac.tool_input(event)
    if name == "Write":
        content = ti.get("content")
        return content if isinstance(content, str) else None
    if name == "Edit":
        if before is None:
            return None
        return rs.apply_edit(before, ti.get("old_string"), ti.get("new_string"),
                             bool(ti.get("replace_all")))
    if name == "MultiEdit":
        text = before
        for e in ti.get("edits") or []:
            if not isinstance(e, dict) or text is None:
                return None
            text = rs.apply_edit(text, e.get("old_string"), e.get("new_string"),
                                 bool(e.get("replace_all")))
        return text
    return None


def decide(event, ws=None):
    """``(decision, reason)``: ('deny', why) or (None, '') for silence."""
    path = ac.edited_path(event)
    rec = rs.record_for(path, ws)
    if not rec:
        return None, ""
    ns_, bare = ac.agent_identity(event)
    if bare == "" or bare in rec.get("keepers", (rec["keeper"],)):
        return None, ""
    field = rec["field"]
    before = rs.read_text(path) if os.path.isfile(path) else None
    after = _after(event, before)
    if after is None:
        return None, ""
    had, old = rs.frontmatter_field(before, field) if before is not None else (False, None)
    has, new = rs.frontmatter_field(after, field)
    if before is None:
        if not has or (new or "").strip().lower() in rs.UNSETTLED:
            return None, ""
        return "deny", ("status_guard: %s may not create %s with %s: %s. A new record "
                        "starts unsettled (open, conjectured or sketch); a settled status "
                        "is set only by %s (claims_set_status) with grounds."
                        % (bare, rec["rel"], field, new, rec["keeper"]))
    if (had, (old or "").strip()) == (has, (new or "").strip()):
        return None, ""
    return "deny", ("status_guard: only %s (or %s) changes the '%s:' line of a registry "
                    "record; %s tried to change it in %s (%s -> %s). Propose the change "
                    "with the MCP tool claims_propose_status instead, citing its grounds, "
                    "and leave the rest of the edit without the status line."
                    % (rec["keeper"], ac.human_name(), field, bare, rec["rel"],
                       old if had else "(none)",
                       new if has else "(none)"))


def main():
    event = ac.read_event()
    try:
        verdict, reason = decide(event)
    except Exception:            # a guard bug never blocks an edit
        return 0
    if verdict == "deny":
        ac.emit_permission("deny", reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
