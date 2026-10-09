# The board

This folder is where the academy instances talk to each other and to you. Every
request between instances is a **ticket**, and every piece of finished work that
comes back for your decision is a **packet**. Both are plain Markdown files, so you
can read and edit them in any editor. Git keeps the history. (With `board.backend`
`github` in `workspace.json` the tickets are GitHub issues instead, read and written by
the same tools; packets and deep-dives stay files here.)

The full contract is `$ACADEMY_ROOT/docs/protocol.md` (tickets) and
`$ACADEMY_ROOT/docs/packet-template.md` (packets). This page is the short version.
It was written by `/academy:init` (`academy/templates/board/README.md`); the folder
list below is regenerated each time an instance is added.

## Where things are

<!-- academy:folders -->
{{folder_table}}
<!-- /academy:folders -->

A ticket is `T-NNNN-<slug>.md` and a packet is `P-NNNN-<slug>.md`. The number is the
id. The slug comes from the title at creation and never changes. Look things up by
id: `T-0007`, not by the name.

## Reading a ticket

The top block (between the `---` lines) is the ticket's state:

- `from` / `to`: who asked, who is asked.
- `status`: `open -> accepted -> in-progress -> delivered -> closed`, with the side
  exits `rejected`, `cancelled` and `blocked` (then `waiting_on` says on what).
- `ask` and `deliverable`: the request and what "done" means, one line each.
- `result`: the answer in one line, once delivered.
- `budget`: how many agent runs it may spend and the heaviest model it may use.

Below it come `## Ask` (the detail of the request), `## Result` (the detail of the
answer) and `## Thread`, the conversation. The thread is append-only: one line per
entry, `- YYYY-MM-DD <speaker>: <text>`, where the speaker is `human`, an instance
such as `expert@lib`, or an agent such as `expert@lib/review-chair`.

## Editing a ticket

You may edit anything. The usual edits:

- **Reply:** add a line at the end of `## Thread`, e.g.
  `- 2026-09-28 human: yes, use the simplest example as the validation case`.
  Never change or delete an existing thread line.
- **Change status:** edit `status:` and add a thread line
  `- <date> human: status open -> cancelled: no longer needed`.
- **Re-route:** change `to:`. Tools move the file to the new folder.

Or use the script, which does the bookkeeping for you:

```
py $ACADEMY_ROOT/academy/scripts/board.py list --to human
py $ACADEMY_ROOT/academy/scripts/board.py show T-0007
py $ACADEMY_ROOT/academy/scripts/board.py append T-0007 --text "go ahead"
py $ACADEMY_ROOT/academy/scripts/board.py transition T-0007 cancelled --reason "superseded by T-0009"
py $ACADEMY_ROOT/academy/scripts/board.py new --to expert@lib --title "What does Theorem 1.3 of XY20 assume" --ask "..." --deliverable "..."
```

Nothing runs by itself. A ticket is picked up only when its receiver's
`/<role>:inbox` is run, at most three at a time.

## Reading a packet

A packet has fixed sections: `## Summary`, `## Produced`,
`## Established vs assumed`, `## Evidence`, `## Decisions needed`, `## Machine notes`
and `## Decision`. "Established vs assumed" is where a sketch is kept apart from a
proof: every statement named there carries its status.

The easiest way to read all open packets at once is the dashboard:

```
py $ACADEMY_ROOT/academy/scripts/render_packets.py
```

which writes `.render/review.html` (open it in a browser; `/academy:review` also
publishes it as a private artifact).

## Deciding

Each question in `## Decisions needed` is `D1`, `D2`, ... with options `(a)`-`(d)`
and a recommendation. Answer in `/academy:review`, with the script

```
py $ACADEMY_ROOT/academy/scripts/packets.py decide P-0012 --decision 1 --choice a --comment "recolour, then check Thm 1.3"
```

or by hand, by adding a line under `## Decision`:

```
- D1: (a) | 2026-09-28 | human | recolour, then check Thm 1.3
- D2: other | 2026-09-28 | human | neither; ask the referee first
```

An informational packet (`None.` under Decisions needed) is acknowledged with
`- D0: ack | <date> | human`. A later line for the same `D<k>` replaces an earlier
one. The script also sets `state: decided` once every decision is answered, and
copies each answer into the packet's ticket thread. Writing a decision starts
nothing; the ticket's owner acts on it at its next inbox run.

## Committing

Tools write files but never commit. `session_start` and `/academy:board sync`
commit the pending board changes as `board: <n> change(s)`. Nothing here is ever
pushed.
