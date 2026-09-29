# Ticket Chain Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tickets between plugins may only go to a neighbour in `[author, expert, researcher, scientist]`, filed by a liaison of that direction, with four directional relay agents forwarding requests that must cross a middle plugin.

**Architecture:** One pure check, `ticket_edge_allowed`, in the shared lib `academy/lib/academy_common.py` (vendored into every plugin), configured by a new `tickets.edges` block in `academy/permissions.json`, and called from the two ticket-creation paths: the MCP tool `tickets_create` and `board.py new`. The main session inside a role home now *files* as that home (agent `main`); everything else about the main session stays human. A new ticket field `final_to` marks relay tickets; the Expert and Researcher inboxes route them to the directional relay agent.

**Tech Stack:** Python 3.10 standard library only (`py` on Windows), `unittest`, Claude Code plugin agent/skill markdown files.

**Spec:** `docs/superpowers/specs/2026-09-28-ticket-chain-gate-design.md` (read it first).

**Repo and branch:** the academy repo, worktree `C:\Work\Math\academy-ticket-chain-gate`, branch `ticket-chain-gate`. All paths below are relative to it. Run every command from it.

## Global Constraints

- Chain: `["author", "expert", "researcher", "scientist"]`; `maxHops: 3`.
- A ticket to or from `human` is always allowed; same role is always allowed.
- Liaisons per direction, exactly as spec section 4 (copied into Task 1's JSON).
- Exempt: `claim-keeper`, `usage-analyst`, `concierge`, and every `decision` ticket filed through `claims_propose_status`.
- The main session in a home files as `<home instance>` with agent `main`; outside every home it is `human`. Only `/academy:board`, `/academy:desk`, `/academy:decide` file as human from a home (`as_human` / `--as human`).
- Relays: `expert:research-intake` (sonnet), `expert:paper-liaison` (haiku), `researcher:experiment-spec` (sonnet), `researcher:lit-request` (haiku); no web, no shell.
- New ticket kinds `research` and `note`; new sender-owned field `final_to`.
- Standard library only; `py`, not `python`; `unittest`, not pytest.
- After any change to `academy/lib/academy_common.py`, run `py academy/scripts/sync_common.py` (the vendored copies must be byte-identical; `academy/tests/test_vendored.py` fails otherwise).
- MCP write-tool arguments are plain ASCII (non-ASCII breaks the caller handshake on Windows).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Hop limit vs ordinary `parent` links.** `report.py` files a review-experiment ticket with `parent` = the commissioning ticket, which may itself be the third hop of a relay chain. Expected: not refused. The limit counts only the consecutive ancestors that carry `final_to` (a refinement of spec 5.3, which assumed `parent` was used only by relays). Test in Task 1 (`test_hop_limit_counts_only_relay_ancestors`).
2. **Roey's main session in a role home loses nothing but the sender identity.** Re-routing `to`, any transition, and ticket updates must still work as human. Expected: only `tickets_create` changes. Test in Task 2 (`test_main_session_updates_stay_human`).
3. **`final_to` pointing backwards or at the receiver's own side** (for example author -> expert with `final_to: author`). Expected: refused with a reason. Test in Task 1 (`test_final_to_must_lie_beyond_to`).
4. **A script calling `board.py new` without `--as`**, which silently filed as human before. Expected: a clear error naming the flag. Test in Task 3 (`test_new_requires_as`).
5. **A `final_to` ticket reaching an inbox whose kind has a normal route** (a `cite` ticket with `final_to: expert` arriving at the Researcher). Expected: the relay route wins over the kind route. Test in Task 5 (`test_final_to_beats_kind`).

---

### Task 1: The shared check and its configuration

**Files:**
- Modify: `academy/lib/academy_common.py` (ticket constants near line 1022; new functions after `is_party` near line 1073; `validate_ticket` near line 1120)
- Modify: `academy/permissions.json` (`tickets` block)
- Test: `academy/tests/test_common.py` (new class `TicketEdgeTests` at the end)
- Regenerate: the five `*/scripts/_academy.py` via `sync_common.py`

**Interfaces:**
- Produces: `ac.MAIN_AGENT = "main"`, `ac.CHAIN_DEFAULT`, `ac.role_of(party, workspace=None) -> str|None`, `ac.ticket_edges(perms) -> dict`, `ac.relay_depth(board, parent) -> int`, `ac.ticket_edge_allowed(frm, to, agent, perms, workspace=None, final_to=None, depth=0, clerical=False) -> (bool, str)`. `TICKET_KINDS` gains `"research"`, `"note"`; `TICKET_FIELDS["sender"]` and `TICKET_KEY_ORDER` gain `"final_to"`.

- [ ] **Step 1: Write the failing tests** (append to `academy/tests/test_common.py`; it already imports `academy_common as ac`, `os`, `tempfile`, `unittest`; add any missing import)

```python
EDGE_PERMS = {
    "roster": {}, "tools": {},
    "tickets": {"edges": {
        "chain": ["author", "expert", "researcher", "scientist"],
        "maxHops": 3,
        "liaisons": {
            "author->expert": ["main", "math-writer", "notation-auditor", "figure-maker"],
            "expert->author": ["librarian", "review-chair", "research-intake", "paper-liaison"],
            "expert->researcher": ["research-intake", "review-chair"],
            "researcher->expert": ["main", "lead-researcher", "prover", "lit-request"],
            "researcher->scientist": ["main", "lead-researcher", "experiment-spec"],
            "scientist->researcher": ["main", "experimenter"]},
        "exempt": ["claim-keeper", "usage-analyst", "concierge"]}}}


class TicketEdgeTests(unittest.TestCase):
    def ok(self, frm, to, agent, **kw):
        return ac.ticket_edge_allowed(frm, to, agent, EDGE_PERMS, **kw)[0]

    def test_human_either_end(self):
        self.assertTrue(self.ok("human", "scientist@ts", ""))
        self.assertTrue(self.ok("author@bi", "human", "math-writer"))

    def test_same_role(self):
        self.assertTrue(self.ok("researcher@a", "researcher@b", "prover"))
        self.assertTrue(self.ok("expert@ts", "expert@ts", "clerk"))

    def test_neighbour_needs_liaison(self):
        self.assertTrue(self.ok("author@bi", "expert@ts", "math-writer"))
        self.assertTrue(self.ok("author@bi", "expert@ts", "main"))
        self.assertFalse(self.ok("author@bi", "expert@ts", "tex-engineer"))
        self.assertTrue(self.ok("researcher@s1", "scientist@ts", "lead-researcher"))
        self.assertFalse(self.ok("researcher@s1", "scientist@ts", "prover"))

    def test_directions_differ(self):
        self.assertTrue(self.ok("expert@ts", "researcher@s1", "research-intake"))
        self.assertFalse(self.ok("expert@ts", "researcher@s1", "paper-liaison"))
        self.assertTrue(self.ok("expert@ts", "author@bi", "paper-liaison"))

    def test_non_neighbour_refused_with_next_hop(self):
        ok, why = ac.ticket_edge_allowed("author@bi", "researcher@s1", "main", EDGE_PERMS)
        self.assertFalse(ok)
        self.assertIn("expert", why)
        self.assertIn("final_to researcher", why)
        ok, why = ac.ticket_edge_allowed("scientist@ts", "author@bi", "main", EDGE_PERMS)
        self.assertFalse(ok)
        self.assertIn("researcher", why)

    def test_exempt_and_clerical(self):
        self.assertTrue(self.ok("author@bi", "researcher@s1", "claim-keeper"))
        self.assertTrue(self.ok("author@bi", "researcher@s1", "math-editor", clerical=True))

    def test_final_to_must_lie_beyond_to(self):
        self.assertTrue(self.ok("author@bi", "expert@ts", "main", final_to="researcher"))
        self.assertTrue(self.ok("author@bi", "expert@ts", "main", final_to="scientist"))
        self.assertFalse(self.ok("author@bi", "expert@ts", "main", final_to="author"))
        self.assertFalse(self.ok("author@bi", "expert@ts", "main", final_to="nobody"))
        self.assertTrue(self.ok("scientist@ts", "researcher@s1", "main", final_to="author"))
        self.assertTrue(self.ok("human", "expert@ts", "", final_to="researcher"))

    def test_hop_limit(self):
        self.assertTrue(self.ok("researcher@s1", "scientist@ts", "experiment-spec",
                                final_to="scientist", depth=2))
        self.assertFalse(self.ok("researcher@s1", "scientist@ts", "experiment-spec",
                                 final_to="scientist", depth=3))

    def test_role_of(self):
        ws = {"instances": {"lab@x": {"role": "scientist"}}}
        self.assertEqual(ac.role_of("author@bi"), "author")
        self.assertEqual(ac.role_of("lab@x", ws), "scientist")
        self.assertIsNone(ac.role_of("human"))

    def test_defaults_without_edges_block(self):
        e = ac.ticket_edges({"roster": {}, "tools": {}})
        self.assertEqual(e["chain"], list(ac.CHAIN_DEFAULT))
        self.assertEqual(e["maxHops"], 3)

    def test_final_to_field_validated(self):
        meta = {"id": "T-0001", "title": "t", "kind": "research", "from": "author@bi",
                "to": "expert@ts", "status": "open", "ask": "a", "deliverable": "d",
                "priority": "normal", "budget": {"runs": 1, "max_model": "sonnet"},
                "created": "2026-09-28", "updated": "2026-09-28", "final_to": "researcher"}
        self.assertEqual(ac.validate_ticket(meta), [])
        meta["final_to"] = "nowhere"
        self.assertTrue(any("final_to" in p for p in ac.validate_ticket(meta)))
        meta["final_to"] = "researcher"
        meta["kind"] = "note"
        self.assertEqual(ac.validate_ticket(meta), [])

    def test_hop_limit_counts_only_relay_ancestors(self):
        board = tempfile.mkdtemp(prefix="edges-")
        def put(tid, parent, final_to):
            meta = {"id": tid, "title": "t", "kind": "other", "from": "author@bi",
                    "to": "expert@ts", "status": "open", "ask": "a", "deliverable": "d",
                    "priority": "normal", "budget": {"runs": 1, "max_model": "sonnet"},
                    "created": "2026-09-28", "updated": "2026-09-28",
                    "parent": parent, "final_to": final_to}
            os.makedirs(os.path.join(board, "expert@ts"), exist_ok=True)
            ac.atomic_write(os.path.join(board, "expert@ts", ac.ticket_filename(tid, "t")),
                            ac.new_ticket(meta))
        put("T-0001", None, "scientist")
        put("T-0002", "T-0001", "scientist")
        put("T-0003", "T-0002", "scientist")
        put("T-0004", "T-0003", None)          # the experiment's own ticket, no final_to
        self.assertEqual(ac.relay_depth(board, "T-0003"), 3)
        self.assertEqual(ac.relay_depth(board, "T-0004"), 0)
        self.assertEqual(ac.relay_depth(board, None), 0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -m unittest academy.tests.test_common -k TicketEdge` from the repo root; if module-style discovery fails, run `py -m unittest discover academy/tests -p test_common.py -k TicketEdge`.
Expected: errors `module 'academy_common' has no attribute 'ticket_edge_allowed'`.

- [ ] **Step 3: Implement in `academy/lib/academy_common.py`**

In the ticket constants:

```python
TICKET_KINDS = ("verify", "cite", "lookup", "prove", "review-experiment", "generalize",
                "experiment", "test", "code", "notation", "referee", "build", "figure",
                "decision", "question", "research", "note", "other")
```

In `TICKET_FIELDS["sender"]` append `"final_to"`; in `TICKET_KEY_ORDER` insert `"final_to"` right after `"parent"`.

After `is_party`:

```python
#: the ticket chain (docs/protocol.md section 5); permissions.json tickets.edges overrides
CHAIN_DEFAULT = ("author", "expert", "researcher", "scientist")
#: the agent name of a role skill running in the main session inside a home
MAIN_AGENT = "main"


def role_of(party, workspace=None):
    """The role of an instance name ('author@bi' -> 'author'); None for 'human'."""
    if not party or party == HUMAN:
        return None
    inst = (workspace or {}).get("instances", {}).get(party)
    if inst and inst.get("role"):
        return inst["role"]
    m = RE_INSTANCE.match(str(party))
    return m.group(1) if m else None


def ticket_edges(perms):
    """permissions.json tickets.edges with defaults: chain, maxHops, liaisons, exempt."""
    e = ((perms or {}).get("tickets") or {}).get("edges") or {}
    return {"chain": list(e.get("chain") or CHAIN_DEFAULT),
            "maxHops": int(e.get("maxHops", 3)),
            "liaisons": dict(e.get("liaisons") or {}),
            "exempt": list(e.get("exempt") or [])}


def relay_depth(board, parent):
    """How many consecutive ancestors, starting at ``parent``, carry ``final_to``.

    Only relay links count toward the hop limit; an ordinary ``parent`` (a review
    ticket filed against the ticket that commissioned the experiment) stops the count.
    """
    n, seen, tid = 0, set(), parent
    while tid and tid not in seen:
        seen.add(tid)
        path = find_ticket(board, tid)
        if not path:
            break
        with open(path, "r", encoding="utf-8") as fh:
            meta, _ = read_frontmatter(fh.read())
        if not meta.get("final_to"):
            break
        n += 1
        tid = meta.get("parent")
    return n


def ticket_edge_allowed(frm, to, agent, perms, workspace=None, final_to=None, depth=0,
                        clerical=False):
    """Whether ``agent`` of instance ``frm`` may file a ticket to ``to``.

    Rules (docs/protocol.md section 5): 'human' at either end is allowed; a clerical
    ticket or an exempt agent is allowed; the same role is allowed; otherwise the roles
    must be adjacent in the chain and ``agent`` a liaison of that direction.
    ``final_to`` (a role or instance) must lie beyond ``to`` as seen from ``frm``, and
    ``depth`` (relay_depth of the parent) + 1 may not exceed maxHops.
    Returns ``(allowed, reason)``.
    """
    edges = ticket_edges(perms)
    chain = edges["chain"]
    rf, rt = role_of(frm, workspace), role_of(to, workspace)
    if final_to:
        rF = final_to if final_to in chain else role_of(final_to, workspace)
        if rF not in chain:
            return False, "final_to must be a chain role or an instance, not %r" % final_to
        if rt is None:
            return False, "final_to needs a receiver with a role, not 'human'"
        if rF != rt and rf in chain and rt in chain:
            i, j, k = chain.index(rf), chain.index(rt), chain.index(rF)
            if not (min(i, k) < j < max(i, k)):
                return False, ("final_to %s does not lie beyond %s as seen from %s"
                               % (rF, rt, rf))
        if depth + 1 > edges["maxHops"]:
            return False, "the relay chain would exceed %d hops" % edges["maxHops"]
    if frm == HUMAN or to == HUMAN:
        return True, "human"
    if clerical or agent in edges["exempt"]:
        return True, "clerical"
    if rf == rt:
        return True, "same role"
    if rf not in chain or rt not in chain:
        return False, "unknown role for %r or %r" % (frm, to)
    i, j = chain.index(rf), chain.index(rt)
    if abs(i - j) != 1:
        step = chain[i + (1 if j > i else -1)]
        return False, ("%s may not file to %s: file to the %s with final_to %s; "
                       "its relay forwards it" % (rf, rt, step, rt))
    names = edges["liaisons"].get("%s->%s" % (rf, rt), [])
    who = agent or MAIN_AGENT
    if who in names:
        return True, "liaison"
    return False, ("%s is not a liaison for %s->%s (liaisons: %s)"
                   % (who, rf, rt, ", ".join(names) or "none"))
```

In `validate_ticket`, after the `parent` check:

```python
    ft = meta.get("final_to")
    if ft and ft not in ROLES and not RE_INSTANCE.match(str(ft)):
        probs.append("final_to must be a role or an instance name, not %r" % ft)
```

- [ ] **Step 4: Add the configuration to `academy/permissions.json`** inside `"tickets"` (next to `"fields"`), and extend the `about` text with one sentence: `"tickets.edges is the ticket chain: who may file to whom (docs/protocol.md section 5)."`

```json
    "edges": {
      "chain": ["author", "expert", "researcher", "scientist"],
      "maxHops": 3,
      "liaisons": {
        "author->expert": ["main", "math-writer", "notation-auditor", "figure-maker"],
        "expert->author": ["librarian", "review-chair", "research-intake", "paper-liaison"],
        "expert->researcher": ["research-intake", "review-chair"],
        "researcher->expert": ["main", "lead-researcher", "prover", "lit-request"],
        "researcher->scientist": ["main", "lead-researcher", "experiment-spec"],
        "scientist->researcher": ["main", "experimenter"]
      },
      "exempt": ["claim-keeper", "usage-analyst", "concierge"]
    },
```

Add `"final_to"` to `tickets.fields.sender`. Replace the `tickets_create` substance with: `"from is the caller's filing instance: an agent's home, the main session's home (agent main) unless as_human, which only /academy:board, desk and decide pass after Roey confirms; to must be a workspace instance or 'human'; the pair must pass tickets.edges (docs/protocol.md section 5); the server allocates id and dates and writes status open."`

- [ ] **Step 5: Sync and run**

Run: `py academy/scripts/sync_common.py` then `py -m unittest discover academy/tests`
Expected: all pass, including `TicketEdgeTests` and `test_vendored`. If a test comparing `TRANSITIONS`/`TICKET_FIELDS` with permissions.json fails, the `final_to` addition is missing on one side.

- [ ] **Step 6: Commit**

```bash
git add academy/lib/academy_common.py academy/permissions.json academy/tests/test_common.py */scripts/_academy.py
git commit -m "Ticket chain: ticket_edge_allowed, final_to, research/note kinds, tickets.edges

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The MCP tool files through the check; the main session files as its home

**Files:**
- Modify: `academy/mcp/tools/__init__.py` (`Context`: new method `filer`)
- Modify: `academy/mcp/tools/tickets.py` (`create_ticket`, tool schema near line 327)
- Modify: `academy/mcp/tools/claims.py` (`_propose`, near line 662)
- Test: `academy/tests/test_mcp.py` (new class `TestChainGate`; fix existing cases that now break)

**Interfaces:**
- Consumes: `ac.ticket_edge_allowed`, `ac.relay_depth`, `ac.MAIN_AGENT` (Task 1).
- Produces: `Context.filer(as_human=False) -> (instance, agent)`; `create_ticket(ctx, a, clerical=False)`; `tickets_create` accepts `final_to` (string) and `as_human` (boolean).

- [ ] **Step 1: Write the failing tests** (append to `academy/tests/test_mcp.py`; `self.server("author@t")` runs the server with its cwd in that instance's home, `self.server()` outside every home, `caller=None` is the main session)

```python
class TestChainGate(McpTestBase):
    def create(self, s, caller=None, **kw):
        args = dict(title="t", kind="question", ask="a", deliverable="d")
        args.update(kw)
        return s.call("tickets_create", caller=caller, **args)

    def test_main_session_in_a_home_files_as_the_home(self):
        err, t = self.create(self.server("author@t"), to="expert@t")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "author@t")
        err, g = self.server().call("tickets_get", id=t["id"])
        self.assertIn("author@t/main: opened", g["body"])

    def test_main_session_outside_homes_is_human(self):
        err, t = self.create(self.server(), to="scientist@t")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "human")

    def test_as_human_from_a_home(self):
        err, t = self.create(self.server("author@t"), to="scientist@t", as_human=True)
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "human")

    def test_as_human_refused_to_agents(self):
        err, msg = self.create(self.server("author@t"), caller="author:math-writer",
                               to="expert@t", as_human=True)
        self.assertTrue(err)
        self.assertIn("as_human", msg)

    def test_non_neighbour_refused(self):
        err, msg = self.create(self.server("author@t"), to="researcher@t", kind="prove")
        self.assertTrue(err)
        self.assertIn("final_to researcher", msg)

    def test_non_liaison_refused(self):
        err, msg = self.create(self.server("author@t"), caller="author:tex-engineer",
                               to="expert@t")
        self.assertTrue(err)
        self.assertIn("liaison", msg)

    def test_research_with_final_to(self):
        err, t = self.create(self.server("author@t"), to="expert@t", kind="research",
                             final_to="researcher")
        self.assertFalse(err, t)
        err, g = self.server().call("tickets_get", id=t["id"])
        self.assertEqual(g["meta"]["final_to"], "researcher")

    def test_propose_status_is_clerical(self):
        err, res = self.server("author@t").call(
            "claims_propose_status", caller="author:math-editor", id="paper:lem:x",
            status="proved", reason="r")
        # the claim may not exist in this fixture; the refusal must not be the chain's
        if err:
            self.assertNotIn("liaison", str(res))
            self.assertNotIn("may not file", str(res))

    def test_main_session_updates_stay_human(self):
        err, t = self.create(self.server("author@t"), to="expert@t")
        self.assertFalse(err, t)
        err, res = self.server("author@t").call("tickets_update", id=t["id"],
                                                fields={"to": "researcher@t"})
        self.assertFalse(err, res)            # only the human re-routes; still allowed
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -m unittest discover academy/tests -p test_mcp.py -k TestChainGate`
Expected: failures (`from` is `human`; the non-neighbour ticket is created).

- [ ] **Step 3: Implement**

`academy/mcp/tools/__init__.py`, in `Context` after `speaker`:

```python
    def filer(self, as_human=False):
        """``(instance, agent)`` a new ticket is filed as (docs/protocol.md section 5).

        An agent files as its instance. The main session files as the home it runs in,
        with agent ``main`` -- a role skill such as /author:next is its role -- unless
        ``as_human`` (only /academy:board, desk and decide pass it, after Roey
        confirms); outside every home it is the human.
        """
        if self.is_human:
            if as_human:
                return ac.HUMAN, ""
            name = self.home_instance()
            return (name, ac.MAIN_AGENT) if name else (ac.HUMAN, "")
        if as_human:
            raise ToolError("as_human is for the main session only (Roey's own tickets)")
        return self.instance, self.agent
