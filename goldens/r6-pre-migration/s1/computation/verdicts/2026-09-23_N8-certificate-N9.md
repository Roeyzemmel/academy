---
id: "2026-09-23_N8-certificate-N9"
date: "2026-09-23"
kind: "claim"
subjects: ["CEX-2"]
clears: ["CEX-2"]
decision: "Theorems A, B and Corollary 5.1 → Proved (agreement: run A's Theorems-A/B"
source: "computation/verdicts.md:932-1004 (HEAD 2026-09-24)"
---

## 2026-09-23 — N8 conceptual certificate (writing/n8-counterexample-proof.md)

Kind: claim. Claim it bears on: N8's conceptual certificate for (Q2) failing at level (A3)
for $M_{12}(1,5,7,11)$ and $M_{12}(1,3,3,5)$, and the geometric consequence (Cor. 5.1) and the
generic-fibre reading (R2 Thm 2.2), all in `writing/n8-counterexample-proof.md`.
Commit audited: n/a (claim verification, not a result JSON)

Run A (Theorems A and B), verbatim:

```
VERDICT
item:       N8 conceptual certificate — Theorem A (M_12(1,5,7,11)) and Theorem B (M_12(1,3,3,5)), writing/n8-counterexample-proof.md
label:      Proved
confidence: CONFIRMED
model:      Fable 5.1 (primary)
inputs:     none for Theorems A and B (the name "M_12(a)" as FMZ's surface is an open identification affecting only the name)
blocking:   none
```

Run A (§5 geometric consequence), verbatim:

```
VERDICT
item:       N8 conceptual certificate — geometric consequence (§5): Cor. 5.1 and the R2 Thm 2.2 reading
label:      Proved modulo stated inputs
confidence: CONFIRMED
model:      Fable 5.1 (primary)
inputs:     Cor. 5.1 (non-illumination, every base point): none beyond R2 Lemma 2.1(a) / R Prop. 4.1 (recorded Proved). The "iff" and the "(Q2) = mutual illumination on a generic fibre" reading: EMM Thm 2.1 and Smillie–Weiss, via R2 Thm 2.2
blocking:   the two named inputs of R2 Thm 2.2, for the "iff" half only
```

Run B, verbatim:

```
VERDICT
item:       N8 conceptual certificate — Theorem A (M_12(1,5,7,11)) and Theorem B (M_12(1,3,3,5)) with Lemmas 1.1–1.2, Prop. 1.3, Prop. 2.1, Lemmas 3.1–3.2, and Corollary 5.1 (writing/n8-counterexample-proof.md)
label:      Proved
confidence: CONFIRMED
model:      Fable 5.1 (primary)
inputs:     none for Theorems A and B (definitions of R §0 / R2 §0.1; R2 Prop. 4.4(a), Proved, for the orbital identification, also proved directly). Corollary 5.1 rests on R2 Lemma 2.1(a) / R Prop. 4.1, recorded Proved. The write-up's §5 item 2 (positive half of illumination for member 2; generic-fibre reading of "(Q2) fails") is Proved modulo EMM Thm 2.1 and Smillie–Weiss via R2 Thm 2.2, as the write-up itself states, and is not covered by this label.
blocking:   none
```

Runs were sequential — run B was dispatched only after run A returned positive; both on the
primary model, Fable 5.1; neither on a fallback.

Decision: Theorems A, B and Corollary 5.1 → **Proved** (agreement: run A's Theorems-A/B
verdict and run B's combined verdict, which also covers Cor. 5.1). §5 item 2 (the positive
half of illumination for member 2, and the generic-fibre reading of "(Q2) fails") stays
**Proved modulo** EMM Thm 2.1 and Smillie–Weiss, via R2 Thm 2.2 — both runs agree this is
unchanged from R2 Thm 2.2's own recorded status, not a new clearance.

Non-blocking findings, both runs: the FMZ name "M_12(a)" for the `CyclicCover` labelling is
still an open identification (affects the name only, not the group-theoretic content); the
p/q letter-count wording in the N8 block is swapped relative to R2 §0.1 (harmless — the
argument is symmetric in the two counts); run B notes Corollary 5.1 would also follow
directly from the certificate via holonomy without invoking R Prop. 4.1 as a separate step;
both runs independently computed, for member 1 too, $R^{\mathrm{pow}} = \Omega^{(2)}
\setminus (\mathrm{gr}(T) \cup \mathrm{gr}(T^{-1}))$, $|R^{\mathrm{pow}}| = 504$ — a
computational corroboration, not part of either label.

Allowed wording: Theorems A and B of `writing/n8-counterexample-proof.md` — the
group-theoretic certificates for (Q2) failing at level (A3) on $M_{12}(1,5,7,11)$ and
$M_{12}(1,3,3,5)$ (as N8 already states, now with an enumeration-free proof for member 1
too) — are **Proved**, citable without a computational enumeration of $W$. Corollary 5.1 (no
base point $z$, torsion or not, has $x_i(z)$ illuminating $x_{i\pm4}(z)$) is **Proved**,
resting only on R2 Lemma 2.1(a). The generic-fibre "(Q2) fails" reading and the positive half
of illumination for member 2 remain **Proved modulo** EMM Thm 2.1 and Smillie–Weiss (R2
Thm 2.2's own status, unchanged).
Open: the FMZ identification of the labelling's name; whether the write-up's other computed
data (element-order counts, $G^{\mathrm{ab}}$ for member 1) or its appendix script were
independently reproduced — neither run reports rerunning the appendix script, only checking
the mathematics it corroborates.
