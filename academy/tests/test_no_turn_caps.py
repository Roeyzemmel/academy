"""#129 (the human, 2026-11-27): no agent of any plugin carries a turn cap (maxTurns);
agents are bounded by effort, workflows by their stages and lost-run handling."""
import glob
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class NoTurnCaps(unittest.TestCase):
    def test_no_agent_has_max_turns(self):
        agents = glob.glob(os.path.join(REPO, "*", "agents", "*.md"))
        self.assertGreater(len(agents), 20)
        found = []
        for path in agents:
            with open(path, encoding="utf-8") as fh:
                head = fh.read().split("\n---", 2)[0]
            if re.search(r"(?m)^maxTurns:", head):
                found.append(os.path.relpath(path, REPO))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
