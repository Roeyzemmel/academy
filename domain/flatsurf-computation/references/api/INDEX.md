# API recipes: index

sage-flatsurf 0.8.0, surface_dynamics 0.7.0, SageMath 10.7. Read the **one file** you
need, never the whole set. Section numbers (§) are those of the old single
`api-recipes.md`, so older citations still resolve here.

| File | § | Read it when |
|---|---|---|
| `setup.md` | 1, 12 intro, 12.1, 12.3, 12.4 | installing, importing, a crash on import; pyflatsurf / cling segfaults |
| `surfaces.md` | 2, 3 | building a surface from polygons, strata, GL(2,R) action, Delaunay, equality; unfolding a billiard |
| `saddle-connections.md` | 4 | saddle connections, holonomy vectors, straight-line flow |
| `cylinders.md` | 5 | cylinder / flow decompositions, moduli |
| `origamis.md` | 6, 12.5 | strata, `Origami`, Veech groups, `origamis.*` generators, index base |
| `libgap.md` | 12.2, 12.6, 12.7, 12.8 | any `libgap` call: import order, orbits, blocks, `RepresentativeAction`, multi-statement GAP functions; import timing on lingo (12.7.5) |
| `illumination.md` | 7 | does p illuminate q; the end-to-end recipes |
| `pure-python.md` | 8 | no Sage available |
| `practice.md` | 9 | what a computation can establish; float vs exact; ranked pitfalls |
| `quick-reference.md` | 10, 11 | removed API not to use; the one-page card. **Before writing any call** |
| `sources.md` | — | upstream doc links; the file's original status note (2026-09-08) |

The tags **[VERIFIED-DOC]** (in upstream docs), **[VERIFIED]** / **Confirmed** (run
here) and **[UNVERIFIED]** keep their meaning; `sources.md` defines them.

**One copy.** This directory is in git (`claude-flatsurf/domain/flatsurf-computation`),
reached through `~/.claude/skills/flatsurf-computation`. The claude.ai-synced copy under
`~/.claude/skills/synced/` is obsolete (a strict subset; its §6 ends at 6.6 and it has
no §12); the "two copies" warning in §12.7 is historical.

**Writing.** A new finding goes in the topic file it belongs to, as the next number in
that file's section (e.g. `### 6.8`, `#### 12.7.7`), never a new top-level file without
a row here. A refutation goes beside the entry it refutes. Writers: `flatsurf:api-prober`,
`/flatsurf:api-check`.
