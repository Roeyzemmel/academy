"""The cite workflow (workflows/cite.js), 2026-10-31: one librarian run, the card checked by
cards.py validate with one fix, the packet and the delivery only after the check, a
mismatch and an unreachable source reported. Under node with a fake agent()."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "cite.js")
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, prompt, schema: opts.schema })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  const v = q.shift()
  if (v && v.__throw) throw new Error(v.__throw)     // a run that ended without its structured output
  return v
}
const body = new Function('args', 'agent', 'phase', 'log', 'return (async () => {' + src + '})()')
// the stage-order tests run nested, as from the inbox (no ship stage); the ship tests pass nested: false
// as the skills pass it (models.py launches prints {} under the default map); null: not given (#83)
body(Object.assign({ nested: true, models: {} }, plan.__args), agent, () => {}, () => {}).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""

ASK = {"ok": True, "detail": "", "ref": "10.1000/xyz", "pinpoint": "Thm 2", "relying": "paper:lem:x",
       "bib": "author@t:references.bib", "instance": "expert@t"}


def card(verdict="match", reachable=True):
    return {"key": "SW10", "pinpoint": "Thm 2", "card": "cards/SW10/thm-2.md", "verdict": verdict,
            "cached": True, "reachable": reachable, "bib_changed": True, "note": ""}


OK = {"ok": True, "errors": []}
BAD = {"ok": False, "errors": ["quote not found in SW10.txt"]}
MOVE = {"ok": True, "status": "delivered", "detail": ""}


@unittest.skipUnless(NODE, "node is not installed")
class CiteTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        d = tempfile.mkdtemp(prefix="acad-ct-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(dict(plan, __args=args))], capture_output=True, text=True, timeout=60)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], [c["label"] for c in out["calls"]], out["calls"]

    def test_clerk_stages_without_detail_lose_nothing(self):
        """#124 follow-up 2: ASK and MOVE ask for detail and do not require it."""
        ask = {k: v for k, v in ASK.items() if k != "detail"}
        res, labels, calls = self.run_wf({"start": [ask], "librarian": [card()], "validate": [OK],
                                          "packet": [{"packet": "P-0300", "error": ""}],
                                          "deliver": [{"ok": True, "status": "delivered"}]}, ticket="T-0904")
        for label in ("start", "deliver"):
            schema = next(c for c in calls if c["label"] == label)["schema"]
            self.assertIn("detail", schema["properties"], label)
            self.assertNotIn("detail", schema["required"], label)
        self.assertTrue(res["ticket_delivered"])
        res, labels, _ = self.run_wf({"start": [dict(ask, ok=False)]}, ticket="T-0904")
        self.assertEqual((res["outcome"], res["reason"]), ("not-started", "no reason given"))

    def test_the_happy_path_lands_after_validation(self):
        res, labels, calls = self.run_wf({"start": [ASK], "librarian": [card()], "validate": [OK],
                                          "packet": [{"packet": "P-0300", "error": ""}], "deliver": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels, ["start", "librarian", "validate", "packet", "deliver"])
        lib = next(c for c in calls if c["label"] == "librarian")
        self.assertEqual(lib["agentType"], "expert:librarian")
        self.assertIn("10.1000/xyz", lib["prompt"])
        self.assertIn("Never write an entry from memory", lib["prompt"])
        self.assertIn("SW10, Thm 2, verdict match", next(c for c in calls if c["label"] == "deliver")["prompt"])
        self.assertTrue(res["validated"])

    def test_one_fix_then_a_noted_failure(self):
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [card()], "validate": [BAD],
                                      "librarian (fix)": [card()], "validate again": [BAD],
                                      "packet": [{"packet": "P-0301", "error": ""}], "deliver": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels.count("librarian (fix)"), 1)
        self.assertFalse(res["validated"])
        self.assertIn("still fails validation", " ".join(res["notes"]))

    def test_mismatch_first_and_unreachable_noted_without_a_ticket(self):
        res, labels, _ = self.run_wf({"librarian": [card("the theorem needs compactness, the paper omits it", False)],
                                      "validate": [OK], "packet": [{"packet": "P-0302", "error": ""}]}, ref="SW10")
        self.assertEqual(labels, ["librarian", "validate", "packet"])
        self.assertTrue(res["notes"][0].startswith("MISMATCH"))
        self.assertIn("UNREACHABLE", " ".join(res["notes"]))

    def test_an_unreachable_source_with_a_ticket_is_parked_on_the_human(self):
        c = dict(card("unreachable", False), card="none written")
        res, labels, calls = self.run_wf({"start": [ASK], "librarian": [c], "packet": [{"packet": "P-0303", "error": ""}],
                                          "park on human": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels, ["start", "librarian", "packet", "park on human"])   # no validation of a card never written
        self.assertNotIn("deliver", labels)                                            # live run 2026-10-31: it was delivered
        self.assertIn("waiting_on [human]", next(x for x in calls if x["label"] == "park on human")["prompt"])
        self.assertEqual(res["outcome"], "unreachable (on the human)")
        self.assertEqual(res["gate"]["packet"], "P-0303")

    def test_a_lost_librarian_stops(self):
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [None], "librarian (retry)": [None],
                                      "lost note": [MOVE]}, ticket="T-0904")
        self.assertEqual(res["outcome"], "lost")
        self.assertNotIn("packet", labels)

    # #94: the librarian sometimes returns no result (T-1026, T-1614); on 2026-11-20 its schema
    # failure ("completed without calling StructuredOutput") ended the whole inbox run
    def test_a_librarian_with_no_result_is_retried_once(self):
        clean = {"exit": 0, "output": json.dumps({"bib_key": 1, "bib_id": 1, "cards": 1, "problems": [], "warnings": []})}
        res, labels, calls = self.run_wf({"start": [ASK], "librarian": [None], "librarian (retry)": [card()],
                                          "duplicates": [clean], "validate": [OK], "packet": [{"packet": "P-0300", "error": ""}],
                                          "deliver": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels, ["start", "librarian", "librarian (retry)", "duplicates", "validate", "packet", "deliver"])
        retry = next(c for c in calls if c["label"] == "librarian (retry)")
        self.assertIn("10.1000/xyz", retry["prompt"])
        self.assertIn("may already be on disk", retry["prompt"])      # never a second bib entry
        self.assertEqual(res["outcome"], "cited")
        self.assertIn("no result", " ".join(res["notes"]))

    # #94 review: a retried librarian may have written the bib entry or the card twice
    # (cards.py new refuses only an identical card path): the retry path counts them
    def test_after_a_retry_the_duplicates_are_counted_by_script(self):
        clean = {"exit": 0, "output": json.dumps({"bib_key": 1, "bib_id": 1, "cards": 1, "problems": [], "warnings": []})}
        res, labels, calls = self.run_wf({"start": [ASK], "librarian": [None], "librarian (retry)": [card()],
                                          "duplicates": [clean], "validate": [OK],
                                          "packet": [{"packet": "P-0300", "error": ""}], "deliver": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels, ["start", "librarian", "librarian (retry)", "duplicates", "validate", "packet", "deliver"])
        dup = next(c for c in calls if c["label"] == "duplicates")
        self.assertEqual(dup["agentType"], "academy:inbox-clerk")
        self.assertIn('cards.py dups SW10 "Thm 2" --bib "author@t:references.bib" --ref "10.1000/xyz" --json', dup["prompt"])
        self.assertEqual(dup["schema"]["required"], ["exit"])
        self.assertEqual(res["outcome"], "cited")

    def test_a_duplicate_after_the_retry_loses_the_ticket_with_a_note(self):
        two = {"exit": 1, "output": json.dumps({"bib_key": 2, "bib_id": 2, "cards": 1,
                                                "problems": ["2 entries with the key SW10 in /p/references.bib"], "warnings": []})}
        res, labels, calls = self.run_wf({"start": [ASK], "librarian": [None], "librarian (retry)": [card()],
                                          "duplicates": [two], "lost note": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels, ["start", "librarian", "librarian (retry)", "duplicates", "lost note"])
        self.assertEqual(res["outcome"], "lost")
        self.assertIn("2 entries with the key SW10", res["reason"])
        self.assertIn("2 entries with the key SW10", next(c for c in calls if c["label"] == "lost note")["prompt"])

    def test_a_duplicate_card_read_from_the_counts_alone_is_lost(self):
        # an output the code cannot parse: the counts the clerk returned decide
        res, labels, _ = self.run_wf({"librarian": [None], "librarian (retry)": [card()],
                                      "duplicates": [{"exit": 1, "output": "garbled", "cards": 2}]}, ref="SW10")
        self.assertEqual(res["outcome"], "lost")
        self.assertIn("duplicate", res["reason"])

    def test_a_lost_duplicate_check_is_noted_and_the_card_still_validated(self):
        res, labels, _ = self.run_wf({"librarian": [None], "librarian (retry)": [card()], "duplicates": [None],
                                      "validate": [OK], "packet": [{"packet": "P-0302", "error": ""}]}, ref="SW10")
        self.assertIn("validate", labels)
        self.assertIn("duplicate check returned nothing", " ".join(res["notes"]))

    def test_a_librarian_schema_failure_is_caught_retried_then_lost(self):
        boom = {"__throw": "agent({schema}): subagent completed without calling StructuredOutput (after in-conversation nudge)"}
        res, labels, calls = self.run_wf({"start": [ASK], "librarian": [boom], "librarian (retry)": [boom],
                                          "lost note": [MOVE]}, ticket="T-0904")
        self.assertEqual(res["outcome"], "lost")
        self.assertIn("twice", res["reason"])
        self.assertIn("unvalidated", res["reason"])
        self.assertEqual(labels, ["start", "librarian", "librarian (retry)", "lost note"])
        note = next(c for c in calls if c["label"] == "lost note")["prompt"]
        self.assertIn("ticket: T-0904", note)
        self.assertIn("note: append to the thread", note)
        self.assertIn("cards.py validate", note)
        self.assertNotIn("ticket_delivered", res)

    def test_a_lost_librarian_without_a_ticket_files_no_note(self):
        res, labels, _ = self.run_wf({"librarian": [None], "librarian (retry)": [None]}, ref="SW10")
        self.assertEqual(res["outcome"], "lost")
        self.assertEqual(labels, ["librarian", "librarian (retry)"])

    def test_a_librarian_fix_that_throws_is_lost_not_an_error(self):
        boom = {"__throw": "subagent completed without calling StructuredOutput"}
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [card()], "validate": [BAD],
                                      "librarian (fix)": [boom], "lost note": [MOVE]}, ticket="T-0904")
        self.assertEqual(res["outcome"], "lost")
        self.assertIn("fix", res["reason"])
        self.assertNotIn("packet", labels)

    def test_a_packet_stage_that_throws_is_noted_and_the_ticket_still_lands(self):
        boom = {"__throw": "subagent completed without calling StructuredOutput"}
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [card()], "validate": [OK],
                                      "packet": [boom], "deliver": [MOVE]}, ticket="T-0904")
        self.assertIn("deliver", labels)
        self.assertIsNone(res["packet"])
        self.assertIn("packet was not filed", " ".join(res["notes"]))


