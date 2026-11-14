export const meta = {
  name: 'maintainer-round',
  description: 'A maintenance round on the academy\'s own code: survey by measurement, plan disjoint tasks, each task developed, reviewed and gated on its own branch (independent tasks side by side), then the branches gated together',
  whenToUse: '/maintainer:round --workflow (the human asked for a round on the plugins: errors from the ledger, slow or large commands, defects). args: {root: "<academy repo>", workspace: "<workspace root>", base: "<branch the round starts from>", cap?: 4, days?: 7, role?: "human", tasks?: [{slug, title, kind, files: [paths], measure, why}]}',
  phases: [
    { title: 'Survey', detail: 'maintain.py survey: ledger families, commands over budget, unreadable definitions' },
    { title: 'Plan', detail: 'at most cap tasks; tasks that touch the same files share a lane' },
    { title: 'Work', detail: 'per task: develop in its own worktree, independent review, one fix round, push through the gate' },
    { title: 'Union', detail: 'maintain.py union: the lanes merged in a throwaway worktree and gated together' },
  ],
}

// The round of 2026-11-13 (docs/error-ledger-review-2026-11-13.md) in code. What it fixes:
// a round starts from what was measured (the survey), never from a hunch; a task is one
// concern on one branch in its own worktree, so tasks that share no file run side by side
// and their push gates too; the one who wrote a change never reviews it; a blocking finding
// gets one fix round and one second look, then the task is reported, not pushed; and the
// side-by-side branches are gated together before anyone is told the round is done.
// The script pushes branches and opens nothing: the pull requests it returns are the
// session's to open, bottom of each lane first, and merging stays the human's.

const A = args || {}
const bad = (reason) => ({ ok: false, reason, tasks: [], pull_requests: [] })
if (!A.root || !A.workspace || !A.base) return bad('args.root (the academy repo), args.workspace (the workspace root) and args.base (the branch the round starts from) are required')
const AR = A.root.replace(/[\\/]+$/, '')
const WS = A.workspace.replace(/[\\/]+$/, '')
const CAP = Math.max(1, Math.min(8, A.cap || 4))
const DAYS = A.days || 7
const ROLE = A.role || 'human'
const SUB = A.sub || 'academy'
const DEV = 'scientist:developer'
const REVIEWER = 'scientist:test-engineer'
const RE_SLUG = /^[a-z0-9][a-z0-9-]{2,40}$/
const SCRIPTS = `Scripts: maintain.py is \`py ${AR}/maintainer/scripts/maintain.py\`; ship.py is \`py scripts/ship.py\` run from the workspace root ${WS} (the shim of ${AR}/academy/scripts/ship.py); the suites are \`py -m unittest discover -s <plugin>/tests -t <plugin>/tests\` from the checkout you work in (python3 where there is no py).\n`
const STAGE = (name, lines) => `WORKFLOW STAGE ${name} of the maintainer-round workflow. Repo: ${SUB} (${AR}). Base branch: ${A.base}.\n` + SCRIPTS + lines.filter(Boolean).join('\n')

const CANDIDATE = { type: 'object', properties: { kind: { type: 'string' }, id: { type: 'string' }, title: { type: 'string' }, evidence: { type: 'string' } }, required: ['kind', 'id', 'title', 'evidence'] }
const SURVEY = { type: 'object', properties: { ok: { type: 'boolean' }, error: { type: 'string' }, candidates: { type: 'array', items: CANDIDATE }, notes: { type: 'array', items: { type: 'string' } } }, required: ['ok', 'error', 'candidates', 'notes'] }
const TASK = {
  type: 'object',
  properties: {
    slug: { type: 'string', description: 'the branch topic: lower case, digits and hyphens' },
    title: { type: 'string' }, kind: { type: 'string', enum: ['error', 'slow', 'large', 'definition', 'defect', 'feature', 'hygiene'] },
    candidates: { type: 'array', items: { type: 'string' }, description: 'the survey ids this task answers' },
    files: { type: 'array', items: { type: 'string' }, description: 'repo-relative files or folders the change will touch' },
    measure: { type: 'string', description: 'the command or case that shows the problem now and will show it gone' },
    why: { type: 'string' },
  },
  required: ['slug', 'title', 'kind', 'files', 'measure', 'why'],
}
const PLAN = { type: 'object', properties: { tasks: { type: 'array', items: TASK }, skipped: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, reason: { type: 'string' } }, required: ['id', 'reason'] } } }, required: ['tasks', 'skipped'] }
const DONE = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' }, reason: { type: 'string', description: 'when not ok: what stopped it' },
    branch: { type: 'string' }, worktree: { type: 'string' }, sha: { type: 'string' },
    before: { type: 'string', description: 'the measure before the change' }, after: { type: 'string' },
    tests: { type: 'string', description: 'the suites run and their result lines' },
    files: { type: 'array', items: { type: 'string' } }, summary: { type: 'string' },
  },
  required: ['ok', 'reason', 'branch', 'worktree', 'sha', 'before', 'after', 'tests', 'files', 'summary'],
}
const FINDING = { type: 'object', properties: { severity: { type: 'string', enum: ['blocking', 'minor'] }, file: { type: 'string' }, line: { type: 'number' }, what: { type: 'string' }, trigger: { type: 'string' } }, required: ['severity', 'file', 'what', 'trigger'] }
const REVIEW = { type: 'object', properties: { examined: { type: 'string' }, findings: { type: 'array', items: FINDING } }, required: ['examined', 'findings'] }
const PUSHED = { type: 'object', properties: { ok: { type: 'boolean' }, sha: { type: 'string' }, detail: { type: 'string', description: 'the last lines of the push, the refusal included' } }, required: ['ok', 'sha', 'detail'] }
const UNION = { type: 'object', properties: { ok: { type: 'boolean' }, merged: { type: 'array', items: { type: 'string' } }, conflict: { type: 'string' }, gate: { type: 'array', items: { type: 'string' } } }, required: ['ok', 'merged', 'conflict', 'gate'] }

