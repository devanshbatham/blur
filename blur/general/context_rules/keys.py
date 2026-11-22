"""Reading a key: its word parts, the carriers values sit in (JSON, query strings, headers, config lines, XML,
prose), the values under secret / plain / place / device keys, value shapes, URL credentials, auth schemes and cookies."""
from .words import *  # noqa: F401,F403  (word-part vocabulary and shared imports)


def read_keys(c, k):
    n = c.n
    cls = n.cls
    allb = "".join(chr(i) for i in range(1, 256))
    nonl = cls(allb.replace("\n", ""))
    sp = cls(" \t")
    digit = cls("0123456789")
    alnum = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
    lower = cls("abcdefghijklmnopqrstuvwxyz")
    upper = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    alpha = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    hexc = cls("0123456789abcdefABCDEF")
    keyc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")

    def P(pattern, pre=None, post=None, **kw):
        cs = lambda x: parse_var("[" + x + "]")[0][0] if x else None
        return n.match(parse_var(pattern), cs(pre), cs(post), **kw)

    # ---------- reading a key: word parts ----------
    # a part starts at the key's start, after - _ . , at a lower->Upper step ("appVersion"), or at a letter after a digit,
    # and ends where the next part starts (no lower-case letter follows it)
    notkey = cls("".join(ch for ch in allb if not (ch.isascii() and (ch.isalnum() or ch in "_.-"))))   # (an OR takes no negated input)
    comp_start = n.AND(alnum, n.OR(notkey.at(-1), cls("\x00").at(-1), cls("-_.").at(-1), n.AND(upper, lower.at(-1)), n.AND(alpha, digit.at(-1)), force=True))
    def part(word):                       # the word, or its plural ("items", "headers")
        L = len(word)
        # inside a run of capitals a part ends where the capitals end: "SHA_256", "XMLHttp", but not "SHA" in "SHARMA"
        caps_go_on = lambda m: n.AND(upper.at(m - 1), upper.at(m), ~lower.at(m + 1))
        return n.OR(n.AND(comp_start, n.lit(word, nocase=True), ~lower.at(L), ~caps_go_on(L)),
                    n.AND(comp_start, n.lit(word + "s", nocase=True), ~lower.at(L + 1), ~caps_go_on(L + 1)), force=True)
    cls_hit = {k: n.OR(*[part(w) for w in ws], force=True) for k, ws in PARTS.items()}
    # an identifier word that ends the key ("employee_number", "UniqueIdentifier"; not "x-amz-id-2")
    cls_hit["idlast"] = n.OR(*[n.AND(comp_start, n.lit(w, nocase=True), ~keyc.at(len(w))) for w in PARTS["idword"]], force=True)
    # a protocol header ("X-Amz-Id-2", "x-request-id") is not a record field
    cls_hit["xhdr"] = n.AND(n.lit("x-", nocase=True), ~keyc.at(-1))

    # carriers: the matched key (with its quotes and separator), where its value starts, and what a value byte may be
    # Odd backslash runs escape a quote; even runs end before it. Binary hops
    # cover the bounded value window without enumerating escape sequences.
    slash = cls("\\")
    odd_slash = n.AND(slash, ~slash.at(-1))
    for power in range(1, 8):
        hop = 1 << power
        odd_slash = n.OR(odd_slash, n.AND(odd_slash.at(-hop), n.run(slash, hop).at(1 - hop)), force=True)
    escaped = odd_slash.at(-1)
    val_json = n.OR(cls(allb.replace('"', "").replace("\n", "")), n.AND(cls('"'), escaped), force=True)
    val_sq = n.OR(cls(allb.replace("'", "").replace("\n", "")), n.AND(cls("'"), escaped), force=True)
    val_param = cls(allb.replace("&", "").replace(";", "").replace(" ", "").replace("\n", "").replace('"', "").replace("'", "").replace(",", "").replace(":", ""))
    val_xml = cls(allb.replace("<", "").replace("\n", ""))
    KEY = "[A-Za-z0-9_.-]{1,60}"
    # a line key starts its line (indentation allowed)
    line_start = n.OR(n.prop_right(n.OR(cls("\n"), cls("\x00"), force=True), sp, 4).at(-1), force=True)
    # a line "Key: value" is machine text when the key has a separator or is lower-case, or the value has no space soon after
    lk_span, lk_end = P(KEY + G(": ", ":\t"), pre="A-Za-z0-9_.-", start_terms=[line_start])
    key_sep_or_lower = n.fill(lk_span, n.AND(lk_span, n.OR(cls("-_."), n.AND(lower, lower.at(1), ~upper.at(-1)) if False else cls("-_."), force=True)), 6)
    all_lower_key = n.AND(lk_end, ~n.fill(lk_span, n.AND(lk_span, upper), 6))
    soon_space = n.spread_left(n.AND(sp, nonl), 24).at(2)
    # the rest of the line is prose when it has a space that does not follow a comma (a list "a, b, c" is not prose)
    prose_after = n.prop_left(n.AND(sp, ~cls(",").at(-1)), nonl, 7)
    line_key = (n.AND(lk_span, n.fill(lk_span, n.AND(lk_end, n.OR(key_sep_or_lower, all_lower_key, ~soon_space if False else key_sep_or_lower, force=True)), 6)) if False else lk_span,
                n.AND(lk_end, n.OR(n.AND(key_sep_or_lower, lk_end), all_lower_key, n.AND(lk_end, ~soon_space),
                                   n.AND(n.fill(lk_span, n.AND(lk_span, cls_hit["plain"]), 6), ~prose_after.at(2)), force=True)))
    # prose key-value: "a session cookie named __Host-session with value 94b7...", "the token labeled auth_token with value 8Gm2...",
    # "the variable API_KEY set to abc123" - the named key's word parts decide, as in machine syntax
    prose_kv = P(G("named ", "labeled ", "labelled ", "called ", "variable ", "field ", "parameter ", "header ", "cookie ") + "[A-Za-z0-9_.-]{2,60}" +
                 G(" with value ", " with the value ", " with a value of ", " set to ", " has value ", " has the value ", " valued ", " = ", " of "),
                 pre="A-Za-z")
    carriers = [
        (prose_kv, cls(allb.replace(" ", "").replace("\n", "").replace(",", "").replace(";", "").replace('"', "").replace("'", "").replace(")", ""))),
        (P('"' + KEY + '"' + G(': "', ':"', ": '")), val_json),
        (P("'" + KEY + "'" + G(": '", ":'")), val_sq),
        (P(KEY + "=", pre="A-Za-z0-9_.-"), val_param),
        (P(KEY + G(" = ", " := ", "= "), pre="A-Za-z0-9_.-", start_terms=[line_start]),
         cls(allb.replace(" ", "").replace("\n", "").replace('"', "").replace("'", "").replace(";", "").replace("&", "").replace(",", ""))),
        (line_key, nonl),
        (P("<" + KEY + ">"), val_xml),
        # hash rockets and subscript assignment ("'secret' => 'x'", "app.config[\"MAIL_PASSWORD\"] = \"x\"")
        (P('"' + KEY + '"' + G(' => "', '=>"', '] = "', ']="')), val_json),
        (P("'" + KEY + "'" + G(" => '", "=>'", "] = '", "]='")), val_sq),
        # a quoted value assigned in code ("salt = \"...\"", "const secret = '...'", "token := \"...\"")
        (P(KEY + G(' = "', ' := "', ' ?= "'), pre="A-Za-z0-9_.-"), val_json),
        (P(KEY + G(" = '", " := '", " ?= '"), pre="A-Za-z0-9_.-"), val_sq),
        # without spaces only at the start of a line (shell, .env): inside a tag, name="x" is an HTML attribute
        (P(KEY + '="', pre="A-Za-z0-9_.-", start_terms=[line_start]), val_json),
        (P(KEY + "='", pre="A-Za-z0-9_.-", start_terms=[line_start]), val_sq),
    ]

    def values(class_names, without=(), quoted=False):
        """Bytes of values whose key has a part in any of `class_names` and no part in `without`."""
        outs = []
        for (span, end), vchars in carriers:
            if quoted and vchars not in (val_json, val_sq):
                continue
            has = n.fill(span, n.AND(span, n.OR(*[cls_hit[k] for k in class_names], force=True)), 6)
            if without:
                has = n.AND(has, ~n.fill(span, n.AND(span, n.OR(*[cls_hit[k] for k in without], force=True)), 6))
            v = n.prop_right(n.AND(end.at(-1), has.at(-1), vchars), vchars, 7)
            # a value that opens an object or array ("headers: {...}") is a container: its own keys decide inside it
            v = n.AND(v, ~n.fill(v, n.AND(v, ~v.at(-1), cls("{[")), 7))
            if quoted:
                closing = cls('"' if vchars is val_json else "'")
                v = n.AND(v, n.fill(v, n.AND(v, ~v.at(1), closing.at(1)), 7))
            if span is prose_kv[0]:                     # a sentence's full stop or colon ends a prose value
                v = n.AND(v, ~n.AND(cls(".:!?"), ~alnum.at(1)))
            if vchars is val_xml:                      # an element's value counts only when its closing tag follows
                v = n.AND(v, n.prop_left(n.AND(vchars, n.lit("</").at(1)), vchars, 7))
            outs.append(v)
        return n.OR(*outs, force=True)

    veto = {}
    def add_veto(labels, sig):
        for lab in labels:
            veto[lab] = n.OR(veto[lab], sig, force=True) if lab in veto else sig

    NAMES = ("GIVENNAME", "LASTNAME")
    PERSONAL = ("SECRET", "PASS", "ID", "USERNAME", "GIVENNAME", "LASTNAME", "IDCARD", "CARD", "SOCIALNUMBER", "PASSPORT", "DRIVERLICENSE",
                "COOKIE", "DATE", "BOD", "TEL", "ADDRESS", "POSTCODE", "BUILDING", "STREET", "SECADDRESS", "CITY")

    # plain keys: their values are not personal
    plain = values(("plain",), without=("person", "secret", "device", "idempotency"))
    add_veto(PERSONAL, plain)
    # secret keys (but a key's own name / id / type / path is not the key itself)
    secret_v = values(("secret", "idempotency"), without=("keyname", "plain"))
    # (the first token of the value: "pass: Crimson#Valley2026 (rotate monthly)" ends at the space)
    secret_v = n.AND(secret_v, ~n.prop_right(n.AND(sp, secret_v), secret_v, 7))
    c.add("SECRET", n.AND(secret_v, ~cls(" \"'"), n.fill(secret_v, digit, 6), n.fill(secret_v, alpha, 6)), 0)
    pw_v = values(("pw",), without=("keyname", "plain"))
    # A quoted password is one value, including spaces and code-like punctuation.
    # Giving its whole span the same priority avoids a first-token SECRET claim
    # splitting a lower-priority PASS claim and leaking the rest of a passphrase.
    c.literal_password = values(("pw",), without=("keyname", "plain"), quoted=True)
    # Terraform/HCL binds a default to the enclosing variable's name. This is
    # explicit block scope, not a password cue leaking across unrelated lines.
    variable, variable_end = P('variable "' + KEY + '"[ \t]{0,8}\\{', pre="A-Za-z0-9_$")
    secret_variable = n.AND(variable,
        n.fill(variable, n.AND(variable, cls_hit["secret"]), 6),
        ~n.fill(variable, n.AND(variable, n.OR(cls_hit["plain"], cls_hit["keyname"], force=True)), 6))
    block = n.prop_right(n.AND(variable_end, secret_variable), cls(allb.replace("{", "").replace("}", "")), 8)
    _, default_end = P('default[ \t]{0,8}=[ \t]{0,8}"', pre="A-Za-z0-9_$", start_terms=[block])
    default = n.prop_right(n.AND(val_json, default_end.at(-1)), val_json, 7)
    default = n.AND(default, n.fill(default, n.AND(default, ~default.at(1), cls('"').at(1)), 7))
    c.literal_password = n.OR(c.literal_password, default, force=True)
    c.add("SECRET", c.literal_password, 0)
    # API/access/signing keys can be opaque alphabetic strings, with no digits.
    # Require both a credential key and its scope, a quoted value, and a whole
    # uninterrupted token. Generic map keys and prose are not sufficient.
    scoped = n.AND(values(("secret",), without=("keyname", "plain"), quoted=True),
                   values(("credential_scope",), quoted=True))
    opaque = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-+/=")
    scoped = n.AND(scoped, ~n.fill(scoped, n.AND(scoped, ~opaque), 7),
                   n.fill(scoped, n.AND(scoped, n.run(opaque, 8)), 7), n.fill(scoped, n.AND(scoped, alpha), 7))
    c.add("SECRET", scoped, 0)
    pw_v = n.AND(pw_v, ~n.prop_right(n.AND(sp, pw_v), pw_v, 7), ~cls(" \"'"))
    c.add("SECRET", n.AND(pw_v, n.fill(pw_v, n.AND(pw_v, n.run(alpha, 4)), 6)), 1)    # letters only, four or more
    # the private members of a JSON Web Key ("kty" nearby): d, p, q, dp, dq, qi (RSA / EC private parts), k (a symmetric key)
    _, jwk_end = P('"' + G("d", "p", "q", "dp", "dq", "qi", "k") + '"' + G(': "', ':"'), pre="A-Za-z0-9_")
    kty = n.lit('"kty"')
    near_kty = n.OR(n.spread_right(kty, 400), n.spread_left(kty, 400), force=True)
    jwk_v = n.prop_right(n.AND(val_json, jwk_end.at(-1), near_kty), val_json, 7)
    c.add("SECRET", n.AND(jwk_v, n.fill(jwk_v, n.run(val_json, 16), 7)), 0)
    place = values(("place",), without=("person",))
    add_veto(NAMES + ("ADDRESS", "SECRET", "PASS", "USERNAME", "ID"), place)
    dev = values(("device",), without=("plain",))
    c.add("USERNAME", n.AND(dev, ~sp, ~cls("\"'"), n.fill(dev, alnum, 6)), 0)
    add_veto(("ID", "CARD", "TEL", "SECRET", "PASS", "IP", "COOKIE"), dev)
    addr = values(("address",), without=("plain",))
    c.add("ADDRESS", n.AND(addr, n.fill(addr, digit, 6), ~cls("\"'")), 0)
    add_veto(NAMES + ("ID",), addr)
    # a value under an identifier key ("UniqueIdentifier", "employee_number", "member_no", "patientId") with no plain part
    # ("request_id", "product_id", "build_number", "page_number") and a digit in it is an identifier
    idv = values(("idlast",), without=("plain", "secret", "device", "place", "postcode", "address", "xhdr"))
    idv = n.AND(idv, ~sp, ~cls("\"'"), n.fill(idv, n.AND(idv, digit), 6))
    c.add("ID", idv, 1)
    post = values(("postcode",))
    c.add("POSTCODE", n.AND(post, alnum), 0)
    add_veto(("SECRET", "PASS", "ID", "TEL"), post)

    # ---------- labels on lines of machine text are keys, never names ----------
    line_start_word = n.AND(alnum, n.OR(cls("\n").at(-1), cls("\x00").at(-1), force=True))
    key_tok = n.prop_right(line_start_word, keyc, 5)
    key_tok_end = n.AND(key_tok, cls(":").at(1))
    machine_after = n.prop_left(n.AND(n.OR(cls("=;/<>{}@"), n.AND(cls("."), alnum.at(-1), alnum.at(1)), digit, force=True), nonl), nonl, 6)
    key_label = n.fill(key_tok, n.AND(key_tok_end, machine_after.at(2)), 5)
    hyph_title = n.fill(n.prop_right(n.AND(upper, ~alnum.at(-1)), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-"), 5),
                        n.AND(cls("-"), upper.at(1), lower.at(-1)), 5)
    hyph_key = n.AND(hyph_title, n.fill(hyph_title, n.AND(hyph_title, cls(":").at(1)), 5))
    # a hyphenated Title-Case compound of ordinary English words is a term ("Accept-Encoding", "Cache-Control"), not a
    # double-barrelled surname ("Okonkwo-Reyes")
    hyph_eng = n.AND(hyph_title, ~n.fill(hyph_title, n.AND(hyph_title, alpha, ~c.english), 5))
    hyph_key = n.OR(hyph_key, hyph_eng, force=True)
    add_veto(NAMES + ("USERNAME", "CITY"), n.OR(key_label, hyph_key, force=True))

    # ---------- value shapes ----------
    prod_span, _ = P("[A-Za-z][A-Za-z+-]{1,20}/[0-9]{1,4}\\.[0-9.]{1,14}", pre="A-Za-z0-9_/-", post="A-Za-z0-9_/-")
    add_veto(("SECRET", "PASS", "IP", "ID", "USERNAME", "DATE", "COOKIE"), prod_span)
    ver_span, _ = P("[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}", pre="A-Za-z0-9._/-", post="A-Za-z0-9._/-")
    add_veto(("SECRET", "PASS", "ID"), ver_span)
    mime_span, _ = P(G("application", "multipart", "text", "image", "audio", "video", "font") + "/[a-z0-9.+-]{2,40}", pre="A-Za-z0-9_-")
    add_veto(("USERNAME", "SECRET", "PASS", "ID") + NAMES, mime_span)
    bool_span, _ = P("=" + G("on", "off", "true", "false", "yes", "no"), post="A-Za-z0-9")
    add_veto(("SECRET", "PASS", "COOKIE"), n.prop_left(n.AND(cls("="), bool_span), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_=-"), 5))
    add_veto(("SECRET", "PASS", "COOKIE"), bool_span)
    uuid_span, _ = P("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", pre="0-9a-fA-F-", post="0-9a-fA-F-")
    dev_near = n.OR(dev, n.spread_right(cls_hit["device"], 24), force=True)
    # a long hex token is a hash (a commit, a checksum), unless it is introduced as someone's identifier
    # ("unique ID 8d969eef...", "user id: 3f2a..."); machine ids (trace, request, commit) stay out through not_personal
    id_led = said(c, ["id", "identifier", "uid", "unique id", "user id", "customer id", "member id", "investor id", "client id",
                      "patient id", "employee id", "account id", "subscriber id", "player id", "student id", "applicant id", "profile id"])
    # a UUID is a machine id (a request, a trace), unless it belongs to a device or is introduced as someone's identifier
    url_rec = c.url_person if hasattr(c, "url_person") else dev_near
    add_veto(("ID", "USERNAME", "CARD", "TEL"), n.AND(uuid_span, ~n.fill(uuid_span, n.AND(uuid_span, n.OR(dev_near, id_led, url_rec, force=True)), 6)))
    for L_ in (32, 40, 64):
        hx, _ = P("[0-9a-f]{%d}" % L_, pre="0-9a-zA-Z", post="0-9a-zA-Z")
        add_veto(("ID", "USERNAME", "CARD", "TEL"), n.AND(hx, ~n.fill(hx, n.AND(hx, n.OR(dev_near, id_led, url_rec, force=True)), 6)))
    region_scope = n.OR(P("[a-z]{2}-[a-z]{3,10}-[0-9]", pre="A-Za-z0-9_-", post="A-Za-z0-9_")[0],
                        P(G("/", "%2F", "%2f") + "[a-z]{2}-[a-z]{3,10}-[0-9]", post="A-Za-z0-9_")[0], force=True)
    scope_tail = n.OR(P("/[a-z0-9]{2,10}/[a-z0-9]{2,10}_request")[0], P(G("%2F", "%2f") + "[a-z0-9]{2,10}" + G("%2F", "%2f") + "[a-z0-9]{2,10}_request")[0], force=True)
    scope = n.OR(region_scope, scope_tail, force=True)
    add_veto(("ID", "USERNAME"), scope)
    trim = {"SECRET": scope, "PASS": scope}
    # keys themselves are never values: the "key" of a JSON / dict pair
    for (span, end), vchars in carriers[1:3]:
        kbytes = n.AND(span, ~end)
        # a key that holds data itself (a map keyed by SSN, e-mail or record number) is not exempt
        kbytes = n.AND(kbytes, ~n.fill(span, n.AND(span, n.OR(n.run(digit, 3), cls("@"), force=True)), 6))
        add_veto(PERSONAL + ("EMAIL", "PROFILE", "URL"), kbytes)
    # API object ids: a short lower-case type prefix, "_", and a body with a digit ("evt_YrA3k...", "usr_10441", "doc_mpE...")
    # are record handles, not people's identifiers (secrets with a prefix stay secrets: this vetoes ID / USERNAME only)
    # the body is all digits ("usr_10441") or random-looking: 8+ characters mixing upper case, lower case and digits
    # ("evt_YrA3kKmOU1SAmG7s"); "john_doe92" or "priya_s" are handles. Never right after "@".
    obj_num, _ = P("[a-z]{2,4}_[0-9]{4,20}", pre="A-Za-z0-9_@", post="A-Za-z0-9_")
    obj_rnd, _ = P("[a-z]{2,4}_[A-Za-z0-9]{8,40}", pre="A-Za-z0-9_@", post="A-Za-z0-9_")
    obj_rnd = n.AND(obj_rnd, n.fill(obj_rnd, n.AND(obj_rnd, upper), 6), n.fill(obj_rnd, n.AND(obj_rnd, lower, cls("_").at(-1) if False else lower), 6),
                    n.fill(obj_rnd, n.AND(obj_rnd, digit), 6))
    obj = n.OR(obj_num, obj_rnd, force=True)
    add_veto(("ID", "USERNAME", "CARD", "TEL"), obj)
    tok_start = n.AND(alnum, n.OR(notkey.at(-1), cls("\x00").at(-1), force=True))
    # the value's whole first word is a plain word, followed by "-" or "_" ("SKU-4111-XL", "req_61rz")
    plain_head = n.AND(tok_start, n.OR(*[n.AND(n.lit(w, nocase=True), cls("-_[").at(len(w))) for w in PARTS["plain"] + ("warning", "warn", "info", "debug", "fatal") if len(w) >= 3], force=True))
    plain_tok = n.prop_right(plain_head, n.OR(alnum, n.AND(cls("-_["), alnum.at(1)), force=True), 5)
    plain_code = n.AND(plain_tok, n.fill(plain_tok, n.AND(plain_tok, cls("-_")), 5))
    add_veto(("ID", "USERNAME", "CARD", "TEL", "SECRET", "PASS"), plain_code)
    # a CSV header row: a line made only of lower-case field names and commas, with at least two commas
    # ("id,name,email,phone,dob,card_last4") names the columns; it holds no values
    fieldc = cls("abcdefghijklmnopqrstuvwxyz0123456789_,")
    bad_c = n.AND(nonl, ~fieldc)
    two_commas = n.AND(cls(","), n.spread_right(cls(","), 60).at(-1))
    hdr_row = n.AND(fieldc, ~n.fill(nonl, bad_c, 7), n.fill(nonl, two_commas, 7))
    add_veto(PERSONAL + ("EMAIL", "PROFILE", "URL"), hdr_row)
    # host names: dot-separated labels ending in an alphabetic top-level label, not an e-mail's local part
    # ("usw1-toolbox2-prod.corp.apple.com", "api.internal.example.io") are machines, not handles, names or ids
    TLD = G("com", "net", "org", "io", "dev", "app", "ai", "co", "cloud", "internal",
                     "corp", "lan", "intranet", "gov", "edu", "mil", "int", "biz", "info", "tech", "xyz", "site", "online")
    host_name = n.OR(P("[A-Za-z0-9-]{1,63}\\." + TLD, pre="A-Za-z0-9._/:-", post="A-Za-z0-9_@-")[0],
                     P("[A-Za-z0-9-]{1,63}\\.[A-Za-z0-9.-]{0,200}\\." + TLD, pre="A-Za-z0-9._/:-", post="A-Za-z0-9_@-")[0], force=True)
    host_name = n.AND(host_name, n.fill(host_name, n.AND(host_name, cls("."), alnum.at(-1), alnum.at(1)), 6))
    add_veto(NAMES + ("USERNAME", "ID", "SECRET", "PASS", "CITY", "IDCARD", "CARD", "TEL"), host_name)

    # ---------- URL credentials, DSN keys, order numbers, DD-Mon-YYYY dates ----------
    host = P("@[A-Za-z0-9-]{1,40}[A-Za-z0-9.-]{0,80}" + G("/", "\"", "'", " ", "\n", ":", ",", ";", "\t"))[0]
    host_at = n.AND(cls("@"), host, ~host.at(-1))
    pwc = cls(allb.replace(":", "").replace(" ", "").replace("\n", "").replace('"', "").replace("'", "").replace("/", ""))
    scheme_reach = n.spread_right(n.lit("://"), 72)
    pw = n.prop_left(n.AND(pwc, host_at.at(1), scheme_reach), pwc, 6)
    c.add("SECRET", n.AND(pw, n.fill(pw, n.AND(pw, cls(":").at(-1)), 6)), 0)
    dsn, _ = P("://[0-9a-f]{16,64}@")
    c.add("SECRET", n.AND(dsn, hexc), 0)
    add_veto(("EMAIL",), n.OR(dsn, n.spread_right(n.AND(cls("@"), dsn.at(-1)), 60), force=True))
    # an order number: an order part in the key ("order", "order_id", "/orders/") followed by a code with digits
    _, order_end = P(G("Order ", "order ", "Order #", "order #", "Order: ", "/orders/", "/order/", "order_id\": \"", "\"order\": \"", "order=",
                       "Order ID ", "Order no. ", "order no. ", "Order number ", "order number "))
    oval = n.prop_right(n.AND(n.OR(upper, digit, force=True), order_end.at(-1)), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"), 5)
    oval = n.AND(oval, n.fill(oval, n.run(digit, 3), 5))
    c.add("ID", oval, 0)
    add_veto(NAMES, oval)
    dmy, _ = P("[0-9]{1,2}-" + G("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec") + "-[0-9]{4}", pre="0-9A-Za-z", post="0-9")
    c.add("DATE", dmy, 0)

    # ---------- auth schemes and cue words: the token right after them is a secret, whatever its length or punctuation ----------
    # "Authorization: Bearer mF_9.B5f-4.1JqM", "Basic dXNlcjpwYXNz", "Bot MTk4...", "token mF_9.B5f-4.1JqM", "api key a1b2.c3d4"
    tok68 = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~+/=-")
    _, scheme_end = P(G("Bearer ", "bearer ", "BEARER ", "Basic ", "basic ", "Token ", "token ", "Bot ", "Negotiate ", "NTLM ", "MAC ", "Hawk ",
                        "api key ", "API key ", "API Key ", "apikey ", "api_key ", "access key ", "access token ", "secret ", "Secret ",
                        "password ", "Password ", "passcode ", "Passcode ", "token: ", "Token: "), pre="A-Za-z0-9_-")
    auth_tok = n.prop_right(n.AND(tok68, scheme_end.at(-1)), tok68, 7)
    # a token, not a word: it has a digit, or upper and lower case after its first letter, or token punctuation inside
    auth_tok = n.AND(auth_tok, n.fill(auth_tok, n.AND(auth_tok, n.OR(digit, n.AND(upper, auth_tok.at(-1), lower.at(-1)),
                                                                      n.AND(cls("._~+/=-"), alnum.at(-1), alnum.at(1)), force=True)), 6),
                     ~n.AND(cls(".,"), ~tok68.at(1)))                        # a sentence's full stop is not part of it
    auth_tok = n.AND(auth_tok, n.fill(auth_tok, n.AND(auth_tok, n.run(tok68, 6)), 6))      # at least 6 characters
    c.add("SECRET", auth_tok, 0)
    add_veto(("USERNAME", "ID", "EMAIL", "IP", "TEL", "GIVENNAME", "LASTNAME", "URL", "DATE"), auth_tok)
    add_veto(("PASS", "SECRET", "ID", "USERNAME"), dmy)             # a date is not a password or a handle

    # ---------- cookies: only the values of cookies whose names are not plain (attributes, theme, lang, consent ...) ----------
    # (no positive confinement: cookie values written as "session_cookie: abc", in prose or in a cookie file all count;
    #  the trim below removes the names, attributes and plain values instead)
    # the key of "key=value" is never a value (base64 padding "...M=" has no value after it)
    pk_span, pk_end = P(KEY + "=", pre="A-Za-z0-9_.=-")
    pk = n.fill(pk_span, n.AND(pk_end, alnum.at(1)), 6)
    add_veto(("USERNAME", "ID", "GIVENNAME", "LASTNAME", "CITY"), n.AND(pk, ~cls("=")))
    ck_key, _ = P(KEY + "=", pre="A-Za-z0-9_.-")
    ck_attr = n.OR(*[n.AND(n.lit(w, nocase=True), ~alnum.at(-1), ~alnum.at(len(w))) for w in ("HttpOnly", "Secure", "Partitioned", "SameSite", "Path", "Domain", "Expires", "Max-Age")], force=True)
    ck_attr = n.prop_right(ck_attr, cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-"), 4)
    # an attribute's value runs to the next ";" ("Expires=Wed, 21 Oct 2026 07:28:00 GMT")
    attr_val = n.prop_right(n.AND(cls(allb.replace(";", "").replace("\n", "")), cls("=").at(-1), ck_attr.at(-2)), cls(allb.replace(";", "").replace("\n", "")), 7)
    trim["COOKIE"] = n.OR(attr_val, veto.pop("COOKIE"), values(("plain",), without=("person", "secret")), plain_code, ck_key, ck_attr, cls(";"), force=True)
    # a device id named in prose ("X-Device-Id: 8f14...", "GAID 3840...", "device 9774d5...") is an online identifier
    hexish = n.OR(uuid_span, *[P("[0-9a-f]{%d}" % L_, pre="0-9a-zA-Z", post="0-9a-zA-Z")[0] for L_ in (16, 32)], force=True)
    c.add("USERNAME", n.AND(hexish, n.fill(hexish, n.AND(hexish, n.spread_right(cls_hit["device"], 24)), 6)), 0)
    add_veto(("ID",), n.AND(hexish, n.fill(hexish, n.AND(hexish, n.spread_right(cls_hit["device"], 24)), 6)))
    # a sentence-initial ordinary English word ("Call Priya", "Email Tom", "Ask Dana") is a verb, not part of the name
    # (unless the word is itself a known first name or surname: "Will", "Grace", "Mark")
    sent_start = n.AND(upper, ~alnum.at(-1), n.OR(cls("\n").at(-1), cls("\x00").at(-1),
                                                  n.AND(cls(" ").at(-1), cls(".!?").at(-2)), force=True))
    s_word = n.prop_right(sent_start, alpha, 4)
    plain_word = n.AND(s_word, ~n.fill(s_word, n.AND(s_word, ~c.english), 4),
                       ~n.fill(s_word, n.AND(s_word, n.OR(c.lex_given, c.lex_sur, *([c.lex_given_amb_any] if hasattr(c, "lex_given_amb_any") else []), force=True)), 4))
    add_veto(NAMES, plain_word)
    # a saint's name is part of a place name ("St. Anne's Chapel", "Saint Louis", "San Jose", "Santa Cruz")
    saint_name = n.prop_right(n.AND(upper, n.OR(*[n.lit(w).at(-len(w)) for w in ("St. ", "Saint ", "San ", "Santa ", "Sainte ", "Sankt ")], force=True),
                                    ~alnum.at(-len("St. ") - 1) if False else upper), alpha, 4)
    add_veto(NAMES, saint_name)
    # IBAN: country code, two check digits, then 11-30 letters and digits (grouped by spaces or not)
    iban, _ = P("[A-Z]{2}[0-9]{2}[A-Z0-9 ]{11,38}", pre="A-Za-z0-9", post="A-Za-z0-9")
    iban = n.AND(iban, ~n.AND(sp, ~iban.at(1)), n.fill(iban, n.AND(iban, sp, alnum.at(-1), alnum.at(1)) if False else n.AND(iban, digit), 6))
    iban = n.AND(iban, ~n.AND(cls(" "), cls(" ").at(1)))
    c.add("IBAN", iban, 0)
    add_veto(("ID", "TEL", "CARD", "SOCIALNUMBER", "PASSPORT", "IDCARD", "DRIVERLICENSE"), iban)
    # identifiers joined by "_" are one token: no word inside one is a name, place or organisation ("svc_mercury_backup")
    idc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")
    under_tok = n.fill(idc, n.AND(cls("_"), alnum.at(-1), alnum.at(1)), 5)
    # (lower-case words only: a capitalised name in a file name is still a name, "Resume_Priya_Sharma_2026.pdf")
    lw = n.prop_right(n.AND(lower, ~alpha.at(-1)), lower, 5)
    add_veto(NAMES + ("CITY", "STATE", "COUNTRY", "ORG", "STREET", "BUILDING", "HEALTH", "FINANCE", "TITLE", "SEX", "SCHOOL", "TIME", "DATE"), n.AND(under_tok, lw))
    # "an account named rclarke_root", "a user called jdoe42": a handle-shaped word after an account noun and a naming word
    _, acct_end = P(G("account named ", "account called ", "user named ", "user called ", "login named ", "admin named ",
                      "administrator named ", "account ", "user account ", "service account "), pre="A-Za-z")
    handle_c = cls("abcdefghijklmnopqrstuvwxyz0123456789_.-")
    acct = n.prop_right(n.AND(handle_c, lower, acct_end.at(-1)), handle_c, 5)
    acct = n.AND(acct, n.fill(acct, n.AND(acct, n.OR(cls("_"), digit, force=True)), 5), ~n.AND(cls(".-"), ~handle_c.at(1)))
    c.add("USERNAME", acct, 1)
    # a word of letters joined by hyphens is not a stated secret ("the password is URL-encoded", "is case-sensitive")
    hy_words, _ = P("[A-Za-z]{2,20}-[A-Za-z][A-Za-z-]{1,40}", pre="A-Za-z0-9_-", post="A-Za-z0-9_-")      # the whole token
    add_veto(("SECRET", "PASS"), n.AND(hy_words, ~c.literal_password))
    # an all-zero number is a placeholder, not an account ("0000-0000-0000-0000")
    zeros, _ = P("0000[0 -]{8,20}", pre="0-9", post="0-9")
    add_veto(("CARD", "ID", "IBAN", "TEL", "BANK"), n.AND(zeros, ~n.fill(zeros, n.AND(zeros, cls("123456789")), 5)))
    # ---------- shapes of code, colours and words that are never handles, passwords or ids ----------
    # a dotted lower-case token that continues as a code path ("com.example.parser", "java.lang.NullPointer", "buffer.len()")
    dot_tok = n.prop_right(n.AND(lower, ~cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.@-").at(-1)),
                           cls("abcdefghijklmnopqrstuvwxyz0123456789_."), 5)
    tok_end = n.AND(dot_tok, ~dot_tok.at(1))
    # it continues into code: ends at "." before a capital ("java.lang.NullPointer"), is called ("buffer.len("), or has 2+ dots
    cont = n.OR(n.AND(tok_end, cls("."), upper.at(1)), n.AND(tok_end, cls("(").at(1)),
                n.AND(dot_tok, cls("."), alnum.at(1), n.prop_right(n.AND(dot_tok, cls("."), alnum.at(1)), dot_tok, 5).at(-1)), force=True)   # dots within one token
    code_path = n.AND(dot_tok, n.fill(dot_tok, cont, 5), n.fill(dot_tok, n.AND(dot_tok, cls("."), alnum.at(1)), 5))
    add_veto(("USERNAME",) + NAMES, n.AND(code_path, ~c.url_person) if hasattr(c, "url_person") else code_path)
    # a colour "#ff5733", "#E91E63" and a number on its own are not handles
    colour = n.OR(P("#[0-9a-fA-F]{6}", pre="A-Za-z0-9&", post="A-Za-z0-9_")[0], P("#[0-9a-fA-F]{3}", pre="A-Za-z0-9&", post="A-Za-z0-9_")[0], force=True)
    colour = n.AND(colour, n.fill(colour, n.AND(colour, cls("abcdefABCDEF")), 4))
    add_veto(("USERNAME", "ID", "SECRET", "PASS", "TEL"), colour)
    tokch = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.@/-")
    num_only = n.prop_right(n.AND(digit, ~tokch.at(-1)), digit, 5)
    num_only = n.AND(num_only, ~n.fill(num_only, n.OR(n.AND(num_only, n.AND(tokch, ~cls(".")).at(1)), n.run(digit, 5), force=True), 5))     # a bare number of up to 4 digits
    add_veto(("USERNAME",), num_only)
    # a plain dictionary word is a handle only right after a handle cue ("username: sunshine", "@sunshine")
    eng_tok = n.prop_right(n.AND(lower, ~alnum.at(-1), ~cls("_.@-").at(-1)), lower, 5)
    eng_tok = n.AND(eng_tok, ~n.fill(eng_tok, n.AND(eng_tok, n.OR(cls("_.@-0123456789").at(1), force=True)), 5))
    eng_plain = n.AND(eng_tok, ~n.fill(eng_tok, n.AND(eng_tok, ~c.english), 5))
    h_cue = n.spread_right(n.OR(n.lit("user", nocase=True), n.lit("login", nocase=True), n.lit("handle", nocase=True), n.lit("nick", nocase=True),
                                n.lit("gamertag", nocase=True), n.lit("account", nocase=True), n.lit("profile", nocase=True), cls("@"), force=True), 24)
    add_veto(("USERNAME",), n.AND(eng_plain, ~n.fill(eng_plain, n.AND(eng_plain, h_cue), 5)))
    # yes / no / true / false / none / null are answers, not passwords
    yn = n.OR(*[n.AND(n.lit(w, nocase=True), ~tokch.at(-1), ~n.AND(tokch, ~cls(".")).at(len(w))) for w in ("yes", "no", "true", "false", "none", "null", "n/a", "on", "off")], force=True)
    add_veto(("PASS", "SECRET", "USERNAME"), n.prop_right(yn, alpha, 3))
    # product, part and model references ("Product code 861-413-4052", "HSN code 8517", "part number 7230693961")
    _, pcode_end = P(G("Product code ", "product code ", "HSN code ", "HSN ", "Model number ", "model number ", "Model no. ", "model no. ",
                       "Part number ", "part number ", "Part no. ", "part no. ", "Item code ", "item code ", "SKU ", "SKU: ", "Model: ",
                       "Product code: ", "EAN ", "UPC ", "ISBN ", "ASIN "), pre="A-Za-z")
    pcode = n.prop_right(n.AND(alnum, pcode_end.at(-1)), n.OR(alnum, n.AND(cls("-/."), alnum.at(1)), force=True), 5)
    add_veto(("TEL", "ID", "CARD", "SOCIALNUMBER", "IDCARD", "PASSPORT", "BANK", "IBAN"), pcode)
    k.NAMES = NAMES
    k.P = P
    k.add_veto = add_veto
    k.allb = allb
    k.alnum = alnum
    k.alpha = alpha
    k.cls = cls
    k.digit = digit
    k.hexc = hexc
    k.lower = lower
    k.n = n
    k.plain_tok = plain_tok
    k.sp = sp
    k.trim = trim
    k.upper = upper
    k.values = values
    k.veto = veto
    # Export plain interface metadata as negative evidence so the optional JS
    # pipeline cannot reintroduce a password merely from its field's name.
    metadata = n.AND(values(("secret",)), values(("keyname",)))
    textchar = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz \t.,!?'")
    k.secret_metadata = n.AND(metadata, ~n.fill(metadata, n.AND(metadata, ~textchar), 7))
