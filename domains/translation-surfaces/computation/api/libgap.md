# libgap from Sage (§12.2, §12.6, §12.7, §12.8)

Split from `api-recipes.md` on 2026-09-24; section numbers are the old ones, so a citation like "api-recipes §6.7.1" still resolves. Index: `INDEX.md`.

### 12.2 `from sage.libs.gap.libgap import libgap` as the *first* Sage import — **Refuted**

```python
from sage.libs.gap.libgap import libgap        # plain `python`, nothing Sage imported yet
```
```
ImportError: cannot import name 'is_MPolynomial' from partially initialized module
'sage.rings.polynomial.multi_polynomial' (most likely due to a circular import)
(.../envs/flatsurf/lib/python3.12/site-packages/sage/rings/polynomial/multi_polynomial.cpython-312-x86_64-linux-gnu.so)
```
Chain: `libgap.pyx` → `gap/util.pyx` → `gap/element.pyx` → `permgroup_element.pyx`
→ `multi_polynomial.pyx` → `multi_polynomial_ring.py` → `multi_polynomial_element.py`.
This is a **Sage 10.7 packaging bug under a plain `python` interpreter**, not a missing
feature: nothing is wrong with libgap itself. The deep dotted path is exactly what a
confident memory or an old tutorial produces, so it belongs in the pitfall list.

**What the library offers instead — Confirmed (both targets):**
```python
from sage.all import libgap                    # 1.4 s
# or, if you need the submodule path for some other reason:
import sage.all
from sage.libs.gap.libgap import libgap        # 2.1 s — works once sage.all is loaded
```
Known case: `libgap.eval('Order(SymmetricGroup(5))')` → `120` on both targets.
Rule: **import `sage.all` (or use `from sage.all import …`) before any
`sage.libs.*` / `sage.rings.*` submodule import** in a script run by `python`
rather than `sage`.

### 12.6 The libgap cluster for origami monodromy groups — **Confirmed** (WSL, SageMath 10.7 / sage-flatsurf 0.8.0 / surface_dynamics 0.7.0), probed 2026-09-19 (api-check)

All calls below use `from sage.all import libgap` (§12.2). Known cases throughout:
the 3-square L `Origami([1,2,0],[2,1,0], as_tuple=True)` (monodromy S_3),
the 4-square torus `Origami([1,0,3,2],[2,3,0,1], as_tuple=True)` (monodromy Klein
four, regular), and `origamis.EierlegendeWollmilchsau()` (8 squares, monodromy
Q_8, regular and normal in S_8).

**Building the monodromy group from 0-based tuples.** `r_tuple()`/`u_tuple()` are
0-based (`r_tuple()[i]` = image of `i`); `libgap.PermList` wants a 1-based image
list. The conversion is:

```python
def to_gap_perm(tup0based):
    n = len(tup0based)
    return libgap.PermList([tup0based[i] + 1 for i in range(n)])

r = to_gap_perm(o.r_tuple())
u = to_gap_perm(o.u_tuple())
G = libgap.Group(r, u)
```

Checked explicitly on the L: `r_tuple() == (1, 2, 0)` gives `PermList([2, 3, 1])`,
which prints as `(1,2,3)` — matching `o.r()` (`(1,2,3)`, 1-based) exactly, so the
`+1` shift is the whole conversion, nothing else changes. `G.Size()` reproduces
the known monodromy order on all three: **L → 6, torus → 4, EW → 8**
(`int(G.Size())` in each case; `libgap.SymmetricGroup(3).Size()` → `6` confirms
`SymmetricGroup(n)` too).

**`libgap.Centralizer(Sn, G)`** — signature `Centralizer(Sn, G)` with
`Sn = libgap.SymmetricGroup(n)`, returns a `GapElement` group. `.Size()` matches
`Origami.automorphism_group().order()` on all three cases exactly:

| case | `Centralizer(Sn,G).Size()` | `automorphism_group().order()` | match |
|---|---|---|---|
| L | 1 | 1 | True |
| torus | 4 | 4 | True |
| EW | 8 | 8 | True |

