"""PostToolUse hook: warn when the library drifts out of step. Warns only; never blocks.

Scoped to the Expert homes of workspace.json (the library homes); silent for every
path outside them.

* **Edit/Write/MultiEdit** of
  - a card (``cards/<key>/<name>.md``, not ``_*.md``): validates it with
    ``cards.validate_card`` -- the schema, and the quote against the cached text
    with the MCP server's normaliser;
  - ``index.md`` or a cached file (``<key>.meta``/``.txt``/...): reports every cached
    key with no index row (``library_index.missing``).
* **Bash/PowerShell** run in a library home, or naming one in the command: reports
  cached keys with no index row whose files changed in the last 15 minutes -- a
  freshly fetched paper -- and nothing about the older gaps, which ``/expert:status``
  lists.

Findings go back to the model as additional context.
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
import cards as cardlib  # noqa: E402
import library_index as li  # noqa: E402

FRESH_SECONDS = 15 * 60
CACHE_EXT = (".meta", ".txt", ".pdf")


def library_homes(workspace):
    return [os.path.abspath(workspace["instances"][n]["home"])
            for n in ex.expert_instances(workspace)
            if os.path.isdir(workspace["instances"][n]["home"])]


def home_of(path, homes):
    for h in homes:
        if ex.is_under(path, h):
            return h
    return None


def _gap_text(gaps, home):
    return ("library: %d cached key(s) in %s have no index.md row: %s. The librarian adds "
            "the row (/expert:library-index)." % (
                len(gaps), home.replace("\\", "/"),
                ", ".join("%s (%s)" % (k, ", ".join(v)) for k, v in sorted(gaps.items()))))


def check_file(path, home):
    msgs = []
    cfg = ex.expert_config(home)
    rel = ac._rel_to(home, path) or ""
    parts = rel.split("/")
    cards_dir = ((cfg or {}).get("paths") or {}).get("cards") or "cards"
    if len(parts) == 3 and parts[0] == cards_dir and parts[2].endswith(".md") \
            and not parts[2].startswith("_"):
        errs, warns, _q = cardlib.validate_path(path, home)
        for e in errs:
            msgs.append("card %s: error: %s" % (rel, e))
        for w in warns:
            msgs.append("card %s: %s" % (rel, w))
    elif len(parts) == 1 and (rel.lower() == "index.md" or
                              os.path.splitext(rel)[1].lower() in CACHE_EXT):
        gaps = li.missing(home, cfg)["cached_without_index_row"]
        if gaps:
            msgs.append(_gap_text(gaps, home))
    return msgs


def fresh_gaps(home, now=None):
    now = now or time.time()
    gaps = li.missing(home, ex.expert_config(home))["cached_without_index_row"]
    out = {}
    for key, kinds in gaps.items():
        for kind in kinds:
            p = os.path.join(home, key + (kind if kind != ".src/" else ".src"))
            try:
                if now - os.path.getmtime(p) <= FRESH_SECONDS:
                    out[key] = kinds
                    break
            except OSError:
                continue
    return out


def mentions(command, home):
    c = command.replace("\\", "/").lower()
    return home.replace("\\", "/").lower().rstrip("/") in c


def main():
    event = ac.read_event()
    ws = ex.load_workspace_or_none()
    if not ws:
        return 0
    homes = library_homes(ws)
    if not homes:
        return 0
    tool = ac.tool_name(event)
    msgs = []
    try:
        if tool in ("Bash", "PowerShell"):
            cmd = ac.shell_command(event)
            cwd = ac.event_cwd(event)
            for h in homes:
                if ex.is_under(cwd, h) or mentions(cmd, h):
                    gaps = fresh_gaps(h)
                    if gaps:
                        msgs.append(_gap_text(gaps, h))
        else:
            path = ac.edited_path(event)
            if not path:
                return 0
            if not os.path.isabs(path):
                path = os.path.join(ac.event_cwd(event), path)
            h = home_of(path, homes)
            if not h:
                return 0
            msgs = check_file(path, h)
    except Exception as exc:  # a warn-only hook never fails the tool call
        sys.stderr.write("library_edit_check: %s\n" % exc)
        return 0
    if not msgs:
        return 0
    return ac.emit_context("PostToolUse", "\n".join(msgs))


if __name__ == "__main__":
    sys.exit(main())
