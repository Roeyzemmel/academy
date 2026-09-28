---
id: GEO-19
aliases: [N3]
title: "A decidability test for realisation as a garage unfolding from (σ,τ)"
summary: "Given OA-3 data, M/Φ is a rectangle-tiled garage iff trivially-stabilised vertices have angle 2π and μν-only-fixed ones 4π; would make PA-4, PA-5w, PA-6 decidable"
kind: prop
status: Not settled
level: OA-3
topics: [a4-realisation, computation]
depends_on: [GEO-9]
source: notes/03-q2/families-hunt.md:91-109
added: 2026-09-24
---

## Statement

### N3 (Not settled) — a decidability test for the realisation problem

**N3.** A decidability claim for the realisation problem (R Remark 1.11, recorded in this
database as Not settled, and target 6 of `computation/spec.md` §6.1). Given
$(\sigma,\tau)$ satisfying (A3) with witnesses $\mu,\nu$ and $\Phi=\{1,\mu,\nu,\mu\nu\}$:
the quotient $P:=M/\Phi$ is a rectangle-tiled parking garage if and only if every vertex of
$M$ whose $\Phi$-stabiliser is trivial has cone angle $2\pi$, and every vertex fixed only by
$\mu\nu$ has cone angle $4\pi$. The corners of $P$ are then read off the vertices fixed by a
reflection, through R Prop. 1.6, so (A5), (A6) and (SC) are decided on $P$. Since the (A3)
data form a finite set — $\mu$ and $\nu$ each range over a coset of the centraliser
$C_{S_n}(G)$ — this would make levels (A4), (A5), (A6) decidable from $(\sigma,\tau)$ alone.

*What would settle it.* Checking the claim against R Prop. 1.4, 1.5 and 1.6 line by line, in
**both** directions, including whether embeddedness (needed for (A6)) and the immersion
condition (no interior cone points of $P$) are really captured by the stated angle
conditions.

*Until it is verified.* Any hypothesis level a computation reports through this test is
flagged experimental, and a counterexample may not claim a level on its strength.

## Notes

- **2026-09-24.** Lead from the GEO-32 verification (run A, 2026-09-24), not verified: its
  test is not sufficient. On the $3\times3$ square frame's unfolding $M$, two
  $K_4$-structures pass the stated test, but their quotient has interior holonomy $-I$, so it
  is not a garage; two more flip 8 edges under $\mu\nu$
  (`computation/verdicts/2026-09-24_GEO-32.md`).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:91-109 (relabel map).
- 2026-09-24: added a Notes lead from the GEO-32 verification (run A,
  `computation/verdicts/2026-09-24_GEO-32.md`); status unchanged.
