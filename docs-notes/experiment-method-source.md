# Experiment method — source material for scientist/skills/experiment-method

(The imported copy under `_import/` was removed once distributed; the original is unchanged in `C:\Work\Math\claude-flatsurf\domain\`.)

Extracted verbatim from the generic (domain-free) parts of the old
`flatsurf-computation` SKILL.md (`_import/flatsurf/domain/flatsurf-computation/SKILL.md`)
during the Group B build of the translation-surfaces domain pack, 2026-09-28.
The domain-specific parts (environment table, bundled scripts, API recipes, API traps)
went to `domains/translation-surfaces/computation/` and `traps.md`.

Note for the scientist builder: the examples in step 2 ("square torus, 3-square L, regular
pentagon") and steps 4 and 6 are domain-flavoured; in a role plugin replace them by a
reference to the domain pack's `examples.md` (validation cases) and `traps.md`.

## Framing (from the skill intro)


Numerics in this subject earn their keep by killing false conjectures cheaply and
by revealing what the correct statement should be. They never prove anything. Keep
that boundary visible in everything reported: an experiment produces "no
counterexample found up to length 40 on these 6 surfaces", never "true".

## The seven steps


1. **Say what would refute the claim** before computing anything. An experiment
   with no refuting outcome is not an experiment.
2. **Validate the setup on something you know.** The square torus, the 3-square L
   in $\mathcal{H}(2)$, the regular pentagon. If the pipeline gets the torus
   wrong, nothing downstream means anything. Every bundled script does this.
3. **Prefer exact arithmetic.** Number fields for Veech surfaces, `ExactReals` /
   pyflatsurf for the rest, `Fraction` in the fallbacks. Floating point turns
   "these two points coincide" — the whole question in illumination problems —
   into a threshold choice, and the answer then depends on the threshold.
4. **Watch the stratum.** Adding a marked point moves $\mathcal{H}(2)$ to
   $\mathcal{H}(2,0)$ and changes dimensions and orbit closures. Unfolding often
   produces a cover rather than the primitive surface, and `erase_marked_points()`
   changes the object. Print the stratum at every stage.
5. **Report the bound and the class searched.** "No connection with squared length
   below 1600, over these 6 surfaces, searching vertex pairs only" is a usable
   research statement; "it doesn't illuminate" is not. Naming the class is not
   pedantry — it is what lets a reader (and you) notice that the search space
   structurally could not have contained the counterexample, which is the most
   common way an exhaustive-looking computation means nothing.
6. **Don't let the computation replace the argument.** Before building
   validation layers around a numerical result, check whether a short proof
   settles it. Two points inside a single cylinder are joined by a segment that
   cannot meet the cone point — one observation, no computer. Reaching for
   exhaustive search where a clean argument exists is the characteristic waste
   here.
7. **Save the script.** Referees and coauthors ask how a computation was done, and
   a rerunnable file with its seed and versions is the answer. Keep experiment
   scripts next to the paper.

When an experiment produces something surprising, suspect the code first — a
stratum mismatch, a squared-vs-linear bound, the factor of 2 — before believing a
new theorem.

## Also generic (from "First: which environment am I in?")

> **A project may forbid running experiments locally at all.** [...] Read the project's
> `CLAUDE.md` before picking a row of that table; it wins over this skill.

> **If Sage is present**, use the recipe files [...] rather than writing from memory — this API changed substantially in recent versions and plausible-looking calls from older tutorials silently do not exist.
