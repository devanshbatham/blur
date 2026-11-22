"""Values that look private but are not, decided by context: versions, documentation IPs, placeholders, hex
literals, workflow references, fiction and projects, recovery phrases; proper nouns that are not people; standards,
algorithms, software names, log levels, school classes."""
from .words import *  # noqa: F401,F403  (word-part vocabulary and shared imports)


def documented_values(c, k):
    NAMES = k.NAMES
    P = k.P
    add_veto = k.add_veto
    alnum = k.alnum
    cls = k.cls
    digit = k.digit
    lower = k.lower
    n = k.n
    sp = k.sp
    upper = k.upper
    # ================= precision: context decides =================
    letters = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    def word(w, nocase=True):                        # a whole word ("example" but not "example.com")
        return n.AND(n.lit(w, nocase=nocase), ~alnum.at(-1), ~cls("./@-_").at(-1), ~alnum.at(len(w)), ~cls("/").at(len(w)),
                     ~n.AND(cls("."), letters.at(1)).at(len(w)))
    # documentation / illustration context: a cue word within about a sentence on either side
    doc_cue = n.OR(*[word(w) for w in ("documentation", "docs", "example", "examples", "e.g.", "for instance", "sample", "placeholder",
                                       "dummy", "illustrative", "illustration", "RFC 5737", "RFC 3849", "TEST-NET", "reserved for documentation",
                                       "fictional", "hypothetical", "tutorial", "demo")], force=True)
    doc_ctx = n.OR(n.spread_right(doc_cue, 110), n.spread_left(doc_cue, 110), force=True)
    # (1) software versions: a dotted number after a product word ("Python 3.14.1", "PostgreSQL 17.2", "v1.2.3", "atlas-v2.6.14"),
    #     with its build suffix ("2026.11.16-4f2a9c1"); no part of one is an address, phone, ip, id or secret
    ver = P("[0-9]{1,4}\\.[0-9]{1,4}[0-9.]{0,12}", pre="0-9.", post="0-9")[0]
    # the word before is product-like: capitalised or with a digit or dot inside ("Python", "Node.js", "k8s"), or a release word
    pw_tok = n.prop_right(n.AND(alnum, ~n.OR(alnum, cls("._-"), force=True).at(-1)), n.OR(alnum, cls("._-"), force=True), 5)
    has_up = n.fill(pw_tok, n.AND(pw_tok, upper), 5)
    has_low = n.fill(pw_tok, n.AND(pw_tok, lower, lower.at(-1)), 5)          # two lower-case letters in a row
    pw_prod = n.OR(n.AND(has_up, has_low), n.fill(pw_tok, n.OR(n.AND(pw_tok, digit, letters.at(-1)), n.AND(pw_tok, cls("."), letters.at(1)), force=True), 5), force=True)
    rel_w = n.OR(*[n.AND(n.lit(w), ~alnum.at(-1)) for w in ("version ", "versions ", "build ", "release ", "tag ", "ver ", "patch ", "firmware ", "kernel ",
                                                            "upgrade to ", "upgraded to ", "bumped to ", "pinned to ")], force=True)
    prod_before = n.OR(n.AND(sp.at(-1), pw_prod.at(-2)), n.spread_right(rel_w, 24).at(-1), n.AND(cls("vV").at(-1), ~alnum.at(-2)),
                       n.AND(cls("vV").at(-1), cls("-_").at(-2)), n.AND(cls("@").at(-1), alnum.at(-2)), force=True)
    ip4 = P("[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}", pre="0-9.", post="0-9")[0]
    ver_tok = n.AND(ver, n.fill(ver, n.AND(ver, ~ver.at(-1), prod_before), 5), ~n.AND(cls("."), ~digit.at(1)), ~n.fill(ver, n.AND(ver, ip4), 5),
                    ~n.fill(ver, n.AND(ver, ~ver.at(1), letters.at(1)), 5))           # "4.1JqM" runs into letters: not a version
    ver_full = n.prop_right(ver_tok, n.OR(ver_tok, n.AND(cls("-+"), alnum.at(1)), alnum, force=True), 5)
    ver_full = n.OR(ver_full, n.AND(cls("vV"), ver_tok.at(1)), force=True)
    add_veto(("DATE",), n.AND(ver_full, n.fill(ver_full, n.AND(ver_full, cls("-+"), alnum.at(1)), 5)))     # "2026.11.16-4f2a9c1" is a build
    add_veto(("ADDRESS", "STREET", "BUILDING", "SECADDRESS", "POSTCODE", "TEL", "ID", "USERNAME", "SECRET", "PASS", "GEOCOORD",
              "CARD", "SOCIALNUMBER", "IDCARD", "PASSPORT", "DRIVERLICENSE", "BANK", "IBAN"), ver_full)
    # (2) documentation IP ranges in a documentation context; loopback and unspecified addresses always
    doc_ip = n.OR(P("192\\.0\\.2\\.[0-9]{1,3}", pre="0-9.", post="0-9")[0], P("198\\.51\\.100\\.[0-9]{1,3}", pre="0-9.", post="0-9")[0],
                  P("203\\.0\\.113\\.[0-9]{1,3}", pre="0-9.", post="0-9")[0], P("2001:[dD][bB]8:[0-9a-fA-F:]{0,30}", pre="0-9a-fA-F:", post="0-9a-fA-F")[0], force=True)
    loop_ip = n.OR(P("127\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}", pre="0-9.", post="0-9")[0], P("0\\.0\\.0\\.0", pre="0-9.", post="0-9")[0],
                   n.AND(n.lit("::1"), ~cls("0123456789abcdefABCDEF:").at(-1), ~cls("0123456789abcdefABCDEF:").at(3)), force=True)
    # (an address of someone's activity stays personal even in a documentation range: "client 203.0.113.57", "logged in from ...")
    act_cue = n.OR(*[word(w) for w in ("client", "from", "login", "logged", "user", "customer", "source", "src", "remote", "forwarded", "visitor",
                                       "attacker", "caller", "origin", "signed")], force=True)
    act_near = n.spread_right(act_cue, 24)
    doc_ip_ok = n.AND(doc_ip, doc_ctx, ~n.fill(doc_ip, n.AND(doc_ip, act_near), 5))
    add_veto(("IP", "TEL", "ID", "ADDRESS", "DATE"), n.OR(doc_ip_ok, loop_ip, force=True))
    ctx_not = {"IP": n.OR(doc_ip_ok, loop_ip, force=True)}
    # (3) placeholders and documented examples: always ("PASSWORD_PLACEHOLDER", "<YOUR_API_KEY>", "changeme", "sk_test_example_only");
    #     a value with EXAMPLE in it ("AKIAIOSFODNN7EXAMPLE") only in a documentation context
    tok_any = n.prop_right(n.AND(n.OR(alnum, cls("_<"), force=True), ~n.OR(alnum, cls("_-.<"), force=True).at(-1)),
                           n.OR(alnum, cls("_-.<>"), force=True), 6)
    ph_in = n.OR(*[n.lit(w, nocase=True) for w in ("placeholder", "your_", "your-", "changeme", "change_me", "dummy", "xxxxxx", "redacted", "<your")], force=True)
    ex_in = n.OR(n.lit("example", nocase=True), n.lit("sample", nocase=True), force=True)
    # "example" / "sample" as a whole "_"-separated segment ("sk_test_example_only"), not the start of random characters ("EXAMPLEa9F3")
    ex_seg = n.AND(ex_in, n.lit("_").at(-1), ~alnum.at(7))
    ph_tok = n.AND(tok_any, n.fill(tok_any, n.OR(n.AND(tok_any, ph_in), n.AND(tok_any, ex_seg), n.AND(tok_any, ex_in, doc_ctx), force=True), 6))
    add_veto(("SECRET", "PASS", "ID", "USERNAME", "COOKIE", "CARD", "IDCARD", "TEL"), ph_tok)
    ctx_not["SECRET"] = n.OR(ph_tok, k.secret_metadata, force=True)
    # (4) well-known hex constants and short hex literals are code, not secrets ("0xDEADBEEF", "0x7fff")
    hexlit, _ = P("0[xX][0-9a-fA-F]{1,16}", pre="A-Za-z0-9_", post="A-Za-z0-9_")
    add_veto(("SECRET", "PASS", "ID", "USERNAME", "TEL", "CARD"), hexlit)
    ctx_not["SECRET"] = n.OR(ctx_not["SECRET"], hexlit, force=True)
    # (5) workflow references: a token led by a workflow word ("CI-RUN-884291", "ISSUE-2026-1173", "PR-4410", "JIRA-77", "INC-2231")
    wf = n.OR(*[n.AND(n.lit(w, nocase=True), cls("-_#").at(len(w))) for w in ("CI", "PR", "MR", "ISSUE", "TICKET", "BUG", "INC", "INCIDENT", "RUN",
              "JOB", "BUILD", "RELEASE", "PIPELINE", "DEPLOY", "CHG", "CHANGE", "TASK", "STORY", "EPIC", "SPRINT", "RFC", "CVE", "SEC", "JIRA",
              "GH", "REQ", "OPS", "SRE", "QA", "DEV", "PROJ", "FEAT", "FIX", "HOTFIX", "COMMIT", "REV", "PATCH")], force=True)
    wf_tok = n.prop_right(n.AND(wf, ~n.OR(alnum, cls("_-"), force=True).at(-1)), n.OR(alnum, n.AND(cls("-_#"), alnum.at(1)), force=True), 5)
    wf_tok = n.AND(wf_tok, n.fill(wf_tok, n.AND(wf_tok, digit), 5))          # a reference has a number ("dev_ankit" is a handle)
    add_veto(("ID", "IDCARD", "TEL", "SOCIALNUMBER", "PASSPORT", "DRIVERLICENSE", "CARD", "USERNAME", "SECRET", "PASS", "DATE"), wf_tok)
    ctx_not["ID"] = n.OR(wf_tok, ver_full, force=True)
    # (6) a reference tied to a person or account is personal even after a "reference" cue ("Customer account reference: 551203")
    _, acc_end = P(G("account reference: ", "account reference ", "account ref: ", "account ref ", "customer reference: ", "customer reference ",
                     "customer ref: ", "member reference: ", "client reference: ", "policyholder reference: ", "account no. ", "account no: "), pre="A-Za-z")
    acc_val = n.prop_right(n.AND(alnum, acc_end.at(-1)), n.OR(alnum, n.AND(cls("-/"), alnum.at(1)), force=True), 5)
    c.add("IDCARD", n.AND(acc_val, n.fill(acc_val, n.AND(acc_val, digit), 5)), 0)
    # (7) names in a fictional / tutorial / cryptography context are characters, not people ("Alice and Bob ... encryption tutorial")
    fict_cue = n.OR(*[word(w) for w in ("fictional", "hypothetical", "tutorial", "encryption", "cryptography", "cryptographic", "protocol",
                                        "thought experiment", "characters", "placeholder")], force=True)
    fict_ctx = n.OR(n.spread_right(fict_cue, 90), n.spread_left(fict_cue, 90), force=True)
    add_veto(NAMES, fict_ctx)
    ctx_not["NAME"] = fict_ctx
    # (8) a name used for a project, tool or environment ("Atlas is an internal project", "Falcon is the name of a feature",
    #     "the Atlas project", "project Atlas")
    proj_noun = n.OR(*[word(w) for w in ("project", "tool", "service", "app", "feature", "library", "framework", "product", "codename", "environment",
                                         "repo", "repository", "cluster", "server", "bot", "system", "platform", "module", "pipeline", "plugin",
                                         "initiative", "programme", "program", "team", "workspace", "dashboard")], force=True)
    cap_tok = n.prop_right(n.AND(upper, ~alnum.at(-1)), letters, 4)
    cap_end = n.AND(cap_tok, ~cap_tok.at(1))
    is_proj = n.AND(cap_end, n.lit(" is ").at(1), n.spread_left(proj_noun, 40).at(4))
    before_proj = n.AND(cap_end, sp.at(1), proj_noun.at(2))
    after_proj = n.AND(cap_tok, ~cap_tok.at(-1), n.OR(*[n.lit(w).at(-len(w)) for w in ("project ", "codename ", "Project ", "Codename ", "the ")], force=True) if False else
                       n.OR(*[n.lit(w).at(-len(w)) for w in ("project ", "codename ", "Project ", "Codename ")], force=True))
    proj_name = n.fill(cap_tok, n.OR(is_proj, before_proj, after_proj, force=True), 4)
    add_veto(NAMES, proj_name)
    ctx_not["NAME"] = n.OR(ctx_not["NAME"], proj_name, force=True)
    # (9) "San Francisco", "Santa Cruz", "St. Louis": the saint word is part of the place name too
    saint_w = n.OR(*[n.AND(n.lit(w), ~alnum.at(-1), upper.at(len(w))) for w in ("San ", "Santa ", "Saint ", "St. ", "Sainte ", "Sankt ")], force=True)
    add_veto(NAMES, n.prop_right(saint_w, letters, 3))
    # (10) recovery / seed phrases: the words after the cue ("recovery phrase is copper meadow falcon river")
    _, rp_end = P(G("recovery phrase is ", "recovery phrase: ", "recovery phrase consisting of the words ", "seed phrase is ", "seed phrase: ",
                    "seed words are ", "seed words: ", "mnemonic is ", "mnemonic: ", "mnemonic phrase is ", "backup phrase is ", "secret phrase is ",
                    "recovery words are ", "recovery words: ", "wallet words are ", "phrase consisting of the words "), pre="A-Za-z")
    rp = n.prop_right(n.AND(lower, rp_end.at(-1)), n.OR(lower, n.AND(sp, lower.at(1), lower.at(-1)), force=True), 7)
    rp = n.AND(rp, n.fill(rp, n.AND(rp, sp, n.spread_right(n.AND(rp, sp), 40).at(-1)), 7))           # at least three words
    c.add("SECRET", rp, 0)
    c.phrase_secret = rp
    add_veto(NAMES + ("USERNAME", "CITY"), rp)
    # placeholder PINs and codes as whole tokens ("PIN codes like 0000 or 1234 are rejected")
    sepc = cls("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-./+:_")
    ph_num = n.OR(*[n.AND(n.lit(w), ~sepc.at(-1), ~n.AND(sp.at(-1), digit.at(-2)), ~sepc.at(len(w)), ~n.AND(sp.at(len(w)), digit.at(len(w) + 1)))
                    for w in ("0000", "1234", "1111", "12345", "123456", "000000", "111111", "9999")], force=True)     # standing alone
    ph_num = n.prop_right(ph_num, digit, 3)
    # only as an example ("like 0000 or 1234", "such as 1111", "e.g. 0000") or in a documentation context, never right after
    # a code cue ("CID 1234", "PIN 0000" is a value); and not inside a multi-part code ("22 BH 1234 AA")
    ex_before = n.spread_right(n.OR(*[n.AND(n.lit(w), ~alnum.at(-1)) for w in ("like ", "such as ", "e.g. ", "eg ", "example ", "examples ", "or ", "and ")], force=True), 14)
    ph_num = n.AND(ph_num, n.OR(ex_before, doc_ctx, force=True), ~n.AND(sp.at(-1), alnum.at(-2)) if False else n.OR(ex_before, doc_ctx, force=True),
                   ~n.fill(ph_num, n.OR(n.AND(ph_num, ~ph_num.at(-1), sp.at(-1), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(-2)),
                                        n.AND(ph_num, ~ph_num.at(1), sp.at(1), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789").at(2)), force=True), 3))
    add_veto(("SECRET", "PASS", "ID", "TEL"), ph_num)
    ctx_not["SECRET"] = n.OR(ctx_not["SECRET"], ph_num, force=True)
    # an @word in a code context is a decorator or annotation ("decorators like @property", "@Override in Java")
    code_cue = n.OR(*[word(w) for w in ("decorator", "decorators", "annotation", "annotations", "syntax", "Python", "Java", "TypeScript", "Kotlin",
                                        "class", "method", "function", "import", "def", "module")], force=True)
    code_ctx = n.OR(n.spread_right(code_cue, 60), n.spread_left(code_cue, 60), force=True)
    at_word = n.prop_right(n.AND(cls("@"), ~alnum.at(-1), letters.at(1)), n.OR(letters, cls("@"), force=True), 4)
    at_word = n.AND(at_word, ~n.fill(at_word, n.AND(at_word, n.OR(digit, cls("_.-"), force=True).at(1)), 4), code_ctx)
    add_veto(("USERNAME",), at_word)
    ctx_not["USERNAME"] = at_word
    k.ctx_not = ctx_not
    k.letters = letters


def proper_nouns_and_codes(c, k):
    NAMES = k.NAMES
    P = k.P
    add_veto = k.add_veto
    allb = k.allb
    alnum = k.alnum
    alpha = k.alpha
    cls = k.cls
    ctx_not = k.ctx_not
    digit = k.digit
    letters = k.letters
    n = k.n
    plain_tok = k.plain_tok
    sp = k.sp
    trim = k.trim
    upper = k.upper
    veto = k.veto
    w = k.w
    # ================= proper nouns that are not people, and codes that are not identifiers =================
    cap, wst = c.cap, c.wstart
    capj = n.OR(cap, n.AND(sp, cap.at(-1), wst.at(1)), force=True)
    cap_run_from = lambda start: n.prop_right(n.AND(wst, start), capj, 5)
    # (a) after a lower-case "the", a capitalised run names a thing, a place, a team or an index ("the Sensex", "the Boston
    #     Celtics", "the Prado"), not a person; "the Patel family" is the one common exception
    the_b = n.AND(n.lit("the ").at(-4), ~alnum.at(-5))
    the_run = cap_run_from(the_b)
    fam = n.OR(*[n.lit(" " + w).at(1) for w in ("family", "household", "brothers", "sisters", "twins", "couple", "kids")], force=True)
    the_run = n.AND(the_run, ~n.fill(the_run, n.AND(the_run, ~the_run.at(1), fam), 5))
    # (b) a list of places: a capitalised word joined by ", " or " and " to a known city, state or country, after a
    #     locative word ("wholesalers in Bengaluru and Pune", "markets of Vienna, Salzburg and Innsbruck")
    place_lab = n.OR(c.get("CITY"), c.get("STATE"), c.get("COUNTRY"), force=True)
    loc_w = n.OR(*[n.AND(n.lit(w + " ").at(-(len(w) + 1)), ~alnum.at(-(len(w) + 2))) for w in
                   ("in", "to", "from", "across", "between", "near", "around", "of", "via", "visit", "visited", "visiting", "towards")], force=True)
    link = n.OR(n.AND(cls(","), sp.at(1), wst.at(2)), n.AND(sp, cls(",").at(-1), wst.at(1)),
                n.AND(n.lit(" and ").at(0), wst.at(5)), n.AND(n.lit("and ").at(0), sp.at(-1)), n.AND(n.lit("nd ").at(0), n.lit("a").at(-1)),
                n.AND(n.lit("d ").at(0), n.lit("an").at(-2)), n.AND(sp, n.lit("and").at(-3), wst.at(1)), force=True)
    chain = n.prop_right(n.AND(wst, loc_w), n.OR(cap, link, force=True), 6)
    # a list (two or more items) with a known place in it; a lone word after "in" is not a list
    city_lex = n.OR(c.get("COUNTRY"), c.get("STATE"), *([c.city_lex] if hasattr(c, "city_lex") else []), force=True)
    chain = n.AND(chain, n.fill(chain, n.AND(chain, place_lab), 6), n.fill(chain, n.AND(chain, link), 6))
    # only single-word items: a two-word item ("Rahul Verma") is a name, not a place
    multi = n.fill(cap, n.OR(n.AND(cap, ~cap.at(1), sp.at(1), wst.at(2)), n.AND(wst, sp.at(-1), cap.at(-2)), force=True), 5)
    chain = n.AND(chain, cap, ~multi)
    # (c) a capitalised word right before a place, event or material head ("Rose Day", "May Day", "Rose Gold", "Victoria Station")
    #     or right after a geographic prefix ("Lake Louise", "Mount Abu", "Fort William")
    heads = ("Day", "Week", "Festival", "Fair", "Gardens", "Garden", "Hall", "Museum", "Gallery", "Station", "Airport", "Bridge", "Market",
             "Cathedral", "Church", "Temple", "Mosque", "Palace", "Tower", "Valley", "Beach", "Island", "Islands", "Lake", "River", "Bay",
             "Falls", "Gold", "Silver", "Pink", "Quartz", "Bronze", "Theatre", "Theater", "Stadium", "Arena", "Mall", "Plaza", "Zoo",
             "Fountain", "Memorial", "Monument", "Canal", "Harbour", "Harbor", "Pier", "Gate", "Fort", "Castle", "Abbey", "Square")
    head_after = n.OR(*[n.AND(n.lit(" " + h).at(1), ~alnum.at(len(h) + 2)) for h in heads], force=True)
    pre_head = n.fill(cap, n.AND(cap, ~cap.at(1), head_after), 5)
    pre_head = n.OR(pre_head, n.fill(cap, n.AND(wst, sp.at(-1), pre_head.at(-2), ~alnum.at(-1)), 5), force=True)   # and the head itself
    prefixes = ("Lake", "Mount", "Mt", "River", "Fort", "Cape", "Isle", "Loch", "Port", "Glen", "Lac", "Monte", "Rio")
    pre_fix = n.OR(*[n.AND(n.lit(w + " ").at(-(len(w) + 1)), ~alnum.at(-(len(w) + 2))) for w in prefixes], force=True)
    post_prefix = cap_run_from(pre_fix)
    # (d) languages and nationalities are not names ("translations for German, French and Spanish")
    langs = ("German", "French", "Spanish", "English", "Italian", "Dutch", "Portuguese", "Russian", "Chinese", "Japanese", "Korean",
             "Arabic", "Hindi", "Bengali", "Tamil", "Telugu", "Urdu", "Turkish", "Polish", "Swedish", "Greek", "Hebrew", "Persian", "Thai",
             "Vietnamese", "Indonesian", "Malay", "Swahili", "Marathi", "Gujarati", "Punjabi", "Kannada", "Malayalam", "Czech", "Danish",
             "Finnish", "Norwegian", "Hungarian", "Romanian", "Ukrainian", "Catalan", "Irish", "Welsh", "Scottish", "Mandarin", "Cantonese",
             "Filipino", "Tagalog", "Latin", "American", "British", "Indian", "Canadian", "Australian", "European", "African", "Asian")
    langs = langs + ("Sinhala", "Sinhalese", "Nepali", "Burmese", "Khmer", "Lao", "Pashto", "Dari", "Farsi", "Kurdish", "Amharic",
                     "Somali", "Yoruba", "Igbo", "Hausa", "Zulu", "Xhosa", "Afrikaans", "Odia", "Assamese", "Konkani", "Maithili",
                     "Sindhi", "Kashmiri", "Tibetan", "Mongolian", "Uzbek", "Kazakh", "Tajik", "Turkmen", "Azerbaijani", "Armenian",
                     "Albanian", "Serbian", "Croatian", "Bosnian", "Slovenian", "Slovak", "Bulgarian", "Macedonian", "Lithuanian",
                     "Latvian", "Estonian", "Icelandic", "Basque", "Galician", "Maltese", "Hawaiian", "Maori", "Quechua", "Guarani",
                     "Aymara", "Yiddish", "Esperanto", "Javanese", "Sundanese", "Cebuano", "Hmong", "Hindustani", "Tigrinya",
                     "Oromo", "Kinyarwanda", "Lingala", "Wolof", "Fula", "Shona", "Sesotho", "Setswana", "Malagasy", "Bengali")
    glued = lambda L: n.OR(n.AND(cls("-'").at(-1), alpha.at(-2)), n.AND(cls("-").at(L), alpha.at(L + 1)), force=True)   # "Al-Farsi"
    lang_w = n.OR(*[n.AND(n.lit(w), ~alnum.at(-1), ~alpha.at(len(w)), ~n.AND(sp.at(len(w)), wst.at(len(w) + 1)), ~glued(len(w)))
                    for w in langs], force=True)
    # religions and traditions ("Theravada Buddhism", "Sunni Islam"): never names, also as the first word of a pair
    faiths = ("Buddhism", "Buddhist", "Theravada", "Mahayana", "Vajrayana", "Hinduism", "Hindu", "Islam", "Islamic", "Muslim",
              "Christianity", "Christian", "Catholicism", "Catholic", "Protestantism", "Protestant", "Judaism", "Jewish", "Sikhism",
              "Sikh", "Jainism", "Jain", "Shinto", "Taoism", "Daoism", "Confucianism", "Zoroastrianism", "Orthodox", "Anglican",
              "Methodist", "Baptist", "Lutheran", "Presbyterian", "Pentecostal", "Evangelical", "Sunni", "Shia", "Shiite", "Sufi",
              "Atheism", "Agnosticism", "Mormon", "Quaker", "Amish", "Rastafarian", "Wicca", "Paganism", "Bahai", "Vedanta")
    faith_w = n.OR(*[n.AND(n.lit(w), ~alnum.at(-1), ~alpha.at(len(w)), ~glued(len(w))) for w in faiths], force=True)
    faith_tok = n.prop_right(faith_w, alpha, 4)
    # a capitalised word named as a language: "X language", "X speakers", "X-speaking", "X script", "the language ... is X"
    lang_after = n.OR(*[n.lit(w).at(1) for w in (" language", " languages", " speakers", "-speaking", " script",
                                                   " dialect", " alphabet", " literature", " grammar", " translation")], force=True)
    capw_end = n.AND(cap, ~cap.at(1))
    named_lang = n.fill(cap, n.AND(capw_end, lang_after), 5)
    lang_before = n.AND(n.spread_right(n.lit("language"), 40), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), ~alnum.at(-1),
                        n.OR(n.lit(" is ").at(-4), n.lit(" was ").at(-5), n.lit(" are ").at(-5), force=True))
    is_lang = n.AND(n.lit(" is the ").at(1), n.spread_left(n.lit("language"), 40).at(8))
    named_lang = n.OR(named_lang, n.fill(cap, n.AND(wst, lang_before), 5), n.fill(cap, n.AND(capw_end, is_lang), 5), force=True)
    # places named by their kind: "the city of Kandy", "Central Province", "the district of Kandy"
    of_place = n.OR(*[n.AND(n.lit(w + " of "), ~alpha.at(-1)).at(-(len(w) + 4)) for w in
                      ("city", "town", "village", "province", "district", "region", "state", "county", "municipality", "capital",
                       "island", "port", "kingdom", "republic", "City", "Town", "Province", "District", "Region", "State")], force=True)
    place_run = n.prop_right(n.AND(wst, of_place), capj, 5)
    prov = n.fill(cap, n.AND(capw_end, n.OR(*[n.AND(n.lit(" " + w), ~alpha.at(len(w) + 1)).at(1) for w in
                                              ("Province", "District", "County", "Region", "Prefecture", "Oblast", "Governorate")],
                                            force=True)), 5)
    # countries: the gazetteer, without the few that are also common first names
    from ..common import COUNTRIES
    clist = [x for x in (COUNTRIES.split("|") if isinstance(COUNTRIES, str) else COUNTRIES)
             if x and x not in ("Jordan", "Chad", "Georgia", "Israel", "India", "Niger", "Kenya", "Ireland", "Holland")]
    clist += ["Samoa", "Burkina Faso", "Timor-Leste", "East Timor", "Eswatini", "Cabo Verde", "Côte d'Ivoire", "Vatican City"]
    country_w = n.OR(*[n.AND(n.lit(x.encode("utf-8").decode("latin-1")), ~alpha.at(-1), ~alpha.at(len(x.encode("utf-8")))) for x in clist], force=True)
    country_tok = n.OR(*[n.spread_right(n.AND(n.lit(x.encode("utf-8").decode("latin-1")), ~alpha.at(-1), ~alpha.at(len(x.encode("utf-8")))),
                                         len(x.encode("utf-8"))) for x in clist if " " in x or "-" in x], country_w, force=True)
    country_tok = n.prop_right(country_tok, alpha, 4)
    lang_tok = n.prop_right(lang_w, alpha, 4)
    not_person = n.OR(the_run, chain, pre_head, post_prefix, lang_tok, faith_tok, named_lang, place_run, prov, country_tok, force=True)
    add_veto(NAMES, not_person)
    ctx_not["NAME"] = n.OR(ctx_not["NAME"], not_person, force=True)
    # (e) standards and algorithm names are not identifiers or addresses ("EN 55032", "ISO 27001", "HMAC-SHA256", "AES-256-GCM")
    std = P(G("EN ", "ISO ", "IEC ", "IEEE ", "ANSI ", "BS ", "DIN ", "ASTM ", "CISPR ", "ETSI ", "NIST SP ", "ISO/IEC ", "IS ", "UL ")
            + "[0-9]{3,6}", pre="A-Za-z0-9", post="0-9")[0]
    std = n.OR(std, n.prop_right(n.AND(n.OR(cls("-:"), force=True), std.at(-1), digit.at(1)), n.OR(digit, cls("-:."), force=True), 3), force=True)
    algo = n.OR(P(G("HMAC-SHA", "HMAC-MD", "SHA-", "SHA", "AES-", "RSA-", "ECDSA-P", "PBKDF2-SHA", "HKDF-SHA", "ChaCha20-Poly")
                  + "[0-9]{1,4}" + "[A-Za-z0-9-]{0,16}", pre="A-Za-z0-9", post="A-Za-z0-9")[0],
                P(G("X25519", "X448", "Ed25519", "Ed448", "P-256", "P-384", "P-521", "MD4", "MD5", "CRC16", "CRC32", "CRC64",
                    "secp256k1", "secp256r1", "secp384r1", "Curve25519"), pre="A-Za-z0-9", post="A-Za-z0-9")[0], force=True)
    add_veto(("ID", "ADDRESS", "POSTCODE", "STATE", "SECADDRESS", "USERNAME", "TEL", "SECRET", "PASS", "IDCARD"), n.OR(std, algo, force=True))
    ctx_not["ID"] = n.OR(ctx_not["ID"], std, algo, force=True)
    # (f) a name followed by a version is software ("libxml2 to 2.12", "openssl 3.0.13", "node@20.11")
    vers_after = n.OR(n.AND(sp.at(1), digit.at(2), cls(".").at(3)), n.AND(sp.at(1), digit.at(2), digit.at(3), cls(".").at(4)),
                      n.AND(n.lit(" to ").at(1), digit.at(5), cls(".").at(6) if False else digit.at(5)), n.AND(n.lit(" v").at(1), digit.at(3)),
                      n.AND(cls("@").at(1), digit.at(2), ~c.get("IP").at(2)), force=True)
    # (a version has a digit after its dot: "64." ends a sentence)
    vers_after = n.AND(vers_after, ~n.AND(sp.at(1), digit.at(2), cls(".").at(3), ~digit.at(4)),
                       ~n.AND(sp.at(1), digit.at(2), digit.at(3), cls(".").at(4), ~digit.at(5)))
    swtok = n.prop_left(n.AND(n.OR(alnum, cls("_-."), force=True), vers_after), n.OR(alnum, cls("_-"), force=True), 5)
    add_veto(("USERNAME", "ID") + NAMES, swtok)
    # (g) a short all-digit token is never a handle ("1900", "42")
    tokc_ = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-.@/")
    d4 = n.prop_right(n.AND(digit, ~tokc_.at(-1), ~cls(HI).at(-1)), digit, 3)
    add_veto(("USERNAME",), n.AND(d4, n.fill(d4, n.AND(d4, ~d4.at(1), ~n.AND(tokc_.at(1), alnum.at(2)), ~alnum.at(1), ~cls(HI).at(1),
                                                    ~n.run(d4, 5).at(-4)), 3)))
    # (h) log levels and compiler diagnostics are not names or identifiers ("ERROR", "WARN", "error[E0382]")
    lvl = n.OR(*[n.AND(n.lit(w), ~alnum.at(-1), ~alnum.at(len(w))) for w in
                 ("ERROR", "WARN", "WARNING", "INFO", "DEBUG", "FATAL", "TRACE", "CRITICAL", "NOTICE", "SEVERE", "PANIC", "ALERT", "EMERG")], force=True)
    lvl_tok = n.prop_right(lvl, upper, 4)
    diag = P(G("error[", "warning[", "error ", "warning ") + "[A-Z]{1,3}[0-9]{3,5}", pre="A-Za-z")[0]
    diag = n.OR(diag, n.AND(cls("]"), diag.at(-1)), force=True)
    add_veto(("ID", "USERNAME", "SECRET", "PASS", "IDCARD") + NAMES, n.OR(lvl_tok, diag, force=True))
    ctx_not["ID"] = n.OR(ctx_not["ID"], lvl_tok, diag, force=True)
    # (i) a router's default address, introduced as such, is not a person's ("the default gateway address is 192.168.1.1")
    gw_w = n.OR(*[n.lit(w, nocase=True) for w in ("default gateway", "gateway address", "router address", "router ip", "default ip",
                                                   "admin page at", "router login", "default address")], force=True)
    gw_ip = n.AND(c.get("IP"), n.spread_right(gw_w, 40))
    add_veto(("IP",), gw_ip)
    # (j) a school class, grade or standard is not an identifier ("Homework for Class 9", "Grade 10 results")
    cls_w = P(G("Class ", "Grade ", "Std ", "Std. ", "Standard ", "Year ", "Form ", "Semester ", "Sem ", "Division ", "Batch ", "Level ",
                "Chapter ", "Lesson ", "Unit ", "Module ", "Week ", "Round ", "Phase ", "Stage ", "Platform ", "Gate ", "Bay ", "Aisle ")
              + "[0-9]{1,2}[A-Za-z]?", pre="A-Za-z", post="0-9A-Za-z")[0]
    # (a class attached to someone is about that person: "Her son Aarav, 7, is in Class 2C")
    attached = n.OR(*[n.lit(w).at(-len(w)) for w in ("is in ", "studies in ", "studying in ", "enrolled in ", "attends ", "in the ")], force=True)
    cls_w = n.AND(cls_w, ~n.fill(cls_w, n.AND(cls_w, ~cls_w.at(-1), attached), 4))
    nonl2 = cls(allb.replace("\n", ""))
    person_line = n.OR(n.spread_right(n.AND(n.OR(c.get("GIVENNAME"), c.get("LASTNAME"), force=True), nonl2), 80),
                       n.spread_left(n.AND(n.OR(c.get("GIVENNAME"), c.get("LASTNAME"), force=True), nonl2), 80), force=True)
    cls_w = n.AND(cls_w, ~n.fill(cls_w, n.AND(cls_w, person_line), 4))           # "Student: Aarush Gupta, Class 3-C"
    add_veto(("ID", "IDCARD", "USERNAME", "TEL", "POSTCODE"), cls_w)
    ctx_not["ID"] = n.OR(ctx_not["ID"], cls_w, force=True)
    # (k) letters glued to digits are a handle or a code, never a name ("ana1985", "2fast")
    #     (only a plain letters-and-digits token: inside "priya.sharma91" the name parts link the handle to its owner)
    lrun = n.prop_right(n.AND(letters, ~letters.at(-1)), letters, 5)
    glued = n.fill(lrun, n.OR(n.AND(lrun, ~lrun.at(1), digit.at(1)), n.AND(lrun, ~lrun.at(-1), digit.at(-1)), force=True), 5)
    hsep = cls("._-@#")
    atok = n.prop_right(n.AND(alnum, ~alnum.at(-1)), alnum, 5)
    plain_tok = n.AND(atok, ~n.fill(atok, n.OR(n.AND(atok, ~atok.at(-1), hsep.at(-1)), n.AND(atok, ~atok.at(1), hsep.at(1), alnum.at(2)), force=True), 5))
    add_veto(NAMES, n.AND(glued, plain_tok))
    # URLs: the person's part of a URL is a handle or a record id, never a name; an article title is a topic
    if hasattr(c, "url_person"):
        add_veto(NAMES + ("CITY", "ORG", "DATE", "TEL", "URL"), c.url_person)
        add_veto(NAMES + ("USERNAME", "ID", "SECRET", "PASS"), c.url_topic)
        ctx_not["NAME"] = n.OR(ctx_not["NAME"], c.url_topic, force=True)
    c.ctx_not = ctx_not
    c.key_trim = trim
    c.key_veto = veto