const out = { ok: false, base: A.base, tasks: [], lanes: [], skipped: [], dropped: [], pull_requests: [], cleanup: [] }

// ---- Survey ---------------------------------------------------------------------------
let tasks = Array.isArray(A.tasks) ? A.tasks : null
if (!tasks) {
  phase('Survey')
  const s = await agent(STAGE('survey', [
    `Run maintain.py survey --days ${DAYS} --json from ${WS} and return its candidates and notes exactly as printed (ok false with the error line if it fails). Change nothing.`,
  ]), { label: 'survey', phase: 'Survey', agentType: DEV, schema: SURVEY, effort: 'low' })
  if (!s || !s.ok) return Object.assign(out, { reason: 'the survey did not run: ' + (s ? s.error : 'the stage returned nothing') })
  out.candidates = s.candidates.length
  out.notes = s.notes
  if (!s.candidates.length) return Object.assign(out, { ok: true, reason: 'the survey found no candidate: nothing to do' })

  // ---- Plan -----------------------------------------------------------------------------
  phase('Plan')
  const p = await agent(STAGE('plan', [
    `Turn these survey candidates into at most ${CAP} tasks for this repo, the most valuable first. One task is one concern: one cause, one fix, one branch.`,
    'Read the code before you name a task: a task says which files it will change (files) and how the problem is shown now and shown gone (measure: a command with a number, or a failing case).',
    'Skip, with the reason, every candidate whose cause is not in this repo (a home\'s own text, the network, the harness, a decision that is the human\'s) or that is already fixed on the base branch (an error recorded by an older checkout). Several candidates with one cause are one task.',
    'Candidates: ' + JSON.stringify(s.candidates),
    'Write nothing and start no branch.',
  ]), { label: 'plan', phase: 'Plan', agentType: DEV, schema: PLAN, effort: 'high' })
  if (!p) return Object.assign(out, { reason: 'the plan stage returned nothing' })
  tasks = p.tasks
  out.skipped = p.skipped
}

// the plan's own rules, in code: a usable slug, once; something to change; a measure
const seen = new Set(), kept = []
for (const t of tasks) {
  if (!t || !RE_SLUG.test(t.slug || '')) { out.dropped.push(`${t && t.slug}: not a usable branch topic`); continue }
  if (seen.has(t.slug)) { out.dropped.push(`${t.slug}: named twice`); continue }
  if (!Array.isArray(t.files) || !t.files.length) { out.dropped.push(`${t.slug}: names no file to change`); continue }
  if (!t.measure) { out.dropped.push(`${t.slug}: no measure, so nothing would show it done`); continue }
  seen.add(t.slug)
  kept.push(t)
}
for (const t of kept.slice(CAP)) out.dropped.push(`${t.slug}: over the cap of ${CAP} (run another round)`)
tasks = kept.slice(0, CAP)
for (const d of out.dropped) log('dropped: ' + d)
if (!tasks.length) return Object.assign(out, { ok: !out.dropped.length, reason: 'no task to work on' })

