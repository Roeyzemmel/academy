"""#127: structured claim records -- named hypotheses and per-item status, modulo and
hash (the human's ruling of 2026-11-27: "Hypotheses + items"; ``steps`` out of scope).
A record without ``hypotheses`` / ``items`` behaves exactly as before (the rest of the
suite); these tests cover the structured form in both profiles: the parsing of the body
texts, the derived status, the check, the item hashes and the lazy-migration proposal."""
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from _util import notebook_config, write

import registry
from registry import cli
from registry.core import federation, structure
from registry.profiles import fsl, s1kb

NB = """---
id: {id}
kind: claim
form: prop
title: "t {id}"
status: {status}
{modulo}lifecycle: active
summary: s
depends_on: []
aliases: []
domain: d
tags: []
{struct}evidence: []
history:
  - "2026-11-20 | {status} | created"
---

## Statement

Let $P$ be a polygon.

**H1.** $P$ is rational.
**H2.** $X$ is conical.

Then:

- **C1.** the unfolding is compact;
- **C2.** it has finitely many
  cone points.

## Proof

Because.
"""

PAPER_TEX = r"""\begin{prop}\label{prop:uc}
Let $P$ be rational. Then
\begin{enumerate}
\item the unfolding is compact \label{it:compact}
\item it has finitely many cone points, and
  \begin{enumerate}
  \item each has angle $2\pi k$; \label{it:angles}
  \end{enumerate}
\item an unlabelled item.
\end{enumerate}
\end{prop}
\begin{lem}\label{lem:x}X holds.\end{lem}
"""

PAPER = """---
id: paper:{label}
kind: claim
title: t
status: {status}
{modulo}lifecycle: active
where: sections/a.tex
{struct}evidence:
  - verdict | rev/A.md | CONFIRMED | rv-a | -
history:
  - 2026-11-20 | {status} | created
---
"""


def modulo_block(items):
    return "modulo:\n" + "".join("  - %s\n" % m for m in items) if items else ""


def quiet(fn, *a):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = fn(*a)
    return rc, out.getvalue(), err.getvalue()


class Parsing(unittest.TestCase):
    def test_notebook_parts_run_to_the_next_marker(self):
        _fm, body = s1kb.split_document(NB.format(id="GEO-1", status="open", modulo="",
                                                  struct=""))
        h, c = structure.nb_parts(s1kb.section(body, "Statement"))
        self.assertEqual(list(h), ["H1", "H2"])
        self.assertEqual(h["H1"], "$P$ is rational.")
        self.assertEqual(h["H2"], "$X$ is conical.")     # a blank line ends a part
        self.assertEqual(list(c), ["C1", "C2"])
        self.assertEqual(c["C2"], "it has finitely many\n  cone points.")

    def test_marker_spellings(self):
        h, c = structure.nb_parts("**H1:** a\n* **C1**. b\n**C2.** c\n## Other\nd")
        self.assertEqual((h, c), ({"H1": "a"}, {"C1": "b", "C2": "c"}))

    def test_paper_items_follow_the_list_nesting(self):
        items = structure.paper_items(PAPER_TEX.split("\\begin{lem}")[0])
        self.assertEqual(list(items), ["compact", "angles"])
        self.assertTrue(items["compact"].startswith("\\item the unfolding is compact"))
        self.assertNotIn("finitely", items["compact"])
        self.assertIn("angle $2\\pi k$", items["angles"])
        self.assertNotIn("unlabelled", items["angles"])

    def test_derive(self):
        d = structure.derive
        self.assertEqual(d({"C1": ("proved", []), "C2": ("proved", [])}), ("proved", []))
        self.assertEqual(d({"C1": ("proved-modulo", ["a", "b"]), "C2": ("proved", []),
                            "C3": ("proved-modulo", ["b", "c"])}),
                         ("proved-modulo", ["a", "b", "c"]))
        self.assertEqual(d({"C1": ("proved", []), "C2": ("sketch", []),
                            "C3": ("conjectured", [])}), ("conjectured", []))
        self.assertEqual(d({"C1": ("proved", []), "C2": ("refuted", [])}), ("refuted", []))
        self.assertEqual(d({}), (None, []))

    def test_item_hashes(self):
        hy = {"H1": "P rational", "H2": "X conical"}
        it = {"C1": "compact", "C2": "finite"}
        base = structure.item_hashes(hy, it)
        self.assertNotEqual(base["C1"], base["C2"])
        # a reworded item changes only its own hash
        h2 = structure.item_hashes(hy, dict(it, C2="finitely many"))
        self.assertEqual(h2["C1"], base["C1"])
        self.assertNotEqual(h2["C2"], base["C2"])
        # a changed hypothesis changes every item's hash
        h3 = structure.item_hashes(dict(hy, H2="X arbitrary"), it)
        self.assertTrue(all(h3[k] != base[k] for k in it))
        # whitespace is not a change
        self.assertEqual(structure.item_hashes(hy, {"C1": " compact\n"})["C1"], base["C1"])


