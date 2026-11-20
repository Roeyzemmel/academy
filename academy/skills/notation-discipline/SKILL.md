---
name: notation-discipline
description: 'Which notation wins (paper style.md > writing-style.md > domain pack) and who changes it. Use whenever a symbol is written or changed, or documents disagree on notation.'
---

# Notation discipline

## Where the rules are

The habits of notation (one object, one symbol; introduce before use; the letter by the
kind of object; notation that earns its place; quoted statements keep the source's
notation; named terms are notation too) are rules 10 and 13 of the academy's writing
guide, `${CLAUDE_PLUGIN_ROOT}/references/writing-style.md`. A paper's own choices (its
symbols, letter families, reserved words, standard examples) are the notation section of
its `.claude/rules/style.md`.

**Precedence: the paper's `style.md` > `writing-style.md` > the domain pack's
`notation.md`** (the human, 2026-11-19, academy issue #106). The pack (`domain_get
<domain> notation.md`) is read only for the symbols the paper file does not settle; where
the pack differs, the paper wins in that home and the pack stays as it is. A home with no
paper file (a Researcher's notebook) follows the guide, then the pack. How the draft's
notation list and the paper file relate: `writing-style.md`, rule 13.

## Changing notation

- A change to a paper's settled notation goes to that home's notation owner (Author:
  `notation-auditor`, which edits only the notation of the paper's `style.md`) or to the
  human.
- A change to the domain's standard notation goes to the Expert as a `notation`
  ticket (the Scientist, not a neighbour of the Expert, files it to the Researcher
  with `final_to: expert`); the librarian curates the pack.
- Never change a symbol across a draft as a side effect of other work. A rename is its
  own item, with a machine note at each changed site.
