"""report.py -- the experiment report packet, generated from the header and the result.

Plan section 3.5 ("Experiment reports"), docs/packet-template.md (kind
``experiment-report``) and docs/protocol.md section 6.2. Every experiment ends in a
report packet; this script writes it, so the report's shape is decided by code and
not by whoever writes the prose.

Inputs:

* the experiment script: its module docstring is the header
  (``Kind:``, ``Claims:``, ``Goal:``, ... as in the lab's ``experiments/README.md``);
* the result JSON written by ``save_result`` (``claims``, ``outcome``,
  ``provenance``, ``result``); optional only for a probe;
* the **report draft**, a short Markdown file the experimenter writes after the
  run (default ``<home>/<scientist.reportDrafts or "reports">/<stem>.md``). It must
  have ``## Conclusion`` with four labelled bullets::

      ## Conclusion

      - **Establishes:** supports | refutes | inconclusive -- what, in words
      - **Does not establish:** ...
      - **Proposed status:** lab:<id> -> supported
      - **Next step:** ...

  and may have ``## Summary`` (at most three lines), ``## Established vs assumed``,
  ``## Class`` (with a ``Cannot contain:`` line), ``## Method``, ``## Validation``
  (with ``Reproduced: yes|no``), ``## Raw outcome``, ``## Decisions needed``,
  ``## Machine notes`` and the type's own sections (``## Certificate``,
  ``## Quantity``, ``## Object``, ``## Check``, ``## Decides``), whose text is added
  to the generated one.

The report is **refused** (exit 2, every problem listed) without an experiment type
(``search | measure | verify | probe``, from the header's ``Kind:`` or ``--type``),
without ``## Conclusion`` and its four bullets, with a proposed status a computation
cannot reach (``proved``, ``proved-modulo``, ``sketch``), and whenever a required
field cannot be found: the question, the claim ids, what the class structurally
cannot contain, the environment profile, the commit, whether the validation case
reproduced.

Usage (from anywhere; the lab comes from --home, the cwd, or workspace.json)::

    py report.py check  SCRIPT [--result JSON] [--draft MD] [--type T] [--env PROFILE] [--home DIR]
    py report.py render SCRIPT [same] [--job ID] [--out FILE] [--json]
    py report.py file   SCRIPT [same] [--job ID] [--ticket T-NNNN] [--to researcher@x] [--ask-prefix TEXT]
                        [--by SPEAKER] [--board DIR] [--workspace FILE] [--dry-run]

``check`` prints ``ok`` or the refusals. ``render`` prints the packet body (or, with
``--json``, the packet's frontmatter fields and body). ``file`` renders, then writes
the packet on the board (academy's ``packets.py``; ``--ticket`` links it to the
ticket that commissioned the experiment) and files a ``review-experiment`` ticket
from the lab to the Researcher instance (academy's ``board.py``), with the packet,
the claims and the files in its refs. Exit codes: 0 ok, 2 refused or error.
"""

import argparse
import ast
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _common as c  # noqa: E402
from _common import ac  # noqa: E402

PLUGIN = os.path.dirname(HERE)
TEMPLATES = os.path.join(PLUGIN, "templates")
TYPES = ("search", "measure", "verify", "probe")
#: statuses a computation may propose (plan section 8: never proved / proved-modulo)
COMPUTATION_STATUSES = ("open", "conjectured", "supported", "refuted", "refuted-as-stated")
#: which proposed statuses fit which conclusion word
FITS = {"supports": ("supported", "open", "conjectured"),
        "refutes": ("refuted", "refuted-as-stated"),
        "inconclusive": ("open", "conjectured")}
HEADER_FIELDS = ("Kind", "Claims", "Goal", "Question", "Constraints", "Properties",
                 "Certificate", "Validation", "Class", "Quantity", "Object", "Method",
                 "Decides", "Result",
                 "Claim tested", "Refuted by", "Search class")
COMMON_DRAFT = ("Summary", "Established vs assumed", "Class", "Method", "Validation",
                "Raw outcome", "Conclusion", "Decisions needed", "Machine notes")
TYPE_SECTIONS = {"search": ("Certificate",), "measure": ("Quantity",),
                 "verify": ("Object", "Check"), "probe": ("Decides",)}
RE_CLAIM = re.compile(r"^[a-z][a-z0-9-]*:\S+$")
MAX_ITEM = 300
#: provenance keys that are not tool versions (every other scalar is listed as one)
NOT_VERSIONS = ("date", "script", "git", "argv", "platform", "commit", "dirty", "cwd",
                "host", "job")


