export const meta = {
  name: 'academy-verify',
  description: 'Expert proof review of one registry statement: blind rigor-reviewer A, B only if A is CONFIRMED (in amend mode on the amended proof when A suggested a dependency), or one reword run R; a falsifier request on a GAP verdict; the decision table, the record, evidence, proposal and packet',
  whenToUse: 'Every verify ticket and /expert:verify, from the library home. args: {claim, ticket?, question?, mode?: "blind"|"reword", base_pass?, base_subject?, findings?}',
  phases: [
    { title: 'Prepare', detail: 'take the ticket, hash the statement, open the pass' },
    { title: 'Review', detail: 'blind run A; a suggested dependency added by the producer (filed and waited for); B only if the table says launch_b, or in amend mode once the amendment is in (or run R); a GAP verdict files a falsifier request, which blocks nothing; CONFIRMED x2 on differing inputs (settle-dependencies) launches one dependency-settler, whose record settle_deps.py checks (one retry) and applies' },
    { title: 'Conclude', detail: 'decision table, record, evidence, proposal, packet, follow-ups' },
  ],
}

// The sequencing rules of conclude.md sections 0-2 and 7, held in code rather than
// in prose (the 2026-10-31 decision): the reviewers are separate fresh agents, B is
// launched only when decision_table.py says launch_b and the statement hash has not
// moved, B gets A's brief byte for byte with run B, a reword pass runs R alone, a lost
// run is relaunched once, and nothing but the review-chair's clerical stages touches
// the files. A falsifier is triggered by a GAP verdict (the human's design, 2026-11-20, as
// revised the same day): when run A, or run B after a CONFIRMED A, finds a gap and the claim
// has no clean falsifier on record for this statement hash and none pending, the chair files
// the falsifier request, naming the gap, alongside the follow-up repair; it blocks nothing
// and the pass concludes as before. It is never a gate between A and B; a counterexample
// already on record still concludes the pass with no B and no status. A CONFIRMED A
// that suggests a dependency (add_dependency, the human's design of 2026-11-20) pauses the
// pass the same way: the chair files a repair to the producer (add exactly those to the
// proof and depends_on) and blocks the ticket; on the rerun B runs in amend mode, told the
// suggestion only (reviews.py amend-brief), and A + B are the two verdicts. Two CONFIRMED runs
// whose modulo lists still differ after the table's mechanical reduction (settle-dependencies,
// #121) get one dependency-settler run, its record checked and applied by settle_deps.py (one
// retry; then a disagreement): settled, the follow-ups are filed and the status proposed, nothing
// waiting on them; a stop is a disagreement with the settler's classification for the human.
// The verdicts are landed by the expert plugin's land_verdict hook (it
// fires for workflow agents: B0 pilot, docs/workflows.md).

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
if (!A.claim || !/^[a-z][a-z0-9]*:\S+$/.test(A.claim)) {
  throw new Error('args.claim must be a namespaced registry id (paper:lem:x, flat:GEO-3), got ' + JSON.stringify(A.claim))
}
const MODE = A.mode === 'reword' ? 'reword' : 'blind'
const QUESTION = A.question || 'may it be raised to proved?'
const CHAIR = 'expert:review-chair'
const REVIEWER = 'expert:rigor-reviewer'
const SETTLER = 'expert:dependency-settler'
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const SCRIPTS = `Scripts: reviews.py is \`py ${AR}/expert/scripts/reviews.py\`, decision_table.py is \`py ${AR}/expert/scripts/decision_table.py\`, statement.py (the Author plugin's) is \`py ${AR}/author/scripts/statement.py\` (python3 where there is no py)` +
  (ROOT ? '.\n' : '; <academy repo> is academy.root of the MCP tool workspace_get (academy.scripts.expert is the scripts folder).\n')
const RE_PASS = /^\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?$/
const RE_HASH = /^[0-9a-f]{6,}$/

