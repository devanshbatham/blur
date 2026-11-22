"""The weight-space program. Every detector below is written as boolean / integer circuits over
the byte stream using only the DSL's ternary-convolution neurons."""
from __future__ import annotations

import string

from ..dsl import Net, Sig
from ..patterns import parse
from .table import TOKENS

D, UP, LO = string.digits, string.ascii_uppercase, string.ascii_lowercase
AL, AN = UP + LO, UP + LO + D
HEX = D + "abcdefABCDEF"
PRINT = "".join(chr(c) for c in range(33, 127))


def minus(chars: str, drop: str) -> str:
    return "".join(c for c in chars if c not in drop)


# --------------------------------------------------------------------------- secrets
# Placeholder fragments that never occur in a real token body: a provider-shaped string that
# contains one of these inside its fixed part is documentation, not a credential.
TOKEN_PLACEHOLDERS = ["xxxx", "example", "your"]


def provider_tokens(n: Net) -> None:
    """Known token formats: prefix template AND exact-length body run AND boundaries, vetoed
    when a placeholder fragment (xxxx / example / your) sits inside the fixed part."""
    an = n.cls(AN)
    fake = n.OR(*[n.lit(p, nocase=True) for p in TOKEN_PLACEHOLDERS], force=True)
    by_len: dict[int, list[Sig]] = {}
    by_tail: dict[str, list[tuple[Sig, int]]] = {}
    for kind, pats, tail, endb in TOKENS:
        anchors = []
        for pat in pats:
            parts = parse(pat)
            sig, L = n.seq(parts)
            terms = [sig, ~an.at(-1), ~n.spread_left(fake, L - 3)]
            if endb:
                terms.append(~n.cls(parse(endb)[0][0]).at(L))
            a = n.AND(*terms)
            anchors.append(a)
            by_len.setdefault(L, []).append(a)
            if tail:
                by_tail.setdefault(tail, []).append((a, L))
        n.out("kind:" + kind, n.OR(*anchors))
    for L, anchors in by_len.items():
        n.out("SECRET", n.spread_right(n.OR(*anchors, force=True), L))
    for tail, items in by_tail.items():
        seeds = {}
        for a, L in items:
            seeds.setdefault(L, []).append(a)
        seed = n.OR(*[n.spread_right(n.OR(*a, force=True), L) for L, a in seeds.items()], force=True)
        n.out("SECRET", n.prop_right(seed, n.cls(parse(tail)[0][0]), 8))


# Round 6 switches (ablations: run_ours.py --set EXAMPLE_VOTES=[...] / --set VALUE_RULES=[...]).
# EXAMPLE_VOTES: context evidence that a value is a test fixture or documentation (see `example_evidence`).
# VALUE_RULES: value-side rules added in round 6, each described where it is used.
EXAMPLE_VOTES = ["word", "testcode", "comment", "block", "uuid"]
VALUE_RULES = ["chunks", "hashlabel", "version", "jwtsample", "b64lower", "compared", "codearg",
               "scope", "redacted", "pathvalue", "userinfo",   # round 6b, after held-out 4
               "crypt", "leet", "trivialbasic", "blankstart", "vdigit"]   # round 6b, from dev negatives 3
# base64url of `{"sub":"1234567890"` + the first bits of the closing quote: the payload of a JWT whose
# subject is the ten digits in order, i.e. the sequential-digits placeholder inside the encoding.
JWT_SAMPLE_PAYLOAD = "eyJzdWIiOiIxMjM0NTY3ODkwI"


def jwt(n: Net) -> None:
    """eyJ<b64url>.eyJ<b64url>.<b64url> - three linked variable-length segments. Not reported when
    the payload opens with `{"sub":"1234567890"` (a sequential-digits subject: the documentation JWT)."""
    b = n.cls(AN + "-_")
    dot = n.cls(".")
    head = n.AND(n.lit("eyJ"), ~n.cls(AN).at(-1), n.run(b, 10))
    seg1 = n.prop_right(head, b, 9)
    sample = [~n.lit(JWT_SAMPLE_PAYLOAD).at(1)] if "jwtsample" in VALUE_RULES else []
    dot1 = n.AND(dot, seg1.at(-1), n.lit("eyJ").at(1), n.run(b, 10).at(1), *sample)
    seg2 = n.prop_right(dot1, b, 10)
    dot2 = n.AND(dot, seg2.at(-1), ~dot1, n.run(b, 10).at(1))
    whole = n.cls(AN + "-_.")
    n.out("SECRET", n.OR(n.prop_left(dot2, whole, 11), n.prop_right(dot2, b, 9)))
    n.out("kind:jwt", dot2)


B64 = AN + "+/="
KEY_BODY = AN + "+/=\r\n\\-"


def private_key(n: Net) -> None:
    """-----BEGIN [...] PRIVATE KEY[ BLOCK]----- header, then the base64 body up to the END line.

    The body may be indented (YAML block scalars), JSON-escaped (\\n), split into quoted string
    literals joined by + or , (keys pasted into source code) or preceded by RFC 1421 header lines
    (Proc-Type / DEK-Info). A header with no base64 after it (documentation that
    shows `-----BEGIN PRIVATE KEY-----` and then `...`) is not reported."""
    begin = n.lit("-----BEGIN ")
    label = n.prop_right(n.spread_right(begin, 11), n.cls(UP + " "), 5)
    tags = [n.spread_right(n.lit(t), len(t)) for t in ("PRIVATE KEY-----", "PRIVATE KEY BLOCK-----")]
    dashes = n.AND(n.OR(*tags), n.cls("-"), ~n.cls("-").at(1))  # last dash of the header
    header_end = n.AND(dashes, label.at(-5))
    nl = n.cls("\n")
    indent = n.prop_right(n.AND(n.cls(" \t"), n.OR(nl.at(-1), n.lit("\\n").at(-2))), n.cls(" \t"), 4)
    after_colon = n.AND(n.cls(" "), n.cls(":").at(-1))
    after_quote = n.AND(n.cls(" \t"), n.cls("\"'").at(-1))
    body_ch = n.OR(n.cls(KEY_BODY + ":,\"'"), indent, after_colon, after_quote, force=True)
    has_body = n.spread_left(n.run(n.cls(B64), 24), 64)
    real = n.AND(header_end, has_body.at(1))
    header = n.prop_left(real, n.cls(UP + " -"), 6)
    body = n.prop_right(real, body_ch, 12)
    n.out("SECRET", n.OR(header, body))
    n.out("kind:private_key", n.AND(begin, header))


URL_PW_PLACEHOLDERS = ["password", "passwd", "pass", "pwd", "pw", "secret", "token", "apikey", "api_key", "key"]
URL_PW_BAD_STARTS = ["$", "%", "{", "[", "xxx", "***", "...", "your"]


URL_PW_MIN = 6
URL_PW_WORDS = ["password", "secret", "example"]  # `password123`, `example-password`: test fixtures
URL_WEAK_MIN = 4
URL_FAKE_USER = ["user", "foo", "test", "demo", "example", "guest", "dummy", "fake", "sample"]  # anywhere in the user
URL_FAKE_HOST = ["localhost", "127.0.0.1", "example", "test", "foo", "host", "domain", "invalid"]  # anywhere in the host
URL_WEAK_WORDS = URL_PW_WORDS + ["pass", "foo", "bar", "test", "demo", "guest", "changeme", "dummy", "fake", "sample", "pwd"]


