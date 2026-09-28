---
name: deep-dive
description: Build an explainer page for any subject — a concept, a definition, a claim with its proof, a paper (ours or a cited one), an experiment with its result, or a research direction — gathered from the registry, the library and the lab by script, written by the read-only explainer agent with the status of every statement shown, rendered with KaTeX, and published as a private artifact that is updated in place on every re-run. Use for "explain X", "walk me through", "deep dive on", "give me an overview of", "what is the story of this lemma / paper / experiment", and when the desk routes an explain request here.
---

# Deep-dive

`$ARGUMENTS` is the subject: `<ns>:<id>` (a registry object), `bib:<key>[#pinpoint]`
(a paper), a result path or `file:<instance>/<path>` (an experiment),
`concept:<term>`, optionally followed by `--kind concept|claim|paper|experiment|direction`.
Scripts: `$S` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. One subject per run
(`references/budget.md`).

1. **Id.** `ID=$(py $S/deep_dive_index.py id "<subject>")`. Board: `workspace.json`
   `board`.
2. **Gather** (read-only): `py $S/gather_deep_dive.py "<subject>" [--kind K] --out
   <board>/.render/$ID.bundle.json`. If its `notes` say the subject was not found,
   report that and stop.
3. **Explain.** Dispatch one `explainer` subagent with only: the bundle path, the
   output path `<board>/deep-dives/$ID.json`, and Roey's question if he asked one. It
   writes the bundle back with its `sections` added and returns a short report. On a
   limit error or an empty result, stop and report (no relaunch).
4. **Render.** `py $S/render_packets.py --deep-dive <board>/deep-dives/$ID.json --out
   <board>/deep-dives/$ID.html`. The script refuses (exit 2) a bundle with a
   statement or a `[[ns:id]]` chip that carries no status; report any non-zero exit
   as it is and do not publish.
5. **Check** the explainer's report: if it names a statement presented above its
   registry status, report that and do not publish.
6. **Publish** `<board>/deep-dives/$ID.html` with the `Artifact` tool, private. If
   `py $S/deep_dive_index.py get $ID` prints a URL, publish to that URL (read it
   first when this conversation has not published it), so a re-run updates the same
   artifact. Otherwise publish new, with a short title and icon `book`.
7. **Record** `py $S/deep_dive_index.py set $ID --url <url> --kind <kind> --title
   "<title>" --subject "<subject>"`, then give Roey the link and the explainer's
   one-line summary, including anything it could not find.

The explainer grades nothing and edits no home. A deep-dive is never evidence for a
status (`references/roster-rules.md`).
