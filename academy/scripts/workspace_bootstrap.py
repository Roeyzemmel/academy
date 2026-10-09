#!/usr/bin/env python3
"""Make a workspace checkout usable by the academy: run once after cloning, on any machine.

    python scripts/bootstrap.py [--workspace DIR] [--no-submodules] [--no-plugins] [--strict] [--adopt-siblings]

This is the academy plugin's ``academy/scripts/workspace_bootstrap.py``; a workspace keeps a
one-line shim at ``scripts/bootstrap.py`` that runs it with ``--workspace <its root>``. The
workspace root is ``--workspace``, else the nearest directory at or above the cwd holding
``workspace.template.json``, else ``$ACADEMY_WORKSPACE``, else the directory holding this
academy checkout when it has a ``workspace.template.json``.

0. if $ACADEMY_GIT_TOKEN (or GH_TOKEN / GITHUB_TOKEN) is set, makes git use it for github.com;
1. gets the submodules: in a cloud session (CLAUDE_CODE_REMOTE, or --adopt-siblings) moves
   the attached sibling checkout of each repo into its submodule path, leaving a symlink
   at the old place; otherwise clones each, or uses the sibling checkout of the same repo
   when the clone is refused;
2. writes ``workspace.json`` (git-ignored) from ``workspace.template.json`` with
   absolute paths for this checkout (the instances' homes and the board, a submodule or a
   plain directory of the workspace); every other top-level key of the template
   (``human``, ``grading``, ``compute``, ``plugins``, ...) is passed through unchanged;
3. exports where everything is, from workspace.json: ACADEMY_ROOT, ACADEMY_WORKSPACE,
   ACADEMY_BOARD, ACADEMY_LIBRARY and ACADEMY_HOME_<INSTANCE> (e.g. ACADEMY_HOME_AUTHOR_P),
   plus PYTHONUTF8, into ``.claude/settings.local.json`` (git-ignored) here and in every
   home, and into ``workspace.env`` for plain shells. The machine-wide places (user
   settings, /etc/environment, shell rc files, the Windows registry) get them tagged
   ``ACADEMY_WS__<TAG>__<NAME>``, TAG being this directory's name, so that several
   workspaces coexist; the academy picks one from the session's directory;
4. on a machine without the Windows ``py`` launcher, installs a ``py`` shim on
   PATH, because the academy's MCP server is started as ``py server.py``;
5. with the ``claude`` CLI, installs the plugins that are not already available
   (registering the local ``academy`` marketplace) and reports each one as available
   or MISSING (skipped with --no-plugins). The plugins are the template's ``plugins`` list
   if it has one, else ``academy``, the role plugins of the instances' roles and the
   domain packs of their ``domains`` (from the marketplace's ``./domains/<domain>``).

The permission rules rendered in step 3 are the academy's
``academy/templates/workspace/permissions.json`` merged with the workspace's own
``workspace.permissions.json`` (same keys; its rules are appended), if any.

Idempotent; every step reports what it did. Standard library only.
"""
import json
import os
import re
import shutil
import subprocess
import sys

#: the academy checkout (marketplace root) this script belongs to
ACADEMY_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: the workspace root; set by ``main`` (``find_workspace``), or by a caller/test directly
ROOT = None
ROLE_PLUGINS = ("researcher", "expert", "scientist", "author")
TEMPLATE = "workspace.template.json"
PERMISSIONS_TEMPLATE = ("academy", "templates", "workspace", "permissions.json")
PERMISSIONS_OVERRIDE = "workspace.permissions.json"


def find_workspace(explicit=None, cwd=None):
    """The workspace root (module docstring): a directory with workspace.template.json;
    None when there is none (an explicit one without the template is none too)."""
    def as_dir(p):
        if not p:
            return None
        p = os.path.abspath(os.path.expanduser(p))
        if os.path.isdir(p):
            return p
        # a workspace.json path (it may not be written yet)
        return os.path.dirname(p) if os.path.isfile(p) or p.endswith(".json") else None
    if explicit:
        d = as_dir(explicit)
        return d if d and os.path.isfile(os.path.join(d, TEMPLATE)) else None
    d = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, TEMPLATE)):
            return d
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    for cand in (as_dir(os.environ.get("ACADEMY_WORKSPACE")), os.path.dirname(ACADEMY_REPO)):
        if cand and os.path.isfile(os.path.join(cand, TEMPLATE)):
            return cand
    return None