```

Add one line to the module docstring: `A new ticket's sender comes from ctx.filer(): the main session inside a home files as that home (agent 'main').`

`academy/mcp/tools/tickets.py` `create_ticket`: change the signature to `def create_ticket(ctx, a, clerical=False):` and replace its first lines up to the `to` check with:

```python
    sender, agent = ctx.filer(bool(a.get("as_human")))
    if not sender:
        raise ToolError("agent %r runs outside every academy home; it cannot file tickets"
                        % ctx.agent)
    to = _one_line("to", a.get("to"))
    if to != ac.HUMAN and to not in ctx.instances():
        raise ToolError("to must be a workspace instance or 'human', got %r" % to)
    final_to = _one_line("final_to", a.get("final_to"), required=False)
    parent = a.get("parent") or None
    if parent and not ac.find_ticket(ctx.board, parent):
        raise ToolError("parent %s is not on the board" % parent)
    depth = ac.relay_depth(ctx.board, parent) if final_to and parent else 0
    ok, why = ac.ticket_edge_allowed(sender, to, agent, ctx.perms, ctx.workspace,
                                     final_to, depth, clerical=clerical)
    if not ok:
        raise ToolError("refused: " + why)
```

In `meta` set `"parent": parent,` and add `"final_to": final_to,` after it; delete the later duplicate `parent` existence check. Replace `speaker = ctx.speaker` with `speaker = ac.format_who(sender, agent)`.

