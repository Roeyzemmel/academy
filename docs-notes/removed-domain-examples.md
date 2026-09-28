# Domain examples removed from `math-proof-writing` when it became `academy:rigor`

Source: `claude-flatsurf/domain/math-proof-writing/SKILL.md` (imported at
`_import/flatsurf/domain/math-proof-writing/SKILL.md`). The generic skill keeps the
substance with neutral wording. The domain-flavoured originals below belong in the
translation-surfaces pack's `traps.md` (Group B), where they can be worked traps
rather than illustrations.

The last column names only the topic of a possible trap. It asserts no mathematics:
whoever writes `traps.md` states each trap from the pack's theorem sheets and cards,
not from this note.

| Section of rigor | Original wording (verbatim) | Generic replacement in rigor | Topic for `traps.md` |
|---|---|---|---|
| 4, "Say what a counterexample would have to look like" | "Concretely: which surface, which genus, what would have to go wrong, what the smallest case is." | "which object, which parameters, what would have to go wrong, what the smallest case is" | Specifying a counterexample: name the stratum, the genus and the smallest surface first. |
| 4, "A blocked route is not a blocked question" | "\"Tokarsky's construction doesn't transfer, because those corners unfold to regular points\" is a correct observation about one route. It is not evidence that no counterexample exists, and treating it as such is how a findable example gets written up as an open question." | "\"The known construction does not transfer here, because the relevant points behave differently\" is a fact about one route" | When Tokarsky's construction fails to transfer, that is not evidence for illumination. |
| 4, "Record the class you searched" | "no counterexample among origamis with ≤ 6 squares, searching over vertex pairs only" | "No counterexample among objects of size ≤ 6, over pairs of distinguished points only." | What a search over small origamis and vertex pairs structurally excludes. |
| Citations (now in `citation-discipline`) | "\"By [EM18], the orbit closure is an affine invariant submanifold\" is only legitimate once it is said why the ambient hypotheses hold." | "\"By [X], the object is Y\" is legitimate only once it is said why X's hypotheses hold here." | Checking the ambient hypotheses before invoking the orbit-closure theorems. |
| 5, gap markers | "\"[gap: this step needs the surface to be primitive — not yet checked]\"" | "\"[gap: needs hypothesis H — not checked]\"" | Primitivity as a silent hypothesis. |
| 5, gap markers | "prefer a visible marker (a `\\gap{...}` macro, a `TODO`)" | "the home's machine-note macro" | (not domain; the macro is the Author config's `noteMacros.machine`) |

Also dropped for neutrality: "genus zero" from the degenerate-case list (the list keeps
empty set, zero, one point, the trivial group and the parameter boundary). The pack may
restore it.
