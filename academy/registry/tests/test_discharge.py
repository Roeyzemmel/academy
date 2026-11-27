"""#127: the mechanical discharge of a proved-modulo record (the human's ruling of
2026-11-27: "Yes, mechanical"). A record becomes proved once every input of its
``modulo`` is established -- a proved record (not proved-modulo: a chain discharges
bottom-up), a ``bib:`` card pinpoint whose card says match, a notation-only definition --
with one ``discharge`` evidence row and a history row; anything else holds it and is
reported. Both profiles (fsl-claims: lab; s1-kb: a notebook), across namespaces."""
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
from registry.core import discharge, grounds, schema
from registry.profiles import fsl, s1kb

LAB = """---
id: lab:{id}
kind: {kind}
title: t {id}
{status}{modulo}lifecycle: active
{tags}evidence:
  - verdict | reviews/{id}/A.md | CONFIRMED | rv-a-{id} | grader rigor-reviewer
  - verdict | reviews/{id}/B.md | CONFIRMED | rv-b-{id} | grader rigor-reviewer
history:
  - 2026-11-20 | {hstatus} | proof review (CONFIRMED rv-a-{id}, CONFIRMED rv-b-{id})
  - 2026-11-01 | sketch | created
---
Body {id}.
"""

NB = """---
id: {id}
kind: claim
form: lemma
title: "t {id}"
status: {status}
lifecycle: active
summary: s
statement: "X {id}."
{modulo}depends_on: []
bears_on: []
supersedes: []
aliases: [{alias}]
domain: d
tags: []
evidence: []
history:
  - "2026-11-20 | {status} | created"
---

## Statement

X {id}.
"""

CARD = """---
key: {key}
pinpoint: {pin}
version: v1
read_from: source
verdict: {verdict}
checked: 2026-11-01
by: expert@t/librarian
---

## Statement

s
"""


def modulo_block(items):
    return "modulo:\n" + "".join("  - %s\n" % m for m in items) if items else ""


def quiet(fn, *a):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = fn(*a)
    return rc, out.getvalue(), err.getvalue()


