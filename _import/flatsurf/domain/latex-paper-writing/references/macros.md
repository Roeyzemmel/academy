# The project's LaTeX conventions

Extracted from Roey's `main.tex`. `assets/preamble.tex` is that preamble verbatim;
`assets/main-skeleton.tex` is the whole file including document structure.
**Verified to compile** (pdflatex, amsart + thmtools + cleveref) with every macro
below exercised.

Read this before writing any `.tex` for the project. Using a macro that does not
exist, or redefining one that does, is the most common way to break a coauthor's
build — so **whatever the preamble currently says is what the `.tex` must use
today.**

That is a constraint on the *output*, not a verdict on the preamble. Roey has said
he is not attached to it and wants to learn current practice, so proposing
improvements is welcome — see `modern-latex.md`, which has tested upgrades and the
reasoning for each. The order is: write correct `.tex` against the preamble as it
stands, and raise the improvement separately. Silently changing shared
infrastructure in a paper with five coauthors breaks other people's builds.

## Document structure

`main.tex` is a shell: preamble, then `\input{sections/<name>}` per section.
Write into the section files, not into `main.tex`. Current sections, in order:

`goal` · `metric_decomps` · `markings` · `scheier_graphs` · `slope1` ·
`flat_illumination` · `remainders` · `preliminaries`

Note that **Preliminaries comes last** in this draft — a deliberate drafting
choice, not an error to fix. Bibliography: `\bibliographystyle{amsalpha}` with
`references.bib`.

## Theorem environments — thmtools, not plain amsthm

Everything is a **sibling of `thm`** and numbered within the section, so Theorem
2.1 is followed by Lemma 2.2. Use the short names; `\begin{theorem}` and
`\begin{lemma}` are **not defined** and will fail.

| Style | Environments |
|---|---|
| plain (italic body) | `thm` `prop` `lem` `fact` `cor` `conj` |
| definition (upright body) | `defn` `exc` `rmk` `ex` `exer` `quest` |
| own counter | `claim` `case` |
| unnumbered | `claim*` `problem` |

`\cref` / `\Cref` names are configured for all of these — always reference with
`\cref{lem:foo}`, never a hand-typed "Lemma~\ref{...}".

Two harmless preamble quirks worth knowing rather than silently "fixing":
`exc` and `exer` are both named *Exercise* (two environments, one name), and
`enumitem` is loaded three times. Neither breaks anything. Mention them if
tidying the preamble comes up; don't change them unasked.

## Macro traps — the ones that will bite

**Blackboard bold is asymmetric.** `\N` `\Z` `\R` are bare; the rest carry a `bb`
prefix: `\bbQ` `\bbH` `\bbC` `\bbT` `\bbD`. There is no `\Q`, `\C`, `\H`, `\T`,
`\D` — writing `\C` for the complex numbers fails to compile.

**Calligraphic H is `\ccH`, not `\cH`.** `\cH` is undefined. So a stratum is
`\ccH(2,1,1)`. Defined: `\cA \cB \cC \cD \cE \cF \cG \ccH \cL \cM \cN \cU \cV
\cP \cQ \cR \cS \cT`, plus `\ML \PML \QD`. Others (`\cI \cJ \cK \cO \cW …`) do
not exist.

**`\Mod` is the mapping class group**, not a moduli space and not a cylinder
modulus. Use `\cM` for an affine invariant submanifold.

**`\parallel` has been redefined** to a short raised double-slash for the
parallel/cylinder relation. It is no longer the ordinary $\parallel$. If ordinary
"divides"-style notation is ever needed, say so rather than quietly redefining it
back.

**`\hol` takes two arguments**, both optionally empty: `\hol{<subscript>}{<arg>}`.
So `\hol{}{\gamma}` prints $\mathrm{hol}(\gamma)$ and `\hol{v}{}` prints
$\mathrm{hol}_v$. Same shape for `\holx` and `\holy` (the $x$- and $y$-components).
`\dev` takes an *optional* argument: `\dev` or `\dev[z]`.