class Refused(ac.AcademyError):
    """The report cannot be written; ``problems`` lists every reason."""

    def __init__(self, problems):
        self.problems = list(problems)
        ac.AcademyError.__init__(self, "; ".join(self.problems))


# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------

def parse_header(text):
    """Map field -> value (continuation lines joined) from the module docstring.

    The same reading as the lab's checker: a field starts a line ``Name: value``,
    continues on indented lines, and ends at a blank line. None if the file does
    not parse or has no docstring.
    """
    try:
        doc = ast.get_docstring(ast.parse(text), clean=False)
    except SyntaxError:
        return None
    if doc is None:
        return None
    fields, current = {}, None
    for raw in doc.splitlines():
        m = re.match(r"^([A-Z][A-Za-z ]*?):\s*(.*)$", raw)
        if m and (m.group(1).strip() in HEADER_FIELDS
                  or m.group(1).startswith("Needs ")):
            current = m.group(1).strip()
            fields[current] = m.group(2).strip()
        elif current and raw.startswith((" ", "\t")) and raw.strip():
            fields[current] = (fields[current] + " " + raw.strip()).strip()
        elif not raw.strip():
            current = None
    title = doc.strip().splitlines()[0].strip() if doc.strip() else ""
    fields["_title"] = title
    return fields


def header_type(header):
    kind = (header.get("Kind") or "").strip()
    return kind.split()[0].lower().strip(",.;") if kind else ""


def claim_ids(text):
    out = []
    for tok in re.split(r"[,\s]+", text or ""):
        tok = tok.strip().strip(".;")
        if RE_CLAIM.match(tok) and tok not in out:
            out.append(tok)
    return out


def sections(text):
    """Draft Markdown -> {heading: text} for '## ' headings (text stripped)."""
    out, cur, buf = {}, None, []
    for ln in text.replace("\r\n", "\n").split("\n"):
        if ln.startswith("## "):
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur, buf = ln[3:].strip(), []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def labelled(text, label):
    """The value of a line ``- **Label:** value`` (bold and bullet optional), or None."""
    rx = re.compile(r"^\s*(?:[-*]\s+)?\**\s*" + re.escape(label) + r"\s*\**\s*:\s*\**\s*(.*)$",
                    re.IGNORECASE)
    for ln in (text or "").splitlines():
        m = rx.match(ln)
        if m:
            return m.group(1).strip()
    return None


def first_word(s):
    m = re.match(r"^[\s`*_(\[]*([A-Za-z-]+)", s or "")
    return m.group(1).lower() if m else ""


def proposed(value):
    """(claim id or '', status or '') from a 'Proposed status:' value."""
    ids = [t for t in re.findall(r"[a-z][a-z0-9-]*:[^\s,;`*]+", value or "")
           if RE_CLAIM.match(t) and not t.startswith(("http:", "https:"))]
    status = ""
    for st in sorted(ac.CLAIM_STATUSES, key=len, reverse=True):
        if re.search(r"(?<![a-z-])" + re.escape(st) + r"(?![a-z-])", (value or "").lower()):
            status = st
            break
    return (ids[0] if ids else ""), status


def compact(obj, limit=MAX_ITEM):
    s = json.dumps(obj, ensure_ascii=False, sort_keys=False)
    return s if len(s) <= limit else s[:limit - 3] + "..."


def clip(s, limit=600):
    s = " ".join(str(s or "").split())
    return s if len(s) <= limit else s[:limit - 3] + "..."


def truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        w = v.strip().lower()
        if w in ("yes", "true", "passed", "pass", "ok", "reproduced", "holds"):
            return True
        if w in ("no", "false", "failed", "fail", "not reproduced", "fails"):
            return False
    return None


def json_validation(data):
    """Whether the result JSON records a passed validation: True / False / None."""
    for holder in (data, data.get("outcome") or {}, data.get("result")
                   if isinstance(data.get("result"), dict) else {}):
        if not isinstance(holder, dict) or "validation" not in holder:
            continue
        v = holder["validation"]
        t = truthy(v)
        if t is not None:
            return t
        if isinstance(v, dict):
            for key in ("passed", "ok", "reproduced", "status", "pass"):
                if key in v and truthy(v[key]) is not None:
                    return truthy(v[key])
    return None


# ----------------------------------------------------------------------------
# Collecting the inputs
# ----------------------------------------------------------------------------

def _abs(home, p):
    return os.path.abspath(p if os.path.isabs(p) else os.path.join(home, p))


def _rel(home, p):
    return c.relative(home, p)


