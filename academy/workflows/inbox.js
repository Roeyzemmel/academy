export const meta = {
  name: 'academy-inbox',
  description: 'Work the board inboxes in the fixed order (Author, Expert, Researcher, Scientist), at most three tickets, serially: routes, relay legs and their conclusions, checkpoints, all in code',
  whenToUse: '/academy:inbox and every role inbox (only: [instance]). args: {root: <academy repo>, n?, cap?, only?: [instance], campaign?, cowork?, ids?: [T-NNNN], sweep?: false (skip the Author\'s note sweep)}',
  phases: [
    { title: 'List', detail: 'each instance\'s inbox.py --json' },
    { title: 'Sweep', detail: 'the Author\'s machine-note sweep, before any ticket' },
    { title: 'Tickets', detail: 'one ticket at a time, by route, then its checkpoint' },
    { title: 'Close', detail: 'the Author\'s delivered self-tickets' },
  ],
}

// The inbox rules of /academy:inbox and the four role inboxes, and the relays' legs, in
// code (the human's decision, 2026-10-31; docs/workflows.md):
//  * the instance order, the cap over the whole run (budget.md rule 1), one ticket at a
//    time with its --check checkpoint (rule 2), a lost agent stops the run (rule 4).
//    A ticket the run leaves unfinished skips only itself (2026-11-14: one ticket waiting
//    on a decision, listed first in every run, closed its whole instance in every run):
//    it is not taken again this run; a ticket that ends blocked is parked, not unfinished;
//    one that was already in-progress before the run and is still unfinished after it is
//    handed to the human (blocked, waiting_on human), so it reaches /academy:decide and
//    stops heading the list; a second unfinished ticket of one instance closes that
//    instance for the run (something there is failing, and the cap is not to be spent on it);
//  * the route is the role's routes.py (in the inbox.py row); this script dispatches it:
//    reject / human / over-budget are clerk moves; a relay's forward leg is the relay's
//    decision and its child ticket only, and the script then checks the child (parent,
//    receiver role, kind, final_to) and makes the conclusion (blocked on the child, or
//    delivered when it failed fast); a relay's return leg is mechanical and made here
//    without the relay; verify and review-experiment run their own workflows nested;
//    a route that needs the main session (a skill, a question to the human, a ticket
//    only `main` may file) ends the run with `for_main`, in order, so nothing overtakes it.
// Every transition is made by the academy's inbox-clerk, acting for the ticket's party
// (instance=...). Each agent runs under its own definition and the plugin hooks. The
// clerk's move vocabulary is its agent file (academy/agents/inbox-clerk.md): no stage here
// lists the moves; each names one (release is blocked -> accepted; the receiver's put back
// of a started ticket, in-progress -> accepted, is one direct step since #123).

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
if (!A.root) throw new Error('args.root must be the academy repo (the folder holding the plugins)')
// ---- Code pin (docs/workflows.md, "Pinned code"; #97): the same block in inbox.js and workplan.js.
// The run reads its code from a worktree of the academy repo pinned at the commit HEAD pointed to
// when it started (academy/scripts/run_pin.py), so a merge, a branch switch or a publish during the
// run changes nothing it runs: every script command and nested workflow takes CODE.root, never
// args.root. args.code (the JSON object `run_pin.py start --json` printed, or its text) is a pin the
// caller made and ends; a nested run (nested: true) runs on the root it was given; pin: false runs on
// args.root, the live checkout. Otherwise the pin stage makes one, and the run ends it on every way
// out (pinEnd(), from a finally, which never throws: a lost unpin is CODE.end_error). A run that hands
// work back (a for_main or a gate: its args carry the pin's root) holds the pin longer (end --hold), and
// CODE.expires says until when. A pin stage that returns no pin is a note, never a failed run.
const PIN_OUT = { type: 'object', properties: { exit: { type: 'number', description: 'the exit code the shell printed' },
  output: { type: 'string', description: 'the command output, verbatim' } }, required: ['output'] }
const PIN_PY = `py ${String(A.root || '').replace(/[\\/]+$/, '')}/academy/scripts/run_pin.py`
const CODE = { sha: null, root: String(A.root || '').replace(/[\\/]+$/, ''), pinned: false, run: null, why: '' }
const PIN_NOTES = []
const PIN_OWN = { run: null, out: null }   // the pin this run made, and so ends; out: the run's result
const pinRead = v => {             // a pin (object or its JSON text, a code fence allowed), else null
  if (typeof v === 'string') {
    const t = v.trim().replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '')
    try { v = JSON.parse(t) } catch (e) { return null }
  }
  if (!v || typeof v !== 'object' || Array.isArray(v) || typeof v.root !== 'string' || !v.root) return null
  if (v.pinned && !/^[0-9a-f]{40}$/.test(String(v.sha || ''))) return null
  return v
}
const pinSet = (c, why) => Object.assign(CODE, { sha: c.sha || null, root: c.root.replace(/[\\/]+$/, ''),
  pinned: !!c.pinned, run: c.run || null, why })
