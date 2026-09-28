# surface_dynamics: strata, origamis, Veech groups (§6, §12.5)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

## 6. surface_dynamics: origamis, Veech groups, strata

### 6.1 Strata **[VERIFIED-DOC — strata module doctests, quoted verbatim]**

The modern constructor is `Stratum(signature, k)` with `k=1` for abelian differentials and `k=2`
for quadratic differentials (`k>=3` for higher-order). `AbelianStratum` / `QuadraticStratum` still
exist as subclasses, but the docs use `Stratum` throughout in 0.7.0.

```python
from surface_dynamics import Stratum

Stratum((2,), k=1)                  # H_2(2)
Stratum([1, 2, 1], k=1)             # H_?(2,1,1)  -- signature is sorted, UniqueRepresentation
Stratum([12], k=2)                  # a quadratic stratum
Stratum({-1: 4}, k=2)               # dict form: exponent multiplicities
Stratum({2: 4}, k=1).signature()    # (2, 2, 2, 2)

Stratum([4], k=1).components()
# (H_3(4)^hyp, H_3(4)^odd)
Stratum([1,1,1,1], k=1).components()
# (H_3(1^4)^c,)
Stratum([12], k=2).components()
# (Q_4(12)^reg, Q_4(12)^irr)
Stratum([6,-1,-1], k=2).components()
# (Q_2(6, -1^2)^hyp, Q_2(6, -1^2)^nonhyp)

Stratum((2,), k=1).dimension()      # 4
Stratum((1,1), k=1).dimension()     # 5
Stratum((0,), k=1).dimension()      # 2
Stratum((3,2,1), k=1).surface_genus()   # 4
Stratum([2], k=1).is_connected()        # True
Stratum([2,2], k=1).is_connected()      # False
Stratum([4], k=1).number_of_components()  # 2
Stratum([2], k=1).one_component()         # H_2(2)^hyp
Stratum([1,1], k=1).unique_component()    # H_2(1^2)^hyp

Stratum([2], k=1).masur_veech_volume()               # 1/120*pi^4
Stratum([4], k=1).hyperelliptic_component().masur_veech_volume()   # 1/6720*pi^6
Stratum((2,), k=1).rank()                            # 2
Stratum([4], k=1).odd_component().rank()             # 3
```

Component selectors: `.hyperelliptic_component()`, `.odd_component()`, `.even_component()`,
`.regular_component()`, `.irregular_component()`, `.non_hyperelliptic_component()`,
`.unique_component()`, `.one_component()`.

**Deprecated on `Stratum` (0.6.0 onwards) — will be removed:** `zeros()`, `genus()`, `nb_zeros()`,
`nb_fake_zeros()`, `nb_poles()`. Use `signature()` and `surface_genus()`. The doctest even shows
the warning text: *"nb_fake_zeros() has been deprecated and will be removed in a future version of
surface-dynamics; use signature()"*.

### 6.2 Origamis / square-tiled surfaces **[VERIFIED-DOC — "Square-tiled Surfaces" tutorial, outputs verbatim]**

```python
from surface_dynamics import Origami, origamis, Stratum

o = Origami("(1,2)", "(1,3)")       # r = (1,2), u = (1,3): the 3-square L in H(2)
print(o.r())        # (1,2)
print(o.u())        # (1,3)

ew = origamis.EierlegendeWollmilchsau()
print(ew.r())       # (1,2,3,4)(5,6,7,8)
print(ew.u())       # (1,5,3,7)(2,8,4,6)

print(o.stratum())            # H_2(2)
print(o.stratum_component())  # H_2(2)^hyp
print(ew.stratum())           # H_3(1^4)
print(ew.stratum_component()) # H_3(1^4)^c
```

Also accepted: `Origami([2,1,3], [3,2,1])` (one-line notation) and `Origami(r, u, as_tuple=True)`
(0-based tuples).

Origamis of a component, and Teichmüller curves in it: **[VERIFIED-DOC]**

