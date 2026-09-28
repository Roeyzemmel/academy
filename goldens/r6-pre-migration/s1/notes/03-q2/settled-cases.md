# Cases in which (Q2) is settled

> Blocks below are copied verbatim from the archived project docs and keep their
> original numbering. A tag `[R §1.4]` means §1.4 of
> `archive/2026-09-project-docs/christoffel-transitivity-results.md`; `[R2 §4.5]` means
> §4.5 of `…results-2.md`. Inside a block, bare numbers ("Prop. 1.6", "Thm 4.5")
> refer to that block's own document; "R …" inside an R2 block means doc R. S1 is the
> 2026-09-08 working summary, which was never uploaded to the project (see README).
> Find any numbered item in `INDEX.md`.

R's classification at level (A0) and the one-cylinder criterion, followed by R2's consolidated table, which supersedes R's list.

---

## [R §5] (Q2) restated, and the cases where it is settled

Only the **cycle structure** of Christoffel values matters, since powers are free:
$$R^{\mathrm{pow}} = G\cdot\bigcup_{u\in W}\big\{(k,l) : k,l \text{ in a common cycle of } u\big\}.$$
So **(Q2) asks whether the cycle partitions of the Christoffel values, saturated
under $G$ (or $G^+$), cover every pair.**

---

## [R §5.1] Classification of settled cases

> **→ [CRIT-3](../../claims/CRIT-3.md)** (R Thm 5.1) — moved to its own file, 2026-09-24.

> **→ [CRIT-4](../../claims/CRIT-4.md)** (R Rmk 5.2) — moved to its own file, 2026-09-24.

---

## [R §5.2] The one-cylinder criterion, and its exact limits

> **→ [CRIT-5](../../claims/CRIT-5.md)** (R Prop 5.3) — moved to its own file, 2026-09-24.

> **→ [CRIT-6](../../claims/CRIT-6.md)** (R Prop 5.4) — moved to its own file, 2026-09-24.

> **→ [CRIT-7](../../claims/CRIT-7.md)** (R Cor 5.5) — moved to its own file, 2026-09-24.

> **→ [CRIT-8](../../claims/CRIT-8.md)** (R Rmk 5.6) — moved to its own file, 2026-09-24.

---

## [R2 §8] Known cases of (Q2), and examples


---

## [R2 §8.1] Consolidated list of cases in which (Q2) is proved

| # | hypothesis | level | $K$ | source |
|---|---|---|---|---|
| 1 | $G$ 2‑transitive — more generally $G$ 2‑homogeneous, since $R^{\mathrm{pow}}$ is symmetric ($u^ki=j\Rightarrow u^{-k}j=i$), so only $G$-orbits on *unordered* pairs matter | (A0) | 1 | R Thm 5.1(a); never under (RD), $n>4$ |
| 2 | some $u\in W$ is an $n$-cycle (one-cylinder height-one direction) | (A0) | that direction | R Prop. 5.3; impossible for normal $G$ non-cyclic (R 5.4) |
| 3 | $G$ abelian ($\iff$ (A7) under (A6)) | (A0) | $\le p+q$; $\ge2^r+1$ | R Thm 5.1(b), Prop. 7.1 — the trivial level |
| 4 | normal origami with $G$ covered by conjugates of $\langle u\rangle$, $u\in W$ | (A0) | — | R Prop. 5.7; EW, $D_4$, $\mathbb Z/4\times\mathbb Z/2$ |
| 5 | **(2T′) ∧ (CT′)** — the master criterion, containing 3 | (A0) | — | Thm 4.7 |
| 5a | (2T) ∧ (D0) [$Z=1$ or abelian] | (A0) | representatives of $A$ | Thm 4.2 |
| 5b | (EP) ∧ (HA) ∧ (CT) | (A0) | — | Thm 4.5 |
| 5c | (EP) ∧ (HA) ∧ $Z=1$ | (A0) | $\le2$ | Thm 4.5(d) |
| 6 | (RD6), $H^+$ primitive, a corner type with a unique reflex vertex, and $Z=1$ | (RD6) | $\le2$ | Prop. 5.1 + Thm 4.5 |
| 7 | (A6), (HA), and every symmetry of $P$ with linear part in $K_4$ is a mid-line reflection | (A6) | $\le2$ | Thm 4.5 + Prop. 6.1 |
| 8 | (A6), (HA), half-turn symmetries all satisfying the counting criterion | (A6) | — | Prop. 4.4(c) |

**Necessary conditions** (limits to any extension): (CT′) is necessary for (Q2) with no
hypothesis (Thm 4.7(c)); so is (D0) when $n>|A|$; so is "every $G$-orbit on unordered pairs is
met". Under (RD) with $n>4$, cases 1 and 2 are unavailable (Thm 3.4(c)): $G$ is imprimitive,
and an $n$-cycle would act transitively on the four blocks through the quotient
$(\mathbb Z/2)^2$, whose elements have order $\le2$.
