export const meta = {
  name: 'academy-generalize',
  description: 'Turn a reviewed experiment\'s Conclusion into conjectures: the source checked by script, one prover writing the proposals file, validated with one retry (then dropped), objects created, the packet filed; the falsifier tests are filed by the main session',
  whenToUse: '/researcher:generalize and every generalize ticket (also nested from the inbox), from the Researcher home. args: {ref: "P-NNNN" | "lab:<id>", ticket?: "T-NNNN" (the generalize ticket), home, instance, file?: <proposals path>, mode?: "propose" | "deliver"}',
  phases: [
    { title: 'Source', detail: 'generalize.py source: the Conclusion and a cleared review' },
    { title: 'Propose', detail: 'one prover writes the proposals file; validate, one retry, then drop' },
    { title: 'Record', detail: 'objects, packet; the tests for the main session' },
  ],
}

// The order of /researcher:generalize in code (2026-10-31; docs/workflows.md): nothing is
// generalized from an experiment whose review has not cleared (generalize.py source refuses);
// the prover writes only the proposals file (at most maxPerRun, never above conjectured;
// lemmas open or sketch); generalize.py validate decides, with one retry before a failing
// proposal is dropped; the objects and the packet come from generalize.py; the test tickets
// are filed by the main session (main is the researcher -> scientist liaison, the prover is
// not), and mode deliver checks they exist before the generalize ticket is delivered.

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
if (!A.ref || !/^(P-\d{4,}|[a-z][a-z0-9]*:\S+)$/.test(A.ref)) throw new Error('args.ref must be a report packet (P-NNNN) or a lab claim id')
if (!A.home) throw new Error('args.home must be the Researcher home')
const MODE = A.mode === 'deliver' ? 'deliver' : 'propose'
const CLERK = 'researcher:review-clerk'
const PROVER = 'researcher:prover'
const T = A.ticket || ''
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const SCRIPTS = `Scripts: generalize.py is \`py ${AR}/researcher/scripts/generalize.py --home ${A.home}\`, packets.py is \`py ${AR}/academy/scripts/packets.py\` (python3 where there is no py)` +
  (ROOT ? '.\n' : '; <academy repo> is academy.root of the MCP tool workspace_get (academy.scripts.<plugin> is each scripts folder).\n')
const clerk = (stage, lines, schema, label, phase) => launch(
  `WORKFLOW STAGE ${stage} of the academy-generalize workflow. Home: ${A.home}.` + (A.instance ? ` Instance: ${A.instance}.` : '') + (T ? ` Ticket: ${T}.` : '') + '\n' + SCRIPTS + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

// #124: the clerk stages ask for their free text (refusal, error, detail) and never require it (a clerk
// that left one out lost its run); a missing one reads 'no reason given'
const SOURCE = { type: 'object', properties: { ok: { type: 'boolean' }, refusal: { type: 'string', description: 'the exit-2 message when the review has not cleared' },
  lab_claim: { type: 'string' }, report: { type: 'string' }, max: { type: 'number', description: 'the cap generalize.py reports (maxPerRun, at most 3)' } },
  required: ['ok', 'lab_claim', 'report', 'max'] }
const CHECKED = { type: 'object', properties: { ok: { type: 'boolean' }, problems: { type: 'array', items: { type: 'string' } },
  failing: { type: 'array', items: { type: 'string' }, description: 'the proposal ids the problems name' }, proposals: { type: 'number' } }, required: ['ok', 'problems', 'failing', 'proposals'] }
const CREATED = { type: 'object', properties: { conjectures: { type: 'array', items: { type: 'string' } }, lemmas: { type: 'array', items: { type: 'string' } }, error: { type: 'string' } }, required: ['conjectures', 'lemmas'] }
const PACKET = { type: 'object', properties: { packet: { type: 'string' }, error: { type: 'string' } }, required: ['packet'] }
const CHILDREN = { type: 'object', properties: { tests: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, refs: { type: 'array', items: { type: 'string' } } }, required: ['id', 'refs'] } } }, required: ['tests'] }
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok'] }

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

const out = { ref: A.ref, ticket: T || null, mode: MODE, notes: [], launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }
const end = async (delivered) => {
  if (!A.nested) out.ship = await ship({ role: 'researcher', ticket: T, done: delivered, instance: A.instance, topic: 'generalize-' + A.ref,
    only: '<home submodule> board', agentType: CLERK, phase: 'Record', notes: out.notes })
  return out
}