def say(msg):
    print("bootstrap: " + msg)


def posix(path):
    return os.path.abspath(path).replace("\\", "/")


URLS = {}          # submodule path -> its url
RESOLVED = {}      # submodule path -> where it actually is (a sibling checkout, in a cloud session)


def where(path):
    return RESOLVED.get(path) or os.path.join(ROOT, path)


def checked_out(path):
    return os.path.exists(os.path.join(where(path), ".git"))


def academy_dir():
    """The academy checkout: the workspace's ``academy`` submodule when checked out, else
    the checkout this script runs from."""
    return where("academy") if checked_out("academy") else ACADEMY_REPO


def template():
    with open(os.path.join(ROOT, TEMPLATE), encoding="utf-8") as fh:
        return json.load(fh)


def board_rel(ws):
    """The board's path as a workspace map names it (a path or ``{"path": ...}``)."""
    b = ws.get("board")
    return b.get("path") if isinstance(b, dict) else b


def board_present():
    """Whether the template's board directory is there: a submodule checkout or a plain
    directory of the workspace (where packets and deep-dives live)."""
    try:
        rel = board_rel(template())
    except (OSError, ValueError):
        return False
    return bool(rel) and os.path.isdir(where(rel))


TOKEN_VARS = ("ACADEMY_GIT_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")


def git_credentials():
    """If the environment carries a GitHub token, make git use it for github.com.

    The helper reads the variable when git asks, so the token is not written to disk
    or into any URL. Give it a fine-grained token limited to the workspace's repos
    (Contents: read and write) and protect ``main`` in each of them."""
    var = next((v for v in TOKEN_VARS if os.environ.get(v)), None)
    if not var:
        say("no git token variable (%s); relying on whatever else authenticates github.com "
            "(e.g. an Authorization header the environment injects)" % ", ".join(TOKEN_VARS))
        return
    helper = '!f() { test "$1" = get && echo username=x-access-token && echo "password=$%s"; }; f' % var
    subprocess.run(["git", "config", "--global", "--replace-all", "credential.https://github.com.helper", helper],
                   check=False)
    say("git credentials for github.com come from $%s" % var)


