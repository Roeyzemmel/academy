export const meta = {
  name: 'academy-domain',
  description: 'One domain-pack change from a ticket: one librarian run (one change, a theorem entry pinned to a card or sent to unverified.md, a CHANGELOG line), the diff checked against the changelog line by script, a notation packet when other instances rely on what changed',
  whenToUse: '/expert:domain and every notation ticket routed to the Expert (also nested from the inbox), from the library home. args: {ticket: "T-NNNN", pack?: "<pack name>", root?: "<academy repo>"}',
  phases: [
    { title: 'Start', detail: 'the ticket; one change only' },
    { title: 'Edit', detail: 'one librarian run' },
    { title: 'Check', detail: 'the diff names only the changelog\'s files' },
    { title: 'Land', detail: 'the notation packet when needed, the ticket' },
  ],
}

// The order of /expert:domain in code (2026-10-31; docs/workflows.md): one change per ticket
// (a ticket asking for two is split: the first is taken and the thread says so), a brief
// built here, and a check the librarian's word cannot replace: `git diff --stat
// domains/<pack>` must list only the files the new CHANGELOG line names (plus CHANGELOG.md).
// Nothing is committed: the human commits the academy repo.

const A = args || {}
if (!A.ticket) throw new Error('args.ticket is required: a pack change is always a ticket (confirm a one-line change with the human as a ticket first)')
const CLERK = 'academy:inbox-clerk'
const LIB = 'expert:librarian'
const T = A.ticket
const clerk = (stage, lines, schema, label, phase) => agent(`WORKFLOW STAGE ${stage} of the academy-domain workflow.\n` + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const START = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' }, pack: { type: 'string' },
  changes: { type: 'array', items: { type: 'string' }, description: 'the changes the ask requests, one line each (two unrelated ones are two entries)' },
  acted_as: { type: 'string' }, academy_root: { type: 'string' }, diff_before: { type: 'array', items: { type: 'string' }, description: 'git diff --name-only domains/<pack> before the edit' } },
  required: ['ok', 'detail', 'pack', 'changes', 'acted_as', 'academy_root', 'diff_before'] }
const EDITED = { type: 'object', properties: { files: { type: 'array', items: { type: 'string' }, description: 'pack files changed, relative to the pack' },
  changelog: { type: 'string', description: 'the CHANGELOG.md line appended' }, card: { type: 'string', description: 'a card written for a theorem entry, or empty' },
  unverified: { type: 'boolean', description: 'an entry that could not be pinned went to theorems/unverified.md' },
  shared: { type: 'boolean', description: 'the change alters a symbol or a statement other instances rely on' },
  clash: { type: 'string', description: 'a project decision it could clash with, or empty' } },
  required: ['files', 'changelog', 'card', 'unverified', 'shared', 'clash'] }
const DIFF = { type: 'object', properties: { changed: { type: 'array', items: { type: 'string' }, description: 'git diff --name-only domains/<pack>, relative to the pack' },
  changelog_last: { type: 'string', description: 'the last line of the pack\'s CHANGELOG.md' } }, required: ['changed', 'changelog_last'] }
const PACKET = { type: 'object', properties: { packet: { type: 'string' }, error: { type: 'string' } }, required: ['packet', 'error'] }
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, status: { type: 'string' }, detail: { type: 'string' } }, required: ['ok', 'status', 'detail'] }

const out = { ticket: T, notes: [], anomalies: [] }

// ---- Start ------------------------------------------------------------------------------
phase('Start')
const s = await clerk('start', [`ticket: ${T}`,
  'Move it to in-progress acting as its receiver (open -> accepted -> in-progress; leave it if in progress). Return the pack it names' +
  (A.pack ? ` (given: ${A.pack})` : '') + ', the changes it asks for (one line each; two unrelated changes are two entries), the instance you acted as, ' +
  'the academy repo root (the folder holding domains/), and git -C <academy> diff --name-only domains/<pack> as it is now.'], START, 'start', 'Start')
if (!s || !s.ok) return Object.assign(out, { outcome: 'not-started', reason: s ? s.detail : 'the start stage returned nothing' })
const pack = A.pack || s.pack
if (!pack || !s.changes.length) return Object.assign(out, { outcome: 'not-started', reason: 'the ticket names no pack or no change' })
if (s.changes.length > 1) {
  out.notes.push(`the ticket asks for ${s.changes.length} changes: the first is taken, the rest wait for a ticket of their own`)
  await clerk('move', [`ticket: ${T}`, `act as: ${s.acted_as}`, `note: append to the thread "split: this run takes only the first change (${s.changes[0].replace(/"/g, "'").slice(0, 120)}); the others need a ticket of their own"`], MOVE, 'split note', 'Start')
}
if ((s.diff_before || []).length) out.notes.push('the pack already had uncommitted changes before this run: ' + s.diff_before.join(', '))

