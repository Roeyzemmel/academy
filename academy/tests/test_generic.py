"""The marketplace is generic: no project, person or machine names in the plugin trees.

Every text file under the plugin trees (``academy/``, ``author/``, ``expert/``,
``researcher/``, ``scientist/``, ``domains/``), the docs and the root README is searched
for the names of one particular workspace (its human, its machines, its instances and
its repositories). A project's names belong in its own workspace and homes; prompts say
"the human" and read the name from workspace.json, examples use neutral names (``Ada``,
``remote-a``, ``author@main``, ``nb:``).

The allowlist is short and explicit: history files (logs, changelogs, dated plans and
the legacy scripts kept verbatim), the ``author`` field of the plugin manifests, the
remote runner's header comment (``fsq.sh`` is pinned byte for byte to its legacy copy),
and a domain pack's citation of a paper by its URL. Anything else is a finding.
"""

import fnmatch
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: the trees searched, relative to the marketplace root
TREES = ("academy", "author", "expert", "researcher", "scientist", "domains", "docs",
         ".claude-plugin")
ROOT_FILES = ("README.md",)

NAMES = re.compile(r"Roey|Roeyzemmel|roeyzemmel|lingo|TAU VPN|tau\.ac\.il|author@bi|expert@ts"
                   r"|researcher@slope1|scientist@ts|BilliardIllumination|FlatSurfLab|Slope1")

#: whole files that are history, kept as written
HISTORY = (
    "docs/migration-log.md",
    "docs/migration-campaign-mode.md",
    "docs/workflow-triage-*.md",
    "docs/superpowers/*",
    "domains/*/CHANGELOG.md",
    "scientist/scripts/legacy/*",
    "academy/tests/test_generic.py",            # this file names what it looks for
)

#: (file glob, line regex): single lines allowed in an otherwise generic file
LINES = (
    ("*.claude-plugin/plugin.json", r'^\s*"name": "Roey Zemmel"\s*$'),       # author field
    (".claude-plugin/marketplace.json", r'^\s*"name": "Roey Zemmel"\s*$'),  # owner field
    ("scientist/scripts/fsq.sh", r"^# fsq -- the FlatSurfLab job runner"),   # = legacy copy
    ("domains/*/theorems/*.md", r"https?://www\.math\.tau\.ac\.il/\S+\.pdf"),  # a citation
)

SKIP_DIRS = {"__pycache__", ".git"}
TEXT_EXT = {".md", ".py", ".json", ".sh", ".ps1", ".txt", ".yml", ".yaml", ".toml", ".tex",
            ".html", ".css", ".js", ".cfg", ".ini", ""}


def _files():
    for name in ROOT_FILES:
        yield name
    for tree in TREES:
        for dirpath, dirnames, filenames in os.walk(os.path.join(REPO, tree)):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                    yield os.path.relpath(os.path.join(dirpath, fn), REPO).replace(os.sep, "/")


def _match(rel, pattern):
    return fnmatch.fnmatchcase(rel, pattern)


def findings():
    """``["path:line: text", ...]`` for every name outside the allowlist."""
    out = []
    for rel in _files():
        if NAMES.search(rel):
            out.append("%s: the path names a project" % rel)
        if any(_match(rel, p) for p in HISTORY):
            continue
        try:
            with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        allowed = [re.compile(rx) for glob, rx in LINES if _match(rel, glob)]
        for n, line in enumerate(lines, 1):
            if NAMES.search(line) and not any(rx.search(line) for rx in allowed):
                out.append("%s:%d: %s" % (rel, n, line.strip()[:120]))
    return out


class MarketplaceIsGeneric(unittest.TestCase):
    def test_no_project_names_outside_the_allowlist(self):
        found = findings()
        self.assertEqual(found, [], "project names in the plugin trees:\n" + "\n".join(found))

    def test_the_allowlist_is_not_stale(self):
        """Every line allowance still matches something, so the list stays small."""
        for glob, rx in LINES:
            pat = re.compile(rx)
            hits = 0
            for rel in _files():
                if not _match(rel, glob):
                    continue
                with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                    hits += sum(1 for line in fh.read().splitlines() if pat.search(line))
            with self.subTest(glob=glob):
                self.assertGreater(hits, 0, "allowance %r on %s matches nothing" % (rx, glob))

    def test_the_guard_catches_a_name(self):
        self.assertTrue(NAMES.search("the job runs on lingo"))
        self.assertTrue(NAMES.search("ask Roey"))
        self.assertFalse(NAMES.search("ask the human (Ada) about remote-a"))


if __name__ == "__main__":
    unittest.main()