def submodule_table():
    """[(path, repo name)] from .gitmodules."""
    rows = []
    for key in ("path", "url"):
        out = subprocess.run(["git", "config", "--file", ".gitmodules", "--get-regexp",
                              r"^submodule\..*\.%s$" % key], cwd=ROOT, capture_output=True, text=True).stdout
        rows.append([l.split(None, 1)[1] for l in out.splitlines()])
    URLS.update({p: u for p, u in zip(*rows)})
    return [(p, u.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")) for p, u in zip(*rows)]


def sibling(repo):
    """A checkout of ``repo`` next to (or under the parent of) this root: what a cloud
    session gives for every repo attached to it, since it has no git credentials for
    the submodule URLs."""
    parent = os.path.dirname(ROOT)
    for cand in (os.path.join(parent, repo), os.path.join(os.getcwd(), repo)):
        if cand != ROOT and os.path.exists(os.path.join(cand, ".git")):
            return cand
    for name in os.listdir(parent):
        cand = os.path.join(parent, name)
        if cand == ROOT or not os.path.exists(os.path.join(cand, ".git")):
            continue
        url = subprocess.run(["git", "-C", cand, "remote", "get-url", "origin"],
                             capture_output=True, text=True).stdout.strip()
        if url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git") == repo:
            return cand
    return None


def diagnose(repo_url):
    """One-shot probe of a failed clone, so the setup log says why: the HTTP status of
    the git endpoint (401 = no credential reached GitHub, 403/404 = the credential
    lacks access to that repo, 200 = fine) or the TLS/proxy error."""
    curl = shutil.which("curl")
    if not curl:
        return
    probe = repo_url.rstrip("/") + "/info/refs?service=git-upload-pack"
    res = subprocess.run([curl, "-sS", "-o", os.devnull, "-w", "HTTP %{http_code}", "--max-time", "20", probe],
                         capture_output=True, text=True)
    say("probe %s -> %s %s" % (probe, res.stdout.strip(), res.stderr.strip()[:200]))
    proxies = [v for v in ("HTTPS_PROXY", "https_proxy", "GIT_SSL_CAINFO", "SSL_CERT_FILE") if os.environ.get(v)]
    say("proxy/CA variables set: %s" % (", ".join(proxies) or "none"))


def adopt_sibling(path, near):
    """Move the attached checkout ``near`` to the submodule path ``path`` and leave a
    symlink at its old place, so the session's attached path still resolves and the
    workspace has one real tree where the submodule expects it. Returns True when
    ``path`` is then a checkout; on any refusal nothing is left half done and the caller
    falls back to using ``near`` in place."""
    dest = os.path.join(ROOT, path)
    if os.path.islink(near) or not os.path.isdir(near):
        return False
    try:
        if os.path.isdir(dest):
            os.rmdir(dest)              # only an empty, uninitialised submodule directory
        elif os.path.lexists(dest):
            return False
        shutil.move(near, dest)
    except OSError:
        if not os.path.exists(near) and os.path.isdir(dest):
            shutil.move(dest, near)     # undo
        return False
    try:
        os.symlink(dest, near, target_is_directory=True)
    except OSError:
        shutil.move(dest, near)         # no symlink, no move: keep the attached path valid
        os.makedirs(dest, exist_ok=True)
        return False
    return True


def submodules(adopt=False):
    """Get each submodule. With ``adopt`` (a cloud session: the attached repos sit next
    to this checkout and there are no git credentials for the submodule URLs), move the
    attached checkout of the same repo into the submodule path (``adopt_sibling``). Else,
    or if that is refused: clone it, else link the sibling checkout of the same repo,
    else report it. One failure never stops the others; git never prompts for
    credentials. Returns the paths that are still missing."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    failed = []
    for path, repo in submodule_table():
        if checked_out(path):
            continue
        if adopt:
            near = sibling(repo)
            if near and adopt_sibling(path, near):
                say("%s: moved the attached checkout %s here (a symlink stays at its old place)"
                    % (path, posix(near)))
                continue
        res = subprocess.run(["git", "submodule", "update", "--init", "--recursive", "--", path],
                             cwd=ROOT, env=env, capture_output=True, text=True)
        if res.returncode == 0 and checked_out(path):
            continue
        near = sibling(repo)
        if near:
            RESOLVED[path] = near
            say("%s: clone refused, using the attached checkout %s" % (path, posix(near)))
        else:
            failed.append(path)
            say("could not get %s (%s): %s" % (path, repo, (res.stderr or res.stdout).strip()[-400:]))
            if len(failed) == 1:
                diagnose(URLS.get(path, ""))
    return failed


def workspace():
    """Write workspace.json from the template: the homes and the board made absolute, every
    other top-level key passed through as the template has it."""
    ws = template()
    ws.pop("_about", None)
    kept = {}
    for name, inst in ws["instances"].items():
        home = where(inst["home"])
        if os.path.isdir(home):
            kept[name] = dict(inst, home=posix(home))
        else:
            say("skipping %s: %s not checked out" % (name, inst["home"]))
    ws["instances"] = kept
    # "board" is a path (the file board) or {"path", "backend": "github", "repo", "transport"}
    if isinstance(ws["board"], dict):
        ws["board"] = dict(ws["board"], path=posix(where(ws["board"]["path"])))
    else:
        ws["board"] = posix(where(ws["board"]))
    path = os.path.join(ROOT, "workspace.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(ws, fh, indent=2)
        fh.write("\n")
    say("wrote workspace.json with %d instance(s)" % len(kept))
    return path


def board_path(ws):
    """The board directory of a workspace map (packets and deep-dives stay files there)."""
    b = ws["board"]
    return b["path"] if isinstance(b, dict) else b


def board_check(ws_path, which=shutil.which, run=subprocess.run):
    """On a GitHub board (board.backend github), report whether ``gh`` is installed and can
    read the board's repository: every ticket read and write goes through ``gh api``. Only
    warns (a cloud setup never fails), and says nothing on a file board. Returns True when
    the board is usable or files, False when a warning was printed."""
    with open(ws_path, encoding="utf-8") as fh:
        b = json.load(fh).get("board")
    if not isinstance(b, dict) or b.get("backend", "files") != "github":
        return True
    repo = b.get("repo") or "?"
    if not which("gh"):
        say("WARNING: the board is on GitHub (%s) but gh is not installed: the board tools, "
            "inbox and SessionStart line cannot read tickets. Install the GitHub CLI and run "
            "`gh auth login` (in a cloud environment: add gh to the image)" % repo)
        return False
    try:
        res = run(["gh", "api", "repos/%s" % repo, "--jq", ".full_name"], capture_output=True,
                  text=True, timeout=30)
        ok, err = res.returncode == 0, (res.stderr or res.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        ok, err = False, str(exc)
    if ok:
        say("board: on GitHub (%s); gh can read it" % repo)
        return True
    say("WARNING: the board is on GitHub (%s) but gh cannot read it: %s. Run `gh auth "
        "login` (in a cloud session: give the environment access to %s)"
        % (repo, (err.splitlines() or ["no output"])[0][:200], repo))
    return False


def env_name(instance):
    """``author@p`` -> ``ACADEMY_HOME_AUTHOR_P``."""
    return "ACADEMY_HOME_" + re.sub(r"[^A-Za-z0-9]+", "_", instance).strip("_").upper()


def home_env(ws_path):
    """The variables that tell every session where everything is, derived from
    workspace.json (the single source): ACADEMY_ROOT, ACADEMY_WORKSPACE, ACADEMY_BOARD and
    one ACADEMY_HOME_<INSTANCE> per instance; ACADEMY_LIBRARY is the Expert's home.
    ACADEMY_ENV_WORKSPACE names the file they were derived from: the academy applies them
    to that file only, so a test's throw-away workspace is left alone."""
    with open(ws_path, encoding="utf-8") as fh:
        ws = json.load(fh)
    env = {"ACADEMY_ROOT": posix(academy_dir()), "ACADEMY_WORKSPACE": posix(ws_path),
           "ACADEMY_ENV_WORKSPACE": posix(ws_path),
           "ACADEMY_BOARD": board_path(ws), "PYTHONUTF8": "1"}
    for name, inst in ws["instances"].items():
        env[env_name(name)] = inst["home"]
        if inst["role"] == "expert":
            env.setdefault("ACADEMY_LIBRARY", inst["home"])
    return env, ws


def tag():
    """This workspace's tag: its directory name, upper-cased with runs of other
    characters as ``_`` (no ``__``, the separator). It scopes the machine-wide
    variables, so several workspaces can coexist on one machine."""
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(ROOT))).strip("_").upper() or "WS"


