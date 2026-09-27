"""PreToolUse gate on `git commit`: refuse a commit that would put a broken
experiment header, or an orphaned result, into history.

Two rules from CLAUDE.md, both of which have bitten before:

  * an experiment whose header still has a placeholder, or whose Result line reads
    as a theorem, must not be committed -- the queue runs HEAD, so a bad header
    becomes the record of the run;
  * a result JSON is committed together with the script that produced it, or it is
    evidence nobody can rerun.

Blocking, but only on errors the checker calls errors; warnings pass. The author
can always override by running the commit themselves.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _common as c  # noqa: E402


def staged(root):
    out = c.git(root, "diff", "--cached", "--name-only", "--diff-filter=d")   # a deletion has no header to check
    if out is None:
        return []
    return [ln.strip().replace("\\", "/") for ln in out.splitlines() if ln.strip()]


def tracked(root, rel):
    out = c.git(root, "ls-files", "--error-unmatch", rel)
    return out is not None


def orphaned_results(root, files):
    """Staged results/<stem>.json, or per-run results/<stem>/<run>.json (what
    save_result(..., subdir=<stem>) writes), whose experiments/<stem>.py is
    neither staged nor already in history."""
    staged_set = set(files)
    problems = []
    for rel in files:
        if not (rel.startswith("results/") and rel.endswith(".json")):
            continue
        parts = rel.split("/")
        stem = parts[1] if len(parts) == 3 else os.path.basename(rel)[: -len(".json")]
        script = "experiments/%s.py" % stem
        if script in staged_set or tracked(root, script):
            continue
        problems.append((rel, script))
    return problems


def main():
    event = c.read_event()
    root = c.project_root(event)
    if not c.is_flatsurflab(root):
        return 0
    command = c.bash_command(event)
    if "git commit" not in command:
        return 0

    files = staged(root)
    scripts = [f for f in files
               if f.startswith("experiments/") and f.endswith(".py")
               and os.path.basename(f) not in c.EXEMPT]

    complaints = []

    if scripts:
        code, output = c.run_checker(root, [os.path.join(root, f) for f in scripts])
        if code not in (None, 0):
            errors = [ln for ln in output.splitlines() if ": ERROR: " in ln]
            if errors:
                complaints.append(
                    "The staged experiment scripts do not satisfy the header "
                    "contract:\n" + "\n".join(errors))

    for rel, script in orphaned_results(root, files):
        complaints.append(
            "%s is staged but %s is neither staged nor in history. Commit the "
            "script with the result it produced, or the result cannot be rerun."
            % (rel, script))

    if not complaints:
        return 0
    return c.speak(
        "\n\n".join(complaints)
        + "\n\nFix these and commit again, or say why the rule does not apply "
          "here and let the author run the commit themselves.")


if __name__ == "__main__":
    sys.exit(main())
