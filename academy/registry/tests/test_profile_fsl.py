"""The ``fsl`` profile (a lab's claim registry, ``claims/<ns>/``): the record checks and
the federation into sibling homes (paper labels, a notebook's ids). Moved from
a lab home's ``tests/test_claims.py`` on 2026-10-09; each case builds a throwaway lab
in a temp directory, with its own workspace.json.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import _util  # noqa: F401  (puts the engine on sys.path)
from registry.profiles import fsl as claims

_WS = {}


def setUpModule():
    # the registry knows a namespace only from workspace.json and finds its home as a
    # sibling directory of that name: give the suite its own workspace (lab, paper, s1)
    # instead of whatever the machine has, so it runs the same on a clean CI runner
    _WS["dir"] = tempfile.TemporaryDirectory()
    base = Path(_WS["dir"].name)
    homes = {"scientist@x": ("lab", "LabHome"),
             "author@x": ("paper", "PaperHome"),
             "researcher@x": ("s1", "NotebookHome")}
    ws = {"board": str(base / "board"),
          "instances": {name: {"role": name.split("@")[0], "ns": ns, "home": str(base / home),
                               "domains": ["translation-surfaces"]}
                        for name, (ns, home) in homes.items()}}
    path = base / "workspace.json"
    path.write_text(json.dumps(ws), encoding="utf-8")
    _WS["old"] = os.environ.get("ACADEMY_WORKSPACE")
    os.environ["ACADEMY_WORKSPACE"] = str(path)


def tearDownModule():
    if _WS["old"] is None:
        os.environ.pop("ACADEMY_WORKSPACE", None)
    else:
        os.environ["ACADEMY_WORKSPACE"] = _WS["old"]
    _WS["dir"].cleanup()

GOOD = """---
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


class Repo:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "LabHome"
        claims._cache.clear()
        for d in ("claims/lab", "results", "experiments", "queue"):
            (self.path / d).mkdir(parents=True)
        (self.path / "results" / "x.json").write_text("{}", encoding="utf-8")
        (self.path / "experiments" / "x.py").write_text('"""h\n\nClaims: lab:foo\n"""\n', encoding="utf-8")

    def write(self, name, text):
        p = self.path / "claims" / "lab" / name
        p.write_text(text, encoding="utf-8")
        return p

    def run(self):
        root = claims.registry_root(self.path)
        cs, perrs = claims.load(root)
        errs, warns = claims.check(cs, repo=self.path, root=root)
        return cs, perrs + errs, warns


class TestClaims(unittest.TestCase):
    def setUp(self):
        self.r = Repo()

    def tearDown(self):
        self.r.tmp.cleanup()

    def test_good_claim_passes(self):
        self.r.write("foo.md", GOOD)
        cs, errs, warns = self.r.run()
        self.assertEqual(errs, [])
        self.assertEqual(cs[0].bears_on, ["paper:prop:foo"])
        self.assertEqual(cs[0].body, "Body.")

    def test_unknown_status(self):
        self.r.write("foo.md", GOOD.replace("status: supported", "status: true"))
        _, errs, _ = self.r.run()
        self.assertTrue(any("status `true`" in e for e in errs))

    def test_history_must_match_status_and_be_newest_first(self):
        self.r.write("foo.md", GOOD.replace("2026-09-24 | supported", "2026-09-24 | open"))
        _, errs, _ = self.r.run()
        self.assertTrue(any("latest history status" in e for e in errs))
        self.r.write("foo.md", GOOD.replace("2026-09-20", "2026-09-30"))
        _, errs, _ = self.r.run()
        self.assertTrue(any("newest first" in e for e in errs))

    def test_missing_evidence_file(self):
        self.r.write("foo.md", GOOD.replace("results/x.json", "results/nope.json"))
        _, errs, _ = self.r.run()
        self.assertTrue(any("does not exist" in e for e in errs))

    def test_supported_needs_evidence(self):
        text = GOOD.replace("  - experiment | results/x.json | not audited | 0 counterexamples below 10\n", "")
        self.r.write("foo.md", text)
        _, errs, _ = self.r.run()
        self.assertTrue(any("no evidence" in e for e in errs))

    def test_refuted_as_stated_needs_successor(self):
        text = GOOD.replace("status: supported", "status: refuted-as-stated").replace(
            "2026-09-24 | supported", "2026-09-24 | refuted-as-stated")
        self.r.write("foo.md", text)
        _, errs, _ = self.r.run()
        self.assertTrue(any("superseded_by" in e for e in errs))

    def test_id_must_match_path(self):
        self.r.write("bar.md", GOOD)
        _, errs, _ = self.r.run()
        self.assertTrue(any("belongs in" in e for e in errs))

    def test_unknown_lab_link_is_error_other_namespaces_are_not(self):
        self.r.write("foo.md", GOOD.replace("paper:prop:foo", "lab:missing"))
        _, errs, _ = self.r.run()
        self.assertTrue(any("lab:missing" in e for e in errs))

    def test_depends_on_refuted_warns(self):
        self.r.write("foo.md", GOOD.replace("bears_on:", "depends_on:\n  - lab:bad\nbears_on:"))
        self.r.write("bad.md", "---\nid: lab:bad\ntitle: t\nstatus: refuted\n"
                     "evidence:\n  - hand | notes | - | counterexample\n"
                     "history:\n  - 2026-09-24 | refuted | found\n---\n")
        _, errs, warns = self.r.run()
        self.assertEqual(errs, [])
        self.assertTrue(any("lab:bad" in w for w in warns))

    def test_colon_names_map_to_double_underscore(self):
        root = claims.registry_root(self.r.path)
        self.assertEqual(claims.file_for(root, "paper:prop:x").name, "prop__x.md")

    def test_config_moves_the_root(self):
        (self.r.path / "queue" / "config.json").write_text(json.dumps({"claimsRoot": "elsewhere"}))
        self.assertEqual(claims.registry_root(self.r.path), (self.r.path / "elsewhere").resolve())

    def test_malformed_frontmatter(self):
        self.r.write("foo.md", "id: lab:foo\n")
        _, errs, _ = self.r.run()
        self.assertTrue(any("no frontmatter" in e for e in errs))

    def test_sql_and_backlinks(self):
        self.r.write("foo.md", GOOD)
        cs, _, _ = self.r.run()
        db = claims.to_sqlite(cs)
        self.assertEqual(db.execute("select status from claims").fetchone()[0], "supported")
        self.assertEqual(db.execute("select count(*) from history").fetchone()[0], 2)
        self.assertEqual(db.execute("select dst from links").fetchone()[0], "paper:prop:foo")
        bl = claims.backlinks("lab:foo", cs, repo=self.r.path)
        self.assertTrue(any("experiments/x.py" in b for b in bl))

    def test_render(self):
        self.r.write("foo.md", GOOD)
        cs, _, _ = self.r.run()
        self.assertIn("`lab:foo`", claims.render_index(cs))
        self.assertIn("lab:foo", claims.render_html(cs))