def tagged(env):
    """The machine-wide form of ``env``: ``ACADEMY_<NAME>`` becomes
    ``ACADEMY_WS__<TAG>__<NAME>``; the academy picks one workspace's set from these
    (``resolve_workspace_env``). ``PYTHONUTF8`` is workspace-independent and stays."""
    t = tag()
    return {("ACADEMY_WS__%s__%s" % (t, k[len("ACADEMY_"):]) if k.startswith("ACADEMY_") else k): v
            for k, v in env.items()}


def is_legacy(key):
    """An unprefixed ``ACADEMY_*`` variable in a machine-wide place: what an earlier
    bootstrap wrote there, and what would make two workspaces overwrite each other."""
    return key.startswith("ACADEMY_") and not key.startswith("ACADEMY_WS__")


def slash2(path):
    """``C:/Work/x`` -> ``//c/Work/x``, the absolute form of a Read/Edit permission path."""
    m = re.match(r"^([A-Za-z]):[\/](.*)$", path)
    return "//%s/%s" % (m.group(1).lower(), m.group(2)) if m else path


def permission_table():
    """The permission templates: the academy's ``templates/workspace/permissions.json``
    (or, from an academy checkout that predates it, the workspace's old
    ``scripts/permissions.json``), with the workspace's ``workspace.permissions.json``
    merged in: per key, its rules are appended after the academy's (duplicates once)."""
    table = {}
    for path in (os.path.join(academy_dir(), *PERMISSIONS_TEMPLATE),
                 os.path.join(ROOT, "scripts", "permissions.json")):
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                table = json.load(fh)
            break
    override = os.path.join(ROOT, PERMISSIONS_OVERRIDE)
    if os.path.isfile(override):
        with open(override, encoding="utf-8") as fh:
            extra = json.load(fh)
        for key, rules in extra.items():
            if key.startswith("_") or not isinstance(rules, list):
                continue
            have = table.setdefault(key, [])
            have.extend(r for r in rules if r not in have)
    return table


