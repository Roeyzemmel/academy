# `flatsurf` — the experiment workflow for translation-surface research

The domain layer shared by three repos: `FlatSurfLab` (the computations),
`BilliardIllumination` (the paper) and `Slope1illuminationResearch` (the (Q2) research
database). It carries what used to be copied between their `.claude/` directories: the
experiment gate, the lingo queue, API checks, result audits, and the claim registry.

Installed as a skills-directory plugin: the directory is linked at
`~/.claude/skills/flatsurf`, so it loads in every project as `flatsurf@skills-dir` with no
marketplace and no install step. Skills are namespaced: `/flatsurf:experiment`,
`/flatsurf:queue`. Agents are `flatsurf:api-prober`, `flatsurf:result-auditor`,
`flatsurf:claim-keeper`. Changes to a `SKILL.md` take effect immediately; changes to
`agents/` or `hooks/` need `/reload-plugins` or a restart.

## What is here and what is not

| Here | Stays in the repos |
|---|---|
| generic flatsurf habits: design before compute, the queue, API checks, audits, claim bookkeeping | the tools: `FlatSurfLab/scripts/{queue.ps1,run.ps1,claims.py,check_experiments.py}`, `fslab/`, Slope1's `tools/kb.py` |
| agents `api-prober`, `result-auditor`, `claim-keeper` | domain agents: Slope1's `family-*`, `refutation-verifier`, `claim-verifier`, `status-keeper`, `librarian`; BI's `experimenter` |
| skills `experiment`, `queue`, `api-check`, `verify-result`, `claims` | Slope1's `/hunt`, `/settle`, `/classify`, `/verify-claim`, `/kb`; BI's `/roadmap`, `/audit-examples` |
| hooks: the experiment-header check and commit gate (FlatSurfLab only), the claim-file check | each repo's `CLAUDE.md` and `.claude/rules/` |
| `references/sage-review.md`, the Sage/flatsurf review checklist | `FlatSurfLab/docs/` (queue, API traps, claims format) |

**No generic coding habits here.** Design-before-building, root-cause-first, TDD and
verification-before-completion come from the `superpowers` plugin, enabled in FlatSurfLab
only; BilliardIllumination and Slope1 carry their own disciplines (`paper`'s verifier
roster; Slope1's `/settle`). The skills here hand off to superpowers where it is enabled
rather than restate it. The research-specific pieces of the retired `rigor` plugin
(2026-09-24; kept at `~/.claude/skills-retired/rigor`) live here:
`/flatsurf:experiment` step 0 (two-line argument / probe / experiment, a probe naming its
question first) and the rule that **a surprising result is a bug until shown otherwise**
(`experiment`, `verify-result`, `queue`).

**`domain/`: the four domain skills**, `flatsurf-computation`, `translation-surfaces`,
`math-proof-writing` and `latex-paper-writing`. They sit outside `skills/`, so the plugin
does not load them. Each one loads as a bare skill through a junction
`~/.claude/skills/<name>` → `domain/<name>`. This is the only copy: none is kept on
claude.ai, so edit them here and commit.

## The per-repo contract: `.claude/flatsurf.json`

Every skill and agent reads this file first; nothing here hard-codes a repo path.

```json
{
  "lab": "../FlatSurfLab",
  "registry": {
    "tool": "claims.py",
    "cmd": "py ..\\FlatSurfLab\\scripts\\claims.py --repo .",
    "setStatus": "flatsurf:claim-keeper"
  },
  "settle": "/flatsurf:verify-result",
  "knownCases": "the square torus, the 3-square L in H(2), the Eierlegende Wollmilchsau, the double pentagon",
  "notes": []
}
```

| Key | Meaning |
|---|---|
| `lab` | path from the repo root to FlatSurfLab (`"."` inside it). Every `scripts\…` command runs there: prefix `cd <lab>;` when the session is elsewhere |
| `registry.tool` | `claims.py` (FlatSurfLab, BI) or `kb.py` (Slope1) |
| `registry.cmd` | how to invoke it from this repo's root |
| `registry.setStatus` | who changes a status: `flatsurf:claim-keeper` for `claims.py`, or the repo's own route (Slope1: `py tools/kb.py set-status`, through its `status-keeper`) |
| `settle` | the pass a returned result goes through before anything is recorded |
| `knownCases` | the independently known cases this repo validates against |
| `notes` | anything repo-specific an agent here must know (e.g. Slope1's hypothesis names) |

A repo without the file gets a one-line refusal from every skill here: "no
`.claude/flatsurf.json`; this repo is not set up for the flatsurf workflow".

## The registries

Federated (FlatSurfLab `docs/claims.md`): `lab:` lives in FlatSurfLab, `paper:` in BI's
`claims/paper/`, `s1:` in Slope1's kb. `claims.py` resolves links across all three.
Status changes need grounds: a cleared result (two `SOUND` audits), a double verifier
sign-off, or Roey's word. In a `claims.py` registry `flatsurf:claim-keeper` makes them;
in Slope1, `kb.py set-status` does, and this plugin does not touch it.

## Standing rules for every agent here

1. **Experiments never run on the laptop.** WSL Sage is for unit tests and one-line API
   checks. Every run goes through the queue to lingo.
2. **A connection timeout means the VPN is down.** Only Roey connects it. Say so and stop.
3. **Results are "no counterexample below bound B over class C"**, never "true", with what
   the class structurally could not contain.
4. **Whoever produced a result never audits it**, and an audit is two independent runs.
5. **Roey commits experiment scripts** that go to the queue, and merges to `main`.

## Models

| Agent | Model / effort | Fallback |
|---|---|---|
| `result-auditor` | fable / xhigh | opus 5.5 counts as an **equal primary** for clearing (Roey, 2026-09-24); any other fallback is PLAUSIBLE only |
| `api-prober` | sonnet / medium | opus |
| `claim-keeper` | sonnet / medium | opus |
