export const meta = {
  name: 'academy-cite',
  description: 'Add or verify one citation: one librarian run (entry, card with a verbatim quote, index row), the card validated by script with one retry, then the packet and the ticket',
  whenToUse: '/expert:cite and every cite ticket (also nested from the inbox), from the library home. args: {ticket?: "T-NNNN", ref?: "<DOI | arXiv id | bib key | title>", pinpoint?, relying?: "<sentence or claim id>", bib?: "<author instance>:references.bib"}',
  phases: [
    { title: 'Start', detail: 'take the ticket and read the ask' },
    { title: 'Cite', detail: 'one librarian run; the card validated, one retry' },
    { title: 'Land', detail: 'the citation packet and the ticket' },
  ],
}

// The order of /expert:cite in code (2026-10-31; docs/workflows.md): the brief is built
// here, the card is checked by cards.py validate (never by the librarian's word), a failing
// card goes back once, and the packet and the delivery come only after the check. The
// librarian's fetches stay on the source allowlist (source_guard.py). Nothing writes a
// \cite into a paper: that is the Author's edit.

const A = args || {}
if (!A.ticket && !A.ref) throw new Error('give args.ticket or args.ref')
const CLERK = 'academy:inbox-clerk'
const LIB = 'expert:librarian'
const T = A.ticket || ''
const ROOT = A.root ? A.root.replace(/[\\/]+$/, '') : null
const AR = ROOT || '<academy repo>'
const SCRIPTS = `Scripts: cards.py is \`py ${AR}/expert/scripts/cards.py\`, from the library home (python3 where there is no py)` +
  (ROOT ? '.\n' : '; <academy repo> is academy.root of the MCP tool workspace_get (academy.scripts.expert is the scripts folder).\n')
const clerk = (stage, lines, schema, label, phase) => agent(`WORKFLOW STAGE ${stage} of the academy-cite workflow.\n` + SCRIPTS + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const ASK = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' },
  ref: { type: 'string' }, pinpoint: { type: 'string' }, relying: { type: 'string' }, bib: { type: 'string' }, instance: { type: 'string' } },
  required: ['ok', 'detail', 'ref', 'pinpoint', 'relying', 'bib', 'instance'] }
const CARD = { type: 'object', properties: {
  key: { type: 'string' }, pinpoint: { type: 'string' }, card: { type: 'string', description: 'the card path' },
  verdict: { type: 'string', description: 'match, or how the source differs from what the paper wants' },
  cached: { type: 'boolean' }, reachable: { type: 'boolean', description: 'false: paywalled, image-only, no text' },
  bib_changed: { type: 'boolean' }, note: { type: 'string' } },
  required: ['key', 'pinpoint', 'card', 'verdict', 'cached', 'reachable', 'bib_changed', 'note'] }
const CHECK = { type: 'object', properties: { ok: { type: 'boolean' }, errors: { type: 'array', items: { type: 'string' } } }, required: ['ok', 'errors'] }
const PACKET = { type: 'object', properties: { packet: { type: 'string' }, error: { type: 'string' } }, required: ['packet', 'error'] }
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

const out = { ticket: T || null, notes: [] }

// ---- Start ----------------------------------------------------------------------------
phase('Start')
let ask = { ok: true, ref: A.ref || '', pinpoint: A.pinpoint || '', relying: A.relying || '', bib: A.bib || '', instance: '' }
if (T) {
  const a = await clerk('start', [`ticket: ${T}`,
    'Move it to in-progress (open -> accepted -> in-progress, acting as its receiver; leave an in-progress ticket as it is), then return from its ask, ## Ask and refs:',
    'the reference (DOI, arXiv id, bib key or title), the pinpoint wanted, the sentence or claim id that relies on it, the target bibliography (<author instance>:references.bib), and the instance you acted as.'],
    ASK, 'start', 'Start')
  if (!a || !a.ok) return Object.assign(out, { outcome: 'not-started', reason: a ? a.detail : 'the start stage returned nothing' })
  ask = { ok: true, ref: A.ref || a.ref, pinpoint: A.pinpoint || a.pinpoint, relying: A.relying || a.relying, bib: A.bib || a.bib, instance: a.instance }
}
if (!ask.ref) return Object.assign(out, { outcome: 'not-started', reason: 'the ask names no reference (DOI, arXiv id, key or title)' })

// ---- Cite: one librarian run, the card checked by script ------------------------------------
phase('Cite')
const brief = SCRIPTS + `${ask.ref}. ` + (ask.pinpoint ? `The pinpoint intended: ${ask.pinpoint}. ` : 'No pinpoint given: locate the statement. ') +
  (ask.relying ? `It is relied on by: ${ask.relying}. ` : '') + (ask.bib ? `The bibliography: ${ask.bib}.` : '') + '\n\n' +
  'If the key is already in that bibliography, verify it against the record rather than adding it again, and say whether the fields match. ' +
  'If it is new, fetch the record and add the entry in the file\'s key style. Then locate the statement, write its card with a verbatim quote ' +
  'from the version named, validate the card, and add the index row if the source is newly cached. Never write an entry from memory and never ' +
  'invent a pinpoint; a source you cannot read is said so on the card.'
