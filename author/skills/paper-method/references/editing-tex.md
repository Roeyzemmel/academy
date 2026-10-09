# Editing the tex without costing a build

Mechanics that hold in every Author home. The conventions a home may change are keys of
the `author` block of `.claude/academy.json` (`docs/config.md`; defaults in brackets
below): the files (`crlf`, `main`, `build`, `checker`), the draft levels
(`statusLevels`, `draft-colours.md`), `preamble`, `labels`, `notes`, `figures`, `bib`
and `mainResults`. The home's `.claude/rules/` add only its macro list and its note-macro
names.

## The preamble (`author.preamble`)

The preamble is the root file (`file` [`author.main`]) up to `end`
[`\begin{document}`], plus any `extraFiles` (a `macros.tex`). `policy`:

- `propose` [default]: write against the preamble as it stands; a needed change is filed
  as a proposal for the human (a ticket or packet with the exact lines and the reason);
- `locked`: the preamble is the human's alone; report what is missing;
- `free`: the writers may edit it.

`preamble_guard` refuses a tool edit of the region under `propose` and `locked`, for
every caller; the human releases a file by hand in `.claude/preamble-release.txt`.

## Line endings

- The files listed in `author.crlf` (typically `main.tex`, the section files and the
  standalone figures) are **CRLF**; everything under `Drafts/` and the records are LF.
- Edit them with the Edit tool, or with a Python patch script created with the Write
  tool and run with the home's Python. In the script, read with
  `io.open(p, encoding="utf-8", newline="")` and write with `newline=""` too: the text
  already carries `\r\n`, and writing it with `newline="\r\n"` doubles every CR. Each
  replacement asserts exactly one match.
- **Never a shell heredoc** for tex or for a script that contains tex: shells collapse or
  eat backslashes and backticks, so a LaTeX line break or a Python `"\begin"` arrives
  mangled (`academy/references/windows.md` for the Windows shells).

## The build

- The build command, its output directory and its lock are `author.build`. Artifacts
  stay in the build directory, never committed. With `-file-line-error` (commonly set
  in `.latexmkrc`) **errors appear as `file.tex:NN:` lines, not only as `!`**: grep for
  both. A stale latexmk exit code 12 clears with `latexmk -pdf -g`.
- **Clean** means: exit 0, no `file.tex:NN:` line, no `undefined`, no `multiply` in the
  log, and no `??` in the PDF text (`pdftotext <build>/<main>.pdf - | grep -c '??'` is 0).
  BibTeX `Warning--` lines are clean only when they name an entry in
  `author.bib.acceptedWarnings` [none]; any other is new and yours. The checker's BUILD
  line counts the accepted ones apart.
- The mechanical gate is `check_paper.py [--strict]`; its known open findings are the
  file named by `gate.baseline`, and a finding outside it is a regression. It
  regenerates `Drafts/statements.md`, which is **generated**: never hand-edit it, rerun
  the script. Its "blocking" section follows the `thm:` statements of
  `author.mainResults.file` [`sections/introduction.tex`] and the `labels` listed there.

## Theorem environments and references

- Use the environment names in `author.theorems` and nothing else; a long name the
  preamble does not define (`\begin{theorem}` where only `thm` exists) breaks the build.
- References use `\<author.labels.refCommand>{}` [`\cref{}` / `\Cref{}`], never a bare
  `\ref`. Labels carry the typed prefixes of `author.labels.prefixes` [`thm: lem: prop:
  cor: defn: eq: sec: fig:`], so a reference's type never drifts from its target
  (checker R6 catches an undefined one).

## Margin notes

- Never an ad-hoc `\todo`. Human notes use the macros in `author.noteMacros.human` and
  `coauthors`; machine notes use only `author.noteMacros.machine`. **Never sign a note as
  a human coauthor.**
- Keep a machine note to `author.notes.maxLines` [3] lines and break long `\texttt` keys
  (`\texttt{a-}\allowbreak\texttt{b}`): the margin clips what it cannot hold (checker R7).
  The long text belongs in the ticket thread.
- An unclosed brace in a margin note is the most common build break, usually an
  environment or a `%` inside the note.
- Every sketched, unverified or judgement-call step gets a machine note in the file and
  is named in the chat message.

## Figures

Standalone files in `author.figures.dir` [`tikz`], included with
`author.figures.include` [`\includestandalone`], each in a `figure` with a `\caption`
and a `fig:` label. Check the preamble before assuming a TikZ library is loaded. The
drawing conventions are the domain pack's `figures.md`.

Colours and the provenance marker: `draft-colours.md`.
