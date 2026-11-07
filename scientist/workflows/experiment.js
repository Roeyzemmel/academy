export const meta = {
  name: 'academy-experiment',
  description: 'One computational experiment, from a claim to a filed report, one leg per mode: design (the header, then the human approves), build (test-first, the strict check, then the human commits), queue, report (the draft checked and rendered, then the human looks), file',
  whenToUse: '/scientist:experiment and every experiment / test / question ticket of the lab (design is also nested from the inbox), from the lab home. args: {mode: "design"|"build"|"queue"|"report"|"file", claim?, ticket?, kind?, stem?, header?, commit_ok?, job?, env?}',
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
const MODES = ['design', 'build', 'queue', 'report', 'file']
if (!MODES.includes(A.mode)) throw new Error('args.mode must be one of ' + MODES.join(', '))
const CLERK = 'academy:inbox-clerk'
const EXP = 'scientist:experimenter'
const T = A.ticket || ''
const clerk = (stage, lines, schema, label) => agent(`WORKFLOW STAGE ${stage} of the academy-experiment workflow (mode ${A.mode}). Run from the lab home (lab.py home names it).\n` + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase: 'Leg', agentType: CLERK, schema, effort: 'low' })

const HOME = { type: 'object', properties: { ok: { type: 'boolean' }, instance: { type: 'string' }, home: { type: 'string' }, run_profile: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'instance', 'home', 'run_profile', 'detail'] }
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
const QUEUED = { type: 'object', properties: { ok: { type: 'boolean' }, job: { type: 'string' }, command: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'job', 'command', 'detail'] }
const DRAFT = { type: 'object', properties: { report: { type: 'string' }, result_line: { type: 'string' } }, required: ['report', 'result_line'] }
const RENDER = { type: 'object', properties: { ok: { type: 'boolean' }, rendered: { type: 'string', description: 'the rendered packet text' }, errors: { type: 'array', items: { type: 'string' } } }, required: ['ok', 'rendered', 'errors'] }
const FILED = { type: 'object', properties: { packet: { type: 'string' }, review_ticket: { type: 'string' }, researcher: { type: 'string' }, why: { type: 'string' }, error: { type: 'string' } }, required: ['packet', 'review_ticket', 'researcher', 'why', 'error'] }
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok', 'detail'] }

const out = { mode: A.mode, ticket: T || null, notes: [] }
const gate = (why, extra) => Object.assign(out, { for_main: Object.assign({ gate: true, why, ticket: T || null }, extra || {}) })
phase('Leg')

if (A.mode === 'design') {
  const h = await clerk('lab-home', [T ? `First take ${T} (open -> accepted -> in-progress, acting as its receiver).` : '', 'Run lab.py home and return the lab instance, its home and the policy.run profile.'], HOME, 'lab home')
  if (!h || !h.ok) return Object.assign(out, { outcome: 'not-started', reason: h ? h.detail : 'lab.py home returned nothing' })
  const d = await agent(`Design one experiment in the lab ${h.home} for ${A.claim || 'the ticket ' + T}${A.kind ? ' (kind ' + A.kind + ')' : ''}. Read the statement from its owner, the pack's examples.md, traps.md and ` +
    'computation/ through domain_get, the nearest existing script and the lab\'s package. First classify the path: a two-line argument that settles it more cheaply than code (give it, ' +
    'and stop), a probe (feasibility, not evidence: header Kind: probe, Goal:, Decides:), or an experiment. For a probe or an experiment return the HEADER ONLY (no body, no code), ' +
    'the answer to "if the claim were false, what would this experiment still report?", and the library calls not yet confirmed in the pack.',
    { label: 'design', phase: 'Leg', agentType: EXP, schema: DESIGN })
  if (d === null) return Object.assign(out, { outcome: 'lost', reason: 'the experimenter returned nothing' })
  Object.assign(out, { path: d.path, stem: d.stem, header: d.header, if_false: d.if_false })
  if (d.path === 'argument') return Object.assign(out, { outcome: 'argument', argument: d.argument, notes: ['a two-line argument settles it: no script (a better result)'] })
  if ((d.api_unfamiliar || []).length) out.notes.push('unfamiliar library calls: run /scientist:api-check on ' + d.api_unfamiliar.join(', ') + ' before build')
  phase('Gate')
  return gate('approve the header (approve / change / drop) before any compute; ask also: ' + d.if_false, { header: d.header, stem: d.stem, next: { mode: 'build', stem: d.stem, ticket: T } })
}

