export const meta = {
  name: 'academy-prove',
  description: 'Take one notebook claim to a reviewable proof: falsifier and attack first, one prover attempt, the outcome read from the attempt file, a verify ticket to the Expert only for a complete attempt',
  whenToUse: '/researcher:prove and every prove ticket (also nested from the inbox). args: {claim: "<ns:id>", ticket?: "T-NNNN", home: "<the Researcher home>", instance?: "researcher@<x>"}',
  phases: [
    { title: 'State', detail: 'status, inputs, earlier attempts, falsifier, attack' },
    { title: 'Attempt', detail: 'an attack-only run if none, then one proof attempt' },
    { title: 'File', detail: 'by the attempt file\'s outcome: the verify ticket and the sketch proposal, or the gaps' },
  ],
}

// The order of /researcher:prove in code (2026-10-31; docs/workflows.md): nothing is
// attempted on a claim nobody tried to break (needs_explore goes back to the caller), an
// unattacked statement gets one attack-only run first, the outcome is read from the
// attempt's frontmatter by the clerk (never from the prover's summary), and only a
// complete attempt files a verify ticket (by the prover, a liaison toward the Expert;
// the script checks the ticket) and proposes sketch. Nothing is set above sketch.

const A = args || {}
if (!A.claim || !/^([a-z][a-z0-9]*:)?[A-Za-z][\w.:-]*$/.test(A.claim)) throw new Error('args.claim must be a registry id, got ' + JSON.stringify(A.claim))
if (!A.home) throw new Error('args.home must be the Researcher home')
const CLERK = 'researcher:review-clerk'
const PROVER = 'researcher:prover'
const T = A.ticket || ''
const STAGE = (name, lines) => `WORKFLOW STAGE ${name} of the academy-prove workflow. Claim: ${A.claim}. Home: ${A.home}.` +
  (A.instance ? ` Instance: ${A.instance}.` : '') + (T ? ` Ticket: ${T}.` : '') + '\n' + lines.filter(Boolean).join('\n')

const STATE = { type: 'object', properties: {
  ok: { type: 'boolean' }, stop_reason: { type: 'string' },
  status: { type: 'string', description: 'the claim\'s registry status' },
  unsettled_inputs: { type: 'array', items: { type: 'string' }, description: 'depends_on / modulo inputs that are not proved' },
  attempts: { type: 'array', items: { type: 'string' }, description: 'earlier attempt paths' },
  falsified: { type: 'boolean', description: 'a falsifier ran: a report, a direction item, or the ticket says so' },
  falsifier_evidence: { type: 'string' },
  attack_exists: { type: 'boolean', description: 'proofs/<id>/attack.md exists' } },
  required: ['ok', 'stop_reason', 'status', 'unsettled_inputs', 'attempts', 'falsified', 'falsifier_evidence', 'attack_exists'] }
const PATH = { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] }
const OUTCOME = { type: 'object', properties: {
  exists: { type: 'boolean' }, outcome: { type: 'string', description: 'the attempt frontmatter\'s outcome: field, verbatim' },
  gaps: { type: 'array', items: { type: 'string' } }, objects: { type: 'array', items: { type: 'string' }, description: 'claims the attempt names (partial results)' } },
  required: ['exists', 'outcome', 'gaps', 'objects'] }
const FILED = { type: 'object', properties: { ticket: { type: 'string' }, proposal: { type: 'string', description: 'the decision ticket of the sketch proposal, or empty' }, refusal: { type: 'string' } }, required: ['ticket', 'proposal', 'refusal'] }
const TICKET = { type: 'object', properties: { found: { type: 'boolean' }, to: { type: 'string' }, kind: { type: 'string' }, refs: { type: 'array', items: { type: 'string' } } }, required: ['found', 'to', 'kind', 'refs'] }
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok', 'detail'] }

const out = { claim: A.claim, ticket: T || null, notes: [] }
const deliver = async (result) => {
  if (!T) return
  const m = await agent(STAGE('close', [`Deliver ${T} (tickets_update deliver: true) with result "${result.replace(/"/g, "'")}".`]),
    { label: 'close', phase: 'File', agentType: CLERK, schema: MOVE, effort: 'low' })
  out.ticket_delivered = !!(m && m.ok)
}

// ---- State ---------------------------------------------------------------------------
phase('State')
const st = await agent(STAGE('prove-state', [
  T ? `First take ${T}: open -> accepted -> in-progress (leave it if it is in progress already).` : '',
  `Then return: the claim's status (claims_show), its unsettled inputs (depends_on and modulo that are not proved), earlier attempts ` +
  `(notebook.py ls / the object's proof: field), whether a falsifier ran (a report or direction item that attacked it, or the ticket says so: give the evidence), ` +
  `and whether proofs/<id>/attack.md exists. Write nothing else.`,
]), { label: 'state', phase: 'State', agentType: CLERK, schema: STATE, effort: 'low' })
if (!st) return Object.assign(out, { outcome: 'not-started', reason: 'the state stage returned nothing' })
if (!st.ok) return Object.assign(out, { outcome: 'not-started', reason: st.stop_reason })
if (/^proved$/.test(st.status)) { await deliver(`${A.claim} is already proved: nothing to attempt`); return Object.assign(out, { outcome: 'already-proved' }) }
if (!st.falsified) return Object.assign(out, { outcome: 'needs-explore', needs_explore: true, reason: 'nobody has tried to break it: run /researcher:explore (its falsifier) first' })
const modulo = (st.unsettled_inputs || []).length ? `It rests on unsettled inputs (${st.unsettled_inputs.join(', ')}): it can be proved at most proved-modulo them; say so in the attempt.` : ''

