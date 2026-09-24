# TikZ conventions for translation-surface figures

Figures in this subject carry real information — which edges are glued, where the
cone points are, how a trajectory sits relative to a cylinder. A reader checks the
mathematics against the picture, so an inconsistent picture is a bug.

**The one rule that matters most: be consistent across the whole paper.** Same
arrow marks for identified edges, same shading for cylinders, same mark for a
singularity, same mark for a marked point — every figure, every time. Below is a
consistent scheme; if the existing drafts use a different one, adopt theirs.

## Preamble

```latex
\usepackage{tikz}
\usetikzlibrary{decorations.markings,arrows.meta,patterns,calc,positioning}
```

## The style block

Put this once in the preamble so every figure inherits it. Everything below
assumes it.

```latex
\tikzset{
  % --- edge identifications: one, two, three ticks; then open arrowheads ---
  ident/.style={very thick},
  tick/.style 2 args={
    ident,
    postaction={decorate, decoration={markings,
      mark=between positions 0.42 and 0.58 step 0.08 with
        {\arrow{Stealth[length=2.4mm]}}}}},
  % simple, robust version: a mark count via repeated arrowheads
  id1/.style={ident, postaction={decorate, decoration={markings,
      mark=at position 0.5 with {\arrow{Stealth[length=2.6mm]}}}}},
  id2/.style={ident, postaction={decorate, decoration={markings,
      mark=at position 0.44 with {\arrow{Stealth[length=2.6mm]}},
      mark=at position 0.56 with {\arrow{Stealth[length=2.6mm]}}}}},
  id3/.style={ident, postaction={decorate, decoration={markings,
      mark=at position 0.38 with {\arrow{Stealth[length=2.6mm]}},
      mark=at position 0.50 with {\arrow{Stealth[length=2.6mm]}},
      mark=at position 0.62 with {\arrow{Stealth[length=2.6mm]}}}}},
  % --- points ---
  sing/.style={circle, fill=black, inner sep=0pt, minimum size=4.2pt},
  marked/.style={circle, draw=black, fill=white, very thick,
                 inner sep=0pt, minimum size=4.2pt},
  reg/.style={circle, fill=black, inner sep=0pt, minimum size=2.4pt},
  % --- trajectories and blockers ---
  traj/.style={draw=blue!70!black, thick},
  traj2/.style={draw=red!70!black, thick, dashed},
  blocker/.style={cross out, draw=red!80!black, very thick,
                  inner sep=0pt, minimum size=5pt},
  % --- regions ---
  cyl/.style={fill=black!10},
  cylB/.style={fill=blue!10},
  poly/.style={draw=black, very thick, fill=black!2},
}
```

Point vocabulary, fixed for the whole paper:

| Mark | Means |
|---|---|
| filled disc `sing` | cone point / zero of $\omega$ |
| open disc `marked` | marked point (zero of order 0) — **visually distinct from a singularity, always** |
| small filled dot `reg` | regular point of interest ($x$, $y$) |
| red cross `blocker` | element of a blocking set |

Arrowhead count = which edges are identified: one head with one head, two with
two, three with three. Direction of the arrow = the direction of the gluing.
Never rely on color alone to encode a gluing; papers get printed in grayscale.

## Figure 1 — a polygon with edge identifications (the L-shaped $\mathcal{H}(2)$ surface)

```latex
\begin{tikzpicture}[scale=1.5]
  % L-shape: 3 unit squares
  \fill[black!2] (0,0) -- (2,0) -- (2,1) -- (1,1) -- (1,2) -- (0,2) -- cycle;
  % horizontal edges (bottom <-> top), one and two arrowheads
  \draw[id1] (0,0) -- (1,0);
  \draw[id1] (0,2) -- (1,2);
  \draw[id2] (1,0) -- (2,0);
  \draw[id2] (1,1) -- (2,1);
  % vertical edges (left <-> right), three arrowheads and plain
  \draw[id3] (0,0) -- (0,2);
  \draw[id3] (1,1) -- (1,2);
  \draw[ident] (2,0) -- (2,1);
  \draw[ident] (0,0) -- (0,0); % placeholder
  \draw[ident, postaction={decorate, decoration={markings,
        mark=at position 0.5 with {\arrow{Stealth[length=2.6mm]}},
        mark=at position 0.5 with {\arrow{Stealth[length=2.6mm]}}}}]
       (1,0) -- (1,1);
  % the single cone point (all vertices are identified)
  \node[sing] at (0,0) {}; \node[sing] at (1,0) {}; \node[sing] at (2,0) {};
  \node[sing] at (0,2) {}; \node[sing] at (1,2) {};
  \node[sing] at (1,1) {}; \node[sing] at (2,1) {}; \node[sing] at (0,1) {};
  \node[below] at (1,-0.15) {$\scriptstyle 2$};
\end{tikzpicture}
```

