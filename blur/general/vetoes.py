"""Context vetoes: shapes and contexts in which a label claim is withdrawn."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)


def context_vetoes(c: Ctx):
    """General profile. Context that makes a candidate not personal data, per output label."""
    n = c.n
    letter, d, sp = n.cls(AL + HI), n.cls(D), n.cls(" ")
    word = n.cls(AL + HI + "'.-")
    def words(ws, nocase=True):
        return n.OR(*[n.AND(n.lit(w if w.isascii() else u(w), nocase=nocase), ~letter.at(-1), ~letter.at(len(w.encode())))
                      for w in ws])
    v = {}
    # role mailboxes: the local part is made only of role words ("hr-helpdesk@", "no-reply@")
    lp = n.cls(AN + "._%+-")
    role = n.fill(n.cls(AL), words(ROLE_MAILBOX), 4)
    role_or_sep = n.OR(role, n.cls("._-"), force=True)
    full_role = n.prop_left(n.AND(role_or_sep, n.cls("@").at(1)), role_or_sep, 5)
    # (every e-mail address is masked, role mailboxes included: the address still reveals the organisation and is
    #  personal data under most policies)
    # placeholder and toll-free numbers, test cards, partly shown cards
    zeros = n.OR(n.lit("000 0000"), n.lit("0000 0000"), n.lit("00000000"), n.lit("000-0000"), n.lit("0000-0000"))
    # (the owner's guide: documented test cards and toll-free numbers are still masked in real data)
    for lab in ("TEL", "ID", "SOCIALNUMBER", "IDCARD"):
        v[lab] = zeros
    # names: date words next to numbers, modal verbs, officials in their role, placeholder names, CamelCase products
    md = n.fill(letter, words(MONTHS_DAYS), 4)
    md_start = n.AND(md, ~md.at(-1))
    md_end = n.AND(md, ~md.at(1))
    wd = n.fill(letter, words(MONTHS_DAYS[-17:]), 4)               # weekdays: "Thu, Nov 19"
    wd_end = n.AND(wd, ~wd.at(1))
    near_num = n.OR(n.AND(md_start, n.OR(d.at(-2), d.at(-3), n.AND(n.cls(",").at(-1), d.at(-2)))),
                    n.AND(md_end, n.OR(d.at(2), d.at(3), n.AND(n.cls(",").at(1), sp.at(2), d.at(3)))),
                    n.AND(wd_end, n.cls(",").at(1), sp.at(2), md.at(3)), n.AND(wd_end, sp.at(1), md.at(2)))
    date_word = n.fill(md, near_num, 4)
    modal = n.AND(n.OR(n.lit("Will "), n.lit("May "), n.lit("Can "), n.lit("Shall ")), ~letter.at(-1),
                  n.OR(n.cls(" \n").at(-1), n.cls(".:!?\n").at(-2), n.cls("\n").at(-1)))
    modal_next = [n.AND(modal, n.cls("abcdefghijklmnopqrstuvwxyz").at(k + 1), ~n.cls(AL).at(k + 1).at(0) if False else modal)
                  for k in (4, 3, 4, 5)]
    # a modal is followed by a bare verb; a person by a finite verb ("Will said", "May joined")
    ed_word = n.fill(letter, n.AND(n.lit("ed"), ~letter.at(2)), 4)
    finite = n.OR(ed_word, words(["said", "says", "told", "was", "is", "has", "had", "went", "wrote", "and", "from", "made",
                                  "came", "took", "gave", "sent", "left", "got", "thinks", "thought", "knows", "will",
                                  "would", "also", "who", "here", "at", "in", "on", "of", "with", "for", "by", "to", "about",
                                  "via", "and", "or", "from", "is"]), force=True)
    lw = n.cls("abcdefghijklmnopqrstuvwxyz")
    m_will = n.AND(n.lit("Will "), lw.at(5), ~finite.at(5))
    m_may = n.AND(n.lit("May "), n.OR(n.AND(lw.at(4), ~finite.at(4)), n.lit("I ").at(4), n.lit("we ").at(4)))
    m_can = n.AND(n.lit("Can "), n.OR(n.AND(lw.at(4), ~finite.at(4)), n.lit("I ").at(4)))
    modal_v = n.fill(letter, n.AND(n.OR(m_will, m_may, m_can), ~letter.at(-1)), 3)
    namerun = n.OR(n.cls(AL + HI + "."), n.AND(sp, n.cls(UP).at(1)), force=True)
    role_start = n.AND(n.cls(UP), said(c, PUBLIC_ROLES))
    public = n.prop_right(role_start, namerun, 5)
    phn = n.OR(*[n.lit(x, nocase=True) for x in PLACEHOLDER_NAMES if x.isascii()])
    phn_span = n.fill(n.OR(letter, n.cls(". "), force=True), n.AND(phn, ~letter.at(-1)), 4)
    camel = n.fill(letter, n.AND(n.cls(LO), n.cls(UP).at(1), ~name_prefix_step(c).at(1)), 4)   # (not "McKenzie", "DeLuca")
    # a name inside a firm's name: "Iyer & Co.", "Lopez & Partners LLP", "Mehta Pvt Ltd"
    orgtail = n.OR(*[n.lit(t) for t in (" & ", " Co.", " Co ", " Ltd", " LLP", " LLC", " Inc", " Pvt", " Chartered", " Sons",
                                        " Associates", " Partners", " Brothers", " Holdings", " GmbH", " PLC")])
    firm = n.fill(n.cls(AL + "'-"), n.AND(letter, orgtail.at(1)), 4)
    # plural nationality / group nouns: "Indians", "Americans", "Europeans"
    demonym = n.fill(letter, n.AND(n.OR(n.lit("ians"), n.lit("eans"), n.lit("ese")), ~letter.at(4).at(0) if False else n.cls(UP).at(-3),
                                   ~letter.at(4)), 4)
    demonym = n.OR(n.fill(letter, n.AND(n.lit("ians"), ~letter.at(4)), 4), n.fill(letter, n.AND(n.lit("eans"), ~letter.at(4)), 4),
                   words(["Americans", "Germans", "Mexicans", "Africans", "Pakistanis", "Bangladeshis", "Nepalis", "Afghans",
                          "Chinese", "Japanese", "Muslims", "Hindus", "Christians", "Sikhs", "Jews", "Dalits", "Arabs",
                          "Kashmiris", "Punjabis", "Gujaratis", "Bengalis", "Tamils", "Marathis"], nocase=False), force=True)
    # a capitalised common word (Grace, Hope, Will, May, Rose, Mark, Bill ...) is a person only when used as one: a lower-case
    # word right after it must be a verb or a preposition ("Grace from legal", "Rose covers"), not a noun ("Grace period")
    # or a pronoun ("Hope you're", "Will you"); three or more of them in a list are words being talked about
    capw = n.fill(letter, n.AND(n.cls(UP), ~letter.at(-1)), 4)
    hom = n.AND(c.english, c.lex_given_amb, capw)          # common words that are also first names
    hom_s, hom_e = n.AND(hom, ~hom.at(-1)), n.AND(hom, ~hom.at(1))
    s_verb = n.AND(n.fill(letter, n.AND(n.cls("s"), ~letter.at(1), letter.at(-1), letter.at(-2), letter.at(-3)), 4),
                   ~words(["this", "thus", "plus", "less", "unless", "ours", "yours", "always", "perhaps", "towards", "news"]))
    verbish = n.OR(finite, s_verb, force=True)
    hom_noun = n.fill(letter, n.AND(hom_e, sp.at(1), lw.at(2), ~verbish.at(2)), 4)
    many = n.atleast(3, *[hom_s.at(k) for k in range(-40, 41)])
    listed = n.fill(letter, n.AND(many, n.OR(n.AND(hom_e, n.OR(n.cls(",").at(1), n.lit(" and ").at(1), n.lit(" or ").at(1))),
                                             n.AND(hom_s, n.OR(n.lit(", ").at(-2), n.lit("and ").at(-4), n.lit("or ").at(-3))))), 4)
    prep = words(["by", "in", "on", "until", "till", "since", "before", "after", "during", "from", "to", "of", "next", "last",
                  "this", "every", "early", "mid", "late", "through", "throughout"])
    prep_before = n.OR(*[n.AND(n.lit(w, nocase=True).at(-(len(w) + 1)), ~letter.at(-(len(w) + 2))) for w in
                         ("by", "in", "on", "until", "till", "since", "before", "after", "during", "from", "to", "of", "next", "last",
                          "this", "every", "early", "mid", "late", "through", "throughout")])
    month_after_prep = n.fill(letter, n.AND(md_start, sp.at(-1), prep_before), 4)
    names_v = n.OR(date_word, modal_v, public, phn_span, camel, firm, demonym, hom_noun, listed, month_after_prep, force=True)
    if hasattr(c, "lc_unsupported"):
        lcu = n.AND(c.lc_unsupported, ~c.greeted_lc) if hasattr(c, "greeted_lc") else c.lc_unsupported
        names_v = n.OR(names_v, lcu, c.hindi_fw, force=True)
    # a word built on an English contraction is never a name: Don'ts, Can't, They'll, We've, I'd, I'm (not O'Brien, D'Souza)
    al = n.cls(AL)
    contr = n.OR(n.lit("n't", nocase=True), *[n.AND(n.lit(x, nocase=True), ~al.at(len(x))) for x in ("'ll", "'re", "'ve", "'d", "'m")],
                 n.lit(u("n’t")), force=True)
    names_v = n.OR(names_v, n.fill(n.cls(AL + "'\xe2\x80\x99"), contr, 4), force=True)
    # reference namespaces: CVE-2024-3094, CWE-79, GHSA-..., RFC 9110, ISBN ...
    refns = n.fill(n.cls(AN + "-"), n.AND(n.OR(*[n.lit(x) for x in ("CVE-", "CWE-", "GHSA-", "RFC", "ISBN", "ISSN", "DOI", "PMID",
                                                                     "KB", "MS-", "RHSA-", "USN-", "DSA-", "OSV-", "INC-", "INC0",
                                                                     "CHG-", "CHG0", "PRB-", "PRB0", "REQ-", "RITM", "SR-", "TKT-",
                                                                     "BUG-", "OPS-", "SEC-", "SRE-", "JIRA-", "TICKET-", "CASE-", "PIR-",
                                                                     "RCA-", "PM-", "ADR-", "RFC-", "EPIC-", "STORY-", "TASK-")]),
                                          ~n.cls(AN).at(-1)), 5)
    v["ID"] = n.OR(v.get("ID", zeros), refns, force=True)
    # cookies need cookie context on their line (a header, attributes, or a cookie jar)
    nonl = n.cls("".join(chr(i) for i in range(1, 256) if chr(i) != "\n"))
    ck = n.OR(n.lit("ookie", nocase=True), n.lit("Path=", nocase=True), n.lit("HttpOnly", nocase=True), n.lit("Expires=", nocase=True),
              n.lit("SameSite", nocase=True), n.cls("\t"),
              # a jar of pairs on one line: "a=1; b=2"
              n.AND(n.cls(";"), n.cls(" ").at(1), n.cls(AN + "_").at(2), n.atleast(1, *[n.cls("=").at(k) for k in range(3, 34)])))
    cookie_line = n.OR(n.prop_right(ck, nonl, 8), n.prop_left(ck, nonl, 8))
    v["COOKIE"] = n.AND(nonl, ~cookie_line)
    v["GIVENNAME"] = names_v
    v["LASTNAME"] = names_v
    # usernames and passwords that are amounts, file names, measurements or dates
    cur = n.OR(n.lit(u("£")), n.lit(u("€")), n.lit(u("¥")), n.cls("$"))
    amt = n.prop_right(n.OR(n.AND(d, cur.at(-1), ~n.cls(AN + "$").at(-2)),
                            n.AND(d, n.cls(" ").at(-1), cur.at(-2), ~n.cls(AN + "$").at(-3)),          # "$ 48"
                            n.AND(d, n.cls(" ").at(-1), n.cls(" ").at(-2), cur.at(-3), ~n.cls(AN + "$").at(-4))),
                       n.cls(D + ".,"), 4)
    amount = n.prop_left(n.AND(amt, ~amt.at(1), ~n.cls("$" + AL).at(1)), amt, 4)     # "$6$rounds=..." is a hash
    fext = n.AND(n.cls("."), n.OR(*[n.AND(n.lit(e), ~n.cls(AN).at(len(e))) for e in
                 ("csv", "json", "txt", "log", "py", "ini", "yaml", "yml", "xml", "pdf", "docx", "xlsx", "png", "jpg", "zip",
                  "gz", "tar", "sql", "md", "html", "js", "env", "conf", "cfg")]).at(1))
    filename = n.fill(n.cls(AN + "._-"), fext, 5)
    measure = c.P(r"\d+(\.\d+)?(m|ms|s|km|kmph|kmh|mph|kg|g|mb|gb|kb|tb|mm|cm|px|hz|khz|mhz|ghz|v|w|kw|mah|rpm|min|h|hr|hrs|x|MB|GB|KB|TB|ms|Hz|GHz|MHz)",
                  pre=WORD + "-_/+", post=WORD + "-_/+")[0]                # a whole token, never the tail of a longer value
    date_tok = c.P(r"\d{1,2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2,4}", pre=WORD, post=WORD)[0]
    ua = c.P(r"[A-Za-z]{2,}/\d+(\.\d+)+", pre=WORD, post=WORD)[0]                  # "Mozilla/5.0", "curl/8.4.0"
    urlish = n.spread_right(n.lit("://"), 3)        # a value that itself contains "://" is a URL (a password inside one does not)
    junk = n.OR(amount, filename, measure, date_tok, ua, urlish, force=True)
    if hasattr(c, "hindi_fw"):
        junk = n.OR(junk, c.hindi_fw, force=True)
    for lab in ("USERNAME", "PASS", "COOKIE", "SECRET"):
        # File/word/measurement shapes do not invalidate an explicitly quoted
        # password. In particular, ordinary words can be part of a passphrase.
        scoped_junk = n.AND(junk, ~c.literal_password) if lab in ("PASS", "SECRET") and hasattr(c, "literal_password") else junk
        v[lab] = n.OR(scoped_junk, v.get(lab), force=True) if lab in v else scoped_junk
    # well-known product and vault names are not passwords
    v["PASS"] = n.OR(v["PASS"], n.fill(n.cls(AN), n.AND(n.lit("1Password"), ~n.cls(AN).at(-1)), 4), force=True)
    return v
