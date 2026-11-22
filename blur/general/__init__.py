"""The general detector: the parts that write circuits, the label priority and the final assembly.

`build()` returns the compiled network as a dict for `blur.engine` and `tools/export_model.py`.
"""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)
from .dates_times import dates, times
from .fields import identifiers, keyed, record_fields, structured, username
from .persons import caseless_names, lexicon, loose_values, name_kind, names
from .places import address, postcode
from .running_text import chains, context, contextual, cookies, defaults, facts, password, prose
from .shapes import email, ids, ip, misc_shapes, national_ids, obfuscation, social, tel
from .vetoes import context_vetoes


def multilingual_part(c):
    if general() and not os.environ.get("NO_ML_NET"):
        from .languages import multilingual
        multilingual(c)


def keys_part(c):
    if general() and not os.environ.get("NO_KEYS_NET"):
        from .context_rules import run as context_rules
        context_rules(c)


def context_part(c):
    if general() and not os.environ.get("NO_CTX_NET"):
        from .frames import context_net
        context_net(c)


PARTS = [context, email, ip, ids, social, tel, misc_shapes, dates, times, postcode, address, username, keyed, multilingual_part,
         lexicon, identifiers, structured, contextual, record_fields, facts, obfuscation, national_ids, caseless_names, cookies, prose, password, chains, defaults, loose_values, names, name_kind, context_part, keys_part]
# when two detectors claim the same characters, the earlier label wins
PRIORITY = ["COOKIE", "SECRET", "PROFILE", "PASS", "EMAIL", "IP", "MAC", "GEOCOORD", "CARD", "IBAN", "BANK", "DRIVERLICENSE", "IDCARD", "TEL", "SOCIALNUMBER", "PASSPORT", "BOD", "DATE",
            "TIME", "SECADDRESS", "STREET", "BUILDING", "STATE", "COUNTRY", "CITY", "POSTCODE", "SEX", "TITLE",
            "ORG", "LASTNAME", "GIVENNAME", "USERNAME", "HEALTH", "FINANCE", "CARD_EXPIRY", "ID", "ADDRESS", "URL"]   # a whole address and a URL are containers: their parts win
# tier 3 is for last-resort guesses