def url_credentials(n: Net) -> None:
    """scheme://user:PASSWORD@host - the password is the secret, unless it is a placeholder
    (the bare word password/pass/secret/token..., a variable reference, xxx, your...) or too weak
    to be a real one. Strength: 6+ characters with a letter and a digit (a digit right after a
    %XX escape does not count) and none of the words password / secret / example, or a random-looking
    run (see `randomness`). This drops test fixtures such as `u:p@`, `user:pass@`, `guest:guest@`,
    `myuser:mypass@`, `user:pass%20pass@`, `user:password123@`.
    A weaker password (4+ characters with a letter, none of URL_WEAK_WORDS) still counts when the
    URL looks real: no URL_FAKE_USER word in the user name and no URL_FAKE_HOST word in the host
    (`amqp://rabbit:falcon@mq.prod.corp` yes, `http://myuser:mypass@localhost` no)."""
    scheme = n.spread_right(n.lit("://"), 3)
    user = n.prop_right(scheme, n.cls(minus(PRINT, ":@/\"'<>`")), 6)
    colon = n.AND(n.cls(":"), user.at(-1), ~scheme)
    not_compared = []
    if "compared" in VALUE_RULES:
        # `== "scheme://user:pw@host"`: the URL is being compared with an expected value (see auth_headers)
        cmp_gap = n.prop_right(n.OR(n.lit("==").at(-1), n.lit("!=").at(-1)), n.cls(CMP_GAP), 2)
        sch_ch = n.cls(AN + "+.-")
        sch = n.prop_right(n.AND(sch_ch, cmp_gap.at(-1)), sch_ch, 4)
        user_c = n.prop_right(n.spread_right(n.AND(n.lit("://"), sch.at(-1)), 3), n.cls(minus(PRINT, ":@/\"'<>`")), 6)
        not_compared = [~n.AND(colon, user_c.at(-1)).at(-1)]
    pw_chars = n.cls(minus(PRINT, "@/\"'<>`"))
    pw = n.prop_right(colon, pw_chars, 6)
    at_sign = n.cls("@")
    word = n.OR(*[n.AND(n.lit(w, nocase=True), at_sign.at(len(w))) for w in URL_PW_PLACEHOLDERS])
    bad = n.OR(word, *[n.lit(w, nocase=True) for w in URL_PW_BAD_STARTS])
    at = n.AND(at_sign, pw.at(-1), ~colon.at(-1), n.cls(AN + "[").at(1))
    back = n.prop_left(at, pw_chars, 6)
    first = n.AND(back, colon.at(-1), ~bad, *not_compared)  # first password character, reached back from the @
    pct = n.cls("%")
    digit = n.AND(n.cls(D), ~pct.at(-1), ~pct.at(-2))
    inside = lambda sig: n.prop_left(n.AND(back, sig), pw_chars, 6)  # sig somewhere between here and the @
    strong = n.AND(n.run(pw_chars, URL_PW_MIN), inside(digit), inside(n.cls(AL)),
                   ~inside(n.OR(*[n.lit(w, nocase=True) for w in URL_PW_WORDS])))
    # weak passwords count in a real-looking URL: user and host are not test/example names
    user_ch, host_ch = n.cls(minus(PRINT, ":@/\"'<>`")), n.cls(AN + "-.")
    fake_user = n.prop_right(n.OR(*[n.lit(w, nocase=True) for w in URL_FAKE_USER]), user_ch, 6)
    fake_host = n.prop_left(n.OR(*[n.lit(w, nocase=True) for w in URL_FAKE_HOST]), host_ch, 6)
    at_of = lambda sig: n.prop_left(n.AND(at_sign, sig.at(1)), pw_chars, 6)  # carried back from the @
    weak = n.AND(n.run(pw_chars, URL_WEAK_MIN), inside(n.cls(AL)), ~fake_user.at(-2),
                 ~inside(n.OR(*[n.lit(w, nocase=True) for w in URL_WEAK_WORDS])), ~at_of(fake_host))
    ph_hard, ph_soft = placeholder_value(n, inside)
    random_pw = inside(randomness(n))
    first = n.AND(first, n.OR(strong, weak, random_pw), ~ph_hard, ~n.AND(ph_soft, ~random_pw))
    span = n.AND(n.prop_right(first, pw_chars, 6), back)
    n.out("SECRET", span)
    n.out("kind:url_password", first)


# --- generic credentials ---------------------------------------------------------------------
IDENT = AN + "_-."
NAME_TAIL = "\"'[]\\"  # what may sit between the identifier and the separator: quotes, brackets, \"
VALUE = minus(PRINT, "\"'`,;()[]{}<>\\")
TOKEN_BODY = AN + "+/=_-"

# Names that announce a credential on their own.
KEYWORDS = ["passw", "pwd", "secret", "token", "apikey", "api_key", "api-key", "api.key", "access_key",
            "accesskey", "access-key", "auth_key", "authkey", "credential", "private_key", "privatekey",
            "private-key", "client_key", "encryption_key", "signing_key", "signingkey", "passphrase",
            "accountkey", "account_key", "sharedaccesskey", "master_key", "masterkey"]
# Names that only suggest one: the value must also look random (see `randomness`).
WEAK_WORDS = ["key", "auth", "sig", "authorization", "bearer", "signature"]
# A name containing one of these words describes the credential (its file, id, type, policy ...)
# rather than holding it. Matched at a word start; the second list must also end at a word end.
NAME_VETO_PREFIX = ["public", "pubkey", "primary", "foreign", "partition", "cache", "field", "header",
                    "length", "expir", "timeout", "policy", "regex", "pattern", "format", "algorithm",
                    "backend", "endpoint", "prefix", "suffix", "label", "placeholder", "error",
                    "title", "column", "index", "version", "hash", "lifetime", "duration", "interval",
                    "enabled", "required", "valid", "filename", "filepath"]
NAME_VETO_WORD = ["name", "file", "path", "dir", "url", "uri", "type", "len", "size", "count", "min", "max",
                  "ttl", "id", "ids", "msg", "message", "algo", "desc", "help", "hint", "prompt", "pub", "sort", "param",
                  "option", "class"]
# Hash-like / id-like words anywhere in the name: the value is a digest or an identifier.
NAME_VETO_PREFIX += ["checksum", "digest", "fingerprint", "commit", "revision"]
NAME_VETO_WORD += ["sha", "md5", "etag", "uuid", "guid", "arn"]
# Suffix rule: <credential word> then (_ / - / . / camelCase) then a noun that is not a value.
# These nouns veto only when they come AFTER the credential word in the same name
# (password_strength, tokenExpiresAt, secret_rotation_days), so `env.API_KEY` or
# `status_token` are untouched. (word, whole word only)
NAME_SUFFIX_NOUNS = [("strength", False), ("complexity", False), ("rule", True), ("rules", True), ("input", False),
                     ("form", True), ("attr", True), ("attribute", False), ("property", False), ("kind", True),
                     ("mode", True), ("status", False), ("state", True), ("source", False), ("provider", False),
                     ("scheme", False), ("method", False), ("handler", False), ("callback", False),
                     ("factory", False), ("generator", False), ("validator", False), ("validation", False),
                     ("checker", False), ("manager", False), ("service", False), ("bucket", False),
                     ("table", False), ("schema", False), ("template", False), ("location", False),
                     ("folder", False), ("link", True), ("ref", True), ("reference", False), ("alias", False),
                     ("number", False), ("num", True), ("limit", False), ("rotation", False), ("created", False),
                     ("updated", False), ("date", True), ("time", True), ("timestamp", False), ("at", True),
                     ("encoding", False), ("env", True), ("var", True), ("variable", False), ("expires", False),
                     ("expiration", False), ("age", True), ("days", True), ("seconds", True), ("exists", True),
                     ("set", True), ("changed", False), ("reset", False), ("retries", False), ("attempts", False)]
# Values that are public-key material by construction (SSH key blobs, RSA / P-256 SPKI in base64).
PUBLIC_KEY_STARTS = ["ssh-rsa", "ssh-ed25519", "ssh-dss", "ecdsa-sha2", "AAAAB3NzaC1", "AAAAC3NzaC1", "AAAAE2VjZHNh",
                     "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A", "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE", "MIGfMA0GCSqGSIb3DQEBAQUAA4GNA"]
