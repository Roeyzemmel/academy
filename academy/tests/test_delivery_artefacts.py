"""#100 part 1 (the human's ruling, 2026-11-20): a delivered ticket needs a checkable
artefact for its kind (``ac.delivery_artefact``), ``inbox.py --check`` refuses a delivery
without one, and the status ``partial`` means "work done, deliverable not met"."""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import academy_common as ac  # noqa: E402

core = ac.inbox_core


def ticket(tid="T-0042", kind="prove", to="researcher@nb", frm="author@p", status="delivered",
           result="done", **kw):
    m = {"id": tid, "title": "t", "kind": kind, "from": frm, "to": to, "status": status,
         "priority": "normal", "ask": "a", "deliverable": "d", "refs": [], "blocks": [],
         "waiting_on": [], "budget": {"runs": 1}, "packets": [], "result": result,
         "created": "2026-11-20", "updated": "2026-11-20"}
    m.update(kw)
    return m


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def git(repo, *a):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", "-C", repo] + list(a), capture_output=True, text=True,
                          env=env, check=True).stdout


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acad-art-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.nb = os.path.join(self.root, "nb")
        self.lib = os.path.join(self.root, "library")
        self.lab = os.path.join(self.root, "lab")
        self.paper = os.path.join(self.root, "paper")
        for d in (self.nb, self.lib, self.lab, self.paper):
            os.makedirs(d)
        self.ws = {"_path": os.path.join(self.root, "workspace.json"),
                   "instances": {"researcher@nb": {"role": "researcher", "home": self.nb},
                                 "expert@x": {"role": "expert", "home": self.lib},
                                 "scientist@x": {"role": "scientist", "home": self.lab},
                                 "author@p": {"role": "author", "home": self.paper}}}

    def check(self, meta, body=None):
        return ac.delivery_artefact(meta, body, self.ws)


class ProveArtefact(Workspace):
    def test_an_attempt_named_in_the_result_that_exists(self):
        write(os.path.join(self.nb, "proofs", "GEO-3", "attempt-2.md"),
              "---\nobject: nb:GEO-3\noutcome: complete\n---\nproof\n")
        r = self.check(ticket(result="complete attempt proofs/GEO-3/attempt-2.md; verify T-0050"))
        self.assertTrue(r["ok"], r)
        self.assertIn("attempt-2.md", r["found"])

    def test_an_absolute_or_file_ref_path_with_colons_in_the_id(self):
        p = os.path.join(self.nb, "proofs", "paper:cor:x", "attempt-1.md")
        write(p, "---\noutcome: complete\n---\n")
        self.assertTrue(self.check(ticket(result="attempt %s complete; gaps: none" % p))["ok"])
        r = self.check(ticket(result="see refs",
                              refs=["file:researcher@nb/proofs/paper:cor:x/attempt-1.md"]))
        self.assertTrue(r["ok"], r)

    def test_no_attempt_named_is_missing(self):
        # T-0700: the clerk's "<title>: none (T-...)", nothing behind it
        r = self.check(ticket(result="T-0042: record the answers: none (T-0042)"))
        self.assertFalse(r["ok"])
        self.assertIn("proof attempt", r["need"])

    def test_a_named_attempt_that_does_not_exist_is_missing(self):
        r = self.check(ticket(result="attempt proofs/GEO-3/attempt-9.md complete"))
        self.assertFalse(r["ok"])
        self.assertIn("attempt-9.md", r["why"])

    def test_an_incomplete_or_failed_attempt_is_not_the_deliverable(self):
        for outcome in ("incomplete", "failed", "in-progress"):
            write(os.path.join(self.nb, "proofs", "GEO-3", "attempt-1.md"),
                  "---\noutcome: %s\n---\n" % outcome)
            r = self.check(ticket(result="attempt proofs/GEO-3/attempt-1.md %s" % outcome))
            self.assertFalse(r["ok"], outcome)
            self.assertIn(outcome, r["why"])

    def test_the_result_body_counts(self):
        write(os.path.join(self.nb, "proofs", "GEO-3", "attempt-1.md"), "no frontmatter\n")
        body = "\n## Ask\n\n## Result\n\nThe attempt is proofs/GEO-3/attempt-1.md.\n\n## Thread\n"
        self.assertTrue(self.check(ticket(result="done"), body)["ok"])

    def test_a_relay_parent_is_carried_by_its_child(self):
        r = self.check(ticket(to="expert@x", final_to="researcher", result="returned: T-0050"))
        self.assertTrue(r["ok"], r)
        self.assertIn("relay", r["why"])


