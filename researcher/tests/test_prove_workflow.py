"""The prove workflow (workflows/prove.js), 2026-10-31: an attack-only run first when none
exists, the outcome read from the attempt file, a verify ticket only for a complete attempt
(filed by the prover, checked), nothing above sketch. Since 2026-11-20 (the human's design):
the attempt goes ahead with no falsifier on record (a failed or incomplete attempt files one
through lead-researcher; the result and the verify ask say whether one is on record), a clerk stage lists the
related registry statements for the prover's brief (cite, never reprove), and the attempt
declares its dependencies in its frontmatter: a complete attempt without them is not filed.
Under node with a fake agent(); skipped without node."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "prove.js")
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, model: opts.model, prompt })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  return q.shift()
}
const body = new Function('args', 'agent', 'phase', 'log', 'return (async () => {' + src + '})()')
// the stage-order tests run nested, as from the inbox (no ship stage); the ship tests pass nested: false
// the max-tier launch models as the inbox passes them (T-1682); a test passes models: null to resolve them
body(Object.assign({ nested: true, models: { 'expert:rigor-reviewer': 'fable', 'expert:referee': 'fable', 'researcher:experiment-reviewer': 'fable', 'researcher:prover': 'fable' } }, plan.__args), agent, () => {}, () => {}).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""


def state(**kw):
    s = {"ok": True, "stop_reason": "", "status": "open", "unsettled_inputs": [], "attempts": [],
         "falsified": True, "falsifier_evidence": "explore D-1", "attack_exists": True}
    s.update(kw)
    return s


MOVE = {"ok": True, "detail": ""}
RELATED_NONE = {"related": [], "queries": ["registry.py find GEO"]}


def done(**kw):
    """The outcome stage's answer for a complete attempt that declares its dependencies."""
    o = {"exists": True, "outcome": "complete", "gaps": [], "objects": [],
         "dependencies_declared": True, "dependencies": [], "inputs_listed": [], "inputs_not_used": []}
    o.update(kw)
    return o


