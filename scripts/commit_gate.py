"""PreToolUse gate: run the paper checker before a commit, and block on regressions.

The gate compares the checker's findings against a recorded baseline, so it blocks
what this session broke rather than the draft's known open state. A finding is keyed
by (file, label, rule) -- never by line number, which drifts with every edit.

Configuration, in .claude/paper-gate.json:
    {"commit": "strict"}  also gate on warnings
    {"commit": "normal"}  gate on violations only  (default)
    {"commit": "off"}     do not gate

Baseline: .claude/paper-gate-baseline.txt, one key per line. Regenerate it with
    py <plugin>/scripts/commit_gate.py --write-baseline
run from the project root, and commit it, whenever the open findings legitimately
change.
"""

import os
import sys

import _common as c

def write_baseline(root, strict):
    code, output = c.run_checker(root, strict=strict)
    if code is None:
        sys.stderr.write(output + "\n")
        return 1
    keys = sorted(c.findings(output))
    path = os.path.join(root, c.BASELINE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Findings accepted as the draft's known open state.\n")
        handle.write("# Key: file|label|rule. Regenerate with commit_gate.py "
                     "--write-baseline; shrinking this file is progress.\n")
        for key in keys:
            handle.write(key + "\n")
    sys.stdout.write("wrote %d baseline findings to %s\n" % (len(keys), c.BASELINE))
    return 0


def main():
    if "--write-baseline" in sys.argv:
        root = os.getcwd()
        if not c.is_paper_repo(root):
            sys.stderr.write("not a paper repo: no scripts/check_paper.py here\n")
            return 1
        return write_baseline(root, c.gate_config(root).get("commit") == "strict")

    event = c.read_event()
    # The hook's `if: Bash(git commit *)` does not filter compound commands (pipes,
    # `;`, heredocs), so without this check every such Bash call ran the checker and
    # was blocked by it. Checked here as well, as FlatSurfLab's gate does.
    if not c.is_git_commit(c.bash_command(event)):
        return 0
    root = c.project_root(event)
    if not c.is_paper_repo(root):
        return 0
    level = c.gate_config(root).get("commit", "normal")
    if level == "off":
        return 0

    code, output = c.run_checker(root, strict=(level == "strict"))
    if code is None or code == 0:
        return 0

    new = c.new_findings(root, output)
    if not new:
        return 0
    if not c.load_baseline(root):
        sys.stderr.write(
            "Commit blocked: check_paper.py%s exited %d and no baseline is recorded.\n\n"
            "%s\nFix these, or record the draft's known open state once with\n"
            "    py \"%s\" --write-baseline\n"
            "run from the project root, so the gate blocks regressions instead.\n"
            % (" --strict" if level == "strict" else "", code, output,
               os.path.abspath(__file__))
        )
        return 2

    sys.stderr.write(
        "Commit blocked: %d finding(s) that are not in the recorded baseline.\n\n%s\n\n"
        "These appeared since the baseline was written. Fix them, or -- if they are a "
        "deliberate change to the draft's open state -- regenerate the baseline with\n"
        "    py \"%s\" --write-baseline\n"
        % (len(new), "\n".join(sorted(new.values())), os.path.abspath(__file__))
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
