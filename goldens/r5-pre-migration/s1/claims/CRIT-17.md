---
id: CRIT-17
aliases: [R2 Thm 4.7]
title: "Master criterion: GA-2T′ ⇒ [(Q2) ⇔ GA-CT′]"
summary: "GA-2T′ holds for abelian G, under GA-2T, or under GA-EP∧GA-HA; under GA-2T′, (Q2) ⇔ GA-CT′; GA-CT′ is necessary for (Q2) with no hypothesis. Recovers CRIT-12 and CRIT-15."
kind: thm
status: Proved
topics: [q2-criteria, orbitals]
depends_on: [CRIT-11, CRIT-12, CRIT-14, CRIT-15]
source: notes/03-q2/orbitals.md:113-134
added: 2026-09-24
---

## Statement

**Theorem 4.7.** (a) (2T′) holds if $G$ is abelian, or if (2T) holds, or if (EP)∧(HA) hold.
(b) Under (2T′): **(Q2) ⇔ (CT′)**. (c) (CT′) is necessary for (Q2) without any hypothesis.
(d) If $Z=1$, (2T′) is (2T) and (CT′) is (D0): Theorem 4.2. If (EP)∧(HA), (CT′)(ii) is
automatic and (CT′)(i) is (CT): Theorem 4.5.

## Proof

*Proof.* (a) Abelian: $Z=G$, $z(i,j)$ is the element carrying $i$ to $j$ and the level sets
are the orbitals of the regular action. (2T): by Prop. 4.4(d) either $Z=1$ or $G$ is
abelian regular. (HA): Theorem 4.5(a)–(c) lists the orbitals as exactly the level sets
of $\mathrm{inv}$. (b) ⇐: each level set is one orbital, and (CT′) exhibits an element of
$R^{\mathrm{pow}}$ in each (for $(\delta,T)$ use Prop. 4.4(b); for $(\delta,\ast)$ the given
pair $(i,u^mi)$ has $d=\delta$ and $z=\ast$). ⇒ is (c): $\mathrm{gr}(T)\subseteq R^{\mathrm{pow}}$
is (i) by Prop. 4.4(b), and $(\delta,\ast)\subseteq R^{\mathrm{pow}}$ is (ii). (d) For $Z=1$,
$z\equiv\ast$; for $\delta\ne0$ (ii) holds with any representative; for $\delta=0$ (ii) is
(D0). Under (HA), (ii) for $\iota\ne0$ holds with $\sigma,\tau,\sigma\tau$ (none lies in $Z$, as
$G$ is nonabelian) and for $\iota=0$ with $\sigma^2$ or $\tau^2$. $\square$

*Meaning.* (2T′) says: the only refinements of the difference classes are the graphs of
centralising elements — the intermediate covers $M\to E_\Lambda$ and $M\to M/T$ account
for all orbitals. Conversely, an origami violating (2T′) has a $G$-orbital not of this
form, hence (by the Galois correspondence) an intermediate cover $M\to M'\to\mathbb T^2$
that is neither a torus quotient nor a quotient by translations — the natural place to
look for a (Q2) counterexample.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/orbitals.md:113-134 (relabel map).