class OtherKinds(Workspace):
    def test_verify_needs_a_pass_folder_with_decision_md(self):
        m = ticket(kind="verify", to="expert@x", frm="researcher@nb", result="CONFIRMED")
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(self.lib, "reviews", "nb", "GEO-3", "2026-11-20-T-0042", "A.md"))
        self.assertFalse(self.check(m)["ok"])                     # no decision.md yet
        write(os.path.join(self.lib, "reviews", "nb", "GEO-3", "2026-11-20-T-0042",
                           "decision.md"))
        r = self.check(m)
        self.assertTrue(r["ok"], r)
        # T-00421 is another ticket
        m2 = ticket(tid="T-0004", kind="verify", to="expert@x")
        write(os.path.join(self.lib, "reviews", "nb", "GEO-4", "2026-11-20-T-00040",
                           "decision.md"))
        self.assertFalse(self.check(m2)["ok"])

    def test_cite_needs_its_card(self):
        m = ticket(kind="cite", to="expert@x", result="Card cards/Mo06/theorem-2-6.md; P-0305")
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(self.lib, "cards", "Mo06", "theorem-2-6.md"), "card")
        self.assertTrue(self.check(m)["ok"])

    def test_experiment_needs_a_header_or_a_result(self):
        m = ticket(kind="experiment", to="scientist@x",
                   result="header experiments/2026-11-20_foo.py written")
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(self.lab, "experiments", "2026-11-20_foo.py"), "# header")
        self.assertTrue(self.check(m)["ok"])
        m = ticket(kind="test", to="scientist@x", result="results/foo/run.json: nothing found")
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(self.lab, "results", "foo", "run.json"), "{}")
        self.assertTrue(self.check(m)["ok"])

    def test_code_needs_a_commit_naming_the_ticket(self):
        git(self.root, "init", "-q", "-b", "main")
        write(os.path.join(self.root, "a.txt"), "a")
        git(self.root, "add", "a.txt")
        git(self.root, "commit", "-q", "-m", "base")
        m = ticket(kind="code", to="author@p", frm="author@p", result="fixed")
        self.assertFalse(self.check(m)["ok"])
        git(self.root, "checkout", "-q", "-b", "2026-11-20/x/author")
        write(os.path.join(self.root, "b.txt"), "b")
        git(self.root, "add", "b.txt")
        git(self.root, "commit", "-q", "-m", "T-00420: not this one")
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(self.root, "c.txt"), "c")
        git(self.root, "add", "c.txt")
        git(self.root, "commit", "-q", "-m", "T-0042: checkpoint")
        r = self.check(m)
        self.assertTrue(r["ok"], r)

    def test_a_code_ticket_outside_a_workspace_is_not_checked(self):
        r = ac.delivery_artefact(ticket(kind="write", to="author@p"), None, None)
        self.assertTrue(r["ok"])
        self.assertIn("not checked", r["why"])

    def test_kinds_without_an_artefact_and_unknown_kinds_pass(self):
        for kind in ("research", "question", "note", "lookup", "decision", "other",
                     "sweep", "no-such-kind"):
            self.assertTrue(self.check(ticket(kind=kind, result="answered"))["ok"], kind)

    def test_only_a_delivered_ticket_is_checked(self):
        for st in ("partial", "closed", "in-progress", "rejected"):
            self.assertTrue(self.check(ticket(status=st, result="nothing"))["ok"], st)