PLACEHOLDER_STARTS = ["your", "xxx", "***", "example", "changeme", "change_me", "placeholder",
                      "insert", "replace", "enter", "todo", "dummy", "sample", "redacted", "null",
                      "none", "undefined", "true", "false", "test", "...", "<", "{", "%", "process.",
                      "os.", "env.", "self.", "this.", "config.", "settings.", "request.", "args."]
PLACEHOLDER_INSIDE = ["example", "xxxx", "****", "://"]
FORMAT_SPECS = ["%s", "%d"]  # only when a non-alphanumeric follows: "%s:%d", not "Ud8%dPQ5"
RANDOM_WINDOW, RANDOM_MIN_LD, RANDOM_MIN_ANY = 16, 3, 10
# Words whose base64 encoding is a documentation placeholder (Kubernetes `data:` examples).
TRIVIAL_WORDS = ["password", "passwd", "secret", "changeme", "admin", "username", "user", "test", "root",
                 "guest", "demo"]
# Round 6: a value that opens with the name of a hash scheme is a digest (`hmac-sha256:08ba...`, `sha1$...`).
HASH_LABELS = ["sha1", "sha224", "sha256", "sha384", "sha512", "md5", "hmac", "pbkdf2", "bcrypt", "scrypt", "argon2"]
# Round 6b: crypt(3) "modular" hashes and their relatives: the stored hash of a password, not the password.
CRYPT_PREFIXES = ["$1$", "$2a$", "$2b$", "$2x$", "$2y$", "$5$", "$6$", "$7$", "$y$", "$apr1$", "$argon2", "$pbkdf2", "$scrypt$"]
# Round 6b: the words password / secret written in leetspeak inside the value (`Cl1ent$ecret!`,
# `verYs3cret`, `Pa55w0rd!`): the documentation password. One character class per letter.
LEET_WORDS = [["pP", "aA@4", "sS$5zZ3", "sS$5zZ3", "wW", "oO0", "rR", "dD"], ["sS$5", "eE3", "cC", "rR", "eE3", "tT"]]
# Round 6: base64 of lower-case letters only. A byte 0x60-0x7F in first, second and third place of a
# triple forces the 1st, 2nd and 3rd base64 character into these classes.
B64_LOWER = ("YZabcdef", "GHWXmn23", "BFJNRVZdhlptx159")
B64_LOWER_GROUPS = 16
EXAMPLE_REACH = 64  # "example" this close before a blank-separated value marks it as documentation
PW_SYMBOLS = "!$*^~"  # count like a digit in a literal; % & @ # are left out (URL escapes, queries, e-mail)


def randomness(n: Net) -> Sig:
    """Neuron-sized randomness measure. Fires at i when text[i:i+16] is one unbroken run of token
    characters and, among its 15 adjacent pairs, either
      - at least 3 are letter<->digit alternations, or
      - at least 10 change character class at all (lower / upper / digit).

    Words, identifiers, paths and camelCase names rarely alternate (sha256, utf8, v2 give one
    letter<->digit flip each; a camelCase hump gives two case flips per word). Uniformly random
    hex flips letter<->digit on 47% of pairs, base62 on 27%, and base62 changes class on 62% of
    pairs, so some window of a real key clears a bar that `my-app-tls-secret-2024` or
    `PBKDF2PasswordHasher` does not."""
    al, d, lo, up = n.cls(AL), n.cls(D), n.cls(LO), n.cls(UP)
    ld = n.OR(n.AND(al, d.at(1)), n.AND(d, al.at(1)))
    case = n.OR(n.AND(lo, up.at(1)), n.AND(up, lo.at(1)))
    pairs = range(RANDOM_WINDOW - 1)
    enough = n.OR(n.atleast(RANDOM_MIN_LD, *[ld.at(k) for k in pairs]),
                  n.atleast(RANDOM_MIN_ANY, *[ld.at(k) for k in pairs], *[case.at(k) for k in pairs]))
    return n.AND(enough, n.run(n.cls(TOKEN_BODY), RANDOM_WINDOW))


def _word_bounds(n: Net) -> tuple[Sig, Sig]:
    """(word start, word continues): identifier words begin after a non-letter or at a
    lower->Upper camel hump; `inner` is a letter that does not begin a new word."""
    al, lo, up = n.cls(AL), n.cls(LO), n.cls(UP)
    camel = n.AND(up, lo.at(-1))
    start = n.OR(n.AND(al, ~al.at(-1)), camel)
    inner = n.AND(al, ~camel)
    return start, inner


# (word, whole word only). Matched at an identifier word start; "whole" also needs a word end.
# api / auth / authorization / bearer / signature / connection were tried first and dropped: on dev
# negatives they armed apiAddress, digest-auth nonces and Basic headers (neg_dev2: 28 -> 59 lines).
CONTEXT_CUES = [("key", True), ("keys", True), ("token", False), ("secret", False), ("passw", False),
                ("credential", False), ("private", False), ("webhook", False), ("dsn", True)]
# Round 4: each round-3 anti-cue was ablated on the dev sets (eval/secrets/ablate_anti.py, same-line
# version). Only "public" removed dev false positives (60 lines) at no dev recall cost; "id" cost
# 4 planted secrets (it also matches inside random values such as ...6id1178...) and the other
# 28 words changed nothing on dev, so they were dropped. Round 3 settled the list.
ANTI_CUES = [("public", False)]
CONTEXT_REACH = 64      # a cue reaches this far to its right (about a line, or into the next one)
CONTEXT_MIN_LEN = 20


def _cues(n: Net, words) -> Sig:
    wstart, inner = _word_bounds(n)
    return n.OR(*[n.AND(n.lit(w, nocase=True), wstart, *([~inner.at(len(w))] if whole else [])) for w, whole in words],
                force=True)


NOT_NEWLINE = frozenset(range(1, 256)) - {10}  # NUL is excluded too: it pads documents apart


def line_right(n: Net, seed: Sig, maxpow: int = 5) -> Sig:
    """seed, carried right over up to 2^(maxpow+1)-1 characters but never across a newline."""
    return n.prop_right(seed, n.cls(NOT_NEWLINE), maxpow)


def line_left(n: Net, seed: Sig, maxpow: int = 5) -> Sig:
    """seed, carried left over up to 2^(maxpow+1)-1 characters but never across a newline."""
    return n.prop_left(seed, n.cls(NOT_NEWLINE), maxpow)


def anti_context(n: Net) -> Sig:
    """1 where an ANTI_CUES word starts on the same line, within 63 characters before this
    position or 63 characters from here on: the line is talking about hashes, ids or versions.
    Round 3 used a plain 64-character spread here, which crossed line ends."""
    a = _cues(n, ANTI_CUES)
    return n.OR(line_right(n, a).at(-1), line_left(n, a))


def context_secrets(n: Net) -> None:
    """Unlabelled random values that only the surrounding text marks as secret.

    A run of 20+ token characters [A-Za-z0-9+/=_-] starting after a character that is not a token
    character, '.', '%' or '@' (`uses: actions/checkout@<sha>`), not starting with '/', not right
    after `Basic ` / `earer ` (auth_headers judges those), with a random 16-character window (see
    `randomness`) among its first 23 characters, a CONTEXT_CUES word starting in the 64 characters
    before it, and no ANTI_CUES word within 64 characters on either side. Masked up to 511."""
    tok = n.cls(TOKEN_BODY)
    ctx = n.spread_right(_cues(n, CONTEXT_CUES), CONTEXT_REACH).at(-1)
    scheme = n.OR(n.lit("Basic ").at(-6), n.lit("earer ").at(-6))  # header values: see auth_headers
    start = n.AND(tok, ~n.cls(TOKEN_BODY + ".%@").at(-1), ~n.cls("/"), n.run(tok, CONTEXT_MIN_LEN),
                  n.spread_left(randomness(n), 8), ctx, ~scheme, *([~anti_context(n)] if ANTI_CUES else []))
    n.out("SECRET", n.prop_right(start, tok, 8))
    n.out("kind:context_secret", start)


