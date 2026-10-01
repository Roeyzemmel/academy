"""The github board store in the places that used to break it: a role plugin's vendored
library, the MCP packets/claims tools, board.py's packet scripts, the transport contract
(paging, ordering, failure half way), the shared inbox main and the campaign cap.

Run from the repo root:  py -m unittest discover academy/tests
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_board_store import StoreCase, INST, route  # noqa: E402
from test_board import INFO_BODY  # noqa: E402

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402
import board_store as bs  # noqa: E402
import decisions as dc  # noqa: E402
import packets as pk  # noqa: E402
from tools import Context, ToolError, tickets as mcp_tickets, packets as mcp_packets  # noqa: E402
from tools import claims as mcp_claims  # noqa: E402

core = ac.inbox_core


_VENDORED = {}


def vendored(role):
    """The role plugin's own copy of the library, as a module of its own (what its scripts
    import as ``_academy``): a different module object from ``academy_common``."""
    if role not in _VENDORED:
        name = "_academy_" + role
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(REPO, role, "scripts", "_academy.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        _VENDORED[role] = mod
    return _VENDORED[role]


class Seeded(StoreCase):
    def setUp(self):
        super().setUp()
        self.put(20, to="scientist@lab", kind="experiment", frm=INST)
        self.put(21, to="expert@main", kind="cite", frm=INST)
        self.files = ac.FileBoardStore(self.board)
        self.transport = bs.from_file_board(self.board)
        self.gh = bs.GithubBoardStore(self.transport, "o/r")
        self.gh.board = self.board           # what open_store sets: packets stay files


class TestVendoredLibraryMeetsTheGithubStore(Seeded):
    """Finding 1: the store is built from the lib's module, a plugin runs on its copy."""

    def test_the_copies_are_different_modules(self):
        v = vendored("researcher")
        self.assertIsNot(v.BoardStore, ac.BoardStore)
        self.assertFalse(isinstance(self.gh, v.BoardStore))      # why isinstance was wrong

    def test_as_store_keeps_a_github_store_whichever_copy_asks(self):
        for role in ("researcher", "expert", "scientist", "author"):
            v = vendored(role)
            self.assertIs(self.gh, v.as_store(self.gh), role)
            self.assertIs(self.files, v.as_store(self.files), role)
            self.assertIsInstance(v.as_store(self.board), v.FileBoardStore)

    def test_as_store_refuses_what_is_neither_a_path_nor_a_store(self):
        for bad in (None, 42, object(), {"board": self.board}):
            with self.assertRaises(ac.AcademyError):
                ac.as_store(bad)
            with self.assertRaises(vendored("expert").AcademyError):
                vendored("expert").as_store(bad)

    def test_a_vendored_select_on_github_gives_the_file_board_rows(self):
        a, _ = core.select(self.files, INST, 9, route=route)
        for role in ("researcher", "expert", "scientist"):
            v = vendored(role)
            b, _ = v.inbox_core.select(self.gh, INST, 9, route=route)
            self.assertTrue(b, role)                              # never silently empty
            self.assertEqual([{k: x for k, x in r.items() if k != "path"} for r in a],
                             [{k: x for k, x in r.items() if k != "path"} for r in b], role)
            self.assertTrue(all(r["path"].startswith("github#") for r in b))

    def test_a_vendored_open_store_speaks_through_its_own_library(self):
        v = vendored("researcher")
        ws = dict(self.ws, board_config={"backend": "github", "repo": "o/r"})
        st = v.open_store(ws, transport=self.transport)
        self.assertIsInstance(st, bs.GithubBoardStore)
        self.assertIs(v, st.lib)
        self.assertEqual(self.board, st.board)                   # packets stay files
        with self.assertRaises(v.AcademyError):                  # its error class, not the lib's
            st.get("T-0099")
        with self.assertRaises(v.ConfigError):
            v.open_store(ws)                                     # no transport: raises, no files
        self.assertEqual(self.gh.find("T-0003"), st.find("T-0003"))

    def test_a_github_store_is_never_wrapped_as_a_file_store(self):
        self.assertNotIsInstance(ac.as_store(self.gh), ac.FileBoardStore)


