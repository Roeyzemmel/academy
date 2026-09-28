"""PostToolUse hook on Edit|Write|MultiEdit: lint a board file after a direct edit.

Only files under the board (workspace.json ``board``) are looked at:
  * a ticket ``<board>/<instance|human>/T-NNNN-*.md`` is checked against the schema
    (``validate_ticket``), its folder and file name, and its section layout;
  * a packet ``<board>/packets/<instance>/P-NNNN-*.md`` is checked with
    ``validate_packet``;
  * a ticket is also compared with its version at the board's git HEAD, and every
    change the caller was not entitled to make is reported (docs/protocol.md
    section 4, "Field ownership"). The human may change any field, but the thread
    stays append-only for everyone.
Agents are meant to change the board only through the academy MCP tools
(permissions.json ``files.board``), so a direct agent edit is itself reported.
Problems are fed back to the model as a PostToolUse block; otherwise silent.
"""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

RE_TICKET_FILE = re.compile(r"^(T-\d{4,})-.*\.md$")
RE_PACKET_FILE = re.compile(r"^(P-\d{4,})-.*\.md$")
RESERVED = ("packets", "deep-dives", ".ids", ".git")
BODY_SECTIONS = ("## Ask", "## Result", ac.THREAD_HEADING)
SECTION_OWNER = {"## Ask": "sender", "## Result": "receiver"}
#: a status change into these (from any state) needs a reason line in the same write
NEEDS_REASON = ("rejected", "cancelled")


def classify(board, path):
    """('ticket'|'packet'|None, path relative to the board with '/')."""
    rel = ac._rel_to(board, path)
    if rel is None or rel == "":
        return None, rel
    parts = rel.split("/")
    name = parts[-1]
    if len(parts) == 2 and parts[0] not in RESERVED and RE_TICKET_FILE.match(name):
        return "ticket", rel
    if len(parts) == 3 and parts[0] == "packets" and RE_PACKET_FILE.match(name):
        return "packet", rel
    return None, rel


def git_head_text(board, rel):
    """The file's text at the board's HEAD, or None (new file, no repo, no git)."""
    try:
        res = subprocess.run(["git", "-C", str(board), "show", "HEAD:" + rel],
                             capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.decode("utf-8", "replace")


def _section_text(body, heading):
    return "\n".join(ac._sections(body).get(heading, [])).strip()


def lint_ticket(meta, body, rel):
    """Schema and layout problems of one ticket file."""
    probs = list(ac.validate_ticket(meta, body))
    folder, name = rel.split("/")[0], rel.split("/")[-1]
    m = RE_TICKET_FILE.match(name)
    if m and meta.get("id") and meta["id"] != m.group(1):
        probs.append("id %s does not match the file name %s" % (meta["id"], name))
    if meta.get("to") and meta["to"] != folder:
        probs.append("to is %s but the ticket lives in %s/ (a ticket lives in the folder "
                     "of its 'to')" % (meta["to"], folder))
    heads = [ln.rstrip() for ln in body.split("\n") if ln.startswith("## ")]
    if heads and heads != list(BODY_SECTIONS):
        probs.append("the body's sections must be exactly %s, in that order (found %s)"
                     % (", ".join(BODY_SECTIONS), ", ".join(heads)))
    return probs


def ownership_problems(old_meta, old_body, new_meta, new_body, instance, human):
    """Changes from HEAD to the working file that ``instance`` may not make."""
    probs = []
    if not ac.thread_is_append_only(old_body, new_body):
        probs.append("## Thread is append-only: an existing entry was edited, moved or "
                     "deleted")
    if human:
        return probs
    party = ac.parties(old_meta, instance)
    allowed = ac.editable_fields(party)
    for key in list(ac.TICKET_KEY_ORDER) + [k for k in new_meta if k not in
                                            ac.TICKET_KEY_ORDER]:
        if key == "updated" or old_meta.get(key) == new_meta.get(key):
            continue
        if key == "status":
            ok, why = ac.can_transition(old_meta.get("status"), new_meta.get("status"),
                                        party)
            if not ok:
                probs.append("status %s -> %s: %s" % (old_meta.get("status"),
                                                      new_meta.get("status"), why))
                continue
            old_n = len(ac.thread_lines(old_body))
            new_n = len(ac.thread_lines(new_body))
            returned = (old_meta.get("status"), new_meta.get("status")) == \
                ("delivered", "in-progress")
            if (new_meta.get("status") in NEEDS_REASON or returned) and new_n <= old_n:
                probs.append("status -> %s needs a reason line in ## Thread in the same "
                             "write" % new_meta.get("status"))
        elif key in ac.TICKET_FIELDS["system"]:
            probs.append("%s is written by the server only" % key)
        elif key in ac.TICKET_FIELDS["human_only"]:
            probs.append("%s may be changed only by the human" % key)
        elif key not in allowed:
            owner = "sender" if key in ac.TICKET_FIELDS["sender"] else "receiver"
            probs.append("%s is owned by the %s; %s is %s" % (
                key, owner, instance or "an agent outside any home",
                " and ".join(sorted(party)) or "neither sender nor receiver"))
    for heading, owner in SECTION_OWNER.items():
        if owner not in party and \
                _section_text(old_body, heading) != _section_text(new_body, heading):
            probs.append("%s is owned by the %s" % (heading, owner))
    return probs


def caller_instance(event):
    """The instance of the home the session runs in, or None."""
    home = ac.find_home(ac.event_cwd(event))
    if not home:
        return None
    try:
        return ac.instance_for_home(ac.load_workspace(), home)
    except ac.AcademyError:
        return None


def check(event, workspace=None):
    """List of problems for one PostToolUse event (empty: say nothing)."""
    path = ac.edited_path(event)
    if not path:
        return []
    if not os.path.isabs(path):
        path = os.path.join(ac.event_cwd(event), path)
    try:
        ws = workspace or ac.load_workspace()
    except ac.AcademyError:
        return []
    board = ws["board"]
    kind, rel = classify(board, path)
    if kind is None:
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return []
    try:
        meta, body = ac.read_frontmatter(text)
    except ac.FrontmatterError as exc:
        return ["frontmatter: %s" % exc]
    if kind == "packet":
        return ac.validate_packet(meta, body)
    probs = lint_ticket(meta, body, rel)
    human = ac.is_human(event)
    ns, bare = ac.agent_identity(event)
    if not human:
        probs.insert(0, "agents change the board only through the academy MCP tools "
                        "(tickets_update); %s edited %s directly"
                     % ("%s:%s" % (ns, bare) if ns else bare, rel))
    old_text = git_head_text(board, rel)
    if old_text is None:
        return probs
    try:
        old_meta, old_body = ac.read_frontmatter(old_text)
    except ac.FrontmatterError:
        return probs
    instance = None if human else caller_instance(event)
    probs += ownership_problems(old_meta, old_body, meta, body, instance, human)
    return probs


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    event = ac.read_event()
    probs = check(event)
    if probs:
        path = ac.edited_path(event) or "the board file"
        ac.emit_block("academy: %s has %d problem(s):\n- %s\nFix them, or revert the "
                      "edit (docs/protocol.md sections 3-4)."
                      % (path, len(probs), "\n- ".join(probs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
