# Talk template (deck + lecture notes from one source set)

Copy this folder, rename, fill. Build (into a scratch directory, never next to the sources):

    latexmk -pdf -interaction=nonstopmode -outdir=/path/to/scratch slides.tex
    latexmk -pdf -interaction=nonstopmode -outdir=/path/to/scratch summary.tex

- `slides.tex` (beamer, `\decktrue`) and `summary.tex` (article, `\deckfalse`) load `preamble.tex`.
- `content/NN-*.tex`: frames, shared by both outputs. `content/art-*.tex`: notes only. `content/b-*.tex`: bonus
  frames (`\bslide`, after the summary in the deck, in their natural place in the notes). `content/a-*.tex`:
  appendix (`\aslide`).
- `\slide{title}{body}`, `\bslide`, `\aslide`, `\slideT{deck title}{notes title}{body}`, `\fig[h]{name}`,
  `\begin{withfig}{name}...\end{withfig}` (figure in a corner column, fixed 0.64/0.34),
  `\begin{withfigr}{name}{text}{fig}...\end{withfigr}` (the same with the column fractions chosen per frame; use it
  when the figure is the point of the frame), `\speak{...}` (speaker note, deck only),
  `\onlydeck{}`, `\onlyarticle{}`.
- `\dslide{title}{body}`: a frame in the deck that does not appear in the notes.
- Statement environments: `defn`, `prop`, `thm`, `lem`, `cor`, `idea` (unproved), `ex`, `rmk`.
- Figures: bare `tikzpicture` files in `figures/`, captions in `figcaptions.tex` (one entry per figure).
- `config.tex`: `\Bonusfalse`, `\Backupfalse` remove those parts from the deck.
- Keep the section order of `summary.tex` equal to `slides.tex`.
- Do not put `\ifdeck ... \fi` inside a frame body; use `\onlydeck{...}` and `\onlyarticle{...}`. A third output, a
  2-3 page handout of the main ideas (`overview.tex`, same preamble with `\deckfalse`, statements copied from
  `content/`), is described in `references/lessons.md` section 13.

## Sections of the talk's own README (write one)

Brief (audience, minutes, main statement); minutes-per-frame table; notation table; sources checked (with
pinpoints); retracted statements; open points; file list kept in step with `slides.tex`.