// ---- deliver: after the main session filed the tests ---------------------------------------
if (MODE === 'deliver') {
  if (!T) throw new Error('mode deliver needs args.ticket')
  if (!A.conjectures || !A.conjectures.length) throw new Error('mode deliver needs args.conjectures (the ids propose returned)')
  const ch = await clerk('children', [`List the tickets whose parent is ${T} (tickets_list with parent: "${T}" and kind: "test"; tickets_get for one), with their refs. Write nothing.`], CHILDREN, 'children', 'Record')
  const tests = ch ? ch.tests : []
  const missing = A.conjectures.filter(cid => !tests.some(t => (t.refs || []).some(r => r === cid || r.endsWith(':' + cid.split(':').pop()))))
  if (missing.length) return Object.assign(out, { outcome: 'tests-missing', missing, reason: 'no test ticket names ' + missing.join(', ') + ': file them first' })
  const result = `${A.conjectures.length} conjectures filed: ${A.conjectures.join(', ')}; lemmas ${(A.lemmas || []).join(', ') || 'none'}; tests ${tests.map(t => t.id).join(', ')}`
  const m = await clerk('close', [`Deliver ${T} (tickets_update deliver: true) with result "${result.slice(0, 240)}"` + (A.packet ? ` and fields.packets [${A.packet}]` : '') + '.'], MOVE, 'close', 'Record')
  Object.assign(out, { outcome: m && m.ok ? 'delivered' : 'unfinished', tests: tests.map(t => t.id) })
  return await end(!!(m && m.ok))
}

// ---- Source -----------------------------------------------------------------------------
phase('Source')
const s = await clerk('source', [`Run generalize.py source ${A.ref} --json: return ok, or ok false with its exit-2 refusal; the lab claim, the report packet and the cap (max).`,
  T ? `If it is ok, take ${T}: open -> accepted -> in-progress (leave an in-progress ticket as it is).` : 'Touch no ticket.'], SOURCE, 'source', 'Source')
if (!s) return Object.assign(out, { outcome: 'not-started', reason: 'the source stage returned nothing' })
if (!s.ok) return Object.assign(out, { outcome: 'not-started', reason: 'generalize.py source refused: ' + (s.refusal || 'no reason given') + ' (run /researcher:review-experiment first)' })
if (!T) return Object.assign(out, { outcome: 'needs-ticket', needs_ticket: true, lab_claim: s.lab_claim, report: s.report,
  reason: 'no generalize ticket: the main session files one to this instance (kind generalize, refs the lab claim and the report), then calls again with it' })
const LAB = s.lab_claim
const MAX = Math.max(1, Math.min(s.max || 3, 3))
const FILE = A.file || `${A.home}/.academy/generalize-${LAB.replace(/[^A-Za-z0-9._-]+/g, '-')}.json`

// ---- Propose: the file, validated by script ---------------------------------------------------
phase('Propose')
const brief = SCRIPTS + `Generalize the reviewed experiment ${s.report || A.ref} (lab claim ${LAB}; home ${A.home}). Read its ## Conclusion, and the domain's examples.md and ` +
  `theorems/INDEX.md (domain_get) for what is known; scout prior art. Write at most ${MAX} proposals to ${FILE} (create the folder), in the shape generalize.py's docstring gives: ` +
  `id in this instance's namespace, title, statement, kind conjecture, status conjectured, bears_on including ${LAB}, the falsifier, the pattern (wider class / ` +
  `relaxed hypothesis / pattern / invariant) and a one-line rationale; optional lemmas (at most three per proposal, status open or sketch, saying what is known and ` +
  `what is missing). Write ONLY that file: create no object and file no ticket.`
const MODEL_STAGE = { agentType: CLERK, phase: 'Propose', notes: out.notes }
const p1 = await launchMax(brief, { label: 'prover', phase: 'Propose', agentType: PROVER }, MODEL_STAGE)
if (p1 === null) return Object.assign(out, { outcome: 'lost', reason: 'the prover returned nothing (a limit?)' })
const validate = (label) => clerk('validate', [`Run generalize.py validate ${FILE} --lab-claim ${LAB} --json and return ok, the problems, the proposal ids they name, and the number of proposals.`], CHECKED, label, 'Propose')
let v = await validate('validate')
if (v && !v.ok) {
  out.notes.push('the proposals failed validation; sent back to the prover once: ' + v.problems.join('; '))
  const p2 = await launchMax(brief + `\n\nThe file ${FILE} fails generalize.py validate:\n- ${v.problems.join('\n- ')}\nFix those proposals in the file.`,
    { label: 'prover (fix)', phase: 'Propose', agentType: PROVER }, MODEL_STAGE)
  if (p2 === null) return Object.assign(out, { outcome: 'lost', reason: 'the prover fix returned nothing' })
  v = await validate('validate again')
  if (v && !v.ok) {
    out.notes.push(`dropped after a second failure: ${v.failing.join(', ')} (${v.problems.join('; ')})`)
    await clerk('drop', [`Remove the proposals ${v.failing.join(', ')} from ${FILE} (a mechanical edit of the JSON list; change nothing else).`], MOVE, 'drop', 'Propose')
    v = await validate('validate after drop')
    if (!v || !v.ok) return Object.assign(out, { outcome: 'failed', reason: 'the proposals file still fails after dropping: ' + (v ? v.problems.join('; ') : 'no answer') })
  }
}
if (!v || !v.proposals) return Object.assign(out, { outcome: 'nothing-proposed', reason: 'no valid proposal' })

