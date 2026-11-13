"""Every plugin script a workflow prompt names carries its full path.

A bare "reviews.py decide ..." in a stage prompt makes the agent guess the folder
(<academy repo>/<plugin>/scripts/<name>.py). Each workflow that names a script in a
prompt must therefore also spell its path, in the style of workplan.js's SCRIPTS line.
Comment lines, the meta block and schema description: lines are for humans and exempt.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BARE = re.compile(r"(?<![\w/.-])([a-z][a-z_]*)\.py\b")


def prompt_lines(text):
    in_meta = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("export const meta"):
            in_meta = True
            continue
        if in_meta:
            in_meta = s != "}"
            continue
        if s.startswith("//") or s.startswith("*") or "description:" in s:
            continue
        yield re.sub(r"\s//\s.*$", "", line)


class WorkflowScriptPaths(unittest.TestCase):
    def test_bare_script_names_have_a_full_path(self):
        files = sorted(REPO.glob("*/workflows/*.js"))
        self.assertTrue(files, "no workflows found under " + str(REPO))
        missing = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            names = {m.group(1) for line in prompt_lines(text) for m in BARE.finditer(line)}
            for n in sorted(names):
                if not re.search(r"/scripts/" + re.escape(n) + r"\.py", text):
                    missing.append(f"{f.relative_to(REPO).as_posix()}: {n}.py has no full path (.../scripts/{n}.py)")
        self.assertEqual(missing, [], "\n" + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