**Centraliser elements back into Python as 0-based tuples** — there is no
`.OnPoints` method on a `GapElement_Permutation`; the working call is the global
GAP function applied as `libgap.OnPoints(point, perm)` (point 1-based in, image
1-based out):

```python
def gap_perm_to_0based_tuple(g, n):
    return tuple(int(libgap.OnPoints(i + 1, g)) - 1 for i in range(n))

elts = list(C.Elements())              # C = libgap.Centralizer(Sn, G)
[gap_perm_to_0based_tuple(g, n) for g in elts]
```
On the L (trivial centraliser): `elts = [()]`, giving `(0, 1, 2)` — the identity,
correctly. `g.OnPoints(i+1)` (method-call form) **fails**:
```
TypeError: int() argument must be a string, a bytes-like object or a real number,
not 'sage.libs.gap.element.GapElement_Permutation'
```
— `OnPoints` is not a bound method of the permutation element; use the
`libgap.OnPoints(pt, perm)` free-function form.

**`libgap.IsTransitive(G, dom)` / `libgap.IsPrimitive(G, dom)`.** Both
`libgap.eval("[1..%d]" % n)` and `libgap(list(range(1, n+1)))` build the same
domain (`dom_eval == dom_call` → `True`); either works, `eval` is marginally
simpler to build in a loop. Confirmed: L → `IsTransitive` `true`, `IsPrimitive`
`true` (3 points, S_3, primitive as required); 4-square torus → `IsTransitive`
`true`, `IsPrimitive` `false` (imprimitive, as required).

**`libgap.AllBlocks(G)`.** Return shape is a `GapElement_List` of 1-based-point
lists, each block containing point 1. On the L (primitive): `AllBlocks(L)` →
`[ ]`, empty — correct, a primitive group has no nontrivial block. On the
4-square torus: `AllBlocks(G)` → `[ [ 1, 2 ], [ 1, 3 ], [ 1, 4 ] ]`, i.e. 0-based
`(0,1)`, `(0,2)`, `(0,3)` after the `-1` shift. Hand check: the Klein four-group
acting regularly on 4 points has exactly 3 nontrivial proper block systems, one
per order-2 subgroup — `{0,1}|{2,3}`, `{0,2}|{1,3}`, `{0,3}|{1,2}` — and
`AllBlocks` returned one representative block per system, each containing point
1 as documented. **This case cannot settle the "whole lattice vs. minimal
systems only" question** the spec raises: Klein four has only one level between
singletons and the whole set, so "all nontrivial block systems" and "all minimal
block systems" coincide here. `AllBlocks` is documented upstream as returning
representatives of *all* block systems (not just minimal ones), which this
result is consistent with but does not distinguish from the buggy
`blocks_all()`-only-minimal behaviour the spec warns about, since Klein four's
lattice has no proper level between the minimal block systems and the whole set.

**Settled on a group with a longer subgroup chain** (2026-09-19 follow-up): the
cyclic group of order 8, `G = <(1,2,3,4,5,6,7,8)>` acting regularly on 8 points,
whose subgroup lattice is the chain `1 < C_2 < C_4 < C_8`, giving two proper
nontrivial block systems by hand — blocks of size 2 (orbits of the order-4
subgroup `<g^2>`: `[[1,3,5,7],[2,4,6,8]]`, only the size-2 system is *minimal*)
and blocks of size 4 (orbits of the order-2 subgroup `<g^4>`:
`[[1,5],[2,6],[3,7],[4,8]]`). `libgap.AllBlocks(G)` on this group:
```python
gen = libgap.PermList(list(range(2, 9)) + [1])   # (1,2,3,4,5,6,7,8)
G = libgap.Group(gen)
libgap.AllBlocks(G)
# [ [ 1, 3, 5, 7 ], [ 1, 5 ] ]
```
**Returns representatives of both systems** — the size-4 block `[1,3,5,7]` (0-based
`(0,2,4,6)`) *and* the size-2 block `[1,5]` (0-based `(0,4)`), both containing
GAP-point 1 as on the torus. **Verdict: `AllBlocks` gives the whole block
lattice (all proper nontrivial block systems), not only the minimal ones** — the
spec's recommendation to use `libgap.AllBlocks(G)` in place of a `blocks_all()`
that returns only minimal systems is **confirmed correct** on a case built
specifically to distinguish the two behaviours. The earlier torus check remains
useful as a second, independent data point but was never sufficient on its own.