class ReviewOfDd0fcd1(Workspace):
    """The review against the real board: cite and experiment results as the workflows write
    them, deliveries with no artefact on purpose, hashes in prose."""

    def test_cite_resolves_the_card_from_the_key(self):
        m = ticket(kind="cite", to="expert@x", refs=["paper:lem:x"],
                   result="Ve89, Theorem (1.1), pp. 553-554, case n = 5 (" + "x" * 300)
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(self.lib, "cards", "Ve89", "_intro.md"))
        self.assertFalse(self.check(m)["ok"])                     # an intro is no card
        write(os.path.join(self.lib, "cards", "Ve89", "theorem-1-1.md"))
        self.assertTrue(self.check(m)["ok"])
        m = ticket(kind="cite", to="expert@x", refs=["bib:Mo06"], result="verdict partial")
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(self.lib, "cards", "Mo06", "theorem-2-6.md"))
        self.assertTrue(self.check(m)["ok"])

    def test_experiment_accepts_its_report_packet_or_a_header_naming_the_ticket(self):
        board = os.path.join(self.root, "board")
        self.ws["board"] = board
        m = ticket(kind="experiment", to="scientist@x", result="report P-0345; review ticket T-1155")
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(board, "packets", "scientist@x", "P-0345-report.md"), "---\nid: P-0345\n---\n")
        self.assertTrue(self.check(m)["ok"])
        m = ticket(kind="experiment", to="scientist@x", result="Not found: 8225 instances")
        self.assertFalse(self.check(m)["ok"])
        write(os.path.join(self.lab, "experiments", "2026-11-01_x.py"), '"""Ticket: T-00420\n"""')
        self.assertFalse(self.check(m)["ok"])                     # another ticket
        write(os.path.join(self.lab, "experiments", "2026-11-02_y.py"), '"""Ticket: T-0042\n"""')
        self.assertTrue(self.check(m)["ok"])

    def test_a_result_that_says_why_there_is_no_artefact_passes_with_its_marker(self):
        self.ws["human"] = {"name": "Ada"}
        git(self.root, "init", "-q", "-b", "main")               # the commit kinds are checked
        for kind, result, marker in (
                ("apply", "Declined, all four edits, nothing changed", "declined"),
                ("apply", "Both edits declined, no tex or registry change", "both edits declined"),
                ("apply", "Not applied (stale): the remark is now item x", "not applied"),
                ("apply", "No tex change: the ticket only asks to hold it", "no tex change"),
                ("apply", "Nothing applied, tex untouched", "nothing applied"),
                ("prove", "s1:GEO-67 is already proved: nothing to attempt", "already proved"),
                ("experiment", "dropped: Ada dropped the search", "dropped"),
                ("figure", "Already in the file (from T-1237): remark", "already in the file"),
                ("apply", "Ada replied 'Good!' (markings.tex:28)", "the decision of Ada"),
                ("experiment", "Falsify step, by argument (Ada accepts it)", "the decision of Ada")):
            r = self.check(ticket(kind=kind, to="author@p", result=result))
            self.assertTrue(r["ok"], (kind, result, r))
            self.assertEqual(r["marker"], marker, result)
        r = self.check(ticket(kind="prove", result="T-0700: record the answers: none (T-0700)"))
        self.assertFalse(r["ok"])                                 # nothing behind it, no reason
        self.assertIsNone(r["marker"])

    def test_a_bare_attempt_number_beside_the_claim_it_names(self):
        write(os.path.join(self.nb, "proofs", "PIR", "attempt-1.md"), "---\noutcome: complete\n---\n")
        self.assertTrue(self.check(ticket(result="proved (sketch) in nb:PIR, attempt-1; verify T-1"))["ok"])
        # the result's own id wins over one of its refs (T-1180)
        write(os.path.join(self.nb, "proofs", "PER-7", "attempt-1.md"), "---\noutcome: in-progress\n---\n")
        r = self.check(ticket(result="nb:PER-7 (attempt-1 in-progress): a derivation", refs=["nb:PIR"]))
        self.assertFalse(r["ok"], r)
        self.assertIn("in-progress", r["why"])

    def test_a_hash_in_prose_resolves_in_a_home_outside_the_root(self):
        home = tempfile.mkdtemp(prefix="acad-home-")
        self.addCleanup(shutil.rmtree, home, True)
        git(home, "init", "-q", "-b", "main")
        write(os.path.join(home, "a.tex"), "a")
        git(home, "add", "a.tex")
        git(home, "commit", "-q", "-m", "re-cut")
        sha = git(home, "rev-parse", "--short=7", "HEAD").strip()
        git(self.root, "init", "-q", "-b", "main")
        self.ws["instances"]["author@p"]["home"] = home
        m = ticket(kind="copy", to="author@p", result="Re-cut: 2026-10-26/pr27-recut/author @ %s." % sha)
        r = self.check(m)
        self.assertTrue(r["ok"], r)