```python
from surface_dynamics import Stratum
H2_hyp = Stratum([2]).hyperelliptic_component()
H2_hyp.origamis(4)                 # all 4-square origamis in that component

cc = Stratum([4]).odd_component()
for T in cc.arithmetic_teichmueller_curves(11):     # all T-curves with <= 11 squares
    cyls = [0]*3
    for o in T:                                     # T iterates over its origamis
        n = len(o.cylinder_decomposition())
        cyls[n-1] += 1
    print(cyls)
# [1474, 4310, 2016]
# [110, 0, 90]
# [1650, 636, 1114]
```

Structural predicates (useful precisely for the "is this a cover?" pitfall) **[VERIFIED-DOC — origami module reference]**:

```python
o.nb_squares()   o.genus()   o.num_cylinders()   o.widths_and_heights()
o.cylinder_decomposition()   o.cylinder_diagram()
o.is_connected()  o.is_primitive()  o.is_normal()  o.is_regular()
o.is_quasi_primitive()  o.is_reduced()  o.is_orientation_cover()  o.is_hyperelliptic()
o.automorphism_group()   o.monodromy()
o.is_isomorphic(other, certificate=False)
o.intermediate_covers(degree=None)   o.lattice_of_quotients()   o.quotient(H)
o.lattice_of_periods()   o.period_generators()   o.absolute_period_generators()
o.vertical_symmetry()  o.horizontal_symmetry()  o.mirror()  o.inverse()
o.vertical_twist(width=1)  o.horizontal_twist(width=1)
o.to_standard_form(return_map=True)   o.reduce()   o.relabel(return_map=True)
o.sl2z_edges()   o.gl2z_edges()   o.pgl2z_edges()   o.psl2z_edges()
o.plot()   o.as_graph()   o.set_positions(pos)
```

### 6.3 Veech group of a square-tiled surface **[VERIFIED-DOC — outputs verbatim]**

This is the one place where you get a *genuinely computable* Veech group.

```python
from surface_dynamics import Origami, origamis

o = Origami("(1,2)", "(1,3)")
G = o.veech_group()
print(G)
# Arithmetic subgroup with permutations of right cosets
#  S2=(2,3)
#  S3=(1,2,3)
#  L=(1,2)
#  R=(1,3)
print(G.is_congruence())      # True

ew = origamis.EierlegendeWollmilchsau()
print(ew.veech_group())
# Arithmetic subgroup with permutations of right cosets
#  S2=()
#  S3=()
#  L=()
#  R=()          <-- index 1: the Veech group is all of SL(2,Z)
```

The return value is a Sage `ArithmeticSubgroup_Permutation`, so the whole Sage arithmetic-subgroup
API applies **[VERIFIED — Sage reference manual, `sage.modular.arithgroup.arithgroup_perm`]**:

```python
G.index()            # index in SL(2,Z)
G.ncusps()           # number of cusps
G.cusp_widths()      # list of cusp widths
G.nu2()   G.nu3()    # elliptic points of order 2 and 3
G.genus()            # genus of the quotient
G.is_congruence()    # Hsu's algorithm
G.congruence_closure()
G.generators()
```

Teichmüller curve object **[VERIFIED — source of `teichmueller_curve.py`]**:

```python
t = o.teichmueller_curve()
t.origami()                       # canonical representative
t.stratum()                       # H_2(2)
t.veech_group()
t.sum_of_lyapunov_exponents()     # 4/3
t.orbit_graph(s2_edges=True, s3_edges=True, l_edges=False, r_edges=False,
              vertex_labels=True)
for o_rep, width in t.cusp_representatives():
    print(o_rep, width)
```