Two further checks on this same cyclic-8 group, both also confirmed:
`libgap.IsTransitive(G, dom)` → `true`, `libgap.IsPrimitive(G, dom)` → `false`
(imprimitive, consistent with having nontrivial blocks); `libgap.Stabilizer(G,
1).Size()` → `1` (regular action ⇒ trivial point stabiliser) and
`libgap.Orbits(H, dom)` → `[ [1], [2], [3], [4], [5], [6], [7], [8] ]`, rank 8 —
a second regular-action data point alongside the Eierlegende Wollmilchsau (§12.6
above), where the same pattern (trivial stabiliser, rank = n) held.

**`libgap.Stabilizer(G, 1)` and `libgap.Orbits(H, dom)`** — rank of the action
(1-based point 1 throughout). On the L: `Stabilizer(G,1).Size()` → `2`,
`Orbits(H, dom)` → `[ [ 1 ], [ 2, 3 ] ]`, rank 2 — the fixed point and the other
two, exactly as expected. On the EW (Q_8 regular, so the stabiliser of any point
is trivial): `Stabilizer(G,1).Size()` → `1`, `Orbits(H, dom)` → eight singleton
orbits, rank 8.

**`libgap.AbelianInvariants(H)`** — returns a `GapElement_List` of integers, the
invariant factors of $H^{\mathrm{ab}}$ (read as a period lattice: e.g. `[2]` on a
stabiliser reads as $\mathbb{Z}/2$). On `Stab_L(1)` (order 2, cyclic): `[ 2 ]`.
On `Stab_EW(1)` (trivial group): `[ ]`, the empty list — correctly, the trivial
group has no invariant factors.

**`libgap.RepresentativeAction(G, libgap([g1,g2]), libgap([h1,h2]), libgap.OnTuples)`**
— simultaneous conjugacy of an ordered pair. Signature confirmed:
`RepresentativeAction(G, seq1, seq2, action)`, both `seq1`/`seq2` wrapped with
`libgap([...])` and the action passed as `libgap.OnTuples`.

Positive case on the EW (`G` = Q_8 acting regularly, `g1=r`, `g2=u` its two
generators): picked a genuine non-identity `h` in `G`, formed the honestly
conjugate target pair `t1 = h^-1*g1*h`, `t2 = h^-1*g2*h`, then
`RepresentativeAction(G, [g1,g2], [t1,t2], OnTuples)` returned
`(1,4,3,2)(5,8,7,6)` — a `GapElement_Permutation`, verified by hand to satisfy
`conj^-1 * g1 * conj == t1` and `conj^-1 * g2 * conj == t2` (`True`). This
conjugator need not equal `h`; the check confirms it is *a* valid one.

Negative case: `RepresentativeAction(G, [g1,g1], [g1,g2], OnTuples)` — the
identical pair `(g1,g1)` cannot be simultaneously conjugate to the distinct pair
`(g1,g2)` since conjugation is injective and `g1 != g2`. Returned `fail`, a
`GapElement_Boolean`.

**Comparing `fail` from Python** — the critical check, since getting this wrong
silently breaks the pruning step:
```python
fail_const = libgap.eval("fail")
res == fail_const     # True for the negative case, False for the positive one
res is None            # False in BOTH cases — fail is a GapElement_Boolean, not None
bool(res)              # True for the positive (conjugator) case, False for `fail`
```
So `res == libgap.eval("fail")` and `bool(res)` (`False` for `fail`, `True` for
any actual permutation) both work; **`res is None` never works** — `fail` is a
distinct `GapElement_Boolean`, never Python `None`. Note also, as a side effect
observed while building the negative case: single-element
`libgap.RepresentativeAction(G, r, u, libgap.OnPoints)` on the EW also returned
`fail` — `r` and `u` (the two Q_8 generators used here) sit in different
conjugacy classes of Q_8 ($\{i,-i\}$ vs. $\{j,-j\}$ in quaternion notation), so
they are not even individually conjugate in this pair; the pair test above is
still the correct example of "positive pair when a genuine non-identity
conjugator exists, negative pair when the two sequences cannot possibly match".

