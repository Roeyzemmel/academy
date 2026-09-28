# Modern LaTeX practice for a math paper

<!-- From the generic part of the old latex-paper-writing skill (Group B, 2026-09-28); project examples replaced by neutral ones. The home's own rules (e.g. BI .claude/rules/tex-conventions.md) say what a paper has adopted. -->

Propose these to the author, explain the reason, and let the author choose. Do
not silently rewrite a preamble: a coauthored paper with several people compiling
it is not the place for unannounced infrastructure changes. (tex-engineer proposes;
the home's rules record what was adopted.)

Every snippet below was **compile-tested** (pdflatex, amsart) before being written
down.

## 1. `\NewDocumentCommand` instead of `\newcommand` + `\if\relax\detokenize`

This is often the biggest concrete improvement available to an older preamble.
Take a macro `\op` (an operator with an optional subscript and an optional
argument) written with the old trick for "argument might be empty":

```latex
\newcommand{\op}[2]{\ensuremath{\mathrm{op}%
  \if\relax\detokenize{#1}\relax\else _{#1}\fi
  \if\relax\detokenize{#2}\relax\else\left(#2\right)\fi}}
% called as \op{}{\gamma} -- you must always supply both braces
```

`xparse` has been part of the LaTeX kernel since the 2020 release, so
`\NewDocumentCommand` is available with no extra package and expresses this
directly:

```latex
\NewDocumentCommand{\op}{o d()}{%
  \mathrm{op}\IfValueT{#1}{_{#1}}%
  \IfValueT{#2}{\mathopen{}\left(#2\right)\mathclose{}}}
```

Now all four forms work and read like the mathematics:

```latex
\op            % op
\op[v]         % op_v
\op(\gamma)    % op(gamma)
\op[v](\gamma) % op_v(gamma)
```

The argument spec is a small language: `o` = optional `[...]`, `d()` = optional
delimited by parentheses, `m` = mandatory, `s` = optional star, `e{_^}` =
optional embellishments. `\IfValueT{#1}{...}` tests whether an optional argument
was given. The same treatment applies to every macro of this shape.

## 2. `\DeclarePairedDelimiter` instead of hard-coded `\left...\right`

A hand-written `\norm{v}` often expands to `\left\lVert v\right\rVert`. Two problems:
`\left...\right` always scales even when it shouldn't, and TeX treats the result
as `\mathinner`, which gives subtly wrong spacing around it. `mathtools` solves
both:

```latex
\DeclarePairedDelimiter{\abs}{\lvert}{\rvert}
\DeclarePairedDelimiter{\norm}{\lVert}{\rVert}
\DeclarePairedDelimiterX{\inProd}[2]{\langle}{\rangle}{#1,#2}
```

```latex
\norm{v}              % normal size -- the right default
\norm*{\frac{a}{b}}   % auto-sized, only where you actually want it
\norm[\big]{x}        % explicitly sized
```

**General rule worth internalizing: do not use `\left...\right` by default.** Use
it only where the content genuinely needs scaling, and prefer `\bigl(`, `\Bigl(`
etc. when you know the size. Automatic sizing produces delimiters that are too
large surprisingly often.

## 3. One sentence per line in the source

The single highest-value habit for a paper with several coauthors and a git repo.
Never hard-wrap a paragraph at 80 columns; instead break the source at sentence
boundaries (and after major clauses):

```latex
Let $G$ be a finitely generated group.
We say that $G$ is \emph{tame} if every finite-index subgroup is finitely
presented.
This is the case $n = 0$ of the definition above.
```

Rewording one sentence then produces a one-line diff instead of a reflowed
paragraph, so `git diff` and merge conflicts become readable. The compiled output
is identical — LaTeX collapses single newlines into spaces.

## 4. Bibliography: `biblatex` + `biber` vs `amsalpha` + BibTeX

The classic setup (`\bibliographystyle{amsalpha}`, `\bibliography{references}`)
is the mathematics standard and is entirely respectable. `biblatex` is the modern
alternative and is genuinely better if the paper has many references:

```latex
\usepackage[style=alphabetic, backend=biber, maxbibnames=99, giveninits=true]{biblatex}
\addbibresource{references.bib}
...
\printbibliography
```

What it buys: `style=alphabetic` reproduces the `[LMW16]` look mathematicians
expect; `maxbibnames=99` stops the "et al." truncation that `amsalpha` applies;
native `doi`, `eprint`, and `url` fields render as links; Unicode in author names
works without escapes (Lelièvre, Möller); `\autocite` and `\textcite` give proper
in-text citation forms.

The costs are real and worth stating: the build needs `biber` rather than
`bibtex`, some journals' submission systems still assume BibTeX, and coauthors
must have it installed. **Recommendation: raise it, but don't switch a paper
mid-flight** unless everyone agrees. If staying with `amsalpha`, at least add
`doi` and `eprint`/`eprintclass` fields to the `.bib` entries — `amsalpha`
renders them.

## 5. `microtype` — one line, free improvement

If it is not loaded yet, `\usepackage{microtype}` enables character protrusion and
font expansion; the visual result is noticeably fewer overfull lines and a more
even gray. There is no downside on a normal TeX Live install. (On a minimal
install that errors with "auto expansion is only possible with scalable fonts",
use `\usepackage[activate=false]{microtype}` or install the scalable fonts.)

## 6. Engine and fonts

`pdflatex` with Computer Modern is the safe default and what most journals expect.
Two modern options worth knowing about:

- **`newtxmath`/`newtxtext`** (Times-like) or **`libertinus`** — still pdflatex,
  just better-looking text with matching math. Low risk.
- **LuaLaTeX or XeLaTeX with `unicode-math`** — lets you use OpenType math fonts
  (Latin Modern Math, STIX Two Math, Libertinus Math) and type Unicode directly.
  The most modern setup, but `unicode-math` conflicts with some traditional math
  packages and a few journal classes assume pdflatex. Good for a preprint,
  risky for a submission.

Do not change engine or fonts without asking — it changes every line break in the
document, which makes the next diff useless.

## 7. Build and lint

- **`latexmk -pdf main.tex`** runs pdflatex/bibtex the right number of times.
  `latexmk -pdf -pvc main.tex` watches and rebuilds on save. Use this instead of
  running `pdflatex` by hand three times.
- **`chktex main.tex`** catches real errors: `\left` without `\right`, math-mode
  ellipsis mistakes, wrong spacing after abbreviations, `$$` instead of `\[`.
- **`latexdiff old.tex new.tex > diff.tex`** produces a marked-up PDF of what
  changed — exactly what a coauthor or a referee-response letter needs.
- Keep the paper in git. `.gitignore` the `.aux/.log/.out/.bbl/.synctex.gz`
  churn.

## 8. Things to keep doing

Where a preamble already does the following, it is right, and these are not
candidates for change:

- **`thmtools`** with `\declaretheorem` and `sibling=thm` — this *is* the modern
  way; it is cleaner than a pile of `\newtheorem[...]` lines and gives
  `\listoftheorems` for free.
- **`cleveref` loaded after `hyperref`** — correct order, and `\cref` is right.
- **`mathtools`** rather than bare `amsmath`.
- **Sections in separate files** via `\input` — essential for coauthoring.
- **`showlabels`** while drafting — genuinely useful, remove for submission.
- **`standalone` + `import`** so figures compile on their own — good practice,
  and much faster than rebuilding the paper to check a picture.

## 9. Small modern touches

- Load `\usepackage{enumitem}` once (a grown preamble often loads it twice). Use
  `\begin{enumerate}[label=(\roman*)]` rather than redefining `\labelenumi`.
- `\mathopen{}` / `\mathclose{}` around scaled delimiters fixes the spacing bug
  mentioned in §2.
- `\operatorname{...}` for a one-off operator; `\DeclareMathOperator` only for
  ones used repeatedly.
- `\eqref{...}` for equation references, or just let `cleveref` handle it.
- `\emph{}` rather than `\textit{}` — it nests correctly.
- `\dots` rather than `\ldots`/`\cdots`; it picks the right one from context.
- For a new definition, `\coloneqq` (mathtools) rather than `:=`.
