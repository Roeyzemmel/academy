"""PostToolUse gate: after writing or editing a claim file in a claims.py registry, run
`claims.py check` on that file and hand any errors back as context.

Advisory only. It fires in any repo whose `.claude/flatsurf.json` names `claims.py` as
its registry (FlatSurfLab, BilliardIllumination) and stays silent everywhere else,
including Slope1, whose kb.py has its own hook.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _common as c  # noqa: E402

MAX_LINES = 20


def config(root):
    try:
        with open(os.path.join(root, ".claude", "flatsurf.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    event = c.read_event()
    root = c.project_root(event)
    cfg = config(root)
    if not cfg or (cfg.get("registry") or {}).get("tool") != "claims.py":
        return 0
    path = c.edited_path(event)
    if not path or not path.endswith(".md") or not os.path.isfile(path):
        return 0
    rel = c.relative(root, path).replace("\\", "/")
    parts = rel.split("/")
    if len(parts) != 3 or parts[0] != "claims" or parts[2] in ("INDEX.md", "README.md"):
        return 0
    tool = os.path.normpath(os.path.join(root, cfg.get("lab", "."), "scripts", "claims.py"))
    if not os.path.isfile(tool):
        return 0
    try:
        proc = subprocess.run([sys.executable, tool, "--repo", root, "check", path],
                              cwd=root, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return 0
    if proc.returncode == 0:
        return 0
    lines = [ln for ln in (proc.stdout + proc.stderr).splitlines() if "ERROR" in ln]
    if not lines:
        return 0
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + ["... (%d more)" % (len(lines) - MAX_LINES)]
    return c.speak("claims.py check on %s:\n%s\nFix the claim file; the format is "
                   "FlatSurfLab's docs/claims.md." % (rel, "\n".join(lines)))


if __name__ == "__main__":
    sys.exit(main())
