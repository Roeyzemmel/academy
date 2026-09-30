"""notebook.py: objects, directions, attempts, journal, scaffold, status; and inbox.py."""

import json
import os
import unittest

from _fixtures import Workspace, write, record
import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402
import inbox  # noqa: E402
import notebook  # noqa: E402

DIRECTION = """---
id: D-1
kind: direction
title: "A program"
statement: "x"
lifecycle: active
---

## Program

Text.

## Questions

<!-- one bullet per question object:
- s9:<id> — one line -->
- s9:Q-1 — first question
- Q-2 — second question, bare id
- s9:Q-9 — not an object yet

## Candidate claims

- s9:C-1 — a claim already proved
- s9:C-2 — a sketch
- lab:ew-check — an experiment claim of the lab

## Falsifiers

- s9:C-2 — the smallest case
"""


class NotebookTests(Workspace):
    def setUp(self):
        super().setUp()
        self.nb = notebook.Notebook(self.R)

    def test_new_object_follows_the_schema(self):
        path = self.nb.new_object("conjecture", "s9:G-1", "Wider class", "All X are Y.",
                                  bears_on=["lab:ew-check"], falsifier="the smallest X",
                                  tags=["generalization"])
        text = rs.read_text(path)
        meta, body = ac.read_frontmatter(text.split("history:")[0] + "---\n")
        self.assertEqual((meta["id"], meta["kind"], meta["status"], meta["bears_on"],
                          meta["lifecycle"], meta["domain"]),
                         ("G-1", "conjecture", "conjectured", ["lab:ew-check"], "active",
                          "test-domain"))
        self.assertIn("## Falsifier\n\nthe smallest X", text)
        self.assertTrue(path.replace("\\", "/").endswith("objects/conjecture/G-1.md"))

    def test_status_rules_for_new_objects(self):
        with self.assertRaises(ac.AcademyError):
            self.nb.new_object("claim", "C-9", "t", status="proved")
        with self.assertRaises(ac.AcademyError):
            self.nb.new_object("definition", "D-9", "t", status="open")
        p = self.nb.new_object("definition", "DEF-1", "A definition", "Let X be...")
        self.assertEqual(rs.frontmatter_field(rs.read_text(p), "status"), (False, None))
        self.assertNotIn("## Falsifier", rs.read_text(p))
        p = self.nb.new_object("claim", "C-8", "t")
        self.assertEqual(rs.frontmatter_field(rs.read_text(p), "status")[1], "open")
        with self.assertRaises(ac.AcademyError):
            self.nb.new_object("claim", "C-8", "again")
        with self.assertRaises(ac.AcademyError):
            self.nb.new_object("theorem", "T-1", "bad kind")

    def test_direction_and_next(self):
        write(os.path.join(self.R, "objects", "direction", "D-1.md"), DIRECTION)
        write(os.path.join(self.R, "objects", "question", "Q-1.md"),
              record("proved", "Q-1", "question"))
        write(os.path.join(self.R, "objects", "question", "Q-2.md"),
              record("open", "Q-2", "question"))
        write(os.path.join(self.R, "objects", "claim", "C-1.md"), record("proved", "C-1"))
        write(os.path.join(self.R, "objects", "claim", "C-2.md"), record("sketch", "C-2"))
        d, items = self.nb.direction("s9:D-1")
        refs = [(i["section"], i["ref"]) for i in items]
        self.assertNotIn(("Questions", "s9:<id>"), refs)            # comments are skipped
        self.assertEqual(len([r for r in refs if r[0] == "Questions"]), 3)
        self.assertIn(("Candidate claims", "lab:ew-check"), refs)
        nxt = [i["ref"] for i in self.nb.next_items("D-1")]
        self.assertEqual(nxt, ["s9:Q-2", "s9:Q-9", "s9:C-2"])
        self.assertEqual([i["ref"] for i in self.nb.next_items("D-1", 1)], ["s9:Q-2"])

    def test_attempts_are_numbered_and_kept(self):
        p1, n1 = self.nb.attempt_path("s9:C-1", create=True)
        p2, n2 = self.nb.attempt_path("C-1", create=True)
        self.assertEqual((n1, n2), (1, 2))
        self.assertTrue(os.path.isfile(p1) and os.path.isfile(p2))
        self.assertEqual(rs.frontmatter_field(rs.read_text(p2), "outcome")[1], "in-progress")
        self.assertEqual(rs.frontmatter_field(rs.read_text(p2), "object")[1], "s9:C-1")

    def test_journal(self):
        p = self.nb.journal_path("2026-09-28", create=True)
        self.assertIn("# Journal 2026-09-28", rs.read_text(p))
        with self.assertRaises(ac.AcademyError):
            self.nb.journal_path("yesterday")

    def test_scaffold_never_overwrites_and_skips_templates(self):
        target = os.path.join(self.tmp, "fresh")
        made = notebook.scaffold(target)
        rels = sorted(os.path.relpath(m, target).replace("\\", "/") for m in made)
        for kind in rs.OBJECT_KINDS:
            self.assertIn("objects/%s/.gitkeep" % kind, rels)
        for d in ("proofs", "journal", "audits", "views"):
            self.assertIn("%s/.gitkeep" % d, rels)
        self.assertIn("README.md", rels)
        self.assertFalse(any(r.startswith("_templates") for r in rels))
        write(os.path.join(target, "README.md"), "mine")
        self.assertEqual(notebook.scaffold(target), [])
        self.assertEqual(rs.read_text(os.path.join(target, "README.md")), "mine")

    def test_ls_reads_legacy_folders_and_status(self):
        write(os.path.join(self.R, "objects", "claim", "C-1.md"), record("proved", "C-1"))
        write(os.path.join(self.R, "claims", "OLD-1.md"), record("Not settled", "OLD-1"))
        refs = {o["ref"]: o["status"] for o in self.nb.objects()}
        self.assertEqual(refs, {"s9:C-1": "proved", "s9:OLD-1": "Not settled"})
        st = self.nb.status()
        self.assertEqual(st["instance"], "researcher@t")
        rc, out, _ = self.run_script("notebook.py", "ls", "--status", "proved", "--json")
        self.assertEqual([o["ref"] for o in json.loads(out)], ["s9:C-1"])

    def test_outside_a_researcher_home(self):
        rc, _, err = self.run_script("notebook.py", "ls", cwd=self.L)
        self.assertEqual(rc, 2)
        self.assertIn("Researcher home", err)