async function pinStart(label) {
  if (A.code !== undefined && A.code !== null) {
    const c = pinRead(A.code)
    if (!c) throw new Error(`args.code is no pin (${String(JSON.stringify(A.code)).slice(0, 80)}): pass the JSON object \`${PIN_PY} start --json\` prints, or leave it out`)
    return pinSet(c, 'given by the caller, which ends it' + (c.why ? ': ' + c.why : ''))
  }
  if (A.nested) { CODE.why = 'nested: the calling run pins the code and gave this root'; return CODE }
  if (A.pin === false) { CODE.why = 'args.pin false: the run reads the live checkout'; return CODE }
  const tag = String(label).replace(/[^A-Za-z0-9@+._-]/g, '-').slice(0, 60)
  const r = await launch(`WORKFLOW STAGE pin. Run \`${PIN_PY} start --label ${tag} --json\` once (python3 where there is no py). ` +
    'Fix nothing, whatever it prints: return the exit code the shell printed and its whole output verbatim.',
  { label: 'pin', agentType: 'general-purpose', tier: 'base', schema: PIN_OUT, effort: 'low' })
  const c = r ? pinRead(String(r.output || '')) : null
  if (!c) {
    CODE.why = 'the pin stage ' + (r ? `printed no pin (${JSON.stringify(String(r.output || '').slice(0, 160))})` : 'returned nothing')
    PIN_NOTES.push(`code not pinned: ${CODE.why}; the run reads the live checkout ${CODE.root}`)
    return CODE
  }
  pinSet(c, String(c.why || ''))
  if (!c.pinned) PIN_NOTES.push(`code not pinned: ${CODE.why || 'run_pin.py gave no reason'}`)
  else {
    PIN_OWN.run = c.run || null
    if (c.dirty) PIN_NOTES.push(`code pinned at ${CODE.sha.slice(0, 12)}: ${CODE.why}`)
  }
  return CODE
}
async function pinEnd() {         // once, on every way out of a run that made its pin; never throws
  if (!PIN_OWN.run) return
  const run = PIN_OWN.run
  PIN_OWN.run = null
  const o = PIN_OWN.out || {}
  const hold = !!((Array.isArray(o.for_main) ? o.for_main.length : o.for_main) || (o.gates && o.gates.length))
  try {
    const r = await launch(`WORKFLOW STAGE unpin. Run \`${PIN_PY} end --run ${run}${hold ? ' --hold' : ''} --json\` once (python3 where there is no py). ` +
      'Fix nothing, whatever it prints: return the exit code the shell printed and its whole output verbatim.',
    { label: 'unpin', agentType: 'general-purpose', tier: 'base', schema: PIN_OUT, effort: 'low', record: true })
    let e = null
    try { e = JSON.parse(String((r && r.output) || '').trim().replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '')) } catch (x) { e = null }
    CODE.ended = !!(e && e.ended === true)
    if (e && e.expires_iso) CODE.expires = e.expires_iso
    if (!CODE.ended) CODE.end_error = r ? `the unpin stage printed ${JSON.stringify(String(r.output || '').slice(0, 160))}` : 'the unpin stage returned nothing'
  } catch (x) {
    CODE.ended = false
    CODE.end_error = `the unpin stage threw: ${String(x && x.message || x).slice(0, 200)}; the marker goes stale on its own (run_pin.py end --run ${run} clears it)`
  }
}
// ---- end Code pin
// the run's code, pinned before anything reads it; the run below ends the pin in its finally
await pinStart('inbox-' + String(A.run_id || ((A.only && A.only.length) ? A.only.join('+') : 'all')))
const ROOT = CODE.root
try {   // the whole run, unindented: its finally ends the pin on every way out (a return, a throw)
// loop (2026-10-31): pass after pass over every inbox until nothing moves; a ticket that needs
// the human becomes a gate (set aside, collected, asked in one batch) and the others go on.
// The whole academy then runs in code, with the human asked only where the rules need them.
const LOOP = !!A.loop
const CAP = LOOP ? Math.max(1, Math.min(A.cap || 12, 30)) : Math.max(0, Math.min(A.cap || A.n || 3, (A.campaign || A.cowork) ? 99 : 3))
const MAX_PASSES = LOOP ? Math.max(1, Math.min(A.passes || 6, 12)) : 1
// ---- The run's budget (references/budget.md rule 7, as of 2026-11-14) ---------------------
// A budget is the run's, counted here as the run goes; it is no longer a number guessed on
// each ticket when it was filed (916 of 1201 tickets carried the default of 1, and a route
// that needed more blocked its ticket on the human "asking for the budget"). Each route's
// cost in agent runs is declared below, by the code that launches them. A ticket whose cost
// does not fit what is left WAITS for the next run (deferred, reported, first in line then);
// it is never blocked for budget. One threshold stays: a ticket costing more than BIG runs
// needs the human's word (args.approve names it). The session's token target, when the human
// set one, ends the taking as well.
const RUN_BUDGET = Math.max(1, Math.min(A.runs || (LOOP ? 36 : 12), 200))
const BIG = Math.max(1, A.big || 8)
const APPROVED = new Set(A.approve || [])
const NESTED_COST = { 'expert:verify': 3, 'researcher:review-experiment': 3, 'researcher:settle': 4, 'researcher:explore': 3,
  'researcher:prove': 2, 'researcher:generalize': 2, 'expert:cite': 1, 'expert:domain': 1, 'expert:referee': 1, 'author:notes': 1 }
function costOf(row, i) {
  const rt = row.route || {}
  if (row.return || row.released || rt.how === 'reject' || rt.how === 'human' || rt.how === 'wait') return 0   // clerk moves only
  if (i.role === 'expert' && rt.target === 'clerk') return 2            // the clerk, and the librarian if it escalates
  if (i.role === 'scientist' && rt.target === 'developer') return 4     // developer and test-engineer, two rounds
  if (rt.how === 'skill') return NESTED_COST[rt.target] || 1
  return 1
}
let spent = 0
const deferred = []
const ORDER = ['author', 'expert', 'researcher', 'scientist']
const CLERK = 'academy:inbox-clerk'
// a relay: the role its child goes to, the kinds the child may have, the final_to default
const RELAYS = {
  'research-intake': { role: 'expert', to: 'researcher', kinds: ['research'], final_default: 'researcher' },
  'paper-liaison': { role: 'expert', to: 'author', kinds: ['question', 'note'] },
  'experiment-spec': { role: 'researcher', to: 'scientist', kinds: ['experiment', 'test'] },
  'lit-request': { role: 'researcher', to: 'expert', kinds: ['cite', 'question'] },
}
const NESTED = {
  'expert:verify': ROOT + '/expert/workflows/verify.js',
  'researcher:review-experiment': ROOT + '/researcher/workflows/review-experiment.js',
  'researcher:prove': ROOT + '/researcher/workflows/prove.js',
  'expert:cite': ROOT + '/expert/workflows/cite.js',
  'researcher:explore': ROOT + '/researcher/workflows/explore.js',
  'researcher:generalize': ROOT + '/researcher/workflows/generalize.js',
  'expert:referee': ROOT + '/expert/workflows/referee.js',
  'expert:domain': ROOT + '/expert/workflows/domain.js',
  'author:notes': ROOT + '/author/workflows/notes.js',
  'scientist:experiment': ROOT + '/scientist/workflows/experiment.js',
}
// every child above is called with nested: true, so it ships nothing itself: this run's --check
// checkpoint ships the ticket's work (docs/workflows.md)
// nested: this run is itself a sub-workflow (of workplan.js); nesting is one level only, so
// the routes that run their own workflow are handed back as for_main instead
const NESTED_OK = !A.nested
const roleOf = (inst) => String(inst || '').split('@')[0]

const ROW = {
  type: 'object',
  properties: {
    id: { type: 'string' }, kind: { type: 'string' }, status: { type: 'string' },
    from: { type: 'string' }, to: { type: 'string' }, final_to: { type: 'string' }, parent: { type: 'string', description: 'the parent ticket, or empty' },
    blocked: { type: 'string', description: 'the row\'s blocked state (e.g. pending), or empty' },
    title: { type: 'string', description: 'the ticket\'s title, verbatim (the verify route reads its claim from it, #89)' },
    refs: { type: 'array', items: { type: 'string' } },
    budget_runs: { type: 'number' },
    // #124: why is asked for, never required (a clerk that leaves it out would lose the list); read as 'no reason given'
    route: { type: 'object', properties: { how: { type: 'string' }, target: { type: ['string', 'null'] }, why: { type: 'string' } }, required: ['how', 'target'] },
    return: { type: 'boolean' }, released: { type: 'boolean' }, over_budget: { type: ['string', 'null'] },
  },
  required: ['id', 'kind', 'status', 'from', 'to', 'final_to', 'refs', 'budget_runs', 'route', 'return', 'released', 'over_budget'],
}
const LIST = {
  type: 'object',
  properties: {
    instances: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' }, role: { type: 'string' }, home: { type: 'string' }, waiting: { type: 'number' },
      rows: { type: 'array', items: ROW } }, required: ['name', 'role', 'home', 'waiting', 'rows'] } },
  },
  required: ['instances'],
}
// #124: detail is asked for and never required (23 clerk runs lost to 'must have required property
// detail' in the ledger since 2026-11-14): clerk() fills in '' for it, and the code reads that
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, status: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'status'] }
const CHECK = { type: 'object', properties: { exit: { type: 'number', description: 'the process exit code as printed by the shell, never inferred' },
  status: { type: 'string' }, output: { type: 'string', description: 'the command output, verbatim' }, detail: { type: 'string' } }, required: ['exit', 'status', 'output'] }
// the check's verdict is read from its own first line ("T-NNNN: <state> (<status>)"), not from the clerk's reading
// of it (live run 2026-10-31: a refused checkpoint made the clerk report exit 3 for a delivered ticket)
const FINISHED = /^(delivered|closed|rejected|cancelled)$/
function readCheck(chk, id) {
  if (!chk) return null
  const m = new RegExp('^' + id + ': (\\S+) \\(([^)]+)\\)', 'm').exec(String(chk.output || ''))
  const status = m ? m[2] : chk.status
  const exit = m ? (FINISHED.test(status) ? 0 : 3) : chk.exit
  const shipped = !/REFUSED|checkpoint incomplete|checkpoint for \S+ exited [1-9]/.test(String(chk.output || ''))
  return Object.assign({}, chk, { status, exit, shipped })
}
const TICKET = { type: 'object', properties: {
  found: { type: 'boolean' }, id: { type: 'string' }, from: { type: 'string' }, to: { type: 'string' },
  kind: { type: 'string' }, status: { type: 'string' }, parent: { type: 'string' }, final_to: { type: 'string' },
  packets: { type: 'array', items: { type: 'string' } } },
  required: ['found', 'id', 'from', 'to', 'kind', 'status', 'parent', 'final_to', 'packets'] }
const RELAY_OUT = { type: 'object', properties: {
  decision: { type: 'string', enum: ['fail-fast', 'forward', 'refused'] },
  result: { type: 'string', description: 'one line: the reason (fail-fast), the child id and ask (forward), the refusal (refused)' },
  result_detail: { type: 'string', description: 'the ## Result body for a fail-fast; else empty' },
  child: { type: 'string', description: 'the child ticket id you filed, or empty' },
  notes: { type: 'array', items: { type: 'string' }, description: 'note tickets filed to the Author, if any' } },
  required: ['decision', 'result', 'result_detail', 'child', 'notes'] }

// #101 part 1 (the human's design, 2026-11-20): before a ticket that launches any agent, the
// clerk records every home's dirty set as this run's claim (manifest.py snapshot); the ticket's
// --check then ships exactly what changed since, in every home, as WIP when it is unfinished,
// and the claim keeps the opt-in stop check (stop_check.py) off the run's files meanwhile.
// One claim file per run and ticket (<run>-<id>.json: concurrent runs never overwrite each
// other's; stale ones are removed at each snapshot and check): run_id names the run, else
// the instances it works. snapshot: false (args) runs without it, as before: --check then ships the ticket's
// repos by --only.
const SNAPSHOT = A.snapshot !== false
// #96 (the human's choice, 2026-11-27: "Leases, one checkout"): two runs with disjoint instance
// sets may work in one checkout at once. After the listing, the clerk takes a lease for this run
// on the home of every listed instance (manifest.py lease take); an instance whose home another
// live run holds is skipped for this run (a note says so), never waited for. Each ticket's
// snapshot heartbeats the run's leases; the run releases them at its end, early stops included
// (a run that dies leaves them to go stale: its pid gone, or 30 minutes without a heartbeat
// when the pid cannot be checked).
// The run id is made unique by that stage (the prefix below, a timestamp and a random suffix:
// a script has no clock of its own); args.run_id names it instead. The leases and the claims
// use the same id. leases: false (args) runs without them, with the prefix as the run id.
const LEASES = A.leases !== false
const RUN_BASE = ('inbox-' + String(A.run_id || ((A.only && A.only.length) ? A.only.join('+') : 'all')))
  .replace(/[^A-Za-z0-9@+._-]/g, '-').slice(0, 90)
let RUN_ID = RUN_BASE
const LEASE = { held: false, skipped: new Map() }
const SNAP = { type: 'object', properties: { exit: { type: 'number', description: 'the exit code the shell printed' },
  output: { type: 'string', description: 'the command output, verbatim' } }, required: ['exit'] }
