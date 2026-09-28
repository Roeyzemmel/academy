---
id: CRIT-20
aliases: [R2 Prop 6.1]
title: "Mid-line reflections of P satisfy GA-CT"
summary: "If θ reflects P in a vertical (horizontal) mid-line, σ (τ) has a T_θ-invariant orbit, so gr(T_θ) is met. Proved under PA-6; Reduced in general to row segments of length ≤2."
kind: prop
status: Reduced
status_note: "Proved under PA-6; Reduced in general (to row segments of length ≤2)"
level: PA-6
topics: [symmetry, q2-criteria]
depends_on: [STR-4, CRIT-14]
source: notes/03-q2/establishing-HA-CT.md:66-73
added: 2026-09-24
body_status_ack: "deliberate: Proved under PA-6 only, Reduced in general; see History"
---

## Statement

**Proposition 6.1 (Proved under (A6)).** Let $\theta$ be a reflection of $P$ in a vertical
mid-line ($\lambda$ swaps $L\leftrightarrow R$, $\iota(T_\theta)=(1,0)$). Then $\sigma$ has a
$T_\theta$-invariant orbit; symmetrically $\tau$ for horizontal mid-lines. *(The axis
$x=c$, $c\in\frac12+\mathbb Z$, meets the connected symmetric $P$ in the interior of a cell $s$;
$\theta s=s$, so the row segment of $s$ is $\theta$-invariant, and $T_\theta$ maps the
$\sigma$-orbit $\{(s',e),(s',e+(1,0)):s'\in\rho(s)\}$ to itself.)* For a general datum with
fixed-point-free $\theta$ the statement is **Reduced** to the case where all row segments have
length $\le2$.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/establishing-HA-CT.md:66-73 (relabel map).
- 2026-09-24: label set to Reduced with note "Proved under PA-6", as in the old STATUS.md row ("Proved under (A6); Reduced in general"); the item's own heading reads "Proved under (A6)".
