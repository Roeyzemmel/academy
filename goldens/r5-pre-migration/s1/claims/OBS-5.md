---
id: OBS-5
aliases: [N16, G5]
title: "gcd criterion for (Q2) failure in the cyclic covers M_N(a)"
summary: "Some sheet-shift orbital of M_N(a) is unmet iff gcd(a_i+a_j, N) ≠ 2 for all i<j, and then (Q2) fails. Needs N/2 not a prime power; for N ≤ 18 only the two N=12 classes; three classes at N=20."
kind: prop
status: Proved
topics: [obstructions, pillowcase-covers]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [OBS-4, OBS-2]
source: notes/03-q2/families-hunt.md:596-653
added: 2026-09-24
---

## Statement

### N16 (Proved) — the cyclic covers

**N16.** For valid $(N,a)$ (the family-3 cyclic pillowcase covers $M_N(a)$; "translation
orbital" here means the graph of a **sheet shift** $T_t$, $t\in A'=2\mathbb Z/N$, not the
graph of an arbitrary centraliser element):

(a) **Some** $\mathrm{gr}(T_t)$ with $0\ne t\in A'$ is unmet iff **$\gcd(a_i+a_j,N)\neq2$ for
all $i<j$**. The unmet $t$ are exactly those with $t\notin\bigcup_{i<j}\langle a_i+a_j\rangle$,
and these include every generator of $A'$. Equivalently: no $a_i+a_j$ has order $N/2$ in
$\mathbb Z/N$; equivalently, for every $i<j$ either $4\mid\gcd(a_i+a_j,N)$ or some odd prime
divides $\gcd(a_i+a_j,N)$. (The earlier reading "**all** translation orbitals are unmet" is
false: in $M_{12}(1,5,7,11)$ the criterion holds, yet $\mathrm{gr}(T_t)$ is met for $t=2,3,4$
(halved); in $M_{12}(1,3,3,5)$ it is met for $t=4,6,8$ (unhalved).) When (a) holds, (Q2)
fails.

(b) This forces $N/2$ to have at least two distinct prime factors, so $N\in\{12,20,24,28,30,36,\dots\}$.

(c) For $N\le18$ it holds exactly for the $S_4$-and-unit classes of $\{1,3,3,5\}$ and
$\{1,5,7,11\}$ at $N=12$ — twelve unit orbits, six per class.

(d) At $N=20$ it holds exactly for the three classes $\{1,9,15,15\}$, $\{1,9,11,19\}$ and
$\{1,3,7,9\}$ (up to $S_4$ and units).

## Proof

*Proof.* (a) $A'=2\mathbb Z/N$ is cyclic, and a cyclic group is a union of proper subgroups
only if one of them is the whole group; so N15 reduces to "no $s_i$ generates $2\mathbb Z/N$",
and $\langle x\rangle=2\mathbb Z/N$ iff $\gcd(x,N)=2$, with the six sums $\pm s_i$. (b) If
$N/2=q^e$, transitivity (N13(a)) makes the $s_i$ generate $A'\cong\mathbb Z/q^e$, and in a
cyclic $q$-group the non-generators form a proper subgroup, so some $s_i$ generates; for odd
$q$, $q\mid s_1,s_2,s_3$ forces $q\mid a_1,a_2,a_3$, contradicting $\gcd(N,a)=1$, and for $q=2$,
$a_0\equiv-a_3\equiv a_2\equiv-a_0\pmod4$ is impossible for odd $a_0$. (c) $N\le18$ with $N/2$
not a prime power leaves only $N=12$, where a residue analysis mod 4 and mod 3 gives exactly
the classes $\{9,9\}\cup\{7,11\}$ (=$\{1,3,3,5\}$ up to units), $\{1,5\}\cup\{3,3\}$ and
$\{1,5\}\cup\{7,11\}$, with 24 ordered quadruples and 6 unit orbits per class (the 4 units act
freely, since $ua=a$ for $u\ne1$ would force every $a_i\equiv0\pmod3$ ($u=5$) or every $a_i$
even ($u=7,11$), both impossible). (d) The same argument mod 4 and mod 5 gives representatives
$\{1,9\}\cup\{15,15\}$, $\{1,9\}\cup\{11,19\}$, $\{1,9\}\cup\{7,3\}$, pairwise inequivalent by
the unordered ratio class $\{\pm w\}/\{\pm z\}$ in $\mathbb P^1(\mathbb F_5)/\pm$, invariant
under scaling, swapping and $S_4$. $\square$

**Against E2a/E2b.** Those runs report FALSE on exactly twelve members, all at $N=12$: the six
unit-orbit representatives of each of $\{1,3,3,5\}$ and $\{1,5,7,11\}$, and no other failure at
$N\le18$. N16(c) predicts exactly this set, unit- and $S_4$-invariant. **The gcd criterion is
now a Proved sufficient condition for (Q2) to fail among these cyclic covers. Whether it is
also necessary is not proved**; it only agrees with E2a/E2b for $N\le18$ — an observation
about that data, not a theorem.

**Consequences, not computed findings.** By N16(b)/(d), the criterion predicts three further
$S_4$-and-unit classes at $N=20$ ($M_{20}(1,9,11,19)$, $M_{20}(1,3,7,9)$, $M_{20}(1,9,15,15)$),
lifts of the two $N=12$ classes at $N=24$, and new classes at $N=28$ and $N=30$ (not lifts,
since $12\nmid28$ and $12\nmid30$), e.g. $M_{28}(1,7,7,13)$ and $M_{30}(1,11,19,29)$. These are
consequences of N16, not independently verified computations; the draft's six named
hand-checks (§6 there) are leads, not findings, and were not verified by this pass.

*Cleared by.* Two `claim-verifier` runs, both Proved modulo N14 (via N15) on both runs (for
(a) only; (b)–(d) need no input); with N14 Proved, N16 → **Proved**; sequential, both on
`claude-opus-5-5`; see `computation/verdicts.md`, entry "2026-09-24 — G2, G4, G5
(writing/n8-generalization.md) → N13, N15, N16". Source: `writing/n8-generalization.md`
§2.2 (G5).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:596-653 (relabel map).