> **[UNVERIFIED / CORRECTION]** Several older write-ups (and some LLM-generated snippets) use
> **`t.cusps()`**. I read the current `teichmueller_curve.py` and **there is no `cusps()` method**.
> The real API is `cusp_representatives()`, which returns a list of pairs `(origami, width)`, and
> the underlying generator `cusp_representative_iterator()`, documented as: *"Iterator over the
> cusp of self. Each term is a couple (o, w) where o is a representative of the cusp (an origami)
> and w is the width of the cusp (an integer)."* For the *number* of cusps use
> `o.veech_group().ncusps()` or the database column `teich_curve_ncusps`.

### 6.4 Lyapunov exponents **[VERIFIED-DOC — outputs verbatim]**

```python
o.lyapunov_exponents_approx()      # [0.333313763095923]     (Monte-Carlo; varies run to run)
o.sum_of_lyapunov_exponents()      # 4/3                     (exact, Eskin-Kontsevich-Zorich)

ew.lyapunov_exponents_approx()     # [0.0000513874765558288, 0.0000408841305871166]
ew.sum_of_lyapunov_exponents()     # 1
```

Full signature: `lyapunov_exponents_approx(nb_iterations=2**17, nb_experiments=4, involution=None)`.
Note that the Eierlegende Wollmilchsau's exponents are theoretically **0** and the numerics return
`5e-5`, `4e-5` — a perfect illustration of what "approx" means. The Tour page independently
reports `[0.332649016459072]` for the same `o` that the tutorial reports `[0.333313763095923]`
for. **These are stochastic. Never quote them as evidence of an exact value; use them only to
identify a candidate rational, then confirm with `sum_of_lyapunov_exponents()`.**

### 6.5 The origami database **[VERIFIED-DOC — outputs verbatim]**

Enormously useful for finding candidate counterexamples without any computation.

```python
from surface_dynamics import OrigamiDatabase, Stratum

D = OrigamiDatabase()
q = D.query(stratum=Stratum([2]), nb_squares=9)
print(q.number_of())      # 2
o1, o2 = q.list()

# comparison-operator form:
q = D.query(('stratum', '=', Stratum([2])), ('nb_squares', '<', 15))
q.cols('nb_squares', 'veech_group_level', 'teich_curve_nu2', 'teich_curve_nu3',
       'teich_curve_genus', 'monodromy_name')
q.show()

D.info(genus=3)
D.max_nb_squares()
D.cols()
```

The 45 queryable columns include `primitive`, `quasi_primitive`, `orientation_cover`,
`hyperelliptic`, `regular`, `genus`, `nb_squares`, `optimal_degree`, `veech_group_index`,
`veech_group_congruence`, `veech_group_level`, `teich_curve_ncusps`, `teich_curve_nu2`,
`teich_curve_nu3`, `teich_curve_genus`, `sum_of_L_exp`, `L_exp_approx`, `min_nb_of_cyls`,
`max_nb_of_cyls`, `min_hom_dim`, `max_hom_dim`, `minus_identity_invariant`, `monodromy_name`,
`monodromy_signature`, `monodromy_index`, `monodromy_order`, `monodromy_solvable`,
`monodromy_nilpotent`, `monodromy_gap_primitive_id`, the `relative_monodromy_*` analogues,
`orientation_stratum`, `orientation_genus`, `pole_partition`, `automorphism_group_order`,
`automorphism_group_name`.

`D.info(genus=3)` reports, e.g., `H_3(4)^hyp : 163 T. curves (up to 51 squares)`, so you know the
coverage limits before you rely on an exhaustive search.

### 6.6 Veech groups in **sage-flatsurf** — a warning

sage-flatsurf 0.6.0 added `S.veech_group()` and `S.affine_automorphism_group()`. **Do not rely on
them for computation.** The module documentation describes `VeechGroup_generic` as a "generic
(currently essentially empty) implementation", and **computing generators raises
`NotImplementedError`**. What does work is the section map:

```python
from flatsurf import translation_surfaces
S = translation_surfaces.square_torus()
A = S.affine_automorphism_group()
M = matrix([[1, 2], [0, 1]])
f = A.derivative().section()(M, check=False)
```

