"""#127: the keeper and the discharge per item of a structured record. An item is set on
grounds checked against that item's hash; the record's status is re-derived from its
items; a whole-record status change sets every item; the mechanical discharge works per
item (an item proved-modulo whose inputs are all established becomes proved)."""
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
from registry.core import discharge, federation, itemedit, schema
from registry.profiles import fsl, s1kb

LAB = """---
id: lab:{id}
kind: claim
title: t {id}
status: {status}
{modulo}lifecycle: active
{struct}evidence:
  - hand | notes/{id}.md | - | - | seed
history:
  - 2026-11-20 | {status} | created
---
**H1.** the surface is compact.

**C1.** the first conclusion.
**C2.** the second conclusion.
"""

STRUCT = ("hypotheses:\n  H1: compact\nitems:\n  C1: [{c1}]\n  C2: [{c2}]\n")

NB = """---
id: {id}
kind: claim
form: lemma
title: "t {id}"
status: {status}
{modulo}lifecycle: active
summary: s
depends_on: []
bears_on: []
supersedes: []
aliases: []
domain: d
tags: []
{struct}evidence: []
history:
  - "2026-11-20 | {status} | created"
---

## Statement

**H1.** a hypothesis.

**C1.** one.
**C2.** two.
"""

REVIEW = ("---\nsubject: lab:{id}\nrun: {run}\nrun_id: rv-{run}-{id}\nverdict: CONFIRMED\n"
          "statement_hash: {h}\nagent: expert:rigor-reviewer\n---\nreview\n")


def modulo_block(items):
    return "modulo:\n" + "".join("  - %s\n" % m for m in items) if items else ""


def quiet(fn, *a):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = fn(*a)
    return rc, out.getvalue(), err.getvalue()