// ---- Attempt ---------------------------------------------------------------------------
phase('Attempt')
if (!st.attack_exists) {
  const atk = await agent(`Attack-only run on ${A.claim} (home ${A.home}), briefed with academy/skills/rigor/references/attack-brief.md: you prove nothing. ` +
    `Write proofs/<id>/attack.md: a counterexample, an unlisted hypothesis, or the attack that failed and why.`,
    { label: 'attack', phase: 'Attempt', agentType: PROVER })
  if (atk === null) return Object.assign(out, { outcome: 'lost', reason: 'the attack run returned nothing (a limit?): nothing further launched' })
  out.notes.push('one attack-only run first (proofs/<id>/attack.md)')
}
const p = await agent(STAGE('attempt-path', ['Run notebook.py attempt <id> --create and return the attempt path it prints.']),
  { label: 'attempt path', phase: 'Attempt', agentType: CLERK, schema: PATH, effort: 'low' })
if (!p || !p.path) return Object.assign(out, { outcome: 'not-started', reason: 'no attempt path' })
out.attempt = p.path
const proved = await agent(`Prove ${A.claim} (home ${A.home}) in the attempt file ${p.path}, per your agent definition: scout prior art first (cite before reproving), ` +
  `then the statement as attempted, the strategy, the proof, the inputs with their statuses, and the gaps; set outcome: in its frontmatter. ` +
  (st.attempts.length ? `Earlier attempts: ${st.attempts.join(', ')} (a repair is this new attempt; the old ones stay). ` : '') +
  (st.attack_exists || !out.notes.length ? '' : 'Read proofs/<id>/attack.md first. ') + modulo + ' Set no status.',
  { label: 'attempt', phase: 'Attempt', agentType: PROVER })
if (proved === null) return Object.assign(out, { outcome: 'lost', reason: 'the prover returned nothing (a limit?): nothing further launched' })

// ---- File: by the file, not by the summary ------------------------------------------------
phase('File')
const o = await agent(STAGE('attempt-outcome', [`Read the frontmatter of ${p.path}: return its outcome: field verbatim, its gaps, and the claims it names. Write nothing.`]),
  { label: 'outcome', phase: 'File', agentType: CLERK, schema: OUTCOME, effort: 'low' })
if (!o || !o.exists) return Object.assign(out, { outcome: 'unfinished', reason: 'the attempt file is missing or unreadable' })
out.gaps = o.gaps
if (o.outcome !== 'complete' || (o.gaps || []).length) {
  out.outcome = 'attempt-incomplete'
  await deliver(`attempt ${p.path} ${o.outcome || 'without outcome'}; gaps: ${(o.gaps || []).join('; ') || 'none listed'}; nothing filed for review`)
  return out
}
const f = await agent(`Your attempt ${p.path} on ${A.claim} is complete. File exactly one verify ticket to the Expert instance (tickets_create: kind verify, ` +
  `title "Verify ${A.claim}", ask "Review ${A.claim}: is the argument in ${p.path} valid from its stated inputs?", deliverable "A verification packet with two verdicts, or one negative verdict.", ` +
  `refs [${A.claim}, file:<instance>/${p.path}]${T ? ', parent ' + T : ''}). ` +
  (/^open$/.test(st.status) ? `Then propose sketch (claims_propose_status, grounds note "complete attempt ${p.path}"). ` : '') +
  'Return the ticket id and the proposal ticket; a refusal verbatim.',
  { label: 'file verify', phase: 'File', agentType: PROVER, schema: FILED, effort: 'low' })
if (!f || !f.ticket) {
  out.outcome = 'blocked'
  out.reason = 'the verify ticket was not filed: ' + (f ? f.refusal : 'the stage returned nothing')
  return out
}
const chk = await agent(STAGE('get', [`tickets_get ${f.ticket} and return its to, kind and refs.`]), { label: 'check verify', phase: 'File', agentType: CLERK, schema: TICKET, effort: 'low' })
const bad = !chk || !chk.found || !/^expert@/.test(chk.to) || chk.kind !== 'verify' || !(chk.refs || []).includes(A.claim)
if (bad) out.notes.push(`ANOMALY: the verify ticket ${f.ticket} is not a verify ticket to the Expert naming ${A.claim}`)
out.verify_ticket = f.ticket
out.proposal = f.proposal || null
out.outcome = 'verify-filed'
await deliver(`complete attempt ${p.path}; verify ticket ${f.ticket}${f.proposal ? '; sketch proposed (' + f.proposal + ')' : ''}`)
return out