def permission_rules(role, env, ws):
    """The machine-path permission rules for a home of ``role``, rendered from
    scripts/permissions.json (Claude Code cannot expand variables in settings.json rules)."""
    table = permission_table()
    homes = {inst["role"]: inst["home"] for inst in ws["instances"].values()}
    values = {"ROOT": env["ACADEMY_ROOT"], "WORKSPACE": posix(ROOT), "BOARD": env["ACADEMY_BOARD"],
              "LIBRARY": env.get("ACADEMY_LIBRARY", ""), "SCIENTIST": homes.get("scientist", ""),
              "AUTHOR": homes.get("author", ""), "USER": posix(os.path.expanduser("~"))}
    all_homes = sorted({inst["home"] for inst in ws["instances"].values()})
    templates = []
    # the workspace root gets only its own key (the ship.py verbs), not the homes' common rules
    base = [] if role == "workspace" else table.get("common", [])
    for tpl in base + table.get(role, []):
        if "{EACH_HOME}" in tpl:                    # one rule per home of the workspace
            templates += [tpl.replace("{EACH_HOME}", h) for h in all_homes]
        else:
            templates.append(tpl)
    rules = []
    for tpl in templates:
        ps_only = tpl.startswith("PS:")
        tpl = tpl[3:] if ps_only else tpl
        for key, val in values.items():
            tpl = tpl.replace("{%s}" % key, val)
        if tpl.startswith(("Read(", "Edit(")):
            tool, path = tpl.split("(", 1)
            rules.append("%s(%s" % (tool, slash2(path)))
            continue
        if not ps_only:
            rules.append(tpl)
        if ps_only or (tpl.startswith("Bash(py ") and "=" not in tpl):
            inner = tpl[len("Bash("):-1] if tpl.startswith("Bash(") else tpl[len("PowerShell("):-1]
            rules.append("PowerShell(%s)" % inner.replace("/", "\\"))
            # a relative script path is typed with forward slashes in PowerShell too
            # ("py scripts/ship.py ..."), so it also gets a forward-slash twin
            script = inner.split()[1] if len(inner.split()) > 1 else ""
            if not ps_only and "/" in script and not re.match(r"^(/|[A-Za-z]:)", script):
                rules.append("PowerShell(%s)" % inner)
    if role == "expert" and homes.get("expert"):    # the librarian keeps the bibliographies its config names
        try:
            with open(os.path.join(homes["expert"], ".claude", "academy.json"), encoding="utf-8") as fh:
                bibs = (json.load(fh).get("expert") or {}).get("bibs") or []
        except (OSError, ValueError):
            bibs = []
        for bib in bibs:
            inst, _, rel = bib.partition(":")
            home = (ws["instances"].get(inst) or {}).get("home")
            if home and rel:
                rules.append("Edit(%s)" % slash2(posix(os.path.join(home, rel))))
    return list(dict.fromkeys(rules))


def write_root_settings(env, ws):
    """The workspace root's own settings.local.json: the environment plus the common rules
    (so a CLI session at the root may run the safe ship.py verbs without a prompt)."""
    write_settings(ROOT, env, permission_rules("workspace", env, ws), retire=RETIRED_ROOT_RULES)


# Rules an earlier bootstrap wrote into the root's settings.local.json that must now prompt
# (rules are otherwise append-only): accept-baseline rewrites what the gate accepts.
RETIRED_ROOT_RULES = (re.compile(r"^(Bash|PowerShell)\(py \S*ship\.py accept-baseline"),)


