"""audit.py (academy #111): the read-only consistency audit. The checks are pure functions
over the board's ticket metas, the packet rows and registry.py stale's items; the packet
gathering is checked on a file board, the registry gathering with a fake runner."""

import datetime
import io
import json
import os
import shutil
import subprocess
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
INFO_BODY = ONE_DECISION_BODY.split("## Decisions needed")[0] + "## Decisions needed\n\nNone.\n\n## Machine notes\n\nNone.\n\n## Decision\n"


def t(tid, status, **kw):
    m = {"id": tid, "status": status, "waiting_on": [], "result": None, "updated": "2026-11-21", "to": "expert@main"}
    m.update(kw)
    return m


def classes(fs):
    return sorted((f["class"], f["id"]) for f in fs)


class TicketTests(unittest.TestCase):
    def test_blocked_on_ended_tickets_only(self):
        fs = audit.audit_tickets([
            t("T-0001", "blocked", waiting_on=["T-0002", "T-0003"]),
            t("T-0002", "closed"), t("T-0003", "cancelled"),
            t("T-0004", "blocked", waiting_on=["T-0005"]), t("T-0005", "in-progress"),     # still running
            t("T-0006", "blocked", waiting_on=["T-0002", "human"]),                         # the human holds it
            t("T-0007", "blocked", waiting_on=[]),                                          # a dead route: not this class
            t("T-0008", "blocked", waiting_on=["T-0002", "author@main"]),                   # an instance: a legal wait
        ], TODAY)
        self.assertEqual(classes(fs), [("ticket-waiting-done", "T-0001")])
        self.assertIn("T-0002 closed, T-0003 cancelled", fs[0]["detail"])
        self.assertIn("transition T-0001 accepted (waiting_on cleared)", fs[0]["fix"])     # never blocked -> open
        self.assertNotIn(" open", fs[0]["fix"])

    def test_a_delivered_child_is_the_return_leg(self):
        fs = audit.audit_tickets([t("T-0001", "blocked", waiting_on=["T-0002"]), t("T-0002", "delivered", result="r")], TODAY)
        self.assertEqual(classes(fs), [("ticket-waiting-done", "T-0001")])
        self.assertIn("return leg is due: run the inbox for expert@main", fs[0]["fix"])

    def test_instances_are_legal_waits_and_free_text_is_malformed(self):
        fs = audit.audit_tickets([
            t("T-0010", "blocked", waiting_on=["T-9999"]),
            t("T-0015", "blocked", waiting_on=["expert@main"]),
            t("T-0016", "blocked", waiting_on=["human (Roey)", "expert"]),
        ], TODAY)
        self.assertEqual(classes(fs), [("ticket-waiting-malformed", "T-0016"), ("ticket-waiting-unknown", "T-0010")])
        self.assertIn("'human (Roey)', 'expert'", next(f for f in fs if f["id"] == "T-0016")["detail"])

    def test_idle_and_empty_delivery(self):
        fs = audit.audit_tickets([
            t("T-0011", "in-progress", updated="2026-11-17"),
            t("T-0012", "in-progress", updated="2026-11-20"),                               # one day: not idle
            t("T-0013", "delivered", result=""), t("T-0014", "delivered", result="P-0001 filed"),
        ], TODAY, idle_days=3)
        self.assertEqual(classes(fs), [("ticket-delivered-no-result", "T-0013"), ("ticket-in-progress-idle", "T-0011")])
        self.assertIn("4 days", next(f for f in fs if f["id"] == "T-0011")["detail"])


