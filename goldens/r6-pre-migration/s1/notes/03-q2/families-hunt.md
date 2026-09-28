# The family hunt: inputs for a (Q2) counterexample search

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

The unverified inputs the computational hunt for a (Q2) counterexample rests on, across the four families of `.claude/rules/families.md` — the Eierlegende Wollmilchsau, the Ornithorynque, the Forni–Matheus–Zorich cyclic covers $M_N(a_1,\dots,a_4)$ of the pillowcase, and abelian covers of the pillowcase.

---

## [2026-09-20] Inputs for the family hunt

N1–N5 and N7 below are recorded as **Not settled**. Nothing there has been verified by this
database; each item says what would settle it. An item may shape a search and may be used
for validation, but it may never be the reason a counterexample is believed, and anything
resting on one inherits the flag. **N6 is Proved**, cleared on 2026-09-20 by two agreeing
`claim-verifier` runs; see its entry below and `computation/verdicts.md`. **N8 is Disproved**
— (Q2) fails at level (A3) for two members of the cyclic-cover family at $N=12$ — cleared on
2026-09-23 by two `refutation-verifier` runs (REFUTATION CONFIRMED) and two `result-auditor`
runs (SOUND) per candidate; see its entry below and `computation/verdicts.md`. **N12 is
Proved** — the parity–translation obstruction generalising N8's Prop. 1.3 to an arbitrary
level-$\Lambda'$ fibration, $\Lambda'\subseteq p\mathbb Z^2$ — cleared on 2026-09-24 by two
`claim-verifier` runs on `claude-opus-5-5`; see its entry below and
`computation/verdicts.md`. **N13–N16 are Proved** — the column-form test, the pillowcase
recipe in column form, and an exact gcd criterion for the cyclic covers, sufficient for
(Q2) to fail — cleared on 2026-09-24 by two sequential `claim-verifier` runs each, on
`claude-opus-5-5`; see their entries below and `computation/verdicts.md`. **N17–N20 are
Proved** — the quotient mechanism of N8: no $D_4$ symmetry, the $\mathbb Z/6$ monodromy of
$M\to M/\langle T\rangle$ pushed to the FMZ pillowcase, and its instance on both N8 members —
cleared on 2026-09-24 by two sequential `claim-verifier` runs on `claude-opus-5-5`, on the
draft after repair (an earlier run on the unrepaired draft returned Partial and did not
clear; see both entries in `computation/verdicts.md`). **N21–N22 are Proved** — a 16-square
counterexample at level (A3), and the lower bound $n\ge16$ for the mechanism, sharp —
cleared on 2026-09-24 by two sequential `claim-verifier` runs each, on `claude-opus-5-5`; see
their entries below and `computation/verdicts.md`. **N23 and N24 are Proved** — a second
16-square counterexample at level (A3) ($O_{16}^{b}$, not in $O_{16}^{a}$'s
$\mathrm{SL}(2,\mathbb Z)$-orbit), and a third ($O_{16}^{c}$) that also fails (Q2) at level
(A3) but **is** in $O_{16}^{a}$'s $\mathrm{SL}(2,\mathbb Z)$-orbit and so is not a new
example — cleared on 2026-09-24 by two sequential `claim-verifier` runs each, on
`claude-opus-5-5`; see their entries below and `computation/verdicts.md`.

> **→ [COMP-1](../../claims/COMP-1.md)** (N1) — moved to its own file, 2026-09-24.

> **→ [COMP-2](../../claims/COMP-2.md)** (N2) — moved to its own file, 2026-09-24.

> **→ [GEO-19](../../claims/GEO-19.md)** (N3) — moved to its own file, 2026-09-24.

> **→ [COMP-3](../../claims/COMP-3.md)** (N4) — moved to its own file, 2026-09-24.

> **→ [COMP-4](../../claims/COMP-4.md)** (N5) — moved to its own file, 2026-09-24.

> **→ [BOUND-3](../../claims/BOUND-3.md)** (N6) — moved to its own file, 2026-09-24.

> **→ [GEO-11](../../claims/GEO-11.md)** (N7) — moved to its own file, 2026-09-24.

---

> **→ [CEX-1](../../claims/CEX-1.md)** (N8) — moved to its own file, 2026-09-24.

---

> **→ [CEX-2](../../claims/CEX-2.md)** (N9, [N8p] Thm A, [N8p] Thm B, [N8p] Cor 5.1, [N8p] Prop 1.3) — moved to its own file, 2026-09-24.

---

> **→ [GEO-12](../../claims/GEO-12.md)** (N10, W1) — moved to its own file, 2026-09-24.

---

> **→ [GEO-13](../../claims/GEO-13.md)** (N11, W4) — moved to its own file, 2026-09-24.

---

> **→ [OBS-1](../../claims/OBS-1.md)** (N12, G1) — moved to its own file, 2026-09-24.

---

## [2026-09-24] N13–N16 (Proved) — column-form test, the pillowcase recipe, and the gcd criterion for cyclic covers

Four further items from `writing/n8-generalization.md`, cleared by two sequential
`claim-verifier` runs each, on `claude-opus-5-5` (an equal primary with Fable 5.1 for
clearing, Roey, 2026-09-24). All four statements below are the **repaired** draft text,
marked "(revised 2026-09-24 after verification)" in the source, after the blocking wording
findings of both passes were applied there.

