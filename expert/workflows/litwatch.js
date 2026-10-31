export const meta = {
  name: 'academy-litwatch',
  description: 'Literature watch for one instance: return-only scouts over the search vocabulary in parallel, hits deduplicated by arXiv id or DOI in code, one scout writes the ledger file',
  whenToUse: '/expert:litwatch, from the library home. args: {instance: "author@<x>", statement?: "<ns:id>" (a one-statement prior-art search, a single scout), groups?: 4}',
  phases: [
    { title: 'Plan', detail: 'the header, the vocabulary and the window' },
    { title: 'Search', detail: 'one return-only scout per group of sources, in parallel' },
    { title: 'Record', detail: 'one scout writes the deduplicated ledger file' },
  ],
}

// The literature watch with its read-only work fanned out (2026-10-31; docs/workflows.md).
// The scouts in the Search phase return candidates and write nothing; the script merges
// and dedupes them; exactly one scout writes, in Record. The ledger folder is listed
// before and after, so a file written outside Record is reported as an anomaly.

const A = args || {}
if (!A.instance || !/^[a-z]+@[a-z0-9][a-z0-9-]*$/.test(A.instance)) throw new Error('args.instance must be a workspace instance (author@<name>)')
const SCOUT = 'expert:related-work-scout'
const GROUPS = Math.max(1, Math.min(A.groups || 4, 6))
const LEDGER = `ledgers/${A.instance}/`

const PLAN = { type: 'object', properties: {
  ok: { type: 'boolean' }, stop_reason: { type: 'string' },
  window_start: { type: 'string', description: 'YYYY-MM-DD: the newest watch-*.md, or 30 days ago' },
  today: { type: 'string', description: 'YYYY-MM-DD' },
  files_before: { type: 'array', items: { type: 'string' }, description: 'the file names now in ' + LEDGER },
  sources: { type: 'array', items: { type: 'object', properties: {
    kind: { type: 'string', enum: ['category', 'keyword', 'author', 'anchor'] }, item: { type: 'string' } },
    required: ['kind', 'item'] } } },
  required: ['ok', 'stop_reason', 'window_start', 'today', 'files_before', 'sources'] }
const HIT = { type: 'object', properties: {
  id: { type: 'string', description: 'arXiv id (e.g. 2410.01234) or DOI; empty if neither' },
  title: { type: 'string' }, authors: { type: 'string' }, url: { type: 'string' }, date: { type: 'string' },
  overlap: { type: 'string', description: 'the statement id it overlaps, or empty' },
  verdict: { type: 'string', description: 'the ledger vocabulary: overlap / related / background / not relevant' },
  note: { type: 'string' } },
  required: ['id', 'title', 'authors', 'url', 'date', 'overlap', 'verdict', 'note'] }
const FOUND = { type: 'object', properties: {
  ran: { type: 'array', items: { type: 'string' }, description: 'the pages and queries actually run, and how deep' },
  hits: { type: 'array', items: HIT } }, required: ['ran', 'hits'] }
const WROTE = { type: 'object', properties: {
  file: { type: 'string' }, files_after: { type: 'array', items: { type: 'string' } } }, required: ['file', 'files_after'] }

// ---- a one-statement prior-art search: one scout, as before -------------------------
if (A.statement) {
  const r = await agent(`Search for prior work on ${A.statement} for ${A.instance}, as your agent definition says, and write ` +
    `${LEDGER}<today>-<id-slug>.md. Report the queries run and the hits ranked by overlap.`, { label: `prior art ${A.statement}`, agentType: SCOUT })
  return { instance: A.instance, statement: A.statement, report: r }
}

// ---- Plan ---------------------------------------------------------------------------
phase('Plan')
const plan = await agent(`RETURN-ONLY stage of the literature watch for ${A.instance}: write nothing. ` +
  `Read ${LEDGER}_header.md in the library home and the search vocabulary (its ## Search vocabulary block, or the one under the watched home's .claude/rules/). ` +
  `If neither exists, return ok false with that reason. Otherwise return the window start (the newest watch-*.md, or 30 days ago), today, ` +
  `the file names now in ${LEDGER}, and every source: each arXiv category, keyword, author and anchor key, one entry each.`,
  { label: 'plan', phase: 'Plan', agentType: SCOUT, schema: PLAN, effort: 'low' })
