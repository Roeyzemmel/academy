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
        # #85 / T-0714: "already proved: nothing to attempt"
        r = self.check(ticket(result="flat:KDC-9 is already proved: nothing to attempt"))
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

    def test_a_delivered_prove_without_an_attempt_is_refused(self):
        self.put(ticket(to="researcher@nb", result="already proved: nothing to attempt"))
        rc, out = self.run_check()
        self.assertEqual(rc, 3, out)
        self.assertTrue(out.startswith("T-0042: unfinished (delivered, no artefact)"), out)
        self.assertIn("partial", out)
        self.assertIn("proof attempt", out)

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
        self.put(ticket(to="researcher@nb", result="already proved"))
        self.assertEqual(self.run_check()[0], 0)


if __name__ == "__main__":
    unittest.main()
