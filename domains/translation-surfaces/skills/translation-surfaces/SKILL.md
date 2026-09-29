---
name: translation-surfaces
description: 'Domain expertise on translation surfaces, rational billiards and illumination / finite blocking: notation, theorems, traps, TikZ conventions. Use for flat or translation surfaces, strata, Veech surfaces, saddle connections, origamis, illumination.'
---

# Translation surfaces and illumination

The entry point of the **translation-surfaces domain pack**. The pack carries the
domain's notation, its theorem statements with real hypotheses, its standard examples,
the specific ways people get it wrong, figure conventions and the computation recipes.
The files are the substance; this page says which one to open. It holds no plugin
logic: method (rigor, citation, experiments, paper writing) lives in the academy base
plugin and the role plugins, which reach these files by name through the MCP tool
`domain_get` (pack `translation-surfaces`).

## The pack

| File | Open it when |
|---|---|
| [`notation.md`](../../notation.md) | writing any formula; the domain's default symbols (a project's decisions and its draft override them) |
| [`theorems/INDEX.md`](../../theorems/INDEX.md) | before stating, citing or applying any theorem from this area; lists all entries and the reading rules |
| [`theorems/illumination.md`](../../theorems/illumination.md) | §1 illumination and blocking: LMW, Wolecki, Tokarsky, HST, Monteil, Apisa–Wright, periodic points |
| [`theorems/orbit-closures.md`](../../theorems/orbit-closures.md) | §2 Eskin–Mirzakhani(–Mohammadi), Wright's cylinder deformation, field of definition, rank, Mirzakhani–Wright |
| [`theorems/veech.md`](../../theorems/veech.md) | §3 the Veech dichotomy, Smillie–Weiss, coverings, Gutkin–Judge |
| [`theorems/strata.md`](../../theorems/strata.md) | §4 strata, period coordinates, Kontsevich–Zorich, Masur–Veech, KMS, Masur's criterion |
| [`theorems/unverified.md`](../../theorems/unverified.md) | §6 — **anything listed here is not settled; check the source before citing** |
| [`open-problems.md`](../../open-problems.md) | §5 open problems and active directions |
| [`examples.md`](../../examples.md) | testing a definition, a lemma or a pipeline; the standard examples with ids |
| [`traps.md`](../../traps.md) | before trusting an argument or a computation; the recurring errors, mathematical and API |
| [`figures.md`](../../figures.md) | drawing polygons with identifications, unfoldings, cylinders, trajectories, blocked pairs |
| [`computation/README.md`](../../computation/README.md) | computing anything: which tool, the bundled scripts, the API recipe index |
| [`CHANGELOG.md`](../../CHANGELOG.md) | what changed in the pack and where old content went |

## Use the reference sheet, not memory

The theorem sheet holds precise statements with sources, one file per section. **Read the
relevant entry before stating or citing any theorem from this area.** Memory
reconstructs hypotheses plausibly and wrongly, and in this field the hypotheses are the
content — "torus cover", "Veech", "primitive", "prelattice", and "square-tiled" are five
different conditions that get conflated.

Each entry has **Statement / Notation used / Common misuse / Source**. The "Common
misuse" lines are not padding; they are the errors that actually appear.

Section 6 ([`theorems/unverified.md`](../../theorems/unverified.md)) is load-bearing.
Anything listed there — including some theorem numberings, the Gutkin–Judge
balanced-covering formulation, and Wolecki's lemma hypotheses — must be checked against
the paper before it goes into a manuscript. Cite nothing from §6 as settled. The sheet
is a map to the sources, not a substitute: a citation in a paper still goes through the
Expert role's library (`academy:citation-discipline`).

## The four traps that cost the most

In short (each is elaborated, with the sheet entry that carries it, in
[`traps.md`](../../traps.md) §A):

1. **"Torus cover" ≠ "square-tiled" ≠ "arithmetic".** LMW's torus covers may branch over
   several points; swapping in "square-tiled" inverts the content of their dichotomy.
2. **Finiteness is per source point, not for pairs.** Finiteness of unilluminated pairs
   is a theorem about rational polygons (Wolecki), not about translation surfaces.
3. **Marked points change the stratum and are never harmless.** $\mathcal{H}(2)$ and
   $\mathcal{H}(2,0)$ are different strata; unfolding can produce marked points or a
   cover rather than the primitive surface.
4. **Illumination is the $\mathrm{bc}=0$ case of finite blocking.** Results do not
   transfer automatically between $\mathrm{bc}=0$ and $\mathrm{bc}\ge 1$.

## Standing habits for this area

- **Say which surface.** $(X,\omega)$, the unfolding $M$ of a polygon $P$, and a
  translation cover of $M$ are three different objects and statements routinely
  fail to transfer between them. Name the one in play in every claim.
- **Check the dimension count.** $\dim_{\mathbb{C}} \mathcal{H}(k_1,\dots,k_n) =
  2g + n - 1$ in period coordinates, with $\sum k_i = 2g-2$. A claim that
  contradicts this arithmetic is wrong, and this is the cheapest available check.
- **Test on the standard examples before believing anything**
  ([`examples.md`](../../examples.md)). If a proposed statement already fails on the
  torus, stop.
- **Genericity language is not decoration.** "Generic" means a specific thing
  (full measure, or dense $G_\delta$, or outside a proper affine invariant
  submanifold) and results differ on which. State which one is meant.
- **Watch what unfolding does.** Unfolding a rational polygon with angle
  denominators $N$ produces a specific surface with a specific $\mathbb{Z}/N$
  symmetry; the billiard flow corresponds to the straight-line flow, and
  trajectories through corners are undefined rather than reflected. Statements
  about the polygon and about its unfolding are related by a dictionary, not by
  identity.

## Notation and figures

[`notation.md`](../../notation.md) is the domain's default notation. A project's
settled decisions and its draft override it (`academy:notation-discipline`); a change to
the domain standard is a `notation` ticket to Expert.

[`figures.md`](../../figures.md) has conventions and reusable TikZ for the pictures this
subject needs. Consistency across a paper's figures matters more than any individual
picture. The project decides where figure files live and how they are included.

## Extending the pack

A new theorem entry goes in its topic file as the next number of its section, with its
source; an unverified one goes in `theorems/unverified.md`. A new API finding goes in
its `computation/api/` topic file. Every change gets a line in
[`CHANGELOG.md`](../../CHANGELOG.md). The Expert role's librarian curates the pack;
other roles propose changes by ticket.