class TestRoleInboxScriptsOnGithub(Seeded):
    """The real wrappers, as subprocesses, on a github workspace and on the file one."""

    def workspace(self, github):
        ws = {"instances": {
            "expert@main": {"role": "expert", "home": os.path.join(self.tmp, "papers"),
                            "domains": ["dom-a"]},
            "author@main": {"role": "author", "home": os.path.join(self.tmp, "paperhome"),
                            "domains": ["dom-a"], "ns": "paper"},
            "researcher@r1": {"role": "researcher", "home": os.path.join(self.tmp, "r1"),
                              "domains": ["dom-b"], "ns": "s1"},
            "scientist@lab": {"role": "scientist", "home": os.path.join(self.tmp, "lab"),
                              "domains": ["dom-b"], "ns": "lab"}},
            "board": ({"path": self.board, "backend": "github", "repo": "o/r",
                       "transport": "_gh_seed:factory"} if github == "seeded" else
                      {"path": self.board, "backend": "github", "repo": "o/r"}
                      if github else self.board)}
        path = os.path.join(self.tmp, "ws-%s.json" % (github or "files"))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(ws, fh)
        return path

    def run_inbox(self, role, instance, ws, *extra, cwd=None):
        env = dict(os.environ, ACADEMY_TEST_SEED=self.board, PYTHONIOENCODING="utf-8",
                   PYTHONPATH=os.pathsep.join([HERE] + ([os.environ["PYTHONPATH"]]
                                                        if os.environ.get("PYTHONPATH") else [])))
        env.pop("ACADEMY_WORKSPACE", None)
        r = subprocess.run([sys.executable, os.path.join(REPO, role, "scripts", "inbox.py"),
                            "--instance", instance, "--workspace", ws, "--json"] + list(extra),
                           capture_output=True, text=True, cwd=cwd or self.tmp, env=env)
        return r

    def rows(self, r):
        doc = json.loads(r.stdout)
        for row in doc["take"]:
            row.pop("path")
        return doc

    def test_researcher_expert_and_scientist_see_the_same_inbox_on_github(self):
        files, gh = self.workspace(None), self.workspace("seeded")
        for role, inst in (("researcher", INST), ("expert", "expert@main"),
                           ("scientist", "scientist@lab")):
            with self.subTest(role=role):
                a = self.run_inbox(role, inst, files)
                b = self.run_inbox(role, inst, gh)
                self.assertEqual(0, a.returncode, a.stderr)
                self.assertEqual(0, b.returncode, b.stderr)
                self.assertTrue(self.rows(b)["take"])             # not the silent empty inbox
                self.assertEqual(self.rows(a), self.rows(b))

    def test_a_github_config_without_a_transport_is_a_clean_error_everywhere(self):
        ws = self.workspace("bare")
        for role, inst in (("researcher", INST), ("expert", "expert@main"),
                           ("scientist", "scientist@lab")):
            with self.subTest(role=role):
                r = self.run_inbox(role, inst, ws)
                self.assertEqual(2, r.returncode)
                self.assertNotIn("Traceback", r.stderr)
                self.assertIn("transport", r.stderr)
                self.assertEqual("", r.stdout)                    # no file-board fallback

    def test_the_wrappers_honour_workspace_and_home_from_anywhere(self):
        ws = self.workspace(None)
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere)
        for role, inst in (("researcher", INST), ("expert", "expert@main")):
            r = self.run_inbox(role, inst, ws, cwd=elsewhere)
            self.assertEqual(0, r.returncode, (role, r.stderr))
        home = os.path.join(self.tmp, "r1")
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "academy.json"), "w") as fh:
            json.dump(self.researcher_config(INST, 1), fh)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("ACADEMY_WORKSPACE", None)
        r = subprocess.run([sys.executable, os.path.join(REPO, "researcher", "scripts",
                                                         "inbox.py"),
                            "--home", home, "--workspace", ws, "--json"],
                           capture_output=True, text=True, cwd=elsewhere, env=env)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(INST, json.loads(r.stdout)["instance"])

    @staticmethod
    def researcher_config(instance, items):
        cfg = {"schema": 1, "role": "researcher", "instance": instance,
               "domains": ["dom-b"], "ns": "s1",
               "paths": {"objects": "objects", "proofs": "proofs", "journal": "journal",
                         "audits": "audits", "records": "objects", "views": ["views"]},
               "registry": {"profile": "s1", "root": "objects", "statusKeeper": "claim-keeper"},
               "budget": {"itemsPerRun": items, "serial": True, "orchestratorModel": "sonnet",
                          "maxModel": "fable", "ticketDefault": {"runs": 1,
                                                                 "max_model": "sonnet"}},
               "gate": {"commit": "normal", "build": False, "baseline": None, "branches": {}},
               "researcher": {"objectKinds": ["definition", "claim", "conjecture", "question",
                                              "example", "assumption", "direction"],
                              "statusField": "status", "reviewsHome": "expert@main",
                              "lab": "scientist@lab",
                              "generalize": {"maxPerRun": 3, "raiseAbove": "conjectured"}}}
        assert not ac.validate_config(cfg), ac.validate_config(cfg)
        return cfg

    def test_the_researcher_keeps_its_config_when_the_instance_is_given(self):
        ws = self.workspace(None)
        home = os.path.join(self.tmp, "r1")
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "academy.json"), "w") as fh:
            json.dump(self.researcher_config(INST, 1), fh)
        r = self.run_inbox("researcher", INST, ws)               # --instance, no --home
        self.assertEqual(0, r.returncode, r.stderr)
        doc = self.rows(r)
        self.assertEqual(1, doc["limit"])                        # budget.itemsPerRun honoured
        self.assertEqual(1, len(doc["take"]))


