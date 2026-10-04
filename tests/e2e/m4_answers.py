"""Module 4 prose generator for tests: builds the two writing stages' text from the
accepted structured labels decoded at run time, so no prose answer is stored."""
from desk_helpers import order_ref


def m4_text(st, g, f, labels):
    if (f.get("minWords") or 0) >= 20:
        return ("Order %s needs attention: %s. The records show the following: %s. The impact is that %s. "
                "The required action is to %s, owned by %s, with a deadline of %s." % ((order_ref(g),) + tuple(l.lower() for l in labels[:6])))
    issue, fields, nxt = labels[0], labels[1], labels[2]
    if fields == "none":
        return "Every field on this record was compared with the others and it was logged as %s. The next step is %s." % (issue.lower(), nxt.lower())
    return "The %s fields on this record were compared, and the problem was logged as %s. The next step is to %s." % (fields.replace("; ", " and "), issue.lower(), nxt[0].lower() + nxt[1:])