**GAP integers into Python / JSON.** `.Size()` (and `AbelianInvariants` entries)
come back as `sage.libs.gap.element.GapElement_Integer`, **not**
JSON-serialisable:
```
TypeError: Object of type GapElement_Integer is not JSON serializable
```
`int(x)` converts cleanly to a plain Python `int`, which **is** serialisable
(`json.dumps(int(G.Size()))` → `"8"`). Every value pulled out of libgap for the
JSON pipeline needs an explicit `int(...)` (or, for lists like `AllBlocks`, a
list comprehension of `int(...)` over the entries).

**Timing.** On the EW (8 points): building the group from `PermList`/`Group` is
effectively instant (~0.0001 s) and `AllBlocks(G)` ~0.0007–0.0013 s. At this
cost, hundreds of members in a sweep is negligible against Sage's own
per-process startup (~1.4–4 s, §12.2/12.3); the sweep's wall time is dominated by
process/import overhead, not by GAP group theory, unless a much larger `n` or a
richer block lattice changes this.

**pyflatsurf** — this whole cluster (`libgap.PermList`, `.Group`,
`.SymmetricGroup`, `.Centralizer`, `.IsTransitive`, `.IsPrimitive`,
`.AllBlocks`, `.Stabilizer`, `.Orbits`, `.AbelianInvariants`,
`.RepresentativeAction`) plus `surface_dynamics.Origami`/`origamis` was reached
through `from sage.all import libgap` and `from surface_dynamics import Origami,
origamis` only — no `flatsurf`/`pyflatsurf` import anywhere in this probe,
consistent with §12.4 (`pyflatsurf` segfaults) not being in the path.

---

### 12.7 Re-probe 2026-09-20 (api-check) — corrections and additions to 12.6

Five independent `api-prober` runs re-derived the 12.6 cluster from scratch in WSL
Sage 10.7 / sage-flatsurf 0.8.0 / surface_dynamics 0.7.0, two of them also on a second
target. **Everything in 12.6 held**, with one wording correction and four additions below.

**Cite this file by path, not by name.** On 2026-09-20 a stale synced copy of the old
single-file recipes (no §12) led three notes to retract correct citations; the record
of the copies is kept in the Scientist home's environment notes.


#### 12.7.1 Correction to 12.6: `g.OnPoints(pt)` does not raise

12.6 above says the method form "fails" and quotes a `TypeError`. The recipe it gives
(use the free function) is right, but the failure mode described is not what happens,
and the difference matters because the real one is silent.

`g.OnPoints(pt)` **raises nothing**. It returns `g**pt`: libgap's method sugar resolves
to GAP's `OnPoints(g, pt)`, which is the power operator `g^pt`, not the point-image
lookup. Checked term by term on `g = (1,2,3,4,5,6,7,8)` for `pt = 1..8`: `g.OnPoints(pt)
== g**pt` every time, no exception ever. On `g = libgap.PermList([2,1,4,3])`,
`g.OnPoints(2)` returns `()`.

The `TypeError` quoted in 12.6 is `int()`'s, one step later:
```
int(g.OnPoints(2))
TypeError: int() argument must be a string, a bytes-like object or a real number,
not 'sage.libs.gap.element.GapElement_Permutation'
```
So the mistake is caught only if `int()` is applied immediately. Store the value first
and you are holding a wrong permutation with nothing raised anywhere. The free-function
form `int(libgap.OnPoints(i + 1, g)) - 1` remains correct and is unchanged.

