export const meta = {
  name: 'academy-notes',
  description: 'File the human\'s and the coauthors\' new margin notes (or a referee packet\'s points) as tickets: the inventory by script, one classification, every proposed ticket checked by routes.check_filed before it is filed, the filed tickets read back, the four lists computed in code',
  whenToUse: '/author:notes and a returned referee packet (also nested from the inbox), from the Author home. args: {home, instance, root?, base?: "<commit>", referee?: "P-NNNN", files?: [paths], uncarried?: true (the standing notes of those files that no ticket carries)}',
  phases: [
    { title: 'Collect', detail: 'the new notes and the inventory (or the packet\'s points)' },
    { title: 'Classify', detail: 'covered / answers / discrepancy / new, with the proposed tickets' },
    { title: 'Check', detail: 'routes.check_filed and the kind rules, one retry' },
    { title: 'File', detail: 'exactly the checked tickets; read back' },
  ],
}

// The order of /author:notes in code (2026-10-31; docs/workflows.md). The inventory comes
// from git (never from memory), the classifier proposes and files nothing, every proposed
// ticket passes the Author's role-cut rule (routes.check_filed: a missing argument is a
// research ticket to the Expert with final_to researcher, never a write) and the kind rules
// below before it is filed, a judgement point or a decision only the human makes is parked
// on human, and what was filed is read back from the board. Notes on the tex are never edited.

const A = args || {}
if (!A.home || !A.instance) throw new Error('args.home and args.instance are required')
// a returned referee ticket names its packet in its packets field (the inbox passes the ticket)
const REFEREE = A.referee || (A.referee_ticket ? `the referee packet in the packets field of ${A.referee_ticket}` : '')
const CLERK = 'academy:inbox-clerk'
const FILER = 'general-purpose'
const SELF_KINDS = ['apply', 'write', 'copy', 'figure', 'build', 'notation', 'sweep']
const ROUTES = A.root ? `${A.root.replace(/[\\/]+$/, '')}/author/scripts/routes.py` : '<author plugin>/scripts/routes.py'
const clerk = (stage, lines, schema, label, phase) => agent(`WORKFLOW STAGE ${stage} of the academy-notes workflow. Author home: ${A.home}. Instance: ${A.instance}.\n` + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const NOTE = { type: 'object', properties: { id: { type: 'string', description: 'file:line, or P-NNNN point k' }, file: { type: 'string' }, line: { type: 'number' },
  macro: { type: 'string' }, label: { type: 'string', description: 'the label of the statement it sits on, or empty' }, text: { type: 'string', description: 'the whole brace group' } },
  required: ['id', 'file', 'line', 'macro', 'label', 'text'] }
const INV = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' }, packet: { type: 'string', description: 'the referee packet id, when one was read' }, ns: { type: 'string', description: 'the paper\'s claim namespace' },
  new: { type: 'array', items: NOTE }, inventory: { type: 'number' }, inventory_notes: { type: 'array', items: NOTE } }, required: ['ok', 'detail', 'ns', 'new', 'inventory', 'inventory_notes'] }
const PROPOSED = { type: 'object', properties: { to: { type: 'string' }, kind: { type: 'string' }, title: { type: 'string' }, ask: { type: 'string' },
  deliverable: { type: 'string' }, agenda: { type: 'string' }, refs: { type: 'array', items: { type: 'string' } }, final_to: { type: 'string' },
  detail: { type: 'string' }, park_on: { type: 'string', description: '"human", the id of another note this one builds on, or empty' } },
  required: ['to', 'kind', 'title', 'ask', 'deliverable', 'agenda', 'refs', 'final_to', 'detail', 'park_on'] }
const DECISION = { type: 'object', properties: { note: { type: 'string' }, decision: { type: 'string', enum: ['covered', 'answers', 'discrepancy', 'new'] },
  ticket: { type: 'string', description: 'covered / answers: the ticket it belongs to' }, words: { type: 'string', description: 'covered / answers: the line to add to that ticket\'s thread' },
  judgement: { type: 'boolean', description: 'a judgement point or a decision only the human can make' },
  claim_vs_file: { type: 'string', description: 'discrepancy: the claim and the actual text' }, proposed: PROPOSED },
  required: ['note', 'decision', 'ticket', 'words', 'judgement', 'claim_vs_file'] }
const CLASSIFIED = { type: 'object', properties: { decisions: { type: 'array', items: DECISION } }, required: ['decisions'] }
const CHECKED = { type: 'object', properties: { problems: { type: 'array', items: { type: 'array', items: { type: 'string' } } } }, required: ['problems'] }
const FILED = { type: 'object', properties: { filed: { type: 'array', items: { type: 'object', properties: { note: { type: 'string' }, ticket: { type: 'string' } }, required: ['note', 'ticket'] } },
  appended: { type: 'array', items: { type: 'string' } }, refused: { type: 'array', items: { type: 'string' } } }, required: ['filed', 'appended', 'refused'] }
const READ = { type: 'object', properties: { tickets: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, to: { type: 'string' }, kind: { type: 'string' },
  final_to: { type: 'string' }, status: { type: 'string' }, waiting_on: { type: 'array', items: { type: 'string' } } }, required: ['id', 'to', 'kind', 'final_to', 'status', 'waiting_on'] } } }, required: ['tickets'] }

