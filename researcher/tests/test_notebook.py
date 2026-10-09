"""notebook.py: objects, directions, attempts, journal, scaffold, status; and inbox.py."""

import json
import os
import sys
import unittest

from _fixtures import Workspace, write, record
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "academy", "lib"))
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


APPROACH = """---
id: AP-1
kind: approach
title: "A mechanism"
statement: "x"
target: C-9
lifecycle: {lc}
{extra}history:
{hist}---

## Mechanism
"""


def approach_text(lc="active", extra="", hist=None):
    hist = hist or ['  - "2026-09-30 | %s | created"\n' % lc]
    return APPROACH.format(lc=lc, extra=extra, hist="".join(hist))


def set_refs(board, tid, refs, **fields):
    path = ac.find_ticket(board, tid)
    meta, body = ac.read_frontmatter(rs.read_text(path))
    meta["refs"] = refs
    meta.update(fields)
    write(path, ac.write_frontmatter(meta, body))


class ApproachTests(Workspace):
    def setUp(self):
        super().setUp()
        self.nb = notebook.Notebook(self.R)

    def put_approach(self, aid="AP-1", lc="active", **kw):
        path = os.path.join(self.R, "objects", "approach", aid + ".md")
        write(path, approach_text(lc, **kw).replace("AP-1", aid))
        return path

    def put_direction(self, did="D-1", approach="AP-1"):
        text = DIRECTION.replace("id: D-1", "id: %s" % did).replace(
            "lifecycle: active\n", "lifecycle: active\napproach: %s\n" % approach, 1)
        write(os.path.join(self.R, "objects", "direction", did + ".md"), text)
        write(os.path.join(self.R, "objects", "question", "Q-2.md"), record("open", "Q-2", "question"))

    def test_approach_kind_parses(self):
        self.assertIn("approach", rs.OBJECT_KINDS)
        path = self.nb.new_object("approach", "s9:AP-2", "Mechanism two", "One line.",
                                  target="C-9")
        a = self.nb.approach("AP-2")
        self.assertEqual((a["kind"], a["lifecycle"], a["target"], a["status"]),
                         ("approach", "active", "C-9", None))
        self.assertTrue(path.replace("\\", "/").endswith("objects/approach/AP-2.md"))
        self.assertEqual(self.nb.approach_problems("AP-2"), [])
        with self.assertRaises(ac.AcademyError):
            self.nb.new_object("approach", "AP-3", "no target")
        with self.assertRaises(ac.AcademyError):
            self.nb.new_object("approach", "AP-4", "t", status="open", target="C-9")

    def test_direction_carries_an_optional_approach(self):
        p = self.nb.new_object("direction", "D-7", "Program", approach="s9:AP-2")
        self.assertEqual(self.nb.find("D-7")["approach"], "AP-2")
        p2 = self.nb.new_object("direction", "D-8", "Program")
        self.assertNotIn("approach:", rs.read_text(p2))
        self.assertIsNone(self.nb.find("D-8")["approach"])

    def test_membership_is_computed_from_directions(self):
        self.put_approach("AP-1")
        self.put_approach("AP-2")
        self.put_direction("D-1", "s9:AP-1")
        self.put_direction("D-2", "AP-2")
        self.put_direction("D-3", "AP-1")
        self.assertEqual(sorted(m["id"] for m in self.nb.approach_members("AP-1")),
                         ["D-1", "D-3"])
        self.assertEqual([m["id"] for m in self.nb.approach_members("s9:AP-2")], ["D-2"])
        rc, out, _ = self.run_script("notebook.py", "approach", "show", "AP-1", "--json")
        self.assertEqual(json.loads(out)["members"], ["s9:D-1", "s9:D-3"])

    # -- P1: one approach per direction, a bad reference is loud -----------------------
    def test_next_skips_blocked_approaches(self):
        self.put_approach("AP-1")
        self.put_direction("D-1", "AP-1")
        self.assertTrue(self.nb.next_items("D-1"))
        self.nb.set_approach("AP-1", "blocked", blocked_by="C-8", reopen_if="a new invariant")
        self.assertEqual(self.nb.next_items("D-1"), [])
        rc, out, _ = self.run_script("notebook.py", "next", "D-1")
        self.assertEqual(rc, 1)
        self.assertIn("is blocked (C-8", out)
        self.nb.set_approach("AP-1", "active", note="uses the new invariant I")
        self.assertTrue(self.nb.next_items("D-1"))

    def test_only_an_active_approach_gives_work(self):
        self.put_approach("AP-1")
        self.put_direction("D-1", "AP-1")
        for lc, word in (("dropped", "dropped"), ("delivered", "nothing new")):
            self.nb.set_approach("AP-1", lc, note="because")
            self.assertEqual(self.nb.next_items("D-1"), [], lc)
            rc, out, _ = self.run_script("notebook.py", "next", "D-1")
            self.assertEqual(rc, 1)
            self.assertIn(word, out)
            self.nb.set_approach("AP-1", "active", note="back again")
            self.assertTrue(self.nb.next_items("D-1"))

    def test_a_bad_approach_reference_is_a_problem_and_next_fails(self):
        self.put_approach("AP-1")
        self.put_approach("AP-2")
        write(os.path.join(self.R, "objects", "claim", "C-9.md"), record("open", "C-9"))
        bad = {"D-1": "[AP-1, AP-2]", "D-2": "AP-1, AP-2", "D-3": "AP-99", "D-4": "C-9",
               "D-5": "lab:AP-1"}
        for did, val in bad.items():
            self.put_direction(did, val)
        self.put_direction("D-6", "AP-2")
        probs = self.nb.direction_problems()
        self.assertEqual(len(probs), 5, probs)
        self.assertTrue(any("D-1" in p and "single" in p for p in probs), probs)
        self.assertTrue(any("D-3" in p and "does not exist" in p for p in probs), probs)
        self.assertTrue(any("D-4" in p and "not an approach" in p for p in probs), probs)
        self.assertTrue(any("D-5" in p and "another notebook" in p for p in probs), probs)
        self.assertEqual(self.nb.approach_problems("AP-1"), [])      # the approach alone is fine
        self.assertEqual(len(self.nb.approach_problems()), 5)        # the whole check sees them
        rc, out, _ = self.run_script("notebook.py", "approach", "check")
        self.assertEqual(rc, 2)
        for did in bad:
            with self.assertRaises(ac.AcademyError, msg=did):
                self.nb.next_items(did)
            rc, _, err = self.run_script("notebook.py", "next", did)
            self.assertEqual(rc, 2, did)
        self.assertTrue(self.nb.next_items("D-6"))

    # -- P4/P5: blocking and reopening rules -----------------------------------------
    def test_blocked_without_blocked_by_fails(self):
        self.put_approach("AP-1")
        with self.assertRaises(ac.AcademyError):
            self.nb.set_approach("AP-1", "blocked", reopen_if="x")
        with self.assertRaises(ac.AcademyError):
            self.nb.set_approach("AP-1", "blocked", blocked_by="C-8")
        self.assertEqual(self.nb.approach("AP-1")["lifecycle"], "active")   # nothing written
        # a hand-edited file is caught by the check
        write(os.path.join(self.R, "objects", "approach", "AP-5.md"),
              approach_text("blocked").replace("AP-1", "AP-5"))
        probs = self.nb.approach_problems("AP-5")
        self.assertTrue(any("blocked without blocked_by" in p for p in probs), probs)
        rc, out, _ = self.run_script("notebook.py", "approach", "check")
        self.assertEqual(rc, 2)

    def test_blocked_by_is_a_registry_id_other_than_the_target(self):
        self.put_approach("AP-1")                                   # target C-9
        for bad in ("free text here", "C-9", "s9:C-9", "AP-1", "two words"):
            with self.assertRaises(ac.AcademyError, msg=bad):
                self.nb.set_approach("AP-1", "blocked", blocked_by=bad, reopen_if="x")
        self.nb.set_approach("AP-1", "blocked", blocked_by="paper:lem:x", reopen_if="x y")
        self.assertEqual(self.nb.approach("AP-1")["blocked_by"], "paper:lem:x")
        # hand edits are caught too
        path = self.put_approach("AP-6", "blocked",
                                 extra="blocked_by: C-9\nreopen_if: x\n")
        self.assertTrue(any("target" in p for p in self.nb.approach_problems("AP-6")))
        self.put_approach("AP-7", "blocked", extra="blocked_by: free text\nreopen_if: x\n")
        self.assertTrue(any("registry id" in p for p in self.nb.approach_problems("AP-7")))

    def test_the_dead_route_predicate_is_the_shared_one(self):
        self.put_approach("AP-8", "blocked", extra="blocked_by: C-8\n")
        self.assertFalse(ac.is_dead_route({"blocked_by": "C-8"}))
        self.assertTrue(any("without reopen_if" in p for p in self.nb.approach_problems("AP-8")))
        self.put_approach("AP-9", "blocked", extra="blocked_by: C-8\nreopen_if: new idea\n")
        self.assertEqual(self.nb.approach_problems("AP-9"), [])

    def test_reopening_needs_a_history_row(self):
        path = self.put_approach("AP-1")
        self.nb.set_approach("AP-1", "blocked", blocked_by="C-8", reopen_if="new invariant")
        a = self.nb.approach("AP-1")
        self.assertEqual((a["lifecycle"], a["blocked_by"]), ("blocked", "C-8"))
        for note in ("", "ok", "retry it"):                         # no mechanism named
            with self.assertRaises(ac.AcademyError, msg=note):
                self.nb.set_approach("AP-1", "active", note=note)
        # editing the lifecycle by hand leaves no history row: the check fails
        txt = rs.read_text(path).replace("lifecycle: blocked", "lifecycle: active", 1)
        txt = txt.replace("blocked_by: C-8\n", "").replace("reopen_if: new invariant\n", "")
        write(path, txt)
        probs = self.nb.approach_problems("AP-1")
        self.assertTrue(any("newest history row" in p for p in probs), probs)
        # a proper reopening writes the row
        write(path, rs.read_text(path).replace("lifecycle: active", "lifecycle: blocked", 1))
        self.nb.set_approach("AP-1", "blocked", blocked_by="C-8", reopen_if="new invariant")
        self.nb.set_approach("AP-1", "active", note="the invariant I of the lattice")
        self.assertEqual(self.nb.approach_problems("AP-1"), [])
        self.assertIn("| active | reopened: the invariant I of the lattice", rs.read_text(path))

    def test_blocked_to_dropped_is_ordinary_and_to_delivered_needs_a_note(self):
        self.put_approach("AP-1")
        self.put_approach("AP-2")
        for aid in ("AP-1", "AP-2"):
            self.nb.set_approach(aid, "blocked", blocked_by="C-8", reopen_if="a new invariant")
        self.nb.set_approach("AP-1", "dropped")                      # no mechanism, no note
        self.assertEqual(self.nb.approach("AP-1")["lifecycle"], "dropped")
        self.assertIsNone(self.nb.approach("AP-1")["blocked_by"])
        self.assertEqual(self.nb.approach_problems("AP-1"), [])
        with self.assertRaises(ac.AcademyError):
            self.nb.set_approach("AP-2", "delivered")
        self.nb.set_approach("AP-2", "delivered", note="the lemma C-8 was proved by other means")
        self.assertEqual(self.nb.approach_problems("AP-2"), [])
        with self.assertRaises(ac.AcademyError):                    # fields only with a block
            self.nb.set_approach("AP-2", "dropped", blocked_by="C-8")

    # -- P6: the history stays a block list, byte-stable -------------------------------
    def test_history_stays_a_block_list_and_round_trips(self):
        path = self.put_approach("AP-1", extra="domain: test-domain\n")
        before = rs.read_text(path)
        note = 'a, b [c] {d}: "e" | f # g'
        self.nb.set_approach("AP-1", "blocked", blocked_by="C-8",
                             reopen_if="a new invariant, [maybe]: one", note=note)
        txt = rs.read_text(path)
        head, body = txt.split("\n---\n", 1)
        lines = head.split("\n")
        self.assertIn("history:", lines)
        hist = lines[lines.index("history:") + 1:]
        self.assertEqual(len(hist), 2)                               # block list, newest first
        self.assertTrue(all(h.startswith("  - ") for h in hist), hist)
        self.assertIn("| blocked | " + note, json.loads(hist[0][4:]))
        self.assertEqual(hist[1], '  - "2026-09-30 | active | created"')    # older row untouched
        self.assertFalse(any(l.startswith("history: [") for l in lines))
        meta, _ = ac.read_frontmatter(txt)
        self.assertEqual(meta["reopen_if"], "a new invariant, [maybe]: one")
        self.assertEqual(meta["domain"], "test-domain")              # other keys untouched
        self.assertEqual(body, before.split("\n---\n", 1)[1])      # the body is byte-stable
        self.assertEqual(self.nb.approach_problems("AP-1"), [])
        # a second move keeps the first row as it was written
        self.nb.set_approach("AP-1", "active", note="the invariant I, [new]: found, really")
        txt2 = rs.read_text(path)
        self.assertIn(hist[0], txt2.split("\n"))
        self.assertIn(hist[1], txt2.split("\n"))
        self.assertNotIn("blocked_by", txt2)
        self.assertEqual(ac.read_frontmatter(txt2)[0]["lifecycle"], "active")
        self.assertEqual(self.nb.approach_problems("AP-1"), [])

    def test_a_legacy_inline_history_becomes_a_block_list(self):
        path = os.path.join(self.R, "objects", "approach", "AP-1.md")
        write(path, '---\nid: AP-1\nkind: approach\ntitle: "T"\ntarget: C-9\n'
                    'lifecycle: active\nhistory: ["2026-09-30 | active | created"]\n---\n\nB\n')
        self.nb.set_approach("AP-1", "dropped", note="no")
        txt = rs.read_text(path)
        self.assertIn('history:\n  - "2026-09-30 | dropped | no (lead-researcher)"\n'
                      '  - "2026-09-30 | active | created"\n---', txt.replace(
                          ac.today(), "2026-09-30"))
        self.assertEqual(self.nb.approach_problems("AP-1"), [])

    # -- S2, P7: seeding check and status ------------------------------------------------
    def test_campaign_check_counts_approaches_and_their_directions(self):
        rc, out, _ = self.run_script("notebook.py", "approach", "check", "--campaign", "C-9")
        self.assertEqual(rc, 2)
        self.assertIn("0 approach(es)", out)
        for i in range(1, 5):
            self.put_approach("AP-%d" % i)
        self.put_direction("D-1", "AP-1")
        self.put_direction("D-2", "AP-2")
        self.put_direction("D-3", "AP-3")                            # AP-4 has none
        rc, out, _ = self.run_script("notebook.py", "approach", "check", "--campaign", "s9:C-9")
        self.assertEqual(rc, 2)
        self.assertIn("AP-4: no direction", out)
        self.assertNotIn("AP-3: no direction", out)
        self.put_direction("D-4", "AP-4")
        rc, out, _ = self.run_script("notebook.py", "approach", "check", "--campaign", "C-9")
        self.assertEqual((rc, out), (0, ""))
        rc, out, _ = self.run_script("notebook.py", "approach", "check", "--campaign", "C-1")
        self.assertEqual(rc, 2)                                      # none aims at C-1

    def test_status_derives_waiting_on_decision_from_tickets(self):
        self.put_approach("AP-1")
        self.put_approach("AP-2")
        self.put_approach("AP-3", "dropped")
        self.put_direction("D-1", "AP-1")
        self.put_direction("D-2", "AP-2")
        ticket(self.B, "scientist@t", "T-0001")
        ticket(self.B, "expert@t", "T-0002", status="blocked")
        set_refs(self.B, "T-0001", ["s9:AP-1"])
        set_refs(self.B, "T-0002", ["s9:D-2"], waiting_on=["human"])
        store = ac.FileBoardStore(self.B)
        st = self.nb.approach_status(store)
        rows = {r["approach"]: r for r in st["approaches"]}
        self.assertEqual(rows["s9:AP-1"]["open_tickets"], ["T-0001"])
        self.assertFalse(rows["s9:AP-1"]["waiting_on_decision"])
        self.assertTrue(rows["s9:AP-2"]["waiting_on_decision"])
        self.assertEqual(rows["s9:AP-2"]["decision_tickets"], ["T-0002"])
        self.assertFalse(st["pause"])                                # AP-1 still has work
        set_refs(self.B, "T-0001", ["s9:AP-1"], status="blocked", waiting_on=["human"])
        self.assertTrue(self.nb.approach_status(store)["pause"])     # every active one waits
        rc, out, _ = self.run_script("notebook.py", "approach", "status", "--board", self.B)
        self.assertEqual(rc, 0)
        self.assertIn("s9:AP-2", out)
        self.assertIn("waiting-on-decision: yes", out)
        self.assertIn("PAUSE", out)
        rc, out, _ = self.run_script("notebook.py", "approach", "status", "--board", self.B,
                                     "--json")
        self.assertTrue(json.loads(out)["pause"])
        # a pending wait on another ticket is not a decision
        set_refs(self.B, "T-0001", ["s9:AP-1"], status="blocked", waiting_on=["T-0002"])
        self.assertFalse(self.nb.approach_status(store)["pause"])

    def test_status_tells_waiting_on_another_actor_from_pause(self):
        """WAITING (tickets out with another role's next actor) is not PAUSE (a human
        decision): academy/lib/workplan.py, from the tickets."""
        self.put_approach("AP-1")
        self.put_approach("AP-2")
        self.put_direction("D-1", "AP-1")
        self.put_direction("D-2", "AP-2")
        store = ac.FileBoardStore(self.B)
        st = self.nb.approach_status(store)
        self.assertEqual("ACTIVE", st["state"])                     # nothing out: work
        ticket(self.B, "scientist@t", "T-0001")
        ticket(self.B, "expert@t", "T-0002")
        set_refs(self.B, "T-0001", ["s9:AP-1"])
        set_refs(self.B, "T-0002", ["s9:D-2"])
        st = self.nb.approach_status(store)
        rows = {r["approach"]: r for r in st["approaches"]}
        self.assertEqual("WAITING", rows["s9:AP-1"]["state"])
        self.assertEqual(["T-0001"], rows["s9:AP-1"]["waiting_tickets"])
        self.assertEqual(("WAITING", False), (st["state"], st["pause"]))
        rc, out, _ = self.run_script("notebook.py", "approach", "status", "--board", self.B)
        self.assertIn("WAITING: every active approach waits", out)
        self.assertNotIn("PAUSE:", out)
        set_refs(self.B, "T-0002", ["s9:D-2"], status="blocked", waiting_on=["human"])
        rows = {r["approach"]: r for r in self.nb.approach_status(store)["approaches"]}
        self.assertEqual("PAUSE", rows["s9:AP-2"]["state"])
        self.assertEqual("WAITING", self.nb.approach_status(store)["state"])

    # -- P2, P3: tickets of an approach, through the store; moves ----------------------------
    def seed_tickets(self):
        self.put_approach("AP-1")
        self.put_direction("D-1", "AP-1")
        for tid, to in (("T-0001", "scientist@t"), ("T-0002", "researcher@t"),
                        ("T-0003", "scientist@t"), ("T-0004", "scientist@t")):
            ticket(self.B, to, tid)
        set_refs(self.B, "T-0001", ["s9:AP-1"])
        set_refs(self.B, "T-0002", ["s9:D-1"])
        set_refs(self.B, "T-0003", ["s9:C-1"])
        set_refs(self.B, "T-0004", ["s9:AP-1"], status="closed")

    def test_approach_tickets_on_a_file_board(self):
        self.seed_tickets()
        got = [t["id"] for t in self.nb.approach_tickets("AP-1", self.B)]
        self.assertEqual(got, ["T-0001", "T-0002"])
        rc, out, _ = self.run_script("notebook.py", "approach", "tickets", "AP-1",
                                     "--board", self.B, "--json")
        self.assertEqual([t["id"] for t in json.loads(out)], ["T-0001", "T-0002"])

    def test_approach_tickets_on_a_github_board(self):
        import board_store as bs
        self.seed_tickets()
        gh = bs.GithubBoardStore(bs.from_file_board(self.B, bs.MemoryTransport()), "o/r",
                                 lib=ac)
        got = self.nb.approach_tickets("AP-1", gh)
        self.assertEqual([t["id"] for t in got], ["T-0001", "T-0002"])
        self.assertEqual(got, self.nb.approach_tickets("AP-1", self.B))       # same as files
        self.nb.set_approach("AP-1", "blocked", blocked_by="C-8", reopen_if="x y")
        self.assertEqual([t["id"] for t in self.nb.held_tickets(gh)], ["T-0001", "T-0002"])

    def test_blocking_lists_the_moves_and_apply_makes_the_ones_it_may(self):
        self.seed_tickets()
        args = ("notebook.py", "approach", "set", "AP-1", "blocked", "--blocked-by", "C-8",
                "--reopen-if", "new invariant", "--board", self.B)
        rc, out, _ = self.run_script(*args)
        self.assertEqual(rc, 0, out)
        self.assertIn("transition T-0001 blocked --blocked-by C-8", out)
        self.assertIn("--as scientist@t", out)
        self.assertNotIn("tried: tried", out)
        self.assertNotIn("T-0003", out)
        self.assertEqual(ac.read_frontmatter(rs.read_text(ac.find_ticket(self.B, "T-0002")))[0]
                         ["status"], "open")                        # printed, not moved
        # an approach blocked again with --apply: the ticket addressed to this instance moves
        self.nb.set_approach("AP-1", "active", note="a new invariant found here")
        rc, out, err = self.run_script(*args, "--apply")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("T-0002 (researcher@t, open): moved to blocked", out)
        self.assertIn("transition T-0001 blocked", out)             # the scientist's stays printed
        meta, body = ac.read_frontmatter(rs.read_text(ac.find_ticket(self.B, "T-0002")))
        self.assertEqual((meta["status"], meta["blocked_by"], meta["reopen_if"]),
                         ("blocked", "C-8", "new invariant"))
        self.assertIn("tried: approach s9:AP-1 blocked by C-8", body)
        self.assertEqual(ac.validate_ticket(meta, body), [])
        # held: the scientist's ticket of the blocked approach is what dispatch must skip
        rc, out, _ = self.run_script("notebook.py", "approach", "tickets", "--held",
                                     "--board", self.B, "--json")
        self.assertEqual([t["id"] for t in json.loads(out)], ["T-0001"])

    def test_reopening_prints_and_applies_the_reopen_moves(self):
        self.seed_tickets()
        run = lambda *a: self.run_script("notebook.py", "approach", "set", "AP-1", *a,  # noqa: E731
                                         "--board", self.B, "--apply")
        rc, out, _ = run("blocked", "--blocked-by", "C-8", "--reopen-if", "new invariant")
        self.assertIn("T-0002 (researcher@t, open): moved to blocked", out)
        # T-0001 (scientist) is blocked by its receiver, as the printed command says
        set_refs(self.B, "T-0001", ["s9:AP-1"], status="blocked", blocked_by="C-8",
                 reopen_if="new invariant")
        # a ticket blocked by something else for the same approach is not reopened
        ticket(self.B, "scientist@t", "T-0005", status="blocked")
        set_refs(self.B, "T-0005", ["s9:AP-1"], blocked_by="C-7", reopen_if="other")
        rc, out, _ = run("active", "--note", "the invariant I of the lattice")
        self.assertEqual(rc, 0, out)
        self.assertIn("T-0002 (researcher@t, blocked): moved to accepted", out)
        self.assertIn("transition T-0001 accepted --reopen \"the invariant I of the lattice\" "
                      "--as scientist@t", out)
        self.assertNotIn("T-0005", out)
        meta, body = ac.read_frontmatter(rs.read_text(ac.find_ticket(self.B, "T-0002")))
        self.assertEqual(meta["status"], "accepted")
        self.assertNotIn("blocked_by", meta)
        self.assertIn("reopened: the invariant I of the lattice", body)


