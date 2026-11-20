export const meta = {
  name: 'academy-experiment',
  description: 'One computational experiment, from a claim to a filed report, one leg per mode: design (the header, then the human approves), build (test-first, the strict check, then the human commits), queue, report (the draft checked and rendered, then the human looks), file',
  whenToUse: '/scientist:experiment and every experiment / test / question ticket of the lab (design is also nested from the inbox), from the lab home. args: {mode: "design"|"build"|"queue"|"report"|"file", claim?, ticket?, kind?, force? (design: no argument path), stem?, header?, commit_ok?, job?, env?}',
  phases: [
    { title: 'Leg', detail: 'the mode\'s own stages' },
    { title: 'Gate', detail: 'what the human must do before the next mode' },
  ],
}

// The order of /scientist:experiment in code (2026-10-31; docs/workflows.md). The human gates
// stay the human's, and the script makes them unskippable: no body before the header is
// approved (design stops), nothing queued before the human commits the script (build stops;
// queue refuses an uncommitted script), nothing filed before the human saw the rendered
// packet (report stops). Each mode is one call; the skill asks between them.

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
const MODES = ['design', 'build', 'queue', 'report', 'file']
if (!MODES.includes(A.mode)) throw new Error('args.mode must be one of ' + MODES.join(', '))
const CLERK = 'academy:inbox-clerk'
const EXP = 'scientist:experimenter'
const T = A.ticket || ''
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const SCRIPTS = `Scripts: lab.py is \`py ${AR}/scientist/scripts/lab.py\`, report.py is \`py ${AR}/scientist/scripts/report.py\`, from the lab home (python3 where there is no py)` +
  (ROOT ? '.\n' : '; <academy repo> is academy.root of the MCP tool workspace_get (academy.scripts.scientist is the scripts folder).\n')
// #124 (as inbox.js, 0881c94): detail is asked for and never required by HOME, QUEUED and MOVE
// (the ledger's 'must have required property detail' rows are academy:inbox-clerk's, this
// workflow's clerk too): clerk() fills in '' for it, and a reader says 'no reason given'
const withDetail = r => (r && typeof r === 'object' && typeof r.detail !== 'string') ? Object.assign({}, r, { detail: '' }) : r
const reasonOf = r => r.detail || 'no reason given'
const clerk = async (stage, lines, schema, label) => {
  const r = await launch(`WORKFLOW STAGE ${stage} of the academy-experiment workflow (mode ${A.mode}). Run from the lab home (lab.py home names it).\n` + SCRIPTS + lines.filter(Boolean).join('\n'),
    { label: label || stage, phase: 'Leg', agentType: CLERK, schema, effort: 'low' })
  return schema === HOME || schema === QUEUED || schema === MOVE ? withDetail(r) : r
}

const HOME = { type: 'object', properties: { ok: { type: 'boolean' }, instance: { type: 'string' }, home: { type: 'string' }, run_profile: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'instance', 'home', 'run_profile'] }
const DESIGN = { type: 'object', properties: {
  path: { type: 'string', enum: ['argument', 'probe', 'experiment'] },
  argument: { type: 'string', description: 'the two-line argument, when that settles it' },
  stem: { type: 'string', description: 'YYYY-MM-DD_<slug> of the script to be' },
  header: { type: 'string', description: 'the header only (for a probe: Kind: probe, Goal:, Decides:)' },
  if_false: { type: 'string', description: 'if the claim were false, what would this experiment still report?' },
  api_unfamiliar: { type: 'array', items: { type: 'string' }, description: 'library calls not yet confirmed in the pack' } },
  required: ['path', 'argument', 'stem', 'header', 'if_false', 'api_unfamiliar'] }
const BUILT = { type: 'object', properties: { script: { type: 'string' }, lab_claim: { type: 'string' }, tests: { type: 'array', items: { type: 'string' } }, note: { type: 'string' } }, required: ['script', 'lab_claim', 'tests', 'note'] }
const CHECK = { type: 'object', properties: { ok: { type: 'boolean' }, errors: { type: 'array', items: { type: 'string' } } }, required: ['ok', 'errors'] }
const COMMITTED = { type: 'object', properties: { committed: { type: 'boolean' }, commit: { type: 'string' }, dirty: { type: 'array', items: { type: 'string' } } }, required: ['committed', 'commit', 'dirty'] }
const QUEUED = { type: 'object', properties: { ok: { type: 'boolean' }, job: { type: 'string' }, command: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'job', 'command'] }
const DRAFT = { type: 'object', properties: { report: { type: 'string' }, result_line: { type: 'string' } }, required: ['report', 'result_line'] }
const RENDER = { type: 'object', properties: { ok: { type: 'boolean' }, rendered: { type: 'string', description: 'the rendered packet text' }, errors: { type: 'array', items: { type: 'string' } } }, required: ['ok', 'rendered', 'errors'] }
const FILED = { type: 'object', properties: { packet: { type: 'string' }, review_ticket: { type: 'string' }, researcher: { type: 'string' }, why: { type: 'string' }, error: { type: 'string' } }, required: ['packet', 'review_ticket', 'researcher'] }   // #124 follow-up 2: why and error asked, never required
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

