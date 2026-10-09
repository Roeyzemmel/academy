"""Shared fixtures for the Scientist plugin's tests: a temporary lab home, workspace
and board, built from ``tests/fixtures/lab`` (real SciLab result JSONs and
headers, copied 2026-09-28)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(TESTS)
SCRIPTS = os.path.join(PLUGIN, "scripts")
FIXTURES = os.path.join(TESTS, "fixtures")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

EW = "2026-09-23_ew_ornithorynque_record"
TORUS = "2026-09-24_torus_cover_periodic_growth"

LAB_CONFIG = {
    "schema": 1, "role": "scientist", "instance": "scientist@main",
    "domains": ["translation-surfaces"], "ns": "lab",
    "paths": {"package": "fslab", "experiments": "experiments/*.py", "results": "results",
              "queue": "queue", "records": "claims", "tests": "tests",
              "views": ["claims/INDEX.md"]},
    "registry": {"profile": "lab", "root": "claims"},
    "gate": {"commit": "normal", "build": False, "baseline": None,
             "branches": {"academy-migration": {"commit": "off"}}},
    "scientist": {
        "envs": {"laptop-wsl": {"kind": "wsl", "distro": "Ubuntu", "conda": "sci"},
                 "remote-a": {"worker": "remote-a"}},
        "policy": {"probe": "laptop-wsl", "test": "laptop-wsl", "run": "remote-a"},
        "queue": {"dir": "queue"},
        "experimentTypes": ["search", "measure", "verify", "probe"]},
}

RESEARCHER_CONFIG = {
    "schema": 1, "role": "researcher", "instance": "researcher@alpha",
    "domains": ["translation-surfaces"], "ns": "s1",
    "paths": {"objects": "objects", "proofs": "proofs", "journal": "journal",
              "audits": "audits", "records": "objects", "views": ["views"]},
    "registry": {"profile": "s1", "root": "objects"},
    "researcher": {"lab": "scientist@main"},
}


class Sandbox(object):
    """A temp directory with ``lab/`` (a Scientist home), ``notebook/`` (a
    Researcher home), ``other/`` (an Author home), ``board/`` and ``workspace.json``.
    ``env`` is os.environ with ACADEMY_WORKSPACE pointing at it."""

    def __init__(self, lab_config=None, researcher_ns="s1"):
        self.root = tempfile.mkdtemp(prefix="scitest-")
        self.lab = os.path.join(self.root, "lab")
        shutil.copytree(os.path.join(FIXTURES, "lab"), self.lab)
        self.write_json(os.path.join(self.lab, ".claude", "academy.json"),
                        lab_config or LAB_CONFIG)
        self.notebook = os.path.join(self.root, "notebook")
        rc = dict(RESEARCHER_CONFIG, ns=researcher_ns)
        self.write_json(os.path.join(self.notebook, ".claude", "academy.json"), rc)
        self.other = os.path.join(self.root, "other")
        os.makedirs(self.other)
        self.board = os.path.join(self.root, "board")
        for d in ("scientist@main", "researcher@alpha", "author@main", "human", "packets"):
            os.makedirs(os.path.join(self.board, d))
        self.workspace = os.path.join(self.root, "workspace.json")
        self.write_json(self.workspace, {
            "instances": {
                "scientist@main": {"role": "scientist", "home": self.lab,
                                 "domains": ["translation-surfaces"], "ns": "lab"},
                "researcher@alpha": {"role": "researcher", "home": self.notebook,
                                      "domains": ["translation-surfaces"],
                                      "ns": researcher_ns},
                "author@main": {"role": "author", "home": self.other,
                              "domains": ["translation-surfaces"], "ns": "paper"}},
            "board": self.board, "human": {"name": "Roey"},
            "compute": {"workers": {"remote-a": {"transport": "ssh", "host": "remote-a",
                                                 "maxJobs": 1, "gateway": "gw-a",
                                                 "conda": {"env": "sci"}}},
                        "gateways": {"gw-a": {"kind": "vpn", "check": "tcp-reachable",
                                              "probeHost": "remote-a:22"}}}})
        self.env = dict(os.environ, ACADEMY_WORKSPACE=self.workspace,
                        PYTHONIOENCODING="utf-8", ACADEMY_CALLER_DIR=os.path.join(
                            self.root, "callers"))
        self._old = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = self.workspace

    @staticmethod
    def write_json(path, obj):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, indent=2)

    def write(self, rel, text, base=None):
        path = os.path.join(base or self.lab, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return path

    def run(self, script, args, stdin=None, cwd=None):
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + list(args),
                              input=stdin, capture_output=True, text=True,
                              encoding="utf-8", env=self.env, cwd=cwd or self.root)
        return proc.returncode, proc.stdout, proc.stderr

    def git(self, *args, cwd=None):
        return subprocess.run(["git"] + list(args), cwd=cwd or self.lab,
                              capture_output=True, text=True)

    def close(self):
        if self._old is None:
            os.environ.pop("ACADEMY_WORKSPACE", None)
        else:
            os.environ["ACADEMY_WORKSPACE"] = self._old
        shutil.rmtree(self.root, ignore_errors=True)
