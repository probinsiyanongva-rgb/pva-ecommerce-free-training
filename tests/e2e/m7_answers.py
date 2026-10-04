"""Module 7 prose generator for tests: builds the Exception Resolution Log notes from
the accepted structured labels decoded at run time, so no prose answer is stored."""
from desk_helpers import order_ref


def m7_text(st, g, f, labels):
    ctype, happened, verified, impact, action, owner, deadline = labels[:7]
    return ("Order %s is logged as a %s case: %s. The records show the following: %s. "
            "The impact is that %s. The required action is to %s, owned by %s, with a deadline of %s."
            % (order_ref(g), ctype.lower(), happened.lower(), verified.lower(), impact.lower(),
               action[0].lower() + action[1:], owner, deadline.lower()))
