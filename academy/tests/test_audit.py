"""audit.py (academy #111): the read-only consistency audit. The checks are pure functions
over the board's ticket metas, the packet rows and registry.py stale's items; the packet
gathering is checked on a file board."""

import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import audit  # noqa: E402
import packets as pk  # noqa: E402
from test_decisions import ONE_DECISION_BODY, make_workspace  # noqa: E402

TODAY = datetime.date(2026, 11, 21)


def t(tid, status, **kw):
    m = {"id": tid, "status": status, "waiting_on": [], "result": None, "updated": "2026-11-21"}
    m.update(kw)
    return m


def classes(fs):
    return sorted((f["class"], f["id"]) for f in fs)


class TicketTests(unittest.TestCase):
    def test_blocked_on_ended_tickets_only(self):
        fs = audit.audit_tickets([
            t("T-0001", "blocked", waiting_on=["T-0002", "T-0003"]),
            t("T-0002", "delivered", result="done"), t("T-0003", "closed"),
            t("T-0004", "blocked", waiting_on=["T-0005"]), t("T-0005", "in-progress"),     # still running
            t("T-0006", "blocked", waiting_on=["T-0002", "human"]),                         # the human holds it
            t("T-0007", "blocked", waiting_on=[]),                                          # a dead route: not this class
        ], TODAY)
        self.assertEqual(classes(fs), [("ticket-waiting-done", "T-0001")])
        self.assertIn("T-0002 delivered, T-0003 closed", fs[0]["detail"])
        self.assertIn("transition T-0001 open", fs[0]["fix"])

    def test_unknown_wait_idle_and_empty_delivery(self):
        fs = audit.audit_tickets([
            t("T-0010", "blocked", waiting_on=["T-9999"]),
            t("T-0015", "blocked", waiting_on=["expert@main"]),                                # an instance, not a ticket
            t("T-0011", "in-progress", updated="2026-11-17"),
            t("T-0012", "in-progress", updated="2026-11-20"),                               # one day: not idle
            t("T-0013", "delivered", result=""), t("T-0014", "delivered", result="P-0001 filed"),
        ], TODAY, idle_days=3)
        self.assertEqual(classes(fs), [("ticket-delivered-no-result", "T-0013"),
                                       ("ticket-in-progress-idle", "T-0011"),
                                       ("ticket-waiting-unknown", "T-0010"), ("ticket-waiting-unknown", "T-0015")])
        self.assertIn("T-9999 (not on the board)", next(f for f in fs if f["id"] == "T-0010")["detail"])
        self.assertIn("no ticket id", next(f for f in fs if f["id"] == "T-0015")["detail"])
        self.assertIn("4 days", next(f for f in fs if f["id"] == "T-0011")["detail"])


class PacketTests(unittest.TestCase):
    def test_rows(self):
        rows = [
            {"packet": "P-0001", "state": "open", "_asked": [1], "_pending": [], "_problems": [], "_path": "/b/a/P-0001-x.md"},
            {"packet": "P-0001", "state": "decided", "_asked": [1], "_pending": [], "_problems": [], "_path": "/b/b/P-0001-y.md"},
            {"packet": "P-0002", "state": "open", "_asked": [1, 2], "_pending": [2], "_problems": []},          # still pending
            {"packet": "P-0003", "state": "open", "_asked": [], "_pending": [], "_problems": []},
            {"packet": "P-0004", "state": "decided", "_asked": [], "_pending": [], "_problems": ["D1 needs 2-4 options"]},
        ]
        fs = audit.audit_packets(rows)
        self.assertEqual(classes(fs), [("packet-duplicate-id", "P-0001"), ("packet-malformed", "P-0004"),
                                       ("packet-open-all-decided", "P-0001"), ("packet-open-no-decisions", "P-0003")])
        self.assertIn("P-0001-x.md; P-0001-y.md", next(f for f in fs if f["class"] == "packet-duplicate-id")["detail"])

    def test_gathered_from_a_file_board(self):
        d = tempfile.mkdtemp(prefix="academy-audit-")
        self.addCleanup(shutil.rmtree, d, True)
        ws, _p = make_workspace(d)
        os.makedirs(ws["board"])
        p = pk.create_packet(ws["board"], "expert@main", "Verify lem x", by="expert@main/review-chair", ticket=None,
                             body=ONE_DECISION_BODY, workspace=ws, date="2026-09-28", kind="verification",
                             subject=["paper:lem:x"], status_before="sketch", status_proposed="proved")
        rows = audit.gather_packets(ws["board"])
        self.assertEqual([r["_asked"] for r in rows], [[1]])
        self.assertEqual(audit.audit_packets(rows), [])            # open with D1 pending: nothing to say
        pid = p["packet"] if isinstance(p, dict) else None
        self.assertTrue(pid is None or pid.startswith("P-"))


class ClaimTests(unittest.TestCase):
    def test_stale_and_unreviewed_deduplicated(self):
        items = [
            {"kind": "stale", "qid": "paper:lem:a", "status": "proved", "pass": "2026-11-01-T-0001", "hold": ""},
            {"kind": "stale", "qid": "paper:lem:a", "status": "proved", "pass": "2026-11-01-T-0001", "hold": ""},
            {"kind": "unreviewed", "qid": "paper:fact:labelled-cover", "status": "proved",
             "hold": "proved without a positive review pass on record (1 pass(es), the last 2026-11-15-T-1243)"},
            {"kind": "stale", "qid": "s1:GEO-3", "status": "proved-modulo", "pass": "p", "hold": "the pass q is still open"},
        ]
        fs = audit.audit_claims(items)
        self.assertEqual(classes(fs), [("claim-no-positive-pass", "paper:fact:labelled-cover"),
                                       ("claim-stale-hash", "paper:lem:a"), ("claim-stale-hash", "s1:GEO-3")])
        self.assertIn("--file-reword", next(f for f in fs if f["id"] == "paper:lem:a")["fix"])
        self.assertNotIn("--file-reword", next(f for f in fs if f["id"] == "s1:GEO-3")["fix"])   # held: no reword


class CliTests(unittest.TestCase):
    def test_json_and_text_on_an_empty_file_board(self):
        d = tempfile.mkdtemp(prefix="academy-audit-")
        self.addCleanup(shutil.rmtree, d, True)
        _ws, path = make_workspace(d)
        os.makedirs(os.path.join(d, "board"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(audit.main(["--workspace", path, "--json", "--no-registry", "--today", "2026-11-21"]), 0)
        self.assertEqual(json.loads(buf.getvalue())["findings"], [])
        self.assertIn("0 finding(s)", audit.render([], []))
        text = audit.render([audit.finding("ticket-waiting-done", "T-1", "d", "f")] * 12, ["x: home missing"], limit=10)
        self.assertIn("ticket-waiting-done (12)", text)
        self.assertIn("and 2 more", text)
        self.assertIn("Not audited:", text)


if __name__ == "__main__":
    unittest.main()