const PREP = {
  type: 'object',
  properties: {
    ok: { type: 'boolean', description: 'false when the pass must not start (an open pass, a refused reword base)' },
    stop_reason: { type: 'string' },
    pass: { type: 'string' },
    pass_dir: { type: 'string', description: 'absolute path of the pass folder' },
    statement_hash: { type: 'string' },
    location: { type: 'string', description: 'where the statement and proof live: for a statement of a tex file, the line of `statement.py <label> --where` (file, the statement\'s lines, the proof\'s lines); else the object and its proofs/ attempt' },
    bundle: { type: 'string', description: 'reword mode: absolute path of the bundle file; else empty' },
    ticket: { type: 'string', description: 'the ticket id, or none' },
    landed: { type: 'array', description: 'a resumed pass (#89): the run files already in the pass folder, each with the statement_hash of its frontmatter; else empty',
      items: { type: 'object', properties: { run: { type: 'string', description: 'A, B or R' }, statement_hash: { type: 'string' } }, required: ['run', 'statement_hash'] } },
    falsifier: { type: 'object', description: 'the claim\'s falsifier on record (blind mode; the sources prove.js accepts, #117)',
      properties: {
        source: { type: 'string', enum: ['claim', 'input', 'parent', 'ticket', 'waived', 'none'],
          description: 'claim: a falsifier attacked this claim; input: one recorded on a declared input whose class or statement covers it; parent: one on the parent lead or direction item that covers it; ticket: the verify ticket\'s thread, or the falsifier request it waited on, records one that came back; waived: the human waived it on the ticket or the claim; none' },
        on: { type: 'string', description: 'for input or parent: the id it is recorded on; for ticket: the request ticket; else empty' },
        evidence: { type: 'string', description: 'where it is (a report, a result, a direction item, a thread line), quoted or pointed at; a waiver quotes the human\'s thread line verbatim' },
        found: { type: 'string', enum: ['nothing', 'counterexample', ''], description: 'what the falsifier found: nothing (it ran and did not break the claim), a counterexample, or empty (none, or a waiver)' },
        request: { type: 'string', description: 'a falsifier request an earlier run of this pass filed (the verify ticket\'s waiting_on or its thread), or empty' },
        request_status: { type: 'string', description: 'that request\'s status, or empty' },
        statement_hash: { type: 'string', description: 'the statement hash the falsifier attacked, when the record says it: a lab claim\'s falsifies: entry <ns:id>@<hash> for this claim, else for a request this workflow filed the hash its ask names, for a waiver the hash it names; else empty' } },
      required: ['source', 'on', 'evidence', 'found', 'request', 'request_status', 'statement_hash'] },
    inputs: { type: 'array', items: { type: 'string' }, description: 'the claim\'s declared inputs (depends_on, its cites as bib:<key>, and the other-namespace inputs its record names), as the registry reads them now, namespaces and #pinpoints kept (a bib: key the current attempt cites at a pinpoint also as bib:<key>#<pinpoint>), in canonical spelling (`decision_table.py canon --subject <claim> <input>...`)' },
    amendment: { type: 'object', description: 'a dependency amendment this pass asked for (2026-11-20; blind mode)',
      properties: {
        request: { type: 'string', description: 'the repair ticket an earlier run of this pass filed to add run A\'s suggested dependencies (the verify ticket\'s waiting_on or its thread), or empty' },
        request_status: { type: 'string', description: 'that ticket\'s status, or empty' },
        attempt: { type: 'string', description: 'the claim\'s current proof attempt (the record\'s proof: field, or the tex proof\'s lines), the amended one once the repair is back; else empty' },
        reviewed_attempt: { type: 'string', description: 'the proof attempt run A reviewed, as this pass recorded it when it asked for the amendment (the repair\'s ask and the verify ticket\'s block note say "run A reviewed <attempt>"), verbatim; else empty' } },
      required: ['request', 'request_status', 'attempt', 'reviewed_attempt'] },
    researcher: { type: 'string', description: 'blind mode: the instance field of `reviews.py researcher-for <claim> --party <each from and to of the ticket and its parent chain>` (a researcher@ instance, or human)' },
    researcher_why: { type: 'string', description: 'its why field, verbatim' },
  },
  required: ['ok', 'pass', 'pass_dir', 'statement_hash', 'location', 'bundle', 'ticket', 'landed'],     // stop_reason: asked, defaulted (#124)
}
const AMEND_OUT = {
  type: 'object',
  properties: {
    request: { type: 'string', description: 'the repair ticket filed (or the earlier one waited on); empty when none' },
    blocked: { type: 'boolean', description: 'the verify ticket is now blocked' },
    waiting_on: { type: 'array', items: { type: 'string' }, description: 'its waiting_on after the update' },
    refusal: { type: 'string', description: 'a refused tickets_create or tickets_update, verbatim; else empty' },
  },
  required: ['request', 'blocked', 'waiting_on'],     // refusal: asked; absent means none (#124)
}
const BUNDLE_OUT = {
  type: 'object',
  properties: {
    bundle: { type: 'string', description: 'absolute path of the amend bundle written; empty when refused' },
    refusal: { type: 'string', description: 'reviews.py amend-brief\'s refusal, verbatim; else empty' },
  },
  required: ['bundle'],     // refusal: asked; absent means none (#124)
}
const FALS_OUT = {
  type: 'object',
  properties: {
    request: { type: 'string', description: 'the falsifier request ticket filed; empty when none' },
    refusal: { type: 'string', description: 'a refused tickets_create, verbatim; else empty' },
  },
  required: ['request'],     // refusal: asked; absent means none (#124)
}
// #121 part 3: the new stages' schemas require nothing; the code supplies every default
const SETTLE_TABLE_OUT = {
  type: 'object',
  properties: {
    written: { type: 'boolean', description: 'S-table.json was written in the pass folder' },
    outcome: { type: 'string', description: 'the outcome in the JSON written' },
  },
  required: [],
}
const SETTLE_OUT = {
  type: 'object',
  properties: {
    ok: { type: 'boolean', description: 'settle_deps.py check exited 0 (ok true)' },
    problems: { type: 'array', items: { type: 'string' }, description: 'settle_deps.py check problems, verbatim; empty when ok' },
    outcome: { type: 'string', enum: ['confirmed-settled', 'disagreement', ''], description: 'settle_deps.py apply outcome; empty when the check failed' },
    proposed_status: { type: 'string', description: 'apply proposed_status (proved-modulo, proved), or empty' },
    modulo: { type: 'array', items: { type: 'string' } },
    declarations: { type: 'array', items: { type: 'object', properties: { dependency: { type: 'string' }, case: { type: 'number' }, from: { type: 'string' } } } },
    notes: { type: 'array', items: { type: 'object', properties: { kind: { type: 'string' }, dependency: { type: 'string' }, sources: { type: 'array', items: { type: 'string' } }, text: { type: 'string' } } } },
    cite: { type: 'array', items: { type: 'object', properties: { input: { type: 'string' }, evidence: { type: 'string' } } } },
    stops: { type: 'array', items: { type: 'object', properties: { input: { type: 'string' }, case: { type: 'number' }, name: { type: 'string' }, evidence: { type: 'string' } } } },
    dropped: { type: 'array', items: { type: 'object', properties: { input: { type: 'string' }, case: { type: 'number' }, line: { type: 'string' } } } },
    grounds: { type: 'object', description: 'apply grounds, verbatim (null when none)' },
    summary: { type: 'string' },
  },
  required: [],
}
const SETTLE_FILED = {
  type: 'object',
  properties: {
    repair: { type: 'string', description: 'the declaration repair filed, or empty' },
    cite: { type: 'array', items: { type: 'string' }, description: 'the cite tickets filed' },
    author: { type: 'string', description: 'the Author ticket filed for a remark, or empty' },
    blocked: { type: 'boolean', description: 'the verify ticket was blocked (it never should be)' },
    refusals: { type: 'array', items: { type: 'string' }, description: 'refused tickets_create calls, verbatim' },
  },
  required: [],
}
const TABLE = {
  type: 'object',
  properties: {
    landed: { type: 'boolean', description: 'the run file exists in the pass folder' },
    run_file: { type: 'string' },
    verdict: { type: 'string' },
    outcome: { type: 'string', description: 'decision_table.py outcome' },
    launch_b: { type: 'boolean', description: 'decision_table.py launch_b (false when absent)' },
    hash_now: { type: 'string', description: 'reviews.py hash of the statement as it stands now' },
    run_hash: { type: 'string', description: 'the statement_hash in the landed run file\'s own frontmatter (empty when not landed)' },
    add_dependency: { type: 'array', items: { type: 'string' }, description: 'decision_table.py add_dependency: the dependencies the run suggests adding (empty when none)' },
    blocking_step: { type: 'string', description: 'for a GAP verdict: the blocking step the run file names (where it is and, in one line, what fails), as the run states it; else empty' },
  },
  required: ['landed', 'run_file', 'verdict', 'outcome', 'launch_b', 'hash_now', 'run_hash'],
}
const DONE = {
  type: 'object',
  properties: {
    outcome: { type: 'string' },
    proposed_status: { type: 'string', description: 'the proposal filed, or none' },
    record: { type: 'string', description: 'path of decision.md' },
    packet: { type: 'string', description: 'the packet id, or none' },
    tickets: { type: 'array', items: { type: 'string' }, description: 'tickets filed or updated' },
    run_files: { type: 'array', items: { type: 'string' }, description: 'the run files in the pass folder after concluding (ls)' },
    report: { type: 'string', description: 'the report of conclude.md section 6' },
  },
  required: ['outcome', 'proposed_status', 'record', 'packet', 'tickets', 'run_files', 'report'],
}

const STAGE = (name, body) =>
  `WORKFLOW STAGE ${name} of the academy-verify workflow (review-chair, workflow mode). ` +
  `Do this stage only, as conclude.md describes it, and return the structured result. ` +
  `Launch no agent: the workflow launches the reviewers.\n${SCRIPTS}\n${body}`

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

// ---- 1. Prepare -------------------------------------------------------------
phase('Prepare')
const prep = await launch(STAGE('prepare', [
  `claim: ${A.claim}`, `ticket: ${A.ticket || 'none'}`, `mode: ${MODE}`,
  MODE === 'reword' ? `base_pass: ${A.base_pass || '(find it: reviews.py list; the last confirmed pass, blind or reword, #127)'}` : '',
  A.base_subject ? `base_subject: ${A.base_subject}` : '',
  A.findings ? `findings for the bundle: ${A.findings}` : '',
  '',
  MODE === 'reword'
    ? `conclude.md section 7 steps 1-4: take the ticket, recover old.txt, check the old hash (for a reword base pass: the wording its R confirmed, #127), \`reviews.py new-pass <id> --reword-of <base pass>\` (with --base-subject when given), write the bundle with \`reviews.py reword-brief\` (no --new-file: it takes the registry's statement). statement_hash is the NEW statement's hash, the registry engine's: \`reviews.py hash --claim ${A.claim}\` (T-0464).`
    : `conclude.md section 0: take the ticket (its budget field gates nothing: never block it for budget), pin and hash the statement with \`reviews.py hash --claim ${A.claim}\` (the registry engine's statement text, the hash claims_set_status checks; never a hand-copied extract, T-0464), open the pass (\`reviews.py new-pass\`, \`reviews.py dir\`). For a statement that lives in a tex file, location is the output line of \`statement.py <label> --where --home <that Author home>\` (the file and the line ranges of the statement and its proof): a section file is too large to read whole, and the reviewer has no shell to find the lines. Write nothing in the pass folder. ` +
      'new-pass returns the open pass of this same ticket when one is open (a rerun, #89): then list in landed the run files already in its folder (A.md, B.md) with the statement_hash of each one\'s frontmatter. ' +
      'Report the claim\'s falsifier on record (falsifier; conclude.md section 0, the sources prove.js accepts, #117): one that attacked this claim; or one recorded on a declared input, or on the parent lead or direction item, whose class or statement covers it, saying how; ' +
      'or the ticket thread records one (a falsifier request on this claim, once it is back: its result); or the human waived it on the ticket or the claim (quote that thread line verbatim); else none. ' +
      'Say what it found (nothing, or a counterexample), any falsifier request on this claim that is filed and not back (a ticket titled "Falsifier for ' + A.claim + '": tickets_list text ' + A.claim + ') with its status in falsifier.request and request_status, and the claim\'s declared inputs (inputs: depends_on, its cites as bib:<key>, read from the registry now). ' +
      'Report the dependency amendment (amendment; conclude.md section 1b): a repair ticket an earlier run of this pass filed to add run A\'s suggested dependencies, with its status, the claim\'s current proof attempt, and the attempt run A reviewed as this pass recorded it ("run A reviewed <attempt>" in the repair\'s ask or the ticket\'s block note); a ticket blocked on it is taken blocked -> in-progress.',
      'Run `reviews.py researcher-for ' + A.claim + ' --party <instance>` once, with a --party for the from and the to of the ticket and of each ticket up its parent chain (tickets_get), and report its instance and why as researcher and researcher_why. ' +
      'Report in falsifier.statement_hash (not the pass\'s own statement_hash) the statement hash the falsifier attacked, read first from the structured fields: a lab claim\'s frontmatter falsifies: ["' + A.claim + '@<hash>", ...] entry for this claim (proofs/<id>/attack.md, the prover\'s own attack step, is not a falsifier); then, for a request this workflow filed, the "statement hash <h>" its ask names; else leave it empty: a falsifier of unknown or another wording does not count (a waiver aside).',
].filter(Boolean).join('\n')), { label: 'prepare', phase: 'Prepare', agentType: CHAIR, schema: PREP, effort: 'low' })

