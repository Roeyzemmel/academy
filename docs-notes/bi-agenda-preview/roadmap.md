# Roadmap: author@bi

<!-- academy roadmap v1 (author plugin, references/formats.md). One work item per
`## R-NNNN [tag] title` heading, then `- key: value` fields, then free text.
Tags: write apply lead verify cite experiment figure build notation sweep referee.
Status: open ticketed blocked needs-human done dropped. `/author:next` picks from
here and from the board; `/author:notes` and `/author:agenda` file new items. -->

The Author's own work items. Items needing another role (a proof, a verification, a
citation, an experiment) become board tickets when `/author:next` reaches them; the
item then waits in `ticketed` until the ticket is delivered.

Migrated on 2026-09-28 from `Drafts/comment_roadmap.md` by agenda_migrate.py; the old file stays as the record of the settled tiers. Each item keeps its original text; `source` says where it came from.

## R-0001 [apply] Define $\Aff^{+}_{d}(X) = D^{-1}(\SO_2(\R))$, the orientation-preserving isometric
- status: open
- agenda: paper:defn:corners
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 5b item 2
- created: 2026-09-28

2. **[apply]** Define $\Aff^{+}_{d}(X) = D^{-1}(\SO_2(\R))$, the orientation-preserving isometric
affine automorphisms, at `defn:corners` and in the notation list.
**[done 2026-09-24 at `defn:corners`; notation list blocked]** — defined in a display in the
lead-in to `defn:corners`, next to $\Aff_d(X)$ and $\Trans(X) = D^{-1}(\Id)$. The notation
list is in `sections/introduction.tex`, outside the files issue 1 was allowed to touch; the
line to add after "$\Aff_d(X) = D^{-1}(O_2(\R))$ the isometric affine automorphisms" is
"$\Aff^{+}_{d}(X) = D^{-1}(\SO_2(\R))$ the orientation-preserving ones" — for the next pass.

## R-0002 [lead] (`top-researcher`, Roey's route) Prove `prop:cornered-arithmetic` with the
- status: open
- agenda: paper:prop:cornered-arithmetic
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 5b item 8
- created: 2026-09-28