## Available operators

```
\id \Id \Aut \SAut \Cyl \Out \Inn \Hom \Ext \Tor \SPMap \PMap \PMapc
\PHE \PHEc \PPHE \Homeo \Isom \Map \Mod \diam \supp \rk \myspan \cork
\asdim \Clop \Ult \SL \PSL \SO \PSO \GL \PGL \area \vol \ax \Leb
\Stab \Fix \tr \Trans \Aff
```

Note `\myspan` (not `\span`, which is a TeX primitive) and `\tr` (which prints
`Tr`). There is no `\hol`-style operator for the blocking cardinality yet — if the
paper needs one, propose `\DeclareMathOperator{\bc}{bc}` rather than writing it
by hand each time.

## Other shortcuts

`\eps` ($\varepsilon$) · `\e` ($\epsilon$) · `\acts` ($\curvearrowright$) ·
`\actedby` · `\norm{v}` · `\inProd{u}{v}` · `\uline{x}` · `\rmd` (upright
differential d) · `\mapsfrom` · `\hooklongrightarrow` · `\eqrmk{note}` (a
right-aligned parenthetical inside a display) · `smallpmatrix` environment ·
`\doublecoset{A}{B}{C}`, `\leftcoset{A}{B}`, `\rightcoset{A}{B}`.

Loaded and available: `tikz-cd` (commutative diagrams), `nicefrac`, `booktabs` +
`tabularx` + `makecell` + `multirow` + `adjustbox` (tables), `subcaption`,
`standalone` + `import` (so figures can be separate compilable files), `float`
(`[H]`), `enumitem`, `showlabels` (labels print in the margin while drafting).

## Comments and draft markers — use the existing system

The preamble has a margin-comment system; **use it instead of inventing `\todo` or
`\gap` macros.** `\newComment{Firstname}{initials}{color}` defines two things:

- `\Firstname{text}` — an auto-numbered margin note, tagged with the initials
- `\initials{text}` — inline text in that person's color

Currently defined:

| Person | Margin note | Inline color | Color |
|---|---|---|---|
| Carlos | `\Carlos{…}` | `\co{…}` | marine |
| Victoria | `\Victoria{…}` | `\vr{…}` | orange |
| Hayim | `\Hayim{…}` | `\hs{…}` | cadetgrey |
| Roey | `\Roey{…}` | `\rz{…}` | blue |
| Barak | `\Barak{…}` | `\bw{…}` | lightblue |
| — | `\Name2{…}` / `\Name3{…}` | `\N2{…}` / `\N3{…}` | teal / brown |

The draft's own stated color conventions are **blue = Sketch, red = Conjecture,
brown = Meta**.

**Never sign a margin note as one of the human coauthors.** Roey has settled the
convention: machine-written notes get their own slot. Add this line to the
preamble alongside the others, once:

```latex
\newComment{Claude}{cl}{purple}
```

Then use `\Claude{…}` for a numbered margin note and `\cl{…}` for inline purple
text. Every step that is sketched, unverified, or a judgement call gets one, and
gets named in the accompanying chat message too — the margin note is for the
person reading the PDF next month, the message is for the person reading now.

If the preamble in front of you does not yet have that line, add it (it is one
line, additive, and breaks nothing) and say that you did.

Note also that `\rz{…}` renders blue, which the draft conventions read as
"Sketch" — so blue inline text is ambiguous between "Roey wrote this" and "this is
a sketch". Worth raising with him; don't resolve it unilaterally.

## Before handing back a `.tex`

- It compiles: `pdflatex main.tex` twice (three times if references shift), clean.
- Every `\cref` resolves; no `??` in the output.
- Every macro used is in the list above — grep the preamble if unsure.
- No new macro defined that duplicates an existing one.
- Any step that is sketched, conjectural, or unverified carries a visible marker
  and is named in the accompanying message.
