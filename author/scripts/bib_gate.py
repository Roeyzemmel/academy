"""PreToolUse (Edit|Write|MultiEdit): only the Expert's librarian edits the bibliography.

An entry filled in from memory is the easiest way to get a fabricated reference into
a paper, so the bibliography has one door: ``expert:librarian`` (permissions.json
``files.bibliography``; the list is ``author.bibWriters`` in academy.json, default
``["librarian"]``).

Scope: the edited path must be the ``paths.bib`` of an Author home; anything else is
a silent no-op. Identity is ``agent_identity`` (namespace-stripped): the bare name
must be a bib writer, and a namespaced caller must come from the ``expert`` plugin
(so an ``author:``-shipped agent of the same name could not pass). The main session
is denied too: the bib is written from a fetched record, never by hand from Claude.
"""

import sys

import _author as au

ac = au.ac


def allowed(event, config):
    ns, bare = ac.agent_identity(event)
    writers = au.author_settings(config).get("bibWriters") or list(au.DEFAULT_BIB_WRITERS)
    if not bare or bare not in [w.lower() for w in writers]:
        return False
    return ns in ("", au.BIB_WRITER_NAMESPACE)


def main():
    event = ac.read_event()
    path = ac.edited_path(event)
    home, cfg = au.author_home(path)
    if not home or not ac.path_in_role(path, cfg, "bib"):
        return 0
    if allowed(event, cfg):
        return 0
    ns, bare = ac.agent_identity(event)
    who = ("%s:%s" % (ns, bare) if ns else bare) if bare else "the main session (no agent)"
    ac.emit_permission("deny", (
        "The bibliography of %s is edited only by the Expert's librarian, which fetches "
        "the record (Crossref / arXiv / MathSciNet) and writes a card with the verbatim "
        "quote. This edit came from %s. File a `cite` ticket to the Expert instance "
        "(/expert:cite, or tickets_create kind=cite) instead of writing the entry here; "
        "do not route around this gate." % (cfg.get("instance", "this paper"), who)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
