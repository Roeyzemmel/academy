export const meta = {
  name: 'academy-inbox',
  description: 'Work the board inboxes in the fixed order (Author, Expert, Researcher, Scientist), at most three tickets, serially: routes, relay legs and their conclusions, checkpoints, all in code',
  whenToUse: '/academy:inbox and every role inbox (only: [instance]). args: {root: <academy repo>, n?, cap?, only?: [instance], campaign?, cowork?, ids?: [T-NNNN]}',
  phases: [
    { title: 'List', detail: 'each instance\'s inbox.py --json' },
    { title: 'Sweep', detail: 'the Author\'s machine-note sweep, before any ticket' },
    { title: 'Tickets', detail: 'one ticket at a time, by route, then its checkpoint' },
    { title: 'Close', detail: 'the Author\'s delivered self-tickets' },
  ],
}

// The inbox rules of /academy:inbox and the four role inboxes, and the relays' legs, in
// code (the human's decision, 2026-10-31; docs/workflows.md):
//  * the instance order, the cap over the whole run (budget.md rule 1), one ticket at a
//    time with its --check checkpoint (rule 2), an unfinished ticket closes its
//    instance for the run, a lost agent stops the run (rule 4);
//  * the route is the role's routes.py (in the inbox.py row); this script dispatches it:
//    reject / human / over-budget are clerk moves; a relay's forward leg is the relay's
//    decision and its child ticket only, and the script then checks the child (parent,
//    receiver role, kind, final_to) and makes the conclusion (blocked on the child, or
//    delivered when it failed fast); a relay's return leg is mechanical and made here
//    without the relay; verify and review-experiment run their own workflows nested;
//    a route that needs the main session (a skill, a question to the human, a ticket
//    only `main` may file) ends the run with `for_main`, in order, so nothing overtakes it.
// Every transition is made by the academy's inbox-clerk, acting for the ticket's party
// (instance=...). Each agent runs under its own definition and the plugin hooks.

const A = args || {}
if (!A.root) throw new Error('args.root must be the academy repo (the folder holding the plugins)')
const ROOT = A.root.replace(/[\\/]+$/, '')
const CAP = Math.max(0, Math.min(A.cap || A.n || 3, (A.campaign || A.cowork) ? 99 : 3))
const ORDER = ['author', 'expert', 'researcher', 'scientist']
const CLERK = 'academy:inbox-clerk'
// a relay: the role its child goes to, the kinds the child may have, the final_to default
const RELAYS = {
  'research-intake': { role: 'expert', to: 'researcher', kinds: ['research'], final_default: 'researcher' },
  'paper-liaison': { role: 'expert', to: 'author', kinds: ['question', 'note'] },
  'experiment-spec': { role: 'researcher', to: 'scientist', kinds: ['experiment', 'test'] },
  'lit-request': { role: 'researcher', to: 'expert', kinds: ['cite', 'question'] },
}
const NESTED = {
  'expert:verify': ROOT + '/expert/workflows/verify.js',
  'researcher:review-experiment': ROOT + '/researcher/workflows/review-experiment.js',
  'researcher:prove': ROOT + '/researcher/workflows/prove.js',
  'expert:cite': ROOT + '/expert/workflows/cite.js',
  'researcher:explore': ROOT + '/researcher/workflows/explore.js',
  'researcher:generalize': ROOT + '/researcher/workflows/generalize.js',
}
// nested: this run is itself a sub-workflow (of workplan.js); nesting is one level only, so
// the routes that run their own workflow are handed back as for_main instead
const NESTED_OK = !A.nested
const roleOf = (inst) => String(inst || '').split('@')[0]