# --- "it is an example": text-only evidence that the surrounding text is a test or documentation --------
# Words that say "this is a test fixture or an illustration". (word, whole word only); matched at an
# identifier word start, so `hcloudTestToken`, `fake_client`, `assertEqual`, `expected` all count.
EXAMPLE_WORDS = [("test", False), ("mock", False), ("stub", True), ("stubs", True), ("fake", False), ("fixture", False),
                 ("dummy", False), ("sample", False), ("example", False), ("demo", True), ("assert", False),
                 ("expect", False), ("it(", False), ("describe(", False), ("e.g.", False), ("for instance", True),
                 ("such as", True), ("usage", True)]
EXAMPLE_LINES = 4       # a word reaches the rest of its own line and, as prose or a call, the next four lines
# A word counts on the lines below it only when it stands as prose or as (part of) a called or defined
# name; inside some other identifier or value (`TEST_KEY=...`, `sk_test_...`, `db.example.net`) it says
# nothing about its neighbours.
PROSE_BEFORE = AN + "_-./\\$="   # characters that may NOT precede a prose word
PROSE_AFTER = " \t\n:,;!?)]"      # a prose word (plus at most three more letters) ends before one of these
CALL_NAME = AN + "_"              # `assertEqual(`, `test_login(`, `it(`: the word, name characters, then `(`
EXAMPLE_LINE_POW = 7    # ... along at most 255 characters of each line
# First non-blank characters of a comment line, a documentation shell prompt or a quoted block.
COMMENT_MARKS = ["# ", "//", "* ", "/*", "-- ", "<!--", "$ ", "> "]
RST_BLOCK_OPEN = [".. code", ".. sourcecode", "::\n"]  # reStructuredText literal blocks
DOC_BLOCK_POW = 10      # a documentation block is followed for at most 2,047 characters
TEST_CODE_POW = 10      # ... and so is test code after a test declaration
NOT_NUL = frozenset(range(1, 256))


def example_evidence(n: Net) -> dict[str, Sig]:
    """Three independent signals, each 1 at a position whose surroundings say "example":

    word     an EXAMPLE_WORDS word starts earlier on the same line (within 255 characters); or one
             starts on one of the EXAMPLE_LINES lines above (each followed for at most 255 characters)
             and stands there as prose (not after a PROSE_BEFORE character; the word, at most three
             more letters, then a PROSE_AFTER character or `. `), or in a called or defined name (the
             word, CALL_NAME characters, then an opening parenthesis), or opens a name that runs to
             the end of the line and is not a value after `= ` or `: ` (`def test_reset_flow`). On its own line "example" does not count
             with a dot directly before or after it (a host name)
    comment  the line's first non-blank characters are one of COMMENT_MARKS (within 255 characters)
    block    inside a Markdown code fence that was opened with a language tag (three backticks and a
             letter as the first non-blank characters of a line; ends at the next three backticks), or
             inside a reStructuredText literal block (`.. code...`, `.. sourcecode...` or `::` at a
             line end; ends at the first line that starts in column 0). At most 2,047 characters.
    testcode (round 6b) within 2,047 characters after a test declaration, across lines:
             a name that begins with "test" (not after a PROSE_BEFORE character) and is called or
             defined (`test_login(`, `TestLogin(`, `testLogin(`, `test(`, `def test_reset_flow`);
             `it(` / `describe(`; an annotation `@Test...` (the @ not after a name character);
             `#[test]`, `...::test]`, `cfg(test)`. It is the same kind of evidence as `word` and
             counts as one vote together with it.
    They are votes, not vetoes: `keyword_assignment` weighs them against the positive evidence."""
    nl, blank, text_ch, printable = n.cls("\n"), n.cls(" \t"), n.cls(NOT_NEWLINE), n.cls(PRINT)
    wstart, inner = _word_bounds(n)
    al, after = n.cls(AL), n.OR(n.cls(PROSE_AFTER), n.AND(n.cls("."), n.cls(" \t\n").at(1)))
    call_name = n.prop_left(n.AND(n.cls(CALL_NAME), n.cls("(").at(1)), n.cls(CALL_NAME), 5)   # name characters running up to a `(`
    name_eol = n.prop_left(n.AND(n.cls(CALL_NAME), nl.at(1)), n.cls(CALL_NAME), 5)   # ... up to the line end
    dot = n.cls(".")
    same, far = [], []
    for w, whole in EXAMPLE_WORDS:
        L = len(w)
        cue = n.AND(n.lit(w, nocase=True), wstart, *([~inner.at(L)] if whole else []))
        ends = n.OR(*[n.AND(*[al.at(L + j) for j in range(k)], after.at(L + k)) for k in range(4)])
        fresh = ~n.cls(PROSE_BEFORE).at(-1)
        # on its own line any occurrence counts, except "example" inside a host name (db.example.net)
        same.append(n.AND(cue, ~dot.at(-1), ~dot.at(L)) if w == "example" else cue)
        far.append(n.AND(cue, n.OR(n.AND(fresh, ends), call_name, n.AND(fresh, name_eol, ~n.cls("=:").at(-2)))))
    s = line_right(n, n.OR(*far, force=True), EXAMPLE_LINE_POW)
    for _ in range(EXAMPLE_LINES):
        s = n.OR(s, line_right(n, n.AND(nl, s.at(-1)), EXAMPLE_LINE_POW))
    s = n.OR(s, line_right(n, n.OR(*same, force=True), EXAMPLE_LINE_POW))
    test = n.AND(n.lit("test", nocase=True), wstart)
    fresh = ~n.cls(PROSE_BEFORE).at(-1)
    decl = n.OR(n.AND(test, fresh, n.OR(call_name, n.AND(name_eol, ~n.cls("=:").at(-2)))),
                n.AND(n.OR(n.lit("it(", nocase=True), n.lit("describe(", nocase=True)), wstart, fresh),
                n.AND(test, n.cls("@").at(-1), ~n.cls(AN + "._-").at(-2), ~inner.at(4)),
                n.AND(test, n.cls("]").at(4), n.OR(n.lit("#[").at(-2), n.cls(":").at(-1))),
                n.lit("cfg(test)", nocase=True))
    indent = n.prop_right(n.AND(blank, ~text_ch.at(-1)), blank, 5)
    first = n.OR(n.AND(printable, ~text_ch.at(-1)), n.AND(printable, indent.at(-1)))  # first non-blank of a line
    mark = n.AND(first, n.OR(*[n.lit(m) for m in COMMENT_MARKS]))
    any_ch = n.cls(NOT_NUL)
    fence = n.lit("```")
    md = n.prop_right(n.AND(fence, first, n.cls(AL).at(3)), n.AND(any_ch, ~fence), DOC_BLOCK_POW)
    rst_open = n.OR(*[n.lit(w) for w in RST_BLOCK_OPEN])
    dedent = n.AND(printable, nl.at(-1))
    rst = n.prop_right(rst_open, n.AND(any_ch, ~dedent), DOC_BLOCK_POW)
    return {"word": s.at(-1), "comment": line_right(n, mark, EXAMPLE_LINE_POW), "block": n.OR(md, rst),
            "testcode": n.prop_right(decl, any_ch, TEST_CODE_POW).at(-1)}


