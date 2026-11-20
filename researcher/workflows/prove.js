export const meta = {
  name: 'academy-prove',
  description: 'Take one notebook claim to a reviewable proof: an attack first, the related registry statements in the brief, one prover attempt declaring its dependencies, the outcome read from the attempt file, a verify ticket to the Expert only for a complete attempt (saying whether a falsifier is on record)',
  whenToUse: '/researcher:prove and every prove ticket (also nested from the inbox). args: {claim: "<ns:id>", ticket?: "T-NNNN", mode?: "repair", for_verify?: "T-NNNN" (a repair a verify pass asked for: no verify ticket; any other repair that changed the record files a reword or blind verify, #85), home: "<the Researcher home>", instance?: "researcher@<x>"}',
  phases: [
    { title: 'State', detail: 'status, inputs, earlier attempts, falsifier on record, attack, related statements' },
    { title: 'Attempt', detail: 'an attack-only run if none, then one proof attempt' },
    { title: 'File', detail: 'by the attempt file\'s outcome: the verify ticket and the sketch proposal, or the gaps' },
  ],
}

// The order of /researcher:prove in code (2026-10-31; docs/workflows.md): an unattacked
// statement gets one attack-only run first, the outcome is read from the attempt's
// frontmatter by the clerk (never from the prover's summary), and only a complete attempt
// files a verify ticket (by the prover, a liaison toward the Expert; the script checks the
// ticket) and proposes sketch. Nothing is set above sketch.
// 2026-11-20 (the human's design, as revised the same day): the attempt never waits for a
// falsifier; a falsifier is triggered by a failure. An attempt that is not complete (failed,
// or complete with gaps or undeclared dependencies after the fix round), on a claim with no
// falsifier on record and none pending, gets one: lead-researcher (a liaison toward the
// Scientist, permissions.json researcher->scientist; the prover is none) files an experiment
// or test ticket that tries to break the claim where the attempt failed. Delivery is
// unchanged; the result names the ticket. A run lost to a limit files nothing. A clerk stage lists the related registry
// statements (the paper's and the notebooks') for the prover's brief: cite, never reprove. The
// attempt declares its dependencies in its frontmatter; a complete attempt without them, or
// with an input its Inputs section names left out, is not complete, and the verify ticket
// names them (refs and ask).

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
if (!A.claim || !/^([a-z][a-z0-9]*:)?[A-Za-z][\w.:-]*$/.test(A.claim)) throw new Error('args.claim must be a registry id, got ' + JSON.stringify(A.claim))
if (!A.home) throw new Error('args.home must be the Researcher home')
const CLERK = 'researcher:review-clerk'
const PROVER = 'researcher:prover'
const LEAD = 'researcher:lead-researcher'
const T = A.ticket || ''
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const SCRIPTS = `Scripts: notebook.py is \`py ${AR}/researcher/scripts/notebook.py --home ${A.home}\` (python3 where there is no py)` +
  (ROOT ? '.\n' : '; <academy repo> is academy.root of the MCP tool workspace_get (academy.scripts.researcher is the scripts folder).\n')
const STAGE = (name, lines) => `WORKFLOW STAGE ${name} of the academy-prove workflow. Claim: ${A.claim}. Home: ${A.home}.` +
  (A.instance ? ` Instance: ${A.instance}.` : '') + (T ? ` Ticket: ${T}.` : '') + '\n' + SCRIPTS + lines.filter(Boolean).join('\n')

const STATE = { type: 'object', properties: {
  ok: { type: 'boolean' }, stop_reason: { type: 'string' },
  status: { type: 'string', description: 'the claim\'s registry status' },
  unsettled_inputs: { type: 'array', items: { type: 'string' }, description: 'depends_on / modulo inputs that are not proved' },
  attempts: { type: 'array', items: { type: 'string' }, description: 'earlier attempt paths' },
  falsified: { type: 'boolean', description: 'a falsifier counts (falsifier_source is not none)' },
  falsifier_evidence: { type: 'string', description: 'where it is: the report, direction item, thread line or waiver, quoted or pointed at' },
  falsifier_source: { type: 'string', enum: ['claim', 'input', 'parent', 'ticket', 'waived', 'none'],
    description: 'claim: a falsifier attacked this claim; input: one recorded on a declared input (depends_on) whose class or statement covers this claim; parent: one on the parent lead or direction item that covers it; ticket: the ticket thread records one; waived: the human waived it on the ticket or the claim; none' },
  falsifier_on: { type: 'string', description: 'for input or parent: the id it is recorded on; else empty' },
  inputs: { type: 'array', items: { type: 'string' }, description: 'the claim\'s declared inputs: depends_on, and the other-namespace inputs its record names as inputs (a registry resolves depends_on only in its own namespace), verbatim' },
  attack_exists: { type: 'boolean', description: 'proofs/<id>/attack.md exists (true or false, by listing proofs/<id>/)' },
  repair: { type: 'boolean', description: 'the ticket asks to repair, polish, restyle or record an argument for the claim, or answers a negative review of it (GAP, a hypothesis to add): not a first proof' },
  repair_ask: { type: 'string', description: 'what the ticket asks to repair, one line (empty if not a repair)' },
  for_verify: { type: 'string', description: 'the verify ticket T-NNNN when the ticket\'s ask carries the marker "amendment for verify T-NNNN pass <pass>" (a repair a verify pass asked for, the dependency amendment); else empty' },
  for_verify_pass: { type: 'string', description: 'the pass that marker names; else empty' },
  statement_hash: { type: 'string', description: 'the claim\'s statement hash now, the registry engine\'s (reviews.py hash --claim <id>)' },
  falsifier_statement_hash: { type: 'string', description: 'the statement hash the falsifier attacked, read first from a lab claim\'s frontmatter falsifies: entry <ns:id>@<hash> for this claim, then the "statement hash <h>" a request\'s ask names; a waiver, the hash it names; else empty' },
  falsifier_pending: { type: 'string', description: 'a falsifier on this claim filed and not back (an experiment or test ticket to the Scientist, or a falsifier request, open, accepted, in progress or blocked): its id; else empty' },
  falsifier_pending_status: { type: 'string', description: 'that ticket\'s status; else empty' } },
  required: ['ok', 'status', 'unsettled_inputs', 'attempts', 'falsified', 'falsifier_evidence', 'repair'] }
// #124: attack_exists is asked for, named in the stage, and not required (22 clerk runs lost to
// 'must have required property attack_exists' in the ledger since 2026-11-14); a missing or
// non-boolean one is unknown, never false and never a skip: the attack-only run goes ahead once,
// told to read an existing attack.md first and stop if one is present (nothing overwritten)
// #124 follow-up 2: stop_reason (STATE) and detail (MOVE) are asked for and never required either; a
// missing reason reads 'no reason given'
// The attack-only run answers whether proofs/<id>/attack.md existed before it started and whether it
// wrote it (the b5470b7 review): an overwrite is an ANOMALY found by this check, not left to the
// prompt. Neither is required (a prover that left one out would lose a max-tier run); a missing
// one is unknown and noted.
const ATTACK = { type: 'object', properties: {
  existed_before: { type: 'boolean', description: 'proofs/<id>/attack.md existed before this run wrote anything (list proofs/<id>/ first)' },
  wrote: { type: 'boolean', description: 'this run wrote proofs/<id>/attack.md' },
  summary: { type: 'string', description: 'one line: the counterexample, the unlisted hypothesis, or the attack that failed' } },
  required: [] }