Tool schema: add `"final_to": S, "as_human": B` to the `tickets_create` properties, and append to its description: `" A ticket must pass the chain (docs/protocol.md section 5): to a neighbouring role, by a liaison; final_to names the role a relay forwards it to."`

`academy/mcp/tools/claims.py` `_propose`: pass `clerical=True`: `return _tickets.create_ticket(ctx, {...}, clerical=True)`.

- [ ] **Step 4: Run the whole MCP suite and fix fallout**

Run: `py -m unittest discover academy/tests`
Expected: `TestChainGate` passes. Existing tests that now fail do so because a main-session call from `self.server("<inst>")` files as that instance, or because a test files a non-neighbour ticket. Fix each by the smallest change that keeps its intent: use `self.server()` (human, outside homes) when the test is about the human, or `as_human=True`, or file from a neighbouring role with a liaison agent (for example `caller="author:math-writer"` to `expert@t`). Do not weaken the new check.

- [ ] **Step 5: Commit**

```bash
git add academy/mcp academy/tests/test_mcp.py
git commit -m "tickets_create: the chain check, final_to, as_human; main session files as its home

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `board.py new` and the three scripts that call it

**Files:**
- Modify: `academy/scripts/board.py` (`create_ticket` near line 161; the `new` parser near line 301; module docstring)
- Modify: `author/scripts/next.py` (`ASK_ROUTES`, `DELIVERABLES`, `ticket_draft`, `file_ticket`, `TICKET_KIND_ROUTES`)
- Modify: `scientist/scripts/report.py` (near line 774)
- Modify: `researcher/scripts/generalize.py` (`ticket_commands`, near line 228)
- Test: `academy/tests/test_board.py`, `author/tests/test_next.py`, `researcher/tests/test_generalize.py`

**Interfaces:**
- Consumes: `ac.ticket_edge_allowed`, `ac.relay_depth`, `ac.MAIN_AGENT`, `ac.load_permissions`.
- Produces: `board.create_ticket(board, to, title, ask, deliverable, kind="other", priority="normal", refs=None, agenda=None, domain=None, parent=None, budget=None, detail="", as_instance=None, agent="", workspace=None, date=None, final_to=None, perms=None)`, which raises `ac.AcademyError` when `as_instance` is missing or the check refuses. The CLI `new` requires `--as` and takes `--final-to`.

- [ ] **Step 1: Write the failing tests**

In `academy/tests/test_board.py` (the class around line 99 has a helper `create` calling `bd.create_ticket(self.board, **args)`; make the helper default `as_instance` to `"human"` so the old tests keep their meaning), add:

```python
    def test_new_requires_as(self):
        with self.assertRaises(ac.AcademyError) as cm:
            bd.create_ticket(self.board, "expert@ts", "T", "a", "d", workspace=self.ws)
        self.assertIn("--as", str(cm.exception))

    def test_new_applies_the_chain(self):
        with self.assertRaises(ac.AcademyError) as cm:
            bd.create_ticket(self.board, "researcher@r1", "T", "a", "d",
                             as_instance="author@bi", workspace=self.ws)
        self.assertIn("final_to researcher", str(cm.exception))
        path = bd.create_ticket(self.board, "expert@ts", "T", "a", "d", kind="research",
                                as_instance="author@bi", workspace=self.ws,
                                final_to="researcher")
        meta, body = bd.read_ticket(path)
        self.assertEqual(meta["final_to"], "researcher")
        self.assertIn("author@bi/main: opened", body)