const ROW = {
  type: 'object',
  properties: {
    id: { type: 'string' }, kind: { type: 'string' }, status: { type: 'string' },
    from: { type: 'string' }, to: { type: 'string' }, final_to: { type: 'string' },
    refs: { type: 'array', items: { type: 'string' } },
    budget_runs: { type: 'number' },
    route: { type: 'object', properties: { how: { type: 'string' }, target: { type: ['string', 'null'] }, why: { type: 'string' } }, required: ['how', 'target', 'why'] },
    return: { type: 'boolean' }, released: { type: 'boolean' }, over_budget: { type: ['string', 'null'] },
  },
  required: ['id', 'kind', 'status', 'from', 'to', 'final_to', 'refs', 'budget_runs', 'route', 'return', 'released', 'over_budget'],
}
const LIST = {
  type: 'object',
  properties: {
    instances: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' }, role: { type: 'string' }, home: { type: 'string' }, waiting: { type: 'number' },
      rows: { type: 'array', items: ROW } }, required: ['name', 'role', 'home', 'waiting', 'rows'] } },
  },
  required: ['instances'],
}
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, status: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'status', 'detail'] }
const CHECK = { type: 'object', properties: { exit: { type: 'number' }, status: { type: 'string' }, detail: { type: 'string' } }, required: ['exit', 'status', 'detail'] }
const TICKET = { type: 'object', properties: {
  found: { type: 'boolean' }, id: { type: 'string' }, from: { type: 'string' }, to: { type: 'string' },
  kind: { type: 'string' }, status: { type: 'string' }, parent: { type: 'string' }, final_to: { type: 'string' },
  packets: { type: 'array', items: { type: 'string' } } },
  required: ['found', 'id', 'from', 'to', 'kind', 'status', 'parent', 'final_to', 'packets'] }
const RELAY_OUT = { type: 'object', properties: {
  decision: { type: 'string', enum: ['fail-fast', 'forward', 'refused'] },
  result: { type: 'string', description: 'one line: the reason (fail-fast), the child id and ask (forward), the refusal (refused)' },
  result_detail: { type: 'string', description: 'the ## Result body for a fail-fast; else empty' },
  child: { type: 'string', description: 'the child ticket id you filed, or empty' },
  notes: { type: 'array', items: { type: 'string' }, description: 'note tickets filed to the Author, if any' } },
  required: ['decision', 'result', 'result_detail', 'child', 'notes'] }

const clerk = (stage, lines, schema, label) => agent(
  `WORKFLOW STAGE ${stage} of the academy-inbox workflow.\n` + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase: stage === 'list' ? 'List' : (stage === 'close-self' ? 'Close' : 'Tickets'), agentType: CLERK, schema, effort: 'low' })
const move = (row, inst, what, label) => clerk('move', [`ticket: ${row.id}`, `act as: ${inst}`, what], MOVE, label || `${row.id} ${what.split(':')[0]}`)

const notes = []
const taken = []
const out = { taken, notes, for_main: null, remaining: {} }

// ---- List ---------------------------------------------------------------------------
phase('List')
const listed = await clerk('list', [
  `For each instance of workspace.json${A.only ? ' among ' + JSON.stringify(A.only) : ''}, run its role's inbox script:`,
  `py <academy>/<role>/scripts/inbox.py --instance <name> --json${A.n ? ' --n ' + A.n : ''}${A.campaign ? ' --campaign ' + A.campaign : ''}${A.cowork ? ' --cowork ' + A.cowork : ''} (academy = ${ROOT}).`,
  'Return every row of "take" with the fields asked (final_to empty when none; budget_runs from budget.runs, 1 when absent; released false when absent), and "waiting".',
], LIST)
if (!listed) return Object.assign(out, { stopped: 'the list stage returned nothing' })
let insts = listed.instances.filter(i => !A.only || A.only.includes(i.name))
insts.sort((a, b) => ORDER.indexOf(a.role) - ORDER.indexOf(b.role) || (a.name < b.name ? -1 : 1))
if (A.ids && A.ids.length) for (const i of insts) i.rows = i.rows.filter(r => A.ids.includes(r.id))
for (const i of insts) out.remaining[i.name] = i.waiting

// ---- Sweep (the Author's, before any ticket; counts against no cap) -------------------
phase('Sweep')
for (const i of insts.filter(i => i.role === 'author')) {
  const s = await agent(`Run the machine-note sweep of ${i.name} (home ${i.home}) as /author:sweep does, and report the counts per section.`,
    { label: `sweep ${i.name}`, phase: 'Sweep', agentType: 'author:note-sweeper' })
  if (s === null) return Object.assign(out, { stopped: `the sweep of ${i.name} was lost (a limit?): nothing further launched` })
  out.sweep = (out.sweep || []).concat([{ instance: i.name, report: s }])
}

