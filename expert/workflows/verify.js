export const meta = {
  name: 'academy-verify',
  description: 'Expert proof review of one registry statement: blind rigor-reviewer A, B only if A is CONFIRMED (or one reword run R), the decision table, the record, evidence, proposal and packet',
  whenToUse: 'Every verify ticket and /expert:verify, from the library home. args: {claim, ticket?, question?, mode?: "blind"|"reword", base_pass?, base_subject?, findings?}',
  phases: [
    { title: 'Prepare', detail: 'take the ticket, hash the statement, open the pass' },
    { title: 'Review', detail: 'blind run A; B only if the table says launch_b (or run R)' },
    { title: 'Conclude', detail: 'decision table, record, evidence, proposal, packet, follow-ups' },
  ],
}

// The sequencing rules of conclude.md sections 0-2 and 7, held in code rather than
// in prose (the 2026-10-31 decision): the reviewers are separate fresh agents, B is
// launched only when decision_table.py says launch_b and the statement hash has not
// moved, B gets A's brief byte for byte with run B, a reword pass runs R alone, a lost
// run is relaunched once, and nothing but the review-chair's clerical stages touches
// the files. The verdicts are landed by the expert plugin's land_verdict hook (it
// fires for workflow agents: B0 pilot, docs/workflows.md).

const A = args || {}

// ---- Models (docs/workflows.md, "Models"): the same block in every workflow. The skill
// that runs the workflow passes args.models, the JSON object `models.py launches` prints:
// the agents whose tier this workspace maps away from their file's model: line, and each
// such tier as "tier:<tier>". Every agent is launched through launch(): an agent the map
// names gets its workspace model; an agent with no academy file (general-purpose) is
// given a tier, never a model (launch(p, {agentType, tier: 'medium'})). Scripts name no
// model. Nested workflows get the same map.
const TIER_MODELS = (A.models && typeof A.models === 'object' && !Array.isArray(A.models)) ? A.models : {}
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
  },
  required: ['ok', 'stop_reason', 'pass', 'pass_dir', 'statement_hash', 'location', 'bundle', 'ticket', 'landed'],
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
  required: ['status', 'detail', 'branches', 'output'] }
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
    : { status: r.status, detail: r.detail }
  if (!/^(pushed|nothing)$/.test(res.status)) res.command = check
  if (res.status === 'refused' && s.notes) s.notes.push(`the ship stage was refused (${res.detail}); fix the cause, then run \`${check}\` once by hand`)
  return res
}

// ---- Max-tier model (docs/config.md, "How the map takes effect"; T-1682): the same block in every
// workflow that launches a max-tier agent (the prover and the graders). The launch value is
// args.models["<plugin:agent>"] (the inbox resolves the map once per run and passes it down), else
// one clerk stage runs models.py; a value that is no Agent-tool alias launches on the agent file's
// model:. A run that returns nothing (a usage limit) is relaunched once on FALLBACK_MODEL, the next
// tier down, and the fallback is noted (MODEL_FALLBACKS, for the record and the ticket).
const MODEL_ALIAS = /^(haiku|sonnet|opus|fable)$/
const FALLBACK_MODEL = 'opus'
const MODEL_OUT = { type: 'object', properties: { output: { type: 'string', description: 'the command output, verbatim' } }, required: ['output'] }
const LAUNCH_MODELS = {}
const MODEL_FALLBACKS = []
async function launchModel(name, s) {   // s: {agentType (a clerk with a shell), phase, notes}
  if (Object.prototype.hasOwnProperty.call(LAUNCH_MODELS, name)) return LAUNCH_MODELS[name]
  const given = (A.models && typeof A.models === 'object') ? A.models[name] : undefined
  let m = null
  const passed = A.models && typeof A.models === 'object' && !Array.isArray(A.models)   // even {}: the skill passed the map
  if (MODEL_ALIAS.test(String(given || ''))) m = given
  else if (passed && !given) m = null   // the passed map leaves it out: its file's model is the workspace's
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
  MODE === 'reword' ? `base_pass: ${A.base_pass || '(find it: reviews.py list)'}` : '',
  A.base_subject ? `base_subject: ${A.base_subject}` : '',
  A.findings ? `findings for the bundle: ${A.findings}` : '',
  '',
  MODE === 'reword'
    ? `conclude.md section 7 steps 1-4: take the ticket, recover old.txt, check the old hash, \`reviews.py new-pass <id> --reword-of <base pass>\` (with --base-subject when given), write the bundle with \`reviews.py reword-brief\` (no --new-file: it takes the registry's statement). statement_hash is the NEW statement's hash, the registry engine's: \`reviews.py hash --claim ${A.claim}\` (T-0464).`
    : `conclude.md section 0: take the ticket (its budget field gates nothing: never block it for budget), pin and hash the statement with \`reviews.py hash --claim ${A.claim}\` (the registry engine's statement text, the hash claims_set_status checks; never a hand-copied extract, T-0464), open the pass (\`reviews.py new-pass\`, \`reviews.py dir\`). For a statement that lives in a tex file, location is the output line of \`statement.py <label> --where --home <that Author home>\` (the file and the line ranges of the statement and its proof): a section file is too large to read whole, and the reviewer has no shell to find the lines. Write nothing in the pass folder. ` +
      'new-pass returns the open pass of this same ticket when one is open (a rerun, #89): then list in landed the run files already in its folder (A.md, B.md) with the statement_hash of each one\'s frontmatter.',
].filter(Boolean).join('\n')), { label: 'prepare', phase: 'Prepare', agentType: CHAIR, schema: PREP, effort: 'low' })