def ticket(board, inst, tid, status="open", kind="prove", priority="normal", agenda=None):
    meta = {"id": tid, "title": "t " + tid, "kind": kind, "from": "author@x", "to": inst,
            "status": status, "priority": priority, "ask": "a", "deliverable": "d",
            "refs": [], "agenda": agenda, "blocks": [], "waiting_on": [],
            "budget": {"runs": 1, "max_model": "sonnet"}, "packets": [],
            "created": "2026-09-28", "updated": "2026-09-28"}
    return write(os.path.join(board, inst, ac.ticket_filename(tid, meta["title"])),
                 ac.new_ticket(meta))


class InboxTests(Workspace):
    def test_order_route_and_cap(self):
        inst = "researcher@t"
        ticket(self.B, inst, "T-0001", kind="other")
        ticket(self.B, inst, "T-0002", kind="review-experiment", priority="high")
        ticket(self.B, inst, "T-0003", kind="prove", agenda="paper:thm:main")
        ticket(self.B, inst, "T-0004", kind="decision")
        ticket(self.B, inst, "T-0005", status="closed")
        ticket(self.B, inst, "T-0006", status="accepted", kind="generalize", priority="low")
        rc, out, _ = self.run_script("inbox.py", "--json")
        data = json.loads(out)
        taken = data["take"]
        self.assertEqual([t["id"] for t in taken], ["T-0002", "T-0003", "T-0001"])
        self.assertEqual([t["route"]["target"] for t in taken],
                         ["researcher:review-experiment", "researcher:prove",
                          "lead-researcher"])
        self.assertEqual((data["instance"], len(data["take"]), data["remaining"]),
                         (inst, 3, 2))

    def test_final_to_routes_to_the_relay(self):
        self.assertEqual(inbox.route({"kind": "research", "final_to": "scientist"})["target"],
                         "experiment-spec")
        self.assertEqual(inbox.route({"kind": "cite", "final_to": "expert"})["target"],
                         "lit-request")
        self.assertEqual(inbox.route({"kind": "question", "final_to": "author"})["target"],
                         "lit-request")
        self.assertEqual(inbox.route({"kind": "prove", "final_to": "researcher"})["target"],
                         "researcher:prove")

    def relay_parent(self, child_status, waiting=None, final_to="scientist"):
        inst = "researcher@t"
        for tid, frm, to, status, extra in (
                ("T-0002", inst, "scientist@t", child_status, {"parent": "T-0001"}),
                ("T-0001", "expert@t", inst, "blocked",
                 {"waiting_on": waiting or ["T-0002"]})):
            meta = {"id": tid, "title": "t " + tid, "kind": "research", "from": frm,
                    "to": to, "status": status, "priority": "normal", "ask": "a",
                    "deliverable": "d", "refs": [], "blocks": [], "waiting_on": [],
                    "final_to": final_to, "budget": {"runs": 1, "max_model": "sonnet"},
                    "packets": [], "created": "2026-09-28", "updated": "2026-09-28"}
            meta.update(extra)
            if status in ("delivered", "closed"):
                meta["result"] = "done"
            write(os.path.join(self.B, to, ac.ticket_filename(tid, meta["title"])),
                  ac.new_ticket(meta))

    def test_return_leg_goes_back_to_the_relay(self):
        self.relay_parent("delivered")
        rc, out, _ = self.run_script("inbox.py", "--json")
        rows = json.loads(out)["take"]
        self.assertEqual([(r["id"], r["route"]["target"], r["return"]) for r in rows],
                         [("T-0001", "experiment-spec", True)])

    def test_return_leg_toward_the_expert_goes_to_lit_request(self):
        self.relay_parent("closed", final_to="expert")
        rc, out, _ = self.run_script("inbox.py", "--json")
        rows = json.loads(out)["take"]
        self.assertEqual([(r["id"], r["route"]["target"], r["return"]) for r in rows],
                         [("T-0001", "lit-request", True)])

    def test_blocked_parent_with_open_child_is_not_taken(self):
        self.relay_parent("in-progress")
        rc, out, _ = self.run_script("inbox.py", "--json")
        self.assertEqual(json.loads(out)["take"], [])

    def test_blocked_parent_waiting_on_human_is_not_taken(self):
        self.relay_parent("delivered", waiting=["T-0002", "human"])
        rc, out, _ = self.run_script("inbox.py", "--json")
        self.assertEqual(json.loads(out)["take"], [])

    def test_ordinary_rows_carry_return_false(self):
        ticket(self.B, "researcher@t", "T-0003", kind="prove")
        rc, out, _ = self.run_script("inbox.py", "--json")
        self.assertEqual([r["return"] for r in json.loads(out)["take"]], [False])

    def test_empty_inbox(self):
        rc, out, _ = self.run_script("inbox.py")
        self.assertEqual(rc, 1)
        self.assertIn("empty", out)


if __name__ == "__main__":
    unittest.main()
