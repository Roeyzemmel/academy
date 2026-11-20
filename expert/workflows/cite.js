export const meta = {
  name: 'academy-cite',
  description: 'Add or verify one citation: one librarian run (entry, card with a verbatim quote, index row), the card validated by script with one retry, then the packet and the ticket',
  whenToUse: '/expert:cite and every cite ticket (also nested from the inbox), from the library home. args: {ticket?: "T-NNNN", ref?: "<DOI | arXiv id | bib key | title>", pinpoint?, relying?: "<sentence or claim id>", bib?: "<author instance>:references.bib"}',
  phases: [
    { title: 'Start', detail: 'take the ticket and read the ask' },
    { title: 'Cite', detail: 'one librarian run; the card validated, one retry' },
    { title: 'Land', detail: 'the citation packet and the ticket' },
  ],
}

// The order of /expert:cite in code (2026-10-31; docs/workflows.md): the brief is built
// here, the card is checked by cards.py validate (never by the librarian's word), a failing
// card goes back once, and the packet and the delivery come only after the check. The
// librarian's fetches stay on the source allowlist (source_guard.py). Nothing writes a
// \cite into a paper: that is the Author's edit.

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
if (!A.ticket && !A.ref) throw new Error('give args.ticket or args.ref')
const CLERK = 'academy:inbox-clerk'
const LIB = 'expert:librarian'
const T = A.ticket || ''
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const SCRIPTS = `Scripts: cards.py is \`py ${AR}/expert/scripts/cards.py\`, from the library home (python3 where there is no py)` +
  (ROOT ? '.\n' : '; <academy repo> is academy.root of the MCP tool workspace_get (academy.scripts.expert is the scripts folder).\n')
const clerk = (stage, lines, schema, label, phase) => launch(`WORKFLOW STAGE ${stage} of the academy-cite workflow.\n` + SCRIPTS + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const ASK = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' },
  ref: { type: 'string' }, pinpoint: { type: 'string' }, relying: { type: 'string' }, bib: { type: 'string' }, instance: { type: 'string' } },
  required: ['ok', 'ref', 'pinpoint', 'relying', 'bib', 'instance'] }
const CARD = { type: 'object', properties: {
  key: { type: 'string' }, pinpoint: { type: 'string' }, card: { type: 'string', description: 'the card path' },
  verdict: { type: 'string', description: 'match, or how the source differs from what the paper wants' },
  cached: { type: 'boolean' }, reachable: { type: 'boolean', description: 'false: paywalled, image-only, no text' },
  bib_changed: { type: 'boolean' }, note: { type: 'string' } },
  required: ['key', 'pinpoint', 'card', 'verdict', 'cached', 'reachable', 'bib_changed', 'note'] }
const CHECK = { type: 'object', properties: { ok: { type: 'boolean' }, errors: { type: 'array', items: { type: 'string' } } }, required: ['ok', 'errors'] }
const PACKET = { type: 'object', properties: { packet: { type: 'string' }, error: { type: 'string' } }, required: ['packet', 'error'] }
// #124: the clerk stages ask for detail (and stop_reason) and never require them (a clerk that left one
// out lost its run); a missing one reads 'no reason given'
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, status: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'status'] }

// ---- Ship (docs/workflows.md, "Shipping is a step of the workflow"): the same block in every
// workflow that writes. Standalone only (a nested run's parent ships), run once, never retried. A
// finished ticket gets the inbox's own scoped checkpoint (inbox.py --check, which honours
// "shipCheckpoint": false); anything else is not-run, with the command for the session.
const SHIP = { type: 'object', properties: { status: { type: 'string', enum: ['pushed', 'nothing', 'refused', 'not-run'] }, detail: { type: 'string' },
  branches: { type: 'array', items: { type: 'string' } }, output: { type: 'string', description: 'the whole output, stdout and stderr, verbatim' } },
  required: ['status', 'output'] }     // detail and branches: asked, defaulted below (#124: no free-text field required)
