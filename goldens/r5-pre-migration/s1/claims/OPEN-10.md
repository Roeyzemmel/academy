---
id: OPEN-10
aliases: [R §7 item 4]
title: "Under PA-SC, the involution μν is hyperelliptic (answered)"
summary: "For ι = μν: under PA-SC, χ(P)=1 so μν has 2g+2 fixed points and M/⟨μν⟩ is the double of P. Attested by Roey 2026-09-24, not machine-verified."
kind: open
status: Proved
status_note: for ι = μν; attested by Roey 2026-09-24; not machine-verified
level: PA-SC
topics: [open, symmetry, geometry]
depends_on: [GEO-4, GEO-2, GEO-8, GEO-9]
source: OPEN.md:80-82
added: 2026-09-24
cleared_by: [computation/verdicts/2026-09-24_OPEN-10-attestation.md]
---

## Statement

Under PA-SC (with PA-4), the involution $\mu\nu$ is hyperelliptic: $M/\langle\mu\nu\rangle$
is the double of $P$, a sphere, and $\mu\nu$ has $2g+2$ fixed points. More generally, for a
PA-4 garage, $\mu\nu$ is hyperelliptic iff $\chi(P)=1$. (Attested by Roey, 2026-09-24; not
machine-verified.)

### R §7 item 4, verbatim:

4. Under (SC), is the involution of (A2) hyperelliptic? Equivalently, does
   $M/\langle\iota\rangle$ have genus 0 / does $\iota$ have $2g+2$ fixed points?
   (Roey's observation, Remark 1.3.)

## Notes

- **2026-09-24.** Lead from the GEO-32 verification (2026-09-24), not verified as an item:
  for any PA-4 garage, the fixed points of $\mu\nu$ are exactly the lifts of the odd corners,
  and $\chi(M)=4\chi(P)-\#\mathrm{odd}$. So $\mu\nu$ has $2g+2$ fixed points iff $\chi(P)=1$;
  equivalently $M/\langle\mu\nu\rangle$ is the double of $P$. That would answer this item
  affirmatively for $\iota=\mu\nu$. Both `claim-verifier` runs on GEO-32 observed this;
  neither verified it as an item (`computation/verdicts/2026-09-24_GEO-32.md`).
- **2026-09-24.** Scope: this attestation covers $\iota=\mu\nu=\phi(-1,-1)$, the involution
  the garage provides. Whether *every* OA-2 involution of $M$ is hyperelliptic under PA-SC
  is not covered, and remains open.

## History

- 2026-09-24: migrated verbatim from OPEN.md:80-82 (relabel map).
- 2026-09-24: added a Notes lead from the GEO-32 verification
  (`computation/verdicts/2026-09-24_GEO-32.md`); status unchanged.
- 2026-09-24: status Not settled → Proved (verdict computation/verdicts/2026-09-24_OPEN-10-attestation.md)
- 2026-09-24: attestation applied per `computation/verdicts/2026-09-24_OPEN-10-attestation.md`
  (Roey, verbatim: "OPEN-10 does hold, I vouch for it."). Statement rewritten to the verdict's
  Allowed wording, scoped to ι = μν; verbatim R §7 item 4 kept under its own sub-heading;
  depends_on gained GEO-8, GEO-9 (unfolding model and corner↔commutator table); title/summary
  updated to reflect the answered, attested status.
