# Extracted (Q2) search record (destined for Slope1 `notes/`)

(The imported copy under `_import/` was removed once distributed; the original is unchanged in `C:\Work\Math\claude-flatsurf\domain\`.)

Verbatim passages cut from the old `flatsurf-computation` API recipe file `libgap.md`
when it became the domain pack's `computation/api/libgap.md` (Group B, 2026-09-28).
They record how the (Q2) search's own code (`fslab/christoffel/gapinv.py`,
`gap_reverify.py`, the `_BFS_GAP` / `_COVER_GAP` strings, lingo job
`20260920-123729`) was checked against libgap: a research record of the Slope1
(Q2) search, not an API fact. The pack keeps the generic libgap findings
(`RepresentativeAction` in a subgroup, `fail` handling, conjugator non-uniqueness,
the multi-statement `eval` refutation and its fix) in neutral wording. Line numbers are
those of the imported file
(`_import/flatsurf/domain/flatsurf-computation/references/api/libgap.md`).

Group B did not write into Slope1illuminationResearch (read-only in this run); moving
this file into Slope1's `notes/` (or its successor, the journal/directions of the
notebook redesign) is left to the Group D builder.

### `libgap.md` lines 33-33 — §12.6 heading ('The libgap cluster for the (Q2) search')

````markdown
### 12.6 The libgap cluster for the (Q2) search — **Confirmed** (WSL, SageMath 10.7 / sage-flatsurf 0.8.0 / surface_dynamics 0.7.0), probed 2026-09-19 (api-check)
````

### `libgap.md` lines 208-213 — §12.6 timing ('hundreds of members in a (Q2) sweep')

````markdown
**Timing.** On the EW (8 points): building the group from `PermList`/`Group` is
effectively instant (~0.0001 s) and `AllBlocks(G)` ~0.0007–0.0013 s. At this
cost, hundreds of members in a (Q2) sweep is negligible against Sage's own
per-process startup (~1.4–4 s, §12.2/12.3); the sweep's wall time is dominated by
process/import overhead, not by GAP group theory, unless a much larger `n` or a
richer block lattice changes this.
````

### `libgap.md` lines 366-513 — §12.7.6 in full (`conj_test_factory` / `simultaneous_conjugator_gap`, gapinv.py)

````markdown
#### 12.7.6 Addition: `conj_test_factory` / `simultaneous_conjugator_gap` (`fslab/christoffel/gapinv.py`) — Confirmed against 12.6/12.7.2, WSL only, probed 2026-09-23 (api-check)

Question under test: does `libgap.RepresentativeAction(D, src, tgt, libgap.OnTuples)`
decide simultaneous conjugacy of pairs *in a subgroup `D`, not `S_n`*, and does
`gapinv.py`'s inversion (`simultaneous_conjugator_gap` returning
`inverse(representative_action_tuples(...))`) actually match `perm.py`'s
`conjugate(g, h) = h g h^-1` under `compose(p, q)[i] = q[p[i]]`? 12.6/12.7.2 confirmed
the raw GAP call and the `fail` trap; they did not run `gapinv.py`'s own wrapper
functions or pin the inversion against `perm.py`. This entry does both, plus a fresh
hand-derived Q_8 pair (not the `(g1,g1)` or `S_4`-transposition cases already on
file) and the latency at `|G| ~ 10^4` the family-hunt budget needs.

Probe: `FlatSurfLab/scratch/probe_repaction_convention.py`, run via
`scripts\run.ps1 scratch\probe_repaction_convention.py` (WSL, SageMath 10.7 /
sage-flatsurf 0.8.0 / surface_dynamics 0.7.0). **Lingo side not run this dispatch —
VPN down (`scripts\vpn.ps1` → "vpn: down (Ethernet 4: Disabled)"); unconfirmed there.**

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
simultaneously conjugate to its elementwise inverse. Ran, with `Rinv = inverse(r)`,
`Uinv = inverse(u)` (`perm.inverse`, i.e. GAP inverse too since inversion doesn't
depend on the composition convention):
```
RepresentativeAction(D,[R,U],[Rinv,Uinv],OnTuples) = (1,6,3,8)(2,5,4,7)   GapElement_Permutation
  == fail_const? False   is None? False   bool? True
  res_pos^-1 * R * res_pos == Rinv ? True
  res_pos^-1 * U * res_pos == Uinv ? True
```
Confirms both the GAP convention $g^x = x^{-1}gx$ (stated in `gapinv.py`'s docstring)
and the hand-derived answer: a genuine conjugator exists, as predicted, and it is a
GAP `GapElement_Permutation` satisfying the GAP-sense relation directly.

**3. `gapinv.py`'s own functions, run (not just the raw GAP call), and the inversion
pinned against `perm.py`.** This is the part 12.6/12.7 never exercised — `conj_test_factory`
and `simultaneous_conjugator_gap` are the functions the (Q2) BFS dedupe actually calls,
not `libgap.RepresentativeAction` directly.
```python
x = gapinv.representative_action_tuples([r, u], [r, u], [r_inv, u_inv], n)
# -> (5, 4, 7, 6, 3, 2, 1, 0)                      (0-based tuple, GAP's x with r^x=r_inv)
h = gapinv.simultaneous_conjugator_gap([r, u], [r_inv, u_inv], n, gens_domain=[r, u])
# -> (7, 6, 5, 4, 1, 0, 3, 2)                      (package convention: conjugate(r,h)==r_inv)
perm.conjugate(r, h) == r_inv   # True
perm.conjugate(u, h) == u_inv   # True   <- BOTH hold: the load-bearing check
```
`h != inverse(x)`'s naive negation is not what's being claimed — checking directly,
`h == inverse(x)` holds exactly (`(7,6,5,4,1,0,3,2) == inverse((5,4,7,6,3,2,1,0))`),
confirming `gapinv.py`'s documented inversion step. **`conj_test_factory`'s negative
case, run through the actual factory-produced test, not just the raw GAP call:**
```python
gapinv.representative_action_tuples([r, u], [r, u], [u, r], n)   # -> None (not fail!)
gapinv.simultaneous_conjugator_gap([r, u], [u, r], n, gens_domain=[r, u])  # -> None
```
Both correctly normalise GAP's `fail` to Python `None` before returning — this is
`_is_fail` working as documented, exercised through the real call path rather than
inline.

**4. Convention pinned in `S_3`, independently of the Q_8 case, with the action
convention made explicit.** `g3 = (1,2,0)` (the 3-cycle $(0\,1\,2)$, 0-based),
`h3 = (1,0,2)` (the transposition $(0\,1)$). Hand-predicted
`perm.conjugate(g3,h3) = h3 g3 h3^-1` (package sense) by relabelling the cycle
$(0\,1\,2)$ under swapping $0\leftrightarrow1$: becomes $(1\,0\,2) = (0\,2\,1)$ as a
cycle, i.e. the 0-based tuple $(2,0,1)$. Ran: `perm.conjugate(g3,h3) == (2,0,1)`
→ **True**, confirming the hand prediction and, independently, `compose`'s "first `p`
then `q`" convention (`gapinv.py`'s stated reduction of the package's `h g h^-1` to
GAP's `h*g*h^-1`). Then asked GAP for the *single-element* conjugator, in GAP's own
`g^x = x^{-1}gx` sense, target = the same `(2,0,1)`:
```
RepresentativeAction(S3, G3, tgt3, OnPoints) = (2,3)     # GAP 1-based cycle notation
  x3 as 0-based tuple: (0, 2, 1)
  h3^-1 predicted: (1, 0, 2)
  match: False
```
This mismatch is **not** a refutation: `g3` (order 3) has nontrivial centraliser
`<g3>` in `S_3` (order 3), so the conjugator solving `g3^x = target` is not unique —
`x3` and `h3^-1` are both valid, differing by an element of `C_{S_3}(g3)`. Checked:
`x3^-1 * G3 * x3 == tgt3`? **True** (GAP arithmetic, confirms `x3` is *a* valid
conjugator). The load-bearing check is instead run through `gapinv.py`'s own wrapper:
```python
h3_from_pkg = gapinv.simultaneous_conjugator_gap([g3], [predicted], 3, gens_domain=[g3, h3])
# -> (0, 2, 1)   (also not equal to h3 -- same non-uniqueness -- but:)
perm.conjugate(g3, h3_from_pkg) == predicted   # True
```
So: **any given `x` from `RepresentativeAction` need not equal "the" conjugator one
constructed by hand when the centraliser is nontrivial, but `gapinv.py`'s
`simultaneous_conjugator_gap` always returns *some* `h` satisfying the package's own
`conjugate(g,h)==target` relation exactly** — which is the only property `conj_test_factory`
relies on. This nuance (non-uniqueness of the conjugator on non-regular actions) is not
in 12.6/12.7 and is worth carrying forward: **never assert `h == (the constructed
conjugator)`; only assert the conjugation relation holds.**

**5. `fail`-handling, reconfirmed through `gapinv.py`'s own `_is_fail`.** Same
three-way table as 12.6/12.7.2 (`is None` always `False`, `== libgap.eval("fail")` and
`bool(...)` both discriminate correctly), and separately confirmed that `_is_fail`
converts both to Python `None` at the `gapinv.py` API boundary (item 3 above) — this
closes the gap between "the raw GAP trap is understood" (12.6/12.7.2) and "the
project's wrapper actually applies the trap correctly" (this entry).

**6. Timing at `|G| ~ 10^4`, the family-hunt budget figure.** Built
`P = Image(IsomorphismPermGroup(DirectProduct(CyclicGroup(100), CyclicGroup(100))))`,
confirmed `P.Size() = 10000`, `IsPermGroup(P)` `True`, 4 generators. 1000 calls to
`libgap.RepresentativeAction(P, [g1,g2], [g1,g2], OnTuples)` (trivial positive case,
`src == tgt`, so the identity conjugator is found immediately — a **lower-bound**
timing, not a worst case; a genuinely hard search in a group this size could cost
more) took **0.0054 s total, 0.0000054 s/call**. Consistent with 12.6's "hundreds of
members negligible against Sage's own process startup" conclusion — even at `|G| ~
10^4`, `RepresentativeAction` itself is not the bottleneck; process/import overhead
(5.5 s WSL / 15-65 s lingo, per 12.7.5) dominates by four to seven orders of
magnitude. **Not a worst-case bound**: a pair genuinely requiring backtracking search
through a 10^4-element group could be far slower; this timing only establishes the
floor.

**Verdict: gapinv.py's `conj_test_factory` assumption is Confirmed**, on every
sub-claim tested: `RepresentativeAction(D, src, tgt, libgap.OnTuples)` decides
simultaneous conjugacy *within the subgroup `D`* (not `S_n`) exactly as the (Q2)
soundness argument requires; `_is_fail`/`simultaneous_conjugator_gap`'s inversion
correctly translates GAP's `g^x=x^{-1}gx` into the package's `conjugate(g,h)=hgh^{-1}`
convention; and the returned conjugator, while not unique when the centraliser of the
source pair in `D` is nontrivial, always satisfies the package's own conjugation
relation, which is all `conj_test_factory` needs.
````

### `libgap.md` lines 517-619 — §12.8 in full (the production failure on lingo, the `_BFS_GAP`/`_COVER_GAP` runs, the fix for `gap_reverify.py`)

````markdown
### 12.8 Multi-statement GAP function definitions through `libgap` — refutation and fix, probed 2026-09-20 (api-check)

**What failed in production.** `fslab/christoffel/gap_reverify.py:419`, `_gap_func`, on
lingo (job `20260920-123729`, commit `de0c1c5`, Sage 10.7): `f = libgap.eval(source)`
where `source` is a `function(gens, maxStates, maxGroup) local ...; ... end;` block
(`_BFS_GAP`, line 193). The docstring at line 408 had already flagged the form
UNCONFIRMED. It has now run and failed.

**Refuted: `libgap.eval(source)` of a `function ... end;` block, trailing `;` included.**
```
sage.libs.gap.util.GAPError: can only evaluate a single statement
```
Reproduced exactly on the production sources, not a toy: `libgap.eval(_BFS_GAP)` and
`libgap.eval(_COVER_GAP)`, both as they stand in `gap_reverify.py` (multi-line, `local`
declarations, `for`/`while` loops, `if`/`Error`, `end;` with trailing newline), both raise
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
semicolon fix is. Both were run on the unmodified `_BFS_GAP` and `_COVER_GAP` strings
from `gap_reverify.py` (not a simplified stand-in) and both succeeded:
```
=== _BFS_GAP repr tail: ';\nend;'
_BFS_GAP libgap.eval(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'>
_BFS_GAP function_factory(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'> True
=== _COVER_GAP repr tail: ';\nend;'
_COVER_GAP libgap.eval(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'>
_COVER_GAP function_factory(stripped) OK <class 'sage.libs.gap.element.GapElement_Function'> True
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
answer, not merely a plausible-looking one. The unmodified production `_BFS_GAP`,
called the same way on the same generators, also completed and gave a self-consistent
answer: `m=8, complete=1, nStates=24, num vals=6` (6 = the number of distinct minimal
Christoffel values reachable in `Q8` from its two order-4 generators before the BFS
frontier closes — `complete=1` confirms the BFS exhausted the state space rather than
hitting `maxStates`).

**The two production dependency questions:**

- **Callable with plain `int` args and a `libgap` list of generators**, i.e.
  `f(gens, int(max_states), int(group_limit))` as `_gap_func`/line 497 calls it —
  **confirmed**. Ran `f_ff(gens, int(100), int(10000))` where `gens = libgap([r, u])`;
  returned the same `GapElement_List` as the non-`int`-cast call. libgap coerces Python
  `int` to GAP integers transparently at the call boundary; no `libgap(...)` wrapping of
  the ints is needed.
- **Caching the returned function in a module-level dict (`_FUNCS`) across calls in one
  Sage process** — **confirmed safe**, at least for repeated calls with fresh arguments.
  Called the same cached `GapElement_Function` twice with identical arguments (results
  agreed) and once with different arguments (returned a distinct, correct result with no
  cross-call state bleed). The GAP function's `local` variables are re-initialised on
  each GAP-level call, as GAP semantics require, and the Sage-side wrapper is a thin
  handle to the GAP object, not a fresh recompilation — nothing was observed to leak
  between calls to the same cached function.

**The fix that must land in `gap_reverify.py`.** Only `_gap_func` at line 419 needs to
change — strip the trailing `end;`'s semicolon before `libgap.eval` (or switch to
`libgap.function_factory` on the same stripped string; either is confirmed). That fix is
`family-experimenter`'s to apply, not made here.

Probed against **sage-flatsurf 0.8.0 / surface_dynamics 0.7.0 / SageMath 10.7**, WSL,
2026-09-20. Probe scripts: `FlatSurfLab/scratch/probe_gap_funcdef.py` (the isolated
`function_factory` characterisation and the Q8 known-answer case) and
`FlatSurfLab/scratch/probe_gap_funcdef2.py` (re-run against the unmodified `_BFS_GAP` /
`_COVER_GAP` production strings). Opened the canonical copy of this file at
`C:\Users\Galit\.claude\skills\flatsurf-computation\references\api-recipes.md` per
Roey's 2026-09-20 designation (2225 lines before this section, §§1-12 including 12.7); did
not open the stale `~/.claude/skills/synced/` copy.
````