// ---- Edit ---------------------------------------------------------------------------------
phase('Edit')
const e = await agent(`Edit the ${pack} domain pack for ${T}: ${s.changes[0]}. Read the current file with domain_get first. A theorem entry carries its real ` +
  'hypotheses and a pinpoint that has a card (write the card first if it has none; an entry you cannot pin goes to theorems/unverified.md). Change one thing, ' +
  `keep the file's structure, and append "- <date> ${T}: <one line naming the file(s) changed>" to CHANGELOG.md. Say whether the change alters a symbol or a ` +
  'statement other instances rely on, and any project decision it could clash with. Commit nothing.',
  { label: 'librarian', phase: 'Edit', agentType: LIB, schema: EDITED })
if (e === null) return Object.assign(out, { outcome: 'lost', reason: 'the librarian run returned nothing (a limit?): nothing further launched' })
Object.assign(out, { pack, files: e.files, changelog: e.changelog, card: e.card || null })
if (e.unverified) out.notes.push('the entry could not be pinned to a card: it went to theorems/unverified.md')

// ---- Check: the diff, not the word ---------------------------------------------------------
phase('Check')
const d = await clerk('diff', [`Return git -C ${s.academy_root} diff --name-only -- domains/${pack} (paths relative to domains/${pack}/, untracked new files included via git status --porcelain) and the last line of domains/${pack}/CHANGELOG.md. Change nothing.`],
  DIFF, 'diff', 'Check')
const before = new Set((s.diff_before || []).map(x => x.replace(new RegExp('^domains/' + pack + '/'), '')))
const changed = (d ? d.changed : []).map(x => x.replace(new RegExp('^domains/' + pack + '/'), '')).filter(x => !before.has(x))
const named = new Set(['CHANGELOG.md'].concat(e.files || []))
const extra = changed.filter(x => !named.has(x))
if (!d) out.anomalies.push('the diff stage returned nothing')
else {
  if (!changed.includes('CHANGELOG.md')) out.anomalies.push('CHANGELOG.md has no new line')
  if (!(d.changelog_last || '').includes(T)) out.anomalies.push(`the last CHANGELOG line does not name ${T}`)
  if (extra.length) out.anomalies.push('files changed that the change does not name: ' + extra.join(', '))
  if (!changed.some(x => x !== 'CHANGELOG.md')) out.anomalies.push('no pack file besides CHANGELOG.md changed')
}
out.changed = changed

// ---- Land -----------------------------------------------------------------------------------
phase('Land')
if (e.shared) {
  const p = await agent(`File a notation packet for ${T} (packets_create kind notation, ticket ${T}): the ${pack} pack changed (${e.changelog}); it alters a symbol or a ` +
    'statement other instances rely on.' + (e.clash ? ` It could clash with a project decision (${e.clash}): put that to the human as one decision with a recommendation.` : ' ## Decisions needed: None.') +
    ' Return the packet id.', { label: 'packet', phase: 'Land', agentType: LIB, schema: PACKET, effort: 'low' })
  out.packet = p && p.packet ? p.packet : null
  if (!out.packet) out.notes.push('the notation packet was not filed: ' + (p ? p.error : 'no answer'))
}
const result = `${pack}: ${(e.files || []).join(', ')}; ${e.changelog}` + (out.packet ? `; packet ${out.packet}` : '') + (out.anomalies.length ? '; CHECK: ' + out.anomalies.join('; ') : '')
const m = await clerk('move', [`ticket: ${T}`, `act as: ${s.acted_as}`,
  out.anomalies.length
    ? `block-human: blocked, waiting_on [human], reason "the pack diff does not match the change: ${out.anomalies.join('; ').replace(/"/g, "'").slice(0, 200)}"`
    : `deliver: deliver: true with result "${result.replace(/"/g, "'").slice(0, 240)}"` + (out.packet ? ` and fields.packets [${out.packet}]` : '')], MOVE, 'close', 'Land')
out.ticket_status = m ? m.status : 'unknown'
out.outcome = out.anomalies.length ? 'blocked-on-check' : 'edited'
return out
