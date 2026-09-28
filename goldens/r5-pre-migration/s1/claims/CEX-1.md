---
id: CEX-1
aliases: [N8]
title: "(Q2) fails at OA-3 for M_12(1,3,3,5) and M_12(1,5,7,11)"
summary: "Two 24-square cyclic pillowcase covers at N=12 refute (Q2) at OA-3 (every corner marked): the orbitals gr(T^{±1}), T = i ↦ i+4, are met by no power of a Christoffel value. Not PA-4 (GEO-13)."
kind: prop
status: Disproved
status_note: the (Q2) instance
level: OA-3
topics: [counterexamples, pillowcase-covers]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [CRIT-14, CRIT-9]
source: notes/03-q2/families-hunt.md:236-312
added: 2026-09-24
---

## Statement

## [2026-09-23] N8 (Disproved) — (Q2) fails at $N=12$ in the cyclic-cover family, level (A3)

> See N9 (2026-09-23) for an enumeration-free strengthening of member 1's certificate, and
> N11 (2026-09-23) for the fact that neither member is (A4) or a quotient of an (A4)
> unfolding. N8 itself stands unchanged — it is not superseded.

**N8.** Two members of the cyclic-cover family $M_N(a_1,\dots,a_4)$ at $N=12$ refute (Q2) as
this database defines it — for origamis with every square corner marked — at hypothesis
level (A3). Each is cleared as a refutation: two `refutation-verifier` runs both REFUTATION
CONFIRMED and two `result-auditor` runs both SOUND on the deciding script
(`computation/verdicts.md`, entries `## 2026-09-23 — candidate refutation M_12(1,3,3,5)` and
`## 2026-09-23 — candidate refutation M_12(1,5,7,11)`, both from
`2026-09-23_cyclic_covers_a`), all four runs sequential and on the primary model.

**Member 1: $M_{12}(1,3,3,5)$.** Labelling `CyclicCover([1,3,3,5], M=12)`, 24 squares,
0-based $r=(1,12,15,2,5,16,19,6,9,20,23,10,13,0,3,14,17,4,7,18,21,8,11,22)$,
$u=(15,10,9,20,19,14,13,0,23,18,17,4,3,22,21,8,7,2,1,12,11,6,5,16)$. $|G|=72$
($(C_6\times S_3)\rtimes C_2$), $|Z|=12$, **not normal**, stratum $H_9(5^2,1^6)$, level (A3).
(Q2) fails on the $G$-orbital of the pair $(0,4)$ — the graph of the translation
$T=(i\mapsto i+4)$, the square of the deck generator — and on that of $(0,20)=\mathrm{gr}(T^{-1})$,
with the value set complete at 432 raw states ($|W|=36$, bound $|G|^2=5184$). Certificate:
**(CT′)(i) fails for $T=\delta^2$**, $\delta=(i\mapsto i+2)$ the FMZ deck generator (itself an
(A1) witness): every value in $W$ has cycle type $4^6$ or $6^4$, a $T$-invariant cycle would
have to be a 6-cycle equal to a residue class mod 4, and each 6-cycle of the 18 type-$6^4$
values meets two residue classes; by R2 Prop. 4.4(b) (Proved), $\mathrm{gr}(T)\not\subset R^{\mathrm{pow}}$,
likewise $\mathrm{gr}(T^{-1})$.