Round trips re-verified exactly: the 4-square torus (`(1,0,3,2)` out and back), and the
EW, `r_tuple() = (1,2,3,0,5,6,7,4)`, `u_tuple() = (4,7,6,5,2,1,0,3)`, both generators
through `PermList` -> `OnPoints` -> 0-based tuple unchanged, with `Group(gr,gu).Size()`
-> `8` confirming the monodromy independently.

#### 12.7.2 Addition: a real separating case for `RepresentativeAction`

12.6's negative case is `RepresentativeAction(G, [g1,g1], [g1,g2], OnTuples)`, which is
impossible for the trivial reason that conjugation is injective. It therefore does not
distinguish **simultaneous** conjugacy from independent elementwise conjugacy, which is
the property the pruning step actually relies on.

The case that does, in `S_4`: `g1 = (1,2)`, `g2 = (3,4)`, `h1 = (1,2)`, `h2 = (1,3)`.
Each pair is conjugate elementwise -- all transpositions are conjugate in `S_4`, and the
single-element calls return non-`fail` permutations:
```
RepresentativeAction(S4, g1, h1) = ()
RepresentativeAction(S4, g2, h2) = (1,2,4,3)
```
But no single tau can do both: tau must fix `{1,2}` setwise, hence send `{3,4}` to
itself, while `g2 -> h2` demands `tau({3,4}) = {1,3}`. Provable by hand, and the
simultaneous call agrees:
```
RepresentativeAction(S4, [g1,g2], [h1,h2], OnTuples) = fail   GapElement_Boolean
```
Any future re-probe of this call should use this pair, not the `(g1,g1)` one.

The truthiness table of 12.6 re-confirmed on the EW, all six values:
```
res_pos  is None : False      res_fail is None : False
res_pos  == fail : False      res_fail == fail : True
bool(res_pos)    : True       bool(res_fail)   : False
```
`is None` cannot discriminate; `== libgap.eval("fail")` and `bool(...)` both can.

#### 12.7.3 Addition: the pitfall that nearly poisoned 12.7.2

Hand-built EW generator tuples, guessed rather than taken from the library, produced
`Warning: the origami is not connected` and a monodromy group of order **4**, not 8.
Nothing crashed; the script ran clean and the numbers looked plausible. It was caught
only by asserting `G.Size() == 8` against the independently known answer.

**Assert the known invariant, not just that the call returned.** Use
`origamis.EierlegendeWollmilchsau()` rather than transcribing tuples.

#### 12.7.4 Addition: `AllBlocks` cross-checked against subgroup orbits

12.6's `AllBlocks` entry re-confirmed, and the whole-lattice claim cross-checked by a
route independent of `AllBlocks` itself. On the cyclic group of order 8, regular action:
```
gen: (1,2,3,4,5,6,7,8)      IsPrimitive(G8,dom8): false
raw AllBlocks(G8): [ [ 1, 3, 5, 7 ], [ 1, 5 ] ]        sizes: [2, 4]
Orbits of <gen^4> (order 2): [ [1,5],[2,6],[3,7],[4,8] ]      -> matches the size-2 rep
Orbits of <gen^2> (order 4): [ [1,3,5,7],[2,4,6,8] ]          -> matches the size-4 rep
```
Both levels returned, so the whole block lattice and not only the minimal systems.

**The four-square torus cannot settle this and a probe using only it proves nothing**:
Klein four has no subgroup level between minimal and whole, and `AllBlocks` there returns
only three size-2 systems. Confirmed by running both.

`int()` coercion re-confirmed on entries of both `AllBlocks` and `AbelianInvariants`:
```
json.dumps(raw_entry) -> TypeError: Object of type GapElement_Integer is not JSON serializable
json.dumps(int(raw_entry)) -> 2
```

#### 12.7.5 Addition: import topology and timing on a remote target

12.1-12.4 re-confirmed on **both** targets, checking `sys.modules` after each
import rather than only that the import succeeded:

