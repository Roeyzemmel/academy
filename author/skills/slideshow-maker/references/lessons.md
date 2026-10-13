# Lessons from the first talk (an illumination-in-billiards talk, 25 minutes, deck + lecture notes)

Each item: the rule, why, and what happened. Examples are labelled; replace them with the new talk's.

## 1. Before writing
- Ask: who is the audience and what do they already know; how many minutes; what is the **one main
  statement**. We started with a headline that a source contradicted (a counterexample family in the
  literature) and had to retract it. Keep content in one file per frame group so a headline change moves
  frames, not text.
- Ask early what is cut when time is short: the author said "I am open to more cutting" and "let's move things
  to a bonus part"; the cuts are decided with the author, not alone. The slot itself changed (30, then 25 minutes).
- On retraction: stop and ask the author for the new main statement; record the retraction under "Retracted" in the
  talk's README; check the author's paper for the same error and file tickets without asking; cut material may
  survive briefly in the notes if the author wants it.

## 2. Truth discipline (most expensive mistakes)
- Open the source and read the pinpoint before citing it. Our first review found a wrong attribution (a
  statement credited to the wrong lemma), a statement credited to a paper whose version has extra hypotheses,
  and a "dichotomy" that was stated too strongly.
- Carry the hypotheses: marked set, genus > 1 for uniqueness of the primitive surface, "simple polygon" for the
  classification, the condition that preimages of marked points are marked. A slide that drops one is wrong
  even if the paper is right.
- Test every claimed statement on the smallest example before putting it on a slide (the unit square covers a
  1 x 1/n rectangle for every n, so "every polygon has a primitive polygon" is false for torus covers).
- Never state what a source contradicts; if the author's own draft contradicts a source, tell the author and
  file a ticket; do not smooth it over.
- Copy the author's own definitions from the paper source; our reconstructed definition of the author's graph was
  wrong and had to be redone. Never cut the author's own construction from the core without asking.
- Every bibliography entry is checked in the library or goes out as a cite ticket; two entries were added from
  memory.
- An independent read-only reviewer (Opus) catches what the writer cannot see; verify each finding against the
  sources before acting (one finding was already fixed).

## 3. Status without decoration
- No colour coding of status, no bracket tags (`[cited]`, `[sketch]`), no commentary about the project's state
  ("this step is not written", "in the draft", "work in progress", "not checked"). The talk transfers ideas;
  it does not report progress.
- Status is carried by the environment: a result of the literature carries its citation in the header; an
  unproved statement is an `Idea`; a definition is a `Definition` (never an idea); a proved or one-line-provable
  statement is a plain proposition with an "Idea of proof". Tell the author, once, that this is now the only
  status signal.
- Unproved statements that come from the author's own work stay `Idea`; removing a tag must not make them look proved.
  A paper in preparation is not cited: its statements are Ideas, unless proved in one line on the slide.
- When a statement changes environment (a proposition becomes an idea), fix its label prefix too.

