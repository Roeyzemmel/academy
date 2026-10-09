---
name: status
description: 'Health of the academy as a whole: per instance, whether its home exists and .claude/academy.json is valid and matches workspace.json, plus ticket and packet counts. Use for "academy status", "is everything configured". Per role: /<role>:status.'
---

# Academy status

Scripts: `$S` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Read-only.

1. `py $S/academy_status.py --instances-only`: one line per instance, `ok` or `!!`
   with the problem.
2. `py $S/academy_status.py --since last`: needs-you, in-flight and came-back
   (without `--mark-visit`, so the desk's "since the last visit" is not moved).
3. Show both outputs as they are. For each `!!` line, name the fix in one line:
   - "no .claude/academy.json yet": the home is not switched over; `/academy:init`
     writes one (only on the human's word);
   - "config invalid": the problem is quoted from `validate_config`; the fields are
     in `docs/config.md`;
   - "differs from workspace.json": the two files must agree on role, domains and ns.

Fix nothing yourself here: this skill reports.