const withDetail = r => (r && typeof r === 'object' && typeof r.detail !== 'string') ? Object.assign({}, r, { detail: '' }) : r
const clerk = async (stage, lines, schema, label) => {
  const r = await launch(
    `WORKFLOW STAGE ${stage} of the academy-inbox workflow.\n` + lines.filter(Boolean).join('\n'),
    { label: label || stage, phase: stage === 'list' ? 'List' : (stage === 'close-self' ? 'Close' : 'Tickets'), agentType: CLERK, schema, effort: 'low' })
  return schema === MOVE || schema === CHECK ? withDetail(r) : r
}
// a stage that throws (no structured output) is a failed snapshot or check, never a failed run
const tryClerk = async (stage, lines, schema, label) => { try { return await clerk(stage, lines, schema, label) } catch (e) { return null } }
const PID_NOTE = '$PPID is left for the shell to expand (the session\'s process, whose end ends the claim and the leases)'
async function snapshot(row) {
  const r = await tryClerk('snapshot', [`py ${ROOT}/academy/scripts/manifest.py snapshot --ticket ${row.id} --run ${RUN_ID} --pid $PPID`,
    `Run it once, as written (python3 where there is no py; ${PID_NOTE}). Return the exit code the shell printed and the output verbatim.`], SNAP, `snapshot ${row.id}`)
  const ok = !!(r && r.exit === 0)
  if (!ok) notes.push(`${row.id}: no snapshot before it (${r ? String(r.output || '').replace(/\s+/g, ' ').slice(0, 120) : 'the stage returned nothing'}); its checkpoint ships its repos by --only, as before`)
  return ok
}
const checkCmd = (row, i) => [`py ${ROOT}/${i.role}/scripts/inbox.py --instance ${i.name} --check ${row.id}`,
  'Run it once. Return the exit code the shell printed (echo $?), the ticket status, and the whole output verbatim in output.']
// #96: the leases. take: the run's id and the instances it may run; release: at the end
async function takeLeases(xs) {
  if (!LEASES || !xs.length) return xs
  const r = await tryClerk('lease', [`py ${ROOT}/academy/scripts/manifest.py lease take ${A.run_id ? '--run' : '--prefix'} ${RUN_BASE} ` +
    `--instances ${xs.map(i => i.name).join(',')} --pid $PPID`,
  `Run it once, as written (python3 where there is no py; ${PID_NOTE}). Return the exit code the shell printed and the output verbatim.`], SNAP, 'lease take')
  const text = String((r && r.output) || '')
  const m = /^run (\S+)\s*$/m.exec(text)
  const id = m && m[1]
  if (!r || r.exit !== 0 || !id || !/^[A-Za-z0-9@+._-]{1,120}$/.test(id) || !id.startsWith(RUN_BASE)) {
    notes.push(`no leases taken (${r ? text.replace(/\s+/g, ' ').slice(0, 120) || 'exit ' + r.exit : 'the stage returned nothing'}): ` +
      `this run works unleased as run ${RUN_ID}; a concurrent run in this checkout is not kept off its homes (#96)`)
    return xs
  }
  RUN_ID = id
  LEASE.held = true
  for (const line of text.split(/\r?\n/)) {
    const k = /^skipped (\S+): (.*)$/.exec(line.trim())
    if (k && xs.some(i => i.name === k[1])) LEASE.skipped.set(k[1], k[2])
  }
  for (const [name, why] of LEASE.skipped) notes.push(`${name} is skipped this run: ${why} (#96: its home is another live run's)`)
  out.leases = { run: RUN_ID, skipped: [...LEASE.skipped.keys()] }
  return xs.filter(i => !LEASE.skipped.has(i.name))
}
async function releaseLeases() {
  if (!LEASE.held) return
  LEASE.held = false
  let r = null
  try {
    // record: tried after a stop as well (a usage limit makes it fail, and the leases then go stale)
    r = await launch(`WORKFLOW STAGE lease of the academy-inbox workflow.\npy ${ROOT}/academy/scripts/manifest.py lease release --run ${RUN_ID}\n` +
      'Run it once (python3 where there is no py). Return the exit code the shell printed and the output verbatim.',
    { label: 'lease release', phase: 'Close', agentType: CLERK, schema: SNAP, effort: 'low', record: true })
  } catch (e) { r = null }
  if (!r || r.exit !== 0) notes.push(`the leases of run ${RUN_ID} were not released (they go stale in 30 minutes): py ${ROOT}/academy/scripts/manifest.py lease release --run ${RUN_ID}`)
}
const move = (row, inst, what, label) => clerk('move', [`ticket: ${row.id}`, `act as: ${inst}`, what], MOVE, label || `${row.id} ${what.split(':')[0]}`)

const notes = []
const taken = []

const out = { taken, notes, for_main: null, gates: [], remaining: {}, passes: 0, budget: null, code: CODE }
notes.push(...PIN_NOTES)
PIN_OWN.out = out
const followed = new Set(A.ids || [])
const children = new Set()           // follow: the child ids this run's relays and research asks filed

// ---- List ---------------------------------------------------------------------------
const knownHome = {}                 // instance -> the last non-empty home a listing gave
// #94 (2026-11-19 21:17): the list stage returned {"instances": []} and the run did nothing, while
// inbox.py listed 24 waiting tickets a minute later. The scripts cannot print that: every instance
// is one entry, and (without --ids, which filters the rows and not the count) waiting > 0 means rows.
// Such a listing is a failed stage: listed once more; empty twice, the run says so (list_failed).
let listFailed = ''
const NO_INSTANCE = 'no instance at all (every instance of workspace.json is one entry, even with no rows)'
function listingProblems(listed) {
  const xs = Array.isArray(listed.instances) ? listed.instances.filter(i => !A.only || A.only.includes(i.name)) : []
  if (!xs.length) return [NO_INSTANCE]
  if (A.ids && A.ids.length) return []
  return xs.filter(i => i.waiting > 0 && !(i.rows || []).length).map(i => `${i.name}: ${i.waiting} waiting, no rows`)
}
async function listAll(pass) {
  const label = pass > 1 ? `list ${pass}` : 'list'
  const lines = [
    `For each instance of workspace.json${A.only ? ' among ' + JSON.stringify(A.only) : ''}, run its role's inbox script:`,
    // with ids the per-instance cut (itemsPerRun) would hide the named tickets, and --all is too long to transcribe
    // (live runs 2026-10-31: 304 rows, four instances lost): --ids filters in the script (the ids and their children)
    `py <academy>/<role>/scripts/inbox.py --instance <name> --json${A.ids && A.ids.length ? ' --ids ' + [...new Set([...A.ids, ...(A.follow ? [...followed, ...children] : [])])].join(',') : ''}${A.n ? ' --n ' + A.n : ''}${A.campaign ? ' --campaign ' + A.campaign : ''}${A.cowork ? ' --cowork ' + A.cowork : ''} (academy = ${ROOT}).`,
    'Return every instance (one entry each, even with no rows) with its "home" copied verbatim from the script\'s JSON (never a path you know otherwise: the workspace\'s checkout, #116), ' +
    'and every row of "take" with the fields asked (final_to empty when none; budget_runs from budget.runs, 1 when absent; released false when absent), and "waiting".',
  ]
  let listed = await clerk('list', lines, LIST, label)
  if (!listed) return null
  let bad = listingProblems(listed)
  if (bad.length) {
    notes.push(`the ${label} stage returned ${bad.join('; ')}: a failed stage, listed once more`)
    listed = await clerk('list', lines.concat([`A first listing returned ${bad.join('; ')}, which the scripts never print: ` +
      'run every instance\'s script again and transcribe its JSON as it is.']), LIST, label + ' (retry)')
    if (!listed) return null
    bad = listingProblems(listed)
    if (bad[0] === NO_INSTANCE) {
      listFailed = `the ${label} stage returned no instance twice: a failed stage, not "nothing to do"; run the inbox scripts by hand (inbox.py --instance <name> --json) and run again`
      return null
    }
    for (const b of bad) notes.push(`ANOMALY: ${b} after the retry: its tickets are not taken this pass; inbox.py --instance ${b.split(':')[0]} --json lists them`)
  }
  const xs = listed.instances.filter(i => (!A.only || A.only.includes(i.name)) && !LEASE.skipped.has(i.name))
  // a later listing can come back with home '' (live run 2026-11-17: the second pass lost every home and the
  // nested prove threw 'args.home must be the Researcher home', ending the run): keep the last home seen
  for (const i of xs) { if (i.home) knownHome[i.name] = i.home; else if (knownHome[i.name]) i.home = knownHome[i.name] }
  xs.sort((a, b) => ORDER.indexOf(a.role) - ORDER.indexOf(b.role) || (a.name < b.name ? -1 : 1))
  // ids: only these tickets; with follow (a loop), also the children of a ticket this run handled,
  // so a relay's child and its return leg move within the same cap
  // A row listed under an instance it is not addressed to is a transcription slip (live run 2026-10-31: a researcher
  // ticket listed under the Scientist): it is dropped, never run with the wrong role
  for (const i of xs) i.rows = i.rows.filter(r => {
    // a return leg is addressed to the receiver and landed by its sender (2026-11-13: T-0369 and T-1153 were dropped)
    if (!r.to || r.to === i.name || (r.return && r.from === i.name)) return true
    notes.push(`ANOMALY: ${r.id} was listed under ${i.name} but is addressed to ${r.to}: dropped from this pass`)
    return false
  })
  if (A.ids && A.ids.length) for (const i of xs) i.rows = i.rows.filter(r => (A.ids.includes(r.id)
      || (A.follow && (children.has(r.id) || (r.parent && followed.has(r.parent)))))
    && !(r.blocked && !r.return && !r.released))   // --all lists pending blocked tickets too: those are not takeable
  // #92: whatever the listing gave (the clerk transcribes it), a row is taken only when the
  // inbox may take it: open, accepted or in-progress, or a return leg / released row
  const TAKEABLE = new Set(['open', 'accepted', 'in-progress'])
  for (const i of xs) i.rows = i.rows.filter(r => {
    if (r.return || r.released || !r.status || TAKEABLE.has(r.status)) return true
    notes.push(`${r.id} was listed with status ${r.status}: not taken`)
    return false
  })
  for (const i of xs) out.remaining[i.name] = i.waiting
  return xs
}
phase('List')
const LIMIT_WHY = 'three agent launches in a row returned nothing: most likely a usage limit (every launch fails until it resets: ' +
  'the session\'s own error names the reset time; resume after it). Nothing further launched (#115)'