| | WSL | remote server |
|---|---|---|
| `surface_dynamics` pulls in `pyflatsurf`/`cppyy`/`cling` | `[]` | `[]` |
| `import flatsurf` pulls them in | `[]`, 0.125 s | `[]`, 0.106 s |
| `import pyflatsurf` | segfault, `returncode -11` | segfault, `returncode -11` |

`-11` is SIGSEGV, the same signal as the exit code 139 (128+11) recorded in 12.4. The
cling stack ends in `CreateInterpreter` / `TROOT::InitInterpreter()` on both machines.
(Superseded 2026-09-22: the cause was the missing `conda activate`; see the resolution
at the head of 12.4.)

**Timing, and it is not what 12.6 assumed.** `import surface_dynamics`: WSL **5.5 s**;
the remote server **64.8 s cold, 14.7 s warm**, on an NFS-backed env. The timer sat inside
the remote process, bracketing the import statement alone, so none of this is ssh
overhead. 12.6's timing note above cites "~1.4-4 s" of per-process startup; that is a
local-disk figure. On a network-filesystem env the steady-state floor is roughly
**15 s per process**, and the first launch after a quiet period pays about a minute. The
conclusion 12.6 draws is unchanged but much stronger: batch a sweep into one process.

An env installed under a non-default conda prefix must be given that prefix explicitly;
otherwise the runner reports `no python in .../miniforge3/envs/flatsurf`, which reads as
"environment not installed" and is not.

#### 12.7.6 Addition: `RepresentativeAction` in a subgroup, and conjugator non-uniqueness — Confirmed, WSL only, probed 2026-09-23 (api-check)

Question under test: does `libgap.RepresentativeAction(D, src, tgt, libgap.OnTuples)`
decide simultaneous conjugacy of tuples *in a subgroup `D`, not `S_n`*? (The probe was
made for one project's wrapper around this call; that record is kept with the project.)

**0. Existence/signature.** `hasattr(libgap, 'RepresentativeAction')` → `True`.
`inspect.signature` fails (`ValueError: no signature found for builtin
<method-wrapper '__call__' of ... GapElement_Function ...>`) — libgap functions carry
no Python-introspectable signature; the call shape has to come from GAP's own help or,
as here, from running it. `help(libgap.RepresentativeAction)` prints only the generic
`GapElement_Function.__call__` docstring (`*args -> GapElement`), no argument names —
confirms existence and callability but not arity; arity is pinned by 12.6's worked
examples and reconfirmed by this run.

**1. Fresh Q_8 hand-derived negative case: `(r,u)` vs `(u,r)`.** Using
`origamis.EierlegendeWollmilchsau()`'s tuples directly (`r = (1,2,3,0,5,6,7,4)`,
`u = (4,7,6,5,2,1,0,3)`, 0-based; `r=i`, `u=j` in quaternion notation), `D = <r,u>`,
`D.Size() = 8`. Hand reasoning: $Q_8$'s conjugacy classes are $\{1\},\{-1\},\{i,-i\},
\{j,-j\},\{k,-k\}$ (inner automorphisms act as $\mathrm{Inn}(Q_8)\cong V_4$, fixing
each cyclic subgroup $\langle i\rangle,\langle j\rangle,\langle k\rangle$ setwise and at
worst inverting its generator). Any conjugate of $i$ lies in $\{i,-i\}$, and $j\notin$
that class, so no single conjugator can send $i\mapsto j$ — the *ordered pair*
$(i,j)\to(j,i)$ is therefore not simultaneously conjugate, by the same obstruction
already used for a single element, but now stated for the pair as the task asked.
Ran:
```
RepresentativeAction(D,[R,U],[U,R],OnTuples) = fail   type: GapElement_Boolean
  == fail_const? True   is None? False   bool? False
```
Matches the hand prediction.