class CampaignCapsTests(unittest.TestCase):
    def test_required_caps(self):
        with self.assertRaises(ac.AcademyError):
            notebook.campaign_caps(None, 4)
        with self.assertRaises(ac.AcademyError):
            notebook.campaign_caps(3, None)
        with self.assertRaises(ac.AcademyError):
            notebook.campaign_caps(0, 4)
        self.assertEqual(notebook.campaign_caps(3, 4, env={})["runs"], 0)   # K = 0 by default

    def test_runs_need_a_profile_and_are_forced_to_zero_in_a_cloud(self):
        with self.assertRaises(ac.AcademyError):
            notebook.campaign_caps(3, 4, 2, env={})
        caps = notebook.campaign_caps(3, 4, 2, "remote-a", env={})
        self.assertEqual((caps["runs"], caps["profile"], caps["cloud"]), (2, "remote-a", False))
        for env, cloud in (({}, True), ({"CLAUDE_CODE_REMOTE": "true"}, False),
                           ({"ACADEMY_CLOUD": "1"}, False)):
            caps = notebook.campaign_caps(3, 4, 2, "remote-a", cloud, env)
            self.assertEqual((caps["runs"], caps["runs_forced_to_zero"], caps["cloud"]),
                             (0, True, True), env)

    def test_the_command(self):
        import subprocess
        import sys
        script = os.path.join(os.path.dirname(os.path.abspath(notebook.__file__)), "notebook.py")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("CLAUDE_CODE_REMOTE", None)
        r = subprocess.run([sys.executable, script, "campaign-check", "--rounds", "3",
                            "--agents", "4", "--runs", "2", "--profile", "remote-a", "--cloud"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("runs=0", r.stdout)
        self.assertIn("forced to 0", r.stdout)
        r = subprocess.run([sys.executable, script, "campaign-check", "--agents", "4"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--rounds is required", r.stderr)


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
