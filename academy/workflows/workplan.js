export const meta = {
  name: 'academy-workplan',
  description: 'A campaign (autonomous, the Researcher\'s rounds of blind provers) or a cowork pass (human-led, the next actors of its released tickets): shared caps, state, next-actor and stop rules in code',
  whenToUse: '/researcher:campaign (kind campaign) and /academy:cowork step 3 (kind cowork). args: {kind, root: <academy repo>, home?: <Researcher home>, instance?: "researcher@<x>", target?, rounds?, agents?, runs?, profile?, cloud?, slug?}',
  phases: [
    { title: 'Caps', detail: 'the normalized caps (workplan.caps)' },
    { title: 'Seed', detail: 'campaign: at least four approaches, by the lead' },
    { title: 'Rounds', detail: 'the next actors, then (campaign) one blind prover per active approach and the lead\'s update' },
    { title: 'Report', detail: 'the shared final shape' },
  ],
}

// Campaign and cowork share their mechanics (academy/lib/workplan.py: tags, state, caps;
// the human's decision of 2026-10-31 that their workflow share components too): the
// caps are normalized once; the state is computed from the tagged tickets, never kept by
// hand; the next actor of a ticket is its role's inbox, run here nested and scoped to the
// tag; the stop rules are one function. A campaign then runs its rounds autonomously. A
// cowork is led by the human, so one call is one pass, and every question goes back to
// the skill (for_main), which asks and calls again.

const A = args || {}
if (!['campaign', 'cowork'].includes(A.kind)) throw new Error('args.kind must be campaign or cowork')
if (!A.root) throw new Error('args.root must be the academy repo')
const ROOT = A.root.replace(/[\\/]+$/, '')
const KIND = A.kind
const TAG = KIND === 'campaign' ? A.target : A.slug
if (!TAG) throw new Error(KIND === 'campaign' ? 'args.target is required' : 'args.slug is required')
if (KIND === 'campaign' && !A.home) throw new Error('a campaign needs args.home (the Researcher home)')
const CLERK = KIND === 'campaign' ? 'researcher:review-clerk' : 'academy:inbox-clerk'
const STAGE = (name, lines) => `WORKFLOW STAGE ${name} of the academy-workplan workflow (${KIND} ${TAG}).` +
  (A.home ? ` Home: ${A.home}.` : '') + (A.instance ? ` Instance: ${A.instance}.` : '') + '\n' + lines.filter(Boolean).join('\n')

const CAPS = { type: 'object', properties: { ok: { type: 'boolean' }, error: { type: 'string' },
  rounds: { type: ['number', 'null'] }, agents: { type: 'number' }, runs: { type: 'number' }, profile: { type: ['string', 'null'] } },
  required: ['ok', 'error', 'rounds', 'agents', 'runs', 'profile'] }
const APPROACH = { type: 'object', properties: { approach: { type: 'string' }, lifecycle: { type: 'string' }, state: { type: 'string' },
  directions: { type: 'array', items: { type: 'string' } }, waiting_tickets: { type: 'array', items: { type: 'string' } },
  decision_tickets: { type: 'array', items: { type: 'string' } } }, required: ['approach', 'lifecycle', 'state', 'directions', 'waiting_tickets', 'decision_tickets'] }
const STATE = { type: 'object', properties: {
  state: { type: 'string', enum: ['ACTIVE', 'WAITING', 'PAUSE', 'DONE'] },
  decision: { type: 'array', items: { type: 'string' }, description: 'tickets that wait on the human' },
  out: { type: 'array', items: { type: 'string' }, description: 'tickets out with another role\'s next actor' },
  own: { type: 'array', items: { type: 'string' } },
  receivers: { type: 'array', items: { type: 'string' }, description: 'the instances the open (own/out) tickets are addressed to' },
  approaches: { type: 'array', items: APPROACH, description: 'campaign only' },
  approach_count_ok: { type: 'boolean', description: 'campaign only: notebook.py approach check passes' },
  target_status: { type: 'string', description: 'campaign only: the target claim\'s status' },
  target_statement: { type: 'string', description: 'campaign only' } },
  required: ['state', 'decision', 'out', 'own', 'receivers'] }
