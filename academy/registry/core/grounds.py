"""Grounds for a status change (plan section 8), as pure functions.

Moved here from the MCP server so that the mutation paths share one rule set: the MCP
tool ``claims_set_status`` and the engine's fsl-claims ``set-status`` apply
:func:`check_grounds` and :func:`check_verdict_refs`; the s1-kb profile's ``set-status``
anchors a change on a verdict file instead and applies the same verdict rules to that
file (``s1kb.verdict_file_problems``). The MCP module re-exports :func:`check_grounds`.

``grounds`` is a dict::

    {"basis": "proof" | "computation" | "human",
     "verdicts": [{"verdict": ..., "run_id": ..., "grader_role": ..., "ref": ...,
                   "statement_hash": ..., "commit": ...}, ...],
     "producer_role": ...,       # the agent (bare name) that produced what was graded
     "statement_hash": ...,      # optional; the hash the verdicts were given on
     "commit": ...,              # computation: the result's commit hash
     "validation_passed": bool,  # computation: the validation case reproduced
     "outcome": "supports" | "refutes",   # computation: the report's conclusion
     "modulo": [ids],            # proved-modulo: the missing inputs
     "superseded_by": id,        # superseded: the record that replaces this one
     "quote": "...", "where": "...",      # human: the human's words, and where said
     "note": "..."}              # the reason, required for an unsettled target

Rules:

* the human (main session) with no grounds at all: accepted (the human's word);
* any grounds that are given must pass, even for the human;
* ``basis: human``: a non-empty ``quote`` of the human's word; any status. From anyone
  but the human, ``where`` must also name the ticket or packet (``T-0007`` /
  ``P-0012``) that holds the quote; the MCP server checks that it does;
* unsettled targets (open/conjectured/sketch) and the lifecycle moves (superseded,
  dropped): a non-empty ``note``; superseded also names ``superseded_by``;
* proof: only proved/proved-modulo (all CONFIRMED) or refuted/refuted-as-stated (all
  DISPROVED); computation: only supported/refuted/refuted-as-stated (all SOUND, or all
  SOUND MODULO), never proved;
* both: at least two verdicts with distinct run ids, each with the ``ref`` of its review
  record; every verdict names its ``grader_role`` and the grounds name the
  ``producer_role``; the graders are the reviewers of the basis (proof:
  ``rigor-reviewer``, or ``expert`` for a review an Expert instance ran; computation:
  ``experiment-reviewer``), the producer is none of the reviewer roles, and no grader
  is the producer (never grade your own work);
* proof: all verdicts on one statement hash, equal to the claim's current one when it
  is known; proved-modulo needs ``modulo``, proved needs none;
* computation: one commit hash for all, the validation case passed, and ``outcome``
  matching the target (supports -> supported, refutes -> refuted*).

The roles in the grounds are declared by the caller. :func:`check_verdict_refs` ties
the rows to the files: each ``ref`` must be a landed review record on disk whose own
``verdict`` and ``run_id`` match the row, and whose ``subject``, ``statement_hash`` and
reviewer (``agent``, or the hook that landed it), when it records them, agree too.
"""

import re

CLAIM_STATUSES = ("open", "conjectured", "sketch", "supported", "proved-modulo",
                  "proved", "refuted", "refuted-as-stated", "superseded", "dropped")
UNSETTLED = ("open", "conjectured", "sketch")
PROOF_TARGETS = ("proved", "proved-modulo", "refuted", "refuted-as-stated")
COMPUTATION_TARGETS = ("supported", "refuted", "refuted-as-stated")
PROOF_VERDICTS = ("CONFIRMED", "PLAUSIBLE", "GAP", "DISPROVED")
EXPERIMENT_VERDICTS = ("SOUND", "SOUND MODULO", "GAP", "BROKEN")
BASES = ("proof", "computation", "human")
LIFECYCLE_TARGETS = ("superseded", "dropped")
# the reviewers of each basis (plan section 8): proofs go to the Expert's rigor-reviewer
# pair (``expert`` when an Expert decision table names only the role), experiments to
# the Researcher's experiment-reviewer pair
PROOF_GRADERS = ("rigor-reviewer", "expert")
COMPUTATION_GRADERS = ("experiment-reviewer",)
REVIEWER_ROLES = PROOF_GRADERS + COMPUTATION_GRADERS + ("referee", "review-chair")
# the hook that lands a review record, for records that do not name their agent
LANDED_BY = {"researcher/land_review": "experiment-reviewer"}
RE_BOARD_REF = re.compile(r"\b[TP]-\d{4,}\b")


def norm_verdict(v):
    return " ".join(str(v or "").replace("_", " ").replace("-", " ").upper().split())


def norm_role(r):
    """'researcher:prover' -> 'prover'; '' when absent."""
    r = str(r or "").strip().lower()
    return r.split(":")[-1].strip()