# ---- #108: the human's hand-back of an unreachable source --------------------------------

import sys  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import handback  # noqa: E402

REASON = ("source unreachable from this session: HU95; a human with access reads Lemma 4.1 "
          "for paper:lem:x")
PARKED = dict(ASK, ref="Hu, A rational polygon (1995)", pinpoint="Lemma 4.1", status="blocked",
              waiting_on=["human"], park_reason=REASON)
HUMAN_TEXT = "Lemma 4.1. Soit P un polygone rationnel; alors\nevery generalized diagonal is finite (\u00e9, \U0001d4ab)."


def rec(ok=True, recorded=("HU95.human.md",), texts=("HU95.human.md entry 1 (human-supplied, T-0904)",),
        problems=(), notes=()):
    j = {"ok": ok, "key": "HU95", "ticket": "T-0904", "recorded": list(recorded), "texts": list(texts),
         "already": False, "problems": list(problems), "notes": list(notes)}
    return {"exit": 0 if ok else 1, "output": json.dumps(j)}


def hcard(found=True, verdict="match", missing=""):
    c = {"key": "HU95", "pinpoint": "Lemma 4.1", "card": "cards/HU95/lemma-4-1.md" if found else "none written",
         "verdict": verdict, "found": found, "bib_changed": False, "note": ""}
    if missing:
        c["missing"] = missing
    return c