# --- placeholder values: one shape + vocabulary rule shared by keyword_assignment and url_credentials
PLACEHOLDER_VOCAB = ["password", "passwd", "pass", "pwd", "changeme", "secret", "admin", "administrator", "root",
                     "test", "testing", "example", "sample", "dummy", "demo", "foo", "bar", "baz", "qux", "todo",
                     "tbd", "fixme", "replaceme", "replace_me", "default", "guest", "user", "letmein", "qwerty",
                     "null", "none", "nil", "undefined", "empty", "placeholder", "redacted", "hidden", "welcome",
                     "hello", "mypassword", "mysecret", "abc", "xyz"]
PLACEHOLDER_ANYWHERE = ["_here", "-here", "here_", "here-", "your", "insert", "replace"]
REDACTED_WORDS = ["redact", "masked"]   # round 6b: a value that says it was removed (`$REDACTED$`), anywhere in it


def placeholder_anywhere() -> list[str]:
    return PLACEHOLDER_ANYWHERE + (REDACTED_WORDS if "redacted" in VALUE_RULES else [])
REPEAT_CHARS = AN + "*#.!-_~+=x"
_ALPHA = string.ascii_lowercase
SEQ4 = ([D[i:i + 4] for i in range(7)] + [D[::-1][i:i + 4] for i in range(7)] + [_ALPHA[i:i + 4] for i in range(23)]
        + ["qwer", "wert", "asdf", "zxcv", "a1b2"])
DIGIT_RUN5 = [D[i:i + 5] for i in range(6)] + [D[::-1][i:i + 5] for i in range(6)]
ASC3 = [_ALPHA[i:i + 3] for i in range(24)] + [D[i:i + 3] for i in range(8)]  # abc, bcd, ... xyz, 012, ... 789


def placeholder_value(n: Net, inside) -> tuple[Sig, Sig]:
    """Fires at the first character of a value that is a placeholder by shape or vocabulary.
    `inside(sig)` must mean "sig fires somewhere from here to the end of this value".
      - a PLACEHOLDER_VOCAB word, then no further letter (`admin`, `test123`, `Password1!`, `demo_2024`;
        not `passport2024` or `Falconcopper12!`)
      - 4 identical characters (`xxxx…`, `****…`, `aaaa…`, `1111…`)
      - a 4-character ascending / descending / keyboard run (`1234…`, `abcd…`, `9876…`, `qwer…`),
        or a 5-digit run anywhere (`abc123456`)
      - a description word anywhere (`your-api-key-here`, `insert_token`, `replace-with-real-secret`)
      - (round 6, "chunks") every character belongs to a three-character ascending run, letters or
        digits: `abc123def456`, `xyz789abc`, `abcdefghi123`; or the value opens with the interleaved
        run `a1b2c3` (`A1B2C3D4E5F6G7H8I9J0`), which the soft `a1b2` shape leaves to a random-looking value
    Returns (hard, soft). Callers let a random-looking value override `soft` (the repeat and
    sequence shapes): Twitter bearer tokens start with 22 `A`s and random hex can start `3210`."""
    letter_after = inside(n.cls(AL))
    vocab = n.OR(*[n.AND(n.lit(w, nocase=True), ~letter_after.at(len(w))) for w in PLACEHOLDER_VOCAB])
    repeat = n.OR(*[n.run(n.cls(c), 4) for c in REPEAT_CHARS])
    seq = n.OR(*[n.lit(w, nocase=True) for w in SEQ4], inside(n.OR(*[n.lit(w) for w in DIGIT_RUN5])))
    described = inside(n.OR(*[n.lit(w, nocase=True) for w in placeholder_anywhere()]))
    hard = [vocab, described]
    if "chunks" in VALUE_RULES:
        asc = n.OR(*[n.lit(w, nocase=True) for w in ASC3])
        loose = n.AND(n.cls(PRINT), ~asc, ~asc.at(-1), ~asc.at(-2))  # a character outside every ascending run
        hard.append(n.AND(asc, ~inside(loose)))
        hard.append(n.lit("a1b2c3", nocase=True))   # the interleaved run: letters and digits both ascending
    return n.OR(*hard), n.OR(repeat, seq)


