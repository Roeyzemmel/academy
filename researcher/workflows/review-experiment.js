export const meta = {
  name: 'academy-review-experiment',
  description: 'Experiment review of one lab claim: experiment-reviewer A, B only when reviews.py decide says need-B, claim-keeper only on a clean clear; settle modes add the candidates plan and decision',
  whenToUse: 'Every review-experiment ticket, /researcher:review-experiment and /researcher:settle, from the Researcher home. args: {subject: "lab:<id>", ticket?, report?: "P-NNNN", result?, mode?: "review"|"settle-audit"|"settle-conclude", candidates?: <file>, verdicts?: [...]}',
  phases: [
    { title: 'Prepare', detail: 'take the ticket, where the pair stands' },
    { title: 'Review', detail: 'run A; run B only on need-B' },
    { title: 'Record', detail: 'claim-keeper, packet, settle plan or decision, the ticket' },
  ],
}

// The sequencing of /researcher:review-experiment and /researcher:settle, in code (the
// 2026-10-31 decision; docs/workflows.md). reviews.py decide is the table and the only
// thing the script branches on; the brief is reviews.py brief's text, built here byte
// for byte (a test pins it), so run B's brief carries nothing of A; a run that did not
// land is relaunched once; a lost run stops the pass; claim-keeper gets the decide
// grounds only on a clear without grounds problems; settle candidates are planned only
// after the audit cleared, and their tickets are returned for the main session to file
// (main is the liaison toward the Scientist and the Expert; the clerk files nothing).
// Runs are landed by the land_review hook, which fires for workflow agents.

const A = args || {}
if (!A.subject || !/^[a-z][a-z0-9]*:\S+$/.test(A.subject)) {
  throw new Error('args.subject must be a namespaced lab claim id (lab:<id>), got ' + JSON.stringify(A.subject))
}
const MODE = ['review', 'settle-audit', 'settle-conclude'].includes(A.mode) ? A.mode : 'review'
if (MODE !== 'review' && !A.candidates) throw new Error('settle modes need args.candidates (the candidates file path)')
const CLERK = 'researcher:review-clerk'
const REVIEWER = 'researcher:experiment-reviewer'
const KEEPER = 'researcher:claim-keeper'
const CLEARED = ['cleared', 'cleared-modulo']

const DECIDE = {
  type: 'object',
  properties: {
    state: { type: 'string', description: 'reviews.py decide state, verbatim' },
    next: { type: 'string' },
    verdicts: { type: 'array', items: { type: 'string' } },
    proposed_status: { type: ['string', 'null'] },
    grounds: { type: ['object', 'null'], description: 'the grounds object, verbatim from decide --json' },
    grounds_problems: { type: 'array', items: { type: 'string' } },
    reasons: { type: 'array', items: { type: 'string' } },
    reproduction: { type: 'string', description: 'a reproduction request a landed run made (another profile), or empty' },
  },
  required: ['state', 'next', 'verdicts', 'proposed_status', 'grounds', 'grounds_problems', 'reasons', 'reproduction'],
}
const PREP = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    stop_reason: { type: 'string' },
    report: { type: 'string', description: 'the report packet id, or empty' },
    result: { type: 'string', description: 'the result file, or empty' },
    has_candidates: { type: 'boolean', description: 'the report lists candidate counterexamples' },
    decide: DECIDE,
  },
  required: ['ok', 'stop_reason', 'report', 'result', 'has_candidates', 'decide'],
}
const PLAN = {
  type: 'object',
  properties: {
    audit: { type: 'string' },
    file_now: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, rank: { type: 'number' }, ref: { type: 'string' }, detail: { type: 'string' } }, required: ['name', 'ref', 'detail'] } },
    waiting: { type: 'array', items: { type: 'string' } },
    deferred: { type: 'array', items: { type: 'string' } },
    notes: { type: 'array', items: { type: 'string' } },
  },
  required: ['audit', 'file_now', 'waiting', 'deferred', 'notes'],
}
const SETTLED = {
  type: 'object',
  properties: {
    recordable: { type: 'array', items: { type: 'string' } },
    rows: { type: 'array', items: { type: 'object' } },
    record: { type: 'string', description: 'the decision record written by settle.py record' },
    note: { type: 'string' },
  },
  required: ['recordable', 'rows', 'record', 'note'],
}
const DONE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok', 'detail'] }

const STAGE = (name, lines) =>
  `WORKFLOW STAGE ${name} of the academy-review-experiment workflow. Subject: ${A.subject}.\n` +
  lines.filter(Boolean).join('\n')
