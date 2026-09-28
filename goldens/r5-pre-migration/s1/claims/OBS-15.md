---
id: OBS-15
aliases: [M9]
title: "K₄ and D₄ quotients of the M_12 members"
summary: "Draft: no D₄; every OA-3 K₄-quotient is non-orientable (so not PA-4); N8's own K₄ does not carry the failure; all but three of member 2's 36 K₄'s have explicit witnesses."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
topics: [drafts, quotients, symmetry]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [OBS-8, OBS-13, OBS-14, GEO-7]
source: "writing/n8-quotient-mechanism.md §7 (M9)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/n8-quotient-mechanism.md §7, item M9; the draft stays the working copy -->

> **M9 ($K_4$ and $D_4$ quotients; computed plus M7; Not settled).**
> 1. There is **no $D_4$** (M2(1)). The largest "folding" is by $\mathrm{Aff}_{K_4}(M)$. The quotient is a rectangle table, $[0,\frac12]\times[0,1]$
>    for member 1 and $[0,\frac12]^2$ for member 2. It contains $T$, so the pair collapses there. On this table the failure reads: "no
>    billiard loop at $\bar p$ that returns with its direction, and so lifts to a translation, has $\mathrm{Aff}_{K_4}$-monodromy $T^{\pm1}$". That is M3/M4
>    again, not a non-illumination.
> 2. **Every (A3) $K_4$-quotient is non-orientable**: all 12 for member 1 and all 36 for member 2. For member 1 each has one boundary circle.
>    For member 2 the quotients are closed (18 of them) or have one or two boundary circles (12 and 6). None is a
>    parking garage. Under (A4), $M/\Phi=P$ is orientable (R Prop. 1.4, R §1.2 splitting). So this is an **independent route to N11's
>    "not (A4)"**, by orientability rather than by N10's fixed-point count.
> 3. **N8's own $K_4$ does not carry the failure.** In $M/\langle\mu,\nu\rangle$ the image of $Tx$ is $\{Tx,\mu Tx,\nu Tx,\iota Tx\}$, and the $\iota T$-witness of M8
>    applies. In member 1 there is also a horizontal witness: $\mu_1T(i)\in\langle\sigma\rangle i$ for 8 squares $i$, and a horizontal segment
>    from $x_i(z)$ ends at $\mu_1 Tx_i(z)$ for every $z$.
> 4. **The other $K_4$'s.** All 12 of member 1's and 33 of member 2's 36 have an explicit witness of one of these three kinds:
>    - $\iota T$ has a regular fixed point;
>    - $\mu T(i)\in\langle\sigma\rangle i$;
>    - $\nu T(i)\in\langle\tau\rangle i$.
>
>    The three exceptions are member 2's $\langle\mu_{12},\nu_5\rangle$, $\langle\mu_{12},\nu_{13}\rangle$ and $\langle\mu_{12},\nu_{21}\rangle$, whose $\iota$ are $\iota_{17},\iota_1,\iota_9$. They are **undecided**. The
>    $\iota T$-target is excluded by M7. The reflection targets $\mu_{12}T x$ and $\nu T x$ have no horizontal or vertical witness, and no
>    orbit-closure argument is available for them, because the relation $y=\mu Tx$ is not complex-linear. Deciding them is a
>    bounded search over holonomies from one named point, so it belongs on the queue, not the laptop. Either outcome would at most be an
>    *equivalent* descent, as in M8.

## Proof

The argument is in [writing/n8-quotient-mechanism.md](../writing/n8-quotient-mechanism.md) §7, item M9, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/n8-quotient-mechanism.md §7 (M9) during the relabelling.