const NEXT = { type: 'object', properties: { items: { type: 'array', items: { type: 'string' } } }, required: ['items'] }
const ARTIFACT = { type: 'object', properties: { artifact: { type: 'string', description: 'the path of the one artifact written' },
  kind: { type: 'string', enum: ['lemma', 'construction', 'equation', 'counterexample', 'none'] }, summary: { type: 'string' } }, required: ['artifact', 'kind', 'summary'] }
const EXISTS = { type: 'object', properties: { exists: { type: 'boolean' } }, required: ['exists'] }
const LEAD = { type: 'object', properties: { updates: { type: 'array', items: { type: 'string' } },
  tickets_filed: { type: 'array', items: { type: 'string' } }, notes: { type: 'string' } }, required: ['updates', 'tickets_filed', 'notes'] }

const out = { kind: KIND, tag: TAG, notes: [], for_main: [], taken: [], rounds_run: 0, agents_used: 0, tickets_filed: [] }

// ---- shared components ----------------------------------------------------------------
async function caps() {
  if (KIND === 'cowork') {
    const agents = A.agents == null ? 1 : A.agents
    return agents >= 1 ? { ok: true, error: '', rounds: null, agents, runs: 0, profile: null } : { ok: false, error: '--agents must be at least 1' }
  }
  return agent(STAGE('campaign-check', [`Run notebook.py campaign-check --rounds ${A.rounds} --agents ${A.agents}` +
    (A.runs != null ? ` --runs ${A.runs}` : '') + (A.profile ? ` --profile ${A.profile}` : '') + (A.cloud ? ' --cloud' : '') +
    ' --json and return its caps, or ok false with its error line.']), { label: 'caps', phase: 'Caps', agentType: CLERK, schema: CAPS, effort: 'low' })
}

function state(label) {
  return agent(STAGE('workplan-state', KIND === 'campaign'
    ? [`Return notebook.py approach status --campaign ${TAG} --json (its state, decision and waiting tickets, and every approach), whether notebook.py approach check --campaign ${TAG} passes,`,
       `the target ${TAG}'s status and statement (claims_show), and the receivers of the open tickets tagged campaign ${TAG}. Write nothing.`]
    : [`Return cowork.py status ${TAG} --json (state, decision, out, own) and the receivers (the "to" instances) of its open tickets. Write nothing.`]),
    { label: label || 'state', phase: 'Rounds', agentType: CLERK, schema: STATE, effort: 'low' })
}

async function nextActor(receivers, cap) {
  // the next actor of each ticket is its role's inbox, scoped to the tag, nested (so its own
  // nested routes come back as for_main); a lost agent in it stops the whole workplan
  const only = (receivers || []).filter(r => r && r !== 'human')
  if (!only.length) return { count: 0 }
  const r = await workflow({ scriptPath: ROOT + '/academy/workflows/inbox.js' },
    Object.assign({ root: ROOT, only, cap, nested: true }, KIND === 'campaign' ? { campaign: TAG } : { cowork: TAG }))
  if (!r) return { lost: true }
  out.taken.push(...(r.taken || []))
  if (r.for_main) out.for_main.push(r.for_main)
  out.notes.push(...(r.notes || []))
  return r.stopped ? { lost: true, why: r.stopped } : r
}

function stopRule(st) {
  if (!st) return 'the state stage returned nothing'
  if (st.state === 'DONE') return 'DONE'
  if (KIND === 'campaign' && /^proved/.test(st.target_status || '')) return 'the target is proved (two agreeing reviews)'
  if (st.state === 'PAUSE') { out.for_main.push({ why: 'decisions for the human (/academy:decide)', tickets: st.decision }); return 'PAUSE: every active group waits on the human' }
  if (st.state === 'WAITING') return 'WAITING: everything open is out with another role\'s next actor'
  if (budget.total && budget.remaining() < 30000) return 'the token budget is spent'
  return null
}