const out = { found: [], filed: [], covered: [], discrepancies: [], notes: [], anomalies: [], unfiled: [] }

// ---- Collect ---------------------------------------------------------------------------
phase('Collect')
const inv = await clerk('collect', REFEREE
  ? [`Read ${REFEREE} (tickets_get for the ticket, then the packet file under board/packets/): return each point as a note with id "<P-NNNN> point <k>", the packet id as packet, the label of the statement it concerns, and its text. ` +
     'Also return the paper\'s claim namespace (the home\'s registry profile) and, for the inventory, the count of note macros in the tex (git grep).']
  : ['Read the home\'s .claude/academy.json: author.noteMacros.human and .coauthors, paths.tex, and workspace.json human.noteMacro.',
     A.files && A.uncarried
       // a section's standing notes that were never filed (2026-10-31): the inventory of those files minus what a ticket carries
       ? `New notes: every note-macro occurrence (human and coauthor macros only, never the machine macro) in ${A.files.join(', ')} that NO ticket carries yet: a ticket carries a note when its detail or ask names its file:line, or quotes its distinctive words (search tickets_list / board.py list for a phrase of each note). Take the whole brace group from the file, with the label of the statement it sits on.`
       : `New notes: lines adding a note macro in git diff --cached -U0 and git diff -U0${A.base ? ' against ' + A.base : ''} over the tex paths; take the whole brace group from the file, with the label of the statement it sits on.`,
     'Inventory: git grep -n for each macro over the tex paths (count, and every note with file, line, macro, label, text). Return the claim namespace too. Write nothing.'],
  INV, 'collect', 'Collect')
if (!inv || !inv.ok) return Object.assign(out, { outcome: 'not-started', reason: inv ? inv.detail : 'the collect stage returned nothing' })
out.found = inv.new.map(n => `${n.file}:${n.line} ${n.label || '(no statement)'}: ${n.text.slice(0, 120)}`)
out.inventory = inv.inventory
if (inv.packet) out.packet = inv.packet
if (!inv.new.length) return Object.assign(out, { outcome: 'nothing-new' })

// ---- Classify ----------------------------------------------------------------------------
phase('Classify')
const brief = (extra) => `You decide, for each new ${REFEREE ? 'point of ' + REFEREE : 'margin note'} of the paper in ${A.home} (instance ${A.instance}), what it is; you FILE NOTHING here. ` +
  'Read the agenda format in the Author plugin\'s references/formats.md. For each note: covered (an active ticket carries the same question: tickets_list / board.py list, a distinctive phrase; give the ticket and the new words if it is weaker); ' +
  'answers (it answers a machine note: give the ticket whose thread records which question is now answered); discrepancy (it says something was changed, "I removed", "renamed to", but the file shows only the note: give the claim and the actual text, and propose an apply ticket if plainly an instruction, else a ticket to this instance parked on human); ' +
  `new (propose the ticket: work that stays in the Author goes to ${A.instance} as apply, write, copy, figure, build or notation; a verification to the Expert as verify; a citation as cite; a note asking for a proof is research to the Expert with final_to researcher, an experiment final_to scientist, never write: the Author invents no argument; ` +
  `agenda <ns>:<label> of the statement it sits on (ns ${inv.ns}); refs the same; detail "<macro> note <file>:<line>: <the note quoted, lightly>"${REFEREE ? ' with "<P-NNNN> point <k>" and refs <P-NNNN>; judgement points parked on human, objective ones as apply / write' : ''}). ` +
  'Mark judgement: true for a judgement point or a decision only the human can make (it is filed to this instance and parked on human). park_on: another note\'s id when this one builds on it.\n' +
  `The notes:\n${JSON.stringify(inv.new)}` + (extra || '')
let cls = await agent(brief(), { label: 'classify', phase: 'Classify', agentType: FILER, model: 'sonnet', schema: CLASSIFIED })
if (cls === null) return Object.assign(out, { outcome: 'lost', reason: 'the classification returned nothing (a limit?)' })

