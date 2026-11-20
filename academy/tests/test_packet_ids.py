"""Packet ids that cannot collide across branches (academy#90 (b)).

A packet id used to come from ``board/.ids/next-packet`` and the packet files of one
checkout only, so two branches (or two clones) that diverged from one board each issued the
same next number: 32 packet ids of the live board name two files each (P-0354..P-0385).
On the GitHub board an id is now also reserved on GitHub, which every branch and clone
shares, as one closed milestone per id (titled ``id:P-0471``); creating a milestone whose
title exists is refused by the server (HTTP 422 ``already_exists``), so two allocators can
never both hold one number (docs/protocol.md, "Id allocation"). A milestone, not a git ref:
the cloud sessions' GitHub proxy refuses writes to ``git/refs`` (HTTP 403).

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
        self.assertEqual(["id:P-%04d" % n for n in range(4, 9)], sorted(server.milestones))
        self.assertEqual({"closed"}, {m["state"] for m in server.milestones.values()})

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
            def list_milestones(self, state="all"):
                held = bs.MemoryTransport.list_milestones(self, state)
                if "id:P-0004" not in self.milestones:
                    bs.MemoryTransport.create_milestone(self, "id:P-0004")
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
        self.assertIn("id:P-10000", t.milestones)
        self.assertEqual(1, st.reserve_id("T", 1))       # one sequence per prefix

    def test_other_milestones_are_ignored(self):
        # the paper's milestones, an open one, a title that only looks like an id
        t = bs.MemoryTransport()
        for title in ("submission", "id:P-0900 draft", "id:Q-0050", "ID:P-0800"):
            t.create_milestone(title, state="open")
        t.create_milestone("id:P-0012")
        self.assertEqual(13, self.store(t).reserve_id("P", 2))
        self.assertIn("id:P-0013", t.milestones)

    def test_a_transport_that_cannot_reserve_is_refused_not_ignored(self):
        class Bare(bs.MemoryTransport):
            list_milestones = None
            create_milestone = None
        with self.assertRaises(ac.ConfigError) as e:
            self.store(Bare()).reserve_id("P", 1)
        self.assertIn("create_milestone", str(e.exception))

    def test_a_failing_transport_names_what_was_not_done(self):
        t = bs.MemoryTransport()
        t.inject("create_milestone", exc=RuntimeError("HTTP 503"))
        with self.assertRaises(ac.AcademyError) as e:
            self.store(t).reserve_id("P", 4)
        self.assertIn("P-0004", str(e.exception))
        self.assertIn("HTTP 503", str(e.exception))

    def test_a_token_without_write_access_fails_loudly(self):
        # a read-only token, or a proxy refusing the write: nothing reserved, nothing taken
        fake = FakeGh([(0, "[]", ""),
                       (1, json.dumps({"message": "Resource not accessible by integration"}),
                        "gh: Resource not accessible by integration (HTTP 403)")])
        st = self.store(gh.GhTransport("me/repo", run=fake, write_interval=0))
        with self.assertRaises(ac.AcademyError) as e:
            st.reserve_id("P", 4)
        self.assertIn("P-0004", str(e.exception))
        self.assertIn("HTTP 403", str(e.exception))
        self.assertEqual(2, len(fake.calls))                 # no next number was tried

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


TAKEN = json.dumps({"message": "Validation Failed",
                    "errors": [{"resource": "Milestone", "code": "already_exists",
                                "field": "title"}],
                    "documentation_url": "https://docs.github.com/rest", "status": "422"})


class TestGhTransportMilestones(unittest.TestCase):
    def test_create_milestone_posts_a_closed_title_and_reports_a_taken_one(self):
        # gh prints the message on stderr and the body, with the error code, on stdout
        fake = FakeGh([(0, json.dumps({"number": 7, "title": "id:P-0004"}), ""),
                       (1, TAKEN, "gh: Validation Failed (HTTP 422)")])
        t = gh.GhTransport("me/repo", run=fake, write_interval=0)
        self.assertTrue(t.create_milestone("id:P-0004"))
        self.assertFalse(t.create_milestone("id:P-0004"))
        args, payload = fake.calls[0]
        self.assertEqual(["api", "-X", "POST"], args[:3])
        self.assertIn("repos/me/repo/milestones", args)
        self.assertEqual({"title": "id:P-0004", "state": "closed"}, payload)
        self.assertEqual(2, len(fake.calls))
        self.assertFalse(any("git/" in a for c in fake.calls for a in c[0]))   # no git refs

    def test_another_422_is_an_error(self):
        fake = FakeGh([(1, json.dumps({"message": "Validation Failed",
                                       "errors": [{"resource": "Milestone", "code": "invalid",
                                                   "field": "state"}]}),
                        "gh: Validation Failed (HTTP 422)")])
        t = gh.GhTransport("me/repo", run=fake, write_interval=0)
        with self.assertRaises(gh.GhError) as e:
            t.create_milestone("id:P-0004", state="bogus")
        self.assertEqual(422, e.exception.status)

    def test_a_403_is_an_error(self):
        fake = FakeGh([(1, json.dumps({"message": "Write access to this GitHub API path is "
                                                  "not permitted through this proxy"}),
                        "gh: Write access ... (HTTP 403)")])
        t = gh.GhTransport("me/repo", run=fake, write_interval=0)
        with self.assertRaises(gh.GhError) as e:
            t.create_milestone("id:P-0004")
        self.assertEqual(403, e.exception.status)

    def test_list_milestones_reads_every_page_of_every_state(self):
        pages = [[{"number": i, "title": "id:P-%04d" % i, "state": "closed"}
                  for i in range(1, 101)],
                 [{"number": 101, "title": "submission", "state": "open"}]]
        fake = FakeGh([(0, json.dumps(p), "") for p in pages])
        t = gh.GhTransport("me/repo", run=fake)
        got = t.list_milestones()
        self.assertEqual(101, len(got))
        self.assertEqual("submission", got[-1]["title"])
        self.assertEqual(["api", "-X", "GET"], fake.calls[0][0][:3])
        self.assertIn("repos/me/repo/milestones?state=all&per_page=100&page=1", fake.calls[0][0])
        self.assertIn("repos/me/repo/milestones?state=all&per_page=100&page=2", fake.calls[1][0])


if __name__ == "__main__":
    unittest.main()