def check_grounds(new_status, grounds, statement_hash=None, human=False,
                  statuses=CLAIM_STATUSES):
    """``(ok, reasons)``: whether ``grounds`` justify ``new_status`` (module docstring)."""
    if new_status not in statuses:
        return False, ["%r is not a registry status (%s)" % (new_status, ", ".join(statuses))]
    if not grounds:
        if human:
            return True, ["the human's word (no grounds recorded)"]
        return False, ["no grounds given: a status change needs two agreeing verdicts "
                       "(plan section 8) or the human's quoted word"]
    if not isinstance(grounds, dict):
        return False, ["grounds must be an object"]
    basis = grounds.get("basis")
    if basis not in BASES:
        return False, ["grounds.basis must be 'proof', 'computation' or 'human'"]

    if basis == "human":
        if not str(grounds.get("quote") or "").strip():
            return False, ["basis 'human' needs grounds.quote: the human's words, verbatim"]
        if not human and not RE_BOARD_REF.search(str(grounds.get("where") or "")):
            return False, ["basis 'human' from an agent needs grounds.where naming the "
                           "ticket or packet (T-0007 / P-0012) that holds the quote"]
        return True, ["the human's quoted word"]

    if new_status in UNSETTLED + LIFECYCLE_TARGETS:
        if not str(grounds.get("note") or "").strip():
            return False, ["moving to %s needs grounds.note (the reason)" % new_status]
        if new_status == "superseded" and not str(grounds.get("superseded_by") or "").strip():
            return False, ["superseded needs grounds.superseded_by: the replacing record's id"]
        return True, ["%s with a stated reason" % new_status]

    if basis == "computation" and new_status not in COMPUTATION_TARGETS:
        return False, ["computation never establishes %r: experiment evidence reaches "
                       "only %s" % (new_status, ", ".join(COMPUTATION_TARGETS))]
    if basis == "proof" and new_status not in PROOF_TARGETS:
        return False, ["a proof review reaches only %s, not %r"
                       % (", ".join(PROOF_TARGETS), new_status)]

    probs = []
    rows = grounds.get("verdicts") or []
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return False, ["grounds.verdicts must be a list of objects"]
    if len(rows) < 2:
        probs.append("two agreeing verdicts are required, %d given" % len(rows))
    verdicts = [norm_verdict(r.get("verdict")) for r in rows]
    runs = [str(r.get("run_id") or "").strip() for r in rows]
    if any(not r for r in runs):
        probs.append("every verdict needs a run_id")
    elif len(set(runs)) != len(runs):
        probs.append("the verdicts' run ids must be distinct (independent runs)")

    producer = norm_role(grounds.get("producer_role") or grounds.get("producer"))
    graders = [norm_role(r.get("grader_role") or r.get("grader")) for r in rows]
    if not producer:
        probs.append("grounds.producer_role is required: who produced what was graded")
    fit = PROOF_GRADERS if basis == "proof" else COMPUTATION_GRADERS
    if any(not g for g in graders):
        probs.append("every verdict needs its grader_role")
    elif producer and producer in graders:
        probs.append("a grader is the producer (%s): nobody grades their own work" % producer)
    elif any(g not in fit for g in graders):
        probs.append("a %s review is graded by %s, not %s"
                     % (basis, " / ".join(fit),
                        ", ".join(sorted(set(g for g in graders if g not in fit)))))
    if producer and producer in REVIEWER_ROLES and producer not in graders:
        probs.append("the producer %r is a reviewer role: name who produced what was "
                     "graded" % producer)
    if any(not str(r.get("ref") or "").strip() for r in rows):
        probs.append("every verdict needs the ref of its review record")

    if basis == "proof":
        bad = [v for v in verdicts if v not in PROOF_VERDICTS]
        if bad:
            probs.append("unknown proof verdict(s) %s" % ", ".join(sorted(set(bad))))
        need = "CONFIRMED" if new_status in ("proved", "proved-modulo") else "DISPROVED"
        if verdicts and any(v != need for v in verdicts):
            probs.append("%s needs every verdict %s; got %s"
                         % (new_status, need, ", ".join(verdicts)))
        hashes = [str(r.get("statement_hash") or grounds.get("statement_hash") or "")
                  for r in rows]
        if any(not h for h in hashes):
            probs.append("every proof verdict needs the statement hash it was given on")
        elif len(set(hashes)) != 1:
            probs.append("the verdicts were given on different statements (hashes differ)")
        elif statement_hash and hashes[0] != statement_hash:
            probs.append("the verdicts' statement hash %s is not the claim's current %s"
                         % (hashes[0], statement_hash))
        modulo = grounds.get("modulo") or []
        if new_status == "proved-modulo" and not modulo:
            probs.append("proved-modulo needs grounds.modulo (the missing inputs)")
        if new_status == "proved" and modulo:
            probs.append("proved with open inputs is proved-modulo")
    else:
        bad = [v for v in verdicts if v not in EXPERIMENT_VERDICTS]
        if bad:
            probs.append("unknown experiment verdict(s) %s" % ", ".join(sorted(set(bad))))
        if verdicts and (len(set(verdicts)) != 1 or verdicts[0] not in
                         ("SOUND", "SOUND MODULO")):
            probs.append("computation needs agreeing SOUND verdicts; got %s"
                         % ", ".join(verdicts))
        commits = [str(r.get("commit") or grounds.get("commit") or "") for r in rows]
        if not rows or any(not c for c in commits):
            probs.append("the result's commit hash is required")
        elif len(set(commits)) != 1:
            probs.append("the verdicts reviewed different commits")
        if grounds.get("validation_passed") is not True:
            probs.append("the validation case must have passed (validation_passed: true)")
        want = "supports" if new_status == "supported" else "refutes"
        if grounds.get("outcome") != want:
            probs.append("%s needs outcome %r from the report's conclusion"
                         % (new_status, want))
    if probs:
        return False, probs
    return True, ["%s grounds: %d agreeing verdicts" % (basis, len(rows))]