**Column form (recalled from N9/N12's setting).** $A$ a finite abelian group, $V$ a finite
set, $\Omega=A\times V$. For $c:V\to A$ and $\pi\in\mathrm{Sym}(V)$, $[c,\pi](m,j)=(m+c(j),\pi j)$,
and $T_t:=[\mathrm{const}_t,\mathrm{id}]$ ($t\in A$) commutes with every column-form map. A
**translation orbital** means the graph $\mathrm{gr}(T_t)$ of such a shift — for the
pillowcase recipe (N14 below) a **sheet shift** $T_t:(i,\varepsilon)\mapsto(i+t,\varepsilon)$,
$t\in A'=\ker\chi$ — never the graph of an arbitrary centralising element.

> **→ [OBS-2](../../claims/OBS-2.md)** (N13, G2) — moved to its own file, 2026-09-24.

> **→ [OBS-3](../../claims/OBS-3.md)** (N14, G3) — moved to its own file, 2026-09-24.

> **→ [OBS-4](../../claims/OBS-4.md)** (N15, G4) — moved to its own file, 2026-09-24.

> **→ [OBS-5](../../claims/OBS-5.md)** (N16, G5) — moved to its own file, 2026-09-24.

---

## [2026-09-24] N17–N20 (Proved) — the quotient mechanism of N8: a $\mathbb Z/6$ monodromy obstruction on $M/\langle T\rangle$, not a lifted non-illumination

Written in answer to Roey's question about N8: is the non-illumination of $(x_i,x_{i\pm4})$
on the two N8 members the lift, through some quotient of $M$, of a non-illumination already
visible on a smaller surface? **Summary answer: no.** In neither member is the unmet pair
the lift of an unmet pair on a quotient. The pair either **collapses** to a single point in
the quotient, or it **stays illuminated**, or (in a few half-translation quotients) its
non-illumination is **equivalent** to the one on $M$ and has no independent proof — collapse
happens in $E=M/\langle T\rangle$, in the FMZ pillowcase $M/\langle\delta\rangle$, in $M/Z$
and in the full $K_4$-quotient (a rectangle); the pair stays illuminated in every proper
intermediate origami and in most half-translation and $K_4$-quotients. **The true mechanism
is a monodromy obstruction of the cyclic $\mathbb Z/6$ translation cover $M\to
E=M/\langle T\rangle$ of the 4-square torus.** Pushed down to the FMZ pillowcase, the
monodromy of every core is $\pm(d_a+d_b)$, a sum of two corner exponents in $\mathbb Z/12$;
for both members' data such a sum is never of order 6, so no straight segment carries $x$ to
$T^{\pm1}x$. The obstruction is a **composite-order** one: it sits in the gap between the
subgroups $\langle2\rangle$ and $\langle3\rangle$ of $\mathbb Z/6$, and neither prime-order
quotient cover sees it (both prime-order covers $M/\langle T^3\rangle\to E$ and
$M/\langle T^2\rangle\to E$ have some core with nonzero monodromy, so a prime-order test such
as W8's would not detect N8).

**Setting (from `writing/n8-quotient-mechanism.md` §0, henceforth [N8q]).** $M$ is the
closed origami (24 squares in both N8 members; no parking garage $P$ anywhere in this block —
N11 shows neither member is (A4), and N20 below shows no (A3) $K_4$-quotient of either
member is even orientable, so R Prop. 1.6 is never invoked and nothing here transfers to a
garage). Squares are $\Omega=\{0,\dots,23\}$, $i=4m+j$ with $m\in\mathbb Z/6$, $j\in
V=\{0,1,2,3\}$ (the columns); $\sigma=r,\tau=u$ as in [N8p] (`writing/n8-counterexample-proof.md`).
$T(i)=i+4$ is the central translation; $\delta(i)=i+2$ is the FMZ deck generator. $\Sigma^*$
is the set of all square corners (marked-point convention); in both members every corner is a
genuine zero, so $\Sigma^*$ is exactly the set of zeros and the "fewer marked points"
transfer caveat is vacuous here.

> **→ [OBS-8](../../claims/OBS-8.md)** (N17, M2) — moved to its own file, 2026-09-24.

> **→ [OBS-9](../../claims/OBS-9.md)** (N18, M3) — moved to its own file, 2026-09-24.

> **→ [OBS-10](../../claims/OBS-10.md)** (N19, M4) — moved to its own file, 2026-09-24.

> **→ [OBS-11](../../claims/OBS-11.md)** (N20, M5) — moved to its own file, 2026-09-24.

---

## [2026-09-24] N21–N22 (Proved) — a 16-square counterexample, and the lower bound 16 for the mechanism

> **→ [CEX-3](../../claims/CEX-3.md)** (N22, G8) — moved to its own file, 2026-09-24.

> **→ [BOUND-4](../../claims/BOUND-4.md)** (N21, G7) — moved to its own file, 2026-09-24.

---

## [2026-09-24] N23–N24 (Proved) — a second 16-square counterexample, and a third that is not new

> **→ [CEX-4](../../claims/CEX-4.md)** (N23, G9) — moved to its own file, 2026-09-24.

> **→ [CEX-5](../../claims/CEX-5.md)** (N24, G10) — moved to its own file, 2026-09-24.