NOTE = {"ok": True, "status": "blocked"}


@unittest.skipUnless(NODE, "node is not installed")
class FromHumanTests(unittest.TestCase):
    """/expert:cite --from-human <ticket> <file|text>: a cite ticket parked on the human because its
    source was unreachable is resumed with what the human read: the material recorded by script,
    the card written from it (read_from human-supplied) and validated, the ticket unparked and
    delivered; material without the pinpoint leaves it parked with what is still missing."""
    run_wf = CiteTests.run_wf

    def plan(self, **over):
        p = {"start": [PARKED], "record text": [rec()], "librarian": [hcard()], "validate": [OK],
             "packet": [{"packet": "P-0400", "error": ""}], "unpark and deliver": [MOVE]}
        p.update(over)
        return p

    def test_a_text_is_recorded_by_script_then_the_card_then_the_delivery(self):
        res, labels, calls = self.run_wf(self.plan(), ticket="T-0904", from_human={"text": HUMAN_TEXT}, root="/acad")
        self.assertEqual(labels, ["start", "record text", "librarian", "validate", "packet", "unpark and deliver"])
        start = calls[0]["prompt"]
        self.assertIn("move nothing", start)
        r = calls[1]
        self.assertEqual(r["agentType"], "expert:librarian")      # it writes the text file: a clerk has no Write
        self.assertIn(HUMAN_TEXT, r["prompt"])                       # the human's words, unaltered
        self.assertIn("byte for byte", r["prompt"])
        self.assertIn("py /acad/expert/scripts/handback.py record HU95 --ticket T-0904 --pinpoint \"Lemma 4.1\"", r["prompt"])
        self.assertIn("--expect " + handback.text_hash(HUMAN_TEXT), r["prompt"])   # the same hash in JS and Python
        self.assertEqual(r["schema"]["required"], ["exit"])
        lib = calls[2]["prompt"]
        self.assertIn("human-supplied", lib)
        self.assertIn("HU95.human.md entry 1", lib)
        self.assertIn("fetch no text of the source", lib)
        self.assertIn("found false", lib)
        self.assertIn("--expect-read-from human-supplied", calls[3]["prompt"])
        dl = calls[5]["prompt"]
        self.assertIn("waiting_on []", dl)
        self.assertIn("in-progress", dl)
        self.assertIn("deliver: true", dl)
        self.assertIn("HU95, Lemma 4.1, verdict match, card cards/HU95/lemma-4-1.md", dl)
        self.assertEqual(res["outcome"], "cited (human-supplied)")
        self.assertTrue(res["ticket_delivered"])
        self.assertEqual(res["handback"]["files"], ["HU95.human.md"])

    def test_the_hash_matches_python_on_hard_text(self):
        for text in ("a", "  x\r\ny\n", "\u00e9\u2014\U0001d4ab $\\alpha$ \"q\" `b`"):
            res, labels, calls = self.run_wf(self.plan(), ticket="T-0904", from_human={"text": text})
            r = next(c for c in calls if c["label"] == "record text")["prompt"]
            self.assertIn("--expect " + handback.text_hash(text) + " ", r, text)

    def test_a_file_is_recorded_by_the_clerk(self):
        plan = self.plan(**{"record file": [rec(recorded=["HU95.human/2026-11-21-t-0904-p808.png"], texts=[],
                                                notes=["p808.png is an image"])]})
        del plan["record text"]
        res, labels, calls = self.run_wf(plan, ticket="T-0904", from_human={"file": "/ws/scratch/p 808.png"})
        self.assertEqual(labels, ["start", "record file", "librarian", "validate", "packet", "unpark and deliver"])
        f = calls[1]
        self.assertEqual(f["agentType"], "academy:inbox-clerk")
        self.assertIn('handback.py record HU95 --ticket T-0904 --pinpoint "Lemma 4.1" --file "/ws/scratch/p 808.png" --json', f["prompt"])
        self.assertIn("read the pages as images", calls[2]["prompt"])
        self.assertIn("p808.png is an image", " ".join(res["notes"]))

    def test_a_ticket_not_parked_on_the_human_is_not_started(self):
        for st in (dict(PARKED, status="in-progress", waiting_on=[]), dict(PARKED, waiting_on=["T-0001"])):
            res, labels, _ = self.run_wf({"start": [st]}, ticket="T-0904", from_human={"text": HUMAN_TEXT})
            self.assertEqual(labels, ["start"])
            self.assertEqual(res["outcome"], "not-started")
            self.assertIn("not parked on the human", res["reason"])

    def test_the_key_comes_from_the_park_reason_or_a_given_ref(self):
        res, labels, calls = self.run_wf(self.plan(), ticket="T-0904", from_human={"text": "x"}, ref="Ot99")
        self.assertIn("record Ot99 ", calls[1]["prompt"])
        st = dict(PARKED, park_reason="source unreachable from this session: 10.1000/xyz; a human with access reads x for y")
        res, labels, _ = self.run_wf({"start": [st]}, ticket="T-0904", from_human={"text": "x"})
        self.assertEqual(res["outcome"], "not-started")
        self.assertIn("no bibliography key", res["reason"])

    def test_material_without_the_pinpoint_leaves_the_ticket_parked_and_says_what_is_missing(self):
        miss = "the page shows Lemma 4.2 and the start of its proof; Lemma 4.1 is on the page before (p. 807)"
        res, labels, calls = self.run_wf({"start": [PARKED], "record text": [rec()],
                                          "librarian": [hcard(False, "n/a", miss)], "still parked": [NOTE]},
                                         ticket="T-0904", from_human={"text": HUMAN_TEXT})
        self.assertEqual(labels, ["start", "record text", "librarian", "still parked"])
        note = calls[-1]["prompt"]
        self.assertIn("note: append to the thread", note)
        self.assertIn(miss, note)
        self.assertIn("stays parked on the human", note)
        self.assertIn("move nothing", note)
        self.assertEqual(res["outcome"], "still missing (on the human)")
        self.assertFalse(res["ticket_delivered"])
        self.assertEqual(res["gate"]["missing"], miss)

    def test_a_text_that_does_not_hash_is_written_again_once_then_left_parked(self):
        bad = rec(False, recorded=[], texts=[], problems=["the text received differs from the text handed back"])
        res, labels, calls = self.run_wf({"start": [PARKED], "record text": [bad], "record text (retry)": [bad],
                                          "still parked": [NOTE]}, ticket="T-0904", from_human={"text": HUMAN_TEXT})
        self.assertEqual(labels, ["start", "record text", "record text (retry)", "still parked"])
        self.assertIn("differs from the text handed back", calls[2]["prompt"])
        self.assertEqual(res["outcome"], "not-recorded (on the human)")
        self.assertNotIn("librarian", labels)
        res, labels, _ = self.run_wf(self.plan(**{"record text": [bad], "record text (retry)": [rec()]}),
                                     ticket="T-0904", from_human={"text": HUMAN_TEXT})
        self.assertEqual(res["outcome"], "cited (human-supplied)")

    def test_a_card_that_fails_validation_twice_is_not_delivered(self):
        res, labels, calls = self.run_wf(self.plan(**{"validate": [BAD], "librarian (fix)": [hcard()],
                                                      "validate again": [BAD], "still parked": [NOTE]}),
                                         ticket="T-0904", from_human={"text": HUMAN_TEXT})
        self.assertEqual(labels, ["start", "record text", "librarian", "validate", "librarian (fix)",
                                  "validate again", "still parked"])
        self.assertEqual(res["outcome"], "unfinished (on the human)")
        self.assertIn("quote not found", calls[-1]["prompt"])
        self.assertNotIn("unpark and deliver", labels)

    def test_a_lost_librarian_is_lost_and_the_ticket_stays_parked(self):
        res, labels, calls = self.run_wf({"start": [PARKED], "record text": [rec()], "librarian": [None],
                                          "librarian (retry)": [None], "lost note": [NOTE]},
                                         ticket="T-0904", from_human={"text": HUMAN_TEXT})
        self.assertEqual(res["outcome"], "lost")
        self.assertNotIn("unpark and deliver", labels)

    def test_bad_arguments_throw(self):
        for args in ({"from_human": {"text": "x"}, "ref": "HU95"}, {"ticket": "T-0904", "from_human": {}},
                     {"ticket": "T-0904", "from_human": "a text"}):
            d = tempfile.mkdtemp(prefix="acad-ct-")
            self.addCleanup(shutil.rmtree, d, True)
            h = os.path.join(d, "h.js")
            with open(h, "w", encoding="utf-8") as fh:
                fh.write(HARNESS)
            p = subprocess.run([NODE, h, SCRIPT, json.dumps({"__args": args})], capture_output=True, text=True, timeout=60)
            out = json.loads(p.stdout.strip().splitlines()[-1])
            self.assertIn("from_human", out.get("error", ""), args)

    def test_standalone_the_delivered_ticket_ships_and_a_parked_one_does_not(self):
        res, labels, _ = self.run_wf(self.plan(ship=[shipped("T-0904")]), ticket="T-0904",
                                     from_human={"text": HUMAN_TEXT}, nested=False)
        self.assertEqual(labels[-1], "ship")
        self.assertEqual(res["ship"]["status"], "pushed")
        res, labels, _ = self.run_wf({"start": [PARKED], "record text": [rec()],
                                      "librarian": [hcard(False, "n/a", "p. 807")], "still parked": [NOTE]},
                                     ticket="T-0904", from_human={"text": HUMAN_TEXT}, nested=False)
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["status"], "not-run")