// ---- one ticket -------------------------------------------------------------------------
async function relayForward(row, inst, r) {
  const final = row.final_to || r.final_default || ''
  const st = await move(row, inst, 'start: move it to in-progress (open -> accepted -> in-progress, or accepted -> in-progress); leave an in-progress ticket as it is')
  if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start: ' + (st ? st.detail : 'lost') }
  const rel = await agent(
    `WORKFLOW RELAY forward leg. Ticket ${row.id}, which you relay for ${inst}; it is in-progress. ` +
    `Decide per your agent definition: fail fast (return decision fail-fast with the reason and the ## Result text), ` +
    `or sharpen and forward: file ONE child with tickets_create to the ${r.to} instance only, kind ${r.kinds.join(' or ')}, ` +
    `parent ${row.id}, final_to ${final || '(none)'}, and return decision forward with its id. ` +
    `Make no status move on ${row.id} (the workflow concludes it). A tickets_create refusal: decision refused, with the refusal verbatim.`,
    { label: `${row.route.target} ${row.id}`, phase: 'Tickets', agentType: `${r.role}:${row.route.target}`, schema: RELAY_OUT })
  if (rel === null) return { lost: true }
  if (rel.decision === 'fail-fast') {
    const m = await move(row, inst, `deliver: deliver: true with result "${rel.result}" and result_detail:\n${rel.result_detail}`)
    return { outcome: m && m.ok ? 'delivered (failed fast)' : 'unfinished', detail: rel.result }
  }
  if (rel.decision === 'forward' && rel.child) {
    const c = await clerk('get', [`ticket: ${rel.child}`, 'tickets_get it and return its fields.'], TICKET, `get ${rel.child}`)
    const bad = []
    if (!c || !c.found) bad.push('the child does not exist')
    else {
      if (c.parent !== row.id) bad.push(`its parent is ${c.parent || 'none'}, not ${row.id}`)
      if (c.from !== inst) bad.push(`it was filed by ${c.from}, not ${inst}`)
      if (roleOf(c.to) !== r.to) bad.push(`it goes to ${c.to}, not a ${r.to} instance`)
      if (!r.kinds.includes(c.kind)) bad.push(`its kind is ${c.kind}, not ${r.kinds.join('/')}`)
      if ((c.final_to || '') !== final) bad.push(`its final_to is ${c.final_to || 'none'}, not ${final || 'none'}`)
    }
    if (bad.length) {
      const m = await move(row, inst, `block-human: blocked, waiting_on [human], reason "the relay's child ${rel.child} fails the chain check: ${bad.join('; ')}"`)
      notes.push(`${row.id}: relay child ${rel.child} refused by the check (${bad.join('; ')})`)
      return { outcome: 'blocked on human', detail: bad.join('; ') }
    }
    const m = await move(row, inst, `block-on: blocked, waiting_on [${rel.child}], reason "relayed to ${c.to} as ${rel.child}"`)
    return { outcome: m && m.ok ? `relayed as ${rel.child}` : 'unfinished', detail: rel.result, notes: rel.notes }
  }
  const m = await move(row, inst, `block-human: blocked, waiting_on [human], reason "relay ${rel.decision}: ${rel.result}"`)
  return { outcome: 'blocked on human', detail: rel.result }
}

async function relayReturn(row, inst) {
  // mechanical: no relay agent. The child is closed by its sender (this instance), the
  // parent goes blocked -> in-progress -> delivered (blocked -> delivered is no transition)
  const m = await move(row, inst,
    'return-leg: tickets_get the ticket; its child is the id in waiting_on. tickets_get the child. If the child is delivered, ' +
    'move it closed (act as the child\'s from). Then move this ticket blocked -> in-progress -> delivered (deliver: true) with result ' +
    '"child <id> <its status>[; packets <ids>]"; a rejected or cancelled child is named as such.', `${row.id} return leg`)
  return { outcome: m && m.ok ? 'delivered (return leg)' : 'unfinished', detail: m ? m.detail : 'lost' }
}