**Member 2: $M_{12}(1,5,7,11)$.** Labelling `CyclicCover([1,5,7,11], M=12)`, 24 squares,
0-based $r=(1,0,3,2,5,4,7,6,9,8,11,10,13,12,15,14,17,16,19,18,21,20,23,22)$,
$u=(3,22,17,12,7,2,21,16,11,6,1,20,15,10,5,0,19,14,9,4,23,18,13,8)$. $|G|=24$
(SmallGroup(24,8) $\cong C_3\rtimes D_4$), $|Z|=24$, **normal**, stratum $H_{11}(5^4)$, level
(A3). (Q2) fails on the orbitals of $(0,4)$ and $(0,20)$ — equivalently, the conjugacy class
$\{E_1,E_2\}$ of order-6 elements mapping to the central involution of $G/C_3\cong D_4$ is
conjugate to no power of any Christoffel value — with the value set complete at 72 raw states
($|W|=14$, bound $|G|^2=576$). Certificate: **the $G/C_3\cong D_4$ argument**: $N=\langle
E_1^2\rangle\cong C_3$ is normal, $G/N\cong D_4=\langle s,t\rangle$ with $uN=s$ (order 4),
$rN=t$ (order 2), both missing elements $E_1,E_2$ mapping to $s^2$; a word with $p$ letters
$x$ and $q$ letters $y$ maps to $s^{\pm\Sigma(-1)^{n_j}}t^p$, equal to $s^2$ only if $p,q$ are
both even, impossible for $\gcd(p,q)=1$; as the maximal element order of $G$ is 6, any $g$
with $g^k$ conjugate to $E_1$ is conjugate to $E_1^{\pm1}$ and maps to $s^2$. With R Prop. 5.7
(Proved), (Q2) fails. **This is consistent with R2 Thm 4.7** ((2T′) $\Rightarrow$ [(Q2)
$\Leftrightarrow$ (CT′)]): both runs record (2T′), (CT′)(ii), (D0) holding on this member,
with (CT′)(i) failing exactly for $T_4$, $T_{20}$.

**Scope of the refutation, exactly.** N8 refutes (Q2) at hypothesis level (A3), as this
database defines (Q2) for origamis with every square corner marked. It says **nothing** about
(A4)–(A7), i.e. about parking-garage unfoldings: on both members the (A4) commutator test
passed only as a **necessary** condition (N3, the test's equivalence with genuine (A4)
realisability, is still Not settled), and (A5) and (A6) **fail** on both. The marked-point
convention is vacuous on both members — every square corner is a zero, not a marked regular
point (member 1: commutator type $2^6 6^2$, no fixed points; member 2: stratum $H_{11}(5^4)$)
— so N8 is not an instance of the "fewer marked points" transfer caveat. **The other ten FALSE
members at $N=12$** (the remaining unit-orbit representatives of the same two $S_4$ classes)
are pipeline results only, carrying the run's three in-run cross-checks and not independently
verified by a `refutation-verifier`; N8 does not extend to them.

**Two structural leads, not claims — flagged Not settled:**

(a) The `2026-09-23_cyclic_covers_a` run A auditor and the M_12(1,3,3,5) run A verifier each
suggested, independently, a possible cylinder-monodromy mechanism: pillowcase monodromies
$\pm(a_i+a_j)$ are never of order 6. This is plausible and **unproved** — recorded as a lead
for a future member of the family, not as part of N8's certificate. **Update, 2026-09-24:**
answered in its arithmetic form by N15/N16 below (both Proved) — see also `OPEN.md`. **Second
update, 2026-09-24:** for the two N8 members specifically, the geometric (pillowcase-monodromy)
reading is now also answered, **without** the FMZ identification, by N19/N20 (both Proved):
N20 computes the corner monodromies $d_v$ directly from the stored permutations of these two
members and shows the pair sums $\pm(d_a+d_b)$ are never of order 6. For the rest of the
cyclic-cover family the geometric reading still needs either N19's hypotheses (freeness of
$\langle\delta\rangle$ off $\Sigma^*$, $M/\langle\delta\rangle$ the pillowcase) checked member
by member as N20 does for these two, or the FMZ identification itself, which stays open.

(b) The `2026-09-23_cyclic_covers_a` run B auditor observed that no Christoffel value in
either of the two failing classes has a 12-cycle. Also recorded as a lead only.

*What would settle N8 further.* Whether N8's mechanism (or lead (a) or (b)) generalises to
other $N$; whether the other ten FALSE $N=12$ members independently verify; N3, to move any
member of this family beyond "necessary conditions passed" at level (A4) and above.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:236-312 (relabel map).