## 4. Order and time
- Define before use. Audit: list every term and the frame that introduces it (we found "torus cover", "cone
  point", "periodic point", the marked set, "plug" used before their definitions).
- Order by dependency, and put the main statement early (by minute 10-13). The covering lemma only mattered
  after the classification, so it moved behind it.
- Budget: about 25 minutes = 14-16 core frames at 1-2 minutes. Write a minutes-per-frame table and add it up.
  Our first estimate was about 41 minutes for a 30-minute slot; the slot shrank to 25, a later estimate was 32, and
  splitting overfull frames took the core from 15 to 19 frames: re-time after every split or merge. Cuts: worked examples to bonus, merged sparse frames, one correspondence
  statement to bonus, the algorithm dropped ("present the idea, not the algorithm").
- Always end with a summary-and-questions frame (our deck once ended on an idea and then "Bonus"). It replaces a
  separate key-takeaways frame; the author removed that one.
- Bonus and appendix frames come after the summary in the deck; promote a bonus frame when a core term depends
  on it (origamis defined "torus cover").

## 5. Density and layout
- One idea per frame. If a frame is overfull, **split it**; do not shrink below `\small`
  (`\footnotesize` frames were later split).
- Slide definitions are short; the formal definition is in the notes (`\onlyarticle`).
- Figures go in a **corner column** next to the text (`withfig`); a figure that is a wide strip stays full width
  under the text. Small figures under long text were the most common complaint.
- Sparse frames after a split are fine; merge two only if both are almost empty.

## 6. Figures
- A figure earns its place only if it shows the mechanism of the claim with a concrete instance. A bare
  commutative diagram of the maps does not illustrate "blockers lift along covers"; a covering of squares with a
  lifted segment does.
- Verify geometry by script with exact arithmetic (our tiling figure used the wrong subdivision: the medial
  subdivision is not a tiling by reflection; a script checked adjacency by reflection).
- Projector-readable: labels at least `\footnotesize`, thick lines, few words; panels in a 2x2 grid for a
  narrow corner column.
- Mark hand-edited generated figures in their header comment; a generator rerun overwrites hand fixes.
- Captions live in one file (`figcaptions.tex`), one entry per figure; the deck shows no captions.

## 7. Notation
- One symbol per object; keep the source paper's symbols. Resolve clashes before the end, not after the
  review (our clashes: the angle pi / a covering map / an origami's map / a projection; K the group vs K_k the
  kites; P the table vs P_1, P_2 cells; B the blocking set vs B(X) the chambers; D the derivative vs D(X) the
  decomposition; T the torus vs T a symmetry; S for five graphs).
- Rename with exact-string replacements, then grep content, figures and captions for the old symbol, and keep
  labels other files reference.
- Put a short notation paragraph at the start of the notes.

## 8. Two outputs from one source
- Deck and notes share content files; notes add `art-*` prose and everything the slides leave out; the notes'
  section order mirrors the deck's (we reordered both when the deck's order changed).
- Notes carry the full statements, proofs the audience will want, and the notation paragraph; the notes
  abstract must not promise sections that do not exist (it did).

## 9. Build and QA loop
- Build into a scratch directory. Require: zero `^!` errors, no undefined or multiply-defined references, no
  `Overfull \vbox` in the deck log. Map each overfull box to its page:
  `awk '/Overfull .vbox/{o=$3} /^\[[0-9]+/{if(o!=""){print $0,o;o=""}}' slides.log`.
- Render pages to PNG (`pdftoppm -r 45`), build a contact sheet and look at it; read the changed frames at
  higher resolution. A stale PDF misleads a reviewer: rebuild before review.

## 10. Working with subagents
- Parallel: source verification, figure drawing (disjoint figure files), the reviewer. Tell each agent which
  files it may edit; two agents edited `figcaptions.tex` at once only because they touched different entries.
- A figure-maker must verify its mathematics (we asked for a script) and report what it could not verify; draw
  the closest correct chain if the requested one fails.
- Do not commit while agents are mid-edit; build, look, then ship. Do not edit while a reviewer runs; the reviewer
  rebuilds into its own scratch directory (a stale PDF misled one review).
- Use the repository's route from the first commit (`ship.py start <sub> <topic> --role author`), and ship each round;
  restore generated views that a checker rewrote instead of leaving them dirty.
- The author asked for more subagents: use one reviewer per round and parallel agents for sources and figures.
- File tickets for findings about the paper without asking.

## 11. Pitfalls
- `\ifdeck` conditionals inside a beamer frame break it; use a macro defined outside.
- `lmodern` and `microtype` font expansion errors in a minimal TeX Live: install `lmodern`.
- A mix of a mix fails in tikz (`\c!35` with `\c=red!60` gave "Undefined color"); write `red!21` or `red!60!white`.
  A node text with `\\` needs `align=center`. `\foreach` over coordinate lists needs `\px/\py` pairs.
