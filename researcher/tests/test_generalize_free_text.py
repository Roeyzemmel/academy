"""#124 follow-up 2: generalize.js's clerk stages ask for their free text and never require it.

A clerk that left out SOURCE.refusal, CREATED.error, PACKET.error or MOVE.detail failed
StructuredOutput and lost its run. Under node with the fake agent() of
test_explore_generalize_workflow (kept in its own file: explore.js's tests change elsewhere),
recording the schema each stage is launched with."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from test_explore_generalize_workflow import H, HARNESS, NODE, SRC, WF

# the shared harness records each call's schema itself once the explore-order branch is in;
# until then it is added here (either way RECORDING records it)
RECORDING = HARNESS if "schema: opts.schema" in HARNESS else \
    HARNESS.replace("model: opts.model, prompt })", "model: opts.model, prompt, schema: opts.schema })", 1)


def run(plan, args):
    d = tempfile.mkdtemp(prefix="acad-gft-")
    try:
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(RECORDING)
        p = subprocess.run([NODE, h, os.path.join(WF, "generalize.js"), json.dumps(dict(plan, __args=args))],
                           capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(d, True)
    out = json.loads(p.stdout.strip().splitlines()[-1])
    return out.get("result"), out["calls"], out.get("error")


@unittest.skipUnless(NODE, "node is not installed")
class GeneralizeFreeText(unittest.TestCase):
    def test_the_recording_harness_records(self):
        self.assertIn("schema: opts.schema", RECORDING)

    def test_no_free_text_field_is_required_and_answers_without_them_lose_nothing(self):
        src = {k: v for k, v in SRC.items() if k != "refusal"}
        res, calls, err = run({
            "source": [src], "prover": ["wrote"],
            "validate": [{"ok": True, "problems": [], "failing": [], "proposals": 1}],
            "create": [{"conjectures": ["flat:CONJ-1"], "lemmas": []}],
            "packet": [{"packet": "P-0400"}],
            "test specs": [{"specs": []}], "file tests": [{"tickets": ["T-8"], "refusals": []}],
            "children": [{"tests": [{"id": "T-8", "refs": ["flat:CONJ-1"]}]}], "close": [{"ok": True}]},
            dict(H, ref="P-0009", ticket="T-7"))
        self.assertIsNone(err, err)
        for label, field in (("source", "refusal"), ("create", "error"), ("packet", "error"), ("close", "detail")):
            schema = next(c for c in calls if c["label"] == label)["schema"]
            self.assertIn(field, schema["properties"], label)
            self.assertNotIn(field, schema["required"], label)
        self.assertEqual(res["outcome"], "delivered")
        self.assertNotIn("undefined", json.dumps(res))

    def test_missing_reasons_read_no_reason_given(self):
        src = {k: v for k, v in SRC.items() if k != "refusal"}
        res, _calls, err = run({"source": [dict(src, ok=False)]}, dict(H, ref="P-0009", ticket="T-7"))
        self.assertIsNone(err, err)
        self.assertIn("refused: no reason given", res["reason"])
        res, _calls, err = run({
            "source": [SRC], "prover": ["wrote"],
            "validate": [{"ok": True, "problems": [], "failing": [], "proposals": 1}],
            "create": [{"conjectures": ["flat:CONJ-1"], "lemmas": []}], "packet": [{"packet": ""}],
            "test specs": [{"specs": []}], "file tests": [{"tickets": ["T-8"], "refusals": []}],
            "children": [{"tests": [{"id": "T-8", "refs": ["flat:CONJ-1"]}]}], "close": [{"ok": True}]},
            dict(H, ref="P-0009", ticket="T-7"))
        self.assertIsNone(err, err)
        self.assertIn("the packet was not filed: no reason given", res["notes"])


if __name__ == "__main__":
    unittest.main()