const PATH = { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] }
const FOR_VERIFY = { type: 'object', properties: { found: { type: 'boolean' }, kind: { type: 'string' },
  refs: { type: 'array', items: { type: 'string' } }, status: { type: 'string' },
  waiting_on: { type: 'array', items: { type: 'string' } }, this_parent: { type: 'string', description: 'the parent of the prove ticket itself, or empty' } },
  required: ['found', 'kind', 'refs', 'status', 'waiting_on', 'this_parent'] }
const OUTCOME = { type: 'object', properties: {
  exists: { type: 'boolean' }, outcome: { type: 'string', description: 'the attempt frontmatter\'s outcome: field, verbatim' },
  gaps: { type: 'array', items: { type: 'string' } }, objects: { type: 'array', items: { type: 'string' }, description: 'claims the attempt names (partial results)' },
  dependencies_declared: { type: 'boolean', description: 'the frontmatter has a dependencies: key (the code decides whether an empty list declares them)' },
  dependencies: { type: 'array', items: { type: 'string' }, description: 'the frontmatter\'s dependencies: items, verbatim, in order' },
  inputs_listed: { type: 'array', items: { type: 'string' }, description: 'the registry ids and bib:<key>#<pinpoint> citations named in its "## Inputs and their status" section, verbatim' },
  inputs_not_used: { type: 'array', items: { type: 'string' }, description: 'those of inputs_listed that the section marks as not used by the proof, verbatim (else empty)' } },
  required: ['exists', 'outcome', 'gaps', 'objects', 'dependencies_declared', 'dependencies', 'inputs_listed', 'inputs_not_used'] }
const RELATED = { type: 'object', properties: {
  related: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string', description: 'the registry id with its namespace (paper:lem:x, flat:GEO-2)' },
    status: { type: 'string', description: 'its registry status, verbatim (- for a definition)' },
    statement: { type: 'string', description: 'its statement, one line' } }, required: ['id', 'status', 'statement'] } },
  queries: { type: 'array', items: { type: 'string' }, description: 'every command or tool call run, verbatim' } },
  required: ['related', 'queries'] }
const RELATED_CAP = 12
const CONFIRMED = { type: 'object', properties: {
  claim_id: { type: 'string', description: 'the claim\'s own id with its namespace, as claims_show gives it' },
  rows: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string', description: 'the id as listed, verbatim' },
    qualified: { type: 'string', description: 'its id with its namespace, as claims_show gives it (empty if not found)' },
    found: { type: 'boolean', description: 'claims_show (or registry.py show) found it' },
    status: { type: 'string', description: 'its registry status as claims_show gives it, verbatim (- for a definition; empty if not found)' } },
    required: ['id', 'qualified', 'found', 'status'] } } },
  required: ['claim_id', 'rows'] }
const FILED = { type: 'object', properties: { ticket: { type: 'string' }, proposal: { type: 'string', description: 'the decision ticket of the sketch proposal, or empty' }, refusal: { type: 'string' } }, required: ['ticket', 'proposal', 'refusal'] }
const TICKET = { type: 'object', properties: { found: { type: 'boolean' }, to: { type: 'string' }, kind: { type: 'string' }, refs: { type: 'array', items: { type: 'string' } },
  title: { type: 'string', description: 'its title, verbatim' } }, required: ['found', 'to', 'kind', 'refs'] }
// #85, the rest (the audit of 2026-11-20): a repair that edits the claim's record re-checks its
// status on the new text. Before the attempt one clerk stage records the proof the status rests
// on and its hash; after an incomplete attempt (a complete one files its own blind verify)
// a second one hashes the statement and that proof again. Nothing is required (#124): a
// missing answer is unknown, and an unknown comparison files nothing and says how to check.
const RECORD_BEFORE = { type: 'object', properties: {
  confirmed_pass: { type: 'string', description: 'the claim\'s last pass (not a -reword pass) whose decision.md records confirmed or confirmed-modulo (reviews.py list <claim>), its name verbatim; else empty' },
  reviewed_proof: { type: 'string', description: 'the proof the claim\'s status rests on: the one that pass reviewed (its decision.md heading names it), else the record\'s proof: field; a path relative to the home' },
  reviewed_proof_hash: { type: 'string', description: 'the output of reviews.py hash --file <that file>, verbatim; empty when there is no such file' },
  proof: { type: 'string', description: 'the record\'s proof: field now, verbatim; else empty' } },
  required: [] }
const RECORD_AFTER = { type: 'object', properties: {
  statement_hash: { type: 'string', description: 'the claim\'s statement hash now (reviews.py hash --claim <id>), verbatim' },
  reviewed_proof_hash: { type: 'string', description: 'the output of reviews.py hash --file <the file named>, verbatim; empty when it is gone' },
  proof: { type: 'string', description: 'the record\'s proof: field now, verbatim; else empty' } },
  required: [] }
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
    : m && !/^(delivered|rejected|partial)$/.test(m[1]) ? { status: 'not-run', detail: `${s.ticket} is ${m[1]}: no checkpoint for an unfinished ticket` }
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

const out = { claim: A.claim, ticket: T || null, notes: [], launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }
const MODEL_STAGE = { agentType: CLERK, phase: 'Attempt', notes: out.notes }
const end = async () => {
  if (!A.nested) out.ship = await ship({ role: 'researcher', ticket: T, done: !!(out.ticket_delivered || out.ticket_partial), instance: A.instance, topic: 'prove-' + A.claim,
    only: '<home submodule> board', agentType: CLERK, phase: 'File', notes: out.notes })
  return out
}
// #100 part 1 (the human's ruling, 2026-11-20): an attempt that is not complete is the work
// done with the deliverable not met: the ticket goes partial (its sender reopens, closes or
// cancels it), never delivered
const markPartial = async (result, note) => {
  if (!T) return
  const m = await launch(STAGE('partial', [`Mark ${T} partial (tickets_update status partial, never deliver: true) with result "${('partial: ' + result + fallbackLine()).replace(/"/g, "'")}"` +
    (note ? ` and, in the same call, note "${String(note).replace(/"/g, "'")}"` : '') + '.']),
    { label: 'close', phase: 'File', agentType: CLERK, schema: MOVE, effort: 'low' })
  out.ticket_partial = !!(m && m.ok)
  out.ticket_delivered = false
}
const deliver = async (result, note) => {
  if (!T) return
  const m = await launch(STAGE('close', [`Deliver ${T} (tickets_update deliver: true) with result "${(result + fallbackLine()).replace(/"/g, "'")}"` +
    (note ? ` and, in the same call, note "${String(note).replace(/"/g, "'")}"` : '') + '.']),
    { label: 'close', phase: 'File', agentType: CLERK, schema: MOVE, effort: 'low' })
  out.ticket_delivered = !!(m && m.ok)
}

