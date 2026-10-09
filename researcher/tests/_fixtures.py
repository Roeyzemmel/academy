"""Shared fixtures for the Researcher plugin's tests: a throw-away workspace in a temp dir.

The workspace has
  researcher@t   home R, ns s9, with .claude/academy.json (switched over)
  researcher@old home O, ns s8, no academy.json (legacy layout: claims/)
  scientist@t    home L, ns lab, no academy.json (legacy claims/lab/)
  expert@t       home E
and a board B. ``ACADEMY_WORKSPACE`` and ``ACADEMY_CALLER_DIR`` point into the temp dir
for the duration of a test (in-process and for hook subprocesses alike).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
SCRIPTS = os.path.join(PLUGIN, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import _academy as ac  # noqa: E402


def researcher_config(instance="researcher@t", ns="s9", extra=None):
    cfg = {
        "schema": 1, "role": "researcher", "instance": instance,
        "domains": ["test-domain"], "ns": ns,
        "paths": {"objects": "objects", "proofs": "proofs", "journal": "journal",
                  "audits": "audits", "records": "objects",
                  "views": ["views", "INDEX.md"]},
        "registry": {"profile": "s1", "root": "objects", "statusKeeper": "claim-keeper"},
        "budget": {"itemsPerRun": 3, "serial": True, "orchestratorModel": "sonnet",
                   "maxModel": "fable", "ticketDefault": {"runs": 1, "max_model": "sonnet"}},
        "gate": {"commit": "normal", "build": False, "baseline": None, "branches": {}},
        "researcher": {"objectKinds": ["definition", "claim", "conjecture", "question",
                                       "example", "assumption", "direction"],
                       "statusField": "status", "reviewsHome": "expert@t",
                       "lab": "scientist@t",
                       "generalize": {"maxPerRun": 3, "raiseAbove": "conjectured"}},
    }
    for k, v in (extra or {}).items():
        cfg[k] = v
    assert not ac.validate_config(cfg), ac.validate_config(cfg)
    return cfg


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


def record(status="open", oid="C-1", kind="claim", extra=""):
    st = "status: %s\n" % status if status is not None else ""
    return ("---\nid: %s\nkind: %s\ntitle: \"A claim\"\n%sstatement: \"x\"\n"
            "history:\n  - \"2026-09-01 | open | status: created\"\n%s---\n\n## Remarks\n"
            % (oid, kind, st, extra))


class Workspace(unittest.TestCase):
    """Base class: builds the workspace; subclasses use self.R, self.O, self.L, self.B."""

    researcher_cfg_extra = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="researcher-test-")
        t = self.tmp.replace("\\", "/")
        self.R, self.O, self.L = t + "/slope", t + "/old", t + "/lab"
        self.E, self.B = t + "/papers", t + "/board"
        for d in (self.R, self.O, self.L, self.E, self.B):
            os.makedirs(d)
        self.ws_path = os.path.join(self.tmp, "workspace.json")
        ws = {"instances": {
            "researcher@t": {"role": "researcher", "home": self.R,
                             "domains": ["test-domain"], "ns": "s9"},
            "researcher@old": {"role": "researcher", "home": self.O,
                               "domains": ["test-domain"], "ns": "s8"},
            "scientist@t": {"role": "scientist", "home": self.L,
                            "domains": ["test-domain"], "ns": "lab"},
            "expert@t": {"role": "expert", "home": self.E, "domains": ["test-domain"]}},
            "board": self.B, "human": {"name": "Ada"}}
        with open(self.ws_path, "w", encoding="utf-8") as fh:
            json.dump(ws, fh)
        write(os.path.join(self.R, ".claude", "academy.json"),
              json.dumps(researcher_config(extra=self.researcher_cfg_extra), indent=2))
        self._env = {k: os.environ.get(k) for k in ("ACADEMY_WORKSPACE", "ACADEMY_CALLER_DIR")}
        os.environ["ACADEMY_WORKSPACE"] = self.ws_path
        os.environ["ACADEMY_CALLER_DIR"] = os.path.join(self.tmp, "callers")

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_hook(self, script, event, cwd=None):
        """Run a hook script as Claude Code does; return (rc, parsed stdout | None)."""
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)],
                             input=json.dumps(event).encode("utf-8"),
                             capture_output=True, env=env, cwd=cwd or self.tmp, timeout=60)
        out = res.stdout.decode("utf-8").strip()
        return res.returncode, (json.loads(out) if out else None)

    def run_script(self, script, *args, cwd=None):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + list(args),
                             capture_output=True, env=env, cwd=cwd or self.R, timeout=60)
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")


def decision(out):
    return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")