async function expertClerk(row, inst) {
  const st = await move(row, inst, 'start: move it to in-progress')
  if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start' }
  let ans = await agent(`Answer ticket ${row.id} (tickets_get it): its ask, from the library and the registry. ` +
    `Begin your answer with ESCALATE if the library cannot answer it.`, { label: `clerk ${row.id}`, phase: 'Tickets', agentType: 'expert:clerk' })
  if (ans === null) return { lost: true }
  if (/^\s*ESCALATE/.test(ans)) {
    if ((row.budget_runs || 1) < 2) {
      await move(row, inst, `block-human: append the clerk's escalation to the thread, then blocked, waiting_on [human], reason "the escalation to the librarian needs budget.runs 2"`)
      return { outcome: 'blocked on human (budget)', detail: 'escalated' }
    }
    ans = await agent(`Ticket ${row.id} escalated by the clerk: ${ans}\nAnswer it as the librarian (look-ups the clerk escalated).`,
      { label: `librarian ${row.id}`, phase: 'Tickets', agentType: 'expert:librarian' })
    if (ans === null) return { lost: true }
  }
  const first = String(ans).trim().split('\n')[0].slice(0, 200).replace(/"/g, "'")
  const m = await move(row, inst, `deliver: deliver: true with result "${first}" and result_detail = the full answer:\n${ans}`)
  return { outcome: m && m.ok ? 'delivered' : 'unfinished', detail: first }
}

async function developerReviewed(row, i) {
  // the producer of code never grades it: developer, then test-engineer on the diff, the
  // findings back through the thread, at most budget.runs agent runs in all
  const st = await move(row, i.name, 'start: move it to in-progress')
  if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start' }
  const runs = Math.max(2, row.budget_runs || 2)
  let used = 0, verdict = ''
  while (used + 2 <= runs) {
    const d = await agent(`WORKFLOW INBOX: code ticket ${row.id} for ${i.name} (home ${i.home}); it is in-progress, make no status move. ` +
      (verdict ? `The test-engineer's findings on your last diff (also in the thread): ${verdict}\n` : '') +
      'Do it per your agent definition (test-first, in a worktree) and end with the diff\'s branch and commit.',
      { label: `developer ${row.id}${used ? ' (round ' + (used / 2 + 1) + ')' : ''}`, phase: 'Tickets', agentType: 'scientist:developer' })
    if (d === null) return { lost: true }
    const t = await agent(`WORKFLOW INBOX: review the developer's diff for code ticket ${row.id} (${i.name}, home ${i.home}): ${String(d).slice(-600)}\n` +
      'Review it per your agent definition and begin your answer with APPROVED or FINDINGS.',
      { label: `test-engineer ${row.id}`, phase: 'Tickets', agentType: 'scientist:test-engineer' })
    if (t === null) return { lost: true }
    used += 2
    verdict = String(t)
    await move(row, i.name, `note: append to the thread "test-engineer: ${verdict.split('\n')[0].slice(0, 200).replace(/"/g, "'")}"`, `${row.id} review note`)
    if (/^\s*APPROVED/.test(verdict)) {
      const m = await move(row, i.name, `deliver: deliver: true with result "code delivered, test-engineer APPROVED: ${String(d).split('\n')[0].slice(0, 120).replace(/"/g, "'")}"`)
      return { outcome: m && m.ok ? 'delivered' : 'unfinished', detail: 'approved' }
    }
  }
  await move(row, i.name, 'block-human: blocked, waiting_on [human], reason "the review still has findings and budget.runs is spent: asking for more runs"')
  return { outcome: 'blocked on human (budget)', detail: verdict.split('\n')[0] }
}

const firstRef = (row, re) => (row.refs || []).find(x => re.test(x)) || ''

async function handle(row, i) {
  const inst = i.name, rt = row.route || {}
  if (row.over_budget) {
    await move(row, inst, `block-human: blocked, waiting_on [human], reason "over budget: ${row.over_budget}; asking for the budget"`)
    return { outcome: 'blocked on human (budget)', detail: row.over_budget }
  }
  if (row.released) {
    const r = await move(row, inst, 'release: blocked -> accepted (everything it waited on is back)')
    if (!r || !r.ok) return { outcome: 'unfinished', detail: 'release failed' }
  }
  if (rt.how === 'reject') {
    await move(row, inst, `reject: rejected, with reason "${rt.why}"`)
    return { outcome: 'rejected', detail: rt.why }
  }
  if (rt.how === 'human') {
    if (i.role === 'author' || i.role === 'scientist')
      return { for_main: { why: `the ${i.role} puts a ticket with no route to the human (AskUserQuestion)`, ticket: row.id, instance: inst } }
    await move(row, inst, `block-human: blocked, waiting_on [human], reason "${rt.why}"`)
    return { outcome: 'blocked on human', detail: rt.why }
  }
  if (rt.how === 'research') return { for_main: { why: 'a self-ticket that needs an argument: the main session (the liaison) files the research ticket to the Expert and blocks this one on it', ticket: row.id, instance: inst } }
  if (RELAYS[rt.target]) return row.return ? relayReturn(row, inst) : relayForward(row, inst, RELAYS[rt.target])
  if (i.role === 'expert' && rt.target === 'clerk') return expertClerk(row, inst)
  // the experimenter's route is the experiment skill: its header is approved by the human
  if (i.role === 'scientist' && rt.target === 'experimenter')
    return { for_main: { why: 'an experiment or test ticket runs /scientist:experiment (the header is approved before any compute)', ticket: row.id, instance: inst, skill: 'scientist:experiment' } }
  if (i.role === 'scientist' && rt.target === 'developer') return developerReviewed(row, i)
  if (rt.how === 'skill' && NESTED[rt.target] && !NESTED_OK)
    return { for_main: { why: `the ${rt.target} workflow cannot nest inside this nested run`, ticket: row.id, instance: inst, skill: rt.target } }
  if (rt.how === 'skill' && NESTED[rt.target]) {
    if (rt.target === 'expert:cite') {
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { ticket: row.id })
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? [r.key, r.pinpoint, r.verdict].filter(Boolean).join(', ') || (r.reason || '') : 'lost', nested: r }
    }
    if (rt.target === 'researcher:explore') {
      const direction = firstRef(row, /^([a-z][a-z0-9]*:)?DIR-\d+$/)
      const r = await workflow({ scriptPath: NESTED[rt.target] }, Object.assign({ ticket: row.id, home: i.home, instance: inst, n: 1 },
        direction ? { direction: direction.split(':').pop() } : {}))
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.anomalies || []).concat(r.reason ? [r.reason] : []).join('; ') : 'lost', nested: r }
    }
    if (rt.target === 'researcher:generalize') {
      const ref = firstRef(row, /^P-\d{4,}$/) || firstRef(row, /^lab:\S+$/)
      if (!ref) return { for_main: { why: 'a generalize ticket whose refs name no report or lab claim', ticket: row.id, instance: inst } }
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { ref, ticket: row.id, home: i.home, instance: inst })
      if (r && r.to_file && r.to_file.length)
        return { for_main: { why: 'generalize: the main session files the falsifier tests (the liaison), then delivers with mode deliver', ticket: row.id, instance: inst, to_file: r.to_file } }
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.reason || '') : 'lost', nested: r }
    }
    if (rt.target === 'researcher:prove') {
      const claim = firstRef(row, /^[a-z][a-z0-9]*:\S+$/) || firstRef(row, /^[A-Z][A-Z0-9]*-\S+$/)
      if (!claim) return { for_main: { why: 'a prove ticket whose refs name no claim', ticket: row.id, instance: inst } }
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { claim, ticket: row.id, home: i.home, instance: inst })
      if (r && r.needs_explore) return { for_main: { why: 'the claim has no falsifier yet: run /researcher:explore first', ticket: row.id, instance: inst, skill: 'researcher:explore' } }
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.verify_ticket || r.reason || '') : 'lost', nested: r }
    }
    if (rt.target === 'expert:verify') {
      const claim = firstRef(row, /^[a-z][a-z0-9]*:\S+$/)
      if (!claim) return { for_main: { why: 'a verify ticket whose refs name no claim', ticket: row.id, instance: inst } }
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { claim, ticket: row.id })
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.proposed_status || '') : 'lost', nested: r }
    }
    const subject = firstRef(row, /^lab:\S+$/)
    if (!subject) return { for_main: { why: 'a review-experiment ticket whose refs name no lab claim', ticket: row.id, instance: inst } }
    const r = await workflow({ scriptPath: NESTED[rt.target] }, { subject, ticket: row.id, report: firstRef(row, /^P-\d+$/), mode: 'review' })
    if (r && r.outcome === 'needs-settle') return { for_main: { why: 'the report lists candidates: run /researcher:settle', ticket: row.id, instance: inst } }
    return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.notes || []).join('; ') : 'lost', nested: r }
  }
  if (rt.how === 'skill') return { for_main: { why: `the skill ${rt.target} runs in the main session`, ticket: row.id, instance: inst, skill: rt.target } }
  if (rt.how === 'agent') {
    const type = `${i.role}:${rt.target}`
    if (row.return) {
      const r = await agent(`WORKFLOW INBOX: the ticket ${row.id} came back delivered to ${inst} (home ${i.home}). Land its result as your agent definition says, then close it (tickets_update status closed).`,
        { label: `${rt.target} ${row.id} (land)`, phase: 'Tickets', agentType: type })
      return r === null ? { lost: true } : { outcome: 'landed', detail: String(r).split('\n')[0] }
    }
    const st = await move(row, inst, 'start: move it to in-progress' + (i.role === 'author' ? '; also return in detail the output of the Author home\'s pinned.py (the statements to leave byte for byte)' : ''))
    if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start: ' + (st ? st.detail : 'lost') }
    const r = await agent(
      `WORKFLOW INBOX: ticket ${row.id} for ${inst} (home ${i.home}); it is already in-progress, so make no move to accepted or in-progress. ` +
      `Work it per your agent definition (the claim is in refs, the agenda entry in agenda). ` +
      (i.role === 'author' ? `Pinned statements, to leave byte for byte: ${st.detail}\n` +
        (taken.length ? `Earlier tickets of this run: ${JSON.stringify(taken.map(t => [t.id, t.outcome, t.detail]))}\n` : '') : '') +
      `Finish by delivering it (tickets_update deliver: true, result one line) or, if you cannot, blocked with waiting_on and the reason.`,
      { label: `${rt.target} ${row.id}`, phase: 'Tickets', agentType: type })
    return r === null ? { lost: true } : { outcome: 'worked', detail: String(r).split('\n')[0] }
  }
  return { for_main: { why: `no workflow route for ${rt.how}:${rt.target}`, ticket: row.id, instance: inst } }
}

