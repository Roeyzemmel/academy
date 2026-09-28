---
name: status
description: The state of this Researcher instance at a glance — notebook objects by kind and status, proof attempts and their latest outcome, experiment reviews waiting for run B, the inbox, and the registry check. Read-only. Use for "/researcher:status", "where is the notebook", "what is open in this direction", before an inbox run, and after a switch-over. For the academy as a whole use /academy:status.
---

# Researcher status

Scripts: `$R`, `$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Read-only:
this skill fixes nothing.

1. `py $R/notebook.py status`: objects by kind and status, proof attempts with their
   latest outcome, reviews waiting for run B.
2. `py $R/inbox.py --all`: the tickets addressed to this instance that are not closed.
3. `py $A/packets.py list --open --instance <instance>`: packets this instance produced
   that await Roey.
4. `claims_check {ns}` on this instance's namespace: registry errors.
5. Show the outputs as they are, then at most three lines naming what needs attention
   first (a review waiting for run B, a blocked ticket, a check error), each with the
   skill that handles it. Do not reconstruct a status from prose; quote the registry.
