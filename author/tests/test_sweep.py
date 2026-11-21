"""sweep.py: the deterministic half of the machine-note sweep (#110, #98 point 1).

``plan`` inventories the notes, acts by kind (prov -> a move into the record, await -> retired
when its ticket ended with a result, human -> the human's list) and hands the rest to the
note-sweeper to judge; ``record`` caches what was judged and still open (signature ->
tickets -> their state), so the next sweep re-reads only files changed since the recorded
commit and re-judges only notes whose ticket moved or whose paragraph changed.
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fixtures import HAVE_GIT, SCRIPTS, Sandbox  # noqa: E402

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import _academy as ac  # noqa: E402
import machine_notes as mn  # noqa: E402
import sweep as sw  # noqa: E402

TODAY = "2026-11-21"

A_TEX = """\\section{A}

\\begin{lem}\\label{lem:a}
A lemma. \\Claude{is the constant sharp?}
\\end{lem}

\\begin{lem}\\label{lem:b}
B. \\Claude[prov]{T-0010: transcribed from the review}
\\end{lem}

C. \\Claude[await]{T-0020 awaits re-verification}

D. \\Claude[await]{T-0021 awaits the verify}

E. \\Claude[await]{T-0022 awaits the check}

F. \\Claude[await]{T-0023 awaits the lookup}

G. \\Claude[human]{which normalisation do you prefer?}

H. \\Claude[later]{an unknown kind}

I. \\Claude[await]{no ticket named here}
"""

B_TEX = """\\section{B}