let insts = await listAll(1)
if (!insts) return Object.assign(out, listFailed ? { stopped: listFailed, list_failed: true } : { stopped: 'the list stage returned nothing (a usage limit?)', usage_limit: LAUNCH_LIMIT.stopped })
insts = await takeLeases(insts)
let lastInsts = insts
// from here on every way out releases the run's leases (#96)
try {

// ---- Sweep (the Author's, before any ticket; counts against no cap) -------------------
phase('Sweep')
for (const i of insts.filter(i => i.role === 'author')) {
  // #129: the sweep (40 to 80 tool calls, usually 0 to 5 notes retired) runs only for a run that
  // takes one of this Author's tickets, and not at all with sweep: false (a cowork that runs the
  // inbox per ticket sweeps once, on its last call)
  if (A.sweep === false || !(i.rows || []).length) {
    notes.push(`${i.name}: no sweep (${A.sweep === false ? 'sweep: false' : 'no ticket of it to take in this run'})`)
    continue
  }
  const s = await launch(`Run the machine-note sweep of ${i.name} (home ${i.home}) as /author:sweep does, and report the counts per section.`,
    { label: `sweep ${i.name}`, phase: 'Sweep', agentType: 'author:note-sweeper' })
  if (s === null) return Object.assign(out, { stopped: `the sweep of ${i.name} was lost (a limit?): nothing further launched` })
  out.sweep = (out.sweep || []).concat([{ instance: i.name, report: s }])
}

// ---- one ticket -------------------------------------------------------------------------
async function relayForward(row, inst, r) {
  const final = row.final_to || r.final_default || ''
  const st = await move(row, inst, 'start: move it to in-progress (open -> accepted -> in-progress, or accepted -> in-progress); leave an in-progress ticket as it is')
  if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start: ' + (st ? st.detail || 'no reason given' : 'lost') }
  const rel = await launch(
    `WORKFLOW RELAY forward leg. Ticket ${row.id}, which you relay for ${inst}; it is in-progress. ` +
    `Decide per your agent definition: fail fast (return decision fail-fast with the reason and the ## Result text), ` +
    `or sharpen and forward: file ONE child with tickets_create to the ${r.to} instance only, kind ${r.kinds.join(' or ')}, ` +
    `parent ${row.id}, final_to ${final || '(none)'}, and return decision forward with its id. ` +
    `Make no status move on ${row.id} (the workflow concludes it). A tickets_create refusal: decision refused, with the refusal verbatim.`,
    { label: `${row.route.target} ${row.id}`, phase: 'Tickets', agentType: `${r.role}:${row.route.target}`, schema: RELAY_OUT })
  if (rel === null) return { lost: true }
  if (rel.decision === 'fail-fast') {
    const m = await move(row, inst, `deliver: deliver: true with result "${rel.result}" and result_detail:\n${rel.result_detail}`)
    return { outcome: m && m.ok ? 'delivered (failed fast)' : 'unfinished', detail: rel.result }
  }
  if (rel.decision === 'forward' && rel.child) {
    const c = await clerk('get', [`ticket: ${rel.child}`, 'tickets_get it and return its fields.'], TICKET, `get ${rel.child}`)
    const bad = []
    if (!c || !c.found) bad.push('the child does not exist')
    else {
      if (c.parent !== row.id) bad.push(`its parent is ${c.parent || 'none'}, not ${row.id}`)
      if (c.from !== inst) bad.push(`it was filed by ${c.from}, not ${inst}`)
      if (roleOf(c.to) !== r.to) bad.push(`it goes to ${c.to}, not a ${r.to} instance`)
      if (!r.kinds.includes(c.kind)) bad.push(`its kind is ${c.kind}, not ${r.kinds.join('/')}`)
      if ((c.final_to || '') !== final) bad.push(`its final_to is ${c.final_to || 'none'}, not ${final || 'none'}`)
    }
    if (bad.length) {
      const m = await move(row, inst, `block-human: blocked, waiting_on [human], reason "the relay's child ${rel.child} fails the chain check: ${bad.join('; ')}"`)
      notes.push(`${row.id}: relay child ${rel.child} refused by the check (${bad.join('; ')})`)
      return { outcome: 'blocked on human', detail: bad.join('; ') }
    }
    const m = await move(row, inst, `block-on: blocked, waiting_on [${rel.child}], reason "relayed to ${c.to} as ${rel.child}"`)
    return { outcome: m && m.ok ? `relayed as ${rel.child}` : 'unfinished', detail: rel.result, notes: rel.notes, child: rel.child, parked: !!(m && m.ok) }
  }
  const m = await move(row, inst, `block-human: blocked, waiting_on [human], reason "relay ${rel.decision}: ${rel.result}"`)
  return { outcome: 'blocked on human', detail: rel.result }
}

async function relayReturn(row, inst) {
  // mechanical: no relay agent. The child is closed by its sender (this instance), the
  // parent goes blocked -> in-progress -> delivered (blocked -> delivered is no transition)
  const m = await move(row, inst,
    'return-leg: tickets_get the ticket; its child is the id in waiting_on. tickets_get the child. If the child is delivered, ' +
    'move it closed (act as the child\'s from). Then move this ticket blocked -> in-progress -> delivered (deliver: true) with result ' +
    '"child <id> <its status>[; packets <ids>]"; a rejected or cancelled child is named as such.', `${row.id} return leg`)
  return { outcome: m && m.ok ? 'delivered (return leg)' : 'unfinished', detail: m ? m.detail : 'lost' }
}

async function expertClerk(row, inst) {
  const st = await move(row, inst, 'start: move it to in-progress')
  if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start' }
  let ans = await launch(`Answer ticket ${row.id} (tickets_get it): its ask, from the library and the registry. ` +
    `Begin your answer with ESCALATE if the library cannot answer it.`, { label: `clerk ${row.id}`, phase: 'Tickets', agentType: 'expert:clerk' })
  if (ans === null) return { lost: true }
  let used = 1
  if (/^\s*ESCALATE/.test(ans)) {
    used = 2
    ans = await launch(`Ticket ${row.id} escalated by the clerk: ${ans}\nAnswer it as the librarian (look-ups the clerk escalated).`,
      { label: `librarian ${row.id}`, phase: 'Tickets', agentType: 'expert:librarian' })
    if (ans === null) return { lost: true }
  }
  const first = String(ans).trim().split('\n')[0].slice(0, 200).replace(/"/g, "'")
  const m = await move(row, inst, `deliver: deliver: true with result "${first}" and result_detail = the full answer:\n${ans}`)
  return { outcome: m && m.ok ? 'delivered' : 'unfinished', detail: first, runs_used: used }
}

// #94 (2026-11-19, T-0181): the review's verdict is a structured field, never read from its
// prose. A review text that mentioned settings.json was neutralised by the harness, the old
// /^APPROVED/ check read the approval as findings, and the ticket went to the human three times.
// summary and findings are asked for, never required (#124); a missing verdict is no approval.
const TE_REVIEW = { type: 'object', properties: {
  verdict: { type: 'string', enum: ['approved', 'findings'], description: 'approved: no finding that needs a fix round; findings: at least one' },
  findings: { type: 'array', items: { type: 'string' }, description: 'one per finding: file and line, what goes wrong on which input, how bad' },
  summary: { type: 'string', description: 'what you examined, in one line' } },
  required: ['verdict'] }
function readReview(t) {
  const ok = t && typeof t === 'object' && (t.verdict === 'approved' || t.verdict === 'findings')
  const findings = ok && Array.isArray(t.findings) ? t.findings.map(String).filter(Boolean) : []
  const summary = ok && typeof t.summary === 'string' ? t.summary : ''
  // the thread keeps every finding, approved or not (#94 review): one shortened line each
  const short = f => { const x = f.replace(/\s+/g, ' ').replace(/"/g, "'").trim(); return x.length > 160 ? x.slice(0, 157) + '...' : x }
  const listed = findings.slice(0, 8).map((f, n) => `${n + 1}. ${short(f)}`).concat(findings.length > 8 ? [`(and ${findings.length - 8} more)`] : [])
  if (!ok) return { approved: false, verdict: false, line: 'no verdict (the review returned no structured verdict)', note: [], text: 'the review returned no verdict: no approval' }
  if (t.verdict === 'approved') return { approved: true, verdict: true, line: 'approved' + (findings.length ? `, with ${findings.length} minor finding(s)` : ''), note: listed, text: findings.join('\n') }
  const text = findings.length ? findings.map((f, n) => `${n + 1}. ${f}`).join('\n') : (summary || 'findings, none listed')
  return { approved: false, verdict: true, line: `findings: ${findings.length ? short(findings[0]) : short(summary || 'none listed')}`, note: findings.length > 1 ? listed : [], text }
}

async function developerReviewed(row, i) {
  // the producer of code never grades it: developer, then test-engineer on the diff, the
  // findings back through the thread, two rounds at most (the route's declared cost, costOf)
  const st = await move(row, i.name, 'start: move it to in-progress')
  if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start' }
  const runs = 4
  let used = 0, extra = 0, review = null
  // a review that throws (a run ended without its structured output, T-1614) is no verdict, never
  // the end of this inbox run; null (nothing came back: a limit?) stays a lost agent
  const askReview = async (prompt, label) => {
    try { return await launch(prompt, { label, phase: 'Tickets', agentType: 'scientist:test-engineer', schema: TE_REVIEW }) } catch (e) {
      notes.push(`${row.id}: the ${label} stage ended without its verdict (${String(e).slice(0, 120)})`)
      return { thrown: true }
    }
  }
  while (used + 2 <= runs) {
    const d = await launch(`WORKFLOW INBOX: code ticket ${row.id} for ${i.name} (home ${i.home}); it is in-progress, make no status move. ` +
      (review ? `The test-engineer's findings on your last diff (also in the thread):\n${review.text}\n` : '') +
      'Do it per your agent definition (test-first, in a worktree) and end with the diff\'s branch and commit.',
      { label: `developer ${row.id}${used ? ' (round ' + (used / 2 + 1) + ')' : ''}`, phase: 'Tickets', agentType: 'scientist:developer' })
    if (d === null) return { lost: true }
    const ask = `WORKFLOW INBOX: review the developer's diff for code ticket ${row.id} (${i.name}, home ${i.home}): ${String(d).slice(-600)}\n` +
      'Review it per your agent definition. Return verdict approved (no finding that needs a fix round) or findings, and each finding in findings.'
    let t = await askReview(ask, `test-engineer ${row.id}`)
    if (t === null) return { lost: true }
    review = readReview(t)
    if (!review.verdict) {
      // no verdict: the reviewer is asked once more before a developer round is spent on nothing
      extra++
      t = await askReview(ask + '\nYour last answer carried no verdict: return the structured answer (verdict approved or findings).', `test-engineer ${row.id} (again)`)
      if (t === null) return { lost: true }
      review = readReview(t)
    }
    used += 2
    const said = [review.line].concat(review.note).map(x => String(x).replace(/"/g, "'")).join('\n').slice(0, 1600)
    await move(row, i.name, `note: append to the thread "test-engineer: ${said}"`, `${row.id} review note`)
    if (review.approved) {
      const m = await move(row, i.name, `deliver: deliver: true with result "code delivered, test-engineer APPROVED: ${String(d).split('\n')[0].slice(0, 120).replace(/"/g, "'")}"`)
      return { outcome: m && m.ok ? 'delivered' : 'unfinished', detail: 'approved', runs_used: used + extra }
    }
  }
  await move(row, i.name, 'block-human: blocked, waiting_on [human], reason "two rounds of review still leave findings: decide how it goes on"')
  return { outcome: 'blocked on human (review)', detail: review ? review.line : '', runs_used: used + extra }
}

const firstRef = (row, re) => (row.refs || []).find(x => re.test(x)) || ''

// #89: a verify ticket reviews the claim its title names, never the first namespaced ref
// (often the parent). The claim refs are the namespaced ids of a registry statement (not
// file:, bib:, check:, or lab:, whose results are reviewed as experiments). In order: the
// claim ref the title names (with or without its namespace); else the one namespaced id the
// title names (a lone ref is often the parent: the title wins, T-1500); else the only claim
// ref; else '' (several, or none: back to the main session, never a guess).
const ID_CH = "[\\p{L}\\p{N}_:\\-′']"
const RE_QID = new RegExp(`^[a-z][a-z0-9]*:[\\p{L}]${ID_CH.replace(']', '.]')}*$`, 'u')
const NOT_CLAIM = /^(file|bib|check|lab|https?|doi|arxiv):/
const LABEL_NS = /^(lem|thm|defn?|cor|prop|fact|rmk|obs|ex|claim|conj|eq|sec|fig|tab):/
const escRe = x => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
// a whole id in the text: not inside a longer id (a '.' or ':' ends it unless a word follows)
const namesId = (text, id) => new RegExp(`(?<![\\p{L}\\p{N}_.:\\-′'])${escRe(id)}(?![\\p{L}\\p{N}_\\-′']|[.:][\\p{L}\\p{N}_])`, 'u').test(text || '')
function titleIds(title) {
  const out = []
  const re = new RegExp(`(?<![\\p{L}\\p{N}_.:\\-′'])([a-z][a-z0-9]*:\\p{L}[\\p{L}\\p{N}_.:\\-′']*)`, 'gu')
  for (const m of String(title || '').matchAll(re)) {
    const id = m[1].replace(/[.:]+$/, '')
    if (!NOT_CLAIM.test(id) && !LABEL_NS.test(id) && !out.includes(id)) out.push(id)
  }
  return out
}
function verifyClaim(row) {
  const ids = (row.refs || []).filter(x => RE_QID.test(x) && !NOT_CLAIM.test(x))
  const title = row.title || ''
  const inTitle = ids.filter(x => namesId(title, x) || namesId(title, x.slice(x.indexOf(':') + 1)))
  if (inTitle.length === 1) return { claim: inTitle[0] }
  if (inTitle.length > 1) return { claim: '', why: `the title names several refs (${inTitle.join(', ')})` }
  const named = titleIds(title)
  if (named.length === 1) return { claim: named[0], from_title: !ids.includes(named[0]) }
  if (named.length > 1) return { claim: '', why: `the title names several ids (${named.join(', ')}) and none is a ref` }
  if (ids.length === 1) return { claim: ids[0] }
  if (ids.length > 1) return { claim: '', why: `several claim refs (${ids.join(', ')}) and the title names none of them` }
  return { claim: '', why: 'neither its refs nor its title name a claim' }
}

// ---- the lead-researcher's proof work goes back to the main session (T-1271) -------------
// Inside this run an agent has no Agent or Workflow tool, so the lead cannot launch prover
// or /researcher:prove (live 2026-11-14/15: T-1257 blocked on the human, T-1264 left
// in-progress twice, nothing proved). It does what it can here (prior-art tickets, the
// prover brief in the journal; for a ticket that names no registry claim it registers the
// statement with claims_new first) and returns decision prove. No falsifier is needed before
// the hand-back (2026-11-20: prove.js attempts without one and a failed attempt or a GAP
// verdict triggers one). The script then checks, in this order:
//  * a falsifier the lead reports on record goes on the ticket's thread (prove.js's state
//    stage reads "the ticket says so", and the verify ask names it; a claim the lead just
//    registered is named by no report); none: no note, and the hand-back says so;
//  * the claim resolves (registry.py statement), then /researcher:prove goes to the main
//    session as for_main, with its args. The ticket stays in-progress: prove.js takes it and
//    delivers it. Every hand-back carries handback: 'lead-researcher' (workplan.js ends a
//    campaign's rounds on it: every later round would re-run the lead on the same ticket).
const CLAIM_ID = /^([a-z][a-z0-9]*:)?[A-Za-z][\w.:-]*$/             // prove.js's own check of args.claim
const TICKET_ID = /^T-\d+$/
const LEAD_OUT = { type: 'object', properties: {
  decision: { type: 'string', enum: ['delivered', 'blocked', 'prove'], description: 'what you did with the ticket: delivered it, blocked it (for a reason other than the missing prover), or left it in-progress for a proof attempt' },
  claim: { type: 'string', description: 'decision prove: the registry id (<ns>:<id>) prover is to attempt; else empty' },
  created: { type: 'boolean', description: 'decision prove: true when you registered the claim with claims_new in this run' },
  brief: { type: 'string', description: 'decision prove: where the prover brief is (journal file and heading); else empty' },
  falsifier: { type: 'string', description: 'decision prove: the falsifier on record for this statement (a delivered experiment or test ticket and its outcome, a report, a direction item; or that the pack has no computational handle on it); empty when none has run yet' },
  pending: { type: 'array', items: { type: 'string' }, description: 'decision prove: the ids of falsifier tickets still open (filed in an earlier run); the proof attempt does not wait for them; else empty' },
  report: { type: 'string', description: 'your report, status first' } },
  required: ['decision', 'claim', 'created', 'brief', 'falsifier', 'pending', 'report'] }
const REG = { type: 'object', properties: { exit: { type: 'number', description: 'the exit code as printed by the shell' },
  output: { type: 'string', description: 'the command output, verbatim' } }, required: ['exit'] }
const oneLine = (x, n) => String(x || '').replace(/\s+/g, ' ').trim().replace(/"/g, "'").slice(0, n || 200)

async function leadResearcher(row, i) {
  const inst = i.name
  const st = await move(row, inst, 'start: move it to in-progress')
  if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start: ' + (st ? st.detail || 'no reason given' : 'lost') }
  const r = await launch(
    `WORKFLOW INBOX: ticket ${row.id} for ${inst} (home ${i.home}); it is already in-progress, so make no move to accepted or in-progress. ` +
    'Work it per your agent definition (the claim is in refs, the agenda entry in agenda). ' + chosen(row) +
    `An earlier run may have worked this ticket already: first read the ticket's thread (tickets_get ${row.id}), the tickets filed for it (tickets_list parent ${row.id}) ` +
    'and the journal, and go on from there; never file a falsifier, lookup or cite ticket a second time. ' +
    'You run inside a workflow: the Agent and Workflow tools are not available here, so you cannot launch prover or run /researcher:prove, ' +
    'and you never block the ticket for that. When the item needs a proof attempt: ' +
    'make sure the statement to prove is a registry claim of this instance (if the ticket names none, register it first with claims_new, status open, ' +
    'the statement as the ticket asks it); a proof attempt does not wait for a falsifier (a failed attempt or a GAP verdict triggers one): ' +
    'report the falsifier on record if there is one (empty if none), name any open falsifier tickets in pending, and file no new one for the attempt; ' +
    `write the prover brief in today's journal (\`py ${ROOT}/researcher/scripts/notebook.py --home ${i.home} journal --create\`), make no status move on the ticket, ` +
    `and return decision prove with the claim id (<ns>:<id>), where the brief is, the falsifier on record (empty if none yet) and pending: ` +
    `the workflow hands /researcher:prove <claim> with ticket ${row.id} to the main session. ` +
    'Otherwise finish by delivering it (tickets_update deliver: true, result one line; decision delivered) or, if you cannot, ' +
    'blocked with waiting_on and the reason (decision blocked).',
    { label: `lead-researcher ${row.id}`, phase: 'Tickets', agentType: 'researcher:lead-researcher', schema: LEAD_OUT })
  if (r === null) return { lost: true }
  const report = String(r.report || '').split('\n')[0]
  if (r.decision !== 'prove') return { outcome: 'worked', detail: report }
  const claim = String(r.claim || '').trim()
  const falsifier = oneLine(r.falsifier)
  const pending = [...new Set((r.pending || []).map(x => String(x).trim()).filter(x => TICKET_ID.test(x)))]
  const base = { ticket: row.id, instance: inst, handback: 'lead-researcher', brief: r.brief || '', created: !!r.created }
  // 2026-11-20: no falsifier wait (prove.js attempts without one; a failed attempt or a GAP
  // verdict triggers one): one on record goes on the thread; none is said in the hand-back's why
  if (falsifier) {
    const nt = await move(row, inst, `note: append to the thread "falsifier on record for ${claim || 'the statement'} (lead-researcher): ${falsifier}"`, `${row.id} falsifier note`)
    if (!nt) return { lost: true }
  }
  Object.assign(base, { skill: 'researcher:prove', falsifier }, pending.length ? { pending } : {})
  const register = `register the statement first (claims_new in ${inst}), then run /researcher:prove <claim> with ticket ${row.id} from the main session`
  if (!CLAIM_ID.test(claim)) {
    notes.push(`ANOMALY: ${row.id}: the lead asked for a proof attempt but named no registry claim${claim ? ' (' + claim + ')' : ''}`)
    return { for_main: Object.assign(base, { why: `${row.id} needs a proof attempt and names no registry claim: ${register}` }) }
  }
  const reg = await clerk('claim', [`From ${i.home} run \`py ${ROOT}/academy/scripts/registry.py statement ${claim}\` once (python3 where there is no py). ` +
    'Return the exit code the shell printed and the output verbatim. Write nothing.'], REG, `claim ${claim}`)
  if (!reg) return { lost: true }                                     // budget.md rule 4: lost, not "missing"
  const output = String(reg.output || '')
  if (/does not resolve/.test(output)) {
    notes.push(`ANOMALY: ${row.id}: the lead's claim ${claim} does not resolve in the registry`)
    return { for_main: Object.assign(base, { claim, why: `${row.id} needs a proof attempt, but its claim ${claim} does not resolve in the registry: ${register}` }) }
  }
  if (reg.exit !== 0) {
    notes.push(`${row.id}: the registry check of ${claim} failed (exit ${reg.exit}): ${oneLine(output, 160)}`)
    return { for_main: Object.assign(base, { claim, why: `${row.id} needs a proof attempt on ${claim}, but the registry check failed (exit ${reg.exit}: ${oneLine(output, 120)}): ` +
      `run \`registry.py statement ${claim}\` from the main session; when it resolves, run /researcher:prove ${claim} with ticket ${row.id}; register it (claims_new) only if that reports it missing` }) }
  }
  return { for_main: Object.assign(base, { claim,
    why: `${row.id} needs a proof attempt on ${claim}${r.created ? ' (registered by the lead in this run)' : ''}, and prover cannot be launched inside the inbox run: ` +
      `run /researcher:prove ${claim} with ticket ${row.id} from the main session (the Workflow prove.js with args)` +
      (falsifier ? '' : '; no falsifier on record: the attempt goes ahead and a failed attempt or a GAP verdict triggers one'),
    args: { claim, ticket: row.id, home: i.home, instance: inst, root: ROOT } }) }
}

// #86: what the human chose on /academy:decide (the ticket's decision_choice), told to the
// agent that resumes the ticket so it does that and does not ask it again
function chosen(row) {
  return row.decision_choice ? `The human already decided this ticket on /academy:decide (its decision_choice): ${row.decision_choice}. Do that; do not ask the human again or block on the same choice. ` : ''
}

async function handle(row, i) {
  const inst = i.name, rt = row.route || {}
  const why = rt.why || 'no reason given'
  if (row.released) {
    const r = await move(row, inst, 'release: blocked -> accepted (everything it waited on is back)')
    if (!r || !r.ok) return { outcome: 'unfinished', detail: 'release failed' }
  }
  if (rt.how === 'reject' && !rt.why) {      // a terminal move needs its reason: without one the human decides (review of 0da42c3)
    return { for_main: { why: `${row.id}: the route says reject but gives no reason; reject it with one, or route it`, ticket: row.id, instance: inst } }
  }
  if (rt.how === 'reject') {
    await move(row, inst, `reject: rejected, with reason "${why}"`)
    return { outcome: 'rejected', detail: why }
  }
  if (rt.how === 'wait') {
    // #128: the argument is already asked (an open child the ticket did not wait on): park on it
    if (!/^T-\d{4,}$/.test(String(rt.target || ''))) return { for_main: { why: `${row.id}: the route says wait but names no ticket`, ticket: row.id, instance: inst } }
    const m = await move(row, inst, `block-on: blocked, waiting_on [${rt.target}], reason "${why}"`)
    return { outcome: m && m.ok ? `waiting on ${rt.target}` : 'unfinished', detail: why, parked: !!(m && m.ok) }
  }
  if (rt.how === 'human') {
    if (i.role === 'author' || i.role === 'scientist')
      return { for_main: { why: `the ${i.role} puts a ticket with no route to the human (AskUserQuestion)`, ticket: row.id, instance: inst } }
    await move(row, inst, `block-human: blocked, waiting_on [human], reason "${why}"`)
    return { outcome: 'blocked on human', detail: why }
  }
  if (rt.how === 'research') {
    // a self-ticket that needs an argument: math-writer (an author -> expert liaison) files the research ticket,
    // the script checks it (the Expert, kind research, final_to researcher, parent this ticket), and the clerk parks this one on it
    const st = await move(row, inst, 'start: move it to in-progress')
    if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start' }
    const f = await launch(`WORKFLOW INBOX: the self-ticket ${row.id} of ${inst} (home ${i.home}) asks for an argument nobody has delivered. Write no argument. ` +
      `File exactly one research ticket to the Expert instance (tickets_create: kind research, final_to researcher, parent ${row.id}, the ask restated with its statement and claim id, ` +
      `deliverable "A proof (or a refutation) of the statement, as a proof object with its status proposed; the ticket result names it.", agenda and refs as ${row.id}'s). Return its id, or the refusal.`,
      { label: `math-writer ${row.id} (research)`, phase: 'Tickets', agentType: 'author:math-writer', schema: { type: 'object', properties: { ticket: { type: 'string' }, refusal: { type: 'string' } }, required: ['ticket', 'refusal'] } })
    if (f === null) return { lost: true }
    if (!f.ticket) {
      await move(row, inst, `block-human: blocked, waiting_on [human], reason "the research ticket was refused: ${String(f.refusal).replace(/"/g, "'").slice(0, 160)}"`)
      return { outcome: 'blocked on human', detail: f.refusal }
    }
    const c = await clerk('get', [`ticket: ${f.ticket}`, 'tickets_get it and return its fields.'], TICKET, `get ${f.ticket}`)
    const bad = !c || !c.found || !/^expert@/.test(c.to) || c.kind !== 'research' || !/^researcher/.test(c.final_to || '') || c.parent !== row.id
    if (bad) notes.push(`ANOMALY: ${f.ticket} is not a research ticket to the Expert with final_to researcher and parent ${row.id}`)
    const m = await move(row, inst, `block-on: blocked, waiting_on [${f.ticket}], reason "the argument is asked of the Researcher as ${f.ticket}"`)
    return { outcome: m && m.ok ? `asked as ${f.ticket}` : 'unfinished', detail: f.ticket, child: f.ticket, parked: !!(m && m.ok) }
  }
  if (RELAYS[rt.target]) return row.return ? relayReturn(row, inst) : relayForward(row, inst, RELAYS[rt.target])
  if (i.role === 'expert' && rt.target === 'clerk') return expertClerk(row, inst)
  // the experimenter's route is the experiment skill: its header is approved by the human
  if (i.role === 'scientist' && rt.target === 'experimenter' && row.kind === 'question') {
    // answered from the lab's records and results: no new compute, no header
    const st = await move(row, inst, 'start: move it to in-progress')
    if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start' }
    const r = await launch(`WORKFLOW INBOX: question ticket ${row.id} for ${inst} (home ${i.home}); it is in-progress. Answer it from the lab's records and results only ` +
      '(no new compute, no script), then deliver it (tickets_update deliver: true, result one line).', { label: `experimenter ${row.id}`, phase: 'Tickets', agentType: 'scientist:experimenter' })
    return r === null ? { lost: true } : { outcome: 'answered', detail: String(r).split('\n')[0] }
  }
  if (i.role === 'scientist' && rt.target === 'experimenter') {
    // the experiment's design leg runs here; its header gate goes to the human (no body before approval)
    if (!NESTED_OK) return { for_main: { why: 'an experiment ticket: /scientist:experiment (design, then the header gate)', ticket: row.id, instance: inst, skill: 'scientist:experiment' } }
    const r = await workflow({ scriptPath: NESTED['scientist:experiment'] }, { models: await modelsMap(), nested: true, root: ROOT, mode: 'design', ticket: row.id, kind: row.kind })
    if (r && r.for_main) return { for_main: Object.assign({ skill: 'scientist:experiment', instance: inst }, r.for_main, { ticket: row.id }) }
    return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.argument || r.reason || '') : 'lost', nested: r }
  }
  if (i.role === 'scientist' && rt.target === 'developer') return developerReviewed(row, i)
  if (rt.how === 'skill' && NESTED[rt.target] && !NESTED_OK)
    return { for_main: { why: `the ${rt.target} workflow cannot nest inside this nested run`, ticket: row.id, instance: inst, skill: rt.target } }
  if (rt.how === 'skill' && NESTED[rt.target]) {
    if (rt.target === 'author:notes') {
      // a returned referee ticket: its packet (the ticket's packets field) is landed as tickets, then the ticket is closed by its sender
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { models: await modelsMap(), nested: true, home: i.home, instance: inst, root: ROOT, referee_ticket: row.id })
      if (r && r.outcome !== 'lost' && r.outcome !== 'not-started')
        await move(row, inst, `close: move it delivered -> closed (you are its sender), with a thread note "${(r.filed || []).length} ticket(s) filed from ${r.packet || 'the packet'}; ${(r.unfiled || []).length} unfiled"`, `${row.id} close`)
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.anomalies || []).concat(r.unfiled || []).join('; ') : 'lost', nested: r }
    }
    if (rt.target === 'expert:referee' || rt.target === 'expert:domain') {
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { models: await modelsMap(), nested: true, root: ROOT, ticket: row.id })
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.packet || r.reason || (r.anomalies || []).join('; ') || '') : 'lost', nested: r }
    }
    if (rt.target === 'expert:cite') {
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { models: await modelsMap(), nested: true, root: ROOT, ticket: row.id })
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? [r.key, r.pinpoint, r.verdict].filter(Boolean).join(', ') || (r.reason || '') : 'lost', nested: r,
        parked: !!(r && r.gate), gate: r && r.gate ? Object.assign({ skill: 'expert:cite' }, r.gate) : null }
    }
    if (rt.target === 'researcher:explore') {
      const direction = firstRef(row, /^([a-z][a-z0-9]*:)?DIR-\d+$/)
      const r = await workflow({ scriptPath: NESTED[rt.target] }, Object.assign({ models: await modelsMap(), nested: true, root: ROOT, ticket: row.id, home: i.home, instance: inst, n: 1 },
        direction ? { direction: direction.split(':').pop() } : {}))
      // explore's prove step comes back as for_main (#87, 2026-11-20): pass it on to the main
      // session with this ticket, as the prove route does; the ticket stays in-progress
      if (r && r.for_main) return { for_main: Object.assign({ instance: inst }, r.for_main, { ticket: row.id }) }
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.anomalies || []).concat(r.reason ? [r.reason] : []).join('; ') : 'lost', nested: r }
    }
    if (rt.target === 'researcher:generalize') {
      const ref = firstRef(row, /^P-\d{4,}$/) || firstRef(row, /^lab:\S+$/)
      if (!ref) return { for_main: { why: 'a generalize ticket whose refs name no report or lab claim', ticket: row.id, instance: inst } }
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { models: await modelsMap(), nested: true, root: ROOT, ref, ticket: row.id, home: i.home, instance: inst })
      if (r && r.to_file && r.to_file.length)
        return { for_main: { why: 'generalize: the falsifier tests are left to file (the lead could not file them)', ticket: row.id, instance: inst, to_file: r.to_file } }
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.reason || '') : 'lost', nested: r }
    }
    if (rt.target === 'researcher:prove') {
      const claim = firstRef(row, /^[a-z][a-z0-9]*:\S+$/) || firstRef(row, /^[A-Z][A-Z0-9]*-\S+$/)
      if (!claim) return { for_main: { why: 'a prove ticket whose refs name no claim', ticket: row.id, instance: inst } }
      const r = await workflow({ scriptPath: NESTED[rt.target] }, { models: await modelsMap(), nested: true, root: ROOT, claim, ticket: row.id, home: i.home, instance: inst })
      if (r && r.already_proved) return { for_main: { why: `${claim} is proved and the ticket was not read as a repair (#85): if it asks for one, run prove.js with these args (mode repair); else deliver or cancel ${row.id} (still in-progress)`,
        ticket: row.id, instance: inst, skill: 'researcher:prove', claim, mode: 'repair', handback: 'prove',
        args: { claim, ticket: row.id, home: i.home, instance: inst, root: ROOT, mode: 'repair' } } }
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.verify_ticket || r.reason || '') : 'lost', nested: r }
    }
    if (rt.target === 'expert:verify') {
      const vc = verifyClaim(row)
      if (!vc.claim) return { for_main: { why: `a verify ticket naming no single claim (#89): ${vc.why}; ask its sender (${row.from || 'the sender'}) to put the claim in refs`, ticket: row.id, instance: inst } }
      const claim = vc.claim
      if (vc.from_title) notes.push(`${row.id}: the claim ${claim} was read from the title (no claim in refs)`)
      // #85: a repair that reworded a reviewed statement files "Verify <claim> (reword of <pass>)"
      // (prove.js): reword mode over that base pass; any other title runs the blind pass
      const rw = /\(reword of (\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?)\)/.exec(row.title || '')
      // #127: the base may be a confirmed reword pass (its chain ends in a blind pair)
      const reword = rw ? { mode: 'reword', base_pass: rw[1] } : {}
      if (reword.mode) notes.push(`${row.id}: a reword verify over the base pass ${reword.base_pass} (from the title)`)
      const r = await workflow({ scriptPath: NESTED[rt.target] }, Object.assign({ models: await modelsMap(), nested: true, root: ROOT, claim, ticket: row.id }, reword))
      if (reword.mode && r && r.outcome === 'not-started') notes.push(`${row.id}: the reword pass over ${reword.base_pass} did not start (${r.reason || 'no reason given'}): ` +
        `a reword ticket whose base pass (a blind pass, or a reword pass chained to one) is not CONFIRMED x2 needs a blind verify instead (the same ticket without "(reword of ...)" in its title)`)
      return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.proposed_status || '') : 'lost', nested: r }
    }
    const subject = firstRef(row, /^lab:\S+$/)
    if (!subject) return { for_main: { why: 'a review-experiment ticket whose refs name no lab claim', ticket: row.id, instance: inst } }
    const r = await workflow({ scriptPath: NESTED[rt.target] }, { models: await modelsMap(), nested: true, root: ROOT, subject, ticket: row.id, report: firstRef(row, /^P-\d+$/), mode: 'review' })
    if (r && r.outcome === 'needs-settle') {
      // settle in the same handle (sequential, still one nesting level): the audit, then the candidates' re-derivations
      const slug = subject.replace(/[^A-Za-z0-9._-]+/g, '-')
      const st = await workflow({ scriptPath: NESTED[rt.target] }, { models: await modelsMap(), nested: true, root: ROOT, subject, ticket: row.id, report: firstRef(row, /^P-\d+$/), mode: 'settle-audit',
        candidates: `${i.home}/.academy/settle-${slug}.json` })
      return { outcome: st ? st.outcome : 'unfinished', detail: st ? (st.notes || []).join('; ') : 'lost', nested: st }
    }
    return { outcome: r ? r.outcome : 'unfinished', detail: r ? (r.notes || []).join('; ') : 'lost', nested: r }
  }
  if (rt.how === 'skill') return { for_main: { why: `the skill ${rt.target} runs in the main session` + (row.decision_choice ? ` (the human chose: ${row.decision_choice})` : ''), ticket: row.id, instance: inst, skill: rt.target } }
  if (rt.how === 'agent' && i.role === 'researcher' && rt.target === 'lead-researcher' && !row.return) return leadResearcher(row, i)
  if (rt.how === 'agent') {
    const type = `${i.role}:${rt.target}`
    if (row.return) {
      const r = await launch(`WORKFLOW INBOX: the ticket ${row.id} came back delivered to ${inst} (home ${i.home}). Land its result as your agent definition says, then close it (tickets_update status closed).`,
        { label: `${rt.target} ${row.id} (land)`, phase: 'Tickets', agentType: type })
      return r === null ? { lost: true } : { outcome: 'landed', detail: String(r).split('\n')[0] }
    }
    const st = await move(row, inst, 'start: move it to in-progress' + (i.role === 'author' ? '; also return in detail the output of the Author home\'s pinned.py (`py ' + ROOT + '/author/scripts/pinned.py --home ' + i.home + '`; the statements to leave byte for byte)' : ''))
    if (!st || !st.ok) return { outcome: 'blocked', detail: 'could not start: ' + (st ? st.detail || 'no reason given' : 'lost') }
    const work = `WORKFLOW INBOX: ticket ${row.id} for ${inst} (home ${i.home}); it is already in-progress, so make no move to accepted or in-progress. ` +
      `Work it per your agent definition (the claim is in refs, the agenda entry in agenda). ` + chosen(row) +
      (i.role === 'author' ? (st.detail ? `Pinned statements, to leave byte for byte: ${st.detail}\n` : `Pinned statements: the start stage returned none; run \`py ${ROOT}/author/scripts/pinned.py --home ${i.home}\` before editing and leave those byte for byte.\n`) +
        (taken.length ? `Earlier tickets of this run: ${JSON.stringify(taken.map(t => [t.id, t.outcome, t.detail]))}\n` : '') : '') +
      `Finish by delivering it (tickets_update deliver: true, result one line) or, if you cannot, blocked with waiting_on and the reason.`
    let r = await launch(work, { label: `${rt.target} ${row.id}`, phase: 'Tickets', agentType: type })
    // #129: an empty result (not null: the agent ran) is a run stopped mid-ticket, most likely at
    // its turn limit (T-1972, T-1984); one continuation run picks up its partial edits, as the
    // main session did by hand, and a second empty one is reported as such, not as "worked"
    const empty = x => x !== null && !String(x).trim()
    if (empty(r)) {
      notes.push(`${row.id}: ${type} stopped without a report (most likely its turn limit, #129): relaunched once to finish from its partial edits`)
      r = await launch(`WORKFLOW INBOX, continuation (#129): an earlier ${type} run on ${row.id} stopped without a report, most likely at its turn limit, ` +
        `and may have left partial edits in the home's working tree (git status and git diff in ${i.home}; the ticket thread). Read them first, ` +
        `keep what is done, do not redo it, and finish the ticket.\n` + work,
      { label: `${rt.target} ${row.id} (continue)`, phase: 'Tickets', agentType: type })
      if (empty(r)) {
        return { outcome: 'unfinished', turn_limit: true,
          detail: `${type} stopped twice without a report (most likely its turn limit, #129); partial edits, if any, are in ${i.home}'s working tree` }
      }
    }
    return r === null ? { lost: true } : { outcome: 'worked', detail: String(r).split('\n')[0] }
  }
  return { for_main: { why: `no workflow route for ${rt.how}:${rt.target}`, ticket: row.id, instance: inst } }
}

