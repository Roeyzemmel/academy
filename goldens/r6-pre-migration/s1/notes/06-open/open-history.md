# Open problems and status

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

Open problems as recorded at the end of each results doc. R2 §10 is the more recent and supersedes R §7 where they overlap (R's Conjecture 5.8 is disproved; R's item 6, the slope‑1 argument, is done in R2 Thm 2.2). `STATUS.md` gives the current one-line view.

---

## [R2 §10] Status and open questions

| item | status |
|---|---|
| Thm 2.2: base-point independence, (Q2) $=R^{\mathrm{pow}}$ | Proved modulo EMM, Smillie–Weiss |
| Thm 2.3: (A4)⇒(RD4), (A5)⇒(RD5), (A6)⇒(RD6); Prop. 2.4 | Proved |
| Thm 3.1: twisted diagonal, (RD)⇒(A3)∧(EP), cycle types | Proved |
| Prop. 3.3: Galois correspondence, symmetries | Proved |
| Prop. 4.1, Thm 4.2, Cor. 4.3: (2T)∧(D0)⇒(Q2); parity obstruction | Proved |
| Prop. 4.4: centralising elements | Proved |
| Thm 4.5: (HA) ⇒ [(Q2) ⇔ (CT)] | Proved |
| Thm 3.4: constraints on $G$ under (RD)–(A6) | Proved |
| Thm 4.7: master criterion (2T′) ⇒ [(Q2) ⇔ (CT′)]; Lemma 4.8 block reduction | Proved |
| Prop. 5.1: (HA) from primitivity + isolated 3‑cycle | Proved |
| Prop. 6.1: mid-line reflections satisfy (CT) | Proved under (A6); Reduced in general |
| R Conj. 5.8 | Disproved (Prop. 7.1) |
| (Q2) under (A7) | Proved (trivial: Cor. 4.3(a)); (Q1) fails except for the unit square |
| (RD) ⇔ (EP)∧(A3$^{\rm std}$); EW satisfies (A3)∧(EP) but not (RD) (Prop. 3.1′) | Proved |
| (Q2) under (A6)∖(A7) | **Reduced** to 5.A (3‑cycle isolation), 5.B (fold-primitivity), 6.A (half-turns), and the imprimitive case (block reduction of S1 §3.5) |
| (A5) proper | Nothing beyond (RD5) used; Jones's list is the extra tool |

> **→ [OPEN-2](../../claims/OPEN-2.md)** (R2 Conj 10.1) — moved to its own file, 2026-09-24.

**Open, by leverage.** Conjecture 10.1 (equivalently: describe the block systems of $G$
for polyomino unfoldings beyond $E_\Lambda$ and $Z$); 5.A; 5.B; 6.A; the grid-line-symmetric
case via Lemma 4.8 ((Q2) for $P/\theta$ plus fibre 2‑transitivity).
Experiments for the computation spec: (i) $H^+$ and the $G$-orbitals versus the level sets
of $\mathrm{inv}$ for all polyominoes $\le10$ cells (tests 10.1, 5.B); (ii) for symmetric
shapes, the smallest direction with a $T$-invariant orbit and the parity of the number of
$u$-orbits (tests 6.A); (iii) $K_{\min}$ against $\max(\text{width},\text{height})+1$;
(iv) polyominoes with $H^+$ imprimitive, $\Lambda=2\mathbb Z^2$ and no grid-line symmetry
(the only place a counterexample to 10.1 can live).

---

## [R §7] Open (as of R)

**Open.**
> **→ [Q2](../../claims/Q2.md)** ((Q2), R §7 open item 1) — moved to its own file, 2026-09-24.
> **→ [BOUND-1](../../claims/BOUND-1.md)** (R Conj 5.8, R §7 open item 2) — moved to its own file, 2026-09-24.
> **→ [OPEN-1](../../claims/OPEN-1.md)** (R §7 item 3, OPEN.md "family hunt" 2026-09-20) — moved to its own file, 2026-09-24.
> **→ [OPEN-10](../../claims/OPEN-10.md)** (R §7 item 4) — moved to its own file, 2026-09-24.
> **→ [OPEN-11](../../claims/OPEN-11.md)** (R §7 item 5) — moved to its own file, 2026-09-24.
> **→ [GEO-30](../../claims/GEO-30.md)** (R2 Thm 2.2, R §7 open item 6) — moved to its own file, 2026-09-24.
> **→ [OPEN-12](../../claims/OPEN-12.md)** (R §7 item 7) — moved to its own file, 2026-09-24.

---

> **→ [OPEN-1](../../claims/OPEN-1.md)** (R §7 item 3, OPEN.md "family hunt" 2026-09-20) — moved to its own file, 2026-09-24.

> **→ [OPEN-7](../../claims/OPEN-7.md)** (OPEN.md lead (a)) — moved to its own file, 2026-09-24.

**The four families.** (1) The Eierlegende Wollmilchsau — the validation case, not a
candidate: (Q2) is known true for it with $K = 2$. (2) The Ornithorynque,
`CyclicCover([1,1,1,3])`. (3) The Forni–Matheus–Zorich cyclic covers $M_N(a_1,\dots,a_4)$ of
the pillowcase. (4) Abelian covers of the pillowcase (N4).

**Ranking: two axes, a Pareto front, never a scalar.** Axis 1, likelihood of (Q2) failure:
(2T′) failing (R2 §4.5's natural place to look), then (CT′)(i) holding only with long
directions, then structural slack, then $K_{\min}$ growth. Axis 2, hypothesis level:
(A3) > (A2) > (A1) > (A0), with the (A4)/(A5)/(A6) flags. Report the non-dominated members
on both axes together with the full table.

**What gates a refutation.** N1, N3 and N4 gate the code paths that would be used to believe
one: N1 the $\mathrm{SL}(2,\mathbb Z)$-orbit reduction and the independent Nielsen-move
enumeration of the value set; N3 every hypothesis-level claim beyond "necessary conditions
passed"; N4 the construction of family 4 itself. Until each is verified, a member found by
those paths is a candidate only, and its hypothesis level is flagged experimental.

**What a counterexample must look like.** Normal members: a non-identity element of $G$
conjugate to no power of any Christoffel value, named with its conjugacy class and a
completeness certificate. Non-normal members: a $G$-orbital, given by a representative pair
$(i,j)$ with $d(i,j)$ and $z(i,j)$, met by no power of any value, again with a completeness
certificate. A record whose value set is not complete is `UNDECIDED`, never a counterexample.


---

<!-- verbatim from STATUS.md:126-138 (HEAD 2026-09-24); the rest of STATUS.md is now generated -->

## Superseded items in R

- R §7 open item 2 (Conjecture 5.8) is disproved by R2 Prop. 7.1.
- R §7 open item 6 (the orbit-closure / slope‑1 argument for a fixed $z_0$) is addressed by
  R2 Thm 2.2, which is Proved modulo EMM and Smillie–Weiss. *This identification was made
  when the repo was set up. Confirm it before relying on it.*
- R Thm 5.1's list of settled cases is extended by R2 §8.1.

## Items to verify before citing

Jeffreys Thm 1.4 (the fetched text was garbled); Hubert–Lelièvre Prop. 5.1 against the
published version (standing hypothesis $n$ prime $\ge5$); Zmiaikou's constant, and which
sense of "primitive" he uses; everything in §6 of `literature/illumination-theorem-reference.md`.