```

(`self.ws` is the loaded workspace from `make_workspace`; if the class stores it under another name, use that name. `bd.read_ticket` exists; line 140 calls it.)

In `author/tests/test_next.py`, next to `test_file_ticket_marks_the_item_ticketed`:

```python
    def test_lead_goes_to_the_expert_for_the_researcher(self):
        c = self.ctx()
        draft = nx.ticket_draft(c, c.roadmap.get("R-0006"))
        self.assertEqual((draft["to"], draft["kind"], draft["final_to"]),
                         ("expert@t", "research", "researcher"))
        self.assertEqual(draft["deliverable"], nx.DELIVERABLES["prove"])
```

In `researcher/tests/test_generalize.py`, assert the generated command carries the agent:

```python
    def test_ticket_commands_name_the_agent(self):
        cmds = gen.ticket_commands(
            [{"id": "s1:G-1", "statement": "s", "falsifier": "f"}],
            "lab:x", "T-0001", "scientist@ts", "researcher@slope1")
        self.assertIn("--agent", cmds[0])
        self.assertEqual(cmds[0][cmds[0].index("--agent") + 1], "main")
```

(Use the module alias the file already imports for `generalize.py`; if it is not `gen`, adapt.)

- [ ] **Step 2: Run to verify they fail**

Run: `py -m unittest discover academy/tests -p test_board.py`, `py -m unittest discover author/tests -p test_next.py`, `py -m unittest discover researcher/tests -p test_generalize.py`
Expected: the new tests fail (no error without `--as`; no `final_to` key; no `--agent`).

- [ ] **Step 3: Implement `board.py`**

In `create_ticket`: change the defaults to `as_instance=None` and add `final_to=None, perms=None` at the end of the signature. Replace `as_instance = as_instance or ac.HUMAN` with:

```python
    if not as_instance:
        raise ac.AcademyError("--as is required: the filing instance ('human' only from "
                              "/academy:board, desk or decide, after Roey confirms)")
