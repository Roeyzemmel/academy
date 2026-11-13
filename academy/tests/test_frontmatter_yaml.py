"""Every agent and skill frontmatter value is one YAML scalar, read whole (2026-11-13).

Two agents were found mis-read by the harness, with no error anywhere:

* ``rigor-reviewer``: a single-quoted description with one apostrophe not doubled
  (``the human's``). The frontmatter did not parse, so the agent was listed as "Agent from
  expert plugin" with **all tools**: the blind, read-only reviewer had lost its tool list,
  its model and its turn limit.
* ``experimenter``: a plain description holding `` ## Conclusion``. `` #`` starts a
  comment, so the description ended there and lost its last two sentences.

The suites are standard-library only, so this is not a YAML parser: it checks the ways a
one-line scalar goes wrong. A plain scalar holding ``: `` is refused too (strict YAML
reads a mapping there), although the harness has tolerated it.
"""

import glob
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def scalar_problem(value):
    """Why YAML would not read ``value`` (the text after ``key:``) whole, or None."""
    v = value.strip()
    if not v or v[0] in "[{|>":
        return None
    if v[0] == "'":
        i, inner = 0, v[1:]
        while i < len(inner):
            if inner[i] == "'":
                if inner[i + 1:i + 2] == "'":
                    i += 2
                    continue
                rest = inner[i + 1:].strip()
                if not rest or rest.startswith("#"):
                    return None
                return ("the single-quoted text ends at an apostrophe that is not doubled: "
                        "...%s" % inner[max(0, i - 25):i + 12])
            i += 1
        return "the single-quoted text never closes"
    if v[0] == '"':
        if re.match(r'"(?:[^"\\]|\\.)*"\s*(#.*)?$', v):
            return None
        return "the double-quoted text is not closed exactly once"
    if " #" in v:
        return "a plain value holds ' #', where a comment starts: quote the value"
    if ": " in v or v.endswith(":"):
        return "a plain value holds ': ', where a mapping starts: quote the value"
    if v[0] in "&*!%@`":
        return "a plain value starts with %r: quote the value" % v[0]
    return None


def frontmatter_files():
    out = []
    for pat in ("*/agents/*.md", "*/skills/*/SKILL.md", "domains/*/skills/*/SKILL.md",
                "*/commands/*.md"):
        out += glob.glob(os.path.join(REPO, pat))
    return sorted(out)


class Scalars(unittest.TestCase):
    def test_the_checker_itself(self):
        ok = ["plain words, with commas", "'it''s quoted'", "'quoted'  # a comment",
              '"double \\" quoted"', "[a, b]", "", "a:b and c#d", "sonnet"]
        bad = ["'the human's word'", "'never closed", "its ## Conclusion", "to: someone else",
               '"two" "strings"', "ends with a colon:", "*starred"]
        self.assertEqual([], [v for v in ok if scalar_problem(v)])
        self.assertEqual([], [v for v in bad if not scalar_problem(v)])

    def test_every_agent_and_skill_frontmatter_is_read_whole(self):
        files = frontmatter_files()
        self.assertGreater(len(files), 60)
        problems = []
        for path in files:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            m = re.match(r"---\n(.*?)\n---\n", text, re.S)
            rel = os.path.relpath(path, REPO).replace(os.sep, "/")
            if not m:
                problems.append("%s: no frontmatter" % rel)
                continue
            for ln in m.group(1).splitlines():
                km = re.match(r"^([A-Za-z_-]+):(.*)$", ln)
                if not km:
                    if ln.strip() and not ln.startswith((" ", "-", "#")):
                        problems.append("%s: not a 'key: value' line: %s" % (rel, ln[:60]))
                    continue
                why = scalar_problem(km.group(2))
                if why:
                    problems.append("%s: %s: %s" % (rel, km.group(1), why))
        self.assertEqual([], problems)


if __name__ == "__main__":
    unittest.main()