@unittest.skipUnless(NODE, "node is not installed")
class ProveTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        a = {"claim": "flat:GEO-3", "home": "/h/nb", "ticket": "T-0010"}
        a.update(args)
        plan = dict(plan, __args=a)
        # 2026-11-20: every run past the state stage has the related-statements clerk stage;
        # a plan that does not care gets an empty answer
        plan.setdefault("related", [RELATED_NONE])
        d = tempfile.mkdtemp(prefix="acad-pv-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], [c["label"] for c in out["calls"]], out["calls"]

    # ---- 2026-11-20: attempt first, related statements, declared dependencies ----------------

    def test_no_falsifier_on_record_still_gets_an_attempt(self):
        """Was test_no_falsifier_means_explore_first (needs-explore, nothing attempted): the
        attempt goes ahead (a falsifier is triggered by a failed attempt or a GAP verdict) and the
        result and the verify ask say that none is on record."""
        res, labels, calls = self.run_wf(dict(self.COMPLETE, state=[state(falsified=False, falsifier_source="none")]))
        self.assertNotIn("needs_explore", res)
        self.assertIn("attempt", labels)
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertFalse(res["falsifier_on_record"])
        self.assertEqual(res["falsifier_source"], "none")
        filed = next(c for c in calls if c["label"] == "file verify")["prompt"]
        self.assertIn("no falsifier on record", filed)
        self.assertIn("no falsifier on record", calls[-1]["prompt"])          # the delivered result line

    def test_a_falsifier_on_record_is_named_in_the_verify_ask(self):
        res, labels, calls = self.run_wf(dict(self.COMPLETE, state=[state(falsifier_source="claim", falsifier_evidence="T-0099 delivered: none up to 12")]))
        self.assertTrue(res["falsifier_on_record"])
        filed = next(c for c in calls if c["label"] == "file verify")["prompt"]
        self.assertIn("falsifier on record: claim", filed)
        self.assertIn("T-0099 delivered", filed)

    RELATED = {"related": [
        {"id": "flat:GEO-7", "status": "open", "statement": "an open neighbour"},
        {"id": "paper:lem:unfold", "status": "proved", "statement": "the unfolding is a translation surface"},
        {"id": "flat:GEO-3", "status": "open", "statement": "the claim itself"},
        {"id": "flat:GEO-5", "status": "proved-modulo", "statement": "a modulo result"},
        {"id": "paper:lem:unfold", "status": "proved", "statement": "a duplicate row"}],
        "queries": ["registry.py find unfolding", "registry.py --repo paper grep unfolding"]}

    @staticmethod
    def confirm(rel, missing=(), status=None, claim="flat:GEO-3"):
        """The confirm stage's answer: every listed id found (claims_show), but those in missing."""
        status = status or {}
        return {"claim_id": claim, "rows": [
            {"id": r["id"], "qualified": r["id"], "found": r["id"] not in missing,
             "status": status.get(r["id"], r["status"]) if r["id"] not in missing else ""}
            for r in rel["related"]]}

    def test_the_prover_brief_carries_the_related_statements(self):
        res, labels, calls = self.run_wf(dict(self.COMPLETE, related=[self.RELATED], **{"confirm related": [self.confirm(self.RELATED)]}))
        self.assertLess(labels.index("related"), labels.index("confirm related"))
        self.assertLess(labels.index("confirm related"), labels.index("attempt"))
        rel = calls[labels.index("related")]
        self.assertEqual(rel["agentType"], "researcher:review-clerk")
        self.assertIn("paper:", rel["prompt"])
        prompt = next(c for c in calls if c["label"] == "attempt")["prompt"]
        self.assertIn("paper:lem:unfold (proved): the unfolding is a translation surface", prompt)
        self.assertIn("flat:GEO-5 (proved-modulo)", prompt)
        self.assertNotIn("the claim itself", prompt)                     # the claim is not its own input
        self.assertEqual(prompt.count("paper:lem:unfold (proved)"), 1)    # deduplicated
        # proved and proved-modulo first
        self.assertLess(prompt.index("paper:lem:unfold"), prompt.index("flat:GEO-7"))
        self.assertLess(prompt.index("flat:GEO-5"), prompt.index("flat:GEO-7"))
        for duty in ("never reprove", "used as input", "or why not"):
            self.assertIn(duty, prompt)
        self.assertEqual([r["id"] for r in res["related"]], ["paper:lem:unfold", "flat:GEO-5", "flat:GEO-7"])

    def test_related_ids_are_confirmed_and_an_unconfirmed_one_is_dropped(self):
        """Review of fd04646, finding 4: each listed id is checked with claims_show by one clerk
        stage; one it could not confirm is dropped (noted), and the confirmed status stands."""
        conf = self.confirm(self.RELATED, missing=("flat:GEO-5",), status={"flat:GEO-7": "proved"})
        res, labels, calls = self.run_wf(dict(self.COMPLETE, related=[self.RELATED], **{"confirm related": [conf]}))
        c = calls[labels.index("confirm related")]
        self.assertEqual(c["agentType"], "researcher:review-clerk")
        self.assertIn("claims_show", c["prompt"])
        for i in ("flat:GEO-7", "paper:lem:unfold", "flat:GEO-5"):
            self.assertIn(i, c["prompt"])
        self.assertEqual(c["prompt"].count("paper:lem:unfold"), 1)          # asked once
        self.assertEqual([(r["id"], r["status"]) for r in res["related"]], [("flat:GEO-7", "proved"), ("paper:lem:unfold", "proved")])   # both proved: the clerk's order
        prompt = next(x for x in calls if x["label"] == "attempt")["prompt"]
        self.assertNotIn("flat:GEO-5", prompt)
        self.assertIn("flat:GEO-5", " ".join(res["notes"]))
        self.assertIn("not confirmed", " ".join(res["notes"]))
        # a confirm stage that returns nothing confirms none: the prover searches itself
        res, labels, calls = self.run_wf(dict(self.COMPLETE, related=[self.RELATED], **{"confirm related": [None]}))
        self.assertEqual(res["related"], [])
        self.assertIn("search it yourself", next(x for x in calls if x["label"] == "attempt")["prompt"])
        self.assertEqual(res["outcome"], "verify-filed")

    def test_related_dedupe_compares_qualified_ids(self):
        """Review of fd04646, finding 4: s1:GEO-3 is not the claim flat:GEO-3, and flat:GEO-7
        and s1:GEO-7 are two statements; a bare listed id is resolved by the confirm stage."""
        rel = {"related": [{"id": "s1:GEO-3", "status": "proved", "statement": "another notebook's GEO-3"},
                           {"id": "s1:GEO-7", "status": "proved", "statement": "s1 seven"},
                           {"id": "flat:GEO-7", "status": "open", "statement": "flat seven"},
                           {"id": "GEO-3", "status": "open", "statement": "the claim, written bare"},
                           {"id": "lem:unfold", "status": "proved", "statement": "bare paper lemma"},
                           {"id": "paper:lem:unfold", "status": "proved", "statement": "the same lemma"}], "queries": []}
        conf = self.confirm(rel)
        for row in conf["rows"]:
            if row["id"] == "GEO-3":
                row["qualified"] = "flat:GEO-3"
            if row["id"] == "lem:unfold":
                row["qualified"] = "paper:lem:unfold"
        res, labels, calls = self.run_wf(dict(self.COMPLETE, related=[rel], **{"confirm related": [conf]}))
        self.assertEqual([r["id"] for r in res["related"]], ["s1:GEO-3", "s1:GEO-7", "paper:lem:unfold", "flat:GEO-7"])
        # a confirmed id that is not the listed one is dropped (second look at 864cc32)
        rel2 = {"related": [{"id": "s1:GEO-9", "status": "proved", "statement": "nine"}], "queries": []}
        conf2 = self.confirm(rel2)
        conf2["rows"][0]["qualified"] = "s1:GEO-90"
        res, labels, calls = self.run_wf(dict(self.COMPLETE, related=[rel2], **{"confirm related": [conf2]}))
        self.assertEqual(res["related"], [])
        self.assertIn("confirmed as s1:GEO-90", " ".join(res["notes"]))

    def test_the_related_list_is_capped_and_a_lost_stage_is_noted(self):
        many = {"related": [{"id": "flat:X-%d" % i, "status": "proved", "statement": "s%d" % i} for i in range(20)], "queries": []}
        res, labels, calls = self.run_wf(dict(self.COMPLETE, related=[many], **{"confirm related": [self.confirm(many)]}))
        self.assertEqual(len(res["related"]), 12)
        res, labels, calls = self.run_wf(dict(self.COMPLETE, related=[None]))
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertIn("related-statements stage returned nothing", " ".join(res["notes"]))
        self.assertNotIn("confirm related", labels)                             # nothing to confirm

    def test_the_declared_dependencies_go_to_the_result_and_the_verify_ticket(self):
        deps = ["paper:lem:unfold", "bib:LMW16#Theorem 11"]
        plan = dict(self.COMPLETE, outcome=[done(dependencies=deps, inputs_listed=["lem:unfold", "bib:LMW16#Theorem 11"])],
                    **{"check verify": [{"found": True, "to": "expert@t", "kind": "verify",
                                         "refs": ["flat:GEO-3", "file:x", "paper:lem:unfold", "bib:LMW16#Theorem 11"]}]})
        res, labels, calls = self.run_wf(plan)
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertEqual(res["dependencies"], deps)
        o = next(c for c in calls if c["label"] == "outcome")["prompt"]
        self.assertIn("dependencies:", o)
        filed = next(c for c in calls if c["label"] == "file verify")["prompt"]
        self.assertIn("paper:lem:unfold, bib:LMW16#Theorem 11]", filed)     # in refs
        self.assertIn("dependencies: paper:lem:unfold; bib:LMW16#Theorem 11", filed)   # in the ask
        self.assertNotIn("ANOMALY", " ".join(res["notes"]))
        # a filed ticket that drops a dependency from its refs is an anomaly
        plan["check verify"] = [{"found": True, "to": "expert@t", "kind": "verify", "refs": ["flat:GEO-3", "file:x"]}]
        res, labels, calls = self.run_wf(plan)
        self.assertIn("ANOMALY", " ".join(res["notes"]))
        self.assertIn("bib:LMW16#Theorem 11", " ".join(res["notes"]))

    def test_an_attempt_without_declared_dependencies_is_not_complete(self):
        """After one fix round that leaves them undeclared (review of fd04646, finding 3)."""
        for o in (done(dependencies_declared=False),                                   # no dependencies: in the frontmatter
                  done(dependencies=["flat:GEO-2"], inputs_listed=["flat:GEO-2", "bib:K#1"]),    # an input left out of it
                  done(dependencies=[], inputs_listed=["flat:GEO-2"])):                # an empty list, an input used
            plan = dict(self.COMPLETE, outcome=[o], **{"fix dependencies": ["fixed"], "outcome (after fix)": [o]})
            res, labels, calls = self.run_wf(plan)
            self.assertEqual(res["outcome"], "attempt-incomplete", o)
            self.assertEqual(labels.count("fix dependencies"), 1, o)                  # one fix round, no more
            self.assertNotIn("file verify", labels)
            self.assertIn("dependencies", calls[-1]["prompt"])                         # the delivered result says why
            self.assertIn("after one fix round", calls[-1]["prompt"])
        self.assertIn("flat:GEO-2", " ".join(res["dependency_gaps"]))                 # the empty list names what it uses
        # the attempt prompt asks for the list
        prompt = next(c for c in calls if c["label"] == "attempt")["prompt"]
        self.assertIn("dependencies:", prompt)

    def test_undeclared_dependencies_get_one_fix_round_of_the_same_file(self):
        """Review of fd04646, finding 3: the prover is asked once to fix the frontmatter of
        the same attempt file, the outcome is read again, and a fixed list is filed."""
        bad = done(dependencies=[], inputs_listed=["paper:lem:unfold"])
        good = done(dependencies=["paper:lem:unfold"], inputs_listed=["paper:lem:unfold"])
        plan = dict(self.COMPLETE, outcome=[bad], **{"fix dependencies": ["fixed"], "outcome (after fix)": [good],
                    "check verify": [{"found": True, "to": "expert@t", "kind": "verify", "refs": ["flat:GEO-3", "paper:lem:unfold"]}]})
        res, labels, calls = self.run_wf(plan)
        self.assertEqual(labels[labels.index("outcome"):labels.index("file verify")], ["outcome", "fix dependencies", "outcome (after fix)"])
        fix = calls[labels.index("fix dependencies")]
        self.assertEqual(fix["agentType"], "researcher:prover")
        self.assertEqual(fix["model"], "fable")                                        # the prover's max-tier model
        for s in ("proofs/GEO-3/attempt-2.md", "dependencies:", "same attempt file", "paper:lem:unfold"):
            self.assertIn(s, fix["prompt"])
        self.assertIn("proofs/GEO-3/attempt-2.md", calls[labels.index("outcome (after fix)")]["prompt"])
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertEqual(res["dependencies"], ["paper:lem:unfold"])
        self.assertIn("fix round", " ".join(res["notes"]))
        # an incomplete attempt (gaps, or not complete) gets no fix round: nothing would be filed anyway
        res, labels, calls = self.run_wf(dict(self.COMPLETE, outcome=[done(outcome="partial", gaps=["step 2"], dependencies_declared=False)]))
        self.assertEqual(res["outcome"], "attempt-incomplete")
        self.assertNotIn("fix dependencies", labels)

    def test_an_input_marked_not_used_need_not_be_declared(self):
        o = done(dependencies=["flat:GEO-2"], inputs_listed=["flat:GEO-2", "flat:GEO-9"], inputs_not_used=["flat:GEO-9"])
        res, labels, calls = self.run_wf(dict(self.COMPLETE, outcome=[o]))
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertNotIn("fix dependencies", labels)
        self.assertIn("not used", calls[labels.index("outcome")]["prompt"])           # the clerk is asked for them
        # an empty list is declared only when the Inputs section names no input it uses
        o = done(dependencies=[], inputs_listed=["flat:GEO-9"], inputs_not_used=["flat:GEO-9"])
        res, labels, calls = self.run_wf(dict(self.COMPLETE, outcome=[o]))
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertIn("dependencies: none declared", calls[labels.index("file verify")]["prompt"])

    def test_the_attempt_template_declares_no_dependencies_by_default(self):
        """An untouched template must not read as declared (review of fd04646, finding 3):
        its frontmatter carries no dependencies: key; the comment says how to add it."""
        tpl = os.path.join(os.path.dirname(HERE), "templates", "notebook", "_templates", "attempt.md")
        with open(tpl, encoding="utf-8") as fh:
            text = fh.read()
        front = text.split("---")[1]
        self.assertNotRegex(front, r"(?m)^dependencies:")
        body = text.split("---", 2)[2]
        self.assertIn("frontmatter key `dependencies`", body)                       # how to add it
        self.assertIn("an empty list only for a", body)
        # no body line starts like the key, which a reader could take for a declaration
        self.assertNotRegex(body, r"(?m)^dependencies:")

    def test_a_complete_attempt_files_a_checked_verify_ticket(self):
        res, labels, calls = self.run_wf({
            "state": [state(attack_exists=False)], "attack": ["no counterexample"],
            "attempt path": [{"path": "proofs/GEO-3/attempt-2.md"}], "attempt": ["done, complete"],
            "outcome": [done()],
            "file verify": [{"ticket": "T-0020", "proposal": "T-0021", "refusal": ""}],
            "check verify": [{"found": True, "to": "expert@t", "kind": "verify", "refs": ["flat:GEO-3", "file:x"]}],
            "close": [MOVE]})
        # 2026-11-20: the related-statements clerk stage runs after the state stage
        self.assertEqual(labels, ["state", "related", "attack", "attempt path", "attempt", "outcome", "file verify",
                                  "check verify", "close"])
        self.assertEqual(res["outcome"], "verify-filed")
        f = next(c for c in calls if c["label"] == "file verify")
        self.assertEqual(f["agentType"], "researcher:prover")
        self.assertIn("propose sketch", f["prompt"])          # the claim was open
        self.assertIn("T-0020", next(c for c in calls if c["label"] == "close")["prompt"])

    COMPLETE = {"state": [state(attack_exists=False)], "attack": ["none"],
                "attempt path": [{"path": "proofs/GEO-3/attempt-2.md"}], "attempt": ["done"],
                "outcome": [done()],
                "file verify": [{"ticket": "T-0020", "proposal": "", "refusal": ""}],
                "check verify": [{"found": True, "to": "expert@t", "kind": "verify", "refs": ["flat:GEO-3"]}],
                "close": [MOVE]}

    def test_every_prover_launch_is_on_the_max_model(self):
        """T-1682: attack, attempt and filing launch on the args' model, or one clerk stage resolves it."""
        res, labels, calls = self.run_wf(dict(self.COMPLETE))
        self.assertEqual([(c["label"], c.get("model")) for c in calls if c["agentType"] == "researcher:prover"],
                         [("attack", "fable"), ("attempt", "fable"), ("file verify", "fable")])
        res, labels, calls = self.run_wf(dict(self.COMPLETE, **{"model researcher:prover": [{"output": "fable"}]}), models=None)
        self.assertEqual(labels.count("model researcher:prover"), 1)          # resolved once per run
        self.assertEqual(calls[labels.index("model researcher:prover")]["agentType"], "researcher:review-clerk")
        self.assertEqual({c.get("model") for c in calls if c["agentType"] == "researcher:prover"}, {"fable"})

    def test_the_attack_line_follows_the_attack_run_not_the_notes(self):
        """The attempt is told to read attack.md only when this run made it, whatever notes the
        model block added (an unresolved model adds one)."""
        bad = {"model researcher:prover": [{"output": "models: workspace.json not found"}]}
        res, labels, calls = self.run_wf(dict(self.COMPLETE, state=[state(attack_exists=True)], **bad), models=None)
        self.assertIn("was not resolved", " ".join(res["notes"]))
        self.assertNotIn("attack.md first", next(c for c in calls if c["label"] == "attempt")["prompt"])
        res, labels, calls = self.run_wf(dict(self.COMPLETE, **bad), models=None)
        self.assertIn("Read proofs/<id>/attack.md first.", next(c for c in calls if c["label"] == "attempt")["prompt"])

    def test_a_lost_attempt_falls_back_to_opus_and_the_ticket_says_so(self):
        res, labels, calls = self.run_wf(dict(self.COMPLETE, attempt=[None], **{"attempt (opus fallback)": ["done"]}))
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertEqual(res["model_fallbacks"], ["attempt: fable -> opus"])
        self.assertIn("model fallback: attempt: fable -> opus", calls[-1]["prompt"])

    def test_the_outcome_comes_from_the_file_not_the_summary(self):
        res, labels, _ = self.run_wf({
            "state": [state()], "attempt path": [{"path": "p.md"}],
            "attempt": ["COMPLETE! the proof is done"],                      # the summary claims success
            "outcome": [{"exists": True, "outcome": "failed", "gaps": ["step 3"], "objects": []}],
            "close": [MOVE]})
        self.assertEqual(res["outcome"], "attempt-incomplete")
        self.assertNotIn("file verify", labels)

    def test_already_proved_and_a_bad_verify_ticket(self):
        res, labels, _ = self.run_wf({"state": [state(status="proved", repair=False)]})
        self.assertEqual(res["outcome"], "already-proved")
        self.assertTrue(res["already_proved"])
        self.assertNotIn("attempt", labels)
        self.assertNotIn("close", labels)                 # #85: never delivered with nothing done
        self.assertFalse(res.get("ticket_delivered"))
        res, labels, _ = self.run_wf({
            "state": [state(status="sketch")], "attempt path": [{"path": "p.md"}], "attempt": ["x"],
            "outcome": [done()],
            "file verify": [{"ticket": "T-0020", "proposal": "", "refusal": ""}],
            "check verify": [{"found": True, "to": "author@t", "kind": "write", "refs": []}],
            "close": [MOVE]})
        self.assertIn("ANOMALY", " ".join(res["notes"]))


    def test_a_repair_of_a_proved_claim_is_attempted(self):
        """#85: a repair ticket on a proved claim (here proved on the human's word, with an
        open GAP and no falsifier on record) gets a new attempt and a verify ticket."""
        plan = dict(self.COMPLETE, state=[state(status="proved", falsified=False, repair=True,
                                                repair_ask="close the GAP in step 3 (T-1243)")])
        res, labels, calls = self.run_wf(plan)
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertTrue(res["repair"])
        prompt = next(c for c in calls if c["label"] == "attempt")["prompt"]
        self.assertIn("This is a repair of a proved claim", prompt)
        self.assertIn("close the GAP in step 3", prompt)
        filed = next(c for c in calls if c["label"] == "file verify")["prompt"]
        self.assertIn("(a repair of the proved claim)", filed)
        self.assertNotIn("propose sketch", filed)

    def test_a_falsifier_on_a_declared_input_or_the_parent_counts(self):
        """#117: T-0825 and the parked T-1425, 1384, 1231, 1523, 1651."""
        for kw in ({"falsifier_source": "input", "falsifier_on": "flat:GEO-2", "inputs": ["flat:GEO-2"]},
                   {"falsifier_source": "parent", "falsifier_on": "flat:DIR-3", "inputs": []},
                   {"falsifier_source": "waived", "falsifier_evidence": "- 2026-11-18 human: waive the experiment", "inputs": []},
                   {"falsifier_source": "input", "falsifier_on": "s1:GEO-2", "inputs": ["GEO-2"]}):
            plan = dict(self.COMPLETE, state=[state(attack_exists=False, falsified=True, **kw)])
            res, labels, calls = self.run_wf(plan)
            self.assertEqual(res["outcome"], "verify-filed", kw)
            self.assertEqual(res["falsifier"]["source"], kw["falsifier_source"])
            self.assertIn("falsifier accepted: " + kw["falsifier_source"], calls[-1]["prompt"])

    def test_a_falsifier_that_does_not_count_is_not_on_record(self):
        """Was ..._is_refused_with_what_would (needs-explore): a source that does not count is
        still checked as before (#117), but now the attempt goes ahead with none on record."""
        for kw in ({"falsifier_source": "input", "falsifier_on": "flat:GEO-9", "inputs": ["flat:GEO-2"]},
                   {"falsifier_source": "waived", "falsifier_evidence": "the lead thinks it is fine", "inputs": []},
                   {"falsifier_source": "none", "falsified": False, "inputs": []},
                   {"falsifier_source": "waived", "falsifier_evidence": "the lead says no human has waived this", "inputs": []},
                   {"falsifier_source": "ticket", "falsifier_evidence": "", "inputs": []},
                   {"falsifier_source": "whatever", "inputs": []},
                   {"falsifier_source": "parent", "falsifier_on": "", "inputs": []}):
            res, labels, calls = self.run_wf(dict(self.COMPLETE, state=[state(**dict({"falsified": True}, **kw))]))
            self.assertEqual(res["outcome"], "verify-filed", kw)
            self.assertFalse(res["falsifier_on_record"], kw)
            self.assertNotIn("falsifier", res)
            self.assertIn("What counts", " ".join(res["notes"]))
            self.assertIn("no falsifier on record", next(c for c in calls if c["label"] == "file verify")["prompt"])

    def test_mode_repair_forces_a_repair(self):
        res, labels, _ = self.run_wf(dict(self.COMPLETE, state=[state(status="proved", repair=False)]), mode="repair")
        self.assertEqual(res["outcome"], "verify-filed")

    def test_a_repair_of_an_unreviewed_claim_needs_no_falsifier_first(self):
        """Was ..._still_needs_a_falsifier: no attempt waits for a falsifier any more (2026-11-20)."""
        res, labels, _ = self.run_wf(dict(self.COMPLETE, state=[state(status="sketch", falsified=False, repair=True)]))
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertFalse(res["falsifier_on_record"])


    # ---- a repair a verify pass asked for (the dependency amendment, review fix 1) ----
    AMEND = {"state": [state(status="sketch", falsified=False, falsifier_evidence="", repair=True,
                             for_verify="T-0007", for_verify_pass="2026-11-20-T-0007",
                             repair_ask="add bib:LMW16#Thm11 to the proof")],
             "attempt path": [{"path": "proofs/GEO-3/attempt-3.md"}], "attempt": ["done"],
             "outcome": [done(dependencies=["bib:LMW16#Thm11"], inputs_listed=["bib:LMW16#Thm11"])],
             "check for-verify": [{"found": True, "kind": "verify", "refs": ["flat:GEO-3", "T-0001"],
                                   "status": "blocked", "waiting_on": ["T-0010"], "this_parent": "T-0007"}],
             "close": [MOVE]}

    def test_a_repair_for_a_verify_pass_files_no_verify_ticket(self):
        res, labels, calls = self.run_wf(self.AMEND)
        self.assertEqual(labels, ["state", "check for-verify", "related", "attempt path", "attempt", "outcome", "close"])
        self.assertEqual(res["outcome"], "amendment-delivered")
        self.assertEqual(res["for_verify"], "T-0007")
        self.assertNotIn("verify_ticket", res)
        close = calls[-1]["prompt"]
        self.assertIn("proofs/GEO-3/attempt-3.md", close)
        self.assertIn("no verify ticket", close)
        self.assertIn("T-0007", close)
        self.assertTrue(any("no verify ticket" in n for n in res["notes"]), res["notes"])

    def test_a_repair_for_a_verify_pass_with_no_falsifier_gets_its_attempt(self):
        # the falsifier gate is gone on main (attempt first): no needs-explore for any attempt
        res, labels, _ = self.run_wf(self.AMEND)
        self.assertEqual(res["outcome"], "amendment-delivered")
        self.assertIn("attempt", labels)

    def test_the_marker_can_come_as_an_argument(self):
        plan = dict(self.AMEND, state=[state(status="sketch", falsified=False, falsifier_evidence="", repair=True)])
        res, labels, _ = self.run_wf(plan, for_verify="T-0007")
        self.assertEqual(res["outcome"], "amendment-delivered")
        self.assertNotIn("file verify", labels)

    def test_a_marker_the_named_verify_ticket_does_not_back_is_ignored(self):
        """Second look at 7044d82: on its shape alone, any prove ticket quoting the marker
        would skip its own verify ticket. Not waiting on this ticket, another claim, not a
        verify ticket, not found: the marker is ignored and the verify ticket is filed."""
        good = self.AMEND["check for-verify"][0]
        for bad in (dict(good, waiting_on=["T-0999"], this_parent=""),
                    dict(good, waiting_on=["human"], this_parent="T-0007"),      # a child, not its repair
                    dict(good, status="in-progress"),
                    dict(good, refs=["flat:GEO-4"]), dict(good, kind="prove"), dict(good, found=False)):
            plan = dict(self.AMEND, **{"check for-verify": [bad],
                                       "file verify": [{"ticket": "T-0020", "proposal": "", "refusal": ""}],
                                       "check verify": [{"found": True, "to": "expert@t", "kind": "verify",
                                                         "refs": ["flat:GEO-3", "bib:LMW16#Thm11"]}]})
            res, labels, _ = self.run_wf(plan)
            self.assertNotIn("for_verify", res, bad)
            self.assertIn("file verify", labels, bad)
            self.assertTrue(any("the marker names T-0007, but" in n for n in res["notes"]), res["notes"])

    def test_a_malformed_marker_is_ignored(self):
        plan = dict(self.AMEND, state=[state(status="sketch", falsified=False, falsifier_evidence="",
                                             repair=True, for_verify="see the ticket")])
        plan.update({"file verify": [{"ticket": "T-0020", "proposal": "", "refusal": ""}],
                     "check verify": [{"found": True, "to": "expert@t", "kind": "verify",
                                       "refs": ["flat:GEO-3", "bib:LMW16#Thm11"]}]})
        res, labels, _ = self.run_wf(plan)
        self.assertNotIn("for_verify", res)                   # an ordinary repair: it files its verify ticket
        self.assertIn("file verify", labels)

    def test_an_incomplete_amendment_is_not_delivered(self):
        plan = dict(self.AMEND, outcome=[done(outcome="partial", gaps=["step 2"])],
                    block=[MOVE], **{"file falsifier": [{"ticket": "T-0030", "proposal": "", "refusal": ""}],
                                     "check falsifier": [{"found": True, "to": "scientist@t", "kind": "test", "refs": ["flat:GEO-3"]}]})
        plan.pop("close")
        res, labels, calls = self.run_wf(plan)
        self.assertEqual(res["outcome"], "amendment-incomplete")
        self.assertEqual(labels[-1], "block")
        self.assertIn("blocked", calls[-1]["prompt"])
        self.assertIn("human", calls[-1]["prompt"])

    def test_the_state_stage_is_asked_for_the_marker(self):
        _r, _l, calls = self.run_wf(self.COMPLETE)
        self.assertIn("amendment for verify", calls[0]["prompt"])


def shipped(t, line):
    return {"status": "nothing", "detail": "", "branches": [], "output": "%s: delivered (delivered)\n%s\n" % (t, line)}


@unittest.skipUnless(NODE, "node is not installed")
class FalsifierOnFailureTests(unittest.TestCase):
    """The human's design (2026-11-20, revised the same day): a failed or incomplete attempt on a
    claim with no falsifier on record and none pending files one, through lead-researcher (a
    liaison toward the Scientist; the prover is none); the delivery is unchanged."""
    run_wf = ProveTests.run_wf
    NONE = dict(falsified=False, falsifier_source="none", falsifier_evidence="")
    FILED_F = {"ticket": "T-0030", "proposal": "", "refusal": ""}
    CHECK_F = {"found": True, "to": "scientist@t", "kind": "experiment", "refs": ["flat:GEO-3"]}

    def plan(self, outcome, st=None, **extra):
        p = {"state": [state(**(st if st is not None else self.NONE))],
             "attempt path": [{"path": "proofs/GEO-3/attempt-2.md"}], "attempt": ["done"],
             "outcome": [outcome], "close": [MOVE]}
        p.update(extra)
        return p

    def test_a_failed_attempt_files_a_falsifier_through_lead_researcher(self):
        for o in (done(outcome="failed", gaps=["step 4: the cylinder bound fails for slope 2"]),
                  done(outcome="complete", gaps=["step 4: the cylinder bound fails for slope 2"])):
            res, labels, calls = self.run_wf(self.plan(o, **{"file falsifier": [self.FILED_F], "check falsifier": [self.CHECK_F]}))
            self.assertEqual(res["outcome"], "attempt-incomplete", o)
            self.assertEqual(labels[-3:], ["file falsifier", "check falsifier", "close"], o)
            f = next(c for c in calls if c["label"] == "file falsifier")
            self.assertEqual(f["agentType"], "researcher:lead-researcher")    # a liaison, not the prover
            self.assertIn("step 4: the cylinder bound fails for slope 2", f["prompt"])   # targets the failed step
            self.assertIn("kind experiment", f["prompt"])
            self.assertIn("parent T-0010", f["prompt"])
            self.assertEqual(res["falsifier_ticket"], "T-0030")
            close = calls[-1]["prompt"]
            self.assertIn("nothing filed for review", close)                 # the delivery as before
            self.assertIn("falsifier filed: T-0030", close)
            self.assertNotIn("ANOMALY", " ".join(res["notes"]))

    def test_undeclared_dependencies_after_the_fix_round_file_one_too(self):
        o = done(dependencies_declared=False)
        res, labels, _c = self.run_wf(self.plan(o, **{"fix dependencies": ["fixed"], "outcome (after fix)": [o],
                                                     "file falsifier": [self.FILED_F], "check falsifier": [self.CHECK_F]}))
        self.assertEqual(res["outcome"], "attempt-incomplete")
        self.assertIn("file falsifier", labels)

    def test_a_bad_falsifier_ticket_is_an_anomaly_and_a_refusal_a_note(self):
        res, _l, _c = self.run_wf(self.plan(done(outcome="failed", gaps=["g"]), **{"file falsifier": [self.FILED_F],
                                  "check falsifier": [dict(self.CHECK_F, to="expert@t")]}))
        self.assertIn("ANOMALY", " ".join(res["notes"]))
        res, labels, calls = self.run_wf(self.plan(done(outcome="failed", gaps=["g"]),
                                         **{"file falsifier": [{"ticket": "", "proposal": "", "refusal": "chain: not a liaison"}]}))
        self.assertEqual(res["outcome"], "attempt-incomplete")
        self.assertIn("not a liaison", " ".join(res["notes"]))
        self.assertNotIn("check falsifier", labels)
        self.assertNotIn("falsifier filed", calls[-1]["prompt"])

    def test_a_complete_attempt_files_no_falsifier(self):
        plan = dict(ProveTests.COMPLETE, state=[state(attack_exists=False, **self.NONE)])
        res, labels, _c = self.run_wf(plan)
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertNotIn("file falsifier", labels)

    def test_on_record_or_pending_files_none(self):
        for st in (dict(falsified=True, falsifier_evidence="explore D-1"),
                   dict(self.NONE, falsifier_pending="T-0031", falsifier_pending_status="in-progress")):
            res, labels, _c = self.run_wf(self.plan(done(outcome="failed", gaps=["g"]), st=st))
            self.assertEqual(res["outcome"], "attempt-incomplete", st)
            self.assertNotIn("file falsifier", labels, st)
            self.assertIn("no falsifier filed", " ".join(res["notes"]), st)
        # a "pending" one that ended is not pending
        res, labels, _c = self.run_wf(self.plan(done(outcome="failed", gaps=["g"]),
                                      st=dict(self.NONE, falsifier_pending="T-0031", falsifier_pending_status="delivered"),
                                      **{"file falsifier": [self.FILED_F], "check falsifier": [self.CHECK_F]}))
        self.assertIn("file falsifier", labels)

    def test_a_lost_prover_run_files_nothing(self):
        res, labels, _c = self.run_wf({"state": [state(**self.NONE)], "attempt path": [{"path": "proofs/GEO-3/attempt-2.md"}],
                                       "attempt": [None], "attempt (opus fallback)": [None]})
        self.assertEqual(res["outcome"], "lost")
        self.assertNotIn("file falsifier", labels)

    def test_an_incomplete_amendment_files_one_and_stays_blocked(self):
        plan = dict(ProveTests.AMEND, outcome=[done(outcome="partial", gaps=["step 2"])], block=[MOVE],
                    **{"file falsifier": [self.FILED_F], "check falsifier": [self.CHECK_F]})
        plan.pop("close")
        res, labels, calls = self.run_wf(plan)
        self.assertEqual(res["outcome"], "amendment-incomplete")
        self.assertEqual(labels[-3:], ["file falsifier", "check falsifier", "block"])
        self.assertIn("waiting_on [human]", calls[-1]["prompt"])
        self.assertIn("falsifier filed: T-0030", calls[-1]["prompt"])

    def test_the_state_stage_is_asked_whether_one_is_pending(self):
        _r, _l, calls = self.run_wf(dict(ProveTests.COMPLETE))
        self.assertIn("falsifier_pending", calls[0]["prompt"])


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": standalone ships once; nested never."""
    run_wf = ProveTests.run_wf
    PLAN = {"state": [state()], "attempt path": [{"path": "proofs/GEO-3/attempt-2.md"}], "attempt": ["done"],
            "outcome": [{"exists": True, "outcome": "partial", "gaps": ["g"], "objects": []}], "close": [MOVE]}

    def test_standalone_ships_once_and_nested_never(self):
        line = "notebook 2026-11-13/t-0010/researcher @ a (2 files) pushed"
        res, labels, calls = self.run_wf(dict(self.PLAN, ship=[shipped("T-0010", line)]), nested=False, root="/acad", instance="researcher@u")
        self.assertEqual(labels[-2:], ["close", "ship"])
        self.assertEqual(calls[-1]["agentType"], "researcher:review-clerk")
        self.assertIn("py /acad/researcher/scripts/inbox.py --instance researcher@u --check T-0010", calls[-1]["prompt"])
        self.assertEqual(res["ship"]["status"], "pushed")
        res, labels, _ = self.run_wf(dict(self.PLAN))
        self.assertNotIn("ship", labels)
        self.assertNotIn("ship", res)

    def test_a_refusal_is_returned_once(self):
        bad = shipped("T-0010", "notebook main @ a (0 files) REFUSED: dirty on main")
        res, labels, _ = self.run_wf(dict(self.PLAN, ship=[bad, bad]), nested=False)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "refused")
        self.assertIn("ship stage was refused", " ".join(res["notes"]))

    def test_no_ticket_is_not_run_with_the_command(self):
        plan = dict(self.PLAN)
        del plan["close"]
        res, labels, _ = self.run_wf(plan, ticket=None, nested=False)
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["command"],
                         "py scripts/ship.py checkpoint --ticket prove-flat-geo-3 --role researcher --only <home submodule> board")


if __name__ == "__main__":
    unittest.main()