def keyword_assignment(n: Net) -> None:
    """<secret-ish name> <separator> <value>.

    name      a KEYWORDS hit (strong) or a WEAK_WORDS word (weak), then the rest of the identifier,
              closing quotes/brackets and up to three blanks; dropped when the identifier contains a
              NAME_VETO word (password_file, token_type, public_key ...)
    separator `=` or `:` (also := => and their quoted forms, never ==); `", "` between two quoted
              call arguments; `" value="` (XML attribute); `>` (XML element); a single blank
    value     8+ value characters, not followed by ( [ {, not a placeholder
    A value is reported when it is random (16+ chars, see `randomness`), or, for a strong name
    with a real separator, when it has a letter and a digit (not one of a %XX escape) or one of
    PW_SYMBOLS after the first character, does not itself mention a keyword,
    does not start like a path, operator or private identifier (/ # _ + & | ./ ~/), is not a
    version string (1.2.3, v2.10.1), a number with a unit (86400000ms) or a file name (ends in
    .ext), and is not a bare snake_case / dotted identifier after `= ` (`x = other_var1`).
    Public-key material (ssh-rsa, AAAAB3NzaC1..., SPKI base64) is never a value.
    Names: besides NAME_VETO words anywhere in the name, a NAME_SUFFIX_NOUNS word after the
    credential word vetoes it (password_strength, tokenExpiresAt, secret_rotation_days). A value starting with `$`
    is a variable reference only when no other non-word character follows (`$DB_PASS_V2`).
    `name:` at the end of a line also takes a value from the start of the next line (YAML, JSON);
    a value containing `: ` is then a nested key, not a value.
    Random-only detections are dropped in anti-context (see `anti_context`) unless the name is strong.
    A blank is a real separator only after `ENV `, `login ` (netrc) or `--`; `curl -u user:` arms
    the same value test. Otherwise a value after a blank needs to be random, and is dropped when
    the word "example" (not as part of a domain) occurs in the 64 characters before it. The exact
    base64 encoding of a TRIVIAL_WORDS word counts as a placeholder. No fixed lookback is longer than 64 characters, the engine's padding
    between documents."""
    v, al, d = n.cls(VALUE), n.cls(AL), n.cls(D)
    blank, quote = n.cls(" \t"), n.cls("\"'")
    wstart, inner = _word_bounds(n)
    lits = lambda words: [n.lit(w, nocase=True) for w in words]

    strong_kw = n.OR(*lits(KEYWORDS), n.AND(n.lit("pass", nocase=True), ~inner.at(4), ~n.cls(LO).at(-1)))
    weak_kw = n.OR(*[n.AND(n.lit(w, nocase=True), wstart, ~inner.at(len(w))) for w in WEAK_WORDS])
    veto_kw = n.OR(*[n.AND(x, wstart) for x in lits(NAME_VETO_PREFIX)],
                   *[n.AND(n.lit(w, nocase=True), wstart, ~inner.at(len(w))) for w in NAME_VETO_WORD])

    def chain(seed: Sig) -> Sig:
        return n.prop_right(n.prop_right(seed, n.cls(IDENT + NAME_TAIL), 5), blank, 1)

    named = chain(n.OR(strong_kw, weak_kw))
    suffix_noun = n.AND(_cues(n, NAME_SUFFIX_NOUNS), named, ~strong_kw, ~weak_kw)  # a noun after the credential word
    vetoed = n.OR(chain(veto_kw), chain(suffix_noun))
    strong = n.AND(chain(strong_kw), ~vetoed)
    anyname = n.AND(named, ~vetoed)

    compare = n.AND(n.cls("="), n.cls("=").at(1))
    # `Name::member` is a scope operator (C++, Java, PHP, Ruby, Rust), not a separator
    scope = [~n.AND(n.cls(":"), n.cls(":").at(1))] if "scope" in VALUE_RULES else []
    # the colon of `scheme://user:password@` is the userinfo separator: `url_credentials` judges that one
    url_user = n.prop_right(n.spread_right(n.lit("://"), 3), n.cls(minus(PRINT, ":@/\"'<>`")), 6)
    userinfo = [~n.AND(n.cls(":"), url_user.at(-1))] if "userinfo" in VALUE_RULES else []
    long_opt = n.spread_right(n.lit("--"), 32)
    context = n.OR(n.spread_right(n.lit("ENV "), 48), n.spread_right(n.lit("login "), 64), long_opt)

    def starts(name: Sig) -> tuple[Sig, Sig]:
        """(value starts after a real separator, value starts after a single blank)."""
        sep = n.AND(n.cls("=:"), name.at(-1), ~compare, *scope, *userinfo)
        gap = n.prop_right(sep, n.cls(" \t\"'`=>\\"), 2)
        assign = n.AND(v, gap.at(-1), ~gap)
        comma = n.AND(n.cls(","), name.at(-1), quote.at(-1))
        arg = n.AND(v, quote.at(-1), n.prop_right(comma, blank, 1).at(-2))
        attr = n.OR(*[n.AND(n.lit(q + " value=" + q), name) for q in "\"'"])
        elem = n.AND(n.cls(">"), name.at(-1), ~n.cls("-=").at(-1))
        colon_eol = n.AND(n.cls("\n"), n.cls(":").at(-1), name.at(-2))
        next_line = n.prop_right(colon_eol, n.cls(" \t\"'"), 3)
        assign = n.OR(assign, n.AND(v, next_line.at(-1), ~next_line))
        after_blank = n.AND(v, ~n.cls("=:"), n.cls(" ").at(-1), name.at(-1))
        return n.OR(assign, arg, n.AND(v, attr.at(-9)), n.AND(v, elem.at(-1))), after_blank

    s_real, s_blank = starts(strong)
    a_real, a_blank = starts(anyname)

    # curl -u user:PASSWORD / curl --user user:PASSWORD
    curl = n.spread_right(n.lit("curl "), 64)
    flag = n.OR(n.AND(n.lit("-u "), curl, ~n.cls("-").at(-1)).at(-2), n.AND(n.lit("--user "), curl).at(-6))
    opener = n.OR(flag, n.AND(quote, flag.at(-1)))
    user = n.prop_right(opener, n.cls(AN + "_.@-"), 5)
    curl_start = n.AND(v, n.AND(n.cls(":"), user.at(-1), ~opener.at(-1)).at(-1))

    # "For example: set the auth token 0123abcd..." - prose, not an assignment
    example = n.AND(n.lit("example", nocase=True), ~n.cls(".").at(-1), ~n.cls(".").at(7))
    in_example = n.spread_right(example, EXAMPLE_REACH).at(-1)
    tier_a = n.OR(s_real, n.AND(s_blank, context.at(-1)), curl_start)  # judged as a literal
    # round 6b: after a bare blank a value starts with a letter or digit (`name *pkg.Type` is a declaration)
    plain_start = [n.cls(AN)] if "blankstart" in VALUE_RULES else []
    cand = n.OR(tier_a, a_real, n.AND(a_blank, ~in_example, *plain_start))            # judged at least as random
    start = n.AND(cand, n.run(v, 8))
    span = n.prop_right(start, v, 7)
    back = lambda sig: n.prop_left(n.AND(span, sig), v, 7)  # "somewhere in the value", seen from its start

    pct = n.cls("%")
    # round 6b: one or two digits right after a word-initial v / V are a version marker (`AppV1Controller`, `api_v2`)
    vmark = n.AND(n.cls("vV"), wstart)
    vdigit = [~n.AND(d, n.OR(vmark.at(-1), n.AND(d.at(-1), vmark.at(-2))))] if "vdigit" in VALUE_RULES else []
    has_digit, has_alpha = back(n.AND(d, ~pct.at(-1), ~pct.at(-2), *vdigit)), back(al)  # %2F is not a digit
    has_symbol = back(n.AND(n.cls(PW_SYMBOLS), ~start))  # a password symbol, not in first place
    is_random = back(randomness(n))
    fmt = [n.AND(x, ~n.cls(AN).at(2)) for x in lits(FORMAT_SPECS)]
    jwt_sample = [n.lit("." + JWT_SAMPLE_PAYLOAD)] if "jwtsample" in VALUE_RULES else []  # see `jwt`
    hard = back(n.OR(n.cls("([{").at(1), *lits(PLACEHOLDER_INSIDE), *fmt, n.AND(n.cls(":"), n.cls(" \t\n").at(1)), *jwt_sample))
    mentions = back(n.OR(*lits(KEYWORDS)))
    # leetspeak password / secret anywhere in the value: on both paths (the digits make `Pa55w0rd!` look random)
    leet = [back(n.OR(*[n.seq([(c, 1) for c in w])[0] for w in LEET_WORDS]))] if "leet" in VALUE_RULES else []
    special = back(n.cls(minus(VALUE, AN + "_.")))
    joined = back(n.cls("_."))
    ident_like = n.AND(start, joined, ~special, blank.at(-1), n.cls("=").at(-2))
    # `$NAME` / `$NAME_V2` is a variable reference; `$txq$mU!c...` is a password that starts with $
    later_special = n.prop_left(n.AND(span, n.cls(minus(VALUE, AN + "_.")), ~start), v, 7)
    dollar_ref = n.AND(n.cls("$"), ~later_special)
    # version strings (1.2.3, v2.10.1-rc1), numbers with a unit (86400000ms, 100MB), file names (*.pem)
    dot = n.cls(".")
    version = n.OR(n.AND(d, dot.at(1), d.at(2)), n.AND(d, d.at(1), dot.at(2), d.at(3)),
                   n.AND(n.cls("vV"), d.at(1), dot.at(2), d.at(3)), n.AND(n.cls("vV"), d.at(1), d.at(2), dot.at(3), d.at(4)))
    not_letter = n.cls(minus(VALUE, AL))
    unit_number = n.AND(d, ~back(n.AND(al, not_letter.at(1))), ~back(n.run(al, 4)))
    ends = lambda k: n.AND(*[al.at(j) for j in range(1, k + 1)], ~v.at(k + 1))
    file_name = back(n.AND(dot, n.OR(ends(2), ends(3), ends(4))))
    public_key = n.OR(*[n.lit(w) for w in PUBLIC_KEY_STARTS])
    path_like = n.OR(n.cls("/#_+&|"), n.lit("./"), n.lit("~/"), version, unit_number, file_name)
    import base64
    b64c = n.cls(AN + "+/=")
    trivial_b64 = [n.AND(n.lit(e), ~b64c.at(len(e))) for e in (base64.b64encode(w.encode()).decode() for w in TRIVIAL_WORDS)]
    ph_hard, ph_soft = placeholder_value(n, back)
    more = []
    if "pathvalue" in VALUE_RULES:
        # `/var/run/docker/netns/3df8...`: a slash, two or more of [a-z_.-], a slash. (The literal path
        # already drops every value that starts with a slash; random base64 opens like this 1 time in 14,000.)
        slash, seg_ch = n.AND(cand, n.cls("/")), n.cls(LO + "_-.")
        seg = n.prop_right(slash, seg_ch, 4)
        more.append(n.AND(slash, back(n.AND(n.cls("/"), seg.at(-1), seg.at(-2), ~slash.at(-1), ~slash.at(-2)))))
    if "hashlabel" in VALUE_RULES:
        more += lits(HASH_LABELS)
    if "crypt" in VALUE_RULES:
        more += [n.lit(w) for w in CRYPT_PREFIXES]
    if "version" in VALUE_RULES:
        more.append(version)
    if "b64lower" in VALUE_RULES:
        # base64 of lower-case letters only: full groups, then the end of the value or one padded group;
        # at least two groups in all. The plain text would have neither digit nor symbol.
        c1, c2, c3 = (n.cls(c) for c in B64_LOWER)
        grp = n.AND(c1, c2.at(1), c3.at(2), b64c.at(3))
        pad = n.AND(c1, b64c.at(1), b64c.at(2), n.cls("=").at(3), ~b64c.at(4))
        tail = n.OR(n.AND(grp, ~b64c.at(4)), pad)   # last group: full and then the value ends, or padded
        for _ in range(B64_LOWER_GROUPS - 2):
            tail = n.OR(n.AND(grp, ~b64c.at(4)), pad, n.AND(grp, tail.at(4)))
        more.append(n.AND(grp, tail.at(4)))
    placeholder = n.OR(*lits(PLACEHOLDER_STARTS), dollar_ref, *trivial_b64, ph_hard, n.AND(ph_soft, ~is_random),
                       public_key, *more, *leet)
    # an unquoted run of letters, digits, _ and . directly followed by a comma is a code reference
    # (`{ token: FixtureDep2, optional: true }`), not a literal
    code_arg = ([n.AND(~n.cls("\"'`").at(-1), ~special, back(n.AND(v, n.cls(",").at(1))))] if "codearg" in VALUE_RULES else [])

    # Example evidence, weighed against the positive evidence: a strong name with a real separator
    # and a random value survives one vote and is dropped by two; everything else (a literal, or a
    # random value whose name is weak or which only follows a blank) is dropped by one context vote.
    # The value's own shape gives a fourth vote that never decides alone: a UUID (8-4-4-4-12 hex)
    # is an identifier at least as often as a credential.
    ev = example_evidence(n)
    near_test = [ev[k] for k in ("word", "testcode") if k in EXAMPLE_VOTES]   # one vote between them
    ctx = ([n.OR(*near_test, force=True)] if near_test else []) + [ev[k] for k in ("comment", "block") if k in EXAMPLE_VOTES]
    votes = list(ctx)
    if "uuid" in EXAMPLE_VOTES:
        votes.append(n.seq([(HEX, 8), ("-", 1), (HEX, 4), ("-", 1), (HEX, 4), ("-", 1), (HEX, 4), ("-", 1), (HEX, 12)])[0])
    ex1 = [~n.OR(*ctx, force=True)] if ctx else []
    ex_random = [~n.AND(n.OR(*ctx, force=True), ~tier_a)] if ctx else []
    if ctx and len(votes) >= 2:
        ex_random.append(~n.atleast(2, *votes))

    literal = n.AND(start, tier_a, n.OR(has_digit, has_symbol), has_alpha, ~hard, ~placeholder, ~mentions, ~ident_like, ~path_like,
                    *[~c for c in code_arg], *ex1)
    random_ = n.AND(start, is_random, ~hard, ~placeholder,
                    *([~n.AND(anti_context(n), ~tier_a)] if ANTI_CUES else []), *ex_random)
    good = n.OR(literal, random_)
    n.out("SECRET", n.prop_right(good, v, 10))  # judged on its first 256 characters, masked up to 2,047
    n.out("kind:keyword_secret", good)


