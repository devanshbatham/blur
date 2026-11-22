"""Detectors that read running text: context cues, stated facts, cookies, passwords, defaults and
chains of related values."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)
from .health import clinical
from .shapes import tel


def context(c: Ctx):
    """Shared structure signals: what is a key (text before a colon, or inside a tag), and what
    may be skipped when walking from a key to its value."""
    n = c.n
    c.printable = n.cls("".join(chr(i) for i in range(33, 127)) + HI)
    sepc = n.cls("".join(chr(i) for i in range(32, 127) if not chr(i).isalnum()) + "\t\n\r")
    escn = n.AND(n.cls("nrt"), n.cls("\\").at(-1))
    tb = n.cls(AN + "/_ =\"-:.<")
    opened = n.prop_right(n.cls("<"), tb, 4)
    gt = n.AND(n.cls(">"), opened.at(-1))
    c.tag = n.AND(opened, n.prop_left(n.AND(tb, gt.at(1)), tb, 4))
    c.ctag = n.AND(c.tag, n.prop_right(n.AND(n.cls("<"), n.cls("/").at(1)), tb, 4))
    c.tag_close = gt
    keyc = n.cls(AL + D + " _'")
    colon, q, star = n.cls(":"), n.cls("\"'"), n.cls("*")
    kend = n.AND(keyc, n.OR(colon.at(1), n.AND(q.at(1), colon.at(2)), n.AND(star.at(1), colon.at(2)),
                            n.AND(star.at(1), star.at(2), colon.at(3))))
    raw = n.prop_left(kend, keyc, 4)
    c.key = n.AND(raw, n.prop_right(n.AND(raw, n.cls(AL)), keyc, 4))
    c.skip = n.OR(sepc, escn, c.tag, c.key, force=True)
    e2, f0 = n.cls("\xe2"), n.cls("\xf0\xf1\xf2\xf3\xf4")
    cont = n.cls("".join(chr(i) for i in range(0x80, 0xC0)))
    c.sym = n.OR(e2, f0, n.AND(cont, e2.at(-1)), n.AND(cont, e2.at(-2)), n.AND(cont, f0.at(-1)), n.AND(cont, f0.at(-2)),
                 n.AND(cont, f0.at(-3)), force=True)
    c.W = n.cls(WORD)
    # an apostrophe or hyphen is part of a word only between letters (O'Brien, Jean-Luc), not as a quote mark
    _lt = n.cls(AL + HI)
    c.wordc = n.OR(_lt, n.AND(n.cls("'-"), _lt.at(-1), _lt.at(1)), force=True)
    # a capital letter: ASCII A-Z, or a two-byte Latin capital (UTF-8 C3 80-9E: À-Þ; C4/C5: Latin Extended-A, mixed case).
    # Three-byte scripts (Indic, CJK, ...) have no case, so their words never count as capitalised.
    if general():
        lat_cap = n.OR(n.AND(n.cls("\xc3"), n.cls("".join(chr(i) for i in range(0x80, 0x9F))).at(1)),
                       n.cls("\xc4\xc5"))   # Latin Extended-A alternates case in both directions: accept either
        c.wstart = n.AND(n.OR(n.cls(UP), lat_cap, force=True), ~c.wordc.at(-1))
    else:
        c.wstart = n.AND(n.cls(UP + HI), ~c.wordc.at(-1))
    c.cap = n.prop_right(c.wstart, c.wordc, 5)
    tokj = n.AND(n.cls(".-_'"), c.W.at(-1), c.W.at(1))
    c.tokbody = n.OR(c.W, tokj, force=True)


def doc_context(c: Ctx, cues):
    """1 everywhere in a document that contains one of the cue words (log-step flood over the whole text)."""
    n = c.n
    letter = n.cls(AL + HI)
    cue = n.OR(*[n.AND(n.lit(w if w.isascii() else u(w), nocase=w.isascii()), ~letter.at(-1), ~letter.at(len(w.encode())))
                 for w in cues])
    anyc = n.cls("".join(chr(i) for i in range(1, 256)))
    return n.OR(n.prop_right(cue, anyc, 11), n.prop_left(cue, anyc, 11))


def contextual(c: Ctx):
    """General profile. Values identified by where they sit: chat speakers, handles, log fields, codes after a cue."""
    if not general():
        return
    n = c.n
    an, d, letter, lo = n.cls(AN), n.cls(D), n.cls(AL), n.cls(LO)
    hc = n.cls(AN + "_.-")
    handle_like = n.OR(n.cls("_."), d, force=True)
    # chat speakers: "[09:14] dev_ankit: ..." (handles with _ . or digits, or all lower case)
    spk_start = n.AND(hc, n.lit("] ").at(-2))
    spk = n.prop_right(spk_start, hc, 5)
    spk_end_colon = n.AND(spk, n.cls(":").at(1))
    spk_tok = n.AND(spk, n.prop_left(spk_end_colon, spk, 5))
    sym_in = n.fill(spk_tok, n.AND(spk_tok, handle_like), 5)
    low_only = n.AND(spk_tok, ~n.fill(spk_tok, n.AND(spk_tok, n.cls(UP)), 5))
    c.add("USERNAME", n.AND(spk_tok, n.OR(sym_in, low_only)), 1)
    # IRC handles: "<NoobMaster69>" (5+ chars with a digit, _ . or inner capital: not an HTML tag)
    irc, _ = c.P(r"<[A-Za-z0-9_.\-]{4,32}> ", pre=WORD, post="",
                 start_terms=[n.OR(n.cls("\n\x00").at(-1), n.lit("] ").at(-2))])
    inner = n.AND(irc, hc)
    special = n.fill(inner, n.AND(inner, n.OR(n.cls("_."), d, n.AND(n.cls(UP), lo.at(-1)), force=True)), 5)
    has_lower = n.fill(inner, n.AND(inner, lo), 5)                  # <YOUR_API_KEY> is a placeholder
    c.add("USERNAME", n.AND(inner, special, has_lower), 1)
    # @mentions (not e-mail addresses: nothing word-like before the @)
    at_start = n.AND(letter, n.cls("@").at(-1), n.cls(" \t\n(,").at(-2))
    mtok = n.prop_right(at_start, hc, 5)
    handle_shape = n.fill(mtok, n.AND(mtok, n.OR(n.cls("_"), d, n.AND(n.cls(UP), lo.at(-1)), force=True)), 5)
    c.add("USERNAME", n.AND(mtok, handle_shape, ~n.fill(mtok, n.AND(mtok, n.cls("/").at(1)), 5)), 1)
    # web server logs: 'IP - user [16/Nov/2026:...'
    lu, _ = c.P(r"[A-Za-z0-9_.@\-]{2,40}", pre=WORD + "@.-", post=WORD + "@.-",
                start_terms=[n.lit(" - ").at(-3), d.at(-4)], end_terms=[n.lit(" [").at(1)])
    c.add("USERNAME", lu, 1)
    acct = n.AND(an, said(c, ["account is under", "account under", "logged in as", "signed in as", "login as", "registered as", "user account for", "account for user", "account of user"]))
    c.add("USERNAME", n.prop_right(acct, hc, 5), 1)
    # SSN cue binds to the next ddd-dd-dddd, whatever its area number
    cue = n.OR(*[n.lit(w, nocase=True) for w in ("ssn", "social security")])
    gap = n.cls("".join(chr(i) for i in range(32, 127) if not chr(i).isdigit()))
    after = n.prop_right(cue, gap, 5)
    ssn, _ = c.P(r"\d{3}-\d{2}-\d{4}", pre=WORD + "-", post=WORD + "-")
    c.add("SOCIALNUMBER", n.fill(ssn, n.AND(ssn, after.at(-1)), 4), 1)
    # one-time codes: a 4-8 digit token shortly after an OTP / verification code mention
    otp = n.OR(*[n.lit(w, nocase=True) for w in ("otp", "one-time password", "one time password", "verification code",
                                                 "2fa code", "security code", "passcode")])
    win = n.prop_right(otp, n.cls("".join(chr(i) for i in range(1, 256))), 6)
    code, _ = c.P(r"\d{4,8}", pre=WORD + "-./+:", post=WORD + "-./:")
    ending = n.OR(*[n.lit(w, nocase=True).at(-len(w)) for w in ("ending ", "ending in ", "ends in ", "last 4 ", "xxxx", "****")])
    cstart = n.AND(code, ~code.at(-1))
    c.add("SECRET", n.fill(code, n.AND(cstart, win, ~ending), 4), 2)
    # gift-card / licence / recovery keys: XXXX-XXXX-XXXX-XXXX with letters and digits
    key, _ = c.P(r"[A-Z0-9]{4,5}(-[A-Z0-9]{4,5}){3,5}", pre=WORD + "-", post=WORD + "-")
    c.add("SECRET", n.AND(key, n.fill(key, n.AND(key, d), 6), n.fill(key, n.AND(key, n.cls(UP)), 6)), 1)
    # Wi-Fi keys
    psk = n.AND(n.cls(AN + "!@#$%^&*_-"), said(c, ["psk", "wpa_passphrase", "wpa-psk", "wifi password", "wi-fi password",
                                                   "wifi pass", "wifi key"]))
    c.add("PASS", n.prop_right(psk, n.cls(AN + "!@#$%^&*_+=.,;:?~-"), 5), 1)
    # children: class / section and roll numbers, and the school, in a document about a child
    child = doc_context(c, CHILD_CUES)
    cls_ = n.OR(*[c.P(p, pre=WORD, post=WORD)[0] for p in (
        r"(Class|Grade|Std|Standard|STD) [IVX]{1,4}", r"(Class|Grade|Std|Standard|STD) \d{1,2}",
        r"(Class|Grade|Std|Standard|STD) \d{1,2}[A-H]", r"(Class|Grade|Std|Standard|STD) \d{1,2}-[A-H]",
        r"(Class|Grade|Std|Standard|STD) [IVX]{1,4}-?[A-H]")], force=True)
    c.add("ID", n.AND(cls_, child), 1)
    c.child_ctx = child
    # values of identifying keys in logs / JSON / query strings: uid=u_77310, "member_id": "M-2231"
    keys = ["uid", "user_id", "userid", "customer_id", "cust_id", "member_id", "patient_id", "account_id", "acct_id", "emp_id",
            "employee_id", "student_id", "subscriber_id", "client_id_user", "person_id", "profile_id", "citizen_id", "voter_id",
            "national_id", "tax_id", "ssn", "dob", "date_of_birth", "phone", "mobile", "msisdn"]
    kend = n.OR(*[n.AND(n.lit(k, nocase=True), ~n.cls(AN + "_").at(-1), ~n.cls(AN + "_").at(len(k))).at(-(len(k) - 1)) for k in keys])
    kreach = n.prop_right(kend, n.cls(' :="\\\''), 3)
    kval = n.AND(n.cls(AN + "+"), kreach.at(-1), ~kend)
    ktok = n.prop_right(kval, n.cls(AN + "_.-+@"), 5)
    c.add("ID", n.AND(ktok, n.fill(ktok, n.AND(ktok, d), 5)), 1)
    # an old date inside a delimited record (a CSV/TSV row with several fields) is most likely a date of birth
    comma = n.cls(",\t|;")
    row = n.atleast(4, *[comma.at(k) for k in range(-70, 71) if k])
    nl = n.cls("\n")
    dob_shape = n.OR(*[c.P(p, pre=WORD + "/-.", post=WORD + "/-.")[0] for p in
                       (r"\d{2}/\d{2}/19\d\d", r"\d{2}/\d{2}/200\d", r"\d{2}-\d{2}-19\d\d", r"\d{2}-\d{2}-200\d",
                        r"19\d\d-\d{2}-\d{2}", r"200\d-\d{2}-\d{2}", r"\d{2}\.\d{2}\.19\d\d", r"\d{2}\.\d{2}\.200\d")], force=True)
    fielded = n.AND(comma.at(-1), n.OR(*[comma.at(k) for k in range(8, 12)], force=True))
    c.add("BOD", n.fill(dob_shape, n.AND(dob_shape, fielded, row), 4), 0)


def facts(c: Ctx):
    """General profile. Special-category facts (health, sexuality, religion, money) are words, not IDs. A term counts
    when the text is about a person: a personal pronoun, a possessive or a name within the same sentence."""
    if not general():
        return
    n = c.n
    wt = n.cls(AL + HI + "-")
    term_tree = word_tree(c, HEALTH_TERMS + SPECIAL_TERMS + ["hiv reactive"])
    c.health_terms = term_tree
    stop = n.cls(".!?\n")
    pron = n.OR(*[n.AND(n.lit(w, nocase=True), ~n.cls(AL).at(-1), ~n.cls(AL).at(len(w))) for w in
                  ("he", "she", "his", "her", "him", "i", "my", "me", "patient", "client", "they", "their", "son", "daughter",
                   "wife", "husband", "mother", "father", "child")])
    # the pronoun's influence spreads along the sentence in both directions, stopping at sentence ends
    sent = n.AND(n.cls("".join(chr(i) for i in range(32, 256) if chr(i) not in ".!?\n")), ~stop)
    personal = n.OR(n.prop_right(pron, sent, 7), n.prop_left(pron, sent, 7))
    multi = n.OR(*[n.AND(n.lit(w, nocase=True), ~n.cls(AL).at(-1)) for w in HEALTH_TERMS + SPECIAL_TERMS if not w.isalpha()])
    multi = n.prop_right(multi, n.cls(AN + "-"), 4)
    c.add("HEALTH", n.AND(n.OR(term_tree, multi), personal), 1)
    # measured values: "HbA1c 8.2%", "BP 150/95", "blood group O-", "BMI 31"
    for pat in (r"(HbA1c|hba1c|A1c) \d{1,2}%", r"(HbA1c|hba1c|A1c) \d{1,2}\.\d%", r"(BRCA1|BRCA2|brca1|brca2) (positive|negative|carrier)",
                r"wheelchair (user|bound)", r"(BP|bp|blood pressure) \d{2,3}/\d{2,3}", r"(BMI|bmi) \d{2}(\.\d)?",
                r"(HIV|COVID|covid|hiv) (positive|negative|reactive)", r"(ICD-10|ICD-11|ICD10|SNOMED|CPT|LOINC) [A-Z0-9][A-Z0-9.\-]{2,9}"):
        c.add("HEALTH", c.P(pat, pre=WORD, post=WORD)[0], 0)
    c.add("HEALTH", c.P(r"\d{1,2} weeks pregnant", pre=WORD, post=WORD)[0], 0)
    clinical(c, personal, term_tree)
    # money facts about a person (a company's income is not personal data)
    mv = n.AND(n.cls(D + "$\xe2"), said(c, ["cibil score", "credit score", "salary", "ctc", "income", "net worth", "loan default"]))
    unit = n.OR(n.cls(D + ",.$LPAlakhcrorekKM\xe2\x82\xb9"), n.AND(n.cls(" "), n.cls(D).at(-1), n.cls("LlkcKM").at(1)), force=True)
    fv = n.prop_right(mv, unit, 4)
    c.add("FINANCE", n.AND(fv, personal), 1)
    # school + class + roll number identifies a child
    rv = n.AND(n.cls(D), said(c, ["roll no", "roll number", "admission no", "admission number", "student id", "enrolment no"]))
    c.add("ID", n.prop_right(rv, n.cls(AN + "-/"), 3), 1)
    # crypto seed phrases: 12 or more consecutive BIP-39 words
    words = open(os.path.join(DATA_DIR, "bip39.txt")).read().split()
    bip = word_tree(c, words)
    bstart = n.AND(bip, ~bip.at(-1))
    bjoin = n.AND(n.cls(" "), bip.at(-1), bip.at(1))
    brun = n.OR(bip, bjoin, force=True)
    words_in = n.AND(bstart, ~n.cls(AL).at(-1))
    twelve = n.atleast(12, *[words_in.at(k) for k in range(0, 120)])
    c.add("SECRET", n.AND(n.fill(brun, n.AND(bstart, twelve), 7), n.fill(brun, n.run(brun, 47), 7)), 0)
    # a quoted phrase: the first word follows a quote mark, which the word tree does not start on
    if general():
        letter = n.cls(AL)
        qword = n.fill(letter, n.AND(letter, n.cls("'\"`").at(-1)), 4)
        eleven = n.atleast(11, *[words_in.at(k) for k in range(0, 110)])
        first = n.AND(bstart, eleven, qword.at(-2), n.cls(" ").at(-1))
        run2 = n.OR(brun, qword, n.AND(n.cls(" "), qword.at(-1), bip.at(1)), force=True)
        long2 = n.fill(run2, n.run(run2, 47), 7)
        c.add("SECRET", n.AND(long2, n.fill(run2, n.OR(first, n.AND(qword, first.at(2)), n.AND(qword, first.at(3)), n.AND(qword, first.at(4)),
                                         n.AND(qword, first.at(5)), n.AND(qword, first.at(6)), n.AND(qword, first.at(7)),
                                         n.AND(qword, first.at(8)), n.AND(qword, first.at(9))), 7)), 0)


def cookies(c: Ctx):
    """General profile. An HTTP cookie is name=value followed by "; "-separated cookie attributes
    (Path, Expires, Domain, Max-Age, HttpOnly, Secure, SameSite). A bare name=value counts when
    the word "cookie" introduces it."""
    if not general():
        return
    n = c.n
    semi, sp = n.cls(";"), n.cls(" ")
    attr = n.OR(*[n.lit(a, nocase=True) for a in ("Path=", "Expires=", "Domain=", "Max-Age=", "HttpOnly", "Secure", "SameSite=")])
    piece = n.cls("".join(ch for ch in map(chr, range(33, 127)) if ch not in ";\"'`|<>,"))
    attr_tok = n.prop_right(attr, piece, 6)
    date_c = n.cls(AL + D + ",: =")
    expires = n.AND(n.prop_right(n.lit("Expires=", nocase=True), date_c, 5), n.prop_left(n.lit("GMT").at(-2), date_c, 5))
    joint = n.OR(n.AND(semi, sp.at(1), attr.at(2)), n.AND(sp, semi.at(-1), attr.at(1)))
    tail = n.OR(attr_tok, expires, joint, force=True)
    head, head_end = c.P(r"[\w.\-]{2,}=[\w.\-+/%:|~!*]+", pre=WORD + "=.-;", post=None)
    with_attrs = n.fill(head, n.AND(head_end, semi.at(1), sp.at(2), attr.at(3)), 6)
    c.add("COOKIE", n.OR(with_attrs, n.prop_right(n.AND(with_attrs, ~with_attrs.at(1)).at(-1), tail, 7)), 0)
    c.add("COOKIE", n.fill(head, n.AND(head, ~head.at(-1), said(c, ["cookie"])), 6), 1)
    # cookie jars: "a=v1; b=v2" — each value is masked when it looks like an identifier (digits or 8+ characters)
    d = n.cls(D)
    vch = n.cls(AN + "%._-+/:|~!*")
    eq = n.AND(n.cls("="), n.cls(AN + "_.-").at(-1), vch.at(1))
    val = n.prop_right(n.AND(vch, eq.at(-1)), vch, 7)
    vend = n.AND(val, ~vch.at(1))
    jar_val = n.fill(val, n.AND(vend, semi.at(1)), 7)
    after_jar = n.fill(val, n.AND(n.AND(val, eq.at(-1)), n.prop_right(n.AND(semi, sp.at(1)), n.cls(AN + "_.- "), 5).at(-2)), 7)
    strong = n.OR(n.fill(val, n.AND(val, d), 7), n.fill(val, n.AND(n.AND(val, eq.at(-1)), n.run(vch, 8)), 7))
    c.add("COOKIE", n.AND(n.OR(jar_val, after_jar), strong, ~attr_tok, ~expires), 1)
    # Netscape cookies.txt rows: domain TAB flag TAB path TAB secure TAB expiry TAB name TAB value
    tab = n.cls("\t")
    T = "\t"
    row, row_end = c.P(r"[\w.\-]{2,}" + T + "(TRUE|FALSE)" + T + r"[\w/.\-]{1,}" + T + "(TRUE|FALSE)" + T + r"\d{1,12}" + T + r"[\w.\-]{1,}" + T,
                       pre=None, post=None)
    c.add("COOKIE", n.prop_right(n.AND(n.cls(AN + "%._-"), row_end.at(-1)), n.cls(AN + "%._-+/=:"), 6), 0)


def prose(c: Ctx):
    """General profile. Values introduced in a sentence: "my username is jdoe", "the password
    b7K&m9 was used", "the city of Bison", "postcode is 53404"."""
    if not general():
        return
    n = c.n
    d = n.cls(D)
    tok = lambda v: n.prop_right(v, c.tokbody, 5)
    cap_run = lambda v: n.prop_right(n.AND(v, c.wstart), n.OR(c.cap, n.AND(n.cls(" "), c.cap.at(-1), c.wstart.at(1)), force=True), 5)
    utk = tok(n.AND(c.W, said(c, ["username", "user name", "handle", "user id", "userid"])))
    c.add("USERNAME", n.AND(utk, ~c.english), 1)
    c.add("CITY", cap_run(said(c, ["city", "town"])), 1)
    c.add("STATE", cap_run(said(c, ["state", "province"])), 1)
    c.add("COUNTRY", cap_run(said(c, ["country"])), 1)
    a_cue = said(c, [u("पता"), u("पत्ता"), "adresse", "dirección", "direccion", "indirizzo", "anschrift",
                     "address", "residing at", "living at", "resides at", "lives at", "located at", "deliver to", "street at",
                     "ship to", "send to", "mail to", "post to", "courier to", "dispatch to", "home address", "c/o"])
    a_cue2 = n.AND(n.cls(" ").at(-1), n.cls(",").at(-2), n.OR(*[n.lit(w, nocase=True).at(-len(w) - 2) for w in ("address",)]))
    a_start = n.AND(n.cls(D + UP + HI), n.OR(a_cue, a_cue2))
    # a full stop that ends a sentence ends the address ("..., Khartoum. The Andijan office is ..."), unless it closes a
    # street abbreviation ("St. Mary's Road", "Rd. 4")
    abbr = n.OR(*[n.lit(w).at(-len(w)) for w in ("St", "Rd", "Ave", "No", "Apt", "Dr", "Mt", "Ft", "Blvd", "Ln", "Sq", "Hwy", "Nr", "Opp")], force=True)
    sent_end = n.AND(n.cls("."), n.cls(" ").at(1), n.cls(UP).at(2), n.cls(LO).at(3), ~abbr, n.run(n.cls(LO), 4).at(-1))   # after a word of 5+ letters
    # or before a new clause: a capitalised word followed by a lower-case word ("..., Mandeville, LA. The client agrees")
    clause = n.spread_left(n.AND(c.cap, ~c.cap.at(1), n.cls(" ").at(1), n.cls(LO).at(2)), 12)
    sent_end = n.OR(sent_end, n.AND(n.cls("."), n.cls(" ").at(1), c.wstart.at(2), clause.at(2), ~abbr), force=True)
    a_body = n.OR(n.AND(n.cls(AN + HI + " '-/#"), ~c.sym), n.AND(n.cls("."), ~sent_end), n.AND(n.cls(","), n.cls(" ").at(1), n.cls(UP + D).at(2)),
                  n.AND(n.cls("\n"), n.cls(UP + D).at(1), n.cls(AN).at(-1)), force=True)
    addr = n.prop_right(a_start, a_body, 6)
    a_trail = n.AND(n.cls(" .,"), ~a_body.at(1))
    c.addr_said = n.AND(addr, ~a_trail)
    tel = c.get("TEL")
    tend = n.AND(tel, ~tel.at(1))
    for lit in (" ext. ", " ext ", " x", "x", " extension "):
        e0 = n.AND(n.lit(lit).at(1), tend, d.at(len(lit) + 1))            # fires on the last character of the phone number
        c.add("TEL", n.OR(n.spread_right(e0.at(-1), len(lit)), n.prop_right(n.AND(d, e0.at(-len(lit) - 1)), d, 3)), 1)
    pv = n.AND(n.cls(AN), said(c, ["postcode", "postal code", "zip code", "zip", "pin code", "pincode", "pin", "live in", "lives in"]))
    pt = n.prop_right(pv, n.OR(n.cls(UP + D), n.AND(n.cls(" -"), n.cls(UP + D).at(1), n.cls(UP + D).at(-1)), force=True), 3)
    c.add("POSTCODE", n.AND(pt, n.fill(pt, n.AND(pt, d), 3)), 1)
    c.pass_said = said(c, ["password", "passcode", "passphrase", "pwd", "passwd"])
    # health facts introduced by a cue run to the end of the clause
    hv = n.AND(c.W, said(c, ["diagnosis code", "diagnosis", "diagnosed with", "blood group", "blood type", "allergic to",
                             "medication", "medications"]))
    hbody = n.OR(n.cls(AN + HI + "+-/"), n.AND(n.cls(" "), n.cls(AN).at(-1), n.cls(UP + D).at(1)), force=True)
    hstop = n.OR(n.AND(n.cls("."), ~c.W.at(1)), n.cls(","))
    # a lower-case phrase after the cue runs up to the last health term in it ("type 2 diabetes")
    hb2 = n.OR(hbody, n.AND(n.cls(" "), n.cls(AN).at(-1), n.cls(LO).at(1)), force=True)
    hraw = n.prop_right(hv, n.AND(hb2, ~hstop), 4)
    tend = n.AND(hraw, c.health_terms, ~c.health_terms.at(1))
    lower_phrase = n.AND(hraw, n.prop_left(tend, hraw, 4))
    upper_v = n.prop_right(n.AND(hv, n.cls(UP + D)), n.AND(hbody, ~hstop), 4)
    htok = n.OR(upper_v, lower_phrase)
    c.add("HEALTH", n.AND(htok, ~n.AND(n.cls(" "), ~htok.at(1))), 1)
    # institutions: capitalised words ending in an institution word
    inst = "School|Primary|Academy|College|University|Institute|Hospital|Clinic|Foundation|Trust|Residency|Apartments|Towers|Society|High"
    joint_i = n.AND(n.cls(" "), c.cap.at(-1), c.wstart.at(1))
    ends_i = n.OR(*[n.AND(n.lit(w), joint_i.at(-1), ~c.wordc.at(len(w))).at(-(len(w) - 1)) for w in inst.split("|")])
    c.add("ORG", n.prop_left(ends_i, n.OR(c.cap, joint_i, force=True), 5), 1)
    # digits spelled as words: seven or more number words in a row
    nw = n.OR(*[n.AND(n.lit(w, nocase=True), ~n.cls(AL).at(-1), ~n.cls(AL).at(len(w))) for w in
                ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "oh", "double", "triple")],
               *[n.AND(n.lit(u(w)), ~n.cls(HI).at(-1), ~n.cls(HI).at(len(u(w)))) for w in
                 ("शून्य", "एक", "दो", "तीन", "चार", "पाँच", "पांच", "छह", "छः", "सात", "आठ", "नौ")],
               n.cls(D))
    nword = n.prop_right(nw, n.cls(AL + HI + D), 3)
    nsep = n.AND(n.cls(" ,-"), n.OR(nword.at(-1), n.AND(n.cls(","), nword.at(-1)).at(-1)), n.OR(nw.at(1), n.AND(n.cls(" "), nw.at(1)).at(1)))
    nbody = n.OR(nword, nsep, force=True)
    nrun = n.prop_right(n.AND(nw, ~nbody.at(-1)), nbody, 6)
    word_start = n.AND(nw, ~n.cls(D), ~n.cls(AL + HI).at(-1))
    words3 = n.atleast(3, *[n.AND(nrun, word_start).at(k) for k in range(0, 120)])
    enough = n.AND(n.atleast(9, *[n.AND(nrun, n.OR(word_start, n.cls(D), force=True)).at(k) for k in range(0, 120)]), words3)
    t_run = n.AND(nrun, n.fill(nrun, n.AND(nrun, ~nrun.at(-1), enough), 6))
    c.add("TEL", n.AND(t_run, n.fill(t_run, n.AND(t_run, word_start), 6)), 1)       # a spoken number has a number word in it