// ---- Tickets: serial, under one cap over the whole run ----------------------------------
phase('Tickets')
let count = 0
const closed = new Set()
const stuck = new Set()              // tickets this run left unfinished: not taken again this run
const unfinishedBy = new Map()       // instance -> how many it left unfinished
const gated = new Set()              // loop: tickets set aside for the human, never retried this run
const touched = new Set()            // instances whose tickets ran (the Author's close-out)
outer:
for (let pass = 1; pass <= MAX_PASSES; pass++) {
  if (pass > 1) {
    insts = await listAll(pass)
    // #114: a later listing that returns nothing (the weekly limit, 2026-11-20) ends the
    // run; the close-out reads the last listing, never a null one
    if (!insts) { if (listFailed) { out.stopped = listFailed; out.list_failed = true } else out.stopped = 'the list stage of pass ' + pass + ' returned nothing (a usage limit?)'; break }
    lastInsts = insts
  }
  out.passes = pass
  let moved = 0
  for (const i of insts) {
    for (const row of i.rows) {
      if (count >= CAP) break outer
      if (closed.has(i.name)) break
      if (gated.has(row.id) || stuck.has(row.id) || taken.some(t => t.id === row.id)) continue
      if (deferred.some(d => d.ticket === row.id)) continue
      const need = costOf(row, i)
      if (need > BIG && !APPROVED.has(row.id)) {
        // an expensive ticket is the human's to start, once; it holds nothing else back
        gated.add(row.id)
        out.gates.push({ ticket: row.id, instance: i.name, why: `it costs about ${need} agent runs (more than ${BIG}): start it with approve: ["${row.id}"]` })
        if (!LOOP && !out.for_main) out.for_main = { why: `${row.id} costs about ${need} agent runs: approve it or leave it`, ticket: row.id, instance: i.name }
        continue
      }
      if (typeof budget !== 'undefined' && budget.total && budget.remaining() < 30000) { out.stopped = 'the token budget is spent: nothing further launched'; break outer }
      if (spent + need > RUN_BUDGET) {
        deferred.push({ ticket: row.id, instance: i.name, needs: need, left: RUN_BUDGET - spent })
        notes.push(`${row.id} waits for the next run: its route costs ${need} agent run(s), ${RUN_BUDGET - spent} left of ${RUN_BUDGET}`)
        continue
      }
      spent += need
      // a route that is clerk moves only (cost 0) writes no file: no snapshot for it
      const snapped = SNAPSHOT && need > 0 && !LAUNCH_LIMIT.stopped ? await snapshot(row) : false
      const res = await handle(row, i)
      if (LAUNCH_LIMIT.stopped) {         // #115: a limit, whatever this ticket's stages made of it
        taken.push({ instance: i.name, id: row.id, route: row.route, outcome: 'stopped (usage limit?)' })
        out.stopped = `${row.id}: ` + LIMIT_WHY
        break outer
      }
      if (typeof res.runs_used === 'number') spent += res.runs_used - need      // what it really took
      if (res.for_main) {
        if (!LOOP) { out.for_main = res.for_main; notes.push(`stopped for the main session at ${row.id}: ${res.for_main.why}`); break outer }
        gated.add(row.id)
        out.gates.push(Object.assign({ ticket: row.id, instance: i.name }, res.for_main))
        continue
      }
      count++
      moved++
      touched.add(i.name)
      followed.add(row.id)
      if (res.child) children.add(res.child)
      if (res.nested && res.nested.child) children.add(res.nested.child)
      if (res.lost) {
        taken.push({ instance: i.name, id: row.id, route: row.route, outcome: 'lost' })
        out.stopped = `an agent on ${row.id} returned nothing (a limit or an API error): nothing further launched (budget.md rule 4)`
        if (LAUNCH_LIMIT.stopped) { out.stopped = `${row.id}: ` + LIMIT_WHY; break outer }
        await move(row, i.name, 'note: append to the thread "interrupted: the workflow agent returned nothing; what was recorded is above"', `${row.id} interrupted`)
        // #101: what the lost ticket wrote is still its manifest: --check commits it as WIP
        if (snapped && !LAUNCH_LIMIT.stopped) {
          const lc = readCheck(await tryClerk('check', checkCmd(row, i), CHECK, `check ${row.id}`), row.id)
          if (!lc || !lc.shipped) notes.push(`${row.id}: its work was not committed as WIP (see the check's output); commit by hand`)
        }
        break outer
      }
      const chk = readCheck(await clerk('check', checkCmd(row, i), CHECK, `check ${row.id}`), row.id)
      if (LAUNCH_LIMIT.stopped) { out.stopped = `${row.id} (its check): ` + LIMIT_WHY; break outer }
      if (chk && !chk.shipped) notes.push(`${row.id}: the checkpoint did not ship everything (see its output); commit by hand`)
      // a ticket that ends blocked is parked (on its child, on the human, on a dead route): --check's exit 3 is
      // then its expected end, not unfinished work (live run 2026-10-31 closed the Expert on it)
      const parkedOk = chk && chk.exit === 3 && chk.status === 'blocked'
      const unfinished = !chk || (chk.exit === 3 && !parkedOk)
      let outcome = unfinished ? 'unfinished' : res.outcome
      if (unfinished) {
        stuck.add(row.id)
        const n = (unfinishedBy.get(i.name) || 0) + 1
        unfinishedBy.set(i.name, n)
        if (row.status === 'in-progress' && chk && chk.status === 'in-progress') {
          // it was in progress before this run and still is: a second run will not finish it either
          const why = String(res.detail || 'no result recorded').replace(/\s+/g, ' ').slice(0, 200)
          const m = await move(row, i.name, `block: it was in-progress before this run and is still unfinished after it. Move it to blocked with waiting_on ["human"] and the thread line "unfinished after two inbox runs (${why}): decide how it goes on"`, `${row.id} park`)
          if (m && m.ok) { outcome = 'parked on the human'; notes.push(`${row.id} was in-progress before the run and is still unfinished: parked on the human (/academy:decide)`) }
          else notes.push(`${row.id} is unfinished for the second run and could not be parked: ${m ? m.detail || 'no reason given' : 'the move returned nothing'}`)
        } else {
          notes.push(`${row.id} is unfinished: it is left as it is and not taken again this run`)
        }
        if (n >= 2) { closed.add(i.name); notes.push(`${i.name} left ${n} tickets unfinished: nothing more from it this run`) }
      }
      taken.push({ instance: i.name, id: row.id, route: row.route, outcome, status: chk ? chk.status : '', detail: res.detail || '' })
      if (res.gate) out.gates.push(Object.assign({ ticket: row.id, instance: i.name }, res.gate))   // done, but it waits on the human
    }
  }
  if (!moved) break                  // quiet: nothing in this pass could move without the human
  if (count >= CAP) break            // the cap is spent: no further listing
}
out.budget = { runs: RUN_BUDGET, spent, deferred }
if (LOOP && out.gates.length && !out.for_main)
  out.for_main = { why: `${out.gates.length} ticket(s) wait on the human: ask them in one batch, then run the loop again`, gates: out.gates }

// ---- Close: the Author's delivered self-tickets ------------------------------------------
phase('Close')
insts = insts || lastInsts || []
if (LAUNCH_LIMIT.stopped) { out.usage_limit = true; if (!/usage limit/.test(out.stopped || '')) out.stopped = (out.stopped ? out.stopped + '; then: ' : '') + LIMIT_WHY }
for (const i of insts.filter(i => i.role === 'author' && touched.has(i.name) && !LAUNCH_LIMIT.stopped)) {
  await clerk('close-self', [`act as: ${i.name}`, 'Close (delivered -> closed) every delivered ticket whose from and to are both this instance; return how many.'], MOVE, `close ${i.name}`)
}
out.count = count
out.cap = CAP
if (insts.some(i => i.role === 'author') && taken.some(t => roleOf(t.instance) === 'author'))
  notes.push('Author: run check_paper.py (`py ' + ROOT + '/author/scripts/check_paper.py --root <home>`) from the home and relay its summary; launch tex-engineer once if an agent reported the build not clean')
return out
} finally {
  await releaseLeases()
}
} finally { await pinEnd() }