```

After the two `_check_party` calls:

```python
    who = bare_agent(agent) or (ac.MAIN_AGENT if as_instance != ac.HUMAN else "")
    depth = ac.relay_depth(board, parent) if final_to and parent else 0
    ok, why = ac.ticket_edge_allowed(as_instance, to, who,
                                     perms if perms is not None else ac.load_permissions(),
                                     ws, final_to, depth)
    if not ok:
        raise ac.AcademyError("refused: " + why)
```

Add `"final_to": final_to,` to `meta` after `"parent": parent,`, and write the thread speaker with `ac.format_who(as_instance, who)`. In the `new` parser: `p.add_argument("--as", dest="as_instance", required=True)` and `p.add_argument("--final-to", dest="final_to")`; pass `final_to=args.final_to` where the CLI calls `create_ticket`. Update the docstring usage line for `new` to show `--as INSTANCE` as required and `[--final-to ROLE]`, and change the sentence about `--as` to: "`--as` names the caller's instance; `new` requires it (`--as human` only from /academy:board, desk and decide); for `transition` and `append`, without it the caller is the human."

- [ ] **Step 4: Implement the three callers**

`author/scripts/next.py`:

```python
ASK_ROUTES = {"lead": ("expert", "research"), "verify": ("expert", "verify"),
              "cite": ("expert", "cite"), "experiment": ("expert", "research"),
              "referee": ("expert", "referee")}
#: the role a relayed ask is really for (docs/protocol.md section 5)
FINAL_TO = {"lead": "researcher", "experiment": "scientist"}
#: the deliverable of a relayed ask is the final receiver's
DELIVERABLE_OF = {"lead": "prove", "experiment": "experiment"}
TICKET_KIND_ROUTES = {"build": "tex-engineer", "figure": "figure-maker",
                      "notation": "notation-auditor", "note": "math-writer"}
```

In `ticket_draft`: `"deliverable": DELIVERABLES[DELIVERABLE_OF.get(it.tag, kind)],` and add `"final_to": FINAL_TO.get(it.tag),` to the returned dict. In `file_ticket`, pass `agent=ac.MAIN_AGENT, final_to=draft.get("final_to")` to `bd.create_ticket`.

`scientist/scripts/report.py`: in the `boardlib.create_ticket(...)` call replace the `agent=` expression with `agent=(by.split("/", 1)[1] if "/" in by else ac.MAIN_AGENT)` (the module's lib alias is `ac` if it imports `_academy as ac`; otherwise use the literal `"main"`).

`researcher/scripts/generalize.py` `ticket_commands`: append `"--agent", "main"` after `"--as", as_instance`.

- [ ] **Step 5: Run all five suites**

Run: `py -m unittest discover academy/tests`, then the same for `author/tests`, `researcher/tests`, `scientist/tests`, `expert/tests`.
Expected: all pass. Fix any other test that calls `bd.create_ticket` without `as_instance` by passing the instance the test means (`"human"` when it means Roey).

- [ ] **Step 6: Commit**

```bash
git add academy/scripts/board.py academy/tests/test_board.py author/scripts/next.py author/tests/test_next.py scientist/scripts/report.py researcher/scripts/generalize.py researcher/tests/test_generalize.py
git commit -m "board.py new: --as required, the chain check, --final-to; next/report/generalize file as main

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `as_human` stays with the three academy skills

**Files:**
- Modify: `academy/skills/board/SKILL.md`, `academy/skills/desk/SKILL.md`, `academy/skills/decide/SKILL.md`
- Test: `academy/tests/test_interface_scripts.py` (new test class at the end)

**Interfaces:**
- Consumes: the `as_human` argument and `--as human` flag (Tasks 2 and 3).

- [ ] **Step 1: Write the failing lint test**