let c = await agent(brief, { label: 'librarian', phase: 'Cite', agentType: LIB, schema: CARD })
if (c === null) return Object.assign(out, { outcome: 'lost', reason: 'the librarian run returned nothing (a limit?): nothing further launched' })
// an unreachable source has no card to validate (live run 2026-10-31 validated the words "none written"): skip the check
const noCard = !c.reachable && !/\.(md|ya?ml)$/i.test(String(c.card || '').trim())
let v = noCard ? null : await clerk('validate', [`Run cards.py validate ${c.card} from the library home and return ok (no error) and every error line.`], CHECK, 'validate', 'Cite')
if (v && !v.ok) {
  out.notes.push('the card failed validation; sent back to the librarian once: ' + v.errors.join('; '))
  const c2 = await agent(brief + `\n\nYour card ${c.card} fails cards.py validate:\n- ${v.errors.join('\n- ')}\n` +
    'Fix the card. A quote you cannot find in the cached text is corrected from the source, or the card says why it cannot be.',
    { label: 'librarian (fix)', phase: 'Cite', agentType: LIB, schema: CARD })
  if (c2 === null) return Object.assign(out, { outcome: 'lost', reason: 'the librarian fix returned nothing', card: c })
  c = c2
  v = await clerk('validate', [`Run cards.py validate ${c.card} and return ok and every error line.`], CHECK, 'validate again', 'Cite')
  if (v && !v.ok) out.notes.push('the card still fails validation after one fix; it must say why: ' + v.errors.join('; '))
}
Object.assign(out, { key: c.key, pinpoint: c.pinpoint, card: c.card, verdict: c.verdict, validated: !!(v && v.ok) })
if (!/^match$/i.test(c.verdict)) out.notes.unshift(`MISMATCH (a mathematical finding): the source differs from what ${ask.relying || 'the paper'} wants: ${c.verdict}`)
if (!c.reachable) out.notes.push('UNREACHABLE source: the card records how it was read; anything resting on it stays an unverified input until a human reads it')
// with a ticket, the bib edit in the Author home ships with it: the touch ledger records it and the
// ticket's --check passes it to ship.py as --touched (docs/branching.md); without one, nothing claims it
if (c.bib_changed && !T) out.notes.push(`${ask.bib || 'references.bib'} changed in the Author home and no ticket ships it: add --touched <that home's submodule>:references.bib to the command below (else the next Expert ticket's checkpoint carries it)`)
const end = async () => {
  if (!A.nested) out.ship = await ship({ role: 'expert', ticket: T, done: !!out.ticket_delivered, instance: ask.instance, topic: 'cite-' + (c.key || ask.ref),
    only: 'library board', agentType: CLERK, phase: 'Land', notes: out.notes })
  return out
}

// ---- Land --------------------------------------------------------------------------------
phase('Land')
const p = await agent(`File the citation packet for ${c.key}: packets_create kind citation, subject [bib:${c.key}#${c.pinpoint || '?'}], ` +
  `the card ${c.card} under ## Produced, the verdict (${c.verdict})${c.reachable ? '' : ' and how the unreadable source was read'} under ## Established vs assumed` +
  (T ? `, ticket ${T}` : '') + `; ## Decisions needed: None. unless the verdict is a mismatch, then one decision on what the relying statement should do. Return the packet id.`,
  { label: 'packet', phase: 'Land', agentType: LIB, schema: PACKET, effort: 'low' })
out.packet = p && p.packet ? p.packet : null
if (!out.packet) out.notes.push('the packet was not filed: ' + (p ? p.error : 'the stage returned nothing'))
// An unreadable source is not delivered (project rule "inaccessible sources"): the ticket is parked on the human
// with the exact ask (the source, the pinpoint wanted, the statement resting on it), and comes back as a gate
if (T && !c.reachable) {
  const why = `source unreachable from this session: ${c.key || ask.ref}; a human with access reads ${ask.pinpoint || 'the statement wanted'} for ${ask.relying || 'the relying statement'}`
  const m = await clerk('move', [`ticket: ${T}`, ask.instance ? `act as: ${ask.instance}` : '',
    `block-human: blocked, waiting_on [human], reason "${why.replace(/"/g, "'").slice(0, 240)}"` + (out.packet ? `, and fields.packets [${out.packet}]` : '')], MOVE, 'park on human', 'Land')
  out.ticket_delivered = false
  out.outcome = m && m.ok ? 'unreachable (on the human)' : 'unfinished'
  out.gate = { why, source: c.key || ask.ref, pinpoint: ask.pinpoint || '', relying: ask.relying || '', packet: out.packet }
  return await end()
}
if (T) {
  const result = `${c.key}, ${c.pinpoint || 'no pinpoint'}, verdict ${c.verdict}, card ${c.card}`.replace(/"/g, "'")
  const m = await clerk('move', [`ticket: ${T}`, ask.instance ? `act as: ${ask.instance}` : '',
    `deliver: deliver: true with result "${result.slice(0, 240)}"` + (out.packet ? ` and fields.packets [${out.packet}]` : '')], MOVE, 'deliver', 'Land')
  out.ticket_delivered = !!(m && m.ok)
}
out.outcome = out.validated ? 'cited' : 'cited (card not validated)'
return await end()
