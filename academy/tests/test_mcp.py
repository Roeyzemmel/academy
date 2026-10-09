"""Tests for the academy MCP server (academy/mcp).

The server is spawned as a subprocess and spoken to in newline-delimited
JSON-RPC 2.0, against a temporary workspace (board, homes, library, queue,
domain pack) so nothing outside the temp dir is written. The grounds checker is
also tested directly as a pure function.

Run from the repo root:  py -m unittest discover academy/tests
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SERVER = os.path.join(PLUGIN, "mcp", "server.py")
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "mcp"))

import academy_common as ac  # noqa: E402
from tools.claims import check_grounds  # noqa: E402
from tools import library as lib  # noqa: E402

EXTRACTION = (
    "LEMMA 6. Let M be a translation surface. The boundary of a maxi-\n"
    "     mal cylinder consists of finitely many saddle connec-\n"
    "tions, and every non-Veech surface is\n"
    "treated separately.\n"
    "\f"
    "Page two says something about the ﬁnite blocking property\n"
    "of non-\n"
    "Veech surfaces.\n"
)
INDEX = (
    "# Index\n\nSome prose.\n\n"
    "| key | authors, short title | version |\n"
    "|---|---|---|\n"
    "| K1 | Someone, \"A paper on cylinders\" | arXiv v2 |\n"
    "| K2 | Other, \"Uncached\" | published |\n"
)


class Server(object):
    """A running server subprocess with a tiny JSON-RPC client."""

    def __init__(self, cwd, env):
        self.caller_dir = env.get("ACADEMY_CALLER_DIR")
        self.p = subprocess.Popen([sys.executable, SERVER], cwd=cwd, env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        self.n = 0

    def request(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            self.n += 1
            msg["id"] = self.n
        self.p.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        self.p.stdin.flush()
        if notify:
            return None
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError("server died: %s" % self.p.stderr.read().decode())
        resp = json.loads(line.decode("utf-8"))
        assert resp["id"] == self.n, resp
        return resp

    def call(self, _tool, caller=None, _hook=True, **args):
        """Call a tool as the hook would have it: record ``caller`` ('human' if None)
        in the handshake directory first, unless ``_hook`` is False."""
        if _hook:
            ac.record_caller(_tool, args, caller or "human", folder=self.caller_dir)
        resp = self.request("tools/call", {"name": _tool, "arguments": args})
        res = resp["result"]
        text = res["content"][0]["text"]
        try:
            data = json.loads(text)
        except ValueError:
            data = text
        return res["isError"], data

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        finally:
            self.p.stdout.close()
            self.p.stderr.close()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class McpTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="academy-mcp-")
        t = cls.tmp.replace("\\", "/")
        cls.board = t + "/board"
        cls.homes = {"author@t": t + "/paper", "expert@t": t + "/library",
                     "scientist@t": t + "/lab", "researcher@t": t + "/notebook"}
        for h in cls.homes.values():
            os.makedirs(h)
        os.makedirs(cls.board)
        ws = {"instances": {
            "author@t": {"role": "author", "home": cls.homes["author@t"],
                         "domains": ["test-pack"], "ns": "paper"},
            "expert@t": {"role": "expert", "home": cls.homes["expert@t"],
                         "domains": ["test-pack"]},
            "scientist@t": {"role": "scientist", "home": cls.homes["scientist@t"],
                            "domains": ["test-pack"], "ns": "lab"},
            "researcher@t": {"role": "researcher", "home": cls.homes["researcher@t"],
                             "domains": ["test-pack"], "ns": "s1"}},
            "board": cls.board, "human": {"name": "Roey"}}
        cls.ws_path = os.path.join(cls.tmp, "workspace.json")
        write(cls.ws_path, json.dumps(ws, indent=2))
        write(os.path.join(cls.tmp, "domains", "test-pack", "notation.md"), "# Notation\n")
        lib_home = cls.homes["expert@t"]
        write(os.path.join(lib_home, "index.md"), INDEX)
        write(os.path.join(lib_home, "K1.txt"), EXTRACTION)
        write(os.path.join(lib_home, "K1.meta"), "key: K1\n")
        q = os.path.join(cls.homes["scientist@t"], "queue")
        write(os.path.join(q, "config.json"), '{"target": "ssh:somewhere", "maxJobs": 1}')
        write(os.path.join(q, "done", "20260901-000000_exp.json"),
              "﻿" + json.dumps({"id": "20260901-000000_exp", "label": "lab:x",
                                     "status": "ok", "log": "~/fsq/collected/x/log"}))
        os.makedirs(os.path.join(q, "pending"))
        cls.env = dict(os.environ, ACADEMY_WORKSPACE=cls.ws_path, PYTHONUTF8="1",
                       ACADEMY_CALLER_DIR=os.path.join(cls.tmp, "callers"))
        cls.env.pop("ACADEMY_CWD", None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def server(self, instance=None):
        cwd = self.homes[instance] if instance else self.tmp
        s = Server(cwd, self.env)
        self.addCleanup(s.close)
        s.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "test", "version": "0"}})
        s.request("notifications/initialized", notify=True)
        return s


class TestProtocol(McpTestBase):
    def test_initialize_and_list(self):
        s = Server(self.tmp, self.env)
        self.addCleanup(s.close)
        init = s.request("initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertEqual(init["serverInfo"]["name"], "academy")
        self.assertIn("tools", init["capabilities"])
        s.request("notifications/initialized", notify=True)
        tools = s.request("tools/list")["result"]["tools"]
        names = {t["name"] for t in tools}
        for want in ("claims_show", "claims_list", "claims_query", "claims_deps",
                     "claims_new", "claims_set_status", "claims_propose_status",
                     "library_lookup", "library_search", "library_verify_quote",
                     "library_missing", "queue_status", "queue_log", "queue_add",
                     "env_list", "env_check", "tickets_list",
                     "tickets_get", "tickets_create", "tickets_update", "packets_list",
                     "packets_get", "packets_create", "packets_decide", "domain_get",
                     "config_get", "workspace_get"):
            self.assertIn(want, names)
        for t in tools:
            self.assertEqual(t["inputSchema"]["type"], "object")
            self.assertTrue(t["description"])

    def test_unknown_method_and_tool(self):
        s = self.server()
        self.assertEqual(s.request("no/such")["error"]["code"], -32601)
        err, text = s.call("no_such_tool")
        self.assertTrue(err)

    def test_permissions_gate_write_tools(self):
        s = self.server("author@t")
        err, text = s.call("tickets_create", caller="expert:rigor-reviewer", title="x",
                           kind="question", to="expert@t", ask="a", deliverable="d")
        self.assertTrue(err)
        self.assertIn("denied", text)


class TestTickets(McpTestBase):
    def test_dead_route_block_and_reopen(self):
        author = self.server("author@t")
        expert = self.server("expert@t")
        w, r = "author:math-writer", "expert:review-chair"
        err, t = author.call("tickets_create", caller=w, title="Check Lemma 4.2",
                             kind="verify", to="expert@t", ask="Verify paper:lem:x.",
                             deliverable="A packet.")
        tid = t["id"]
        err, res = expert.call("tickets_update", caller=r, id=tid, status="accepted")
        self.assertFalse(err, res)
        err, msg = expert.call("tickets_update", caller=r, id=tid, status="blocked")
        self.assertTrue(err)                                   # neither kind
        dead = {"blocked_by": "paper:lem:x", "reopen_if": "a new invariant"}
        err, msg = expert.call("tickets_update", caller=r, id=tid, status="blocked",
                               fields=dead)
        self.assertTrue(err)                                   # no thread line of what was tried
        err, res = expert.call("tickets_update", caller=r, id=tid, status="blocked",
                               fields=dead, reason="tried the strip bound; circular")
        self.assertFalse(err, res)
        err, msg = expert.call("tickets_update", caller=r, id=tid, status="accepted")
        self.assertTrue(err)                                   # reopen needs the mechanism
        err, res = expert.call("tickets_update", caller=r, id=tid, status="accepted",
                               reopen="a Prym construction")
        self.assertFalse(err, res)
        err, got = expert.call("tickets_get", caller=r, id=tid)
        self.assertNotIn("blocked_by", got["meta"])
        self.assertEqual(got["problems"], [])
        self.assertIn("reopened: a Prym construction", got["body"])

    def test_create_campaign_field(self):
        author = self.server("author@t")
        w = "author:math-writer"
        args = dict(title="Prior art", kind="lookup", to="expert@t", ask="Is it known?",
                    deliverable="A note.")
        err, tagged = author.call("tickets_create", caller=w, campaign="paper:thm:x", **args)
        self.assertFalse(err, tagged)
        err, plain = author.call("tickets_create", caller=w, **args)
        self.assertFalse(err, plain)
        err, got = author.call("tickets_get", caller=w, id=tagged["id"])
        self.assertEqual("paper:thm:x", got["meta"]["campaign"])
        self.assertEqual([], got["problems"])
        err, got = author.call("tickets_get", caller=w, id=plain["id"])
        self.assertNotIn("campaign", got["meta"])
        # a campaign is one line: a multi-line value is refused before anything is written
        err, msg = author.call("tickets_create", caller=w, campaign="a\nb", **args)
        self.assertTrue(err)
        self.assertIn("one line", msg)
        # and the inbox core selects exactly the tagged ticket for that campaign
        rows, _t = ac.inbox_core.select(self.board, "expert@t", 3, campaign="paper:thm:x",
                                        route=lambda m: {"how": "skill", "target": "x",
                                                         "why": "y"})
        self.assertEqual([tagged["id"]], [r["id"] for r in rows])
        self.assertEqual("paper:thm:x", rows[0]["campaign"])

    def test_round_trip(self):
        author = self.server("author@t")
        expert = self.server("expert@t")
        w = "author:math-writer"
        r = "expert:review-chair"
        err, t = author.call("tickets_create", caller=w, title="Check Lemma 4.2",
                             kind="verify", to="expert@t", ask="Verify paper:lem:x.",
                             deliverable="A packet with two verdicts.",
                             refs=["paper:lem:x"], note="uses the strip bound twice")
        self.assertFalse(err, t)
        tid = t["id"]
        self.assertRegex(tid, r"^T-\d{4}$")
        self.assertTrue(t["path"].endswith("/expert@t/%s-check-lemma-4-2.md" % tid))
        self.assertEqual(t["from"], "author@t")

        # the sender may not accept its own outgoing ticket
        err, msg = author.call("tickets_update", caller=w, id=tid, status="accepted")
        self.assertTrue(err)
        self.assertIn("receiver", msg)
        # rejecting needs a reason
        err, msg = expert.call("tickets_update", caller=r, id=tid, status="rejected")
        self.assertTrue(err)
        # the receiver may not edit the ask
        err, msg = expert.call("tickets_update", caller=r, id=tid,
                               fields={"ask": "something else"})
        self.assertTrue(err)

        for st in ("accepted", "in-progress"):
            err, res = expert.call("tickets_update", caller=r, id=tid, status=st)
            self.assertFalse(err, res)
        err, msg = expert.call("tickets_update", caller=r, id=tid, status="delivered")
        self.assertTrue(err)                       # no result yet
        err, p = expert.call("packets_create", caller=r, title="Verification of lem:x",
                             kind="verification", ticket=tid, subject=["paper:lem:x"],
                             status_before="sketch", status_proposed="proved",
                             sections={"summary": "Two runs confirmed.",
                                       "produced": "- Verdicts: `file:expert@t/reviews/x`",
                                       "established_vs_assumed":
                                           "- **Established:** paper:lem:x (proposed proved)",
                                       "evidence": "- Runs A and B.",
                                       "decisions_needed":
                                           "### D1. Recolour now?\n\n- (a) Yes.\n- (b) No.\n"
                                           "- Recommendation: (a), both agree.",
                                       "machine_notes": "None."})
        self.assertFalse(err, p)
        self.assertTrue(p["linked_to_ticket"])
        err, res = expert.call("tickets_update", caller=r, id=tid, status="delivered",
                               fields={"result": "CONFIRMED x2; recolour proposed"},
                               result_detail="See the packet.")
        self.assertFalse(err, res)
        # the receiver may not close; the sender does
        err, msg = expert.call("tickets_update", caller=r, id=tid, status="closed")
        self.assertTrue(err)
        err, res = author.call("tickets_update", caller=w, id=tid, status="closed",
                               note="recolour landed")
        self.assertFalse(err, res)

        # the human decides the packet; the answer is echoed into the ticket
        human = self.server()
        err, msg = expert.call("packets_decide", caller=r, id=p["packet"], decision=1,
                               choice="a")
        self.assertTrue(err)
        err, d = human.call("packets_decide", id=p["packet"], decision=1, choice="a",
                            note="go")
        self.assertFalse(err, d)
        self.assertEqual(d["state"], "decided")

        err, got = human.call("tickets_get", id=tid)
        self.assertFalse(err)
        self.assertEqual(got["problems"], [])
        self.assertEqual(got["meta"]["status"], "closed")
        self.assertEqual(got["meta"]["packets"], [p["packet"]])
        thread = [x[2] for x in ac.thread_lines(got["body"])]
        self.assertEqual(thread[0], "opened: uses the strip bound twice")
        self.assertIn("status open -> accepted", thread)
        self.assertIn("status in-progress -> delivered", thread)
        self.assertIn("status delivered -> closed", thread)
        self.assertTrue(thread[-1].startswith("decision on %s D1: (a) Yes." % p["packet"]))
        speakers = {x[1] for x in ac.thread_lines(got["body"])}
        self.assertIn("author@t/math-writer", speakers)
        self.assertIn("expert@t/review-chair", speakers)
        self.assertIn("See the packet.", got["body"])

        err, pk = human.call("packets_get", id=p["packet"])
        self.assertEqual(pk["problems"], [])
        self.assertEqual(pk["answers"]["1"][0], "(a)")

        err, ls = human.call("tickets_list", to="expert@t")
        self.assertIn(tid, [x["id"] for x in ls["tickets"]])
        err, pl = human.call("packets_list", instance="expert@t")
        self.assertEqual(pl["packets"][0]["pending_decisions"], [])

    def test_budget_max_model_is_optional_and_not_stamped(self):
        # T-0071: the model comes from the agent file. A new ticket's default budget
        # is runs only; a sender may give runs alone, or add max_model as a note.
        human = self.server()
        err, t = human.call("tickets_create", title="Default budget", kind="question",
                            to="expert@t", ask="q", deliverable="d")
        self.assertFalse(err, t)
        err, g = human.call("tickets_get", id=t["id"])
        self.assertEqual(g["meta"]["budget"], {"runs": 1})
        err, t = human.call("tickets_create", title="Runs only", kind="question",
                            to="expert@t", ask="q", deliverable="d", budget={"runs": 2})
        self.assertFalse(err, t)
        err, g = human.call("tickets_get", id=t["id"])
        self.assertEqual(g["meta"]["budget"], {"runs": 2})
        err, t = human.call("tickets_create", title="Advisory note", kind="question",
                            to="expert@t", ask="q", deliverable="d",
                            budget={"runs": 1, "max_model": "haiku"})
        self.assertFalse(err, t)
        err, g = human.call("tickets_get", id=t["id"])
        self.assertEqual(g["meta"]["budget"], {"runs": 1, "max_model": "haiku"})
        self.assertEqual(g["problems"], [])

    def test_human_reroutes_and_blocking(self):
        human = self.server()
        err, a = human.call("tickets_create", title="First", kind="question",
                            to="researcher@t", ask="q", deliverable="d")
        self.assertFalse(err, a)
        err, b = human.call("tickets_create", title="Second", kind="question",
                            to="expert@t", ask="q", deliverable="d")
        self.assertFalse(err, b)
        # blocked needs waiting_on; the awaited ticket's blocks is mirrored
        err, msg = human.call("tickets_update", id=b["id"], status="blocked")
        self.assertTrue(err)
        err, res = human.call("tickets_update", id=b["id"], status="blocked",
                              fields={"waiting_on": [a["id"]]})
        self.assertFalse(err, res)
        err, ga = human.call("tickets_get", id=a["id"])
        self.assertEqual(ga["meta"]["blocks"], [b["id"]])
        # re-route: the file moves to the new receiver's folder
        err, res = human.call("tickets_update", id=a["id"], fields={"to": "scientist@t"})
        self.assertFalse(err, res)
        self.assertIn("/scientist@t/", res["path"])
        self.assertFalse(os.path.exists(ga["path"]))
        # an agent may not re-route
        lab = self.server("scientist@t")
        err, msg = lab.call("tickets_update", caller="scientist:experimenter", id=a["id"],
                            fields={"to": "expert@t"})
        self.assertTrue(err)


class TestLibrary(McpTestBase):
    def test_verify_quote(self):
        s = self.server("author@t")
        cases = [
            ("The boundary of a maximal cylinder consists of finitely many saddle "
             "connections", True),                                  # broken words
            ("every non-Veech surface is treated separately.", True),
            ("the finite blocking property of non-Veech surfaces", True),  # ligature+hyphen
            ("The boundary of a minimal cylinder consists of finitely many", False),
            ("the boundary of a maximal cylinder", False),               # case-sensitive
        ]
        for quote, want in cases:
            err, res = s.call("library_verify_quote", key="K1", quote=quote)
            self.assertFalse(err, res)
            self.assertEqual(res["match"], want, quote)
        err, res = s.call("library_verify_quote", key="K1",
                          quote="finite blocking property")
        self.assertEqual(res["page"], 2)
        err, msg = s.call("library_verify_quote", key="K2", quote="anything")
        self.assertTrue(err)
        log = os.path.join(self.homes["expert@t"], ".academy", "access.log")
        with open(log, encoding="utf-8") as fh:
            self.assertIn("library_verify_quote", fh.read())
        with open(os.path.join(self.homes["expert@t"], ".academy", ".gitignore")) as fh:
            self.assertIn("*", fh.read())

    def test_search_lookup_missing(self):
        s = self.server("author@t")
        err, res = s.call("library_search", query="saddle connections of a cylinder")
        self.assertFalse(err, res)
        self.assertEqual(res["hits"][0]["key"], "K1")
        err, res2 = s.call("library_search", query="cylinders", kind="index")
        self.assertEqual([h["key"] for h in res2["hits"]], ["K1"])
        # incremental: a second search re-indexes nothing
        err, res3 = s.call("library_search", query="saddle")
        self.assertEqual(res3["reindexed_files"], 0)
        err, lk = s.call("library_lookup", key="K1")
        self.assertTrue(lk["files"][".txt"])
        self.assertEqual(lk["index_row"]["version"], "arXiv v2")
        err, miss = s.call("library_missing", bib=False)
        self.assertEqual(miss["indexed_without_txt"], ["K2"])
        self.assertEqual(miss["cached_without_index_row"], [])

    def test_parse_index(self):
        rows = lib.parse_index(INDEX)
        self.assertEqual([r["key"] for r in rows], ["K1", "K2"])
        self.assertEqual(rows[1]["version"], "published")


class TestOtherTools(McpTestBase):
    def test_domain_get(self):
        s = self.server()
        err, res = s.call("domain_get", name="test-pack")
        self.assertEqual(res["files"], ["notation.md"])
        err, res = s.call("domain_get", name="test-pack", file="notation.md")
        self.assertEqual(res["text"], "# Notation\n")
        err, msg = s.call("domain_get", name="test-pack", file="../../workspace.json")
        self.assertTrue(err)
        err, msg = s.call("domain_get", name="nope")
        self.assertTrue(err)

    def test_queue(self):
        s = self.server("scientist@t")
        err, res = s.call("queue_status")
        self.assertFalse(err, res)
        self.assertEqual(res["counts"], {"done": 1})
        self.assertEqual(res["jobs"][0]["label"], "lab:x")
        err, lg = s.call("queue_log", id="20260901")
        self.assertFalse(err, lg)
        self.assertIn("never uses ssh", lg["note"])

    def test_queue_add_and_envs(self):
        s = self.server("scientist@t")
        lab = self.homes["scientist@t"]
        err, envs = s.call("env_list")
        self.assertFalse(err, envs)
        self.assertEqual(envs["envs"], {})
        self.assertIn("not switched over", envs["problems"][0])
        err, msg = s.call("env_check")
        self.assertTrue(err)
        err, msg = s.call("queue_add", caller="scientist:experimenter",
                          script="experiments/none.py")
        self.assertTrue(err)
        self.assertIn("no script", msg)
        write(os.path.join(lab, "experiments", "e.py"), "print(1)\n")
        err, msg = s.call("queue_add", caller="scientist:experimenter",
                          script="experiments/e.py")
        self.assertTrue(err)
        self.assertIn("not committed", msg)      # the temp lab is not a git repo
        err, msg = s.call("queue_add", caller="scientist:experimenter",
                          script="../outside.py")
        self.assertIn("inside the lab home", msg)
        err, msg = s.call("queue_add", caller="author:math-writer", script="experiments/e.py")
        self.assertTrue(err)
        self.assertIn("refused", msg)
        # with an academy.json: profiles, policy, a static check
        with open(os.path.join(PLUGIN, "templates", "academy-json", "scientist.json"),
                  encoding="utf-8") as fh:
            cfg = json.loads(fh.read().replace("{{instance}}", "scientist@t")
                             .replace("{{domain}}", "test-pack").replace("{{ns}}", "lab"))
        cfg["scientist"]["envs"]["far"] = {"kind": "ssh", "host": "far.example.invalid"}
        path = os.path.join(lab, ".claude", "academy.json")
        write(path, json.dumps(cfg))
        self.addCleanup(os.remove, path)
        err, envs = s.call("env_list")
        self.assertEqual(envs["policy"]["run"], "local")
        err, chk = s.call("env_check")
        self.assertFalse(err, chk)
        self.assertTrue(chk["ok"])
        self.assertEqual(chk["policy_uses"], ["probe", "run", "test"])
        err, chk = s.call("env_check", env="far")
        self.assertTrue(chk["ok"], chk)
        self.assertEqual(chk["checked"], "static")
        from tools import queue as qtools
        self.assertIn("needs host", qtools.check_profile("x", {"kind": "ssh"})[0])
        self.assertIn("kind must be", qtools.check_profile("x", {"kind": "vm"})[0])
        # check_profile delegates to env.py's own static_problems, so env_check can
        # never call a profile ok that `env.py check` would reject: maxJobs above 3
        # and a malformed preflight are both real env.py rules the old looser copy
        # here never enforced.
        self.assertTrue(any("maxJobs" in p for p in
                            qtools.check_profile("x", {"kind": "ssh", "host": "h",
                                                        "maxJobs": 9})))
        self.assertTrue(any("preflight" in p for p in
                            qtools.check_profile("x", {"kind": "ssh", "host": "h",
                                                        "preflight": "nope"})))
        err, msg = s.call("env_check", env="nope")
        self.assertTrue(err)

    def test_queue_add_dry_run(self):
        """queue_add builds the job with the Scientist's env.py; by default (and in the
        migration run) it is a dry run that writes nothing and returns the job file."""
        lab = self.homes["scientist@t"]

        def git(*a):
            subprocess.run(["git", "-C", lab] + list(a), capture_output=True, check=True)
        git("init", "-q")
        self.addCleanup(shutil.rmtree, os.path.join(lab, ".git"), True)
        git("config", "user.email", "t@example.invalid")
        git("config", "user.name", "T")
        write(os.path.join(lab, "experiments", "2026-09-30_e2.py"), "print(2)\n")
        git("add", "experiments/2026-09-30_e2.py")
        git("commit", "-q", "-m", "e2")
        s = self.server("scientist@t")
        pending = os.path.join(lab, "queue", "pending")
        before = sorted(os.listdir(pending))
        err, res = s.call("queue_add", caller="scientist:experimenter",
                          script="experiments/2026-09-30_e2.py", label="lab:x",
                          script_args="--bound 4")
        self.assertFalse(err, res)
        self.assertTrue(res["dry_run"])
        self.assertFalse(res["written"])
        self.assertEqual(res["job"]["args"], ["--bound", "4"])
        self.assertEqual(res["job"]["label"], "lab:x")
        self.assertEqual(res["job"]["script"], "experiments/2026-09-30_e2.py")
        self.assertTrue(res["path"].endswith("queue/pending/%s.json" % res["job"]["id"]))
        self.assertEqual(res["env"], "queue")          # pre-switch: queue/config.json
        self.assertIn("dry-run", res["note"])
        self.assertEqual(sorted(os.listdir(pending)), before)
        # enabled in the home's academy.json: the job file is written
        with open(os.path.join(PLUGIN, "templates", "academy-json", "scientist.json"),
                  encoding="utf-8") as fh:
            cfg = json.loads(fh.read().replace("{{instance}}", "scientist@t")
                             .replace("{{domain}}", "test-pack").replace("{{ns}}", "lab"))
        cfg["scientist"]["queue"]["mcpAdd"] = "on"
        path = os.path.join(lab, ".claude", "academy.json")
        write(path, json.dumps(cfg))
        self.addCleanup(os.remove, path)
        err, res = s.call("queue_add", caller="scientist:experimenter",
                          script="experiments/2026-09-30_e2.py", note="n")
        self.assertFalse(err, res)
        self.assertTrue(res["written"])
        self.assertTrue(os.path.isfile(res["path"]))
        self.addCleanup(os.remove, res["path"])
        self.assertEqual(res["env"], "local")

    def test_workspace_and_config(self):
        s = self.server("author@t")
        err, ws = s.call("workspace_get", caller="author:math-writer")
        self.assertEqual(ws["caller"]["instance"], "author@t")
        err, cfg = s.call("config_get")
        self.assertIsNone(cfg["config"])

    def test_set_status_refused_without_grounds(self):
        s = self.server("researcher@t")
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="s1:X-1", status="proved")
        self.assertTrue(err)
        self.assertIn("no grounds", msg)
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:x", status="proved",
                          grounds={"basis": "computation", "commit": "abc",
                                   "validation_passed": True, "outcome": "supports",
                                   "verdicts": [{"verdict": "SOUND", "run_id": "a"},
                                                {"verdict": "SOUND", "run_id": "b"}]})
        self.assertTrue(err)
        self.assertIn("computation never establishes", msg)
        err, msg = s.call("claims_set_status", caller="expert:rigor-reviewer",
                          id="lab:x", status="supported")
        self.assertTrue(err)
        # grounds that pass reach the registry engine, which has no lab:x here
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:x", status="supported", grounds=comp())
        self.assertTrue(err)
        self.assertIn("no claim `lab:x`", msg)

    def test_claim_keeper_cannot_prove_without_grounds(self):
        # the review finding: claim-keeper used to reach the server as the human
        s = self.server("researcher@t")
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:x", status="proved")
        self.assertTrue(err)
        self.assertIn("no grounds", msg)


class TestKeeperRouting(unittest.TestCase):
    """claims_propose_status must file the decision to the namespace's OWN researcher.

    The bug: _keeper_instance looked up the owning instance, then used only its
    domains to build a candidate list and returned cands[0]. With two researcher
    instances sharing a domain, a proposal about the second one's namespace was
    filed to the first -- researcher@beta's `flat:` decisions went to
    researcher@alpha, whose notebook does not hold those objects.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-keeper-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        t = self.tmp.replace("\\", "/")
        self.board = t + "/board"
        os.makedirs(self.board)
        # two researchers sharing one domain, registered first-to-last as in the
        # real workspace: the s1 notebook predates the flat one.
        self.homes = {"researcher@s1": t + "/s1", "researcher@beta": t + "/flat",
                      "author@t": t + "/paper"}
        for h in self.homes.values():
            os.makedirs(h)
        ws = {"instances": {
            "researcher@s1": {"role": "researcher", "home": self.homes["researcher@s1"],
                              "domains": ["test-pack"], "ns": "s1"},
            "researcher@beta": {"role": "researcher", "home": self.homes["researcher@beta"],
                                "domains": ["test-pack"], "ns": "flat"},
            "author@t": {"role": "author", "home": self.homes["author@t"],
                         "domains": ["test-pack"], "ns": "paper"}},
            "board": self.board, "human": {"name": "Roey"}}
        self.ws_path = os.path.join(self.tmp, "workspace.json")
        write(self.ws_path, json.dumps(ws, indent=2))
        self.env = dict(os.environ, ACADEMY_WORKSPACE=self.ws_path, PYTHONUTF8="1",
                        ACADEMY_CALLER_DIR=os.path.join(self.tmp, "callers"))
        self.env.pop("ACADEMY_CWD", None)

    def server(self, instance=None):
        cwd = self.homes[instance] if instance else self.tmp
        s = Server(cwd, self.env)
        self.addCleanup(s.close)
        s.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "test", "version": "0"}})
        s.request("notifications/initialized", notify=True)
        return s

    def test_proposal_goes_to_the_namespace_owner(self):
        s = self.server()
        err, res = s.call("claims_propose_status", id="flat:some-claim", status="sketch",
                          reason="complete attempt")
        self.assertFalse(err, res)
        self.assertEqual(res["to"], "researcher@beta")

    def test_a_proposal_from_outside_every_home_is_not_from_human(self):
        # the main session outside a home is the human for tickets in general, but a
        # status proposal is the owning notebook's work: T-0065/T-0066 were stamped
        # 'from: human' although researcher@flat filed them
        s = self.server()
        err, res = s.call("claims_propose_status", id="flat:some-claim", status="sketch",
                          reason="complete attempt")
        self.assertFalse(err, res)
        self.assertEqual(res["from"], "researcher@beta")

    def test_the_other_researcher_still_gets_its_own(self):
        s = self.server()
        err, res = s.call("claims_propose_status", id="s1:OBS-22", status="sketch",
                          reason="complete attempt")
        self.assertFalse(err, res)
        self.assertEqual(res["to"], "researcher@s1")

    def test_a_namespace_owned_by_a_non_researcher_still_falls_back(self):
        # paper: belongs to an author; its keeper is a researcher sharing the domain.
        s = self.server()
        err, res = s.call("claims_propose_status", id="paper:lem:x", status="sketch",
                          reason="complete attempt")
        self.assertFalse(err, res)
        self.assertIn(res["to"], ("researcher@s1", "researcher@beta"))