**2. Fresh Q_8 hand-derived positive case: `(r,u)` vs `(r^-1,u^-1)`, via `k = ij`.**
Hand computation from the quaternion relations $ij=k$, $ji=-k$, $ki=j$, $kj=-i$:
$k\,i\,k^{-1} = k\,i\,(-k) = -(k\,i\,k) = -(j\,k) = -i$ (using $jk=i$), and
$k\,j\,k^{-1} = k\,j\,(-k) = -(k\,j\,k) = -((-i)\,k) = i\,k = -j$ (using $ik=-j$). So
conjugation by $k$ sends $(i,j)\mapsto(-i,-j) = (i^{-1},j^{-1})$ — the pair **is**
simultaneously conjugate to its elementwise inverse. Ran, with `Rinv`, `Uinv` the inverses of `r`, `u` (inversion does not depend on the
composition convention):
```
RepresentativeAction(D,[R,U],[Rinv,Uinv],OnTuples) = (1,6,3,8)(2,5,4,7)   GapElement_Permutation
  == fail_const? False   is None? False   bool? True
  res_pos^-1 * R * res_pos == Rinv ? True
  res_pos^-1 * U * res_pos == Uinv ? True
```
Confirms both the GAP convention $g^x = x^{-1}gx$
and the hand-derived answer: a genuine conjugator exists, as predicted, and it is a
GAP `GapElement_Permutation` satisfying the GAP-sense relation directly.

**3. The conjugator is not unique: assert the relation, not the element.** In `S_3`,
with `g3 = (1,2,0)` (the 3-cycle $(0\,1\,2)$, 0-based) and target `(2,0,1)` (its
conjugate by the transposition $(0\,1)$), GAP returned a different conjugator:
```
RepresentativeAction(S3, G3, tgt3, OnPoints) = (2,3)     # GAP 1-based cycle notation
  x3 as 0-based tuple: (0, 2, 1)
```
This is **not** a refutation: `g3` has centraliser `<g3>` of order 3 in `S_3`, so the
conjugator solving `g3^x = target` is determined only up to `C_{S_3}(g3)`. Checked:
`x3^-1 * G3 * x3 == tgt3` → **True**. **Never assert `h == (the constructed
conjugator)`; only assert the conjugation relation holds.** And mind the convention:
GAP's is $g^x = x^{-1} g x$, so a wrapper exposing $h g h^{-1}$ must invert GAP's answer.

**4. Timing at `|G| ~ 10^4`.** Built
`P = Image(IsomorphismPermGroup(DirectProduct(CyclicGroup(100), CyclicGroup(100))))`,
confirmed `P.Size() = 10000`, `IsPermGroup(P)` `True`, 4 generators. 1000 calls to
`libgap.RepresentativeAction(P, [g1,g2], [g1,g2], OnTuples)` (trivial positive case,
`src == tgt`, so the identity conjugator is found immediately — a **lower-bound**
timing, not a worst case; a genuinely hard search in a group this size could cost
more) took **0.0054 s total, 0.0000054 s/call**. Consistent with 12.6's "hundreds of
members negligible against Sage's own process startup" conclusion — even at `|G| ~
10^4`, `RepresentativeAction` itself is not the bottleneck; process/import overhead
(5.5 s WSL / 15-65 s on the remote target, per 12.7.5) dominates by four to seven orders of
magnitude. **Not a worst-case bound**: a pair genuinely requiring backtracking search
through a 10^4-element group could be far slower; this timing only establishes the
floor.

**Verdict: Confirmed.** `RepresentativeAction(D, src, tgt, libgap.OnTuples)` decides
simultaneous conjugacy *within the subgroup `D`* (not `S_n`); the returned conjugator,
while not unique when the centraliser of the source tuple in `D` is nontrivial, always
satisfies GAP's relation $\mathrm{src}^x = \mathrm{tgt}$.

---

### 12.8 Multi-statement GAP function definitions through `libgap` — refutation and fix, probed 2026-09-20 (api-check)

**What failed.** `f = libgap.eval(source)` in a queued Sage 10.7 job, where `source` is a
multi-line `function(gens, maxStates, maxGroup) local ...; ... end;` block. (The job
record is kept with the project that ran it.)

**Refuted: `libgap.eval(source)` of a `function ... end;` block, trailing `;` included.**
```
sage.libs.gap.util.GAPError: can only evaluate a single statement
```
Reproduced on two real multi-line GAP function sources, not a toy (`local`
declarations, `for`/`while` loops, `if`/`Error`, `end;` with trailing newline): both raise
the identical `GAPError`. `libgap.function_factory(source)` with the trailing `;` left in
raises the **same** `GAPError` — `function_factory` is "almost the same as calling
`libgap.eval(function_name)`" (its own docstring, `sage/libs/gap/libgap.pyx:431`) and
inherits the restriction; it does not sidestep it. Also refuted: assigning inside GAP,
`libgap.eval("name := function(...) ... end;;")`, raises the same `GAPError` — the
statement-count restriction applies to the whole string handed to `eval`, before any
assignment or factory logic sees it, so wrapping does not help.

**Confirmed replacement.** Strip the string with `.strip()` and drop exactly the final
`;` that follows the closing `end`, then hand the result to either `libgap.eval` or
`libgap.function_factory` — both work once that one semicolon is gone:
```python
def _strip_trailing_semicolon(source):
    s = source.strip()
    if s.endswith(";"):
        s = s[:-1]
    return s