class PartialStatus(unittest.TestCase):
    def test_partial_is_a_status_with_its_transitions(self):
        self.assertIn("partial", ac.TICKET_STATUSES)
        self.assertNotIn("partial", ac.TERMINAL)
        rcv, snd = {"receiver"}, {"sender"}
        self.assertTrue(ac.can_transition("in-progress", "partial", rcv)[0])
        self.assertFalse(ac.can_transition("in-progress", "partial", snd)[0])
        self.assertTrue(ac.can_transition("delivered", "partial", rcv)[0])   # a correction
        for new in ("in-progress", "closed", "cancelled"):
            self.assertTrue(ac.can_transition("partial", new, snd)[0], new)
            self.assertFalse(ac.can_transition("partial", new, rcv)[0], new)
        self.assertFalse(ac.can_transition("partial", "delivered", rcv)[0])
        self.assertTrue(ac.can_transition("partial", "open", set(), human=True)[0])
        self.assertTrue(ac.reason_needed("partial", "in-progress"))

    def test_permissions_json_mirrors_the_table(self):
        perms = ac.load_permissions(os.path.join(PLUGIN, "permissions.json"))
        tr = perms["tickets"]["transitions"]
        self.assertEqual(tr["partial"], {"in-progress": ["sender"], "closed": ["sender"],
                                         "cancelled": ["sender"]})
        self.assertEqual(tr["in-progress"]["partial"], ["receiver"])
        self.assertEqual(tr["delivered"]["partial"], ["receiver"])

    def test_a_partial_ticket_needs_a_result(self):
        m = ticket(status="partial", result="")
        self.assertTrue(any("result" in p for p in ac.validate_ticket(m)))
        self.assertFalse(ac.validate_ticket(ticket(status="partial", result="half")))

    def test_a_partial_child_releases_its_waiter(self):
        parent = ticket(status="blocked", waiting_on=["T-0050"], kind="research",
                        to="expert@x", final_to="researcher")
        look = {"T-0050": "partial"}.get
        self.assertTrue(ac.released_waits(parent, look))
        self.assertTrue(ac.relay_return_ready(parent, look))

    def test_the_serial_checkpoint_settles_partial(self):
        r = core.serial_checkpoint(ticket(status="partial", result="half"))
        self.assertEqual(r["state"], "partial")
        self.assertFalse(r["unfinished"])
        r = core.serial_checkpoint(ticket(status="partial", result=""))
        self.assertTrue(r["unfinished"])
        self.assertIn("partial", core.SHIP_STATES)


class PartialComesBackToItsSender(unittest.TestCase):
    """Review of dd0fcd1, point 6: a partial ticket an instance sent is a return row of that
    instance's inbox; one the human sent is not (desk, /academy:decide)."""

    def test_the_senders_inbox_takes_it(self):
        board = tempfile.mkdtemp(prefix="acad-pr-")
        self.addCleanup(shutil.rmtree, board, True)
        for tid, frm, to, status in (("T-0001", "researcher@nb", "scientist@x", "partial"),
                                     ("T-0002", "human", "scientist@x", "partial"),
                                     ("T-0003", "researcher@nb", "scientist@x", "delivered"),
                                     ("T-0004", "researcher@nb", "researcher@nb", "partial")):
            m = ticket(tid=tid, frm=frm, to=to, status=status, kind="experiment", result="half")
            os.makedirs(os.path.join(board, to), exist_ok=True)
            ac.atomic_write(os.path.join(board, to, ac.ticket_filename(tid, "t")), ac.new_ticket(m))
        rows, total = core.select(board, "researcher@nb", 3)
        self.assertEqual([r["id"] for r in rows], ["T-0001"])
        r = rows[0]
        self.assertTrue(r["partial"] and r["return"])
        self.assertEqual(r["route"]["target"], "lead-researcher")
        self.assertIn("reopen", r["route"]["why"])
        self.assertTrue(core.takeable(r))
        self.assertEqual(core.select(board, "researcher@nb", 3, return_legs=False)[0], [])


