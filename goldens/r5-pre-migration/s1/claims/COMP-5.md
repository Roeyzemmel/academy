---
id: COMP-5
aliases: [W8]
title: "A completeness route for GA-CT′(i) that avoids the |G|² BFS"
summary: "Sketch: for T of prime order, GA-CT′(i) fails iff the class of M→M/⟨T⟩ vanishes on every rational cylinder core; computable from cusp representatives without enumerating G."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
topics: [computation, drafts, quotients, a4-realisation]
examples: [EX-L4]
depends_on: [CRIT-17, OBS-20]
source: "writing/a4-candidate-generation.md §2.4 (W8)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/a4-candidate-generation.md §2.4, item W8; the draft stays the working copy -->

> **W8 (a completeness route that avoids the $|G|^2$ BFS; sketch; Not settled).** For $T$ of
> prime order $p$, the cover $M\to M''=M/\langle T\rangle$ is cyclic, with class
> $\varphi_T\in H^1(M''\setminus V;\mathbb F_p)$. A cylinder level lifts to a $T$-invariant
> cycle exactly when $\varphi_T(\text{core})\ne0$, and all levels of a cylinder are homologous
> off $V$. So **(CT′)(i) fails for $T$ if and only if $\varphi_T$ vanishes on every rational
> cylinder core.**
>
> $M''$ is a lattice surface, so every rational direction is affinely equivalent to one of
> finitely many cusp representatives. The set of values is therefore
> $\{(A^*\varphi_T)(c)\}$, with $A$ ranging over $\mathrm{Aff}(M'')$, a finite orbit in a
> finite module, and $c$ ranging over the cores of the cusp representatives.
>
> This is computable **without enumerating $G$**. That matters here: (A4) groups are huge
> (the L‑tetromino already has $|G|=165888$), so the pipeline's complete $|G|^2$ BFS is out
> of reach for garage unfoldings, and without some such route a FALSE verdict can never be
> certified. The same idea extends to cyclic $T$ of composite order, with $\mathbb Z/k$
> coefficients and the requirement that $\varphi_T(\text{core})$ be a unit.
>
> *To check:* the claim about orbits in punctured homology, and the identification of the
> cover's class with the deck element.

**Heuristic reading of W7** (not proved):
- For **cyclic** covers of an annular $P'$, (CT′)(i) holds as soon as some periodic billiard
  orbit winds once around the hole. In the $3\times3$ ring the diamond orbit of direction
  $(1,1)$ does this, which the hand-check confirms (§5).
- So abelian covers of annuli look unpromising.
- Promising covers are those with **$\pi_1(P')$ of rank at least 2 and $D$ nonabelian**,
  where the billiard classes, like the primitive classes of $F_2$, are a sparse subset.
  The same holds for $P'$ whose short periodic orbits are all homologically constrained, for
  example all of even winding. Whether such $P'$ exist is open. It is a question about
  $P'$ alone, and it is cheap to probe.

**(2T′) at (A4).**

## Proof

The argument is in [writing/a4-candidate-generation.md](../writing/a4-candidate-generation.md) §2.4, item W8, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/a4-candidate-generation.md §2.4 (W8) during the relabelling.
