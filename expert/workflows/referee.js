export const meta = {
  name: 'academy-referee',
  description: 'Whole-paper referee report for one Author instance: the PDF checked fresh (built if stale, never while LaTeX Workshop holds the lock), one cold referee run with a brief built in code, the packet landed by the hook, the ticket delivered',
  whenToUse: '/expert:referee and every referee ticket (also nested from the inbox), from the library home. args: {instance?: "author@<x>", ticket?: "T-NNNN", focus?: "<what the human wants looked at hardest, only if they said>"}',
  phases: [
    { title: 'Prepare', detail: 'the ticket, the Author instance, a fresh PDF' },
    { title: 'Referee', detail: 'one cold referee run; the land_referee hook files the packet' },
    { title: 'Land', detail: 'the packet found, the ticket delivered' },
  ],
}

// The order of /expert:referee in code (2026-10-31; docs/workflows.md). The brief is built
// here from facts only (the PDF, its date, what changed since the last report, the vision
// file, and the human's own focus if given): telling a referee where the weak parts are
// destroys the pass, so nothing else can be added. The referee has no shell, so the clerk
// builds the PDF, and never while author.build.lock is held. The report is landed by the
// expert plugin's land_referee hook (it fires for workflow agents).

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
const CLERK = 'academy:inbox-clerk'
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const T = A.ticket || ''
const clerk = (stage, lines, schema, label, phase) => launch(`WORKFLOW STAGE ${stage} of the academy-referee workflow.\n` + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const START = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' }, instance: { type: 'string', description: 'the Author instance to referee' }, acted_as: { type: 'string' } }, required: ['ok', 'instance', 'acted_as'] }
const PDF = { type: 'object', properties: {
  ok: { type: 'boolean' }, stop_reason: { type: 'string', description: 'why there is no fresh PDF (the build lock stayed, the build failed)' },
  pdf: { type: 'string', description: 'absolute path' }, built: { type: 'string', description: 'YYYY-MM-DD of the PDF' }, rebuilt: { type: 'boolean' },
  vision: { type: 'string', description: 'absolute path of <Author home>/Drafts/vision.md, or empty when there is none' },
  last_report: { type: 'string', description: 'the newest reviews/referee/<instance>/<date>.md in the library, or empty' },
  last_date: { type: 'string' }, changed_since: { type: 'string', description: 'one line: the section files changed in the Author home since last_date (git log), or empty' } },
  required: ['ok', 'pdf', 'built', 'rebuilt', 'vision', 'last_report', 'last_date', 'changed_since'] }
const FOUND = { type: 'object', properties: { packet: { type: 'string' }, blocking: { type: 'number' }, copy: { type: 'string' } }, required: ['packet', 'blocking', 'copy'] }
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

// ---- Max-tier model (docs/config.md, "How the map takes effect"; T-1682): the same block in every
// workflow that launches a max-tier agent (the prover and the graders). The launch value is the
// Models block's map entry for "<plugin:agent>" (args.models, or the map that block resolved once
// for the run when none was given, #83; nested runs get it); an agent the map leaves out runs on its
// file's model:, which is then the workspace's. A value that is no Agent-tool alias is resolved by
// one clerk stage running models.py agent; one still unusable launches on the agent file's
// model:. A run that returns nothing (a usage limit) is relaunched once on FALLBACK_MODEL, the next
// tier down, and the fallback is noted (MODEL_FALLBACKS, for the record and the ticket).
const MODEL_ALIAS = /^(haiku|sonnet|opus|fable)$/
const FALLBACK_MODEL = 'opus'
const MODEL_OUT = { type: 'object', properties: { output: { type: 'string', description: 'the command output, verbatim' } }, required: ['output'] }
const LAUNCH_MODELS = {}
const MODEL_FALLBACKS = []
async function launchModel(name, s) {   // s: {agentType (a clerk with a shell), phase, notes}
  if (Object.prototype.hasOwnProperty.call(LAUNCH_MODELS, name)) return LAUNCH_MODELS[name]
  const map = await modelsMap()   // given, or resolved once for the run: never a stand-in {}
  const given = Object.prototype.hasOwnProperty.call(map, name) ? map[name] : undefined
  let m = null
  if (MODEL_ALIAS.test(String(given || ''))) m = given
  else if (!given) m = null   // the map leaves it out: its file's model is the workspace's
  else {
    if (given) s.notes.push(`args.models gave ${JSON.stringify(given)} for ${name}, which is no launch alias: resolved here`)
    const r = await launch(`WORKFLOW STAGE model. Run \`py ${AR}/academy/scripts/models.py agent ${name} --launch\` once, from the home` +
      (ROOT ? '' : ' (<academy repo> is academy.root of the MCP tool workspace_get)') +
      '. Fix nothing, whatever it prints: return its whole output verbatim.', { label: 'model ' + name, phase: s.phase, agentType: s.agentType, schema: MODEL_OUT, effort: 'low' })
    const w = String(r ? r.output : '').trim()
    if (MODEL_ALIAS.test(w)) m = w
    else s.notes.push(`the launch model of ${name} was not resolved (${r ? JSON.stringify(w.slice(0, 160)) : 'the model stage returned nothing'}): it runs on its agent file's model`)
  }
  LAUNCH_MODELS[name] = m
  return m
}
async function launchMax(prompt, opts, s) {   // launch(prompt, opts) on the launch model of opts.agentType
  const model = await launchModel(opts.agentType, s)
  const r = await launch(prompt, model ? Object.assign({}, opts, { exactModel: model }) : opts)
  if (r !== null || !model || model === FALLBACK_MODEL) return r
  MODEL_FALLBACKS.push(`${opts.label}: ${model} -> ${FALLBACK_MODEL}`)
  s.notes.push(`${opts.label}: the ${model} run returned nothing (a usage limit?); relaunched once on ${FALLBACK_MODEL} (a fallback-model run)`)
  // the lost run may have done part of its work: a stage that files or writes is not idempotent
  return launch('A previous run of this stage was cut off: check what it already did (files written, tickets filed) before doing it again.\n' + prompt,
    Object.assign({}, opts, { label: `${opts.label} (${FALLBACK_MODEL} fallback)`, exactModel: FALLBACK_MODEL }))
}
const fallbackLine = () => MODEL_FALLBACKS.length ? `; model fallback: ${MODEL_FALLBACKS.join(', ')}` : ''

const out = { ticket: T || null, notes: [], launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }

// ---- Prepare ---------------------------------------------------------------------------
phase('Prepare')
let instance = A.instance || ''
let actedAs = ''
if (T) {
  const s = await clerk('start', [`ticket: ${T}`,
    'Move it to in-progress acting as its receiver (open -> accepted -> in-progress; leave it if in progress), then return the Author instance it asks to be refereed ' +
    '(its refs, or its sender when that is an Author instance) and the instance you acted as.'], START, 'start', 'Prepare')
  if (!s || !s.ok) return Object.assign(out, { outcome: 'not-started', reason: s ? s.detail || 'no reason given' : 'the start stage returned nothing' })
  instance = instance || s.instance
  actedAs = s.acted_as
}
const pdf = await clerk('pdf', [
  instance ? `Author instance: ${instance}.` : 'Author instance: the only Author instance in workspace.json (say which; if there are several, return ok false naming them).',
  'Read its .claude/academy.json (config_get): author.main, author.build (dir, cmd, lock) and paths.tex. The PDF is <build.dir>/<main stem>.pdf in the Author home.',
  'If it is missing or older than the newest .tex under paths.tex: if author.build.lock exists, wait for it to go (check every 15 s, at most two minutes); if it stays, return ok false ' +
  '"LaTeX Workshop is building". Otherwise run author.build.cmd in the Author home and use the new PDF (a failed build: ok false with its last error lines). Edit nothing in the Author home.',
  'Also return: whether <Author home>/Drafts/vision.md exists (its absolute path, or empty), the newest report under <library>/reviews/referee/<instance>/ and its date, ' +
  'and one line naming the section files changed in the Author home since that date (git log --since; empty when there is no earlier report).',
], PDF, 'pdf', 'Prepare')
if (!pdf || !pdf.ok) return Object.assign(out, { outcome: 'not-started', reason: pdf ? pdf.stop_reason || 'no reason given' : 'the pdf stage returned nothing' })
instance = instance || (pdf.pdf.match(/(author@[a-z0-9-]+)/) || [])[1] || instance
// a clerk may answer "none: ... does not exist" where the schema asks for empty: only a real
// file counts (a vision .md, an earlier report .md), so the brief never states a false fact
if (!/\.md$/.test(pdf.last_report || '')) { pdf.last_report = ''; pdf.changed_since = '' }
if (!/\.md$/.test(pdf.vision || '')) pdf.vision = ''
if (pdf.rebuilt) out.notes.push(`the PDF was stale and was rebuilt (${pdf.built})`)
Object.assign(out, { instance, pdf: pdf.pdf, built: pdf.built })

// ---- Referee: the brief from facts only ---------------------------------------------------
phase('Referee')
const brief = `Referee ${instance} cold. The PDF is ${pdf.pdf}, built ${pdf.built}. ` +
  (pdf.last_report ? `The last report is ${pdf.last_date}${pdf.changed_since ? '; changed since: ' + pdf.changed_since : ''}. ` : 'There is no earlier report. ') +
  (A.focus ? `The human asks you to look hardest at: ${A.focus}. ` : '') +
  `Do not read the agenda or tickets before your cold reading. After it, check the paper against its vision, ` +
  (pdf.vision ? pdf.vision : 'there is none') + `. Ticket: ${T || 'none'}.`
const r = await launchMax(brief, { label: 'referee', phase: 'Referee', agentType: 'expert:referee' }, { agentType: CLERK, phase: 'Referee', notes: out.notes })
if (r === null) return Object.assign(out, { outcome: 'lost', reason: 'the referee run returned nothing (a limit?): nothing further launched' })

// ---- Land: the hook filed the packet; find it, deliver ------------------------------------------
phase('Land')
const f = await clerk('find', [`The land_referee hook has just filed a referee packet for ${instance}` + (T ? ` linked to ${T}` : '') +
  `. Find it (packets_list / the newest under the board's packets/expert@*/ of kind referee), and return its id, how many findings it marks blocking, and the copy kept under reviews/referee/${instance}/.`],
  FOUND, 'find packet', 'Land')
if (!f || !f.packet) {
  out.notes.push('no referee packet was found: the land_referee hook may not have landed the report (it asks once for the REFEREE block)')
  return Object.assign(out, { outcome: 'unlanded' })
}
Object.assign(out, { packet: f.packet, blocking: f.blocking, copy: f.copy })
if (T) {
  const m = await clerk('move', [`ticket: ${T}`, actedAs ? `act as: ${actedAs}` : '',
    `deliver: deliver: true with result "referee packet ${f.packet}; ${f.blocking} blocking${fallbackLine()}" and fields.packets [${f.packet}]`], MOVE, 'deliver', 'Land')
  out.ticket_delivered = !!(m && m.ok)
}
out.outcome = 'refereed'
if (!A.nested) out.ship = await ship({ role: 'expert', ticket: T, done: !!out.ticket_delivered, instance: actedAs, topic: 'referee-' + instance,
  only: 'library board', agentType: CLERK, phase: 'Land', notes: out.notes })
return out
