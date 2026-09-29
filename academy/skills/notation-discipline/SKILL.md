---
name: notation-discipline
description: 'Which notation wins (domain pack < project decisions < the draft) and how to introduce symbols: one symbol per object, introduced before use, changes routed to their owner. Use whenever a symbol is written or changed, or documents disagree on notation.'
---

# Notation discipline

## Precedence

Three sources can fix notation. When they disagree, the later one wins:

1. **The domain pack's `notation.md`** (through `domain_get`): the subject's standard
   notation, the default for a new home.
2. **The project's decisions** (for an Author home, its notation-decisions rules file):
   choices the project has settled, binding on every new formula.
3. **The draft itself**: the notation list or section a reader actually sees.

So the draft is the authority. If a decisions file disagrees with the draft's notation
list, the decisions file is wrong and gets fixed; if the pack disagrees with the
project, the project wins in that home and the pack stays as it is.

## Rules for every formula

- **One object, one symbol; one symbol, one meaning** within a document. A clash is a
  finding, not a style preference.
- **Introduce before use.** Every symbol is defined, or points to its definition,
  before its first use; a result stated in the introduction points forward.
- **Follow the settled choices** even where you would choose differently. Propose a
  change; do not make it.
- **Quoted statements keep the source's notation**, verbatim, with a sentence
  translating it if it differs.
- **Named terms are notation too.** A defined word is used
  (say, "admissible") in its defined sense only; a second sense needs a different word.

## Changing notation

- A change to the project's decisions goes to that home's notation owner (Author:
  `notation-auditor`, which edits only the decisions file) or to Roey.
- A change to the domain's standard notation goes to Expert as a `notation` ticket;
  the librarian curates the pack.
- Never change a symbol across a draft as a side effect of other work. A rename is its
  own item, with a machine note at each changed site.
