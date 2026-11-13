export const meta = {
  name: 'academy-explore',
  description: 'Work one research direction forward, at most three items: the clerk picks them (notebook.py next), one lead-researcher moves each one step (falsify, prior art, prove), and the script checks the step against the board and the notebook',
  whenToUse: '/researcher:explore and every question ticket (also nested from the inbox), from the Researcher home. args: {direction?: "DIR-n", items?: [ids], ticket?: "T-NNNN", question?: "<the ask, for a question ticket without a direction>", home, instance, n?}',
  phases: [
    { title: 'Pick', detail: 'the direction and its next items' },
    { title: 'Move', detail: 'one lead-researcher run, one step per item' },
    { title: 'Check', detail: 'falsifier tickets, prove-after-falsify, the journal' },
  ],
}

// The order of /researcher:explore in code (2026-10-31; docs/workflows.md): the items come
// from notebook.py next (the direction's own order, at most three), the lead is briefed
// with ids only (nothing pasted in), each item moves one step in the order falsify, prior
// art, prove, and the script checks what the lead reports: a falsify step must have filed
// an experiment ticket to the Scientist naming the item, a prove step needs a falsifier
// that ran, and today's journal records the run. The lead's judgement stays its own.

const A = args || {}
if (!A.home) throw new Error('args.home must be the Researcher home')
if (!A.direction && !A.ticket) throw new Error('give args.direction, or args.ticket for a question')
const CLERK = 'researcher:review-clerk'
const LEAD = 'researcher:lead-researcher'
const CAP = Math.max(1, Math.min(A.n || 3, 3))
const T = A.ticket || ''
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const SCRIPTS = `Scripts: notebook.py is \`py ${AR}/researcher/scripts/notebook.py --home ${A.home}\` (python3 where there is no py)` +
  (ROOT ? '.\n' : '; <academy repo> is academy.root of the MCP tool workspace_get (academy.scripts.researcher is the scripts folder).\n')
