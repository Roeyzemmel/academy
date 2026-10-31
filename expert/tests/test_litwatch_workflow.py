"""The literature-watch workflow (workflows/litwatch.js), 2026-10-31: return-only scouts in
parallel, hits deduplicated in code by arXiv id or DOI (the sharper verdict kept), one
writer, an anomaly for a file written outside the Record stage. Skipped without node."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "litwatch.js")
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, prompt })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  return q.shift()
}
async function parallel(thunks) { const out = []; for (const t of thunks) { try { out.push(await t()) } catch (e) { out.push(null) } } return out }
const body = new Function('args', 'agent', 'phase', 'log', 'parallel', 'return (async () => {' + src + '})()')
body(plan.__args, agent, () => {}, () => {}, parallel).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""


def hit(i, verdict="related", overlap=""):
    return {"id": i, "title": "t", "authors": "a", "url": "u", "date": "2026-10-30",
            "overlap": overlap, "verdict": verdict, "note": ""}


PLAN = {"ok": True, "stop_reason": "", "window_start": "2026-10-24", "today": "2026-10-31",
        "files_before": ["_header.md", "watch-2026-10-24.md"],
        "sources": [{"kind": "category", "item": "math.DS"}, {"kind": "anchor", "item": "AB12"},
                    {"kind": "keyword", "item": "illumination"},
                    {"kind": "keyword", "item": "finite blocking"},
                    {"kind": "author", "item": "Lelievre"}]}


@unittest.skipUnless(NODE, "node is not installed")
class LitwatchTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        a = {"instance": "author@t"}
        a.update(args)
        plan = dict(plan, __args=a)
        d = tempfile.mkdtemp(prefix="acad-lw-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], out["calls"]

    def test_groups_dedupe_and_one_writer(self):
        res, calls = self.run_wf({
            "plan": [PLAN],
            "search categories": [{"ran": ["math.DS new"], "hits": [hit("2410.01234v2")]}],
            "search anchors": [{"ran": ["AB12 citing"], "hits": [hit("arXiv:2410.01234", "overlap", "paper:thm:x")]}],
            "search keywords 1": [{"ran": ["q1"], "hits": [hit("10.1000/XYZ")]}],
            "search keywords 2": [{"ran": ["q2"], "hits": [hit("https://doi.org/10.1000/xyz")]}],
            "record": [{"file": "ledgers/author@t/watch-2026-10-31.md",
                        "files_after": ["_header.md", "watch-2026-10-24.md", "watch-2026-10-31.md"]}]})
        labels = [c["label"] for c in calls]
        self.assertEqual(labels, ["plan", "search categories", "search anchors", "search keywords 1",
                                  "search keywords 2", "record"])
        ids = sorted(h["id"] for h in res["hits"])
        self.assertEqual(ids, ["10.1000/xyz", "2410.01234"])
        top = res["hits"][0]
        self.assertEqual((top["id"], top["verdict"]), ("2410.01234", "overlap"))   # sharper verdict kept
        for c in calls:
            if c["label"].startswith("search") or c["label"] == "plan":
                self.assertIn("WRITE NOTHING" if c["label"] != "plan" else "write nothing", c["prompt"])
        self.assertIn("Lelievre", next(c for c in calls if c["label"] == "search keywords 1")["prompt"])
        self.assertEqual(res["anomalies"], [])
        self.assertEqual(len(res["cite_candidates"]), 2)

    def test_a_file_written_outside_record_is_an_anomaly_and_a_lost_search_is_named(self):
        res, calls = self.run_wf({
            "plan": [dict(PLAN, sources=[{"kind": "keyword", "item": "k"}])],
            "search keywords 1": [None],
            "record": [{"file": "f", "files_after": ["_header.md", "watch-2026-10-24.md",
                                                    "watch-2026-10-31.md", "stray.md"]}]}, groups=1)
        self.assertEqual(res["lost"], ["keywords 1"])
        self.assertIn("stray.md", res["anomalies"][0])
        self.assertIn("Searches lost", calls[-1]["prompt"])

    def test_no_header_stops_and_a_statement_is_one_scout(self):
        res, calls = self.run_wf({"plan": [dict(PLAN, ok=False, stop_reason="no header")]})
        self.assertEqual(res["reason"], "no header")
        self.assertEqual([c["label"] for c in calls], ["plan"])
        res, calls = self.run_wf({"prior art paper:thm:x": ["report"]}, statement="paper:thm:x")
        self.assertEqual([c["label"] for c in calls], ["prior art paper:thm:x"])


if __name__ == "__main__":
    unittest.main()