function report(st, why) {
  return Object.assign(out, { state: st ? st.state : 'unknown', stopped: why,
    waiting_on: st ? (st.out || []) : [], decisions: st ? (st.decision || []) : [] })
}

// ---- Caps ------------------------------------------------------------------------------
phase('Caps')
const cp = await caps()
if (!cp || !cp.ok) return report(null, 'caps: ' + (cp ? cp.error : 'the caps stage returned nothing') + (KIND === 'campaign' ? ' (stop and ask; suggest 3 rounds and 4 agents)' : ''))
out.caps = cp

// ---- Cowork: one pass ------------------------------------------------------------------------
if (KIND === 'cowork') {
  phase('Rounds')
  const before = await state('state before')
  const stop = stopRule(before)
  if (stop && stop !== 'WAITING: everything open is out with another role\'s next actor') return report(before, stop)
  const r = await nextActor(before.receivers, cp.agents)          // at most --agents tickets in flight
  const after = r.lost ? before : await state('state after')
  phase('Report')
  if (out.taken.some(t => /^author@/.test(t.instance)))
    out.notes.push('an Author ticket ran: run /author:sweep if tex was touched (the inbox swept before it)')
  out.plan_log = out.taken.map(t => `${t.id} (${t.instance}): ${t.outcome}${t.detail ? ' - ' + t.detail : ''}`)
  return report(after, r.lost ? ('an agent was lost: ' + (r.why || 'no result')) : (stopRule(after) || 'pass done: report to the human, ask what needs asking, then call again'))
}

// ---- Campaign ---------------------------------------------------------------------------
const LEAD_TYPE = 'researcher:lead-researcher'
const PROVER = 'researcher:prover'
phase('Seed')
let st = await state('state')
if (!st) return report(null, 'the state stage returned nothing')
if (!st.approach_count_ok) {
  const seed = await agent(`Round 0 of the campaign on ${TAG} (home ${A.home}): seed at least four approach objects with notebook.py new approach ` +
    `(substantially different mechanisms, grouped by idea, duplicates merged), each with at least one concrete direction; file the one target-level ` +
    `prior-art check to the Expert as a lookup or cite ticket tagged campaign ${TAG}. Return the updates and the tickets filed.`,
    { label: 'seed', phase: 'Seed', agentType: LEAD_TYPE, schema: LEAD })
  if (seed === null) return report(st, 'the seeding run was lost (a limit?)')
  out.tickets_filed.push(...(seed.tickets_filed || []))
  st = await state('state after seeding')
  if (!st || !st.approach_count_ok) return report(st, 'notebook.py approach check still fails after seeding: fewer than four valid approaches')
}

