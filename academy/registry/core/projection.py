"""Status projection: every profile's statuses onto five coarse classes.

Cross-namespace rules use only the class (a lab claim that depends on a refuted input
warns whether the input says ``refuted`` or a v1 notebook's ``Disproved``), and so do
``find --class`` and the cross-repo views. ``supported`` is *unsettled* on purpose: no
computation proves a claim. A v1 notebook's ``Reduced`` is *true-modulo* and ``Partial``
*unsettled* (plan section 6).
"""

FALSE, TRUE, TRUE_MODULO, UNSETTLED, NA = "false", "true", "true-modulo", "unsettled", "n/a"
CLASSES = (FALSE, TRUE, TRUE_MODULO, UNSETTLED, NA)

FSL = {
    "refuted": FALSE, "refuted-as-stated": FALSE,
    "proved": TRUE,
    "proved-modulo": TRUE_MODULO,
    "open": UNSETTLED, "conjectured": UNSETTLED, "sketch": UNSETTLED, "supported": UNSETTLED,
    "superseded": NA, "dropped": NA,
}

S1 = {
    "Disproved": FALSE,
    "Proved": TRUE,
    "Proved modulo stated inputs": TRUE_MODULO, "Reduced": TRUE_MODULO,
    "Not settled": UNSETTLED, "Partial": UNSETTLED,
}


#: schema v2 (core/schema.py): one vocabulary; superseded/dropped are a lifecycle there,
#: and a record that is not active is n/a whatever its status (schema.project)
V2 = {
    "refuted": FALSE, "refuted-as-stated": FALSE,
    "proved": TRUE,
    "proved-modulo": TRUE_MODULO,
    "open": UNSETTLED, "conjectured": UNSETTLED, "sketch": UNSETTLED, "supported": UNSETTLED,
}


def project(status, table):
    """The class of ``status`` under ``table``; no status (a definition, a remark, an
    example, a ledger entry) is n/a. An unknown word is unsettled: never true."""
    if not status:
        return NA
    return table.get(status, UNSETTLED)