```python
class AsHumanLintTests(unittest.TestCase):
    ALLOWED = {os.path.join("academy", "skills", s, "SKILL.md")
               for s in ("board", "desk", "decide")}
    PATTERN = re.compile(r"as_human|--as\s+human")

    def test_only_board_desk_decide_file_as_human(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        bad, seen = [], set()
        for plugin in ("academy", "author", "expert", "researcher", "scientist"):
            for sub in ("skills", "agents", "scripts", "hooks"):
                root = os.path.join(repo, plugin, sub)
                for dp, _dn, fns in os.walk(root):
                    for fn in fns:
                        if not fn.endswith((".md", ".py", ".json")) or fn == "_academy.py":
                            continue
                        rel = os.path.relpath(os.path.join(dp, fn), repo)
                        with open(os.path.join(dp, fn), encoding="utf-8") as fh:
                            text = fh.read()
                        if self.PATTERN.search(text):
                            seen.add(rel)
                            if rel not in self.ALLOWED and rel != os.path.join(
                                    "academy", "scripts", "board.py"):
                                bad.append(rel)
        self.assertEqual(bad, [], "only /academy:board, desk and decide file as human")
        self.assertTrue(self.ALLOWED <= seen, "the three skills must say --as human")
```

(Add `import re` if missing. `board.py` is exempt because it documents the flag.)

- [ ] **Step 2: Run to verify it fails**

Run: `py -m unittest discover academy/tests -p test_interface_scripts.py -k AsHuman`
Expected: FAIL on `the three skills must say --as human` (and possibly on other files that currently pass `--as human`; fix those in step 3 by passing their instance).

- [ ] **Step 3: Edit the three skills**

In each of `board`, `desk` and `decide`, where the skill runs `board.py new`, make the command pass `--as human` explicitly, and add this sentence after the confirmation step: "File as the human (`--as human`) only after Roey confirmed this ticket through AskUserQuestion; this is the one sanctioned way to file as Roey from inside a home (docs/protocol.md section 5)." If `decide` files no new tickets, add the sentence where it records answers, naming `--as human` for any ticket it files.

- [ ] **Step 4: Run and commit**

Run: `py -m unittest discover academy/tests`
Expected: PASS.

```bash
git add academy/skills academy/tests/test_interface_scripts.py
git commit -m "Only /academy:board, desk and decide file as human; lint test

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The four relay agents and inbox routing on `final_to`

**Files:**
- Create: `expert/agents/research-intake.md`, `expert/agents/paper-liaison.md`, `researcher/agents/experiment-spec.md`, `researcher/agents/lit-request.md`
- Modify: `academy/permissions.json` (roster; `tickets_create` / `tickets_update` allow lists)
- Modify: `expert/scripts/inbox.py` (`ROUTES`, `route`), `researcher/scripts/inbox.py` (`route`)
- Modify: `expert/skills/inbox/SKILL.md`, `researcher/skills/inbox/SKILL.md` (route tables)
- Test: `expert/tests/test_plugin.py` (`PLAN`, route test), `researcher/tests/test_plugin.py` (`AGENTS`), `researcher/tests/test_notebook.py` (route test)

**Interfaces:**
- Consumes: the `final_to` field and the `research` / `note` kinds (Task 1).
- Produces: `expert/scripts/inbox.py` `route(meta)` returns `{"how": "agent", "target": "research-intake"|"paper-liaison", "why": ...}` for relay tickets; `researcher/scripts/inbox.py` `route(t)` returns `"experiment-spec"` or `"lit-request"`.

- [ ] **Step 1: Write the failing tests**

`expert/tests/test_plugin.py`: add to the `PLAN` dict `"research-intake": ("sonnet", "opus")` and `"paper-liaison": ("haiku", "sonnet")`; add both to `EFFORT` if the dict lists every agent (`"low"` for paper-liaison, `"medium"` for research-intake). Add to the inbox test class:

```python
    def test_final_to_beats_kind(self):
        import inbox
        r = inbox.route({"kind": "cite", "final_to": "researcher"})
        self.assertEqual((r["how"], r["target"]), ("agent", "research-intake"))
        r = inbox.route({"kind": "research", "final_to": "scientist"})
        self.assertEqual(r["target"], "research-intake")
        r = inbox.route({"kind": "question", "final_to": "author"})
        self.assertEqual(r["target"], "paper-liaison")
        r = inbox.route({"kind": "cite", "final_to": "expert"})
        self.assertEqual(r["target"], "expert:cite")          # final_to is the receiver
```

(Import `inbox` the way the existing route test at line 193 does.)

`researcher/tests/test_plugin.py`: add `"experiment-spec"` and `"lit-request"` to `AGENTS` with models sonnet and haiku in whatever structure the file uses. `researcher/tests/test_notebook.py`, next to `test_order_route_and_cap`:

```python
    def test_final_to_routes_to_the_relay(self):
        self.assertEqual(inbox.route({"kind": "research", "final_to": "scientist"}),
                         "experiment-spec")
        self.assertEqual(inbox.route({"kind": "cite", "final_to": "expert"}), "lit-request")
        self.assertEqual(inbox.route({"kind": "question", "final_to": "author"}),
                         "lit-request")
        self.assertEqual(inbox.route({"kind": "prove", "final_to": "researcher"}),
                         "/researcher:prove")
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -m unittest discover expert/tests` and `py -m unittest discover researcher/tests`
Expected: roster tests fail (agent files missing) and the route tests fail.

- [ ] **Step 3: Routing code**

`expert/scripts/inbox.py`:

```python
#: relay tickets (final_to beyond the Expert) go to the relay of their crossing
RELAYS = {"researcher": "research-intake", "scientist": "research-intake",
          "author": "paper-liaison"}


def _final_role(meta):
    ft = meta.get("final_to")
    return ac.role_of(ft) if ft and ft not in ac.ROLES else ft


def route(meta):
    final = _final_role(meta)
    if final and final != "expert" and final in RELAYS:
        return {"how": "agent", "target": RELAYS[final],
                "why": "relay toward %s: check, sharpen, forward (final_to)" % final}
    kind = meta.get("kind") or "other"
    ...                                   # the existing body, unchanged
```

Add `"note": ("human", "human", "a note is for the Author; block with waiting_on [human]")` to `ROUTES`. Add a `research` row only through `final_to`: a `research` ticket with no `final_to` falls to `BELONGS`; add `"research": "researcher"` there.

`researcher/scripts/inbox.py`:

```python
RELAYS = {"scientist": "experiment-spec", "expert": "lit-request", "author": "lit-request"}


def route(t):
    ft = t.get("final_to")
    final = ac.role_of(ft) if ft and ft not in ac.ROLES else ft
    if final and final != "researcher" and final in RELAYS:
        return RELAYS[final]
    return ROUTES.get(t.get("kind"), DEFAULT_ROUTE)