class TestSharedInboxMain(Seeded):
    def test_clamp_is_the_one_place_the_cap_lives(self):
        self.assertEqual([3, 1, 3, 3, 3, 2, 3], [core.clamp(x) for x in
                                                 (0, 1, 3, 9, None, 2, "x")])
        for role in ("researcher", "expert", "scientist"):
            with open(os.path.join(REPO, role, "scripts", "inbox.py"), encoding="utf-8") as fh:
                self.assertNotIn("min(int(", fh.read(), role)    # no private copy of the clamp

    def test_resolve_instance_reads_the_config_behind_an_instance(self):
        args = core.parser("x").parse_args(["--instance", INST, "--workspace", self.ws_path])
        self.assertEqual((INST, None), core.resolve_instance(args, "researcher"))
        with self.assertRaises(ac.AcademyError):
            core.resolve_instance(core.parser("x").parse_args(
                ["--workspace", self.ws_path]), "scientist", cwd=self.tmp)


class TestCampaignCap(Seeded):
    def setUp(self):
        super().setUp()
        for n in range(30, 35):
            self.put(n, campaign="c")            # with T-0006, T-0007: seven to take
        self.files = ac.FileBoardStore(self.board)
        self.gh = bs.GithubBoardStore(bs.from_file_board(self.board), "o/r")

    def run_core(self, store, *argv):
        out = io.StringIO()
        args = core.parser("x").parse_args(list(argv) + ["--json"])
        rc = core.run(args, INST, store, 3, route, out=out)
        return rc, json.loads(out.getvalue())

    def test_a_campaign_alone_lifts_the_cap_of_three(self):
        for store in (self.files, self.gh):
            rc, doc = self.run_core(store, "--campaign", "c")
            self.assertEqual(0, rc)
            self.assertEqual(7, len(doc["take"]), store.backend)
            self.assertEqual(0, doc["remaining"])
            self.assertIsNone(doc["limit"])

    def test_n_still_bounds_a_campaign(self):
        _rc, doc = self.run_core(self.files, "--campaign", "c", "--n", "2")
        self.assertEqual(2, len(doc["take"]))
        self.assertEqual(5, doc["remaining"])

    def test_without_a_campaign_the_cap_holds(self):
        for argv in ([], ["--n", "9"]):
            _rc, doc = self.run_core(self.files, *argv)
            self.assertEqual(3, len(doc["take"]), argv)
        out = io.StringIO()
        args = core.parser("x").parse_args(["--json"])
        core.run(args, INST, self.files, 1, route, out=out)       # itemsPerRun 1 lowers it
        self.assertEqual(1, len(json.loads(out.getvalue())["take"]))

    def test_an_in_progress_ticket_outside_the_campaign_is_surfaced_not_hidden(self):
        for store in (self.files, self.gh):
            _rc, doc = self.run_core(store, "--campaign", "c")
            self.assertEqual(["T-0003"], doc["outside_campaign"])   # in progress, no campaign
            self.assertIn("T-0003", doc["unfinished"])
            self.assertNotIn("T-0003", [r["id"] for r in doc["take"]])
        out = io.StringIO()
        core.run(core.parser("x").parse_args(["--campaign", "c"]), INST, self.files, 3, route,
                 out=out)
        self.assertIn("T-0003 are in progress outside campaign c", out.getvalue())

    def test_all_lists_in_progress_then_blocked_then_open(self):
        rows, _ = core.select(self.gh, INST, 3, all=True, route=route)
        order = [r["status"] for r in rows]
        self.assertEqual(["in-progress", "blocked", "blocked", "blocked"],
                         order[:4], order)
        self.assertEqual(["accepted", "open"], sorted({s for s in order[4:]},
                                                      key=order.index)[:2])
        self.assertLess(max(i for i, s in enumerate(order) if s == "blocked"),
                        min(i for i, s in enumerate(order) if s in ("open", "accepted")))
        a, _ = core.select(self.files, INST, 3, all=True, route=route)
        self.assertEqual([r["id"] for r in a], [r["id"] for r in rows])


