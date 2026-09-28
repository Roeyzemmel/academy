---
id: OBS-16
aliases: [M10]
title: "The M_12 (Q2) failure is not a lifted non-illumination"
summary: "Draft: for both M_12 members the unmet orbitals gr(T^{±1}) are not the lift of an unmet pair on any quotient examined; the mechanism is the Z/6 core monodromy of M → M/⟨T⟩ missing the generators."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
topics: [drafts, quotients, obstructions]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [OBS-9, OBS-10, OBS-11, OBS-12, OBS-13, OBS-14, OBS-15]
source: "writing/n8-quotient-mechanism.md §8 (M10)"
added: 2026-09-24
body_status_ack: "the body's 'Proved' refers to other items (M2–M5)"
---

## Statement

<!-- copied from writing/n8-quotient-mechanism.md §8, item M10; the draft stays the working copy -->

> **M10 (the answer; assembles M3–M9; Not settled).** For both N8 members, the unmet orbitals $\mathrm{gr}(T^{\pm1})$ are
> **not the lift of an unmet pair on any quotient**. In every intermediate origami (M6), in every half-translation quotient
> except the listed ones (M8), and in all but three $K_4$-quotients (M9), the images are either identified or illuminated.
> Where the non-illumination does descend, it is equivalent to the one on $M$ and not independently explained.
> **The mechanism is (c), in monodromy form.** $M\to E=M/\langle T\rangle$ is a $\mathbb Z/6$ cover of the 4-square torus. Its
> core monodromies are $\pm\tfrac12(d_a+d_b)$ (M4), and they lie in $\langle2\rangle\cup\langle3\rangle$ and miss the generators (M5).
> Equivalently, (a) holds with the FMZ pillowcase $M/\langle\delta\rangle$, where the pair collapses and the statement is "pair sums of the corner exponents are
> never of order 6 in $\mathbb Z/12$".

**Relation to R2 §4.5.** The failing orbitals are graphs of centralising elements, which is the $(\delta,T)$ branch of $\mathrm{inv}$.
So the failure is (CT′)(i) at the translation quotient $M\to M/\langle T\rangle$, which R2 §4.5 lists as a quotient by translations.
It is **not** the "neither torus nor translation quotient" branch. A computed check makes this sharper:
- **Member 2** satisfies (2T′): 23 orbitals and 23 level sets. This agrees with the N8 verifier runs.
- **Member 1 fails (2T′)**: the level sets $(\pi_u,\ast)$ and $(\pi_r\pi_u,\ast)$ each split into two orbitals of size 72. So member 1 **does** have an
  intermediate cover of the R2 §4.5 kind. Those split orbitals are nevertheless **met** ($R^{\mathrm{pow}}$ misses only $\mathrm{gr}(T^{\pm1})$).

The place R2 §4.5 calls natural to look is present in member 1 and is not where (Q2) fails.

**Relation to W7 (the covering criterion).** M3–M5 are W7 at level (A3), with the garage base $P'$ replaced by the translation surface
$E\setminus V$ and $D=\langle T\rangle\cong\mathbb Z/6$ cyclic. The classes of the folded cylinder cores become the classes of the closed geodesics of $E$, and their cyclic
subgroups $\langle0\rangle,\langle2\rangle,\langle3\rangle$ cover $\mathbb Z/6$ except for the deck elements $d=T^{\pm1}$. The one feature to carry into P2 of the
(A4) note is this. **A cyclic deck group of composite order can be missed even though every prime-order quotient cover is hit.**
So the first stage of P2 must test "some core class generates $d$", not "$\varphi_T\ne0$ on some core".

**What would overturn "not a lift"** (earning the flag): a quotient $Q=M/H$ in which the images are distinct and non-illumination is provable in $Q$
without passing through M3. The class examined is all intermediate origamis (complete, M6), all 6+14 derivative-$(-I)$ involutions (complete, M8), all
12+36 (A3) Klein groups (complete except three, M9), and $\mathrm{Aff}_{K_4}$. Not examined: quotients by a single reflection $\langle\mu_a\rangle$ or
$\langle\nu_b\rangle$ (non-orientable or with boundary; the targets are of reflection type, so M9(4) applies to them too), and quotients that are not global,
such as branched covers onto other surfaces that do not come from a group action.

**Hand-off.**
- **For `/verify-claim`:** M3, M4 and M7 are the substantive arguments. M5, M6, M8 and M9 rest on them plus the hand-check. M4 generalises
  N8 to the whole FMZ family as a *criterion for the graphs $\mathrm{gr}(\delta^{2s})$ only*. It says nothing about other orbitals.
- **For `/hunt`:** M4 predicts, without any $|G|^2$ BFS, which $M_N(a)$ fail (Q2) on $\mathrm{gr}(\delta^{2s})$. They are exactly the $N,a$ for which some
  $2s\ne0$ is outside $\bigcup\langle d_a+d_b\rangle$. That is a cheap pre-filter, and a necessary-and-sufficient test for those orbitals, to compare against
  the ten unverified FALSE members at $N=12$. *(revised 2026-09-24, second pass)* Applying M4 across the family requires its
  hypotheses for each member: that $M/\langle\delta\rangle$ is the pillowcase $E_0/\langle-I\rangle$, and freeness off $\Sigma^*$.
  These can be checked member by member as in M5, or taken from the FMZ construction as an input. **N15 (Proved) already gives the
  group-theoretic test on the translation orbitals** for the whole recipe:
  $\mathrm{gr}(T_t)\cap R^{\mathrm{pow}}=\varnothing\iff t\notin\bigcup\langle a_i+a_j\rangle$. M4 is its geometric counterpart and
  adds nothing to it as a filter.

## Proof

The argument is in [writing/n8-quotient-mechanism.md](../writing/n8-quotient-mechanism.md) §8, item M10, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/n8-quotient-mechanism.md §8 (M10) during the relabelling.
