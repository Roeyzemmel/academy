# Frame patterns (TeX, using the template's macros)

Cited result (source in the header, no tag):
```tex
\slide{Main statement}{%
\begin{prop}[{\cite[Prop.~3.11]{AW21}}]\label{prop:tc-class}
A simple rational polygon unfolds to a torus cover iff it is Gaussian, Eisenstein or rectangle-tiled.
\end{prop}}
```
Definition (never an idea), figure in the corner:
```tex
\slide{Delaunay cells}{\small%
\begin{withfig}{fig-cells}
\begin{defn} ... two plain sentences ... \end{defn}
\end{withfig}}
```
Unproved statement: `\begin{idea}[name]\label{idea:x} ... \end{idea}`; proved short statement:
`\begin{prop} ... \end{prop}` then `\emph{Idea of proof.} one line`.

Split instead of shrinking: definition frame (`\slide{Chambers}`) and the frame that uses it
(`\slide{The graph}`), the second one repeating only the symbol it needs.

Summary and questions (always the last core frame): three bullets of what was shown, then 2-3 questions the
audience can take away; no status vocabulary.

Bonus frame: `\bslide{Title}{...}` in `content/b-*.tex`, input after the summary in the deck and in its natural
place in the notes. Notes-only prose: `\onlyarticle{...}`. Speaker note: `\speak{...}`.

Anti-patterns: a full-paragraph definition in `\footnotesize`; `[cited]`/`[sketch]` brackets; "not proved yet"
sentences; a figure under three bullets at a tenth of the frame; a commutative diagram where a concrete
instance would show the mechanism; a definition marked as an idea; an abstract promising a section that does
not exist.