if (!prep || !prep.ok) {
  log('pass not started: ' + (prep ? prep.stop_reason : 'the prepare stage returned nothing'))
  return { claim: A.claim, outcome: 'not-started', reason: prep ? prep.stop_reason : 'prepare lost' }
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
const brief = (run) => MODE === 'reword'
  ? `Reword review of ${A.claim} (reword mode, run R): read the bundle ${prep.bundle} first; ` +
    `the proof is at ${prep.location}. The question: does the proof as reviewed still prove the new wording?\n` +
    ids.replace('RUN', 'R')
  : `Review ${A.claim}: its statement and proof are at ${prep.location}. The question: ${QUESTION} ` +
    `Work through your obligation ledger before reading the proof.\n` + ids.replace('RUN', run)

// ---- 2. Review: one run, checked by the table, relaunched once when it did not land ----
const notes = []
const table = (run) => launch(STAGE('table', [
  `pass_dir: ${prep.pass_dir}`, `run: ${run}`, `claim: ${A.claim}`,
  `Check that ${run}.md landed in the pass folder; run \`decision_table.py "<pass_dir>/${run}.md" --json\` ` +
  `(no B argument) and report its outcome and launch_b, and the statement_hash of the run file's own frontmatter (run_hash); re-hash the statement as it stands now ` +
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

phase('Review')
let runs = []
if (MODE === 'reword') {
  const r = await review('R')
  runs.push(Object.assign({ run: 'R' }, r))
  notes.push('reword pass: one informed run R, no blind pair (T-0347)')
} else {
  const a = await review('A')
  runs.push(Object.assign({ run: 'A' }, a))
  if (a.lost) {
    // nothing to add
  } else if (!a.launch_b) {
    notes.push(`run B skipped by design: the table on A says ${a.outcome} (launch_b false)`)
  } else if (a.hash_now !== prep.statement_hash) {
    notes.push(`statement moved under the review (hash ${prep.statement_hash} -> ${a.hash_now}): B not launched, nothing to conclude on the old wording`)
  } else {
    const b = await review('B')     // the identical brief, run B, a fresh agent told nothing of A
    runs.push(Object.assign({ run: 'B' }, b))
  }
}
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
  MODEL_FALLBACKS.length ? `A reviewer run fell back to a lighter model (${MODEL_FALLBACKS.join(', ')}): say so in the record, the ticket result and its thread.` : '',
  '',
  MODE === 'reword'
    ? 'conclude.md section 7 steps 6-7, then sections 4-6.'
    : 'conclude.md sections 2-6: the input-by-input status, the final decision_table.py over the landed runs with --established, the record decision.md, evidence rows, the proposal (only the script\'s proposed_status), follow-up tickets exactly as the script routes them, the packet, the ticket result and delivery, the blast radius, the report.',
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
const res = { claim: A.claim, pass: prep.pass, pass_dir: prep.pass_dir, runs, notes,
         outcome: done.outcome, proposed_status: done.proposed_status, record: done.record,
         packet: done.packet, tickets: done.tickets, report: done.report, anomalies: extra,
         launch_models: LAUNCH_MODELS, model_fallbacks: MODEL_FALLBACKS }
// the ticket's state is read by inbox.py --check itself (the concluder delivers it)
if (!A.nested) res.ship = await ship({ role: 'expert', ticket: ticket === 'none' ? '' : ticket, done: true, topic: 'verify-' + A.claim,
  only: 'library board', agentType: CHAIR, phase: 'Conclude', notes })
return res
