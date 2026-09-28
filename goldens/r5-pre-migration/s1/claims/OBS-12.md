---
id: OBS-12
aliases: [M6]
title: "No intermediate origami of the M_12 members carries the (Q2) failure"
summary: "Draft: all 13 / 28 proper block systems give quotient origamis satisfying (Q2), and the images of (i, T^{±1}i) there either coincide or are met; so the failure is not lifted from a quotient origami."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
topics: [drafts, quotients]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [CEX-2, GEO-30]
cites: [EMM15, SW08]
source: "writing/n8-quotient-mechanism.md §5 (M6)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/n8-quotient-mechanism.md §5, item M6; the draft stays the working copy -->

> **M6 (no intermediate origami carries the failure; computed; Not settled).** An intermediate origami is a
> cover $M\to M'\to\mathbb T^2$, the same thing as a $G$-block system. It includes every $M/H$ with $H\le Z$. Member 1 has
> **13** proper nontrivial block systems and member 2 has **28**. For each, the quotient origami $M'$ satisfies (Q2),
> with a positive certificate: all pairs are met by Christoffel values of size at most 8. For each, the images of
> $(i,T^{\pm1}i)$ either
> - coincide: the column system, which gives $E$ ($4\times6$ blocks, $|G_q|=4$), and the three systems of 2 blocks; or
> - are distinct and met in $M'$.
>
> So the failure is **not** a W5-lift from any quotient origami, whether a translation quotient or not.
> For $M/\langle T^2\rangle$ and $M/\langle T^3\rangle$ there are explicit segments for **every** $z$ and every $i$, checked by exact tracing:
> - member 1: $\sigma^2=T^3$, a horizontal segment of length 2, is $\equiv T$ in $M/\langle T^2\rangle$. One of $\tau^{\pm2}$, vertical of length 2, gives $T^4\equiv T$ in $M/\langle T^3\rangle$.
> - member 2: $\tau^2=T^3$, vertical of length 2, handles $M/\langle T^2\rangle$. One of the holonomies $\pm(2,2)$ gives $T^4$, for $z_1\ne z_2$, which handles $M/\langle T^3\rangle$.
>
> For a general $1\ne H\le Z$ with $T\notin H$ there is always an $h\in H$ with $hT\notin\{1,T^{\pm1}\}$: take $h=T^2$ if
> $H=\langle T^2\rangle$, and any $h\ne T^{-2}$ otherwise. By Theorem A (member 2), or by the recorded and re-checked computation
> $R^{\mathrm{pow}}=\Omega^{(2)}\setminus\mathrm{gr}(T^{\pm1})$ (member 1, reproduced here at $K\le8$), the pair is then met.
> The geometric reading at non-torsion $z$ uses R2 Thm 2.2, which is Proved modulo EMM and Smillie–Weiss.

## Proof

The argument is in [writing/n8-quotient-mechanism.md](../writing/n8-quotient-mechanism.md) §5, item M6, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/n8-quotient-mechanism.md §5 (M6) during the relabelling.
