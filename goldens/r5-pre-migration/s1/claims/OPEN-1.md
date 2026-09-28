---
id: OPEN-1
aliases: [R §7 item 3, OPEN.md "family hunt" 2026-09-20]
title: "(Q2) at PA-4: is some counterexample a garage unfolding? (realisation problem)"
summary: "Is there a (Q2) counterexample at PA-4, i.e. an origami that is the unfolding of a rectangle-tiled parking garage? All known counterexamples (CEX-1, CEX-3, CEX-4) are OA-3 but not PA-4"
kind: open
status: Not settled
level: PA-4
topics: [open, a4-realisation, counterexamples]
examples: [EX-EW, EX-M12-1335, EX-M12-15711, EX-O16a, EX-O16c]
depends_on: [Q2, GEO-13, GEO-12, GEO-19, CEX-1, CEX-3, CEX-5]
source: "OPEN.md:71-79; OPEN.md:97-113"
added: 2026-09-24
---

## Statement

**Is there an origami failing (Q2) that satisfies PA-4**, i.e. is the unfolding of a
rectangle-tiled parking garage? More broadly (R §7 item 3): which $(\sigma,\tau)$ satisfying
OA-3 arise from some garage at levels PA-4, PA-5, PA-6?

Known: no counterexample found so far is PA-4. GEO-13 covers both CEX-1 members, and CEX-3/CEX-5
fail GEO-12's four-fixed-point test. The candidate-generation draft is
[writing/a4-candidate-generation.md](../writing/a4-candidate-generation.md), with drafts GEO-22–25,
OBS-17–21 and COMP-5. The first census is spec P1.

## Notes

The two source passages, verbatim:

<!-- verbatim from OPEN.md:71-79 (HEAD 2026-09-24) -->
3. The realisation problem (Remark 1.11): which $(\sigma,\tau)$ satisfying (A3)
   arise from some $P$ at levels (A4), (A5), (A6)? Is the EW one of them — the
   $\chi(P)=-1$ candidate is numerically consistent, but would sit at (A4) only,
   satisfying neither (A5) nor (SC).
   > Superseded, for the EW question specifically, by R2 Prop. 3.1′ + R2 Thm 2.3 (both
   > Proved: the EW is not (RD), and (A4) $\Rightarrow$ (RD4)) and independently by N11
   > (`notes/03-q2/families-hunt.md`, 2026-09-23, Proved): the EW is **not** an (A4)
   > unfolding. The realisation problem for $(\sigma,\tau)$ satisfying (A3) in general
   > stays open.

<!-- verbatim from OPEN.md:97-113 (HEAD 2026-09-24) -->
## [2026-09-20] Open: the family hunt for a (Q2) counterexample

A computational hunt for a counterexample to (Q2) inside four known families of origamis,
rather than over polyominoes. Conventions, family definitions and enumeration counts are in
`.claude/rules/families.md`; the inputs it rests on are N1–N8 in
`notes/03-q2/families-hunt.md`. N1–N5 and N7 are **Not settled**; N6 is **Proved** (cleared
2026-09-20, see `computation/verdicts.md`). N7 bears on axis 2's (A4) flag: passing R Cor.
1.7's commutator test is close to automatic below degree 6, so a member's (A4) flag from that
test alone carries little weight until N7 is settled. **N8 is Disproved** (cleared
2026-09-23): (Q2) fails at hypothesis level (A3), every-corner-marked, for two cyclic-cover
members at $N=12$ — so the family hunt's (Q2)-in-general target is settled at that level.
**N11 (Proved, cleared 2026-09-23) answers, for these two members specifically, that the
refutation does not survive to (A4)–(A7)**: neither is a parking-garage unfolding, nor an
origami-quotient of one. What is still open is whether some *other* member of the family
refutes (Q2) at (A4) or above (the parking-garage realisation problem, item N3), and whether
N8's mechanism generalises within the family beyond the two cleared members and the ten
unverified pipeline FALSEs at $N=12$.

## History

- 2026-09-24: migrated verbatim from OPEN.md:71-79; OPEN.md:97-113 (relabel map).