For an actual, finite, presentable Veech group your options are:
1. a **square-tiled surface** → `surface_dynamics`'s `o.veech_group()` (§6.3), which is complete;
2. the **canonicalize test** of §2.5 to check membership of one specific matrix;
3. the GAP package **Origami** (Weitze-Schmithüsen et al., v2.0.1, 2024-07-09), which computes
   Veech groups of general origamis — a separate, non-Sage tool worth knowing about.

### 6.7 Origami generators: `origamis.*` **[VERIFIED — run 2026-09-19, WSL Sage, surface_dynamics 0.7.0 / sage-flatsurf 0.8.0]**

Complete list of public generators in 0.7.0 (`[n for n in dir(origamis) if not n.startswith('_')]`):

```
['CyclicCover', 'EierlegendeWollmilchsau', 'Escalator', 'Heisenberg',
 'Podium', 'ProjectiveLine', 'ShresthaWang', 'Stair']
```

**Refuted: `origamis.Ornithorynque` does not exist.**

```python
origamis.Ornithorynque()
# AttributeError: 'OrigamiGenerators' object has no attribute 'Ornithorynque'
```

It reads as correct — the Ornithorynque is as standard a named example as the Eierlegende
Wollmilchsau — but only the latter has a generator. Build it as `origamis.CyclicCover([1,1,1,3])`
(below), which reports itself as `M_6(1,1,1,3)`.

#### 6.7.1 `origamis.EierlegendeWollmilchsau()` — confirmed, verbatim

```python
ew = origamis.EierlegendeWollmilchsau()
repr(ew)                          # 'Eierlegende Wollmilchsau'
str(ew)                           # '(1,2,3,4)(5,6,7,8)\n(1,5,3,7)(2,8,4,6)'   (1-based)
ew.r_tuple()                      # (1, 2, 3, 0, 5, 6, 7, 4)        0-based
ew.u_tuple()                      # (4, 7, 6, 5, 2, 1, 0, 3)        0-based
ew.nb_squares()                   # 8
ew.stratum()                      # H_3(1^4)
ew.stratum_component()            # H_3(1^4)^c
ew.genus()                        # 3
ew.veech_group().index()          # 1   (Veech group is all of SL(2,Z))
ew.sum_of_lyapunov_exponents()    # 1
```

#### 6.7.2 JSON serialisation: which of these are Sage types

Checked explicitly, because a pipeline that dumps invariants to JSON will crash on the Sage ones.

| call | type | `json.dumps` |
|---|---|---|
| `r_tuple()` / `u_tuple()` entries | **Python `int`** | **OK** |
| `nb_squares()` | **Python `int`** | OK |
| `genus()` | **Python `int`** | OK |
| `veech_group().index()` | **Python `int`** | OK |
| `sum_of_lyapunov_exponents()` | `sage.rings.rational.Rational` | `TypeError: Object of type Rational is not JSON serializable` |
| `monodromy().order()` | `sage.rings.integer.Integer` | `TypeError: Object of type Integer is not JSON serializable` |
| `automorphism_group().order()` | `sage.rings.integer.Integer` | `TypeError` |
| `lattice_of_periods()` / `lattice_of_absolute_periods()` | `tuple` of `Integer` | `TypeError` |
| `stratum()` / `stratum_component()` | `AbelianStratum…` object | not serialisable; use `str()` |

So `r_tuple()`/`u_tuple()` need **no** conversion; `int(...)` / `str(...)` the group orders, the
lattice triples and the Lyapunov sum.

#### 6.7.3 `origamis.CyclicCover(a, M=None)` — confirmed

Signature: `CyclicCover(a, M=None)`. `a` is a quadruple; `M` defaults to `sum(a)`; the result has
**`2*M` squares** (not `2*sum(a)` when `M` is given explicitly).