def defaults(c: Ctx):
    """Last-resort guesses for shapes that are almost always one label when they are labelled."""
    n = c.n
    if general():
        return
    bound = WORD + "+-.,:/%$#"
    c.add("BUILDING", c.P(r"\d{3}", pre=bound, post=WORD + "-.:/%")[0], 3)
    c.add("POSTCODE", c.P(r"\d{5}", pre=bound, post=WORD + "-.:/%")[0], 3)
    c.add("STATE", c.P("(" + "|".join(US_STATES) + ")", pre=WORD + "<_/@.-", post=WORD + "_@.-'")[0], 3)


def password(c: Ctx):
    """Passwords. The token is the run of non-space characters, minus one wrapping pair of
    quotes/brackets and trailing , . ; :  It is a password when it follows a password-like key,
    or when it is 4-14 characters mixing lowercase, uppercase and digits (and is not something
    with an unambiguous shape of its own, nor a key=value fragment)."""
    n = c.n
    pr = c.printable
    bs = n.cls("\\")
    esc = n.OR(n.AND(bs, n.cls("nrt").at(1)), n.AND(n.cls("nrt"), bs.at(-1)))
    lt_slash = n.AND(n.cls("<"), n.cls("/").at(1))
    body = n.AND(pr, ~lt_slash, ~c.tag, ~c.tag_close, ~esc)
    raw_start = n.AND(body, ~body.at(-1))
    raw_end = n.AND(body, ~body.at(1))
    wrap_o, wrap_c = n.cls("[\"'`*({"), n.cls("]\"'`*)}")
    opener = n.AND(raw_start, wrap_o)
    opener2 = n.AND(wrap_o, opener.at(-1))
    trail = n.AND(raw_end, n.cls(",.;:"))
    last = n.OR(n.AND(raw_end, ~trail), n.AND(body, trail.at(1)))
    closer = n.AND(last, wrap_c)
    closer2 = n.AND(wrap_c, closer.at(1))
    wrapped_open = n.OR(opener, opener2)
    strip_close = n.AND(n.OR(closer, closer2), n.prop_right(wrapped_open, body, 4))
    core = n.AND(body, ~wrapped_open, ~trail, ~strip_close)
    start = n.AND(core, ~core.at(-1))

    # keyed
    hit = n.AND(n.OR(*[n.lit(w, nocase=True) for w in ("password", "passcode", "passkey", "pass code", "passwd", "pwd")]),
                n.OR(c.key, c.tag), ~c.ctag)
    reach = n.prop_right(hit, n.OR(c.key, c.tag, c.tag_close, n.cls(": \t*=\"'[{`("), esc, force=True), 5)
    keyed_pw = n.fill(core, n.AND(start, reach.at(-1), ~c.key), 4)
    holder = n.OR(*[n.AND(n.lit(w, nocase=True), ~n.cls(AN).at(len(w))) for w in
                    ("changeme", "change_me", "xxx", "***", "password", "your_password", "yourpassword", "<", "${", "$", "{{",
                     "null", "none", "n/a", "redacted", "hidden", "secret", "example", "dummy", "placeholder", "todo", "tbd")])
    keyed_pw = n.AND(keyed_pw, ~n.fill(core, n.AND(start, holder), 4))
    if general():
        said_pw = n.prop_right(n.AND(core, c.pass_said), core, 4)
        is_word = n.fill(core, n.AND(start, c.english), 4)
        keyed_pw = n.AND(n.OR(keyed_pw, said_pw), ~n.AND(is_word, ~n.fill(core, n.AND(core, n.cls(D)), 4)))
        keyed_pw = n.AND(keyed_pw, ~n.fill(core, n.AND(start, holder), 4))
    c.add("PASS", keyed_pw, 1)
    if general():
        qq = n.cls("\"'")
        inq = n.cls("".join(chr(i) for i in range(32, 127) if chr(i) not in "\"'") + HI)
        pw_open = n.AND(qq, n.OR(c.pass_said.at(1), n.AND(reach.at(-1), qq)))
        c.add("PASS", n.prop_right(n.AND(inq, pw_open.at(-1)), inq, 6), 1)

    # by shape
    strong = n.OR(*[c.get(lab, 0) for lab in ("EMAIL", "IP", "GEOCOORD", "DRIVERLICENSE", "IDCARD", "SOCIALNUMBER",
                                              "DATE", "BOD", "SECADDRESS", "TEL", "URL", "COOKIE", "ID", "CARD")], force=True)
    letter = n.cls(AL)
    keyish = n.AND(n.run(letter, 3), n.cls(":=\"_").at(3))
    lower, upper, digit = n.cls(LO), n.cls(UP), n.cls(D)
    has = lambda sig: n.fill(core, n.AND(core, sig), 4)
    q, colon = n.cls("\"'"), n.cls(":")
    is_key = has(n.AND(~core.at(1), c.key, n.OR(colon.at(1), n.AND(q.at(1), colon.at(2)))))
    word_num, _ = c.P(r"[A-Z][a-z]{2,}\d{1,2}", pre=None, post=None)   # "Client4", "User2": an identifier
    plain_id = n.AND(n.fill(core, n.AND(start, word_num), 4),
                     ~has(n.AND(core, ~n.cls(AL + D + "'"))))
    min_len = n.fill(core, n.AND(start, n.run(core, 4)), 4)
    if general():   # "IPv4", "Win10": in general text a short mixed token needs a symbol to count
        symbol = n.cls("!#$%^&*@?~+=|{}[]<>;:")
        min_len = n.OR(n.fill(core, n.AND(start, n.run(core, 8)), 4), n.AND(min_len, has(symbol)))
    ok = n.AND(has(lower), has(upper), has(digit), min_len,
               ~n.fill(core, n.AND(start, n.run(core, 15)), 4), ~has(strong), ~has(keyish), ~is_key, ~plain_id)
    c.add("PASS", ok, 0)


