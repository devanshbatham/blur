"""Values recognised from the field they sit in: usernames, keyed values, identifiers, structured
records."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)
from .persons import names
from .urls import url_parts


def username(c: Ctx):
    low = r"[\l]"
    pre, post = WORD + "@._-:/<", WORD + "@_"
    pats = [rf"{low}{{5,}}\d{{1,6}}", rf"{low}{{3,4}}\d{{2,6}}", rf"\d{{1,4}}{low}{{3,}}",
            rf"{low}{{3,}}\.{low}{{3,}}\d{{0,4}}", rf"\d{{1,4}}{low}{{3,}}\.{low}{{3,}}",
            rf"{low}{{3,}}-{low}{{2,}}\.{low}{{3,}}\d{{0,4}}", rf"\d{{1,4}}{low}{{3,}}-{low}{{2,}}\.{low}{{3,}}"]
    if general():
        pats += [r"[A-Z][a-z]{2,}\d{2,4}", r"[A-Z][a-z]{2,}[A-Z][a-z]{2,}\d{2,4}", rf"{low}{{2}}\d{{3,6}}",
                 r"[A-Z][a-z]{2,}_[A-Z][a-z]{2,}[A-Za-z]*\d{0,4}",
                 rf"{low}{{2,}}_{low}{{2,}}\d{{1,5}}", rf"{low}{{2,}}_\d{{2,6}}"]
    else:
        pats += [r"\d{2}[A-Z]{1,3}\d{4}", r"[A-Z]{3}\d{2}", r"\d{2}[A-Z]{2,3}\d{2}", r"\d{2,4}[A-Z]{1,3}", r"[A-Z]{1,3}\d{4}"]
    if general():
        c.add("USERNAME", c.P(r"@[A-Za-z][\w]{2,29}", pre=WORD + "@._-/", post=WORD + "@./")[0])
    www = c.n.lit("www.")
    code_tail = c.n.OR(*[c.n.AND(c.n.lit("." + e), ~c.n.cls(AN).at(len(e) + 1)) for e in
                         ("json", "get", "post", "py", "js", "ts", "com", "org", "net", "txt", "html", "log", "csv", "yaml", "yml",
                          "xml", "md", "sh", "exe", "dll", "jar", "zip", "png", "jpg", "pdf", "io", "dev", "app", "status",
                          "text", "data", "value", "keys", "items", "append", "format", "lower", "upper", "split", "strip")])
    for pat in pats:
        um = c.P(pat, pre=pre, post=post, start_terms=[~www], end_terms=[~c.n.AND(c.n.cls("\"'").at(1), c.n.cls(":").at(2)),
                                                                   ~c.n.cls("=:").at(1)])[0]
        c.add("USERNAME", c.n.AND(um, ~c.n.fill(um, c.n.AND(um, code_tail), 5)))


def keyed(c: Ctx):
    n = c.n
    d = n.cls(D)
    token = lambda v: n.prop_right(v, c.tokbody, 5)
    capword = lambda v: n.prop_right(n.AND(v, c.wstart), c.wordc, 5)
    number = lambda v, lo, hi: n.OR(*[n.spread_right(n.AND(v, n.run(d, k), ~c.W.at(k)), k) for k in range(lo, hi + 1)])

    v_last = cue(c, ["last name", "lastname", "last_name", "surname", "family name", "familyname"])
    v_given = cue(c, ["given name", "givenname", "given_name", "first name", "firstname", "first_name", "forename",
                      "middle name", "middlename", "second name"], veto=[v_last])
    v_user = cue(c, ["username", "user name", "user_name", "userid", "user id", "handle"])
    v_name = cue(c, ["name"], veto=[v_last, v_given, v_user], whole=True)
    lower2 = n.cls(LO + HI).at(1)
    step = lambda prev: n.prop_right(n.AND(c.wstart, n.OR(n.AND(n.cls(" ").at(-1), prev.at(-2)),
                                                           n.AND(n.cls(" ").at(-1), n.cls(",").at(-2), prev.at(-3)))), c.wordc, 5)
    for label, v in (("LASTNAME", v_last), ("GIVENNAME", v_given)):
        cur = capword(v)
        for _ in range(4):
            c.add(label, cur, 1)
            cur = step(cur)
    generic = capword(n.AND(v_name, lower2))
    c.generic_names = [generic]
    prev = generic
    for _ in range(3):
        prev = n.prop_right(n.AND(c.wstart, lower2, n.cls(" ").at(-1), prev.at(-2)), c.wordc, 5)
        c.generic_names.append(prev)
    utok = token(v_user)
    c.add("USERNAME", n.AND(utok, ~n.fill(utok, n.AND(utok, c.english, ~c.english.at(-1)), 5)) if hasattr(c, "english") else utok, 1)
    c.any_value = n.AND(c.W, ~c.key, ~c.tag, ~n.cls("</").at(-1), n.prop_right(c.key, c.skip, 3).at(-1), ~c.key.at(-1))

    v_sex = cue(c, ["sex", "gender"], whole=True)
    c.add("SEX", n.AND(v_sex, n.cls("MFO"), ~c.W.at(1)), 1)
    c.add("SEX", n.spread_right(n.AND(v_sex, n.lit("Other"), ~c.W.at(5)), 5), 1)
    v_title = cue(c, ["title"], whole=True)
    t_tok = capword(v_title)
    c.add("TITLE", n.fill(t_tok, n.AND(t_tok, ~c.wordc.at(1), ~n.cls(" ").at(1)), 4), 1)
    c.add("TIME", number(cue(c, ["time", "schedule", "hour"], whole=True), 1, 2), 1)
    c.add("BUILDING", number(cue(c, ["building"]), 1, 4), 1)
    inner_sp = n.AND(n.cls(" "), c.W.at(1), c.W.at(-1))
    fbody = n.AND(n.OR(n.cls(AL + HI + D + "'.-"), inner_sp, force=True), ~c.key, ~c.tag)
    for label, words in (("CITY", ["city"]), ("STREET", ["street"]), ("COUNTRY", ["country"]), ("STATE", ["state"])):
        v = cue(c, words, whole=True)
        if label == "STATE":
            c.add(label, capword(v), 1)
        elif label == "COUNTRY":
            joint = n.AND(n.cls(" "), c.cap.at(-1), c.wstart.at(1))
            c.add(label, n.prop_right(capword(v), n.OR(c.cap, joint, force=True), 5), 1)
        else:
            c.add(label, n.prop_right(n.AND(v, n.cls(UP + HI)), fbody, 5), 1)
    v_social = cue(c, ["social", "ssn", "security number"])
    v_idcard = cue(c, ["id card", "idcard", "id_card", "national id", "identity card", "identification"])
    v_dl = cue(c, ["license", "licence", "driver"])
    v_pp = cue(c, ["passport"])
    v_tel = cue(c, ["telephone", "phone", "mobile", "contact number", "tel"])
    has_digit = lambda v: n.AND(v, n.OR(*[n.AND(d, n.prop_right(v, c.tokbody, 4)).at(k) for k in range(0, 10)]))
    c.add("SOCIALNUMBER", token(n.AND(v_social, d)), 1)
    letter = n.cls(AL)
    id_word = n.AND(n.lit("id", nocase=True), ~letter.at(-1), ~letter.at(2), n.OR(c.key, c.tag), ~c.ctag)
    v_id = n.AND(c.W, ~c.key, ~c.tag, ~n.cls("</").at(-1), n.prop_right(id_word, c.skip, 5).at(-1),
                 ~v_social, ~v_dl, ~v_pp, ~v_user)
    if not general():
        c.add("IDCARD", token(n.AND(v_id, d, n.run(d, 6))), 1)
    social_sep = c.get("SOCIALNUMBER", 0)
    sep_social = n.OR(social_sep, c.get("SOCIALNUMBER", 2))
    dashed = n.AND(sep_social, n.cls("-. "))
    after_social = n.prop_right(n.fill(sep_social, dashed, 4), n.cls(", \n\t|;"), 3)
    v_after = n.AND(d, after_social.at(-1), ~sep_social, ~d.at(-1), n.run(d, 9))
    c.add("IDCARD", n.OR(*[n.spread_right(n.AND(v_after, n.run(d, k), ~c.W.at(k)), k) for k in range(9, 15)]), 1)
    c.add("IDCARD", token(has_digit(v_idcard)), 1)
    c.add("DRIVERLICENSE", token(has_digit(v_dl)), 1)
    c.add("PASSPORT", token(has_digit(v_pp)), 1)
    c.add("POSTCODE", number(cue(c, ["postcode", "postal", "zip"]), 4, 5), 1)
    tel_v = n.AND(n.OR(v_tel, n.AND(n.cls("+"), v_tel.at(1))), n.OR(d, n.cls("+")))
    c.add("TEL", n.prop_right(tel_v, c.tel_body, 4), 1)
    c.v_pass = cue(c, ["password", "passcode", "passkey", "pass code"])


def identifiers(c: Ctx):
    """General profile. An identifier is a token containing digits that follows an identifying
    word ("customer ID is CUST051927", "MRN: 3456721", "the pin for this shipment is 614398").
    A URL is a scheme or www. followed by URL characters."""
    if not general():
        return
    n = c.n
    low, d = n.cls(LO), n.cls(D)
    joint = n.OR(n.AND(n.cls("-./"), c.W.at(-1), n.cls(AN).at(1)), n.AND(n.cls(" "), c.W.at(-1), d.at(1)))
    body = n.OR(n.cls(AN), joint, force=True)
    other = n.OR(*[c.get(lab) for lab in ("TEL", "SOCIALNUMBER", "DATE", "BOD", "IP", "EMAIL", "TIME", "GEOCOORD")], force=True)
    masked_run = n.OR(n.lit("XXX"), n.lit("xxx"), n.lit("***"), n.lit("###"))
    # a reference cue applies to the value right after it ("booking BK-2231"), never across other words: in
    # "paid for the booking using his card 5476 ..." the number belongs to "card"
    np_start = n.AND(n.cls(AN + "#"), said(c, NOT_PERSONAL + ["chargeback form", "loan application"]))
    c.not_personal = n.prop_right(np_start, n.OR(n.cls(AN + "-._"), force=True), 5)
    # a lowercase-led value is an identifier only when its first word has a digit ("a3f9c2e1"), never a verb ("replaces 19")
    an = n.cls(AN)
    lw_start = n.AND(low, n.run(an, 8), ~an.at(-1))
    lw_word = n.prop_right(lw_start, an, 5)
    lw_ok = n.AND(lw_start, n.fill(lw_word, n.AND(lw_word, d), 5))
    for loose, need in ((False, 3), (True, 4)):
        start = n.AND(n.OR(n.cls(UP + D), n.AND(lw_ok, n.run(an, 8)), force=True), said(c, ID_CUES, loose))
        tok = n.prop_right(start, body, 5)
        ok = n.AND(tok, n.fill(tok, n.AND(tok, d), 5), n.fill(tok, n.AND(start, n.run(body, need)), 5),
                   ~n.fill(tok, n.AND(tok, other), 5), ~n.fill(tok, n.AND(tok, masked_run), 5))
        c.add("ID", ok, 1)
        if not loose:
            # introduced as a bank account ("account number is 745-3216598721", "a/c 001234567890"): a financial account,
            # with six or more digits; an "account reference" is a customer reference, not a bank account
            acc = n.AND(ok, n.fill(tok, n.AND(start, said(c, ["account", "acct", "a/c", "bank account", "savings account",
                                                                "current account", "checking account"])), 5),
                        n.fill(tok, n.atleast(6, *[n.AND(tok, d).at(k) for k in range(0, 24)]), 5),
                        ~n.fill(tok, n.AND(start, said(c, ["account reference", "account ref", "account id", "account name"])), 5))
            c.add("BANK", acc, 1)
    for pat in (r"[A-Za-z]{1,4}-\d{4,10}", r"[A-Za-z]{1,4}-\d{4,10}-[A-Za-z]{1,2}", r"[A-Z]{2,5}\d{5,12}", r"[A-Z]\d{6,12}-[A-Za-z]{1,2}",
                r"[A-Z]\d{8,12}"):
        c.add("ID", c.P(pat, pre=WORD + "-_/.", post=WORD + "-_/")[0], 0)
    ibody = n.OR(n.cls(UP + D), n.AND(n.cls(" "), n.cls(UP + D).at(-1), n.cls(UP + D).at(1)), force=True)
    ihead, _ = c.P(r"[A-Z]{2}\d{2}", pre=WORD, post=None)
    istart = n.AND(ihead, ~ihead.at(-1))
    itok = n.prop_right(istart, ibody, 5)
    iban = n.AND(itok, n.fill(itok, n.AND(istart, n.run(ibody, 15), n.atleast(8, *[n.AND(itok, d).at(k) for k in range(0, 34)])), 5))
    c.add("ID", iban, 0)
    c.iban = iban
    for sep in (" ", "-"):
        for last in ("{4}", "{3}", "{2}", "{1}"):
            c.add("CARD", n.AND(c.P(rf"\d{{4}}{sep}\d{{4}}{sep}\d{{4}}{sep}\d{last}", pre=WORD + "+-.", post=WORD + "-")[0], ~c.iban), 0)
    cv = n.AND(d, said(c, ["credit card number", "credit card", "debit card", "card number", "ccn", "ccns", "card"]))
    ctok = n.prop_right(cv, n.OR(d, n.AND(n.cls(" -"), d.at(-1), d.at(1)), force=True), 4)
    c.add("CARD", n.AND(ctok, n.fill(ctok, n.AND(cv, n.run(d, 4)), 4), n.fill(ctok, n.AND(cv, n.atleast(12, *[n.AND(ctok, d).at(k) for k in range(0, 20)])), 4)), 1)
    c.add("ID", c.P(r"\d{4} \d{4} \d{4}", pre=WORD + "+-.", post=WORD + "-", end_terms=[~n.AND(n.cls(" "), d.at(1)).at(1)],
                    start_terms=[~n.AND(d.at(-2), n.cls(" ").at(-1))])[0], 2)                      # 12 digits in three groups
    c.add("ID", c.P(r"[A-Z]{5}\d{4}[A-Z]")[0], 0)                                                 # tax-id shape AAAAA9999A
    c.add("ID", c.P(r"[A-Z]{2} \d{2} [A-Z]{1,2} \d{4}")[0], 0)                                    # vehicle registration
    kv = n.AND(n.cls(AN), n.OR(said(c, ["api key", "apikey", "access key", "secret key", "api token", "auth token", "access token", "token"]),
                               said(c, ["api key", "access key", "secret key", "api token"], True)))
    ktok = n.prop_right(kv, n.cls(AN + "_-"), 6)
    c.add("SECRET", n.AND(ktok, n.fill(ktok, n.AND(kv, n.run(n.cls(AN + "_-"), 12)), 6)), 0)
    ev = n.AND(d, said(c, ["exp", "expiry", "expires", "expiration", "valid thru", "valid through", "cad", "caducidad",
                           "vence", "validade", "gültig bis", "expire"]))
    c.add("CARD_EXPIRY", n.spread_right(n.AND(ev, c.P(r"(0[1-9]|1[0-2])\d{2}", pre=WORD, post=WORD)[0]), 4), 1)
    c.add("CARD_EXPIRY", n.OR(n.spread_right(n.AND(ev, c.P(r"\d{2}/\d{2}")[0], ~d.at(-1)), 5), n.spread_right(n.AND(ev, n.AND(c.P(r"\d{2}/\d{4}")[0], ~d.at(-1))), 7)), 1)
    for pat in (r"[A-Z]{2,5}-\d{2,6}-\d{2,6}-\d{1,4}", r"[A-Z]{2,5}-\d{2,6}-\d{2,6}", r"[A-Z]{2,5}/\d{4}/\d{3,6}",
                r"[A-Z]{2}-\d{2}-\d{4}-\d{7}", r"[A-Z]{2}\d{2} ?\d{4}\d{7}"):
        c.add("ID", c.P(pat, pre=WORD + "-/", post=WORD + "-/")[0], 0)
    for pat in (r"[A-Z]{2,5}-[A-Z0-9]{6,12}", r"[A-Z]\d{2,4}-\d{3,4}-\d{3,4}", r"\d{2}-\d{6}-\d{2}", r"[A-Z]\d{2}-\d{4}-\d{3}-\d{2}",
                r"[A-Z]\d{3,4}-\d{4}-\d{3}-\d", r"[A-HJ-NPR-Z0-9]{17}", r"[A-Z]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}"):
        cm = c.P(pat, pre=WORD + "-/", post=WORD + "-/")[0]
        c.add("ID", n.AND(cm, n.fill(cm, n.AND(cm, d, n.cls(D + UP).at(1)), 6)), 2)
    # a run of six or more digits as a URL path segment ("/kyc/aadhaar/234567890123")
    seg_num, _ = c.P(r"\d{6,19}", pre=WORD, post=WORD)
    c.add("ID", n.AND(seg_num, n.fill(seg_num, n.AND(seg_num, ~seg_num.at(-1), n.cls("/").at(-1)), 5)), 1)
    hx = "[0-9a-fA-F]"
    c.add("ID", c.P(f"{hx}{{8}}-{hx}{{4}}-{hx}{{4}}-{hx}{{4}}-{hx}{{12}}", pre=WORD + "-", post=WORD + "-")[0], 0)
    c.add("DATE", c.P(r"(19|20)\d{2}(01|02|03|04|05|06|07|08|09|10|11|12)[0-3]\d", pre=WORD + "+-.,:/%$#", post=WORD + "-.:/%")[0], 2)
    bound = WORD + "+-.,:/%$#"
    long_num, _ = c.P(r"\d{8,19}", pre=bound, post=WORD + "-.:/%")
    epoch = n.OR(c.P(r"1[5-9]\d{8}", pre=bound, post=WORD)[0], c.P(r"1[5-9]\d{11}", pre=bound, post=WORD)[0],
                 c.P(r"(19|20)\d{2}(0|1)\d[0-3]\d[0-2]\d[0-5]\d[0-5]\d", pre=bound, post=WORD)[0])
    c.add("ID", n.AND(long_num, ~epoch), 3)
    code, _ = c.P(r"[A-Z0-9]{2,6}-?[A-Z0-9]{3,12}", pre=WORD + "-_#/.", post=WORD + "-_/")
    digits4 = n.atleast(4, *[n.AND(code, d).at(k) for k in range(0, 19)])
    c.add("ID", n.AND(code, n.fill(code, n.AND(code, ~code.at(-1), digits4), 5), n.fill(code, n.AND(code, n.cls(UP)), 5)), 3)
    url = r"[\w\-./?%&=:#~+@]*[\w/]"
    c.add("URL", c.P(r"[a-z0-9\-]{2,}\.(com|org|net|in|io|co|edu|gov)/[\w\-./?%&=:#~+@]*[\w/]", pre=WORD + "/@.-", post=WORD + "/")[0], 3)
    url_parts(c)
    for head in ("https://", "http://", "ftp://", r"www\."):
        c.add("URL", c.P(head + url, pre=WORD + "/@.", post=WORD + "/")[0], 3)


def structured(c: Ctx):
    """General profile. Values carried by structure rather than by words: URL query parameters and
    path segments, UPI and crypto addresses, password hashes, one-time codes, security answers,
    hostnames and home directories, plus codes and DMS coordinates."""
    if not general():
        return
    n = c.n
    d, up = n.cls(D), n.cls(UP)
    qv = n.cls("".join(ch for ch in map(chr, range(33, 127)) if ch not in "&#\"'<>`|,;)]}") + HI)
    lead = n.cls("?&#;")

    def param(names, label, tier=0):
        hits = [n.AND(n.lit(w + "=", nocase=True), lead.at(-1)).at(-len(w)) for w in names]   # fires on the "="
        eq = n.OR(*hits)
        c.add(label, n.prop_right(n.AND(qv, eq.at(-1)), qv, 7), tier)

    param(["token", "access_token", "id_token", "refresh_token", "api_key", "apikey", "key", "secret", "password", "pwd",
           "pass", "auth", "session", "sessionid", "sid", "sig", "signature", "code", "otp", "X-Amz-Signature",
           "X-Amz-Credential", "X-Amz-Security-Token", "X-Goog-Signature", "X-Goog-Credential", "client_secret"], "SECRET")
    param(["email", "e", "mail", "utm_content"], "EMAIL")
    param(["phone", "mobile", "tel", "msisdn"], "TEL")
    param(["user", "uid", "user_id", "userid", "username", "customer_id", "account_id", "pa", "cc", "pan"], "ID")
    param(["pn", "name", "fullname", "first_name", "last_name"], "GIVENNAME")
    # userinfo: scheme://USER:password@host
    sch = n.lit("://").at(-2)
    ui = n.cls(AN + "._%+-")
    usr = n.prop_right(n.AND(ui, sch.at(-1)), ui, 5)
    usr_ok = n.fill(usr, n.AND(usr, ~ui.at(1), n.cls(":").at(1)), 5)
    pwc = n.cls("".join(chr(i) for i in range(33, 127) if chr(i) not in "@/ ?#"))
    has_at = n.prop_right(n.AND(n.cls(":"), usr.at(-1)), pwc, 6)
    svc = n.OR(*[n.lit(x) for x in ("svc_", "svc-", "sa-", "service", "app_", "root", "postgres", "admin")],
               *[n.AND(n.lit(x + ":"), ~n.cls(AN).at(-1)) for x in ("app", "api", "web", "db", "backend", "worker", "deploy", "ci",
                                                                     "bot", "readonly", "replica", "sa", "svc", "mysql", "redis")])
    c.sure_user = [n.AND(usr_ok, n.fill(usr, n.AND(usr, ~ui.at(1), n.prop_left(n.AND(has_at, n.cls("@").at(1)), has_at, 6).at(1)), 5),
                         ~n.fill(usr, n.AND(usr, ~usr.at(-1), svc), 5))]
    sv = n.AND(c.W, said(c, ["ssid", "wifi name", "wi-fi name", "network name"]))
    c.add("ID", n.prop_right(sv, n.cls(AN + "_-."), 4), 1)
    # personal path segments: /users/<x>/, /u/<x>/, /profile/<x>, /home/<x>/, C:\Users\<x>\
    seg = n.cls(AN + HI + "._-%+")
    heads = ["/users/", "/user/", "/u/", "/profile/", "/profiles/", "/people/", "/members/", "/home/", "/employees/",
             "/patients/", "\\Users\\", "\\users\\", "/Users/"]
    ends = n.OR(*[n.lit(h).at(-(len(h) - 1)) for h in heads])
    c.sure_user.append(n.prop_right(n.AND(seg, ends.at(-1)), seg, 6))
    kvv = n.cls(AN + "%._-+/:|~!*=")
    keq = n.AND(n.cls("="), n.cls(AN + "_.-").at(-1), n.cls(AN + "%").at(1))
    kval = n.prop_right(n.AND(kvv, keq.at(-1)), n.AND(kvv, ~n.cls("&;,").at(0)), 7)
    k0 = n.AND(kval, keq.at(-1))
    # a generic key=value is a secret when the value is long and mixes digits, lower and upper case (a token, not a word or an id)
    rnd = n.AND(n.fill(kval, n.AND(kval, d), 7), n.fill(kval, n.AND(kval, n.cls(LO)), 7), n.fill(kval, n.AND(kval, n.cls(UP)), 7),
                n.fill(kval, n.AND(k0, n.run(kvv, 12)), 7))
    c.add("SECRET", n.AND(kval, rnd), 2)
    sess_key = n.OR(*[n.AND(n.lit(w + "=", nocase=True), ~n.cls(AN + "_").at(-1)).at(-len(w)) for w in
                      ("sid", "sessionid", "session", "sess", "token", "auth", "csrf", "xsrf", "eid", "uid", "cid", "gclid", "fbclid", "mc_eid")])
    sess_v = n.AND(n.fill(kval, n.AND(k0, sess_key.at(-1)), 7), n.fill(kval, n.AND(kval, d), 7), n.fill(kval, n.AND(k0, n.run(kvv, 8)), 7))
    c.add("SECRET", n.AND(kval, sess_v), 1)
    c.add("SECRET", c.P(r"\d{8,10}:AA[\w\-]{30,40}", pre=WORD, post=WORD)[0], 0)        # Telegram bot token
    c.add("SECRET", c.P(r"(AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}", pre=WORD, post=WORD)[0], 0)  # AWS key ids, documentation ones included
    hook, _ = c.P(r"hooks\.slack\.com/(services|workflows|triggers)/[A-Za-z0-9/]{20,}", pre=WORD, post=WORD)
    c.add("SECRET", n.AND(hook, n.prop_right(n.lit("/services/").at(-10), n.cls(AN + "/"), 6)), 0)
    cu = n.OR(*[n.lit(f).at(-len(f)) for f in ("-u ", "--user ", "--user=")])
    cu_user = n.prop_right(n.AND(n.cls(AN + "._-"), cu), n.cls(AN + "._-"), 4)
    cu_pass = n.prop_right(n.AND(n.cls(":").at(-1), cu_user.at(-2), ~n.cls(" ")), n.cls("".join(chr(i) for i in range(33, 127) if chr(i) not in "'\"")), 5)
    c.add("PASS", n.AND(cu_pass, ~n.cls(":")), 1)
    c.sure_user.append(n.AND(n.prop_right(n.AND(n.cls(AN + "._-"), cu), n.cls(AN + "._-"), 4),
                             n.prop_left(n.AND(n.cls(AN + "._-"), n.cls(":").at(1)), n.cls(AN + "._-"), 4)))
    c.add("SECRET", c.P(r"github_pat_[\w]{50,100}", pre=WORD, post=WORD)[0], 0)
    c.add("SECRET", c.P(r"(api_test|api_live|api_dev|api_prod|api_key|sk_live|sk_test|rk_live)_[A-Za-z0-9]{16,}", pre=WORD, post=WORD)[0], 0)
    # deep links and messaging links carrying a phone number
    for h in ("tel:", "sms:", "wa.me/", "phone="):
        e = n.lit(h, nocase=True).at(-(len(h) - 1))
        c.add("TEL", n.prop_right(n.AND(n.cls(D + "+"), e.at(-1)), n.cls(D + "-"), 4), 0)
    # payment handles (UPI) and percent-encoded e-mail addresses
    psp = ("okhdfcbank|okaxis|okicici|oksbi|ybl|ibl|axl|apl|paytm|upi|okbizaxis|axisbank|icici|hdfcbank|sbi|kotak|"
           "pthdfc|ptsbi|ptaxis|ptyes|yapl|ikwik|freecharge|jupiteraxis|abdm")
    # (a full stop may end the sentence; only a domain continuing after it makes this an e-mail address)
    c.add("ID", c.P(rf"[\w.\-]{{2,}}@({psp})", pre=WORD + ".@", post=WORD + "@",
                    end_terms=[~n.AND(n.cls(".").at(1), n.cls(AN).at(2))])[0], 0)
    c.add("EMAIL", c.P(r"[\w.+\-]{1,}%40[\w\-.]{1,}\.[a-zA-Z]{2,}", pre=WORD + ".%", post=WORD)[0], 0)
    # crypto addresses and keys
    c.add("ID", c.P(r"bc1[02-9ac-hj-np-z]{25,59}", pre=WORD, post=WORD)[0], 0)
    c.add("ID", c.P(r"0x[0-9a-fA-F]{40}", pre=WORD, post=WORD)[0], 0)
    c.add("ID", c.P(r"[a-z0-9\-]{3,}\.eth", pre=WORD + ".", post=WORD)[0], 1)
    # password hashes
    for pat in (r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{40,}", r"\$argon2(id|i|d)\$[\w$=,./+\-]{20,}",
                r"\$[156y]\$[./A-Za-z0-9=$,]{1,40}\$[./A-Za-z0-9]{20,}", r"[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}"):
        c.add("SECRET", c.P(pat, pre=WORD, post=None)[0], 0)
    # one-time codes, PINs, security answers
    cv2 = n.AND(d, said(c, ["cvv", "cvc", "cvc2", "cid", "cvv2", "security code"]))
    c.add("SECRET", n.prop_right(cv2, d, 2), 0)
    ov = n.AND(d, said(c, ["otp", "one time password", "one-time password", "verification code", "security code", "auth code",
                           "pin", "atm pin", "upi pin", "door code", "passcode", "2fa code"]))
    otok = n.prop_right(ov, d, 3)
    c.add("SECRET", n.AND(otok, n.fill(otok, n.AND(ov, n.run(d, 4)), 3)), 1)
    av = n.AND(c.W, said(c, ["maiden name", "first pet", "security answer", "first school", "childhood friend",
                             "favourite teacher", "favorite teacher", "birthplace", "answer is", "answer was", "answer:",
                             "the answer is", "secret answer", "memorable word", "memorable answer"]))
    atok = n.prop_right(av, n.OR(c.W, n.AND(n.cls(" "), c.W.at(-1), up.at(1)), force=True), 5)
    c.add("SECRET", n.AND(atok, ~n.fill(atok, n.AND(atok, n.cls(":").at(1)), 5)), 0)     # "Answer:" is a key, not the answer
    # Wi-Fi QR payloads
    nosemi = "[" + "".join("\\" + ch if ch in "\\]-^[" else ch for ch in map(chr, range(32, 127)) if ch != ";") + "]"
    c.add("SECRET", c.P(rf"WIFI:S:{nosemi}{{1,32}};T:\w{{3,4}};P:{nosemi}{{1,63}};;", pre=None, post=None)[0], 0)
    # hostnames and machine names that carry a person's name
    dev_words = "macbook|macbook-pro|macbook-air|iphone|ipad|laptop|pc|desktop|phone|pixel|galaxy|thinkpad|ideapad|xps|surface|notebook|imac|mini|workstation|android|tablet|dell|hp|lenovo|asus|acer|nb|ws"
    dev_words += "|mbp|mba|lt|dt|wks|vm|box"
    for pat in (rf"[A-Z]{{3,}}-({dev_words.upper()})(.local|.LOCAL)?", rf"[A-Z]{{2,}}-[A-Z]{{2,}}-({dev_words.upper()})(.local|.LOCAL)?",
                rf"[A-Z][a-z]{{2,}}-[A-Z][a-z]{{2,}}-({dev_words}|{dev_words.upper()})(.local)?", rf"[A-Z][a-z]{{2,}}-({dev_words}|{dev_words.title()})(.local)?",
                rf"[a-z]{{3,}}-({dev_words})(.local)?",
                r"(DESKTOP|LAPTOP)-[A-Z]{3,}[0-9]{0,3}",
                r"[A-Z]{3,}-(MACBOOK|MACBOOK-PRO|MACBOOK-AIR|IPHONE|IPAD|LAPTOP|PC|DESKTOP)(.local)?"):
        c.sure_user.append(c.P(pat, pre=WORD + "-", post=WORD + "-")[0])
    pk, pk_end = c.P(r"(ssh-rsa|ssh-ed25519|ssh-dss|ecdsa-sha2-nistp256) [A-Za-z0-9+/=]{16,} ", pre=WORD, post=None)
    c.sure_user.append(n.prop_right(n.AND(n.cls(AN), pk_end.at(-1)), n.cls(AN + "@._-"), 5))
    # location codes: plus codes, what3words, degrees-minutes-seconds
    pc = "[23456789CFGHJMPQRVWX]"
    c.add("GEOCOORD", c.P(rf"{pc}{{4,8}}\+{pc}{{2,3}}", pre=WORD + "+", post=WORD)[0], 0)
    c.add("GEOCOORD", c.P(r"///[a-z]{2,}\.[a-z]{2,}\.[a-z]{2,}", pre=WORD, post=WORD)[0], 0)
    deg, q1 = "\u00b0", "['\u2032]"
    q2 = "[\"\u2033]"
    dms = r"\d{1,3}" + deg + r"\d{1,2}" + q1 + r"\d{1,2}[.0-9]*" + q2 + "[NSEW]"
    c.add("GEOCOORD", c.P(dms + " ?" + dms, pre=WORD, post=WORD)[0], 0)
    c.add("GEOCOORD", c.P(r"@-?\d{1,3}\.\d{3,8},-?\d{1,3}\.\d{3,8}", pre=WORD, post=None)[0], 0)
    c.add("GEOCOORD", c.P(r"q=-?\d{1,3}\.\d{3,8},-?\d{1,3}\.\d{3,8}", pre=WORD, post=WORD)[0], 0)
    # MAC in Cisco dotted notation
    c.add("MAC", c.P(r"[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}", pre=WORD + ".", post=WORD + ".")[0], 0)
    # card numbers in other layouts (14 digits 4-6-4, 19 digits, unspaced 13-19 with a card prefix)
    for pat in (r"3\d{3}[ -]\d{6}[ -]\d{4}", r"[3-6]\d{3}[ -]\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{3}", r"[3-6]\d{12,18}"):
        c.add("CARD", c.P(pat, pre=WORD + "+-.", post=WORD + "-")[0], 2)
    for pat in (r"[3-6]\d{3} ?[-./] ?\d{4} ?[-./] ?\d{4} ?[-./] ?\d{4}", r"[3-6]\d{3} \d{4}\n\d{4} \d{4}"):
        c.add("CARD", c.P(pat, pre=WORD + "+-.", post=WORD + "-")[0], 0)
    c.add("TEL", c.P(r"\d{5}[\xf0-\xf4][\x80-\xbf]{3}\d{5}", pre=WORD, post=WORD)[0], 1)
    c.add("ID", c.P(r"\d{2} BH \d{4} [A-Z]{1,2}", pre=WORD, post=WORD)[0], 0)
    c.add("ID", c.P(r"[2-9]\d{3} [0-9O]{4} [0-9O]{4}", pre=WORD, post=WORD)[0], 1)
    # encoded payloads that may hide PII: data URIs, and base64 tokens after a contact or data cue
    b64c = "[A-Za-z0-9+/]"
    c.add("SECRET", c.P(rf"base64,{b64c}{{8,}}=?=?", pre=None, post=WORD)[0], 0)
    bv = n.AND(n.cls(AN), said(c, ["contact", "email", "e-mail", "payload", "data", "u", "token", "user"]))
    btok = n.prop_right(bv, n.cls(AN + "+/="), 6)
    b64ish = n.AND(btok, n.fill(btok, n.AND(bv, n.run(n.cls(AN + "+/="), 16)), 6), n.fill(btok, n.AND(btok, n.cls(UP)), 6),
                   n.fill(btok, n.AND(btok, n.cls(LO)), 6), n.OR(n.fill(btok, n.AND(btok, d), 6), n.fill(btok, n.AND(btok, n.cls("=")), 6)))
    c.add("TEL", c.P(r"[6-9]\.\d{6,9}E9", pre=WORD, post=WORD)[0], 1)                         # a phone number stored as a float
    c.add("SECRET", b64ish, 1)
    # VAT numbers belong to businesses: any VAT-shaped number within a short distance after "VAT"
    vat_near = n.spread_right(n.lit("VAT"), 40)
    c.vat = n.AND(c.P(r"[A-Z]{2}\d{8,12}", pre=WORD, post=WORD)[0], vat_near)
    # Indian mobile numbers without separators and common written forms
    for pat in (r"[6-9]\d{9}", r"[6-9]\d{4} \d{5}"):
        c.add("TEL", c.P(pat, pre=D + "+-./", post=D + "-/")[0], 3)
    for pat in (r"[6-9]\d{9}", r"0[6-9]\d{4}[- ]\d{5}", r"91[- ]?[6-9]\d{4}[- ]?\d{5}", r"[+0]{1,2}91[- ]?[6-9]\d{4}[- ]?\d{5}", r"[6-9]\d{4}[ ./_-]\d{5}",
                r"[6-9]\d \d{2} \d{2} \d{2} \d{2}", r"0\d{2,4}[- ]\d{4}[- ]\d{4}", r"\(0\d{2,4}\) ?\d{4}[- ]\d{4}"):
        c.add("TEL", c.P(pat, pre=WORD + "+-./", post=WORD + "-/")[0], 2)


def record_fields(c: Ctx):
    """Both profiles. Values that sit as a field of a record (table cell, list item, XML element, quoted value, tab column,
    bold item) next to other personal data: a lone capitalised non-English word there is a name, a handle-shaped token
    a username; a password key's value runs to the end of its own quotes / field; coordinate pairs."""
    n = c.n
    letter, d, up, lo = n.cls(AL + HI), n.cls(D), n.cls(UP), n.cls(LO)
    nonl = n.cls("".join(chr(i) for i in range(1, 256) if chr(i) != "\n"))
    anyc = n.cls("".join(chr(i) for i in range(1, 256)))
    # other personal data nearby: an e-mail, an IP, a phone-like digit run, an ID-like token
    pii = n.OR(c.get("EMAIL"), c.get("IP"), c.get("TEL"), n.run(d, 6), force=True)
    near = n.OR(n.prop_right(pii, anyc, 6), n.prop_left(pii, anyc, 6))
    # a token delimited as a field on both sides
    open_d = n.OR(n.cls("|\t<\"'[*").at(-1), n.lit("| ").at(-2), n.lit("- ").at(-2), n.lit("** ").at(-3), n.lit("<").at(-1),
                  n.AND(n.cls(" ").at(-1), n.cls("\n ").at(-2)), n.cls("\n").at(-1), n.lit(", ").at(-2), force=True)
    tokc = n.cls(AL + HI + "'-")
    tok = n.fill(tokc, n.AND(tokc, ~tokc.at(-1), open_d), 4)
    tok_end = n.AND(tok, ~tok.at(1))
    close_d = n.OR(n.cls("|\t>\"'*\n,]").at(1), n.lit(" |").at(1), n.AND(n.cls(" ").at(1), n.cls("\n").at(2)), force=True)
    field = n.fill(tok, n.AND(tok_end, close_d), 4)
    cap_word = n.AND(field, n.fill(tok, n.AND(up, ~tokc.at(-1), lo.at(1), lo.at(2), lo.at(3)), 4))     # 4+ letters: not "Ext", "Qty"
    not_word = ~n.fill(tok, n.AND(tok, c.english), 4)
    c.add("GIVENNAME", n.AND(cap_word, not_word, near), 2)
    # handle-shaped tokens in the same positions: letters with digits, dots, underscores or hyphens
    hc = n.cls(AN + "._-")
    htok = n.fill(hc, n.AND(hc, ~hc.at(-1), open_d), 5)
    hend = n.AND(htok, ~htok.at(1))
    hfield = n.fill(htok, n.AND(hend, close_d), 5)
    has_d = n.fill(htok, n.AND(htok, d), 5)
    has_l = n.fill(htok, n.AND(htok, lo, lo.at(1), lo.at(2)), 5)
    no_up_start = ~n.fill(htok, n.AND(htok, ~hc.at(-1), up), 5)
    c.add("USERNAME", n.AND(hfield, has_d, has_l, no_up_start, near, ~n.fill(htok, n.AND(htok, n.cls("@")), 5)), 2)
    # password values: up to the closing quote (quoted) or the end of the field (markdown / plain)
    keys = ["password", "passwd", "pwd", "passcode", "passphrase", "pass", "temporary password"]
    q_open = n.OR(*[n.lit(k + v, nocase=True).at(-(len(k) + len(v))) for k in keys for v in ('": "', '":"', "': '", "':'", '" : "', ': "', '="')])
    q_stop = n.AND(n.cls("\"'"), n.OR(n.cls(",}]\n\r;").at(1), n.cls(" ").at(1), force=True))
    c.add("PASS", n.AND(n.prop_right(q_open, n.AND(nonl, ~q_stop), 5), ~n.cls("\"'").at(0).at(0) if False else nonl), 0)
    m_open = n.OR(*[n.lit(k + v, nocase=True).at(-(len(k) + len(v))) for k in keys for v in (":** ", ": **", ":**", "**: ", ": ", "> ")])
    m_stop = n.OR(n.lit("**"), n.lit("  "), n.cls("\n<|"), force=True)
    pv = n.prop_right(n.AND(m_open, ~n.cls(" \n")), n.AND(nonl, ~m_stop), 5)
    c.add("PASS", n.AND(pv, n.fill(pv, n.AND(pv, n.cls(AN)), 5)), 1)
    # coordinate pairs: "[35.1373, -120.0376]", "28.4245, 77.0469"
    for pat in (r"\[-?\d{1,2}\.\d{1,7}, ?-?\d{1,3}\.\d{1,7}\]", r"\d{1,2}\.\d{3,7}, ?-?\d{1,3}\.\d{1,7}", r"-\d{1,2}\.\d{3,7}, ?-?\d{1,3}\.\d{1,7}",
                r"\d{1,2}\.\d{1,7}, ?-?\d{1,3}\.\d{3,7}", r"-\d{1,2}\.\d{1,7}, ?-?\d{1,3}\.\d{3,7}"):
        c.add("GEOCOORD", c.P(pat, pre=WORD + ".-[", post=WORD + ".]")[0], 1)
    # identifiers standing as a field of a record with other personal data: 8-12 digit numbers, multi-part codes
    dtok = n.fill(n.cls(D), n.AND(n.cls(D), ~n.cls(D).at(-1), open_d), 4)
    dfield = n.AND(n.fill(dtok, n.AND(dtok, ~dtok.at(1), close_d), 4), n.fill(dtok, n.AND(dtok, n.run(d, 8)), 4),
                   ~n.fill(dtok, n.AND(dtok, n.run(d, 13)), 4))
    # (a 10-digit number starting 15-19 is a Unix timestamp of 2017-2033, not an identifier)
    epoch = n.fill(dtok, n.AND(dtok, ~dtok.at(-1), n.cls("1"), n.cls("56789").at(1), n.run(d, 10), ~d.at(10)), 4)
    c.add("ID", n.AND(dfield, near, ~epoch), 1)
    cc = n.cls(UP + D + "-. ")
    # (in the general model a space never joins parts: "MRN 4477120" is a key and its value, not one code)
    jch = "-." if general() else "-. "
    joint = n.OR(n.AND(n.cls(jch), n.cls(UP + D).at(-1), n.cls(UP + D + "-").at(1)), n.AND(n.cls("-"), n.cls("-").at(-1)), force=True)
    cbody = n.OR(n.cls(UP + D + "ÂÜÉÈÇ"), n.cls("\xc3"), joint, force=True)
    ctok = n.fill(cbody, n.AND(n.cls(UP + D), ~cbody.at(-1), open_d), 6)
    cfield = n.fill(ctok, n.AND(ctok, ~ctok.at(1), close_d), 6)
    c_dig = n.atleast(4, *[n.AND(ctok, d).at(k) for k in range(0, 40)])
    c_let = n.atleast(2, *[n.AND(ctok, n.cls(UP)).at(k) for k in range(0, 40)])
    c_sep = n.fill(ctok, n.AND(ctok, n.cls("-. ")), 6)
    cstart = n.AND(ctok, ~ctok.at(-1))
    c.add("ID", n.AND(cfield, c_sep, n.fill(ctok, n.AND(cstart, c_dig, c_let, n.run(ctok, 10)), 6), near), 1)
    # random passwords by shape: letters, digits and an inner symbol in one 5-24 character token
    nsp = n.cls("".join(chr(i) for i in range(33, 127)))
    ptok = n.fill(nsp, n.AND(nsp, ~nsp.at(-1)), 5)
    delim = n.cls("\"'*<>[](),.;`")
    lead = n.prop_right(n.AND(ptok, delim, ~ptok.at(-1)), n.AND(ptok, delim), 3)
    trail = n.prop_left(n.AND(ptok, delim, ~ptok.at(1)), n.AND(ptok, delim), 3)
    core = n.AND(ptok, ~lead, ~trail)
    sym = n.cls("!@#$%^&*+=|;:'\"<>?/\\`~()[]{}")
    inner_sym = n.AND(core, sym, core.at(-1), core.at(1))
    has = lambda sig: n.fill(core, n.AND(core, sig), 5)
    clen_ok = n.AND(n.fill(core, n.run(core, 5), 5), ~n.fill(core, n.run(core, 25), 5))
    no_url = ~has(n.lit("://"))
    markup = n.OR(n.cls("<>\""), n.lit("..."), n.AND(n.cls("="), n.run(n.cls(AL), 3).at(-3)), n.lit("/"), force=True)   # tags, attributes, key=value, paths
    shape = n.AND(core, clen_ok, has(d), has(n.cls(UP)), has(n.cls(LO)), has(inner_sym), no_url, ~has(markup),
                  ~has(n.AND(n.cls("@"), n.cls(AL).at(1), n.prop_right(n.cls("."), n.cls(AL), 2).at(3))))
    # (measured: the bare shape cost more precision than it gained recall on the development split, so it is not used)
    # phone numbers written as 3-5 digit groups with mixed or dotted separators: "02 52 50.13.99", "0149.988-386 5842"
    for pat in (r"\d{2,4}[ .-]\d{2,4}[ .-]\d{2,4}[ .-]\d{2,4}[ .-]\d{2,4}", r"\d{2,4}[ .-]\d{2,4}[ .-]\d{2,4}[ .-]\d{2,4}",
                r"\d{4}[ .-]\d{3}[ .-]\d{4}", r"\d{3,4}[.]\d{3}[.]\d{4}"):
        tp, _ = c.P(pat, pre=WORD + ".-", post=WORD + ".-")
        four = n.fill(tp, n.AND(tp, n.run(d, 4)), 5)
        mixed = n.AND(n.fill(tp, n.AND(tp, n.cls(".")), 5), n.fill(tp, n.AND(tp, n.cls(" -")), 5))
        ndig = n.atleast(9, *[n.AND(tp, d).at(k) for k in range(0, 20)])
        c.add("TEL", n.AND(tp, n.OR(four, mixed), n.fill(tp, n.AND(tp, ~tp.at(-1), ndig), 5)), 2)

