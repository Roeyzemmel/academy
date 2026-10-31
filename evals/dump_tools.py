"""Write evals/mocks/academy/_tools.json: the academy MCP server's own tools/list, so the
mocked tools in the eval suites carry their real schemas and descriptions.

    python3 evals/dump_tools.py        (rerun after changing a tool's schema)
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "academy", "lib"))
sys.path.insert(0, os.path.join(REPO, "academy", "mcp"))

import server  # noqa: E402

out = os.path.join(HERE, "mocks", "academy", "_tools.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump({"tools": [t.listing() for t in server.TOOLS.values()]}, fh, indent=1)
    fh.write("\n")
print(out)