def record_fields(text):
    """The flat ``key: value`` lines of a review record's leading frontmatter, quotes
    stripped; {} when there is none."""
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for ln in lines[1:]:
        if ln.strip() == "---":
            return out
        if ln[:1] in (" ", "\t", "-") or ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k.strip()] = "" if v in ("null", "~") else v
    return {}


def check_verdict_refs(grounds, resolve, claim_id=None):
    """Problems (empty when fine) tying each verdict row of proof/computation ``grounds``
    to its review record on disk. ``resolve(ref)`` returns a path or None. Each record
    must exist and carry the row's ``verdict`` and ``run_id``; when it records them,
    its ``subject`` must be ``claim_id`` (with or without the namespace), its
    ``statement_hash`` the row's, and its reviewer (``agent``, or the hook that landed
    it) one of the basis' graders."""
    g = grounds or {}
    if g.get("basis") not in ("proof", "computation"):
        return []
    fit = PROOF_GRADERS if g["basis"] == "proof" else COMPUTATION_GRADERS
    probs = []
    for r in g.get("verdicts") or []:
        if not isinstance(r, dict):
            continue
        ref = str(r.get("ref") or "").strip()
        if not ref:
            continue            # check_grounds reports it
        p = resolve(ref)
        try:
            with open(str(p), encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, TypeError):
            probs.append("review record %s: not found on disk" % ref)
            continue
        f = record_fields(text)
        if not f.get("verdict") or not f.get("run_id"):
            probs.append("review record %s: not a landed review record (no verdict and "
                         "run_id in its frontmatter)" % ref)
            continue
        if norm_verdict(f["verdict"]) != norm_verdict(r.get("verdict")):
            probs.append("review record %s says %s, the grounds say %s"
                         % (ref, norm_verdict(f["verdict"]), norm_verdict(r.get("verdict"))))
        if f["run_id"] != str(r.get("run_id") or "").strip():
            probs.append("review record %s is run %s, the grounds say %s"
                         % (ref, f["run_id"], r.get("run_id")))
        subj = f.get("subject")
        if claim_id and subj:
            want = {str(claim_id), str(claim_id).split(":", 1)[-1]}
            if subj not in want and subj.split(":", 1)[-1] not in want:
                probs.append("review record %s is about %s, not %s" % (ref, subj, claim_id))
        h = str(r.get("statement_hash") or g.get("statement_hash") or "")
        if f.get("statement_hash") and h and f["statement_hash"] != h:
            probs.append("review record %s was given on statement %s, the grounds say %s"
                         % (ref, f["statement_hash"], h))
        who = norm_role(f.get("agent")) or LANDED_BY.get(f.get("landed_by", ""), "")
        if who and who not in fit:
            probs.append("review record %s was written by %s, not a %s reviewer (%s)"
                         % (ref, who, g["basis"], " / ".join(fit)))
    return probs


def summary(grounds, human="the human"):
    """One line for a history row: what the change rests on (no ': ', so the row stays
    a bare value in the dialect)."""
    if not grounds:
        return "%s's word" % human
    b = grounds.get("basis")
    if b == "human":
        where = str(grounds.get("where") or "").strip()
        return '%s\'s word "%s"%s' % (human, str(grounds.get("quote")).strip(),
                                      (" (%s)" % where) if where else "")
    rows = grounds.get("verdicts") or []
    if not rows:
        return str(grounds.get("note") or "").strip()
    runs = ", ".join("%s %s" % (norm_verdict(r.get("verdict")), r.get("run_id")) for r in rows)
    return "%s review (%s)" % (b, runs)
