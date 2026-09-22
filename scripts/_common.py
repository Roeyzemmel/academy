"""Shared helpers for the `paper` plugin's gate scripts.

Every gate reads the hook JSON on stdin, resolves the project root from ``cwd``,
and exits 0 immediately when the project does not look like a paper repo -- so the
plugin is inert in any other checkout.
"""

import json
import os
import re
import subprocess
import sys

CHECKER = os.path.join("scripts", "check_paper.py")
GATE_CONFIG = os.path.join(".claude", "paper-gate.json")
TEX_DIRS = ("sections", "tikz")
DIRTY = os.path.join(".build", ".dirty")
BASELINE = os.path.join(".claude", "paper-gate-baseline.txt")
FINDING = re.compile(
    r"^\s*(?P<file>[^\s:]+):(?P<line>\d+):\s*(?P<label>.*?):\s*\[(?P<rule>[A-Z]\d+)\]"
)


def read_event():
    """Parse the hook event from stdin. Never raises: a bad event means 'do nothing'."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def project_root(event):
    root = event.get("cwd") or os.getcwd()
    return root if os.path.isdir(root) else os.getcwd()


def is_paper_repo(root):
    return os.path.isfile(os.path.join(root, CHECKER))


def gate_config(root):
    """Project overrides: {"commit": "strict"|"normal"|"off", "build": true|false}."""
    cfg = {"commit": "normal", "build": True}
    path = os.path.join(root, GATE_CONFIG)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except (ValueError, OSError):
            pass
    return cfg


def edited_path(event):
    """The file an Edit/Write/MultiEdit event touches, or None."""
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    return path if isinstance(path, str) and path else None


def bash_command(event):
    """The command of a Bash/PowerShell event, or ''."""
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command")
    return command if isinstance(command, str) else ""


def is_git_commit(command):
    """True when some segment of a shell command runs `git [options] commit`.

    Errs towards True (e.g. `git log --grep commit`), since a false positive only
    costs a checker run while a false negative lets a commit through ungated."""
    return re.search(r"\bgit\b[^;&|\n]*\bcommit\b", command) is not None


def relative(root, path):
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    except ValueError:          # different drives on Windows
        return None
    return None if rel.startswith("..") else rel.replace("\\", "/")


def is_paper_tex(root, path):
    """True for the paper's own .tex: main.tex, sections/*.tex, tikz/*.tex."""
    rel = relative(root, path) if path else None
    if not rel or not rel.endswith(".tex"):
        return False
    return rel == "main.tex" or rel.split("/")[0] in TEX_DIRS


def run_checker(root, strict=False, timeout=120):
    """Run the project's checker. Returns (exit code, combined output)."""
    cmd = [sys.executable, CHECKER] + (["--strict"] if strict else [])
    try:
        proc = subprocess.run(
            cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "checker timed out"
    except OSError as exc:
        return None, "checker could not run: %s" % exc
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def emit(event_name, payload, extra=None):
    """Print a hookSpecificOutput block and exit 0."""
    block = {"hookEventName": event_name}
    block.update(payload)
    out = {"hookSpecificOutput": block}
    if extra:
        out.update(extra)
    sys.stdout.write(json.dumps(out))
    sys.exit(0)


def mark_dirty(root):
    try:
        os.makedirs(os.path.join(root, ".build"), exist_ok=True)
        with open(os.path.join(root, DIRTY), "w", encoding="utf-8") as handle:
            handle.write("tex edited\n")
    except OSError:
        pass


def clear_dirty(root):
    try:
        os.remove(os.path.join(root, DIRTY))
    except OSError:
        pass


def findings(output):
    """Map finding key -> the first line that reported it. Keyed without line numbers,
    which drift with every edit."""
    found = {}
    for line in output.splitlines():
        m = FINDING.match(line)
        if not m:
            continue
        key = "%s|%s|%s" % (m.group("file").replace("\\", "/"),
                            m.group("label").strip(), m.group("rule"))
        found.setdefault(key, line.strip())
    return found


def load_baseline(root):
    path = os.path.join(root, BASELINE)
    if not os.path.isfile(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return {ln.strip() for ln in handle
                    if ln.strip() and not ln.startswith("#")}
    except OSError:
        return set()


def new_findings(root, output):
    """The findings in `output` that the recorded baseline does not accept."""
    baseline = load_baseline(root)
    return {k: v for k, v in findings(output).items() if k not in baseline}