if (!prep || !prep.ok) {
  log('pass not started: ' + (prep ? prep.stop_reason || 'no reason given' : 'the prepare stage returned nothing'))
  return { claim: A.claim, outcome: 'not-started', reason: prep ? prep.stop_reason || 'no reason given' : 'prepare lost' }
}
if (!RE_PASS.test(prep.pass) || !RE_HASH.test(prep.statement_hash)) {
  throw new Error(`prepare returned a malformed pass ${JSON.stringify(prep.pass)} or hash ${JSON.stringify(prep.statement_hash)}`)
}
const ticket = prep.ticket || 'none'
// #89: a resumed pass keeps the runs that landed on this statement; runs on another wording
// are not mixed with new ones
const landed = new Map((prep.landed || []).filter(l => /^[ABR]$/.test(String(l.run || '').replace(/\.md$/, '')))
  .map(l => [String(l.run).replace(/\.md$/, ''), l.statement_hash]))
const stale = [...landed].filter(([, h]) => h !== prep.statement_hash).map(([r]) => r)
if (!stale.length && landed.has('B') && !landed.has('A')) stale.push('B (without A)')
if (stale.length) {
  log(`resumed pass ${prep.pass} holds runs on another statement (${stale.join(', ')})`)
  return { claim: A.claim, outcome: 'not-started', pass: prep.pass,
    reason: `the open pass ${prep.pass} of this ticket holds run(s) ${stale.join(', ')} that cannot be resumed (another statement hash, or B without A): abandon it (reviews.py abandon ${A.claim} ${prep.pass} --reason "statement changed") and run again` }
}
const ids = `subject: ${A.claim} · pass: ${prep.pass} · run: RUN · statement_hash: ${prep.statement_hash} · ticket: ${ticket}`
let amendBundle = ''      // set once the amend bundle is written (run B in amend mode)
const brief = (run) => run === 'B' && amendBundle
  ? `Review ${A.claim} in amend mode (run B, rigor-reviewer "Amend mode"): read the bundle ${amendBundle} first; ` +
    `its statement and amended proof are at ${prep.location}. The question: ${QUESTION} ` +
    `Work through your obligation ledger before reading the proof.\n` + ids.replace('RUN', 'B')
  : MODE === 'reword'
  ? `Reword review of ${A.claim} (reword mode, run R): read the bundle ${prep.bundle} first; ` +
    `the proof is at ${prep.location}. The question: does the proof as reviewed still prove the new wording?\n` +
    ids.replace('RUN', 'R')
  : `Review ${A.claim}: its statement and proof are at ${prep.location}. The question: ${QUESTION} ` +
    `Work through your obligation ledger before reading the proof.\n` + ids.replace('RUN', run)

// ---- 2. Review: one run, checked by the table, relaunched once when it did not land ----
const notes = []
let amending = false      // run A suggested a dependency: B is an amend run (2026-11-20)
const table = (run) => launch(STAGE('table', [
  `pass_dir: ${prep.pass_dir}`, `run: ${run}`, `claim: ${A.claim}`,
  `Check that ${run}.md landed in the pass folder; run ` +
  (run === 'B'
    ? `\`decision_table.py "<pass_dir>/A.md" "<pass_dir>/B.md" --json\` (run B is tabled against A: ${amending ? 'an amend run, mode amend' : 'the blind pair'})`
    : `\`decision_table.py "<pass_dir>/${run}.md" --json\` (no B argument)`) +
  ` and report its outcome, launch_b, add_dependency (empty when none), for a GAP verdict the blocking step the run names (blocking_step), and the statement_hash of the run file's own frontmatter (run_hash); re-hash the statement as it stands now ` +
  `exactly as the prepare stage hashed it, through the registry engine (\`reviews.py hash --claim ${A.claim}\`; never \`hash\` on a copied extract). Write nothing.`,
].join('\n')), { label: `table ${run}`, phase: 'Review', agentType: CHAIR, schema: TABLE, effort: 'low' })

async function review(run) {
  if (landed.has(run)) {          // a resumed pass (#89): conclude what landed, never relaunch it
    const t = await table(run)
    if (t && t.landed && t.run_hash && t.run_hash !== prep.statement_hash) {
      notes.push(`run ${run}: the landed ${t.run_file} is on statement ${t.run_hash}, not ${prep.statement_hash}: not used`)
      return { lost: true, stale: true }
    }
    if (t && t.landed) { notes.push(`run ${run} had landed in the resumed pass ${prep.pass}: kept, not relaunched`); return t }
  }
  for (let attempt = 1; attempt <= 2; attempt++) {
    const out = await launchMax(brief(run), { label: `run ${run}${attempt > 1 ? ' (relaunch)' : ''}`, phase: 'Review', agentType: REVIEWER },
      { agentType: CHAIR, phase: 'Review', notes })
    if (out === null) {           // a terminal API error (a limit): launch nothing further
      notes.push(`run ${run} lost (no result: a limit or an API error); nothing further launched`)
      return { lost: true }
    }
    const t = await table(run)
    if (t && t.landed && t.run_hash && t.run_hash !== prep.statement_hash) {
      // the file the table read is not this run's (an older run of a resumed pass the
      // prepare stage did not list): never concluded on (#89 review)
      notes.push(`run ${run}: the landed ${t.run_file} is on statement ${t.run_hash}, not ${prep.statement_hash}: not used`)
      return { lost: true, stale: true }
    }
    if (t && t.landed) {
      if (attempt > 1) notes.push(`run ${run}: the kept run is the relaunch`)
      return t
    }
    notes.push(`run ${run} attempt ${attempt} did not land a verdict`)
  }
  return { lost: true }
}