class Homes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="structure-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.nb = self.tmp / "NotebookHome"
        self.bi = self.tmp / "PaperHome"
        ws = {"instances": {
            "researcher@t": {"role": "researcher", "home": str(self.nb), "ns": "s1"},
            "author@t": {"role": "author", "home": str(self.bi), "ns": "paper"}},
            "board": str(self.tmp / "board"), "human": {"name": "the human"}}
        wsp = write(self.tmp / "workspace.json", json.dumps(ws))
        old = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = str(wsp)
        self.addCleanup(lambda: os.environ.__setitem__("ACADEMY_WORKSPACE", old)
                        if old is not None else os.environ.pop("ACADEMY_WORKSPACE", None))
        self.addCleanup(registry.clear_cache)
        notebook_config(self.nb, ns="s1", rules={})
        write(self.bi / "sections" / "a.tex", PAPER_TEX)
        write(self.bi / "rev" / "A.md", "review\n")
        registry.clear_cache()

    # -- fixtures ------------------------------------------------------------
    def obj(self, eid, status="proved-modulo", modulo=("GEO-9",), struct=None):
        if struct is None:
            struct = ('hypotheses:\n  H1: "P rational"\n  H2: "X conical"\n'
                      "items:\n  C1: [proved]\n  C2: [proved-modulo, GEO-9]\n")
        p = write(self.nb / "objects" / "claim" / (eid + ".md"), NB.format(
            id=eid, status=status, modulo=modulo_block(modulo), struct=struct))
        registry.clear_cache()
        return p

    def paper(self, label="prop:uc", status="proved-modulo", modulo=("paper:lem:x",),
              struct=None):
        if struct is None:
            struct = ('hypotheses:\n  H1: "P is rational"\n'
                      "items:\n  compact: [proved]\n  angles: [proved-modulo, paper:lem:x]\n")
        p = write(self.bi / "claims" / "paper" / (label.replace(":", "__") + ".md"),
                  PAPER.format(label=label, status=status, modulo=modulo_block(modulo),
                               struct=struct))
        registry.clear_cache()
        return p

    def nb_errors(self):
        registry.clear_cache()
        kb = s1kb.load_kb(self.nb)
        s1kb.run_check(kb)
        return kb.errors

    def paper_errors(self):
        registry.clear_cache()
        claims, perrs = fsl.load(fsl.registry_root(self.bi))
        errs, _w = fsl.check(claims, repo=self.bi)
        return perrs + errs

    def setup_nb_dep(self):
        write(self.nb / "objects" / "claim" / "GEO-9.md", NB.format(
            id="GEO-9", status="open", modulo="", struct="").replace(
            "**H1.**", "H1.").replace("**H2.**", "H2.").replace("- **C1.**", "-").replace(
            "- **C2.**", "-"))

    # -- notebook ------------------------------------------------------------
    def test_notebook_structured_record_is_clean(self):
        self.setup_nb_dep()
        self.obj("GEO-1")
        self.assertEqual(self.nb_errors(), [])

    def test_notebook_status_must_be_derived(self):
        self.setup_nb_dep()
        self.obj("GEO-1", status="proved", modulo=())
        errs = " ".join(self.nb_errors())
        self.assertIn("the items derive `proved-modulo`", errs)

    def test_notebook_record_modulo_is_the_items_union(self):
        self.setup_nb_dep()
        write(self.nb / "objects" / "claim" / "GEO-8.md", NB.format(
            id="GEO-8", status="open", modulo="", struct="").replace("**", ""))
        self.obj("GEO-1", modulo=("GEO-9", "GEO-8"))
        self.assertIn("modulo [GEO-9, GEO-8] but the items' inputs are [GEO-9]",
                      " ".join(self.nb_errors()))

    def test_notebook_keys_and_texts_must_match(self):
        self.setup_nb_dep()
        self.obj("GEO-1", status="proved", modulo=(),
                 struct='hypotheses:\n  H1: "P rational"\nitems:\n  C1: [proved]\n'
                        "  C3: [proved]\n")
        errs = " ".join(self.nb_errors())
        self.assertIn("items without a `**C<n>.**` line in the statement: C3", errs)
        self.assertIn("`**C<n>.**` lines not under `items`: C2", errs)
        self.assertIn("`**H<n>.**` lines in the statement not under `hypotheses`: H2", errs)

    def test_item_modulo_rule(self):
        self.setup_nb_dep()
        self.obj("GEO-1", status="proved-modulo", modulo=("GEO-9",),
                 struct='hypotheses:\n  H1: a\n  H2: b\nitems:\n  C1: [proved-modulo]\n'
                        "  C2: [proved, GEO-9]\n")
        errs = " ".join(self.nb_errors())
        self.assertIn("item C1: proved-modulo needs its modulo inputs", errs)
        self.assertIn("item C2: inputs GEO-9 are given only with proved-modulo", errs)

    def test_store_structure_and_item_hashes(self):
        self.setup_nb_dep()
        self.obj("GEO-1")
        st = federation.store("s1", self.nb)
        s = st.structure("GEO-1")
        self.assertEqual(s["status"], "proved-modulo")
        self.assertEqual(s["modulo"], ["GEO-9"])
        self.assertEqual(sorted(s["hashes"]), ["C1", "C2"])
        whole = st.statement_hash("GEO-1")
        # the whole-statement hash is the old one: the frontmatter fields do not enter it
        p = self.obj("GEO-1", struct="")
        self.assertEqual(federation.store("s1", self.nb).statement_hash("GEO-1"), whole)
        self.assertIsNone(federation.store("s1", self.nb).structure("GEO-1"))
        # rewording C2 changes only C2's hash
        self.obj("GEO-1")
        p.write_text(p.read_text(encoding="utf-8").replace("finitely many", "few"),
                     encoding="utf-8")
        registry.clear_cache()
        s2 = federation.store("s1", self.nb).structure("GEO-1")
        self.assertEqual(s2["hashes"]["C1"], s["hashes"]["C1"])
        self.assertNotEqual(s2["hashes"]["C2"], s["hashes"]["C2"])

    def test_cli_statement_items_and_structure_proposal(self):
        self.setup_nb_dep()
        p = self.obj("GEO-1", struct="")
        registry.clear_cache()
        rc, out, err = quiet(cli.main, ["--repo", str(self.nb), "structure", "s1:GEO-1"])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("items:\n  C1: [proved-modulo, GEO-9]\n  C2: [proved-modulo, GEO-9]",
                      out)
        self.assertIn("H1: $P$ is rational.\n  H2: $X$ is conical.\n", out)
        self.assertNotIn("items:", p.read_text(encoding="utf-8"))   # dry run
        rc, out, err = quiet(cli.main, ["--repo", str(self.nb), "structure", "s1:GEO-1",
                                        "--write"])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("items:", p.read_text(encoding="utf-8"))
        self.assertEqual(self.nb_errors(), [])
        registry.clear_cache()
        rc, out, err = quiet(cli.main, ["--repo", str(self.nb), "statement", "s1:GEO-1",
                                        "--items"])
        self.assertEqual(rc, 0, out + err)
        st = federation.store("s1", self.nb).structure("GEO-1")
        self.assertIn("C1 proved-modulo GEO-9 hash %s" % st["hashes"]["C1"], out)
        self.assertTrue(out.startswith("hash: "))

    # -- paper ---------------------------------------------------------------
    def test_paper_structured_record_is_clean(self):
        self.paper("lem:x", status="proved", modulo=(), struct="")
        self.paper()
        self.assertEqual(self.paper_errors(), [])
        s = federation.store("paper", self.bi).structure("prop:uc")
        self.assertEqual(list(s["texts"]), ["compact", "angles"])
        self.assertEqual(s["hypotheses"], {"H1": "P is rational"})

    def test_paper_labels_must_match(self):
        self.paper("lem:x", status="proved", modulo=(), struct="")
        self.paper(status="proved", modulo=(),
                   struct="items:\n  compact: [proved]\n  it:gone: [proved]\n")
        errs = " ".join(self.paper_errors())
        self.assertIn("write the label without its `it:` prefix (`gone`)", errs)
        self.assertIn("`\\label{it:...}` items not under `items`: angles", errs)

    def test_paper_structure_proposal(self):
        self.paper("lem:x", status="proved", modulo=(), struct="")
        p = self.paper(struct="")
        rc, out, err = quiet(cli.main, ["--repo", str(self.bi), "structure", "paper:prop:uc",
                                        "--write"])
        self.assertEqual(rc, 0, out + err)
        text = p.read_text(encoding="utf-8")
        self.assertIn("items:\n  compact: [proved-modulo, paper:lem:x]\n"
                      "  angles: [proved-modulo, paper:lem:x]\n", text)
        self.assertEqual(self.paper_errors(), [])

    def test_unstructured_records_are_untouched(self):
        self.paper("lem:x", status="proved", modulo=(), struct="")
        st = federation.store("paper", self.bi)
        self.assertIsNone(st.structure("lem:x"))
        self.assertEqual(self.paper_errors(), [])


if __name__ == "__main__":
    unittest.main()
