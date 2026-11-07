export const meta = {
  name: 'academy-weekly',
  description: 'The weekly usage packet and error-ledger settle: gather the numbers, keep the allowed proposals, write and file one usage packet, settle only once it is filed',
  whenToUse: '/academy:usage --weekly (also unattended, from a scheduled task). args: {instance: "<the cwd home\'s instance>", days?: 7, start?: "YYYY-MM-DD", end?: "YYYY-MM-DD"}',
  phases: [
    { title: 'Gather', detail: 'usage_report.py and error_ledger.py report, as JSON' },
    { title: 'Write', detail: 'the packet body from the kept proposals, filed with packets.py' },
    { title: 'Settle', detail: 'error_ledger.py settle --packet, only after the packet exists' },
  ],
}

// The weekly cycle of /academy:usage --weekly in code (the human's decision, 2026-10-31;
// docs/workflows.md): the usage-analyst gathers and proposes, the script keeps only the
// proposals the rules allow (never a grader's downgrade; a downgrade is a tier, never a
// model name; at most three decisions, regressions first), the analyst writes and files
// exactly those, and error_ledger.py settle runs only after the packet is shown to exist.
// Nothing is resolved by hand here (that is the human's word), and nothing asks a question:
// the job may run unattended.

const A = args || {}
if (!A.instance || !/^[a-z]+@[a-z0-9][a-z0-9-]*$/.test(A.instance)) {
  return { filed: false, reason: 'no instance: from outside any home, print the report (usage_report.py) and file no packet' }
}
const DAYS = A.days || 7
const ANALYST = 'academy:usage-analyst'
const GRADERS = ['rigor-reviewer', 'experiment-reviewer', 'referee']
const TIERS = ['base', 'medium', 'large', 'max']
const STAGE = (name, lines) => `WORKFLOW STAGE ${name} of the academy-weekly workflow. Instance: ${A.instance}. Window: --days ${DAYS}.\n` + lines.filter(Boolean).join('\n')

const PROPOSAL = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: ['downgrade', 'budget', 'error-family'] },
    agent: { type: 'string', description: 'downgrade: the bare or namespaced agent' },
    from_tier: { type: 'string' }, to_tier: { type: 'string' },
    family: { type: 'string', description: 'error-family: the family label' },
    state: { type: 'string', description: 'error-family: regression / recurring / new' },
    question: { type: 'string' }, options: { type: 'array', items: { type: 'string' } },
    recommendation: { type: 'string' }, evidence: { type: 'string' },
  },
  required: ['kind', 'question', 'options', 'recommendation', 'evidence'],
}
const DATA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' }, error: { type: 'string', description: 'a script\'s error line, if one failed' },
    start: { type: 'string' }, end: { type: 'string' },
    summary: { type: 'string', description: 'at most three lines' },
    open_classes: { type: 'number' }, regressions: { type: 'array', items: { type: 'string' } },
    limit_failures: { type: 'number' },
    proposals: { type: 'array', items: PROPOSAL },
  },
  required: ['ok', 'error', 'start', 'end', 'summary', 'open_classes', 'regressions', 'limit_failures', 'proposals'],
}
const FILED = { type: 'object', properties: { ok: { type: 'boolean' }, packet: { type: 'string' }, error: { type: 'string' } }, required: ['ok', 'packet', 'error'] }
const SETTLED = { type: 'object', properties: { ok: { type: 'boolean' }, closed: { type: 'number' }, detail: { type: 'string' } }, required: ['ok', 'closed', 'detail'] }

const out = { instance: A.instance, filed: false, settled: false, dropped: [] }

