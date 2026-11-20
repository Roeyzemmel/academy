"""No clerk stage of a workflow requires a free-text field (#124).

A schema's ``required`` list is enforced by StructuredOutput: an agent that leaves a
required property out fails the stage and the run is lost. The ledger counted 23 runs of
``academy:inbox-clerk`` lost to "must have required property 'detail'" and 22 of
``researcher:review-clerk`` to 'attack_exists' (board/.errors, since 2026-11-14). A clerk
stage reads its answer in code, so a free-text field (a reason, an error line, a detail)
is asked for and never required; the code says 'no reason given' when it is missing.

This test reads every ``*/workflows/*.js`` statically: the schema constants, the stages
launched with a clerk agentType (directly, through a helper such as ``clerk(...)``, or
through ``launchModel``/``ship``'s ``s.agentType``, which is always a clerk), and the
``required`` lists of each schema and the schemas it nests. It fails on a clerk schema
that requires a free-text field, except those in ``ALLOWED`` (handled elsewhere) and an
``output`` the code parses (``OUTPUT_READ``).
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Free-text fields: a clerk that omits one must not lose its run.
FREE = ("detail", "why", "error", "reason", "stop_reason", "refusal")
# 'output' is free text when the code only shows it; where the code parses it (a command's
# verbatim output read line by line), it is the answer itself and stays required.
OUTPUT_READ = {
    ("academy/workflows/inbox.js", "CHECK"): "readCheck parses the inbox.py --check output",
    ("academy/workflows/inbox.js", "REG"): "REG_OUTPUT_PLACEHOLDER",
    ("academy/workflows/workplan.js", "MODEL_OUT"): "launchModel parses the model line",
    ("expert/workflows/referee.js", "MODEL_OUT"): "launchModel parses the model line",
    ("researcher/workflows/generalize.js", "MODEL_OUT"): "launchModel parses the model line",
    ("researcher/workflows/prove.js", "MODEL_OUT"): "launchModel parses the model line",
    ("researcher/workflows/review-experiment.js", "MODEL_OUT"): "launchModel parses the model line",
}
# the shared Ship block parses inbox.py --check's output (ship() reads the ticket's state and
# the repos from it), in every workflow that ships
SHIPPING = ("expert/workflows/cite.js", "expert/workflows/verify.js", "expert/workflows/referee.js",
            "expert/workflows/domain.js", "researcher/workflows/prove.js", "researcher/workflows/explore.js",
            "researcher/workflows/generalize.js", "researcher/workflows/review-experiment.js",
            "scientist/workflows/experiment.js")
OUTPUT_READ.update({(f, "SHIP"): "ship() parses the --check output" for f in SHIPPING})
OUTPUT_READ.update({
    ("expert/workflows/verify.js", "MODEL_OUT"): "launchModel parses the model line",
    ("researcher/workflows/explore.js", "REG"): "the prove step reads registry.py statement's output",
})
# Out of this test's reach, each handled by its own change (#124 follow-ups run in parallel):
ALLOWED_FILES = {}         # explore.js, verify.js and maintain.js were fixed on their own branches (2026-11-20)
ALLOWED_SCHEMAS = {}       # SHIP was the last (2026-11-20): it now requires only status and output
CLERK_TYPE = re.compile(r"^[a-z]+:[a-z-]*(clerk|review-chair)$")
# Clerical stage agents not named a clerk: their stages run a script and return its answer.
CLERK_LIKE = {"academy:usage-analyst": "its agent file says 'Clerical'; weekly.js's three stages run scripts"}
SCHEMA_CONST = re.compile(r"^[ \t]*const ([A-Z][A-Z0-9_]*) = \{", re.M)
REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^")


def is_clerk_type(name):
    return bool(CLERK_TYPE.match(name)) or name in CLERK_LIKE


def mask(src):
    """The source with every string, template literal, comment and regex literal blanked
    to spaces (same length, newlines kept), so brackets can be matched on it."""
    out = list(src)
    n = len(src)

    def prev_sig(i):
        k = i - 1
        while k >= 0 and src[k] in " \t\r\n":
            k -= 1
        return src[k] if k >= 0 else ""

    def literal_end(i):
        """The index after the literal or comment starting at i, or None if none starts there."""
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            return n if j < 0 else j
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            return n if j < 0 else j + 2
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            return j + 1
        if c == "`":
            j = i + 1
            while j < n and src[j] != "`":
                if src[j] == "\\":
                    j += 2
                elif src.startswith("${", j):
                    j = code_end(j + 2)
                else:
                    j += 1
            return j + 1
        if c == "/" and prev_sig(i) in REGEX_BEFORE | {""}:
            j, cls = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    cls = True
                elif src[j] == "]":
                    cls = False
                elif src[j] == "/" and not cls:
                    break
                j += 1
            j += 1
            while j < n and src[j].isalpha():         # flags
                j += 1
            return j
        return None

    def code_end(j):
        """Inside ${...}: the index after its closing brace."""
        depth = 0
        while j < n:
            e = literal_end(j)
            if e is not None:
                j = e
                continue
            c = src[j]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    return j + 1
                depth -= 1
            j += 1
        return j

    i = 0
    while i < n:
        e = literal_end(i)
        if e is None:
            i += 1
            continue
        for k in range(i, min(e, n)):
            if out[k] != "\n":
                out[k] = " "
        i = e
    return "".join(out)


def match(m, i):
    """Index after the bracket matching the one at m[i]."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    for j in range(i, len(m)):
        c = m[j]
        if c in pairs:
            stack.append(pairs[c])
        elif c in ")]}":
            if not stack or stack.pop() != c:
                raise ValueError(f"unbalanced {c!r} at {j}")
            if not stack:
                return j + 1
    raise ValueError(f"no match for {m[i]!r} at {i}")