```python
orn = origamis.CyclicCover([1,1,1,3])          # the Ornithorynque
repr(orn)                         # 'M_6(1,1,1,3)'
orn.nb_squares()                  # 12
orn.stratum()                     # H_4(2^3)
orn.stratum_component()           # H_4(2^3)^even
orn.genus()                       # 4
orn.veech_group().index()         # 1
orn.sum_of_lyapunov_exponents()   # 1
orn.r_tuple()                     # (1, 8, 7, 2, 5, 0, 11, 6, 9, 4, 3, 10)
orn.u_tuple()                     # (7, 6, 5, 0, 11, 10, 9, 4, 3, 2, 1, 8)

cc = origamis.CyclicCover([1,1,1,1])
repr(cc)                          # 'M_4(1,1,1,1)'
cc.nb_squares()                   # 8
cc.r_tuple()                      # (1, 4, 7, 2, 5, 0, 3, 6)
cc.u_tuple()                      # (7, 2, 5, 0, 3, 6, 1, 4)
cc.is_isomorphic(origamis.EierlegendeWollmilchsau())   # True
```

Note that `CyclicCover([1,1,1,1])` is isomorphic to the Eierlegende Wollmilchsau but is **not
given with the same labelling** — the tuples differ. Anything pinned to square indices must pick
one of the two constructions and stay with it.

**Validation, in source order** (`generators.py`, `surface_dynamics/flat_surfaces/origamis/`).
Reproduce this order exactly in any re-implementation; an input failing two tests reports the
first:

```python
if M is None: M = sum(a)
a = list(map(Integer, a))
if len(a) != 4:                  raise ValueError("a should be of length 4")
if any(ai % 2 == 0 for ai in a): raise ValueError("ai should be odd")
if gcd([M] + a) != 1:            raise ValueError("gcd(M,a) should be 1")
if M % 2:                        raise ValueError("M should be even")
if sum(a) % M:                   raise ValueError("the sum of ai should be 0 mod M")
```

Messages verbatim, each triggered:

| call | error |
|---|---|
| `CyclicCover([1,1,1])` | `ValueError: a should be of length 4` |
| `CyclicCover([1,1,1,2])` | `ValueError: ai should be odd` |
| `CyclicCover([3,3,3,3])` | `ValueError: gcd(M,a) should be 1` |
| `CyclicCover([1,1,1,3], M=5)` | `ValueError: M should be even` |
| `CyclicCover([1,1,1,1], M=8)` | `ValueError: the sum of ai should be 0 mod M` |
| `CyclicCover([1,1,1,3], M=4)` | `ValueError: the sum of ai should be 0 mod M` |
| `CyclicCover([1,1,1,3], M=12)` | `ValueError: the sum of ai should be 0 mod M` |

Precedence traps confirmed by running inputs that fail two tests at once:
`[3,3,3,3], M=5` → `M should be even` (**not** the gcd message: `gcd([5,3,3,3]) == 1`, so the gcd
test passes); `[2,2,2,2]` → `ai should be odd` (before gcd); `[1,1,1,1], M=3` → `M should be even`
(before `sum % M`); `[1,1,2]` → the length message wins over the even-entry one.

**An explicit `M` other than `sum(a)` is allowed** whenever `M | sum(a)`, `M` even and
`gcd(M, a) = 1`. Confirmed:

```python
origamis.CyclicCover([1,1,1,1], M=2)   # M_2(1,1,1,1)  4 squares,  H_1(0)
origamis.CyclicCover([1,1,1,1], M=4)   # M_4(1,1,1,1)  8 squares,  H_3(1^4)
origamis.CyclicCover([1,1,1,3], M=2)   # M_2(1,1,1,3)  4 squares,  H_1(0)
origamis.CyclicCover([1,1,1,5], M=8)   # M_8(1,1,1,5) 16 squares,  H_7(3^4)
```

So "M defaults to sum(a)" is **not** "M must be sum(a)"; an enumerator that only ever passes the
default silently skips every proper divisor, including the degenerate torus cases.

