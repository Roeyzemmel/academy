# Using computation responsibly in research (§9)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

## 9. Using this responsibly in research

### 9.1 What numerical experiments can and cannot establish

**They can:**
- **Refute.** One explicit geodesic from `p` to `q`, with its holonomy vector, *is* a proof that
  `p` illuminates `q`. One direction whose flow decomposition has a minimal component *is* a
  disproof of complete periodicity in that direction (subject to §9.2). A `False` from
  `O.is_teichmueller_curve(bound)` is conclusive, because it exhibits a witnessing direction.
- **Find the right statement.** Compute the invariant on 50 origamis from the database and the
  pattern in `sum_of_L_exp`, `teich_curve_ncusps` or `min_nb_of_cyls` will usually tell you what
  the theorem should say. This is the highest-value use.
- **Calibrate.** Before proving a bound, check numerically whether it is remotely tight.

**They cannot:**
- **Prove universally quantified statements.** "No connection of length ≤ 40" says nothing about
  length 41. Illumination is a statement about *all* geodesics; a bounded search is a statement
  about finitely many.
- **Certify a negative on a non-lattice surface.** On a Veech surface, the Veech dichotomy can
  sometimes upgrade a finite check into a theorem (if you know the direction is periodic, a
  bounded search in that direction is exhaustive). Off the Veech locus there is no such upgrade.
- **Establish exact values from `lyapunov_exponents_approx`.** §6.4 shows the method returning
  `5e-5` for a true value of `0`, and two different values for the same origami on two doc pages.
- **Turn `O.dimension()` into an orbit closure.** It is documented as a lower bound.

### 9.2 Floating point versus exact arithmetic

The flatsurf stack is unusually good here, and you should exploit it.

- **Number fields (the default, and what you want).** `polygons.triangle(a, b, c)` and
  `EuclideanPolygonsWithAngles(...)` return polygons over a real number field; the doc's own
  output `Polygon(vertices=[(0,0), (1,0), (1/2, c^7 - 13/2*c^5 + 21/2*c^3 - 3/2*c)])` shows the
  generator `c`. Everything downstream — gluings, holonomies, `parabolic()`, cylinder moduli — is
  then **exact**. Always `print(S.base_ring())` after unfolding, and be suspicious if it says
  `Real Double Field`.
- **`AA` (algebraic reals).** `polygons.regular_ngon(12, field=AA)`. Exact but slower; `length()`
  returns an `AA` element by design, since a length need not lie in the field of definition.
- **`pyexactreal` / `ExactReals`.** For *transcendental* parameters — genuinely useful if you want
  a surface with a generic modulus, e.g. to check that a phenomenon is not an arithmetic accident:
  **[VERIFIED-DOC — Tour]**

  ```python
  from pyexactreal import ExactReals
  from flatsurf import similarity_surfaces, Polygon

  R = ExactReals(QuadraticField(3))
  almost_one = R.random_element(1)
  P = Polygon(angles=(1, 1, 4), vertices=[(0, 0), (almost_one, 0)])
  S = similarity_surfaces.billiard(P).minimal_cover(cover_type="translation")
  print(S.base_ring())
  ```

  These are exact real numbers represented lazily with certified comparisons — not floats.
- **`libflatsurf`/`pyflatsurf` is exact too**, over the same coefficient rings (via `pyeantic` for
  number fields and `pyexactreal` for exact reals). The floating-point numbers you see in flow
  decomposition output (`~ -7.6568542`) are only the *display* of exact elements.
- **Where floats do creep in:** `lyapunov_exponents_approx` (Monte-Carlo, genuinely stochastic),
  `RDF(...)` conversions in the tutorials, `float(...)` in plotting, and everything in §8.2.

### 9.3 Common pitfalls, ranked by how often they bite

1. **`saddle_connections(B)` bounds the SQUARED length.** Wrong by a square, silently.
2. **Marked points change the stratum.** `minimal_cover` yields `H_6(5^2, 0^2)`, not
   `H_6(5^2)`, and every dimension you compare against is then wrong. Call
   `erase_marked_points()` — *unless* the marked points are the points you are studying, in which
   case say so explicitly in your notes.
3. **Unfolding gives a cover, not the primitive surface.** Check `o.is_primitive()`,
   `o.intermediate_covers()` on the origami side; on the sage-flatsurf side, an orbit closure
   dimension that is smaller than expected is the usual symptom.
4. **`cyl.area()` from libflatsurf is twice the area.** Halve it before computing moduli. The
   docs say so in a comment that is very easy to skim past.
5. **`O.dimension()` is a lower bound**, and `is_teichmueller_curve` can only prove `False`.
6. **A singularity has many `(label, vertex)` representatives.** Compare `SurfacePoint`s
   (`S.point(...)`), which have correct `__eq__`/`__hash__`; never compare `start_data()` tuples.
7. **Mutable surfaces misbehave.** Always `set_immutable()`.
8. **Sage `Integer` vs C++ `int` at the pyflatsurf boundary.** The docs write `int(16)`,
   `int(0)`, `-int(1)` deliberately.
9. **`traj.flow(n)` stops early at a vertex.** A short trajectory is a signal, not a failure.
10. **sage-flatsurf's `veech_group()` cannot compute generators** (`NotImplementedError`). Use
    `surface_dynamics` origamis, or the `canonicalize()` membership test.
11. **`t.cusps()` does not exist** on a Teichmüller curve. Use `cusp_representatives()`.
12. **`delaunay_decomposition()` / `delaunay_triangulation()` are deprecated** — use
    `delaunay_decompose().codomain()` / `delaunay_triangulate().codomain()`.
13. **Origami invariants are a mix of Python `int` and Sage types.** `r_tuple()`, `nb_squares()`,
    `genus()`, `veech_group().index()` are plain `int` and serialise; `monodromy().order()`,
    `automorphism_group().order()`, `lattice_of_*periods()` and `sum_of_lyapunov_exponents()` are
    Sage `Integer` / `Rational` and raise `TypeError` in `json.dumps`. §6.7.2 has the table.
14. **`lattice_of_periods()` is the *relative* lattice.** On the Eierlegende Wollmilchsau it is
    `(1,0,1)` while `lattice_of_absolute_periods()` is `(2,0,2)`. Picking the wrong one silently
    loses the torus-cover index. §6.7.4.
15. **A twist word whose matrix is the identity relabels the squares.** On the 3-square L,
    `(h(1) v(-1) h(1))^4` returns `r_tuple() == (0,2,1)` instead of `(1,0,2)`; on the EW the same
    word leaves the tuples alone, so testing on one origami proves nothing. §6.7.5.

### 9.4 A workflow that keeps you honest

1. Build the surface, print `S.base_ring()` and **both** strata (with and without marked points).
2. Record the exact package versions in the notebook: `import flatsurf; flatsurf.__version__` and
   the surface-dynamics equivalent, plus the date.
3. Run the cheap probe (§7.2c or §8) to form a conjecture.
4. Re-run at 2× and 10× the bound. If the answer changes, the first run was noise.
5. Perturb: change the polygon slightly (or use `ExactReals` for a generic parameter). If the
   phenomenon vanishes, it was arithmetic; if it survives, it may be a theorem.
6. Before writing anything down, ask which half of §9.1 the result belongs to, and phrase the
   claim accordingly ("we verified computationally that …up to length 40", never "…there is no").

