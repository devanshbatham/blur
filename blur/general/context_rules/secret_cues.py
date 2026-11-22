"""Credentials stated in text: command-line flags, cue words in many languages, PINs and one-time codes, backup and
recovery code lists, and the templates, encodings, paths and data URIs that are not credentials."""
from .words import *  # noqa: F401,F403  (word-part vocabulary and shared imports)


def stated_credentials(c, k):
    NAMES = k.NAMES
    P = k.P
    add_veto = k.add_veto
    allb = k.allb
    alnum = k.alnum
    alpha = k.alpha
    cls = k.cls
    ctx_not = k.ctx_not
    digit = k.digit
    lower = k.lower
    n = k.n
    sp = k.sp
    upper = k.upper
    values = k.values
    wsx = k.wsx
    # ================= secrets: containers and cues =================
    vchar = cls(allb.replace(" ", "").replace("\n", "").replace("\t", "").replace('"', "").replace("'", "").replace("`", "").replace("&", "").replace(";", ""))
    def token_after(end_sig, min_len=6, need_strong=True):
        v = n.prop_right(n.AND(vchar, end_sig.at(-1)), vchar, 6)
        v = n.AND(v, ~n.AND(cls(".,:)"), n.OR(wsx.at(1), force=True)))
        if need_strong:
            v = n.AND(v, n.fill(v, n.AND(v, n.OR(digit, cls("!@#$%^&*~+=?/_-"), n.AND(upper, lower.at(-1)), force=True)), 6))
        return n.AND(v, n.fill(v, n.AND(v, n.run(vchar, min_len)), 6))
    # (14) command-line flags that carry a secret: --password X, --password=X, --api-token=X, --secret X, -p'X', -pX after -u
    flag_end = P("--[a-z-]{0,20}" + G("password", "passwd", "token", "secret", "pass", "pwd", "api-key", "apikey", "access-key", "auth") + "[a-z-]{0,12}" + G("=", " "),
                 pre="A-Za-z0-9_-")[1]
    flag_v = token_after(flag_end, 4)
    _, pshort = P(G(" -p", " -P", " --pass=") , post=None)
    after_u = n.spread_right(n.OR(n.lit(" -u "), n.lit(" -u"), n.lit(" --user "), n.lit(" --username "), n.lit(" -U "), force=True), 60)
    quote = cls("'" + '"')
    p_attached = n.OR(token_after(n.AND(pshort, after_u), 4),
                      token_after(n.AND(quote, n.AND(pshort, after_u).at(-1)), 4), force=True)      # -p'secret' 
    p_spaced = token_after(n.AND(n.lit(" -p ").at(-3), after_u) if False else n.AND(n.lit("-p ").at(-2), after_u, sp), 4)
    for v in (flag_v, p_attached, p_spaced):
        c.add("SECRET", v, 0)
        add_veto(NAMES + ("USERNAME", "ID", "URL", "CITY"), v)
    # (15) cue words that state a secret, in several languages ("secret is", "token is", "密码是", "パスワード:", "비밀번호:", "пароль:")
    cues = ["secret is ", "Secret is ", "secret: ", "token is ", "token: ", "api key is ", "seed is ", "2FA secret is ",
            "TOTP secret ", "totp secret ", "recovery key is ", "license key is ", "licence key is ", "access key is ", "signing key is "]
    for w in ("パスワード: ", "パスワード：", "パスワードは", "密码是 ", "密码是", "密码: ", "密码：", "口令: ", "비밀번호: ", "비밀번호는 ", "암호: ",
              "пароль: ", "Пароль: ", "пароль - ", "contraseña: ", "Contraseña: ", "contraseña es ", "senha: ", "Senha: ", "senha é ",
              "mot de passe : ", "mot de passe: ", "Mot de passe : ", "Passwort: ", "passwort: ", "Kennwort: ", "wachtwoord: ", "Wachtwoord: ",
              "parola: ", "şifre: ", "Şifre: ", "hasło: ", "Hasło: ", "lösenord: ", "kata sandi: ", "mật khẩu: "):
        cues.append(w)                        # (G converts to byte view itself)
    _, cue_end = P(G(*cues), pre="A-Za-z")
    # "key is" names a credential unless a qualifier says what kind of key ("cache key is", "primary key is", "the key is C minor")
    quals = ("cache", "sort", "primary", "foreign", "partition", "composite", "lookup", "hash", "map", "dictionary", "row", "index",
             "join", "music", "musical", "shard", "routing", "object", "storage", "s3", "redis", "bucket", "unique", "natural", "surrogate")
    qual_before = n.OR(*[n.AND(n.lit(q + " ", nocase=True).at(-(len(q) + 1)), ~alnum.at(-(len(q) + 2))) for q in quals], force=True)
    _, key_end = P("key is ", pre="A-Za-z", start_terms=[~qual_before])
    cue_end = n.OR(cue_end, key_end, force=True)
    cue_v = token_after(cue_end, 6)
    # short password words, with words in between ("my pw for the admin panel is hunter2!!"); the value must look like one
    pw_w = n.OR(*[n.AND(n.lit(w, nocase=True), ~alnum.at(-1), ~alnum.at(len(w))) for w in ("pw", "pwd", "passwd", "pword")], force=True)
    nonl_ = cls(allb.replace("\n", "").replace(".", "").replace("!", "").replace("?", ""))
    pw_near = n.AND(n.spread_right(pw_w, 40), n.prop_right(pw_w, nonl_, 5))
    pw_is = n.AND(P(G(" is ", ": ", " = "))[1], pw_near.at(-3))
    cue_v = n.OR(cue_v, token_after(pw_is, 6), token_after(P(G("vault login ", "vault login -token=", "gh auth login --with-token "),
                                                                        pre="A-Za-z")[1], 16), force=True)
    c.add("SECRET", cue_v, 0)
    add_veto(NAMES + ("USERNAME", "ID", "CITY", "DATE", "TEL"), cue_v)
    # a worked encoding or digest is content, not a credential: "Base64 of 'hello' is aGVsbG8=", "the SHA-256 of the file is 9f86..."
    enc_w = n.OR(*[n.AND(n.lit(w, nocase=True), ~alnum.at(-1)) for w in ("base64 of", "base64-encoded", "base64 encoding of", "encodes to",
                   "encoded as", "hash of", "sha-256 of", "sha256 of", "sha-1 of", "sha1 of", "md5 of", "checksum", "digest", "hex of",
                   "fingerprint of", "the hash is", "integrity")], force=True)
    enc_near = n.AND(n.spread_right(enc_w, 40), n.prop_right(enc_w, nonl_, 5))
    enc_is = n.AND(P(G(" is ", ": ", " = ", " -> ", " => "))[1], enc_near.at(-3))
    enc_v = n.prop_right(n.AND(vchar, enc_is.at(-1)), vchar, 7)
    add_veto(("SECRET", "PASS", "ID", "USERNAME"), enc_v)
    # a lower-case filesystem path is a location, not a password ("pwd is /home/ops/app", "key: ~/.ssh/id_ed25519")
    pathc = cls("abcdefghijklmnopqrstuvwxyz0123456789._-/~")
    tokbound = n.OR(cls(" \t\n\"'`(=,;"), cls("\x00"), force=True)
    p0 = n.AND(n.OR(cls("/"), n.AND(cls("~"), cls("/").at(1)), force=True), tokbound.at(-1))      # a whole token that starts with / or ~/
    ptok = n.prop_right(p0, pathc, 7)
    p_end_ok = n.AND(ptok, ~ptok.at(1), n.OR(tokbound.at(1), n.AND(cls(".,;:)"), tokbound.at(2) if False else ~alnum.at(2)).at(1) if False else
                                         n.OR(tokbound, cls(".,;:)!?")).at(1), force=True))
    path_v = n.AND(ptok, n.fill(ptok, p_end_ok, 7), n.fill(ptok, n.AND(ptok, cls("/"), alpha.at(1)), 7))
    add_veto(("SECRET", "PASS"), path_v)
    not_secret_ctx = n.OR(path_v, enc_v, force=True)
    # (16) PINs, one-time codes and backup codes after their cue ("PIN is 0429", "OTP 482913", "door code is 4471",
    #      "backup codes are 8812-4471 and 9903-1186")
    _, pin_end = P(G("PIN is ", "pin is ", "PIN: ", "PIN ", "OTP ", "OTP is ", "otp is ", "OTP: ", "code is ", "passcode is ", "door code is ",
                     "security code is ", "verification code is ", "one-time code ", "CVV ", "CVV: ", "CVV is ",
                     "暗証番号「", "暗証番号は", "暗証番号：", "暗証番号: ", "暗証番号「#", "暗証番号は#", "认证码", "验证码：", "验证码是", "비밀번호는 ", "인증번호 "), pre="A-Za-z")
    pin_v = n.prop_right(n.AND(digit, pin_end.at(-1)), n.OR(digit, n.AND(cls("- "), digit.at(-1), digit.at(1)), force=True), 4)   # "12-34-56"
    pin_v = n.AND(pin_v, n.fill(pin_v, n.run(pin_v, 4), 4), ~n.fill(pin_v, n.AND(pin_v, ~pin_v.at(1), n.OR(cls("0123456789.-/:,"), force=True).at(1), digit.at(2)), 4))
    c.add("SECRET", pin_v, 0)
    _, bc_end = P(G("backup codes are ", "backup codes: ", "backup code: ", "backup code is ", "recovery codes are ", "recovery codes: ",
                    "recovery code is ", "recovery code: ", "codes are ", "Backup codes: ", "Recovery codes: ",
                    "backup codes:\n", "Backup codes:\n", "recovery codes:\n", "Recovery codes:\n", "BACKUP CODES:\n", "RECOVERY CODES:\n"), pre="A-Za-z")
    codec = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-")
    bc_region = n.prop_right(n.AND(codec, bc_end.at(-1)), n.OR(codec, n.AND(cls(", "), codec.at(1) if False else n.OR(codec.at(1), sp.at(1), force=True)),
                                                             n.lit(" and ").at(0) if False else n.OR(cls(", "), force=True), n.AND(cls("\n"), codec.at(1), codec.at(-1)), force=True), 6)
    bc_tok = n.AND(bc_region, codec, n.fill(n.AND(bc_region, codec) if False else codec, n.AND(bc_region, codec, digit), 4))
    bc_tok = n.AND(bc_tok, ~n.fill(codec, n.AND(codec, n.lit("and")), 3))
    c.add("SECRET", n.AND(bc_tok, n.fill(codec, n.AND(bc_tok, n.run(codec, 4)), 4)), 0)
    # (17) template placeholders are not values ("${DB_PASSWORD}", "{{ secrets.API_KEY }}", "%(password)s", "<redacted>", "$API_KEY")
    tmpl = n.OR(P("\\$\\{[A-Za-z0-9_.:-]{1,60}\\}")[0], P("\\{\\{[ A-Za-z0-9_.|()'\"-]{1,80}\\}\\}")[0], P("%\\([A-Za-z0-9_]{1,40}\\)[sd]")[0],
                P("<[a-z_ -]{2,40}>")[0], P("<[A-Z_ -]{2,40}>")[0], P("\\$[A-Z][A-Z0-9_]{2,40}", post="A-Za-z0-9_")[0], force=True)
    add_veto(("SECRET", "PASS", "COOKIE", "ID"), tmpl)
    # the payload of a data: URI is content (an image, a font), never a credential
    _, duri_end = P("data:[a-z]{2,12}/[A-Za-z0-9.+-]{2,40};base64,", pre="A-Za-z0-9")
    b64c = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    duri = n.prop_right(n.AND(b64c, duri_end.at(-1)), b64c, 9)
    add_veto(("SECRET", "PASS", "COOKIE", "ID", "USERNAME"), duri)
    setting = values(("setting",), without=("person", "device"))                # "TOKEN_TTL=3600", "PASSWORD_MIN_LENGTH=12"
    add_veto(("SECRET", "PASS", "ID", "IDCARD", "TEL", "CARD", "SOCIALNUMBER"), setting)     # "max_tokens: 4096000000"
    # a name given to a device or network is not a secret ("the device named SoundBar-7764", "a network called HomeWiFi-5G")
    _, dn_end = P(G("device named ", "device called ", "speaker named ", "printer named ", "network named ", "network called ", "SSID named ",
                    "headphones named ", "TV named ", "phone named ", "laptop named ", "router named "), pre="A-Za-z")
    dn_v = n.prop_right(n.AND(alnum, dn_end.at(-1)), n.OR(alnum, n.AND(cls("-_."), alnum.at(1)), force=True), 5)
    add_veto(("SECRET", "PASS"), dn_v)
    ctx_not["SECRET"] = n.OR(ctx_not["SECRET"], tmpl, setting, dn_v, force=True)
    # the next query parameter is never part of a value: cut claims at "&key=" ("abc123&mode=fast")
    nxt_param = n.AND(cls("&"), n.prop_left(n.AND(cls("="), n.OR(alnum, cls("_.-"), force=True).at(-1)), n.OR(alnum, cls("_.-[]"), force=True), 5).at(1))
    c.pre_cut_mark = nxt_param
    c.pre_cut = ("SECRET", "PASS", "COOKIE", "ID", "USERNAME")
    k.duri = duri
    k.not_secret_ctx = not_secret_ctx
    k.w = w


