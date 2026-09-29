---
name: prove
description: 'Take one notebook claim to a reviewable proof: prover writes the next attempt under proofs/<id>/, and a complete attempt becomes a verify ticket to the Expert. Never sets a status. Use for "/researcher:prove <claim>" and on prove tickets.'
---

# Prove a claim

`$ARGUMENTS` is a claim id (`<ns>:<id>`) or a `prove` ticket. Scripts: `$R`, `$A` as
in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget: `academy/references/budget.md`;
independence: `academy/references/roster-rules.md` (the producer never grades its own
work).

1. **State of play.** `claims_show` on the claim (status, `depends_on`, `modulo`) and
   `py $R/notebook.py ls` / the object's `proof:` field for earlier attempts. A claim
   already `proved` needs nothing; a claim resting on an unsettled input can be proved
   at most `proved-modulo` that input — say so in the brief. On a ticket: move it
   `accepted`, then `in-progress` (`$A/board.py transition ... --as <instance>`).
2. **Falsified yet?** A claim nobody tried to break goes first to `/researcher:explore`
   (its falsifier), unless the ticket says the falsifier already ran; name the ticket
   or report that settled it.
3. **One `prover`**, on its primary model, briefed with the claim id and the attempt
   path from `py $R/notebook.py attempt <id> --create`. It scouts prior art first
   (cite before reproving), then writes the attempt: statement as attempted, strategy,
   proof, inputs with their statuses, gaps. A repair of an earlier attempt is a new
   attempt; the old one stays.
4. **Read the outcome** from the attempt's frontmatter (`outcome:`), not from the
   agent's summary:
   - `complete` (no gaps): file the review. One `verify` ticket to the Expert instance
     (`reviewsHome` in the config): `py $A/board.py new --to <expert instance> --kind
     verify --title "Verify <id>" --ask "Review <id>: is the argument in <attempt path>
     valid from its stated inputs?" --deliverable "A verification packet with two
     verdicts, or one negative verdict." --refs <id>,file:<instance>/<attempt path>
     --as <instance> [--parent T-NNNN]`. The claim stays `sketch` until claim-keeper
     acts on the packet.
   - `failed` or gaps left: nothing is filed. Record the gap in the journal; a gap
     that is a separate lemma becomes its own object (`claims_new`, `open`) with a
     `prove` ticket to this instance.
5. **Status.** Propose `sketch` for a claim that was `open` and now has a complete
   attempt (`claims_propose_status`, grounds: the note "complete attempt <path>").
   Nothing higher: `proved` and `proved-modulo` come only from two agreeing Expert
   reviews, through claim-keeper.
6. **Report**: the attempt path and outcome, each gap, the inputs and their statuses,
   the ticket filed, and the status proposed. On a ticket, deliver it with the verify
   ticket's id as the result.
