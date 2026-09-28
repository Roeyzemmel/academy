---
id: OBS-11
aliases: [N20, M5]
title: "Pillowcase criterion applied to the two M_12 members"
summary: "In both M_12 members δ = ι₂ meets OBS-10's hypotheses; corner monodromies {1,3,3,5} / {1,5,7,11}, pair-sum subgroups cover {0,4,6,8} ∌ ±2, so no x illuminates T^{±1}x."
kind: prop
status: Proved
topics: [obstructions, pillowcase-covers, counterexamples]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [OBS-10, OBS-9, OBS-8]
source: notes/03-q2/families-hunt.md:790-834
added: 2026-09-24
---

## Statement

### N20 (Proved) — the N8 instance

**N20.** In both N8 members $\delta=\iota_2$ satisfies N19's hypotheses:
$\langle\delta\rangle$ is free off $\Sigma^*$ (the only involution in $\langle\delta\rangle
\cong\mathbb Z/12$ is $\delta^6=T^3$, a translation, which fixes no regular point), and
$Q_0=M/\langle\delta\rangle$ is the pillowcase $E_0/\langle-I\rangle$ with
$E=M/\langle\delta^2\rangle=\mathbb R^2/2\mathbb Z^2$ (N18) and $\bar\delta=-I$ (since a
corner of $Q_0$, angle $\pi$, must be a branch point of $E\to Q_0$ with a single fixed
preimage in $V=\mathbb Z^2/2\mathbb Z^2$).

The corner monodromies, computed as $\delta^{d_v}(i)=\tau^{-1}\sigma^{-1}(i)$ for $i$ with
lower-left corner at $v$, are $\{1,3,3,5\}$ (member 1) and $\{1,5,7,11\}$ (member 2) — the
same quadruples $a$ that index the members in the cyclic-cover family. The pair sums over the
three pairings are $\pm6,\pm4,\pm4$ (member 1) and $\pm6,\pm4,0$ (member 2), so the union of
subgroups they generate is $\{0,4,6,8\}$ in both cases.

**$T^{\pm1}=\delta^{\pm2}$ and $\pm2\notin\{0,4,6,8\}$, so no $x\in M\setminus\Sigma^*$
illuminates $Tx$ or $T^{-1}x$.** By N19's converse, $T^{\pm2}x$ and $T^3x$ **are** reached,
but only outside a finite exceptional set, not from every $x$ as an earlier reading of this
argument claimed: for member 1, $T^3x$ is reached iff $x$'s image avoids the horizontal-edge
midpoints, and $T^{\pm2}x$ is reached from every $x$ (the two other exceptional sets are
disjoint); for member 2, $T^3x$ is reached iff $x$'s image avoids the vertical-edge
midpoints, and $T^{\pm2}x$ is reached iff it avoids the square centres. These values are
consistent with, and sharper than, the group-theoretic bound of [N8p] Lemma 3.2 / §2.3 (which
only bounds two of the three parity classes by $\{0,\pm2\}$ without excluding $0$).

**What this settles.** N8 lead (a) — "pillowcase monodromies $\pm(a_i+a_j)$ never of order
6" — is here an **argument**, not merely an arithmetic coincidence, for the two N8 members:
the $d_v$ are computed directly from the stored permutations, so the FMZ identification of
`CyclicCover`'s labelling with FMZ's $\mathbb Z/N$ action (N8 lists this as open) is **not
needed** for this geometric reading, on these two members. N8 lead (b) ("no 12-cycle") is the
same fact seen from $G$: a $T$-invariant cycle would need a unit core value.

*Cleared by.* Two `claim-verifier` runs, both Proved, no inputs (FMZ identification not
used), sequential, both on `claude-opus-5-5`; see `computation/verdicts.md`, entry
"2026-09-24 — M2–M5 (writing/n8-quotient-mechanism.md), after repair → N17–N20". Source:
`writing/n8-quotient-mechanism.md` §4 (M5).

**Scope of N17–N20, exactly.** These four items cover the "no $D_4$", the monodromy, and the
pillowcase parts of `writing/n8-quotient-mechanism.md` (M2–M5) only. **M1** (the
definition/lemma on quotient illumination) and **M6–M10** (the explicit quotient table,
non-descent through intermediate origamis, half-translation and reflection quotients, and
the final assembly answering Roey's question in full) are **Not settled** and, if mentioned,
must be described as such — in particular, the claim that *no* quotient of either N8 member
carries the failure independently of M3–M5 (M10's "the answer") is not covered by this pass.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:790-834 (relabel map).
