"""Temp superproject with one submodule checkout and a bare remote, for ship.py tests."""
import os
import subprocess

# Never wait on an editor, pager or credential prompt; set process-wide so ship.py's own
# git calls in the tests inherit it too.
QUIET_GIT = {"GIT_EDITOR": "true", "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat",
             "GIT_MERGE_AUTOEDIT": "no", "GCM_INTERACTIVE": "never"}
os.environ.update(QUIET_GIT)


def run(cwd, *args):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60,
                       stdin=subprocess.DEVNULL)
    if p.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(args), p.stderr))
    return p.stdout.strip()


def configure(repo):
    run(repo, "config", "user.name", "Test")
    run(repo, "config", "user.email", "t@example.com")
    run(repo, "config", "commit.gpgsign", "false")


def add_submodule(tmp, root, name):
    """Add submodule ``name`` to the temp workspace: a bare remote ``<name>-remote.git`` and
    a checkout on main with one commit pushed. Returns (sub_path, remote_path)."""
    remote = os.path.join(tmp, "%s-remote.git" % name)
    sub = os.path.join(root, name)
    run(tmp, "init", "-q", "--bare", "-b", "main", remote)
    with open(os.path.join(root, ".gitmodules"), "a", encoding="utf-8") as f:
        f.write('[submodule "%s"]\n\tpath = %s\n\turl = %s\n' % (name, name, remote.replace("\\", "/")))
    run(tmp, "clone", "-q", remote, sub)
    configure(sub)
    run(sub, "switch", "-q", "-c", "main")
    with open(os.path.join(sub, "a.txt"), "w", encoding="utf-8") as f:
        f.write("a\n")
    run(sub, "add", "a.txt")
    run(sub, "commit", "-q", "-m", "init")
    run(sub, "push", "-q", "-u", "origin", "main")
    return sub, remote


def make_workspace(tmp):
    """Return (root, sub_path, remote_path). The submodule is 'sub', on main, one commit pushed."""
    root = os.path.join(tmp, "root")
    remote = os.path.join(tmp, "remote.git")
    sub = os.path.join(root, "sub")
    os.makedirs(root)
    run(tmp, "init", "-q", "--bare", "-b", "main", remote)
    run(root, "init", "-q", "-b", "main")
    with open(os.path.join(root, ".gitmodules"), "w", encoding="utf-8") as f:
        f.write('[submodule "sub"]\n\tpath = sub\n\turl = %s\n' % remote.replace("\\", "/"))
    run(tmp, "clone", "-q", remote, sub)
    for repo in (root, sub):
        configure(repo)
    run(sub, "switch", "-q", "-c", "main")
    with open(os.path.join(sub, "a.txt"), "w", encoding="utf-8") as f:
        f.write("a\n")
    run(sub, "add", "a.txt")
    run(sub, "commit", "-q", "-m", "init")
    run(sub, "push", "-q", "-u", "origin", "main")
    return root, sub, remote


# A stand-in for the author plugin's commit_gate module. The mode is STUB_MODE if set,
# else the cfg's gate.commit (as the real gate derives it), else "normal".
STUB_GATE = '''
import json, os, sys

# The loader must register this module in sys.modules under its own name before
# executing it (dataclasses, pickling and friends look it up there).
if sys.modules.get(__name__) is None or sys.modules[__name__].__dict__ is not globals():
    raise ImportError("module %s not registered in sys.modules before exec" % __name__)

def gate_check(home, cfg, branch):
    with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"home": home, "cfg": cfg, "branch": branch}) + "\\n")
    if os.environ.get("STUB_RAISE"):
        raise RuntimeError("stub gate exploded")
    gate = cfg.get("gate") if isinstance(cfg.get("gate"), dict) else {}
    mode = os.environ.get("STUB_MODE") or gate.get("commit") or "normal"
    findings = json.loads(os.environ.get("STUB_FINDINGS", "{}"))
    return mode, findings

# gate_check_detail as the current academy gate has it (STUB_CAUSE is the cause text);
# STUB_NO_DETAIL=1 stands in for an academy checkout that predates it, and
# STUB_NO_CHECK=1 (with it) for one that predates gate_check as well. It looks
# gate_check up at call time, so a test that wraps gate_check still sees its calls.
if not os.environ.get("STUB_NO_DETAIL"):
    def gate_check_detail(home, cfg, branch):
        mode, findings = gate_check(home, cfg, branch)
        return mode, findings, os.environ.get("STUB_CAUSE", "")
if os.environ.get("STUB_NO_CHECK"):
    del gate_check

if __name__ == "__main__":
    with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"argv": sys.argv[1:]}) + "\\n")
    print("baseline written")
    print("baseline note on stderr", file=sys.stderr)
'''