def write_settings(directory, env, allow=(), retire=()):
    path = os.path.join(directory, ".claude", "settings.local.json")
    cur = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            cur = json.load(fh)
    cur.setdefault("env", {}).update(env)
    if retire and isinstance(cur.get("permissions"), dict) and isinstance(cur["permissions"].get("allow"), list):
        cur["permissions"]["allow"] = [r for r in cur["permissions"]["allow"]
                                       if not (isinstance(r, str) and any(p.match(r) for p in retire))]
    if allow:
        have = cur.setdefault("permissions", {}).setdefault("allow", [])
        have.extend(r for r in allow if r not in have)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cur, fh, indent=2)
        fh.write("\n")


def write_user_env(env):
    """Merge the variables, tagged, into the user-level ~/.claude/settings.json ``env``
    (dropping the unprefixed ones an earlier bootstrap left). The
    per-directory settings.local.json only applies to a session opened inside that
    directory, but a cloud session may be opened elsewhere (the repos attached beside
    it) and a plugin's MCP server then starts without ACADEMY_WORKSPACE. Nothing else
    in the file is touched."""
    path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    cur = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                cur = json.load(fh)
        except ValueError:
            say("%s is not valid JSON; user-level environment NOT written" % path)
            return
    if not isinstance(cur, dict):
        return
    have = cur.setdefault("env", {})
    for k in [k for k in have if is_legacy(k)]:
        del have[k]
    have.update(tagged(env))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cur, fh, indent=2)
        fh.write("\n")
    say("set the workspace %s variables in %s (sessions opened outside the workspace)" % (tag(), path))


