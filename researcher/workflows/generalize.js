export const meta = {
  name: 'academy-generalize',
  description: 'Turn a reviewed experiment\'s Conclusion into conjectures: the source checked by script, one prover writing the proposals file, validated with one retry (then dropped), objects created, the packet filed; the falsifier tests are filed by the main session',
  whenToUse: '/researcher:generalize and every generalize ticket (also nested from the inbox), from the Researcher home. args: {ref: "P-NNNN" | "lab:<id>", ticket?: "T-NNNN" (the generalize ticket), home, instance, file?: <proposals path>, mode?: "propose" | "deliver"}',
  phases: [
    { title: 'Source', detail: 'generalize.py source: the Conclusion and a cleared review' },
    { title: 'Propose', detail: 'one prover writes the proposals file; validate, one retry, then drop' },
    { title: 'Record', detail: 'objects, packet; the tests for the main session' },
  ],
}

// The order of /researcher:generalize in code (2026-10-31; docs/workflows.md): nothing is
// generalized from an experiment whose review has not cleared (generalize.py source refuses);
// the prover writes only the proposals file (at most maxPerRun, never above conjectured;
// lemmas open or sketch); generalize.py validate decides, with one retry before a failing
// proposal is dropped; the objects and the packet come from generalize.py; the test tickets
// are filed by the main session (main is the researcher -> scientist liaison, the prover is
// not), and mode deliver checks they exist before the generalize ticket is delivered.

const A = args || {}
if (!A.ref || !/^(P-\d{4,}|[a-z][a-z0-9]*:\S+)$/.test(A.ref)) throw new Error('args.ref must be a report packet (P-NNNN) or a lab claim id')
if (!A.home) throw new Error('args.home must be the Researcher home')
const MODE = A.mode === 'deliver' ? 'deliver' : 'propose'
const CLERK = 'researcher:review-clerk'
const PROVER = 'researcher:prover'
const T = A.ticket || ''
const clerk = (stage, lines, schema, label, phase) => agent(
  `WORKFLOW STAGE ${stage} of the academy-generalize workflow. Home: ${A.home}.` + (A.instance ? ` Instance: ${A.instance}.` : '') + (T ? ` Ticket: ${T}.` : '') + '\n' + lines.filter(Boolean).join('\n'),
  { label: label || stage, phase, agentType: CLERK, schema, effort: 'low' })

const SOURCE = { type: 'object', properties: { ok: { type: 'boolean' }, refusal: { type: 'string', description: 'the exit-2 message when the review has not cleared' },
  lab_claim: { type: 'string' }, report: { type: 'string' }, max: { type: 'number', description: 'the cap generalize.py reports (maxPerRun, at most 3)' } },
  required: ['ok', 'refusal', 'lab_claim', 'report', 'max'] }
const CHECKED = { type: 'object', properties: { ok: { type: 'boolean' }, problems: { type: 'array', items: { type: 'string' } },
  failing: { type: 'array', items: { type: 'string' }, description: 'the proposal ids the problems name' }, proposals: { type: 'number' } }, required: ['ok', 'problems', 'failing', 'proposals'] }
const CREATED = { type: 'object', properties: { conjectures: { type: 'array', items: { type: 'string' } }, lemmas: { type: 'array', items: { type: 'string' } }, error: { type: 'string' } }, required: ['conjectures', 'lemmas', 'error'] }
const PACKET = { type: 'object', properties: { packet: { type: 'string' }, error: { type: 'string' } }, required: ['packet', 'error'] }
const CHILDREN = { type: 'object', properties: { tests: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, refs: { type: 'array', items: { type: 'string' } } }, required: ['id', 'refs'] } } }, required: ['tests'] }
const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok', 'detail'] }

const out = { ref: A.ref, ticket: T || null, mode: MODE, notes: [] }

// ---- deliver: after the main session filed the tests ---------------------------------------
if (MODE === 'deliver') {
  if (!T) throw new Error('mode deliver needs args.ticket')
  if (!A.conjectures || !A.conjectures.length) throw new Error('mode deliver needs args.conjectures (the ids propose returned)')
  const ch = await clerk('children', [`List the tickets whose parent is ${T} (tickets_list / tickets_get), kind test, with their refs. Write nothing.`], CHILDREN, 'children', 'Record')
  const tests = ch ? ch.tests : []
  const missing = A.conjectures.filter(cid => !tests.some(t => (t.refs || []).some(r => r === cid || r.endsWith(':' + cid.split(':').pop()))))
  if (missing.length) return Object.assign(out, { outcome: 'tests-missing', missing, reason: 'no test ticket names ' + missing.join(', ') + ': file them first' })
  const result = `${A.conjectures.length} conjectures filed: ${A.conjectures.join(', ')}; lemmas ${(A.lemmas || []).join(', ') || 'none'}; tests ${tests.map(t => t.id).join(', ')}`
  const m = await clerk('close', [`Deliver ${T} (tickets_update deliver: true) with result "${result.slice(0, 240)}"` + (A.packet ? ` and fields.packets [${A.packet}]` : '') + '.'], MOVE, 'close', 'Record')
  return Object.assign(out, { outcome: m && m.ok ? 'delivered' : 'unfinished', tests: tests.map(t => t.id) })
}

