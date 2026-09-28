---
id: GEO-13
aliases: [N11, W4]
title: "The M_12 members, EW, D_4 and Ornithorynque are not PA-4 nor quotients of PA-4"
summary: "Their commutators have fewer than four fixed points, so by GEO-12 none is a PA-4 unfolding nor an origami quotient of one; whether the M_12 members fail GA-RD is unresolved"
kind: prop
status: Proved
status_note: one clause unresolved
level: PA-4
topics: [a4-realisation, counterexamples, quotients]
examples: [EX-M12-1335, EX-M12-15711, EX-EW, EX-D4, EX-ORN]
depends_on: [GEO-12, STR-2, GEO-20]
source: notes/03-q2/families-hunt.md:384-415
added: 2026-09-24
---

## Statement

## [2026-09-23] N11 (Proved, with one clause unresolved) — N8's members are not (A4), nor quotients of an (A4) unfolding; neither are the EW, the $D_4$ regular origami, or the Ornithorynque

**N11.**
- $M_{12}(1,3,3,5)$ and $M_{12}(1,5,7,11)$ (N8) are **not (A4)**: both have commutator
  $[\sigma,\tau]$ with no fixed points ($2^6\,6^2$ and $6^4$ respectively), contradicting
  N10's "at least four fixed points". Neither is even an **origami-quotient** (origami
  covering over $\mathbb T^2$) of any (A4) unfolding: a covering map sends fixed points of
  $[\sigma,\tau]$ to fixed points, and neither member's commutator has any.
- The Eierlegende Wollmilchsau (commutator $2^4$, no fixed points) is **not (A4)** — by N10
  directly, and independently already by R2 Prop. 3.1′ (not (RD)) together with R2 Thm 2.3
  ((A4) $\Rightarrow$ (RD4)), both Proved.
- The $D_4$ regular origami (commutator $2^4$) and the Ornithorynque (commutator $3^3\,1^3$,
  three fixed points, short of the four N10 requires) are also **not (A4)**.
- **Unresolved clause, not part of the label above**: whether the two N8 members are
  additionally **not (RD)**. Run A verified this as **Proved**, citing R2 Thm 3.1(d) directly
  (the commutator restricted to an (EP)-block is a square in $\mathrm{Sym}(B_e)$; a single
  6-cycle filling a 6-point block, or a $6^4$-type block restriction, is not a square). Run B
  verified it as **Proved modulo stated inputs**, through the file's own item W3 (Not settled
  in `writing/a4-candidate-generation.md`), numerically re-checked on all four blocks of each
  member. The two runs disagree on the label for this one clause; **no change is recorded for
  it**, and it is not needed for "not (A4)" or "not a quotient", which hold independently.

*Cleared by.* Two `claim-verifier` runs on the primary model (Fable 5.1), sequential, both
Proved/CONFIRMED on the "not (A4)" and "not a quotient" clauses on 2026-09-23; see
`computation/verdicts.md`, entry "W1 and W4 (writing/a4-candidate-generation.md)". Source:
`writing/a4-candidate-generation.md`, item W4 (uses W1 = N10; cites W5, "lifting lemma", but
does not need it — the quotient statement follows from N10 plus equivariance of fixed points
under a covering map alone).

*Consequence.* N8's refutation of (Q2) at level (A3) does not reach level (A4): neither
member is a parking-garage unfolding, nor a quotient of one. (Q2) at hypothesis levels
(A4)–(A7) remains **Not settled**.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:384-415 (relabel map).