- In `figcaptions.tex` use `\csname`, not `\@namedef` (the preamble has no `\makeatletter`).
- Labels keep stale prefixes after a statement changes environment; fix them.
- Keep the talk README's file list in step with `slides.tex` (order lives there, not in the numeric prefixes).
- Generated figures and captions drift apart: regenerate captions with the figures.
- The repository's commit route (`ship.py`) is the only way to commit; submodule pointers and the board's
  error ledger are never committed from a session, whatever the stop hook says.

# Lessons from the second round (revising a mature deck with the author's comments; same talk)

## 12. Revising with the author's comments
- **State the main subject up front and in the title.** The author's last comment was that the talk's subject (here:
  finding the primitive billiard of a given billiard) must be emphasised. Put it in the subtitle, in a deck-only
  "What this talk is about" frame right after the title (goal, why, how: three bullets, with unproved parts called
  `Idea`), and in the first sentence of the notes' abstract and of the handout. Check at the end that every core
  frame prepares or uses the main subject; the rest is bonus.
- **State results for the notion the audience reads, define the general one once.** The author wanted results for
  non-illumination, with finite blocking only defined on the first frame, "to make it more readable". Do it only
  where the sentence stays true with the same hypotheses and source (the n = 0 case of a closedness or lifting
  statement has the same proof); statements whose content is finite blocking (dichotomy, classification) stay as
  they are. Give the author the list of the ones left, with the reason.
- **Technical machinery by intuition, then one clean statement.** Where the formalism is not the point, define the
  object in two plain sentences (a flat morphism: finite-to-one, locally an isometry up to the allowed rotations
  and reflections, straight segments to straight segments, singular points matching) and state the one result
  that is used (two points of the image do not illuminate each other iff no two lifts do). Check **both
  directions** of an "iff" and say which one the cited source gives; a direction that is your own path-lifting
  argument is reported to the author as not previous work. An open-question item that the new statement answers
  is removed from the notes.
- **Nothing is invented; everything follows from earlier work.** When the author names an example ("the double
  EW slope 1 example"), find it in the author's own earlier work (research notebook, paper history,
  `git log -S`, archived drafts) and copy it; if it cannot be identified, leave a placeholder and report the
  candidates. The agent that writes the slide does not repair the earlier statement; it reports.
- **No internal names on slides or in the paper.** Notebook object ids, instance names, ticket numbers and
  "notes" are replaced by a citation key the author chooses (`[Ze27]`); add the bibitem only with details the
  author gives, otherwise "in preparation" and ask.
- **When asked to replace a figure's object, verify the slide's claim for the replacement first.** The author
  asked for "the isosceles triangle got by flipping along the long edge"; for the right triangle
  (pi/10, pi/2, 2pi/5) that is (pi/5, 2pi/5, 2pi/5), whose unfolding has genus 2 and half the area of the kite's,
  so the slide's claim ("same unfolding") was false for it. Use the closest correct object (the same triangle
  flipped along the other leg), say so plainly, and report both. Compare genus, cone angles, area and groups by
  script.
- **Ask what a figure instruction colours.** "Colour the edges by the triangle they come from" meant colouring the
  *vertices* by the vertex of the triangle they fold to; the first version coloured edges. For a colouring, ask:
  edges, vertices or tiles; by what.
- **A user-supplied figure source is data, not truth.** A pasted 26-gon "extracted from an image" was verified
  (tiling type, tile count, 26 corners, only x and y inside, every B/C point a vertex) before use, and the
  caption says "after Tokarsky's example", not "Tokarsky's own", until the match with the paper is checked.
- **A classical theorem as stated on the slide may be a corollary with a convention.** The polygon version of
  Tokarsky's lemma is true if trajectories stop at vertices and false if they pass through vertices of angle
  pi/j (rhombus with angles pi/4, 3pi/4). Check the paper's convention for trajectories, state it on the slide in
  a short parenthesis, attribute the triangle lemma to the source and the polygon statement to whoever proves it.
  If the primary source is paywalled, say so and base nothing on memory.