class TestSharedRowHelpers(Seeded):
    def test_extra_row_has_the_core_shape_and_the_overrides(self):
        meta = self.gh.get("T-0008")[1]
        rt = {"how": "skill", "target": "x", "why": "landing"}
        row = core.extra_row(meta, rt, returned=True, status="delivered", **{"from": INST})
        plain = core._row(dict(meta, _return=False, _blocked=None), rt)
        self.assertEqual(set(plain) | {"return"}, set(row))
        self.assertTrue(row["return"])
        self.assertEqual(INST, row["from"])
        self.assertEqual(8, core.num(meta))
        self.assertEqual(8, core.num("T-0008"))
        rel = core.extra_row(meta, rt, released=True)
        self.assertTrue(rel["released"])

    def test_released_waits_is_the_shared_wait_rule(self):
        st = {"T-0001": "open", "T-0002": "delivered", "T-0003": "cancelled"}.get
        base = {"status": "blocked", "waiting_on": ["T-0002", "T-0003"]}
        self.assertTrue(ac.released_waits(base, st))
        self.assertFalse(ac.released_waits(dict(base, waiting_on=["T-0001", "T-0002"]), st))
        self.assertFalse(ac.released_waits(dict(base, waiting_on=["T-0002", "human"]), st))
        self.assertFalse(ac.released_waits(dict(base, waiting_on=["T-0099"]), st))
        self.assertFalse(ac.released_waits(dict(base, status="accepted"), st))
        self.assertFalse(ac.released_waits(dict(base, blocked_by="GEO-31", reopen_if="x"), st))
        self.assertFalse(ac.released_waits({"status": "blocked"}, st))
        # the relay return leg uses the same rule
        relay = dict(base, final_to="expert", to="researcher@r1")
        self.assertTrue(ac.relay_return_ready(relay, st))
        self.assertFalse(ac.relay_return_ready(dict(relay, waiting_on=["T-0001"]), st))

    def test_relay_depth_stops_at_a_missing_parent_on_both_stores(self):
        for store in (self.files, self.gh):
            self.assertEqual(0, ac.relay_depth(store, "T-0099"), store.backend)
            self.assertEqual(0, ac.relay_depth(store, None))
            self.assertEqual(1, ac.relay_depth(store, "T-0010"))   # final_to, no parent
        # a chain whose parent is gone: the link counts, then the walk ends without raising
        self.put(40, final_to="expert", parent="T-0099")
        self.put(41, final_to="expert", parent="T-0040")
        for store in (ac.FileBoardStore(self.board),
                      bs.GithubBoardStore(bs.from_file_board(self.board), "o/r")):
            self.assertEqual(2, ac.relay_depth(store, "T-0041"), store.backend)


