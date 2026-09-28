---
id: OPEN-7
aliases: [OPEN.md lead (a)]
title: "Pillowcase monodromies ±(a_i+a_j) never of order 6, for the whole cyclic family"
summary: "Answered arithmetically by OBS-4/OBS-5, and geometrically for the two CEX-1 members by OBS-10/OBS-11; open for other M_N(a) (needs OBS-10's hypotheses per member or the FMZ labelling)."
kind: open
status: Not settled
topics: [open, pillowcase-covers]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [OBS-4, OBS-5, OBS-10, OBS-11, CEX-1, CEX-2]
source: OPEN.md:115-137
added: 2026-09-24
body_status_ack: "the body's 'Proved' refers to the items that answer parts of the lead"
---

## Statement

**Two structural leads from N8.** (a) Pillowcase monodromies $\pm(a_i+a_j)$ may never be of
order 6 — suggested independently by the `2026-09-23_cyclic_covers_a` run A auditor and the
M_12(1,3,3,5) run A verifier (`computation/verdicts.md`). **Answered in its arithmetic
form, 2026-09-24, by N15/N16** (`notes/03-q2/families-hunt.md`, both Proved): the exact
criterion "$t\notin\bigcup_{i<j}\langle a_i+a_j\rangle$" and its cyclic-cover specialisation
"$\gcd(a_i+a_j,N)\ne2$ for all six pairs" are proved statements about the recipe's column
form, from which the two N8 members are re-derived as instances. **Answered in its geometric
(pillowcase-monodromy) form, also 2026-09-24, for the two N8 members specifically, by
N19/N20** (`notes/03-q2/families-hunt.md`, both Proved), **without** the FMZ identification:
N20 computes the corner monodromies $d_v$ directly from the stored permutations of these two
members and derives $\pm(d_a+d_b)$ never of order 6 as a theorem, not a gloss. **For the rest
of the cyclic-cover family, lead (a)'s geometric reading is still open**: it needs either
N19's hypotheses (freeness of $\langle\delta\rangle$ off $\Sigma^*$, and
$M/\langle\delta\rangle$ the pillowcase) checked member by member, as N20 does for these two,
or the FMZ identification of `CyclicCover`'s labelling with FMZ's $\mathbb Z/N$ action, which
the N8 proof §4 still lists as open. Do not read N19/N20 as closing lead (a) for the family
in general — only for the two N8 members. (b) No Christoffel
value in either of N8's two failing classes has a 12-cycle — observed by the
`2026-09-23_cyclic_covers_a` run B auditor; also unproved when recorded. **N9 (Proved,
2026-09-23) explains this observation**: it shows that no element of $G$ outside $\ker\psi$
(the column-parity kernel) has order divisible by 12 for either member, which is exactly the
condition ruling out a 12-cycle. Lead (b) is therefore explained, though N9's own scope (via
(NU)) is what is cited, not lead (b) itself.

## History

- 2026-09-24: migrated verbatim from OPEN.md:115-137 (relabel map).
