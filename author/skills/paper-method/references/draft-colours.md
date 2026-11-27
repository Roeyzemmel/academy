# Draft colours and the provenance marker

The mapping between colours, registry statuses and verdict words is
`academy:status-vocabulary`; this file is how a writer applies them in the tex. The
scheme is the home's: `author.statusLevels` (or, in older homes, `author.envs`,
`author.colourCommands`, `author.colours`) and `author.provenance` (`docs/config.md`).

## Status colours (`author.statusLevels`)

Every theorem-like statement carries exactly one level, recording how far it is
established. Each level has a `name`, an `env` and/or a `command`, a `colour`, the
registry `statuses` it may carry, and a `kind`: `established` (the one uncoloured level:
proved in full, or cited precisely), `unestablished` (nothing established may rest on it:
checker R1) or `commentary` (not a claim). The default scheme is established, sketch
(blue), conjectural (red), both unestablished, and meta (brown, commentary); a home may
use others (one "draft" level, other colours, extra levels). Apply them through the
preamble's macros, never a raw `\color`:

- **a whole statement** → the level's `env`, wrapped outside the theorem environment:
  `\begin{sketch} \begin{prop} … \end{prop} \end{sketch}`;
- **a span inside a sentence** → the level's `command`: `\Sketch{…}`.

The command form takes its content as a macro argument, so it **breaks on a blank line
or on an `&` inside a `tikzcd` or `align`**; the environment does not. Recolour by
renaming one word. The colours themselves are defined once, in the preamble.

An unestablished statement becomes established only when an Expert verification (a `verify` ticket, two
agreeing verifier runs) lands. **No writing agent recolours its own work.**

## The reword marks (a level of kind `mark`)

A settled statement (`proved` / `proved-modulo`) reworded after its review is
**reworded**: settled on its earlier wording, reword review owed
(`academy:status-vocabulary`). It keeps its status colour; on top of it the words
changed since the reviewed text are violet, `\Reworded{…}`, and the removed words stand
struck where they were, `\Struck{…}`. Violet, not purple (purple is the `\Claude` notes).

- **Generated, never typed.** `scripts/reword_marks.py` (dry run by default, `--apply` to
  write) takes every claim `registry.py stale` lists, recovers the reviewed text exactly
  from the paper's git history (its hash must be the base pass's `statement_hash`, or the
  statement is reported and left alone), diffs it word by word against the current text
  and writes the marks; it removes them when the claim is no longer stale (the reword pass
  confirmed). A writer never adds, edits or removes a mark by hand: after a rewording,
  run the script.
- **Outside the hash.** Every statement hash ignores the marks (`\Reworded{x}` as `x`,
  `\Struck{x}` as nothing), so writing or removing them never voids a pass or a pin.
- **What is never marked**: environment boundaries, labels, `\item`, line breaks,
  comments, list options. Display math is coloured but never struck (`soul`'s `\st` is
  text-mode only); the dry run lists what it left unmarked.
- **The checker** (only with the level): W5 warns on a stale settled claim without marks
  (it reads as settled on its current text); R8 fails marks on a claim that is not stale.
- **Opt-in**: `author.statusLevels` holds `{"name": "reworded", "kind": "mark", "command":
  "\\Reworded", "strike": "\\Struck", "colour": "violet", "requires": "stale",
  "generated": true}` (`docs/config.md`), and the preamble defines the two macros (for
  example `\Reworded` as `\textcolor` and `\Struck` as `soul`'s `\st`, both violet).
  Without the level nothing is checked and `--apply` refuses.

## The provenance marker (`author.provenance`)

Independent of the status colours, and not a status. It marks what the authors added
since the last accepted round: a new claim, an added assumption, a proof following a
lead (`kinds`). It is a margin change bar layered on top: the statement keeps its status
colour, and the checker's R1 and "exactly one status colour" are unaffected.

- **a block** → the environment (`env`, default `added`), nested *outside* the status
  environment: `\begin{added}\begin{sketch}\begin{prop}…\end{prop}\end{sketch}\end{added}`;
- **a short span** (one added hypothesis inside an existing statement) → the command
  (`command`, default `\Added`); a highlight, so never across a blank line or an `&`;
- put the kind after the opening as a tex comment, `%% added: <kind>` (never a margin
  note, R7).

A writer applies it to its own additions from a ticket, a lead or a delivered proof, and
**never removes it**: `removedBy` (default the human) removes it once the round is
accepted, and `/author:presync` lists the markers and proposes their removal. It is never
a level of `statusLevels` (nor in `envs` or `colourCommands`) and never replaces a status
colour. A home without
`author.provenance` (or with `"enabled": false`) uses no marker.
