export const meta = {
  name: 'academy-verify',
  description: 'Expert proof review of one registry statement: blind rigor-reviewer A, B only if A is CONFIRMED (or one reword run R), the decision table, the record, evidence, proposal and packet',
  whenToUse: 'Every verify ticket and /expert:verify, from the library home. args: {claim, ticket?, question?, mode?: "blind"|"reword", base_pass?, base_subject?, findings?}',
  phases: [
    { title: 'Prepare', detail: 'take the ticket, hash the statement, open the pass' },
    { title: 'Review', detail: 'blind run A; B only if the table says launch_b (or run R)' },
    { title: 'Conclude', detail: 'decision table, record, evidence, proposal, packet, follow-ups' },
  ],
}

// The sequencing rules of conclude.md sections 0-2 and 7, held in code rather than
// in prose (the 2026-10-31 decision): the reviewers are separate fresh agents, B is
// launched only when decision_table.py says launch_b and the statement hash has not
// moved, B gets A's brief byte for byte with run B, a reword pass runs R alone, a lost
// run is relaunched once, and nothing but the review-chair's clerical stages touches
// the files. The verdicts are landed by the expert plugin's land_verdict hook (it
// fires for workflow agents: B0 pilot, docs/workflows.md).

const A = args || {}
if (!A.claim || !/^[a-z][a-z0-9]*:\S+$/.test(A.claim)) {
  throw new Error('args.claim must be a namespaced registry id (paper:lem:x, flat:GEO-3), got ' + JSON.stringify(A.claim))
}
const MODE = A.mode === 'reword' ? 'reword' : 'blind'
const QUESTION = A.question || 'may it be raised to proved?'
const CHAIR = 'expert:review-chair'
const REVIEWER = 'expert:rigor-reviewer'
const RE_PASS = /^\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?$/
const RE_HASH = /^[0-9a-f]{6,}$/

const PREP = {
  type: 'object',
  properties: {
    ok: { type: 'boolean', description: 'false when the pass must not start (budget, an open pass, a refused reword base)' },
    stop_reason: { type: 'string' },
    pass: { type: 'string' },
    pass_dir: { type: 'string', description: 'absolute path of the pass folder' },
    statement_hash: { type: 'string' },
    location: { type: 'string', description: 'where the statement and proof live: file:label, or the object and its proofs/ attempt' },
    bundle: { type: 'string', description: 'reword mode: absolute path of the bundle file; else empty' },
    ticket: { type: 'string', description: 'the ticket id, or none' },
  },
  required: ['ok', 'stop_reason', 'pass', 'pass_dir', 'statement_hash', 'location', 'bundle', 'ticket'],
}
const TABLE = {
  type: 'object',
  properties: {
    landed: { type: 'boolean', description: 'the run file exists in the pass folder' },
    run_file: { type: 'string' },
    verdict: { type: 'string' },
    outcome: { type: 'string', description: 'decision_table.py outcome' },
    launch_b: { type: 'boolean', description: 'decision_table.py launch_b (false when absent)' },
    hash_now: { type: 'string', description: 'reviews.py hash of the statement as it stands now' },
  },
  required: ['landed', 'run_file', 'verdict', 'outcome', 'launch_b', 'hash_now'],
}
const DONE = {
  type: 'object',
  properties: {
    outcome: { type: 'string' },
    proposed_status: { type: 'string', description: 'the proposal filed, or none' },
    record: { type: 'string', description: 'path of decision.md' },
    packet: { type: 'string', description: 'the packet id, or none' },
    tickets: { type: 'array', items: { type: 'string' }, description: 'tickets filed or updated' },
    run_files: { type: 'array', items: { type: 'string' }, description: 'the run files in the pass folder after concluding (ls)' },
    report: { type: 'string', description: 'the report of conclude.md section 6' },
  },
  required: ['outcome', 'proposed_status', 'record', 'packet', 'tickets', 'run_files', 'report'],
}

const STAGE = (name, body) =>
  `WORKFLOW STAGE ${name} of the academy-verify workflow (review-chair, workflow mode). ` +
  `Do this stage only, as conclude.md describes it, and return the structured result. ` +
  `Launch no agent: the workflow launches the reviewers.\n\n${body}`

// ---- 1. Prepare -------------------------------------------------------------
phase('Prepare')
const prep = await agent(STAGE('prepare', [
  `claim: ${A.claim}`, `ticket: ${A.ticket || 'none'}`, `mode: ${MODE}`,
  MODE === 'reword' ? `base_pass: ${A.base_pass || '(find it: reviews.py list)'}` : '',
  A.base_subject ? `base_subject: ${A.base_subject}` : '',
  A.findings ? `findings for the bundle: ${A.findings}` : '',
  '',
  MODE === 'reword'
    ? 'conclude.md section 7 steps 1-4: take the ticket (budget: one reviewer run plus you), recover old.txt / new.txt, check the old hash, `reviews.py new-pass <id> --reword-of <base pass>` (with --base-subject when given), write the bundle with `reviews.py reword-brief`. statement_hash is the NEW statement\'s hash.'
    : 'conclude.md section 0: take the ticket (budget: two reviewer runs plus you; else block it and return ok=false), pin and hash the statement (`reviews.py hash --file`), open the pass (`reviews.py new-pass`, `reviews.py dir`). Write nothing in the pass folder.',
].filter(Boolean).join('\n')), { label: 'prepare', phase: 'Prepare', agentType: CHAIR, schema: PREP, effort: 'low' })