// ---- The falsifier on record (2026-11-20) ------------------------------------------
// What counts is prove.js's #117 rule, held here against the prepare stage's report: a known
// source with evidence; an input that is one of the declared inputs (namespace prefixes
// ignored) and names it; a parent that names it; a waiver that quotes the human's thread line
// ("- YYYY-MM-DD human: ..."). That it covers the claim is the stage's report.
const FSOURCES = ['claim', 'input', 'parent', 'ticket', 'waived', 'none']
const bare = x => String(x || '').trim().replace(/^[a-z][a-z0-9]*:/, '')
function falsifierOnRecord(f) {
  f = f || {}
  let src = FSOURCES.includes(f.source) ? f.source : 'none'
  if (f.source && !FSOURCES.includes(f.source)) notes.push(`falsifier source ${JSON.stringify(f.source)} is not a known source: not counted`)
  if (src === 'input' && bare(f.on) === bare(A.claim)) src = 'claim'
  let counts = src !== 'none'
  if (counts && !String(f.evidence || '').trim()) { counts = false; notes.push(`a ${src} falsifier was reported with no evidence: not counted`) }
  if (counts && src === 'input' && !(prep.inputs || []).map(bare).includes(bare(f.on))) {
    counts = false
    notes.push(`the falsifier named is on ${f.on || '(none named)'}, not a declared input of ${A.claim} (${(prep.inputs || []).join(', ') || 'none declared'}): not counted`)
  }
  if (counts && (src === 'input' || src === 'parent') && !f.on) { counts = false; notes.push(`a ${src} falsifier was reported with no id it is recorded on: not counted`) }
  if (counts && src === 'waived' && !/(^|\n)\s*-?\s*\d{4}-\d{2}-\d{2} human:/.test(f.evidence || '')) {
    counts = false
    notes.push('a waiver was reported without the human\'s thread line (- YYYY-MM-DD human: ..., the human\'s quoted words; a line "human (via main session):" is the session\'s bookkeeping, and a waiver recorded through the MCP tools needs via: "human" with the quote): not counted')
  }
  // review V1 #2: a falsifier counts only once it came back clean or with a counterexample
  // (found nothing / counterexample); a request only once it is delivered or closed
  const found = String(f.found || '').trim()
  if (counts && src !== 'waived' && !['nothing', 'counterexample'].includes(found)) {
    counts = false
    notes.push(`a ${src} falsifier was reported with found ${JSON.stringify(found)} (not nothing, not a counterexample): not counted`)
  }
  if (counts && (src === 'ticket' || f.request) && !/^(delivered|closed)$/.test(String(f.request_status || '').trim())) {
    counts = false
    notes.push(`the falsifier request ${f.request || f.on || '(none named)'} is ${f.request_status || 'of unknown status'}, not delivered or closed: not counted`)
  }
  // review V1 #3: a falsifier attacked one wording; on another statement hash it never counts,
  // and with the hash unknown only the human's waiver does
  const fh = String(f.statement_hash || '').trim()
  if (counts && fh && fh !== prep.statement_hash) {
    counts = false
    notes.push(`the ${src} falsifier was recorded on another wording (statement hash ${fh}, now ${prep.statement_hash}): not counted`)
  } else if (counts && !fh) {
    if (src === 'waived') notes.push('the waiver\'s statement hash is unknown: counted, a waiver being the human\'s call')
    else { counts = false; notes.push(`the ${src} falsifier's statement hash is unknown (it may have attacked an older wording): not counted`) }
  }
  return { counts, source: src, on: f.on || '', evidence: f.evidence || '', found: counts && src !== 'waived' ? found : '' }
}
const DONE_TICKET = /^(delivered|closed|rejected|cancelled)$/

// The falsifier request's addressee (review V1 #5) is computed by reviews.py researcher-for
// (decision_table.researcher_for): the Researcher owning the claim's namespace, else the one its
// bears_on names, else the one in the ticket's parent chain; none or several is the human's call.
function researcherTo() {
  const r = String(prep.researcher || '').trim()
  const why = String(prep.researcher_why || '').trim() || 'the prepare stage named none'
  return /^researcher@[A-Za-z0-9_.-]+$/.test(r) ? { instance: r, why } : { instance: '', why: r === 'human' ? why : `no Researcher instance reported (${JSON.stringify(r)}): ${why}` }
}

// A GAP verdict (run A single-negative, or run B after a CONFIRMED A) with no falsifier
// that counts on record and none pending: the chair files the falsifier request, naming the
// gap, alongside the follow-up repair the conclude stage files. It blocks nothing: the pass
// concludes and the ticket is delivered as before (the human's design, 2026-11-20).
const GAP = /^GAP\b/i
function falsifierPending() {
  const f = prep.falsifier || {}
  const req = String(f.request || '').trim()
  if (!req || DONE_TICKET.test(String(f.request_status || '').trim())) return ''
  const fh = String(f.statement_hash || '').trim()
  return fh && fh !== prep.statement_hash ? '' : req     // a request on another wording is not this one's
}
async function requestFalsifier(gap) {
  const f = falsifier || (falsifier = falsifierOnRecord(prep.falsifier))
  if (f.counts) { notes.push(`no falsifier request: ${A.claim} has a falsifier on record (${f.source}${f.on ? ' ' + f.on : ''})`); return null }
  const pending = falsifierPending()
  if (pending) { notes.push(`no falsifier request: ${pending} on ${A.claim} is pending (${prep.falsifier.request_status || 'status unknown'})`); return null }
  const to = researcherTo()
  if (!to.instance) {
    notes.push(`no falsifier request: no Researcher to ask for the falsifier of ${A.claim} (${to.why}); the human decides whether one is run`)
    return null
  }
  const T = ticket === 'none' ? '' : ticket
  const step = String(gap.blocking_step || '').trim() || '(the run names no blocking step: the gap of its report)'
  const req = await launch(STAGE('falsifier', [
    `claim: ${A.claim}`, `ticket: ${ticket}`, `pass: ${prep.pass}`, `the gap: run ${gap.run} ${gap.verdict}, blocking step: ${step}`,
    `conclude.md section 1a. File one falsifier request with tickets_create: kind research, to ${to.instance} (${to.why}; reviews.py researcher-for), final_to scientist ` +
      `(the Expert is no neighbour of the Scientist: the Researcher's experiment-spec relays it), refs [${A.claim}${T ? ', ' + T : ''}]${T ? ', parent ' + T : ''}; ` +
      `title "Falsifier for ${A.claim}"; ask: run a falsifier on ${A.claim}, an experiment or test that tries to break it where the proof has a gap ` +
      `(the blocking step: ${step}; a search over the class it quantifies over, its standard examples first), and deliver what it found (nothing, or a counterexample with its certificate); ` +
      `the ask names the statement it attacks as "statement hash ${prep.statement_hash}" (a falsifier counts only on the wording it attacked); ` +
      'deliverable: the result (a lab result or report id) and whether it found a counterexample. ' +
      `It blocks nothing: never block or wait on ${T || 'any ticket'}; the conclude stage still files the follow-up repair and delivers the ticket. If tickets_create refuses, return the refusal verbatim.`,
    'Write nothing in the pass folder and no claims_propose_status; return the request id.',
  ].join('\n')), { label: 'falsifier', phase: 'Review', agentType: CHAIR, schema: FALS_OUT, effort: 'low' })
  const id = req && /^T-\d{4,}$/.test(String(req.request || '').trim()) ? req.request.trim() : ''
  if (!req) notes.push('the falsifier stage returned nothing: no request is known to be filed')
  else if (req.refusal) notes.push(`the falsifier request was refused (${req.refusal})`)
  else if (!id) notes.push('the falsifier stage returned no ticket id: no request is known to be filed')
  if (id) notes.push(`falsifier requested on the ${gap.verdict} of run ${gap.run}: ${id} to ${to.instance}, targeting the blocking step (${step}); it blocks nothing`)
  return id || null
}

