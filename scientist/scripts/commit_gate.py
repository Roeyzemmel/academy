"""PreToolUse gate (matcher ``Bash|PowerShell``) on ``git commit`` in a Scientist home.

Refuses a commit that would put a broken experiment header, or an orphaned result,
into history. Two rules, both of which have bitten before:

  * an experiment whose header still has a placeholder, or whose Result line reads
    as a theorem, must not be committed -- the queue runs HEAD, so a bad header
    becomes the record of the run;
  * a result JSON is committed together with the script that produced it, or it is
    evidence nobody can rerun.

Scoping (the fix over the old flatsurf gate, which read only Bash and only the
session cwd): the gate works out **which repository each ``git commit`` in the
command runs in** (``cd`` / ``Set-Location`` / ``pushd`` segments and ``git -C``,
bash or PowerShell), and acts only when that repository's top level is a Scientist
home (``_common.lab_config``: its ``.claude/academy.json`` has role scientist and
workspace.json lists the instance as a scientist). Anywhere else it is silent.

Mode comes from the home's ``gate`` block (``gate_mode`` with the current branch):
``off`` is silent, ``normal`` blocks on checker errors, ``strict`` on warnings too,
``warn`` reports what ``normal`` would block (stderr, ``commit gate (warn):``) and lets
the commit go ahead, as the Author gate does. The author can always override by running
the commit themselves.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _common as c  # noqa: E402
from _common import ac  # noqa: E402


def staged(root):
    # a deletion has no header to check
    out = c.git(root, "diff", "--cached", "--name-only", "--diff-filter=d")
    if out is None:
        return []
    return [ln.strip().replace("\\", "/") for ln in out.splitlines() if ln.strip()]


def tracked(root, rel):
    return c.git(root, "ls-files", "--error-unmatch", rel) is not None


def orphaned_results(root, files, exp_dir="experiments", res_dir="results",
                     is_tracked=None):
    """Staged ``<results>/<stem>.json``, or per-run ``<results>/<stem>/<run>.json``,
    whose ``<experiments>/<stem>.py`` is neither staged nor already in history."""
    is_tracked = is_tracked or (lambda rel: tracked(root, rel))
    staged_set = set(files)
    res_dir = res_dir.strip("/")
    problems = []
    for rel in files:
        if not (rel.startswith(res_dir + "/") and rel.endswith(".json")):
            continue
        parts = rel[len(res_dir) + 1:].split("/")
        stem = parts[0] if len(parts) == 2 else os.path.basename(rel)[: -len(".json")]
        script = "%s/%s.py" % (exp_dir, stem)
        if script in staged_set or is_tracked(script):
            continue
        problems.append((rel, script))
    return problems


def check_repo(root, cfg):
    """Complaints for a commit in the lab repo ``root`` (list of strings)."""
    return check_repo_mode(root, cfg)[1]


def check_repo_mode(root, cfg):
    """``(mode, complaints)`` for a commit in the lab repo ``root``; in mode 'warn' the
    complaints are those of 'normal' (checker errors, orphaned results)."""
    mode = ac.gate_mode(cfg, c.git_branch(root))
    if mode == "off":
        return mode, []
    files = staged(root)
    home = cfg["_home"]
    complaints = []
    scripts = [f for f in files if c.is_experiment(cfg, os.path.join(root, f))]
    if scripts:
        code, output = c.run_checker(cfg, [os.path.join(root, f) for f in scripts],
                                     strict=(mode == "strict"))
        if code not in (None, 0):
            label = (": ERROR: ", ": WARN: ") if mode == "strict" else (": ERROR: ",)
            bad = [ln for ln in output.splitlines() if any(t in ln for t in label)]
            if bad:
                complaints.append("The staged experiment scripts do not satisfy the "
                                  "header contract:\n" + "\n".join(bad))
    exp_dir = c.relative(root, os.path.join(home, c.experiments_dir(cfg)))
    res_dir = c.relative(root, os.path.join(home, c.results_dir(cfg)))
    for rel, script in orphaned_results(root, files, exp_dir, res_dir):
        complaints.append(
            "%s is staged but %s is neither staged nor in history. Commit the script "
            "with the result it produced, or the result cannot be rerun." % (rel, script))
    return mode, complaints


def main():
    event = ac.read_event()
    if ac.tool_name(event) not in ("Bash", "PowerShell"):
        return 0
    command = ac.shell_command(event)
    if not ac.is_git_commit(command):
        return 0
    complaints = []
    seen = set()
    for target in c.commit_targets(command, ac.event_cwd(event)):
        root = c.git_toplevel(target)
        if not root or root.lower() in seen:
            continue
        seen.add(root.lower())
        cfg = c.lab_config(root)
        if cfg is None:
            continue
        mode, found = check_repo_mode(root, cfg)
        if mode == "warn" and found:
            sys.stderr.write("commit gate (warn): %s: %d finding(s); not blocking on this "
                             "branch.\n%s\n" % (cfg.get("instance", root), len(found),
                                                  "\n\n".join(found)))
            continue
        complaints.extend(found)
    if not complaints:
        return 0
    return c.speak(
        "\n\n".join(complaints)
        + "\n\nFix these and commit again, or say why the rule does not apply here "
          "and let the author run the commit themselves.")


if __name__ == "__main__":
    sys.exit(main())