def enclosing(m, i, opener="{"):
    """Start index of the innermost unclosed `opener` before i."""
    close = {"{": "}", "(": ")", "[": "]"}[opener]
    depth = 0
    for j in range(i - 1, -1, -1):
        c = m[j]
        if c == close:
            depth += 1
        elif c == opener:
            if depth == 0:
                return j
            depth -= 1
    return -1


def top_level(m, a, b):
    """The (key, value-span) pairs at depth 0 of the object literal m[a:b] (a at '{')."""
    items, depth, start = [], 0, a + 1
    for j in range(a + 1, b - 1):
        c = m[j]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            items.append((start, j))
            start = j + 1
    items.append((start, b - 1))
    return items


class Workflow:
    def __init__(self, rel, src):
        self.rel, self.src, self.m = rel, src, mask(src)
        self.schemas = {}                                    # name -> (start, end)
        for mo in SCHEMA_CONST.finditer(self.m):
            a = mo.end() - 1
            self.schemas[mo.group(1)] = (a, match(self.m, a))
        self.clerk_consts = set()
        for mo in re.finditer(r"^const ([A-Z][A-Z0-9_]*) = (.*)$", src, re.M):
            if any(is_clerk_type(s) for s in re.findall(r"'([^']*)'", mo.group(2))):
                self.clerk_consts.add(mo.group(1))

    def is_clerk(self, expr):
        expr = expr.strip()
        lit = re.fullmatch(r"'([^']*)'", expr)
        if lit:
            return is_clerk_type(lit.group(1))
        # launchModel and ship take the clerk with a shell as s.agentType
        return expr in self.clerk_consts or expr == "s.agentType"

    def helper_of(self, i):
        """The name of the top-level function or arrow const whose definition encloses i."""
        best = None
        for mo in re.finditer(r"^(?:async )?(?:function (\w+)\(|const (\w+) = (?:async )?\()", self.m, re.M):
            if mo.start() > i:
                break
            best = mo.group(1) or mo.group(2)
        return best

    def calls_of(self, name):
        for mo in re.finditer(r"(?<![\w.])" + re.escape(name) + r"\(", self.m):
            line_start = self.m.rfind("\n", 0, mo.start()) + 1
            if re.fullmatch(r"\s*(?:async )?function ", self.m[line_start:mo.start()]):
                continue                                         # the definition itself
            a = mo.end() - 1
            yield a, match(self.m, a)

    def clerk_schemas(self):
        """{schema name or '<inline @line>': [labels of the clerk launch sites]}."""
        found, helpers = {}, []
        for mo in re.finditer(r"(?<![\w.])agentType\s*:", self.m):
            a = enclosing(self.m, mo.start())
            if a < 0:
                continue
            b = match(self.m, a)
            kv = {}
            for s, e in top_level(self.m, a, b):
                key = self.m[s:e].split(":", 1)
                kv[key[0].strip()] = (s + len(key[0]) + 1, e) if len(key) == 2 else None
            if "agentType" not in kv or not kv["agentType"] or not self.is_clerk(self.src[slice(*kv["agentType"])]):
                continue
            if "schema" not in kv:
                continue
            line = self.src.count("\n", 0, a) + 1
            if kv["schema"] is None or self.m[slice(*kv["schema"])].strip() == "schema":
                helpers.append((self.helper_of(a), line))
                continue
            vs, ve = kv["schema"]
            expr = self.m[vs:ve].strip()
            if expr.startswith("{"):
                s0 = vs + self.m[vs:ve].index("{")
                found.setdefault(f"<inline @{line}>", []).append(("inline", (s0, match(self.m, s0))))
            elif expr in self.schemas:
                found.setdefault(expr, []).append(("line", line))
        seen = set()
        while helpers:
            name, line = helpers.pop()
            if name is None or name in seen:
                continue
            seen.add(name)
            for a, b in self.calls_of(name):
                body = self.m[a:b]
                for ident in set(re.findall(r"\b([A-Z][A-Z0-9_]*)\b", body)):
                    if ident in self.schemas:
                        found.setdefault(ident, []).append(("line", self.src.count("\n", 0, a) + 1))
                if re.search(r"(?<![\w.])schema(?![\w])", body):
                    helpers.append((self.helper_of(a), line))
        return found

    def required(self, span, seen=None):
        """Every string of every required list in the schema text at span, nested schema
        constants included."""
        seen = seen if seen is not None else set()
        a, b = span
        names = set()
        for mo in re.finditer(r"required\s*:\s*\[([^\]]*)\]", self.src[a:b]):
            names.update(re.findall(r"'([^']*)'", mo.group(1)))
        for ident in set(re.findall(r"\b([A-Z][A-Z0-9_]*)\b", self.m[a:b])):
            if ident in self.schemas and ident not in seen:
                seen.add(ident)
                names |= self.required(self.schemas[ident], seen)
        return names

    def violations(self):
        """{schema: sorted free-text fields it requires} over its clerk schemas."""
        bad = {}
        for name, sites in self.clerk_schemas().items():
            span = sites[0][1] if sites[0][0] == "inline" else self.schemas[name]
            req = self.required(span, {name})
            fields = [f for f in FREE if f in req]
            if "output" in req and (self.rel, name) not in OUTPUT_READ:
                fields.append("output")
            if fields:
                bad[name] = sorted(fields)
        return bad