PAPER_CLAIM = """---
id: paper:prop:foo
title: the proposition
status: {status}
evidence:
{evidence}history:
  - 2026-09-25 | {status} | seeded
---
"""


class TestFederation(unittest.TestCase):
    """Links into the sibling repos: paper labels, a notebook's kb ids, home namespaces."""

    def setUp(self):
        self.r = Repo()
        top = self.r.path.parent
        self.bi = top / "PaperHome"
        (self.bi / "sections").mkdir(parents=True)
        (self.bi / "Drafts").mkdir()
        (self.bi / "sections" / "a.tex").write_text(
            "\\begin{prop}\\label{prop:foo}x\\end{prop}\n\\label{lem:bar}\n", encoding="utf-8")
        (self.bi / "Drafts" / "statements.md").write_text(
            "| label | env | title | colour | proof |\n|---|---|---|---|---|\n"
            "| `prop:foo` | prop | Foo | established | yes |\n"
            "| `lem:bar` | lem |  | sketch | sketched |\n", encoding="utf-8")
        s1 = top / "NotebookHome"
        (s1 / "claims").mkdir(parents=True)
        (s1 / "claims" / "CEX-1.md").write_text(
            "---\nid: CEX-1\naliases: [N8]\ntitle: \"t\"\nstatus: Disproved\n---\nbody\n", encoding="utf-8")

    def tearDown(self):
        self.r.tmp.cleanup()

    def errs_for(self, target, rel="bears_on"):
        self.r.write("foo.md", GOOD.replace("bears_on:\n  - paper:prop:foo", f"{rel}:\n  - {target}"))
        return self.r.run()

    def test_paper_label_resolves(self):
        _, errs, _ = self.errs_for("paper:prop:foo")
        self.assertEqual(errs, [])

    def test_paper_label_missing(self):
        _, errs, _ = self.errs_for("paper:lem:nowhere")
        self.assertTrue(any("not a \\label" in e for e in errs), errs)

    def test_s1_id_resolves_and_alias_is_named(self):
        _, errs, _ = self.errs_for("s1:CEX-1")
        self.assertEqual(errs, [])
        _, errs, _ = self.errs_for("s1:N8")
        self.assertTrue(any("s1:CEX-1" in e for e in errs), errs)
        _, errs, _ = self.errs_for("s1:Q99")
        self.assertTrue(any("no such id" in e for e in errs), errs)

    def test_depends_on_disproved_s1_warns(self):
        _, errs, warns = self.errs_for("s1:CEX-1", rel="depends_on")
        self.assertEqual(errs, [])
        self.assertTrue(any("refuted" in w for w in warns), warns)

    def test_absent_sibling_is_unchecked(self):
        import shutil
        shutil.rmtree(self.bi)
        claims._cache.clear()
        _, errs, _ = self.errs_for("paper:lem:nowhere")
        self.assertEqual(errs, [])

    def test_paper_claim_outside_its_home_is_error(self):
        p = self.r.path / "claims" / "paper" / "prop__foo.md"
        p.parent.mkdir()
        p.write_text(PAPER_CLAIM.format(status="open", evidence=""), encoding="utf-8")
        _, errs, _ = self.r.run()
        self.assertTrue(any("live in PaperHome" in e for e in errs), errs)

    def paper_run(self, status, evidence=""):
        p = self.bi / "claims" / "paper" / "prop__foo.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(PAPER_CLAIM.format(status=status, evidence=evidence), encoding="utf-8")
        root = claims.registry_root(self.bi)
        cs, perrs = claims.load(root)
        errs, warns = claims.check(cs, repo=self.bi, root=root)
        return perrs + errs, warns

    def test_black_statement_needs_proved_and_is_flagged_unverified(self):
        errs, _ = self.paper_run("refuted", "  - hand | notes | - | counterexample\n")
        self.assertTrue(any("black in the draft" in e for e in errs), errs)
        errs, warns = self.paper_run("proved", "  - hand | notes | - | argument\n")
        self.assertEqual(errs, [])
        self.assertTrue(any("no verdict or citation" in w for w in warns), warns)
        for ev in ("  - verdict | Drafts/statements.md | proved | two runs\n",
                   "  - citation | references.bib | - | cites Ha02\n"):
            errs, warns = self.paper_run("proved", ev)
            self.assertEqual((errs, warns), ([], []))


if __name__ == "__main__":
    unittest.main()