class CheckRefuses(unittest.TestCase):
    """``inbox.py --check`` on a delivered prove ticket, against a file board."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acad-chk-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.board = os.path.join(self.root, "board")
        self.nb = os.path.join(self.root, "nb")
        os.makedirs(self.nb)
        self.ws = {"_path": os.path.join(self.root, "workspace.json"), "board": self.board,
                   "instances": {"researcher@nb": {"role": "researcher", "home": self.nb}}}

    def put(self, meta):
        folder = os.path.join(self.board, meta["to"])
        os.makedirs(folder, exist_ok=True)
        ac.atomic_write(os.path.join(folder, ac.ticket_filename(meta["id"], meta["title"])),
                        ac.new_ticket(meta))

    def run_check(self):
        args = types.SimpleNamespace(check="T-0042", workspace=None, home=None)
        out = io.StringIO()
        orig_ship, orig_ws = core.ship_checkpoint, ac.load_workspace
        core.ship_checkpoint = staticmethod(lambda *a, **k: None)
        ac.load_workspace = lambda *a, **k: self.ws
        try:
            rc = core.run(args, "researcher@nb", self.board, 3, None, out=out)
        finally:
            core.ship_checkpoint = orig_ship
            ac.load_workspace = orig_ws
        return rc, out.getvalue()

    def test_a_delivered_prove_without_an_attempt_is_moved_to_partial(self):
        """Review of dd0fcd1, point 5: the refusal moves the ticket to partial itself (as its
        receiver, a thread note naming what is missing) and the check is then settled."""
        self.put(ticket(to="researcher@nb", result="T-0042: prove it: none (T-0042)"))
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("T-0042: partial (partial); no artefact: a prove "
                                       "ticket without a proof attempt"), out)
        self.assertIn("moved delivered -> partial", out)
        _ref, meta, body = ac.as_store(self.board).get("T-0042")
        self.assertEqual(meta["status"], "partial")
        self.assertIn("researcher@nb/inbox-check: no artefact: a prove ticket without a proof "
                      "attempt", body)
        self.assertIn("researcher@nb/inbox-check: status delivered -> partial", body)
        self.assertEqual(ac.validate_ticket(meta, body), [])

    def test_a_delivery_with_a_marker_passes_and_warns(self):
        self.put(ticket(to="researcher@nb", result="already proved: s1:GEO-1, nothing to attempt"))
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("T-0042: delivered (delivered)"), out)
        self.assertIn("WARN: T-0042 delivered without a proof attempt", out)
        self.assertIn("'already proved'", out)

    def test_a_delivered_prove_with_its_attempt_passes(self):
        write(os.path.join(self.nb, "proofs", "GEO-3", "attempt-1.md"),
              "---\noutcome: complete\n---\n")
        self.put(ticket(to="researcher@nb", result="complete attempt proofs/GEO-3/attempt-1.md"))
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("T-0042: delivered (delivered)"), out)

    def test_a_partial_ticket_is_finished(self):
        self.put(ticket(to="researcher@nb", status="partial", result="attempt incomplete"))
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("T-0042: partial (partial)"), out)

    def test_the_workspace_can_switch_it_off(self):
        self.ws["artefactCheck"] = False
        self.put(ticket(to="researcher@nb", result="T-0042: none"))
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("T-0042: delivered (delivered)"), out)


if __name__ == "__main__":
    unittest.main()