phase('Rounds')
const rounds = {}                       // approach -> rounds it has had a prover
let reseed = false, why = null
for (let round = 1; round <= cp.rounds; round++) {
  // 1. take what came back: the Researcher's own inbox, scoped to the campaign
  const r = await nextActor([A.instance || (st.receivers || []).find(x => /^researcher@/.test(x))].filter(Boolean), 3)
  if (r.lost) { why = 'an agent was lost in the inbox run: ' + (r.why || 'no result'); break }
  st = await state(`state round ${round}`)
  why = stopRule(st)
  if (why) break
  if (reseed) {
    const s = await agent(`The last round of the campaign on ${TAG} was a failed wave (no artifact, or every approach blocked). Reseed: fresh formulations, ` +
      `and reopen any approach whose reopen_if now holds (notebook.py approach set ... --note naming the new mechanism). Return the updates.`,
      { label: `reseed ${round}`, phase: 'Rounds', agentType: LEAD_TYPE, schema: LEAD })
    if (s === null) { why = 'the reseeding run was lost'; break }
    reseed = false
    st = await state(`state round ${round} reseeded`)
  }
  // 2-3. one blind prover per active, non-waiting approach, serially, against --agents
  const artifacts = []
  let used = 0                          // --agents binds per round: reaching it ends only the round
  for (const ap of (st.approaches || []).filter(a => a.lifecycle === 'active' && a.state === 'ACTIVE')) {
    if (used >= cp.agents) { out.notes.push(`round ${round}: --agents (${cp.agents}) reached; the round ends`); break }
    const items = []
    for (const d of ap.directions || []) {
      const n = await agent(STAGE('next', [`Return the items of notebook.py next ${d} --json (nothing for a blocked, dropped or delivered approach).`]),
        { label: `next ${d}`, phase: 'Rounds', agentType: CLERK, schema: NEXT, effort: 'low' })
      if (n) items.push(...n.items.map(x => `${d}: ${x}`))
    }
    if (!items.length) continue
    // blind: the approach, its next items and the target statement, nothing of the other approaches
    const a = await agent(`Campaign prover on approach ${ap.approach} (home ${A.home}). Target: ${TAG}: ${st.target_statement || '(claims_show it)'}\n` +
      `Your directions' next items:\n- ${items.join('\n- ')}\nProduce ONE concrete artifact (a lemma with a proof attempt, a construction, an equation, or a counterexample to a sublemma) ` +
      `as a file in the notebook, and return its path. Search background and standard theorems for your approach only; never whether the target is solved.`,
      { label: `prover ${ap.approach} r${round}`, phase: 'Rounds', agentType: PROVER, schema: ARTIFACT })
    out.agents_used++
    used++
    if (a === null) { why = `the prover on ${ap.approach} was lost (a limit?)`; break }
    rounds[ap.approach] = (rounds[ap.approach] || 0) + 1
    const e = a.artifact && a.kind !== 'none' ? await agent(STAGE('exists', [`Does ${a.artifact} exist in the home? Return exists.`]),
      { label: `exists ${ap.approach} r${round}`, phase: 'Rounds', agentType: CLERK, schema: EXISTS, effort: 'low' }) : null
    if (e && e.exists) artifacts.push({ approach: ap.approach, artifact: a.artifact, kind: a.kind, summary: a.summary })
    else out.notes.push(`round ${round}: ${ap.approach} produced no artifact (a wasted slot)`)
  }
  if (why) break
  out.rounds_run = round
  // 4-7. the lead: reduction audit, approach updates, diversity check, hand-off tickets
  const survivors = (st.approaches || []).filter(a => a.lifecycle === 'active')
  const cross = survivors.length > 0 && survivors.every(a => (rounds[a.approach] || 0) >= 2)
  const l = await agent(`Round ${round} of the campaign on ${TAG} (home ${A.home}) is done. The artifacts: ${JSON.stringify(artifacts)}.\n` +
    `Audit them with the rigor reduction audit (anything claimed proved goes to /researcher:prove's verify route as a ticket; nothing is graded here); ` +
    `update the approaches (notebook.py approach set AP-n <lifecycle> ...; blocked needs --blocked-by and --reopen-if); run the diversity check ` +
    `(more than half the active directions in one family: redirect the extras); file every ask for another role as a ticket tagged campaign ${TAG}. ` +
    (cross ? 'Every surviving approach has had two rounds: you may call cross-pollination. ' : 'No cross-pollination yet. ') +
    'Return the updates and the tickets filed.', { label: `lead r${round}`, phase: 'Rounds', agentType: LEAD_TYPE, schema: LEAD })
  if (l === null) { why = 'the lead\'s update was lost (a limit?)'; break }
  out.tickets_filed.push(...(l.tickets_filed || []))
  if (!artifacts.length) reseed = true                      // a failed wave: the next round reseeds
}
phase('Report')
st = await state('state final')
return report(st, why || stopRule(st) || `--rounds (${cp.rounds}) reached`)
