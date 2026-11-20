"""Packet ids that cannot collide across branches (academy#90 (b)).

A packet id used to come from ``board/.ids/next-packet`` and the packet files of one
checkout only, so two branches (or two clones) that diverged from one board each issued the
same next number: 32 packet ids of the live board name two files each (P-0354..P-0385).
On the GitHub board an id is now also reserved on GitHub, which every branch and clone
shares, as one ref per id (``refs/academy/ids/P-0471``); creating a ref that exists is
refused by the server, so two allocators can never both hold one number
(docs/protocol.md, "Id allocation").

Run from the repo root:  py -m unittest discover academy/tests
"""

import json
import os
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board import BoardCase, INFO_BODY  # noqa: E402
from test_board_push import FakeGh  # noqa: E402

import academy_common as ac  # noqa: E402
import board_gh as gh  # noqa: E402
import board_store as bs  # noqa: E402
import packets as pk  # noqa: E402

INST = "expert@main"
DATE = "2026-11-20"


def packet_ids(board):
    """The id of every packet file under ``board``, one entry per file."""
    out = []
    for _d, _ds, files in os.walk(os.path.join(board, "packets")):
        out += [f.split("-")[0] + "-" + f.split("-")[1] for f in files if f.startswith("P-")]
    return sorted(out)


class Diverged(BoardCase):
    """A base board with three packets, copied to two branches that then diverge."""

    def setUp(self):
        super().setUp()
        for n in (1, 2, 3):
            self.packet(self.board, ac.FileBoardStore(self.board), "base %d" % n)
        self.a = os.path.join(self.tmp, "branch-a")
        self.b = os.path.join(self.tmp, "branch-b")
        shutil.copytree(self.board, self.a)
        shutil.copytree(self.board, self.b)

    def packet(self, board, store, title):
        path = pk.create_packet(store, INST, title, kind="verification", body=INFO_BODY,
                                date=DATE)
        self.assertTrue(path.startswith(board))
        return os.path.basename(path)[:6]

    def github(self, board, transport):
        store = bs.GithubBoardStore(transport, "o/r")
        store.board = board
        return store

    def test_before_two_file_branches_issue_the_same_id(self):
        # the defect, kept as the control: a file board knows only its own checkout
        got_a = self.packet(self.a, ac.FileBoardStore(self.a), "on a")
        got_b = self.packet(self.b, ac.FileBoardStore(self.b), "on b")
        self.assertEqual("P-0004", got_a)
        self.assertEqual("P-0004", got_b)

    def test_after_two_github_branches_never_share_an_id(self):
        server = bs.MemoryTransport()
        a, b = self.github(self.a, server), self.github(self.b, server)
        got = [self.packet(self.a, a, "a1"), self.packet(self.b, b, "b1"),
               self.packet(self.a, a, "a2"), self.packet(self.b, b, "b2"),
               self.packet(self.b, b, "b3")]
        self.assertEqual(["P-0004", "P-0005", "P-0006", "P-0007", "P-0008"], got)
        merged = packet_ids(self.a) + [p for p in packet_ids(self.b)
                                       if p not in ("P-0001", "P-0002", "P-0003")]
        self.assertEqual(len(merged), len(set(merged)), merged)       # no twin after a merge
        self.assertEqual(sorted("refs/academy/ids/P-%04d" % n for n in range(4, 9)),
                         sorted(server.refs))

    def test_a_branch_far_ahead_does_not_drag_the_other_back(self):
        # branch a holds P-0040 locally (its counter is 41); b, behind, still gets 41
        server = bs.MemoryTransport()
        with open(os.path.join(self.a, ".ids", "next-packet"), "w") as fh:
            fh.write("40\n")
        self.assertEqual("P-0040", self.packet(self.a, self.github(self.a, server), "a"))
        self.assertEqual("P-0041", self.packet(self.b, self.github(self.b, server), "b"))
        with open(os.path.join(self.b, ".ids", "next-packet")) as fh:
            self.assertEqual("42\n", fh.read())          # the local counter follows GitHub

    def test_a_reservation_made_between_listing_and_creating_is_skipped(self):
        # the race: another clone takes the number this one just read as free
        class Racing(bs.MemoryTransport):
            def matching_refs(self, prefix):
                held = bs.MemoryTransport.matching_refs(self, prefix)
                self.refs.setdefault("refs/academy/ids/P-0004", "0" * 40)
                return held
        server = Racing()
        self.assertEqual("P-0005", self.packet(self.a, self.github(self.a, server), "a"))


