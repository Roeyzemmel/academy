export const meta = {
  name: 'academy-explore',
  description: 'Work one research direction forward, at most three items: the clerk picks them (notebook.py next), one lead-researcher moves each one step in prove\'s order (prior art, then prove, handed back to the main session; a falsifier only after a failed attempt or a GAP), and the script checks the step against the board and the notebook',
  whenToUse: '/researcher:explore and every question ticket (also nested from the inbox), from the Researcher home. args: {direction?: "DIR-n", items?: [ids], ticket?: "T-NNNN", question?: "<the ask, for a question ticket without a direction>", home, instance, n?}',
  phases: [
    { title: 'Pick', detail: 'the direction and its next items' },
    { title: 'Move', detail: 'one lead-researcher run, one step per item' },
    { title: 'Check', detail: 'the prove hand-back, a falsifier only after an attempt, the journal, the artefacts' },
  ],
}

// The order of /researcher:explore in code (2026-10-31; docs/workflows.md): the items come
// from notebook.py next (the direction's own order, at most three), the lead is briefed
// with ids only (nothing pasted in), and each item moves one step. The steps are prove's
// order (the human's ruling of 2026-11-20, #87): prior art, then prove, and a falsifier only
// after an attempt failed or came back incomplete, or a proof got a GAP verdict; never
// before an attempt. The script checks what the lead reports:
//  * prove: the lead cannot launch prover inside this run (an agent has no Agent or Workflow
//    tool, T-1271), so the claim is checked (registry.py statement) and /researcher:prove
//    goes to the main session as for_main with its args, exactly as the inbox hands back a
//    lead (handback: lead-researcher); the ticket stays in-progress and prove.js delivers it;
//  * falsify: the attempt or verify ticket that triggered it is read (a failed or incomplete
//    attempt, or a GAP verdict), and the ticket must be an experiment to the Scientist
//    naming the item; one filed before an attempt is an anomaly and no artefact;
//  * today's journal records the run, and the artefacts the lead names exist;
//  * a ticket is delivered only on an artefact (a ticket filed, a direction item or object
//    updated or made, an attempt path), and its result names them (#87: T-1668 was
//    delivered with nothing behind it); with none it stays in-progress with a thread note.
// No clerk schema of this file requires free text (detail, why, error, reason): a missing
// detail gets a default where it is read (the shared SHIP block aside, pinned identical).
// The lead's judgement stays its own.

const A = args || {}

// ---- Models (docs/workflows.md, "Models"): the same block in every workflow. The skill
// that runs the workflow passes args.models, the JSON object `models.py launches` prints:
// the agents whose tier this workspace maps away from their file's model: line, and each
// such tier as "tier:<tier>". Every agent is launched through launch(): an agent the map
// names gets its workspace model; an agent with no academy file (general-purpose) is
// given a tier, never a model (launch(p, {agentType, tier: 'medium'})). Scripts name no
// model. Nested workflows get the same map (models: await modelsMap()).
// Given and not given differ (#83). Given (a JSON object, or its JSON text), the map stands,
// {} included: {} is what models.py launches prints when the workspace maps nothing away, so
// it means "no override". Not given (absent or null), the run's first launch() resolves it
// first: one general-purpose stage at tier base runs models.py launches, once per run.
// Anything else given, or a stage that returns no JSON object, throws, naming the command.
const TIER_MODELS = {}
const MODELS = { source: null, ready: null }   // source: 'args' | 'resolved'
const MODELS_PY = `${A.root ? String(A.root).replace(/[\\/]+$/, '') : '<academy repo>'}/academy/scripts/models.py launches`
const MODELS_CMD = `py ${MODELS_PY}`   // python3 where there is no py (the stage is told)
const MODELS_OUT = { type: 'object', properties: { output: { type: 'string', description: 'the command output, verbatim' } }, required: ['output'] }
const modelsRefused = why => new Error(`args.models ${why}: rerun with args.models = the JSON object \`${MODELS_CMD}\` prints` +
  ' ({} when it prints {}: no override)' + (A.root ? '' : '; <academy repo> is academy.root of the MCP tool workspace_get'))