class PacketTests(unittest.TestCase):
    def test_rows(self):
        rows = [
            {"packet": "P-0001", "state": "open", "_asked": [1], "_answered": [1], "_pending": [], "_problems": [], "_path": "/b/a/P-0001-x.md"},
            {"packet": "P-0001", "state": "decided", "_asked": [1], "_answered": [1], "_pending": [], "_problems": [], "_path": "/b/b/P-0001-y.md"},
            {"packet": "P-0002", "state": "open", "_asked": [1, 2], "_answered": [1], "_pending": [2], "_problems": []},   # still pending
            {"packet": "P-0003", "state": "open", "_asked": [], "_answered": [], "_pending": [], "_problems": []},          # awaits its ack
            {"packet": "P-0005", "state": "open", "_asked": [], "_answered": [0], "_pending": [], "_problems": []},         # acked, still open
            {"packet": "P-0004", "state": "decided", "_asked": [], "_answered": [], "_pending": [], "_problems": ["D1 needs 2-4 options"]},
            {"_path": "/b/a/P-0006-broken.md", "_unreadable": "the frontmatter does not parse"},
        ]
        fs = audit.audit_packets(rows)
        self.assertEqual(classes(fs), [("packet-duplicate-id", "P-0001"), ("packet-malformed", "P-0004"),
                                       ("packet-open-all-decided", "P-0001"), ("packet-open-all-decided", "P-0005"),
                                       ("packet-unreadable", "P-0006-broken.md")])
        self.assertIn("P-0001-x.md; P-0001-y.md", next(f for f in fs if f["class"] == "packet-duplicate-id")["detail"])
        self.assertIn("D0 acknowledgement", next(f for f in fs if f["id"] == "P-0005")["detail"])

    def test_gathered_from_a_file_board(self):
        d = tempfile.mkdtemp(prefix="academy-audit-")
        self.addCleanup(shutil.rmtree, d, True)
        ws, _p = make_workspace(d)
        os.makedirs(ws["board"])
        kw = dict(by="expert@main/review-chair", ticket=None, workspace=ws, date="2026-09-28", kind="verification",
                  subject=["paper:lem:x"], status_before="sketch", status_proposed="proved")
        self.assertTrue(pk.create_packet(ws["board"], "expert@main", "Verify lem x", body=ONE_DECISION_BODY, **kw))
        pk.create_packet(ws["board"], "expert@main", "Note", body=INFO_BODY, **kw)
        info_path = next(r["_path"] for r in pk.list_packets(ws["board"]) if r.get("title") == "Note")
        with open(info_path, "a", encoding="utf-8") as fh:
            fh.write("\n- D0: ack | 2026-11-21 | human\n")
        with open(os.path.join(os.path.dirname(info_path), "P-0999-broken.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nnot: [valid\n---\n")
        rows = audit.gather_packets(ws["board"])
        self.assertEqual(sorted(tuple(r.get("_asked", ())) for r in rows), [(), (), (1,)])
        info_id = next(r["packet"] for r in rows if r.get("_path") == info_path)
        self.assertEqual(classes(audit.audit_packets(rows)), [("packet-open-all-decided", info_id),
                                                              ("packet-unreadable", "P-0999-broken.md")])


class ClaimTests(unittest.TestCase):
    def test_stale_and_unreviewed_deduplicated_and_covered(self):
        items = [
            {"kind": "stale", "qid": "paper:lem:a", "status": "proved", "pass": "2026-11-01-T-0001", "hold": "", "open_ticket": None},
            {"kind": "stale", "qid": "paper:lem:a", "status": "proved", "pass": "2026-11-01-T-0001", "hold": "", "open_ticket": None},
            {"kind": "unreviewed", "qid": "paper:fact:x", "status": "proved",
             "hold": "proved without a positive review pass on record", "open_ticket": None},
            {"kind": "stale", "qid": "s1:GEO-3", "status": "proved-modulo", "pass": "p", "hold": "the pass q is still open", "open_ticket": None},
            {"kind": "unreviewed", "qid": "s1:GEO-4", "status": "proved", "hold": "h", "open_ticket": "T-0765 Verify s1:GEO-4"},
        ]
        fs, cov = audit.audit_claims(items)
        self.assertEqual(classes(fs), [("claim-no-positive-pass", "paper:fact:x"),
                                       ("claim-stale-hash", "paper:lem:a"), ("claim-stale-hash", "s1:GEO-3")])
        self.assertEqual(cov, ["s1:GEO-4"])
        self.assertIn("--file-reword", next(f for f in fs if f["id"] == "paper:lem:a")["fix"])
        self.assertNotIn("--file-reword", next(f for f in fs if f["id"] == "s1:GEO-3")["fix"])   # held: no reword
        fs, cov = audit.audit_claims(items, covered=True)
        self.assertIn("covered by the open ticket T-0765", next(f for f in fs if f["id"] == "s1:GEO-4")["fix"])

    def test_gather_stale_names_every_failure(self):
        d = tempfile.mkdtemp(prefix="academy-audit-")
        self.addCleanup(shutil.rmtree, d, True)
        homes = {k: os.path.join(d, k) for k in ("a", "b", "c", "d", "x")}
        for h in homes.values():
            os.makedirs(h)
        ws = {"instances": {
            "author@a": {"role": "author", "home": homes["a"]},                        # no ns, but an Author home
            "researcher@b": {"role": "researcher", "ns": "b", "home": homes["b"]},
            "researcher@c": {"role": "researcher", "ns": "c", "home": homes["c"]},
            "researcher@d": {"role": "researcher", "ns": "d", "home": homes["d"]},
            "researcher@e": {"role": "researcher", "ns": "e", "home": os.path.join(d, "gone")},
            "expert@x": {"role": "expert", "home": homes["x"]}}}                        # no ns: not run
        R = lambda rc, out, err="": subprocess.CompletedProcess([], rc, out, err)  # noqa: E731
        answers = {homes["a"]: R(0, json.dumps({"items": [{"kind": "stale", "qid": "paper:x"}], "board": None})),
                   homes["b"]: R(2, "", "stale: no library reviews/ folder beside this repo"),
                   homes["c"]: R(0, json.dumps({"items": [], "board": "rate limited"}),
                                 "stale: the home of `z:` is not beside this repo; skipped"),
                   homes["d"]: R(0, "not json")}
        ran = []

        def run(home):
            ran.append(home)
            return answers[home]

        problems = []
        items = audit.gather_stale(ws, problems, run=run)
        self.assertEqual(items, [{"kind": "stale", "qid": "paper:x"}])
        self.assertNotIn(homes["x"], ran)
        joined = "\n".join(problems)
        self.assertIn("researcher@b: registry.py stale exit 2: stale: no library reviews/", joined)
        self.assertIn("researcher@c: registry.py stale: stale: the home of `z:`", joined)
        self.assertIn("researcher@c: registry.py stale could not read the board (rate limited)", joined)
        self.assertIn("researcher@d: registry.py stale printed no JSON", joined)
        self.assertIn("researcher@e: home", joined)


class CliTests(unittest.TestCase):
    def test_json_and_text_on_an_empty_file_board(self):
        d = tempfile.mkdtemp(prefix="academy-audit-")
        self.addCleanup(shutil.rmtree, d, True)
        _ws, path = make_workspace(d)
        os.makedirs(os.path.join(d, "board"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(audit.main(["--workspace", path, "--json", "--no-registry", "--today", "2026-11-21"]), 0)
        out = json.loads(buf.getvalue())
        self.assertEqual((out["findings"], out["not_audited"]), ([], []))
        self.assertIn("0 finding(s)", audit.render([], []))
        text = audit.render([audit.finding("ticket-waiting-done", "T-1", "d", "f")] * 12, ["x: home missing"], limit=10, covered=["s1:A"])
        self.assertIn("ticket-waiting-done (12)", text)
        self.assertIn("and 2 more", text)
        self.assertIn("Covered: 1", text)
        self.assertIn("Not audited:", text)

    def test_the_class_filter(self):
        d = tempfile.mkdtemp(prefix="academy-audit-")
        self.addCleanup(shutil.rmtree, d, True)
        ws, path = make_workspace(d)
        os.makedirs(os.path.join(ws["board"], "packets", "expert@main"))
        with open(os.path.join(ws["board"], "packets", "expert@main", "P-0001-x.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nnot: [valid\n---\n")
        for cls, n in (("packet-unreadable", 1), ("packet-malformed", 0)):
            buf = io.StringIO()
            with redirect_stdout(buf):
                audit.main(["--workspace", path, "--json", "--no-registry", "--no-tickets", "--class", cls])
            self.assertEqual(len(json.loads(buf.getvalue())["findings"]), n, cls)


if __name__ == "__main__":
    unittest.main()
