---
id: 2026-09-24_OPEN-10-attestation
date: 2026-09-24
kind: attestation
subjects: [OPEN-10]
clears: [OPEN-10]
decision: "Roey attests that OPEN-10 holds (for ι = μν): label → Proved, on Roey's word; not machine-verified"
source: "Roey, in session, 2026-09-24"
---
## 2026-09-24 — OPEN-10 (under PA-SC, the OA-2 involution is hyperelliptic): attestation

Kind: attestation, by Roey. This is not a `claim-verifier` pass. It is recorded so that the
label's provenance stays visible.

Roey, verbatim (2026-09-24): "OPEN-10 does hold, I vouch for it."

The argument on record is the lead both `claim-verifier` runs on GEO-32 observed
(`computation/verdicts/2026-09-24_GEO-32.md`). Neither run verified it as an item:

> For any PA-4 garage, the fixed points of $\mu\nu$ are exactly the lifts of the odd corners,
> and $\chi(M)=4\chi(P)-\#\mathrm{odd}$. So $\mu\nu$ has $2g+2$ fixed points iff $\chi(P)=1$;
> equivalently $M/\langle\mu\nu\rangle$ is the double of $P$.

Under PA-SC, $P$ is a disc, so $\chi(P)=1$ and $\mu\nu$ is hyperelliptic.

Decision: **attested → OPEN-10, Proved**, for $\iota=\mu\nu=\phi(-1,-1)$, the involution the
garage provides. Scope: the item asks about "the involution of (A2)". This attestation
covers $\iota=\mu\nu$. Whether *every* OA-2 involution of $M$ is hyperelliptic under PA-SC is
not covered.
Allowed wording: "Under PA-SC (with PA-4), the involution $\mu\nu$ is hyperelliptic:
$M/\langle\mu\nu\rangle$ is the double of $P$, a sphere, and $\mu\nu$ has $2g+2$ fixed points.
More generally, for a PA-4 garage, $\mu\nu$ is hyperelliptic iff $\chi(P)=1$. (Attested by
Roey, 2026-09-24; not machine-verified.)"
Open: a `/verify-claim` pass, if a machine check is ever wanted; and the general-$\iota$ question.
