"""Values recognised by their shape: e-mail and IP addresses, identifiers, social and national ID
numbers, phone numbers and obfuscated spellings."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)
from .persons import names


def email(c: Ctx):
    n = c.n
    local = n.cls(AN + "._%+-\\" + HI)
    dom = n.cls(AN + "-")
    dc = n.OR(dom, n.AND(n.cls("."), dom.at(1), dom.at(-1)), force=True)
    at = n.AND(n.cls("@"), local.at(-1), dom.at(1))
    domain = n.prop_right(at, dc, 6)
    tld_dot = n.AND(n.cls("."), domain, n.run(n.cls(AL), 2).at(1))
    good = n.AND(at, n.prop_left(tld_dot, dc, 6).at(1))
    em = n.OR(n.prop_left(good, local, 6), n.prop_right(good, dc, 6))
    if general():
        # every e-mail address is masked: role mailboxes and documentation examples too (owner policy, 2026-11-17)
        # internationalised addresses: non-ASCII letters in the local part and the domain
        hi = n.cls(HI)
        local_i = n.OR(local, hi, force=True)
        dom_i = n.OR(dom, hi, force=True)
        dc_i = n.OR(dom_i, n.AND(n.cls("."), dom_i.at(1), dom_i.at(-1)), force=True)
        at_i = n.AND(n.cls("@"), local_i.at(-1), dom_i.at(1))
        domain_i = n.prop_right(at_i, dc_i, 6)
        tld_i = n.AND(n.cls("."), domain_i, n.run(n.OR(n.cls(AL), hi, force=True), 2).at(1))
        good_i = n.AND(at_i, n.prop_left(tld_i, dc_i, 6).at(1))
        em = n.OR(em, n.prop_left(good_i, local_i, 6), n.prop_right(good_i, dc_i, 6))
        fext = n.OR(*[n.AND(n.lit("." + e), ~n.cls(AN).at(len(e) + 1)) for e in ("png", "jpg", "jpeg", "gif", "svg", "webp", "js", "css",
                                                                                  "json", "py", "md", "txt", "pdf", "zip", "ts")])
        em = n.AND(em, ~n.fill(em, n.AND(em, fext), 6))
        # quoted local part and IP-literal domain
        c.add("EMAIL", c.P(r"\"[\w .+\-]{1,40}\"@[\w\-.]{2,}\.[a-zA-Z]{2,}", pre=WORD, post=WORD)[0])
        c.add("EMAIL", c.P(r"[\w.+\-]{1,}@\[\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\]", pre=WORD, post=None)[0])
        # HTML entity for @, reversed addresses ("moc.liamg@ayirp")
        c.add("EMAIL", c.P(r"[\w.+\-]{1,}&#64;[\w\-.]{1,}\.[a-zA-Z]{2,}", pre=WORD, post=WORD)[0])
        c.add("EMAIL", c.P(r"(moc|ten|gro|ni|ude|vog|oc|oi)\.[\w\-.]{1,}@[\w.+\-]{2,}", pre=WORD, post=WORD)[0])
    c.add("EMAIL", em)
    if general():
        tld = "(com|net|org|in|io|co|edu|gov|uk|de|fr|us)"
        for local in (r"[a-z0-9]{2,}", r"[a-z0-9]{2,} dot [a-z0-9]{2,}"):
            c.add("EMAIL", c.P(local + r" at [a-z0-9\-]{2,} dot " + tld, pre=WORD, post=WORD)[0])
        for o, cl in ((r"\[", r"\]"), (r"\(", r"\)")):
            c.add("EMAIL", c.P(rf"[\w.]{{2,}} ?{o}at{cl} ?[\w\-]{{2,}} ?{o}dot{cl} ?[a-z]{{2,6}}", pre=WORD, post=WORD)[0])


def ip(c: Ctx):
    n = c.n
    dotted_more = n.AND(n.cls("."), n.cls(WORD).at(1))
    v4, _ = c.P(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", pre=WORD + ".", post=WORD, end_terms=[~dotted_more.at(1)])
    # infrastructure addresses (loopback, unspecified, netmasks) are not personal
    infra = n.OR(n.lit("127."), n.lit("0.0.0.0"), n.lit("255.255."), n.lit("255.0.0.0"), n.lit("10."), n.lit("192.168."),
                 *[n.lit(f"172.{k}.") for k in range(16, 32)])
    v4 = n.AND(v4, ~n.fill(v4, n.AND(v4, ~v4.at(-1), infra), 4)) if general() else v4
    if general():   # "1.2.3.4-beta": a version string
        v4 = n.AND(v4, ~n.fill(v4, n.AND(v4, ~v4.at(1), n.cls("-").at(1), n.cls(AL).at(2)), 4))
        cidr = n.AND(n.cls("/"), v4.at(-1), n.cls(D).at(1))
        c.add("IP", n.OR(cidr, n.prop_right(cidr, n.cls(D), 1)), 0)
    c.ip_v4 = v4
    c.add("IP", v4)
    hexs = byteset(HEXC)
    parts = [(hexs, 1, 4)] + [(byteset(":"), 1, 1), (hexs, 1, 4)] * 7
    v6, _ = n.match(parts, byteset(WORD + ":"), byteset(WORD + ":%"))
    c.add("IP", v6)
    # compressed form: a token of hex digits and colons that contains "::" and at least 7 characters
    hx = n.cls(HEXC + ":")
    tok_start = n.AND(hx, ~n.cls(WORD + ":").at(-1))
    tok = n.prop_right(tok_start, hx, 5)
    ends_ok = n.AND(tok, ~n.cls(WORD + ":").at(1))
    whole = n.AND(tok, n.prop_left(ends_ok, hx, 5))
    zone = n.AND(n.cls("%"), n.cls(HEXC + ":").at(-1), n.cls(AL).at(1))
    c.add("IP", n.prop_right(zone, n.cls(AN), 3), 0)
    c.add("IP", n.AND(whole, n.fill(whole, n.AND(whole, n.lit("::")), 5), n.fill(whole, n.AND(tok_start, n.run(hx, 7)), 5),
                      n.fill(whole, n.AND(whole, n.cls(D)), 5)))


def ids(c: Ctx):
    """Identity documents. Defaults for ambiguous shapes follow the shape->label table measured
    on the dev split (see eval/shapes.py); a key in front of the value overrides them."""
    n = c.n
    for pat in (r"[A-Z]{2}\d{5}[A-Z]{2}", r"[A-Z]\d{13}", r"[A-Z]{3}\d{6}[A-Z]", r"[A-Z]\d{7}[A-Z]", r"\d{8}[A-Z]"):
        c.add("IDCARD", c.P(pat)[0])
    bench = not general()
    for k in (11, 12, 13, 14) if bench else ():
        c.add("IDCARD", c.P(rf"\d{{{k}}}", pre=WORD + "+")[0], 2)
    for pat in (r"\d{9}", r"[A-Z]{2}\d{7}", r"\d{2}[A-Z]{2}\d{5}", r"[A-Z]\d{2}[A-Z]\d{4}[A-Z]", r"[A-Z]{3}\d{6}") if bench else ():
        c.add("PASSPORT", c.P(pat, pre=WORD + "+")[0])
    c.add("DRIVERLICENSE", c.P(r"[A-Z][A-Z0-9]{4}\d{10}")[0])
    c.add("DRIVERLICENSE", c.P(r"[A-Z][A-Z0-9]{4}\d{6}[A-Z]{2}\d{3}")[0])
    c.add("DRIVERLICENSE", c.P(r"[A-Z]\d \d{2} [A-Z0-9]{7} \d")[0])
    for s in (r"\.", " ", "-"):
        c.add("DRIVERLICENSE", c.P(rf"[A-Z][A-Z0-9]{{4}}{s}\d{{6}}{s}\d{s}\d{{3}}")[0])
        c.add("DRIVERLICENSE", c.P(rf"[A-Z][A-Z0-9]{{4}}{s}\d{{6}}{s}[A-Z]{{2}}{s}\d{{3}}")[0])
    if not bench:
        return
    for pat in (r"\d{8}", r"[A-Z]\d{7}", r"[A-Z]\d{8}", r"[A-Z]\d{12}", r"[A-Z]\d{2}[A-Z]{2}\d{7}"):
        c.add("DRIVERLICENSE", c.P(pat, pre=WORD + "+")[0], 2)
    # any other 8-13 character token of capitals and digits that has both: a licence number
    tok, _ = c.P(r"[A-Z0-9]{8,13}", pre=WORD + "_#(", post=WORD + "_(")
    mixed = n.AND(n.fill(tok, n.AND(tok, n.cls(UP)), 4), n.fill(tok, n.AND(tok, n.cls(D)), 4))
    c.add("DRIVERLICENSE", mixed, 3)


def social(c: Ctx):
    n = c.n
    d = n.cls(D)
    G = general()
    for s, raw in ((r"\.", "."), (" ", " "), ("-", "-")):
        sep = n.cls(raw)
        not_mid = dict(start_terms=[~n.AND(d.at(-2), sep.at(-1))], end_terms=[~n.AND(sep.at(1), d.at(2))])
        if G:
            # real-world: NXX-NXX-XXXX is a phone number; AAA-GG-SSSS (valid area/group/serial) is an SSN
            c.add("TEL", c.P(rf"[2-9]\d{{2}}{s}[2-9]\d{{2}}{s}\d{{4}}", pre=WORD + "+", **not_mid)[0], 2)
            c.add("TEL", c.P(rf"\d{{3}}{s}\d{{3}}{s}\d{{4}}", pre=WORD + "+", **not_mid)[0], 3)
            if raw != ".":
                ok = [~n.cls("9"), ~n.lit("000"), ~n.lit("666"), ~n.lit("00").at(4), ~n.lit("0000").at(7)]
                c.add("SOCIALNUMBER", c.P(rf"\d{{3}}{s}\d{{2}}{s}\d{{4}}", pre=WORD + "+-", post=WORD + "-",
                                          start_terms=not_mid["start_terms"] + ok, end_terms=not_mid["end_terms"])[0])
        else:
            for pat in (rf"\d{{3}}{s}\d{{3}}{s}\d{{4}}", rf"\d{{3}}{s}\d{{2}}{s}\d{{4}}"):
                c.add("SOCIALNUMBER", c.P(pat, pre=WORD + "+", **not_mid)[0], 2)
        for pat in (rf"\d{{3}}{s}\d{{4}}{s}\d{{4}}{s}\d{{2}}", rf"\d{s}\d{{2}}{s}\d{{2}}{s}\d{{5}}{s}\d{{3}}{s}\d{{2}}",
                    rf"\d{{2}}{s}\d{{2}}{s}\d{{2}}{s}\d{{2}}{s}[A-Z]\d{{2}}{s}\d",
                    rf"[A-Z][a-z]{{2}}{s}[A-Z][a-z]{{2}}{s}\d{{2}}{s}[A-Z]{s}\d{{2}}{s}\d{s}[A-Z]{{3}}"):
            c.add("SOCIALNUMBER", c.P(pat, pre=WORD + "+", **not_mid)[0])
    c.add("SOCIALNUMBER", c.P(r"[A-Z][a-z]{2}[A-Z][a-z]{2}\d{2}[A-Z]\d{3}[A-Z]{3}")[0])
    c.add("SOCIALNUMBER", c.P(r"\d{8}[A-Z]\d{3}")[0])
    if G:
        c.add("SOCIALNUMBER", c.P(r"[A-Z]{2} ?\d{6} ?[A-Z]")[0])
        c.add("SOCIALNUMBER", c.P(r"[A-Z]{2} \d{2} \d{2} \d{2} [A-Z]")[0])
        v = n.AND(d, said(c, ["ssn", "ssns", "social security number", "social security", "social insurance number",
                               "national insurance number", "sin"]))
        grp = n.OR(d, n.AND(n.cls(" -"), d.at(-1), d.at(1)), force=True)
        tok = n.prop_right(v, grp, 4)
        c.add("SOCIALNUMBER", n.AND(tok, n.fill(tok, n.AND(v, n.run(grp, 9)), 4)), 1)
        pv = n.AND(n.OR(d, n.AND(n.cls("+("), d.at(1))), said(c, [u("फोन"), u("मोबाइल"), u("फ़ोन"), "téléphone", "handynummer", "telefon",
                                                                    "teléfono", "telefono", "celular", "móvil", u("电话"), u("電話"),
                                                                    "call me on", "call me at", "call", "phone", "mobile", "cell", "telephone",
                                                                    "tel", "whatsapp", "fax", "contact number", "reach me at", "reach me on"]))
        pbody = n.OR(d, n.AND(n.cls(" -.)"), d.at(1), n.OR(d.at(-1), n.cls(")").at(-1))), n.AND(n.cls(" -."), n.cls("(").at(1), d.at(2), d.at(-1)),
                     n.AND(n.cls("("), d.at(1)), n.AND(n.cls(")"), d.at(-1)), n.AND(n.cls("+"), d.at(1)), force=True)
        ptok = n.prop_right(pv, pbody, 4)
        c.add("TEL", n.AND(ptok, n.fill(ptok, n.AND(pv, n.atleast(7, *[n.AND(ptok, d).at(k) for k in range(0, 20)])), 4)), 1)
        # phone numbers: any (ddd) ddd-dddd, 1-ddd-ddd-dddd, 001-..., and an extension "x123"
        for pat in (r"0\d{1,2}-\d{3}-\d{4}", r"\(0\d{1,2}\) \d{4} \d{4}", r"\+\d{1,3} \(\d{3}\) ?\d{3}[-. ]\d{4}", r"\(\d{3}\) ?\d{3}[-. ]\d{4}", r"\(\d{3}\)\d{3}-\d{4}", r"1-\d{3}-\d{3}-\d{4}", r"001-\d{3}-\d{3}-\d{4}",
                    r"\(0\d{2,4}\) ?\d{3,4} ?\d{3,4}", r"\+\d{1,3}\.\d{2,4}\.\d{3}\.\d{3,4}"):
            c.add("TEL", c.P(pat, pre=WORD + "+", post=WORD)[0], 1)
        # (NXX) NXX-XXXX and an optional +1 / 1- prefix
        for pat in (r"\([2-9]\d{2}\) ?[2-9]\d{2}[-. ]\d{4}",):
            c.add("TEL", c.P(pat, pre=WORD, post=WORD)[0])
        return
    for k in (10, 15):
        c.add("SOCIALNUMBER", c.P(rf"\d{{{k}}}", pre=WORD + "+")[0], 2)


def tel(c: Ctx):
    n = c.n
    d = n.cls(D)
    sep = n.cls(" .-")
    joint = n.AND(sep, d.at(-1), d.at(1))
    body = n.OR(d, joint, force=True)
    if general():   # "+44 (0)20 7946 0958"
        body = n.OR(d, joint, n.AND(sep, d.at(-1), n.cls("(").at(1), d.at(2)), n.AND(n.cls("("), d.at(1), n.cls(")").at(2)),
                    n.AND(n.cls(")"), d.at(-1), d.at(1)), force=True)
    plus = n.AND(n.cls("+"), d.at(1), ~n.cls(WORD).at(-1))
    zero = n.AND(n.cls("0"), ~n.cls(WORD + "+.:/").at(-1), ~n.AND(d.at(-2), sep.at(-1)))
    social = c.get("SOCIALNUMBER")
    zero = n.AND(zero, ~n.AND(social, ~social.at(-1)))
    c.tel_body = body
    c.tel_ext = True
    for start, need_sep, tier in ((plus, False, 0), (zero, True, 2)):
        span = n.prop_right(start, body, 4)
        digs = n.AND(span, d)
        ok = [start, n.atleast(10, *[digs.at(k) for k in range(0, 22)])]
        if need_sep:
            ok.append(n.OR(*[n.AND(span, joint).at(k) for k in range(1, 16)]))
        c.add("TEL", n.prop_right(n.AND(*ok), body, 4), tier)


def misc_shapes(c: Ctx):
    c.add("GEOCOORD", c.P(r"\[\d{1,2}\.\d{1,5}, -?\d{1,2}\.\d{1,5}\]", pre=None, post=None)[0])
    c.add("SECADDRESS", c.P(rf"({SEC_WORDS}) \d{{1,3}}")[0])
    if general():
        c.add("SECADDRESS", c.P(r"(PO Box|P\.O\. Box|Post Box|PB) \d{1,6}")[0])
        c.add("SECADDRESS", c.P(r"(Flat|Apt|Apartment|Unit|Suite|House|Plot|Door) \d{1,4}[A-Z]?", post=WORD)[0])
    c.add("STATE", c.P("(ENG|WLS|SCT|NIR|SCOT)", pre=WORD + "-", post=WORD + "-")[0])
    n = c.n
    the = n.lit("the ", nocase=True).at(-4)
    names = COUNTRIES if general() else "United Kingdom|United States|France|Italia|Nederland|Deutschland|Schweiz|España"
    c.add("COUNTRY", c.P(f"({names})", start_terms=[] if general() else [~the])[0])
    if general():
        c.add("CITY", c.P(f"({CITIES})", pre=WORD + "-", post=WORD + "-")[0], 2)
        c.add("STATE", c.P(f"({STATE_NAMES})", pre=WORD + "-", post=WORD + "-")[0], 2)
        num = r"\d{1,3}\.\d{3,8}"
        not_decimal = ~n.AND(n.cls("."), n.cls(D).at(1)).at(1)
        for sep in (", ", ",", " "):
            for lead in ("", "-"):
                c.add("GEOCOORD", c.P(lead + num + sep + "-?" + num, pre=WORD + ".-", post=WORD, end_terms=[not_decimal])[0])
        c.add("GEOCOORD", c.P(num + " ?[NS], ?" + num + " ?[EW]", pre=WORD + ".-")[0])
        deg = "\u00b0"
        c.add("GEOCOORD", c.P(r"\d{1,3}\.\d{2,8}" + deg + " ?[NS],? ?" + r"\d{1,3}\.\d{2,8}" + deg + " ?[EW]", pre=WORD + ".-")[0])
        c.add("GEOCOORD", c.P(r"GPS(Latitude|Longitude): \d{1,3}/1, \d{1,2}/1, \d{1,5}/\d{1,3}", pre=WORD)[0])
        c.add("GEOCOORD", c.P("Latitude: -?" + num + ", Longitude: -?" + num, pre=WORD, post=WORD, end_terms=[not_decimal])[0])
    sp = n.cls(" ")
    in_text_l = n.AND(sp.at(-1), n.cls(LO).at(-2))          # "... the IT support"
    in_text_r = n.AND(sp.at(1), n.cls(LO).at(2))
    c.add("COUNTRY", c.P("(GB|US|ES|CH|FR|DE|IT|NL|UK)", pre=WORD + "<_/@.-", post=WORD + "_@.-",
                         start_terms=[~in_text_l], end_terms=[~in_text_r])[0], 2)
    c.add("POSTCODE", c.P(r"\d{5}-\d{4}", pre=WORD + "+-.", post=WORD + "-")[0])
    c.add("SEX", c.P("(Female|Male|Feminine|Masculine|Prefer not to disclose|Non-binary|Non-Binary)")[0])
    c.title_vocab = c.P(f"({TITLES})", post=WORD + "-.")[0]
    if not general():
        c.add("TITLE", c.title_vocab)


def obfuscation(c: Ctx):
    """General profile. Text deliberately broken up: spaced characters ("p r i y a @ g m a i l . c o m",
    "9 8 7 6 5 4 3 2 1 0"), symbols written as words in any case ("priya AT gmail DOT com")."""
    if not general():
        return
    n = c.n
    an, sp, d = n.cls(AN), n.cls(" "), n.cls(D)
    single = n.AND(an, ~an.at(-1), ~an.at(1))
    sym = n.AND(n.cls("@."), sp.at(-1), sp.at(1))
    unit = n.OR(single, sym, force=True)
    spaced = n.OR(n.AND(unit, n.OR(n.AND(sp.at(1), unit.at(2)), n.AND(sp.at(-1), unit.at(-2)))),
                  n.AND(sp, unit.at(-1), unit.at(1)), force=True)
    start = n.AND(spaced, ~spaced.at(-1))
    run = n.prop_right(start, spaced, 6)
    has_at = n.fill(run, n.AND(run, n.cls("@")), 6)
    has_dot = n.fill(run, n.AND(run, n.cls("."), n.prop_right(n.AND(run, n.cls("@")), run, 6)), 6)
    c.add("EMAIL", n.AND(run, has_at, has_dot), 0)
    digits = n.AND(run, d)
    ten = n.atleast(9, *[digits.at(k) for k in range(0, 24)])
    c.add("TEL", n.AND(run, n.fill(run, n.AND(start, ten), 6), ~has_at), 1)
    # words for symbols, any case: "priya AT gmail DOT com", "priya (at) gmail [dot] com"
    for at, dot in (("(at|AT|At)", "(dot|DOT|Dot)"), (r"\((at|AT)\)", r"\((dot|DOT)\)"), (r"\[(at|AT)\]", r"\[(dot|DOT)\]")):
        c.add("EMAIL", c.P(rf"[\w.]{{2,}} ?{at} ?[\w\-]{{2,}} ?{dot} ?[a-zA-Z]{{2,6}}", pre=WORD, post=WORD)[0], 0)


def national_ids(c: Ctx):
    """General profile. National identifier layouts from several countries; each is either self-validating by
    shape or needs its keyword (TFN, NIR, ITIN ...)."""
    if not general():
        return
    n = c.n
    d = n.cls(D)
    shapes = (r"9\d{2}-[7-9]\d-\d{4}",                                  # US ITIN
              r"\d[A-Z][A-Z0-9]\d-[A-Z][A-Z0-9]\d-[A-Z][A-Z0-9]\d{2}",   # US Medicare MBI
              r"[12] \d{2} \d{2} \d{2} \d{3} \d{3} \d{2}",            # France NIR
              r"\d{3}\.\d{3}\.\d{3}-\d{2}",                           # Brazil CPF
              r"\d{6}-\d{4}", r"\d{8}-\d{4}",                          # Swedish personnummer
              r"\d{17}[0-9X]",                                           # China resident ID
              r"[STFGM]\d{7}[A-Z]",                                      # Singapore NRIC / FIN
              r"784-\d{4}-\d{7}-\d",                                    # UAE Emirates ID
              r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]",                  # Italy codice fiscale
              r"\d{8}[A-Z]", r"[XYZ]\d{7}[A-Z]",                          # Spain DNI / NIE
              r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z][0-9A-Z]",                 # India GSTIN (contains a PAN)
              r"\d{2}-\d{4}-\d{4}-\d{4}",                               # India ABHA number
              r"[A-Z]{3}\d{7}")                                           # India voter ID (EPIC)
    for pat in shapes:
        c.add("ID", c.P(pat, pre=WORD + "-.", post=WORD + "-")[0], 1)
    grp = n.OR(d, n.AND(n.cls(" -"), d.at(-1), d.at(1)), force=True)
    kv = n.AND(d, said(c, ["tfn", "medicare", "nhs", "nhs number", "sin", "bsn", "nir", "insee", "abn", "uan", "esic", "ration card",
                           "ssn ending", "ending in", "ending", "last 4", "last four", "aadhaar", "aadhar", "personnummer"]))
    c.add("ID", n.prop_right(kv, grp, 4), 1)
    # passport machine-readable zone: lines of capitals, digits and "<" filler
    mrz, _ = c.P(r"[A-Z0-9<]{30,48}", pre=WORD + "<", post=WORD + "<")
    c.add("ID", n.AND(mrz, n.fill(mrz, n.AND(mrz, n.lit("<<")), 6)), 0)