def code_and_interface_text(c, k):
    """A credential is a value, not code and not interface text. Under a password-like name in source code the value is
    often an expression ("password = algo.p(x)", "passwordToCipherKey(password []byte"); in a translation file it is a
    label ("Current Password", "Парола"). Both are vetoed as secrets; a lower-case passphrase is not affected."""
    n, cls, add_veto = k.n, k.cls, k.add_veto
    identc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$")
    upper, lower = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), cls("abcdefghijklmnopqrstuvwxyz")
    high = cls("".join(chr(i) for i in range(0x80, 0x100)))
    call = n.AND(cls("("), identc.at(-1))                                          # "name(" : a function call
    pairs = n.OR(n.lit("()"), n.lit("[]"), n.lit("{}"), force=True)               # empty brackets: types and calls
    code = n.OR(call, pairs, force=True)
    # words of a label: a space before a capitalised word ("Current Password") or between non-Latin words
    label_space = n.OR(n.AND(cls(" "), upper.at(1), lower.at(2), lower.at(-1)), n.AND(cls(" "), n.OR(high.at(-1), high.at(1), force=True)),
                       force=True)
    add_veto(("SECRET", "PASS"), n.AND(n.OR(code, label_space, force=True), ~c.literal_password))


def names_in_code(c, k):
    """A secret is random; a name in code is made of words. Split a value the way programmers write names (at case
    changes, "_", ".", "-" and digits), look each part up in a word tree, and when dictionary words cover more than
    half of the value it is an identifier ("d3_bisector", "userPasswordHash", "ECC_pub_key"), not a credential.
    Measured on CredData: this removes about 10,000 false positives for 14 lost true lines. A passphrase, or a value
    with password symbols ("Crimson#Valley2026"), is never judged this way. Code syntax that is never a secret is
    vetoed too: pointers and references ("*cfg.Token", "&opts"), member arrows ("pop3->passwd"), generics ("<T>")."""
    import os
    from ..common import DATA_DIR
    n, cls, add_veto = k.n, k.cls, k.add_veto
    lower, upper = cls("abcdefghijklmnopqrstuvwxyz"), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    letter = n.OR(lower, upper, force=True)
    tokc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")
    # where a word part starts: after a non-letter, at a lower-to-upper step ("userPassword"), or at the last capital of
    # a capital run before lower case ("XMLHttp")
    seg0 = n.OR(n.AND(letter, ~letter.at(-1)), n.AND(upper, lower.at(-1)), n.AND(upper, upper.at(-1), lower.at(1)), force=True)
    seg_end = n.AND(letter, ~lower.at(1), ~n.AND(upper, upper.at(1)))
    ci = {ch: cls(ch + ch.upper()) for ch in "abcdefghijklmnopqrstuvwxyz"}
    words = sorted({w.lower() for w in open(os.path.join(DATA_DIR, "words20.txt")).read().split()
                    if w.isascii() and w.isalpha() and len(w) >= 3})
    node = {ch: n.AND(ci[ch], seg0) for ch in ci}
    ends_by_len = {}
    for w in words:
        for i in range(2, len(w) + 1):
            if w[:i] not in node:
                node[w[:i]] = n.AND(node[w[:i - 1]].at(-1), ci[w[i - 1]])
        ends_by_len.setdefault(len(w), []).append(node[w])
    covered = n.OR(*[n.spread_left(n.AND(n.OR(*[x for x in ws[j:j + 256]], force=True), seg_end), L)
                     for L, ws in sorted(ends_by_len.items()) for j in range(0, len(ws), 256)], force=True)
    covered = n.AND(covered, tokc)
    uncovered = n.AND(tokc, ~covered)
    # at the end of a token, compare covered and uncovered characters over the token (up to 48 characters back)
    tok_end = n.AND(tokc, ~tokc.at(1))
    pos, neg = [], []
    for j in range(48):
        same = n.run(tokc, j + 1).at(-j)                       # characters j back are still in this token
        pos.append(n.AND(covered.at(-j), same, tok_end))
        neg.append(n.AND(uncovered.at(-j), same, tok_end))
    wordy_end = n.AND(n.vote(pos, neg, need=1), tok_end)
    tok = n.prop_right(n.AND(tokc, ~tokc.at(-1)), tokc, 6)
    wordy = n.fill(tok, wordy_end, 6)
    # not a password with symbols around it, not part of a passphrase
    sym = cls("!#$%^&*+=@~?|")
    near_sym = n.fill(tok, n.OR(n.AND(tok, ~tok.at(-1), sym.at(-1)), n.AND(tok, ~tok.at(1), sym.at(1)), force=True), 6)
    wordy = n.AND(wordy, ~near_sym, *([~c.phrase_secret] if hasattr(c, "phrase_secret") else []))
    # only a name with a programmer's structure ("_", ".", or a camelCase step), shorter than 40 characters, with no
    # hyphen or space between words: "correct-horse-battery-staple" is a passphrase, a key body is long base64
    structured = n.fill(tok, n.AND(tok, n.OR(cls("_."), n.AND(upper, lower.at(-1)), force=True), tok.at(-1), tok.at(1)), 6)
    hyphened = n.fill(tok, n.AND(cls("-"), letter.at(-1), letter.at(1)), 6)
    spaced = n.fill(tok, n.OR(n.AND(tok, ~tok.at(-1), cls(" ").at(-1), letter.at(-2)),
                              n.AND(tok, ~tok.at(1), cls(" ").at(1), letter.at(2)), force=True), 6)
    long_tok = n.fill(tok, n.run(tokc, 40), 6)
    in_path = n.fill(tok, n.OR(n.AND(tok, ~tok.at(-1), cls("/").at(-1)), n.AND(tok, ~tok.at(1), cls("/").at(1)), force=True), 6)
    wordy = n.AND(wordy, structured, ~hyphened, ~spaced, ~long_tok, ~in_path)        # (a path segment is not a code name)
    # a quoted value right under a password key is a password, whatever its words ("password = \"MySecretPass\"")
    pw_quoted = n.AND(k.values(("pw",), without=("keyname", "plain")), n.fill(tok, n.AND(tok, ~tok.at(-1), cls("\"'`").at(-1)), 6))
    k.pw_quoted = pw_quoted
    wordy = n.AND(wordy, ~n.fill(tok, pw_quoted, 6))
    # code syntax: a pointer or reference ("*cfg", "&opts"), a member arrow, a scope, generics
    ident = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
    code = n.OR(n.lit("->"), n.lit("::"), n.AND(cls("<"), ident.at(-1)), force=True)
    add_veto(("SECRET", "PASS"), n.AND(n.OR(wordy, code, force=True), ~c.literal_password))


