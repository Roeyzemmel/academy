# Draft colours and the provenance marker

The mapping between colours, registry statuses and verdict words is
`academy:status-vocabulary`; this file is how a writer applies them in the tex. The names
are the home's `author.envs`, `author.colourCommands`, `author.colours` and
`author.provenance` (`docs/config.md`).

## Status colours

Every theorem-like statement carries exactly one colour, recording how far it is
established: established (uncoloured: proved in full, or cited precisely), sketch,
conjectural, meta. Apply them through the preamble's macros, never a raw `\color`:

- **a whole statement** → the environment (`author.envs`), wrapped outside the theorem
  environment: `\begin{sketch} \begin{prop} … \end{prop} \end{sketch}`;
- **a span inside a sentence** → the command (`author.colourCommands`): `\Sketch{…}`.

The command form takes its content as a macro argument, so it **breaks on a blank line
or on an `&` inside a `tikzcd` or `align`**; the environment does not. Recolour by
renaming one word. The colours themselves are defined once, in the preamble.

A sketch becomes established only when an Expert verification (a `verify` ticket, two
agreeing verifier runs) lands. **No writing agent recolours its own work.**

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
accepted, and `/author:presync` lists the markers and proposes their removal. It never
goes in `envs` or `colourCommands` and never replaces a status colour. A home without
`author.provenance` (or with `"enabled": false`) uses no marker.
