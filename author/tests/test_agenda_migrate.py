"""agenda_migrate.py: the one-shot converter from an old Drafts/roadmap.md to tickets.

Dry run by default; --apply files through board.create_ticket; the roadmap file is only
ever read; a second run files nothing new.
"""

import hashlib
import json
import os
import subprocess
import sys
import unittest

from fixtures import SCRIPTS, Sandbox
from test_inbox import AGENDA, ticket

sys.path.insert(0, SCRIPTS)
import agenda_migrate as am  # noqa: E402
import _academy as ac  # noqa: E402


def item(iid, tag, title, **fields):
    body = fields.pop("body", "Do %s." % title)
    lines = ["## %s [%s] %s" % (iid, tag, title)]
    fields = dict([("status", fields.pop("status", "open"))] + list(fields.items()))
    for k, v in fields.items():
        lines.append("- %s: %s" % (k, v))
    return "\n".join(lines) + "\n\n" + body + "\n"


ROADMAP = "# Roadmap: author@t\n\nPreamble.\n\n## Notes\n\nprose\n\n" + "\n".join([
    item("R-0001", "apply", "Fix lem:d wording", agenda="paper:lem:d"),
    item("R-0002", "write", "Explain lem:b", agenda="lem:b", priority="low"),
    item("R-0003", "apply", "Main theorem edit", agenda="paper:thm:main", priority="high",
         depends_on="[R-0004]"),
    item("R-0004", "write", "Global prose pass", agenda="global", priority="high"),
    item("R-0005", "verify", "Verify lem:b", agenda="paper:lem:b"),
    item("R-0006", "lead", "Prove lem:d", agenda="paper:lem:d", status="ticketed",
         ticket="T-0002"),
    item("R-0007", "cite", "Cite LMW16", agenda="global", status="ticketed", ticket="T-0003"),
    item("R-0008", "apply", "Already done", agenda="global", status="done"),
    item("R-0009", "write", "Ask Roey", agenda="global", status="needs-human"),
    item("R-0010", "apply", "After a rejected ticket", agenda="prop:a",
         depends_on="[T-0004]"),
    item("R-0011", "lead", "Prove thm:main", agenda="paper:thm:main"),
    item("R-0012", "write", "After prop:a", agenda="global", depends_on="[paper:prop:a]"),
    item("R-0013", "write", "Route to the figure maker", agenda="global",
         route="figure-maker"),
    item("R-0014", "cite", "Cite after the verify", agenda="global", depends_on="[R-0005]"),
    item("R-0015", "write", "Dropped idea", status="dropped"),
])


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class MigrateTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.agenda = os.path.join(self.sb.home, "Drafts", "agenda.md")
        self.roadmap = os.path.join(self.sb.home, "Drafts", "roadmap.md")
        self.sb.write(self.agenda, AGENDA)
        self.sb.write(self.roadmap, ROADMAP)
        b = self.sb.board
        ticket(b, "T-0002", "researcher@t", "delivered", kind="prove", result="proved")
        ticket(b, "T-0003", "expert@t", "open", kind="cite")
        ticket(b, "T-0004", "expert@t", "rejected", kind="verify")
        os.environ["ACADEMY_WORKSPACE"] = self.sb.workspace

    def tearDown(self):
        os.environ.pop("ACADEMY_WORKSPACE", None)
        self.sb.cleanup()

    def run_cli(self, *args):
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "agenda_migrate.py"),
                              "--roadmap", self.roadmap, "--home", self.sb.home] + list(args),
                             capture_output=True, env=dict(self.sb.env))
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")

    def all_tickets(self):
        out = {}
        for folder in os.listdir(self.sb.board):
            d = os.path.join(self.sb.board, folder)
            for f in os.listdir(d):
                if f.startswith("T-"):
                    meta, body = ac.read_frontmatter(self.sb.read(os.path.join(d, f)))
                    out[meta["id"]] = dict(meta, _body=body)
        return out

    def by_item(self, made_json):
        tix = self.all_tickets()
        return {i: tix[t] for i, t in made_json["made"].items()}

    def test_parse_reads_items_and_ignores_prose_sections(self):
        items = am.parse_items(ROADMAP)
        self.assertEqual(len(items), 15)
        it = items[2]
        self.assertEqual((it.id, it.tag, it.priority, it.depends_on, it.agenda),
                         ("R-0003", "apply", "high", ["R-0004"], "paper:thm:main"))
        with self.assertRaises(am.al.AgendaError):
            am.parse_items("## R-0001 [write] a\n\n## R-0001 [write] b\n")

    def test_dry_run_is_the_default_and_files_nothing(self):
        before = set(self.all_tickets())
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertIn("DRY RUN", out)
        self.assertIn("Nothing was written", out)
        self.assertEqual(set(self.all_tickets()), before)
        code, out, err = self.run_cli("--json")
        d = json.loads(out)
        self.assertTrue(d["dry_run"])
        self.assertEqual(d["made"], {})
        self.assertGreater(len(d["convert"]), 5)

    def test_the_mapping(self):
        code, out, err = self.run_cli("--apply", "--json")
        self.assertEqual(code, 0, err)
        d = json.loads(out)
        self.assertFalse(d["dry_run"])
        t = self.by_item(d)
        # local tags -> self-tickets of that kind, agenda as the claim id
        for iid, kind, agenda in (("R-0001", "apply", "paper:lem:d"),
                                  ("R-0002", "write", "paper:lem:b"),
                                  ("R-0004", "write", "global"),
                                  ("R-0013", "figure", "global")):
            m = t[iid]
            self.assertEqual((m["from"], m["to"], m["kind"], m["agenda"]),
                             ("author@t", "author@t", kind, agenda), iid)
            self.assertEqual(ac.validate_ticket({k: v for k, v in m.items()
                                                 if k != "_body"}), [], iid)
            self.assertIn("roadmap item %s" % iid, m["_body"])
        self.assertEqual(t["R-0001"]["refs"], ["paper:lem:d"])
        self.assertEqual(t["R-0002"]["priority"], "low")
        self.assertIn("Do Fix lem:d wording.", t["R-0001"]["_body"])
        # asks -> the Expert, research with final_to for a lead
        self.assertEqual((t["R-0005"]["to"], t["R-0005"]["kind"], t["R-0005"]["refs"]),
                         ("expert@t", "verify", ["paper:lem:b"]))
        self.assertEqual((t["R-0011"]["to"], t["R-0011"]["kind"], t["R-0011"]["final_to"]),
                         ("expert@t", "research", "researcher"))
        # needs-human -> a self-ticket parked on human
        self.assertEqual((t["R-0009"]["status"], t["R-0009"]["waiting_on"]),
                         ("blocked", ["human"]))
        # an item depending on an item -> a self-ticket waiting on that item's ticket
        self.assertEqual((t["R-0003"]["status"], t["R-0003"]["waiting_on"]),
                         ("blocked", [d["made"]["R-0004"]]))
        # a dependency on a claim is text, not a wait
        self.assertEqual(t["R-0012"]["status"], "open")
        self.assertIn("paper:prop:a", t["R-0012"]["_body"])
        self.assertIn("paper:prop:a", t["R-0012"]["refs"])
        # done / dropped / already ticketed: not converted
        for iid in ("R-0006", "R-0007", "R-0008", "R-0015"):
            self.assertNotIn(iid, d["made"])
        self.assertEqual({s["item"]: s["ticket"] for s in d["skipped"]},
                         {"R-0006": "T-0002", "R-0007": "T-0003"})
        self.assertEqual((d["counts"]["done"], d["counts"]["dropped"]), (1, 1))

    def test_held_items_are_reported_not_filed(self):
        code, out, err = self.run_cli("--apply", "--json")
        d = json.loads(out)
        held = {h["item"]: h["why"] for h in d["held"]}
        self.assertIn("rejected", held["R-0010"])            # depends on a rejected ticket
        self.assertIn("run again", held["R-0014"])           # an ask waiting on R-0005
        self.assertNotIn("R-0010", d["made"])
        self.assertNotIn("R-0014", d["made"])

    def test_a_second_run_files_nothing_new(self):
        self.assertEqual(self.run_cli("--apply")[0], 0)
        before = set(self.all_tickets())
        code, out, err = self.run_cli("--apply", "--json")
        d = json.loads(out)
        self.assertEqual(code, 1, err)                        # nothing to convert
        self.assertEqual(d["made"], {})
        self.assertEqual(set(self.all_tickets()), before)

    def test_a_held_ask_is_filed_on_a_later_run_once_its_dependency_is_met(self):
        first = json.loads(self.run_cli("--apply", "--json")[1])
        tid = first["made"]["R-0005"]
        bd = am.gp.board_module()
        for st in ("accepted", "in-progress"):
            bd.transition_ticket(self.sb.board, tid, st, as_instance="expert@t")
        bd.transition_ticket(self.sb.board, tid, "delivered", result="CONFIRMED",
                             as_instance="expert@t")
        second = json.loads(self.run_cli("--apply", "--json")[1])
        self.assertEqual(list(second["made"]), ["R-0014"])

    def test_the_roadmap_file_is_never_modified(self):
        before = sha(self.roadmap)
        self.run_cli()
        self.run_cli("--apply")
        self.run_cli("--apply")
        self.assertEqual(sha(self.roadmap), before)

    def test_the_converter_only_ever_opens_the_roadmap_for_reading(self):
        import builtins
        import io
        import contextlib
        real = builtins.open
        opened = []

        def spy(file, mode="r", *a, **k):
            if os.path.basename(str(file)) == "roadmap.md":
                opened.append(mode)
            return real(file, mode, *a, **k)

        before = sha(self.roadmap)
        builtins.open = spy
        try:
            for args in (["--roadmap", self.roadmap, "--home", self.sb.home],
                         ["--roadmap", self.roadmap, "--home", self.sb.home, "--apply"],
                         ["--roadmap", self.roadmap, "--home", self.sb.home, "--apply"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    am.main(args)
        finally:
            builtins.open = real
        self.assertTrue(opened)                               # it does read the file
        self.assertTrue(all(not set(m) & set("wax+") for m in opened), opened)
        self.assertEqual(sha(self.roadmap), before)

    def ctx(self):
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        return am.nx.Context(self.agenda, self.sb.board, ws, "author@t", "paper", 3, ["dom"])

    def plan_of(self, *items):
        ctx = self.ctx()
        return am.plan(ctx, am.parse_items("\n".join(items))), ctx

    def test_a_converted_item_whose_ticket_died_is_reported_not_refiled(self):
        self.assertEqual(self.run_cli("--apply")[0], 0)
        made = json.loads(self.run_cli("--json")[1])       # dry run: nothing new
        self.assertEqual(made["convert"], [])
        first = {t: m for t, m in self.all_tickets().items() if "roadmap item R-0001"
                 in m["_body"]}
        tid = next(iter(first))
        bd = am.gp.board_module()
        bd.transition_ticket(self.sb.board, tid, "cancelled", reason="no longer wanted",
                             as_instance="author@t")
        before = set(self.all_tickets())
        code, out, err = self.run_cli("--apply", "--json")
        d = json.loads(out)
        self.assertEqual(code, 1, err)
        self.assertEqual(d["made"], {})
        self.assertEqual(set(self.all_tickets()), before)       # nothing re-filed
        skipped = {s["item"]: s for s in d["skipped"]}
        self.assertEqual(skipped["R-0001"]["ticket"], tid)
        self.assertIn("cancelled", skipped["R-0001"]["why"])
        self.assertIn("not filed again", skipped["R-0001"]["why"])

    def test_dependants_of_a_dead_ticket_are_held_however_they_name_it(self):
        pl, _ = self.plan_of(
            item("R-0001", "write", "direct", depends_on="[T-0004]"),                # rejected
            item("R-0002", "write", "via ticketed", status="ticketed", ticket="T-0004"),
            item("R-0003", "write", "through the item", depends_on="[R-0002]"))
        held = {h["item"]: h["why"] for h in pl["held"]}
        self.assertIn("rejected", held["R-0001"])
        self.assertIn("rejected", held["R-0003"])            # same outcome as the direct one
        self.assertIn("R-0002", held["R-0003"])
        self.assertEqual(pl["convert"], [])

    def test_a_dependant_of_an_item_converted_earlier_whose_ticket_died_is_held(self):
        ctx = self.ctx()
        first = am.parse_items(item("R-0001", "write", "first", agenda="global"))
        made = am.apply(ctx, am.plan(ctx, first))
        am.gp.board_module().transition_ticket(self.sb.board, made["R-0001"], "cancelled",
                                               reason="x", as_instance="author@t")
        ctx = self.ctx()
        both = am.parse_items(item("R-0001", "write", "first", agenda="global") + "\n" +
                              item("R-0002", "write", "second", depends_on="[R-0001]"))
        pl = am.plan(ctx, both)
        self.assertEqual(pl["convert"], [])                      # nothing re-filed
        self.assertIn("cancelled", {h["item"]: h["why"] for h in pl["held"]}["R-0002"])
        self.assertIn("cancelled", pl["skipped"][0]["why"])

    def test_branches_cycle_unknown_tag_unknown_status(self):
        pl, _ = self.plan_of(
            item("R-0001", "write", "a", depends_on="[R-0002]"),
            item("R-0002", "write", "b", depends_on="[R-0001]"),
            item("R-0003", "banana", "weird tag"),
            item("R-0004", "write", "weird status", status="sleeping"))
        held = {h["item"]: h["why"] for h in pl["held"]}
        self.assertIn("cycle", held["R-0001"])
        self.assertIn("cycle", held["R-0002"])
        self.assertIn("unknown tag [banana]", held["R-0003"])
        self.assertIn("unknown status 'sleeping'", held["R-0004"])
        self.assertEqual(pl["convert"], [])
        self.assertEqual(len(pl["problems"]), 2)

    def test_branches_ticketed_but_missing_and_unknown_dependencies(self):
        pl, _ = self.plan_of(
            item("R-0001", "lead", "ticketed, gone", status="ticketed", ticket="T-0099"),
            item("R-0002", "write", "after the gone one", depends_on="[R-0001]"),
            item("R-0003", "write", "unknown item", depends_on="[R-0077]"),
            item("R-0004", "write", "unknown ticket", depends_on="[T-0098]"),
            item("R-0005", "write", "after a dropped one", depends_on="[R-0006]"),
            item("R-0006", "write", "dropped", status="dropped"),
            item("R-0007", "write", "after a done one", depends_on="[R-0008]"),
            item("R-0008", "write", "done", status="done"))
        self.assertTrue(any("T-0099" in p and "not on the board" in p for p in pl["problems"]))
        held = {h["item"]: h["why"] for h in pl["held"]}
        self.assertIn("not on the board", held["R-0002"])
        self.assertIn("unknown item R-0077", held["R-0003"])
        self.assertIn("unknown ticket T-0098", held["R-0004"])
        self.assertIn("dropped", held["R-0005"])
        self.assertEqual([d["item"] for d in pl["convert"]], ["R-0007"])   # done: met
        self.assertEqual(pl["convert"][0]["waiting_on"], [])

    def test_campaign_is_carried_to_the_filed_tickets(self):
        d = json.loads(self.run_cli("--apply", "--json", "--campaign", "paper:thm:main")[1])
        tix = self.all_tickets()
        self.assertTrue(d["made"])
        self.assertTrue(all(tix[t].get("campaign") == "paper:thm:main"
                            for t in d["made"].values()))


if __name__ == "__main__":
    unittest.main()