// ---- State ---------------------------------------------------------------------------
phase('State')
const st = await launch(STAGE('prove-state', [
  T ? `First take ${T}: open -> accepted -> in-progress (leave it if it is in progress already).` : '',
  `Then return: the claim's status (claims_show), its unsettled inputs (depends_on and modulo that are not proved), earlier attempts ` +
  `(notebook.py ls / the object's proof: field), whether a falsifier counts and its source (#117: one that attacked this claim, an experiment or test of the Scientist (proofs/<id>/attack.md, the prover's own attack step, is not a falsifier); or one recorded on a declared input, or on the parent lead or ` +
  `direction item, whose class or statement covers this claim, saying how; or the ticket thread records one; or the human waived it on the ticket or the claim: then quote that thread line verbatim), with the evidence, and the declared inputs, ` +
  `the claim's statement hash now (statement_hash: \`py ${AR}/expert/scripts/reviews.py hash --claim ${A.claim}\`, the registry engine's), ` +
  `the statement hash the falsifier attacked (falsifier_statement_hash: first a lab claim's frontmatter falsifies: ["${A.claim}@<hash>", ...] entry; then the "statement hash <h>" its request's ask names; else empty), ` +
  `any falsifier on this claim filed and not back (an experiment or test ticket to the Scientist, or a "Falsifier for ${A.claim}" request: tickets_list text ${A.claim}) with its status (falsifier_pending, falsifier_pending_status), ` +
  `whether proofs/<id>/attack.md exists (attack_exists: true or false; always return it), and whether the ticket asks for a repair (repair, polish, restyle or record an argument, or answer a negative review) rather than a first proof, with what it asks, ` +
  `and, when its ask carries the marker "amendment for verify T-NNNN pass <pass>", that verify ticket and pass (for_verify, for_verify_pass). Write nothing else.`,
]), { label: 'state', phase: 'State', agentType: CLERK, schema: STATE, effort: 'low' })
if (!st) return Object.assign(out, { outcome: 'not-started', reason: 'the state stage returned nothing' })
if (!st.ok) return Object.assign(out, { outcome: 'not-started', reason: st.stop_reason || 'no reason given' })
// #85: a repair (args.mode 'repair', or a ticket that asks for one) goes on whatever the status; a
// proved claim with no repair asked is handed back, never delivered (nothing was done)
// The dependency amendment (2026-11-20 review): a repair a verify pass asked for (the marker
// "amendment for verify T-NNNN pass P" in the ask, or args.for_verify) files no verify ticket,
// since run B of that pass, on the amended proof, is the second verdict; an incomplete one is
// blocked on the human, and files a falsifier as any failed attempt does
const RE_TICKET = /^T-\d{4,}$/
let forVerify = [A.for_verify, st.for_verify].map(x => String(x || '').trim()).find(x => RE_TICKET.test(x)) || ''
for (const x of [A.for_verify, st.for_verify]) {
  if (String(x || '').trim() && !RE_TICKET.test(String(x).trim())) out.notes.push(`for_verify ${JSON.stringify(x)} is not a ticket id: ignored`)
}
// The marker is checked against the verify ticket it names (second look at 7044d82: on its
// shape alone, any prove ticket quoting it would skip its own verify ticket): it must be a
// verify ticket on this claim, blocked and waiting on this very ticket.
if (forVerify) {
  const vt = T ? await launch(STAGE('for-verify', [`tickets_get ${forVerify} and return whether it was found, its kind, refs, status and waiting_on; and tickets_get ${T} and return its parent. Write nothing.`]),
    { label: 'check for-verify', phase: 'State', agentType: CLERK, schema: FOR_VERIFY, effort: 'low' }) : null
  const same = r => { const x = String(r || '').trim(), c = String(A.claim).trim(); return x === c || x.endsWith(':' + c) || c.endsWith(':' + x) }
  const why = !T ? 'it has no ticket of its own to be waited on'
    : !vt ? 'the check stage returned nothing'
    : !vt.found ? `${forVerify} was not found`
    : vt.kind !== 'verify' ? `${forVerify} is a ${vt.kind || '?'} ticket, not verify`
    : !(vt.refs || []).some(same) ? `${forVerify} does not name ${A.claim}`
    // the wait alone ties the repair to the pass: verify.js blocks the verify ticket on the
    // repair it files (a child ticket of a verify ticket that waits on something else is
    // not its repair; third look at 3759900)
    : vt.status !== 'blocked' || !(vt.waiting_on || []).includes(T)
      ? `${forVerify} is ${vt.status || '?'} and does not wait on ${T}`
      : ''
  if (why) {
    out.notes.push(`the marker names ${forVerify}, but ${why}: not a repair for a verify pass (its verify ticket is filed as usual)`)
    forVerify = ''
  }
}
const repair = A.mode === 'repair' || !!st.repair || !!forVerify
out.repair = repair
if (forVerify) {
  out.for_verify = forVerify
  out.notes.push(`a repair for the verify pass of ${forVerify}${st.for_verify_pass ? ' (pass ' + st.for_verify_pass + ')' : ''}: no verify ticket is filed (run B of that pass is the second verdict)`)
}
if (/^proved$/.test(st.status) && !repair) {
  return Object.assign(out, { outcome: 'already-proved', already_proved: true,
    reason: `${A.claim} is proved and the ticket asks for no repair: nothing attempted, the ticket left as it was (rerun with mode repair, or deliver or cancel it)` })
}
// #117: a falsifier on a declared input or the parent lead counts when it covers the claim, and
// so does the human's waiver; checked in code against what the stage reported. Since 2026-11-20
// it decides what the result and the verify ask say is on record, and whether a failed attempt
// files one (with none pending): nothing waits for it
// What the code holds (review of 7ecda27): a known source with evidence; an input that is
// one of the declared inputs (namespace prefixes ignored); a waiver that quotes a thread line
// of the human ("- YYYY-MM-DD human: ..."). That the falsifier covers the claim is the stage's
// report, as the claim's own falsifier always was.
const SOURCES = ['claim', 'input', 'parent', 'ticket', 'waived', 'none']
const bare = x => String(x || '').trim().replace(/^[a-z][a-z0-9]*:/, '')
let src = st.falsifier_source || (st.falsified ? 'claim' : 'none')
if (!SOURCES.includes(src)) { out.notes.push(`falsifier source ${JSON.stringify(src)} is not a known source: not counted`); src = 'none' }
if (st.falsifier_source && (src === 'none') === !!st.falsified) out.notes.push(`the state stage said falsified ${!!st.falsified} with source ${src}: the source decides`)
if (src === 'input' && bare(st.falsifier_on) === bare(A.claim)) src = 'claim'
let counts = src !== 'none'
if (counts && !String(st.falsifier_evidence || '').trim()) {
  counts = false
  out.notes.push(`a ${src} falsifier was reported with no evidence: not counted`)
}
if (counts && src === 'input' && !(st.inputs || []).map(bare).includes(bare(st.falsifier_on))) {
  counts = false
  out.notes.push(`the falsifier named is on ${st.falsifier_on || '(none named)'}, not a declared input of ${A.claim} (${(st.inputs || []).join(', ') || 'none declared'}): not counted`)
}
if (counts && (src === 'input' || src === 'parent') && !st.falsifier_on) counts = false
if (counts && src === 'waived' && !/(^|\n)\s*-?\s*\d{4}-\d{2}-\d{2} human:/.test(st.falsifier_evidence || '')) {
  counts = false
  out.notes.push('a waiver was reported without the human\'s thread line (- YYYY-MM-DD human: ..., the human\'s quoted words; a line "human (via main session):" is the session\'s bookkeeping, and a waiver recorded through the MCP tools needs via: "human" with the quote): not counted')
}
// the same rule as verify.js (2026-11-20): a falsifier counts only on the statement hash it
// attacked, which must be the claim's current one; with the hash unknown only a waiver counts
const hashNow = /^[0-9a-f]{6,}$/.test(String(st.statement_hash || '').trim()) ? st.statement_hash.trim() : ''
const fHash = String(st.falsifier_statement_hash || '').trim()
if (counts && fHash && fHash !== hashNow) {
  counts = false
  out.notes.push(hashNow ? `the ${src} falsifier was recorded on another wording (statement hash ${fHash}, now ${hashNow}): not counted`
    : `the ${src} falsifier's hash ${fHash} cannot be checked (the claim's current hash was not reported): not counted`)
} else if (counts && !fHash) {
  if (src === 'waived') out.notes.push('the waiver\'s statement hash is unknown: counted, a waiver being the human\'s call')
  else { counts = false; out.notes.push(`the ${src} falsifier's statement hash is unknown (it may have attacked an older wording): not counted`) }
}
if (counts) out.falsifier = { source: src, on: st.falsifier_on || null, evidence: st.falsifier_evidence || '' }
out.falsifier_on_record = counts
out.falsifier_source = counts ? src : 'none'
const PENDING_DONE = /^(delivered|closed|rejected|cancelled)$/
const pending = String(st.falsifier_pending || '').trim()
const falsifierPending = /^T-\d{4,}$/.test(pending) && !PENDING_DONE.test(String(st.falsifier_pending_status || '').trim()) ? pending : ''
if (pending && !falsifierPending) out.notes.push(`the falsifier ${pending} reported pending is ${st.falsifier_pending_status || 'not a ticket id'}: not pending`)
if (!counts) out.notes.push(`no falsifier on record for ${A.claim}${falsifierPending ? ` (${falsifierPending} is pending)` : ''}: the attempt goes ahead; a failed or incomplete attempt files one, and the verify ask says none is on record. ` +
  `What counts: an experiment or test ticket to the Scientist that tries to break it (a search over the class it quantifies over, its standard examples first); or one on a declared input or the parent lead whose class covers it; or the human's waiver on the ticket`)