if (!prep || !prep.ok) {
  log('pass not started: ' + (prep ? prep.stop_reason : 'the prepare stage returned nothing'))
  return { claim: A.claim, outcome: 'not-started', reason: prep ? prep.stop_reason : 'prepare lost' }
}
if (!RE_PASS.test(prep.pass) || !RE_HASH.test(prep.statement_hash)) {
  throw new Error(`prepare returned a malformed pass ${JSON.stringify(prep.pass)} or hash ${JSON.stringify(prep.statement_hash)}`)
}
const ticket = prep.ticket || 'none'
const ids = `subject: ${A.claim} · pass: ${prep.pass} · run: RUN · statement_hash: ${prep.statement_hash} · ticket: ${ticket}`
const brief = (run) => MODE === 'reword'
  ? `Reword review of ${A.claim} (reword mode, run R): read the bundle ${prep.bundle} first; ` +
    `the proof is at ${prep.location}. The question: does the proof as reviewed still prove the new wording?\n` +
    ids.replace('RUN', 'R')
  : `Review ${A.claim}: its statement and proof are at ${prep.location}. The question: ${QUESTION} ` +
    `Work through your obligation ledger before reading the proof.\n` + ids.replace('RUN', run)

// ---- 2. Review: one run, checked by the table, relaunched once when it did not land ----
const notes = []
const table = (run) => agent(STAGE('table', [
  `pass_dir: ${prep.pass_dir}`, `run: ${run}`, `claim: ${A.claim}`,
  `Check that ${run}.md landed in the pass folder; run \`decision_table.py "<pass_dir>/${run}.md" --json\` ` +
  `(no B argument) and report its outcome and launch_b; re-hash the statement as it stands now ` +
  `exactly as the prepare stage hashed it (\`reviews.py hash --file\`). Write nothing.`,
].join('\n')), { label: `table ${run}`, phase: 'Review', agentType: CHAIR, schema: TABLE, effort: 'low' })

async function review(run) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    const out = await agent(brief(run), { label: `run ${run}${attempt > 1 ? ' (relaunch)' : ''}`, phase: 'Review', agentType: REVIEWER })
    if (out === null) {           // a terminal API error (a limit): launch nothing further
      notes.push(`run ${run} lost (no result: a limit or an API error); nothing further launched`)
      return { lost: true }
    }
    const t = await table(run)
    if (t && t.landed) {
      if (attempt > 1) notes.push(`run ${run}: the kept run is the relaunch`)
      return t
    }
    notes.push(`run ${run} attempt ${attempt} did not land a verdict`)
  }
  return { lost: true }
}

phase('Review')
let runs = []
if (MODE === 'reword') {
  const r = await review('R')
  runs.push(Object.assign({ run: 'R' }, r))
  notes.push('reword pass: one informed run R, no blind pair (T-0347)')
} else {
  const a = await review('A')
  runs.push(Object.assign({ run: 'A' }, a))
  if (a.lost) {
    // nothing to add
  } else if (!a.launch_b) {
    notes.push(`run B skipped by design: the table on A says ${a.outcome} (launch_b false)`)
  } else if (a.hash_now !== prep.statement_hash) {
    notes.push(`statement moved under the review (hash ${prep.statement_hash} -> ${a.hash_now}): B not launched, nothing to conclude on the old wording`)
  } else {
    const b = await review('B')     // the identical brief, run B, a fresh agent told nothing of A
    runs.push(Object.assign({ run: 'B' }, b))
  }
}
log(runs.map(r => `${r.run}: ${r.lost ? 'lost' : r.verdict + ' -> ' + r.outcome}`).join('; '))

// ---- 3. Conclude --------------------------------------------------------------
phase('Conclude')
const done = await agent(STAGE('conclude', [
  `claim: ${A.claim}`, `ticket: ${ticket}`, `mode: ${MODE}`, `pass: ${prep.pass}`, `pass_dir: ${prep.pass_dir}`,
  `statement_hash: ${prep.statement_hash}`, `location: ${prep.location}`,
  `runs (from the workflow): ${JSON.stringify(runs)}`,
  `process notes for the record (copy them into its process note): ${JSON.stringify(notes)}`,
  '',
  MODE === 'reword'
    ? 'conclude.md section 7 steps 6-7, then sections 4-6.'
    : 'conclude.md sections 2-6: the input-by-input status, the final decision_table.py over the landed runs with --established, the record decision.md, evidence rows, the proposal (only the script\'s proposed_status), follow-up tickets exactly as the script routes them, the packet, the ticket result and delivery, the blast radius, the report.',
  'Then list the run files in the pass folder (run_files).',
].join('\n')), { label: 'conclude', phase: 'Conclude', agentType: CHAIR, schema: DONE })

if (!done) {
  return { claim: A.claim, pass: prep.pass, pass_dir: prep.pass_dir, outcome: 'conclude-lost', runs, notes }
}
// the concluder launches nothing: only the runs this workflow made may be in the folder
const allowed = new Set(runs.filter(r => !r.lost).map(r => r.run + '.md'))
const extra = (done.run_files || []).map(f => f.split(/[\\/]/).pop())
  .filter(f => /^[ABR](-\d+)?(-noverdict)?\.md$/.test(f) && !allowed.has(f))
if (extra.length) notes.push('ANOMALY: run files the workflow did not launch: ' + extra.join(', '))
return { claim: A.claim, pass: prep.pass, pass_dir: prep.pass_dir, runs, notes,
         outcome: done.outcome, proposed_status: done.proposed_status, record: done.record,
         packet: done.packet, tickets: done.tickets, report: done.report, anomalies: extra }