def build() -> dict:
    c = Ctx()
    for part in PARTS:
        part(c)
    n = c.n
    # move the listed labels' shape-only detectors to the "default guess" tier
    for (tier, label) in list(c.m):
        if tier == 0 and label in AMBIGUOUS:
            c.m.setdefault((AMBIGUOUS[label], label), []).extend(c.m.pop((tier, label)))
    if getattr(c, "sure_user", None):          # usernames identified by structure (paths, hostnames) are certain
        c.m.setdefault((0, "USERNAME"), []).extend(c.sure_user)
    if general():
        from ..secrets import circuits
        for part in (circuits.credit_card, circuits.mac, *circuits.SECRET_PARTS):
            part(n)
        if "CARD_SHAPE" in n.outputs:
            n.outputs.pop("CARD", None)
            c.add("CARD", n.OR(*n.outputs.pop("CARD_SHAPE"), force=True), 0)
        if "SECRET" in n.outputs:
            secret = n.OR(*n.outputs.pop("SECRET"), force=True)
            secret = n.AND(secret, ~n.fill(secret, n.AND(secret, c.get("PASS", 1)), 6))
            in_url = n.AND(secret, c.get("URL"))
            past_amp = n.prop_right(n.AND(in_url, n.cls("&")), in_url, 6)
            c.add("SECRET", n.AND(secret, ~past_amp), 0)
        if "MAC" in n.outputs:
            c.add("MAC", n.OR(*n.outputs.pop("MAC"), force=True), 0)
    if hasattr(c, "person_over"):      # a place word that is evidently a person yields before conflicts are resolved
        for key in [k for k in c.m if k[1] in ("CITY", "STATE", "COUNTRY")]:
            c.m[key] = [n.AND(sig, ~c.person_over) for sig in c.m[key]]
    if general() and hasattr(c, "iban"):
        # a whole IBAN outranks the card / phone / national-number shapes found inside it
        for key in list(c.m):
            if key[1] in ("CARD", "TEL", "SOCIALNUMBER", "PASSPORT", "DRIVERLICENSE"):
                c.m[key] = [n.AND(sig, ~c.iban) for sig in c.m[key]]
    # key-aware vetoes act before the tiers are resolved, so a vetoed claim does not block the right label
    if general() and getattr(c, "pre_cut", None):
        for (tier, label) in list(c.m):
            if label in c.pre_cut:
                # a claim that runs across "&key=" ends there; the next parameter's own claims are untouched
                c.m[(tier, label)] = [n.AND(sig, ~n.prop_right(n.AND(c.pre_cut_mark, sig, sig.at(-1)), sig, 7)) for sig in c.m[(tier, label)]]
    if general() and getattr(c, "key_veto", None):
        bad_cache = {}
        for (tier, label) in list(c.m):
            if label in c.key_veto:
                # a span with any vetoed byte goes whole: one flood over all claims of the label (cookies, confined to
                # their values by key_only below, lose only the vetoed bytes)
                if True:
                    if label not in bad_cache:
                        U = n.OR(*[s for (t2, l2), v2 in c.m.items() if l2 == label for s in v2], force=True)
                        hit = n.AND(U, c.key_veto[label])
                        if label in ("GIVENNAME", "LASTNAME") and hasattr(c, "name_framed"):
                            hit = n.AND(hit, ~c.name_framed)          # a role or description frame outranks word-level doubts
                        bad_cache[label] = n.fill(U, hit, 6)
                    c.m[(tier, label)] = [n.AND(sig, ~bad_cache[label]) for sig in c.m[(tier, label)]]
            if label in getattr(c, "key_only", {}):
                c.m[(tier, label)] = [n.AND(sig, c.key_only[label]) for sig in c.m[(tier, label)]]
    # the network's "this is not a ..." decisions, exported for the pipeline so that its own rules respect them
    # (only the context decisions - documentation, fiction, projects, versions, workflow references, placeholders - not the
    #  structural vetoes, which the pipeline's own key logic handles)
    if general() and getattr(c, "ctx_not", None):
        for k, sig in c.ctx_not.items():
            n.out("_NOT_" + k, sig)
    if os.environ.get("DBG_M"):
        for (t_, l_), v_ in list(c.m.items()):
            n.out("dbgm_%d_%s" % (t_, l_), n.OR(*v_, force=True))
    taken, finals = [], {}
    for tier in (0, 1, 2, 3):
        for label in PRIORITY:
            if (tier, label) not in c.m:
                continue
            mask = n.OR(*c.m[(tier, label)], force=True)
            if tier >= 2 and label not in ("PASS", "USERNAME"):
                kv = n.AND(c.key, ~c.key_exempt) if hasattr(c, "key_exempt") and label in ("_NAME", "GIVENNAME", "LASTNAME") else c.key
                mask = n.AND(mask, ~kv, ~c.tag)
            finals.setdefault(label, []).append(n.AND(mask, *[~t for t in taken]) if taken else mask)
            taken.append(mask)
    sp = n.cls(" ")
    out = {}
    url_whole = n.OR(*[sig for (t, l), v in c.m.items() if l == "URL" for sig in v], force=True) if any(l == "URL" for _, l in c.m) else None
    cv = context_vetoes(c) if general() else {}
    for label, sigs in finals.items():
        m = n.OR(*sigs, force=True)
        if general() and label in cv:
            hit = n.AND(m, cv[label])
            if label in ("GIVENNAME", "LASTNAME") and hasattr(c, "name_framed"):
                hit = n.AND(hit, ~c.name_framed)
            m = n.AND(m, ~n.fill(m, hit, 6))
        if general() and label in ("SECRET", "PASS", "ID", "IDCARD", "PASSPORT", "DRIVERLICENSE"):
            # completeness: a secret or a code is masked as a whole token, never in part ("Crimson#[...]", "SunnyField[...]")
            allb_ = "".join(chr(i) for i in range(1, 256))
            stop = " \t\n\"'`,;&()[]{}<>|:=?@" + ("" if label in ("SECRET", "PASS") else "/_.")      # ids end at "_" / "." (file names)
            # ASCII and two-byte (accented Latin, Cyrillic) characters only: CJK text has no spaces, so it never joins a token
            asc_ok = n.cls("".join(ch for ch in allb_ if ch not in stop and ord(ch) < 0x80))
            lead2 = n.cls("".join(chr(i) for i in range(0xC2, 0xE0)))
            tokc = n.OR(asc_ok, lead2, n.AND(n.cls("".join(chr(i) for i in range(0x80, 0xC0))), lead2.at(-1)), force=True)
            whole = n.fill(tokc, n.AND(tokc, m), 6)
            whole = n.AND(whole, ~n.AND(n.cls(".!?"), ~tokc.at(1), n.cls(AN).at(-1)) if label not in ("SECRET", "PASS") else
                          ~n.AND(n.cls("."), ~tokc.at(1)))                               # a sentence's full stop is not part of it
            pad = n.prop_right(n.AND(n.cls("="), whole.at(-1)), n.cls("="), 2)               # base64 padding "...=="
            m = n.OR(m, whole, pad, force=True)
            if label in ("SECRET", "PASS"):
                # a value runs past a space only inside quotes ("'P@ss w0rd!'"); otherwise it ends at the first space
                q_open = n.fill(m, n.AND(m, ~m.at(-1), n.cls("'\"`").at(-1)), 6)
                after_sp = n.prop_right(n.AND(n.cls(" "), m), m, 7)
                block = n.fill(m, n.AND(m, n.cls("\n")), 7)                       # a PEM block spans lines and spaces
                # a phrase of 3+ lower-case words is one secret (a seed or recovery phrase)
                wordsp = n.OR(n.cls(LO), n.AND(n.cls(" "), n.cls(LO).at(-1), n.cls(LO).at(1)), force=True)
                only_words = n.AND(m, ~n.fill(m, n.AND(m, ~wordsp), 7))
                two_sp = n.fill(m, n.AND(m, n.cls(" "), n.spread_right(n.AND(m, n.cls(" ")), 40).at(-1)), 7)
                phrase = n.OR(n.AND(only_words, two_sp), *([n.fill(m, n.AND(m, c.phrase_secret), 7)] if hasattr(c, "phrase_secret") else []), force=True)
                m = n.OR(n.AND(m, q_open), n.AND(m, block), n.AND(m, ~after_sp), n.AND(m, phrase), force=True)
        if general() and label in getattr(c, "key_trim", {}):
            m = n.AND(m, ~c.key_trim[label])
        if general():
            if label == "EMAIL":
                m = n.AND(m, ~n.fill(m, n.AND(m, ~m.at(-1), n.cls("@")), 6))
            if label in ("PASS", "SECRET", "ID", "USERNAME", "COOKIE"):
                # a value needs at least three letters or digits ("," or ":" alone is never a secret)
                pair = n.AND(m, n.cls(AN), m.at(1), n.cls(AN).at(1))
                m = n.AND(m, n.fill(m, pair, 6))
            if label in ("ID", "CARD", "TEL", "SOCIALNUMBER"):
                masked_already = n.OR(n.lit("XXX"), n.lit("xxx"), n.lit("***"), n.lit("###"), n.lit("REDACTED"))
                m = n.AND(m, ~n.fill(m, n.AND(m, masked_already), 6))
            if label in ("ID", "POSTCODE", "TEL", "SOCIALNUMBER", "CARD"):
                # placeholder numbers: 1234, 12345, 123456, 123456789, 0000 ...
                # only when the placeholder is the whole value
                ph = n.OR(*[n.AND(n.lit(x), ~m.at(-1), ~m.at(len(x))) for x in
                            ("1234", "12345", "123456", "0000", "00000", "000000", "111111")])
                m = n.AND(m, ~n.fill(m, n.AND(m, ph), 6))
            if label in ("ADDRESS", "STREET", "CITY", "STATE", "BUILDING", "POSTCODE", "SECADDRESS"):
                # an address never ends in punctuation: "..., Madrid." keeps its full stop
                ac = n.cls(AN + "".join(chr(i) for i in range(0x80, 0x100)))
                m = n.AND(m, ~n.AND(n.cls(".,;:"), ~n.AND(m.at(1), ac.at(1)), ~n.AND(m.at(2), ac.at(2))))
            if label in ("CITY", "STATE", "COUNTRY") and hasattr(c, "person_over"):
                m = n.AND(m, ~c.person_over)
            if label in ("ID", "IP", "CARD", "DRIVERLICENSE", "PASSPORT", "POSTCODE", "BUILDING", "TEL"):
                m = n.AND(m, ~n.fill(m, n.AND(m, c.not_personal), 6))       # order numbers, versions, timestamps ...
                m = n.AND(m, ~c.vat)
            if label in ("USERNAME", "GIVENNAME", "LASTNAME", "CITY", "STATE", "ID", "PASS"):
                m = n.AND(m, ~n.fill(m, n.AND(m, n.OR(c.sym, c.sym.at(-1), c.sym.at(1))), 6))   # "₹48" is not a word
        out[label] = n.AND(m, ~n.AND(sp, ~m.at(1)), ~n.AND(sp, ~m.at(-1)))
        if label == "ORG" and general() and hasattr(c, "child_ctx"):
            sw = n.OR(*[n.AND(n.lit(w), ~c.wordc.at(-1), ~c.wordc.at(len(w))) for w in
                        ("School", "Primary", "Preschool", "Vidyalaya", "Academy", "Kindergarten", "Montessori", "Elementary",
                         "Nursery", "High")])
            n.out("SCHOOL", n.AND(out[label], n.fill(out[label], n.AND(out[label], sw), 6), c.child_ctx))
        if label in ("URL", "STREET", "BUILDING") and general():
            continue                       # written below
        n.out(label, out[label])
    if general():
        # a URL is reported whole (its personal parts are reported as well, under their own labels)
        if url_whole is not None:
            n.out("URL", url_whole)
        # a street is reported with its house number: "1027 Leo Ln"
        st, bd = out.get("STREET"), out.get("BUILDING")
        if st is not None and bd is not None:
            bd_end = n.AND(bd, ~bd.at(1))
            join = n.OR(n.AND(sp, bd.at(-1), st.at(1)), n.AND(n.cls(","), bd.at(-1), sp.at(1), st.at(2)),
                        n.AND(sp, n.cls(",").at(-1), bd.at(-2), st.at(1)))
            run = n.OR(st, bd, join, force=True)
            full = n.fill(run, n.AND(run, st), 6)
            n.out("STREET", full)
            n.out("BUILDING", n.AND(bd, ~full))
        else:
            for k in ("STREET", "BUILDING"):
                if k in out:
                    n.out(k, out[k])
    if general():
        # overlay: a whole postal address as one span (its parts keep their own labels as well)
        parts = n.OR(*[out[k] for k in ("BUILDING", "STREET", "SECADDRESS", "CITY", "STATE", "POSTCODE", "COUNTRY") if k in out], force=True)
        comma = n.cls(",")
        glue = n.OR(n.AND(comma, parts.at(-1), sp.at(1), parts.at(2)), n.AND(sp, comma.at(-1), parts.at(-2), parts.at(1)),
                    n.AND(sp, parts.at(-1), parts.at(1)))
        run = n.OR(parts, glue, force=True)
        # a full address needs a number in it (house number, flat, postcode): "MG Road, Bengaluru" is only a place
        home = n.prop_right(n.AND(n.cls(UP + D), said(c, ["house on", "lives on", "live on", "living on", "resides on",
                                                            "resides at", "lives at", "home on", "flat on", "stays on"], loose=True)),
                            n.cls(AN + " ,.-"), 5)
        anchor = n.OR(*[out[k] for k in ("BUILDING", "SECADDRESS", "POSTCODE") if k in out],
                      *([n.AND(out["STREET"], home)] if "STREET" in out else []), force=True)
        n.out("ADDRESS", n.OR(n.fill(run, n.AND(run, anchor), 6), c.addr_said))
    if general() and hasattr(c, "literal_password"):
        # Preserve the network's final, accepted literal boundaries in the JS
        # pipeline. Rejected placeholders do not receive this auxiliary signal.
        n.out("_SECRET_LITERAL", n.AND(c.literal_password, out["SECRET"]))
    return n.compile()