CMP_GAP = " \t\"'`(b"   # between `==` and the compared value: blanks, quotes, `(`, a bytes-literal prefix
# Credentials used in documentation and test suites; their Basic-auth encodings are vetoed.
TRIVIAL_BASIC_PAIRS = ["user:pass", "user:password", "username:password", "admin:admin", "admin:password",
                       "test:test", "foo:bar", "user:secret", "demo:demo", "guest:guest", "root:root",
                       "Aladdin:open sesame"]  # the last one is RFC 7617's example
# Round 6b: every trivial user with every trivial password (`user:passwd`, `admin:secret`, ...)
TRIVIAL_USERS = ["user", "username", "admin", "test", "foo", "demo", "guest", "root"]
TRIVIAL_PASSWORDS = ["pass", "passwd", "password", "pwd", "secret", "admin", "test", "bar", "demo", "guest", "root", "changeme"]


def trivial_basic_pairs() -> list[str]:
    extra = [u + ":" + p for u in TRIVIAL_USERS for p in TRIVIAL_PASSWORDS] if "trivialbasic" in VALUE_RULES else []
    return TRIVIAL_BASIC_PAIRS + [x for x in extra if x not in TRIVIAL_BASIC_PAIRS]


BASIC_MIN = 16  # base64 of at least 12 bytes: a 3-letter user name and an 8-character password


def auth_headers(n: Net) -> None:
    """`Bearer <token>` with a random-looking token of 16+ characters, and
    `Authorization: Basic <base64>` (16+ base64 characters whose first 12 change character class
    4+ times, which base64 of a real user:password does and prose does not), unless it is exactly
    the encoding of a TRIVIAL_BASIC_PAIRS credential."""
    tok = n.cls(TOKEN_BODY + ".~")
    bearer = n.AND(n.lit("earer "), n.cls("Bb").at(-1))
    # `== "Basic ..."` / `!= "Bearer ..."`: the header is being compared with an expected value (a test)
    cmp_gap = n.prop_right(n.OR(n.lit("==").at(-1), n.lit("!=").at(-1)), n.cls(CMP_GAP), 2)
    compared = lambda k: [~cmp_gap.at(-k)] if "compared" in VALUE_RULES else []
    b_start = n.AND(tok, bearer.at(-6), n.run(tok, 16), *compared(8))
    b_span = n.prop_right(b_start, tok, 7)
    jwt_sample = ([~n.prop_left(n.AND(b_span, n.lit("." + JWT_SAMPLE_PAYLOAD)), tok, 7)] if "jwtsample" in VALUE_RULES else [])
    b_good = n.AND(b_start, n.prop_left(n.AND(b_span, randomness(n)), tok, 7), *jwt_sample)
    n.out("SECRET", n.prop_right(b_good, tok, 10))
    n.out("kind:bearer_token", b_good)

    b64, lo, up, al, d = n.cls(B64), n.cls(LO), n.cls(UP), n.cls(AL), n.cls(D)
    basic = n.AND(n.lit("Basic "), n.spread_right(n.lit("uthorization"), 24))
    flips = [n.OR(n.AND(lo, up.at(1)), n.AND(up, lo.at(1))), n.OR(n.AND(al, d.at(1)), n.AND(d, al.at(1)))]
    import base64
    trivial = [base64.b64encode(p.encode()).decode() for p in trivial_basic_pairs()]
    known = n.OR(*[n.AND(n.lit(t), ~b64.at(len(t))) for t in trivial])
    a_good = n.AND(b64, basic.at(-6), n.run(b64, BASIC_MIN), n.atleast(4, *[f.at(k) for f in flips for k in range(11)]), ~known, *compared(7))
    n.out("SECRET", n.prop_right(a_good, b64, 7))
    n.out("kind:basic_auth", a_good)


def aws_secret_near_id(n: Net) -> None:
    """A bare 40-character base64 string is an AWS secret access key when an access key id
    (AKIA.../ASIA...) starts within the 64 characters before it and the string is random."""
    b = n.cls(AN + "+/")
    ids = [n.AND(n.seq(parse(p + "[A-Z2-7]{16}"))[0], ~n.cls(AN).at(-1), ~n.cls(UP + D).at(20)) for p in ("AKIA", "ASIA")]
    near = n.spread_right(n.OR(*ids), 64)
    key = n.AND(n.run(b, 40), ~b.at(-1), ~b.at(40), ~n.cls("=").at(40), near.at(-1), n.spread_left(randomness(n), 25))
    n.out("SECRET", n.spread_right(key, 40))
    n.out("kind:aws_secret_access_key", key)


