# Standard examples

The surfaces every definition, lemma and pipeline in this domain is tested on before it
is believed. **If a proposed statement already fails on the square torus, stop.** Each
example has an id, which definition tests, experiment headers and review packets use
to name it (`ex:<id>`).

This file unifies three earlier lists (2026-09-28):
- **[ND]** a project's decisions file (a paper home's notation decisions), "The
  standard examples" (7 examples, with what each one catches);
- **[TS]** the old `translation-surfaces` skill, "Test on the standard examples" (5);
- **[FC]** the old `flatsurf-computation` skill, "Validate the setup on something you
  know" (3).

**What is recorded here and what is not.** The "Stated" lines carry only what those
three lists say. The "On file" lines point to values printed by an actual run or by
upstream documentation, as recorded in `computation/api/` with that file's own
verification tag; they are pointers, not new claims. Nothing else about an example is
asserted in this file. Anything a list names without a construction is marked
**[UNSPECIFIED]**, and anything whose identity differs between sources is marked
**[CHECK]**. A project may fix a subset or add examples in its own decisions file
(the [ND] project fixes its seven); that file wins inside its project.

## Summary

| id | Example | In lists | Role |
|---|---|---|---|
| `square-torus` | the square torus | ND, TS, FC | the degenerate case |
| `L3` | the three-square L | ND, TS, FC | smallest interesting square-tiled surface |
| `ew` | the Eierlegende Wollmilchsau | ND, TS | maximally symmetric origami |
| `rectangle` | the unfolding of the rectangle | ND | base case of the billiard dictionary |
| `tri-30-60-90` | the unfolding of the 30-60-90 triangle | ND | a rational triangle with group of order 12 |
| `tri-45-45-90` | the unfolding of the 45-45-90 triangle | ND | a rational triangle with group of order 8 |
| `double-pentagon` | the double pentagon | ND, TS | a Veech surface that is not a torus cover |
| `regular-pentagon` | the regular pentagon | TS, FC | [CHECK] which object is meant |
| `nmk-triangles` | the Veech surfaces from the $(n,m,k)$ triangles | TS | [UNSPECIFIED] a family |

The discriminating example is `double-pentagon` [ND]: "a happy answer on the double
pentagon for a torus-cover-only notion means the definition or the script is wrong".
See `traps.md` A1 for why torus cover, square-tiled and arithmetic are different
conditions.

## The examples

### `square-torus` — the square torus

- **Stated.** [ND] "the degenerate case; $\Sigma$ empty or one marked point". [TS] "If a
  proposed statement already fails on the torus, stop." [FC] "If the pipeline gets the
  torus wrong, nothing downstream means anything."
- **Construction.** sage-flatsurf `translation_surfaces.square_torus()`
  (`computation/api/surfaces.md` §2, `saddle-connections.md` §4.4); pure Python: the
  one-square origami `Origami([0], [0])` in `computation/scripts/origami_illumination.py`,
  whose self-test checks lattice-point counts on the torus.
- **Note.** Whether $\Sigma$ is empty or one marked point is a choice [ND]; say which
  (`traps.md` A3).

### `L3` — the three-square L

- **Stated.** [ND] "in $\mathcal{H}(2)$; the smallest interesting square-tiled surface".
  [TS] "a square-tiled surface in $\mathcal{H}(2)$ (the 3-square L)". [FC] "the 3-square
  L in $\mathcal{H}(2)$".
- **Construction.** An origami on 3 squares. `surface_dynamics`:
  `Origami("(1,2)", "(1,3)")` (1-based), labelled "the 3-square L in H(2)" in
  `computation/api/origamis.md` §6.2 [VERIFIED-DOC]; the bundled script uses the same permutations,
  0-based: `Origami([1, 0, 2], [2, 1, 0])` in `origami_illumination.py`.
- **On file.** `computation/api/origamis.md` §6.2: `o.stratum()` → `H_2(2)`,
  `o.stratum_component()` → `H_2(2)^hyp`.
- **[CHECK]** `computation/api/origamis.md` §12.5 and `libgap.md` §12.6 call a
  *different* origami "the 3-square L": `Origami('(1,2,3)', '(1,3)')`, i.e. 0-based
  `([1,2,0],[2,1,0])` (on file there: stratum `H_2(2)`, genus 2, monodromy group $S_3$). Both are 3-square origamis in $\mathcal{H}(2)$ by those records, but they
  are different permutation pairs; a test that depends on the square labels must say
  which one it used.

