"""Shared helpers for the flatsurf plugin's hook gates (the FlatSurfLab gates and the claim check).

Every gate reads the hook event as JSON on stdin, resolves the project root from
``cwd``, and exits 0 immediately when the checkout does not look like this repo --
so nothing here misfires if the directory is ever opened somewhere else.

Exit-code contract (Claude Code hooks):
    0  silent, nothing to say
    2  stderr goes back to the model: blocking for PreToolUse, advisory context
       for PostToolUse
"""

import json
import os
import subprocess
import sys

CHECKER = os.path.join("scripts", "check_experiments.py")
EXEMPT = {"_template.py", "smoke_sage.py", "__init__.py"}


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


def is_flatsurflab(root):
    return (os.path.isfile(os.path.join(root, CHECKER))
            and os.path.isdir(os.path.join(root, "fslab")))


def edited_path(event):
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    path = tool_input.get("file_path")
    return path if isinstance(path, str) and path else None


def bash_command(event):
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command")
    return command if isinstance(command, str) else ""


def is_experiment(root, path):
    """True for experiments/<something>.py that is meant to carry a header."""
    if not path:
        return False
    try:
        rel = os.path.relpath(os.path.abspath(path), root)
    except ValueError:
        return False
    parts = rel.replace("\\", "/").split("/")
    return (len(parts) == 2 and parts[0] == "experiments"
            and parts[1].endswith(".py") and parts[1] not in EXEMPT)


def relative(root, path):
    try:
        return os.path.relpath(os.path.abspath(path), root).replace("\\", "/")
    except ValueError:
        return str(path)


def run_checker(root, args=()):
    """Run scripts/check_experiments.py. Returns (exit code, output) or (None, '')
    if it could not be run at all -- a gate never fails a task over its own tooling."""
    cmd = [sys.executable, os.path.join(root, CHECKER), "--quiet"] + list(args)
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def git(root, *args):
    try:
        proc = subprocess.run(["git"] + list(args), cwd=root,
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def speak(message):
    """Hand `message` back to the model and stop this tool call's silence."""
    sys.stderr.write(message.rstrip() + "\n")
    return 2