def chains(c: Ctx):
    """Address fields follow a fixed order (country, building, street, city, state, postcode),
    so a detected field identifies its neighbours."""
    n = c.n
    d, comma, sp = n.cls(D), n.cls(","), n.cls(" ")
    country = c.get("COUNTRY")
    after = n.prop_right(country, c.skip, 4)
    v = n.AND(d, after.at(-1), ~country, ~d.at(-1))
    c.add("BUILDING", n.OR(*[n.spread_right(n.AND(v, n.run(d, k), ~c.W.at(k)), k) for k in range(1, 5)]), 1)

    # A field is a run of letters/digits/inner spaces; the next field is whatever starts after
    # the separators that follow the previous one (", " or a new list line or the next key).
    # typographic symbols ("—", "–", "→", emoji) are punctuation, not letters: a field ends at them
    inner_sp = n.AND(sp, c.W.at(1), c.W.at(-1), ~c.sym.at(1), ~c.sym.at(-1))
    fbody = n.AND(n.OR(n.cls(AL + HI + D + "'.-"), inner_sp, force=True), ~c.key, ~c.tag, ~c.sym)
    fstart = n.AND(c.W, ~c.key, ~c.tag)
    nxt = lambda prev: n.prop_right(n.AND(fstart, n.prop_right(prev, c.skip, 4).at(-1), ~prev), fbody, 5)
    # "<number>, <Words>, <Words>" is an address line even with nothing in front of it
    more = lambda sig: n.AND(sig, comma.at(1), sp.at(2), c.wstart.at(3))
    num, num_end = c.P(r"\d{1,4}[A-Z]?", end_terms=[comma.at(1), sp.at(2), c.wstart.at(3)],
                       start_terms=[~n.AND(sp.at(-1), n.cls(AL + HI).at(-2))])
    cand = n.prop_right(n.AND(c.wstart, sp.at(-1), comma.at(-2), num_end.at(-3)), fbody, 5)
    lone = n.fill(num, n.AND(num_end, n.fill(cand, more(cand)).at(3)))
    building = n.OR(lone, c.get("BUILDING"), force=True)
    c.add("BUILDING", lone, 1)
    street = n.AND(n.prop_right(n.AND(fstart, n.cls(AL + HI), n.prop_right(building, c.skip, 4).at(-1), ~building), fbody, 5),
                   ~c.get("COUNTRY"))
    c.add("STREET", street, 1)
    c.chain_street = street

    # two capital letters followed by a 5-digit code: state and postcode
    zip5, _ = c.P(r"\d{5}", pre=WORD + "+-.", post=WORD + "-.")
    zip9 = c.get("POSTCODE", 0)
    zstart = n.AND(n.OR(zip5, zip9), d, ~d.at(-1))
    st2, st2_end = c.P(r"[A-Z]{2}", pre=WORD + "<_/@.-", post=WORD + "_@.-")
    to_zip = n.prop_left(zstart, c.skip, 3)
    us_state = n.fill(st2, n.AND(st2_end, to_zip.at(1)), 1)
    c.add("STATE", us_state, 1)
    after_us = n.prop_right(us_state, c.skip, 3)
    c.add("POSTCODE", n.fill(zip5, n.AND(zip5, d, ~d.at(-1), after_us.at(-1)), 3), 1)

    # "Springfield, IL" / "Chicago, Illinois": a state code or name right after "<Capitalised>, "
    code, code_end = c.P("(" + "|".join(US_STATES + ["IN", "OR", "OK", "ID", "HI", "ME", "MS"]) + ")", pre=WORD + "<_/@.-", post=WORD + "_@-'")
    after_cap = n.AND(sp.at(-1), comma.at(-2), c.cap.at(-3))
    c.add("STATE", n.fill(code, n.AND(code, ~code.at(-1), after_cap), 1), 1)
    d = n.cls(D)

    # capitalised words right before the state / right after a street, across brackets and keys
    state = c.get("STATE")
    st_start = n.AND(state, ~state.at(-1))
    before_state = n.prop_left(st_start, c.skip, 3)
    tok_end = n.AND(c.cap, ~c.wordc.at(1))
    link = n.OR(n.AND(sp, c.cap.at(-1), c.wstart.at(1)),
                *[n.spread_right(n.AND(n.lit(f" {w} "), c.cap.at(-1), c.wstart.at(len(w) + 2)), len(w) + 2)
                  for w in ("upon", "on", "under", "le", "in", "by")])
    st_all = c.get("STREET")
    body = n.AND(n.OR(c.cap, link, force=True), ~state, ~st_all, ~c.key, ~c.tag)
    c.add("CITY", n.prop_left(n.AND(tok_end, before_state.at(1), body), body, 5), 2)
    country = c.get("COUNTRY")
    before_country = n.AND(comma.at(1), sp.at(2), n.AND(country, ~country.at(-1)).at(3))
    region = n.prop_left(n.AND(tok_end, before_country, n.OR(c.cap, link, force=True), ~c.key, ~c.tag), n.OR(c.cap, link, force=True), 5)
    if general():
        # "<City>, <ST>": whatever capitalised words stand right before a state code are a city, even "Washington"
        cs = n.AND(code, ~code.at(-1), after_cap)
        cbody = n.AND(n.OR(c.cap, link, force=True), ~c.key, ~c.tag)
        city_st = n.prop_left(n.AND(tok_end, comma.at(1), sp.at(2), cs.at(3)), cbody, 5)
        c.add("CITY", city_st, 1)
        # a 4-6 digit code right after a city is its postcode; then "<Region>, <Country>" after a city/postcode is a state
        cities = n.OR(c.get("CITY"), city_st, force=True)
        pc = n.AND(d, ~d.at(-1), n.OR(n.AND(sp.at(-1), cities.at(-2)), n.AND(sp.at(-1), comma.at(-2), cities.at(-3)),
                                      n.AND(sp.at(-1), n.cls("-").at(-2), sp.at(-3), cities.at(-4))))
        code46 = n.OR(*[n.spread_right(n.AND(pc, n.run(d, k), ~c.W.at(k)), k) for k in (4, 5, 6)])
        c.add("POSTCODE", code46, 1)
        prior = n.prop_right(n.OR(cities, code46, force=True), n.cls(", "), 1)
        is_state = n.fill(region, n.AND(region, ~region.at(-1), prior.at(-1)), 5)
        c.add("STATE", n.AND(is_state, ~cities), 1)
        c.add("CITY", n.AND(region, ~is_state), 2)
    else:
        c.add("CITY", n.AND(region, body), 2)
    # after a street, but not across a sentence end
    chain_sep = n.AND(c.skip, ~n.cls(".!?"))
    after_street = n.prop_right(st_all, chain_sep, 3)
    c.add("CITY", n.prop_right(n.AND(c.wstart, after_street.at(-1), body), body, 5), 2)
    city_all = c.get("CITY")
    # 4-5 digit postcode right after the state; any short token right after a city is a state
    after_state = n.prop_right(state, n.cls(", "), 1)
    pv = n.AND(d, after_state.at(-1), ~d.at(-1))
    c.add("POSTCODE", n.OR(*[n.spread_right(n.AND(pv, n.run(d, k), ~c.W.at(k)), k) for k in (4, 5)]), 2)
