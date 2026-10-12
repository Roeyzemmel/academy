"""T-0347, the reword pass, tested by test-engineer from the ticket's rule (not from the
code's output): one informed run R; R CONFIRMED (scope equivalent / weaker / covered) on
a base pass CONFIRMED x2 on ``base_hash`` => confirmed, propose proved, recolour; R GAP or
``exceeds`` => a full blind pass; anything else carries nothing. Hashes are computed here
independently (sha256 of the whitespace-collapsed text, first 16 hex digits, as the
registry's ``statement_hash_of`` docstring states)."""

import hashlib
import os
import re
import unittest

import fixtures
import _academy as ac
import decision_table as dt

SUBJ = "paper:lem:strip-bound"
PRIMARY = "claude-opus-5-5"
OLD = "Let $M$ be a compact translation surface. Then every point is illuminated."
NEW = "Let $M$ be a compact translation surface. Then every point of $M$ is illuminated."


def h16(text):
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()[:16]


H_OLD, H_NEW = h16(OLD), h16(NEW)


def blind(run, verdict="CONFIRMED", h=H_OLD, pass_="2026-09-28-T-0007", modulo="[]",
          extra=""):
    return ("---\nsubject: %s\npass: %s\nrun: %s\nrun_id: rv-%s\nverdict: %s\n"
            "modulo: %s\nmodel: %s\nstatement_hash: %s\n%s---\n\nreport %s\n"
            % (SUBJ, pass_, run, run, verdict, modulo, PRIMARY, h, extra, run))


def reword(verdict="CONFIRMED", scope="equivalent", base_pass="2026-09-28-T-0007",
           base_hash=H_OLD, h=H_NEW, run_id="rv-R"):
    return ("---\nsubject: %s\npass: 2026-10-12-T-0347-reword\nrun: R\nrun_id: %s\n"
            "verdict: %s\nmodulo: []\nmodel: %s\nstatement_hash: %s\nmode: reword\n"
            "base_pass: %s\nbase_hash: %s\nreword_scope: %s\n---\n\nreport R\n"
            % (SUBJ, run_id, verdict, PRIMARY, h, base_pass, base_hash, scope))