\\begin{prop}\\label{prop:x}
X. \\Claude{T-0030: unverified step}
\\end{prop}
"""


def ticket(sb, tid, status, result="", updated="2026-11-20", to="expert@t"):
    lines = ["---", "id: %s" % tid, "title: t %s" % tid, "kind: verify", "from: author@t",
             "to: %s" % to, "status: %s" % status, "priority: normal", "ask: a",
             "deliverable: d", "budget: {runs: 1}", "created: 2026-11-01",
             "updated: %s" % updated]
    if result:
        lines.append("result: %s" % json.dumps(result))
    path = os.path.join(sb.board, to, "%s-t.md" % tid)
    sb.write(path, "\n".join(lines) + "\n---\n\n## Thread\n")
    return path


def git(home, *args):
    p = subprocess.run(["git", "-C", home, "-c", "user.name=t", "-c", "user.email=t@t"]
                       + list(args), capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout.strip()


@unittest.skipUnless(HAVE_GIT, "git is not installed")
class SweepBase(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.home = self.sb.home
        self.a = os.path.join(self.home, "sections", "a.tex")
        self.b = os.path.join(self.home, "sections", "b.tex")
        self.sb.write(self.a, A_TEX)
        self.sb.write(self.b, B_TEX)
        ticket(self.sb, "T-0010", "closed", "done")
        ticket(self.sb, "T-0020", "delivered", "CONFIRMED x2 (A, B)")
        ticket(self.sb, "T-0021", "delivered", "GAP in step 2 (A)")
        ticket(self.sb, "T-0022", "in-progress")
        ticket(self.sb, "T-0023", "rejected", "wrong route")
        ticket(self.sb, "T-0030", "open")
        self.sb.git_init(self.home)
        git(self.home, "add", "-A")
        git(self.home, "commit", "-q", "-m", "init")
        self.cfg = ac.load_config(self.home)
        self.store = ac.FileBoardStore(self.sb.board)

    def plan(self, **kw):
        kw.setdefault("today", TODAY)
        return sw.plan(self.home, self.cfg, self.store, **kw)

    def record(self, **kw):
        kw.setdefault("today", TODAY)
        return sw.record(self.home, self.cfg, self.store, **kw)

    def bodies(self, rows):
        return [r["text"] for r in rows]

    def commit_all(self, msg="edit"):
        git(self.home, "add", "-A")
        git(self.home, "commit", "-q", "--allow-empty", "-m", msg)


class PlanByKindTests(SweepBase):
    def test_first_sweep_is_full_and_acts_by_kind(self):
        p = self.plan()
        self.assertEqual(p["mode"], "full")
        self.assertIn("no sweep recorded", p["reason"])
        # await: T-0020 delivered with a positive result -> delete; T-0021 GAP -> pointer
        ret = {r["tickets"][0]: r for r in p["retire"]}
        self.assertEqual(sorted(ret), ["T-0020", "T-0021"])
        self.assertEqual(ret["T-0020"]["action"], "delete")
        self.assertEqual(ret["T-0020"]["replacement"], "")
        self.assertEqual(ret["T-0021"]["action"], "pointer")
        rep = ret["T-0021"]["replacement"]
        self.assertTrue(rep.startswith("\\Claude{T-0021 delivered: GAP"), rep)
        self.assertLessEqual(mn.estimate_lines(mn.scan(rep)[0]["body"]), 3)
        self.assertEqual(ret["T-0020"]["raw"], "\\Claude[await]{T-0020 awaits re-verification}")
        # prov: a move into the thread of the ticket it names
        (mv,) = p["move"]
        self.assertEqual(mv["record_to"], {"ticket": "T-0010"})
        self.assertEqual(mv["label"], "lem:b")
        # await on a live ticket waits; it is not handed to the agent
        self.assertEqual([w["tickets"] for w in p["waiting"]], [["T-0022"]])
        # the rest is judged: untyped, a rejected wait, a wait naming no ticket, human, unknown
        judged = {r["text"]: r["why"] for r in p["judge"]}
        self.assertIn("is the constant sharp?", judged)
        self.assertIn("T-0023 awaits the lookup", judged)
        self.assertIn("no ticket named here", judged)
        self.assertIn("which normalisation do you prefer?", judged)
        self.assertIn("an unknown kind", judged)
        self.assertIn("T-0030: unverified step", judged)
        self.assertEqual(self.bodies(p["human"]), ["which normalisation do you prefer?"])
        self.assertTrue(any("later" in a for a in p["anomalies"]))
        self.assertTrue(any("names no ticket" in a for a in p["anomalies"]))
        self.assertEqual(p["todo"], len(p["retire"]) + len(p["move"]) + len(p["judge"]))
        self.assertEqual(p["counts"]["notes"], 10)
        self.assertEqual(p["counts"]["by_kind"]["await"], 5)

    def test_a_delivered_ticket_without_a_result_still_waits(self):
        ticket(self.sb, "T-0020", "delivered", "")
        p = self.plan()
        self.assertIn(["T-0020"], [w["tickets"] for w in p["waiting"]])

    def test_a_prov_note_naming_no_ticket_goes_to_a_record_ticket_on_its_label(self):
        self.sb.write(self.b, B_TEX.replace("X. ", "X. \\Claude[prov]{from the old draft} "))
        p = self.plan()
        mv = [m for m in p["move"] if m["text"] == "from the old draft"][0]
        self.assertEqual(mv["record_to"], {"record_ticket": True, "agenda": "paper:prop:x"})

    def test_plan_is_written_for_record(self):
        self.plan()
        path = os.path.join(self.home, ".academy", "note-sweep-plan.json")
        self.assertTrue(os.path.isfile(path))
        with open(os.path.join(self.home, ".academy", ".gitignore")) as fh:
            self.assertEqual(fh.read().strip(), "*")


class CacheTests(SweepBase):
    def agent_pass(self, p, skip=()):
        """What the note-sweeper does with a plan: apply the retirements and moves, leave
        the judged notes open (except those in ``skip``, left unjudged)."""
        for path in (self.a, self.b):
            text = self.sb.read(path)
            for r in p["retire"] + p["move"]:
                if r["file"] == os.path.relpath(path, self.home).replace(os.sep, "/"):
                    text = text.replace(r["raw"], r.get("replacement", ""))
            self.sb.write(path, text)

    def test_record_caches_the_open_notes_and_the_next_sweep_has_nothing_to_do(self):
        p = self.plan()
        self.agent_pass(p)
        r = self.record()
        self.assertTrue(r["advanced"], r)
        self.assertEqual(r["pending"], [])
        self.assertGreaterEqual(r["cached"], len(p["judge"]) + len(p["waiting"]))
        self.assertEqual(r["narrowed"], 1)               # the GAP pointer the agent left
        self.commit_all()
        q = self.plan()
        self.assertEqual(q["mode"], "incremental")
        self.assertEqual(q["todo"], 0, q)
        self.assertTrue(q["recorded"])                     # nothing to do: recorded at once
        self.assertEqual(self.bodies(q["human"]), ["which normalisation do you prefer?"])

    def test_only_changed_files_are_inventoried(self):
        p = self.plan()
        self.agent_pass(p)
        self.record()
        self.commit_all()
        # a new note in b.tex: only b.tex is read again
        self.sb.write(self.b, B_TEX + "\nY. \\Claude{a new question}\n")
        q = self.plan()
        self.assertEqual(q["changed_files"], ["sections/b.tex"])
        self.assertEqual([(r["text"], r["why"]) for r in q["judge"]], [("a new question", "new")])

    def test_a_ticket_that_moves_brings_its_note_back_even_in_an_unchanged_file(self):
        p = self.plan()
        self.agent_pass(p)
        self.record()
        self.commit_all()
        ticket(self.sb, "T-0022", "delivered", "CONFIRMED", updated="2026-11-21")
        ticket(self.sb, "T-0030", "open", updated="2026-11-21")      # a thread line
        q = self.plan()
        self.assertEqual(q["changed_files"], [])
        self.assertEqual([(r["tickets"], r["action"]) for r in q["retire"]],
                         [(["T-0022"], "delete")])
        self.assertEqual([(r["text"], r["why"]) for r in q["judge"]],
                         [("T-0030: unverified step", "ticket moved")])

    def test_a_reply_next_to_a_note_brings_it_back(self):
        p = self.plan()
        self.agent_pass(p)
        self.record()
        self.commit_all()
        text = self.sb.read(self.a).replace("is the constant sharp?}",
                                            "is the constant sharp?} \\Ada{yes, by Lemma 3}")
        self.sb.write(self.a, text)
        q = self.plan()
        self.assertEqual([(r["text"], r["why"]) for r in q["judge"]],
                         [("is the constant sharp?", "context changed")])

    def test_limit_defers_and_the_commit_waits_until_the_backlog_is_done(self):
        p = self.plan(limit=2)
        self.assertEqual(p["todo"], 2)
        self.assertGreater(p["deferred"], 0)
        self.agent_pass(p)
        r = self.record()
        self.assertFalse(r["advanced"])
        self.assertIn("deferred", r["why"])
        self.commit_all()
        seen, advanced, rounds = set(), False, 0
        while not advanced and rounds < 10:
            rounds += 1
            q = self.plan(limit=2)
            self.assertEqual(q["mode"], "full")        # no recorded commit yet
            self.assertFalse(seen & {x["sig"] for x in q["judge"]})   # nothing judged twice
            seen.update(x["sig"] for x in q["retire"] + q["move"] + q["judge"])
            self.agent_pass(q)
            r = self.record()
            advanced = r["advanced"]
            self.assertEqual(advanced, not q["deferred"], r)
            self.commit_all()
        self.assertTrue(advanced)
        self.assertEqual(len(seen), len(p["retire"]) + len(p["move"]) + len(p["judge"])
                         + p["deferred"] - 2)
        q = self.plan()
        self.assertEqual((q["mode"], q["todo"]), ("incremental", 0))

    def test_unjudged_notes_stay_uncached(self):
        p = self.plan()
        self.agent_pass(p)
        sig = [r for r in p["judge"] if r["text"] == "is the constant sharp?"][0]["sig"]
        r = self.record(unjudged=[sig])
        self.assertFalse(r["advanced"])
        self.commit_all()
        q = self.plan()
        self.assertEqual([x["text"] for x in q["judge"]], ["is the constant sharp?"])

    def test_unapplied_moves_hold_the_commit(self):
        p = self.plan()
        r = self.record()                              # the agent applied nothing
        self.assertFalse(r["advanced"])
        self.assertEqual(len(r["pending"]), len(p["retire"]) + len(p["move"]))

    def test_max_age_rejudges_old_verdicts(self):
        p = self.plan()
        self.agent_pass(p)
        self.record(today="2026-10-01")
        self.commit_all()
        self.assertEqual(self.plan(max_age=60)["todo"], 0)
        q = self.plan(max_age=10, full=True)
        self.assertIn("is the constant sharp?", [x["text"] for x in q["judge"]])
        self.assertEqual({x["why"] for x in q["judge"]}, {"stale"})

    def test_full_reads_every_file_and_keeps_the_cache(self):
        p = self.plan()
        self.agent_pass(p)
        self.record()
        self.commit_all()
        st = sw.load_state(self.home)
        st["cache"] = {k: v for k, v in st["cache"].items() if v["file"] != "sections/b.tex"}
        sw.save_state(self.home, st)                  # b.tex's verdict lost
        self.assertEqual(self.plan()["todo"], 0)      # b.tex unchanged: not read
        q = self.plan(full=True)
        self.assertEqual([x["text"] for x in q["judge"]], ["T-0030: unverified step"])

    def test_a_lost_recorded_commit_falls_back_to_full(self):
        st = sw.load_state(self.home)
        st["commit"] = "0" * 40
        sw.save_state(self.home, st)
        p = self.plan()
        self.assertEqual(p["mode"], "full")
        self.assertIn("not found", p["reason"])


class InventoryAndCliTests(SweepBase):
    def test_inventory_counts(self):
        inv = sw.inventory(self.home, self.cfg)
        self.assertEqual(inv["notes"], 10)
        self.assertEqual(inv["by_kind"], {"untyped": 2, "prov": 1, "await": 5, "human": 1,
                                          "later": 1, "check": 0})
        self.assertEqual(inv["by_file"], {"sections/a.tex": 9, "sections/b.tex": 1})
        self.assertEqual(inv["naming_a_ticket"], 6)
        self.assertEqual(inv["over_max_lines"], 0)

    def test_cli_plan_json_and_text(self):
        env = dict(self.sb.env)
        base = [sys.executable, os.path.join(SCRIPTS, "sweep.py"), "--home", self.home,
                "--board", self.sb.board, "--today", TODAY]
        p = subprocess.run(base + ["plan", "--json"], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["mode"], "full")
        p = subprocess.run(base + ["plan"], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertRegex(p.stdout.splitlines()[0], r"^sweep: todo \d+ \(retire 2, move 1, "
                                                   r"judge \d+\)")
        p = subprocess.run(base + ["record"], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("not advanced", p.stdout)
        p = subprocess.run(base + ["inventory"], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("10 machine notes", p.stdout)

    def test_record_without_a_plan_is_an_error(self):
        with self.assertRaises(sw.SweepError):
            self.record()

    def test_not_a_git_repository_is_full(self):
        import shutil
        shutil.rmtree(os.path.join(self.home, ".git"))
        p = self.plan()
        self.assertEqual(p["mode"], "full")
        self.assertIn("not a git", p["reason"])
        self.assertFalse(p["recorded"])


def meta(tid, status, result="", kind="verify"):
    return (tid, {"id": tid, "status": status, "result": result, "kind": kind})


class AwaitDecisionTests(unittest.TestCase):
    """Review of 38e8803, findings 2 and 3: every ticket an await note names decides, and
    only a positive verdict (CONFIRMED / SOUND, nothing negative or conditional) deletes."""

    def d(self, metas, text="T-0001 awaits re-verification"):
        return sw.await_decision(text, metas)

    def test_every_named_ticket_must_have_ended_with_a_result(self):
        both = [meta("T-0001", "delivered", "CONFIRMED x2"), meta("T-0002", "closed", "SOUND")]
        self.assertEqual((self.d(both)["list"], self.d(both)["action"]), ("retire", "delete"))
        live = [meta("T-0001", "delivered", "CONFIRMED"), meta("T-0002", "in-progress")]
        self.assertEqual(self.d(live)["list"], "waiting")
        dead = [meta("T-0001", "rejected", "wrong route"), meta("T-0002", "open")]
        self.assertEqual(self.d(dead)["list"], "judge")
        self.assertIn("T-0001", self.d(dead)["detail"])
        self.assertEqual(self.d([meta("T-0001", "delivered", "CONFIRMED"), ("T-0009", None)])
                         ["list"], "judge")
        self.assertEqual(self.d([meta("T-0001", "closed", "")])["list"], "judge")
        self.assertEqual(self.d([meta("T-0001", "delivered", "")])["list"], "waiting")

    def test_a_pointer_names_the_negative_ticket(self):
        r = self.d([meta("T-0001", "delivered", "CONFIRMED x2"),
                    meta("T-0002", "delivered", "GAP in step 2")])
        self.assertEqual((r["list"], r["action"], r["ticket"]), ("retire", "pointer", "T-0002"))
        self.assertIn("GAP in step 2", r["result"])

    def test_only_a_positive_verdict_deletes(self):
        for res in ("CONFIRMED x2 (A, B)", "confirmed by both runs", "SOUND (A); SOUND (B)"):
            self.assertEqual(self.d([meta("T-0001", "delivered", res)])["action"], "delete", res)
        for res in ("a gap in step 2", "2 GAPs", "disproved by counterexamples",
                    "fails for n=3", "the lemma is false", "Not proved",
                    "proved modulo a citation",
                    "Complete attempt (attempt-3), modulo PL Schoenflies",
                    "SOUND MODULO the Tokarsky lemma", "CONFIRMED (A), PLAUSIBLE (B)",
                    "CONFIRMED but needs revision", "inconclusive", "CONFIRMED; unverified "
                    "step 3", "BROKEN", "an error in the index count", "partial: case 1 only"):
            r = self.d([meta("T-0001", "delivered", res)])
            self.assertEqual((r["list"], r.get("action")), ("retire", "pointer"), res)

    def test_a_result_with_no_verdict_or_the_wrong_kind_is_judged(self):
        r = self.d([meta("T-0001", "delivered", "verify ticket T-0005 filed", kind="prove")])
        self.assertEqual(r["list"], "judge")
        r = self.d([meta("T-0001", "delivered", "CONFIRMED", kind="prove")])
        self.assertEqual(r["list"], "judge")
        self.assertIn("prove", r["detail"])
        # a note that waits on something else than a verification takes any kind
        r = self.d([meta("T-0001", "delivered", "CONFIRMED: the pinpoint is p. 4", kind="cite")],
                   text="T-0001 awaits the citation")
        self.assertEqual(r["action"], "delete")


class ReviewFixTests(SweepBase):
    def test_a_note_naming_two_tickets_waits_on_the_live_one(self):
        self.sb.write(self.b, B_TEX + "\nZ. \\Claude[await]{T-0020 then T-0022}\n")
        p = self.plan()
        self.assertIn(["T-0020", "T-0022"], [w["tickets"] for w in p["waiting"]])
        self.assertNotIn(["T-0020", "T-0022"], [r["tickets"] for r in p["retire"]])

    def test_identical_notes_in_two_places_are_cached_apart(self):
        dup = "\\Claude{the same question}"
        self.sb.write(self.a, "One. %s\n\nTwo.\n" % dup)
        self.sb.write(self.b, "Other paragraph. %s\n" % dup)
        p = self.plan()
        self.assertEqual(len(p["judge"]), 2)
        self.assertTrue(self.record()["advanced"])
        self.commit_all()
        self.assertEqual(self.plan(full=True)["todo"], 0)

    def test_an_applied_move_of_one_of_two_identical_notes_is_applied(self):
        dup = "\\Claude[prov]{T-0010: transcribed}"
        self.sb.write(self.a, "One. %s\n" % dup)
        self.sb.write(self.b, "Two. %s\n" % dup)
        p = self.plan()
        self.assertEqual(len(p["move"]), 2)
        self.sb.write(self.a, "One.\n")
        r = self.record()
        self.assertEqual([x["file"] for x in r["pending"]], ["sections/b.tex"])
        self.sb.write(self.b, "Two.\n")
        self.plan()
        self.assertEqual(self.record()["pending"], [])

    def test_cached_verdicts_expire_after_notes_max_age(self):
        self.sb.write(self.a, "One. \\Claude{a question}\n")
        self.sb.write(self.b, "Two.\n")
        self.plan()
        self.record(today="2026-11-01")
        self.commit_all()
        q = self.plan()                                   # default 14 days
        self.assertEqual([(x["text"], x["why"]) for x in q["judge"]], [("a question", "stale")])
        self.sb.write_config(author=dict(self._author(), notes={"maxAge": 0}))
        self.cfg = ac.load_config(self.home)
        self.assertEqual(self.plan()["todo"], 0)          # 0: never

    def test_a_plan_that_was_never_recorded_is_said_so(self):
        self.plan()
        q = self.plan()
        self.assertTrue(any("not recorded" in w for w in q["warnings"]), q["warnings"])
        self.assertIn("WARNING", sw.summary(q))
        self.record()
        self.assertEqual(self.plan()["warnings"], [])

    def _author(self):
        with open(os.path.join(self.home, ".claude", "academy.json"), encoding="utf-8") as fh:
            return json.load(fh)["author"]


if __name__ == "__main__":
    unittest.main()