// ---- The dependency amendment (2026-11-20) -----------------------------------------
// A's suggestion counts as made (the 2026-11-20 review) only when a repair this pass filed
// has ended delivered or closed, the claim's current attempt is not the one run A reviewed
// (recorded in the pass's repair ask and block note), and every suggested dependency is
// among the declared inputs as the registry reads them now, namespace and #pinpoint kept,
// compared in canonical spelling (decision_table's canon_input: the table reports A's
// suggestion in it, the prepare stage the inputs; the spelling-only part is redone here).
const PIN_GLUE = /(\b(?:thm|theorem|lem|lemma|prop|proposition|cor|corollary|defn?|definition|rmk|rem|remark|sect?|section|item|pp?|ex|example|eq|fig|figure|tab|table|claim|step|fact|obs|ch|chapter|app|appendix)|§)[\s.\-]+(?=\d)/gi
function depKey(x) {
  const t = String(x || '').split(/\s+/).filter(Boolean).join(' ').replace(/^[`'"]+|[`'"]+$/g, '')
  const i = t.indexOf('#')
  return i < 0 ? t : t.slice(0, i) + '#' + t.slice(i + 1).trim().replace(PIN_GLUE, '$1')
}
const REPAIR_DONE = /^(delivered|closed)$/
const NO_ATTEMPT = /^\(?\s*(none|no attempt( reported)?|unknown|n\/a)\s*\)?$/i
function amendmentIn(deps) {
  const am = prep.amendment || {}
  const have = new Set((prep.inputs || []).map(depKey))
  const missing = deps.filter(d => !have.has(depKey(d)))
  const status = am.request_status || ''
  const open = !!am.request && !DONE_TICKET.test(status)
  const why = []
  if (am.request && !open && !REPAIR_DONE.test(status)) why.push(`the repair ${am.request} ended ${status}, not delivered or closed`)
  // a placeholder is no record (second look at 7044d82: '(no attempt reported)' always
  // 'differed' from the current attempt, so an untouched proof passed)
  const rec = String(am.reviewed_attempt || '').trim()
  if (am.request && !open && (!rec || NO_ATTEMPT.test(rec))) why.push('the pass did not record the attempt run A reviewed')
  else if (am.request && !open && (!String(am.attempt || '').trim() || NO_ATTEMPT.test(am.attempt.trim()) || am.attempt.trim() === am.reviewed_attempt.trim())) {
    why.push(`the claim's current attempt (${am.attempt || 'none reported'}) is the one run A reviewed: the proof was not amended`)
  }
  if (am.request && !open && missing.length) why.push(`the declared inputs of ${A.claim} lack ${missing.join(', ')} (namespace and pinpoint as suggested)`)
  const done = !!am.request && !open && !why.length
  return { done, missing, open, why, request: am.request || '', status, attempt: am.attempt || '' }
}
async function requestAmendment(deps, st) {
  const T = ticket === 'none' ? '' : ticket
  const list = deps.join(', ')
  const reviewed = String((prep.amendment || {}).attempt || '').trim()
  // no repair without the attempt A reviewed on record: the human decides instead
  const how = !st.open && !st.request && !reviewed
    ? [`The prepare stage reported no proof attempt for ${A.claim}, so the attempt run A reviewed cannot be recorded and an amendment could not be checked: file nothing. ` +
       (T ? `Block ${T}: tickets_update status blocked, waiting_on [human], reason "run A suggests adding ${list} to ${A.claim}, but the attempt it reviewed is not on record: the human decides (record it and rerun, or a fresh pass)".` : 'There is no verify ticket to block.')]
    : st.open
    ? [`An earlier run of this pass filed the repair ${st.request} (${st.status || 'status unknown'}), which is not back: file nothing. ` +
       (T ? `Block ${T}: tickets_update status blocked, waiting_on [${st.request}], note "amendment ${st.request} not back; the pass ${prep.pass} stays open".` : 'There is no verify ticket to block.')]
    : st.request
      ? [`The repair ${st.request} ended (${st.status}) without the amendment: ${st.why.join('; ')}. File nothing. ` +
         (T ? `Block ${T}: tickets_update status blocked, waiting_on [human], reason "the repair ${st.request} ended (${st.status}) without the amendment of ${A.claim} (${st.why.join('; ')}): the human decides (another repair, or a fresh pass)".` : 'There is no verify ticket to block.')]
      : [`File one repair with tickets_create: kind prove, to the Researcher instance that owns the namespace of ${A.claim} ` +
         `(for a claim of another namespace, paper: or lab:, the Researcher of the claim's domain, as a prove follow-up is routed, conclude.md section 4.3; a lab: claim with final_to scientist), ` +
         `refs [${A.claim}${T ? ', ' + T : ''}]${T ? ', parent ' + T : ''}; title "Repair: add dependencies to ${A.claim}"; ` +
         `ask (mode repair, researcher prove.js): add exactly these dependencies to the proof of ${A.claim} (cite and use them where the argument relies on them) and to the claim's depends_on (a bib: key to its cites, cited in the proof at its pinpoint): ${list}; change nothing else, not the statement; write the amended proof as a new attempt. ` +
         (T ? `The ask's first line ends with the marker "amendment for verify ${T} pass ${prep.pass}" and its detail says "run A reviewed ${reviewed}": this repair files no verify ticket (run B of ${T}'s pass, on the amended proof, is the second verdict) and delivers with the new attempt's path. ` : '') +
         `deliverable: the amended proof attempt and the record's depends_on. The ask names the dependencies only: never run A's verdict, report or findings.`,
         T ? `Then block ${T}: tickets_update status blocked, waiting_on [<the repair's id>], note "amendment requested: <id> (add ${list}); run A reviewed ${reviewed}; the pass ${prep.pass} stays open and resumes when it is back". ` +
             `If tickets_create refuses, block ${T} waiting_on [human] with the refusal as the reason, and return the refusal.`
           : 'There is no verify ticket: block nothing.']
  return launch(STAGE('amendment', [
    `claim: ${A.claim}`, `ticket: ${ticket}`, `pass: ${prep.pass}`, `suggested dependencies (run A's add_dependency): ${list}`,
    `conclude.md section 1b. ${how.join('\n')}`,
    'Write nothing in the pass folder and no claims_propose_status; return the request id, whether the ticket is blocked and its waiting_on.',
  ].join('\n')), { label: 'amendment', phase: 'Review', agentType: CHAIR, schema: AMEND_OUT, effort: 'low' })
}

phase('Review')
let runs = []
let falsifier = null        // the falsifier on record (a counterexample stops B), once read
if (MODE === 'reword') {
  const r = await review('R')
  runs.push(Object.assign({ run: 'R' }, r))
  notes.push('reword pass: one informed run R, no blind pair (T-0347)')
} else {
  const a = await review('A')
  runs.push(Object.assign({ run: 'A' }, a))
  const suggested = (!a.lost && Array.isArray(a.add_dependency)) ? a.add_dependency.filter(x => String(x || '').trim()) : []
  // the table decides (it refuses a suggestion that names no existing result): an amend pass
  // is the table's awaiting-amendment with the suggestion it reports
  amending = !a.lost && a.outcome === 'awaiting-amendment' && suggested.length > 0
  if (!a.lost && a.outcome === 'awaiting-amendment' && !suggested.length) notes.push('ANOMALY: the table on A says awaiting-amendment but reports no add_dependency: not an amend pass')
  if (a.lost) {
    // nothing to add
  } else if (!a.launch_b && !amending) {
    notes.push(`run B skipped by design: the table on A says ${a.outcome} (launch_b false)`)
  } else if (a.hash_now !== prep.statement_hash) {
    notes.push(`statement moved under the review (hash ${prep.statement_hash} -> ${a.hash_now}): B not launched, nothing to conclude on the old wording`)
  } else {
    falsifier = falsifierOnRecord(prep.falsifier)   // the counterexample rule: one on record stops B
    if (falsifier.found === 'counterexample') {
      notes.push(`run B not launched: the falsifier (${falsifier.source}${falsifier.on ? ' ' + falsifier.on : ''}) found a counterexample: ${falsifier.evidence}`)
    } else {
      if (falsifier.counts && falsifier.source !== 'claim') notes.push(`falsifier accepted: ${falsifier.source}${falsifier.on ? ' ' + falsifier.on : ''}`)
      if (amending) {
        // A suggested a dependency: B reviews the amended proof, once the amendment is in
        const st = amendmentIn(suggested)
        if (!landed.has('B') && !st.done) {
          if (st.request && !st.open) notes.push(`the repair ${st.request} ended (${st.status}) without the amendment: ${st.why.join('; ')}`)
          const req = await requestAmendment(suggested, st)
          const id = req && /^T-\d{4,}$/.test(String(req.request || '').trim()) ? req.request.trim() : ''
          if (!req) notes.push('the amendment stage returned nothing: no repair is known to be filed')
          if (req && req.refusal) notes.push(`the repair was refused (${req.refusal})`)
          if (req && ticket !== 'none' && !req.blocked) notes.push(`ANOMALY: ${ticket} was not blocked on the amendment`)
          notes.push(`run B not launched: A is CONFIRMED and suggests adding ${suggested.join(', ')}; ${id ? 'repair ' + id : 'no repair'}`)
          log(`A: ${a.verdict} + add_dependency ${suggested.join(', ')} -> awaiting the amendment${id ? ' ' + id : ''}`)
          const res = { claim: A.claim, outcome: 'awaiting-amendment', pass: prep.pass, pass_dir: prep.pass_dir, runs, notes,
            amendment_request: id || null, add_dependency: suggested,
            reason: (req && req.refusal ? `the repair was refused (${req.refusal}). ` : '') +
              `run A suggests adding ${suggested.join(', ')} to the proof of ${A.claim}: B waits for the amendment, and the pass ${prep.pass} stays open; ` +
              (ticket !== 'none' ? `rerun ${ticket} once ${id || 'the repair'} is back (the pass resumes, A is kept, B runs in amend mode)` : 'without a verify ticket the pass cannot be resumed (reviews.py resumes a ticket\'s own pass only)'),
            launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }
          if (!A.nested) res.ship = await ship({ role: 'expert', ticket: ticket === 'none' ? '' : ticket, done: false, topic: 'verify-' + A.claim,
            only: 'library board', agentType: CHAIR, phase: 'Review', notes })
          return res
        }
        if (!landed.has('B')) {
          const bb = await launch(STAGE('amend-brief', [
            `claim: ${A.claim}`, `pass: ${prep.pass}`, `ticket: ${ticket}`,
            `conclude.md section 1b, "The amend run": write run B's bundle with \`reviews.py amend-brief ${A.claim} ${prep.pass} --attempt ${st.attempt || '<the claim\'s current proof attempt>'}${ticket !== 'none' ? ' --ticket ' + ticket : ''} --out <a file outside reviews/>\` ` +
            '(the scratch folder of the home), once, and return its path; on a refusal return it verbatim and write nothing else.',
          ].join('\n')), { label: 'amend-brief', phase: 'Review', agentType: CHAIR, schema: BUNDLE_OUT, effort: 'low' })
          if (!bb || bb.refusal || !String(bb.bundle || '').trim()) {
            notes.push(`run B not launched: the amend bundle was not written (${bb ? bb.refusal || 'no path returned' : 'the stage returned nothing'})`)
            return { claim: A.claim, outcome: 'awaiting-amendment', pass: prep.pass, pass_dir: prep.pass_dir, runs, notes,
              add_dependency: suggested, reason: 'the amend bundle could not be written: ' + (bb ? bb.refusal || 'no path' : 'stage lost') + '; rerun the ticket',
              launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }
          }
          amendBundle = bb.bundle.trim()
        }
        notes.push(`amend pass: A suggested ${suggested.join(', ')}; the producer added ${suggested.length > 1 ? 'them' : 'it'}; B reviews the amended proof, told the suggestion only`)
        const b = await review('B')     // amend mode: a fresh agent told only A's suggestion (the bundle)
        runs.push(Object.assign({ run: 'B', mode: 'amend' }, b))
      } else {
        const b = await review('B')     // the identical brief, run B, a fresh agent told nothing of A
        runs.push(Object.assign({ run: 'B' }, b))
      }
    }
  }
}
const counterexample = !!(falsifier && falsifier.counts && falsifier.found === 'counterexample')
// a GAP verdict (A single-negative, or B after a CONFIRMED A) files the falsifier request
const gapRun = MODE === 'blind' && !counterexample ? [...runs].reverse().find(r => !r.lost && !r.stale && GAP.test(String(r.verdict || '')) && r.hash_now && r.hash_now === prep.statement_hash) : null
const falsifierRequest = gapRun && !runs.some(r => r.stale) ? await requestFalsifier(gapRun) : null
// ---- Differing inputs: the dependency-settler (#121, the human's design of 2026-11-20) ----
// CONFIRMED x2 whose modulo lists still differ after the table's mechanical reduction is
// settle-dependencies: one settler run classifies each differing input in the fixed order,
// settle_deps.py checks its record (one retry with the problems, then a disagreement with an
// anomaly) and applies it. Settled: the declaration repair (the amendment's marker, nothing
// waits on it), a cite ticket per missing source, an Author ticket for a remark in paper
// text, and the status proposed to the keeper. A stop: the disagreement path, with the
// settler's classification for the human.
const settleRun = MODE === 'blind' && !counterexample && !runs.some(r => r.stale)
  ? runs.find(r => r.run === 'B' && !r.lost && r.outcome === 'settle-dependencies') : null

function recordOf(text) {   // the last fenced json block of the settler's report
  const blocks = [...String(text || '').matchAll(/```json[ \t]*\r?\n([\s\S]*?)```/g)]
  if (!blocks.length) return { problems: ['the report has no fenced json block (the record)'] }
  try {
    const r = JSON.parse(blocks[blocks.length - 1][1])
    return r && typeof r === 'object' && !Array.isArray(r) ? { record: r } : { problems: ['the json block is not an object'] }
  } catch (e) { return { problems: ['the json block does not parse: ' + String(e.message || e)] } }
}
const strs = x => Array.isArray(x) ? x.map(v => String(v)) : []
const objs = x => Array.isArray(x) ? x.filter(v => v && typeof v === 'object') : []
async function settleDependencies(b) {
  const pd = prep.pass_dir
  const disagree = (why, extra) => Object.assign({ outcome: 'disagreement', proposed_status: '', modulo: [], declarations: [], notes: [], cite: [],
    stops: [], dropped: [], grounds: null, problems: [], summary: why, attempts: 0 }, extra || {})
  if (b.hash_now !== prep.statement_hash) {
    notes.push(`the statement moved under the review (hash ${prep.statement_hash} -> ${b.hash_now}): the differing inputs are not settled`)
    return disagree('the statement moved under the review')
  }
  const tw = await launch(STAGE('settle-table', [
    `pass_dir: ${pd}`, `claim: ${A.claim}`,
    `conclude.md section 2, "Differing inputs". Run \`decision_table.py "<pass_dir>/A.md" "<pass_dir>/B.md" --json\` once and write its output verbatim (LF) to "<pass_dir>/S-table.json", ` +
      'the table the dependency-settler reads and settle_deps.py checks against. Write nothing else; return written and the outcome in the JSON.',
  ].join('\n')), { label: 'settle-table', phase: 'Review', agentType: CHAIR, schema: SETTLE_TABLE_OUT, effort: 'low' })
  if (!tw || tw.written !== true || tw.outcome !== 'settle-dependencies') {
    notes.push(`ANOMALY: the settle table was not written as settle-dependencies (${tw ? `written ${tw.written}, outcome ${tw.outcome || 'none'}` : 'the stage returned nothing'}): the dependency-settler not launched`)
    return disagree('the settle table could not be written')
  }
  const ids = `subject: ${A.claim} · pass: ${prep.pass} · statement_hash: ${prep.statement_hash} · ticket: ${ticket}`
  const brief = (prev) => `Settle the differing inputs of ${A.claim}: two blind runs are CONFIRMED on different modulo lists. ` +
    `Read the two verdicts ${pd}/A.md and ${pd}/B.md and the table ${pd}/S-table.json (outcome settle-dependencies: classify each of its differing_inputs), ` +
    `and the proof at ${prep.location}. Classify each differing input by the first case that applies, in the fixed order of your instructions, ` +
    'and end your report with the one fenced json record.\n' + ids +
    (prev ? `\nA first run's record failed \`settle_deps.py check\`; its problems:\n- ${prev.problems.join('\n- ')}\n` +
      (prev.record ? `Its record was:\n${JSON.stringify(prev.record)}\n` : '') + 'Classify afresh and return the whole record, with those problems fixed.' : '')
  let prev = null
  for (let attempt = 1; attempt <= 2; attempt++) {
    const label = attempt === 1 ? 'settler' : 'settler (retry)'
    const out = await launchMax(brief(prev), { label, phase: 'Review', agentType: SETTLER }, { agentType: CHAIR, phase: 'Review', notes })
    if (out === null) {     // a limit or an API error: launch nothing further (the role rule; review of 39de757)
      notes.push(`${label} returned nothing (a limit or an API error): not relaunched, concluded as a disagreement`)
      return disagree('the dependency-settler returned nothing', { problems: ['the settler returned nothing'], attempts: attempt })
    }
    let got = recordOf(out)
    if (got.record) {
      const r = await launch(STAGE('settle', [
        `pass_dir: ${pd}`, `claim: ${A.claim}`,
        `conclude.md section 2, "Differing inputs". Write the dependency-settler's report below verbatim (LF) to "<pass_dir>/S.md" and its record verbatim to "<pass_dir>/S.json" ` +
          '(overwrite both: the last run is the one kept). Run `py ' + AR + '/expert/scripts/settle_deps.py check "<pass_dir>/S.json" --table "<pass_dir>/S-table.json"` once; ' +
          'if it says ok, run `settle_deps.py apply` with the same arguments once and return its fields verbatim (outcome, proposed_status, modulo, declarations, notes, cite, stops, dropped, grounds, summary) with ok true; ' +
          'else return ok false and its problems verbatim. Judge nothing: the script decides. File nothing.',
        `The record (S.json):\n${JSON.stringify(got.record)}`,
        `The report (S.md):\n${String(out)}`,
      ].join('\n')), { label: attempt === 1 ? 'settle' : 'settle (retry)', phase: 'Review', agentType: CHAIR, schema: SETTLE_OUT, effort: 'low' })
      if (!r) got = { record: got.record, problems: ['the settle stage returned nothing: the record was not checked'] }
      else if (r.ok === true && ['confirmed-settled', 'disagreement'].includes(r.outcome)) {
        return { outcome: r.outcome, proposed_status: r.outcome === 'confirmed-settled' ? String(r.proposed_status || '') : '',
          modulo: strs(r.modulo), declarations: objs(r.declarations), notes: objs(r.notes), cite: objs(r.cite), stops: objs(r.stops),
          dropped: objs(r.dropped), grounds: r.grounds && typeof r.grounds === 'object' ? r.grounds : null, problems: [],
          summary: String(r.summary || ''), attempts: attempt }
      } else if (r.ok === true) got = { record: got.record, problems: [`settle_deps.py apply returned outcome ${JSON.stringify(r.outcome || '')}`] }
      else got = { record: got.record, problems: strs(r.problems).length ? strs(r.problems) : ['settle_deps.py check failed (no problems reported)'] }
    }
    notes.push(`${label}: the record is not valid (${got.problems.join('; ')})`)
    prev = got
  }
  notes.push(`ANOMALY: the dependency-settler's record failed settle_deps.py check twice (${prev.problems.join('; ')}): concluded as a disagreement`)
  return disagree('the settler\'s record failed the check twice', { problems: prev.problems, attempts: 2 })
}

// confirmed-settled: one declaration repair (the dependency amendment's marker and machinery:
// researcher-for, for_verify, so prove.js files no verify ticket), carrying the routine and
// remark notes; a cite ticket per missing source; an Author ticket for a remark in paper text.
// Nothing blocks the verify ticket and nothing is parked on the human.
async function fileSettled(st) {
  const T = ticket === 'none' ? '' : ticket
  const decl = st.declarations.map(d => String(d.dependency || '')).filter(Boolean)
  const routine = st.notes.filter(n => n.kind === 'routine')
  const remarks = st.notes.filter(n => n.kind === 'remark')
  const paper = /^paper:/.test(A.claim)
  const repairNotes = routine.concat(paper ? [] : remarks)
  const noteText = n => n.kind === 'routine'
    ? `the step resting on ${n.dependency} is routine: name every source (${strs(n.sources).join(', ')}) in the proof, ${n.dependency} the one kept`
    : `a remark naming the other sources (${strs(n.sources).filter(x => x !== n.dependency).join(', ')}) for ${n.dependency}: ${n.text || ''}`
  const to = researcherTo()
  const asks = []
  if (decl.length || repairNotes.length) {
    if (!to.instance) notes.push(`no declaration repair filed${decl.length ? ' for ' + decl.join(', ') : ''}: no Researcher to ask (${to.why}); the record and the packet name it as an open item`)
    else {
      const reviewed = String((prep.amendment || {}).attempt || '').trim()
      asks.push(`One declaration repair with tickets_create: kind prove, to ${to.instance} (${to.why}; reviews.py researcher-for), refs [${A.claim}${T ? ', ' + T : ''}]${T ? ', parent ' + T : ''}; ` +
        `title "Repair: declare dependencies of ${A.claim}"; ask (mode repair, researcher prove.js): ` +
        (decl.length ? `add exactly these dependencies to the proof of ${A.claim} (cite them where the argument relies on them) and to the claim's depends_on (a bib: key to its cites, cited at its pinpoint): ${decl.join(', ')}; ` : '') +
        (repairNotes.length ? `and in the proof: ${repairNotes.map(noteText).join('; ')}; ` : '') +
        'change nothing else, not the statement; write the amended proof as a new attempt. ' +
        (T ? `The ask's first line ends with the marker "amendment for verify ${T} pass ${prep.pass}"${reviewed ? ` and its detail says "run A reviewed ${reviewed}"` : ''}: this repair files no verify ticket (both runs of ${T}'s pass reviewed the proof with these inputs in view) and delivers with the new attempt's path. ` : '') +
        'deliverable: the amended proof attempt and the record\'s depends_on. The ask names the dependencies and notes only: never a run\'s verdict, report or findings. Return its id as repair.')
    }
  }
  for (const c of st.cite) {
    asks.push(`One cite ticket with tickets_create: kind cite, to this Expert instance (a missing card, conclude.md section 4.3), refs [${A.claim}${T ? ', ' + T : ''}]${T ? ', parent ' + T : ''}; ` +
      `title "Cite: ${String(c.input || '').slice(0, 80)}"; ask: find, cache and card the source of "${c.input}", the input ${A.claim} rests on (the settler's evidence: ${c.evidence || 'none given'}); deliverable: the bib key and pinpoint. Add its id to cite.`)
  }
  if (paper && remarks.length) {
    asks.push(`One ticket with tickets_create: kind write, to the Author instance owning ${A.claim}, refs [${A.claim}${T ? ', ' + T : ''}]${T ? ', parent ' + T : ''}; title "Remark after ${A.claim}: other sources"; ` +
      `ask: add a remark after the proof of ${A.claim} naming the other sources of the step: ${remarks.map(noteText).join('; ')}; deliverable: the remark in the section file. Return its id as author.`)
  }
  if (!asks.length) return { repair: '', cite: [], author: '', refusals: [] }
  const r = await launch(STAGE('settle-file', [
    `claim: ${A.claim}`, `ticket: ${ticket}`, `pass: ${prep.pass}`,
    'conclude.md section 2, "Differing inputs": the settled record\'s follow-ups. File exactly these, each once:',
    ...asks.map((a, i) => `${i + 1}. ${a}`),
    `None blocks anything: never block ${T || 'any ticket'} or wait on them; the conclude stage proposes the status at once. A refused tickets_create: return the refusal verbatim in refusals. ` +
      'Write nothing in the pass folder and no claims_propose_status.',
  ].join('\n')), { label: 'settle-file', phase: 'Review', agentType: CHAIR, schema: SETTLE_FILED, effort: 'low' })
  const id = x => /^T-\d{4,}$/.test(String(x || '').trim()) ? String(x).trim() : ''
  const res = { repair: r ? id(r.repair) : '', cite: r ? strs(r.cite).map(id).filter(Boolean) : [], author: r ? id(r.author) : '', refusals: r ? strs(r.refusals) : [] }
  if (!r) notes.push('the settle-file stage returned nothing: no follow-up is known to be filed')
  if (r && r.blocked) notes.push(`ANOMALY: ${ticket} was blocked on a settled pass's follow-ups (nothing waits on them)`)
  for (const x of res.refusals) notes.push(`a settled pass's follow-up was refused (${x})`)
  if (res.repair) notes.push(`declaration repair ${res.repair} to ${to.instance}${decl.length ? ': declare ' + decl.join(', ') : ''} (settled, #121); it blocks nothing`)
  if (res.cite.length) notes.push(`cite tickets ${res.cite.join(', ')} for the missing sources (settled, #121)`)
  if (res.author) notes.push(`Author ticket ${res.author} for the remark (case 3)`)
  return res
}
const settled = settleRun ? await settleDependencies(settleRun) : null
const settleFiled = settled && settled.outcome === 'confirmed-settled' ? await fileSettled(settled) : null
log(runs.map(r => `${r.run}: ${r.lost ? 'lost' : r.verdict + ' -> ' + r.outcome}`).join('; '))
if (runs.some(r => r.stale)) {     // #89 review: a run file on another statement is never concluded on
  return { claim: A.claim, outcome: 'stale-pass', pass: prep.pass, pass_dir: prep.pass_dir, runs, notes,
    reason: `the pass ${prep.pass} holds a run on another statement: abandon it (reviews.py abandon ${A.claim} ${prep.pass} --reason "statement changed") and run again`,
    launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }
}

// ---- 3. Conclude --------------------------------------------------------------
phase('Conclude')
const done = await launch(STAGE('conclude', [
  `claim: ${A.claim}`, `ticket: ${ticket}`, `mode: ${MODE}`, `pass: ${prep.pass}`, `pass_dir: ${prep.pass_dir}`,
  `statement_hash: ${prep.statement_hash}`, `location: ${prep.location}`,
  `runs (from the workflow): ${JSON.stringify(runs)}`,
  `process notes for the record (copy them into its process note): ${JSON.stringify(notes)}`,
  falsifierRequest ? `The falsifier request ${falsifierRequest} was filed on the gap (it blocks nothing): name it in the record, the ticket result and its thread, alongside the follow-up repair.` : '',
  MODEL_FALLBACKS.length ? `A reviewer run fell back to a lighter model (${MODEL_FALLBACKS.join(', ')}): say so in the record, the ticket result and its thread.` : '',
  '',
  MODE === 'reword'
    ? 'conclude.md section 7 steps 6-7, then sections 4-6.'
    : counterexample
      ? `conclude.md section 1a, "A counterexample": the falsifier (${falsifier.source}${falsifier.on ? ' ' + falsifier.on : ''}) found a counterexample: ${falsifier.evidence}. ` +
        'Run B was not launched. Return outcome falsifier-counterexample and proposed_status none: never claims_propose_status, no status changes. ' +
        'Write the record decision.md (A\'s table, the falsifier and its evidence, the process notes), the evidence row for A, and route the counterexample as the decision table routes every counterexample (conclude.md section 4.3; decision_table follow_up, kind counterexample): ' +
        'one ticket, kind decision to human, at once, with the counterexample and where it is recorded (what becomes of the claim, a weaker statement or a repair, is the human\'s call); ' +
        'then the packet (the counterexample in Decisions needed, for the human), the ticket result and delivery, the blast radius, the report.'
      : (amending && runs.some(r => r.run === 'B' && !r.lost)
          ? 'An amend pass (conclude.md section 1b): run B reviewed the proof amended with A\'s suggested dependencies; decision_table.py A.md B.md decides it (mode amend), the added dependencies in its modulo until established. Then: '
          : '') +
        (settled && settled.outcome === 'confirmed-settled'
          ? `The table on B says settle-dependencies and the dependency-settler's record (S.md, S.json, against S-table.json, in the pass folder) was checked and applied by settle_deps.py: confirmed-settled (#121; conclude.md section 2, "Differing inputs"). ` +
            `Propose ${settled.proposed_status}${settled.modulo.length ? ' modulo ' + settled.modulo.join(', ') : ''} through claims_propose_status to the keeper, as for confirmed-modulo, with exactly these grounds: ${JSON.stringify(settled.grounds)}; ` +
            `file a verify-input item for each modulo input not established (section 2), except a kept definition (the table's kept_definitions): its definition-input decision to the human, once per definition (section 3, #103), and no decision ticket to the human on any other input. Record in decision.md both runs' lists (modulo_lists), the differing inputs, the settler's classification (S.md) and what apply returned (${settled.summary}; dropped ${JSON.stringify(settled.dropped)}; declarations ${JSON.stringify(settled.declarations)}; notes ${JSON.stringify(settled.notes)}; cite ${JSON.stringify(settled.cite)}). ` +
            (settleFiled && (settleFiled.repair || settleFiled.cite.length || settleFiled.author)
              ? `The workflow filed ${[settleFiled.repair && 'the declaration repair ' + settleFiled.repair, settleFiled.cite.length && 'the cite tickets ' + settleFiled.cite.join(', '), settleFiled.author && 'the Author ticket ' + settleFiled.author].filter(Boolean).join(', ')}: do not file them again; name them in the record, the packet and the ticket result. `
              : '') +
            'Return outcome confirmed-settled; settle_deps.py\'s proposed_status and grounds stand where sections 2-6 say the script\'s (the table alone stops at settle-dependencies). Then: '
          : settled
            ? `The table on B says settle-dependencies, and the differing inputs were not settled (${settled.summary}${settled.stops.length ? '; the settler\'s stops: ' + JSON.stringify(settled.stops) : ''}${settled.problems.length ? '; the record\'s problems: ' + settled.problems.join('; ') : ''}). ` +
              'Conclude it as a disagreement (no status, never claims_propose_status): the decision ticket to the human (section 4.3) with the union and intersection of the two lists as options, and the settler\'s classification attached for the human (S.md and S.json in the pass folder when written, the stops and their evidence above). Return outcome disagreement. Then: '
            : '') +
        'conclude.md sections 2-6: the input-by-input status, the final decision_table.py over the landed runs with --established, the record decision.md, evidence rows, the proposal (only the script\'s proposed_status), follow-up tickets exactly as the script routes them, the packet, the ticket result and delivery, the blast radius, the report.',
  'Then list the run files in the pass folder (run_files).',
].filter(s => s !== '').join('\n')), { label: 'conclude', phase: 'Conclude', agentType: CHAIR, schema: DONE })

if (!done) {
  return { claim: A.claim, pass: prep.pass, pass_dir: prep.pass_dir, outcome: 'conclude-lost', runs, notes, launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }
}
// the concluder launches nothing: only the runs this workflow made may be in the folder
const allowed = new Set(runs.filter(r => !r.lost).map(r => r.run + '.md'))
// a resumed pass (#89) also holds what the earlier launch left: its relaunches and no-verdict files
const earlier = f => landed.size > 0 && /^[AB](-\d+|-noverdict)\.md$/.test(f)
const extra = (done.run_files || []).map(f => f.split(/[\\/]/).pop())
  .filter(f => /^[ABR](-\d+)?(-noverdict)?\.md$/.test(f) && !allowed.has(f) && !earlier(f))
if (extra.length) notes.push('ANOMALY: run files the workflow did not launch: ' + extra.join(', '))
if (counterexample && done.proposed_status && done.proposed_status !== 'none') {
  notes.push(`ANOMALY: the concluder proposed ${done.proposed_status} on a falsifier's counterexample (no status may change)`)
}
if (settled && settled.outcome === 'confirmed-settled' && (done.outcome !== 'confirmed-settled' || done.proposed_status !== settled.proposed_status)) {
  notes.push(`ANOMALY: settle_deps.py settled the pass (${settled.proposed_status}, to the keeper), but the concluder returned outcome ${done.outcome}, proposed_status ${done.proposed_status}`)
}
if (settled && settled.outcome !== 'confirmed-settled' && done.proposed_status && done.proposed_status !== 'none') {
  notes.push(`ANOMALY: the concluder proposed ${done.proposed_status} on unsettled differing inputs (a disagreement: no status may change)`)
}
if (counterexample && done.outcome !== 'falsifier-counterexample') notes.push(`the concluder returned outcome ${done.outcome}: the pass is falsifier-counterexample`)
const res = { claim: A.claim, pass: prep.pass, pass_dir: prep.pass_dir, runs, notes,
         outcome: counterexample ? 'falsifier-counterexample' : done.outcome, proposed_status: done.proposed_status, record: done.record,
         packet: done.packet, tickets: done.tickets, report: done.report, anomalies: extra, falsifier_request: falsifierRequest,
         settle: settled ? { outcome: settled.outcome, proposed_status: settled.proposed_status || null, modulo: settled.modulo, stops: settled.stops,
           problems: settled.problems, attempts: settled.attempts, filed: settleFiled } : null,
         launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }
if (falsifier && falsifier.counts) res.falsifier = { source: falsifier.source, on: falsifier.on || null, evidence: falsifier.evidence, found: falsifier.found }
// the ticket's state is read by inbox.py --check itself (the concluder delivers it)
if (!A.nested) res.ship = await ship({ role: 'expert', ticket: ticket === 'none' ? '' : ticket, done: true, topic: 'verify-' + A.claim,
  only: 'library board', agentType: CHAIR, phase: 'Conclude', notes })
return res
