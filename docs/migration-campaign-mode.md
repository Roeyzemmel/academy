# Migrating to campaign mode: the board as the only queue

Status: written 2026-09-30 for the branch `claude/adoring-archimedes-qzvk5s` (PR #3), which
carries the design `docs/superpowers/specs/2026-09-29-campaign-mode-design.md` and the
GitHub board of `docs/github-board.md`. Read this page before merging the PR and before
touching the live paper repo or the board.

Nothing below is run for you. Every step that changes a repo or the board is yours (the
commit rule of each home stands), and every converter here is a dry run until you pass
`--apply`.

## 1. What changes, in one page

| before | after |
|---|---|
| The Author has two queues: `Drafts/roadmap.md` (items `R-NNNN`) and the board | **The board is the only queue.** `Drafts/roadmap.md`, `R-NNNN` ids and the roadmap sync are gone |
| `/author:next` plans a batch from agenda and roadmap | `/author:inbox` takes at most 3 tickets from the board, ordered by `Drafts/agenda.md`; `/author:next` is a one-line redirect |
| Your margin notes become roadmap items | `/author:notes` files them as tickets (to the Author itself, or to the role that owns the work) |
| Agenda gaps become roadmap items | `agenda.py gaps --file` files one ticket per gap (idempotent) |
| The sweep folds answered notes into roadmap items | The sweep folds them into the thread of the ticket the note belongs to |
| Each role has its own inbox script | One shared `inbox_core` (academy lib, vendored into every plugin); each role keeps only its routing table |
| `blocked` needs only `waiting_on` | Two kinds: **pending** (`waiting_on`) and **dead route** (`blocked_by` + `reopen_if` + a `tried:` thread line); a dead route reopens only with `--reopen "<new mechanism>"` |
| Researcher: `explore` only | New opt-in `/researcher:campaign <target> --rounds N --agents M [--runs K --profile P]`; new object kind `approach` |
| The board is files | Files (still the default) **or** GitHub Issues + a Project, behind one `BoardStore` seam (`board.backend` in `workspace.json`) |

New ticket kinds: `write`, `apply`, `copy`, `sweep` (the Author's own work). New ticket
fields: `campaign`, `blocked_by`, `reopen_if`. No existing ticket needs editing: all 95
tickets of the current board validate and export with 0 drift.

## 2. Order of work

Do the parts in this order. Parts A and B are independent of GitHub and can be done the
same day; part C waits on something that is not built yet (section 7).

1. **A. Merge and update the plugins** (academy repo).
2. **B. Retire the roadmap** (the paper repo, `BilliardIllumination`).
3. **C. Move the board to GitHub** (optional, later).
4. **D. Start using campaigns** (optional, any time after A).

## 3. Part A: merge the PR and update the plugins

1. Review and merge PR #3 in `Roeyzemmel/academy`. It merges cleanly onto the main that
   already has the GitHub-board work (PR #4).
2. Update the installed plugins (`academy`, `author`, `researcher`, `expert`,
   `scientist`) in every checkout that uses them, for example by refreshing the marketplace
   copy. The plugins must all come from the same commit: each one vendors the shared
   library as `scripts/_academy.py`, and a mixed set breaks the shared inbox. In the
   academy repo a test guards this: `py academy\scripts\sync_common.py --check` must be
   silent.
3. Check each home still validates: `/academy:status` (config and `workspace.json`), then
   `/author:status`.
4. Nothing else is needed on the board. The file board keeps working exactly as before
   (`board.backend` defaults to `files`).

What to expect afterwards:

- `/author:inbox` replaces `/author:next`. The old command still answers, with a
  redirect, so habits keep working.
- `/academy:inbox` works every instance's inbox in one run, one ticket at a time, in the
  fixed order Author, Expert, Researcher, Scientist.
- An old `.claude/academy.json` that still has an `author.roadmap` path key keeps
  validating; the key is ignored. Remove it when convenient.

## 4. Part B: retire the roadmap in the paper repo

Do this in `BilliardIllumination` (author@bi) on a branch. The converter only reads
`Drafts/roadmap.md`; nothing ever writes it. The Overleaf sync is unaffected (the roadmap
is not part of `main.tex`).

### 4.1 Freeze

1. Finish or park any batch in flight: no half-run `/author:next`. Commit or stash the
   working tree of the paper repo.
2. Make sure the board repo has no uncommitted ticket changes.
3. Tell coauthors not to add roadmap items from now on (they can leave margin notes in
   the PDF as before; `/author:notes` turns them into tickets).

### 4.2 Dry run

From the paper repo root:

    py %ACADEMY_ROOT%\author\scripts\agenda_migrate.py --roadmap Drafts\roadmap.md --home .

It prints, per roadmap item, the ticket it would become, and a list of everything
**held** and every judgement call. Nothing is filed. The mapping:

| roadmap item | becomes |
|---|---|
| `done`, `dropped` | nothing (the paper and the ticket history are the record) |
| `ticketed` | nothing: it already has a ticket (named in the report; a ticket missing from the board is reported as a problem) |
| `open`, tag `write` `apply` `figure` `build` `notation` `sweep` (or a `route:` agent) | a **self-ticket** (author@bi to itself) of that kind |
| `open`, tag `lead` or `experiment` | a `research` ticket to the Expert with `final_to` (researcher / scientist) |
| `open`, tag `verify` `cite` `referee` | a ticket of that kind to the Expert |
| `needs-human`, `blocked` | a self-ticket parked `blocked` on `human` (kind `question` for an ask tag) |

Carried over: the priority, the body (prefixed by a line `roadmap item R-NNNN`, which is
the provenance and what makes the run idempotent), the agenda entry, and claim references.

Dependencies: an item that waits on another item or ticket becomes a ticket
`waiting_on` it (self-tickets), or is **held** and filed on a later run once the dependency
is met (asks that leave the Author, because the sender cannot block them). A dependency on
an agenda entry or a claim becomes a line in the ticket body, not a wait.

### 4.3 Read the report before applying

Go through the **held** list and the judgement calls. Typical holds:

- an item with an unknown tag or status (fix the item in the roadmap, or decide by hand);
- a dependency on a dropped item, a rejected or cancelled ticket, or a ticket that is not
  on the board;
- a dependency cycle.

Decide each one: file it by hand (`/academy:board`), drop it, or fix the roadmap line and
re-run the dry run. A bundled 61-item snapshot (`docs-notes/bi-agenda-preview/roadmap.md`)
plans 61 tickets with none held; the live file may differ.

### 4.4 Apply

    py %ACADEMY_ROOT%\author\scripts\agenda_migrate.py --roadmap Drafts\roadmap.md --home . --apply

Tickets are filed through `board.create_ticket` (as author@bi), in the board repo. A second
run files nothing new: an item whose ticket carries its provenance line counts as
converted, **even if that ticket was later rejected or cancelled** (then it is reported,
not re-filed). Held items are filed by a later run once their dependency is met.

Commit the new tickets in the board repo (on the session branch, `cloud/<date>`, in a cloud
session; Roey reviews and merges as usual).

### 4.5 Retire the file

1. `git mv Drafts/roadmap.md Drafts/archive/roadmap-2026-09-30.md` (keep it: the provenance
   lines point at its item ids).
2. Remove `"roadmap": "Drafts/roadmap.md"` from `.claude/academy.json` (optional, it is
   ignored).
3. Search the paper repo for leftovers that point at nothing: `R-0` (old item ids in
   prose or margin notes), `/author:next`, `roadmap`. Replace item ids by the ticket ids
   the converter printed (each ticket's body names its item).
4. Regenerate the agenda view: `/author:agenda`, then `/author:status`.

### 4.6 Check

- `py %ACADEMY_ROOT%\author\scripts\agenda.py check --home .` : 0 problems. It now also
  rejects **two agenda entries sharing one claim**; if your agenda legitimately does that,
  the check reports it and you decide (split the claim or merge the entries).
- `py %ACADEMY_ROOT%\author\scripts\agenda.py gaps --home .` (without `--file`): lists
  the gaps with no ticket. Running it with `--file` files them, one ticket per entry, and
  filing the same gap twice gives one ticket.
- `/author:inbox --all` lists the Author's tickets without taking any; `/author:inbox`
  takes the first three.

### 4.7 If it goes wrong

The converter never modifies the roadmap, the agenda or the tex. To undo: cancel the
filed tickets (`/academy:board`, reason: "migration redone") and restore the archived
roadmap. Note that a cancelled converted ticket counts as converted and is **not** re-filed
by a later run (it is reported instead), so a redo means filing those items by hand.

## 5. Part D: using campaigns

Not a migration step; here so the rules are in one place.

    /researcher:campaign <target> --rounds N --agents M [--runs K --profile P]

- `--rounds` and `--agents` are required. `--runs` (lab runs, 0 if omitted) needs `--profile`.
  `K` is forced to 0 in a cloud session (the workspace rule against heavy environments).
- The caps, what is suspended inside a campaign (budget rules 1 and 3, never 2) and the
  serial dispatch rule live once, in `academy/references/budget.md` ("Campaigns").
  Dispatch mechanics: `researcher/references/campaign-dispatch.md`.
- A campaign needs at least four approaches aimed at the target, each with a direction:
  `notebook.py approach check --campaign <target>`.
- Approaches (`objects/approach/`) carry all campaign state; a campaign resumes from the
  notebook and the board. `notebook.py approach status` shows which approaches wait on a
  decision and whether the campaign must pause.
- A campaign never records your decisions. Anything that needs you is a ticket blocked on
  `human`; `/academy:decide` is where you answer.
- Blocking an approach moves its open tickets to dead-route blocked with the same
  `blocked_by`: `--apply` does it for tickets addressed to the Researcher's own instance;
  for other roles it prints the `board.py transition ... --as <receiver>` commands, because
  only a ticket's receiver or you may block it. Reopening the approach prints or applies the
  matching `--reopen` moves.
- Check spend with `/academy:usage`; `--agents`, each ticket's `budget.runs` and a limit
  error are the only brakes, and the driver (the main session) enforces them.

## 6. Part C: moving the board to GitHub

Read `docs/github-board.md` (mapping, permissions, rules on each side) and run
`/academy:board-migrate preflight`, then `export`, `run` (rehearsal in a scratch repo
first), `verify`, `cutover`. Before you do:

1. **Export once more and compare.** `board_export.py --board <board> --summary` must show
   no `problems` and `board_verify.py` 0 drift (today: 95 tickets, 0 problems, 0 drift). A
   manifest exported before this PR used other names for the dependency fields
   (`blocked_by` for native dependencies); re-export, never reuse an old manifest.
2. **What GitHub gets that files do not:** a `route:dead` label on dead-route tickets, a
   Project **Block** field (`pending` or `dead-route`), Kind options for `write` `apply`
   `copy` `sweep` (`board_project.py` holds the declared field spec; `--check` proves it
   covers every kind and status). The `board-sync` workflow enforces the rules it can
   (one label of each kind, role derived from `to`, state follows status, dead-route
   reopening needs a `reopened:` thread entry, trusted state comment only from the
   workflow bot). Limits, stated plainly: GitHub has one account identity, so `board-sync`
   cannot tell who moved a status; a forged `reopened:` comment with a valid speaker name
   still passes. Set `ACADEMY_HUMAN_LOGINS` in the workflow to your login so a human move out
   of a dead route is not flagged.
3. **Cutover switch.** `workspace.json`:

       "board": {"path": "<board dir>", "backend": "github",
                 "repo": "<owner>/<name>", "transport": "<module>:<factory>"}

   A plain string (`"board": "<dir>"`) stays the file board. A `github` backend without a
   transport fails with an error and never falls back to files.
4. **State (2026-10-01).** The REST transport is built: `academy/lib/board_gh.py`
   (`"transport": "board_gh:transport"`, through an authenticated `gh` on the machine).
   The board was pushed to `Roeyzemmel/BilliardIlluminationWorkspace` (106 tickets, 0 drift,
   round trip to files exact), the GitHub store reads it identical to the files, and a full
   ticket lifecycle (new, accept, append, in-progress, deliver, close) ran live through
   `board.py` on the scratch repo. Still not built: the Project half of `board-sync`
   (writing Project fields to a live Project; the Project itself needs a token with the
   `project` scope).

## 7. Open items and risks

| item | state |
|---|---|
| Real GitHub transport (MCP/REST) for `GithubBoardStore` | not built; blocks part C |
| Project fields written to a live Project | spec only (`board_project.py`) |
| Campaign caps (`--rounds`, `--agents`, `--runs`, cloud, pause) | enforced by the driver in prose; `notebook.py campaign-check` validates them, nothing counts spend |
| Dispatching a role's ticket route as a subagent from the main session | assumed, never exercised on a real Scientist or Expert ticket (spec open risk (a)) |
| Forged `reopened:` comment on GitHub | passes `board-sync` (one account identity); documented |
| Four tests fail on this branch and on main | `test_fsq_sh_behaviour`, `test_powershell_set_location` (scientist), `test_matches_golden_modulo_r7`, `test_powershell_set_location_and_call_operator` (author): Windows and golden environment tests, unrelated to this work |
| The PR description of #3 | still describes the first three commits; rewrite before merge |

## 8. Checklist

- [ ] PR #3 reviewed and merged; plugins updated everywhere, from one commit.
- [ ] `/academy:status` clean in each home.
- [ ] Paper repo: branch; frozen; dry run read; held items decided.
- [ ] `agenda_migrate.py --apply` run; tickets committed in the board repo.
- [ ] `Drafts/roadmap.md` archived; `roadmap` key dropped; `R-NNNN` leftovers replaced.
- [ ] `agenda.py check` 0 problems; `/author:inbox --all` shows the expected tickets.
- [ ] (later) GitHub: transport built, rehearsal verified, `ACADEMY_HUMAN_LOGINS` set, cutover.
