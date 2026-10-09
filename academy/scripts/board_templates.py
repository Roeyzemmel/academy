"""board_templates.py -- the GitHub board's repository files, rendered for one workspace.

    py board_templates.py ticket-form [--workspace FILE]           print the rendered ticket.yml
    py board_templates.py render --out DIR [--workspace FILE]      write DIR/.github/ (the issue
                                                                   form and the board-sync workflow)
    py board_templates.py check --out DIR [--workspace FILE]       exit 1 when DIR/.github differs

The templates are ``academy/templates/github-board/.github/``. Everything is copied as is
except the issue form ``ISSUE_TEMPLATE/ticket.yml``, whose "To (instance)" dropdown holds
the placeholder ``"{{instances}}"``: it becomes the workspace's instance names and
``human``, in the order the Project's Instance field uses (``board_project.py``). A new
instance reaches the form by rerunning ``render`` (``/academy:board-migrate`` does it at
cutover), never by editing the options by hand. Offline: nothing is sent anywhere.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))

import academy_common as ac  # noqa: E402

TEMPLATES = os.path.join(os.path.dirname(HERE), "templates", "github-board", ".github")
TICKET_FORM = os.path.join("ISSUE_TEMPLATE", "ticket.yml")
PLACEHOLDER = '["{{instances}}"]'


def instance_options(instances):
    """The dropdown's options: the instance names (sorted, as the Project field) + human."""
    out = sorted(instances or [])
    return out + ([ac.HUMAN] if ac.HUMAN not in out else [])


def render_ticket_form(instances, template=None):
    """The issue form with the instance dropdown filled in (a YAML flow list)."""
    if template is None:
        with open(os.path.join(TEMPLATES, TICKET_FORM), encoding="utf-8") as fh:
            template = fh.read()
    if PLACEHOLDER not in template:
        raise ValueError("the ticket form template has no %s placeholder" % PLACEHOLDER)
    return template.replace(PLACEHOLDER, json.dumps(instance_options(instances)))


def rendered_files(instances):
    """{relative path under .github/ ('/'): text} for every template file."""
    out = {}
    for base, _dirs, files in os.walk(TEMPLATES):
        for name in sorted(files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, TEMPLATES)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if rel == TICKET_FORM:
                text = render_ticket_form(instances, text)
            out[rel.replace(os.sep, "/")] = text
    return out


def _instances(workspace_path=None):
    ws = ac.load_workspace(workspace_path)
    return list(ws["instances"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("ticket-form", "render", "check"))
    ap.add_argument("--workspace", help="workspace.json (default: the usual lookup)")
    ap.add_argument("--out", help="the board repository's root (render, check)")
    a = ap.parse_args(argv)
    try:
        instances = _instances(a.workspace)
    except ac.ConfigError as exc:
        sys.stderr.write("board_templates: %s\n" % exc)
        return 2
    if a.command == "ticket-form":
        sys.stdout.write(render_ticket_form(instances))
        return 0
    if not a.out:
        sys.stderr.write("board_templates: %s needs --out DIR\n" % a.command)
        return 2
    files = rendered_files(instances)
    drift = []
    for rel, text in sorted(files.items()):
        path = os.path.join(a.out, ".github", *rel.split("/"))
        if a.command == "render":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            print("wrote .github/%s" % rel)
        else:
            try:
                with open(path, encoding="utf-8") as fh:
                    same = fh.read() == text
            except OSError:
                same = False
            if not same:
                drift.append(rel)
                print("differs: .github/%s" % rel)
    if a.command == "check":
        print("%d of %d template files differ" % (len(drift), len(files)))
        return 1 if drift else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
