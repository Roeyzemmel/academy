export const meta = {
  name: 'academy-cite',
  description: 'Add or verify one citation: one librarian run (entry, card with a verbatim quote, index row), the card validated by script with one retry, then the packet and the ticket; or resume a ticket parked on the human with what the human read (from_human)',
  whenToUse: '/expert:cite and every cite ticket (also nested from the inbox), from the library home; /expert:cite --from-human. args: {ticket?: "T-NNNN", ref?: "<DOI | arXiv id | bib key | title>", pinpoint?, relying?: "<sentence or claim id>", bib?: "<author instance>:references.bib", from_human?: {file?: "<path inside the workspace>", text?: "<the statement, as the human gave it>"} (with ticket)}',
  phases: [
    { title: 'Start', detail: 'take the ticket and read the ask' },
    { title: 'Cite', detail: 'one librarian run (once more if it returns nothing); the card validated, one retry' },
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
// #108: the human's hand-back. A cite ticket parked on the human (an unreachable source, below) is
// resumed with what the human read: a file (a PDF or page image inside the workspace) or the quoted
// statement as text. The material is recorded in the library by script (handback.py: a text checked
// against its hash, computed here from the human's own words), the librarian writes the card from it
// alone (read_from human-supplied), cards.py validates it, and only then is the ticket unparked and
// delivered; material that does not hold the pinpoint leaves it parked, saying what is still missing.
const FH = A.from_human === undefined || A.from_human === null ? null : A.from_human
if (FH !== null && (typeof FH !== 'object' || Array.isArray(FH) || !(FH.file || FH.text)))
  throw new Error('args.from_human is {file?: "<path inside the workspace>", text?: "<the statement, as the human gave it>"}: give one of them')
if (FH && !A.ticket) throw new Error('args.from_human resumes a cite ticket parked on the human: give args.ticket')
if (FH && !/^T-\d+$/.test(String(A.ticket))) throw new Error('args.from_human: args.ticket must be a ticket id T-NNNN, got ' + JSON.stringify(A.ticket))
// the digest handback.py checks (library.text_digest): sha256 of the UTF-8 bytes, line ends LF,
// blanks around removed. Plain JavaScript: the workflow sandbox promises no crypto module
const utf8 = t => {
  const b = []
  for (const ch of t) {
    const c = ch.codePointAt(0)
    if (c < 0x80) b.push(c)
    else if (c < 0x800) b.push(0xc0 | (c >> 6), 0x80 | (c & 63))
    else if (c < 0x10000) b.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
    else b.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
  }
  return b
}
const sha256 = bytes => {
  const rr = (v, n) => (v >>> n) | (v << (32 - n))
  const H = [], K = []
  for (let p = 2, n = 0; n < 64; p++) {          // the first 64 primes: the fractional parts of their roots
    let prime = true
    for (let d = 2; d * d <= p; d++) if (p % d === 0) { prime = false; break }
    if (!prime) continue
    if (n < 8) H[n] = (Math.pow(p, 1 / 2) * 4294967296) | 0
    K[n++] = (Math.pow(p, 1 / 3) * 4294967296) | 0
  }
  const m = bytes.slice()
  m.push(0x80)
  while (m.length % 64 !== 56) m.push(0)
  const bits = bytes.length * 8
  for (const x of [Math.floor(bits / 4294967296), bits >>> 0]) m.push((x >>> 24) & 255, (x >>> 16) & 255, (x >>> 8) & 255, x & 255)
  let h = H.slice()
  for (let o = 0; o < m.length; o += 64) {
    const w = []
    for (let i = 0; i < 16; i++) w[i] = (m[o + 4 * i] << 24) | (m[o + 4 * i + 1] << 16) | (m[o + 4 * i + 2] << 8) | m[o + 4 * i + 3]
    for (let i = 16; i < 64; i++) {
      const s0 = rr(w[i - 15], 7) ^ rr(w[i - 15], 18) ^ (w[i - 15] >>> 3)
      const s1 = rr(w[i - 2], 17) ^ rr(w[i - 2], 19) ^ (w[i - 2] >>> 10)
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0
    }
    let [a, b, c, d, e, f, g, k] = h
    for (let i = 0; i < 64; i++) {
      const t1 = (k + (rr(e, 6) ^ rr(e, 11) ^ rr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0
      const t2 = ((rr(a, 2) ^ rr(a, 13) ^ rr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0
      k = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0
    }
    h = [a, b, c, d, e, f, g, k].map((x, i) => (x + h[i]) | 0)
  }
  return h.map(x => (x >>> 0).toString(16).padStart(8, '0')).join('')
}
const handHash = text => 'sha256:' + sha256(utf8(String(text).replace(/\r\n?/g, '\n').replace(/^[ \t\n]+|[ \t\n]+$/g, '')))
const RE_BIBKEY = /^[A-Za-z0-9][A-Za-z0-9_.+-]*$/
const CLERK = 'academy:inbox-clerk'
const LIB = 'expert:librarian'
const T = A.ticket || ''
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const SCRIPTS = `Scripts: cards.py is \`py ${AR}/expert/scripts/cards.py\`, from the library home (python3 where there is no py)` +
  (ROOT ? '.\n' : '; <academy repo> is academy.root of the MCP tool workspace_get (academy.scripts.expert is the scripts folder).\n')
// #94: a stage that throws (a run that ended without its structured output: 2026-11-20, T-1614,
// "subagent completed without calling StructuredOutput") is a lost stage, never the end of the
// run that nests this one (the inbox): it reads as null, as a run that returned nothing does
async function safe(prompt, opts) {
  try { return await launch(prompt, opts) } catch (e) {
    log(`stage ${opts && opts.label} lost: ${String(e).slice(0, 200)}`)
    if (++LAUNCH_LIMIT.nulls >= 3) LAUNCH_LIMIT.stopped = true     // a throw counts as a null
    return null
  }
}
const clerk = (stage, lines, schema, label, phase) => safe(`WORKFLOW STAGE ${stage} of the academy-cite workflow.\n` + SCRIPTS + lines.filter(Boolean).join('\n'),
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
// cards.py dups --json, parsed by the code; the counts are asked too, for an output that does not parse
const DUPS = { type: 'object', properties: { exit: { type: 'number', description: 'the exit code the shell printed' },
  bib_key: { type: 'number' }, bib_id: { type: ['number', 'null'] }, cards: { type: 'number' },
  output: { type: 'string', description: 'its whole stdout, verbatim' } }, required: ['exit'] }
const CHECK = { type: 'object', properties: { ok: { type: 'boolean' }, errors: { type: 'array', items: { type: 'string' } } }, required: ['ok', 'errors'] }
const PACKET = { type: 'object', properties: { packet: { type: 'string' }, error: { type: 'string' } }, required: ['packet', 'error'] }
// #124: the clerk stages ask for detail (and stop_reason) and never require them (a clerk that left one
// out lost its run); a missing one reads 'no reason given'
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, status: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'status'] }
// #108: the start of a hand-back reads the parked ticket (park_reason: asked, never required, #124)
const ASK_FH = { type: 'object', properties: Object.assign({}, ASK.properties, { kind: { type: 'string' }, status: { type: 'string' },
  waiting_on: { type: 'array', items: { type: 'string' } },
  park_reason: { type: 'string', description: 'the reason of its last move to blocked, verbatim' } }),
  required: ASK.required.concat(['kind', 'status', 'waiting_on']) }
// handback.py record --json, parsed by the code
const REC = { type: 'object', properties: { exit: { type: 'number', description: 'the exit code the shell printed' },
  output: { type: 'string', description: 'its JSON line, verbatim' } }, required: ['exit'] }
// the librarian's card from the human's material: found false is "the material does not hold the pinpoint"
const HCARD = { type: 'object', properties: {
  key: { type: 'string' }, pinpoint: { type: 'string' }, card: { type: 'string', description: 'the card path, or none written' },
  verdict: { type: 'string', description: 'match, or how the source differs from what the paper wants' },
  found: { type: 'boolean', description: 'the material holds the pinpoint' },
  missing: { type: 'string', description: 'found false: exactly what is still needed (statement, page, and why)' },
  bib_changed: { type: 'boolean' }, note: { type: 'string' } },
  required: ['key', 'pinpoint', 'card', 'verdict', 'found', 'bib_changed', 'note'] }

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
let key = ''     // the hand-back's bibliography key (#108)
if (T) {
  const a = await clerk('start', [`ticket: ${T}`,
    FH ? 'Read it (tickets_get) and move nothing: a human hands back what they read of its source, and the ticket stays as it is until the card is checked. Return from its ask, ## Ask and refs:'
      : 'Move it to in-progress (open -> accepted -> in-progress, acting as its receiver; leave an in-progress ticket as it is), then return from its ask, ## Ask and refs:',
    'the reference (DOI, arXiv id, bib key or title), the pinpoint wanted, the sentence or claim id that relies on it, the target bibliography (<author instance>:references.bib), and the instance you acted as' +
    (FH ? ' (its receiver); and its kind, its status, its waiting_on (a list), and the reason of its last move to blocked, verbatim from its thread (park_reason).' : '.')],
    FH ? ASK_FH : ASK, 'start', 'Start')
  if (!a || !a.ok) return Object.assign(out, { outcome: 'not-started', reason: a ? a.detail || 'no reason given' : 'the start stage returned nothing' })
  ask = { ok: true, ref: A.ref || a.ref, pinpoint: A.pinpoint || a.pinpoint, relying: A.relying || a.relying, bib: A.bib || a.bib, instance: a.instance }
  if (FH) {
    const waits = Array.isArray(a.waiting_on) ? a.waiting_on.map(String) : String(a.waiting_on || '').split(/[\s,\[\]]+/)
    if (a.status !== 'blocked' || !waits.includes('human'))
      return Object.assign(out, { outcome: 'not-started', reason: `${T} is ${a.status || 'in no status the clerk read'}` +
        (waits.filter(Boolean).length ? ` (waiting on ${waits.filter(Boolean).join(', ')})` : '') +
        ', not parked on the human: --from-human resumes a cite ticket parked on the human (blocked, waiting_on [human])' })
    if (a.kind !== 'cite') return Object.assign(out, { outcome: 'not-started', reason: `${T} is a ${a.kind || 'ticket of no kind the clerk read'} ticket: --from-human resumes a cite ticket` })
    const why = String(a.park_reason || '')
    // the park must be cite's own (the unreachable source), not another wait on the human
    if (!/source unreachable from this session: /.test(why))
      return Object.assign(out, { outcome: 'not-started', reason: `${T} is parked on the human, but not by cite for an unreachable source (its last park reason: ${JSON.stringify(why.slice(0, 160))})` })
    const m = /source unreachable from this session: ([A-Za-z0-9][A-Za-z0-9_.+-]*)(?=;|\s|$)/.exec(why)
    const parked = m ? m[1].replace(/\.+$/, '') : ''
    const given = A.ref && RE_BIBKEY.test(A.ref) ? A.ref : ''
    if (given && parked && given !== parked)
      return Object.assign(out, { outcome: 'not-started', reason: `args.ref ${given} is not the key ${T} was parked for (${parked}): give the parked key, or none` })
    key = given || parked || (RE_BIBKEY.test(String(ask.ref || '')) ? ask.ref : '')
    if (!key) return Object.assign(out, { outcome: 'not-started', reason: 'no bibliography key: the park reason names none and the ask\'s reference is no key; pass args.ref = the key' })
    const p = /a human with access reads (.*?) for /.exec(why)
    if (!ask.pinpoint && p && p[1] !== 'the statement wanted') ask.pinpoint = p[1]
  }
}
if (!ask.ref && !key) return Object.assign(out, { outcome: 'not-started', reason: 'the ask names no reference (DOI, arXiv id, key or title)' })

// ---- Cite: one librarian run, the card checked by script ------------------------------------
phase('Cite')
let c = null
const end = async () => {
  if (!A.nested) out.ship = await ship({ role: 'expert', ticket: T, done: !!out.ticket_delivered, instance: ask.instance, topic: 'cite-' + ((c && c.key) || key || ask.ref),
    only: 'library board', agentType: CLERK, phase: 'Land', notes: out.notes })
  return out
}
const actAs = ask.instance ? `act as: ${ask.instance}` : ''
// a shell word: single quotes, a quote inside as '\'' (no $, backtick or backslash is expanded)
const q = x => "'" + String(x || '').replace(/'/g, "'\\''") + "'"
// #108: a hand-back that cannot finish leaves the ticket parked on the human, with one thread line
// saying why (what is still missing); the gate is the same ask, sharpened
const stillParked = async (why, outcome) => {
  const line = `cite --from-human: ${why}; the ticket stays parked on the human`.replace(/"/g, "'")
  const m = await clerk('note', [`ticket: ${T}`, actAs,
    `note: append to the thread "${line.slice(0, 600)}", and move nothing (it stays blocked, waiting_on [human])`], MOVE, 'still parked', c ? 'Land' : 'Cite')
  if (!m || !m.ok) out.notes.push('the thread line was not written: ' + line)
  out.ticket_delivered = false
  out.outcome = outcome
  out.gate = { why, source: key, pinpoint: ask.pinpoint || '', relying: ask.relying || '', missing: out.missing || '' }
  return await end()
}
const HB = `py ${AR}/expert/scripts/handback.py`
const pin = ask.pinpoint ? ` --pinpoint ${q(ask.pinpoint)}` : ''
const readRec = r => {
  try { return JSON.parse(String((r && r.output) || '').trim().split(/\r?\n/).find(l => /^\{/.test(l)) || 'null') } catch (e) { return null }
}
const handback = { files: [], texts: [], ids: [] }
const took = j => {
  if (j.id && !handback.ids.includes(j.id)) handback.ids.push(j.id)
  for (const f of j.recorded || []) if (!handback.files.includes(f)) handback.files.push(f)
  for (const t of j.texts || []) if (!handback.texts.includes(t)) handback.texts.push(t)
  for (const n of j.notes || []) out.notes.push('hand-back: ' + n)
}
const recWhy = (r, j) => j && Array.isArray(j.problems) && j.problems.length ? j.problems.join('; ')
  : r ? `handback.py exited ${r.exit} with no JSON line` : 'the record stage returned nothing'
if (FH && FH.text) {
  const h = handHash(FH.text)
  const tf = `.academy/handback-${T}.txt`
  const recPrompt = again => `WORKFLOW STAGE record of the academy-cite workflow: a human's hand-back of an unreachable source, for ${T}.\n` + SCRIPTS +
    (again ? `A first try recorded nothing: ${again}.\n` : '') +
    `1. With the Write tool, write the text between the two marker lines below to ${tf} in the library home, byte for byte: ` +
    'no reflowing, no correction, no character added or dropped, nothing of the marker lines.\n' +
    `2. Run \`${HB} record ${key} --ticket ${T}${pin} --text-file ${tf} --expect ${h} --json; echo $?\` once, from the library home.\n` +
    'Return the exit code the shell printed, and its JSON line verbatim in output. Fix nothing and write nothing else.\n' +
    '----- BEGIN HUMAN TEXT -----\n' + String(FH.text) + '\n----- END HUMAN TEXT -----'
  let r = await safe(recPrompt(''), { label: 'record text', phase: 'Cite', agentType: LIB, schema: REC, effort: 'low' })
  // recorded, and as this text: the script's own digest of what it wrote must be the human's (#108 review)
  const good = j => !!(j && j.ok && j.hash === h && j.id === h)
  const bad = (r, j) => j && j.ok ? `the record's digest ${j.hash} is not the hand-back's ${h}` : recWhy(r, j)
  let j = readRec(r)
  if (!good(j) && !LAUNCH_LIMIT.stopped) {
    out.notes.push('the hand-back text was not recorded (' + bad(r, j) + '); written again once')
    r = await safe(recPrompt(bad(r, j)), { label: 'record text (retry)', phase: 'Cite', agentType: LIB, schema: REC, effort: 'low' })
    j = readRec(r)
  }
  if (!good(j)) return await stillParked(`the text handed back could not be recorded verbatim in the library (${bad(r, j)}); run --from-human again`, 'not-recorded (on the human)')
  took(j)
}
if (FH && FH.file) {
  const r = await clerk('record file', [`Run \`${HB} record ${key} --ticket ${T}${pin} --file ${q(FH.file)} --json; echo $?\` once, from the library home. ` +
    'Return the exit code the shell printed, and its JSON line verbatim in output. Fix nothing.'], REC, 'record file', 'Cite')
  const j = readRec(r)
  if (!(j && j.ok && /^sha256:[0-9a-f]{64}$/.test(String(j.id || ''))))
    return await stillParked(`the file handed back (${FH.file}) could not be recorded in the library (${recWhy(r, j)})`, 'not-recorded (on the human)')
  took(j)
}
if (FH) out.handback = handback

const brief = FH
  ? SCRIPTS + `${key}: a source no session could reach, read by a human for the cite ticket ${T}. ` +
    (ask.pinpoint ? `The pinpoint wanted: ${ask.pinpoint}. ` : 'No pinpoint given: locate the statement the relying sentence needs. ') +
    (ask.relying ? `It is relied on by: ${ask.relying}. ` : '') + (ask.bib ? `The bibliography: ${ask.bib}.` : '') + '\n\n' +
    `What the human handed back, recorded in the library home: ${handback.files.join(', ')}` +
    (handback.texts.length ? ` (the text to quote from: ${handback.texts.join('; ')})` : ' (no text: read the pages as images)') + '.\n' +
    'Write the card from that material only, and fetch no text of the source (a bibliography record may still be fetched, as for any entry). ' +
    `If the material holds the pinpoint: write the card with cards.py new ... --read-from human-supplied --handback ${handback.ids.join(',')} ` +
    '(the record ids of what you quote, of those; the card keeps them as handback:), its version as the material shows it ' +
    '(edition, journal, year, page) or "human-supplied, <date>" when it shows none, and its quote verbatim from that material: copied exactly from ' +
    'the recorded text, or, from a page image or a PDF with no text, transcribed exactly, said so in ## Notes, and the card given --status unverified ' +
    '--status-reason "transcribed from <file>; not checked by script" (cards.py requires it). Fill ## Statement and ## Hypotheses ' +
    'from it, validate the card (cards.py validate <card> --expect-read-from human-supplied), set the verdict against the relying statement, and where ' +
    'the index row says the source is unreachable, add that a human supplied this pinpoint (date, ticket). If the key is not yet in that bibliography, ' +
    'add the entry from a fetched record as usual. If the material does not hold the pinpoint (another page or statement, cut off, unreadable), ' +
    'write no card: return found false and say in missing exactly what is still needed (the statement, the page, and why). ' +
    'Never quote from memory and never invent a pinpoint.'
  : SCRIPTS + `${ask.ref}. ` + (ask.pinpoint ? `The pinpoint intended: ${ask.pinpoint}. ` : 'No pinpoint given: locate the statement. ') +
  (ask.relying ? `It is relied on by: ${ask.relying}. ` : '') + (ask.bib ? `The bibliography: ${ask.bib}.` : '') + '\n\n' +
  'If the key is already in that bibliography, verify it against the record rather than adding it again, and say whether the fields match. ' +
  'If it is new, fetch the record and add the entry in the file\'s key style. Then locate the statement, write its card with a verbatim quote ' +
  'from the version named, validate the card, and add the index row if the source is newly cached. Never write an entry from memory and never ' +
  'invent a pinpoint; a source you cannot read is said so on the card.'
// #94 (T-1026, T-1614): a librarian that returns no result is run once more, told that the first
// run may have written already; a second empty run loses the ticket alone, said in its thread
const lost = async (reason) => {
  if (T) await clerk('note', [`ticket: ${T}`, ask.instance ? `act as: ${ask.instance}` : '',
    `note: append to the thread "cite: ${reason.replace(/"/g, "'").slice(0, 300)}; check the library and the bibliography by hand ` +
    `(cards.py validate on any card written) before the ticket is run again"`], MOVE, 'lost note', 'Cite')
  return Object.assign(out, { outcome: 'lost', reason })
}
const lib = (prompt, label) => safe(prompt, { label, phase: 'Cite', agentType: LIB, schema: FH ? HCARD : CARD })
c = await lib(brief, 'librarian')
const retried = c === null && !LAUNCH_LIMIT.stopped
if (retried) {
  out.notes.push('the librarian run returned no result; run once more')
  c = await lib(brief + '\n\nA first run on this reference ended without its result. What it wrote (the bib entry, the card, the index row) ' +
    'may already be on disk: look before writing, finish what is there, and never add a second entry or card for the same pinpoint.', 'librarian (retry)')
}
if (c === null) return await lost('the librarian returned no result twice (a limit, or a run that ended without its structured output): ' +
  'nothing further launched; any card or bib entry it wrote is unvalidated and uncommitted')
// #108: the human's material does not hold the pinpoint: no card, the ticket stays parked, saying what is missing
if (FH && c.found !== true) {
  out.missing = String(c.missing || '').trim() || 'the librarian did not say what is missing'
  return await stillParked(`what was handed back (${handback.files.join(', ')}) does not hold ${ask.pinpoint || 'the statement wanted'}: ${out.missing}`,
    'still missing (on the human)')
}
// #94 review: two runs on one reference can leave two bib entries or two cards (cards.py new refuses only
// the same card path): on the retry path cards.py dups counts them, and more than one loses the ticket
if (retried) {
  const d = await clerk('duplicates', [`Run \`cards.py dups ${c.key} ${q(c.pinpoint || ask.pinpoint)}` + (ask.bib ? ` --bib ${q(ask.bib)}` : '') +
    (ask.ref ? ` --ref ${q(ask.ref)}` : '') + ' --json; echo $?` once, from the library home. Return the exit code the shell printed, ' +
    'its JSON line verbatim in output, and the counts bib_key, bib_id and cards from it.'], DUPS, 'duplicates', 'Cite')
  if (!d) out.notes.push('the duplicate check returned nothing: look for a second bib entry or card of ' + c.key + ' by hand')
  else {
    let r = null
    try { r = JSON.parse(String(d.output || '').trim().split(/\r?\n/).find(l => /^\{/.test(l)) || 'null') } catch (e) { r = null }
    const n = r || d
    const many = ['bib_key', 'bib_id', 'cards'].filter(k => typeof n[k] === 'number' && n[k] > 1)
    if (many.length || (!r && d.exit === 1)) {
      const what = r && Array.isArray(r.problems) && r.problems.length ? r.problems.join('; ')
        : many.length ? many.map(k => `${n[k]} (${k})`).join(', ') : 'cards.py dups exited 1'
      out.card = c.card
      return await lost(`the librarian retry left a duplicate: ${what}; remove the extra one, then run the ticket again`)
    }
    if (r && Array.isArray(r.warnings) && r.warnings.length) out.notes.push('duplicate check: ' + r.warnings.join('; '))
  }
}
// an unreachable source has no card to validate (live run 2026-10-31 validated the words "none written"): skip the check
const isCard = card => /\.(md|ya?ml)$/i.test(String(card || '').trim())
const noCard = !FH && !c.reachable && !isCard(c.card)
if (FH && !isCard(c.card)) return await stillParked(`the librarian found ${ask.pinpoint || 'the statement'} in what was handed back but names no card (${c.card})`, 'unfinished (on the human)')
// a hand-back's card must say it was read from the human's material (#108): cards.py checks it,
// and it must quote only the records this run made (round 2 of the review): a record's digest shows it
// unchanged, not who wrote it, so an id the record stage did not return fails the card
const expectRead = FH ? ` --expect-read-from human-supplied --expect-handback ${handback.ids.join(',')}` : ''
let v = noCard ? null : await clerk('validate', [`Run cards.py validate ${c.card}${expectRead} from the library home and return ok (no error) and every error line.`], CHECK, 'validate', 'Cite')
if (v && !v.ok) {
  out.notes.push('the card failed validation; sent back to the librarian once: ' + v.errors.join('; '))
  const c2 = await lib(brief + `\n\nYour card ${c.card} fails cards.py validate:\n- ${v.errors.join('\n- ')}\n` +
    'Fix the card. A quote you cannot find in the cached text is corrected from the source, or the card says why it cannot be.',
    'librarian (fix)')
  if (c2 === null) { out.card = c.card; return await lost(`the librarian fix returned no result: the card ${c.card} fails cards.py validate and is uncommitted`) }
  c = c2
  v = await clerk('validate', [`Run cards.py validate ${c.card}${expectRead} and return ok and every error line.`], CHECK, 'validate again', 'Cite')
  if (v && !v.ok) out.notes.push('the card still fails validation after one fix; it must say why: ' + v.errors.join('; '))
}
Object.assign(out, { key: c.key, pinpoint: c.pinpoint, card: c.card, verdict: c.verdict, validated: !!(v && v.ok) })
if (!/^match$/i.test(c.verdict)) out.notes.unshift(`MISMATCH (a mathematical finding): the source differs from what ${ask.relying || 'the paper'} wants: ${c.verdict}`)
if (FH && !out.validated) {
  return await stillParked(`the card ${c.card} written from what was handed back fails cards.py validate after one fix (` +
    (v ? v.errors.join('; ') : 'the validate stage returned nothing') + '): it is not delivered', 'unfinished (on the human)')
}
if (!FH && !c.reachable) out.notes.push('UNREACHABLE source: the card records how it was read; anything resting on it stays an unverified input until a human reads it')
// with a ticket, the bib edit in the Author home ships with it: the touch ledger records it and the
// ticket's --check passes it to ship.py as --touched (docs/branching.md); without one, nothing claims it
if (c.bib_changed && !T) out.notes.push(`${ask.bib || 'references.bib'} changed in the Author home and no ticket ships it: add --touched <that home's submodule>:references.bib to the command below (else the next Expert ticket's checkpoint carries it)`)

// ---- Land --------------------------------------------------------------------------------
phase('Land')
const p = await safe(`File the citation packet for ${c.key}: packets_create kind citation, subject [bib:${c.key}#${c.pinpoint || '?'}], ` +
  `the card ${c.card} under ## Produced, the verdict (${c.verdict})` +
  (FH ? ` and how the source was read (by a human with access, who handed back ${handback.files.join(', ')} for ${T}: read_from human-supplied)`
    : c.reachable ? '' : ' and how the unreadable source was read') + ' under ## Established vs assumed' +
  (T ? `, ticket ${T}` : '') + `; ## Decisions needed: None. unless the verdict is a mismatch, then one decision on what the relying statement should do. Return the packet id.`,
  { label: 'packet', phase: 'Land', agentType: LIB, schema: PACKET, effort: 'low' })
out.packet = p && p.packet ? p.packet : null
if (!out.packet) out.notes.push('the packet was not filed: ' + (p ? p.error : 'the stage returned nothing'))
// An unreadable source is not delivered (project rule "inaccessible sources"): the ticket is parked on the human
// with the exact ask (the source, the pinpoint wanted, the statement resting on it), and comes back as a gate
if (T && !FH && !c.reachable) {
  const why = `source unreachable from this session: ${c.key || ask.ref}; a human with access reads ${ask.pinpoint || 'the statement wanted'} for ${ask.relying || 'the relying statement'}`
  const m = await clerk('move', [`ticket: ${T}`, ask.instance ? `act as: ${ask.instance}` : '',
    `block-human: blocked, waiting_on [human], reason "${why.replace(/"/g, "'").slice(0, 240)}"` + (out.packet ? `, and fields.packets [${out.packet}]` : '')], MOVE, 'park on human', 'Land')
  out.ticket_delivered = false
  out.outcome = m && m.ok ? 'unreachable (on the human)' : 'unfinished'
  out.gate = { why, source: c.key || ask.ref, pinpoint: ask.pinpoint || '', relying: ask.relying || '', packet: out.packet }
  return await end()
}
if (T) {
  const result = (`${c.key}, ${c.pinpoint || 'no pinpoint'}, verdict ${c.verdict}, card ${c.card}` + (FH ? ', read from what a human handed back' : '')).replace(/"/g, "'")
  const deliver = `deliver: deliver: true with result "${result.slice(0, 240)}"` + (out.packet ? ` and fields.packets [${out.packet}]` : '')
  // #108: the parked ticket is unparked first (blocked -> in-progress, the receiver clearing waiting_on), then
  // delivered, each a stage of its own, so a delivery that fails after the unpark is said (review 7)
  if (FH) {
    const u = await clerk('move', [`ticket: ${T}`, actAs, 'unpark: tickets_update status in-progress with waiting_on [] ' +
      '(the human handed back what they read: the receiver clears the park, blocked -> in-progress); nothing else'], MOVE, 'unpark', 'Land')
    if (!u || !u.ok) {
      out.ticket_delivered = false
      out.notes.push(`the card ${c.card} is valid, but ${T} could not be unparked (${u ? u.detail || 'no reason given' : 'the stage returned nothing'}): ` +
        `it is still blocked on the human; move it to in-progress (waiting_on []) and deliver it with "${result.slice(0, 240)}"`)
      out.outcome = 'cited, ticket not unparked'
      return await end()
    }
  }
  const m = await clerk('move', [`ticket: ${T}`, actAs, deliver], MOVE, 'deliver', 'Land')
  out.ticket_delivered = !!(m && m.ok)
  if (FH && !out.ticket_delivered) {
    const line = `cite --from-human: the card ${c.card} is written and valid, and the ticket was unparked, but the delivery failed ` +
      `(${m ? m.detail || 'no reason given' : 'the stage returned nothing'}): deliver it with result '${result.slice(0, 240)}'`
    const n = await clerk('note', [`ticket: ${T}`, actAs, `note: append to the thread "${line.replace(/"/g, "'").slice(0, 600)}", and move nothing`], MOVE, 'deliver failed note', 'Land')
    if (!n || !n.ok) out.notes.push('the thread line was not written: ' + line)
    out.outcome = 'cited, ticket not delivered'
    return await end()
  }
}
out.outcome = FH ? 'cited (human-supplied)' : out.validated ? 'cited' : 'cited (card not validated)'
return await end()
