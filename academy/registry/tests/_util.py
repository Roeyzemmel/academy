"""Shared fixtures for the registry engine's tests: temp homes and a temp workspace."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[1]                      # academy/academy
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import registry  # noqa: E402
from registry.core import federation  # noqa: E402

LAB_GOOD = """---
id: lab:foo
title: a claim
status: supported
where: experiments/x.py
bears_on:
  - paper:prop:foo
evidence:
  - experiment | results/x.json | not audited | 0 counterexamples below 10
history:
  - 2026-09-24 | supported | ran
  - 2026-09-20 | open | created
open:
  - no audit
---
Body.
"""

S1_Q = """---
id: CEX-1
aliases: [N8]
title: "t"
summary: s
kind: prop
status: Disproved
---
## Statement
It fails.
"""

S1_GA = """---
id: GA-2T′
title: primed
kind: assumption
old: "(2T′)"
implies: []
incomparable_with: []
---
## Statement
x
"""

S1_VERDICT = """---
id: 2026-09-24_G8
date: 2026-09-24
subjects: [CEX-1]
---
ok
"""


def write(path, text, newline="\n"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)
    return path


class Homes(unittest.TestCase):
    """Three sibling homes in a temp dir (lab, paper, s1) and a workspace naming them.

    ``suffix`` makes them worktree-like (``FlatSurfLab-wt`` ...); the workspace still
    names the plain directories, which exist only when ``plain`` is true."""

    suffix = ""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="registry-test-"))
        sfx = self.suffix
        self.lab = self.tmp / ("FlatSurfLab" + sfx)
        self.bi = self.tmp / ("BilliardIllumination" + sfx)
        self.s1 = self.tmp / ("Slope1illuminationResearch" + sfx)
        ws = {"instances": {
            "scientist@t": {"role": "scientist", "home": str(self.tmp / "FlatSurfLab"),
                            "domains": ["d"], "ns": "lab"},
            "author@t": {"role": "author", "home": str(self.tmp / "BilliardIllumination"),
                         "domains": ["d"], "ns": "paper"},
            "researcher@t": {"role": "researcher",
                             "home": str(self.tmp / "Slope1illuminationResearch"),
                             "domains": ["d"], "ns": "s1"}},
            "board": str(self.tmp / "board"), "human": {"name": "Roey"}}
        self.ws = write(self.tmp / "workspace.json", json.dumps(ws))
        self._env = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = str(self.ws)
        registry.clear_cache()
        # the lab
        write(self.lab / "claims" / "lab" / "foo.md", LAB_GOOD)
        write(self.lab / "results" / "x.json", "{}")
        write(self.lab / "experiments" / "x.py", '"""h\n\nClaims: lab:foo\n"""\n')
        (self.lab / "queue").mkdir(parents=True)
        # the paper
        write(self.bi / "sections" / "a.tex",
              "\\begin{prop}\\label{prop:foo}Every $x$ is fine.\\end{prop}\n\\label{lem:bar}\n")
        write(self.bi / "Drafts" / "statements.md",
              "| label | env | title | colour | proof |\n|---|---|---|---|---|\n"
              "| `prop:foo` | prop | Foo | established | yes |\n")
        # Slope1
        write(self.s1 / "claims" / "CEX-1.md", S1_Q)
        write(self.s1 / "assumptions" / "GA-2T′.md", S1_GA)
        write(self.s1 / "computation" / "verdicts" / "2026-09-24_G8.md", S1_VERDICT)

    def tearDown(self):
        if self._env is None:
            os.environ.pop("ACADEMY_WORKSPACE", None)
        else:
            os.environ["ACADEMY_WORKSPACE"] = self._env
        registry.clear_cache()
        shutil.rmtree(self.tmp, ignore_errors=True)
