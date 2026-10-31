# Eval suites: the judgement calls the workflow scripts cannot check

The workflows hold the academy's sequencing in code (`docs/workflows.md`); what is left to a
model is a decision: a relay's fail-fast or forward, the clerk's escalation, the
usage-analyst's proposals. These cases pin those decisions with `claude plugin eval`
(https://code.claude.com/docs/en/plugin-evals.md).

The suites live here, at the marketplace root, not inside one plugin, because each case
loads two plugins (`plugins:` in `prompt.md`): the role plugin whose agent is under test and
`academy`, whose MCP server it calls. A case may load only plugins under the directory the
run targets, so run from the repo root with `--eval-dir evals`:

    claude plugin eval . --eval-dir evals --trust-plugin --no-publish --ablation none --max-cost-usd 5
    claude plugin eval . --eval-dir evals --case 'research-intake-*' --runs 1 --ablation none --trust-plugin

The academy server is mocked per case (`<case>/mocks/academy/<tool>.md`); its real tool
schemas are `mocks/academy/_tools.json`, written by `python3 evals/dump_tools.py` (rerun it
after changing a tool). The cases set `EVAL_ACADEMY_ALLOW_LAUNCH=1`, the eval form of the
human's opt-out of the launch guards. `results/` is local (gitignored). Each case costs
about $0.10 per run.