if (A.mode === 'build') {
  if (!A.header || !A.stem) throw new Error('build needs args.header (the approved text) and args.stem')
  let b = await agent(`Build the experiment ${A.stem} from this APPROVED header (do not change it):\n${A.header}\n` +
    'Package code test-first, the script from the lab\'s template with validate() before run(), the lab claim created (claims_new, status open). Queue nothing, commit nothing.',
    { label: 'build', phase: 'Leg', agentType: EXP, schema: BUILT })
  if (b === null) return Object.assign(out, { outcome: 'lost', reason: 'the experimenter returned nothing' })
  let c = await clerk('check', [`Run lab.py cmd check experiments/${A.stem}.py --strict (run the command it prints) and return ok and the error lines.`], CHECK, 'check')
  if (c && !c.ok) {
    out.notes.push('the strict check failed; one fix round: ' + c.errors.join('; '))
    b = await agent(`The strict check of experiments/${A.stem}.py fails:\n- ${c.errors.join('\n- ')}\nFix the script (the header stays as approved).`, { label: 'build (fix)', phase: 'Leg', agentType: EXP, schema: BUILT }) || b
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
  if (!q || !q.ok) return Object.assign(out, { outcome: 'not-queued', reason: q ? q.detail : 'no answer' })
  return Object.assign(out, { outcome: 'queued', job: q.job, command: q.command, notes: ['watch it with /scientist:queue'] })
}

if (A.mode === 'report') {
  if (!A.stem) throw new Error('report needs args.stem')
  const opts = (A.env ? ` --env ${A.env}` : '') + (A.job ? ` --job ${A.job}` : '')
  let dr = await agent(`The result of experiments/${A.stem}.py is back${A.job ? ' (job ' + A.job + ')' : ''}. Fill the header's Result: ("no counterexample below bound B over class C", never "true"), ` +
    `and write the report draft reports/${A.stem}.md with ## Conclusion (Establishes: supports / refutes / inconclusive, Does not establish:, Proposed status:, Next step:) and ## Validation ` +
    '(Reproduced: yes|no). A surprising result is a bug until shown otherwise: say what you checked.', { label: 'report draft', phase: 'Leg', agentType: EXP, schema: DRAFT })
  if (dr === null) return Object.assign(out, { outcome: 'lost', reason: 'the experimenter returned nothing' })
  let c = await clerk('report-check', [`Run report.py check experiments/${A.stem}.py${opts}; return ok and every refusal line.`], CHECK, 'report check')
  if (c && !c.ok) {
    out.notes.push('report.py check refused; one fix round: ' + c.errors.join('; '))
    dr = await agent(`report.py check refuses experiments/${A.stem}.py:\n- ${c.errors.join('\n- ')}\nFix the header or the draft (never a hand-written packet).`, { label: 'report draft (fix)', phase: 'Leg', agentType: EXP, schema: DRAFT }) || dr
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
if (!f || !f.packet) return Object.assign(out, { outcome: 'not-filed', reason: f ? f.error : 'no answer' })
if (T) {
  const m = await clerk('close', [`Deliver ${T} (tickets_update deliver: true, acting as its receiver) with result "report ${f.packet}; review ticket ${f.review_ticket} to ${f.researcher}" and fields.packets [${f.packet}].`], MOVE, 'deliver')
  out.ticket_delivered = !!(m && m.ok)
}
return Object.assign(out, { outcome: 'filed', packet: f.packet, review_ticket: f.review_ticket, researcher: f.researcher, why: f.why })
