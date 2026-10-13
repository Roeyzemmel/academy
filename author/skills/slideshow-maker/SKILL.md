---
name: slideshow-maker
description: 'Build a research talk as a beamer deck plus lecture notes from one TeX source set: verified statements, definitions before use, figures that show the mechanism, no status tags, a review loop. Use for "make slides", "a 25-minute talk".'
---

# Slideshow maker

A talk transfers ideas to a specific audience in a fixed time. It is not a progress report and not the paper
in small type. The full list of lessons, with the mistakes that taught them, is `references/lessons.md`; read
it once before the first frame. Companion skills: `academy:rigor` and `academy:citation-discipline` govern what
may be said; `academy:notation-discipline` governs symbols; the domain pack has the figure conventions.

## Steps
1. **Pin the brief** (ask, do not guess): audience and what they know, minutes, the one main statement, what
   the author wants cut first. One question batch, then proceed.
2. **Verify before drafting.** Every cited statement is read in the cached source (`library_lookup`, then the
   text) with its hypotheses; every claimed statement is tried on the smallest example. A source that
   contradicts the author's claim is reported to the author and filed as a ticket, not smoothed over.
3. **Plan the order and the time**: list each term with the frame that defines it; order by dependency; the main
   statement before the midpoint (minute 10-13 of 25); a minutes-per-frame table summing to the slot; everything cut goes to the bonus
   part. Show the plan to the author.
4. **Start from `template/`** (deck and notes from one source set; see its README). One content file per frame
   group; frames in `content/NN-*.tex`, notes-only prose in `content/art-*.tex`, bonus in `b-*`.
5. **Write the frames** with the rules below; figures are drawn and checked by script (parallel agents on
   disjoint figure files).
6. **Build and look**: scratch build of both outputs; zero errors, no undefined references, no overfull deck
   frames; render pages to PNG and read them (`references/lessons.md` section 9).
7. **Review**: one read-only Opus reviewer per round (do not edit while it runs) with `references/review-brief.md`; verify each finding against the
   sources, apply order, figure and bonus changes, file tickets for findings about the paper. Rebuild, look again.
8. **Ship** by the home's route (the Author home: `ship.py`, on a work branch). Report: what the talk contains,
   the minutes table, what moved to the bonus part, what the reviewer found and what you did, and what is not
   verified. Re-time after every split or merge.

## Rules that decide most frames
- **Status without decoration**: no colour, no bracket tags, no remarks about the project's state. A cited
  result carries its source in the environment header; an unproved statement is an `Idea`; a definition is a
  `Definition`; a proved short statement is a proposition with "Idea of proof". The author's paper in preparation is never
  cited; its unproved statements are Ideas. Say once to the author that the
  environment name is then the only status signal.
- **Define before use**, on the slide where the term first appears; formal definitions in the notes.
- **One idea per frame**; split an overfull frame, never shrink below `\small`; figures in a corner column.
- **Figures show the mechanism with a concrete instance**, readable at projector size, geometry verified by
  exact arithmetic, captions in `figcaptions.tex`.
- **One symbol per object**; resolve clashes before review; after a rename grep content, figures and captions.
- **Present the idea, not the algorithm**; end with a summary-and-questions frame.
- **Carry the hypotheses** of every statement; a dropped hypothesis is an error.

## References
- `references/lessons.md`: the lessons, grouped, with what went wrong.
- `references/review-brief.md`: the reviewer's brief.
- `references/frame-patterns.md`: frame patterns and anti-patterns in TeX.
- `template/`: a building deck + notes skeleton.
