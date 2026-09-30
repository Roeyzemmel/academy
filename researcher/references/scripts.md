# The Researcher plugin's scripts, as the skills call them

`$R` below is `${CLAUDE_PLUGIN_ROOT}/scripts` (this plugin); if the variable is not
expanded in the session, use `~/.claude/skills/researcher/scripts`. `$A` is the base
plugin's scripts, `~/.claude/skills/academy/scripts` (its commands are in
`academy/references/scripts.md`). Every script is stdlib Python run with `py`; set
`PYTHONIOENCODING=utf-8` when capturing output. Run them from the Researcher home, or
pass `--home`. Exit code 0 is success, 1 "nothing found", 2 an error with a one-line
message on stderr; a skill reports a non-zero exit as it is and does not retry.

| Script | Used by | Command lines |
|---|---|---|
| `notebook.py` | explore, prove, corollaries, status, academy:init | `ls [--kind K] [--status S] [--json]` · `direction ID [--json]` · `next ID [--n N] [--json]` · `new KIND ID --title T [--statement S] [--status open\|conjectured\|sketch] [--bears-on a,b] [--depends-on a,b] [--falsifier F] [--tags a,b] [--target ID] [--approach ID]` · `approach show ID [--json]` · `approach check [ID]` · `approach set ID active\|blocked\|delivered\|dropped [--blocked-by ID --reopen-if LINE] [--note WHAT] [--board DIR]` · `attempt ID [--create] [--by WHO]` · `journal [--date D] [--create]` · `scaffold HOME [--dry-run]` · `status [--json]` |
| `reviews.py` | review-experiment, settle, generalize, claims, status | `list SUBJECT [--json]` · `decide SUBJECT [--json]` · `pending [--json]` · `brief SUBJECT --run A\|B [--result R] [--ticket T] [--report P]` |
| `settle.py` | settle | `plan SUBJECT --candidates FILE [--max N] [--json]` · `decide SUBJECT --candidates FILE [--json]` · `record SUBJECT --candidates FILE [--partial]` |
| `generalize.py` | generalize | `source P-NNNN\|<lab-id> [--json]` · `validate FILE --lab-claim ID` · `create FILE --lab-claim ID [--apply]` · `tickets FILE --lab-claim ID --parent T-NNNN [--to I] [--as I] [--apply]` · `packet-body FILE --lab-claim ID --report P-NNNN --out PATH` |
| `inbox.py` | inbox | `[--instance I] [--n N] [--all] [--json] [--campaign T]` · `--check T-NNNN` (exit 3: unfinished); a wrapper over the academy's `inbox_core`, routes in `routes.py` |
| `status_guard.py` | hook, PreToolUse Edit\|Write\|MultiEdit | only claim-keeper or Roey changes a `status:` line in any registry record |
| `claims_edit_check.py` | hook, PostToolUse Edit\|Write\|MultiEdit | the registry engine's `check <file>` on an edited record, plus a blocking `build` where the profile asks (s1-kb); silent in a home whose legacy hook is still registered |
| `land_review.py` | hook, SubagentStop | lands an experiment-reviewer report as `audits/<lab-id>/<date>-<A\|B>.md` |

The base plugin's `board.py` and `packets.py` (under `$A`) file tickets and packets
from the main session: `board.py new` requires `--as <this instance>`, and the ticket
chain applies (`academy/references/scripts.md`). Agents use the MCP tools (`tickets_create`, `packets_create`) instead.

The MCP tools appear as `mcp__plugin_academy_academy__<tool>` when the base plugin's
`.mcp.json` loads, and as `mcp__academy__<tool>` when the server is registered with
`claude mcp add -s user academy` (the fallback); the agents list both.
