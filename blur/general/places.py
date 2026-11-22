"""Postcodes and street addresses."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)


def postcode(c: Ctx):
    n = c.n
    full, _ = c.P(r"[A-Z]{1,2}\d{1,2}[A-Z]? \d[A-Z]{2}", pre=WORD + "<_/", post=WORD + "_@")
    part, _ = c.P(r"[A-Z]{1,2}\d{1,2}[A-Z]?", pre=WORD + "<_/@", post=WORD + "_@", end_terms=[~n.cls("'").at(1)])
    fstart = n.AND(full, ~full.at(-1))
    comma = n.AND(n.cls(","), full.at(-1), n.cls(" ").at(1), fstart.at(2))
    c.add("POSTCODE", n.OR(full, comma, n.AND(n.cls(" "), comma.at(-1))), 0)
    if not general():
        c.add("POSTCODE", n.AND(part, ~c.key), 2)


def address(c: Ctx):
    """Street = run of capitalised words ending in a street word; building = number just before
    it; city = capitalised words just after it or just before the state."""
    n = c.n
    wordc, wstart, cap = c.wordc, c.wstart, c.cap
    joint = n.AND(n.cls(" "), cap.at(-1), wstart.at(1))
    body = n.OR(cap, joint, force=True)
    ends = []
    for w in STREET_SUFFIX.split("|"):
        ends.append(n.AND(n.lit(w), joint.at(-1), ~wordc.at(len(w))).at(-(len(w) - 1)))
    street = n.prop_left(n.OR(*ends), body, 5)
    if general():
        # a street name needs address context: a house number before it, an address-list comma after it, or a
        # locative word ("on", "at", "in") before it; "Google Drive" and "Central Park" are not streets
        d = n.cls(D)
        st0 = n.AND(street, ~street.at(-1))
        st_end = n.AND(street, ~street.at(1))
        num_before = n.OR(n.AND(n.cls(" ").at(-1), n.cls(D + "ABCDEFGH").at(-2), n.cls(D).at(-3)),
                          n.AND(n.cls(" ").at(-1), n.cls(",").at(-2), d.at(-3)), n.AND(n.cls(" ").at(-1), d.at(-2)))
        loc_before = n.OR(*[n.lit(w + " ").at(-len(w) - 1) for w in ("on", "at", "in", "off", "near", "Street:", "Address:")])
        list_after = n.AND(n.cls(",").at(1), n.cls(" ").at(2), n.cls(UP + D).at(3))
        ctx = n.OR(n.fill(street, n.AND(st0, n.OR(num_before, loc_before)), 5), n.fill(street, n.AND(st_end, list_after), 5))
        c.add("STREET", n.AND(street, ctx))
    else:
        c.add("STREET", street)
    sstart = n.AND(street, ~street.at(-1))
    comma, space = n.cls(","), n.cls(" ")
    before_street = n.OR(n.AND(comma.at(1), space.at(2), sstart.at(3)), n.AND(space.at(1), sstart.at(2)))
    c.add("BUILDING", c.P(r"\d{1,4}", end_terms=[before_street])[0])
    state = c.get("STATE")
    not_state = n.AND(body, ~state, ~state.at(1), ~street, ~street.at(-1))
    after_street = n.OR(n.AND(street.at(-3), comma.at(-2), space.at(-1)), n.AND(street.at(-2), space.at(-1)))
    city_f = n.prop_right(n.AND(wstart, after_street, ~state), not_state, 5)
    st_start = n.AND(state, ~state.at(-1))
    before_state = n.OR(n.AND(comma.at(1), space.at(2), st_start.at(3)), n.AND(space.at(1), st_start.at(2)))
    city_b = n.prop_left(n.AND(cap, before_state, ~street), not_state, 5)
    c.add("CITY", n.OR(city_f, city_b), 2)