**Transcription note.** The construction loop in `generators.py` has an asymmetry that looks like
an upstream typo but determines the labelling: inside the `neg` branch, the two `u` steps test
membership with `if j not in seen and j not in neg:` and then `pos.add(j)`. Copy it verbatim — a
"corrected" version produces a different square indexing.

#### 6.7.4 Invariants on origamis **[VERIFIED — three cases with known answers]**

| | 4-square torus `Origami([1,0,3,2],[2,3,0,1], as_tuple=True)` | 3-square L `Origami([1,0,2],[2,1,0], as_tuple=True)` | Eierlegende Wollmilchsau |
|---|---|---|---|
| `stratum()` | `H_1(0)` | `H_2(2)` | `H_3(1^4)` |
| `genus()` | 1 | 2 | 3 |
| `monodromy()` gens | `(1,2)(3,4), (1,3)(2,4)` | `(1,2), (1,3)` | `(1,2,3,4)(5,6,7,8), (1,5,3,7)(2,8,4,6)` |
| `monodromy().order()` | 4 | 6 | 8 |
| `automorphism_group().order()` | 4 | 1 | 8 |
| `Centralizer(Sym(n), mono).Size()` | 4 | 1 | 8 |
| `is_normal()` | True | False | True |
| `is_regular()` | True | False | True |
| `is_primitive()` | False | True | False |
| `lattice_of_periods()` | `(2, 0, 2)` | `(1, 0, 1)` | **`(1, 0, 1)`** |
| `lattice_of_absolute_periods()` | `(2, 0, 2)` | `(1, 0, 1)` | `(2, 0, 2)` |
| `len(intermediate_covers())` | 5 | 2 | 6 |

- **`monodromy()`** returns a `sage.groups.perm_gps.permgroup.PermutationGroup_generic_with_category`
  — a **group**, not a permutation — generated by `r` and `u`. Its `domain()` is `{1, …, n}`, so it
  is **1-based**, while `r_tuple()`/`u_tuple()` are 0-based. `.order()` is a Sage `Integer`.
  Keyword `relative=True` gives the monodromy relative to the largest torus covered.
- **`automorphism_group()`** is the **centraliser of `⟨r,u⟩` in `S_n`** — the *translation* group
  (affine maps with trivial linear part), **not** the affine group. Confirmed against
  `libgap.Centralizer(SymmetricGroup(n).gap(), S.subgroup(o.monodromy().gens()).gap()).Size()`:
  orders agree (4, 1, 8) in all three cases. Returns a `PermutationGroup_subgroup_with_category`
  inside `Sym(n)`; `.order()` is a Sage `Integer`. The docstring says this explicitly:
  *"corresponds combinatorially to the centralizer of the group generated by the permutations `r`
  and `u`"*.
- **`is_normal()` vs `is_regular()`**: documented differently (`is_normal` = the defining subgroup
  of `F_2` is normal; `is_regular` = `Aut` acts transitively on squares) but **equivalent**, and
  both equal `|automorphism_group()| == nb_squares()`. Verified to agree on all three cases.
- **`lattice_of_periods()` / `lattice_of_absolute_periods()`** return a **triple of Sage
  `Integer`s** `(a, t, u)` for the standard basis `((a,0), (t,u))` with `0 <= t < a`, `0 < u`.
  `lattice_of_periods` uses holonomies of **saddle connections** (i.e. relative periods);
  `lattice_of_absolute_periods` uses holonomies of **loops**. They differ: on the EW,
  `lattice_of_periods() == (1,0,1)` while `lattice_of_absolute_periods() == (2,0,2)`. If you want
  the "is this a proper torus cover" index-2 signal on the EW, it is the **absolute** one.
- **`is_primitive()`** returns a Python `bool`; documented as "does not cover another origami" /
  "the monodromy action has no non-trivial block".