class KeeperPerItem(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="items-keeper-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.lab = self.tmp / "LabHome"
        self.nb = self.tmp / "NotebookHome"
        ws = {"instances": {
            "scientist@t": {"role": "scientist", "home": str(self.lab), "ns": "lab"},
            "researcher@t": {"role": "researcher", "home": str(self.nb), "ns": "s1"}},
            "board": str(self.tmp / "board"), "human": {"name": "the human"}}
        wsp = write(self.tmp / "workspace.json", json.dumps(ws))
        old = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = str(wsp)
        self.addCleanup(lambda: os.environ.__setitem__("ACADEMY_WORKSPACE", old)
                        if old is not None else os.environ.pop("ACADEMY_WORKSPACE", None))
        self.addCleanup(registry.clear_cache)
        (self.lab / "claims" / "lab").mkdir(parents=True)
        notebook_config(self.nb, ns="s1", rules={})
        self.plain("in-a", "proved")
        self.plain("in-b", "open")

    # -- fixtures ------------------------------------------------------------
    def plain(self, cid, status):
        write(self.lab / "notes" / (cid + ".md"), "n\n")
        text = LAB.format(id=cid, status=status, modulo="", struct="").split("**H1.**")[0]
        if status == "proved":
            text = text.replace("  - hand | notes/%s.md | - | - | seed" % cid,
                                "  - citation | notes/%s.md | - | - | seed" % cid)
        write(self.lab / "claims" / "lab" / (cid + ".md"), text + "Body.\n")
        registry.clear_cache()

    def lab_claim(self, cid="s", status="proved-modulo", c1="proved",
                  c2="proved-modulo, lab:in-b", modulo=("lab:in-b",)):
        write(self.lab / "notes" / (cid + ".md"), "n\n")
        p = write(self.lab / "claims" / "lab" / (cid + ".md"), LAB.format(
            id=cid, status=status, modulo=modulo_block(modulo),
            struct=STRUCT.format(c1=c1, c2=c2)))
        registry.clear_cache()
        return p

    def store(self):
        registry.clear_cache()
        return federation.store("lab", self.lab)

    def reviews(self, cid, h):
        refs = []
        for run in "AB":
            write(self.lab / "reviews" / cid / (run + ".md"),
                      REVIEW.format(id=cid, run=run, h=h))
            refs.append(("reviews/%s/%s.md" % (cid, run), "rv-%s-%s" % (run, cid)))
        return refs

    def grounds(self, cid, key, modulo=(), item_hash=True):
        st = self.store()
        h = st.statement_hash(cid)
        g = {"basis": "proof", "producer_role": "researcher", "statement_hash": h,
             "item": key,
             "verdicts": [{"verdict": "CONFIRMED", "run_id": rid, "statement_hash": h,
                           "grader_role": "expert", "ref": ref}
                          for ref, rid in self.reviews(cid, h)]}
        if item_hash:
            g["item_hash"] = st.item_hash(cid, key)
        if modulo:
            g["modulo"] = list(modulo)
        return g

    def rec(self, cid):
        p = self.lab / "claims" / "lab" / (cid + ".md")
        return fsl.parse_text(p.read_text(encoding="utf-8"), p, fallback=False)

    def lab_errors(self):
        registry.clear_cache()
        claims, perrs = fsl.load(fsl.registry_root(self.lab))
        errs, _ = fsl.check(claims, repo=self.lab)
        return perrs + errs

    # -- set one item --------------------------------------------------------
    def test_fixture_is_clean(self):
        self.lab_claim()
        self.assertEqual(self.lab_errors(), [])

    def test_setting_the_last_item_proved_makes_the_record_proved(self):
        self.lab_claim(c2="sketch", status="sketch", modulo=())
        g = self.grounds("s", "C2")
        res = itemedit.set_item("lab:s", self.lab, "C2", "proved", g, date="2026-11-27")
        self.assertEqual((res["old"], res["record_old"], res["record"]),
                         ("sketch", "sketch", "proved"))
        c = self.rec("s")
        self.assertEqual(c.fields["items"], {"C1": ["proved"], "C2": ["proved"]})
        self.assertEqual(c.status, "proved")
        self.assertTrue(c.history[0].startswith("2026-11-27 | proved | item C2 sketch -> proved"))
        rows = [r for r in c.evidence if r.startswith("verdict |")]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("item C2" in r for r in rows))
        self.assertEqual(self.lab_errors(), [])

    def test_an_item_proved_modulo_carries_the_record_modulo(self):
        self.lab_claim(c2="sketch", status="sketch", modulo=())
        g = self.grounds("s", "C2", modulo=["lab:in-b"])
        res = itemedit.set_item("lab:s", self.lab, "C2", "proved-modulo", g)
        self.assertEqual((res["record"], res["modulo"]), ("proved-modulo", ["lab:in-b"]))
        self.assertEqual(self.rec("s").modulo, ["lab:in-b"])
        self.assertEqual(self.lab_errors(), [])

    def test_grounds_on_another_item_hash_are_refused_and_nothing_written(self):
        p = self.lab_claim(c2="sketch", status="sketch", modulo=())
        g = self.grounds("s", "C2")
        g["item_hash"] = "0" * 16
        before = p.read_bytes()
        with self.assertRaises(itemedit.Refused) as cm:
            itemedit.set_item("lab:s", self.lab, "C2", "proved", g)
        self.assertIn("is not item C2's current", str(cm.exception))
        self.assertEqual(p.read_bytes(), before)
        g = self.grounds("s", "C2")
        with self.assertRaises(itemedit.Refused) as cm:
            itemedit.set_item("lab:s", self.lab, "C1", "proved", g)
        self.assertIn("the grounds are for item C2, not C1", str(cm.exception))

    def test_a_reworded_item_does_not_invalidate_another_items_grounds(self):
        p = self.lab_claim(c2="sketch", status="sketch", modulo=())
        g = self.grounds("s", "C2")
        # C1 is reworded after the review: the whole hash moves, C2's does not
        p.write_text(p.read_text(encoding="utf-8").replace("the first conclusion",
                                                           "the first, reworded"),
                     encoding="utf-8")
        self.assertNotEqual(self.store().statement_hash("s"), g["statement_hash"])
        res = itemedit.set_item("lab:s", self.lab, "C2", "proved", g)
        self.assertEqual(res["record"], "proved")
        # ... but a changed hypothesis does
        self.lab_claim(c2="sketch", status="sketch", modulo=())
        g = self.grounds("s", "C2")
        p.write_text(p.read_text(encoding="utf-8").replace("is compact", "is closed"),
                     encoding="utf-8")
        with self.assertRaises(itemedit.Refused):
            itemedit.set_item("lab:s", self.lab, "C2", "proved", g)

    def test_whole_grounds_without_item_hash_need_the_whole_hash(self):
        p = self.lab_claim(c2="sketch", status="sketch", modulo=())
        g = self.grounds("s", "C2", item_hash=False)
        p.write_text(p.read_text(encoding="utf-8").replace("the first conclusion",
                                                           "the first, reworded"),
                     encoding="utf-8")
        with self.assertRaises(itemedit.Refused) as cm:
            itemedit.set_item("lab:s", self.lab, "C2", "proved", g)
        self.assertIn("is not the claim's current", str(cm.exception))

    def test_a_record_without_items_is_refused(self):
        with self.assertRaises(itemedit.Refused) as cm:
            itemedit.set_item("lab:in-b", self.lab, "C1", "proved", {})
        self.assertIn("has no `items`", str(cm.exception))

    def test_a_whole_record_change_sets_every_item(self):
        self.lab_claim(c2="sketch", c1="sketch", status="sketch", modulo=())
        g = self.grounds("s", None, item_hash=False)
        g.pop("item")
        g["modulo"] = ["lab:in-b"]
        fsl.set_status(self.lab, "lab:s", "proved-modulo", g)
        c = self.rec("s")
        self.assertEqual(c.fields["items"], {"C1": ["proved-modulo", "lab:in-b"],
                                             "C2": ["proved-modulo", "lab:in-b"]})
        self.assertEqual(c.status, "proved-modulo")
        self.assertEqual(self.lab_errors(), [])

    # -- discharge per item ------------------------------------------------
    def test_discharge_per_item(self):
        self.lab_claim(c2="proved-modulo, lab:in-a", modulo=("lab:in-a",))
        a = discharge.assess("lab:s", self.lab)
        self.assertTrue(a["dischargeable"], a)
        self.assertEqual(sorted(a["items"]), ["C2"])
        discharge.apply("lab:s", self.lab, date="2026-11-27")
        c = self.rec("s")
        self.assertEqual(c.fields["items"], {"C1": ["proved"], "C2": ["proved"]})
        self.assertEqual(c.status, "proved")
        self.assertNotIn("modulo", c.fields)
        rows = [r for r in c.evidence if schema.evidence_cells(r)[0] == "discharge"]
        self.assertEqual(len(rows), 1)
        self.assertIn("item C2", rows[0])
        self.assertIn("item C2 discharged: inputs lab:in-a proved", c.history[0])
        self.assertEqual(self.lab_errors(), [])

    def test_a_partial_discharge_keeps_the_record_proved_modulo(self):
        self.lab_claim(c1="proved-modulo, lab:in-a", c2="proved-modulo, lab:in-b",
                       modulo=("lab:in-a", "lab:in-b"))
        rc, out, err = quiet(cli.main, ["--repo", str(self.lab), "discharge", "lab:s"])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("C1", out)
        c = self.rec("s")
        self.assertEqual(c.fields["items"], {"C1": ["proved"],
                                             "C2": ["proved-modulo", "lab:in-b"]})
        self.assertEqual((c.status, c.modulo), ("proved-modulo", ["lab:in-b"]))
        self.assertEqual(self.lab_errors(), [])
        # nothing left to discharge: held, and nothing written
        before = (self.lab / "claims" / "lab" / "s.md").read_bytes()
        a = discharge.assess("lab:s", self.lab)
        self.assertFalse(a["dischargeable"])
        with self.assertRaises(ValueError):
            discharge.apply("lab:s", self.lab)
        self.assertEqual((self.lab / "claims" / "lab" / "s.md").read_bytes(), before)

    # -- the notebook profile ----------------------------------------------
    def test_notebook_item_on_the_human_word_and_its_discharge(self):
        write(self.nb / "objects" / "claim" / "GEO-2.md", NB.format(
            id="GEO-2", status="proved", modulo="", struct="").replace("**", ""))
        p = write(self.nb / "objects" / "claim" / "GEO-1.md", NB.format(
            id="GEO-1", status="sketch", modulo="",
            struct='hypotheses:\n  H1: "a hypothesis."\nitems:\n  C1: [proved]\n'
                   "  C2: [sketch]\n"))
        registry.clear_cache()
        kb = s1kb.load_kb(self.nb)
        s1kb.run_check(kb)
        self.assertEqual(kb.errors, [])
        g = {"basis": "human", "quote": "C2 holds modulo GEO-2", "modulo": ["GEO-2"]}
        res = itemedit.set_item("s1:GEO-1", self.nb, "C2", "proved-modulo", g, human=True)
        self.assertEqual(res["record"], "proved-modulo")
        v2 = s1kb.load_kb(self.nb).entities["GEO-1"].v2
        self.assertEqual(v2["items"]["C2"], ["proved-modulo", "GEO-2"])
        self.assertEqual(v2["modulo"], ["GEO-2"])
        registry.clear_cache()
        discharge.apply("s1:GEO-1", self.nb)
        v2 = s1kb.load_kb(self.nb).entities["GEO-1"].v2
        self.assertEqual((v2["status"], v2["items"]["C2"]), ("proved", ["proved"]))
        self.assertNotIn("modulo", v2)
        self.assertIn("item C2", p.read_text(encoding="utf-8"))

    def test_notebook_whole_change_sets_every_item(self):
        write(self.nb / "objects" / "claim" / "GEO-1.md", NB.format(
            id="GEO-1", status="sketch", modulo="",
            struct='hypotheses:\n  H1: "a hypothesis."\nitems:\n  C1: [sketch]\n'
                   "  C2: [sketch]\n"))
        registry.clear_cache()
        rc, out, err = quiet(s1kb.main, ["set-status", "GEO-1", "open", "--note",
                                         "reopened", "--root", str(self.nb)])
        self.assertEqual(rc, 0, out + err)
        v2 = s1kb.load_kb(self.nb).entities["GEO-1"].v2
        self.assertEqual((v2["status"], v2["items"]), ("open", {"C1": ["open"],
                                                                "C2": ["open"]}))


if __name__ == "__main__":
    unittest.main()