class TestCallerHandshake(McpTestBase):
    def test_write_without_hook_record_refused(self):
        s = self.server("author@t")
        err, msg = s.call("tickets_create", _hook=False, title="x", kind="question",
                          to="expert@t", ask="a", deliverable="d")
        self.assertTrue(err)
        self.assertIn("could not be identified", msg)

    def test_read_without_hook_record_is_unverified(self):
        s = self.server("author@t")
        err, ws = s.call("workspace_get", _hook=False)
        self.assertFalse(err, ws)
        self.assertEqual(ws["caller"]["agent"], "human")
        self.assertFalse(ws["caller"]["verified"])

    def test_caller_argument_refused(self):
        s = self.server("author@t")
        # Server.call takes caller as the hook's record; send it as a raw argument
        resp = s.request("tools/call", {"name": "workspace_get",
                                        "arguments": {"caller": "human"}})
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("reserved", resp["result"]["content"][0]["text"])

    def test_record_is_consumed_once(self):
        s = self.server("author@t")
        args = dict(title="Once", kind="question", to="expert@t", ask="a", deliverable="d")
        err, t = s.call("tickets_create", caller="author:math-writer", **args)
        self.assertFalse(err, t)
        err, msg = s.call("tickets_create", _hook=False, **args)
        self.assertTrue(err)
        self.assertIn("could not be identified", msg)

    def test_record_names_the_agent(self):
        s = self.server("author@t")
        err, ws = s.call("workspace_get", caller="author:math-writer")
        self.assertEqual(ws["caller"]["agent"], "author:math-writer")
        self.assertTrue(ws["caller"]["verified"])

    def test_ambiguous_records_refuse_writes(self):
        s = self.server("author@t")
        args = dict(title="Twin", kind="question", to="expert@t", ask="a", deliverable="d")
        ac.record_caller("tickets_create", args, "human", folder=s.caller_dir)
        ac.record_caller("tickets_create", args, "author:math-writer", folder=s.caller_dir)
        err, msg = s.call("tickets_create", _hook=False, **args)
        self.assertTrue(err)
        self.assertIn("in flight", msg)
        for n in os.listdir(s.caller_dir):          # leave no records for other tests
            os.remove(os.path.join(s.caller_dir, n))

    def test_role_agent_outside_its_role_home_refused(self):
        # the server's home is not the agent's (2026-10-09, fix 1): an expert agent
        # acts for the only expert instance, never for the author home it runs in
        s = self.server("author@t")
        err, t = s.call("tickets_create", caller="expert:librarian", title="x",
                        kind="question", to="author@t", ask="a", deliverable="d")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "expert@t")
        err, msg = s.call("tickets_create", caller="expert:librarian", title="x",
                          instance="author@t", kind="question", to="expert@t", ask="a",
                          deliverable="d")
        self.assertTrue(err)
        self.assertIn("belongs to the expert role", msg)
        err, t = s.call("tickets_create", caller="academy:concierge", title="Desk",
                        kind="question", to="expert@t", ask="a", deliverable="d")
        self.assertFalse(err, t)

    def test_claims_new_guards(self):
        s = self.server("author@t")
        err, msg = s.call("claims_new", caller="author:math-writer", id="paper:lem:y",
                          title="t", status="proved")
        self.assertTrue(err)
        err, msg = s.call("claims_new", caller="author:math-writer", id="lab:y",
                          title="t")
        self.assertTrue(err)
        self.assertIn("own instance's namespace", msg)


