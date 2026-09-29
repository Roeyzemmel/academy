"""The OLD claims.py frontmatter reader, kept verbatim for the migration only.

Two uses, both transitional (removed with the shims, plan section 9 phase 8):

* the R2 requote (``registry requote``) parses every lab/paper file with this reader
  and with the dialect (``core.fm``) after requoting, and proves them equal field by
  field;
* the fsl-claims profile falls back to it for a file the dialect rejects, so a home
  that has not been requoted yet (a main checkout before its migration branch is
  merged) still loads. Every such file is reported by ``check`` as a warning naming
  the dialect error, so the fallback never hides.

The reader: frontmatter in a flat YAML subset, ``key: value`` or ``key:`` then indented
``  - item`` lines; list fields split on commas; every other value kept raw (quotes
included).
"""
import re


def parse(text, list_fields):
    """``(fields, body)`` as <lab>/scripts/claims.py's ``parse_text`` read them
    (body stripped). Raises ValueError with the old messages."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter: the file must start with a line `---`")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("frontmatter is not closed by a line `---`")
    fields, key = {}, None
    for n, raw in enumerate(lines[1:end], start=2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s+-\s?(.*)$", raw)
        if m:
            if key is None or not isinstance(fields.get(key), list):
                raise ValueError(f"line {n}: list item outside a list field")
            fields[key].append(m.group(1).strip())
            continue
        m = re.match(r"^([a-z_]+):\s*(.*)$", raw)
        if not m:
            raise ValueError(f"line {n}: expected `key: value` or `  - item`")
        key, val = m.group(1), m.group(2).strip()
        if key in list_fields:
            fields[key] = [] if not val else [v.strip() for v in val.strip("[]").split(",")
                                               if v.strip()]
        else:
            fields[key] = val
    body = "\n".join(lines[end + 1:]).strip()
    return fields, body