def code_shapes(c, k):
    """Shapes that only code has (measured on CredData: about 3,600 false positives removed for 27 true lines):
    - a dotted reference: identifier segments joined by dots, each letters with at most a few trailing digits
      ("oauth2.Token", "cfg.AccessToken", "client.secret"), up to 40 characters; a random token has letters right
      after digits or digit-led segments ("a1b2.c3d4", "mF_9.B5f-4.1JqM") and is not affected;
    - a short snake-case name of three or more segments, none longer than ten ("ECC_pub_k256v1_DER", "TF_Complex64");
      a key such as "sk_live_..." has one long random segment and is not affected;
    - a pointer, reference or negation in front of a name ("*cfg.Token", "&opts", "!isValid")."""
    n, cls, add_veto = k.n, k.cls, k.add_veto
    letter = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    digit = cls("0123456789")
    identc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$")
    refc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$.")
    # a token of identifier characters and dots
    rtok = n.prop_right(n.AND(refc, ~refc.at(-1)), refc, 6)
    seg_bad = n.OR(n.AND(digit, letter.at(1)),                                 # a letter right after a digit
                   n.AND(digit, n.OR(cls(".").at(-1), force=True)),            # a segment that starts with a digit
                   n.AND(digit, ~refc.at(-1)),
                   n.run(digit, 4), n.lit(".."), force=True)
    has_dot = n.AND(cls("."), identc.at(-1), letter.at(1))
    dotted = n.AND(rtok, n.fill(rtok, has_dot, 6), n.fill(rtok, n.run(letter, 3), 6), ~n.fill(rtok, seg_bad, 6),
                   ~n.fill(rtok, n.run(refc, 41), 6))
    # bounded by code, not by more token characters ("-", "/", "+", "=" continue a random token)
    cont_before, cont_after = cls("-/+~%"), cls("-/+=~%:@")                  # ("=" after: base64 padding; ":" "@": user:pass, user@host)
    bounded = lambda t: ~n.fill(t, n.OR(n.AND(t, ~t.at(1), cont_after.at(1)), n.AND(t, ~t.at(-1), cont_before.at(-1)), force=True), 6)
    dotted = n.AND(dotted, bounded(rtok))
    # a short snake-case name
    alnum = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
    utokc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")
    utok = n.prop_right(n.AND(utokc, ~utokc.at(-1)), utokc, 6)
    under = n.AND(cls("_"), alnum.at(-1), alnum.at(1))
    seg_after_under = n.prop_right(n.AND(alnum, under.at(-1)), alnum, 4)
    second_under = n.AND(under, seg_after_under.at(-1))                      # two underscores inside one token
    lower, upper = cls("abcdefghijklmnopqrstuvwxyz"), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    flip = n.AND(upper, lower.at(-1))                                        # "AbC": a case flip inside a segment is random
    word3 = n.OR(n.run(lower, 3), n.run(upper, 3), force=True)               # a word fragment ("ECC", "pub", "omplex")
    snake = n.AND(utok, n.fill(utok, second_under, 6), ~n.fill(utok, n.run(alnum, 11), 6), n.fill(utok, word3, 6),
                  ~n.fill(utok, flip, 6))
    snake = n.AND(snake, bounded(utok))
    # a pointer or reference to a dotted name ("*oauth2.Token", "&cfg.Secret"); a password may start with "*" or "!"
    lead = n.AND(cls("*&"), letter.at(1), ~alnum.at(-1), dotted.at(1))
    pointed = dotted
    sym_before, sym_after = cls("!#$%^&*+@~?|"), cls("!#$%^&*+=@~?|")          # ("key=value": "=" before a value separates)
    near_sym = lambda t: n.fill(t, n.OR(n.AND(t, ~t.at(-1), sym_before.at(-1), ~lead.at(-1)), n.AND(t, ~t.at(1), sym_after.at(1)), force=True), 6)
    add_veto(("SECRET", "PASS"), n.AND(n.OR(n.AND(dotted, ~near_sym(dotted)), n.AND(snake, ~near_sym(snake)), lead, force=True),
                                     ~c.literal_password))


