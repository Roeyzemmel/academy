"""Shared fixtures for the Author plugin's tests: a throw-away workspace with an
Author home, an Expert/Researcher/Scientist instance, a board, and fake checker /
build scripts, all under one temp directory. Nothing touches a real home.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
SCRIPTS = os.path.join(PLUGIN, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

HAVE_GIT = shutil.which("git") is not None

FAKE_CHECKER = r'''import os, sys
# prints the lines of FAKE_FINDINGS (a file next to this script) and exits with FAKE_CODE
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "fake_findings.txt"), encoding="utf-8") as fh:
    body = fh.read()
code = int(open(os.path.join(here, "fake_code.txt")).read().strip() or 0)
with open(os.path.join(here, "checker_calls.txt"), "a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\n")
sys.stdout.write(body)
sys.exit(code)
'''

FAKE_BUILD = r'''import os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "build_calls.txt"), "a", encoding="utf-8") as fh:
    fh.write(os.getcwd() + "\n")
sys.exit(int(open(os.path.join(here, "build_code.txt")).read().strip() or 0))
'''


def author_config(home, tools, instance="author@t", **over):
    cfg = {
        "schema": 1, "role": "author", "instance": instance, "domains": ["dom"],
        "ns": "paper",
        "paths": {"tex": ["main.tex", "sections/*.tex"], "bib": "references.bib",
                  "drafts": "Drafts", "agenda": "Drafts/agenda.md",
                  "records": "claims",
                  "views": ["Drafts/statements.md"]},
        "registry": {"profile": "paper", "root": "claims"},
        "gate": {"commit": "normal", "build": True,
                 "baseline": ".claude/paper-gate-baseline.txt",
                 "branches": {"academy-migration": {"commit": "off"}}},
        "author": {
            "main": "main.tex",
            "build": {"dir": ".build", "cmd": [sys.executable,
                                               os.path.join(tools, "fake_build.py")],
                      "lock": ".build/.lock"},
            "checker": {"script": os.path.join(tools, "fake_checker.py").replace("\\", "/"),
                        "args": [], "strictArgs": ["--strict"],
                        "statements": "Drafts/statements.md"},
            "writers": ["math-writer", "math-editor", "tex-engineer", "figure-maker",
                        "note-sweeper", "librarian"],
            "bibWriters": ["librarian"],
        },
    }
    for k, v in over.items():
        cfg[k] = v
    return cfg


class Sandbox(object):
    """A temp workspace: author home, other homes, board, tools."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="author-test-")
        self.tools = os.path.join(self.root, "tools")
        self.home = os.path.join(self.root, "paper")
        self.other = os.path.join(self.root, "lab")
        self.board = os.path.join(self.root, "board")
        for d in (self.tools, self.home, self.other, self.board,
                  os.path.join(self.home, "sections"), os.path.join(self.home, "Drafts"),
                  os.path.join(self.home, ".claude")):
            os.makedirs(d, exist_ok=True)
        for inst in ("author@t", "expert@t", "researcher@t", "scientist@t", "human"):
            os.makedirs(os.path.join(self.board, inst), exist_ok=True)
        self.write(os.path.join(self.tools, "fake_checker.py"), FAKE_CHECKER)
        self.write(os.path.join(self.tools, "fake_build.py"), FAKE_BUILD)
        self.set_checker("", 0)
        self.set_build(0)
        self.write_config()
        self.write(os.path.join(self.home, "main.tex"), "\\documentclass{amsart}\n")
        self.write(os.path.join(self.home, "references.bib"), "")
        self.workspace = os.path.join(self.root, "workspace.json")
        self.write(self.workspace, json.dumps({
            "instances": {
                "author@t": {"role": "author", "home": self.home, "domains": ["dom"],
                             "ns": "paper"},
                "expert@t": {"role": "expert", "home": os.path.join(self.root, "lib"),
                             "domains": ["dom"]},
                "researcher@t": {"role": "researcher", "home": os.path.join(self.root, "nb"),
                                 "domains": ["dom"], "ns": "s1"},
                "scientist@t": {"role": "scientist", "home": self.other,
                                "domains": ["dom"], "ns": "lab"}},
            "board": self.board, "human": {"name": "Roey", "noteMacro": "\\Roey"}}))
        self.env = dict(os.environ, ACADEMY_WORKSPACE=self.workspace,
                        ACADEMY_CALLER_DIR=os.path.join(self.root, "callers"),
                        PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")

    # ------------------------------------------------------------------
    @staticmethod
    def write(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def read(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def write_config(self, **over):
        self.write(os.path.join(self.home, ".claude", "academy.json"),
                   json.dumps(author_config(self.home, self.tools, **over), indent=2))

    def set_checker(self, output, code):
        self.write(os.path.join(self.tools, "fake_findings.txt"), output)
        self.write(os.path.join(self.tools, "fake_code.txt"), str(code))

    def set_build(self, code):
        self.write(os.path.join(self.tools, "build_code.txt"), str(code))

    def set_baseline(self, keys):
        self.write(os.path.join(self.home, ".claude", "paper-gate-baseline.txt"),
                   "# baseline\n" + "".join(k + "\n" for k in keys))

    def calls(self, name):
        p = os.path.join(self.tools, name)
        return self.read(p).splitlines() if os.path.isfile(p) else []

    def git_init(self, path, branch="main"):
        subprocess.run(["git", "init", "-q", "-b", branch, path], check=True,
                       capture_output=True)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def run_hook(script, event, env, cwd=None):
    """Run a hook script with ``event`` on stdin: (returncode, parsed stdout|None, stderr)."""
    res = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)],
                         input=json.dumps(event).encode("utf-8"), capture_output=True,
                         env=env, cwd=cwd, timeout=120)
    out = res.stdout.decode("utf-8").strip()
    return res.returncode, (json.loads(out) if out else None), res.stderr.decode(
        "utf-8", "replace")