def gather(script, lab, result=None, draft=None, rtype=None, env=None, job=None):
    """Read and check everything; returns the context dict or raises Refused."""
    cfg, home, inst = lab["cfg"], lab["home"], lab["instance"]
    sci = cfg.get("scientist") or {}
    probs, notes = [], []
    spath = _abs(home, script)
    if not os.path.isfile(spath):
        raise Refused(["no experiment script at %s" % spath])
    with open(spath, "r", encoding="utf-8") as fh:
        header = parse_header(fh.read())
    if header is None:
        raise Refused(["%s has no module docstring (the header)" % _rel(home, spath)])
    stem = os.path.splitext(os.path.basename(spath))[0]

    # type
    htype = header_type(header)
    if rtype and htype and rtype != htype:
        probs.append("--type %s disagrees with the header's Kind: %s" % (rtype, htype))
    etype = htype or (rtype or "")
    allowed = [t for t in (sci.get("experimentTypes") or TYPES)]
    if not etype:
        probs.append("no experiment type: the header has no Kind: line and no --type was "
                     "given (one of %s)" % " | ".join(allowed))
    elif etype not in allowed or etype not in TYPES:
        probs.append("experiment type %r is not one of %s" % (etype, " | ".join(allowed)))

    # result JSON
    data, rpath = None, None
    if result:
        rpath = _abs(home, result)
    else:
        cand = os.path.join(home, c.results_dir(cfg), stem + ".json")
        if os.path.isfile(cand):
            rpath = cand
        elif os.path.isdir(os.path.join(home, c.results_dir(cfg), stem)):
            probs.append("results/%s/ holds per-run results: name one with --result" % stem)
    if rpath:
        try:
            with open(rpath, "r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except (OSError, ValueError) as exc:
            probs.append("cannot read the result JSON %s: %s" % (rpath, exc))
            data = None
    elif etype != "probe" and not any("per-run" in p for p in probs):
        probs.append("no result JSON for %s (results/%s.json); a %s report needs one"
                     % (stem, stem, etype or "non-probe"))
    outcome = (data or {}).get("outcome") if isinstance((data or {}).get("outcome"), dict) \
        else None
    prov = (data or {}).get("provenance") or {}
    if data is not None:
        pscript = prov.get("script")
        if pscript and os.path.basename(str(pscript)) != os.path.basename(spath):
            probs.append("the result was written by %s, not by %s"
                         % (pscript, _rel(home, spath)))
        if outcome and etype and outcome.get("kind") and outcome["kind"] != etype:
            probs.append("the result's outcome is a %s, the report says %s"
                         % (outcome["kind"], etype))
        if outcome is None and etype != "probe":
            notes.append("report.py: the result JSON has no outcome block (a result from "
                         "before the kinds); the raw outcome lists its top-level keys")

    # claims and question
    claims = claim_ids(header.get("Claims", ""))
    for cid in (data or {}).get("claims") or []:
        if RE_CLAIM.match(str(cid)) and cid not in claims:
            claims.append(cid)
    if not claims:
        probs.append("no claim ids: the header's Claims: line names none")
    question = header.get("Goal") or header.get("Question") or ""
    if not question:
        probs.append("no question: the header has no Goal: line")

    # draft
    dpath = _abs(home, draft) if draft else os.path.join(
        home, sci.get("reportDrafts") or "reports", stem + ".md")
    dsec = {}
    if not os.path.isfile(dpath):
        probs.append("no report draft at %s (it carries ## Conclusion)" % _rel(home, dpath))
    else:
        with open(dpath, "r", encoding="utf-8") as fh:
            dsec = sections(fh.read())
        known = COMMON_DRAFT + TYPE_SECTIONS.get(etype, ())
        for h in dsec:
            if h not in known:
                probs.append("the draft has a section '## %s' a %s report does not take "
                             "(allowed: %s)" % (h, etype or "typed", ", ".join(known)))
    concl = dsec.get("Conclusion")
    est = notest = prop_val = nxt = None
    word, pclaim, pstatus = "", "", ""
    if dsec and concl is None:
        probs.append("the draft has no ## Conclusion; the report is refused without it")
    elif concl is not None:
        est = labelled(concl, "Establishes")
        notest = labelled(concl, "Does not establish")
        prop_val = labelled(concl, "Proposed status")
        nxt = labelled(concl, "Next step")
        for name, val in (("Establishes", est), ("Does not establish", notest),
                          ("Proposed status", prop_val), ("Next step", nxt)):
            if not val:
                probs.append("## Conclusion needs a '%s:' line" % name)
        if est:
            word = first_word(est)
            if word not in FITS:
                probs.append("Establishes: must begin with supports, refutes or "
                             "inconclusive, not %r" % (word or est[:20]))
        if prop_val:
            pclaim, pstatus = proposed(prop_val)
            if not pstatus:
                probs.append("Proposed status: names no registry status (%s)"
                             % ", ".join(COMPUTATION_STATUSES))
            elif pstatus not in COMPUTATION_STATUSES:
                probs.append("a computation cannot propose %r: only %s (plan section 8)"
                             % (pstatus, ", ".join(COMPUTATION_STATUSES)))
            elif word in FITS and pstatus not in FITS[word]:
                probs.append("Establishes: %s does not fit the proposed status %s"
                             % (word, pstatus))
            if pclaim and claims and pclaim not in claims:
                probs.append("Proposed status: names %s, which is not among the claims "
                             "(%s)" % (pclaim, ", ".join(claims)))
    summary = dsec.get("Summary")
    if summary and len([ln for ln in summary.splitlines() if ln.strip()]) > 3:
        probs.append("## Summary in the draft has more than three lines")

    # class and what it cannot contain
    cannot = labelled(dsec.get("Class", ""), "Cannot contain")
    if not cannot:
        cannot = cannot_contain(etype, header, outcome)
    if not cannot:
        probs.append("nothing says what the class structurally cannot contain: add "
                     "'Cannot contain: ...' under ## Class in the draft (or '[excludes ...]' "
                     "tags / 'Not covered:' in the header)")

    # environment
    envs = sci.get("envs") or {}
    policy = sci.get("policy") or {}
    profile = env or policy.get("probe" if etype == "probe" else "run")
    if not profile:
        probs.append("no environment profile: pass --env (the home has no policy yet)")
    elif envs and profile not in envs:
        probs.append("env profile %r is not in scientist.envs (%s)"
                     % (profile, ", ".join(sorted(envs))))
    gitp = prov.get("git") if isinstance(prov.get("git"), dict) else {}
    commit = gitp.get("commit") or prov.get("commit")
    dirty = gitp.get("dirty")
    if not commit and etype != "probe":
        probs.append("the result JSON records no commit (provenance.git.commit)")
    if dirty:
        notes.append("report.py: the result was produced from a dirty tree (provenance "
                     "git.dirty true); the commit alone does not reproduce it")

    # validation
    vsec = dsec.get("Validation", "")
    rep_line = labelled(vsec, "Reproduced")
    reproduced, vsource = None, ""
    if rep_line is not None:
        reproduced, vsource = truthy(first_word(rep_line) or rep_line), "the draft"
    if reproduced is None and data is not None:
        reproduced, vsource = json_validation(data), "the result JSON"
    if reproduced is None:
        probs.append("whether the validation case reproduced is unknown: add "
                     "'Reproduced: yes|no' under ## Validation in the draft")
    elif reproduced is False and word and word != "inconclusive":
        probs.append("the validation case did not reproduce, so the conclusion must be "
                     "inconclusive, not %s" % word)
    if not header.get("Validation") and etype != "probe":
        probs.append("the header has no Validation: line")

    if etype == "probe":
        if not header.get("Decides"):
            probs.append("a probe names what its answer decides: the header needs Decides:")
        if data is None and not dsec.get("Raw outcome"):
            probs.append("a probe without a result JSON needs ## Raw outcome in the draft")
    if probs:
        raise Refused(probs)
    return {
        "lab": lab, "instance": inst, "home": home, "script": spath, "stem": stem,
        "header": header, "type": etype, "data": data, "result_path": rpath,
        "outcome": outcome, "provenance": prov, "claims": claims, "question": question,
        "draft": dsec, "draft_path": dpath, "establishes": est, "not_established": notest,
        "word": word, "proposed_claim": pclaim or (claims[0] if claims else ""),
        "proposed_status": pstatus, "next_step": nxt, "cannot": cannot,
        "profile": profile, "profile_def": envs.get(profile) or {}, "commit": commit,
        "dirty": dirty, "reproduced": reproduced, "vsource": vsource, "job": job,
        "notes": notes,
    }


def cannot_contain(etype, header, outcome):
    """What the class structurally cannot contain, from the header / outcome, or ''."""
    if etype == "search":
        tags = re.findall(r"\[(excludes\b[^\]]*)\]", header.get("Constraints", ""), re.I)
        if tags:
            return "; ".join(t.strip() for t in tags)
    if outcome and isinstance(outcome.get("class"), dict) and outcome["class"].get("excluded"):
        exc = outcome["class"]["excluded"]
        return "; ".join(str(x) for x in exc) if isinstance(exc, list) else str(exc)
    for field in ("Class", "Goal", "Object", "Search class", "Constraints"):
        m = re.search(r"not covered\s*:\s*(.+?)(?:\.\s|\.$|$)", header.get(field, ""),
                      re.I)
        if m:
            return m.group(1).strip()
    return ""


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------

def ref(ctx, path):
    return "`file:%s/%s`" % (ctx["instance"], _rel(ctx["home"], path))


def _extra(ctx, name):
    text = ctx["draft"].get(name, "")
    return ("\n\n" + text) if text else ""


def build_fields(ctx):
    """The template placeholders for this report."""
    h, out, et = ctx["header"], ctx["outcome"], ctx["type"]
    claims = ", ".join(ctx["claims"])
    status = (out or {}).get("status") or ("no outcome block" if ctx["data"] else
                                           "no result JSON")
    pst = ctx["proposed_status"]
    f = {}
    f["summary"] = ctx["draft"].get("Summary") or "\n".join([
        "%s experiment `%s` on %s: %s." % (et.capitalize(), ctx["stem"], claims, status),
        "Conclusion: %s" % clip(ctx["establishes"], 220),
        "Proposed status: %s -> %s, pending two experiment reviews."
        % (ctx["proposed_claim"], pst)])
    produced = ["- Script %s (header `Kind: %s`)." % (ref(ctx, ctx["script"]), et)]
    if ctx["result_path"]:
        produced.append("- Result %s." % ref(ctx, ctx["result_path"]))
    else:
        produced.append("- No result JSON (a probe).")
    produced.append("- Claims concerned: %s." % claims)
    f["produced"] = "\n".join(produced)
    f["established"] = ctx["draft"].get("Established vs assumed") or "\n".join([
        "- **Established:** (computation, not yet reviewed; proposed %s for %s) %s"
        % (pst, ctx["proposed_claim"], ctx["establishes"]),
        "- **Assumed:** the run on profile `%s` at commit `%s` executed the script as "
        "written, and the validation case certifies the pipeline on this class."
        % (ctx["profile"], ctx["commit"] or "unknown"),
        "- **Not established:** %s" % ctx["not_established"]])
    ev = []
    if ctx["result_path"]:
        ev.append("- Result %s: outcome `%s`, commit `%s` (%s)%s."
                  % (ref(ctx, ctx["result_path"]), status, ctx["commit"] or "unknown",
                     "dirty tree" if ctx["dirty"] else "clean tree",
                     (", run " + str(ctx["provenance"]["date"]))
                     if ctx["provenance"].get("date") else ""))
    if ctx["job"]:
        ev.append("- Queue job `%s` on profile `%s`." % (ctx["job"], ctx["profile"]))
    ev.append("- Validation case: %s (from %s)."
              % ("reproduced" if ctx["reproduced"] else "NOT reproduced", ctx["vsource"]))
    if h.get("Result"):
        ev.append("- The script's own Result field: %s" % clip(h["Result"], 700))
    f["evidence"] = "\n".join(ev)
    f["question"] = "%s\n\nClaims: %s." % (ctx["question"], claims)
    cls_parts = []
    if et == "search":
        cls_parts.append("Constraints: %s" % (h.get("Constraints") or "(none stated)"))
        if out and out.get("constraints") is not None:
            cls_parts.append("Parameters actually used: `%s`" % compact(out["constraints"]))
    elif et == "measure":
        cls_parts.append(h.get("Class") or "(no Class: line)")
    elif et == "verify":
        cls_parts.append("One named object (see ## Object).")
    else:
        cls_parts.append("A probe: feasibility, not evidence.")
    cls_parts.append("**Cannot contain:** %s" % ctx["cannot"])
    extra = ctx["draft"].get("Class", "")
    extra = "\n".join(ln for ln in extra.splitlines()
                      if labelled(ln, "Cannot contain") is None).strip()
    if extra:
        cls_parts.append(extra)
    f["class"] = "\n\n".join(cls_parts)
    method = h.get("Method")
    if not method:
        if et == "search":
            method = "Properties: %s\n\nCertificate: %s" % (h.get("Properties", "-"),
                                                            h.get("Certificate", "-"))
        elif et == "measure":
            method = "Quantity: %s" % h.get("Quantity", "-")
        else:
            method = "As in the script %s." % ref(ctx, ctx["script"])
    needs = ["%s: %s" % (k, v) for k, v in h.items() if k.startswith("Needs ")]
    f["method"] = method + ("\n\n" + "\n".join(needs) if needs else "") + \
        _extra(ctx, "Method")
    pd = ctx["profile_def"]
    prov = ctx["provenance"]
    env_lines = ["- Profile: `%s`%s" % (ctx["profile"], (" (kind %s%s)" % (
        pd.get("kind"), (", host " + pd["host"]) if pd.get("host") else "")) if pd else "")]
    env_lines.append("- Commit: `%s`%s" % (ctx["commit"] or "unknown",
                                           " (dirty tree)" if ctx["dirty"] else ""))
    vers = ["%s %s" % (k, v) for k, v in prov.items()
            if k not in NOT_VERSIONS and isinstance(v, (str, int, float)) and v != ""]
    if vers:
        env_lines.append("- Versions: %s" % ", ".join(vers))
    if prov.get("platform"):
        env_lines.append("- Platform: %s" % prov["platform"])
    if prov.get("argv") is not None:
        env_lines.append("- Arguments: `%s`" % compact(prov.get("argv")))
    f["environment"] = "\n".join(env_lines)
    vtext = [h.get("Validation") or "(the probe states none)",
             "**Reproduced:** %s (from %s)." % ("yes" if ctx["reproduced"] else "no",
                                                ctx["vsource"])]
    vextra = "\n".join(ln for ln in ctx["draft"].get("Validation", "").splitlines()
                       if labelled(ln, "Reproduced") is None).strip()
    if vextra:
        vtext.append(vextra)
    f["validation"] = "\n\n".join(vtext)
    f["raw_outcome"] = raw_outcome(ctx)
    f["conclusion"] = ctx["draft"]["Conclusion"]
    f["decisions"] = ctx["draft"].get("Decisions needed") or "None."
    notes = ctx["notes"] + ([ctx["lab"]["note"]] if ctx["lab"].get("note") else [])
    dnotes = ctx["draft"].get("Machine notes", "")
    if dnotes and dnotes.strip() != "None.":
        notes = [dnotes] + ["- " + n for n in notes]
        f["machine_notes"] = "\n".join(notes)
    else:
        f["machine_notes"] = "\n".join("- " + n for n in notes) or "None."
    # the type's own sections
    if et == "search":
        cert = [h.get("Certificate") or "(no Certificate: line)"]
        if out:
            cert.append("Outcome: `%s`, %s example(s)." % (out.get("status"),
                                                          out.get("count", "?")))
            for i, ex in enumerate((out.get("examples") or [])[:3], 1):
                cert.append("- Example %d certificate: `%s`"
                            % (i, compact(ex.get("certificate") if isinstance(ex, dict)
                                          else ex)))
        f["certificate"] = "\n\n".join(cert) + _extra(ctx, "Certificate")
    elif et == "measure":
        f["quantity"] = (h.get("Quantity") or "(no Quantity: line)") + "\n\n" + \
            distribution(out) + _extra(ctx, "Quantity")
    elif et == "verify":
        obj = h.get("Object") or "(no Object: line)"
        if out and isinstance(out.get("object"), dict):
            obj += "\n\nObjects in the outcome: %s." % ", ".join(
                "`%s`" % k for k in out["object"])
        f["object"] = obj + _extra(ctx, "Object")
        chk = ["Properties: %s" % (h.get("Properties") or "(no Properties: line)")]
        if out and isinstance(out.get("properties"), dict):
            rows = ["| Property | Outcome |", "|---|---|"]
            for k, v in out["properties"].items():
                rows.append("| %s | %s |" % (str(k).replace("|", "/"), v))
            chk.append("\n".join(rows))
            chk.append("Overall: `%s`, by %s independent route(s)."
                       % (out.get("status"), out.get("routes", "?")))
        f["check"] = "\n\n".join(chk) + _extra(ctx, "Check")
    else:
        f["decides"] = (h.get("Decides") or "") + _extra(ctx, "Decides")
    return f


def distribution(out):
    """A few lines on the measured values: how many, and their range where numeric."""
    if not out or "values" not in out:
        return "Distribution: no outcome values recorded."
    vals = out["values"]
    if isinstance(vals, dict):
        keys = list(vals)
        lines = ["Distribution: values for %d member(s): %s."
                 % (len(keys), ", ".join("`%s`" % k for k in keys[:12])
                    + (" ..." if len(keys) > 12 else ""))]
        nums = [v for v in vals.values() if isinstance(v, (int, float))
                and not isinstance(v, bool)]
        if nums and len(nums) == len(keys):
            lines.append("Range: %s .. %s." % (min(nums), max(nums)))
        return "\n".join(lines)
    if isinstance(vals, list):
        nums = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if nums:
            return "Distribution: %d value(s), range %s .. %s, mean %.6g." % (
                len(nums), min(nums), max(nums), sum(nums) / len(nums))
        return "Distribution: %d value(s)." % len(vals)
    return "Distribution: `%s`." % compact(vals)


def raw_outcome(ctx):
    out, data = ctx["outcome"], ctx["data"]
    drawn = ctx["draft"].get("Raw outcome", "")
    lines = []
    if out:
        for k, v in out.items():
            lines.append("- `%s`: `%s`" % (k, compact(v)))
        lines.append("\nFull block: `outcome` in %s." % ref(ctx, ctx["result_path"]))
    elif data is not None:
        res = data.get("result")
        keys = list(res) if isinstance(res, dict) else []
        lines.append("No outcome block (a result from before the kinds). Top-level keys "
                     "of `result`: %s." % (", ".join("`%s`" % k for k in keys) or "none"))
        lines.append("\nFull data: %s." % ref(ctx, ctx["result_path"]))
    if drawn:
        lines.append(("\n" if lines else "") + drawn)
    return "\n".join(lines).strip()


def load_template(etype, folder=TEMPLATES):
    with open(os.path.join(folder, "report-%s.md" % etype), "r", encoding="utf-8") as fh:
        text = fh.read().replace("\r\n", "\n")
    # drop the leading HTML comment that documents the template
    return re.sub(r"^\s*<!--.*?-->\s*", "", text, count=1, flags=re.S)


def render(ctx, folder=TEMPLATES):
    """(meta, body): the packet's frontmatter fields and its body."""
    tpl = load_template(ctx["type"], folder)
    fields = build_fields(ctx)

    def sub(m):
        key = m.group(1)
        if key not in fields:
            raise ac.AcademyError("template report-%s.md uses {{%s}}, which report.py does "
                                  "not fill" % (ctx["type"], key))
        return fields[key].strip()

    body = "\n" + re.sub(r"\{\{([a-z_]+)\}\}", sub, tpl).strip() + "\n"
    meta = {
        "title": "Experiment report: %s" % ctx["stem"],
        "kind": "experiment-report",
        "subject": list(ctx["claims"]),
        "status_proposed": ctx["proposed_status"] if len(ctx["claims"]) == 1 else None,
    }
    probe = dict(meta, packet="P-0001", instance=ctx["instance"],
                 by=ctx["instance"], state="open", created=ac.today())
    probs = ac.validate_packet({k: v for k, v in probe.items() if v is not None}, body)
    if probs:
        raise Refused(["the rendered packet is invalid: %s" % p for p in probs])
    return meta, body


# ----------------------------------------------------------------------------
# Filing
# ----------------------------------------------------------------------------

def _academy_module(name):
    """Import academy/scripts/<name>.py from the academy repo (reuse, not a copy)."""
    path = os.path.join(ac.repo_root(), "academy", "scripts", name + ".py")
    if not os.path.isfile(path):
        raise ac.AcademyError("academy script not found: %s" % path)
    scripts = os.path.dirname(path)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    if name in sys.modules and getattr(sys.modules[name], "__file__", "") and \
            os.path.abspath(sys.modules[name].__file__) == os.path.abspath(path):
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _home_config(home):
    try:
        return ac.load_config(home)
    except ac.AcademyError:
        return None


def route_reviewer(ws, instance, claims, to=None):
    """The Researcher instance that reviews this experiment, and how it was chosen.

    ``to`` if given; else the researcher whose ``ns`` owns one of the claims; else
    the researcher whose academy.json names this lab (``researcher.lab``); else the
    one researcher sharing a domain (the first by name if several).
    """
    insts = ws["instances"]
    researchers = sorted(n for n, i in insts.items() if i.get("role") == "researcher")
    if to:
        if to not in researchers:
            raise Refused(["--to %s is not a researcher instance of workspace.json" % to])
        return to, "named with --to"
    for cid in claims:
        ns = cid.split(":", 1)[0]
        for r in researchers:
            if insts[r].get("ns") == ns:
                return r, "owns the namespace of %s" % cid
    for r in researchers:
        cfg = _home_config(insts[r].get("home", ""))
        if cfg and (cfg.get("researcher") or {}).get("lab") == instance:
            return r, "its academy.json names %s as its lab" % instance
    mine = set((insts.get(instance) or {}).get("domains") or [])
    shared = [r for r in researchers if mine & set(insts[r].get("domains") or [])]
    if shared:
        why = "shares a domain with %s" % instance
        if len(shared) > 1:
            why += " (first of %s)" % ", ".join(shared)
        return shared[0], why
    raise Refused(["no researcher instance to review the report: none owns the claims' "
                   "namespaces, names this lab, or shares its domains; pass --to"])


def file_report(ctx, meta, body, board=None, workspace=None, ticket=None, to=None,
                by=None, dry_run=False, ask_prefix=None):
    """Write the packet and the review ticket. Returns a dict describing both.

    ``ask_prefix`` is put in front of the ticket's one-line ask (``<prefix> -- ...``),
    for a mark every reader must see first, such as ``dry-run: migration test``."""
    ws = ac.load_workspace(workspace)
    inst = ctx["instance"]
    if inst not in ws["instances"]:
        raise Refused(["%s is not an instance of workspace.json" % inst])
    reviewer, why = route_reviewer(ws, inst, ctx["claims"], to)
    boardlib = _academy_module("board")
    packets = _academy_module("packets")
    bdir = boardlib.resolve_board(board, workspace)
    by = by or "%s/experimenter" % inst
    plan = {"packet_title": meta["title"], "instance": inst, "reviewer": reviewer,
            "reviewer_because": why, "board": bdir.replace("\\", "/"), "by": by,
            "commissioned_by": ticket}
    if dry_run:
        return dict(plan, dry_run=True)
    ppath = packets.create_packet(bdir, inst, meta["title"], meta["kind"], by, ticket,
                                  None, meta["subject"], None, meta["status_proposed"],
                                  body, workspace=ws)
    pid = re.match(r"^(P-\d+)", os.path.basename(ppath)).group(1)
    refs = list(ctx["claims"]) + [pid, "file:%s/%s" % (inst, _rel(ctx["home"], ctx["script"]))]
    if ctx["result_path"]:
        refs.append("file:%s/%s" % (inst, _rel(ctx["home"], ctx["result_path"])))
    ask = ("Review experiment report %s (%s, %s): two experiment-reviewer runs."
           % (pid, ctx["type"], ", ".join(ctx["claims"])))
    if ask_prefix:
        ask = "%s -- %s" % (" ".join(str(ask_prefix).split()), ask)
    detail = ("The report proposes %s -> %s. Conclusion: %s"
              % (ctx["proposed_claim"], ctx["proposed_status"],
                 clip(ctx["establishes"], 400)))
    try:
        tpath = boardlib.create_ticket(
            bdir, reviewer, "Review experiment %s" % ctx["stem"], ask,
            "An experiment-review packet with two verdicts (SOUND / SOUND MODULO / GAP / "
            "BROKEN); the ticket result names them.",
            kind="review-experiment", priority="normal", refs=refs, parent=ticket,
            budget={"runs": 2, "max_model": "fable"}, detail=detail, as_instance=inst,
            agent=(by.split("/", 1)[1] if "/" in by else ac.MAIN_AGENT),
            workspace=ws)
    except ac.AcademyError as exc:
        raise ac.AcademyError("packet %s was written (%s) but the review ticket was not: %s"
                              % (pid, ppath, exc))
    tid = re.match(r"^(T-\d+)", os.path.basename(tpath)).group(1)
    return dict(plan, packet=pid, packet_path=ppath.replace("\\", "/"), ticket=tid,
                ticket_path=tpath.replace("\\", "/"))


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="report.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "render", "file"):
        p = sub.add_parser(name)
        p.add_argument("script")
        p.add_argument("--result"); p.add_argument("--draft")
        p.add_argument("--type", choices=TYPES); p.add_argument("--env")
        p.add_argument("--home"); p.add_argument("--workspace")
        p.add_argument("--job")
        if name == "render":
            p.add_argument("--out"); p.add_argument("--json", action="store_true")
        if name == "file":
            p.add_argument("--ticket"); p.add_argument("--to"); p.add_argument("--by")
            p.add_argument("--board"); p.add_argument("--dry-run", action="store_true")
            p.add_argument("--ask-prefix", help="put in front of the review ticket's ask")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        lab = c.resolve_lab(a.home, os.getcwd(), a.workspace)
        ctx = gather(a.script, lab, a.result, a.draft, a.type, a.env, a.job)
        if a.cmd == "check":
            print("ok: %s report for %s (%s -> %s)" % (ctx["type"], ctx["stem"],
                                                      ctx["proposed_claim"],
                                                      ctx["proposed_status"]))
            return 0
        meta, body = render(ctx)
        if a.cmd == "render":
            text = json.dumps(dict(meta, body=body), ensure_ascii=False, indent=1) \
                if a.json else body.lstrip("\n")
            if a.out:
                ac.atomic_write(a.out, text if text.endswith("\n") else text + "\n")
                print(a.out)
            else:
                sys.stdout.write(text if text.endswith("\n") else text + "\n")
            return 0
        res = file_report(ctx, meta, body, a.board, a.workspace, a.ticket, a.to, a.by,
                          a.dry_run, a.ask_prefix)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    except Refused as r:
        print("refused:", file=sys.stderr)
        for p in r.problems:
            print("- " + p, file=sys.stderr)
        return 2
    except ac.AcademyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
