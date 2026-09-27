---
name: referee
description: The whole-paper referee report — an agent reads the built PDF cold, as a referee who has never seen the draft, and writes Drafts/referee_report.md on unstated standing assumptions, hypotheses used but never stated, terms used before definition, notation introduced twice, results a reader one field over cannot place, and the introduction's promises versus what the body actually establishes. No edits to the tex. Use before a coauthor round, before submission, or when the paper has drifted.
---

# Referee the whole paper

Not a proof check — `proof-verifier` does that, one label at a time. This is the other
failure mode: a paper where every proof is fine and the document does not hold together.
Standing hypotheses nobody stated, a term used three pages before its definition, an
introduction promising a theorem the body only sketches.

Dispatch `referee` (`subagent_type: referee`), in the background — the cold read is the
slow part. It is **read-only on the paper**; its single output file is
`Drafts/referee_report.md`.

## The brief

> Referee this paper cold. <What changed since the last report, if there was one, and
> its date.> <Anything the author wants looked at hardest, if they said.> Do not read
> the roadmap before your cold reading.

Add nothing else — telling the referee where the weak parts are is exactly what
destroys the pass.

## Afterwards

The report separates **objective** findings from **judgement** ones. The objective list
is actionable: file it through the roadmap as `[apply]` or `[write]` items. The
judgement list goes to the author untouched — do not turn it into edits, and do not
dispatch anything against it.

Relay the overall assessment paragraph in full, the counts, and the five findings the
referee would fix first. Never ask questions.