const modelsRead = (v, loose) => {   // a JSON object (or its text) into TIER_MODELS; null when it is none
  if (typeof v === 'string') {
    // loose: the stage's output may sit in a code fence, nothing else: a paraphrase or a map
    // inside prose is refused, never guessed (review of abf478f)
    const t = loose ? v.trim().replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '') : v
    try { v = JSON.parse(t) } catch (e) { return null }
  }
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null
  for (const k of Object.keys(v)) if (typeof v[k] === 'string') TIER_MODELS[k] = v[k]
  return TIER_MODELS
}
if (A.models !== undefined && A.models !== null) {
  if (!modelsRead(A.models, false)) throw modelsRefused(`is no JSON object (${String(JSON.stringify(A.models)).slice(0, 80)})`)
  MODELS.source = 'args'
}
const modelsMap = () => MODELS.ready || (MODELS.ready = (async () => {
  if (MODELS.source) return TIER_MODELS
  const r = await launchOnce(`WORKFLOW STAGE models. Run \`${MODELS_CMD}\` once (\`python3 ${MODELS_PY}\` where there is no py)` +
    (A.root ? '' : ' (<academy repo> is academy.root of the MCP tool workspace_get)') +
    '. Fix nothing, whatever it prints: return its whole output verbatim.',
  { label: 'models', agentType: 'general-purpose', tier: 'base', schema: MODELS_OUT, effort: 'low' })
  if (r === null) {     // a usage limit at the start: the run stops as on three null launches (#115), it does not throw
    LAUNCH_LIMIT.nulls = 3
    LAUNCH_LIMIT.stopped = true
    MODELS.ready = null
    return null
  }
  const w = String((r && r.output) || '').trim()
  if (!modelsRead(w, true)) throw modelsRefused('was not given, and the models stage ' + (r ? `printed no JSON object (${JSON.stringify(w.slice(0, 160))})` : 'returned nothing'))
  MODELS.source = 'resolved'
  return TIER_MODELS
})())
const TIER_DEFAULTS = { base: 'haiku', medium: 'sonnet', large: 'opus', max: 'opus' }
// Three launches in a row that return nothing (a usage limit: every launch fails until the
// reset, #115; two can be one lost run and its fallback, whose record still runs) stop the run: launch() then launches nothing and returns null at once, so
// each caller's "returned nothing" path ends it; LAUNCH_LIMIT.stopped tells the result.
const LAUNCH_LIMIT = { nulls: 0, stopped: false }
const launch = async (prompt, opts) => {
  // record: true is the stage that writes down what came back: tried even after a stop
  // (litwatch's record after three lost scouts of a fan-out; review of aeba1f4)
  const rec = !!(opts && opts.record)
  if (rec) { opts = Object.assign({}, opts); delete opts.record }
  if (LAUNCH_LIMIT.stopped && !rec) return null
  if (!MODELS.source && !(await modelsMap())) return null   // the lookup returned nothing: stopped
  const r = await launchOnce(prompt, opts)
  if (r === null) { if (++LAUNCH_LIMIT.nulls >= 3) LAUNCH_LIMIT.stopped = true } else LAUNCH_LIMIT.nulls = 0
  return r
}
const launchOnce = (prompt, opts) => {
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k)
  const mapped = k => has(TIER_MODELS, k) && typeof TIER_MODELS[k] === 'string' && TIER_MODELS[k] ? TIER_MODELS[k] : null
  const t = opts && opts.agentType
  const m = t ? mapped(t) : null
  if (opts && has(opts, 'tier')) {
    if (!has(TIER_DEFAULTS, opts.tier)) throw new Error('launch: unknown tier ' + JSON.stringify(opts.tier))
    const o = Object.assign({}, opts, { model: m || mapped('tier:' + opts.tier) || TIER_DEFAULTS[opts.tier] })
    delete o.tier
    return agent(prompt, o)
  }
  if (opts && opts.exactModel) {   // the max-tier block's resolved model (or its fallback): it stands
    const o = Object.assign({}, opts, { model: opts.exactModel })
    delete o.exactModel
    return agent(prompt, o)
  }
  return agent(prompt, m ? Object.assign({}, opts, { model: m }) : opts)
}
// ---- end Models
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
const clerk = (stage, lines, schema, label, phase) => launch(
  `WORKFLOW STAGE ${stage} of the academy-explore workflow. Home: ${A.home}.` + (A.instance ? ` Instance: ${A.instance}.` : '') + '\n' + SCRIPTS + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const DIR = { type: 'object', properties: { exists: { type: 'boolean' }, lifecycle: { type: 'string' }, title: { type: 'string' }, items: { type: 'number' } }, required: ['exists', 'lifecycle', 'items'] }
const NEXT = { type: 'object', properties: { items: { type: 'array', items: { type: 'object', properties: { ref: { type: 'string' }, kind: { type: 'string' }, status: { type: 'string' } }, required: ['ref', 'kind', 'status'] } }, remaining: { type: 'number' } }, required: ['items', 'remaining'] }
const MOVED = { type: 'object', properties: { items: { type: 'array', items: { type: 'object', properties: {
  item: { type: 'string' }, step: { type: 'string', enum: ['prior-art', 'prove', 'falsify', 'none'] },
  tickets: { type: 'array', items: { type: 'string' }, description: 'the ticket ids you filed for this item' },
  objects: { type: 'array', items: { type: 'string' }, description: 'the notebook objects you made (ids)' },
  updated: { type: 'array', items: { type: 'string' }, description: 'the notebook files you updated, home-relative (the direction object, objects/direction/DIR-n.md); not the journal' },
  claim: { type: 'string', description: 'step prove: the registry id (<ns>:<id>) prover is to attempt; else empty' },
  after: { type: 'string', description: 'step falsify: the failed or incomplete attempt (proofs/<id>/attempt-<n>.md) or the verify ticket with the GAP verdict that calls for it; else empty' },
  note: { type: 'string' } },
  required: ['item', 'step', 'tickets', 'objects', 'updated', 'claim', 'after', 'note'] } }, report: { type: 'string' }, next_picks: { type: 'array', items: { type: 'string' } } },
  required: ['items', 'report', 'next_picks'] }
const TICKET = { type: 'object', properties: { found: { type: 'boolean' }, to: { type: 'string' }, kind: { type: 'string' }, refs: { type: 'array', items: { type: 'string' } } }, required: ['found', 'to', 'kind', 'refs'] }
const JOURNAL = { type: 'object', properties: { exists: { type: 'boolean' }, path: { type: 'string' }, mentions: { type: 'array', items: { type: 'string' }, description: 'the item ids today\'s journal mentions' },
  found: { type: 'array', items: { type: 'string' }, description: 'of the artefacts listed, those that exist, verbatim: a ticket tickets_get finds, a file under the home, an object notebook.py finds' } },
  required: ['exists', 'path', 'mentions', 'found'] }
const TRIGGER = { type: 'object', properties: { exists: { type: 'boolean' }, kind: { type: 'string', enum: ['attempt', 'verdict', 'other'] },
  outcome: { type: 'string', description: 'an attempt: its frontmatter\'s outcome: field, verbatim; else empty' },
  gaps: { type: 'number', description: 'an attempt: how many gaps it lists' },
  falsifying_gaps: { type: 'number', description: 'an attempt: how many of its Gaps items are fix-unclear or needs-assumption (#126: the item\'s tag, else your reading; resting on a registry statement is fix-known)' },
  verdict: { type: 'string', enum: ['CONFIRMED', 'PLAUSIBLE', 'GAP', 'DISPROVED', ''], description: 'a verify ticket or review: the verdict it reports; else empty' } },
  required: ['exists', 'kind', 'outcome', 'gaps', 'verdict'] }
const REG = { type: 'object', properties: { exit: { type: 'number', description: 'the exit code as printed by the shell' },
  output: { type: 'string', description: 'the command output, verbatim' } }, required: ['exit', 'output'] }
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok'] }
const CLAIM_ID = /^([a-z][a-z0-9]*:)?[A-Za-z][\w.:-]*$/             // prove.js's own check of args.claim
const TICKET_ID = /^T-\d+$/
const oneLine = (x, n) => String(x || '').replace(/\s+/g, ' ').trim().replace(/"/g, "'").slice(0, n || 200)

// ---- Ship (docs/workflows.md, "Shipping is a step of the workflow"): the same block in every
// workflow that writes. Standalone only (a nested run's parent ships), run once, never retried. A
// finished ticket gets the inbox's own scoped checkpoint (inbox.py --check, which honours
// "shipCheckpoint": false); anything else is not-run, with the command for the session.
const SHIP = { type: 'object', properties: { status: { type: 'string', enum: ['pushed', 'nothing', 'refused', 'not-run'] }, detail: { type: 'string' },
  branches: { type: 'array', items: { type: 'string' } }, output: { type: 'string', description: 'the whole output, stdout and stderr, verbatim' } },
  required: ['status', 'output'] }     // detail and branches: asked, defaulted below (#124: no free-text field required)
async function ship(s) {   // {role, ticket, done, instance, topic, only, agentType, phase, notes}
  // #136 item 4: without a ticket the run ships its slug's branch through inbox.py --ship-slug,
  // under --check's guards and scope (never a direct ship.py checkpoint, which bypasses them)
  const slug = String(s.topic).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  const id = s.ticket || slug
  const inbox = `py ${AR}/${s.role}/scripts/inbox.py${s.instance ? ' --instance ' + s.instance : ''}`
  const check = s.ticket ? `${inbox} --check ${s.ticket}` : `${inbox} --ship-slug ${slug}`
  if (s.ticket && !s.done) return { status: 'not-run', detail: `${s.ticket} is not finished: its checkpoint runs once it is (as in the inbox)`, command: check }
  const r = await launch(`WORKFLOW STAGE ship. Run \`${check} 2>&1\` once, from the home` + (ROOT ? '' : ' (<academy repo> is academy.root of the MCP tool workspace_get)') +
    '. Never run it again and fix nothing, whatever it prints: return its whole output verbatim.', { label: 'ship', phase: s.phase, agentType: s.agentType, schema: SHIP, effort: 'low' })
  const lines = String(r ? r.output : '').split(/\r?\n/)
  const m = lines.map(l => new RegExp('^' + id + ': (\\S+) \\(').exec(l)).find(Boolean)
  const rows = lines.map(l => /^(\S+) (\S+) @ \S+ \(\d+ files\) (.*)$/.exec(l)).filter(Boolean)
  const bad = lines.find(l => /REFUSED|PUSH FAILED|checkpoint incomplete|checkpoint for \S+ (exited [1-9]|timed out|could not start|failed)/.test(l))
  const skipped = lines.find(l => /checkpoint not run/.test(l))
  const branches = rows.filter(x => /^pushed/.test(x[3])).map(x => x[1] + ' ' + x[2])
  const res = !r ? { status: 'not-run', detail: 'the ship stage returned nothing' }
    : m && !/^(delivered|rejected|partial)$/.test(m[1]) ? { status: 'not-run', detail: `${id} is ${m[1]}: no checkpoint for an unfinished ticket` }
    : bad ? { status: 'refused', detail: bad.trim() }
    : skipped ? { status: 'not-run', detail: skipped.trim() }
    : branches.length ? { status: 'pushed', detail: `pushed ${branches.join(', ')}`, branches }
    : rows.length ? { status: 'nothing', detail: 'nothing to commit or push' }
    : m ? { status: 'not-run', detail: 'no checkpoint ran ("shipCheckpoint": false, another board, or no ship script)' }
    : { status: r.status || 'not-run', detail: r.detail || 'no detail given' }
  if (!/^(pushed|nothing)$/.test(res.status)) res.command = check
  if (res.status === 'refused' && s.notes) s.notes.push(`the ship stage was refused (${res.detail}); fix the cause, then run \`${check}\` once by hand`)
  return res
}

const out = { direction: A.direction || null, ticket: T || null, notes: [], anomalies: [] }

// ---- Pick ---------------------------------------------------------------------------------
phase('Pick')
if (T) {
  const s = await clerk('start', [`Take ${T}: open -> accepted -> in-progress (leave an in-progress ticket as it is).`], MOVE, 'start', 'Pick')
  if (!s || !s.ok) return Object.assign(out, { outcome: 'not-started', reason: s ? (s.detail || 'the start stage did not take the ticket') : 'the start stage returned nothing' })
}
let picks = []
if (A.direction) {
  let d = await clerk('direction', [`Return notebook.py direction ${A.direction} --json: whether it exists, its lifecycle, title and the number of items. Write nothing.`], DIR, 'direction', 'Pick')
  if (d && !d.exists) {
    const f = await launch(SCRIPTS + `The direction ${A.direction} has no object yet (home ${A.home}). Create it (notebook.py new direction ${A.direction} --title "...") ` +
      'and fill its program and its lists (questions, candidate claims) from what the notebook holds; work no item yet. Report what you wrote.',
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
const lead = await launch(
  SCRIPTS + (A.direction ? `Work direction ${A.direction} (home ${A.home}), items ${picks.join(', ')}.` :
    `Answer the question ticket ${T} (home ${A.home}) as a one-item run; read it with tickets_get.`) +
  ' Move each item ONE step, in the order of /researcher:prove (the human\'s ruling of 2026-11-20): ' +
  'prior art first (prover\'s scout pass, lookup / cite tickets to the Expert) for an item whose literature is not checked yet; ' +
  'then prove (an item with no proof attempt, or one to repair): the attempt does not wait for a falsifier. You run inside a workflow and cannot launch prover ' +
  'or run /researcher:prove: make sure the item is a registry claim of this instance (a question that names none: register it with claims_new, status open, ' +
  'the statement as asked), write the prover brief in today\'s journal, file no ticket for the attempt, and return step prove with the claim id; ' +
  `the workflow hands /researcher:prove <claim>${T ? ' with ticket ' + T : ''} to the main session, which delivers ${T ? 'the ticket' : 'the attempt'}. ` +
  'Only then falsify: an item whose attempt (proofs/<id>/attempt-<n>.md) failed, or came back incomplete with a gap whose fix is unclear or that needs a new hypothesis in the statement ' +
  '(tagged [fix-unclear] or [needs-assumption]; never for [fix-known] gaps, an undeclared dependencies list, or an attempt complete modulo unreviewed inputs, #126), or whose proof got a GAP verdict, and that has no ' +
  'falsifier on record or pending, gets its smallest falsifier (you file the experiment ticket to the Scientist: a probe for one named example, a search for a family ' +
  'or a range, with the claim id, what refutes it, a validation case and the unsettled inputs), and after names that attempt or verify ticket; ' +
  'never file a falsifier for an item with no such attempt and no GAP verdict. ' +
  'Update the direction\'s lists and today\'s journal (notebook.py journal --create); new questions or claims become unsettled objects. ' +
  'Return per item the step, the tickets filed, the objects made, the notebook files updated, the claim (step prove) and after (step falsify); ' +
  'your report, and what the next run would pick.',
  { label: 'lead', phase: 'Move', agentType: LEAD, schema: MOVED })
if (lead === null) return Object.assign(out, { outcome: 'lost', reason: 'the lead run returned nothing (a limit?): nothing further launched' })
const moved = (lead.items || []).map(i => Object.assign({ tickets: [], objects: [], updated: [], claim: '', after: '' }, i))
out.items = moved
out.report = lead.report
out.next_picks = lead.next_picks

// ---- Check: against the board and the notebook ------------------------------------------------
phase('Check')
const seen = {}
const art = { tickets: [], objects: [], files: [] }   // what a delivery may name, in this order
const add = (k, x) => {
  x = String(x || '').trim()
  if (k === 'tickets' && !TICKET_ID.test(x)) { if (x) out.notes.push(`${x} is no ticket id (T-NNNN): not counted as an artefact`); return }
  if (k === 'tickets' && T && x === T) { out.notes.push(`${x} is the ticket itself: not counted as an artefact`); return }   // review of 1bbcc77
  if (x && !art[k].includes(x)) art[k].push(x)
}
const prove = []                      // {claim} | {claim, why}: the prove steps to hand back
const incomplete = []                 // #100: items whose falsifier followed an attempt not complete
for (const it of moved) {
  seen[it.item] = (seen[it.item] || 0) + 1
  if (seen[it.item] > 1) out.anomalies.push(`${it.item} was moved more than one step`)
  if (A.direction && !picks.some(p => p === it.item || p.endsWith(':' + it.item) || it.item.endsWith(':' + p.split(':').pop())))
    out.anomalies.push(`${it.item} was not one of the picked items`)
  it.objects.forEach(x => add('objects', x))
  it.updated.forEach(x => add('files', x))
  if (it.step === 'prove') {
    const claim = String(it.claim || '').trim()
    if (it.tickets.length) out.notes.push(`${it.item}: the prove step filed ${it.tickets.join(', ')} (a proof attempt files nothing before it runs)`)
    if (!CLAIM_ID.test(claim)) {
      out.anomalies.push(`${it.item}: the prove step names no registry claim${claim ? ' (' + claim + ')' : ''}`)
      prove.push({ item: it.item, claim, why: `${it.item} needs a proof attempt and names no registry claim: register the statement (claims_new${A.instance ? ' in ' + A.instance : ''}), then run /researcher:prove <claim>` })
      continue
    }
    const reg = await clerk('claim', [`From ${A.home} run \`py ${AR}/academy/scripts/registry.py statement ${claim}\` once (python3 where there is no py). ` +
      'Return the exit code the shell printed and the output verbatim. Write nothing.'], REG, `claim ${claim}`, 'Check')
    if (!reg) return Object.assign(out, { outcome: 'lost', reason: `the registry check of ${claim} returned nothing (a limit?): nothing further launched` })
    if (/does not resolve/.test(String(reg.output || '')) || reg.exit !== 0) {
      out.anomalies.push(`${it.item}: the claim ${claim} does not resolve in the registry (exit ${reg.exit})`)
      prove.push({ item: it.item, claim, why: `${it.item} needs a proof attempt, but ${claim} does not resolve (registry.py statement exit ${reg.exit}: ${oneLine(reg.output, 120)}): ` +
        `run registry.py statement ${claim} from the main session; register it (claims_new) only if that reports it missing, then run /researcher:prove ${claim}` })
      continue
    }
    prove.push({ item: it.item, claim })
    continue
  }
  if (it.step === 'falsify') {
    // never before an attempt: the attempt or verify ticket named in after must have failed, be incomplete, or carry a GAP
    const trig = String(it.after || '').trim()
    const tr = trig ? await clerk('trigger', [`Read ${trig} (an attempt file under the home, or a verify ticket with tickets_get): ` +
      'whether it exists; for an attempt, its frontmatter\'s outcome: field verbatim, how many gaps it lists and how many of them are fix-unclear or needs-assumption (falsifying_gaps: the item\'s tag, else your reading; ' +
      'resting on a registry statement is fix-known, "None" is no gap); for a verify ticket or review, the verdict it reports. Write nothing.'],
      TRIGGER, `trigger ${it.item}`, 'Check') : null
    if (trig && !tr) return Object.assign(out, { outcome: 'lost', reason: `the trigger check of ${it.item} returned nothing (a limit?): nothing further launched` })
    // #126: an attempt triggers one only when failed or with a fix-unclear / needs-assumption gap
    // (a clerk answer without the count falls back to the gap count, read conservatively)
    // a clerk answer without the count: read as none, with an anomaly for the human (the raw
    // gap count would count a "None." item: review of c4cde59, finding 3)
    const fKnown = typeof tr?.falsifying_gaps === 'number'
    const fGaps = fKnown ? tr.falsifying_gaps : 0
    if (tr && tr.exists && tr.kind === 'attempt' && !fKnown && tr.outcome !== 'failed') {
      out.anomalies.push(`${it.item}: the trigger check of ${trig} did not report falsifying_gaps: read as none (#126); the human decides whether the falsifier stays`)
    }
    const afterAttempt = !!tr && tr.exists && ((tr.kind === 'attempt' && (tr.outcome === 'failed' || fGaps > 0)) || tr.verdict === 'GAP')
    if (!afterAttempt) {
      out.anomalies.push(`${it.item}: a falsifier filed before an attempt (${trig ? trig + ' is no failed attempt, has no fix-unclear or needs-assumption gap (#126) and is no GAP verdict' : 'no attempt or GAP verdict named'}): ` +
        `${it.tickets.join(', ') || 'no ticket'}; the human decides whether it stays`)
      continue
    }
    if (!it.tickets.length) { out.anomalies.push(`${it.item}: a falsify step without an experiment ticket`); continue }
    if (tr.kind === 'attempt') incomplete.push(`${it.item} (${trig} ${tr.outcome || 'without outcome'})`)
    for (const tid of it.tickets) {
      const t = await clerk('get', [`tickets_get ${tid} and return its to, kind and refs.`], TICKET, `get ${tid}`, 'Check')
      const short = it.item.split(':').pop()
      if (!t || !t.found || !/^scientist@/.test(t.to) || t.kind !== 'experiment' || !(t.refs || []).some(r => r === it.item || r.endsWith(':' + short) || r === short))
        out.anomalies.push(`${it.item}: the falsifier ticket ${tid} is not an experiment ticket to the Scientist naming the item`)
      else add('tickets', tid)
    }
    continue
  }
  it.tickets.forEach(x => add('tickets', x))
}
const listed = art.tickets.concat(art.objects, art.files)
const j = await clerk('journal', ['Return whether today\'s journal file exists (notebook.py journal shows its path), its path, and which of these ids it mentions: ' + moved.map(i => i.item).join(', ') + '. ' +
  (listed.length ? 'Return in found those of these artefacts that this run made or changed today: a ticket tickets_get finds whose created date is today and whose parent or refs name ' + (T || 'the item') + ' or the item; a file under the home or an object (notebook.py) changed today (git log or the file time; existing is not enough): ' + listed.join(', ') + '. ' : 'No artefacts to check: found is empty. ') +
  'Write nothing.'], JOURNAL, 'journal', 'Check')
if (!j || !j.exists) out.notes.push('today\'s journal does not exist: the lead did not record the run')
else if (moved.some(i => i.step !== 'none' && !(j.mentions || []).includes(i.item))) out.notes.push('today\'s journal does not mention every item moved')
if (!j && !prove.length) {      // a lost clerk run is lost, not "no artefact" (budget.md rule 4; review of 1bbcc77); a prove hand-back needs no check
  out.notes.push('the journal/artefact check returned nothing (lost): the ticket is left as it is')
  return Object.assign(out, { outcome: 'lost', ticket_delivered: false, reason: 'the check stage returned nothing' })
}
out.artefacts = listed.filter(x => j && (j.found || []).includes(x))
const missing = listed.filter(x => !out.artefacts.includes(x))
if (missing.length) out.notes.push(`artefacts the lead named that the clerk did not find: ${missing.join(', ')}`)

// ---- the prove step goes back to the main session (T-1271, #87) ------------------------------
if (prove.length) {
  const ok = prove.filter(p => !p.why)
  const runs = prove.map(p => p.why ? { claim: p.claim, why: p.why } : { claim: p.claim, args: { claim: p.claim } })
  let first = true
  for (const r of runs) if (r.args) {
    Object.assign(r.args, first && T ? { ticket: T } : {}, { home: A.home, instance: A.instance || null, root: ROOT })
    first = false
  }
  const head = runs.find(r => r.args) || runs[0]
  out.for_main = Object.assign({ skill: 'researcher:prove', handback: 'lead-researcher', ticket: T || null, instance: A.instance || null, claim: head.claim,
    why: ok.length
      ? `${T || A.direction}: a prove step, and prover cannot be launched inside the explore run: run /researcher:prove ${ok[0].claim}${T ? ' with ticket ' + T : ''} from the main session ` +
        `(the Workflow prove.js with args${runs.length > 1 ? '; then each further entry of runs' : ''}); the attempt does not wait for a falsifier`
      : head.why }, head.args ? { args: head.args } : {}, runs.length > 1 ? { runs } : {})
  out.outcome = 'handed-back'
  out.ticket_delivered = false
} else if (T) {
  // ---- delivery: only on an artefact, and the result names it (#87) -------------------------
  if (out.artefacts.length) {
    const steps = moved.map(i => `${i.item}: ${i.step}`).join('; ')
    const result = `${steps || 'answered'}; artefacts: ${out.artefacts.join(', ')}`.replace(/"/g, "'").slice(0, 240)
    if (incomplete.length) {
      // #100 part 1: the attempt behind the falsifier is not complete: the work is done and
      // the deliverable is not met, so the ticket goes partial (its sender decides), never delivered
      const pr = `partial: attempt not complete for ${incomplete.join(', ')}; ${result}`.replace(/"/g, "'").slice(0, 240)
      const m = await clerk('close', [`Mark ${T} partial (tickets_update status partial, never deliver: true) with result "${pr}".`], MOVE, 'close', 'Check')
      out.ticket_partial = !!(m && m.ok)
      out.ticket_delivered = false
      out.outcome = 'partial'
    } else {
      const m = await clerk('close', [`Deliver ${T} (tickets_update deliver: true) with result "${result}".`], MOVE, 'close', 'Check')
      out.ticket_delivered = !!(m && m.ok)
    }
  } else {
    await clerk('note', [`Leave ${T} in-progress (make no status move) and append to its thread the note "explore: no artefact (no ticket filed, no direction item or object updated, ` +
      `no attempt): not delivered; ${oneLine(String(lead.report || '').split('\n')[0], 160)}".`], MOVE, 'note', 'Check')
    out.ticket_delivered = false
    out.outcome = 'no-artefact'
    out.reason = 'the lead left no artefact (no ticket filed, no direction item or object updated, no attempt): the ticket is not delivered'
  }
}
if (!out.outcome) out.outcome = out.anomalies.length ? 'moved (with anomalies)' : 'moved'
if (!A.nested) out.ship = await ship({ role: 'researcher', ticket: T, done: !!(out.ticket_delivered || out.ticket_partial), instance: A.instance, topic: 'explore-' + (A.direction || ''),
  only: '<home submodule> board', agentType: CLERK, phase: 'Check', notes: out.notes })
return out