```

Add `"research": "lead-researcher"` to `ROUTES`.

- [ ] **Step 4: The agent files**

Model each on an existing agent of its plugin (`expert/agents/clerk.md` for the frontmatter keys: `name`, `description`, `tools`, `model`, `effort`, `fallback`, `maxTurns`, `skills`, `color`). The tools line for all four (both MCP spellings, as `clerk.md` does):

`Read, Grep, Glob, mcp__plugin_academy_academy__library_lookup, mcp__plugin_academy_academy__library_search, mcp__plugin_academy_academy__claims_show, mcp__plugin_academy_academy__claims_list, mcp__plugin_academy_academy__tickets_get, mcp__plugin_academy_academy__tickets_list, mcp__plugin_academy_academy__tickets_create, mcp__plugin_academy_academy__tickets_update, mcp__plugin_academy_academy__workspace_get, mcp__academy__library_lookup, mcp__academy__library_search, mcp__academy__claims_show, mcp__academy__claims_list, mcp__academy__tickets_get, mcp__academy__tickets_list, mcp__academy__tickets_create, mcp__academy__tickets_update, mcp__academy__workspace_get`

`experiment-spec` also gets `mcp__plugin_academy_academy__queue_status, mcp__academy__queue_status` (to see what the lab already ran).

Frontmatter values:

| agent | model | effort | fallback | maxTurns | skills |
|---|---|---|---|---|---|
| research-intake | sonnet | medium | opus | 20 | `[academy:citation-discipline, academy:status-vocabulary, academy:honest-reporting]` |
| paper-liaison | haiku | low | sonnet | 10 | `[academy:status-vocabulary, academy:honest-reporting]` |
| experiment-spec | sonnet | medium | opus | 20 | `[academy:status-vocabulary, academy:honest-reporting, scientist:experiment-method]` |
| lit-request | haiku | low | sonnet | 10 | `[academy:citation-discipline, academy:honest-reporting]` |

Descriptions (one sentence each, used for routing):

- research-intake: "The Expert's relay from the Author to the Researcher: takes one ticket whose final_to lies beyond the Expert, fails it fast (not pinned down, already answered by the library or the registry), otherwise writes the research block (cards with pinpoints, related claims with statuses, nearby known results, open literature questions) into a child ticket to the Researcher, and files notes of results the Author should know. Writes no mathematics, grades nothing, no web, no shell. Use only through /expert:inbox."
- paper-liaison: "The Expert's relay from the Researcher side to the Author: takes one ticket whose final_to is an Author, fails it fast when it concerns no paper claim or section, otherwise restates it in the paper's terms (claim id, section, what the Author must decide) as a child ticket to the Author. Use only through /expert:inbox."
- experiment-spec: "The Researcher's relay from the Expert to the Scientist: takes one ticket whose final_to is the Scientist, fails it fast (no claim named, or the lab already has a result for that claim and class), otherwise writes an exact experiment spec (claim id, kind search/measure/verify, class and bounds, what refutes the claim, a validation case, scope defaults) as a child ticket to the Scientist. Writes no code, grades nothing. Use only through /researcher:inbox."
- lit-request: "The Researcher's relay from the Scientist toward the Expert (and on to the Author): takes one ticket whose final_to lies beyond the Researcher, answers it from the library's read tools when they suffice, otherwise files a precise cite, literature or question ticket to the Expert with the claim's context. Use only through /researcher:inbox."

Body of each agent (adapt the check, sharpen and forward lines per spec section 5.2 for that agent):

```markdown
You relay one ticket one hop along the academy's chain (docs/protocol.md section 5).
You never write mathematics, never grade, never search the web, never ask a question.

## Steps

1. Read the ticket (`tickets_get`) and its parent, if any. Move it `accepted`, then
   `in-progress`.
2. **Fail fast.** <the agent's fail-fast conditions from spec 5.2>. If one holds, write
   the reason (and the answer, with its card or claim id, when the library or registry
   gave one) as `result` and `## Result`, and move the ticket `delivered`. Stop.
3. **Sharpen.** <what the agent adds, from spec 5.2>, written as the child's
   `ask_detail`, under the heading `## <Research block | Experiment spec | Request |
   For the paper>`.
4. **Forward.** `tickets_create` to the neighbour toward `final_to`, with `parent` set
   to this ticket, the same `final_to`, and a kind the receiver routes (`lead` does not
   exist: use `research` toward the Researcher, `experiment` toward the Scientist,
   `cite` or `question` toward the Expert, `question` or `note` toward the Author).
   Then move this ticket `blocked` with `waiting_on: [<child id>]`.
5. **When the child comes back delivered** (the inbox runs you again on this ticket):
   deliver this ticket with a one-line result pointing at the child and its packets.

A refusal from `tickets_create` is reported in the thread and the ticket goes
`blocked`, `waiting_on: [human]`; never retry around the chain.
```

research-intake additionally: "Results the Author should know go out as separate `note` tickets to the Author instance that sent the ticket, one per result, each with its card key and pinpoint."

- [ ] **Step 5: Permissions and skills**

`academy/permissions.json`: add `"research-intake", "paper-liaison"` to `roster.expert`, and `"experiment-spec", "lit-request"` to `roster.researcher`. Add all four to `tools.tickets_create.allow` and `tools.tickets_update.allow`. Do not add them to `@producers`.

`expert/skills/inbox/SKILL.md`: add rows to the route table:
`| research-intake | one research-intake run on the ticket; on a later run, when its child is delivered, the same agent delivers the parent |` and the same for `paper-liaison`. Add the kinds `note` (to the Author only) and `research` (relay) to the skill's description line.
`researcher/skills/inbox/SKILL.md`: in step 2, add "a ticket whose `final_to` lies beyond the Researcher to its relay (`experiment-spec` toward the Scientist, `lit-request` toward the Expert or the Author), whatever its kind; a `research` ticket without `final_to` to `lead-researcher`".

- [ ] **Step 6: Run and commit**

Run: `py -m unittest discover academy/tests`, and the same for `expert/tests`, `researcher/tests`.
Expected: PASS (including the roster and `test_mcp_tool_names_exist_on_the_server` checks on the new agents).

```bash
git add expert researcher academy/permissions.json
git commit -m "Four directional relays and inbox routing on final_to

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Reroute the flows that break the chain (agents, skills, references)

**Files:**
- Modify: `author/skills/next/references/routing.md`, `author/agents/math-writer.md`, `author/agents/figure-maker.md`
- Modify: `researcher/agents/prover.md`, `researcher/agents/lead-researcher.md`
- Modify: `expert/skills/verify/references/conclude.md`, `expert/agents/review-chair.md`, `expert/skills/domain/SKILL.md`
- Modify: `scientist/skills/examples-audit/SKILL.md`, `academy/skills/citation-discipline/SKILL.md`
- Test: `academy/tests/test_interface_scripts.py` (a content test)

**Interfaces:**
- Consumes: the rule, the `research` kind and `final_to` (Tasks 1-5).

- [ ] **Step 1: Write the failing content test**

