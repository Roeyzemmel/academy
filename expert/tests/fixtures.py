"""Shared fixtures for the Expert plugin's tests: a throw-away academy.

``Sandbox`` builds, in a temp directory, a workspace.json (``expert@ts`` with a
library home, ``author@bi`` with a paper home), an empty board, and a small library
(index.md, cached .txt/.meta/.src files). Scripts run as subprocesses exactly as
Claude Code runs a hook, with ``ACADEMY_WORKSPACE`` pointing at the sandbox.
Run from the repo root:  py -m unittest discover expert/tests
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

import _academy as ac  # noqa: E402

INDEX = """# Index

One row per cached source.

| key | authors, short title | version | source URL | source dir | how read | date | used for |
|---|---|---|---|---|---|---|---|
| ABC21 | Able-Baker-Charlie, "A paper" | arXiv v2 (1 Jan 2021) | `https://arxiv.org/pdf/2101.00001v2` | `ABC21.src/` | **source** | 2026-09-19 | Lemma 2.1 |
| XY20 | Ex-Why, "Another" | published | `https://example.org/xy.pdf` | **no arXiv source** | text (extraction) | 2026-09-19 | Thm 3 |

## Not cached

Prose after the table.
"""

ABC_TXT = ("Lemma 2.1. Let M be a translation sur-\nface and let x be a peri-\nodic point. "
           "Then the orbit of x is ﬁnite.\fTheorem 3.4. Every “nice” surface "
           "is illuminated.\n")
ABC_TEX = ("\\begin{lem}\\label{L:one}\nLet $M$ be a translation surface and let $x$ be a "
           "periodic point.\nThen the orbit of $x$ is finite.\n\\end{lem}\n")
XY_TXT = "Theorem 3. Any two points are finitely blocked\non a Veech surface.\n"


def card_text(key="ABC21", pinpoint="Lemma 2.1", quote="Let M be a translation surface and "
              "let x be a periodic point.", read_from="extraction", statement="The orbit "
              "of a periodic point is finite.", hypotheses=("M a translation surface",),
              **extra):
    import cards
    meta = {"key": key, "pinpoint": pinpoint, "version": "arXiv v2", "read_from": read_from,
            "verdict": "match", "used_by": ["paper:lem:x"], "checked": "2026-09-28",
            "by": "expert@ts/librarian"}
    meta.update(extra)
    return cards.render_card(meta, statement, list(hypotheses), quote)


class Sandbox(object):
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="expert-test-")
        self.lib = os.path.join(self.root, "papers")
        self.bi = os.path.join(self.root, "bi")
        self.board = os.path.join(self.root, "board")
        for d in (self.lib, self.bi, self.board, os.path.join(self.board, "expert@ts"),
                  os.path.join(self.board, "author@bi"), os.path.join(self.board, "human")):
            os.makedirs(d, exist_ok=True)
        self.ws_path = os.path.join(self.root, "workspace.json")
        ws = {"instances": {
            "expert@ts": {"role": "expert", "home": self.lib.replace("\\", "/"),
                          "domains": ["translation-surfaces"]},
            "author@bi": {"role": "author", "home": self.bi.replace("\\", "/"),
                          "domains": ["translation-surfaces"], "ns": "paper"}},
            "board": self.board.replace("\\", "/"), "human": {"name": "Roey"}}
        with open(self.ws_path, "w", encoding="utf-8") as fh:
            json.dump(ws, fh)
        self.write("papers/index.md", INDEX)
        self.write("papers/ABC21.txt", ABC_TXT)
        self.write("papers/ABC21.meta", "key: ABC21\nauthors: Able, A.\ntitle: A paper\n")
        self.write("papers/ABC21.src/main.tex", ABC_TEX)
        self.write("papers/XY20.txt", XY_TXT)
        self.env = {"ACADEMY_WORKSPACE": self.ws_path, "ACADEMY_CALLER_DIR":
                    os.path.join(self.root, "callers"), "PYTHONIOENCODING": "utf-8"}
        self._old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def path(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def write(self, rel, text, newline="\n"):
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline=newline) as fh:
            fh.write(text)
        return p

    def read(self, rel):
        with open(self.path(rel), "r", encoding="utf-8", newline="") as fh:
            return fh.read()

    def workspace(self):
        return ac.load_workspace(self.ws_path)

    def close(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)


def run_script(script, event=None, args=(), env=None, cwd=None):
    """Run a script (hook or CLI); return (code, parsed JSON stdout or text, stderr)."""
    full = dict(os.environ)
    full.update(env or {})
    res = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + list(args),
                         input=(json.dumps(event) if event is not None else "").encode("utf-8"),
                         capture_output=True, env=full, cwd=cwd, timeout=120)
    out = res.stdout.decode("utf-8", "replace").strip()
    try:
        parsed = json.loads(out) if out else None
    except ValueError:
        parsed = out
    return res.returncode, parsed, res.stderr.decode("utf-8", "replace")