// ---- Gather -------------------------------------------------------------------------
phase('Gather')
const d = await agent(STAGE('data', [
  `Run usage_report.py --days ${DAYS} --json and error_ledger.py report --days ${DAYS} --json (your step 1), read them,`,
  'and return the window, a summary of at most three lines, the counts, the regression families,',
  'and your proposals: downgrades (an agent whose runs are short and clerical on a heavier tier), budget changes,',
  'and recurring error families worth deciding on, each with 2-4 options and a recommendation. Write nothing.',
]), { label: 'gather', phase: 'Gather', agentType: ANALYST, schema: DATA, effort: 'low' })
if (!d) return Object.assign(out, { reason: 'the gather stage returned nothing (a limit?): nothing filed, nothing settled' })
if (!d.ok) return Object.assign(out, { reason: 'a script failed: ' + d.error })

// ---- the rules, in code -------------------------------------------------------------
const bare = (a) => String(a || '').split(':').pop()
const kept = []
for (const p of d.proposals || []) {
  if (p.kind === 'downgrade') {
    if (GRADERS.includes(bare(p.agent))) { out.dropped.push(`downgrade of the grader ${p.agent} (never proposed)`); continue }
    const f = TIERS.indexOf(p.from_tier), t = TIERS.indexOf(p.to_tier)
    if (f < 0 || t < 0 || t >= f) { out.dropped.push(`downgrade of ${p.agent}: ${p.from_tier} -> ${p.to_tier} is not a lower tier`); continue }
  }
  if (!Array.isArray(p.options) || p.options.length < 2 || p.options.length > 4) { out.dropped.push(`"${p.question}": needs 2-4 options`); continue }
  kept.push(p)
}
// regressions first, then recurring error families, then the rest; at most three
const rank = (p) => p.kind === 'error-family' ? (p.state === 'regression' ? 0 : p.state === 'recurring' ? 1 : 3) : 2
kept.sort((a, b) => rank(a) - rank(b))
const decisions = kept.slice(0, 3)
for (const p of kept.slice(3)) out.dropped.push(`over the cap of three: "${p.question}"`)
out.decisions = decisions

// ---- Write and file -------------------------------------------------------------------
phase('Write')
const start = A.start || d.start, end = A.end || d.end
const f = await agent(STAGE('write', [
  `Write the packet body (your step 2) to <board>/.render/usage-body.md and file it (your step 3) with --title "Usage ${start}..${end}".`,
  `## Summary: ${d.summary}`,
  `## Decisions needed: exactly these ${decisions.length} decision(s), in this order, as ### D1.., each with its options and the Recommendation line; ` +
    (decisions.length ? JSON.stringify(decisions) : 'None.'),
  out.dropped.length ? `## Machine notes: add one bullet "usage-analyst: the workflow dropped ${out.dropped.length} proposal(s): ${out.dropped.join('; ')}".` : '',
  'Return the packet id (P-NNNN) the filing printed, or ok false with its error line. Do not settle: the workflow does.',
]), { label: 'write and file', phase: 'Write', agentType: ANALYST, schema: FILED })
if (!f) return Object.assign(out, { reason: 'the write stage returned nothing: nothing settled' })
if (!f.ok || !/^P-\d{4,}$/.test(f.packet)) return Object.assign(out, { reason: 'the packet was not filed: ' + (f.error || JSON.stringify(f.packet)) + '; nothing settled' })
out.filed = true
out.packet = f.packet
log(`filed ${f.packet}`)

// ---- Settle, only after the packet is shown to exist ------------------------------------
phase('Settle')
const s = await agent(STAGE('settle', [
  `First run packets.py show ${f.packet}: if it does not show the packet, return ok false and run nothing else.`,
  `Then error_ledger.py settle --packet ${f.packet} (your step 4) and return how many classes it closed. Resolve nothing by hand.`,
]), { label: 'settle', phase: 'Settle', agentType: ANALYST, schema: SETTLED, effort: 'low' })
out.settled = !!(s && s.ok)
out.closed = s ? s.closed : 0
if (!out.settled) out.reason = 'the packet is filed but the settle did not run: ' + (s ? s.detail : 'the stage returned nothing') + ' (run error_ledger.py settle --packet ' + f.packet + ' by hand)'
out.summary = d.summary
return out