async function ship(s) {   // {role, ticket, done, instance, topic, only, agentType, phase, notes}
  if (!s.ticket) return { status: 'not-run', detail: 'no ticket: run the command from the workspace root (unless workspace.json says "shipCheckpoint": false)',
    command: `py scripts/ship.py checkpoint --ticket ${String(s.topic).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')} --role ${s.role} --only ${s.only}` }
  const check = `py ${AR}/${s.role}/scripts/inbox.py${s.instance ? ' --instance ' + s.instance : ''} --check ${s.ticket}`
  if (!s.done) return { status: 'not-run', detail: `${s.ticket} is not finished: its checkpoint runs once it is (as in the inbox)`, command: check }
  const r = await launch(`WORKFLOW STAGE ship. Run \`${check} 2>&1\` once, from the home` + (ROOT ? '' : ' (<academy repo> is academy.root of the MCP tool workspace_get)') +
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
    : { status: r.status || 'not-run', detail: r.detail || 'no detail given' }
  if (!/^(pushed|nothing)$/.test(res.status)) res.command = check
  if (res.status === 'refused' && s.notes) s.notes.push(`the ship stage was refused (${res.detail}); fix the cause, then run \`${check}\` once by hand`)
  return res
}

const out = { ticket: T || null, notes: [] }

// ---- Start ----------------------------------------------------------------------------
phase('Start')
let ask = { ok: true, ref: A.ref || '', pinpoint: A.pinpoint || '', relying: A.relying || '', bib: A.bib || '', instance: '' }
if (T) {
  const a = await clerk('start', [`ticket: ${T}`,
    'Move it to in-progress (open -> accepted -> in-progress, acting as its receiver; leave an in-progress ticket as it is), then return from its ask, ## Ask and refs:',
    'the reference (DOI, arXiv id, bib key or title), the pinpoint wanted, the sentence or claim id that relies on it, the target bibliography (<author instance>:references.bib), and the instance you acted as.'],
    ASK, 'start', 'Start')
  if (!a || !a.ok) return Object.assign(out, { outcome: 'not-started', reason: a ? a.detail || 'no reason given' : 'the start stage returned nothing' })
  ask = { ok: true, ref: A.ref || a.ref, pinpoint: A.pinpoint || a.pinpoint, relying: A.relying || a.relying, bib: A.bib || a.bib, instance: a.instance }
}
if (!ask.ref) return Object.assign(out, { outcome: 'not-started', reason: 'the ask names no reference (DOI, arXiv id, key or title)' })

// ---- Cite: one librarian run, the card checked by script ------------------------------------
phase('Cite')
const brief = SCRIPTS + `${ask.ref}. ` + (ask.pinpoint ? `The pinpoint intended: ${ask.pinpoint}. ` : 'No pinpoint given: locate the statement. ') +
  (ask.relying ? `It is relied on by: ${ask.relying}. ` : '') + (ask.bib ? `The bibliography: ${ask.bib}.` : '') + '\n\n' +
  'If the key is already in that bibliography, verify it against the record rather than adding it again, and say whether the fields match. ' +
  'If it is new, fetch the record and add the entry in the file\'s key style. Then locate the statement, write its card with a verbatim quote ' +
  'from the version named, validate the card, and add the index row if the source is newly cached. Never write an entry from memory and never ' +
  'invent a pinpoint; a source you cannot read is said so on the card.'
let c = await launch(brief, { label: 'librarian', phase: 'Cite', agentType: LIB, schema: CARD })
if (c === null) return Object.assign(out, { outcome: 'lost', reason: 'the librarian run returned nothing (a limit?): nothing further launched' })
// an unreachable source has no card to validate (live run 2026-10-31 validated the words "none written"): skip the check
const noCard = !c.reachable && !/\.(md|ya?ml)$/i.test(String(c.card || '').trim())
let v = noCard ? null : await clerk('validate', [`Run cards.py validate ${c.card} from the library home and return ok (no error) and every error line.`], CHECK, 'validate', 'Cite')
if (v && !v.ok) {
  out.notes.push('the card failed validation; sent back to the librarian once: ' + v.errors.join('; '))
  const c2 = await launch(brief + `\n\nYour card ${c.card} fails cards.py validate:\n- ${v.errors.join('\n- ')}\n` +
    'Fix the card. A quote you cannot find in the cached text is corrected from the source, or the card says why it cannot be.',
    { label: 'librarian (fix)', phase: 'Cite', agentType: LIB, schema: CARD })
  if (c2 === null) return Object.assign(out, { outcome: 'lost', reason: 'the librarian fix returned nothing', card: c })
  c = c2
  v = await clerk('validate', [`Run cards.py validate ${c.card} and return ok and every error line.`], CHECK, 'validate again', 'Cite')
  if (v && !v.ok) out.notes.push('the card still fails validation after one fix; it must say why: ' + v.errors.join('; '))
}
Object.assign(out, { key: c.key, pinpoint: c.pinpoint, card: c.card, verdict: c.verdict, validated: !!(v && v.ok) })
if (!/^match$/i.test(c.verdict)) out.notes.unshift(`MISMATCH (a mathematical finding): the source differs from what ${ask.relying || 'the paper'} wants: ${c.verdict}`)
if (!c.reachable) out.notes.push('UNREACHABLE source: the card records how it was read; anything resting on it stays an unverified input until a human reads it')
// with a ticket, the bib edit in the Author home ships with it: the touch ledger records it and the
// ticket's --check passes it to ship.py as --touched (docs/branching.md); without one, nothing claims it
if (c.bib_changed && !T) out.notes.push(`${ask.bib || 'references.bib'} changed in the Author home and no ticket ships it: add --touched <that home's submodule>:references.bib to the command below (else the next Expert ticket's checkpoint carries it)`)
const end = async () => {
  if (!A.nested) out.ship = await ship({ role: 'expert', ticket: T, done: !!out.ticket_delivered, instance: ask.instance, topic: 'cite-' + (c.key || ask.ref),
    only: 'library board', agentType: CLERK, phase: 'Land', notes: out.notes })
  return out
}

// ---- Land --------------------------------------------------------------------------------
phase('Land')
const p = await launch(`File the citation packet for ${c.key}: packets_create kind citation, subject [bib:${c.key}#${c.pinpoint || '?'}], ` +
  `the card ${c.card} under ## Produced, the verdict (${c.verdict})${c.reachable ? '' : ' and how the unreadable source was read'} under ## Established vs assumed` +
  (T ? `, ticket ${T}` : '') + `; ## Decisions needed: None. unless the verdict is a mismatch, then one decision on what the relying statement should do. Return the packet id.`,
  { label: 'packet', phase: 'Land', agentType: LIB, schema: PACKET, effort: 'low' })
out.packet = p && p.packet ? p.packet : null
if (!out.packet) out.notes.push('the packet was not filed: ' + (p ? p.error : 'the stage returned nothing'))
// An unreadable source is not delivered (project rule "inaccessible sources"): the ticket is parked on the human
// with the exact ask (the source, the pinpoint wanted, the statement resting on it), and comes back as a gate
if (T && !c.reachable) {
  const why = `source unreachable from this session: ${c.key || ask.ref}; a human with access reads ${ask.pinpoint || 'the statement wanted'} for ${ask.relying || 'the relying statement'}`
  const m = await clerk('move', [`ticket: ${T}`, ask.instance ? `act as: ${ask.instance}` : '',
    `block-human: blocked, waiting_on [human], reason "${why.replace(/"/g, "'").slice(0, 240)}"` + (out.packet ? `, and fields.packets [${out.packet}]` : '')], MOVE, 'park on human', 'Land')
  out.ticket_delivered = false
  out.outcome = m && m.ok ? 'unreachable (on the human)' : 'unfinished'
  out.gate = { why, source: c.key || ask.ref, pinpoint: ask.pinpoint || '', relying: ask.relying || '', packet: out.packet }
  return await end()
}
if (T) {
  const result = `${c.key}, ${c.pinpoint || 'no pinpoint'}, verdict ${c.verdict}, card ${c.card}`.replace(/"/g, "'")
  const m = await clerk('move', [`ticket: ${T}`, ask.instance ? `act as: ${ask.instance}` : '',
    `deliver: deliver: true with result "${result.slice(0, 240)}"` + (out.packet ? ` and fields.packets [${out.packet}]` : '')], MOVE, 'deliver', 'Land')
  out.ticket_delivered = !!(m && m.ok)
}
out.outcome = out.validated ? 'cited' : 'cited (card not validated)'
return await end()