```python
class ChainDocsTests(unittest.TestCase):
    """No skill or agent tells a role to file to a non-neighbour."""
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    CASES = {
        os.path.join("author", "agents", "math-writer.md"): "final_to",
        os.path.join("author", "agents", "figure-maker.md"): "final_to",
        os.path.join("author", "skills", "next", "references", "routing.md"): "final_to",
        os.path.join("expert", "skills", "verify", "references", "conclude.md"): "final_to",
        os.path.join("expert", "agents", "review-chair.md"): "final_to",
        os.path.join("scientist", "skills", "examples-audit", "SKILL.md"): "final_to",
        os.path.join("academy", "skills", "citation-discipline", "SKILL.md"): "neighbour",
    }

    def test_rerouted_docs_mention_the_relay(self):
        for rel, word in self.CASES.items():
            with open(os.path.join(self.REPO, rel), encoding="utf-8") as fh:
                self.assertIn(word, fh.read(), rel)

    def test_prover_no_longer_files_experiments(self):
        with open(os.path.join(self.REPO, "researcher", "agents", "prover.md"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotRegex(text, r"(?i)ticket[^.\n]*to (the )?scientist")
```

- [ ] **Step 2: Run to verify it fails**

Run: `py -m unittest discover academy/tests -p test_interface_scripts.py -k ChainDocs`
Expected: FAIL.

- [ ] **Step 3: Edit each file** (each edit replaces the old route with the new one in the file's own voice)

- `author/skills/next/references/routing.md`: `[lead]` becomes "a `research` ticket to the Expert with `final_to: researcher` (research-intake prepares it)", and `[experiment]` becomes "a `research` ticket to the Expert with `final_to: scientist`". Add a line: "Delivered `note` tickets from the Expert land with math-writer as roadmap items."
- `author/agents/math-writer.md` (near line 35): a new argument becomes "a `research` ticket to the Expert with `final_to: researcher`", not a prove ticket to the Researcher.
- `author/agents/figure-maker.md` (near line 27): computed data comes from "a `research` ticket to the Expert with `final_to: scientist`".
- `researcher/agents/prover.md` (near line 56): remove filing experiment or test tickets. Replace with "Ask lead-researcher for an experiment; it files the spec to the Scientist."
- `researcher/agents/lead-researcher.md` (near line 40): state that it is the Researcher's liaison to the Scientist, and that a request from the Expert with `final_to: scientist` is handled by experiment-spec, not by it.
- `expert/skills/verify/references/conclude.md` (near lines 106-110) and `expert/agents/review-chair.md` (near line 61): a repair or verify-input ticket for a `lab:` claim goes "to the Researcher with `final_to: scientist`". A `paper:` claim still goes to the Author (a neighbour), and an `s1:`-type claim to its Researcher.
- `expert/skills/domain/SKILL.md` (line 3, description): "a Scientist's api-prober routes a pack change here" becomes "a Scientist's pack change arrives through the Researcher (`final_to: expert`)".
- `scientist/skills/examples-audit/SKILL.md` (near line 61): a question to an Author instance goes "to the Researcher with `final_to: author`". A question to a Researcher is unchanged.
- `academy/skills/citation-discipline/SKILL.md` (line 22): "file a `cite` ticket to Expert" becomes "file a `cite` ticket to the Expert if it is your neighbour (Author, Researcher). The Scientist files it to the Researcher with `final_to: expert`".

- [ ] **Step 4: Run and commit**

Run: all five suites (`py -m unittest discover <plugin>/tests` for academy, author, expert, researcher, scientist).
Expected: PASS.

```bash
git add author expert researcher scientist academy/skills academy/tests/test_interface_scripts.py
git commit -m "Reroute the non-neighbour flows through the relays

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The protocol and role documentation

**Files:**
- Modify: `docs/protocol.md` (§1 near line 8, §3 kind table near lines 184-202, §5 near line 318, §6 near line 334)
- Modify: `docs/roles.md`, `expert/README.md`, `researcher/README.md` (agent lists), `README.md` only if it lists agents

- [ ] **Step 1: Edit `docs/protocol.md`**

- §1 Parties: add "The main session inside a role home files tickets as that home's instance, speaker `<instance>/main`. Only `/academy:board`, `/academy:desk` and `/academy:decide` file as `human` from a home (`--as human` / `as_human`), after Roey confirms. Every other write by the main session is still the human's."
- §3: rename the "Typical route" column to "Route (required)". Add rows for `research` (Author -> Expert, relayed with `final_to`) and `note` (Expert -> Author, informational). Add the field `final_to` to the frontmatter schema: "sender-owned, optional; the role (or instance) the request is really for; set on relayed tickets; a receiver whose role is not `final_to` hands the ticket to its relay".
- §5: add a subsection "5.1 The ticket chain" with the rule from spec section 2, the liaison table from spec section 4, the relays table from spec section 5, the hop limit (counting only ancestors that carry `final_to`), and the exemptions. Point to `permissions.json` `tickets.edges` as the source of truth.
- §6: add "6.4 A research request from the Author": Author -> `research`, `final_to: researcher` -> Expert (research-intake: fail fast or research block) -> Researcher `lead` work -> delivered back up hop by hop. Add "6.5 An experiment for the paper": Author -> Expert -> Researcher (experiment-spec) -> Scientist.

- [ ] **Step 2: Edit the role docs**

`docs/roles.md`: under each role, one line naming its liaisons per direction and, for Expert and Researcher, their relays. Add the two new agents to the agent lists in `expert/README.md` and `researcher/README.md`, with one line each and the model.

- [ ] **Step 3: Check and commit**

Run: `py -m unittest discover academy/tests` (some tests read protocol.md; they must still pass).

```bash
git add docs README.md expert/README.md researcher/README.md
git commit -m "Protocol: the ticket chain, final_to, research and note kinds, relays

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Whole-branch verification

- [ ] **Step 1:** `py academy/scripts/sync_common.py --check`. Expected: no drift.
- [ ] **Step 2:** Run every suite: `py -m unittest discover academy/tests`, `author/tests`, `expert/tests`, `researcher/tests`, `scientist/tests`. Expected: all PASS; report the counts.
- [ ] **Step 3:** Grep for leftovers: `grep -rn "\"lead\": (\"researcher\"" author/` and `grep -rn "to the Scientist" researcher/agents/prover.md`. Expected: nothing.
- [ ] **Step 4:** Live board check (read-only): `py academy/scripts/board.py list --json` against the real board, and confirm that open tickets which now violate the chain are listed for Roey. The change does not rewrite existing tickets; the report names each one with its sender and receiver so Roey can re-route or cancel it.
- [ ] **Step 5:** Hand off with superpowers:finishing-a-development-branch (merge-locally or keep only; merging to `main` is Roey's).
