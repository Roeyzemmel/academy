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
const CLERK = 'academy:inbox-clerk'
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const T = A.ticket || ''
const clerk = (stage, lines, schema, label, phase) => agent(`WORKFLOW STAGE ${stage} of the academy-referee workflow.\n` + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const START = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' }, instance: { type: 'string', description: 'the Author instance to referee' }, acted_as: { type: 'string' } }, required: ['ok', 'detail', 'instance', 'acted_as'] }
const PDF = { type: 'object', properties: {
  ok: { type: 'boolean' }, stop_reason: { type: 'string', description: 'why there is no fresh PDF (the build lock stayed, the build failed)' },
  pdf: { type: 'string', description: 'absolute path' }, built: { type: 'string', description: 'YYYY-MM-DD of the PDF' }, rebuilt: { type: 'boolean' },
  vision: { type: 'string', description: 'absolute path of <Author home>/Drafts/vision.md, or empty when there is none' },
  last_report: { type: 'string', description: 'the newest reviews/referee/<instance>/<date>.md in the library, or empty' },
  last_date: { type: 'string' }, changed_since: { type: 'string', description: 'one line: the section files changed in the Author home since last_date (git log), or empty' } },
  required: ['ok', 'stop_reason', 'pdf', 'built', 'rebuilt', 'vision', 'last_report', 'last_date', 'changed_since'] }
const FOUND = { type: 'object', properties: { packet: { type: 'string' }, blocking: { type: 'number' }, copy: { type: 'string' } }, required: ['packet', 'blocking', 'copy'] }
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, status: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'status', 'detail'] }

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
  const r = await agent(`WORKFLOW STAGE ship. Run \`${check} 2>&1\` once, from the home` + (ROOT ? '' : ' (<academy repo> is academy.root of the MCP tool workspace_get)') +
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
  if (MODEL_ALIAS.test(String(given || ''))) m = given
  else {
    if (given) s.notes.push(`args.models gave ${JSON.stringify(given)} for ${name}, which is no launch alias: resolved here`)
    const r = await agent(`WORKFLOW STAGE model. Run \`py ${AR}/academy/scripts/models.py agent ${name} --launch\` once, from the home` +
      (ROOT ? '' : ' (<academy repo> is academy.root of the MCP tool workspace_get)') +
      '. Fix nothing, whatever it prints: return its whole output verbatim.', { label: 'model ' + name, phase: s.phase, agentType: s.agentType, schema: MODEL_OUT, effort: 'low' })
    const w = String(r ? r.output : '').trim()
    if (MODEL_ALIAS.test(w)) m = w
    else s.notes.push(`the launch model of ${name} was not resolved (${r ? JSON.stringify(w.slice(0, 160)) : 'the model stage returned nothing'}): it runs on its agent file's model`)
  }
  LAUNCH_MODELS[name] = m
  return m
}
async function launchMax(prompt, opts, s) {   // agent(prompt, opts) on the launch model of opts.agentType
  const model = await launchModel(opts.agentType, s)
  const r = await agent(prompt, model ? Object.assign({}, opts, { model }) : opts)
  if (r !== null || !model || model === FALLBACK_MODEL) return r
  MODEL_FALLBACKS.push(`${opts.label}: ${model} -> ${FALLBACK_MODEL}`)
  s.notes.push(`${opts.label}: the ${model} run returned nothing (a usage limit?); relaunched once on ${FALLBACK_MODEL} (a fallback-model run)`)
  // the lost run may have done part of its work: a stage that files or writes is not idempotent
  return agent('A previous run of this stage was cut off: check what it already did (files written, tickets filed) before doing it again.\n' + prompt,
    Object.assign({}, opts, { label: `${opts.label} (${FALLBACK_MODEL} fallback)`, model: FALLBACK_MODEL }))
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
  if (!s || !s.ok) return Object.assign(out, { outcome: 'not-started', reason: s ? s.detail : 'the start stage returned nothing' })
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
if (!pdf || !pdf.ok) return Object.assign(out, { outcome: 'not-started', reason: pdf ? pdf.stop_reason : 'the pdf stage returned nothing' })
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
