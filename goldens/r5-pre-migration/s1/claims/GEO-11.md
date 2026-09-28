---
id: GEO-11
aliases: [N7]
title: "The PA-4 commutator test is vacuous below degree 6"
summary: "Any commutator is even, so the GEO-10 test only bites with two distinct even cycle lengths, needing n ≥ 6; exhaustive search on n ≤ 5 finds no failing pair"
kind: prop
status: Not settled
topics: [unfoldings, a4-realisation, computation]
examples: [EX-EW, EX-D4]
depends_on: [GEO-10]
source: notes/03-q2/families-hunt.md:198-232
added: 2026-09-24
---

## Statement

### N7 (Not settled) — R Cor. 1.7's (A4) test is vacuous below degree 6, and weaker in general than it reads

**N7.** R Cor. 1.7 (in `notes/01-geometry/unfoldings.md`) states, as a necessary condition
for (A4), that the number of cycles of the commutator $[\sigma,\tau]$ of each **even** length
is even. The observation: a *part* of this is automatic and carries no information.

A cycle of length $L$ has sign $(-1)^{L-1}$, so even-length cycles each contribute a factor
of $-1$ and odd-length cycles contribute nothing. Hence the sign of any permutation is
$(-1)^{(\text{total number of even-length cycles})}$. A commutator is always an even
permutation. Therefore the total number of even-length cycles of the commutator is always
even, for **any** pair of permutations whatsoever, with no hypothesis.

The consequence: Corollary 1.7 constrains nothing unless the commutator has cycles of **two
or more distinct even lengths**, since with a single even length present the per-length count
equals the total count and is even automatically. Two distinct even lengths need at least
$2+4$, so at least 6 points. An exhaustive search over transitive pairs on 3, 4 and 5 points
found no pair failing the test, and the smallest reported witness is the pair
$\sigma=(0,1,3,2,5,4)$, $\tau=(2,3,0,4,1,5)$ in 0-based tuple form, whose commutator has cycle
type $2,4$.

**What N7 does not say.** It does not contradict R Cor. 1.7, which remains **Proved** and
correct as stated; it says the corollary is a weaker filter than a reader would assume, and
in particular that passing it is no evidence at all on fewer than 6 points. Note also that
the Eierlegende Wollmilchsau and the $D_4$ origami, whose commutators have cycle type $2^4$ —
a single even length, four cycles — pass it for exactly this trivial reason, which is worth
knowing when reading R Remark 1.11's discussion of whether the Wollmilchsau is an (A4)
unfolding.

*What would settle it.* Two `claim-verifier` runs, checking the sign computation, the "two
distinct even lengths" threshold, the exhaustive search over degrees 3 to 5, and the reported
witness. The runs can now execute code, so the witness and the search are directly
checkable.

*Consequence for the hunt.* If N7 holds, a member passing the (A4) commutator test has told
you almost nothing, and the realisation question stays with item N3.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:198-232 (relabel map).