const clerk = (stage, lines, schema, label, phase) => agent(
  `WORKFLOW STAGE ${stage} of the academy-explore workflow. Home: ${A.home}.` + (A.instance ? ` Instance: ${A.instance}.` : '') + '\n' + SCRIPTS + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const DIR = { type: 'object', properties: { exists: { type: 'boolean' }, lifecycle: { type: 'string' }, title: { type: 'string' }, items: { type: 'number' } }, required: ['exists', 'lifecycle', 'title', 'items'] }
const NEXT = { type: 'object', properties: { items: { type: 'array', items: { type: 'object', properties: { ref: { type: 'string' }, kind: { type: 'string' }, status: { type: 'string' } }, required: ['ref', 'kind', 'status'] } }, remaining: { type: 'number' } }, required: ['items', 'remaining'] }
const MOVED = { type: 'object', properties: { items: { type: 'array', items: { type: 'object', properties: {
  item: { type: 'string' }, step: { type: 'string', enum: ['falsify', 'prior-art', 'prove', 'none'] },
  tickets: { type: 'array', items: { type: 'string' } }, objects: { type: 'array', items: { type: 'string' } }, note: { type: 'string' } },
  required: ['item', 'step', 'tickets', 'objects', 'note'] } }, report: { type: 'string' }, next_picks: { type: 'array', items: { type: 'string' } } },
  required: ['items', 'report', 'next_picks'] }
const TICKET = { type: 'object', properties: { found: { type: 'boolean' }, to: { type: 'string' }, kind: { type: 'string' }, refs: { type: 'array', items: { type: 'string' } } }, required: ['found', 'to', 'kind', 'refs'] }
const FALS = { type: 'object', properties: { falsified: { type: 'boolean' }, evidence: { type: 'string' } }, required: ['falsified', 'evidence'] }
const JOURNAL = { type: 'object', properties: { exists: { type: 'boolean' }, path: { type: 'string' }, mentions: { type: 'array', items: { type: 'string' }, description: 'the item ids today\'s journal mentions' } }, required: ['exists', 'path', 'mentions'] }
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok', 'detail'] }

// ---- Ship (docs/workflows.md, "Shipping is a step of the workflow"): the same block in every
// workflow that writes. Standalone only (a nested run's parent ships), run once, never retried. A
// finished ticket gets the inbox's own scoped checkpoint (inbox.py --check, which honours
// "shipCheckpoint": false); anything else is not-run, with the command for the session.
const SHIP = { type: 'object', properties: { status: { type: 'string', enum: ['pushed', 'nothing', 'refused', 'not-run'] }, detail: { type: 'string' },
  branches: { type: 'array', items: { type: 'string' } }, output: { type: 'string', description: 'the whole output, stdout and stderr, verbatim' } },
  required: ['status', 'detail', 'branches', 'output'] }
async function ship(s) {   // {role, ticket, done, instance, topic, only, agentType, phase, notes}
  if (!s.ticket) return { status: 'not-run', detail: 'no ticket: run the command from the workspace root (unless workspace.json says "shipCheckpoint": false)',
    command: `py scripts/ship.py checkpoint --ticket ${String(s.topic).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')} --role ${s.role} --only ${s.only}` }
  const check = `py ${AR}/${s.role}/scripts/inbox.py${s.instance ? ' --instance ' + s.instance : ''} --check ${s.ticket}`
  if (!s.done) return { status: 'not-run', detail: `${s.ticket} is not finished: its checkpoint runs once it is (as in the inbox)`, command: check }
  const r = await agent(`WORKFLOW STAGE ship. Run \`${check} 2>&1\` once, from the home` + (ROOT ? '' : ' (<academy repo> is academy.root of the MCP tool workspace_get)') +
    '. Never run it again and fix nothing, whatever it prints: return its whole output verbatim.', { label: 'ship', phase: s.phase, agentType: s.agentType, schema: SHIP, effort: 'low' })
  const lines = String(r ? r.output : '').split(/\r?\n/)
  const m = lines.map(l => new RegExp('^' + s.ticket + ': (\\S+) \\(').exec(l)).find(Boolean)
  const rows = lines.map(l => /^(\S+) (\S+) @ \S+ \(\d+ files\) (.*)$/.exec(l)).filter(Boolean)
  const bad = lines.find(l => /REFUSED|PUSH FAILED|checkpoint incomplete|checkpoint for \S+ (exited [1-9]|timed out|could not start|failed)/.test(l))
  const skipped = lines.find(l => /checkpoint not run/.test(l))
  const branches = rows.filter(x => /^pushed/.test(x[3])).map(x => x[1] + ' ' + x[2])
  const res = !r ? { status: 'not-run', detail: 'the ship stage returned nothing' }
    : m && !/^(delivered|rejected)$/.test(m[1]) ? { status: 'not-run', detail: `${s.ticket} is ${m[1]}: no checkpoint for an unfinished ticket` }
    : bad ? { status: 'refused', detail: bad.trim() }
    : skipped ? { status: 'not-run', detail: skipped.trim() }
    : branches.length ? { status: 'pushed', detail: `pushed ${branches.join(', ')}`, branches }
    : rows.length ? { status: 'nothing', detail: 'nothing to commit or push' }
    : m ? { status: 'not-run', detail: 'no checkpoint ran ("shipCheckpoint": false, another board, or no ship script)' }
    : { status: r.status, detail: r.detail }
  if (!/^(pushed|nothing)$/.test(res.status)) res.command = check
  if (res.status === 'refused' && s.notes) s.notes.push(`the ship stage was refused (${res.detail}); fix the cause, then run \`${check}\` once by hand`)
  return res
}

const out = { direction: A.direction || null, ticket: T || null, notes: [], anomalies: [] }

// ---- Pick ---------------------------------------------------------------------------------
phase('Pick')
if (T) {
  const s = await clerk('start', [`Take ${T}: open -> accepted -> in-progress (leave an in-progress ticket as it is).`], MOVE, 'start', 'Pick')
  if (!s || !s.ok) return Object.assign(out, { outcome: 'not-started', reason: s ? s.detail : 'the start stage returned nothing' })
}
let picks = []
if (A.direction) {
  let d = await clerk('direction', [`Return notebook.py direction ${A.direction} --json: whether it exists, its lifecycle, title and the number of items. Write nothing.`], DIR, 'direction', 'Pick')
  if (d && !d.exists) {
    const f = await agent(SCRIPTS + `The direction ${A.direction} has no object yet (home ${A.home}). Create it (notebook.py new direction ${A.direction} --title "...") ` +
      'and fill its program and its lists (questions, candidate claims with falsifiers) from what the notebook holds; work no item yet. Report what you wrote.',
      { label: 'fill direction', phase: 'Pick', agentType: LEAD })
    if (f === null) return Object.assign(out, { outcome: 'lost', reason: 'the lead run that fills the direction returned nothing' })
    out.notes.push(`the direction ${A.direction} was created and filled first`)
    d = await clerk('direction', [`Return notebook.py direction ${A.direction} --json again.`], DIR, 'direction again', 'Pick')
  }
  if (!d || !d.exists) return Object.assign(out, { outcome: 'not-started', reason: `no direction ${A.direction}` })
  if (d.lifecycle !== 'active') return Object.assign(out, { outcome: 'not-started', reason: `the direction is ${d.lifecycle}` })
  const n = await clerk('next', [`Return notebook.py next ${A.direction} --n ${CAP} --json as {ref, kind, status} per item, and how many unsettled items remain after these.`], NEXT, 'next', 'Pick')
  picks = (n ? n.items : []).map(x => x.ref)
  if (A.items && A.items.length) picks = picks.filter(p => A.items.some(i => p === i || p.endsWith(':' + i))).slice(0, CAP)
  out.remaining = n ? n.remaining : null
  if (!picks.length) return Object.assign(out, { outcome: 'nothing-to-do', reason: 'notebook.py next gives no unsettled item' })
}
out.picked = picks

// ---- Move: one lead, ids only --------------------------------------------------------------
phase('Move')
const lead = await agent(
  SCRIPTS + (A.direction ? `Work direction ${A.direction} (home ${A.home}), items ${picks.join(', ')}.` :
    `Answer the question ticket ${T} (home ${A.home}) as a one-item run; read it with tickets_get.`) +
  ' Move each item ONE step, in this order: falsify (a candidate claim gets its smallest falsifier: you file the experiment ticket to the Scientist, ' +
  'a probe for one named example, a search for a family or a range, with the claim id, what refutes it, a validation case and the unsettled inputs); ' +
  'prior art (prover\'s scout pass, lookup / cite tickets to the Expert); prove (only an item that survived falsification and has no prior proof: ' +
  'prover writes an attempt, and /researcher:prove files the review). Update the direction\'s lists and today\'s journal (notebook.py journal --create); ' +
  'new questions or claims become unsettled objects. Return per item the step, the tickets filed and the objects made, your report, and what the next run would pick.',
  { label: 'lead', phase: 'Move', agentType: LEAD, schema: MOVED })
if (lead === null) return Object.assign(out, { outcome: 'lost', reason: 'the lead run returned nothing (a limit?): nothing further launched' })
out.items = lead.items
out.report = lead.report
out.next_picks = lead.next_picks

// ---- Check: against the board and the notebook ------------------------------------------------
phase('Check')
const seen = {}
for (const it of lead.items || []) {
  seen[it.item] = (seen[it.item] || 0) + 1
  if (seen[it.item] > 1) out.anomalies.push(`${it.item} was moved more than one step`)
  if (A.direction && !picks.some(p => p === it.item || p.endsWith(':' + it.item) || it.item.endsWith(':' + p.split(':').pop())))
    out.anomalies.push(`${it.item} was not one of the picked items`)
  if (it.step === 'falsify') {
    if (!it.tickets.length) { out.anomalies.push(`${it.item}: a falsify step without an experiment ticket`); continue }
    for (const tid of it.tickets) {
      const t = await clerk('get', [`tickets_get ${tid} and return its to, kind and refs.`], TICKET, `get ${tid}`, 'Check')
      const short = it.item.split(':').pop()
      if (!t || !t.found || !/^scientist@/.test(t.to) || t.kind !== 'experiment' || !(t.refs || []).some(r => r === it.item || r.endsWith(':' + short) || r === short))
        out.anomalies.push(`${it.item}: the falsifier ticket ${tid} is not an experiment ticket to the Scientist naming the item`)
    }
  }
  if (it.step === 'prove') {
    const f = await clerk('falsified', [`Did a falsifier run on ${it.item} before this run (a reviewed or reported experiment, a probe report, or a direction item that records it)? Return falsified and the evidence. Write nothing.`],
      FALS, `falsified ${it.item}`, 'Check')
    if (!f || !f.falsified) out.anomalies.push(`${it.item}: moved to prove with no falsifier on record`)
  }
}
const j = await clerk('journal', ['Return whether today\'s journal file exists (notebook.py journal shows its path), its path, and which of these ids it mentions: ' + (lead.items || []).map(i => i.item).join(', ') + '. Write nothing.'],
  JOURNAL, 'journal', 'Check')
if (!j || !j.exists) out.notes.push('today\'s journal does not exist: the lead did not record the run')
else if ((lead.items || []).some(i => i.step !== 'none' && !j.mentions.includes(i.item))) out.notes.push('today\'s journal does not mention every item moved')

if (T) {
  const steps = (lead.items || []).map(i => `${i.item}: ${i.step}${i.tickets.length ? ' (' + i.tickets.join(', ') + ')' : ''}`).join('; ')
  const m = await clerk('close', [`Deliver ${T} (tickets_update deliver: true) with result "${(steps || lead.report.split('\n')[0]).replace(/"/g, "'").slice(0, 240)}".`], MOVE, 'close', 'Check')
  out.ticket_delivered = !!(m && m.ok)
}
out.outcome = out.anomalies.length ? 'moved (with anomalies)' : 'moved'
if (!A.nested) out.ship = await ship({ role: 'researcher', ticket: T, done: !!out.ticket_delivered, instance: A.instance, topic: 'explore-' + (A.direction || ''),
  only: '<home submodule> board', agentType: CLERK, phase: 'Check', notes: out.notes })
return out
