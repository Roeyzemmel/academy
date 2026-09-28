---
id: GEO-32
aliases: []
title: "PA-SC and PA-5 are incomparable"
summary: "Garage level: an 8-square fan (one 4π corner) is PA-SC but not PA-5; the 3×3 square frame (embedded, not simple) is PA-5 but not PA-SC"
kind: prop
status: Proved
status_note: garage-level reading; origami-level half (a) too
level: PA-4
topics: [assumptions, unfoldings]
depends_on: [GEO-9]
cites: [CW12]
examples: []
source: "new; adapts the (SC)/(A5) remark of archive R §0.2 to the new PA-5"
added: 2026-09-24
cleared_by: [computation/verdicts/2026-09-24_GEO-32.md]
---

## Statement

(Garage level.) There is a PA-4 garage that is simply connected and not PA-5, and one that is
PA-5 and not simply connected; so neither of PA-SC and PA-5 implies the other, even under
PA-4. Witnesses: the 8-square fan (one $4\pi$ corner, ten $\pi/2$ corners, $\chi=1$; or the
slit $2\times2$ square with one $2\pi$ corner) and the $3\times3$ square frame (embedded, not
simple; corners $\pi/2$ and $3\pi/2$ only, $\chi=0$). The same examples show PA-SC and PA-5w
incomparable. (Origami level, half (a): no garage structure on the fan's unfolding is PA-5,
since $[\sigma,\tau]$ has 4-cycles (GEO-9).)

## Proof

- **PA-SC does not imply PA-5.** Witness: the **8-square fan**, squares $Q_1,\dots,Q_8$
  around one vertex $v$, with $Q_j$ in quadrant $j\bmod4$ and consecutive squares glued along
  their edge from $v$, except $Q_8|Q_1$ — the two-sheeted $[-1,1]^2$ branched at $0$ and cut
  along $[0,1]\times\{0\}$. Corner census: ten corners of angle $\pi/2$, one of angle $4\pi$
  ($m=8$), seven boundary points of angle $\pi$ (not corners), no interior cone points. It has
  $\chi=1$, and Gauss–Bonnet checks: $10\cdot\pi/2-3\pi=2\pi$. It is simply connected (PA-SC)
  but its $4\pi$ corner violates PA-5. Its unfolding has 32 squares, genus 4, in
  $\mathcal H(3,3)$. A smaller witness: the $2\times2$ square slit from its centre to a side
  midpoint, with one $2\pi$ corner, $\chi=1$, unfolding in $\mathcal H(1,1)$. Angles $\ge2\pi$
  are allowed at PA-4: CW12 `parking.tex` l. 503–505, "no apriori upper bound on the angle at
  a vertex".
- **PA-5 does not imply PA-SC.** Witness: the $3\times3$ square frame (embedded, not simple —
  a polyomino with a hole). Its corners are $\{\pi/2{:}4,\ 3\pi/2{:}4\}$ only, so it is PA-5;
  it has $\chi=0$, so it is not simply connected.
- **Origami-level half (a).** No garage structure on the 8-square fan's unfolding $M$ is PA-5:
  the commutator $[\sigma,\tau]$ has two 4-cycles, and by GEO-9 a PA-5 garage's corners are all
  odd multiples of $\pi/2$, hence produce only odd cycles (GEO-9's table: corner of angle
  $m\pi/2$ even gives two cycles of length $m/2$; PA-5 excludes even $m$). So no PA-5 garage
  structure unfolds to this $M$.

## Notes

- **Origami-level half (b), not part of the label.** No garage structure on the $3\times3$
  frame's unfolding $M$ is simply connected. Two routes, both from the verdict:
  - *Enumeration route.* Both runs enumerate the free $K_4$-structures on $M$ (run A: 16
    commuting pairs, one of which is a garage; run B: 9 structures, one of which is a garage)
    and check none is simply connected.
  - *Hyperellipticity route (run A's hand route).* A simply connected $P$ forces $\mu\nu$ to
    have $2g+2=12$ fixed points, but the derivative-$(-I)$ involutions on $M$ have 8, 0, 8 and
    8 fixed points respectively — none reaches 12. Run A derived these counts by hand from the
    frame's symmetries; only $|C|=4$ came from a script. Run B notes that, under this repo's
    rule, its computational route alone would give at most "modulo".
- **Understated (run B).** The 6-square fan has a $3\pi$ corner and satisfies PA-4, PA-SC and
  PA-5w but not PA-5. So PA-SC does not imply PA-5 even under PA-5w. The same examples also
  show PA-SC and PA-5w incomparable (run A finding F4), which until now rested on R §0.2 alone
  (the same Gauss–Bonnet gap).

## History

- 2026-09-24: created with the new PA-5 (the old statement, for PA-5w, stays verbatim in
  R §0.2).
- 2026-09-24: status Not settled → Proved (verdict computation/verdicts/2026-09-24_GEO-32.md)
- 2026-09-24: cleared Proved (garage-level reading, origami-level half (a) too) on
  `computation/verdicts/2026-09-24_GEO-32.md` — two sequential `claim-verifier` runs on
  claude-opus-5-5 (equal primary, Roey 2026-09-24), both Proved/CONFIRMED, no inputs.
  Statement replaced with the verdict's Allowed wording; Proof transcribed from the verdict's
  findings (8-square fan and slit 2×2 square witnesses, CW12 citation, 3×3 frame witness,
  origami-level half (a) via GEO-9). Origami-level half (b) and the understated 6-square-fan
  remark added under Notes, not part of the label. `depends_on: [GEO-9]`, `cites: [CW12]` set.
- 2026-09-24: PA-5 restated on the unfolding (semi-corners only at relative marking points);
  the class is unchanged (GEO-9), so this item stands as cleared.
