# Working on a Windows laptop

Facts that cost a run each time they were forgotten, on the Windows machines the academy
was built on. A home's `CLAUDE.md` names only what differs on its machine (for example
which Python version `py` is); everything below is the general rule.

## Python

- **`py` is the interpreter** (the Python launcher). Bare `python` (and `python3`) is
  usually the Microsoft Store stub, which opens the Store instead of running anything.
  The plugins' hooks and MCP server use `py` unless `ACADEMY_PYTHON` names another
  (`docs/config.md`); on Linux and macOS set it to `python3`.
- Assume the **standard library only** on the Windows side: `pytest` and the heavy
  libraries live in the lab's environment profiles (WSL, a remote worker), not here.
  Tests use `unittest` (`py tests/run_all.py`, `py -m unittest discover`).
- The console's code page is not UTF-8: set `PYTHONIOENCODING=utf-8` when a tool prints
  `′`, `∖` or other non-ASCII text and the console chokes on it.

## Writing files

- **Write source files with the editing tools** (Write, Edit), never with a shell
  heredoc or `echo`. PowerShell eats backticks and mangles apostrophes; bash heredocs
  (Git Bash) collapse backslashes, so LaTeX (`\\`, `\begin`) and Python string escapes
  arrive mangled.
- For a bulk edit, write a patch script to the scratchpad with the Write tool and run it
  with `py`; each replacement asserts exactly one match.
- **Line endings.** Git for Windows defaults to `core.autocrlf=true`. A home's
  `.gitattributes` (written by `/academy:init`) fixes LF for the files that must be LF;
  files that are CRLF on purpose (an Author home's tex, `*.ps1`) are read and written
  with `newline=""` so the existing `\r\n` passes through unchanged
  (`author/skills/paper-method/references/editing-tex.md`).

## Shells

- The hooks run in bash (Git Bash on Windows). Paths there are `/c/...`; native tools
  want `C:\...`. Prefer the scripts' own path arguments to hand-converted paths.
- **Calling a native command from PowerShell rewrites quotes**, so a bash command line
  built on the Windows side and passed to `wsl`/`bash -c` arrives altered. Use the
  wrappers that build it on the far side (`env.py run <profile> ...` for the lab).
- PowerShell 5.1 drops an empty-string element from an argument array passed to a native
  command; pass a placeholder or build the argument list in the callee.
- A script under Git Bash that looks for a conda env finds the Windows side, not WSL's:
  reach WSL environments through the lab's profiles (`/scientist:env`).
- Symlinks need Developer Mode (or an elevated shell); tests that create them skip or
  fail without it.