8. **[lead]** (`top-researcher`, Roey's route) Prove `prop:cornered-arithmetic` with the
barycentric DS system: the covering onto the relative torus marked by $

## R-0003 [write] New lemma next to `cor:db-faith`: for $\Sigma_X \ne \emptyset$, every corner
- status: open
- agenda: paper:cor:db-faith
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 5b item 10
- created: 2026-09-28

10. **[write]** New lemma next to `cor:db-faith`: for $\Sigma_X \ne \emptyset$, every corner
is a vertex of the first barycentric subdivision of the Delaunay decomposition. The
route is as in the previous numbering; with the new definition $\varphi$ is a genuine
rotation, so the translation caveat is gone. Rests on the blue `defn:delaunay`. Blue, queued.

## R-0004 [write] Three distinct names, one per torus (Roey): the absolute torus
- status: open
- agenda: paper:defn:maximal-torus
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 5b item 14
- created: 2026-09-28

14. **[write]** Three distinct names, one per torus (Roey): the **absolute torus**
$\R^2/L(X)$ (now "the maximal torus" $T(X)$ in `defn:maximal-torus`), the **reduced
absolute torus** $\R^2/\Lambda_0(X)$ (now "the reduced torus" $T_0(X)$), and the
**relative torus** $T_\Lambda(X)$ (`defn:relative-marking`). Give each a distinct symbol,
use the names consistently across `sections/`, keep "maximal" only as a property (the
`\Sketch` after `defn:maximal-torus`), and add the three to the notation list. Resolve the
$\Lambda(T)$ clash in the proof of `thm:torus-periodic-points` (markings:439, where
$\Lambda(T)$ is the absolute lattice) against `eq:relative-lattice`; close that part of
Tier 10b item 3. Update the `\Claude` at `appendix_null_holonomy.tex:38`. Report the
symbols chosen here.

## R-0005 [write] *"We may move the entire `metric_decomps` into an
- status: needs-human
- agenda: paper:defn:delaunay
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 8 item 2
- created: 2026-09-28

2. **[needs Roey / structural]** *"We may move the entire `metric_decomps` into an
appendix."* Recorded as a proposal, not a decision. The mechanics are cheap: 351 lines,
12 labels, and only **two** are referenced from outside the file — `sec:metric` (from
`appendix_thick_part`, `flat_structures`, `schreier_graphs`) and `defn:delaunay` (from
`appendix_thick_part`, `schreier_graphs`). So the move is an `\input` reorder in
`main.tex` plus a handful of `\cref`s, not a rewrite.
**Sequencing concern, the reason not to do it first:** `defn:delaunay` is currently
*false as written* and is used from its definition through the end of `sec:schreier`.
Moving the section wholesale would carry a broken definition into an appendix and put
more distance between it and the statements that depend on it. Recommended order:
repair `defn:delaunay` (item 1), then move. Also worth deciding at the same time whether
`metric_decomps` merges with `appendix_thick_part`, which already holds the systole and
the Delaunay-based compactness proof and currently duplicates `defn:systole` against
`metric_decomps.tex:50` — the `[apply, minor]` notation item under Tier 3d open.

## R-0006 [notation] *Use `SW08`'s `Q_{g,b}` instead of `Q( ilde S, ilde\Sigma)`;
- status: needs-human
- agenda: paper:defn:covering-moduli
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 8 item 3
- created: 2026-09-28

3. **[needs Roey / notation]** *Use `SW08`'s `Q_{g,b}` instead of `Q(	ilde S, 	ilde\Sigma)`;
marked versus unmarked `s` should be visibly different spaces.* Small in the tex — nine
occurrences, `markings.tex` (7: lines 166, 168, 178, 187, 221, 295, and the `Q(\pi)`
definition) and `appendix_thick_part.tex` (2: lines 39, 111). Roey's point is served
directly: the forgetful diagram at `markings.tex:295`,
`Q(S,\Sigma \cup \{s\}) 	o Q(S,\Sigma)`, becomes `Q_{g,b+1} 	o Q_{g,b}`, where the
distinction is in the index. **Three things to settle before anyone edits:**
- **(a) The change may be a correction, not just a rename — check the fonts.** In `SW08`
  the two symbols are *different spaces*: the extraction at `SW08.txt:462-470` reads
  "We define Qg,b = Q(S, ) to be the quotient Quad(S,Sigma)/Diffeo_0(S,Sigma)", then
  "Qg,b = Q(S, )/Mod(S,Sigma)" — i.e. one font of `Q` is the **Teichmüller-level** space
  and the other the **moduli space**, and `pdftotext` has flattened the distinction. The
  draft's `Q(S,\Sigma)` is defined at `markings.tex:166` as the *moduli* space, "modulo
  `Mod(S,\Sigma)`". If the font pairing is what it appears to be, the draft's current
  symbol collides with `SW08`'s for the pre-quotient space, and Roey's switch removes the
  collision. **This is a lead, not a fact:** the cache rules are explicit that an
  extraction mangles exactly this, so the pairing must be confirmed against `SW08.pdf`
  before it is relied on — a `source-checker` job, not a `math-writer` one.
- **(b) `Q_{g,b}` is a count, and the draft needs labels.** `b` records *how many* points
  are marked, not which, and the draft's strata prescribe a cone angle at each labelled
  point of `\Sigma`, while the covering constructions follow specific points through
  `\pi`. Decide whether `Mod(S,\Sigma)` fixes `\Sigma` pointwise (labelled) or permutes it
  (unlabelled); if labelled, `Q_{g,b}` names the space but cannot carry the labelling,
  and some statements will still need `(S,\Sigma)` in scope. `Q(\pi)` has no numerical
  name at all and is unaffected either way.
- **(c) Adopting the name asserts an equality the draft does not have.** `SW08` says
  explicitly (`SW08.txt:457-459`, extraction) that it assumes no relation between the
  marked points and the differential, and that the marked points "need not contain the
  collection of zeros and poles". The draft's space *requires* `\Sigma \supseteq` zeros
  (`markings.tex:166`). So the draft's space is a **sublocus** of `SW08`'s `Q_{g,b}`, not
  the same space, and taking the name unqualified would silently claim otherwise. This is
  the same judgement call already recorded twice — the "`SW08`-sublocus reading" listed
  against `defn:covering-moduli` in `Drafts/verdicts.md`, and the Tier 3d open item on
  the fourth departure of `defn:covering-moduli` from `SW08`. Settle it once, here or
  there, rather than a third time.

## R-0007 [lead] `prop:polygon-sym`, `K_4`, connectivity of `M_P` — unblocked 2026-09-22
- status: open
- agenda: paper:prop:polygon-sym
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 9 item 6
- created: 2026-09-28

6. **`prop:polygon-sym`, `K_4`, connectivity of `M_P`** **[lead]** — unblocked 2026-09-22
(issue 8's falsifier is `done`; see there, especially the marked-points finding).
Read `R ∈ Δ_P` as `R ∈ K_P`; Roey's "Unless $\Delta = K_4$, in which case it is a
'directional' double cover"; replace "Just work with the unfolding" by the proof; prove
the connectivity `\Sketch` in `sec:billiard-tables`.

## R-0008 [lead] Orthogonal polygons — note at `\subsubsection{Orthogonal polygons}`
- status: open
- agenda: global
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 9 item 7
- created: 2026-09-28

7. **Orthogonal polygons** **[lead]** — note at `\subsubsection{Orthogonal polygons}`:
"these are useful facts that should be proved. Sketch: $a_t$ commutes with the Klein
group $K_4$; if the billiard table was simply connected its pillowcase must be a half
translation surface homeomorphic to a sphere, forcing that the induced
$-\Id$-involution will be hyperelliptic." Falsifier by `experimenter` first.

## R-0009 [lead] Rhombus example — ledger `ex:rhombus-same-unfolding-c`: "now let's check
- status: open
- agenda: paper:defn:relative-marking
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 9 item 8
- created: 2026-09-28

8. **Rhombus example** **[lead]** — ledger `ex:rhombus-same-unfolding-c`: "now let's check
whether they are the same surface or just two distinct double covers of the double
pentagon." `experimenter`: unfold the kite `(π/5, π/2, 4π/5, π/2)`, the rhombus
`(π/5, 4π/5)` and — Roey, 2026-09-22 — the isosceles triangle `(π/10, π/10, 4π/5)`;
test pairwise translation isomorphism and whether each covers the double pentagon.
Queued for lingo.
Status 2026-09-22: **queued** — Roey committed the script in `../FlatSurfLab`
(commit `1cb3692`: `experiments/2026-09-22_rhombus_kite_isosceles_double_pentagon.py`,
`fslab/billiard_unfold.py`, `tests/test_billiard_unfold_sage.py`), then
`scripts\queue.ps1 -Add` job `20260922-160438_2026-09-22_rhombus_kite_isosceles_double_pentagon`,
submitted to lingo (reachable) and accepted into the remote spool, FIFO behind one running
job. (A second, redundant `-Add` of the same script/label — `20260922-170206_...` —
was also submitted; both sit `[ex:rhombus-same-unfolding]` in `queue\running\`, and the
duplicate should be cancelled or its result discarded once collected.) Row written in
`Drafts/experiments.md`. Issue 6 remains **blocked** on the outcome.
Status update 2026-09-22: both jobs **failed** on lingo (exit 139, segfault, no result;
the duplicate is moot). Cause, from the lingo log: `fslab.billiard_unfold.translation_isomorphic()`
compares `S.canonicalize()`, which starts pyflatsurf's cppyy/cling backend and crashes in
`rootcling` exactly as the bare `import pyflatsurf` did at `defn:relative-marking`
(2026-09-19). So `canonicalize()` is not safe with pyflatsurf broken, contrary to the
skill's `api-recipes.md` §12.4 (now corrected). **Toolchain fixed 2026-09-22**: the real
cause was that `scripts/run.sh` activated the env by `PATH` only, skipping the
compiler `activate.d` scripts that cling needs. `run.sh` now does a full `conda activate`,
and `pyflatsurf`, `canonicalize()` and `GL2ROrbitClosure` were verified on lingo. To rerun:
Roey commits `scripts/run.sh` in FlatSurfLab, then requeues the rhombus script once (not
twice). Issue 6 stays **blocked** until that run is `done`.
**Requeued 2026-09-22** as job `20260922-194443_2026-09-22_rhombus_kite_isosceles_double_pentagon`,
pinned to commit `c571b7d` (which contains the `run.sh` fix); submitted to lingo. Don't
requeue until this job is fetched.
**Done 2026-09-22** (`results/2026-09-22_rhombus_kite_isosceles_double_pentagon.json`,
validation passed; row in `Drafts/experiments.md`). Without marked points, the kite, the
rhombus and the isosceles triangle unfold to **one and the same** surface, in `H_4(3,3)`:
the three pairs are translation-isomorphic. With the canonical `Σ_M` the kite's unfolding
has 12 marked points and the other two have 2 each; kite vs rhombus and kite vs isosceles
are not isomorphic, rhombus vs isosceles are. So the answer to
`ex:rhombus-same-unfolding-c` is "the same surface", not "two distinct covers".
**It covers no double pentagon, at any scale.** That reason is the main session's argument
and was not computed by the run: the double pentagon's only zero has angle 6π, every
point over it in a translation cover has angle a multiple of 6π, and `H_4(3,3)` has only
8π points. The run's own test (non-integer area ratio against
`veech_double_n_gon(5)` at one fixed size) does not by itself rule out a rescaled double
pentagon. Anything that goes into the paper from this goes through a writer and
`/paper:verify` as usual.
The double-pentagon test is a necessary-condition sieve only (area ratio, Riemann–Hurwitz).

## R-0010 [apply] Leftover machine notes — fold into the outcomes of 1, 3, 5;
- status: open
- agenda: global
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 9 item 9
- created: 2026-09-28

9. **Leftover machine notes** **[apply]** — fold into the outcomes of 1, 3, 5;
`/paper:sweep` at the close.

## R-0011 [lead] A definition of "billiard table" by ported boundaries and plugs
- status: open
- agenda: global
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 9c item 2
- created: 2026-09-28

2. **A definition of "billiard table" by ported boundaries and plugs** **[lead]**
(`top-researcher`) — flat_structures:979, on the "no orbifold point in its interior"
paragraph of `sec:billiard-tables` and its trailing `\Claude` note (which already
flags ported boundaries as unchecked against the gluing model): *"ported boundaries
are allowed for flat dihedral structures but not for billiard tables, and this could
be the definition for billiard tables - quotients without ported boundaries and no
interior plugs. A consequence of this definition is that there are no interior
points with non-trivial stabilizers."* Two parts: (a) state this as the actual
definition of a billiard table (a flat dihedral structure, quotient without ported
boundaries and without interior plugs), in place of or alongside whatever
`sec:billiard-tables` currently uses to characterise them; (b) prove the claimed
consequence — no interior point of the unfolding has a non-trivial rotation-only
stabiliser — from that definition, which would settle the very question left open by
Tier 9b's "Open from issue 2" (3) (ported boundaries fall outside the gluing model,
nobody has checked whether a ported table can have such a point). Falsifier first:
`experimenter` should test whether a ported table can be built with a rotation-only
interior stabiliser before the consequence is written up. Needs Roey to confirm this
is meant as the formal definition (replacing or supplementing the current
characterisation) rather than an equivalent description — flag with `\Claude` if the
distinction matters to how it's phrased.

## R-0012 [write] Extract the affine-in-charts case of the lifting lemma (`math-writer`)
- status: open
- agenda: paper:lem:lift-to-unfoldings
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 9c item 3
- created: 2026-09-28

3. **Extract the affine-in-charts case of the lifting lemma** **[write]** (`math-writer`)
— flat_structures:374, at the end of the second paragraph of `lem:lift-to-unfoldings`
(the generalisation from flat morphisms to maps affine in charts, added by Tier 9b
issue 3 to serve `lem:flat-equivalence-props`): *"Way too long. The proof for affine
in charts map should be extracted to a different lemma, possibly right after the
definition, as it is easier and involves less moving parts though I believe the
proofs would be similar."* Split the lemma: keep `lem:lift-to-unfoldings` as the flat
morphism statement close to Vorobets' Prop. 5.1 (Tier 9b issue 3's shape), and move
the affine-in-charts generalisation (statement and the corresponding part of the
proof) into a new lemma placed right after `defn:flat-equivalence` (per Roey's
"possibly right after the definition"), which `lem:flat-equivalence-props` then cites
instead. Re-read every place that currently cites the second paragraph of
`lem:lift-to-unfoldings` (`lem:flat-equivalence-props`'s proof, per Tier 9b issue 3's
own "blast radius" note) and repoint it. Roey's expectation that "the proofs would be
similar" is a hint, not a guarantee — if the split proof needs new argument beyond
reusing the existing steps, flag it and keep both statements blue rather than
silently inventing one. Delete Roey's note.

## R-0013 [lead] Write the proof of `prop:vorobets-lift`, following Vorobets
- status: open
- agenda: paper:prop:vorobets-lift
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 9c item 4
- created: 2026-09-28

4. **Write the proof of `prop:vorobets-lift`, following Vorobets** **[lead]**
(`top-researcher`) — flat_structures:1085, on the `\Claude` note after
`prop:vorobets-lift` (which flags the periodic-point decoration $(M_Q, P(M_Q))$ as
unsourced against Vo96a Prop. 5.1): *"Correct, but the billiard tables in Vorobets'
statements are complete analogues to the quotients $M \big/ \Delta$, and so the proof
in our settings should be able to follow the lines of the original proof."* Reading:
Roey confirms the decoration gap is real (the `\Claude` note stands) but says it is
not a blocker — `prop:vorobets-lift` currently has no proof at all, only the
citation, and one should be written by adapting Vorobets' own argument to the
decorated statement, since his billiard tables are exactly the quotients $M/\Delta$
this draft uses. Write the proof (as a `\Sketch` first), tracking where the
periodic-point decoration needs its own justification beyond what Vo96a's proof
supplies — that's the part the `\Claude` note already isolates. `source-checker`
already quoted Prop. 5.1 and its proof into `Drafts/sources.md` (Tier 9b issue 3); no
new citation pass is needed unless the write-up finds it must lean on a different
part of Vo96a. Once written, note whether `\Cref{lem:lift-to-unfoldings} is the
general form of this result` (the paragraph right after the proposition) still reads
correctly or needs updating to point at the proof instead of standing in for it.

## R-0014 [apply] Delete a stale note: already executed by Tier 9 issue 1
- status: open
- agenda: paper:prop:unfolding-lift-general
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 9c item 5
- created: 2026-09-28

5. **Delete a stale note: already executed by Tier 9 issue 1** **[apply]**
(`math-editor`) — flat_structures:1095, on `prop:unfolding-lift-general`: *"This is
actually a consequence of `\cref{lem:lift-to-unfoldings}`, as the unfolding of a
translation surface is itself."* Already covered: Tier 9 issue 1 proved exactly this
("`prop:unfolding-lift-general` proved as the case `X = M`"), and the tex confirms
it — the proposition already has a one-paragraph proof reading "A translation
surface is the flat structure presented by $(M, \{\Id\})$ ... `\cref{lem:lift-to-unfoldings}`
applied to $\pi$ gives a translation covering..." right below it, with its own
`\Claude` note recording the 2026-09-22 (Tier 9 issue 1) authorship. Roey's note
predates that fix and was never cleared; delete it, nothing else to do. (Also
fine for `/paper:sweep` to pick up, but small enough to apply directly.)

## R-0015 [write] Slope section: override by the slope-1 research (`math-writer`),
- status: open
- agenda: paper:defn:cylinder-monodromy
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 10 item 7
- created: 2026-09-28

7. **Slope section: override by the slope-1 research** **[write]** (`math-writer`),
then **[verify]** — slope_blocking:128. "The chat" is the research database in the
sibling repo `C:\Work\Math\Slope1illuminationResearch` (read its `CLAUDE.md`,
`STATUS.md` and `INDEX.md`).
- The relevant parts are the dictionary (R Prop. 4.1–4.3: trajectories ↔ Christoffel
  rotations, conjugation = free homotopy), base-point independence (R2 Thm 2.2,
  proved modulo EMM and Smillie–Weiss; torsion base points differ, R2 §2.1), and the
  orbital criterion (R2 §4, `notes/03-q2/orbitals.md`).
- Rewrite `defn:cylinder-monodromy`, `fact:S-normal-symmetric` and
  `prop:blocking-monodromy` from it, keeping the database's own statuses. Everything
  from slope_blocking:124 onward stays sketch/conjecture until `/paper:verify` has
  run, as Roey asks.
- Cite nothing from that repo as published.

## R-0016 [write] The Eisenstein figure (`figure-maker`) — background:50
- status: open
- agenda: paper:lem:tok
- priority: normal
- depends_on: []
- route: figure-maker
- source: comment_roadmap.md, Tier 10 item 8
- created: 2026-09-28

8. **The Eisenstein figure** (`figure-maker`) — background:50.
- Roey accepted the suggestion ("OK"). Choose between `figures/eisenstein_non-illumination.pdf`
  and `tikz/eisenstein_self_illumination.tex`, preferring the TikZ source, and write a
  real caption.
- Place it next to `lem:tok`, and flag the choice for Roey's review.

## R-0017 [write] appendix_thick_part:327 `defn:delaunay` references (`source-checker`)
- status: open
- agenda: paper:defn:delaunay
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 10b item 1
- created: 2026-09-28

1. appendix_thick_part:327 `defn:delaunay` references **[write]** (`source-checker`) —
*"Good! add references for this definition."* Closes the "not yet filed anywhere" flag
left in Tier 3d's "Open from this tier" paragraph (below) and its "Swept 2026-09-23"
note. `defn:delaunay` already cites `\cite[\S4]{MS91}` throughout; find out what
further reference Roey wants (a name for the decomposition, e.g. the original Delaunay
paper, or a second exposition alongside `ORSZ`) and add it through `/paper:cite`.

## R-0018 [write] flat_structures:364 `lem:similarity-forced-by-rotation` case 3, too long
- status: open
- agenda: paper:lem:similarity-forced-by-rotation
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 10b item 2
- created: 2026-09-28

2. flat_structures:364 `lem:similarity-forced-by-rotation` case 3, too long **[write]**
(`math-writer`) — *"Too long. The last case should read that without loss of
generality $K_X = K_4$, and then its normalisers are $O \cdot D$ with $O \in O_2$ and
$D$ diagonal, or $g = r_{\theta} a_t$."* Roey's reply to Tier 10 issue 4's three-case
restatement (2026-09-23): compress case 3 using the normal form he gives — reduce to
$K_X = K_4$ up to conjugation (already how the proof starts) and state the admissible
$g$ directly as $O \cdot D$ ($O \in O_2(\R)$, $D$ diagonal) or $g = r_\theta a_t$,
rather than the current $g' = hc$ derivation. Queued for `/paper:verify` once written
(the lemma is already in the verification queue below; this changes its proof, so the
queue line needs updating when done).

## R-0019 [write] markings:432 `thm:torus-periodic-points`, "free" moved and proof shortened
- status: open
- agenda: paper:thm:torus-periodic-points
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 10b item 3
- created: 2026-09-28

3. markings:432 `thm:torus-periodic-points`, "free" moved and proof shortened **[write]**
(`math-writer`) — *"the definition of 'free' set should be moved to before the
theorem, and $F$ should be assumed free throughout. Also, the proof is too long and
invents many signs, shorten it and make it more readable."* Roey's reply to Tier 10
issue 5's restatement. Two parts: (a) mechanical — move the `free` definition
(currently inside the theorem statement) to a `defn` or a sentence before
`thm:torus-periodic-points`; (b) a judgement call — "assume $F$ free throughout" would
drop item 1 of the theorem, which Tier 10 issue 5 deliberately proved **without**
freeness (it matches `rmk:nonempty-marking` at $n = 1$); flag this in a `\Claude` note
rather than silently narrowing the theorem, and shorten items 2–3 and the proof instead.
**Blast radius, Tier 5b issue 2 (2026-09-24):** the proof's "Invariant loci" paragraph
(markings.tex:439) locally defines $\Lambda(T) = \hol(H_1(T;\Z))$ for a marked torus —
its *absolute* period lattice — which now collides with the settled meaning of
$\Lambda(T)$ fixed by `eq:relative-lattice` (the *relative*-period lattice, used
throughout `defn:relative-marking` and the rewritten `lem:torus-corners-torsion`).
Rename the local one (e.g. $\Lambda_F(T)$) when this item is executed.

## R-0020 [lead] markings:497, add $J(F)$ to the periodic points (`top-researcher`)
- status: open
- agenda: paper:cor:periodic-prim-relations
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 10b item 4
- created: 2026-09-28

4. markings:497, add $J(F)$ to the periodic points **[lead]** (`top-researcher`) —
replying to the `\Claude` note on `cor:periodic-prim-relations` (Tier 10 issue 2, D6)
that flags the corollary's last sentence as false in genus 2 (`J(p) \in P(X,p)`,
`J(p) \notin P(X) \cup \{p\}$ for `X` primitive in $\ccH(2)$): *"Instead we should add
$J(F)$ to the periodic points."* Reading, to be checked rather than assumed: restate
the corollary's last clause as $P(X, F) = P(X) \cup F \cup J(F)$ for $X$ primitive,
where $J$ is the hyperelliptic involution of the AW21 Theorem 1.4 paragraph just below
(quadratic-differential case) — the translation-surface analogue needs its own $J$,
which is not yet defined for `cor:periodic-prim-relations`'s translation-surface
setting; check whether one exists, or whether Roey means something narrower. Queue for
`/paper:verify` once written.
**Roey (chat, 2026-09-25):** *"as I commented there it should include all of the
involution images of the marked points."* So the clause is to read
$P(X, F) = P(X) \cup F \cup \bigcup_J J(F)$, the union over the involutions $J$ of $X$.
Still a reading, to be checked rather than assumed: which involutions? The genus-2
counterexample needs $J$ with $DJ = -\Id$ (the hyperelliptic involution), and the
natural class is the affine automorphisms with $DJ = -\Id$. Two of them differ by a
translation automorphism, so if the paper's "primitive" forces $\Trans(X) = \{\Id\}$
there is at most one (unchecked against the paper's definition). The corollary is uncoloured (black) while its last sentence is false, which
is `check`'s one error in the paper registry. The restated corollary goes **blue** until
`/paper:verify` passes it.

## R-0021 [lead] slope_blocking:93, define $\sim$/$\approx$ from the strong AW21 result
- status: open
- agenda: paper:rmk:saturation-vs-symmetry
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Tier 10b item 5
- created: 2026-09-28

5. slope_blocking:93, define $\sim$/$\approx$ from the strong AW21 result **[lead]**
(`top-researcher`) — replying to the `\Claude` note after `rmk:saturation-vs-symmetry`
("Unverified: that the generic surface of such a locus has $\Trans(X) = \{\Id\}$ … and
this reading of AW21's proof. Their Sublemma 2.12 and Example 2.6 (v3) are not yet in
`Drafts/sources.md`."): *"OK let's define the relation as the strong result we get
from \cite{AW21}."* Reading: rather than defining $\sim$/$\approx$ ad hoc and then
arguing they agree with AW21's covering-lemma proof, state the definition directly off
AW21's Sublemma 2.12 (and Example 2.6, needed for the domain-defect counterexample),
with a pinpoint through `source-checker` first. Coordinate with the pending
`/paper:verify` on `defn:saturated-marking` (Tier 4a issue 1, which already asks the
verifier to check `rmk:saturation-vs-symmetry` against the same AW21 paragraphs) —
write this up but hold it for that verification, or fold the two together.

## R-0022 [apply] `rmk:nonempty-marking` (`markings.tex:90`): the garbled "is always assume that"
- status: open
- agenda: paper:rmk:nonempty-marking
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[apply]** `rmk:nonempty-marking` (`markings.tex:90`): the garbled "is always assume that"
and the typo `p \in X\bbT^2` (archive:2651, flagged three times).

## R-0023 [apply] The `\Claude` note in the proof of `lem:thick-part-compact`
- status: open
- agenda: paper:lem:thick-part-compact
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[apply]** The `\Claude` note in the proof of `lem:thick-part-compact`
(`appendix_thick_part.tex:537–542`, "…neither proved here nor cited") is stale twice over:
MS91 Prop. 4.1, Lemma 4.2, Thm 4.4 are cited after `defn:delaunay` (`:331`), and `ORSZ` is
cited. Repoint it or delete it (archive:2602).

## R-0024 [write] Split `lem:illumination-chase` (`arithmetic.tex:314`, `\Roey{Separate to different
- status: open
- agenda: paper:lem:illumination-chase
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[write]** Split `lem:illumination-chase` (`arithmetic.tex:314`, `\Roey{Separate to different
lemmas?}`); the proof stays a sketch. With it, clear its R1 (sketched proof under an
uncoloured statement) by colouring the statement, unless Roey says otherwise
(archive:3157, 2726).

## R-0025 [write] `ex:rhombus-same-unfolding`: write in the result of Tier 9 issue 8
- status: open
- agenda: paper:ex:rhombus-same-unfolding
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[write]** `ex:rhombus-same-unfolding`: write in the result of Tier 9 issue 8
(`results/2026-09-22_rhombus_kite_isosceles_double_pentagon.json`: kite, rhombus and
isosceles give one surface without marked points; with the canonical `Σ_M` the kite
differs), qualify "same translation surface" for marked points, delete notes a–c, mark
Tier 9 issue 8 [done] (archive:1567, 1763). Note a (the brown→blue recolour, "Revert if
you disagree") is answered: Roey, 2026-09-25, "sure", so the example stays blue.

## R-0026 [apply] The lead-in to `defn:delaunay` (`appendix_thick_part.tex:298–299`) repeats
- status: open
- agenda: paper:defn:delaunay
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[apply]** The lead-in to `defn:delaunay` (`appendix_thick_part.tex:298–299`) repeats
"with cone singularities" on two consecutive lines; delete one (found 2026-09-25).

## R-0027 [cite] Source pinpoints still second-hand: AAH22 §2.1 / Prop 2.4 / Table 1 for
- status: open
- agenda: paper:ex:platonic-boundary
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[verify]** Source pinpoints still second-hand: AAH22 §2.1 / Prop 2.4 / Table 1 for
`ex:platonic-boundary` (archive:1814(b)); AW21 published vs arXiv numbering at
`defn:saturated-marking` and `slope_blocking.tex:166` (archive:1834(d), 1852(b));
`rmk:flat-structure-orbifold` cites Th80 Ch. 13 at chapter level only (archive:1814(d)).
For `source-checker`.

## R-0028 [verify] EMM15 with marked points, flagged "Unverified input" at `markings.tex:270`
- status: open
- agenda: global
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[verify]** EMM15 with marked points, flagged "Unverified input" at `markings.tex:270`
(archive:1834(c)).

## R-0029 [cite] The golden locus written blue under Tier 10 D9: `KM16` is in the bib, pending
- status: open
- agenda: global
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[verify]** The golden locus written blue under Tier 10 D9: `KM16` is in the bib, pending
`/paper:cite`, and the argument is unverified (archive:1834(b)).

## R-0030 [write] The cleaner lift-to-the-unfolding route, noted but not written
- status: open
- agenda: global
- priority: low
- depends_on: []
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

- **[write, optional]** The cleaner lift-to-the-unfolding route, noted but not written
(`appendix_thick_part.tex:40–46`; archive:1852(a)).

## R-0031 [verify] Verify fact:forgetful-props
- status: open
- agenda: paper:fact:forgetful-props
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: fact:forgetful-props
- created: 2026-09-28

- `fact:forgetful-props` — `sections/markings.tex` — repaired proof (issue A1), a primary pair asked for by the roadmap's own [verify] — queued by Tier 3d, issue 1

## R-0032 [verify] Verify lem:flat-equivalence-props
- status: open
- agenda: paper:lem:flat-equivalence-props
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:flat-equivalence-props
- created: 2026-09-28

- `lem:flat-equivalence-props` — `sections/flat_structures.tex` — proof replaced 2026-09-22 (Tier 9, issue 1) by an application of `lem:lift-to-unfoldings`; verify after that lemma; 2026-09-22 (Tier 9b, issue 3) the references were updated to the rewritten lemma's paragraphs and clauses (not a fresh argument); 2026-09-23 item 1's converse reads `φ(Σ_X) = Σ_Y` off `defn:flat-morphism` (D1) instead of deriving it — queued by Tier 3d, issue 2, updated by Tier 9, issue 1, updated by Tier 9b, issue 3, updated by Tier 10, issue 1

## R-0033 [verify] Verify lem:marking-full-preimage
- status: open
- agenda: paper:lem:marking-full-preimage
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:marking-full-preimage
- created: 2026-09-28

- `lem:marking-full-preimage` — `sections/markings.tex` — new sketch, Roey's `lem:periodic-coimage-reply` lead, immersion route — queued by Tier 3d, issue D

## R-0034 [verify] Verify lem:periodic-coimage
- status: open
- agenda: paper:lem:periodic-coimage
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:periodic-coimage
- created: 2026-09-28

- `lem:periodic-coimage` — `sections/markings.tex` — replacement proof (round 3 item 3) via `lem:marking-full-preimage` — queued by Tier 3d, issue D

## R-0035 [verify] Verify lem:relative-marking-invariance
- status: open
- agenda: paper:lem:relative-marking-invariance
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:relative-marking-invariance
- created: 2026-09-28

- `lem:relative-marking-invariance` — `sections/markings.tex` — restated per item 13 (`g(Y) > 1`, `π(Σ_X) = Σ_Y`), new proof on the extra-path lead; 2026-09-23 the hypothesis `π(Σ_X) = Σ_Y` deleted as part of `defn:flat-morphism` (D1), the proof now cites the definition for it, argument unchanged; check also the `v = a + b` decomposition step, the writer's own addition (archive:2409) — queued by Tier 3d, issue D, updated by Tier 10, issue 1

## R-0036 [verify] Verify lem:thick-part-compact
- status: open
- agenda: paper:lem:thick-part-compact
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:thick-part-compact
- created: 2026-09-28

- `lem:thick-part-compact` — `sections/appendix_thick_part.tex` — circumradius (pigeonhole) and closedness (via `lem:saddle-homotopy`) paragraphs rewritten, MT02 Lemma 1.6 transfer; stays modulo the Delaunay and topology inputs — queued by Tier 3d, issue E

## R-0037 [verify] Verify lem:lift-to-unfoldings
- status: open
- agenda: paper:lem:lift-to-unfoldings
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:lift-to-unfoldings
- created: 2026-09-28

- `lem:lift-to-unfoldings` — `sections/flat_structures.tex` — rewritten 2026-09-22 (Tier 9b, issue 3) on Roey's route: statement shaped on `\cite[Prop.\ 5.1]{Vo96a}` (a model, not an input), proof by continuation on the universal cover of `M_X^\circ`. One cited-at-section-level input, confirmed by `source-checker` (Hatcher Thm. 1.38 + p. 57 remark give the fact together, no single numbered statement does): a covering space of a simply-connected, locally path-connected space is trivial (`\cite[\S 1.3]{Ha02}`). One still uncited, visibly flagged: a proper local homeomorphism onto a connected manifold is a finite covering. Unresolved and flagged by the writer: the degree-formula display is now stated off the mirror points of `Y` only (a strengthening over the previous dense-open-set claim) — queued by Tier 9, issue 1, rewritten by Tier 9b, issue 3

## R-0038 [verify] Verify lem:structure-group-hierarchy
- status: open
- agenda: paper:lem:structure-group-hierarchy
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:structure-group-hierarchy
- created: 2026-09-28

- `lem:structure-group-hierarchy` — `sections/flat_structures.tex` — replacement proof (2026-09-22) as the first assertion of `lem:lift-to-unfoldings`; the Th80 dependency is gone; 2026-09-22 (Tier 9b, issue 3) the citation follows the rewritten lemma's main paragraph directly, no item number — queued by Tier 9, issue 1, updated by Tier 9b, issue 3

## R-0039 [verify] Verify prop:unfolding-lift-general
- status: open
- agenda: paper:prop:unfolding-lift-general
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:unfolding-lift-general
- created: 2026-09-28

- `prop:unfolding-lift-general` — `sections/flat_structures.tex` — proof written 2026-09-22 as the case `X = M` of `lem:lift-to-unfoldings`; 2026-09-22 (Tier 9b, issue 3) the reference follows the rewrite, content unchanged — queued by Tier 9, issue 1, updated by Tier 9b, issue 3

## R-0040 [verify] Verify rmk:polygon-determined
- status: open
- agenda: paper:rmk:polygon-determined
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: rmk:polygon-determined
- created: 2026-09-28

- `rmk:polygon-determined` — `sections/flat_structures.tex` — generalised to flat equivalence; new side-point argument (affine lift at a mirror point forces `h lin(τ_s) h^{-1} = lin(τ')`), unchecked reading: the folding charts at a side point; a `rmk`, queued because it was black before and is now blue — queued by Tier 9, issue 3; generalised again 2026-09-22 (Tier 9, issue 5) to immersed tables, conclusion `dev_Q ∘ φ = A ∘ dev_P`: verify with the immersed hypothesis (local isometry off `Σ_P`, path-metric completion, `dev_P` open not injective) and note the falsifier is only queued and the ZK75/MT02/McM23 immersed coverage unverified — updated by Tier 9, issue 5

## R-0041 [verify] Verify lem:similarity-forced-by-rotation
- status: open
- agenda: paper:lem:similarity-forced-by-rotation
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:similarity-forced-by-rotation
- created: 2026-09-28

- `lem:similarity-forced-by-rotation` — `sections/flat_structures.tex` — new lemma with proof (2×2 linear algebra, no cited inputs); round-3 lead of `lem:flat-equivalence-props`, falsifier `20260921-175900_2026-09-21_similarity_forced_by_rotation`; 2026-09-23 restated in three cases (rotation / central `K_X ≤ {±Id}` / reflection), case 3 now characterises the admissible `g` (`g(ℓ) ⊥ g(ℓ^⊥)`, `g = hc`, `K_Y = hK_Xh^{-1}`, normaliser clause) — a new argument, verify the whole proof afresh; the falsifier predates the split and did not test case 3's characterisation — queued by Tier 3d, issue 2, updated by Tier 10, issue 4

## R-0042 [verify] Verify defn:delaunay
- status: open
- agenda: paper:defn:delaunay
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: defn:delaunay
- created: 2026-09-28

- `defn:delaunay` — `sections/appendix_thick_part.tex` (moved from `metric_decomps.tex` by D8) — restated on MS91 §4 (length-minimising paths, `ι_c`, `H_c`), scope cut to no boundary and `Σ_X ≠ ∅`; a definition, queued because its recolouring clears `ex:ppsg`'s R1; check the restatement and the cited paragraph after it against `Drafts/sources.md` `## MS91` (the Lemma 4.2 interior reading is flagged). Do **not** read a positive verdict as clearing `prop:delaunay-invariance`, false as stated (2026-09-23: restated with the full-preimage hypothesis, blue, and queued on its own by Tier 10, issue 3) — queued by Tier 3d, issue C

## R-0043 [verify] Verify defn:saturated-marking
- status: open
- agenda: paper:defn:saturated-marking
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: defn:saturated-marking
- created: 2026-09-28

- `defn:saturated-marking` — `sections/slope_blocking.tex` — saturation redefined as "the marked sets over a generic $X$ partition $X \setminus P(X)$" (blue span), a defn Roey tagged [verify]; check it against AW21's proof of Lemma 2.10 and Sublemma 2.12 (`AW21.src/main.tex:543-603`) and check the companion blue `rmk:saturation-vs-symmetry` (domain defect; the degree-3 $\mathfrak S_3$ counterexample to "symmetry implies saturation", with its unverified reducedness input) — queued by Tier 4a, issue 1

## R-0044 [verify] Verify fact:flat-morphism-compose
- status: open
- agenda: paper:fact:flat-morphism-compose
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: fact:flat-morphism-compose
- created: 2026-09-28

- `fact:flat-morphism-compose` — `sections/flat_structures.tex` — D12, queued at Roey's request after D1: the composition proof now uses `ψ(φ(Σ_X)) = ψ(Σ_Y) = Σ_Z` and `ψ(Σ_Y) = Σ_Z` (D1) where it used `⊆`; rests on the blue `lem:structure-group-hierarchy` (`K_Y ≤ K_Z`); unchecked detail from its `\Claude` note: at a mirror point `y` the transition between two chart discs is taken to be an element of `R² ⋊ K_Y`, which `fact:flat-structure-charts` proves only componentwise — queued by Tier 10, issue 1

## R-0045 [verify] Verify rmk:flat-morphism-flow
- status: open
- agenda: paper:rmk:flat-morphism-flow
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: rmk:flat-morphism-flow
- created: 2026-09-28

- `rmk:flat-morphism-flow` — `sections/flat_structures.tex` — D12, a `rmk` queued at Roey's request after D1 (its "first condition of `defn:flat-morphism`" now includes `φ(Σ_X) = Σ_Y`; the argument is unchanged): forward direction via the translation covering of `lem:lift-to-unfoldings` (verify after it), converse by developing geodesics on a ball; flagged unverified: the converse's extension to mirror points by continuity — queued by Tier 10, issue 1

## R-0046 [verify] Verify prop:delaunay-invariance
- status: open
- agenda: paper:prop:delaunay-invariance
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:delaunay-invariance
- created: 2026-09-28

- `prop:delaunay-invariance` — `sections/appendix_thick_part.tex` (moved from `metric_decomps.tex` by D8) — restated with `Σ_Y ≠ ∅` and `φ^{-1}(Σ_Y) = Σ_X` (Roey: "Add it freely here"), new three-step proof counting length-minimising paths on `defn:delaunay`'s `ι_p, S_p, H_p`; rests on the blue `defn:delaunay` (verify after it) and on D1 of `defn:flat-morphism`; flagged uncited: existence of a length-minimising path from `p` to `Σ_X`, and the Euclidean cone neighbourhood used in Step 3's circle-covering argument (`x ∈ Σ_X`); check also Step 1's "agree on the disc" (two local translations agreeing at `0`) — queued by Tier 10, issue 3

## R-0047 [verify] Verify thm:torus-periodic-points
- status: open
- agenda: paper:thm:torus-periodic-points
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: thm:torus-periodic-points
- created: 2026-09-28

- `thm:torus-periodic-points` — `sections/markings.tex` — restated blue on Roey's lead (Tier 10, issue 5): rank-one relation group `L_p`, union over all `v` with `Σv > 0` grouped by the generator `v(p)`, `Q`-description with `dim_Q V_F = n+1`, arithmetic freeness hypothesis and its equivalence with the dimension form, the dashed arrow well defined; proof replaced. Inputs: `fact:forgetful-props` item 4 (blue, queued), `\cite[Theorem~2.1]{EMM15}` with marked points via `\cite[\S 2.2]{LMW16}`, and `Wr14` (unquoted in `sources.md`, marked points unchecked — an unverified input). Check in particular the step `ε ∉ W` from the 0-dimensional fibre, and the closedness of `N_v` — queued by Tier 10, issue 5

## R-0048 [verify] Verify lem:null-holonomy-tori
- status: open
- agenda: paper:lem:null-holonomy-tori
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:null-holonomy-tori
- created: 2026-09-28

- `lem:null-holonomy-tori` — `sections/appendix_null_holonomy.tex` — new, blue (Tier 10, issue 6), Roey's "respects the covering to `T(X)` and `T_0(X)`": `Z(X) = τ_X^{-1}(Σ_{T(X)}) = (τ^0_X)^{-1}(Σ_{T_0(X)})`, finiteness, `Z(X) = Σ_X` iff compatible with `τ_X`, `L(X) ⊆ Λ_0(X) ⊆ Λ(X)`, `Z(X) ⊆ R(X)`; rests on the blue `defn:maximal-torus` (check its lattice/finiteness claims with it); no cited inputs — queued by Tier 10, issue 6

## R-0049 [verify] Verify prop:reduced-torus-covering
- status: open
- agenda: paper:prop:reduced-torus-covering
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:reduced-torus-covering
- created: 2026-09-28

- `prop:reduced-torus-covering` — `sections/appendix_null_holonomy.tex` — the chat's (i) and (ii): `Λ_0(X) ⊆ Λ_0(Y)`, `q_0` a covering carrying marked set onto marked set, and `q_0` iso iff `Σ_{T(X)} = q^{-1}(Σ_{T(Y)})` iff `L(Y) ⊆ Λ_0(X)`; key step `eq:developed-marked-sets` (`Σ̃_Y = Σ̃_X + L(Y)`); reading "`T_0(X) = T_0(Y)`" = "`q_0` iso" flagged — queued by Tier 10, issue 6

## R-0050 [verify] Verify prop:reduced-torus-compatible
- status: open
- agenda: paper:prop:reduced-torus-compatible
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:reduced-torus-compatible
- created: 2026-09-28

- `prop:reduced-torus-compatible` — `sections/appendix_null_holonomy.tex` — the chat's (iii): `π^{-1}(Σ_Y) = Σ_X` ⇒ `Σ̃_X = Σ̃_Y` by path lifting; input: the first paragraph of the proof of `prop:relative-marking-compatible` (finite branched covering, lifting from any preimage), read as not using `g(Y) > 1` — check that reading — queued by Tier 10, issue 6

## R-0051 [verify] Verify prop:reduced-torus-balanced
- status: open
- agenda: paper:prop:reduced-torus-balanced
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:reduced-torus-balanced
- created: 2026-09-28

- `prop:reduced-torus-balanced` — `sections/appendix_null_holonomy.tex` — the chat's (v), with `Z(X) = Σ_X` as the hypothesis: (a) `T_0(X) = T_0(Y)` ⇔ (b) ⇔ (c) `X` compatible with `π`, and then `Z(Y) = Σ_Y`; verify after `lem:null-holonomy-tori` and the two props above — queued by Tier 10, issue 6

## R-0052 [verify] Verify defn:cylinder-monodromy
- status: open
- agenda: paper:defn:cylinder-monodromy
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: defn:cylinder-monodromy
- created: 2026-09-28

- `defn:cylinder-monodromy` — `sections/slope_blocking.tex` — author's [verify] (slope_blocking:132, "Give these two last subsections another verification"); a defn, inside a `sketch`; check well-definedness of `S(X_0', x_0)` (free homotopy classes vs. based loops) — queued by Tier 4, issue 4

## R-0053 [verify] Verify fact:S-normal-symmetric
- status: open
- agenda: paper:fact:S-normal-symmetric
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: fact:S-normal-symmetric
- created: 2026-09-28

- `fact:S-normal-symmetric` — `sections/slope_blocking.tex` — author's [verify] (slope_blocking:132); a `fact` with no proof, inside a `sketch`; note the statement writes `S(X_0, x_0)` where the definition has `X_0'` — queued by Tier 4, issue 4

## R-0054 [verify] Verify prop:blocking-monodromy
- status: open
- agenda: paper:prop:blocking-monodromy
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:blocking-monodromy
- created: 2026-09-28

- `prop:blocking-monodromy` — `sections/slope_blocking.tex` — author's [verify] (slope_blocking:132); sketched, no proof environment; Roey: "should be overriden by the chat" (**[needs Roey]**), so a verdict reports only — queued by Tier 4, issue 4

## R-0055 [verify] Verify prop:fiber-disjoint-trajectory
- status: open
- agenda: paper:prop:fiber-disjoint-trajectory
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:fiber-disjoint-trajectory
- created: 2026-09-28

- `prop:fiber-disjoint-trajectory` — `sections/slope_blocking.tex` — author's [verify] (slope_blocking:350), inside a `sketch`; the writer's note says $\gamma_0$ chosen by holonomy need not have a straight representative missing $F$, and `lem:primitive-purity` may fail for non-discrete $H$ — queued by Tier 4, issue 3

## R-0056 [verify] Verify cor:slope-minus-one
- status: open
- agenda: paper:cor:slope-minus-one
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: cor:slope-minus-one
- created: 2026-09-28

- `cor:slope-minus-one` — `sections/slope_blocking.tex` — repaired proof (minimal $B$, $\lambda\in\{\pm1\}$ via `fact:aw-slope-pm-one`), inside a `sketch`; check against AW21 Example 2.6 (same-fibre pairs have slope 1, so the corollary claims no generic-fibre pair is finitely blocked) and the irreducibility of $\cM$ — queued by Tier 4, issue 3

## R-0057 [verify] Verify prop:saturated-markings-coverings
- status: open
- agenda: paper:prop:saturated-markings-coverings
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:saturated-markings-coverings
- created: 2026-09-28

- `prop:saturated-markings-coverings` — `sections/slope_blocking.tex` — new, blue: the two claims split off `fact:aw-closed-markings` (maximal saturated $\overline{\cN}$; saturated markings ↔ (half-)translation coverings for reduced generic $X$), sketch read off AW21's proof of Lemma 2.10 and Sublemma 2.12 (`AW21.src/main.tex:543-603`) on Roey's slope_blocking:93 lead; inputs `fact:aw-slope-pm-one`, `defn:saturated-marking` (blue, queued — verify after it); flagged unverified: $\Sigma'=P(X)$ at generic $X$, $\cN_\pi$ irreducible over $\cM$ and partitioning $X\setminus P(X)$, and the reading of part (1) — queued by Tier 4, issue 3b

## R-0058 [verify] Verify cor:parking-garage-classification
- status: open
- agenda: paper:cor:parking-garage-classification
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: cor:parking-garage-classification
- created: 2026-09-28

- `cor:parking-garage-classification` — `sections/arithmetic.tex` — author's [verify] (arithmetic:64, "Does it follow from the definition of a parking garage?"): does "without plugs" follow from the parking-garage definition (billiards:51 material, `CW12`)? A `cor` inside a `sketch` with no proof; a verdict answers the question and reports only, it does not recolour — queued by Tier 5, issue 3; 2026-09-24 see also `rmk:billiard-corners`: "without plugs" does not exclude boundary vertices of angle $k\pi$, whose preimages are not in $\cC_{\Delta_P}(M_P)$ — updated by Tier 5b, issue 1; 2026-09-24 the statement now reads "a parking garage without plugs … and without semi-corners (`defn:billiard-pathologies`)" (Roey's fifth reply, item 13), so the verdict should also say whether the result holds under both exclusions (the route `rmk:billiard-corners` + `prop:cornered-arithmetic` reaches only "$M_Q$ arithmetic"); the plug question stands — updated by Tier 5b, issue 4

## R-0059 [verify] Verify lem:torus-corners-torsion
- status: open
- agenda: paper:lem:torus-corners-torsion
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: lem:torus-corners-torsion
- created: 2026-09-28

- `lem:torus-corners-torsion` — `sections/markings.tex` — 2026-09-24 (Tier 5b, issue 2, item 7) rewritten as "Cornered tori are marked once": the old torsion-bound statement and its smaller-torus covering `q` are gone, replaced by Roey's "step 2/one marked point" — for a marked torus $T$ with $\Lambda(T) = L(T)$ (`eq:relative-lattice`) and $\Sigma_T \subseteq \cC(T)$, $\#\Sigma_T = 1$ — plus a new closing paragraph proving $\Lambda(T) = L(T)$ for $T = T_\Lambda(X)$ marked by $\rho_X(\Sigma_X)$; the "Linear parts" and "The commutator" paragraphs reuse the old proof's lift-to-$\R^2$/$\det(\Id-A) \in \{1,2,3,4\}$ argument, but "The commutator" now concludes $t \in \Lambda(T) = L(T)$ directly (no torsion bound) and "One marked point" gets $d \in \Lambda(T) = L(T)$ the same way; check the new "relative torus" paragraph's maximality step ($\Lambda(T) \subseteq \Lambda(X) = L(T)$ off `eq:relative-lattice`); a fresh argument on the same lift/commutator machinery, verify whole — queued by Tier 5, issue 4, rewritten by Tier 5b, issue 2

## R-0060 [verify] Verify rmk:billiard-corners
- status: open
- agenda: paper:rmk:billiard-corners
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: rmk:billiard-corners
- created: 2026-09-28

- `rmk:billiard-corners` — `sections/markings.tex` — new, blue, Roey's item-11 link (vertex of angle $\pi p/q$ ⇒ preimages fixed by the lift of $\sigma_e\sigma_{e'}$, a rotation by $\pm 2\pi p/q$): a `rmk`, queued because it is a recolourable argument; rests on `rmk:plug-unfolding` and on the blue stabiliser `\Sketch` after `defn:billiard-table` (verify with it); check the $q = 1$ case ($\sigma_e = \sigma_{e'}$ in $\Delta_P$ by injectivity of $D$), the stabiliser $g\Gamma_v g^{-1}$ of $g\tilde v$, and the "exactly when" (only for $\cC_{\Delta_P}$, not for $\cC(M_P)$) — queued by Tier 5b, issue 1; 2026-09-24 wording only: the $q = 1$ vertices are now called semi-corners (`defn:billiard-pathologies`), the last sentence reads "neither semi-corners nor plugs", argument unchanged — updated by Tier 5b, issue 4

## R-0061 [verify] Verify prop:cornered-arithmetic
- status: open
- agenda: paper:prop:cornered-arithmetic
- priority: normal
- depends_on: []
- source: comment_roadmap.md, Verification queue: prop:cornered-arithmetic
- created: 2026-09-28

- `prop:cornered-arithmetic` — `sections/arithmetic.tex` — 2026-09-24 (Tier 5b, issue 6, item 15, Roey's sixth reply) the DS paragraphs of item 8's proof are cut; the proof is now the relative-torus route alone: normalise $\rho_X$ at $\sigma_0 \in \Sigma_X$; for $\varphi \in \Aff^{+}_{d}(X)$, $A = D\varphi$, show $A\Lambda(X) = \Lambda(X)$ (`eq:relative-lattice`), define $\bar\varphi$ on $T = T_\Lambda(X)$ with $\rho_X \circ \varphi = \bar\varphi \circ \rho_X$, $\bar\varphi \in \Aff^{+}_{d}(T, \Sigma_T) \setminus \Trans(T)$ when $A \ne \Id$; so $\Sigma_T = \rho_X(\Sigma_X) \subseteq \cC(T)$, and `lem:torus-corners-torsion` (with its $\Lambda(T) = L(T)$ paragraph) gives $\#\Sigma_T = 1$. Inputs: `rmk:nonempty-marking`, `defn:relative-marking` with `eq:relative-lattice`, `defn:corners`, `defn:arithmetic` (established), `lem:torus-corners-torsion` (blue, queued — verify after it); no DS or Delaunay input, no citation. The new blue `rmk:cornered-arithmetic-ds` after it is not an input. Check first: $A\Lambda = \Lambda$ (both $L(X)$ and $\hol(H_1(X, \Sigma_X; \Z))$ preserved, as $\varphi$ permutes $\Sigma_X$) and the well-definedness of $\bar\varphi$ — queued by Tier 5b, issue 2; rewritten by Tier 5b, issue 6
