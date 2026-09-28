---
id: COMP-2
aliases: [N2]
title: "Conjugacy pruning of the Christoffel-tree search"
summary: "States (g1,g2) simultaneously conjugate by G (by G^+ under OA-3) have conjugate subtrees, so one per class leaves R^pow unchanged; states drop from |G|² to the class count."
kind: prop
status: Not settled
topics: [computation]
depends_on: []
source: notes/03-q2/families-hunt.md:77-89
added: 2026-09-24
---

## Statement

### N2 (Not settled; expected to clear immediately) — conjugacy pruning of the search tree

**N2.** In the breadth-first search over states $(g_1,g_2)$ of the Christoffel tree evaluated
in $G$, two states that are simultaneously conjugate by an element of $G$ — of
$G^+=G.\Phi$ under (A3) — have conjugate subtrees; and since $R^{\mathrm{pow}}$ is
$G$-saturated, keeping one representative of each class does not change the computed
$R^{\mathrm{pow}}$.

*What it buys.* The state count drops from at most $|G|^2$ to the number of classes.

*What would settle it.* The one-line argument, plus the observation that it needs the
conjugating element to carry the **pair** of generators to the pair simultaneously, not each
separately.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:77-89 (relabel map).