const out = { mode: A.mode, ticket: T || null, notes: [] }
const gate = (why, extra) => Object.assign(out, { for_main: Object.assign({ gate: true, why, ticket: T || null }, extra || {}) })
phase('Leg')

if (A.mode === 'design') {
  const h = await clerk('lab-home', [T ? `First take ${T} (open -> accepted -> in-progress, acting as its receiver).` : '', 'Run lab.py home and return the lab instance, its home and the policy.run profile.'], HOME, 'lab home')
  if (!h || !h.ok) return Object.assign(out, { outcome: 'not-started', reason: h ? reasonOf(h) : 'lab.py home returned nothing' })
  const designBrief = `Design one experiment in the lab ${h.home} for ${A.claim || 'the ticket ' + T}${A.kind ? ' (kind ' + A.kind + ')' : ''}. Read the statement from its owner, the pack's examples.md, traps.md and ` +
    'computation/ through domain_get, the nearest existing script and the lab\'s package. ' +
    (A.force
      ? 'The human asked for the experiment itself (an argument was offered before and not taken): do not answer with an argument; classify it as a probe or an experiment. '
      : 'First classify the path: a two-line argument that settles it more cheaply than code (give it, and stop), a probe, or an experiment. ') +
    'A probe is feasibility, not evidence: header Kind: probe, Goal:, Decides:. For a probe or an experiment return the HEADER ONLY (no body, no code), ' +
    'the answer to "if the claim were false, what would this experiment still report?", and the library calls not yet confirmed in the pack.'
  const d = await launch(designBrief, { label: 'design', phase: 'Leg', agentType: EXP, schema: DESIGN })
  if (d === null) return Object.assign(out, { outcome: 'lost', reason: 'the experimenter returned nothing' })
  // #88: what comes back is checked in code. An argument instead of a header is the
  // human's call (accept it, prove instead, or run the experiment anyway), never a leg
  // left unfinished; a probe or experiment must bring a header (Kind:, no code), else one
  // retry, then the leg fails visibly instead of putting junk to the header gate.
  // a field line: markup around the key is allowed (`**Kind:** search`, `- Kind : x`, a
  // docstring opener), never a newline between the key and its value (review of 641a695)
  const field = (key) => new RegExp(`^[ \\t#*>\`"'-]*\\**${key}\\**[ \\t]*:[ \\t*\`]*([A-Za-z]+)`, 'mi')
  // code, not prose: 'class v = ...' in a wrapped sentence is prose (a real lab header)
  const CODE = /^[ \t]*(def \w+\s*\(|class \w+\s*[(:]|import [\w.]+(\s+as\s+\w+)?[ \t]*$|from [\w.]+ import [\w*])/m
  const problemsOf = (x) => {
    if (x.path === 'argument') return String(x.argument || '').trim() ? [] : ['path argument with no argument']
    const h = String(x.header || '')
    const probs = []
    const kind = ((h.match(field('Kind')) || [])[1] || '').toLowerCase()
    if (!h.trim()) probs.push('no header')
    else if (!kind) probs.push('no Kind: line (write it as a plain line: Kind: search)')
    else if (x.path === 'probe' && kind !== 'probe') probs.push(`path probe with Kind: ${kind} (a probe is Kind: probe)`)
    else if (x.path !== 'probe' && !/^(search|measure|verify)$/.test(kind)) probs.push(`Kind: ${kind} is not search, measure or verify (an experiment's kinds; Kind: probe goes with path probe)`)
    if (CODE.test(h)) probs.push('code in the header (the header only, no body)')
    if (x.path === 'probe' && !(field('Goal').test(h) && field('Decides').test(h))) probs.push('a probe needs Goal: and Decides:')
    if (!/^\d{4}-\d{2}-\d{2}_[\w-]+$/.test(String(x.stem || ''))) probs.push(`stem ${JSON.stringify(x.stem || '')} is not YYYY-MM-DD_<slug>`)
    return probs
  }
  if (A.force && d.path === 'argument') d.path = 'experiment'     // asked for the experiment: no argument path
  let probs = problemsOf(d)
  if (probs.length) {
    out.notes.push('the design returned no usable header (' + probs.join('; ') + '): one retry')
    const d2 = await launch(designBrief + `\n\nA first design returned this, which is not usable (${probs.join('; ')}):\n` +
      JSON.stringify({ path: d.path, stem: d.stem, header: d.header, argument: d.argument }) +
      '\nReturn it again, fixed: path probe or experiment with the HEADER ONLY (a plain Kind: line, the fields of that kind, no code) and a stem YYYY-MM-DD_<slug>' +
      (A.force ? '.' : '; or path argument with the argument, if an argument settles it.'), { label: 'design (retry)', phase: 'Leg', agentType: EXP, schema: DESIGN })
    if (d2) { Object.assign(d, d2); if (A.force && d.path === 'argument') d.path = 'experiment'; probs = problemsOf(d) }
    if (probs.length) {
      // never a ticket left in-progress that asks no one (review of 641a695)
      phase('Gate')
      out.reason = 'the design returned no usable header twice: ' + probs.join('; ')
      return gate('the design leg returned no usable header twice (' + probs.join('; ') + '): run mode design again, write the header with the experimenter here, or drop the ticket',
        { outcome: 'no-header', problems: probs, header: d.header || '', argument: d.argument || '' })
    }
  }
  Object.assign(out, { path: d.path, stem: d.stem, header: d.header, if_false: d.if_false })
  if (d.path === 'argument') {
    phase('Gate')
    out.argument = d.argument
    return gate('the experimenter answered with an argument instead of a header (#88): accept it (deliver the ticket with it as its result), ' +
      'prove instead (file a prove ticket to the Researcher with the argument as the lead), or run the experiment anyway (mode design again with force: true)',
      { argument: d.argument, outcome: 'argument-instead', options: ['accept the argument', 'prove instead', 'run the experiment anyway'],
        next: { mode: 'design', force: true, claim: A.claim || null, ticket: T, kind: A.kind || null } })
  }
  if ((d.api_unfamiliar || []).length) out.notes.push('unfamiliar library calls: run /scientist:api-check on ' + d.api_unfamiliar.join(', ') + ' before build')
  phase('Gate')
  return gate('approve the header (approve / change / drop) before any compute; ask also: ' + d.if_false, { header: d.header, stem: d.stem, next: { mode: 'build', stem: d.stem, ticket: T } })
}

if (A.mode === 'build') {
  if (!A.header || !A.stem) throw new Error('build needs args.header (the approved text) and args.stem')
  let b = await launch(`Build the experiment ${A.stem} from this APPROVED header (do not change it):\n${A.header}\n` +
    'Package code test-first, the script from the lab\'s template with validate() before run(), the lab claim created (claims_new, status open). Queue nothing, commit nothing.',
    { label: 'build', phase: 'Leg', agentType: EXP, schema: BUILT })
  if (b === null) return Object.assign(out, { outcome: 'lost', reason: 'the experimenter returned nothing' })
  let c = await clerk('check', [`Run lab.py cmd check experiments/${A.stem}.py --strict (run the command it prints) and return ok and the error lines.`], CHECK, 'check')
  if (c && !c.ok) {
    out.notes.push('the strict check failed; one fix round: ' + c.errors.join('; '))
    b = await launch(`The strict check of experiments/${A.stem}.py fails:\n- ${c.errors.join('\n- ')}\nFix the script (the header stays as approved).`, { label: 'build (fix)', phase: 'Leg', agentType: EXP, schema: BUILT }) || b
    c = await clerk('check', [`Run lab.py cmd check experiments/${A.stem}.py --strict again; return ok and the error lines.`], CHECK, 'check again')
  }
  Object.assign(out, { script: b.script, lab_claim: b.lab_claim, checked: !!(c && c.ok) })
  if (!out.checked) return Object.assign(out, { outcome: 'check-failed', reason: (c ? c.errors : []).join('; ') })
  phase('Gate')
  if (!A.commit_ok) return gate('commit the experiment script (the human commits it), then call mode queue', { script: b.script, next: { mode: 'queue', stem: A.stem, ticket: T } })
  out.notes.push('the human said to commit: the experimenter commits it with the result JSON rules of the lab')
  return Object.assign(out, { outcome: 'built', next: { mode: 'queue', stem: A.stem, ticket: T } })
}

if (A.mode === 'queue') {
  if (!A.stem) throw new Error('queue needs args.stem')
  const cm = await clerk('committed', [`Is experiments/${A.stem}.py committed and unchanged since (git status --porcelain of the path empty, git log -1 of the path)? Return committed, the commit, and the dirty paths.`], COMMITTED, 'committed?')
  if (!cm || !cm.committed) return gate('the script is not committed: the human commits it first (the queue runs the committed script)', { dirty: cm ? cm.dirty : [] })
  const q = await clerk('queue', [`File the run on the policy.run profile: lab.py cmd queue -Add experiments/${A.stem}.py -Label <the lab claim in its header> -Note "<one line>"` +
    (A.env ? ` (profile ${A.env})` : '') + '; run the command it prints; return the job id, the command, and any refusal.'], QUEUED, 'queue')
  if (!q || !q.ok) return Object.assign(out, { outcome: 'not-queued', reason: q ? reasonOf(q) : 'no answer' })
  return Object.assign(out, { outcome: 'queued', job: q.job, command: q.command, notes: ['watch it with /scientist:queue'] })
}

if (A.mode === 'report') {
  if (!A.stem) throw new Error('report needs args.stem')
  const opts = (A.env ? ` --env ${A.env}` : '') + (A.job ? ` --job ${A.job}` : '')
  let dr = await launch(`The result of experiments/${A.stem}.py is back${A.job ? ' (job ' + A.job + ')' : ''}. Fill the header's Result: ("no counterexample below bound B over class C", never "true"), ` +
    `and write the report draft reports/${A.stem}.md with ## Conclusion (Establishes: supports / refutes / inconclusive, Does not establish:, Proposed status:, Next step:) and ## Validation ` +
    '(Reproduced: yes|no). A surprising result is a bug until shown otherwise: say what you checked.', { label: 'report draft', phase: 'Leg', agentType: EXP, schema: DRAFT })
  if (dr === null) return Object.assign(out, { outcome: 'lost', reason: 'the experimenter returned nothing' })
  let c = await clerk('report-check', [`Run report.py check experiments/${A.stem}.py${opts}; return ok and every refusal line.`], CHECK, 'report check')
  if (c && !c.ok) {
    out.notes.push('report.py check refused; one fix round: ' + c.errors.join('; '))
    dr = await launch(SCRIPTS + `report.py check refuses experiments/${A.stem}.py:\n- ${c.errors.join('\n- ')}\nFix the header or the draft (never a hand-written packet).`, { label: 'report draft (fix)', phase: 'Leg', agentType: EXP, schema: DRAFT }) || dr
    c = await clerk('report-check', [`Run report.py check experiments/${A.stem}.py${opts} again; return ok and the refusal lines.`], CHECK, 'report check again')
  }
  if (!c || !c.ok) return Object.assign(out, { outcome: 'check-failed', reason: (c ? c.errors : []).join('; ') })
  const r = await clerk('render', [`Run report.py render experiments/${A.stem}.py${opts}; return ok and the rendered text.`], RENDER, 'render')
  phase('Gate')
  return gate('the human sees the rendered packet before it is filed', { rendered: r ? r.rendered : '', result_line: dr.result_line, next: { mode: 'file', stem: A.stem, ticket: T, job: A.job, env: A.env } })
}

// file
if (!A.stem) throw new Error('file needs args.stem')
const opts = (A.env ? ` --env ${A.env}` : '') + (A.job ? ` --job ${A.job}` : '') + (T ? ` --ticket ${T}` : '')
const f = await clerk('report-file', [`Run report.py file experiments/${A.stem}.py${opts}; return the packet id, the review-experiment ticket it filed, the Researcher it went to and why (the script prints it), or the error.`], FILED, 'file')
if (!f || !f.packet) return Object.assign(out, { outcome: 'not-filed', reason: f ? f.error || 'no reason given' : 'no answer' })
if (T) {
  const m = await clerk('close', [`Deliver ${T} (tickets_update deliver: true, acting as its receiver) with result "report ${f.packet}; review ticket ${f.review_ticket} to ${f.researcher}" and fields.packets [${f.packet}].`], MOVE, 'deliver')
  out.ticket_delivered = !!(m && m.ok)
}
Object.assign(out, { outcome: 'filed', packet: f.packet, review_ticket: f.review_ticket, researcher: f.researcher, why: f.why || 'no reason given' })
// only the file leg ships: the other legs end at a human gate (build's commit is the human's)
if (!A.nested) out.ship = await ship({ role: 'scientist', ticket: T, done: !!out.ticket_delivered, topic: 'report-' + A.stem,
  only: '<home submodule> board', agentType: CLERK, phase: 'Leg', notes: out.notes })
return out
