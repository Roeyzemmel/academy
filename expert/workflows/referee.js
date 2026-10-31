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

const out = { ticket: T || null, notes: [] }

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
if (pdf.rebuilt) out.notes.push(`the PDF was stale and was rebuilt (${pdf.built})`)
Object.assign(out, { instance, pdf: pdf.pdf, built: pdf.built })

// ---- Referee: the brief from facts only ---------------------------------------------------
phase('Referee')
const brief = `Referee ${instance} cold. The PDF is ${pdf.pdf}, built ${pdf.built}. ` +
  (pdf.last_report ? `The last report is ${pdf.last_date}${pdf.changed_since ? '; changed since: ' + pdf.changed_since : ''}. ` : 'There is no earlier report. ') +
  (A.focus ? `The human asks you to look hardest at: ${A.focus}. ` : '') +
  `Do not read the agenda or tickets before your cold reading. After it, check the paper against its vision, ` +
  (pdf.vision ? pdf.vision : 'there is none') + `. Ticket: ${T || 'none'}.`
const r = await agent(brief, { label: 'referee', phase: 'Referee', agentType: 'expert:referee' })
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
    `deliver: deliver: true with result "referee packet ${f.packet}; ${f.blocking} blocking" and fields.packets [${f.packet}]`], MOVE, 'deliver', 'Land')
  out.ticket_delivered = !!(m && m.ok)
}
out.outcome = 'refereed'
return out