// ---- Source -----------------------------------------------------------------------------
phase('Source')
const s = await clerk('source', [`Run generalize.py source ${A.ref} --json: return ok, or ok false with its exit-2 refusal; the lab claim, the report packet and the cap (max).`,
  T ? `If it is ok, take ${T}: open -> accepted -> in-progress (leave an in-progress ticket as it is).` : 'Touch no ticket.'], SOURCE, 'source', 'Source')
if (!s) return Object.assign(out, { outcome: 'not-started', reason: 'the source stage returned nothing' })
if (!s.ok) return Object.assign(out, { outcome: 'not-started', reason: 'generalize.py source refused: ' + s.refusal + ' (run /researcher:review-experiment first)' })
if (!T) return Object.assign(out, { outcome: 'needs-ticket', needs_ticket: true, lab_claim: s.lab_claim, report: s.report,
  reason: 'no generalize ticket: the main session files one to this instance (kind generalize, refs the lab claim and the report), then calls again with it' })
const LAB = s.lab_claim
const MAX = Math.max(1, Math.min(s.max || 3, 3))
const FILE = A.file || `${A.home}/.academy/generalize-${LAB.replace(/[^A-Za-z0-9._-]+/g, '-')}.json`

// ---- Propose: the file, validated by script ---------------------------------------------------
phase('Propose')
const brief = `Generalize the reviewed experiment ${s.report || A.ref} (lab claim ${LAB}; home ${A.home}). Read its ## Conclusion, and the domain's examples.md and ` +
  `theorems/INDEX.md (domain_get) for what is known; scout prior art. Write at most ${MAX} proposals to ${FILE} (create the folder), in the shape generalize.py's docstring gives: ` +
  `id in this instance's namespace, title, statement, kind conjecture, status conjectured, bears_on including ${LAB}, the falsifier, the pattern (wider class / ` +
  `relaxed hypothesis / pattern / invariant) and a one-line rationale; optional lemmas (at most three per proposal, status open or sketch, saying what is known and ` +
  `what is missing). Write ONLY that file: create no object and file no ticket.`
const p1 = await agent(brief, { label: 'prover', phase: 'Propose', agentType: PROVER })
if (p1 === null) return Object.assign(out, { outcome: 'lost', reason: 'the prover returned nothing (a limit?)' })
const validate = (label) => clerk('validate', [`Run generalize.py validate ${FILE} --lab-claim ${LAB} --json and return ok, the problems, the proposal ids they name, and the number of proposals.`], CHECKED, label, 'Propose')
let v = await validate('validate')
if (v && !v.ok) {
  out.notes.push('the proposals failed validation; sent back to the prover once: ' + v.problems.join('; '))
  const p2 = await agent(brief + `\n\nThe file ${FILE} fails generalize.py validate:\n- ${v.problems.join('\n- ')}\nFix those proposals in the file.`,
    { label: 'prover (fix)', phase: 'Propose', agentType: PROVER })
  if (p2 === null) return Object.assign(out, { outcome: 'lost', reason: 'the prover fix returned nothing' })
  v = await validate('validate again')
  if (v && !v.ok) {
    out.notes.push(`dropped after a second failure: ${v.failing.join(', ')} (${v.problems.join('; ')})`)
    await clerk('drop', [`Remove the proposals ${v.failing.join(', ')} from ${FILE} (a mechanical edit of the JSON list; change nothing else).`], MOVE, 'drop', 'Propose')
    v = await validate('validate after drop')
    if (!v || !v.ok) return Object.assign(out, { outcome: 'failed', reason: 'the proposals file still fails after dropping: ' + (v ? v.problems.join('; ') : 'no answer') })
  }
}
if (!v || !v.proposals) return Object.assign(out, { outcome: 'nothing-proposed', reason: 'no valid proposal' })

// ---- Record -----------------------------------------------------------------------------------
phase('Record')
const c = await clerk('create', [`Run generalize.py create ${FILE} --lab-claim ${LAB} --apply and return the conjecture ids and the lemma ids it wrote (or its error).`], CREATED, 'create', 'Record')
if (!c || c.error) return Object.assign(out, { outcome: 'failed', reason: 'generalize.py create: ' + (c ? c.error : 'no answer') })
const pk = await clerk('packet', [`Run generalize.py packet-body ${FILE} --lab-claim ${LAB} --report ${s.report} --out ${A.home}/.academy/generalize-body.md, then packets.py new ` +
  `--instance ${A.instance || '<this instance>'} --kind generalization --title "Generalizations of ${LAB}" --ticket ${T} --subject ${c.conjectures.concat(c.lemmas).join(',')} ` +
  `--status-proposed conjectured --body <that file>; return the packet id.`], PACKET, 'packet', 'Record')
Object.assign(out, { lab_claim: LAB, file: FILE, conjectures: c.conjectures, lemmas: c.lemmas, packet: pk && pk.packet ? pk.packet : null })
if (!out.packet) out.notes.push('the packet was not filed: ' + (pk ? pk.error : 'no answer'))
out.to_file = [{ why: 'the falsifier tests: main is the researcher -> scientist liaison',
  command: `py <researcher plugin>/scripts/generalize.py tickets ${FILE} --lab-claim ${LAB} --parent ${T} --apply`,
  then: { mode: 'deliver', ticket: T, conjectures: c.conjectures, lemmas: c.lemmas, packet: out.packet } }]
out.outcome = 'proposed'
return out
