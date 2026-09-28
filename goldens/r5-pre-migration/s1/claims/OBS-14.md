---
id: OBS-14
aliases: [M8]
title: "Half-translation quotients M/⟨g⟩ of the M_12 members, g a −I involution"
summary: "Draft: in M/⟨g⟩ the pair (x, Tx) is illuminated when gT is an involution with regular fixed points; otherwise the non-illumination descends, but only equivalently, via OBS-13."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
topics: [drafts, quotients]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [OBS-7, OBS-13, OBS-8, OBS-11, OBS-12]
source: "writing/n8-quotient-mechanism.md §6 (M8)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/n8-quotient-mechanism.md §6, item M8; the draft stays the working copy -->

> **M8 (classification of $M/\langle g\rangle$, $g$ a derivative-$(-I)$ involution; M1 + M7 + M2; Not settled).** In
> $N_g=M/\langle g\rangle$ the image of $Tx$ is $\{Tx,gTx\}$, and $gT$ has derivative $-I$.
> - **Illuminated** when $gT$ is an involution with regular fixed points. These are member 1's $\iota_{3,11,19}$, which include N8's $\iota$, and member 2's
>   $\iota_{3,5,7,11,13,15,19,21,23}$, which include N8's $\iota_7$. Explicit witness: if $gT$ fixes the midpoint $p$ of the top edge of square $k$, then
>   the segment from $x_k(z)$ through $p$ ends at $gTx_k(z)$ for **every** $z\in(0,1)^2$. It lies in squares $k$ and $\tau k$, so it
>   meets no corner. Exact tracing confirms this for $k=0$ in both members: $\iota_{19}T(0)=15=\tau(0)$ and $\iota_7T(0)=3=\tau(0)$.
>   So $\bar x_0(z)$ illuminates $\bar x_4(z)$ in $N_g$.
> - **Descends** when $gT$ has no regular fixed point or $(gT)^2\ne1$. These are member 1's $\iota_{7,15,23}$ and member 2's
>   $\iota_{0,12}$ (where $gT$ has order $>2$) and $\iota_{1,9,17}$. By M7, $x$ never illuminates $gTx$. Together with M5, $\bar x$ never illuminates
>   $\overline{T^{\pm1}x}$ in $N_g$, for every $x$. This **is** a non-illumination on a half-translation surface, but it is **equivalent** to the one on $M$
>   through M7. $T$ does not normalise $\langle g\rangle$ when $gTg^{-1}=T^{-1}$, so there is no $N_g/\bar T$. Every larger quotient
>   $M/H'$ with $H'\supsetneq\langle g\rangle$ and $H'\cap Z\ne1$ either contains $T$, so the pair collapses, or contains a translation $h$
>   with $hT\notin\{1,T^{\pm1}\}$, so the pair is illuminated (the M6 argument). We have found no quotient in which this
>   descended non-illumination is proved without M3–M5. That is a judgement about the proofs available, not a theorem.
> - **The FMZ quotient $\langle\delta\rangle$** contains $T=\delta^2$, so the pair collapses. This is where the mechanism is visible (M4, M5).

## Proof

The argument is in [writing/n8-quotient-mechanism.md](../writing/n8-quotient-mechanism.md) §6, item M8, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/n8-quotient-mechanism.md §6 (M8) during the relabelling.