const clerk = (name, lines, schema, phase) =>
  agent(STAGE(name, lines), { label: name, phase, agentType: CLERK, schema, effort: 'low' })

// reviews.py brief, byte for byte (tests/test_review_experiment_workflow.py pins it)
function brief(run, result, ticket, report) {
  const lines = [
    `Review one computed result. You are run ${run} of an experiment-review pair; another ` +
    `run may exist, and you must not look for it or account for it.`,
    `Subject: ${A.subject}.`,
  ]
  if (result) lines.push(`Result: ${result}.`)
  if (report) lines.push(`Experiment report packet: ${report} (read it with packets_get).`)
  if (ticket) lines.push(`Ticket: ${ticket}.`)
  lines.push(`Follow your agent definition and the checklist ` +
    `skills/review-experiment/checklist.md. End with the '## Review record' ` +
    `block, Run: ${run}.`)
  return lines.join('\n')
}

const notes = []
const out = { subject: A.subject, mode: MODE, notes, runs: [], to_file: [] }

// ---- Prepare -----------------------------------------------------------------
phase('Prepare')
const prep = await clerk(MODE === 'settle-conclude' ? 'decide' : 'prepare', [
  A.ticket ? `ticket: ${A.ticket}` : 'ticket: none',
  A.report ? `report: ${A.report}` : '',
  MODE === 'settle-conclude'
    ? 'Return reviews.py decide <subject> --json parsed, as prepare would (ok true, has_candidates true).'
    : 'Take the ticket (open -> accepted -> in-progress), find the report packet and the result, say whether the report lists candidate counterexamples, and return reviews.py decide <subject> --json parsed.',
], PREP, 'Prepare')
if (!prep || !prep.ok) {
  log('not started: ' + (prep ? prep.stop_reason : 'prepare returned nothing'))
  return Object.assign(out, { outcome: 'not-started', reason: prep ? prep.stop_reason : 'prepare lost' })
}
if (MODE === 'review' && prep.has_candidates) {
  notes.push('the report lists candidate counterexamples: run this workflow in settle-audit mode instead (/researcher:settle)')
  return Object.assign(out, { outcome: 'needs-settle' })
}
const report = A.report || prep.report || ''
const result = A.result || prep.result || ''
let d = prep.decide

// ---- Review: the table says which run; one relaunch for a run that did not land ----
phase('Review')
if (MODE !== 'settle-conclude') {
  const tried = {}
  while (d && (d.state === 'need-A' || d.state === 'need-B')) {
    const run = d.state === 'need-A' ? 'A' : 'B'
    tried[run] = (tried[run] || 0) + 1
    if (tried[run] > 2) { notes.push(`run ${run} did not land twice; the pass stops here`); break }
    const text = await agent(brief(run, result, A.ticket, report), {
      label: `run ${run}${tried[run] > 1 ? ' (relaunch)' : ''}`, phase: 'Review', agentType: REVIEWER })
    if (text === null) { notes.push(`run ${run} lost (no result: a limit or an API error); nothing further launched`); out.runs.push({ run, lost: true }); break }
    const before = d.state
    d = await clerk('decide', ['Return reviews.py decide <subject> --json parsed. Write nothing.'], DECIDE, 'Review')
    if (!d) { notes.push('the decide stage returned nothing'); break }
    if (d.state === before) { notes.push(`run ${run} attempt ${tried[run]} did not land a review record`); continue }
    if (tried[run] > 1) notes.push(`run ${run}: the kept run is the relaunch`)
    out.runs.push({ run, landed: true })
    if (run === 'A' && d.state !== 'need-B') notes.push(`run B skipped by design: the table on A says ${d.state}`)
  }
}
out.state = d ? d.state : 'unknown'
out.decide = d
log(`audit ${out.state}`)