def code_names_and_placeholders(c, k):
    """More shapes only code has, and values that only stand in for a credential (measured on CredData: about 3,900
    false positives removed for 31 true lines):
    - a camelCase or PascalCase name made of word-like parts ("lower48Point", "someVariable", "ContextAmd64"): every
      capital starts a lower-case run of two or more, digits only end a part, and there are no runs of capitals;
    - a name that mixes snake_case and kebab-case ("ECC_pk_brainpool-p256-sha256"), with short parts;
    - a credential word standing in for the value ("pass", "password", "secret", "changeme", "foobar")."""
    n, cls, add_veto = k.n, k.cls, k.add_veto
    lower, upper = cls("abcdefghijklmnopqrstuvwxyz"), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    digit = cls("0123456789")
    alnum = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
    sym_before, sym_after = cls("!#$%^&*+@~?|"), cls("!#$%^&*+=@~?|")
    cont = cls("-/+~%_.:@")
    def whole(tokc):                                       # a token of tokc, not continued by other token characters
        t = n.prop_right(n.AND(tokc, ~tokc.at(-1)), tokc, 6)
        edge = n.OR(n.AND(t, ~t.at(1), n.OR(cont, sym_after, force=True).at(1)),
                    n.AND(t, ~t.at(-1), n.OR(cont, sym_before, force=True).at(-1)), force=True)
        return t, n.fill(t, edge, 6)
    # camelCase / PascalCase
    ctok, c_edge = whole(alnum)
    start = n.AND(ctok, ~ctok.at(-1))
    bad = n.OR(n.AND(upper, upper.at(1)),                                   # a run of capitals
               n.AND(upper, ~n.AND(lower.at(1), lower.at(2))),               # a capital not starting a word
               n.AND(digit, lower.at(1)),                                    # digits only end a part
               n.run(digit, 4),
               n.AND(start, lower, ~n.run(lower, 3)), n.AND(start, digit), force=True)
    step = n.AND(upper, ~start)                                              # a second part
    quoted = n.fill(ctok, n.AND(start, cls("\"'`").at(-1)), 6)                  # a quoted string is a value, not a name
    camel = n.AND(ctok, n.fill(ctok, step, 6), ~n.fill(ctok, bad, 6), ~c_edge, ~quoted)
    # snake_case mixed with kebab-case
    mtokc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
    mtok, m_edge = whole(mtokc)
    sep = n.AND(cls("_-"), alnum.at(-1), alnum.at(1))
    has_u = n.fill(mtok, n.AND(cls("_"), sep), 6)
    has_h = n.fill(mtok, n.AND(cls("-"), sep), 6)
    word3 = n.OR(n.run(lower, 3), n.run(upper, 3), force=True)
    mixed = n.AND(mtok, has_u, has_h, ~n.fill(mtok, n.run(alnum, 11), 6), n.fill(mtok, word3, 6), ~m_edge)
    # a credential word as the value
    words = ("pass", "password", "passwd", "pwd", "secret", "token", "user", "username", "changeme", "example", "xxx", "xxxx",
             "xxxxxx", "dummy", "sample", "placeholder", "yourpassword", "mypassword", "foobar", "foo", "bar", "test", "testing")
    # (the whole value: only a quote, space, "=", ":" or bracket before it, a quote, space, comma or bracket after it)
    opener = n.OR(cls(" \t\"'`=:([{,"), cls("\n"), cls("\x00"), force=True)
    closer = n.OR(cls(" \t\"'`,;)]}\n\r@"), cls("\x00"), force=True)
    ph = n.OR(*[n.AND(n.lit(w, nocase=True), opener.at(-1), closer.at(len(w))) for w in words], force=True)
    ph = n.prop_right(ph, alnum, 4)
    add_veto(("SECRET", "PASS"), n.OR(n.AND(n.OR(camel, mixed, force=True), ~c.literal_password), ph, force=True))