if (!plan) return { instance: A.instance, reason: 'the plan stage returned nothing' }
if (!plan.ok) return { instance: A.instance, reason: plan.stop_reason }

// group the sources: categories together, anchors together, keywords (with the authors that narrow them) split evenly
const by = (k) => plan.sources.filter(s => s.kind === k).map(s => s.item)
const groups = []
if (by('category').length) groups.push({ name: 'categories', items: by('category').map(c => 'category ' + c) })
if (by('anchor').length) groups.push({ name: 'anchors', items: by('anchor').map(a => 'anchor ' + a) })
const kws = by('keyword'), authors = by('author')
const slots = Math.max(1, GROUPS - groups.length)
for (let g = 0; g < slots && g < kws.length; g++) {
  const items = kws.filter((_, i) => i % slots === g).map(k => 'keyword ' + k)
  groups.push({ name: `keywords ${g + 1}`, items: items.concat(authors.length ? ['authors to narrow a broad keyword: ' + authors.join(', ')] : []) })
}
if (!groups.length) return { instance: A.instance, reason: 'the vocabulary lists no source to search' }

// ---- Search: return-only, in parallel ---------------------------------------------------
phase('Search')
const found = await parallel(groups.map(g => () => agent(
  `RETURN-ONLY search for the literature watch of ${A.instance}: WRITE NOTHING (another stage writes the ledger). ` +
  `New listings only, since ${plan.window_start}. Run exactly these sources and say which pages and queries you read and how deep:\n- ` +
  g.items.join('\n- ') + `\nFor each candidate, give its arXiv id or DOI, the statement of ${A.instance} it overlaps (if any) and a verdict.`,
  { label: `search ${g.name}`, phase: 'Search', agentType: SCOUT, schema: FOUND })))

const lost = groups.filter((_, i) => !found[i]).map(g => g.name)
const norm = (id) => String(id || '').trim().toLowerCase().replace(/^arxiv:/, '').replace(/^https?:\/\/(dx\.)?doi\.org\//, '').replace(/v\d+$/, '')
const merged = new Map(), unkeyed = []
for (const f of found.filter(Boolean)) {
  for (const h of f.hits || []) {
    const k = norm(h.id)
    if (!k) { unkeyed.push(h); continue }
    const prev = merged.get(k)
    // keep the sharper verdict: an overlap beats a relation beats background
    const rank = (x) => ({ overlap: 0, related: 1, background: 2 }[String(x.verdict).toLowerCase()] ?? 3)
    if (!prev || rank(h) < rank(prev)) merged.set(k, Object.assign({}, h, { id: k }))
  }
}
const hits = [...merged.values(), ...unkeyed].sort((a, b) => (a.overlap ? 0 : 1) - (b.overlap ? 0 : 1))
const ran = found.filter(Boolean).flatMap(f => f.ran || [])
log(`${hits.length} distinct hit(s) from ${found.filter(Boolean).length}/${groups.length} search(es)`)

// ---- Record: exactly one writer ----------------------------------------------------------
phase('Record')
const file = `${LEDGER}watch-${plan.today}.md`
const w = await agent(
  `Write the literature watch file ${file} in the library home, in your ledger format, from exactly these results ` +
  `(window ${plan.window_start}..${plan.today}; a watch with no hits still gets its file):\n` +
  `Pages and queries run: ${JSON.stringify(ran)}\n` + (lost.length ? `Searches lost (say so in the file): ${lost.join(', ')}\n` : '') +
  `Hits (deduplicated): ${JSON.stringify(hits)}\nThen list the file names in ${LEDGER}.`,
  { label: 'record', phase: 'Record', agentType: SCOUT, schema: WROTE, effort: 'low' })
const before = new Set(plan.files_before || [])
const extra = w ? (w.files_after || []).filter(f => !before.has(f) && !file.endsWith(f)) : []
return { instance: A.instance, window: [plan.window_start, plan.today], file: w ? w.file : null,
         hits, ran, lost, anomalies: extra.length ? ['files written outside the Record stage: ' + extra.join(', ')] : [],
         cite_candidates: hits.filter(h => h.overlap || /^(overlap|related)$/i.test(h.verdict)) }