def exclude_locally(home, pattern):
    """Keep a per-machine file out of a home's status without touching its tracked
    .gitignore: append to the repo's own info/exclude (the home is a separate repo)."""
    res = subprocess.run(["git", "-C", home, "rev-parse", "--git-path", "info/exclude"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        return
    path = os.path.join(home, res.stdout.strip())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    have = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
    if pattern not in have.splitlines():
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(("" if have.endswith("\n") or not have else "\n") + pattern + "\n")


def rule_paths(rule):
    """The absolute paths a permission rule depends on: the script after ``py``, and the
    target of a Read rule (Edit targets may be created on demand)."""
    r = rule.replace("\\\\", "\\").replace("\\", "/")
    out = []
    m = re.match(r"^Read\((.*?)(?:/\*\*)?\)$", r)
    if m:
        out.append(re.sub(r"^//([a-z])/", lambda k: k.group(1).upper() + ":/", m.group(1)))
    out += re.findall(r"py ((?:[A-Za-z]:)?/[^\s:*)]+\.py)", r)
    return out


def check_permissions(role_of, env, ws):
    """Report, per home, whether every rendered rule is in its effective settings (tracked
    settings.json + local) and whether the paths the rules name exist, so a moved workspace
    or a stale template cannot silently shrink what a session may do."""
    def allow(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh).get("permissions", {}).get("allow", [])
        except (OSError, ValueError):
            return []
    for home, role in sorted(role_of.items()):
        if not os.path.isdir(home):
            continue
        have = allow(os.path.join(home, ".claude", "settings.json")) + \
            allow(os.path.join(home, ".claude", "settings.local.json"))
        rendered = permission_rules(role, env, ws)
        missing = [r for r in rendered if r not in have]
        dead = sorted({p for r in have for p in rule_paths(r) if not os.path.exists(p)})
        say("permissions %-30s %2d rules in effect, %d rendered rule(s) missing, %d rule path(s) not found%s"
            % (os.path.basename(home), len(have), len(missing), len(dead),
               "" if not (missing or dead) else "  <-- " + "; ".join(missing[:2] + dead[:2])))


def strip_block(text, start, end):
    """``text`` without the block from the line ``start`` to the line ``end``."""
    out, skip = [], False
    for ln in text.splitlines(True):
        if ln.strip() == start:
            skip = True
        if not skip:
            out.append(ln)
        if skip and ln.strip() == end:
            skip = False
    return "".join(out)


def persist_env(env):
    """Make this workspace's variables visible to every process, not only Claude's tools
    (the academy MCP server reads them), in the tagged form so that several workspaces
    coexist (see ``tagged``). Unprefixed variables an earlier bootstrap left in these
    machine-wide places are removed. Idempotent."""
    if os.name == "nt":
        import winreg  # per-user and persistent; only processes started afterwards see it
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
            i = 0
            stale = []
            while True:
                try:
                    stale.append(winreg.EnumValue(key, i)[0])
                    i += 1
                except OSError:
                    break
            for k in (k for k in stale if is_legacy(k)):
                winreg.DeleteValue(key, k)
            for k, v in tagged(env).items():
                winreg.SetValueEx(key, k, 0, winreg.REG_SZ, v)
        say("set %d user environment variable(s) for workspace %s in HKCU\\Environment; "
            "restart Claude Code and the terminal" % (len(env), tag()))
        return
    glob = os.path.join(ROOT, "workspace.global.env")     # what the shell rc files source
    with open(glob, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join('%s="%s"\n' % kv for kv in sorted(tagged(env).items())))
    start, end = "# >>> academy workspace %s >>>" % tag(), "# <<< academy workspace %s <<<" % tag()
    block = '%s\nset -a; . "%s"; set +a\n%s\n' % (start, glob, end)
    for rc in (".bashrc", ".profile", ".zshenv"):
        path = os.path.join(os.path.expanduser("~"), rc)
        text = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        # the unprefixed, workspace-independent block of an earlier bootstrap
        new_text = strip_block(text, "# >>> academy workspace >>>", "# <<< academy workspace <<<")
        if start not in new_text:
            new_text += ("\n" if new_text and not new_text.endswith("\n") else "") + block
        if new_text != text:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_text)
    root = os.geteuid() == 0
    if root:  # launchers that read no shell rc file (the cloud container runs as root)
        mine = tagged(env)
        lines = []
        if os.path.exists("/etc/environment"):
            with open("/etc/environment", encoding="utf-8") as fh:
                lines = [l for l in fh.read().splitlines()
                         if l.split("=")[0] not in mine and not is_legacy(l.split("=")[0])]
        with open("/etc/environment", "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines + ['%s="%s"' % kv for kv in sorted(mine.items())]) + "\n")
    say("persisted the %s variables, tagged (shell rc files%s)"
        % (tag(), ", /etc/environment" if root else ""))


def settings_local(ws_path):
    """Set the environment in this repo's and in every home's git-ignored
    .claude/settings.local.json (so a session started in any home sees the others), and
    write workspace.env for plain shells (``set -a; . ./workspace.env``)."""
    env, ws = home_env(ws_path)
    write_root_settings(env, ws)
    homes = sorted({inst["home"] for inst in ws["instances"].values()})
    role_of = {inst["home"]: inst["role"] for inst in ws["instances"].values()}
    for home in homes:
        if os.path.isdir(home):
            write_settings(home, env, permission_rules(role_of[home], env, ws))
            exclude_locally(home, ".claude/settings.local.json")
    check_permissions(role_of, env, ws)
    with open(os.path.join(ROOT, "workspace.env"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join('%s="%s"\n' % kv for kv in sorted(env.items())))
    persist_env(env)
    write_user_env(env)
    say("set %s in .claude/settings.local.json here and in %d home(s); wrote workspace.env"
        % (", ".join(k for k in sorted(env) if k != "PYTHONUTF8"), len(homes)))


def py_shim():
    if shutil.which("py"):
        return
    target = shutil.which("python3") or shutil.which("python")
    if not target:
        say("WARNING: no python found; the academy MCP server cannot start")
        return
    bindir = os.path.join(os.path.expanduser("~"), ".local", "bin")
    os.makedirs(bindir, exist_ok=True)
    link = os.path.join(bindir, "py")
    if not os.path.lexists(link):
        os.symlink(target, link)
    if bindir not in os.environ.get("PATH", "").split(os.pathsep):
        say("WARNING: %s is not on PATH; add it before starting Claude Code" % bindir)
    say("py shim: %s -> %s" % (link, target))


def run_claude(claude, *args):
    """Run one claude CLI call; report a failure instead of swallowing it."""
    res = subprocess.run([claude, *args], cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        say("claude %s failed (exit %d): %s" % (" ".join(args[:3]), res.returncode,
                                                (res.stderr or res.stdout).strip()[:300]))
    return res.returncode, res.stdout


def domain_plugin(domain, academy=None):
    """The plugin name of the domain pack ``domain``: the marketplace entry whose source is
    ``./domains/<domain>``, else that pack's own .claude-plugin/plugin.json; None if neither."""
    academy = academy or academy_dir()
    try:
        with open(os.path.join(academy, ".claude-plugin", "marketplace.json"), encoding="utf-8") as fh:
            entries = json.load(fh).get("plugins") or []
    except (OSError, ValueError):
        entries = []
    want = "domains/%s" % domain
    for e in entries:
        if isinstance(e, dict) and str(e.get("source", "")).replace("\\", "/").strip("./").rstrip("/") == want:
            return e.get("name")
    try:
        with open(os.path.join(academy, "domains", domain, ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as fh:
            return json.load(fh).get("name")
    except (OSError, ValueError):
        return None


def plugin_names(ws, academy=None):
    """The plugins this workspace needs: its ``plugins`` list if it has one, else
    ``academy``, the role plugins of its instances' roles (in a fixed order) and the domain
    pack of every domain an instance names (a domain with no pack is reported)."""
    if isinstance(ws.get("plugins"), list) and ws["plugins"]:
        return [str(p) for p in ws["plugins"]]
    insts = list((ws.get("instances") or {}).values())
    roles = {i.get("role") for i in insts}
    names = ["academy"] + [r for r in ROLE_PLUGINS if r in roles]
    for inst in insts:
        for d in inst.get("domains") or []:
            name = domain_plugin(d, academy)
            if not name:
                say("no domain pack for %r in the academy marketplace" % d)
            elif name not in names:
                names.append(name)
    return names


def available(claude, names):
    """Of ``names``, the plugins Claude Code already has, from any source
    (a marketplace install, or a ~/.claude/skills symlink on a developer machine)."""
    _, out = run_claude(claude, "plugin", "list")
    return {n for n in names if re.search(r"(?m)^\s*\S*\s*%s@" % re.escape(n), out)}


def plugins():
    claude = shutil.which("claude")
    if not claude:
        say("claude CLI not on PATH; enable the plugins from .claude/settings.json instead")
        return
    try:
        names = plugin_names(template())
    except (OSError, ValueError) as exc:
        say("cannot read %s (%s); plugins not checked" % (TEMPLATE, exc))
        return
    have = available(claude, names)
    missing = [n for n in names if n not in have]
    if have:
        say("already available: %s" % ", ".join(sorted(have)))
    if missing:
        run_claude(claude, "plugin", "marketplace", "add", posix(academy_dir()))
        for name in missing:
            run_claude(claude, "plugin", "install", name + "@academy", "--scope", "project")
        have = available(claude, names)
    for name in names:
        say("plugin %-11s %s" % (name, "available" if name in have else "MISSING"))


def main(argv):
    """Exit 0 unless --strict, even with submodules missing: a cloud setup script that
    fails hides its output. The summary at the end says what is missing."""
    global ROOT
    argv = list(argv)
    explicit = None
    if "--workspace" in argv:
        i = argv.index("--workspace")
        explicit = argv[i + 1] if i + 1 < len(argv) else ""
        del argv[i:i + 2]
    if explicit is not None or ROOT is None:
        ROOT = find_workspace(explicit)
    if not ROOT:
        say("no workspace found (a directory with %s): run from inside one or pass "
            "--workspace DIR" % TEMPLATE)
        return 1
    git_credentials()
    adopt = "--adopt-siblings" in argv or os.environ.get("CLAUDE_CODE_REMOTE") == "true"
    failed = [] if "--no-submodules" in argv else submodules(adopt)
    if os.path.isdir(os.path.join(academy_dir(), "academy")) and board_present():
        ws_path = workspace()
        settings_local(ws_path)
        board_check(ws_path)
        if os.name != "nt":
            py_shim()
        if "--no-plugins" not in argv:
            plugins()
    else:
        say("the academy checkout or the board directory is missing, so workspace.json was NOT written")
    if failed:
        say("MISSING submodules: %s" % ", ".join(failed))
        say("Grant this environment / session read access to those repos, then rerun "
            "`python scripts/bootstrap.py` and restart Claude Code (plugins load at start).")
        return 1 if "--strict" in argv else 0
    say("done. Start Claude Code in a home or here.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