class TestReserveId(unittest.TestCase):
    def store(self, transport):
        return bs.GithubBoardStore(transport, "o/r")

    def test_takes_the_larger_of_the_local_number_and_the_highest_reserved(self):
        t = bs.MemoryTransport()
        st = self.store(t)
        self.assertEqual(7, st.reserve_id("P", 7))
        self.assertEqual(8, st.reserve_id("P", 3))
        self.assertEqual(20, st.reserve_id("P", 20))
        self.assertEqual(10000, st.reserve_id("P", 10000))
        self.assertIn("refs/academy/ids/P-10000", t.refs)
        self.assertEqual(1, st.reserve_id("T", 1))       # one sequence per prefix

    def test_a_transport_that_cannot_reserve_is_refused_not_ignored(self):
        class Bare(bs.MemoryTransport):
            matching_refs = None
            create_ref = None
        with self.assertRaises(ac.ConfigError) as e:
            self.store(Bare()).reserve_id("P", 1)
        self.assertIn("create_ref", str(e.exception))

    def test_a_failing_transport_names_what_was_not_done(self):
        t = bs.MemoryTransport()
        t.inject("create_ref", exc=RuntimeError("HTTP 503"))
        with self.assertRaises(ac.AcademyError) as e:
            self.store(t).reserve_id("P", 4)
        self.assertIn("P-0004", str(e.exception))
        self.assertIn("HTTP 503", str(e.exception))

    def test_the_file_board_has_no_authority_beyond_its_checkout(self):
        self.assertEqual(12, ac.FileBoardStore("/nowhere").reserve_id("P", 12))


class TestAllocateWithReserve(BoardCase):
    def test_the_reserved_number_wins_and_the_counter_follows(self):
        asked = []

        def reserve(prefix, n):
            asked.append((prefix, n))
            return n + 5
        self.assertEqual("P-0006", ac.allocate_id(self.board, "packet", reserve=reserve))
        self.assertEqual([("P", 1)], asked)
        with open(os.path.join(self.board, ".ids", "next-packet")) as fh:
            self.assertEqual("7\n", fh.read())
        self.assertFalse(os.path.exists(os.path.join(self.board, ".ids", "lock")))

    def test_a_reserve_below_the_local_number_is_an_error(self):
        with self.assertRaises(ac.AcademyError):
            ac.allocate_id(self.board, "packet", reserve=lambda prefix, n: n - 1)

    def test_the_counter_never_moves_back(self):
        os.makedirs(os.path.join(self.board, ".ids"))
        with open(os.path.join(self.board, ".ids", "next-packet"), "w") as fh:
            fh.write("9\n")
        self.assertEqual("P-0009", ac.allocate_id(self.board, "packet",
                                                  reserve=lambda prefix, n: n))
        with open(os.path.join(self.board, ".ids", "next-packet")) as fh:
            self.assertEqual("10\n", fh.read())


class TestGhTransportRefs(unittest.TestCase):
    def test_create_ref_points_at_the_default_head_and_reports_a_taken_ref(self):
        fake = FakeGh([(0, json.dumps({"sha": "abc"}), ""),
                       (0, json.dumps({"ref": "refs/academy/ids/P-0004"}), ""),
                       (1, "", "gh: Reference already exists (HTTP 422)")])
        t = gh.GhTransport("me/repo", run=fake, write_interval=0)
        self.assertTrue(t.create_ref("refs/academy/ids/P-0004"))
        self.assertFalse(t.create_ref("refs/academy/ids/P-0004"))
        self.assertIn("repos/me/repo/commits/HEAD", fake.calls[0][0])
        self.assertEqual(["api", "-X", "POST"], fake.calls[1][0][:3])
        self.assertIn("repos/me/repo/git/refs", fake.calls[1][0])
        self.assertEqual({"ref": "refs/academy/ids/P-0004", "sha": "abc"}, fake.calls[1][1])
        self.assertEqual(3, len(fake.calls))                   # the head is asked once

    def test_another_422_is_an_error(self):
        fake = FakeGh([(0, json.dumps({"sha": "abc"}), ""),
                       (1, "", "gh: Reference name is invalid (HTTP 422)")])
        t = gh.GhTransport("me/repo", run=fake, write_interval=0)
        with self.assertRaises(gh.GhError):
            t.create_ref("refs/academy/ids/bad name")

    def test_matching_refs_lists_ref_names(self):
        rows = [{"ref": "refs/academy/ids/P-0004"}, {"ref": "refs/academy/ids/P-0005"}]
        fake = FakeGh([(0, json.dumps(rows), "")])
        t = gh.GhTransport("me/repo", run=fake)
        self.assertEqual(["refs/academy/ids/P-0004", "refs/academy/ids/P-0005"],
                         t.matching_refs("academy/ids/P-"))
        self.assertIn("repos/me/repo/git/matching-refs/academy/ids/P-", fake.calls[0][0])


if __name__ == "__main__":
    unittest.main()
