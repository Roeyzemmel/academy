# The review packet

Plan section 7. One template for every role: `academy/templates/packet.md`.

A packet is how finished work comes back to Roey for a decision or an
acknowledgement. `/academy:review` renders all open packets into one HTML dashboard.
It then asks each pending decision with `AskUserQuestion`, and a script writes the
answers back (section 4).

## 1. Location and id

- A packet lives at `board/packets/<instance>/P-NNNN-<slug>.md`, where `<instance>`
  is the instance that produced it.
- The id comes from `allocate_id(board, "packet")`, under the same lock as tickets.
- The file name follows the ticket rules (`packet_filename`, slug default `packet`)
  and never changes.
- An experiment report is a packet of kind `experiment-report`. Its body adds the
  Scientist report sections, including `## Conclusion` (section 3).

## 2. Frontmatter

The keys are written in this order. No other keys are allowed.

| Key | Type | Req. | Meaning |
|---|---|---|---|
| `packet` | `P-NNNN` | yes | The id; equals the filename prefix |
| `title` | str, one line | yes | Dashboard heading |
| `instance` | instance | yes | The producing instance, which is also the folder |
| `kind` | enum, below | yes | What is being reviewed |
| `by` | speaker (`<instance>/<agent>` or `human`) | yes | Who assembled the packet; for a hook-landed grader output, the grader |
| `ticket` | `T-NNNN` \| empty | no | The ticket this packet answers; the decision is echoed into its thread |
| `agenda` | claim id \| `global` \| empty | no | The Author agenda entry concerned |
| `subject` | list of refs | yes (may be `[]`) | The objects under review, in the ref forms of protocol.md section 3 |
| `status_before` | status \| empty | no | The subject's registry status now (one status vocabulary) |
| `status_proposed` | status \| empty | no | The status the producers propose; `status_before -> status_proposed` on the dashboard |
| `state` | `open` \| `decided` \| `withdrawn` | yes | `decided` once every decision has a line in `## Decision` |
| `created` | `YYYY-MM-DD` | yes | |
| `decided` | `YYYY-MM-DD` \| empty | no | Set when `state` becomes `decided` |

When `subject` names more than one object with different statuses, both status
fields stay empty and the statuses are given in `## Established vs assumed`.

The statuses are those of the unified registry: `open`, `conjectured`, `sketch`,
`supported`, `proved-modulo`, `proved`, `refuted`, `refuted-as-stated`.

**`kind`** is one of the following:

| kind | Produced by |
|---|---|
| `verification` | review-chair (from the rigor-reviewer pair) |
| `citation` | librarian |
| `referee` | referee, landed by hook |
| `experiment-report` | experimenter, via the report generator |
| `experiment-review` | claim-keeper / lead-researcher (from the experiment-reviewer pair) |
| `generalization` | prover / lead-researcher (`/researcher:generalize`) |
| `proof` | prover |
| `notation` | notation-auditor / librarian |
| `agenda` | Author orchestration (`/author:inbox` batch results) |
| `migration` | migration builders (schema v2, roadmap → agenda, ledgers) |
| `handover` | end of the unattended run, one per home |
| `usage` | usage-analyst |
| `failure` | a failed phase gate or run |
| `other` | anything else |

## 3. Body sections

The sections are exact `##` headings, in this order. The first six are required at
creation, and `## Decision` must exist and be empty at creation. A kind may add
sections, but only **between `## Evidence` and `## Decisions needed`** (for example
the report's `## Question`, `## Class`, `## Method`, `## Environment`,
`## Validation`, `## Raw outcome`, `## Conclusion`).

1. `## Summary`: at most three non-blank lines.
2. `## Produced`: bullets, each with a ref.
3. `## Established vs assumed`: bullets beginning **Established:**, **Assumed:** or
   **Not established:**. Every statement named carries its status. A sketch is never
   presented as established.
4. `## Evidence`: bullets, each with a ref (verdict, run id, commit, quote).
5. `## Decisions needed`: either the single line `None.` (an informational packet),
   or one or more decisions in this exact shape:

   ```markdown
   ### D1. <question ending in ?>

   - (a) <option>
   - (b) <option>
   - Recommendation: (<letter>), <why>
   ```

   - Decisions are numbered `D1`, `D2`, … with no gaps.
   - Each decision has 2–4 options lettered `(a)`–`(d)` and exactly one
     `Recommendation:` line.
   - Roey may always answer `other` with free text, so an "other" option is never
     listed.
6. `## Machine notes`: one bullet per judgement call, naming the agent. It is
   `None.` if there were none.
7. `## Decision`: the write-back section. It is empty at creation.

## 4. The `## Decision` write-back format

There is one line per answered decision, appended in answer order:

```
- D<k>: (<letter>) | <YYYY-MM-DD> | <speaker> | <optional note>
- D<k>: other | <YYYY-MM-DD> | <speaker> | <free text, required>
```

- Informational packet (`None.` above): the acknowledgement is the single line
  `- D0: ack | <YYYY-MM-DD> | human`.
- Regex:
  `^- D(\d+): (\([a-d]\)|other|ack) \| (\d{4}-\d{2}-\d{2}) \| ([^\s|]+)(?: \| (.*))?$`.
- **Only the human decides.** `<speaker>` is `human`. `packets_decide` is
  human-only.
- **Editing by hand.** Roey may also write these lines by hand in VS Code; they count
  the same way.
- **Last line wins.** A later line for the same `D<k>` supersedes an earlier one.
  Lines are never deleted.
- **When every `D<k>` has a line** (or the `D0` line is present), the writer sets
  `state: decided` and `decided: <date>`.
- **Echo into the ticket.** For each decision written, if `ticket` is set, one
  thread line is appended to that ticket:
  `- <date> human: decision on P-NNNN D<k>: (<letter>) <option text>`. For `other`,
  the free text replaces `(<letter>) <option text>`.
- **What happens next** is the ticket owner's work, picked up by its next inbox
  run. Writing the decision starts nothing.

## 5. Example

```markdown
---
packet: P-0012
title: Verification of paper:lem:strip-bound
instance: expert@main
kind: verification
by: expert@main/review-chair
ticket: T-0007
agenda: paper:thm:main
subject: [paper:lem:strip-bound]
status_before: sketch
status_proposed: proved
state: open
created: 2026-09-28
decided:
---

## Summary

Two independent rigor-reviewer runs both CONFIRMED the strip bound.
Recolouring to black is proposed; one cited hypothesis needs Roey's word.

## Produced

- Verdict records A and B: `file:expert@main/reviews/paper/lem-strip-bound/`.

## Established vs assumed

- **Established:** paper:lem:strip-bound (proposed proved; two CONFIRMED, distinct run ids).
- **Assumed:** bib:LMW16#Thm1.3 applies to the non-Veech case (quote verified).
- **Not established:** that Theorem 1.3 needs the lemma at all.

## Evidence

- Run A `rv-20260928-1`, run B `rv-20260928-2`, statement hash `9f2c...`.

## Decisions needed

### D1. Recolour lem:strip-bound to established now?

- (a) Yes, recolour now.
- (b) Wait until Theorem 1.3's dependence is checked.
- Recommendation: (a), both runs agree and the dependence question is separate.

## Machine notes

- review-chair: treated run B's minor remark on notation as non-blocking.

## Decision

- D1: (a) | 2026-09-28 | human | recolour, then open a ticket on Thm 1.3's dependence
```