- **`intermediate_covers()`** returns a **`list` of `Origami_dense_pyx`**, including the trivial
  1-square cover and the origami itself (L: `[1-square, L]`; EW: 6 entries ending in the EW).
  Optional `degree=` argument filters by degree.

#### 6.7.5 The twists relabel **[VERIFIED — the SL(2,Z) relabelling trap, demonstrated]**

Signature is `horizontal_twist(width=1, cylinder=None)` / `vertical_twist(width=1, cylinder=None)`
— **the parameter is named `width`, not `k`** (positional use is fine). `horizontal_twist` returns
the origami `(r, r^{-width} u)`; `cylinder=i` twists only the band containing `i` and is then
**not** an SL(2,R) deformation.

Take `S = h(1) v(-1) h(1)`, whose matrix is `[[0,1],[-1,0]]`, of order 4, so `S^4 = I`. On the
3-square L:

```python
L = Origami([1,0,2], [2,1,0], as_tuple=True)
L.r_tuple(), L.u_tuple()                     # (1, 0, 2)  (2, 1, 0)

S1 = L.horizontal_twist(1).vertical_twist(-1).horizontal_twist(1)
S1.r_tuple(), S1.u_tuple()                   # (0, 2, 1)  (1, 0, 2)

S4 = the same three-step word applied four times
S4.r_tuple(), S4.u_tuple()                   # (0, 2, 1)  (1, 0, 2)
S4.is_isomorphic(L)                          # True
tuple(S4.r_tuple()) == tuple(L.r_tuple())    # False   <-- relabelled
```

So a word whose matrix is the **identity** comes back isomorphic but with **different `r_tuple()`
and `u_tuple()`**. The relabelling is not uniform: on the Eierlegende Wollmilchsau the same
`S^4` word returns `r_tuple() == (1,2,3,0,5,6,7,4)` and `u_tuple() == (4,7,6,5,2,1,0,3)`,
i.e. **unchanged** — so "my test origami came back with the same tuples" proves nothing.

Consequences for a search pipeline:

- Anything keyed on **square indices** (a marked pair of squares, a tracked cone-point corner)
  must be re-identified after every twist, or applied one generator at a time with the labels
  transported explicitly.
- Label-free invariants survive: on the L, `lattice_of_absolute_periods()` stayed `(1,0,1)`,
  `automorphism_group().order()` stayed 1, `is_normal()` stayed `False` across `S^1` and `S^4`.
  That is consistent with them being SL(2,Z)-orbit invariants, but **three points on one origami
  is a consistency check, not a proof** — the mathematical argument still has to be made
  separately.

---

### 12.5 `Origami` constructor forms and index base — **Confirmed** (both targets)

Both constructor forms exist in 0.7.0 and give the *same* object:

```python
from surface_dynamics import Origami
o  = Origami('(1,2,3)', '(1,3)')                    # 1-based cycle strings
o2 = Origami([1, 2, 0], [2, 1, 0], as_tuple=True)   # 0-based images
o2 == o                 # True
```

The 3-square L, read off the installed library:

| call | value | base |
|---|---|---|
| `repr(o)` | `(1,2,3)` / `(1,3)(2)` | **1-based** |
| `o.r()` | `(1,2,3)` (a `SymmetricGroupElement`) | **1-based** |
| `o.u()` | `(1,3)` | **1-based** |
| `o.r_tuple()` | `(1, 2, 0)` | **0-based** |
| `o.u_tuple()` | `(2, 1, 0)` | **0-based** |
| `o.nb_squares()` | `3` | |
| `o.stratum()` | `H_2(2)` | |
| `o.genus()` | `2` | |
| `o.is_reduced()` | `True` | |

Confirms the CLAUDE.md trap: **1-based in the string/permutation form, 0-based in
`r_tuple()` / `u_tuple()`.** Sanity check on the 0-based tuples: `r_tuple()[0] == 1`
says square 0 → square 1, matching the 1-based cycle `(1,2,3)` sending 1 → 2.