Label the edges with letters ($a$, $b$, $c$) *in addition to* the arrowheads when
there are more than three identification classes — arrowhead counting past three
is unreadable.

## Figure 2 — unfolding a rational billiard

Show the polygon, then its reflected copies, with the original shaded darker and
the copies faint. Rotate copies by the elements of the dihedral group; label the
copy by the group element.

```latex
\begin{tikzpicture}[scale=2]
  \def\P{(0,0) -- (1,0) -- (0,1) -- cycle}   % the (pi/4, pi/4, pi/2) triangle
  % the four reflected copies making the unfolded square torus
  \begin{scope}[opacity=0.35]
    \draw[poly] (1,0) -- (1,1) -- (0,1) -- cycle;
  \end{scope}
  \draw[poly] \P;
  \node at (0.3,0.25) {$P$};
  \node at (0.72,0.7) {$\rho P$};
  % a billiard trajectory in P and its unfolded straight line
  \draw[traj2] (0.15,0) -- (0.5,0.35) -- (0.85,0) ;   % billiard path
  \draw[traj]  (0.15,0) -- (0.85,0.7);                % its unfolding
  \node[reg,label=below:$x$] at (0.15,0) {};
\end{tikzpicture}
```

The pedagogical point of every unfolding figure is that the *bent* path in $P$ and
the *straight* path in $M_P$ are the same trajectory. Draw both, in the two
trajectory styles, in the same picture.

## Figure 3 — cylinder decomposition

Shade cylinders in distinguishable grays (`cyl`, `cylB`, or `black!10`,
`black!22`, `black!34`) rather than colors, draw the core curves as thin lines,
and mark the saddle connections bounding them in `ident` weight.

```latex
\begin{tikzpicture}[scale=1.5]
  % horizontal cylinder decomposition of the L-surface: two cylinders
  \fill[black!22] (0,0) rectangle (2,1);   % wide short cylinder
  \fill[black!10] (0,1) rectangle (1,2);   % narrow tall cylinder
  \draw[very thick] (0,0) -- (2,0) -- (2,1) -- (1,1) -- (1,2) -- (0,2) -- cycle;
  \draw[thin, dashed] (0,0.5) -- (2,0.5);
  \draw[thin, dashed] (0,1.5) -- (1,1.5);
  \node at (2.35,0.5) {$C_1$};
  \node at (1.35,1.5) {$C_2$};
  \node[right] at (2.6,0.5) {$\scriptstyle c=2,\ h=1$};
  \node[right] at (2.6,1.5) {$\scriptstyle c=1,\ h=1$};
\end{tikzpicture}
```

Always annotate circumference and height (or the modulus) — a cylinder figure
without them is decorative rather than informative.

## Figure 4 — illumination / blocking

The picture must make visible *why* the pair is blocked or unilluminated: draw
several of the candidate trajectories, not one, and put the blockers exactly where
they interrupt them.

```latex
\begin{tikzpicture}[scale=1.5]
  \draw[poly] (0,0) rectangle (3,2);
  \node[reg, label=below left:$x$] (x) at (0.4,0.4) {};
  \node[reg, label=above right:$y$] (y) at (2.6,1.6) {};
  \draw[traj] (x) -- (y);
  \draw[traj] (x) -- (1.5,0) -- (y);
  \draw[traj] (x) -- (0,1.2) -- (y);
  \node[blocker] at (1.5,1.0) {};
  \node[blocker] at (2.0,0.55) {};
  \node[below right] at (2.05,0.5) {$\scriptstyle B$};
\end{tikzpicture}
```

For an *unilluminated* pair there are no trajectories to draw, which makes the
figure hard: instead show the family of directions leaving $x$ and where each one
goes, or show the covering picture in which the obstruction becomes visible.

## Practical notes

- **Fix a scale per figure type** and reuse it, so a unit square is the same size
  throughout the paper.
- **`\pgfmathsetmacro` for anything computed** (golden ratio for pentagons,
  $\cos(\pi/5)$, etc.) rather than pasting decimals — decimals drift between
  figures and stop matching the text.
- **Regular $n$-gons**: `\foreach \i in {0,...,\n}` with
  `({cos(360*\i/\n)},{sin(360*\i/\n)})`, and remember TikZ trig is in degrees.
- **Compile figures standalone first** (`\documentclass{standalone}`) — it is much
  faster than rebuilding the paper, and errors are legible.
- **Keep each figure in its own file** under `figures/` and `\input` it. Figures
  get reused between the paper, talks, and referee responses.
- **Check in grayscale.** Print or convert to gray before submitting; encode
  everything essential in line weight, dash pattern, and marks.