const oneLine = (x, n) => String(x || '').replace(/\s+/g, ' ').trim().replace(/"/g, "'").slice(0, n || 200)
const falsifierLine = counts
  ? `falsifier on record: ${src}${out.falsifier.on ? ' ' + out.falsifier.on : ''} (${oneLine(out.falsifier.evidence, 160)})`
  : 'no falsifier on record'

// The related statements (2026-11-20): what the registry already holds, so the prover cites
// instead of reproving. The clerk searches; one more clerk stage confirms every listed id with
// claims_show (review of fd04646: an id the code never checked went into the brief) and an id
// it cannot confirm is dropped. The code drops the claim itself and duplicates, comparing ids
// with their namespace (s1:GEO-3 is not flat:GEO-3), puts proved and proved-modulo first and
// keeps at most RELATED_CAP.
const rel = await launch(STAGE('related', [
  `Find the registry statements related to ${A.claim}: read it (claims_show), take the terms and objects of its statement, and search every registry of the workspace ` +
  'with them, the paper (paper:) and the notebooks (and the lab): `py ' + AR + '/academy/scripts/registry.py federation` (from the home) names each namespace\'s home; ' +
  'then `registry.py --repo <home> find <term>` in a notebook, `registry.py --repo <home> grep <term>` in the paper or the lab (python3 where there is no py), ' +
  `and claims_show for a match's status. Return the best matches (at most ${RELATED_CAP}; proved and proved-modulo first), each with its id (with its namespace), its status and its statement in one line, ` +
  'and every query run, verbatim. Write nothing.',
]), { label: 'related', phase: 'State', agentType: CLERK, schema: RELATED, effort: 'low' })
const RANK = s => /^proved$/.test(s) ? 0 : /^proved-modulo$/.test(s) ? 1 : 2
const hasNs = x => /^[a-z][a-z0-9]*:/.test(String(x || '').trim())
const listed = []
const seenListed = new Set([String(A.claim).trim()])
if (!rel) out.notes.push('the related-statements stage returned nothing: the prover searches the registry itself')
for (const r of (rel && rel.related) || []) {
  const id = String(r && r.id || '').trim()
  if (!id || seenListed.has(id)) continue
  seenListed.add(id)
  listed.push({ id, statement: oneLine(r.statement, 240) })
}
const related = []
if (listed.length) {
  const conf = await launch(STAGE('confirm-related', [
    `Confirm each of these registry ids with claims_show (or \`registry.py show <id>\` from the home; python3 where there is no py), and resolve ${A.claim} itself the same way: ` +
    listed.map(r => r.id).join(', ') + '. Return for each listed id, verbatim, whether it was found, its id with its namespace and its status as the registry gives them; ' +
    `and ${A.claim}'s own id with its namespace. Never guess: an id you could not show is not found. Write nothing.`,
  ]), { label: 'confirm related', phase: 'State', agentType: CLERK, schema: CONFIRMED, effort: 'low' })
  const rows = new Map(((conf && conf.rows) || []).filter(x => x && x.id).map(x => [String(x.id).trim(), x]))
  const claimQ = String((conf && conf.claim_id) || '').trim() || String(A.claim).trim()
  const selfIds = new Set([claimQ].concat(hasNs(A.claim) ? [String(A.claim).trim()] : []))
  const seen = new Set()
  const dropped = []
  for (const r of listed) {
    const c = rows.get(r.id)
    if (!c || !c.found) { dropped.push(r.id); continue }
    // the confirmed id must be the listed one (with its namespace added), never another
    let q = String(c.qualified || '').trim() || r.id
    if (!(q === r.id || q.endsWith(':' + r.id) || r.id.endsWith(':' + q))) { dropped.push(r.id + ' (confirmed as ' + q + ')'); continue }
    if (selfIds.has(q) || seen.has(q)) continue
    seen.add(q)
    related.push({ id: q, status: oneLine(c.status, 40) || '?', statement: r.statement })
  }
  if (!conf) out.notes.push(`the confirm stage for the related statements returned nothing: none of ${listed.length} listed goes to the prover, which searches the registry itself`)
  else if (dropped.length) out.notes.push(`related statements not confirmed by claims_show, dropped from the brief: ${dropped.join(', ')}`)
}
related.sort((x, y) => RANK(x.status) - RANK(y.status))   // stable: the clerk's order within a rank
out.related = related.slice(0, RELATED_CAP)
if (related.length > RELATED_CAP) out.notes.push(`the related-statements stage returned ${related.length} statements: the first ${RELATED_CAP} go to the prover`)
const relatedBrief = out.related.length
  ? 'Related statements already in the registry (the clerk\'s search; ' + ((rel && rel.queries) || []).length + ' queries):\n' +
    out.related.map(r => `- ${r.id} (${r.status}): ${r.statement}`).join('\n') + '\n' +
    'Cite (use as an input) each one that does the work, and never reprove a proved statement: a cited one goes in dependencies: and in Inputs and their status. ' +
    'Under ## Related statements of the attempt, say for each one listed here either "used as input" or why not. '
  : 'The clerk found no related statement in the registry' + (rel ? '' : ' (its stage returned nothing)') +
    ': search it yourself (claims_list, claims_query) before proving anything; never reprove a proved statement. '
const modulo = (st.unsettled_inputs || []).length ? `It rests on unsettled inputs (${st.unsettled_inputs.join(', ')}): it can be proved at most proved-modulo them; say so in the attempt.` : ''

// ---- Attempt ---------------------------------------------------------------------------
phase('Attempt')
let attacked = false
const attackKnown = typeof st.attack_exists === 'boolean'
if (!attackKnown) out.notes.push('the state stage did not say whether proofs/<id>/attack.md exists (attack_exists missing): unknown, so the attack-only run went ahead once, told to read an existing attack.md and stop if one is present')
if (!attackKnown || !st.attack_exists) {
  const atk = await launchMax(`Attack-only run on ${A.claim} (home ${A.home}), briefed with academy/skills/rigor/references/attack-brief.md: you prove nothing. ` +
    (attackKnown ? '' : 'If proofs/<id>/attack.md already exists, read it first and stop there: write nothing and return (the state stage could not say whether one exists). ') +
    `Write proofs/<id>/attack.md: a counterexample, an unlisted hypothesis, or the attack that failed and why; its frontmatter carries statement_hash: ${hashNow || '<the claim\'s statement hash>'}. ` +
    'Return whether proofs/<id>/attack.md existed before you wrote anything (existed_before), whether you wrote it (wrote), and the attack in one line.',
    { label: 'attack', phase: 'Attempt', agentType: PROVER, schema: ATTACK }, MODEL_STAGE)
  if (atk === null) return Object.assign(out, { outcome: 'lost', reason: 'the attack run returned nothing (a limit?): nothing further launched' })
  attacked = true
  const before = atk && typeof atk.existed_before === 'boolean' ? atk.existed_before : null
  const wrote = atk && typeof atk.wrote === 'boolean' ? atk.wrote : null
  out.attack = { existed_before: before, wrote }
  if (before === null) out.notes.push('the attack run did not say whether proofs/<id>/attack.md existed before it (existed_before missing): an overwrite could not be checked')
  if (before && wrote !== false) out.notes.push(`ANOMALY: the attack run ${wrote ? 'overwrote' : 'may have overwritten (wrote unknown)'} an existing proofs/<id>/attack.md` +
    (attackKnown ? ' that the state stage reported absent' : '') + ': compare it with its git history before relying on it')
  else if (before && attackKnown) out.notes.push('the attack run found proofs/<id>/attack.md although the state stage reported none; it left it as it was')
  out.notes.push('one attack-only run first (proofs/<id>/attack.md)')
}
// #85: what the repair's status rests on, recorded before the attempt can edit the record (not
// for the dependency amendment, whose pass is still open and reviews the amended proof itself)
const REVIEWS = `py ${AR}/expert/scripts/reviews.py`
const recordCheck = repair && !forVerify
let recBefore = null
if (recordCheck) {
  recBefore = await launch(STAGE('repair-before', [
    `This repair may edit the record of ${A.claim}: record what its status rests on now. Run \`${REVIEWS} list ${A.claim}\` (add --home <the library home, workspace_get> when it finds no reviews) ` +
    'and read each pass\'s decision.md: confirmed_pass is the last pass, not one whose name ends in -reword, that records confirmed or confirmed-modulo (else empty). ' +
    'reviewed_proof is the proof that pass reviewed (its decision.md heading names it), else the record\'s proof: field, as a path relative to the home; ' +
    `reviewed_proof_hash is the output of \`${REVIEWS} hash --file <home>/<reviewed_proof>\` (empty when there is no such file); proof is the record's proof: field now. Write nothing.`,
  ]), { label: 'repair before', phase: 'Attempt', agentType: CLERK, schema: RECORD_BEFORE, effort: 'low' })
  if (!recBefore) out.notes.push('the repair-before stage returned nothing: whether this repair changes the record is not checked')
}
const p = await launch(STAGE('attempt-path', ['Run notebook.py attempt <id> --create and return the attempt path it prints.']),
  { label: 'attempt path', phase: 'Attempt', agentType: CLERK, schema: PATH, effort: 'low' })
if (!p || !p.path) return Object.assign(out, { outcome: 'not-started', reason: 'no attempt path' })
out.attempt = p.path
const proved = await launchMax(`Prove ${A.claim} (home ${A.home}) in the attempt file ${p.path}, per your agent definition: scout prior art first (cite before reproving), ` +
  `then the statement as attempted, the strategy, the proof, the inputs with their statuses, and the gaps; set outcome: in its frontmatter. ` +
  'State the dependencies as part of the proof: the frontmatter\'s dependencies: lists every registry id and bib:<key>#<pinpoint> the proof relies on, ' +
  'the same items as Inputs and their status (an attempt without it is not complete and is not filed for review). ' + relatedBrief +
  (st.attempts.length ? `Earlier attempts: ${st.attempts.join(', ')} (a repair is this new attempt; the old ones stay). ` : '') +
  (attacked ? 'Read proofs/<id>/attack.md first. ' : '') +
  (repair ? `This is a repair of a ${st.status} claim${T ? ' (ticket ' + T + ': tickets_get it)' : ''}: ${st.repair_ask || 'what the ticket asks'}. Fix exactly that in this new attempt, and make the record edits the ticket asks (the statement only if it asks). ` : '') +
  modulo + ' Set no status.',
  { label: 'attempt', phase: 'Attempt', agentType: PROVER }, MODEL_STAGE)
if (proved === null) return Object.assign(out, { outcome: 'lost', reason: 'the prover returned nothing (a limit?): nothing further launched' })

// ---- File: by the file, not by the summary ------------------------------------------------
phase('File')
const readOutcome = label => launch(STAGE('attempt-outcome', [`Read ${p.path}: return its frontmatter's outcome: field verbatim, its gaps, the claims it names, ` +
  'whether the frontmatter has a dependencies: key and its items verbatim, the registry ids and bib:<key>#<pinpoint> citations its "## Inputs and their status" section names, ' +
  'and which of those the section marks as not used by the proof. Write nothing.']),
  { label, phase: 'File', agentType: CLERK, schema: OUTCOME, effort: 'low' })
// the declared dependencies: a list in the frontmatter, holding every input the Inputs section
// names as used (one ref matches another written with or without its namespace). An empty
// list declares them only when that section names no input the proof uses (review of fd04646:
// an empty list next to used inputs is a list left unwritten).
const clean = xs => [...new Set((xs || []).map(x => String(x || '').trim()).filter(Boolean))]
const sameRef = (a, b) => a === b || a.endsWith(':' + b) || b.endsWith(':' + a)
const depCheck = o => {
  const deps = clean(o.dependencies)
  const notUsed = clean(o.inputs_not_used)
  const used = clean(o.inputs_listed).filter(x => !notUsed.some(n => sameRef(n, x)))
  const undeclared = used.filter(x => !deps.some(d => sameRef(d, x)))
  const gaps = !o.dependencies_declared ? ['the frontmatter declares no dependencies: list']
    : !deps.length && used.length ? [`the dependencies: list is empty but the Inputs section names inputs the proof uses: ${used.join(', ')}`]
    : undeclared.length ? [`inputs not in its dependencies: ${undeclared.join(', ')}`] : []
  return { deps, used, gaps }
}
let o = await readOutcome('outcome')
if (!o || !o.exists) return Object.assign(out, { outcome: 'unfinished', reason: 'the attempt file is missing or unreadable' })
const completeNoGaps = x => x.outcome === 'complete' && !(x.gaps || []).length
let dc = depCheck(o)
let fixed = false
// review of fd04646, finding 3: a complete attempt whose only defect is its dependencies list
// gets one fix round: the prover fixes the frontmatter of the same file, the clerk reads it again
if (completeNoGaps(o) && dc.gaps.length) {
  fixed = true
  const fx = await launchMax(`Your attempt ${p.path} on ${A.claim} is complete, but its frontmatter's dependencies are not declared: ${dc.gaps.join('; ')}. ` +
    'Fix the frontmatter of that same attempt file, nothing else: its dependencies: key lists every registry id and bib:<key>#<pinpoint> the proof uses ' +
    `(the inputs its "## Inputs and their status" section names as used${dc.used.length ? ': ' + dc.used.join(', ') : ''}; dependencies: [] only when the proof uses no input). ` +
    'Write no new attempt, change no other line, set no status, file nothing.',
    { label: 'fix dependencies', phase: 'File', agentType: PROVER }, MODEL_STAGE)
  const o2 = fx === null ? null : await readOutcome('outcome (after fix)')
  if (o2 && o2.exists) { o = o2; dc = depCheck(o) }
  out.notes.push(fx === null ? 'the dependencies fix round returned nothing: the attempt stays undeclared'
    : !o2 || !o2.exists ? 'the attempt could not be read again after the dependencies fix round'
    : dc.gaps.length ? `one fix round left the dependencies undeclared: ${dc.gaps.join('; ')}`
    : 'one fix round declared the dependencies')
}
out.gaps = o.gaps
const deps = dc.deps
const depGaps = dc.gaps
out.dependencies = deps
// A failed or incomplete attempt triggers the falsifier (2026-11-20): filed by lead-researcher,
// a liaison toward the Scientist (the prover is none), checked by the clerk; it changes no delivery
async function fileFalsifier(gl) {
  if (counts) { out.notes.push(`no falsifier filed: one is on record (${src}${out.falsifier.on ? ' ' + out.falsifier.on : ''})`); return '' }
  if (falsifierPending) { out.notes.push(`no falsifier filed: ${falsifierPending} is pending (${st.falsifier_pending_status || 'status unknown'})`); return '' }
  const target = gl.length ? gl.join('; ') : `the attempt's outcome ${o.outcome || 'without outcome'}, no gap listed`
  const r = await launch(`WORKFLOW STAGE file-falsifier of the academy-prove workflow (lead-researcher, workflow mode): do this only and return the structured result; launch no agent. ` +
    `Claim: ${A.claim}. Home: ${A.home}. The proof attempt ${p.path} is ${o.outcome || 'without outcome'} and ${A.claim} has no falsifier on record and none pending. ` +
    `File exactly one ticket to the Scientist instance (tickets_create from your instance: kind experiment, or test when one named example settles it; to the scientist@ instance of the workspace, workspace_get), ` +
    `title "Falsifier for ${A.claim}", ask: an experiment or test that tries to break ${A.claim} where the attempt failed (${oneLine(target, 600)}): a search over the class it quantifies over, its standard examples first, ` +
    `reporting the bound and the class searched; the ask names the statement it attacks as "statement hash ${hashNow || '<the claim\'s statement hash>'}" and asks that the lab claim record it as falsifies: ["${A.claim}@<that hash>"]; deliverable "what it found: nothing in the class searched, or a counterexample with its certificate", refs [${A.claim}, file:<instance>/${p.path}]${T ? ', parent ' + T : ''}. ` +
    'Write nothing else, set no status. Return the ticket id; a refusal verbatim.',
    { label: 'file falsifier', phase: 'File', agentType: LEAD, schema: FILED, effort: 'low' })
  if (!r || !r.ticket) { out.notes.push('the falsifier was not filed: ' + (r ? r.refusal || 'no ticket id returned' : 'the stage returned nothing')); return '' }
  const c = await launch(STAGE('get', [`tickets_get ${r.ticket} and return its to, kind and refs.`]), { label: 'check falsifier', phase: 'File', agentType: CLERK, schema: TICKET, effort: 'low' })
  if (!c || !c.found || !/^scientist@/.test(c.to) || !/^(experiment|test)$/.test(c.kind) || !(c.refs || []).some(x => sameRef(String(x).trim(), A.claim))) {
    out.notes.push(`ANOMALY: the falsifier ticket ${r.ticket} is not an experiment or test ticket to the Scientist naming ${A.claim}`)
  }
  out.falsifier_ticket = r.ticket
  out.notes.push(`falsifier filed on the failed attempt: ${r.ticket} (targets: ${oneLine(target, 200)})`)
  return r.ticket
}
const falsLine = id => id ? `; falsifier filed: ${id}` : ''

// #85, the rest: after an incomplete repair (a complete one files its own blind verify, which
// reviews the new text), compare the record with what the repair-before stage recorded. Changed,
// with a review standing on the old text (proved or proved-modulo, or a confirmed pass): a verify
// ticket to the Expert, filed by lead-researcher (a researcher->expert liaison) and checked by the
// clerk. Reword mode (conclude.md section 7: one informed run R over the CONFIRMED x2 base) only
// when the statement moved and the reviewed proof did not: reword-brief refuses an unchanged
// statement, and a changed proof takes the blind pass. The inbox reads reword mode from the
// title's "(reword of <pass>)". A changed proof after an incomplete attempt files nothing (review
// of 62be9fa: a blind pass on an attempt its prover reported incomplete is a GAP and adds
// nothing): the result and a thread note say the status no longer stands on the reviewed text
// and that a verify follows the next complete attempt. Unchanged: the result says why none is
// needed; unknown: it says how to check. A confirmed pass that names no reviewed proof compares
// nothing: unknown, never untouched. Returns {clause, ticket, note} for the delivered result.
const RE_PASS = /^\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?$/
const isHash = x => /^[0-9a-f]{6,}$/.test(String(x || '').trim())
async function recheckRecord() {
  const none = (why, needed) => {
    out.record_verify = null
    out.record_verify_why = why
    return { clause: `; ${needed ? 'no verify ticket needed' : 'no verify ticket for the record'}: ${why}` }
  }
  const how = `compare \`${REVIEWS} hash --claim ${A.claim}\` with ${hashNow || 'the hash before the repair (not reported)'} by hand`
  if (!recBefore) return none(`the record check did not run (the repair-before stage returned nothing): ${how}`)
  const reviewed = String(recBefore.reviewed_proof || '').trim()
  const aft = await launch(STAGE('repair-after', [
    `The repair attempt ${p.path} is done: hash the record of ${A.claim} again. statement_hash is the output of \`${REVIEWS} hash --claim ${A.claim}\`; ` +
    (reviewed ? `reviewed_proof_hash is the output of \`${REVIEWS} hash --file <home>/${reviewed}\` (empty when the file is gone); ` : 'reviewed_proof_hash is empty; ') +
    'proof is the record\'s proof: field now. Write nothing.',
  ]), { label: 'repair after', phase: 'File', agentType: CLERK, schema: RECORD_AFTER, effort: 'low' })
  if (!aft) return none(`the record check after the attempt returned nothing: ${how}`)
  const hAfter = isHash(aft.statement_hash) ? String(aft.statement_hash).trim() : ''
  const stmt = !hashNow || !hAfter ? 'unknown' : hAfter === hashNow ? 'same' : 'changed'
  const pBefore = String(recBefore.proof || '').trim()
  const pAfter = String(aft.proof || '').trim()
  const rhB = String(recBefore.reviewed_proof_hash || '').trim()
  const rhA = String(aft.reviewed_proof_hash || '').trim()
  const cp = String(recBefore.confirmed_pass || '').trim()
  const base = RE_PASS.test(cp) && !/-reword$/.test(cp) ? cp : ''
  if (cp && !base) out.notes.push(`the confirmed pass ${JSON.stringify(cp)} reported is no base pass name: no reword base`)
  // no reviewed proof named: with a confirmed pass a proof was reviewed and nothing was compared
  const proof = pBefore !== pAfter ? 'changed' : !reviewed ? (base ? 'unknown' : 'same') : !isHash(rhB) ? 'unknown' : rhA === rhB ? 'same' : 'changed'
  out.record_change = { statement: stmt, proof, statement_hash_before: hashNow || null, statement_hash_after: hAfter || null,
    reviewed_proof: reviewed || null, proof_before: pBefore || null, proof_after: pAfter || null, confirmed_pass: base || null }
  if (stmt === 'same' && proof === 'same') {
    return none(`statement hash ${hashNow} unchanged and the reviewed proof ${reviewed || '(none on the record)'} untouched`, true)
  }
  if (stmt !== 'changed' && proof !== 'changed') {
    return none(`the record could not be compared (statement ${stmt}, reviewed proof ${proof}): ${how}` +
      (reviewed ? `, and \`${REVIEWS} hash --file <home>/${reviewed}\` with ${isHash(rhB) ? rhB : 'its hash before (not reported)'}` : ''))
  }
  const what = [stmt === 'changed' ? `statement hash ${hashNow} -> ${hAfter}` : '',
    proof === 'changed' ? (pBefore !== pAfter ? `the record's proof: ${pBefore || '(none)'} -> ${pAfter || '(none)'}` : `the reviewed proof ${reviewed} edited`) : ''].filter(Boolean).join('; ')
  if (!(/^proved(-modulo)?$/.test(st.status) || base)) {
    return none(`the record changed (${what}) but no review stands on the old text (status ${st.status}, no confirmed pass)`)
  }
  if (proof === 'changed') {
    out.record_stale = true
    const why = `the record changed (${what}) after an incomplete attempt: the ${st.status} status no longer stands on the reviewed text` +
      `${base ? ' (pass ' + base + ')' : ''}; a verify follows the next complete attempt (a blind pass on an attempt reported incomplete would add nothing)`
    out.notes.push(why)
    return Object.assign(none(why), { note: why })
  }
  const reword = stmt === 'changed' && proof === 'same' && !!base
  const whyBlind = reword ? ''
    : proof === 'unknown' ? 'the reviewed proof could not be compared, and a reword pass needs it unchanged'
    : 'no confirmed pass to reword from (a reword pass needs a CONFIRMED x2 base)'
  const marker = `(reword of ${base})`
  const title = reword ? `Verify ${A.claim} ${marker}` : `Verify ${A.claim}`
  const ask = reword
    ? `Reword review of ${A.claim} (mode reword, base_pass ${base}): the repair${T ? ' ' + T : ''} changed its statement (statement hash ${hashNow} -> ${hAfter}); ` +
      `the proof that pass reviewed (${reviewed || 'its proof'}) is untouched. Does it still prove the new wording?`
    : `Review ${A.claim}: the repair${T ? ' ' + T : ''} changed its record (${what}), and its status (${st.status}${base ? ', pass ' + base : ''}) stands on a review of the old text. ` +
      `Is the argument in ${pAfter || reviewed || 'its proof'} valid from its stated inputs for the statement as it stands? A blind pass, not a reword: ${whyBlind}.`
  const proofRef = reword ? reviewed : (pAfter || reviewed)
  const r = await launch(`WORKFLOW STAGE file-record-verify of the academy-prove workflow (lead-researcher, workflow mode): do this only and return the structured result; launch no agent. ` +
    `Claim: ${A.claim}. Home: ${A.home}. A repair changed the claim's record. File exactly one ticket to the Expert instance (tickets_create from your instance: kind verify, to the expert@ instance of the workspace, workspace_get), ` +
    `title "${title}", ask "${oneLine(ask, 4000)}", deliverable "A verification packet${reword ? ' with the reword run\'s verdict, or the blind pass it calls for' : ' with two verdicts, or one negative verdict'}.", ` +
    `refs [${[A.claim].concat(proofRef ? ['file:<instance>/' + proofRef] : []).join(', ')}]${T ? ', parent ' + T : ''}. Write nothing else, set no status. Return the ticket id; a refusal verbatim.`,
    { label: 'file record verify', phase: 'File', agentType: LEAD, schema: FILED, effort: 'low' })
  if (!r || !r.ticket) {
    const why = `the verify ticket for the changed record (${what}) was not filed: ` + (r ? r.refusal || 'no ticket id returned' : 'the stage returned nothing')
    out.notes.push(why)
    out.record_verify = null
    out.record_verify_why = why
    return { clause: `; ${why}` }
  }
  const c = await launch(STAGE('get', [`tickets_get ${r.ticket} and return its to, kind, refs and title.`]),
    { label: 'check record verify', phase: 'File', agentType: CLERK, schema: TICKET, effort: 'low' })
  if (!c || !c.found || !/^expert@/.test(c.to) || c.kind !== 'verify' || !(c.refs || []).some(x => sameRef(String(x).trim(), A.claim)) ||
      (reword && !String(c.title || '').includes(marker))) {
    out.notes.push(`ANOMALY: the verify ticket ${r.ticket} for the changed record is not a verify ticket to the Expert naming ${A.claim}` +
      (reword ? ` with "${marker}" in its title (what the inbox reads as reword mode)` : ''))
  }
  out.record_verify = { ticket: r.ticket, mode: reword ? 'reword' : 'blind', base_pass: reword ? base : null }
  out.record_verify_why = reword ? `the statement changed (${what}) over the confirmed pass ${base}, the reviewed proof untouched` : whyBlind
  return { ticket: r.ticket, clause: `; ${reword ? 'reword' : 'blind'} verify ticket ${r.ticket} for the changed record (${what}${reword ? ', base pass ' + base : ''})` }
}

if (forVerify && (!completeNoGaps(o) || depGaps.length)) {
  // an incomplete amendment is not delivered: the verify pass would take a delivered repair
  // for the amendment; the human decides
  out.outcome = 'amendment-incomplete'
  const fid = await fileFalsifier((o.gaps || []).concat(depGaps))
  const gl = ((o.gaps || []).concat(depGaps).join('; ') || 'none listed').replace(/"/g, "'")
  if (T) {
    const m = await launch(STAGE('block', [`Block ${T}: tickets_update status blocked, waiting_on [human], reason "the amendment attempt ${p.path} for the verify pass of ${forVerify} is ${o.outcome || 'without outcome'} (gaps: ${gl}): ${forVerify} stays blocked on this repair; the human decides${falsLine(fid)}".`]),
      { label: 'block', phase: 'File', agentType: CLERK, schema: MOVE, effort: 'low' })
    out.ticket_blocked = !!(m && m.ok)
  }
  out.reason = `the amendment attempt ${p.path} is ${o.outcome || 'without outcome'} (gaps: ${gl}): not delivered, no verify ticket${falsLine(fid)}`
  return await end()
}
if (forVerify) {
  out.outcome = 'amendment-delivered'
  await deliver(`complete attempt ${p.path}: the amendment for the verify pass of ${forVerify}${st.for_verify_pass ? ' (pass ' + st.for_verify_pass + ')' : ''}; no verify ticket filed (run B of that pass reviews this attempt)`)
  return await end()
}
if (!completeNoGaps(o) || depGaps.length) {
  out.outcome = 'attempt-incomplete'
  if (depGaps.length) out.dependency_gaps = depGaps
  const gl = (o.gaps || []).concat(o.outcome === 'complete' ? depGaps : [])
  const fid = await fileFalsifier(gl)
  const rec = recordCheck ? await recheckRecord() : { clause: '' }
  // review of 62be9fa, point 3: the line says what was filed (the attempt itself never is)
  await markPartial(`attempt ${p.path} ${o.outcome || 'without outcome'}${o.outcome === 'complete' && depGaps.length ? ' but its dependencies are not declared' + (fixed ? ' after one fix round' : '') : ''}; ` +
    `gaps: ${gl.join('; ') || 'none listed'}; ${rec.ticket ? 'the attempt is filed for no review' : 'nothing filed for review'}${falsLine(fid)}${rec.clause}`, rec.note)
  return await end()
}
const depAsk = deps.length ? `dependencies: ${deps.join('; ')}` : 'dependencies: none declared'
const f = await launchMax(`Your attempt ${p.path} on ${A.claim} is complete. File exactly one verify ticket to the Expert instance (tickets_create: kind verify, ` +
  `title "Verify ${A.claim}", ask "${oneLine(`Review ${A.claim}: is the argument in ${p.path} valid from its stated inputs?${repair ? ' (a repair of the ' + st.status + ' claim)' : ''} ` +
    `${depAsk}. ${falsifierLine}.`, 4000)}", deliverable "A verification packet with two verdicts, or one negative verdict.", ` +
  `refs [${[A.claim, 'file:<instance>/' + p.path].concat(deps).join(', ')}]${T ? ', parent ' + T : ''}). ` +
  (/^open$/.test(st.status) ? `Then propose sketch (claims_propose_status, grounds note "complete attempt ${p.path}"). ` : '') +
  'Return the ticket id and the proposal ticket; a refusal verbatim.',
  { label: 'file verify', phase: 'File', agentType: PROVER, schema: FILED, effort: 'low' }, MODEL_STAGE)
if (!f || !f.ticket) {
  out.outcome = 'blocked'
  out.reason = 'the verify ticket was not filed: ' + (f ? f.refusal : 'the stage returned nothing')
  if (recordCheck) { out.record_verify = null; out.record_verify_why = 'the complete attempt\'s verify ticket was not filed (see reason): once filed, it re-checks the record too' }
  return await end()
}
// #85: the complete repair's own blind verify reviews the new attempt on the statement as it
// stands, so a changed record needs no second ticket
if (recordCheck) {
  out.record_verify = null
  out.record_verify_why = `the verify ticket ${f.ticket} reviews the new attempt and the statement as it stands: no second ticket for the record`
}
const chk = await launch(STAGE('get', [`tickets_get ${f.ticket} and return its to, kind and refs.`]), { label: 'check verify', phase: 'File', agentType: CLERK, schema: TICKET, effort: 'low' })
const bad = !chk || !chk.found || !/^expert@/.test(chk.to) || chk.kind !== 'verify' || !(chk.refs || []).includes(A.claim)
if (bad) out.notes.push(`ANOMALY: the verify ticket ${f.ticket} is not a verify ticket to the Expert naming ${A.claim}`)
const missingRefs = chk && chk.found ? deps.filter(d => !(chk.refs || []).some(r => sameRef(String(r).trim(), d))) : []
if (missingRefs.length) out.notes.push(`ANOMALY: the verify ticket ${f.ticket} does not name the dependencies ${missingRefs.join(', ')} in its refs`)
out.verify_ticket = f.ticket
out.proposal = f.proposal || null
out.outcome = 'verify-filed'
const fal = out.falsifier && out.falsifier.source !== 'claim' ? `; falsifier accepted: ${out.falsifier.source}${out.falsifier.on ? ' ' + out.falsifier.on : ''}` : ''
await deliver(`complete attempt ${p.path}; verify ticket ${f.ticket}${f.proposal ? '; sketch proposed (' + f.proposal + ')' : ''}${fal}` +
  `${counts ? '' : '; no falsifier on record'}; ${depAsk}`)
return await end()