// ---- Record --------------------------------------------------------------------
phase('Record')
const cleanClear = d && CLEARED.includes(d.state) && d.grounds && !(d.grounds_problems || []).length && d.proposed_status
if (d && !['need-A', 'need-B'].includes(d.state) && MODE !== 'settle-conclude') {
  if (cleanClear) {
    out.keeper = await agent(
      `Set the status of ${A.subject} to ${d.proposed_status} with claims_set_status, grounds exactly as given ` +
      `(from reviews.py decide; the server re-checks them):\n${JSON.stringify(d.grounds)}\n` +
      `Ticket: ${A.ticket || 'none'}. Report what was set, or the refusal verbatim.`,
      { label: 'claim-keeper status', phase: 'Record', agentType: KEEPER })
  } else if (out.runs.some(r => r.landed) || (d.verdicts || []).length) {
    out.keeper = await agent(
      `Attach the landed experiment-review verdicts of ${A.subject} as evidence rows (claims_attach_evidence); ` +
      `change no status. The pair stands at ${d.state}` +
      ((d.grounds_problems || []).length ? `, cleared but with grounds problems: ${d.grounds_problems.join('; ')}` : '') +
      `. Report the rows attached.`,
      { label: 'claim-keeper evidence', phase: 'Record', agentType: KEEPER })
  }
  if (d.reproduction) {
    out.to_file.push({ kind: 'test', to_role: 'scientist', parent: A.ticket || '',
                       title: `Reproduce ${A.subject} on another profile`, ask: d.reproduction })
    notes.push('a run asked for reproduction: the pair waits on the test ticket in to_file')
  }
  if (d.state === 'unresolved' || d.reproduction) {
    const pk = await clerk('packet', [
      `The human must decide: the pair is ${d.state}${d.reproduction ? ' and a run asked for reproduction' : ''}.`,
      `Reasons: ${JSON.stringify(d.reasons || [])}. Verdicts: ${JSON.stringify(d.verdicts || [])}.`,
      'File one experiment-review packet with these facts and one decision (how to proceed); return ok and its id in detail.',
    ], DONE, 'Record')
    if (pk) out.packet = pk.detail
  }
}

if (MODE === 'settle-audit' && !['need-A', 'need-B'].includes(out.state)) {
  const plan = await clerk('settle-plan', [
    `candidates file: ${A.candidates}`, report ? `report: ${report}` : '',
    'Write or check the candidates file from the report (settle/SKILL.md step 1), then return settle.py plan <subject> --candidates <file> --json parsed.',
  ], PLAN, 'Record')
  out.plan = plan
  if (plan && CLEARED.includes(out.state)) {
    for (const c of (plan.file_now || []).slice(0, 3)) {   // never more than three per run
      out.to_file.push({ kind: 'experiment', to_role: 'scientist', candidate: c.name, refs: [A.subject, c.ref],
        title: `Re-derive ${c.name} independently`, detail: c.detail,
        then: { kind: 'verify', to_role: 'expert', title: `Is ${c.name} a counterexample to the claim ${A.subject} bears on?`,
                when: 'once the re-derivation report is back (a later run)' } })
    }
    if ((plan.file_now || []).length > 3) notes.push(`${plan.file_now.length - 3} candidate(s) over the cap of three deferred`)
  } else {
    notes.push(`the script audit is ${out.state}: no candidate ticket is filed`)
  }
}

if (MODE === 'settle-conclude') {
  const s = await clerk('settle-decide', [
    `candidates file: ${A.candidates}`,
    `verdicts to copy in (from the Expert packets): ${JSON.stringify(A.verdicts || [])}`,
    'Copy the verdicts into the candidates file, then settle.py decide <subject> --candidates <file> --json and settle.py record <subject> --candidates <file>; return the decision parsed and the record path.',
  ], SETTLED, 'Record')
  out.settle = s
  for (const name of (s && CLEARED.includes(out.state) ? s.recordable : [])) {
    const row = (s.rows || []).find(r => r.name === name) || {}
    out.to_keeper = out.to_keeper || []
    out.to_keeper.push(await agent(
      `The candidate ${name} is a recordable refutation (settle.py decide: two CONFIRMED verdicts and a cleared audit; record ${s.record}). ` +
      `Set the status of the claim it refutes (refuted, or refuted-as-stated with the repaired statement the record names), ` +
      `with proof grounds from its two CONFIRMED verdicts: ${JSON.stringify(row)}. Report what was set, or the refusal verbatim.`,
      { label: `claim-keeper ${name}`, phase: 'Record', agentType: KEEPER }))
  }
}

// ---- the ticket -----------------------------------------------------------------
const waiting = ['need-A', 'need-B'].includes(out.state) || out.to_file.length
if (A.ticket && !waiting) {
  const v = (d && d.verdicts || []).join(', ') || 'none'
  const res = await clerk('close', [`ticket: ${A.ticket}`, `Deliver it with result: "${out.state}; verdicts ${v}${out.packet ? '; packet ' + out.packet : ''}".`], DONE, 'Record')
  out.ticket_closed = !!(res && res.ok)
}
out.outcome = out.state
return out