class TestGithubStoreContract(Seeded):
    def test_paging_reads_every_page_and_skips_pull_requests(self):
        t = bs.from_file_board(self.board, bs.MemoryTransport(max_page=2))
        t.add_pull_request()
        store = bs.GithubBoardStore(t, "o/r")
        a, ta = core.select(self.files, INST, 9, all=True, route=route)
        b, tb = core.select(store, INST, 9, all=True, route=route)
        self.assertEqual([r["id"] for r in a], [r["id"] for r in b])
        self.assertEqual(ta, tb)
        pages = [c[3] for c in t.calls if c[0] == "list_issues" and c[1] == ("to:" + INST,)]
        self.assertGreater(max(pages), 2)                       # several pages were read
        self.assertEqual(sorted(m["id"] for _r, m in self.files.iter_meta()),
                         sorted(m["id"] for _r, m in store.iter_meta()))

    def test_comments_are_paged_and_read_in_id_order(self):
        t = bs.from_file_board(self.board, bs.MemoryTransport(max_page=1))
        store = bs.GithubBoardStore(t, "o/r")
        n = 5
        self.assertEqual(self.files.get("T-0005")[2], store.get("T-0005")[2])
        rows = t.list_comments(n, page=1, per_page=100)
        self.assertEqual(1, len(rows))                          # the cap is the transport's

        class Shuffled(bs.MemoryTransport):
            def list_comments(self, number, page=1, per_page=100):
                rows = super().list_comments(number, 1, 10 ** 6)
                return rows[::-1] if page == 1 else []          # newest first
        s = Shuffled()
        bs.from_file_board(self.board, s)
        self.assertEqual(self.files.get("T-0005")[2],
                         bs.GithubBoardStore(s, "o/r").get("T-0005")[2])

    def test_links_are_set_once_not_on_every_save(self):
        t = self.transport
        meta = dict(self.gh.get("T-0003")[1], parent="T-0001", status="blocked",
                    waiting_on=["T-0006"])
        body = self.gh.get("T-0003")[2]
        self.gh.save(meta, body)
        self.gh.save(dict(meta, updated="2026-09-30"), ac.append_thread(body, INST, "again"))
        self.gh.save(dict(meta, updated="2026-09-30"), ac.append_thread(body, INST, "again"))
        self.assertEqual(1, sum(1 for c in t.calls if c[0] == "set_parent" and c[1] == 3))
        self.assertEqual(1, sum(1 for c in t.calls if c[0] == "add_dependency" and c[1] == 3))
        self.assertEqual({3: 1}, t.parents)
        self.assertEqual([(3, 6)], t.dependencies)

    def test_save_verifies_the_issue_exists_and_is_a_ticket(self):
        meta, body = self.gh.get("T-0003")[1:]
        for bad in ("T-0099", "T-0015"):                         # missing; a placeholder
            with self.assertRaises(ac.AcademyError, msg=bad):
                self.gh.save(dict(meta, id=bad), body)
        self.assertNotIn(99, self.transport.issues)

    def test_thread_comments_go_in_before_the_label_and_state_move(self):
        self.transport.calls.clear()
        bd.transition_ticket(self.gh, "T-0005", "accepted", reopen="a new construction",
                             as_instance=INST)
        names = [c[0] for c in self.transport.calls]
        self.assertLess(max(i for i, n in enumerate(names) if n == "add_comment"),
                        names.index("update_issue"))
        texts = [c for c in self.transport.thread_comments(5)]
        self.assertIn("reopened: a new construction", texts[-2])
        self.assertNotIn("route:dead", self.transport.issues[5]["labels"])

    def test_a_failure_half_way_leaves_a_state_a_retry_repairs(self):
        self.transport.inject("update_issue")
        with self.assertRaises(RuntimeError):
            bd.transition_ticket(self.gh, "T-0002", "blocked", blocked_by="GEO-31",
                                 reopen_if="a new invariant", reason="induction",
                                 as_instance=INST)
        self.assertEqual("accepted", self.gh.status_of("T-0002"))   # the commit point held
        self.assertNotIn("route:dead", self.transport.issues[2]["labels"])
        self.assertIn("tried: induction", self.gh.get("T-0002")[2])  # comments were first
        bd.transition_ticket(self.gh, "T-0002", "blocked", blocked_by="GEO-31",
                             reopen_if="a new invariant", reason="induction",
                             as_instance=INST)
        meta, body = self.gh.get("T-0002")[1:]
        self.assertEqual("blocked", meta["status"])
        self.assertEqual([], ac.validate_ticket(meta, body))

    def test_a_failed_create_leaves_a_closed_placeholder_not_an_open_new_ticket(self):
        self.transport.inject("add_comment")
        before = set(self.transport.issues)
        with self.assertRaises(RuntimeError):
            bd.create_ticket(self.gh, "expert@main", "Chk", "a", "d", kind="cite",
                             as_instance="researcher@r1", workspace=self.ws)
        (n,) = set(self.transport.issues) - before
        issue = self.transport.issues[n]
        self.assertEqual(("closed", ["placeholder"]), (issue["state"], issue["labels"]))
        self.assertIsNone(self.gh.find(ac.format_id("T", n)))
        self.assertNotIn("(new ticket)", [i["title"] for i in self.transport.issues.values()])
        path = bd.create_ticket(self.gh, "expert@main", "Chk", "a", "d", kind="cite",
                                as_instance="researcher@r1", workspace=self.ws)
        self.assertEqual("github#%d" % (n + 1), path)

    def test_the_encoded_payload_is_exactly_this(self):
        """An independent literal: what GitHub receives, written out by hand."""
        meta = {"id": "T-0007", "title": "Check it", "kind": "verify", "from": "author@main",
                "to": "expert@main", "status": "blocked", "priority": "high", "ask": "a",
                "deliverable": "d", "refs": [], "blocks": [], "waiting_on": ["T-0003"],
                "budget": {"runs": 1, "max_model": "sonnet"}, "packets": [],
                "created": "2026-09-30", "updated": "2026-09-30", "parent": "T-0002"}
        body = "\n## Ask\n\na\n\n## Result\n\n\n## Thread\n\n" \
               "- 2026-09-30 author@main: opened\n" \
               "- 2026-09-30 expert@main: set waiting_on: [T-0003]\n"
        e = bc.encode(meta, body)
        self.assertEqual(7, e["number"])
        self.assertEqual("T-0007: Check it", e["title"])
        self.assertEqual(sorted(["status:blocked", "kind:verify", "role:expert",
                                 "to:expert@main", "from:author@main", "prio:high"]),
                         sorted(e["labels"]))
        self.assertEqual(("open", None), (e["state"], e["state_reason"]))
        self.assertEqual("T-0002", e["parent"])
        self.assertEqual(["T-0003"], e["waits_on"])
        self.assertEqual(["%s\n**author@main** 2026-09-30\n\nopened" % bc.THREAD_MARK,
                          "%s\n**expert@main** 2026-09-30\n\nset waiting_on: [T-0003]"
                          % bc.THREAD_MARK], e["comments"])
        first, _, rest = e["body"].partition("\n")
        self.assertTrue(first.startswith("<!-- academy:meta "))
        self.assertIn('"waiting_on":["T-0003"]', first)
        self.assertNotIn("status", first)                       # labels carry it, once
        self.assertEqual("\n## Ask\n\na\n\n## Result\n\n\n", rest)


