# Worked examples

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

Hand-checked examples. The validation and regression tables in `computation/` repeat these as test cases.

---

## [R2 §8.2] Examples (hand-checked)

| $P$ | $m$ | $H^+$ | primitive | $H$ | $C(G)$ | orbitals | (2T) | $K_{\min}$ |
|---|---|---|---|---|---|---|---|---|
| L‑tromino | 3 | $S_3$ | yes | $S_3$ | 1 | 4 $=\iota$-classes | yes | 2 |
| L‑tetromino | 4 | $S_4$ | yes | $S_4$ | 1 | 4 | yes | 2 |
| T‑tetromino | 4 | $S_4$ | yes | $S_4$ | $\mathbb Z/2$, mid-line, $\iota=(1,0)$ | 5 | no | 2 |
| S‑tetromino | 4 | $S_4$ | yes | $S_4$ | $\mathbb Z/2$, half-turn, $\iota=(1,0)$ | 5 | no | 3 |
| P‑pentomino | 5 | $S_5$ | yes | $S_5$ | 1 | 4 | yes | 2 |
| U‑pentomino | 5 | $S_5$ | yes | $A_5$ | $\mathbb Z/2$, mid-line | 5 | no | 2 |
| W‑pentomino | 5 | $S_5$ | yes | $A_5$ | 1 (diagonal symmetry $\notin K_4$) | 4 | yes | 2 |
| plus‑pentomino | 5 | $S_5$ | yes | $A_5$ | $K_4$ | $4+3=7$ | no | 2 |
| $2\times3$ rectangle | 6 | $D_2\times D_3$ | no | order 6 | $G$ | 23 $=D_\delta$'s | yes | 3 |
| L of $2\times2$ blocks | 12 | order 2592 | no (blocks of size 3) | order 648 | 1 | 16 $=D_\delta$'s, $A=(\mathbb Z/4)^2$ | yes | 3 |

Every row with $m\ge5$ and (HA) matches Theorem 4.5 exactly (orbitals $=4+|C(G)\setminus1|$);
U5 has $H=A_5$ because $X_L,X_R$ are odd and $Y_B,Y_T$ even permutations there.