def workflows(root=REPO):
    for f in sorted(root.glob("*/workflows/*.js")):
        rel = f.relative_to(root).as_posix()
        yield Workflow(rel, f.read_text(encoding="utf-8"))


def measure(root=REPO):
    """{workflow: {schema: [fields]}} for every workflow, nothing allowed (the raw count)."""
    return {w.rel: w.violations() for w in workflows(root)}


class ClerkSchemasRequireNoFreeText(unittest.TestCase):
    def test_no_clerk_schema_requires_a_free_text_field(self):
        offenders = []
        for w in workflows():
            if w.rel in ALLOWED_FILES:
                continue
            for name, fields in w.violations().items():
                if name in ALLOWED_SCHEMAS:
                    continue
                offenders.append(f"{w.rel} {name} requires {fields}")
        self.assertEqual(offenders, [], "a clerk that leaves one out loses its run (#124): "
                         "ask for the field, do not require it, and default it where it is read")

    def test_the_allow_lists_name_real_things(self):
        rels = {w.rel: w for w in workflows()}
        for rel in ALLOWED_FILES:
            self.assertIn(rel, rels, "an allowed file that no longer exists: drop it from ALLOWED_FILES")
        for rel, name in OUTPUT_READ:
            self.assertIn(rel, rels)
            self.assertIn(name, rels[rel].schemas, f"{rel}: no schema {name}")
        self.assertTrue(any("SHIP" in w.schemas for w in rels.values()))

    def test_the_reader_finds_the_clerk_stages(self):
        """The analysis is not vacuous: it sees the stages it is meant to see."""
        by = {w.rel: w for w in workflows()}
        self.assertIn("MOVE", by["academy/workflows/inbox.js"].clerk_schemas())         # through move -> clerk
        self.assertIn("SHIP", by["expert/workflows/cite.js"].clerk_schemas())           # s.agentType
        self.assertIn("STATE", by["researcher/workflows/prove.js"].clerk_schemas())     # a direct launch
        self.assertIn("CAPS", by["academy/workflows/workplan.js"].clerk_schemas())      # the ternary CLERK
        prove = by["researcher/workflows/prove.js"].clerk_schemas()
        self.assertNotIn("FILED", prove)              # launched by the prover and the lead only
        self.assertIn("MODEL_OUT", prove)             # launchModel's s.agentType
        # SHIP is a clerk schema and no longer requires a free-text field (output is parsed)
        self.assertNotIn("SHIP", by["expert/workflows/cite.js"].violations())

    def test_the_reader_catches_a_required_free_text_field(self):
        src = ("const CLERK = 'academy:inbox-clerk'\n"
               "const NOTE = { type: 'object', properties: { why: { type: 'string' } }, required: ['why'] }\n"
               "const OUT = { type: 'object', properties: { ok: { type: 'boolean' }, items: { type: 'array', items: NOTE } }, required: ['ok', 'items'] }\n"
               "const MOVE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok', 'detail'] }\n"
               "const FINE = { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok'] }\n"
               "const SHOWN = { type: 'object', properties: { output: { type: 'string' } }, required: ['output'] }\n"
               "const clerk = (stage, lines, schema) => launch(`STAGE ${stage}: ${lines.join(',')}`, { agentType: CLERK, schema })\n"
               "const a = await clerk('x', ['a, b', `c ${'d'}`], OUT)\n"
               "const b = await clerk('m', [/\\)/.test('x') ? 'y' : 'z'], MOVE)\n"
               "const c = await launch('p', { label: 'l', agentType: 'researcher:review-clerk', schema: FINE })\n"
               "const d = await launch('p', { label: 'l', agentType: 'researcher:prover', schema: MOVE })\n"
               "const e = await launch('p', { agentType: 'expert:review-chair', schema: SHOWN })\n"
               "const f = await launch('p', { agentType: CLERK, schema: { type: 'object', properties: { reason: { type: 'string' } }, required: ['reason'] } })\n")
        w = Workflow("x/workflows/x.js", src)
        bad = w.violations()
        self.assertEqual(bad.pop("OUT"), ["why"])             # nested through NOTE
        self.assertEqual(bad.pop("MOVE"), ["detail"])
        self.assertEqual(bad.pop("SHOWN"), ["output"])        # shown only: not in OUTPUT_READ
        self.assertEqual(list(bad.values()), [["reason"]])    # the inline schema
        self.assertNotIn("FINE", w.violations())

    def test_an_indented_schema_is_read_too(self):
        """Review of 0da42c3: a schema const declared inside a block (review-experiment.js's
        ST) was invisible to the reader."""
        src = ("const CLERK = 'academy:inbox-clerk'\n"
               "if (x) {\n"
               "  const ST = { type: 'object', properties: { detail: { type: 'string' } }, required: ['detail'] }\n"
               "  const st = await launch('p', { agentType: CLERK, schema: ST })\n"
               "}\n")
        self.assertEqual(Workflow("x/workflows/x.js", src).violations(), {"ST": ["detail"]})


if __name__ == "__main__":
    unittest.main()