class Discharge(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="discharge-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.lab = self.tmp / "LabHome"
        self.nb = self.tmp / "NotebookHome"
        self.lib = self.tmp / "Library"
        ws = {"instances": {
            "scientist@t": {"role": "scientist", "home": str(self.lab), "ns": "lab"},
            "researcher@t": {"role": "researcher", "home": str(self.nb), "ns": "s1"},
            "expert@t": {"role": "expert", "home": str(self.lib)}},
            "board": str(self.tmp / "board"), "human": {"name": "the human"}}
        wsp = write(self.tmp / "workspace.json", json.dumps(ws))
        old = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = str(wsp)
        self.addCleanup(lambda: os.environ.__setitem__("ACADEMY_WORKSPACE", old)
                        if old is not None else os.environ.pop("ACADEMY_WORKSPACE", None))
        self.addCleanup(registry.clear_cache)
        registry.clear_cache()
        (self.lab / "claims" / "lab").mkdir(parents=True)
        notebook_config(self.nb, ns="s1", rules={})
        (self.lib / "cards").mkdir(parents=True)
        self.card("AW21", "Theorem 3.6", "match", "theorem-3-6")
        self.card("AW21", "Lemma 2.1", "partial", "lemma-2-1")
        # the lab: proved inputs, a proved-modulo input, a notation-only definition
        self.claim("in-a", "proved")
        self.claim("in-b", "proved")
        self.claim("mid", "proved-modulo", ["lab:in-a"])
        self.claim("defn-n", None, kind="definition", tags=["notation-only"])
        # the notebook: one proved, one open
        self.obj("GEO-1", "proved", alias="N1")
        self.obj("GEO-2", "open")

    # -- fixtures ------------------------------------------------------------
    def card(self, key, pin, verdict, slug):
        write(self.lib / "cards" / key / (slug + ".md"),
              CARD.format(key=key, pin=pin, verdict=verdict))

    def claim(self, cid, status, modulo=(), kind="claim", tags=()):
        for r in "AB":
            write(self.lab / "reviews" / cid / (r + ".md"),
                  "---\nsubject: lab:%s\nrun: %s\nrun_id: rv-%s-%s\nverdict: CONFIRMED\n"
                  "agent: expert:rigor-reviewer\n---\nreview\n" % (cid, r, r.lower(), cid))
        return write(self.lab / "claims" / "lab" / (cid + ".md"), LAB.format(
            id=cid, status="status: %s\n" % status if status else "", hstatus=status or "",
            kind=kind, modulo=modulo_block(modulo),
            tags=("tags: [%s]\n" % ", ".join(tags)) if tags else ""))

    def obj(self, eid, status, modulo=(), alias=""):
        return write(self.nb / "objects" / "claim" / (eid + ".md"), NB.format(
            id=eid, status=status, modulo=modulo_block(modulo), alias=alias))

    def lab_rec(self, cid):
        p = self.lab / "claims" / "lab" / (cid + ".md")
        return fsl.parse_text(p.read_text(encoding="utf-8"), p, fallback=False)

    def nb_rec(self, eid):
        return s1kb.load_kb(self.nb).entities[eid].v2

    def lab_clean(self):
        claims, perrs = fsl.load(fsl.registry_root(self.lab))
        errs, _ = fsl.check(claims, repo=self.lab)
        self.assertEqual((perrs, errs), ([], []))

    def run_cli(self, *argv, repo=None):
        registry.clear_cache()
        return quiet(cli.main, ["--repo", str(repo or self.lab), "discharge", *argv])

    # -- the rule ------------------------------------------------------------
    def test_fixture_is_clean(self):
        self.lab_clean()
        kb = s1kb.load_kb(self.nb)
        s1kb.run_check(kb)
        self.assertEqual(kb.errors, [])

    def test_all_inputs_proved_discharges_with_evidence_and_history(self):
        p = self.claim("pm", "proved-modulo", ["lab:in-a", "in-b"])
        a = discharge.assess("lab:pm", self.lab)
        self.assertTrue(a["dischargeable"], a)
        self.assertEqual([i["id"] for i in a["inputs"]], ["lab:in-a", "lab:in-b"])
        discharge.apply("lab:pm", self.lab, date="2026-11-27")
        c = self.lab_rec("pm")
        self.assertEqual(c.status, "proved")
        self.assertNotIn("modulo", c.fields)
        self.assertNotIn("modulo:", p.read_text(encoding="utf-8"))
        rows = [r for r in c.evidence if schema.evidence_cells(r)[0] == "discharge"]
        self.assertEqual(len(rows), 1, c.evidence)
        t, ref, verdict, _run, note = schema.evidence_cells(rows[0])
        self.assertEqual((ref, verdict), ("lab:in-a, lab:in-b", "proved"))
        self.assertIn("lab:in-a: proved", note)
        self.assertEqual(c.history[0],
                         "2026-11-27 | proved | discharged: inputs lab:in-a, lab:in-b proved")
        # the two reviews that carried proved-modulo stay on the record
        self.assertEqual(sum(r.startswith("verdict |") for r in c.evidence), 2)
        self.lab_clean()

    def test_an_input_still_proved_modulo_holds_it_and_a_chain_goes_bottom_up(self):
        self.claim("top", "proved-modulo", ["lab:mid"])
        a = discharge.assess("lab:top", self.lab)
        self.assertFalse(a["dischargeable"])
        self.assertIn("proved-modulo (a chain discharges bottom-up)", " ".join(a["problems"]))
        before = (self.lab / "claims" / "lab" / "top.md").read_bytes()
        with self.assertRaises(ValueError):
            discharge.apply("lab:top", self.lab)
        self.assertEqual((self.lab / "claims" / "lab" / "top.md").read_bytes(), before)
        # --input in-a: mid discharges, then top (which rests on mid) in the same run
        rc, out, err = self.run_cli("--input", "lab:in-a")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.lab_rec("mid").status, "proved")
        self.assertEqual(self.lab_rec("top").status, "proved")
        self.lab_clean()

    def test_free_text_holds_it_and_is_reported(self):
        self.claim("ft", "proved-modulo", ["lab:in-a", "the sum theorem (uncited)"])
        rc, out, err = self.run_cli("lab:ft", "--dry-run")
        self.assertEqual(rc, 0, err)
        self.assertIn("lab:ft  proved-modulo  held", out)
        self.assertIn("free text", out)
        self.assertIn("ok  lab:in-a proved", out)
        self.assertEqual(self.lab_rec("ft").status, "proved-modulo")

    def test_bib_input_counts_only_with_a_matching_card(self):
        self.claim("cite", "proved-modulo", ["bib:AW21#Theorem 3.6", "lab:in-a"])
        a = discharge.assess("lab:cite", self.lab)
        self.assertTrue(a["dischargeable"], a)
        self.assertEqual(a["inputs"][0]["status"], "cited")
        for item, why in (("bib:AW21#Lemma 2.1", "says partial"),
                          ("bib:AW21#Theorem 9.9", "no card of AW21 at Theorem 9.9"),
                          ("bib:AW21", "no pinpoint"),
                          ("bib:Zz99#Theorem 1", "no card of Zz99")):
            with self.subTest(item=item):
                self.claim("cite2", "proved-modulo", [item])
                registry.clear_cache()
                a = discharge.assess("lab:cite2", self.lab)
                self.assertFalse(a["dischargeable"])
                self.assertIn(why, " ".join(a["problems"]))
        discharge.apply("lab:cite", self.lab, date="2026-11-27")
        c = self.lab_rec("cite")
        self.assertEqual(c.history[0], "2026-11-27 | proved | discharged: inputs "
                                       "bib:AW21#Theorem 3.6 cited, lab:in-a proved")
        self.lab_clean()

    def test_a_notation_only_definition_counts(self):
        self.claim("usesdef", "proved-modulo", ["lab:defn-n"])
        a = discharge.assess("lab:usesdef", self.lab)
        self.assertTrue(a["dischargeable"], a)
        self.assertEqual(a["inputs"][0]["status"], "notation-only")

    def test_cross_namespace_inputs_through_the_federation(self):
        self.claim("x", "proved-modulo", ["s1:GEO-1"])
        self.claim("y", "proved-modulo", ["s1:N1", "s1:GEO-2"])   # alias; an open input
        self.assertTrue(discharge.assess("lab:x", self.lab)["dischargeable"])
        a = discharge.assess("lab:y", self.lab)
        self.assertEqual(a["inputs"][0]["id"], "s1:GEO-1")
        self.assertIn("s1:GEO-2 is open", " ".join(a["problems"]))
        rc, out, err = self.run_cli("--all")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.lab_rec("x").status, "proved")
        self.assertEqual(self.lab_rec("y").status, "proved-modulo")
        # --input from the notebook reaches the lab record that names it
        self.obj("GEO-2", "proved")
        rc, out, err = self.run_cli("--input", "GEO-2", "--dry-run", repo=self.nb)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("lab:y  proved-modulo  dischargeable", out)

    def test_notebook_profile_discharges_with_its_own_rows(self):
        self.obj("GEO-3", "proved-modulo", ["GEO-1", "lab:in-a", "bib:AW21#Theorem 3.6"])
        self.obj("GEO-4", "proved-modulo", ["GEO-2"])
        rc, out, err = self.run_cli("--all", "--dry-run", repo=self.nb)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("s1:GEO-3  proved-modulo  dischargeable", out)
        self.assertIn("s1:GEO-4  proved-modulo  held", out)
        self.assertEqual(self.nb_rec("GEO-3")["status"], "proved-modulo")   # dry run
        rc, out, err = self.run_cli("--all", repo=self.nb)
        self.assertEqual(rc, 0, out + err)
        v = self.nb_rec("GEO-3")
        self.assertEqual(v["status"], "proved")
        self.assertNotIn("modulo", v)
        self.assertEqual(schema.evidence_cells(v["evidence"][-1])[:3],
                         ("discharge", "s1:GEO-1, lab:in-a, bib:AW21#Theorem 3.6", "proved"))
        self.assertTrue(v["history"][0].endswith(
            "| proved | discharged: inputs s1:GEO-1 proved, lab:in-a proved, "
            "bib:AW21#Theorem 3.6 cited"), v["history"][0])
        self.assertEqual(self.nb_rec("GEO-4")["status"], "proved-modulo")
        kb = s1kb.load_kb(self.nb)
        s1kb.run_check(kb)
        self.assertEqual(kb.errors, [])
        with self.assertRaises(ValueError):
            s1kb.discharge(self.nb, "GEO-4")

    def test_modulo_edges_reach_across_namespaces(self):
        from registry.core import graph
        self.obj("GEO-5", "proved-modulo", ["lab:in-a"])
        self.claim("z", "proved-modulo", ["lab:in-a"])
        registry.clear_cache()
        got = {e["from"] for e in graph.walk("lab:in-a", self.lab, reverse=True,
                                             rels=graph.DEP_RELS + ("modulo",))}
        self.assertEqual(got, {"s1:GEO-5", "lab:z", "lab:mid"})

    # -- the grounds gate ----------------------------------------------------
    def test_established_now_holds_a_proved_input_to_its_current_statement(self):
        # #133: the decision table's conclude step reads inputs through this
        from unittest import mock
        from registry.core import stale
        a = discharge.established_now("lab:in-a", "lab", str(self.lab))
        self.assertTrue(a["established"], a)
        self.assertFalse(discharge.established_now("lab:mid", "lab", str(self.lab))
                         ["established"])
        self.assertTrue(discharge.established_now("lab:defn-n", "lab", str(self.lab))
                        ["established"])
        hit = [{"kind": "stale", "id": "in-a", "hash": "new", "pass_hash": "old"}]
        with mock.patch.object(stale, "reviews_root", return_value=self.lib), \
                mock.patch.object(stale, "find", return_value=hit) as find:
            a = discharge.established_now("lab:in-a", "lab", str(self.lab))
        self.assertFalse(a["established"])
        self.assertIn("stale", a["why"])
        self.assertEqual(find.call_args[0][2], {"in-a"})

    def test_check_grounds_on_discharge_grounds(self):
        ok = {"input": "lab:a", "id": "lab:a", "status": "proved"}
        cases = (({"basis": "discharge", "modulo": ["lab:a"], "inputs": [ok]}, "proved", True),
                 ({"basis": "discharge", "modulo": ["lab:a"], "inputs": [ok]},
                  "proved-modulo", False),
                 ({"basis": "discharge", "modulo": [], "inputs": []}, "proved", False),
                 ({"basis": "discharge", "modulo": ["lab:a", "lab:b"], "inputs": [ok]},
                  "proved", False),
                 ({"basis": "discharge", "modulo": ["lab:a"],
                   "inputs": [dict(ok, status="proved-modulo")]}, "proved", False),
                 ({"basis": "discharge", "modulo": ["lab:a"],
                   "inputs": [dict(ok, status="cited")]}, "proved", False))   # not a bib:
        for g, status, want in cases:
            with self.subTest(g=g, status=status):
                self.assertEqual(grounds.check_grounds(status, g)[0], want)

    def test_proof_grounds_for_proved_with_open_inputs_still_refused(self):
        rows = [{"verdict": "CONFIRMED", "run_id": "r" + r, "statement_hash": "h",
                 "grader_role": "rigor-reviewer", "ref": "x/%s.md" % r} for r in "AB"]
        g = {"basis": "proof", "producer_role": "prover", "verdicts": rows,
             "modulo": ["lab:a"]}
        ok, why = grounds.check_grounds("proved", g)
        self.assertFalse(ok)
        self.assertIn("proved with open inputs is proved-modulo", " ".join(why))
        dis = [{"input": "lab:a", "id": "lab:a", "status": "proved"}]
        self.assertTrue(grounds.check_grounds("proved", dict(g, discharge=dis))[0])
        self.assertFalse(grounds.check_grounds(
            "proved", dict(g, discharge=[dict(dis[0], status="sketch")]))[0])

    def test_set_status_refuses_proved_on_the_modulo_pass_while_inputs_are_open(self):
        p = self.claim("pm", "proved-modulo", ["lab:mid"])
        before = p.read_bytes()
        h = fsl.statement_hash(self.lab, "lab:pm")
        rows = [{"verdict": "CONFIRMED", "run_id": "rv-%s-pm" % r.lower(),
                 "statement_hash": h, "grader_role": "rigor-reviewer",
                 "ref": "reviews/pm/%s.md" % r} for r in "AB"]
        g = {"basis": "proof", "producer_role": "prover", "verdicts": rows}
        for grounds_, why in ((g, "is a discharge"),
                              ({"basis": "discharge"}, "cannot be discharged"),
                              (dict(g, discharge=[{"input": "lab:mid", "id": "lab:mid",
                                                   "status": "proved"}]),
                               "cannot be discharged")):    # the caller's word is not taken
            with self.subTest(why=why):
                with self.assertRaises(fsl.Refused) as cm:
                    fsl.set_status(self.lab, "lab:pm", "proved", grounds_)
                self.assertIn(why, str(cm.exception))
                self.assertEqual(p.read_bytes(), before)
        # once the input is proved, the discharge goes through set_status too
        self.claim("mid", "proved")
        fsl.set_status(self.lab, "lab:pm", "proved", {"basis": "discharge"}, date="2026-11-27")
        c = self.lab_rec("pm")
        self.assertEqual((c.status, c.history[0]),
                         ("proved", "2026-11-27 | proved | discharged: inputs lab:mid proved"))

    def test_cli_dry_run_writes_nothing_and_needs_a_selection(self):
        p = self.claim("pm", "proved-modulo", ["lab:in-a"])
        before = p.read_bytes()
        rc, out, err = self.run_cli("--all", "--dry-run")
        self.assertEqual(rc, 0, err)
        self.assertIn("dry run: nothing written", out)
        self.assertIn("lab:pm  proved-modulo  dischargeable", out)
        self.assertEqual(p.read_bytes(), before)
        rc, _out, err = self.run_cli()
        self.assertEqual(rc, 2)
        rc, out, _err = self.run_cli("--all", "--dry-run", "--json")
        got = {i["id"]: i["dischargeable"] for i in json.loads(out)["items"]}
        self.assertEqual(got["lab:pm"], True)


if __name__ == "__main__":
    unittest.main()