# --------------------------------------------------------------------------- structured PII
def email(n: Net) -> None:
    local = n.cls(AN + "._%+-")
    dom = n.cls(AN + "-")
    dc = n.OR(dom, n.AND(n.cls("."), dom.at(1), dom.at(-1)), force=True)  # dots only between labels
    at = n.AND(n.cls("@"), local.at(-1), dom.at(1))
    domain = n.prop_right(at, dc, 6)
    tld_dot = n.AND(n.cls("."), domain, n.run(n.cls(AL), 2).at(1))
    reach = n.prop_left(tld_dot, dc, 6)
    good = n.AND(at, reach.at(1))
    n.out("EMAIL", n.OR(n.prop_left(good, local, 6), n.prop_right(good, dc, 6)))


def ipv4(n: Net) -> None:
    d, dot = n.cls(D), n.cls(".")
    o1 = n.AND(d, ~d.at(1))
    o2 = n.AND(d, d.at(1), ~d.at(2))
    o3 = n.AND(n.OR(n.AND(n.cls("01"), d.at(1), d.at(2)),
                    n.AND(n.cls("2"), n.cls("01234").at(1), d.at(2)),
                    n.AND(n.cls("2"), n.cls("5").at(1), n.cls("012345").at(2))), ~d.at(3))
    octs = [(o1, 1), (o2, 2), (o3, 3)]
    any_oct = n.OR(o1, o2, o3)
    start = n.AND(any_oct, ~n.cls(D + ".").at(-1))
    for _ in range(3):
        start = n.OR(*[n.AND(start.at(-L - 1), o.at(-L - 1), dot.at(-1), any_oct) for o, L in octs])
    tail_ok = [n.AND(start, o, ~n.AND(dot, d.at(1)).at(L)).at(-(L - 1)) for o, L in octs]
    end = n.OR(*tail_ok)  # fires on the last digit
    n.out("IPV4", n.prop_left(end, n.cls(D + "."), 3))


def ssn(n: Net) -> None:
    d = n.cls(D)
    for s in "- ":
        sep = n.cls(s)
        core = n.AND(n.run(d, 3), sep.at(3), n.run(d, 2).at(4), sep.at(6), n.run(d, 4).at(7),
                     ~n.cls(D + "-").at(-1), ~n.cls(D + "-").at(11),
                     ~n.cls("9"), ~n.lit("000"), ~n.lit("666"), ~n.lit("00").at(4), ~n.lit("0000").at(7))
        n.out("SSN", n.spread_right(core, 11))


def phone(n: Net) -> None:
    d, nz = n.cls(D), n.cls("23456789")
    sep = n.cls("-. ")
    for paren in (False, True):
        for gap in ((1,) if not paren else (0, 1)):
            if paren:
                area, a_len = [n.cls("("), nz.at(1), d.at(2), d.at(3), n.cls(")").at(4)], 5
            else:
                area, a_len = [nz, d.at(1), d.at(2)], 3
            p = a_len + gap
            terms = area + [nz.at(p), d.at(p + 1), d.at(p + 2), sep.at(p + 3),
                            n.run(d, 4).at(p + 4), ~d.at(p + 8)]
            if gap:
                terms.append((n.cls(" -") if paren else sep).at(a_len))
            raw = n.AND(*terms)
            plain = n.AND(raw, ~n.cls(D + "+-.").at(-1))
            plus1 = n.AND(n.lit("+1"), sep.at(2), raw.at(3), ~n.cls(AN).at(-1))
            one = n.AND(n.cls("1"), n.cls("- .").at(1), raw.at(2), ~n.cls(D + "+-.").at(-1))
            n.out("PHONE", n.spread_right(plain, p + 8))
            n.out("PHONE", n.spread_right(plus1, p + 11))
            n.out("PHONE", n.spread_right(one, p + 10))
    # international: + then at least 8 digits, single separators between digit groups
    plus = n.AND(n.cls("+"), d.at(1), ~n.cls(AN).at(-1))
    joint = n.AND(n.cls(" -.()"), n.OR(d.at(1), n.cls("(").at(1)), n.OR(d.at(-1), n.cls(")").at(-1)))
    body = n.OR(d, joint, force=True)
    span = n.prop_right(plus, body, 4)
    digits_in = n.AND(span, d)
    enough = n.atleast(8, *[digits_in.at(k) for k in range(1, 21)])
    n.out("PHONE", n.prop_right(n.AND(plus, enough), body, 4))


def mac(n: Net) -> None:
    h = n.cls(HEX)
    for s in ":-":
        sp = n.cls(s)
        terms = [~n.cls(HEX + ":-").at(-1), ~n.cls(HEX + ":-").at(17)]
        for g in range(6):
            terms += [h.at(3 * g), h.at(3 * g + 1)]
            if g < 5:
                terms.append(sp.at(3 * g + 2))
        n.out("MAC", n.spread_right(n.AND(*terms), 17))


def credit_card(n: Net) -> None:
    """Layout + issuer prefix + a real Luhn checksum computed in the weights.

    Each digit is embedded as a 9-channel thermometer (value = how many channels fire), once
    plain and once through the Luhn doubling map, so the checksum sum S needs only +1 weights.
    S mod 10 == 0 is tested with one integer 'tent' (three ReLUs) per multiple of ten."""
    d = n.cls(D)
    plain = [n.cls("".join(str(v) for v in range(10) if v >= k)) for k in range(1, 10)]
    dbl = lambda v: 2 * v if v < 5 else 2 * v - 9
    doubled = [n.cls("".join(str(v) for v in range(10) if dbl(v) >= k)) for k in range(1, 10)]
    layouts = {"16": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
               "4-4-4-4": [0, 1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18],
               "15": list(range(15)),
               "4-6-5": [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16]}
    for name, pos in layouts.items():
        L = pos[-1] + 1
        seps = [k for k in range(L) if k not in pos]
        first = n.cls("34" if len(pos) == 15 else "23456")
        shape = n.AND(first, *[d.at(k) for k in pos], *[n.cls(" -").at(k) for k in seps],
                      ~n.cls(D).at(-1), ~n.cls(D).at(L))
        conns = []
        for j, k in enumerate(pos):
            therm = doubled if (len(pos) - 1 - j) % 2 else plain
            conns += [(t.ch, k, 1) for t in therm]
        total = n.neuron(conns, 0, act="relu", tag=("luhn", name))
        tents = []
        for m in range(1, len(pos)):
            c = 10 * m
            tents += [(n.neuron([(total.ch, 0, 1)], -(c - 1), "relu", tag=0).ch, 0, 1),
                      (n.neuron([(total.ch, 0, 1)], -c, "relu", tag=1).ch, 0, -1),
                      (n.neuron([(total.ch, 0, 1)], -c, "relu", tag=2).ch, 0, -1),
                      (n.neuron([(total.ch, 0, 1)], -(c + 1), "relu", tag=0).ch, 0, 1)]
        valid = n.neuron(tents, 0, "clip", tag=("luhn_ok", name))
        n.out("CARD", n.spread_right(n.AND(shape, valid), L))
        n.out("CARD_SHAPE", n.spread_right(shape, L))


SECRET_PARTS = [provider_tokens, jwt, private_key, url_credentials, keyword_assignment, auth_headers,
                aws_secret_near_id]
# Opt-in: unlabelled random values marked only by nearby cue words. Off by default because on the
# dev negatives it costs more false positives than it buys recall (round 3).
CONTEXT_PARTS = [context_secrets]
PII_PARTS = [email, ipv4, ssn, phone, mac, credit_card]


def build(parts=None) -> dict:
    n = Net()
    for part in (parts or SECRET_PARTS + PII_PARTS):
        part(n)
    return n.compile()