class Base(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.addCleanup(self.sb.close)
        old = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = self.sb.ws_path
        self.addCleanup(lambda: os.environ.__setitem__("ACADEMY_WORKSPACE", old)
                        if old is not None else os.environ.pop("ACADEMY_WORKSPACE", None))
        self.sdir = os.path.join(self.sb.lib, "reviews", "paper", "lem-strip-bound")

    def put(self, pass_, name, text):
        d = os.path.join(self.sdir, pass_)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return os.path.join(d, name)

    def base_pass(self, a=None, b=None, decided=True):
        self.put("2026-09-28-T-0007", "A.md", a or blind("A"))
        self.put("2026-09-28-T-0007", "B.md", b or blind("B"))
        if decided:
            self.put("2026-09-28-T-0007", "decision.md", "outcome: confirmed\n")

    def table(self, r_text, pass_="2026-10-12-T-0347-reword"):
        p = self.put(pass_, "R.md", r_text)
        r = dt.read_record(p)
        ba, bb, notes = dt.base_records(p, r.get("base_pass"))
        return dt.decide(r, None, primary=[PRIMARY], base=(ba, bb), base_notes=notes)


class RewordTable(Base):
    def test_the_rule_gives_proved_and_grounds_the_registry_accepts(self):
        self.base_pass()
        res = self.table(reword())
        self.assertEqual((res["outcome"], res["proposed_status"], res["recolour"]),
                         ("confirmed", "proved", True))
        claims = __import__("_expert").mcp_module("claims")
        self.assertTrue(claims.check_grounds("proved", res["grounds"], H_NEW)[0])
        self.assertFalse(claims.check_grounds("proved", res["grounds"], H_OLD)[0])

    def test_base_hash_mismatch_carries_nothing(self):
        self.base_pass()
        res = self.table(reword(base_hash="0" * 16))
        self.assertEqual((res["outcome"], res["proposed_status"], res["grounds"]),
                         ("invalid-base", None, None))
        # the base runs on another statement than the one R names
        self.base_pass(a=blind("A", h="0" * 16), b=blind("B", h="0" * 16))
        self.assertEqual(self.table(reword())["outcome"], "invalid-base")

    def test_reword_on_a_reword_pass_carries_nothing(self):
        self.base_pass()
        self.put("2026-10-12-T-0347-reword", "R.md", reword())
        self.put("2026-10-12-T-0347-reword", "decision.md", "outcome: confirmed\n")
        third = "Let $M$ be a compact translation surface; every point of $M$ is lit."
        res = self.table(reword(base_pass="2026-10-12-T-0347-reword", base_hash=H_NEW,
                                h=h16(third), run_id="rv-R2"),
                         pass_="2026-10-20-T-0400-reword")
        self.assertEqual((res["outcome"], res["proposed_status"]), ("invalid-base", None))

    def test_finding_a_reword_record_inside_the_base_pass_is_not_a_blind_run(self):
        """Finding: a base pass whose A.md is a reword record (mis-filed or hand-placed)
        is taken as CONFIRMED x2: _base_problems / _decide never check is_reword on the
        base records (a reword run is never one of a blind pair)."""
        self.base_pass(a=reword(h=H_OLD, base_hash="0" * 16, run_id="rv-A")
                       .replace("pass: 2026-10-12-T-0347-reword", "pass: 2026-09-28-T-0007"))
        self.assertEqual(self.table(reword())["outcome"], "invalid-base")

    def test_unchanged_statement_or_abandoned_base_carries_nothing(self):
        self.base_pass()
        self.assertEqual(self.table(reword(h=H_OLD))["outcome"], "invalid-base")
        self.put("2026-09-28-T-0007", "abandoned.md", "relaunched\n")
        self.assertEqual(self.table(reword())["outcome"], "invalid-base")

    def test_wording_beyond_the_proof_takes_a_full_blind_pass(self):
        self.base_pass()
        for v, s in (("GAP", "exceeds"), ("CONFIRMED", "exceeds"), ("GAP", "equivalent")):
            res = self.table(reword(verdict=v, scope=s))
            self.assertEqual((res["outcome"], res["proposed_status"], res["launch_b"],
                              res["launch_full_pass"]),
                             ("full-pass-needed", None, False, True), (v, s))

    def test_base_modulo_is_carried_over(self):
        self.base_pass(a=blind("A", modulo="[paper:lem:a]"), b=blind("B", modulo="[paper:lem:a]"))
        res = self.table(reword(scope="covered"))
        self.assertEqual((res["outcome"], res["proposed_status"], res["modulo"]),
                         ("confirmed-modulo", "proved-modulo", ["paper:lem:a"]))


class RewordPassCli(Base):
    def cli(self, *args):
        return fixtures.run_script("reviews.py", args=list(args) + ["--home", self.sb.lib],
                                   env={"ACADEMY_WORKSPACE": self.sb.ws_path})

    def test_new_pass_refuses_a_reword_pass_as_base(self):
        self.base_pass()
        self.put("2026-10-12-T-0347-reword", "R.md", reword())
        self.put("2026-10-12-T-0347-reword", "decision.md", "outcome: confirmed\n")
        code, out, err = self.cli("new-pass", SUBJ, "--ticket", "T-0400", "--reword-of",
                                  "2026-10-12-T-0347-reword")
        self.assertEqual(code, 1, out)

    def test_new_pass_refuses_a_base_split_over_two_statements(self):
        self.base_pass(b=blind("B", h="0" * 16))
        code, out, err = self.cli("new-pass", SUBJ, "--reword-of", "2026-09-28-T-0007")
        self.assertEqual(code, 1, out)

    def test_brief_hashes_and_whitespace_only_change(self):
        self.base_pass()
        code, name, err = self.cli("new-pass", SUBJ, "--ticket", "T-0347", "--reword-of",
                                   "2026-09-28-T-0007")
        self.assertEqual(code, 0, err)
        code, out, err = self.cli("reword-brief", SUBJ, name, "--old-text", OLD,
                                  "--new-text", NEW)
        self.assertEqual(code, 0, err)
        for line in ("run: R", "mode: reword", "base_pass: 2026-09-28-T-0007",
                     "base_hash: %s" % H_OLD, "statement_hash: %s" % H_NEW):
            self.assertIn(line, out)
        # a change in whitespace only is no rewording (the hash collapses whitespace)
        code, out, err = self.cli("reword-brief", SUBJ, name, "--old-text", OLD,
                                  "--new-text", OLD.replace(" ", "\n  "))
        self.assertEqual(code, 1, out)

    def test_brief_refuses_a_blind_pass(self):
        self.base_pass()
        code, out, err = self.cli("reword-brief", SUBJ, "2026-09-28-T-0007", "--old-text",
                                  OLD, "--new-text", NEW)
        self.assertEqual(code, 1, out)


REPORT = """Report.

VERDICT
subject: paper:lem:strip-bound
pass: 2026-09-28-T-0007
run: A
verdict: CONFIRMED
modulo: none
model: claude-opus-5-5
statement_hash: 0123456789abcdef
blocking: none
ticket: T-0007
"""


class LandVerdictKeys(Base):
    def land(self, text, agent_id="abc123def"):
        ev = {"hook_event_name": "SubagentStop", "agent_type": "expert:rigor-reviewer",
              "agent_id": agent_id, "last_assistant_message": text,
              "stop_hook_active": False}
        return fixtures.run_script("land_verdict.py", ev,
                                   env={"ACADEMY_WORKSPACE": self.sb.ws_path})

    def keys(self, pass_, name):
        with open(os.path.join(self.sdir, pass_, name), encoding="utf-8") as fh:
            text = fh.read()
        return [ln.split(":", 1)[0] for ln in text.split("---\n")[1].splitlines()]

    def test_a_blind_record_has_exactly_the_documented_keys(self):
        """land_verdict's documented record: the VERDICT fields plus run_id, agent,
        landed; nothing of the reword mode."""
        self.land(REPORT)
        self.assertEqual(self.keys("2026-09-28-T-0007", "A.md"),
                         ["subject", "pass", "run", "run_id", "verdict", "modulo", "model",
                          "statement_hash", "blocking", "gap_class", "ticket", "agent",
                          "landed"])

    def test_a_reword_block_without_a_base_pass_blocks(self):
        text = REPORT.replace("pass: 2026-09-28-T-0007", "pass: 2026-10-12-T-0347-reword") \
            .replace("run: A", "run: R\nmode: reword\nbase_hash: 0123456789abcdee\n"
                               "reword_scope: equivalent")
        code, out, err = self.land(text)
        self.assertEqual(out["decision"], "block", out)
        self.assertIn("base_pass", out["reason"])

    def test_finding_a_reword_block_does_not_land_in_a_blind_pass(self):
        """Finding: a reword block naming a blind pass lands R.md beside its A/B, where
        the notebook's blind path counts it as a run (registry test
        test_finding_a_reword_run_beside_one_blind_run_is_not_a_pair)."""
        self.land(REPORT)
        text = REPORT.replace("run: A", "run: R\nmode: reword\nbase_pass: "
                              "2026-09-01-T-0001\nbase_hash: 0123456789abcdee\n"
                              "reword_scope: equivalent")
        self.land(text, agent_id="zzz999")
        self.assertNotIn("R.md", os.listdir(os.path.join(self.sdir, "2026-09-28-T-0007")))


if __name__ == "__main__":
    unittest.main()