// lanes: two tasks that touch the same file or folder cannot run side by side; they share
// a lane and are stacked in plan order. Tasks in different lanes share nothing.
const norm = (f) => String(f).replace(/\\/g, '/').replace(/^\.\//, '').replace(/\/+$/, '')
const touches = (a, b) => a.files.some(x => b.files.some(y => { const p = norm(x), q = norm(y); return p === q || p.startsWith(q + '/') || q.startsWith(p + '/') }))
const laneOf = new Map()
tasks.forEach((t, i) => laneOf.set(t.slug, i))
let moved = true
while (moved) {
  moved = false
  for (const a of tasks) for (const b of tasks) {
    const la = laneOf.get(a.slug), lb = laneOf.get(b.slug)
    if (la !== lb && touches(a, b)) { const m = Math.min(la, lb); laneOf.set(a.slug, m); laneOf.set(b.slug, m); moved = true }
  }
}
const lanes = [...new Set(tasks.map(t => laneOf.get(t.slug)))].map(id => tasks.filter(t => laneOf.get(t.slug) === id))
out.lanes = lanes.map(l => l.map(t => t.slug))
log(`${tasks.length} task(s) in ${lanes.length} lane(s): ` + out.lanes.map(l => l.join(' -> ')).join(' | '))

// ---- Work -----------------------------------------------------------------------------
const RULES = [
  'Rules: work only in the worktree this stage names; never the main checkout, never another worktree, never main. Commits and pushes go through ship.py (raw git commit / push are refused by a hook). Never --no-gate. Stdlib-only Python that runs on 3.10; a new script or test follows its neighbours.',
]
async function one(t, base) {
  const rec = { slug: t.slug, title: t.title, kind: t.kind, base, pushed: false, review: 'none', findings: [] }
  const d = await agent(STAGE(`develop ${t.slug}`, [
    `Task: ${t.title}. Why: ${t.why}`,
    `It is expected to touch: ${t.files.join(', ')}. The measure: ${t.measure}`,
    `1. From ${WS}: \`py scripts/ship.py start ${SUB} ${t.slug} --role ${ROLE} --worktree --on ${base}\`. It prints the worktree; everything below happens there.`,
    '2. Take the measure now and keep the number or the failing output (before).',
    '3. Write the test that fails for this problem, then the change that makes it pass. Keep to this one concern: a second problem you meet is a line in your summary, not a change.',
    '4. Run the suite of every plugin you touched and, when ruff is installed, `ruff check .`; then take the measure again (after). A measure on live data must give the same answer as before wherever the answer is not what you changed: compare the outputs.',
    `5. From ${WS}: \`py scripts/ship.py commit ${SUB} --repo <the worktree> --all -m "<message>"\`: the message says what was wrong, what changed and the before and after numbers. Commit only; the workflow pushes after the review.`,
    'Return ok false with the reason when the problem is not there, is not in this repo, or cannot be fixed without a decision; change nothing in that case and remove nothing.',
    ...RULES,
  ]), { label: `develop ${t.slug}`, phase: 'Work', agentType: DEV, schema: DONE })
  if (!d) return Object.assign(rec, { reason: 'the develop stage returned nothing' })
  Object.assign(rec, { branch: d.branch, worktree: d.worktree, sha: d.sha, before: d.before, after: d.after, tests: d.tests, files: d.files, summary: d.summary })
  if (d.worktree) out.cleanup.push(d.worktree)
  if (!d.ok || !d.branch || !d.sha) return Object.assign(rec, { reason: d.reason || 'no commit was made' })

  const look = (label) => agent(STAGE(label, [
    `Review one change you did not write: \`git -C ${d.worktree} diff ${base}..${d.branch}\` (read whole files where the diff is not enough). The task was: ${t.title}.`,
    'Look for what is wrong, not for style: a result that differs from before where it should not, an input that occurs in practice and crashes, a caller in this repo that relied on what changed (grep for it), a test that would pass without the change. Reproduce a finding when that is cheap.',
    'blocking: it gives a wrong result or breaks a caller. minor: worth a line, not a fix round. For each: the file and line, what happens, and the input or sequence that triggers it. Say what you examined, so that no finding means something.',
    'Read-only: change, commit and push nothing.',
  ]), { label, phase: 'Work', agentType: REVIEWER, schema: REVIEW })
  let r = await look(`review ${t.slug}`)
  if (!r) return Object.assign(rec, { review: 'lost', reason: 'the review returned nothing: not pushed unreviewed' })
  rec.findings = r.findings
  let blocking = r.findings.filter(f => f.severity === 'blocking')
  if (blocking.length) {
    const f = await agent(STAGE(`fix ${t.slug}`, [
      `Your change on ${d.branch} (worktree ${d.worktree}) was reviewed. Fix exactly these blocking findings, each with a test that fails without the fix; a finding you can show to be wrong is answered in your summary instead, with the evidence.`,
      JSON.stringify(blocking),
      `Run the touched suites again, then from ${WS}: \`py scripts/ship.py commit ${SUB} --repo ${d.worktree} --all -m "<what the review found and what changed>"\`. Commit only.`,
      ...RULES,
    ]), { label: `fix ${t.slug}`, phase: 'Work', agentType: DEV, schema: DONE })
    if (!f || !f.ok) return Object.assign(rec, { review: 'blocking', reason: 'blocking findings were not fixed: ' + (f ? f.reason : 'the fix stage returned nothing') })
    Object.assign(rec, { sha: f.sha, tests: f.tests, fix: f.summary })
    r = await look(`re-review ${t.slug}`)
    if (!r) return Object.assign(rec, { review: 'lost', reason: 'the second review returned nothing: not pushed' })
    rec.findings = r.findings
    blocking = r.findings.filter(x => x.severity === 'blocking')
    if (blocking.length) return Object.assign(rec, { review: 'blocking', reason: `${blocking.length} blocking finding(s) remain after one fix round: left for the session, not pushed` })
    rec.review = 'clean after one fix'
  } else {
    rec.review = 'clean'
  }

  const p = await agent(STAGE(`push ${t.slug}`, [
    `From ${WS}: \`py scripts/ship.py push ${SUB} --repo ${d.worktree}\`. It runs the push gate (the repo's workflows) and then pushes; wait for it and read its own exit status, not a pipe's.`,
    'Return ok true and the pushed sha only when it printed the push line; else ok false with the refusal as printed. A refusal is returned, never retried, and never passed with --no-gate.',
  ]), { label: `push ${t.slug}`, phase: 'Work', agentType: DEV, schema: PUSHED, effort: 'low' })
  if (!p || !p.ok) return Object.assign(rec, { reason: 'the push was refused: ' + (p ? p.detail : 'the stage returned nothing') })
  return Object.assign(rec, { pushed: true, sha: p.sha || rec.sha })
}

phase('Work')
// a lane is worked in order, each task on the one before it; the lanes run side by side
const worked = await pipeline(lanes, async (lane) => {
  const done = []
  let base = A.base
  for (const t of lane) {
    const rec = await one(t, base)
    done.push(rec)
    if (!rec.pushed) {       // what stands on it cannot start: say so, do not build on sand
      for (const rest of lane.slice(done.length)) done.push({ slug: rest.slug, title: rest.title, kind: rest.kind, base: rec.branch || base, pushed: false, review: 'none', findings: [], reason: `not started: ${rec.slug}, which it is stacked on, was not pushed` })
      break
    }
    base = rec.branch
  }
  return done
})
out.tasks = worked.filter(Boolean).flat()
for (const lane of lanes) if (!out.tasks.some(t => t.slug === lane[0].slug)) for (const t of lane) out.tasks.push({ slug: t.slug, title: t.title, kind: t.kind, base: A.base, pushed: false, review: 'none', findings: [], reason: 'the lane failed before its first stage returned' })
const pushed = out.tasks.filter(t => t.pushed)
for (const t of out.tasks) log(`${t.slug}: ${t.pushed ? 'pushed ' + t.sha : 'NOT pushed (' + t.reason + ')'}`)

// ---- Union ----------------------------------------------------------------------------
// every branch was gated alone; main will hold them all. The tips of the lanes (each holds
// its lane) are merged in a throwaway worktree and the gate is run on that.
const tips = lanes.map(l => [...l].reverse().map(t => pushed.find(p => p.slug === t.slug)).find(Boolean)).filter(Boolean).map(t => t.branch)
if (tips.length > 1) {
  phase('Union')
  const u = await agent(STAGE('union', [
    `From ${AR}: \`py ${AR}/maintainer/scripts/maintain.py union --base ${A.base} --branches ${tips.join(' ')} --json\`. Return what it printed: ok, the merged branches, the conflict (branch and detail as one string, or empty) and the gate lines. Change nothing; it creates no branch and pushes nothing.`,
  ]), { label: 'union', phase: 'Union', agentType: DEV, schema: UNION, effort: 'low' })
  out.union = u ? { ok: u.ok, merged: u.merged, conflict: u.conflict, gate: u.gate } : { ok: false, merged: [], conflict: 'the union stage returned nothing', gate: [] }
} else {
  out.union = { ok: true, merged: tips, conflict: '', gate: ['one lane: its own push gate is the union'] }
}

out.pull_requests = pushed.map(t => ({
  head: t.branch, base: t.base, title: t.title,
  body: [t.summary, '', '## Measured', `before: ${t.before}`, `after: ${t.after}`, '', '## Tests', t.tests, '', '## Review', `${t.review}; ` + (t.findings.length ? t.findings.map(f => `${f.severity}: ${f.file}: ${f.what}`).join('; ') : 'no finding'), t.fix ? `fix round: ${t.fix}` : ''].filter(x => x !== undefined).join('\n'),
}))
out.ok = out.union.ok && out.tasks.every(t => t.pushed)
if (!out.ok) out.reason = !out.union.ok ? 'the branches do not pass together: ' + (out.union.conflict || 'the gate failed on the union') : 'some tasks were not pushed (see each task\'s reason)'
return out
