"""The MCP listing tools stay small (2026-11-13): on a board of 1192 tickets an unfiltered
``tickets_list`` returned 384 000 characters and ``packets_list`` 166 000. A listing is now
cut to ``limit`` rows and says so, has the filters a caller needs to ask for less, and is
written without indentation."""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
sys.path.insert(0, os.path.join(PLUGIN, "mcp"))

import server  # noqa: E402
import tools  # noqa: E402
from tools import packets, tickets  # noqa: E402


class Store(object):
    def __init__(self, metas, github=True):
        self.metas = metas
        self.github = github

    def iter_meta(self):
        for m in self.metas:
            n = int(m["id"][2:])
            yield ("github#%d" % n if self.github else "/b/tickets/x/%s.md" % m["id"]), m


class Ctx(object):
    def __init__(self, store, board="/b"):
        self.store = store
        self.board = board


def metas(n):
    out = []
    for i in range(1, n + 1):
        out.append({"id": "T-%04d" % i, "title": "ticket %d about %s" % (i, "slopes" if i % 2 else "tori"),
                    "kind": "verify" if i % 3 == 0 else "question", "from": "human",
                    "to": "expert@e" if i % 2 else "author@a",
                    "status": "closed" if i % 5 == 0 else "open", "priority": "normal",
                    "parent": "T-0001" if i in (7, 8) else None,
                    "cowork": "sec-3" if i == 9 else None, "updated": "2026-11-13"})
    return out


class TicketsList(unittest.TestCase):
    def call(self, n=250, github=True, **a):
        return tickets._list(Ctx(Store(metas(n), github)), a)

    def test_a_long_listing_is_cut_and_says_so(self):
        r = self.call()
        self.assertEqual((250, 50, True, 0), (r["count"], r["shown"], r["truncated"], r["offset"]))
        self.assertEqual(50, len(r["tickets"]))
        self.assertEqual({"open": 200, "closed": 50}, r["by_status"])
        self.assertIn("offset=50", r["hint"])
        nxt = self.call(offset=50)
        self.assertEqual("T-0051", nxt["tickets"][0]["id"])
        last = self.call(offset=220)
        self.assertEqual(30, last["shown"])
        self.assertEqual(250, len(self.call(limit=0)["tickets"]))
        self.assertNotIn("truncated", self.call(limit=0))
        self.assertNotIn("truncated", self.call(n=50))
        with self.assertRaises(tools.ToolError):
            self.call(limit="many")

    def test_the_filters(self):
        self.assertEqual(["T-0007", "T-0008"],
                         [t["id"] for t in self.call(parent="T-0001")["tickets"]])
        self.assertEqual(["T-0009"], [t["id"] for t in self.call(cowork="sec-3")["tickets"]])
        self.assertEqual(83, self.call(kind="verify")["count"])
        self.assertEqual(125, self.call(text="  SLOPES ")["count"])
        self.assertEqual(1, self.call(text="T-0042")["count"])
        self.assertEqual(200, self.call(include_terminal=False)["count"])
        self.assertEqual(125, self.call(to="expert@e")["count"])

    def test_a_row_carries_no_empty_field_and_a_path_only_for_a_file(self):
        r = self.call(n=8)
        row = r["tickets"][0]
        self.assertNotIn("path", row)
        self.assertNotIn("parent", row)
        self.assertNotIn("agenda", row)
        self.assertEqual("T-0001", r["tickets"][6]["parent"])
        self.assertTrue(self.call(n=2, github=False)["tickets"][0]["path"].endswith("T-0001.md"))


class PacketsList(unittest.TestCase):
    def setUp(self):
        self.board = tempfile.mkdtemp(prefix="mcp-listing-")
        self.addCleanup(shutil.rmtree, self.board, True)
        d = os.path.join(self.board, "packets", "expert@e")
        os.makedirs(d)
        for i in range(1, 131):
            pending = i % 10 == 0
            body = ("## Decisions needed\n\n### D1. Go?\n\n- (a) Yes.\n- (b) No.\n\n## Decision\n\n"
                    if pending else "## Decisions needed\n\nNone.\n\n## Decision\n\n")
            with open(os.path.join(d, "P-%04d-x.md" % i), "w", encoding="utf-8") as fh:
                fh.write("---\npacket: P-%04d\ntitle: packet %d\ninstance: expert@e\n"
                         "kind: %s\nstate: pending\ncreated: 2026-11-13\n---\n\n%s"
                         % (i, i, "usage" if i % 13 == 0 else "verification", body))

    def call(self, **a):
        return packets._list(Ctx(None, self.board), a)

    def test_newest_first_cut_and_filtered(self):
        r = self.call()
        self.assertEqual((130, 50, True), (r["count"], r["shown"], r["truncated"]))
        self.assertEqual("P-0130", r["packets"][0]["packet"])
        self.assertEqual("packets/expert@e/P-0130-x.md", r["packets"][0]["path"])
        self.assertEqual(self.board.replace("\\", "/"), r["board"])
        self.assertEqual({"pending": 130}, r["by_state"])
        self.assertEqual(10, self.call(kind="usage")["count"])
        pend = self.call(pending=True)
        self.assertEqual(13, pend["count"])
        self.assertTrue(all(p["pending_decisions"] for p in pend["packets"]))
        self.assertEqual([], r["packets"][1]["pending_decisions"])     # the key stays


class Wire(unittest.TestCase):
    def test_a_result_is_written_without_indentation(self):
        text = server._result({"a": [{"b": 1}, {"b": 2}]})["content"][0]["text"]
        self.assertNotIn("\n", text)
        self.assertEqual("plain", server._result("plain")["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