// ---- Tickets: serial, under one cap over the whole run ----------------------------------
phase('Tickets')
let count = 0
const closed = new Set()
outer:
for (const i of insts) {
  for (const row of i.rows) {
    if (count >= CAP) break outer
    if (closed.has(i.name)) break
    const res = await handle(row, i)
    if (res.for_main) { out.for_main = res.for_main; notes.push(`stopped for the main session at ${row.id}: ${res.for_main.why}`); break outer }
    count++
    if (res.lost) {
      taken.push({ instance: i.name, id: row.id, route: row.route, outcome: 'lost' })
      out.stopped = `an agent on ${row.id} returned nothing (a limit or an API error): nothing further launched (budget.md rule 4)`
      await move(row, i.name, 'note: append to the thread "interrupted: the workflow agent returned nothing; what was recorded is above"', `${row.id} interrupted`)
      break outer
    }
    const chk = await clerk('check', [`py ${ROOT}/${i.role}/scripts/inbox.py --instance ${i.name} --check ${row.id}`, 'Return its exit code, the ticket status and its output in detail.'], CHECK, `check ${row.id}`)
    const unfinished = !chk || chk.exit === 3
    if (unfinished) { closed.add(i.name); notes.push(`${row.id} is unfinished: nothing more from ${i.name} this run`) }
    taken.push({ instance: i.name, id: row.id, route: row.route, outcome: unfinished ? 'unfinished' : res.outcome, status: chk ? chk.status : '', detail: res.detail || '' })
  }
}

// ---- Close: the Author's delivered self-tickets ------------------------------------------
phase('Close')
for (const i of insts.filter(i => i.role === 'author' && taken.some(t => t.instance === i.name))) {
  await clerk('close-self', [`act as: ${i.name}`, 'Close (delivered -> closed) every delivered ticket whose from and to are both this instance; return how many.'], MOVE, `close ${i.name}`)
}
out.count = count
out.cap = CAP
if (insts.some(i => i.role === 'author') && taken.some(t => roleOf(t.instance) === 'author'))
  notes.push('Author: run check_paper.py from the home and relay its summary; launch tex-engineer once if an agent reported the build not clean')
return out