// ---- Check: the role cut and the kind rules, one retry --------------------------------------
phase('Check')
function kindProblems(d) {
  const p = d.proposed, probs = []
  if (!p) return ['a new note with no proposed ticket']
  if (SELF_KINDS.includes(p.kind) && p.to !== A.instance) probs.push(`a ${p.kind} ticket stays in the Author: to ${A.instance}, not ${p.to}`)
  if (['verify', 'cite', 'research', 'referee', 'lookup'].includes(p.kind) && !/^expert@/.test(p.to)) probs.push(`a ${p.kind} ticket goes to the Expert, not ${p.to}`)
  if (p.kind === 'research' && !/^(researcher|scientist)/.test(p.final_to || '')) probs.push('a research ticket names final_to researcher (or scientist for an experiment)')
  if (d.judgement && !(p.to === A.instance && p.park_on === 'human')) probs.push('a judgement point is filed to this instance and parked on human')
  if (p.park_on && p.park_on !== 'human' && p.to !== A.instance) probs.push('only a ticket to the Author itself can be parked on another (a receiver\'s move)')
  return probs
}
async function check(decisions) {
  const props = decisions.filter(d => d.decision === 'new' || (d.decision === 'discrepancy' && d.proposed))
  const rc = await clerk('check-filed', [`Write this JSON list to <home>/.academy/notes-check.json and run python3 ${ROUTES} --check-filed <that file>; return its output list.`,
    JSON.stringify(props.map(d => Object.assign({ to: d.proposed.to, kind: d.proposed.kind, title: d.proposed.title, ask: d.proposed.ask, final_to: d.proposed.final_to })))],
    CHECKED, 'check-filed', 'Check')
  const bad = {}
  props.forEach((d, i) => {
    const probs = ((rc && rc.problems[i]) || []).concat(kindProblems(d))
    if (probs.length) bad[d.note] = probs
  })
  return bad
}
let bad = await check(cls.decisions)
if (Object.keys(bad).length) {
  out.notes.push('proposals sent back once: ' + Object.entries(bad).map(([n, p]) => `${n}: ${p.join('; ')}`).join(' | '))
  const again = await agent(brief(`\n\nThese proposals break the rules; correct them (return every decision again):\n${JSON.stringify(bad)}`),
    { label: 'classify again', phase: 'Check', agentType: FILER, model: 'sonnet', schema: CLASSIFIED })
  if (again === null) return Object.assign(out, { outcome: 'lost', reason: 'the second classification returned nothing' })
  cls = again
  bad = await check(cls.decisions)
}
const fileable = cls.decisions.filter(d => (d.decision === 'new' || (d.decision === 'discrepancy' && d.proposed)) && !bad[d.note])
for (const [n, p] of Object.entries(bad)) out.unfiled.push(`${n}: not filed after one correction (${p.join('; ')})`)
const appends = cls.decisions.filter(d => (d.decision === 'covered' || d.decision === 'answers') && d.ticket)
out.covered = appends.map(d => `${d.note} -> ${d.ticket}`)
out.discrepancies = cls.decisions.filter(d => d.decision === 'discrepancy').map(d => `${d.note}: ${d.claim_vs_file}`)

// ---- File: exactly the checked tickets, then read back ---------------------------------------------
phase('File')
if (fileable.length || appends.length) {
  const f = await agent(`File exactly these tickets for ${A.instance} (Author home ${A.home}), and nothing else: py <academy plugin>/scripts/board.py new --as ${A.instance} ` +
    '--to <to> --kind <kind> --title ... --ask ... --deliverable ... [--agenda ...] --refs ... [--final-to ...] --detail ...; then, for a ticket with park_on, ' +
    'board.py transition <id> blocked --waiting-on <human | the ticket filed for that note> --reason "<why>" --as ' + A.instance + '.\n' +
    `Tickets: ${JSON.stringify(fileable.map(d => Object.assign({ note: d.note }, d.proposed)))}\n` +
    `Then add these thread lines (board.py append <ticket> --text "<words>" --as ${A.instance}): ${JSON.stringify(appends.map(d => ({ ticket: d.ticket, words: d.words, note: d.note })))}\n` +
    'Edit no file and run no git write. Return the ticket filed per note, the tickets appended to, and any refusal verbatim.',
    { label: 'file', phase: 'File', agentType: FILER, model: 'sonnet', schema: FILED })
  if (f === null) return Object.assign(out, { outcome: 'lost', reason: 'the filing run returned nothing; check the board for what was filed' })
  out.filed = f.filed
  if (f.refused.length) out.anomalies.push('refused: ' + f.refused.join('; '))
  const rb = f.filed.length ? await clerk('readback', [`tickets_get each of ${f.filed.map(x => x.ticket).join(', ')} and return its to, kind, final_to, status and waiting_on.`], READ, 'read back', 'File') : { tickets: [] }
  for (const x of f.filed) {
    const d = fileable.find(y => y.note === x.note), t = (rb ? rb.tickets : []).find(y => y.id === x.ticket)
    if (!d || !t) { out.anomalies.push(`${x.ticket}: not found on the board`); continue }
    if (t.to !== d.proposed.to || t.kind !== d.proposed.kind || (d.proposed.final_to || '') !== (t.final_to || '')) out.anomalies.push(`${x.ticket} was filed as ${t.kind} to ${t.to}, not as checked (${d.proposed.kind} to ${d.proposed.to})`)
    if (d.proposed.park_on && t.status !== 'blocked') out.anomalies.push(`${x.ticket} should be parked on ${d.proposed.park_on}`)
  }
  for (const d of fileable) if (!f.filed.some(x => x.note === d.note)) out.unfiled.push(`${d.note}: the filer did not file it`)
}
// every inventory note that no ticket carries (by its file:line in a ticket's detail is the filer's job; here: the run's own)
const carried = new Set([].concat(out.filed.map(x => x.note), appends.map(d => d.note)))
out.not_carried = inv.new.filter(n => !carried.has(n.id)).map(n => n.id)
out.outcome = out.anomalies.length || out.unfiled.length ? 'filed (with problems)' : 'filed'
return out