def shipped(t, line="library 2026-11-13/t-0904/expert @ abc1234 (2 files) pushed"):
    return {"status": "pushed", "detail": "", "branches": [], "output": "%s: delivered (delivered)\n%s\n" % (t, line)}


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": a standalone run ships once; a nested one never."""
    run_wf = CiteTests.run_wf
    PLAN = {"start": [ASK], "librarian": [card()], "validate": [OK], "packet": [{"packet": "P-0300", "error": ""}], "deliver": [MOVE]}

    def test_standalone_with_a_ticket_ships_once_by_the_inbox_check(self):
        res, labels, calls = self.run_wf(dict(self.PLAN, ship=[shipped("T-0904")]), ticket="T-0904", nested=False, root="/acad")
        self.assertEqual(labels, ["start", "librarian", "validate", "packet", "deliver", "ship"])
        self.assertIn("py /acad/expert/scripts/inbox.py --instance expert@t --check T-0904", calls[-1]["prompt"])
        self.assertEqual(calls[-1]["agentType"], "academy:inbox-clerk")
        self.assertEqual(res["ship"]["status"], "pushed")
        self.assertEqual(res["ship"]["branches"], ["library 2026-11-13/t-0904/expert"])

    def test_the_bib_in_the_author_home_ships_with_the_ticket(self):
        # the ticket's --check ships the bib too (the touch ledger, --touched): its line is a
        # branch like any other, and no note sends the human to ship it by hand
        out = shipped("T-0904")
        out["output"] = shipped("T-0904")["output"] + "paper 2026-11-13/t-0904/expert @ def5678 (1 files) pushed\n"
        res, labels, _ = self.run_wf(dict(self.PLAN, ship=[out]), ticket="T-0904", nested=False)
        self.assertEqual(res["ship"]["status"], "pushed")
        self.assertEqual(res["ship"]["branches"], ["library 2026-11-13/t-0904/expert",
                                                   "paper 2026-11-13/t-0904/expert"])
        self.assertNotIn("references.bib", " ".join(res["notes"]))

    def test_nested_never_ships(self):
        res, labels, _ = self.run_wf(dict(self.PLAN), ticket="T-0904", nested=True)
        self.assertNotIn("ship", labels)
        self.assertNotIn("ship", res)

    def test_a_refused_ship_is_returned_once_and_noted(self):
        bad = shipped("T-0904", "library main @ abc (0 files) REFUSED: dirty on main")
        res, labels, _ = self.run_wf(dict(self.PLAN, ship=[bad, bad]), ticket="T-0904", nested=False)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "refused")
        self.assertIn("ship stage was refused", " ".join(res["notes"]))

    def test_no_ticket_is_not_run_with_the_command(self):
        res, labels, _ = self.run_wf({"librarian": [card()], "validate": [OK], "packet": [{"packet": "P-0302", "error": ""}]},
                                     ref="SW10", nested=False)
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["status"], "not-run")
        self.assertEqual(res["ship"]["command"], "py scripts/ship.py checkpoint --ticket cite-sw10 --role expert --only library board")
        self.assertIn("--touched <that home's submodule>:references.bib", " ".join(res["notes"]))   # no ticket claims it

    def test_a_ticket_parked_on_the_human_does_not_ship(self):
        c = dict(card("unreachable", False), card="none written")
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [c], "packet": [{"packet": "P-0303", "error": ""}],
                                      "park on human": [MOVE]}, ticket="T-0904", nested=False)
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["status"], "not-run")


if __name__ == "__main__":
    unittest.main()