### `ew` — the Eierlegende Wollmilchsau

- **Stated.** [ND] "maximally symmetric origami; breaks naive counts". [TS] listed.
- **Construction.** `surface_dynamics`: `origamis.EierlegendeWollmilchsau()`. Use the
  library constructor rather than transcribing tuples: hand-typed tuples once gave a
  disconnected origami and a wrong monodromy order with no error
  (`computation/api/libgap.md` §12.7.3).
- **On file.** `computation/api/origamis.md` §6.7.1 (confirmed run): 8 squares, stratum
  `H_3(1^4)`, component `H_3(1^4)^c`, genus 3, `veech_group().index()` → 1,
  `sum_of_lyapunov_exponents()` → 1. `libgap.md` §12.6: monodromy $Q_8$, regular.

### `rectangle` — the unfolding of the rectangle

- **Stated.** [ND] "genus 1, the 2×2 torus; the billiard dictionary's base case".
- **Construction.** Billiard unfolding of a rectangle: `polygons.rectangle(a, b)` then
  `similarity_surfaces.billiard(P).minimal_cover('translation')`
  (`computation/api/surfaces.md` §2, §3.1). Check for marked points
  (`surfaces.md` §3.2(a)).

### `tri-30-60-90` — the unfolding of the 30-60-90 triangle

- **Stated.** [ND] "$K$ of order 12", where [ND]'s $K$ is the finite orthogonal group of
  the flat structure (that project's notation).
- **Construction.** `polygons.triangle(1, 2, 3)` (angles proportional to $1:2:3$) then
  the billiard unfolding of `surfaces.md` §3.1. **Not run for this file**: print the
  stratum and erase or keep marked points consciously (`surfaces.md` §3.2).

### `tri-45-45-90` — the unfolding of the 45-45-90 triangle

- **Stated.** [ND] "$K$ of order 8".
- **Construction.** `polygons.triangle(1, 1, 2)` then the billiard unfolding of
  `surfaces.md` §3.1. **Not run for this file**, same caveats.

### `double-pentagon` — the double pentagon

- **Stated.** [ND] "a Veech surface that is **not** a torus cover — any definition that
  only makes sense for torus covers must visibly refuse it". [TS] "the regular pentagon /
  double pentagon".
- **Construction.** sage-flatsurf `translation_surfaces.veech_double_n_gon(5)`
  (`computation/api/surfaces.md` §2.3). Use exact (number-field) arithmetic
  (`computation/api/practice.md` §9.2).
- **On file.** `computation/api/setup.md` §12.4: `veech_double_n_gon(5).canonicalize()`
  and `GL2ROrbitClosure(...).decomposition((1,0))` run once the environment is fixed.

### `regular-pentagon` — the regular pentagon [CHECK]

- **Stated.** [FC] "the regular pentagon" as a known validation case; [TS] "the regular
  pentagon / double pentagon" as one entry.
- **[CHECK]** The sources do not say whether this is the regular pentagon *as a billiard
  table* (whose unfolding is a translation surface) or the double pentagon surface
  itself. Whoever uses it names the object and its construction in the header; until a
  project fixes it, prefer `double-pentagon`.

### `nmk-triangles` — Veech surfaces from the $(n,m,k)$ triangles [UNSPECIFIED]

- **Stated.** [TS] "the Veech surfaces from the $(n,m,k)$ triangles". No list says which
  triangles or which convention for $(n,m,k)$.
- **Construction.** Billiard unfolding of `polygons.triangle(n, m, k)` (angles
  proportional to $n:m:k$), `surfaces.md` §3.1 — but which triples give Veech surfaces
  is a mathematical statement that is **not** on the theorem sheet
  (`theorems/INDEX.md`). Cite the source before using a member of this family as a
  "known Veech" validation case.

## Using the examples

- **Definition tests.** A definition test reports its value on each example the project
  fixes, or a one-line reason it cannot be computed there. The Scientist role's
  `examples-audit` skill runs them.
- **Validation cases.** An experiment's validation case reproduces a value that is *on
  file* for one of these examples (or a cited value), never one invented for the test.
- **Dropping a hypothesis** [ND]: "remove one from a definition or a lemma and check that
  the counterexample reappears. A hypothesis whose removal breaks nothing is either
  unnecessary or the test is too weak, and either is worth reporting."