class TestMcpAndScriptsOnGithub(Seeded):
    def ctx(self, store=None):
        return Context(cwd=self.tmp, workspace=self.ws, store=store or self.gh)

    def stray_files(self):
        return [os.path.join(d, f) for d, _ds, fs in os.walk(self.tmp) for f in fs
                if "github#" in f or "github#" in d]

    def test_packets_create_links_the_ticket_through_the_store(self):
        out = mcp_packets.create_packet(self.ctx(), {
            "title": "Verdict", "kind": "verification", "instance": INST, "ticket": "T-0001",
            "body": INFO_BODY})
        self.assertEqual("P-0001", out["packet"])
        self.assertTrue(out["linked_to_ticket"])
        self.assertEqual([], self.stray_files())                # no 'github#1' file anywhere
        meta, body = self.gh.get("T-0001")[1:]
        self.assertEqual(["P-0001"], meta["packets"])
        self.assertEqual("human", ac.thread_lines(body)[-1][1])
        self.assertIn("packet P-0001: Verdict", ac.thread_lines(body)[-1][2])
        self.assertEqual([], bc.validate_issue(self.transport.issues[1],
                                               self.transport.comments[1]))
        self.assertTrue(os.path.isfile(out["path"]))            # the packet itself is a file
        files = ac.FileBoardStore(self.board)
        self.assertEqual(files.get("T-0001")[1]["packets"], [])  # the file copy is untouched

    def test_packets_create_refuses_a_missing_ticket_on_github(self):
        with self.assertRaises(ToolError):
            mcp_packets.create_packet(self.ctx(), {
                "title": "V", "kind": "verification", "instance": INST, "ticket": "T-0099",
                "body": INFO_BODY})
        self.assertEqual([], self.stray_files())

    def test_packets_decide_echoes_into_the_github_ticket(self):
        mcp_packets.create_packet(self.ctx(), {
            "title": "Verdict", "kind": "verification", "instance": INST, "ticket": "T-0001",
            "body": INFO_BODY})
        out = mcp_packets.decide(self.ctx(), {"id": "P-0001", "decision": 0, "choice": "ack"})
        self.assertEqual("T-0001", out["echoed_into"])
        self.assertEqual("acknowledged P-0001", ac.thread_lines(self.gh.get("T-0001")[2])[-1][2])
        self.assertEqual([], self.stray_files())

    def test_claims_human_quote_is_checked_against_the_github_ticket(self):
        ok = {"where": "T-0001", "quote": "Ask T-0001"}
        mcp_claims.check_human_where(self.ctx(), ok)             # raises when it cannot
        with self.assertRaises(ToolError):
            mcp_claims.check_human_where(self.ctx(), {"where": "T-0001", "quote": "not there"})
        with self.assertRaises(ToolError):
            mcp_claims.check_human_where(self.ctx(), {"where": "T-0099", "quote": "x"})

    def test_the_packet_scripts_run_on_a_github_store(self):
        path = pk.create_packet(self.gh, INST, "Verdict", kind="verification", ticket="T-0001",
                                body=INFO_BODY, workspace=self.ws, date="2026-09-30")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual([], self.stray_files())
        self.assertEqual(["P-0001"], self.gh.get("T-0001")[1]["packets"])
        self.assertEqual(["T-0001"], dc._packet_unblocks(self.gh, "T-0001"))
        self.assertEqual(["T-0099"], dc._packet_unblocks(self.gh, "T-0099"))
        pk.decide_packet(self.gh, "P-0001", "ack", date="2026-09-30")
        self.assertEqual("decision on P-0001 D0: ack",
                         ac.thread_lines(self.gh.get("T-0001")[2])[-1][2])
        with self.assertRaises(ac.AcademyError):
            pk.create_packet(self.gh, INST, "V", ticket="T-0099", body=INFO_BODY,
                             workspace=self.ws)

    def test_a_store_without_a_board_directory_cannot_hold_packets(self):
        bare = bs.GithubBoardStore(self.transport, "o/r")
        with self.assertRaises(ac.AcademyError):
            pk.create_packet(bare, INST, "V", body=INFO_BODY, workspace=self.ws)


if __name__ == "__main__":
    unittest.main()