def references_and_labels(c, k):
    """The value is not a literal (measured on CredData's "password" false positives, which reviewers marked false):
    - a variable reference: "$password", "${pass}" is a template, "$Secret" in PowerShell, "%PASSWORD%";
    - an unquoted name followed by code punctuation ("{user: usr, password: pwd}", "Password: pass},"): a variable,
      not a literal (a literal in code is quoted; in YAML the value ends the line);
    - interface text: a quoted value that starts with a capital and goes on with more words ("Şifre katılımcı ...")."""
    n, cls, add_veto = k.n, k.cls, k.add_veto
    letter = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    identc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")
    upper = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    high = cls("".join(chr(i) for i in range(0x80, 0x100)))
    # $name, %NAME%
    # (the "$" starts the value, and no password symbol follows the name: "Kube$ecret99" and "$ecret99!" are passwords)
    sym = cls("!#%^&*+=@~?|")
    vstart = n.OR(cls(" \t\"'`=:(,[{"), cls("\n"), cls("\x00"), force=True)
    dname = n.prop_right(n.AND(identc, cls("$").at(-1), letter, vstart.at(-2)), identc, 5)
    dname = n.AND(dname, ~n.fill(dname, n.AND(dname, ~dname.at(1), sym.at(1)), 5))
    dollar = n.OR(dname, n.AND(cls("$"), dname.at(1)), force=True)
    # %NAME% (a Windows variable starts with a letter; "%2F" is URL encoding)
    upname = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")                  # (a Windows variable is an upper-case name)
    pname = n.prop_right(n.AND(upper, cls("%").at(-1), upname.at(1), upname.at(2)), upname, 5)
    percent = n.AND(pname, n.fill(pname, n.AND(pname, ~pname.at(1), cls("%").at(1)), 5), ~n.fill(pname, cls("0123456789").at(0) if False else n.AND(pname, cls("0123456789"), cls("%").at(-1)), 5))
    # an unquoted identifier followed by "," "}" ")" after ": " or "= "
    itok = n.prop_right(n.AND(identc, ~identc.at(-1), n.OR(cls(" ").at(-1), force=True), cls(":=").at(-2)), identc, 5)
    var_ref = n.AND(itok, n.fill(itok, n.AND(itok, ~itok.at(1), cls(",})").at(1)), 5))
    # (inside code: an open "{" or "(" earlier on the line; "Lotte: Ria2024tuin, netwerk ..." is a chat line)
    nonl = cls("".join(chr(i) for i in range(1, 256) if chr(i) != "\n"))
    in_code = n.AND(n.spread_right(cls("{("), 80), n.prop_right(cls("{("), nonl, 6))
    var_ref = n.AND(var_ref, n.fill(itok, n.AND(itok, in_code), 5))
    # interface text: a quoted capitalised word followed by a space and another word
    # (only as the value of a key in machine text: "key": "Label text", key = 'Label text'; a passphrase quoted in prose
    # is still a passphrase)
    kv_quote = n.AND(cls("\"'").at(-1), n.OR(cls(":=").at(-2), n.AND(cls(" ").at(-2), cls(":=").at(-3)), force=True))
    wtok = n.prop_right(n.AND(n.OR(upper, high, force=True), kv_quote), n.OR(letter, high, force=True), 5)
    label = n.AND(wtok, n.fill(wtok, n.AND(wtok, ~wtok.at(1), cls(" ").at(1), n.OR(letter, high, force=True).at(2)), 5))
    label = n.AND(label, ~n.fill(wtok, k.pw_quoted, 5))                     # a quoted value under a password key is a password
    add_veto(("SECRET", "PASS"), n.OR(dollar, percent, var_ref, label, force=True))