f = libgap.function_factory(_strip_trailing_semicolon(source))
```
`libgap.function_factory(str) -> GapElement_Function`, confirmed by
`inspect.signature` failing (it is a Cython builtin, `ValueError: no signature found for
builtin`) and its docstring read directly instead: `Gap.function_factory(self,
function_name)`, "the name of a GAP function" — the doc line describes the intended use
(wrapping an already-named GAP function) but the probe shows it accepts and evaluates a
full function-literal source string exactly like `eval` does, once that string is a
single GAP statement. `libgap.eval(_strip...(source))` also returns a
`GapElement_Function` and is equally usable; `function_factory` is not required, only the
semicolon fix is. Both were run on the two unmodified production strings (not a
simplified stand-in) and both succeeded:
```
=== SOURCE_A repr tail: ';\nend;'
SOURCE_A libgap.eval(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'>
SOURCE_A function_factory(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'> True
=== SOURCE_B repr tail: ';\nend;'
SOURCE_B libgap.eval(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'>
SOURCE_B function_factory(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'> True
```

**Known-answer case, genuinely multi-statement** (a `local` block, a `for` loop, list
accumulation, a `return` of a list) run on `origamis.EierlegendeWollmilchsau()` with
`assert Size() == 8` checked *before* trusting anything, per the pitfall recorded in
12.7.3:
```
Group(r,u).Size() = 8          # assert passed
function_factory call result: [ [ 1, 4, 2, 4, 4, 4, 4, 4 ], 27, 8 ]
element orders sorted: [1, 2, 4, 4, 4, 4, 4, 4]
order histogram: Counter({4: 6, 1: 1, 2: 1})
```
This is the quaternion group `Q8`'s exact element-order profile — one identity (order 1),
one central involution (order 2), six elements of order 4 — an independently known
answer, not merely a plausible-looking one.

**Two usage questions:**

- **Callable with plain `int` args and a `libgap` list of generators**, i.e.
  `f(gens, int(max_states), int(group_limit))` —
  **confirmed**. Ran `f_ff(gens, int(100), int(10000))` where `gens = libgap([r, u])`;
  returned the same `GapElement_List` as the non-`int`-cast call. libgap coerces Python
  `int` to GAP integers transparently at the call boundary; no `libgap(...)` wrapping of
  the ints is needed.
- **Caching the returned function in a module-level dict across calls in one
  Sage process** — **confirmed safe**, at least for repeated calls with fresh arguments.
  Called the same cached `GapElement_Function` twice with identical arguments (results
  agreed) and once with different arguments (returned a distinct, correct result with no
  cross-call state bleed). The GAP function's `local` variables are re-initialised on
  each GAP-level call, as GAP semantics require, and the Sage-side wrapper is a thin
  handle to the GAP object, not a fresh recompilation — nothing was observed to leak
  between calls to the same cached function.

Probed against **sage-flatsurf 0.8.0 / surface_dynamics 0.7.0 / SageMath 10.7**, WSL,
2026-09-20.
