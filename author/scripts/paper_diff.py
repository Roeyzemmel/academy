"""paper_diff -- a coloured-diff PDF of the whole paper against the last shared version.

    paper_diff.py --root HOME [--base REF] [--out FILE] [--no-build] [--json]

The base version is a git ref, taken in this order:

  1. ``--base REF``;
  2. ``author.diff.base`` in the home's ``.claude/academy.json``;
  3. the most recent tag (by tag date) matching ``author.diff.tags`` (default
     ``shared-*``, ``round-*``, ``submitted-*``);
  4. nothing: exit 1 with a one-line message.

The base tree is exported with ``git archive`` into a temporary directory; the home's
working tree, index and refs are never touched. ``latexdiff --flatten`` expands the
``\\input`` / ``\\include`` files of both versions, so the whole paper is compared. The
diff ``.tex`` is written to ``<build.dir>/diff/<stem>-diff.tex`` (the build directory is
gitignored in an Author home) and built there by ``latexmk`` with the home as the working
directory, so figures and the bibliography resolve as in the normal build. The build
directory is a sub-directory of the normal one, so it does not collide with the build
lock's builds.

``author.diff.args`` (a list) replaces the default latexdiff options. The defaults are the
ones that built on a real 130-page paper (2026-11-13): ``--math-markup=off`` (a changed
formula shows its new version, unmarked: latexdiff's formula markup wraps a display in
``\\DIFdel{...}``, inside which a ``tikzcd`` or an alignment with ``&`` does not compile)
and diagrams (``tikzcd``, ``tikzpicture``) treated as pictures, replaced whole. Prose,
statements and proofs are marked as usual. A home whose formulas are plain can set
``["--math-markup=whole", "--allow-spaces"]``.

Exit codes: 0 the diff (and, unless ``--no-build``, the PDF) was written; 1 no base was
found, or latexdiff / the build failed (the log tail and the diff ``.tex`` path are
printed; the caller reports "diff not built"); 2 an error (no git repository, a tool
missing, bad arguments). Stdlib only.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _author as au  # noqa: E402

DEFAULT_TAGS = ("shared-*", "round-*", "submitted-*")
#: latexdiff options when ``author.diff.args`` is absent (the module docstring says why
#: formula markup is off); allow-spaces: ``\\input {x}``.
DEFAULT_LATEXDIFF_ARGS = (
    "--math-markup=off", "--allow-spaces",
    # a commutative diagram or a TikZ picture is replaced whole, never marked up cell by
    # cell (on a real paper the cell markup of one changed tikzcd broke the build)
    r"--config=PICTUREENV=(?:picture|tikzpicture|tikzcd|DIFnomarkup)[\w\d*@]*",
)
LATEXDIFF_TIMEOUT = 600
BUILD_TIMEOUT = 900
LOG_TAIL = 40


class DiffError(Exception):
    """Raised with the exit code and the message to print."""

    def __init__(self, message, code=2):
        Exception.__init__(self, message)
        self.code = code


# ----------------------------------------------------------------------------
# git
# ----------------------------------------------------------------------------

def git(home, *args, **kw):
    """(returncode, stdout text) of ``git -C home ...``; never raises on a git failure."""
    try:
        proc = subprocess.run(["git", "-C", home] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, **kw)
    except OSError as exc:
        raise DiffError("git could not run: %s" % exc)
    return proc.returncode, proc.stdout.decode("utf-8", "replace").strip()


def rev_parse(home, ref):
    """The commit sha of ``ref``, or None."""
    if not ref or ref.startswith("-"):
        return None
    code, out = git(home, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return out if code == 0 and out else None


def newest_tag(home, patterns):
    """The most recent tag (by tag date, else commit date) matching a pattern, or None."""
    if not patterns:
        return None
    args = ["for-each-ref", "--sort=-creatordate", "--count=1", "--format=%(refname:short)"]
    args += ["refs/tags/%s" % p for p in patterns]
    code, out = git(home, *args)
    return out.splitlines()[0] if code == 0 and out else None


def resolve_base(home, cli_base, settings):
    """``(ref, sha, how)``; raises DiffError(code 1) when no base can be found."""
    diff = settings.get("diff") if isinstance(settings.get("diff"), dict) else {}
    if cli_base:
        ref, how = cli_base, "--base"
    elif diff.get("base"):
        ref, how = str(diff["base"]), "author.diff.base"
    else:
        patterns = diff.get("tags") or list(DEFAULT_TAGS)
        ref, how = newest_tag(home, [str(p) for p in patterns]), "newest tag"
        if not ref:
            raise DiffError("no diff base: no tag matching %s; give one with --base REF "
                            "or set author.diff.base" % ", ".join(patterns), 1)
    sha = rev_parse(home, ref)
    if not sha:
        raise DiffError("diff base %r (%s) is not a commit of this repository" % (ref, how), 1)
    return ref, sha, how


def export_tree(home, sha, dest):
    """Extract the home's directory at commit ``sha`` into ``dest`` (empty, existing).

    ``git archive`` reads the object database only: the working tree, the index and the
    refs are untouched. When the home is a sub-directory of its repository, only that
    sub-tree is exported.
    """
    code, prefix = git(home, "rev-parse", "--show-prefix")
    if code != 0:
        raise DiffError("%s is not inside a git repository" % home)
    tree = "%s:%s" % (sha, prefix.rstrip("/")) if prefix else sha
    try:
        proc = subprocess.run(["git", "-C", home, "archive", "--format=tar", tree],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise DiffError("git could not run: %s" % exc)
    if proc.returncode != 0:
        raise DiffError("git archive failed: %s" % proc.stderr.decode("utf-8", "replace").strip(), 1)
    tmp = os.path.join(dest, ".base.tar")
    with open(tmp, "wb") as fh:
        fh.write(proc.stdout)
    root = os.path.realpath(dest)
    with tarfile.open(tmp) as tf:
        # a link in the paper is not followed into the diff
        members = [m for m in tf.getmembers() if not (m.issym() or m.islnk())]
        for m in members:
            target = os.path.realpath(os.path.join(dest, m.name))
            if target != root and not target.startswith(root + os.sep):
                raise DiffError("unsafe path in the base archive: %s" % m.name)
        try:
            tf.extractall(dest, members=members, filter="data")
        except TypeError:  # Python without extraction filters
            tf.extractall(dest, members=members)
    os.remove(tmp)


# ----------------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------------

def latexdiff_args(settings):
    diff = settings.get("diff") if isinstance(settings.get("diff"), dict) else {}
    args = diff.get("args")
    if isinstance(args, list):
        return [str(a) for a in args]
    return list(DEFAULT_LATEXDIFF_ARGS)


def latexdiff_cmd(old_main, new_main, args):
    return ["latexdiff", "--flatten"] + list(args) + [old_main, new_main]


def latexmk_cmd(tex_rel, outdir_rel):
    return ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
            "-outdir=%s" % outdir_rel, tex_rel]


def tail(text, n=LOG_TAIL):
    return "\n".join(text.splitlines()[-n:])


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


# ----------------------------------------------------------------------------
# the run
# ----------------------------------------------------------------------------

def run(args):
    root = os.path.abspath(args.root)
    home, config = au.author_home(root)
    if not home:
        home, config = root, {}
    home = os.path.abspath(home)
    settings = au.author_settings(config)
    main = settings.get("main") or "main.tex"
    stem = os.path.splitext(os.path.basename(main))[0]
    if not os.path.isfile(os.path.join(home, main)):
        raise DiffError("%s not found in %s" % (main, home))
    if shutil.which("git") is None:
        raise DiffError("git is not on PATH")
    if shutil.which("latexdiff") is None:
        raise DiffError("latexdiff is not on PATH")
    code, _ = git(home, "rev-parse", "--git-dir")
    if code != 0:
        raise DiffError("%s is not inside a git repository" % home)

    ref, sha, how = resolve_base(home, args.base, settings)
    build_dir = (settings.get("build") or {}).get("dir") or ".build"
    outdir = os.path.join(home, *build_dir.split("/"), "diff")
    os.makedirs(outdir, exist_ok=True)
    diff_tex = os.path.join(outdir, stem + "-diff.tex")
    result = {"base": ref, "base_sha": sha, "base_from": how, "diff_tex": diff_tex,
              "pdf": None, "built": False}

    with tempfile.TemporaryDirectory(prefix="paper-diff-") as tmpdir:
        export_tree(home, sha, tmpdir)
        old_main = os.path.join(tmpdir, main)
        if not os.path.isfile(old_main):
            raise DiffError("%s does not exist at %s (%s)" % (main, ref, sha[:10]), 1)
        cmd = latexdiff_cmd(old_main, os.path.join(home, main), latexdiff_args(settings))
        try:
            proc = subprocess.run(cmd, cwd=home, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=LATEXDIFF_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DiffError("diff not built: latexdiff failed: %s" % exc, 1)
    # the temporary base tree is gone; latexdiff has already inlined it
    if proc.returncode != 0 or not proc.stdout.strip():
        raise DiffError("diff not built: latexdiff exited %d\n%s"
                        % (proc.returncode, tail(proc.stderr.decode("utf-8", "replace"))), 1)
    with open(diff_tex, "wb") as fh:
        fh.write(proc.stdout)
    if args.no_build:
        return result

    rel_tex = os.path.relpath(diff_tex, home)
    rel_out = os.path.relpath(outdir, home)
    env = dict(os.environ)
    env["TEXINPUTS"] = home + os.pathsep + env.get("TEXINPUTS", "")
    env["BIBINPUTS"] = home + os.pathsep + env.get("BIBINPUTS", "")
    try:
        mk = subprocess.run(latexmk_cmd(rel_tex, rel_out), cwd=home, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=BUILD_TIMEOUT)
        built_rc, built_out = mk.returncode, mk.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        built_rc, built_out = 1, "latexmk could not finish: %s" % exc
    pdf = os.path.join(outdir, stem + "-diff.pdf")
    if built_rc != 0 or not os.path.isfile(pdf):
        log = read_text(os.path.join(outdir, stem + "-diff.log"))
        raise DiffError("diff not built: latexmk exited %d; diff .tex: %s\n%s"
                        % (built_rc, diff_tex, tail(log or built_out)), 1)
    if args.out:
        final = os.path.abspath(args.out)
        if final != os.path.abspath(pdf):
            os.makedirs(os.path.dirname(final), exist_ok=True)
            shutil.copyfile(pdf, final)
            pdf = final
    result["pdf"], result["built"] = pdf, True
    return result


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        description="Coloured-diff PDF of the whole paper against the last shared version.")
    ap.add_argument("--root", default=".", help="the Author home (default: the cwd)")
    ap.add_argument("--base", default=None,
                    help="git ref of the base version (default: author.diff.base, else "
                         "the newest shared-* / round-* / submitted-* tag)")
    ap.add_argument("--out", default=None,
                    help="where to put the PDF (default: <build.dir>/diff/<main>-diff.pdf)")
    ap.add_argument("--no-build", action="store_true", help="stop after writing the diff .tex")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)
    try:
        result = run(args)
    except DiffError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["built"]:
        print(result["pdf"])
    else:
        print(result["diff_tex"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