// ---- Record -----------------------------------------------------------------------------------
phase('Record')
const c = await clerk('create', [`Run generalize.py create ${FILE} --lab-claim ${LAB} --apply and return the conjecture ids and the lemma ids it wrote (or its error).`], CREATED, 'create', 'Record')
if (!c || c.error) return Object.assign(out, { outcome: 'failed', reason: 'generalize.py create: ' + (c ? c.error : 'no answer') })
const pk = await clerk('packet', [`Run generalize.py packet-body ${FILE} --lab-claim ${LAB} --report ${s.report} --out ${A.home}/.academy/generalize-body.md, then packets.py new ` +
  `--instance ${A.instance || '<this instance>'} --kind generalization --title "Generalizations of ${LAB}" --ticket ${T} --subject ${c.conjectures.concat(c.lemmas).join(',')} ` +
  `--status-proposed conjectured --body <that file>; return the packet id.`], PACKET, 'packet', 'Record')
Object.assign(out, { lab_claim: LAB, file: FILE, conjectures: c.conjectures, lemmas: c.lemmas, packet: pk && pk.packet ? pk.packet : null })
if (!out.packet) out.notes.push('the packet was not filed: ' + (pk ? pk.error || 'no reason given' : 'no answer'))
// the falsifier tests: lead-researcher (a researcher -> scientist liaison) files the ones
// generalize.py tickets prints; the script then checks a test names each conjecture and delivers
const SPECS = { type: 'object', properties: { specs: { type: 'array', items: { type: 'object' } } }, required: ['specs'] }
const sp = await clerk('test-specs', [`Run generalize.py tickets ${FILE} --lab-claim ${LAB} --parent ${T} (WITHOUT --apply) and return the ticket specs it prints, one object each (to, kind, title, ask, deliverable, refs, parent, detail). File nothing.`],
  SPECS, 'test specs', 'Record')
const filed = await launch(`File exactly these falsifier test tickets to the Scientist instance (tickets_create, one each, as given; you are the researcher -> scientist liaison): ` +
  `${JSON.stringify(sp ? sp.specs : [])}. Return the ticket ids, or the refusals verbatim.`,
  { label: 'file tests', phase: 'Record', agentType: 'researcher:lead-researcher', schema: { type: 'object', properties: { tickets: { type: 'array', items: { type: 'string' } }, refusals: { type: 'array', items: { type: 'string' } } }, required: ['tickets', 'refusals'] } })
if (filed && filed.refusals.length) out.notes.push('test tickets refused: ' + filed.refusals.join('; '))
const ch = await clerk('children', [`List the tickets whose parent is ${T} (tickets_list with parent: "${T}" and kind: "test"; tickets_get for one), with their refs. Write nothing.`], CHILDREN, 'children', 'Record')
const tests = ch ? ch.tests : []
const missing = c.conjectures.filter(cid => !tests.some(t => (t.refs || []).some(r => r === cid || r.endsWith(':' + cid.split(':').pop()))))
if (missing.length || !filed) {
  out.to_file = [{ why: 'the falsifier tests the lead did not file', missing,
    command: `py ${AR}/researcher/scripts/generalize.py tickets ${FILE} --lab-claim ${LAB} --parent ${T} --apply`,
    then: { mode: 'deliver', ticket: T, conjectures: c.conjectures, lemmas: c.lemmas, packet: out.packet } }]
  out.outcome = 'proposed (tests missing)'
  return await end(false)
}
const result = `${c.conjectures.length} conjectures filed: ${c.conjectures.join(', ')}; lemmas ${c.lemmas.join(', ') || 'none'}; tests ${tests.map(t => t.id).join(', ')}`
const m = await clerk('close', [`Deliver ${T} (tickets_update deliver: true) with result "${result.slice(0, 240)}"` + (out.packet ? ` and fields.packets [${out.packet}]` : '') + '.'], MOVE, 'close', 'Record')
out.tests = tests.map(t => t.id)
out.outcome = m && m.ok ? 'delivered' : 'proposed (not delivered)'
return await end(!!(m && m.ok))
