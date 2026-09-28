---
id: "2026-09-21_regression-cadef3e"
date: "2026-09-21"
kind: "result"
subjects: ["regression"]
clears: []
decision: "not cleared (both GAP, and they agree — no wording may be cited)"
source: "computation/verdicts.md:1469-1520 (HEAD 2026-09-24)"
---

## 2026-09-21 — 2026-09-20_christoffel_regression (rerun at cadef3e)

Kind:            result
Claim it bears on: audited against its own header — the regression of `fslab/christoffel/`
against `computation/spec.md` §6.1 and `computation/spec-addendum-2.md` §4, rerun after the
header fixes ordered by the 2026-09-20 audit below.
Commit audited:  `cadef3e` (job `20260920-161100_2026-09-20_christoffel_regression`,
`dirty: false`, `--bound 8`)

Run A: GAP (narrow, header-only; every number right) — earlier findings 1–7 and 9 are fixed
at `cadef3e`. Two still block: (i) lines 18 and 96 of the script say $|G|$ is compared on
**eleven** rows; it is compared on **ten** — plus5 pins `G=None` (line 141) and addendum-2
§4 has an em dash for it, so $|G|=240$ is a new computed datum, not a reproduction; (ii) the
`NAMED_PINS["ORN"]["orb"] = 5` self-pin (line 150) is not fixed — the comment at
lines 148–149 attributes it to the FMZ side computation, which predicts no orbital count.
Independent reproduction without `fslab`, all agreeing: unit 4/4/3/K2; R2x1 8/8/7/K3 with
32/48/56 and $(2,1)$ the only closing direction; L3 648/1/4/K2; T4 1152/2/5/K2;
S4 1152/2/5/K3; U5 14400/2/5/K2; plus5 240/4/7/K2; R2x3 24/24/23/K3; EW 8/8/7/K2;
ORN 108/3/5/K2, element orders $\{1,2,3,6\}$, no 12-cycle. A WSL Sage check confirms the
EW/CyclicCover tuples against `families.py`, ORN as $H_4(2^3)^{\mathrm{even}}$ with
monodromy 108 and automorphism group 3, and EW's absolute period lattice $(2,0,2)$. Could
not check: the remote log; whether the addendum-2 §4 $|G|$ values were hand-verified; the
24-minute start-to-date gap.   [Fable 5.1, primary]
Run B: GAP (narrow) — independently names the same two defects: "eleven" → ten at lines 18
and 95–96, and the ORN `orb=5` self-pin at lines 148–150. All other earlier findings are
fixed. Reproduced unit, R2x1, L3, plus5, R2x3, EW, D4 and ORN by its own probe; Sage gives
plus5 monodromy 240, automorphism group 4, $H_5(2^4)$, and ORN matches. Minor points: line 84
"no 12-cycle" is not a JSON field; the message at line 304 is stale for ORN; the `Result:`
line reports the `8ceb09d` run, so the `cadef3e` numbers are carried only by the JSON and the
ledger.   [Fable 5.1, primary]

Decision: not cleared (both GAP, and they agree — no wording may be cited)

Next action: fix the header — ten rows, not eleven; plus5 $|G|=240$ marked as a new computed
datum rather than a reproduction; the ORN `orb` self-pin dropped or labelled as the code's
own earlier output — commit, rerun and re-settle. **The rerun is on hold**: Roey has said
nothing runs on lingo until a proper scheduler is set up there (2026-09-21).

Allowed wording: none, currently. Both auditors independently offer the wording below as
what the fix would license, and it is recorded here as **prospective, not current** — it may
not be cited until the header is fixed, the script is rerun, and that rerun is re-audited:

> No disagreement with the pinned tables of spec §6.1 and addendum-2 §4 over the fifteen
> named surfaces … $|G|$ on the ten rows with a table value … L4, P5, W5, L3x2blocks
> UNDECIDED for every group-derived field … plus-pentomino $|G| = 240$ and the Ornithorynque
> record ($K_{\min}$ 2, $|G|$ 108, $|Z|$ 3, five orbitals, $H_4(2^3)^{\mathrm{even}}$) are new
> data corroborated by independent reimplementations, not by a table. Not checked: (2T′),
> primitivity, per-row hypothesis level. Cannot refute (Q2) on the regression rows.

Open: the same items the 2026-09-20 entry below left open, unchanged by this rerun; plus
whether the remaining two header defects recur once fixed, which only a further rerun (on
hold) can settle.