- **A convention a formula depends on goes on the slide** (side numbering of the octagon: the transitions
  C_k -> C_{k+3}, C_{k+5} are off by one otherwise). Recompute such formulas from the geometry by script, for all
  cases.
- **Dropping a slide from the deck is not dropping it from the notes**; ask which was meant, wrap a deck-removed
  frame in `\onlyarticle{...}` when it stays in the notes, delete the file when it is gone from both. Merge two
  statement-only bonus frames into one and keep the proof and the figure in the notes (`\onlyarticle`).
- **Talk-voice lines do not belong in the notes** ("the talk concerns the left column", "the best converse one can
  hope for"): wrap in `\onlydeck` or delete; delete again when they stop being true.
- **Figures are too small more often than too large.** Fixes that worked: one figure per frame, legends moved from
  inside the figure to a caption line on the slide or the caption, the explanatory paragraph removed so the figure
  can fill the frame, the column ratio set per frame (`withfigr{name}{0.36}{0.62}`; `withfig` is fixed at
  0.64/0.34), figures side by side rather than stacked. Look at every changed frame as an image.
- **Gather open decisions into one batch** for the author (reword / rename / remove, the recommended option
  first) instead of asking one by one; unverifiable items (a source the library lacks, a formula) go to parallel
  verifier agents, not to the author.
- **Hygiene when committing**: `git add -A talk ':!talk/pdf' ':!talk/.claude'` (generated PDFs and an
  agent-memory directory are not part of the work); commit on the work branch only, never on main; the author may
  stage changes to trace work: leave the index as it is and add to it.

## 13. A third output: the overview handout
- For distribution to the audience: 2-3 pages, `overview.tex` with `\deckfalse` and the same preamble, unnumbered
  sections, one abstract sentence naming the main subject, only main ideas in the talk's order, no proofs and no
  technical definitions beyond one clause, at most two figures, the same reference list restricted to what is
  cited. Every statement is **copied** from `content/*.tex` with its environment (an idea stays an idea); nothing
  is strengthened. Build it into its own scratch directory and check the page count.
- The notes review (an agent with edit rights only on notes-only files, building into its own directory) found: a
  `\cref` printing "Theorem" for propositions and ideas that share one counter (load `hyperref` and `cleveref`
  before the `\newtheorem` lines in the article branch); definitions duplicated between `art-*` files and frames;
  attributions that no source supports (remove or weaken, list them for the author); overclaims ("every table
  covers a primitive one" is an Idea for tables, a theorem for surfaces); a notes abstract promising a claim that
  the body does not make. Run this review once per revision round, with the deck's overfull count before and after.

## 14. Working with several agents at once (what worked and what broke)
- Disjoint file sets per agent, a separate `-outdir` per agent (`.build/talk-A`, `-B`, `-C`), small Edit-tool
  replacements for the shared `figcaptions.tex` (re-read before each edit), and "if the build fails on another
  agent's half-finished file, wait a minute and retry, do not fix it". No collisions with four agents in parallel.
- Brief each agent with the author's request in the author's words, the files it may edit, the verification it
  must run (script, not belief), and what to report (computed vs only read vs could not verify).
- Windows pitfalls: in Git Bash `sed` with backslashes silently does nothing, and Python non-raw strings turn
  `\b`, `\f`, `\t` into control characters (a search for `'\fi'` never matches `\fig`, and `\fig` itself begins with
  `\fi`: search for a newline followed by `\fi`). Edit TeX with raw strings (`r'...'`) or the Edit tool; re-read
  the file after every brace-changing edit and build after every batch; a doubled or missing `}` at the end of a
  `\slide` is the usual cause of "\begin{frame} ended by \end{document}". Long here-documents in the shell fail on
  quotes: write the file with the Write tool.
- A beamer frame body must not contain `\ifdeck ... \fi` (or `\else`); use `\onlydeck{}` and `\onlyarticle{}`.
