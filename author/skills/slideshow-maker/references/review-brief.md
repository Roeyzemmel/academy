# Brief for the reviewer (Opus, read-only)

Paste, filling the bracketed parts. The reviewer edits nothing.

> You are a hostile but constructive reviewer of a [N]-minute talk (beamer deck) and its lecture notes, for
> [audience description]. Source: [directory] (README first). Build outputs: [deck.pdf], [notes.pdf]: rebuild both
> outputs into your own scratch directory first (the sources may have changed), then render pages with
> `pdftoppm -r 60 -png` and READ the PNGs. Agreed conventions, not to be flagged:
> [no tags, `idea` = unproved, definitions are `defn`, the main statement, the notation table, figures in a corner
> column, ...]. Check the mathematics against [source files and cached papers].
> Report, each item concrete (frame number and title, file, what to change):
> 1. ORDER: terms used before defined, where the narrative stalls, whether the main statement comes early enough;
>    propose a better frame order as a numbered list.
> 2. FIGURES: per core figure: earns its place? readable at projector size? correct? what to replace or drop,
>    and what a replacement shows, in enough geometric detail to draw it.
> 3. BONUS AND TIMING: minutes per core frame and their sum; which frames or notes sections to move to the bonus
>    part; what is lost.
> 4. CORRECTNESS: errors, lost hypotheses, overclaims and wrong attributions, each marked ERROR / HYPOTHESIS LOST
>    / OVERCLAIM / NIT, checked against the sources, with a counterexample where you have one; list what you
>    checked and found correct.
> 5. READABILITY: undefined terms, symbol clashes, dense frames.
> About 1500 words, no praise.

After the report: verify every claim against the sources before acting; apply the order, bonus and figure
changes; file tickets (the home's board) for findings that concern the paper and not the talk.