def proof_rows(*verdicts, h="H1", grader="rigor-reviewer"):
    return [{"verdict": v, "run_id": "r%d" % i, "statement_hash": h, "grader_role": grader,
             "ref": "reviews/r%d.md" % i}
            for i, v in enumerate(verdicts)]


def proof(*verdicts, **kw):
    g = {"basis": "proof", "producer_role": "prover", "verdicts": proof_rows(*verdicts)}
    g.update(kw)
    return g


def rows_of(g, **kw):
    """``g`` with every verdict row updated by ``kw`` (a key set to None is removed)."""
    g = dict(g)
    g["verdicts"] = [{k: v for k, v in dict(r, **kw).items() if v is not None}
                     for r in g["verdicts"]]
    return g


def comp(verdicts=("SOUND", "SOUND"), **kw):
    g = {"basis": "computation", "commit": "c0ffee", "validation_passed": True,
         "outcome": "supports", "producer_role": "experimenter",
         "verdicts": [{"verdict": v, "run_id": "e%d" % i,
                       "grader_role": "researcher:experiment-reviewer",
                       "ref": "audits/ew/2026-09-28-%s.md" % "AB"[i % 2]}
                      for i, v in enumerate(verdicts)]}
    g.update(kw)
    return g


class TestAccessLogPath(unittest.TestCase):
    """The server writes where ``expert.accessLog`` says, and hot.py reads (Group F)."""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="acad-log-")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _config(self, access_log):
        with open(os.path.join(PLUGIN, "templates", "academy-json", "expert.json"),
                  encoding="utf-8") as fh:
            cfg = json.loads(fh.read().replace("{{instance}}", "expert@t")
                             .replace("{{domain}}", "translation-surfaces"))
        if access_log is None:
            cfg["expert"].pop("accessLog", None)
        else:
            cfg["expert"]["accessLog"] = access_log
        os.makedirs(os.path.join(self.home, ".claude"))
        with open(os.path.join(self.home, ".claude", "academy.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(cfg, fh)

    def test_default_without_config(self):
        self.assertEqual(os.path.normpath(lib.access_log_path(self.home)),
                         os.path.join(self.home, ".academy", "access.log"))

    def test_template_default_is_the_derived_dir(self):
        self._config(".academy/access.log")
        self.assertEqual(os.path.normpath(lib.access_log_path(self.home)),
                         os.path.join(self.home, ".academy", "access.log"))

    def test_configured_path_is_honoured(self):
        self._config("logs/clerk.log")
        self.assertEqual(os.path.normpath(lib.access_log_path(self.home)),
                         os.path.join(self.home, "logs", "clerk.log"))


class TestGrounds(unittest.TestCase):
    def ok(self, *a, **k):
        res, why = check_grounds(*a, **k)
        self.assertTrue(res, why)

    def no(self, *a, **k):
        res, why = check_grounds(*a, **k)
        self.assertFalse(res, why)
        return why

    def test_no_grounds(self):
        self.no("proved", None)
        self.no("supported", {})
        self.ok("proved", None, human=True)          # Roey's word

    def test_unknown_status(self):
        self.no("Disproved", {"basis": "proof"})

    def test_proof(self):
        g = proof("CONFIRMED", "CONFIRMED")
        self.ok("proved", g)
        self.ok("proved", g, statement_hash="H1")
        self.no("proved", g, statement_hash="H2")    # statement changed since
        self.no("proved", proof("CONFIRMED"))
        self.no("proved", proof("CONFIRMED", "PLAUSIBLE"))
        dup = proof("CONFIRMED", "CONFIRMED")
        dup["verdicts"][1]["run_id"] = dup["verdicts"][0]["run_id"]
        self.no("proved", dup)
        mixed = proof("CONFIRMED", "CONFIRMED")
        mixed["verdicts"][1]["statement_hash"] = "H9"
        self.no("proved", mixed)
        nohash = [{"verdict": "CONFIRMED", "run_id": "a", "grader_role": "rigor-reviewer",
                   "ref": "a.md"},
                  {"verdict": "CONFIRMED", "run_id": "b", "grader_role": "rigor-reviewer",
                   "ref": "b.md"}]
        self.no("proved", {"basis": "proof", "producer_role": "prover", "verdicts": nohash})
        self.ok("proved", {"basis": "proof", "producer_role": "prover", "verdicts": nohash,
                           "statement_hash": "H"})
        self.no("proved-modulo", g)                  # needs modulo
        self.ok("proved-modulo", dict(g, modulo=["s1:Q2"]))
        self.no("proved", dict(g, modulo=["s1:Q2"]))
        self.no("supported", g)                      # a proof review never "supports"
        self.ok("refuted", proof("DISPROVED", "disproved"))
        self.no("refuted", g)

    def test_grader_is_never_the_producer(self):
        why = self.no("proved", proof("CONFIRMED", "CONFIRMED", producer_role="rigor-reviewer"))
        self.assertIn("grades their own work", " ".join(why))
        self.no("proved", dict(proof("CONFIRMED", "CONFIRMED"), producer_role=""))
        g = proof("CONFIRMED", "CONFIRMED")
        del g["verdicts"][1]["grader_role"]
        self.no("proved", g)
        # namespaced names are compared bare
        self.no("supported", comp(producer_role="researcher:experiment-reviewer"))

    def test_human_quote(self):
        self.ok("proved", {"basis": "human", "quote": "Lemma 4.2 is fine, I checked it",
                           "where": "chat 2026-09-28"}, human=True)
        self.no("proved", {"basis": "human", "quote": "  "}, human=True)
        self.ok("refuted", {"basis": "human", "quote": "that's false"}, human=True)
        # from an agent, the quote must be pinned to a ticket or packet
        self.no("proved", {"basis": "human", "quote": "fine", "where": "chat"})
        self.ok("proved", {"basis": "human", "quote": "fine", "where": "T-0003 thread"})

    def test_roles_fit_the_basis(self):
        self.no("proved", proof("CONFIRMED", "CONFIRMED", producer_role="claim-keeper",
                                verdicts=proof_rows("CONFIRMED", "CONFIRMED",
                                                    grader="experimenter")))
        why = self.no("supported", rows_of(comp(), grader_role="prover"))
        self.assertIn("graded by experiment-reviewer", " ".join(why))
        why = self.no("supported", rows_of(comp(producer_role="experiment-reviewer"),
                                           grader_role="experimenter"))
        self.assertIn("graded by experiment-reviewer", " ".join(why))
        self.ok("proved", proof("CONFIRMED", "CONFIRMED", producer_role="researcher",
                                verdicts=proof_rows("CONFIRMED", "CONFIRMED",
                                                    grader="expert")))
        g = proof("CONFIRMED", "CONFIRMED")
        del g["verdicts"][0]["ref"]
        self.no("proved", g)

    def test_lifecycle_targets(self):
        self.ok("dropped", {"basis": "human", "quote": "drop it"}, human=True)
        self.ok("dropped", {"basis": "proof", "note": "out of scope"})
        self.no("superseded", {"basis": "proof", "note": "restated"})
        self.ok("superseded", {"basis": "proof", "note": "restated",
                               "superseded_by": "lab:new"})

    def test_computation(self):
        self.ok("supported", comp())
        self.ok("supported", comp(("SOUND MODULO", "sound_modulo")))
        self.ok("refuted", comp(outcome="refutes"))
        why = self.no("proved", comp())
        self.assertIn("computation never establishes", why[0])
        self.no("proved-modulo", comp())
        self.no("supported", comp(("SOUND", "GAP")))
        self.no("supported", comp(("SOUND", "SOUND MODULO")))
        self.no("supported", comp(("SOUND",)))
        self.no("supported", comp(validation_passed=False))
        self.no("supported", comp(commit=""))
        self.no("supported", comp(outcome="refutes"))
        g = comp()
        g["verdicts"][1]["commit"] = "other"
        g["verdicts"][0]["commit"] = "c0ffee"
        self.no("supported", g)

    def test_human_grounds_still_checked(self):
        self.no("proved", comp(), human=True)

    def test_unsettled_needs_reason(self):
        self.no("sketch", {"basis": "proof"})
        self.ok("sketch", {"basis": "proof", "note": "run A found a gap"})
        self.no("open", {"basis": "whim", "note": "x"})


LAB_CLAIM = """---
id: lab:ew
title: EW check
status: open
where: experiments/x.py
evidence: []
history:
  - 2026-09-20 | open | created
---
Body.
"""

S1_CLAIM = """---
id: GEO-1
aliases: [N1]
title: Corners
summary: Corners of P are cycles
kind: prop
status: Not settled
---
## Statement
Corners of $P$ are cycles.

## History
- 2026-09-20: created
"""


class TestRegistryBackend(McpTestBase):
    """claims_* on the registry engine, against the temp homes (lab, notebook as s1)."""

    def setUp(self):
        lab, s1 = self.homes["scientist@t"], self.homes["researcher@t"]
        write(os.path.join(lab, "claims", "lab", "ew.md"), LAB_CLAIM)
        write(os.path.join(lab, "results", "ew.json"), "{}")
        write(os.path.join(lab, "experiments", "x.py"), '"""h\n\nClaims: lab:ew\n"""\n')
        write(os.path.join(lab, "audits", "ew-A.md"), "A\n")
        for i, r in enumerate("AB"):
            write(os.path.join(lab, "audits", "ew", "2026-09-28-%s.md" % r),
                  "---\nsubject: lab:ew\nrun: %s\nrun_id: e%d\nverdict: SOUND\n"
                  "landed_by: researcher/land_review\n---\nreport\n" % (r, i))
        write(os.path.join(s1, "tools", "kb.py"), "# layout marker\n")
        write(os.path.join(s1, "claims", "GEO-1.md"), S1_CLAIM)
        write(os.path.join(s1, "computation", "verdicts", "2026-09-28_GEO-1.md"),
              "---\nid: 2026-09-28_GEO-1\nsubjects: [GEO-1]\nclears: [GEO-1]\n---\n"
              "Run A: VERDICT — label: Proved; confidence: CONFIRMED\n"
              "Run B: VERDICT — label: Proved; confidence: CONFIRMED\n")
        # the review finding: a file about nothing, whose body says GAP
        write(os.path.join(s1, "computation", "verdicts", "2026-09-28_empty.md"),
              "---\nid: 2026-09-28_empty\nsubjects: []\n---\nRun A: GAP\nRun B: GAP\n")

    def tearDown(self):
        for h in (self.homes["scientist@t"], self.homes["researcher@t"]):
            for d in ("claims", "results", "experiments", "audits", "tools", "computation",
                      "kb", "site", "STATUS.md", "INDEX.md", "OPEN.md"):
                p = os.path.join(h, d)
                if os.path.isdir(p):
                    shutil.rmtree(p)
                elif os.path.isfile(p):
                    os.remove(p)

    def lab_text(self):
        with open(os.path.join(self.homes["scientist@t"], "claims", "lab", "ew.md"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_reads(self):
        s = self.server("scientist@t")
        err, res = s.call("claims_show", id="lab:ew")
        self.assertFalse(err, res)
        self.assertIn("id: lab:ew", res["stdout"])
        self.assertIn("experiment experiments/x.py", res["stdout"])
        err, res = s.call("claims_list", ns="lab")
        self.assertIn("lab:ew", res["stdout"])
        err, res = s.call("claims_query", ns="lab", sql="select status from claims")
        self.assertIn("open", res["stdout"])
        err, res = s.call("claims_check", ns="lab")
        self.assertEqual(res["exit"], 0, res)
        err, res = s.call("claims_show", id="s1:N1")          # an alias, through s1-kb
        self.assertFalse(err, res)
        self.assertIn("(resolved from alias 'N1')", res["stdout"])
        err, res = s.call("claims_query", ns="s1", sql="select id from entities")
        self.assertIn("GEO-1", res["stdout"])
        err, res = s.call("claims_list", ns="nope")
        self.assertTrue(err)

    def test_set_status_with_grounds_edits_the_record(self):
        s = self.server("researcher@t")
        g = comp()
        err, res = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:ew", status="supported", grounds=g, note="two audits")
        self.assertFalse(err, res)
        text = self.lab_text()
        self.assertIn("status: supported", text)
        self.assertIn("| supported | two audits; computation review (SOUND e0, SOUND e1)",
                      text)
        self.assertIn("audit | audits/ew/2026-09-28-A.md | SOUND | run e0; grader "
                      "researcher:experiment-reviewer", text)
        self.assertIn("audit | audits/ew/2026-09-28-B.md | SOUND | run e1", text)
        self.assertEqual(res["check"]["exit"], 0, res)
        # computation never proves, whatever the file says
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:ew", status="proved", grounds=comp())
        self.assertTrue(err)
        self.assertIn("computation never establishes", msg)
        self.assertIn("status: supported", self.lab_text())

    def test_set_status_refused_by_the_record_check(self):
        # the human's word passes, but `refuted-as-stated` without `superseded_by` fails
        # the record's check
        s = self.server("researcher@t")
        before = self.lab_text()
        err, msg = s.call("claims_set_status", id="lab:ew", status="refuted-as-stated",
                          grounds={"basis": "human", "quote": "false as written"})
        self.assertTrue(err)
        self.assertIn("inconsistent", msg)
        self.assertEqual(self.lab_text(), before)

    def test_made_up_verdicts_are_refused(self):
        # the review finding: two SOUND verdicts with invented run ids and no records
        s = self.server("researcher@t")
        before = self.lab_text()
        swapped = comp()
        swapped["verdicts"] = [dict(r, run_id=o["run_id"]) for r, o in
                               zip(swapped["verdicts"], reversed(swapped["verdicts"]))]
        for g, why in (
                (rows_of(comp(), ref=None), "ref of its review record"),
                (rows_of(comp(), ref="audits/none.md"), "not found"),
                (swapped, "is run e")):
            err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                              id="lab:ew", status="supported", grounds=g)
            self.assertTrue(err, g)
            self.assertIn(why, msg)
            self.assertEqual(self.lab_text(), before)

    def test_human_quote_by_claim_keeper(self):
        s = self.server("researcher@t")
        word = {"basis": "human", "quote": "drop it", "where": "chat"}
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:ew", status="refuted", grounds=word)
        self.assertTrue(err)                               # not pinned to the board
        self.assertIn("ticket or packet", msg)
        err, t = self.server().call("tickets_create", title="lab:ew", kind="decision",
                                    to="researcher@t", ask="Roey: drop it, it is false.",
                                    deliverable="d")
        self.assertFalse(err, t)
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:ew", status="refuted",
                          grounds=dict(word, quote="it is true", where=t["id"]))
        self.assertTrue(err)                               # the ticket does not say so
        self.assertIn("does not contain the quote", msg)
        err, res = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:ew", status="refuted", grounds=dict(word, where=t["id"]))
        self.assertFalse(err, res)
        text = self.lab_text()
        self.assertIn("status: refuted", text)
        self.assertIn('Roey\'s word "drop it" (%s)' % t["id"], text)
        self.assertIn("hand | %s | Roey's word" % t["id"], text)

    def test_lifecycle_move(self):
        write(os.path.join(self.homes["scientist@t"], "claims", "lab", "ew2.md"),
              LAB_CLAIM.replace("lab:ew", "lab:ew2"))
        s = self.server("researcher@t")
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:ew", status="superseded",
                          grounds={"basis": "proof", "note": "restated"})
        self.assertTrue(err)
        self.assertIn("superseded_by", msg)
        err, res = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="lab:ew", status="superseded",
                          grounds={"basis": "proof", "note": "restated",
                                   "superseded_by": "lab:ew2"})
        self.assertFalse(err, res)
        text = self.lab_text()
        self.assertIn("status: superseded", text)          # a v1 record: the old words
        self.assertIn("superseded_by: lab:ew2", text)
        self.assertIn("superseded by lab:ew2", text)

    def test_attach_evidence_is_append_only(self):
        s = self.server("researcher@t")
        row = {"type": "audit", "ref": "audits/ew-A.md", "verdict": "SOUND", "run_id": "A"}
        err, res = s.call("claims_attach_evidence", caller="researcher:claim-keeper",
                          id="lab:ew", row=row)
        self.assertFalse(err, res)
        self.assertIn("audit | audits/ew-A.md | SOUND | run A", self.lab_text())
        err, msg = s.call("claims_attach_evidence", caller="researcher:claim-keeper",
                          id="lab:ew", row=row)
        self.assertTrue(err)
        self.assertIn("already recorded", msg)
        err, msg = s.call("claims_attach_evidence", caller="researcher:claim-keeper",
                          id="lab:ew", row=dict(row, ref="audits/none.md"))
        self.assertTrue(err)
        self.assertIn("does not exist", msg)

    def test_s1_set_status(self):
        s = self.server("researcher@t")
        vfile = "computation/verdicts/2026-09-28_GEO-1.md"
        # proof verdicts given on another statement than GEO-1's current one
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="s1:GEO-1", status="proved",
                          grounds=proof("CONFIRMED", "CONFIRMED", verdict_file=vfile))
        self.assertTrue(err)
        self.assertIn("statement hash", msg)
        err, t = self.server().call("tickets_create", title="GEO-1", kind="decision",
                                    to="researcher@t", ask="GEO-1 is proved, see the verdict",
                                    deliverable="d")
        word = {"basis": "human", "quote": "GEO-1 is proved, see the verdict",
                "where": t["id"]}
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="s1:GEO-1", status="proved", grounds=word)
        self.assertTrue(err)
        self.assertIn("verdict_file", msg)
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="s1:GEO-1", status="supported", grounds=comp())
        self.assertTrue(err)
        self.assertIn("no s1 word", msg)
        # the review finding: a verdict file with no subject, whose runs say GAP
        path = os.path.join(self.homes["researcher@t"], "claims", "GEO-1.md")
        with open(path, "rb") as fh:
            before = fh.read()
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="s1:GEO-1", status="proved", grounds=dict(
                              word, verdict_file="computation/verdicts/2026-09-28_empty.md"))
        self.assertTrue(err)
        self.assertIn("does not clear GEO-1", msg)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), before)
        err, res = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="s1:GEO-1", status="proved", grounds=dict(word, verdict_file=vfile))
        self.assertFalse(err, res)
        with open(os.path.join(self.homes["researcher@t"], "claims", "GEO-1.md"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("status: Proved", text)
        self.assertIn("cleared_by: [%s]" % vfile, text)
        self.assertIn("status Not settled → Proved (verdict %s)" % vfile, text)

    def test_s1_set_status_on_an_expert_review(self):
        # phase 7 (P-0004 D9, P-0005 D8): the claim verdicts live in the Expert's library
        # and the grounds name them by the protocol ref file:expert@<name>/reviews/...
        lib = self.homes["expert@t"]
        self.addCleanup(shutil.rmtree, os.path.join(lib, "reviews"), True)
        src = os.path.join(self.homes["researcher@t"], "computation", "verdicts",
                           "2026-09-28_GEO-1.md")
        with open(src, encoding="utf-8") as fh:
            write(os.path.join(lib, "reviews", "s1", "GEO-1", "2026-09-28_GEO-1.md"), fh.read())
        os.remove(src)                                     # only the library copy is left
        ref = "file:expert@t/reviews/s1/GEO-1/2026-09-28_GEO-1.md"
        s = self.server("researcher@t")
        err, t = self.server().call("tickets_create", title="GEO-1", kind="decision",
                                    to="researcher@t", ask="GEO-1 is proved, see the review",
                                    deliverable="d")
        word = {"basis": "human", "quote": "GEO-1 is proved, see the review", "where": t["id"]}
        err, msg = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="s1:GEO-1", status="proved",
                          grounds=dict(word, verdict_file=ref.replace("GEO-1.md", "GEO-2.md")))
        self.assertTrue(err)
        self.assertIn("nor an Expert review ref", msg)
        err, res = s.call("claims_set_status", caller="researcher:claim-keeper",
                          id="s1:GEO-1", status="proved", grounds=dict(word, verdict_file=ref))
        self.assertFalse(err, res)
        with open(os.path.join(self.homes["researcher@t"], "claims", "GEO-1.md"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("status: Proved", text)
        self.assertIn("cleared_by: [%s]" % ref, text)

    def test_deps_across_namespaces(self):
        lab = self.homes["scientist@t"]
        write(os.path.join(lab, "claims", "lab", "ew.md"),
              LAB_CLAIM.replace("evidence: []", "depends_on:\n  - s1:N1\nevidence: []"))
        s = self.server("scientist@t")
        err, res = s.call("claims_deps", id="lab:ew")
        self.assertFalse(err, res)
        self.assertEqual([(e["from"], e["to"]) for e in res["edges"]], [("lab:ew", "s1:GEO-1")])
        err, res = s.call("claims_deps", id="s1:GEO-1", reverse=True, transitive=True)
        self.assertEqual([e["from"] for e in res["edges"]], ["lab:ew"])
        self.assertEqual(res["edges"][0]["status"], "open")



def _real_home(**want):
    """The home of the first workspace.json instance matching ``want`` (role=..., ns=...), or ''
    when there is no workspace: these tests run against real homes only where they exist."""
    try:
        with open(os.environ["ACADEMY_WORKSPACE"], encoding="utf-8-sig") as fh:
            ws = json.load(fh)
    except (KeyError, OSError, ValueError):
        return ""
    for inst in ws.get("instances", {}).values():
        if all(inst.get(k) == v for k, v in want.items()):
            return inst["home"]
    return ""


REAL_LAB = _real_home(ns="lab")
REAL_S1 = _real_home(ns="s1")
REAL_PAPER = _real_home(ns="paper")


REGISTRY_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "scripts", "registry.py")


@unittest.skipUnless(REAL_LAB and REAL_S1 and REAL_PAPER and os.path.isdir(REAL_LAB + "/claims")
                     and os.path.isdir(REAL_S1 + "/objects"),
                     "the real registries are not on this machine")
class TestRealRegistries(unittest.TestCase):
    """claims_show equals the legacy command line (read-only on the homes)."""

    def run_cli(self, argv, cwd):
        p = subprocess.run([sys.executable] + argv, cwd=cwd, capture_output=True,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
        return p.stdout.decode("utf-8").replace("\r\n", "\n")

    def test_show_matches_cli(self):
        callers = tempfile.mkdtemp(prefix="academy-callers-")
        self.addCleanup(shutil.rmtree, callers, True)
        env = dict(os.environ, PYTHONUTF8="1", ACADEMY_CALLER_DIR=callers)
        env.pop("ACADEMY_WORKSPACE", None)
        s = Server(REAL_LAB, env)
        self.addCleanup(s.close)
        s.request("initialize", {"protocolVersion": "2025-06-18"})
        cases = [
            ("lab:descent-family-n-le-7", [REGISTRY_PY, "--repo", REAL_LAB, "show",
                                           "lab:descent-family-n-le-7"], REAL_LAB),
            ("paper:conj:origami-slope",
             [REGISTRY_PY, "--repo", REAL_PAPER,
              "show", "paper:conj:origami-slope"], REAL_LAB),
            ("s1:BOUND-1", [REGISTRY_PY, "--repo", REAL_S1, "show", "BOUND-1"], REAL_S1),
        ]
        for cid, argv, cwd in cases:
            err, res = s.call("claims_show", id=cid)
            self.assertFalse(err, res)
            self.assertEqual(res["exit"], 0, res)
            self.assertEqual(res["stdout"], self.run_cli(argv, cwd), cid)


class TestChainGate(McpTestBase):
    def create(self, s, caller=None, **kw):
        args = dict(title="t", kind="question", ask="a", deliverable="d")
        args.update(kw)
        return s.call("tickets_create", caller=caller, **args)

    def test_main_session_in_a_home_files_as_the_home(self):
        err, t = self.create(self.server("author@t"), to="expert@t")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "author@t")
        err, g = self.server().call("tickets_get", id=t["id"])
        self.assertIn("author@t/main: opened", g["body"])

    def test_main_session_outside_homes_is_human(self):
        err, t = self.create(self.server(), to="scientist@t")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "human")

    def test_as_human_from_a_home(self):
        err, t = self.create(self.server("author@t"), to="scientist@t", as_human=True)
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "human")

    def test_as_human_refused_to_agents(self):
        err, msg = self.create(self.server("author@t"), caller="author:math-writer",
                               to="expert@t", as_human=True)
        self.assertTrue(err)
        self.assertIn("as_human", msg)

    def test_non_neighbour_refused(self):
        err, msg = self.create(self.server("author@t"), to="researcher@t", kind="prove")
        self.assertTrue(err)
        self.assertIn("final_to researcher", msg)

    def test_non_liaison_refused(self):
        err, msg = self.create(self.server("author@t"), caller="author:tex-engineer",
                               to="expert@t")
        self.assertTrue(err)
        self.assertIn("liaison", msg)

    def test_research_with_final_to(self):
        err, t = self.create(self.server("author@t"), to="expert@t", kind="research",
                             final_to="researcher")
        self.assertFalse(err, t)
        err, g = self.server().call("tickets_get", id=t["id"])
        self.assertEqual(g["meta"]["final_to"], "researcher")

    def test_propose_status_is_clerical(self):
        # author@t -> researcher@t is not a neighbour edge; a proposal is clerical
        err, res = self.server("author@t").call(
            "claims_propose_status", caller="author:math-editor", id="paper:lem:x",
            status="proved", reason="r")
        self.assertFalse(err, res)
        self.assertEqual(res["from"], "author@t")
        self.assertEqual(res["to"], "researcher@t")
        err, g = self.server().call("tickets_get", id=res["id"])
        self.assertEqual(g["meta"]["kind"], "decision")

    def test_main_session_updates_stay_human(self):
        err, t = self.create(self.server("author@t"), to="expert@t")
        self.assertFalse(err, t)
        err, res = self.server("author@t").call("tickets_update", id=t["id"],
                                                fields={"to": "researcher@t"})
        self.assertFalse(err, res)            # only the human re-routes; still allowed


if __name__ == "__main__":
    unittest.main()
