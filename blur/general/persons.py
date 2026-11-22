"""Personal names: the name lexicons, lower-case and caseless names, and the name kind."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)


def all_sur_ranked(here):
    """Surnames in frequency order (US Census 2010 list is stored most-frequent first)."""
    p = os.path.join(here, "surnames_ranked.txt")
    return open(p).read().split() if os.path.exists(p) else []


def lexicon(c: Ctx):
    """c.english: common English words (SCOWL). c.lex_given / c.lex_sur: frequent given names
    and surnames from a CC0 public list (they add recall for ordinary names in running text)."""
    here = DATA_DIR
    size = int(os.environ.get("LEX", "35" if general() else "20"))
    words = set(open(os.path.join(here, f"words{size}.txt")).read().split()) | set(EXTRA_WORDS)
    # everyday abbreviations and loan words that the lexicon lacks but that are not names by themselves; they join the
    # ordinary words before the name lists are split, so "Max" is an ambiguous name (confirmed by "Max Weber"), not a dead one
    words |= {"max", "min", "avg", "approx", "misc", "info", "chai", "masala", "pesto", "tapas", "sushi"}
    common = set(open(os.path.join(here, "words50.txt")).read().split()) | words   # names that are also words are dropped
    given = set(open(os.path.join(here, "given.txt")).read().split()) - common
    sur = set(open(os.path.join(here, "surnames.txt")).read().split()) - common
    all_given = set(open(os.path.join(here, "given.txt")).read().split())
    all_sur = set(open(os.path.join(here, "surnames.txt")).read().split())
    words = sorted(words)
    c.english = word_tree(c, words)
    c.lex_given = word_tree(c, given)
    c.lex_sur = word_tree(c, sur)
    if general():
        top_sur = set(all_sur_ranked(here)[:3000])
        c.lex_given_amb = word_tree(c, (all_given & common) - NOT_NAMES, first_upper=True)
        c.lex_given_amb_any = word_tree(c, (all_given & common) - NOT_NAMES)       # the same names in any case ("hi john")
        c.lex_sur_amb = word_tree(c, (top_sur & common) | (all_sur & common & all_given), first_upper=True)


def loose_values(c: Ctx):
    """Weak guesses that need the lexicon: a lowercase non-word standing as a value is a
    username; a lone M / F / O standing as a value is a sex."""
    n = c.n
    sp = n.cls(" ")
    low, low_end = c.P(r"[\l]{4,}", pre=WORD + "@._-:/<\\", post=WORD + "@_.-")
    start = n.AND(low, ~low.at(-1), c.any_value)
    ends = n.AND(low_end, ~n.AND(sp.at(1), n.cls(LO).at(2)))
    c.add("USERNAME", n.AND(n.fill(low, start), n.fill(low, ends), ~c.english, ~c.key), 3)
    title = c.get("TITLE")
    pre_ok = n.OR(n.cls("\"'[>*`(").at(-1), n.AND(sp.at(-1), ~c.wordc.at(-2)), n.AND(sp.at(-1), title.at(-2)))
    post_ok = n.cls("\"']<*`), \n\r\\").at(1)
    c.add("SEX", n.AND(n.cls("MFO"), ~c.W.at(-1), ~c.W.at(1), pre_ok, post_ok, ~c.key, ~n.cls(".:").at(1),
                       ~n.AND(n.cls("'").at(1), n.cls(AL).at(2))), 3)


def caseless_names(c: Ctx):
    """General profile. Scripts without capital letters (Devanagari, Tamil, Arabic, CJK ...) need other cues: a key word for
    "name" in that language, or a grammatical marker that follows a person (Hindi agent marker "ने", honorific "जी",
    Japanese "さん", Korean "님", Hindi "श्री"/"श्रीमती" before a name)."""
    if not general():
        return
    n = c.n
    hi = n.cls(HI)
    sp = n.cls(" ")
    hstart = n.AND(hi, ~hi.at(-1), ~n.cls(AL + D).at(-1))
    htok = n.prop_right(hstart, hi, 5)
    hend = n.AND(htok, ~hi.at(1))
    # key words for "name" in several languages, followed by up to three case-less words
    kv = n.OR(*[n.lit(w) for w in (u("नाम"), u("पूरा नाम"), u("பெயர்"), u("নাম"), u("ಹೆಸರು"), u("పేరు"), u("ਨਾਮ"), u("名前"),
                                    u("姓名"), u("이름"), u("اسم"), u("имя"), u("Имя"))])
    after = n.prop_right(kv, n.OR(hi, n.cls(" :-\t"), force=True), 4)
    v1 = n.AND(hstart, after.at(-1), ~kv)
    w1 = n.prop_right(v1, hi, 5)
    w2 = n.prop_right(n.AND(hstart, sp.at(-1), w1.at(-2)), hi, 5)
    c.add("_NAME", n.OR(w1, w2), 1)
    # a case-less word (or two) right before a person marker
    markers = [u(" ने "), u(" जी"), u("さん"), u("様"), u("님"), u(" साहब"), u(" بن ")]
    mark = n.OR(*[n.lit(m) for m in markers])
    nm1 = n.fill(htok, n.AND(hend, mark.at(1)), 5)
    nm2 = n.fill(htok, n.AND(hend, sp.at(1), n.AND(nm1, hstart).at(2)), 5)
    pre = n.OR(*[n.lit(u(w) + " ").at(-len(u(w)) - 1) for w in ("श्री", "श्रीमती", "डॉ.", "कुमारी")])
    nm3 = n.fill(htok, n.AND(hstart, pre), 5)
    after_bin = n.fill(htok, n.AND(hstart, n.lit(u(" بن ")).at(-len(u(" بن ")))), 5)
    c.add("_NAME", n.OR(nm1, nm2, nm3, after_bin), 1)


def names(c: Ctx):
    """Names are an open vocabulary (almost every one in the data is unique), so they are found
    by position (after a title, alone inside quotes/brackets/tags/bold, in comma lists, as the
    value of a key) and by not being a common English word. A run of capitalised words that
    contains an ordinary word is a phrase, not a name."""
    n = c.n
    lower2 = n.OR(n.cls(LO + HI).at(1), n.AND(n.cls("'").at(1), n.cls(UP).at(2)))
    comma, sp = n.cls(","), n.cls(" ")
    q_open = n.cls("\"'[`").at(-1)
    q_close = n.OR(n.cls("\"']`").at(1), n.AND(n.cls(",.").at(1), n.cls("\"']`").at(2)))
    m_open, m_close = n.cls(">*").at(-1), n.cls("<*").at(1)
    tok_end = n.AND(c.cap, ~c.wordc.at(1))
    wst = n.AND(c.wstart, lower2)
    quoted = n.AND(n.fill(c.cap, n.AND(wst, q_open)), n.fill(c.cap, n.AND(tok_end, q_close)))
    marked = n.AND(n.fill(c.cap, n.AND(wst, m_open)), n.fill(c.cap, n.AND(tok_end, m_close)), ~c.key)
    listed = n.AND(n.fill(c.cap, n.AND(wst, sp.at(-1), comma.at(-2))), n.fill(c.cap, n.AND(tok_end, comma.at(1))), ~c.key)
    joint = n.AND(sp, c.cap.at(-1), c.wstart.at(1))
    body = n.OR(c.cap, joint, force=True)
    b_open, b_close = n.cls("[*").at(-1), n.cls("]*").at(1)
    seq = n.AND(n.prop_right(n.AND(wst, b_open), body, 5), n.prop_left(n.AND(tok_end, b_close), body, 5), c.cap, ~c.key)
    if general():
        tv = c.title_vocab
        eng_cap = n.AND(c.cap, c.english, ~tv)
        nb = n.OR(n.AND(tv, ~tv.at(1), sp.at(1), eng_cap.at(2)), n.AND(tv, ~tv.at(-1), sp.at(-1), eng_cap.at(-2)))
        c.add("TITLE", n.AND(tv, ~n.fill(tv, nb, 4)))
    title = c.get("TITLE")
    t1 = n.fill(c.cap, n.AND(wst, sp.at(-1), title.at(-2)))
    t2 = n.fill(c.cap, n.AND(wst, sp.at(-1), t1.at(-2)))
    # value of any key ("Student 6: Kanesu"), or a numbered list line ("7. Bréville Ballim")
    after_key = n.prop_right(c.key, c.skip, 3)
    d, dot = n.cls(D), n.cls(".")
    numbered = n.AND(sp.at(-1), dot.at(-2), d.at(-3))
    chain = [n.fill(c.cap, n.AND(wst, n.OR(n.AND(after_key.at(-1), ~c.key.at(-1)), numbered)))]
    for _ in range(3):
        chain.append(n.fill(c.cap, n.AND(wst, sp.at(-1), chain[-1].at(-2))))
    # part of running text: followed by a space and a lowercase word
    in_sentence = n.fill(c.cap, n.AND(tok_end, sp.at(1), n.cls(LO).at(2)))
    valued = n.AND(n.OR(*chain, *c.generic_names), ~in_sentence, ~c.key)
    # phrase veto: any ordinary (non-title) word in the same run of capitalised words
    phrase = n.AND(n.fill(body, n.AND(c.cap, c.english, ~title), 5), n.fill(body, joint, 5))
    camel = n.fill(c.cap, n.AND(c.cap, n.cls(UP), n.cls(LO).at(-1), ~name_prefix_step(c)))   # (not "McKenzie", "DeLuca")
    proper = n.fill(c.cap, wst)                                  # capitalised, second letter lowercase
    def ends_like_name(tok, tok_end_sig):
        hits = []
        for e in sorted(set(NAME_ENDINGS)):
            L = len(e)
            hits.append(n.AND(n.lit(e).at(-(L - 1)), tok_end_sig, n.run(n.cls(AL + HI), L + 2).at(-(L + 1))))
        return n.fill(tok, n.AND(tok, n.OR(*hits)), 4)
    ORGW = ("County", "&", "Inc", "LLC", "Ltd", "Group", "Corp", "University", "Street", "Road", "Avenue", "Media", "Realty",
            "Logistics", "Solutions", "Bank", "Hospital", "College", "School", "Institute", "Memorial", "Airport", "Motors",
            "Foundation", "Trust", "Station", "Stadium", "Museum", "Park", "Bridge", "Hall", "Centre", "Center", "Airlines",
            "Industries", "Enterprises", "Technologies", "Labs", "Pharma", "Steel", "Power", "Holdings", "Capital", "Partners",
            "Associates", "Clinic", "Library", "Award", "Prize", "Medal", "Lecture", "Fellowship", "Scholarship", "Chair",
            "Nagar", "Marg", "Chowk", "Colony", "Layout", "Cross", "Main", "Square", "Hotel", "Hotels", "Resort", "Restaurant",
            "Cafe", "Mall", "Temple", "Church", "Mosque", "Gurudwara", "Mahal", "Bhavan", "Palace", "Market", "Hall", "Club")
    org_word = n.OR(*[n.AND(n.lit(w), ~c.wordc.at(-1), ~c.wordc.at(len(w))) for w in ORGW])
    org_run = n.fill(body, n.AND(body, org_word), 5)
    is_org = n.fill(c.cap, n.AND(c.cap, org_run))
    caps = n.fill(c.cap, n.AND(c.wstart, n.cls(UP).at(1), n.cls(UP).at(2)))     # JOHN SMITH
    lists = [c.lex_given, c.lex_sur] + ([c.lex_given_amb, c.lex_sur_amb] if general() else [])
    caps_word = n.AND(caps, ~c.english)
    caps_pair = n.OR(n.fill(c.cap, n.AND(tok_end, sp.at(1), n.AND(caps_word, c.wstart).at(2))), n.fill(c.cap, n.AND(c.wstart, sp.at(-1), caps_word.at(-2))))
    caps_named = n.AND(caps, n.OR(n.AND(n.OR(*lists), n.fill(c.cap, n.AND(c.wstart, n.run(n.cls(UP), 4)))), n.AND(caps_word, caps_pair)))
    nameable = n.OR(proper, caps_named) if general() else proper
    g_known = n.AND(c.lex_given, nameable)
    after_g = n.fill(c.cap, n.AND(c.wstart, sp.at(-1), g_known.at(-2), nameable))
    said_g = said_l = None
    if general():
        said_g = n.fill(c.cap, n.AND(wst, said(c, ["first name", "given name", "forename", "middle name"])))
        said_l = n.fill(c.cap, n.AND(wst, said(c, ["last name", "surname", "family name"])))
    hon = n.OR(*[n.AND(n.lit(h + ". ").at(-len(h) - 2), ~n.cls(AL).at(-len(h) - 3)) for h in ("Dr", "Mr", "Mrs", "Ms", "Prof", "Mx", "Sr", "Jr", "Sra", "Srta", "Dra", "Mme", "Mlle", "Hr", "Fr")],
               *[n.AND(n.lit(h + " ").at(-len(h) - 1), ~n.cls(AL).at(-len(h) - 2)) for h in ("Dr", "Mr", "Mrs", "Ms", "Prof", "Mx")])
    after_t = n.fill(c.cap, n.AND(wst, n.OR(n.AND(sp.at(-1), n.cls(".").at(-2), title.at(-3)), hon)))
    s_known = n.AND(c.lex_sur, nameable)

    # ---- evidence neuron: weak signals are summed with +1 / -1 weights; a name needs a total of 2
    letter = n.cls(AL)
    intro = n.OR(*[n.AND(n.lit(w + " ", nocase=True).at(-len(w) - 1), ~letter.at(-len(w) - 2)) for w in
                   ("by", "Dear", "with", "and", "named", "called", "contact", "thank", "Thanks", "Hi", "Hello", "user",
                    "reminded", "told", "asked", "emailed", "met", "thanked", "telling", "informed", "notified", "friend", "husband",
                    "wife", "son", "daughter", "brother", "sister", "mother", "father", "assistant", "colleague", "manager", "boss",
                    "neighbour", "neighbor", "cousin", "uncle", "aunt", "partner", "agent", "patient", "customer", "client", "name,",
                    "s/o", "w/o", "d/o", "c/o", "Shri", "Smt.", "Smt", "Sri", "Kumari", "Hey", "hi", "hey")],
                  *[n.lit(w + "\n").at(-len(w) - 1) for w in ("Thanks,", "Thank you,", "Regards,", "Best,", "Cheers,", "Sincerely,",
                                                                "regards,", "Warm regards,", "Best regards,", "Kind regards,", "Yours,")])
    introduced = n.fill(c.cap, n.AND(wst, intro))
    # verbs that take a person as their object are stronger evidence than prepositions
    pverb = n.OR(*[n.AND(n.lit(w + " ", nocase=True).at(-len(w) - 1), ~letter.at(-len(w) - 2)) for w in
                   ("reminded", "told", "asked", "emailed", "thanked", "telling", "informed", "notified", "messaged", "texted",
                    "phoned", "hired", "fired", "promoted", "congratulated", "introduced", "welcomed", "contacted", "pinged",
                    "married", "divorced", "dear", "regards,", "thanks,")])
    person_verb = n.fill(c.cap, n.AND(wst, pverb))
    not_word = n.AND(proper, ~c.english)
    nw_start = n.AND(wst, not_word)
    next_name = n.fill(c.cap, n.AND(tok_end, sp.at(1), nw_start.at(2)))
    prev_name = n.fill(c.cap, n.AND(wst, sp.at(-1), not_word.at(-2)))
    morph = ends_like_name(c.cap, tok_end)
    alone = n.fill(c.cap, n.AND(wst, n.cls("\n\x00\"'([").at(-1)))                # stands alone on a line or in quotes
    alone = n.AND(alone, n.fill(c.cap, n.AND(tok_end, n.cls("\n\x00\"')],.!?").at(1))))
    coord = n.fill(c.cap, n.AND(tok_end, n.OR(n.lit(" and ").at(1), n.lit(" & ").at(1), n.lit(" or ").at(1))))
    sentence_start = n.fill(c.cap, n.AND(wst, n.OR(n.AND(sp.at(-1), n.cls(".!?").at(-2)), n.cls("\n\x00").at(-1)),
                                         c.english))
    positional = n.AND(n.OR(quoted, marked, listed, seq, valued), proper)
    # mid-sentence (after a lowercase word or a comma) a capitalised non-word is a name by itself
    mid = n.fill(c.cap, n.AND(nw_start, sp.at(-1), n.cls(LO + ",;:").at(-2)))
    located = n.fill(c.cap, n.AND(wst, n.OR(*[n.AND(n.lit(w + " ").at(-len(w) - 1), ~letter.at(-len(w) - 2)) for w in ("in", "at", "near", "across", "throughout")])))
    copy = lambda sig, k: n.neuron([(sig.ch, sig.off, 1)], 0, tag=("copy", k))
    loc = None
    if general():
        before = lambda words: n.fill(c.cap, n.AND(wst, n.OR(*[n.AND(n.lit(w + " ").at(-len(w) - 1), ~n.cls(AL).at(-len(w) - 2)) for w in words])))
        in_near = before(["in", "near", "at", "outside", "around", "across"])
        to_from = before(["to", "from", "via", "towards", "toward", "into"])
        travel = before(["moved from", "came from", "comes from", "native of", "hails from", "hail from", "flew to", "flew from",
                         "shifted to", "relocated to", "relocated from", "posted in", "posted to", "transferred to", "headquartered in",
                         "bus to", "train to", "flight to", "flights to", "trip to", "travel to", "travelled to", "traveled to", "moved to",
                         "move to", "go to", "going to", "went to", "drive to", "drove to", "return to", "returned to", "back to",
                         "live in", "lives in", "lived in", "living in", "based in", "born in", "located in", "stay in", "stayed in",
                         "city of", "town of", "village of", "state of", "district of", "visit", "visited", "visiting"])
        after_words = n.OR(*[n.lit(w).at(1) for w in (" which is", " city", " district", " state", " airport", " station", " region", " village")])
        country = n.OR(c.get("COUNTRY"), c.get("STATE"), force=True)
        then_place = n.AND(comma.at(1), sp.at(2), n.AND(country, ~country.at(-1)).at(3))
        followed = n.fill(c.cap, n.AND(tok_end, n.OR(after_words, then_place)))
        person = n.OR(g_known, after_g, after_t, force=True)
        lconns = [(x.ch, x.off, 1) for x in (in_near, copy(in_near, 1), to_from, travel, copy(travel, 1), followed, copy(followed, 1))] + \
                 [(x.ch, x.off, -1) for x in (person, copy(person, 1), copy(person, 2), c.key)]
        pends = []
        for e in sorted(set(PLACE_ENDINGS)):
            L = len(e)
            pends.append(n.AND(n.lit(e).at(-(L - 1)), tok_end, n.run(n.cls(AL + HI), L + 2).at(-(L + 1))))
        pmorph = n.fill(c.cap, n.AND(c.cap, n.OR(*pends)), 4)
        # look ahead and back along an address-like list: "<X>, <known place>" and "<known place>, <X>"
        known = n.OR(c.get("CITY"), c.get("STATE"), c.get("COUNTRY"), c.get("POSTCODE"), force=True)
        kstart = n.AND(known, ~known.at(-1))
        list_next = n.fill(c.cap, n.AND(tok_end, comma.at(1), sp.at(2), kstart.at(3)))
        list_prev = n.fill(c.cap, n.AND(wst, sp.at(-1), comma.at(-2), known.at(-3)))
        lconns += [(x.ch, x.off, 1) for x in (pmorph, list_next, copy(list_next, 1), list_prev, copy(list_prev, 1))]
        from ..dsl import Sig as _S
        c.place_pos = [_S(ch, off) for ch, off, w in lconns if w > 0]
        place_neg = [_S(ch, off) for ch, off, w in lconns if w < 0] + [introduced, introduced, morph, person, person]
        loc = n.AND(n.vote(c.place_pos, place_neg, 2, tag="place-evidence"), proper, ~c.english)
        # "Kozhikode, Kerala": an unknown capitalised word right after a place and a comma is also a place
        known_place = n.OR(loc, c.get("CITY"), force=True)
        loc2 = n.AND(n.fill(c.cap, n.AND(wst, sp.at(-1), comma.at(-2), known_place.at(-3))), proper, ~c.english, ~person, ~c.get("CITY"))
        c.add("CITY", loc, 2)
        c.add("STATE", loc2, 2)
    extra = []
    if general():
        initial = n.fill(c.cap, n.AND(wst, sp.at(-1), n.cls(".").at(-2), n.cls(UP).at(-3), ~n.cls(AL + HI).at(-4)))   # "J. K. Rowling"
        roles = ("President", "Senator", "Governor", "Judge", "Captain", "Professor", "Officer", "Minister", "Doctor", "Nurse",
                 "Coach", "Chancellor", "Mayor", "Principal", "Director", "Detective", "Sergeant", "Colonel", "General", "Agent",
                 "Uncle", "Aunt", "Auntie", "Cousin", "Brother", "Sister", "Pastor", "Rabbi", "Imam", "Sheikh", "Dean", "Chef")
        role = n.fill(c.cap, n.AND(wst, n.OR(*[n.AND(n.lit(r + " ").at(-len(r) - 1), ~n.cls(AL).at(-len(r) - 2)) for r in roles])))
        g_amb = n.AND(c.lex_given_amb, nameable)                     # Will, John, Mark: names that are also words
        s_amb = n.AND(c.lex_sur_amb, nameable)                       # Smith, Brown, Gray
        any_sur = n.OR(s_known, s_amb)
        amb_pair_g = n.fill(c.cap, n.AND(g_amb, tok_end, sp.at(1), n.AND(any_sur, c.wstart).at(2)))    # Will Smith
        amb_pair_s = n.fill(c.cap, n.AND(any_sur, c.wstart, sp.at(-1), n.OR(g_amb, g_known).at(-2)))
        pair_run = n.fill(body, n.OR(amb_pair_g, amb_pair_s), 5)
        extra = [initial, copy(initial, 1), role, copy(role, 1), g_amb, s_amb, amb_pair_g, amb_pair_s, copy(amb_pair_s, 1),
                 pair_run, copy(pair_run, 1)]
        c.pair_last = amb_pair_s
    plus = [person_verb, person_verb, g_known, copy(g_known, 1), copy(g_known, 2), s_known, not_word, positional, t1, copy(t1, 1), t2, after_g,
            copy(after_g, 1), after_t, copy(after_t, 1), introduced, next_name, prev_name, mid] + extra
    phrase = n.AND(phrase, ~n.fill(body, g_known, 5))               # "Amanda Gray": a known given name keeps the run
    nl = lambda k: ~n.cls(AL + HI + "-'").at(-k)
    the = n.fill(c.cap, n.AND(wst, n.OR(n.AND(n.lit("the ").at(-4), nl(5)), n.AND(n.lit("The ").at(-4), nl(5)),
                                         n.AND(n.lit("a ").at(-2), nl(3)), n.AND(n.lit("an ").at(-3), nl(4)))))
    place = n.fill(c.cap, n.OR(c.get("CITY"), c.get("COUNTRY"), c.get("STATE"), force=True))
    nonword = n.cls("".join(chr(i) for i in range(0, 128) if not (chr(i).isalpha() or chr(i) in "'-")))
    compound = n.fill(c.cap, n.AND(c.cap, n.cls("-"), n.OR(n.cls(LO).at(1), nonword.at(1))))   # "Follow-up", "Pre-"
    # a two-letter part on either side of a hyphen marks a coined term ("Wi-Fi", "E-mail", "On-Page")
    compound = n.OR(compound, n.fill(c.cap, n.AND(c.cap, n.cls("-"), n.OR(n.AND(n.cls(UP).at(-2), ~c.wordc.at(-3)),
                                                                         n.AND(n.cls(LO).at(2), ~c.wordc.at(3))))))
    fw = n.fill(c.cap, n.AND(c.wstart, n.OR(*[n.AND(n.lit(w.capitalize()), ~c.wordc.at(len(w))) for w in FUNCTION_WORDS if len(w) > 1],
                                            *[n.AND(n.lit(w.upper()), ~c.wordc.at(len(w))) for w in FUNCTION_WORDS if len(w) > 1])))
    # English derivational suffixes (word formation): such a word is a common noun or adjective, not a name
    dsuf = n.OR(*[n.AND(n.lit(x).at(-(len(x) - 1)), tok_end, n.run(n.cls(AL), len(x) + 3).at(-(len(x) + 2))) for x in
                  ("tion", "tions", "sion", "ity", "ities", "ment", "ments", "ness", "ship", "ics", "ism", "ology", "graphy",
                   "ware", "able", "ible", "ance", "ence", "ive", "ous", "ful", "less", "ical", "ized", "ised", "izing", "ising",
                   "ated", "ating", "ure", "ures", "ency", "ancy", "ary", "graphic", "metric", "logic", "logical", "nomic",
                   "code", "codes", "shot", "shots", "laws", "work", "works", "ware", "board", "book", "line", "lines", "base")])
    english_form = n.fill(c.cap, n.AND(c.cap, dsuf))
    greet = n.fill(c.cap, n.AND(c.wstart, n.OR(*[n.AND(n.lit(w), ~c.wordc.at(len(w))) for w in
                     ("Dear", "Hi", "Hello", "Hey", "Thanks", "Regards", "Sincerely", "Mr", "Mrs", "Ms", "Dr", "Sir", "Madam", "Judge",
                      "Bill", "Priority", "High", "Low", "Good", "Pass", "Fail", "Note", "Notes", "Total", "Status")])))
    heading = n.fill(c.cap, n.AND(tok_end, n.OR(n.lit("**\n").at(1), n.lit("**:").at(1), n.lit(":**").at(1), n.lit("**").at(1))))
    heading = n.AND(heading, n.fill(c.cap, n.AND(wst, n.OR(n.lit("**").at(-2), n.lit("\n").at(-1), n.lit("# ").at(-2)))))
    month = n.fill(c.cap, n.AND(c.P(MONTHS, pre=WORD + "-", post=WORD + "-")[0], c.wstart))
    month = n.AND(month, ~n.fill(c.cap, n.AND(tok_end, sp.at(1), wst.at(2))))      # "April May": a month followed by a name is a name
    epon = n.OR(*[n.lit("'s " + w).at(1) for w in ("disease", "syndrome", "law", "theorem", "principle", "equation", "effect",
                                                   "constant", "rule", "paradox", "test", "sign", "palsy", "dementia")])
    eponym = n.fill(c.cap, n.AND(tok_end, epon))
    # a capitalised word followed by a verb of speech or action is a person
    VERBS = ("said", "says", "asked", "told", "wrote", "replied", "called", "emailed", "joined", "arrived", "mentioned", "confirmed",
             "noted", "explained", "added", "lives", "lived", "works", "worked", "agreed", "signed", "sent", "met", "left", "came",
             "went", "visited", "thanked", "smiled", "laughed", "wants", "wanted", "needs", "needed", "forgot", "knows", "thinks", "gave",
             "took", "paid", "ordered", "booked", "messaged", "texted", "pinged", "reported", "requested", "complained", "approved",
             "reviewed", "shared", "posted", "resigned", "moved", "answered", "responded", "phoned", "rang", "died",
             "will", "would", "can", "has", "had", "is", "was")
    verb_after = n.fill(c.cap, n.AND(tok_end, n.OR(*[n.AND(n.lit(" " + v).at(1), ~c.wordc.at(len(v) + 2)) for v in VERBS[:-6]])))
    aux_after = n.fill(c.cap, n.AND(tok_end, n.OR(*[n.AND(n.lit(" " + v).at(1), ~c.wordc.at(len(v) + 2)) for v in VERBS[-6:]])))
    before_number = n.fill(c.cap, n.AND(tok_end, sp.at(1), n.cls(D).at(2)))
    place_person = n.AND(place, next_name)
    plus += [place_person, copy(place_person, 1), copy(place_person, 2), copy(place_person, 3),
             n.AND(verb_after, not_word), n.AND(verb_after, nameable, ~c.english),
             n.AND(verb_after, n.OR(g_known, s_known, *([g_amb] if general() else []))), n.AND(aux_after, not_word),
             n.AND(morph, not_word), n.AND(alone, not_word), n.AND(coord, not_word)]
    minus = [sentence_start, is_org, copy(is_org, 1), phrase, copy(phrase, 1), camel, copy(camel, 1), copy(camel, 2), c.key,
             located, copy(located, 1), the, copy(the, 1), place, copy(place, 1), copy(place, 2), month,
             eponym, copy(eponym, 1), copy(eponym, 2), copy(eponym, 3), copy(is_org, 2), copy(is_org, 3), copy(is_org, 4), copy(is_org, 5),
             before_number, copy(before_number, 1), greet, greet, greet, greet, heading, heading, compound, compound, compound, fw, fw, fw, fw, english_form, english_form]
    if said_g is not None:
        plus += [said_g, copy(said_g, 1), said_l, copy(said_l, 1)]
    if loc is not None:
        # person and place readings compete inside one neuron: every place cue counts against the person reading
        minus = minus + c.place_pos + [loc2]
    ev1 = n.AND(n.vote(plus, minus, 2, tag="name-evidence"), nameable)
    # second pass: a word next to a word that already looks like a name gets extra evidence ("Georgia Brown", "María de la Cruz")
    ev1_start = n.AND(ev1, c.wstart)
    PART = ("de", "la", "del", "da", "di", "van", "der", "von", "bin", "ibn", "al", "el", "le", "du", "dos")
    part_next = n.OR(*[n.lit(" " + w + " ").at(1) for w in PART])
    listed_ok = n.OR(n.AND(c.cap, ~c.english), s_known, g_known, *([g_amb, s_amb] if general() else []))
    nb_next = n.AND(n.fill(c.cap, n.AND(tok_end, sp.at(1), ev1_start.at(2))), listed_ok)
    nb_prev = n.AND(n.fill(c.cap, n.AND(wst, sp.at(-1), ev1.at(-2))), listed_ok)
    before_particle = n.fill(c.cap, n.AND(tok_end, part_next))
    name = n.AND(n.vote(plus + [nb_next, nb_next, nb_prev, before_particle, before_particle], minus, 2, tag="name-evidence-2"), nameable,
                 ~is_org)
    if general() and not os.environ.get("NO_POS_GATE"):
        # positive evidence is necessary: the word is in the name lists, or a name key / title / introduction / person verb
        # marks it, or it sits next to a word with such evidence. "Capitalised and not an English word" alone is not a
        # name: it is just as often a cheese, a town, a product, or any word of another language.
        al_ = n.cls(AL)
        # name positions: a key or label containing "name" (not user/file/host/company ... name), bridged by separators
        # and markup ('Full name</td><td>', 'customerName": "', 'full_name="'); a signature line; the object of a chat verb;
        # the subject of a past-tense verb
        nm = n.AND(n.lit("name", nocase=True), ~n.OR(*[n.lit(w, nocase=True).at(-len(w)) for w in
                   ("user", "file", "host", "domain", "company", "product", "brand", "table", "column", "field", "class",
                    "function", "method", "variable", "project", "event", "user_", "file_", "host_", "user ", "file ", "host ",
                    "company ", "product ", "brand ", "domain ")], n.lit("s", nocase=True).at(4), force=True))
        nm_end = nm.at(-3)
        bridge = n.OR(n.cls(" :=\"'*|\t>"), c.tag, force=True)
        key_reach = n.prop_right(nm_end, bridge, 5)
        namekey = n.fill(c.cap, n.AND(wst, key_reach.at(-1)))
        closers = ("regards", "thanks", "sincerely", "cheers", "best", "warmly", "yours truly", "thank you")
        sig = n.fill(c.cap, n.AND(wst, n.OR(n.lit("--\n").at(-3), n.lit("-- \n").at(-4),
                     *[n.lit(w + ",\n", nocase=True).at(-(len(w) + 2)) for w in closers],
                     *[n.lit(w + ",\n\n", nocase=True).at(-(len(w) + 3)) for w in closers])))
        chat_obj = n.fill(c.cap, n.AND(wst, n.OR(*[n.AND(n.lit(w + " ", nocase=True).at(-len(w) - 1), ~al_.at(-len(w) - 2)) for w in
                          ("ask", "asked", "tell", "told", "ping", "pinged", "call", "called", "thank", "thanks", "met", "meet",
                           "email", "emailed", "text", "texted", "message", "messaged", "contact", "cc", "bcc", "invite", "invited",
                           "remind", "reminded", "bhai", "didi", "ji")])))
        ed_next = n.fill(al_, n.AND(n.lit("ed"), ~al_.at(2), al_.at(-1), al_.at(-2)), 4)
        ed_verb = n.fill(c.cap, n.AND(tok_end, sp.at(1), n.cls(LO).at(2), ed_next.at(2)))
        hindi_subj = n.fill(c.cap, n.AND(tok_end, n.OR(n.lit(" ne "), n.lit(" ji "), n.lit(" ji,"), n.lit(" ko bol"), n.lit(" se baat")).at(1)))
        amb = n.OR(g_amb, s_amb, force=True)                      # in the name lists and also an ordinary word
        namey = n.OR(not_word, amb, force=True)                   # (an ordinary word that is in no name list gets no evidence)
        # a listed first name before a Hindi postposition: "Riya ki report", "Aman ka phone", "Neha ko bhejo"
        hindi_post = n.AND(n.OR(g_known, g_amb, force=True),
                           n.fill(c.cap, n.AND(tok_end, n.OR(*[n.lit(" " + w + " ") for w in ("ki", "ka", "ke", "ko", "se", "bhi")]).at(1))))
        # a chat speaker: "[12/10/26, 8:05 PM] Kavya: ...", "09:14 - Asha Rao: ..." (a listed name, a timestamp before it, speech after it)
        listed_nm = n.OR(g_known, s_known, amb, force=True)
        # (after a 12-hour clock stamp, as chat exports write it, any word that is not an ordinary word is the speaker;
        #  after other stamps, as in logs, only a listed name: "[10:02:11] Kafka: ..." is a component)
        stamp_h = n.AND(n.cls("M"), n.cls("AP").at(-1), n.OR(n.cls(D).at(-2), n.cls(D).at(-3)))
        stamp_d = n.OR(n.AND(n.lit("] ").at(-2), n.cls(D).at(-3)), n.AND(n.lit(" - ").at(-3), n.cls(D).at(-4)))
        stamp_c = n.OR(n.AND(n.lit("] ").at(-2), stamp_h.at(-3)), n.AND(n.lit(" - ").at(-3), stamp_h.at(-4)))
        s_last = n.fill(c.cap, n.AND(tok_end, n.cls(":").at(1), n.cls(" ").at(2)))
        s_first = n.OR(n.AND(n.OR(g_known, g_amb, force=True), n.fill(c.cap, n.AND(wst, stamp_d))), n.AND(namey, n.fill(c.cap, n.AND(wst, stamp_c))))
        spk_name = n.AND(namey, n.OR(n.AND(s_first, s_last),
                                         n.AND(s_first, n.fill(c.cap, n.AND(tok_end, sp.at(1), n.AND(s_last, c.wstart).at(2)))),
                                         n.AND(s_last, n.fill(c.cap, n.AND(wst, sp.at(-1), n.AND(s_first, tok_end).at(-2))))))
        lo_ = n.cls(LO)
        # initials before a surname: "J. K. Rowling"
        init_before = n.fill(c.cap, n.AND(wst, sp.at(-1), n.cls(".").at(-2), n.cls(UP).at(-3), ~al_.at(-4)))
        # by-phrases and transfer verbs: "signed by", "written by", "sent to", "assigned to"
        by_to = n.fill(c.cap, n.AND(wst, n.OR(*[n.AND(n.lit(w + " ", nocase=True).at(-len(w) - 1), ~al_.at(-len(w) - 2)) for w in
                       ("signed by", "written by", "approved by", "reviewed by", "prepared by", "created by", "reported by",
                        "authored by", "submitted by", "sent by", "book by", "signed", "sent to", "send to", "assigned to",
                        "forwarded to", "escalated to", "spoke to", "talk to", "talked to", "reply to", "belongs to",
                        "addressed to", "go to", "goes to", "name of", "identified as", "forward this to", "forward to",
                        "adding", "added", "call with", "spoke with", "speak with", "meeting with", "met with", "signed for by",
                        "names", "said", "says", "did", "does", "is", "was", "omg", "lol", "and then", "copy", "loop in")])))
        # ... followed by what a person does: an irregular past or a third-person verb ("forgot", "wants", "just replied")
        did = n.fill(c.cap, n.AND(tok_end, n.OR(*[n.AND(n.lit(" " + w), ~al_.at(len(w) + 1)).at(1) for w in
                     ("forgot", "went", "came", "got", "took", "gave", "left", "wrote", "sent", "paid", "made", "knew", "thought",
                      "wants", "needs", "just", "could", "should", "might", "must", "reply", "coming", "going", "said", "did")])))
        # role labels introduce a list of people: "Reviewers: A B, C D and E F"
        rl = n.OR(*[n.lit(w, nocase=True).at(-len(w)) for w in
                    ("reviewers:", "reviewer:", "attendees:", "participants:", "members:", "owner:", "owners:", "author:", "authors:",
                     "assignee:", "reporter:", "cc:", "bcc:", "to:", "from:", "by:", "contact:", "manager:", "lead:", "present:",
                     "absent:", "signed:", "prepared by:", "approved by:", "reviewed by:", "organiser:", "organizer:", "host:")])
        role_reach = n.prop_right(n.AND(rl, n.cls(" ")), n.cls(AL + HI + " ,.'-&"), 6)
        role_list = n.fill(c.cap, n.AND(c.cap, role_reach))
        # an ambiguous name used as a person: before a lower-case word (the common-noun case is vetoed separately), or as a
        # vocative ("..., Hope.")
        amb_use = n.AND(amb, n.OR(n.fill(c.cap, n.AND(tok_end, sp.at(1), lo_.at(2))),
                                  n.fill(c.cap, n.AND(wst, n.lit(", ").at(-2), n.fill(c.cap, n.AND(tok_end, n.cls(".!?").at(1)))))))
        # relations, greetings and honorifics introduce a person (a comma may follow: "her husband, Will Hunter").
        # ("by", "with", "and" are not used here: they introduce cheeses and towns just as often)
        REL = ("Dear", "named", "called", "thank", "thanks", "hi", "hello", "hey", "reminded", "told", "asked", "emailed", "met",
               "thanked", "telling", "informed", "notified", "friend", "husband", "wife", "son", "daughter", "brother", "sister",
               "mother", "father", "assistant", "colleague", "manager", "boss", "neighbour", "neighbor", "cousin", "uncle", "aunt",
               "partner", "patient", "customer", "client", "s/o", "w/o", "d/o", "c/o", "shri", "smt", "smt.", "sri", "kumari",
               "intern", "tenant", "landlord", "teacher", "doctor", "nurse", "employee", "candidate", "applicant", "director",
               "advocate", "fiancee", "guardian", "nominee", "caller", "driver", "courier", "student", "user",
               "herr", "frau", "senor", "senora", "monsieur", "madame", "signor", "signora", "yaar", "bhaiya", "lead", "thanks to",
               "supervisor", "mentor", "roommate", "flatmate", "girlfriend", "boyfriend", "nephew", "niece", "grandmother", "grandfather",
               "is", "was")
        rel = n.fill(c.cap, n.AND(wst, n.OR(*[n.AND(n.lit(w + sepr, nocase=True).at(-len(w) - len(sepr)), ~al_.at(-len(w) - len(sepr) - 1))
                                             for w in REL[:-3] for sepr in (" ", ", ")],
                                           *[n.AND(n.lit(w + " ", nocase=True).at(-len(w) - 1), n.lit(r + " ", nocase=True).at(-len(w) - len(r) - 2))
                                             for w in ("is", "was") for r in ("name", "tenant", "this", "he", "she", "who")])))
        # surname shapes: O'Connell, D'Souza (a single capital, an apostrophe, a capitalised rest)
        apos_sur = n.fill(c.cap, n.AND(wst, n.cls(UP), n.cls("'").at(1), n.cls(UP).at(2), lo_.at(3)))
        # a possessive followed by something a person has: "Rohan's (my husband)", "Will's company trip", "Asha's phone"
        poss = n.fill(c.cap, n.AND(tok_end, n.lit("'s").at(-1), n.OR(n.lit(" (my "), n.lit(" (her "), n.lit(" (his "),
                      *[n.lit(" " + w) for w in ("phone", "number", "email", "address", "account", "laptop", "birthday", "mother",
                        "father", "wife", "husband", "son", "daughter", "brother", "sister", "manager", "team", "desk", "house",
                        "car", "company", "passport", "salary", "report", "note", "flight", "trip", "room", "order", "card", "pin")]).at(1)))
        # an apposition that describes a person: "Grace, our legal intern", "Asha, who joined in May"
        appos = n.AND(namey, n.fill(c.cap, n.AND(tok_end, n.OR(n.lit(", our "), n.lit(", my "), n.lit(", his "), n.lit(", her "),
                                                          n.lit(", who "), n.lit(", whose ")).at(1))))
        introduced_strict = n.OR(rel, apos_sur, poss, appos, force=True)
        FOREIGN_FW = ("der die das und ist nicht ein eine einen dem den des mit für auf von zu wir sie ich auch wird sind oder aber habe hat "
                      "el la los las que es un una para por con del al se su más pero como está muy también "
                      "le les et est une dans sur avec pas qui ce cette sont nous vous au aux du mais "
                      "il lo gli che è per non sono della delle anche "
                      "uma não para com é da dos das").split()
        ffw = n.OR(*[n.AND(n.lit(u(w), nocase=w.isascii()), ~n.cls(AL + HI).at(-1), ~n.cls(AL + HI).at(len(u(w)))) for w in sorted(set(FOREIGN_FW))])
        nonl_ = n.cls("".join(chr(i) for i in range(1, 256) if chr(i) != "\n"))
        # two or more such words within the sentence around: count over a window on the same line
        ffw_near = n.atleast(2, *[n.AND(ffw, nonl_).at(k) for k in range(-48, 49, 1)])
        foreign_line = n.OR(n.prop_right(ffw_near, nonl_, 5), n.prop_left(ffw_near, nonl_, 5))
        weak = n.OR(n.AND(verb_after, namey), n.AND(aux_after, namey), n.AND(ed_verb, namey), n.AND(by_to, namey), n.AND(did, namey),
                    amb_use, person_verb, force=True)
        ctx = n.OR(after_t, n.AND(weak, ~foreign_line), introduced_strict, namekey, sig, chat_obj,
                   n.AND(hindi_subj, namey), hindi_post, spk_name, init_before, role_list,
                   *([said_g, said_l] if said_g is not None else []), force=True)
        # a list hit counts by itself only when the word is not also an ordinary word (Rose, Max, Summer need a context cue),
        # the line is not in another language, and (for surnames) it is not a lone surname
        given_alone = n.AND(g_known, ~c.english)
        joiner = n.cls(" _.-")
        sur_with = n.AND(s_known, ~c.english, n.OR(n.fill(c.cap, n.AND(wst, joiner.at(-1), n.AND(c.cap, n.OR(g_known, g_amb)).at(-2))),
                                                    n.fill(c.cap, n.AND(tok_end, sp.at(1), n.AND(c.cap, c.wstart, n.OR(g_known, s_known)).at(2)))))
        sur_ok = sur_with if os.environ.get("LONE_SURNAME_NEEDS_GIVEN") else n.AND(s_known, ~c.english)
        pos0 = n.OR(n.AND(n.OR(given_alone, sur_ok), ~foreign_line), ctx, force=True)
        pos0 = n.AND(pos0, c.cap)
        p_start = n.AND(pos0, c.wstart)
        p_end = n.AND(pos0, tok_end)
        # (only a word that could be a name: "Call Priya" and "Thanks, Priya" do not make "Call" or "Thanks" a name)
        nb = n.OR(n.AND(namey, n.OR(n.fill(c.cap, n.AND(tok_end, sp.at(1), p_start.at(2))), n.fill(c.cap, n.AND(wst, sp.at(-1), pos0.at(-2))))),
                  n.AND(n.fill(c.cap, n.AND(tok_end, part_next)), ~foreign_line),
                  # coordination with a name that has evidence: "X and José", "Raj, Priya, Aanya"
                  n.AND(namey, n.OR(n.fill(c.cap, n.AND(tok_end, n.lit(" and ").at(1), p_start.at(6))),
                                    n.fill(c.cap, n.AND(tok_end, n.lit(", ").at(1), p_start.at(3))),
                                    n.fill(c.cap, n.AND(wst, n.lit(" and ").at(-5), p_end.at(-6))),
                                    n.fill(c.cap, n.AND(wst, n.lit(", ").at(-2), p_end.at(-3))),
                                    n.fill(c.cap, n.AND(wst, n.lit(", and ").at(-6), p_end.at(-7))),
                                    # fields of one record: 'Iyengar', 'Meera'
                                    n.fill(c.cap, n.AND(tok_end, n.lit("', '").at(1), p_start.at(5))),
                                    n.fill(c.cap, n.AND(tok_end, n.lit('","').at(1), p_start.at(4))),
                                    n.fill(c.cap, n.AND(wst, n.lit("', '").at(-4), p_end.at(-5))))), force=True)
        # two steps: a neighbour of a neighbour ("Anna-Maria Müller-Schmidt and José García")
        nb1 = n.OR(pos0, nb, force=True)
        nb = n.OR(nb, n.AND(namey, n.OR(n.fill(c.cap, n.AND(tok_end, sp.at(1), n.AND(nb1, c.wstart).at(2))), n.fill(c.cap, n.AND(wst, sp.at(-1), nb1.at(-2))))), force=True)
        c.name_positive = n.OR(pos0, nb, force=True)
        strong = n.AND(n.OR(introduced_strict, after_t, spk_name, hindi_post, force=True), namey, nameable, ~is_org, ~month)
        strong2 = n.AND(namey, nameable, ~is_org, n.fill(c.cap, n.AND(wst, sp.at(-1), n.AND(strong, tok_end).at(-2))))
        name = n.OR(n.AND(name, c.name_positive), strong, strong2, force=True)
        # a speaker or a titled person before a colon is not a key: "Ms. Grace Fernandes: Get well soon"
        sk = n.AND(n.OR(after_t, spk_name, force=True), namey, nameable)
        c.key_exempt = n.OR(sk, n.AND(namey, nameable, n.fill(c.cap, n.AND(wst, sp.at(-1), n.AND(sk, tok_end).at(-2)))), force=True)
    if os.environ.get("DBG"):
        for k, v in (("not_word", not_word), ("verb_after", verb_after), ("aux_after", aux_after), ("sentence_start", sentence_start),
                     ("nameable", nameable), ("ev", name), ("phrase", phrase), ("is_org", is_org), ("the", the), ("place", place), ("country", c.get("COUNTRY")), ("city", c.get("CITY")), ("state", c.get("STATE")),
                     ("located", located), ("before_number", before_number), ("greet", greet), ("heading", heading), ("intro", introduced), ("nb_next", nb_next), ("ev1", ev1), ("pverb", person_verb), ("english", c.english), ("key", c.key), ("month", month), ("eponym", eponym)):
            n.out("dbg_" + k, v)
    # a place word that behaves like a person ("Georgia Brown lives ...", "Paris said ...") is a person
    ev_start = n.AND(name, c.wstart)
    c.person_over = n.fill(c.cap, n.AND(place, name, n.OR(n.AND(tok_end, sp.at(1), ev_start.at(2)), verb_after)))
    last_cues = [after_g, after_t, n.AND(s_known, ~g_known)] + ([said_l, c.pair_last, n.AND(s_amb, ~g_amb), initial, role] if said_l is not None else [])
    c.known_given = n.AND(n.OR(g_known, *([said_g] if said_g is not None else [])), ~n.OR(*last_cues[:2], *([said_l] if said_l is not None else [])))
    c.known_last = n.AND(n.OR(*last_cues), ~c.known_given)
    if general():
        # lower-case names: "my name is amanda gray", "i am ravi", "dear priya" - the first word after the cue,
        # unless it is an ordinary word, then one more word
        wordtok = n.cls(AL + HI + "'-")
        cue_v = n.AND(n.cls(LO), ~wordtok.at(-1), said(c, ["my name is", "name is", "i am", "i'm", "this is", "dear", "regards", "sincerely", "signed"]))
        lc1 = n.AND(n.prop_right(cue_v, wordtok, 5), ~c.english)
        nxt = n.AND(n.cls(LO), sp.at(-1), lc1.at(-2))
        lc2 = n.prop_right(n.AND(nxt, ~lc1), wordtok, 5)
        lc2_end = n.AND(lc2, ~wordtok.at(1))
        closes = n.OR(n.cls(",.;!?\n").at(1), n.lit(" and ").at(1))
        lc2 = n.AND(lc2, n.OR(n.AND(lc2, ~c.english), n.fill(lc2, n.AND(lc2_end, closes), 5)))
        hon_lc = n.OR(*[n.lit(h + ". ").at(-len(h) - 2) for h in ("dr", "mr", "mrs", "ms", "prof")],
                      *[n.AND(n.lit(h + " ").at(-len(h) - 1), ~wordtok.at(-len(h) - 2)) for h in ("dr", "mr", "mrs", "ms", "prof")])
        lc3 = n.AND(n.prop_right(n.AND(n.cls(LO), hon_lc), wordtok, 5), ~c.english)
        name = n.OR(name, lc1, lc2, lc3)
        c.known_given = n.OR(c.known_given, lc1)
        c.known_last = n.OR(c.known_last, lc2, lc3)
    if general():
        lwt = n.cls(LO + HI)
        ltok_start = n.AND(lwt, ~n.cls(AL + HI + D + "_.@/-'").at(-1))
        ltok = n.prop_right(ltok_start, lwt, 4)
        lend = n.AND(ltok, ~lwt.at(1))
        clean_end = n.fill(ltok, n.AND(lend, ~n.cls(AL + D + "_@/-").at(1), ~n.AND(n.cls("."), n.cls(AN).at(1)).at(1)), 4)
        lword = n.AND(ltok, clean_end, n.fill(ltok, n.AND(ltok_start, n.run(lwt, 3)), 4), ~c.english)
        lw_start = n.AND(lword, ~lword.at(-1))
        lnext = n.fill(lword, n.AND(lend, sp.at(1), lw_start.at(2)), 4)
        lprev = n.fill(lword, n.AND(lw_start, sp.at(-1), lword.at(-2)), 4)
        in_list = n.fill(lword, n.AND(lword, n.OR(c.lex_given, c.lex_sur)), 4)
        list_pair = n.fill(lword, n.AND(n.OR(lnext, lprev), n.OR(n.AND(lend, sp.at(1), in_list.at(2)), n.AND(lw_start, sp.at(-1), in_list.at(-2)))), 4)
        lcue = n.OR(*[n.AND(n.lit(w + " ").at(-len(w) - 1), ~n.cls(AL).at(-len(w) - 2)) for w in
                      ("met", "with", "and", "to", "from", "told", "asked", "called", "call", "dear", "hi", "hey", "hello", "thanks",
                       "by", "mr", "mrs", "ms", "dr", "friend", "brother", "sister", "wife", "husband", "son", "daughter", "is", "named",
                       "meet", "ask", "tell", "ping", "contact", "cc", "sir", "madam", "ji")])
        lintro = n.fill(lword, n.AND(lw_start, lcue), 4)
        lstrong = n.fill(lword, n.AND(lw_start, n.OR(*[n.AND(n.lit(w + " ").at(-len(w) - 1), ~n.cls(AL).at(-len(w) - 2)) for w in
                     ("identified as", "forward this to", "forward to", "adding", "addressed to", "call with", "did", "from call:",
                      "who is", "who's", "hey its", "hi its", "hello its", "hey it's", "hi it's", "to user", "the user",
                      "talk to", "spoke to", "speak to", "speak with", "spoke with", "meet with", "met with", "my name is", "name is",
                      "i am", "i'm", "this is", "ask", "tell", "message", "text", "email", "ping", "call", "dear", "hi", "hey",
                      "thanks", "regards", "mr", "mrs", "ms", "dr", "shri", "smt")])), 4)
        lverb = n.fill(lword, n.AND(lend, n.OR(*[n.AND(n.lit(" " + v).at(1), ~c.wordc.at(len(v) + 2)) for v in VERBS])), 4)
        lmorph = ends_like_name(lword, lend)
        lconns = [(x.ch, x.off, 1) for x in (in_list, list_pair, copy(list_pair, 1), copy(list_pair, 2), lintro, lstrong, copy(lstrong, 1), lverb, lnext, lprev,
                                             lmorph)]
        lname1 = n.AND(n.neuron(lconns, -2, "clip", tag="lc-name-evidence"), lword)
        # second pass: a lower-case word right next to a lower-case name ("ved vyas")
        l1s = n.AND(lname1, ~lname1.at(-1))
        lnb = n.fill(lword, n.OR(n.AND(lend, sp.at(1), l1s.at(2)), n.AND(lw_start, sp.at(-1), lname1.at(-2))), 4)
        lname = n.AND(n.neuron(lconns + [(lnb.ch, lnb.off, 1)], -2, "clip", tag="lc-name-evidence-2"), lword)
        # positive evidence is necessary: the word (or its neighbour) is in the name lists, or a strong cue introduces it.
        # "Not an English word" alone never makes a name (romanised Hindi, Spanish, product names ... are not English either)
        cued = n.OR(n.AND(in_list, n.OR(lintro, lverb)), lstrong, n.AND(lword, n.OR(lc1, lc2, lc3)), force=True)   # a list hit needs a cue, not a neighbour
        if "key_reach" in dir():       # the same name positions count for lower-case words: a name key, a signature line
            lpos = n.fill(lword, n.AND(lw_start, n.OR(key_reach.at(-1), n.lit("--\n").at(-3),
                          *[n.lit(w + ",\n", nocase=True).at(-(len(w) + 2)) for w in closers])), 4)
            cued = n.OR(cued, lpos, force=True)
        lexical = n.OR(cued, n.fill(lword, n.AND(lw_start, sp.at(-1), n.AND(lword, cued).at(-2)), 4),
                       n.fill(lword, n.AND(lend, sp.at(1), n.AND(lword, cued, lw_start).at(2)), 4), force=True)
        hin = n.fill(n.cls(LO), n.OR(*[n.AND(n.lit(w), ~n.cls(AN + "_@.-/=").at(-1), ~n.cls(AN + "_@-/=").at(len(w)))
                                         for w in HINDI_FUNCTION_WORDS]), 4)
        hend = n.AND(n.cls(LO), ~n.cls(AL).at(1))
        hverb = n.OR(*[n.AND(n.lit(sfx).at(-len(sfx) + 1), n.cls(LO).at(-len(sfx)), n.cls(LO).at(-len(sfx) - 1)) for sfx in
                       ("ega", "egi", "enge", "engi", "unga", "ungi", "oge", "ogi")],
                     n.OR(n.lit(" hoon"), n.lit(" hun "), n.lit(" hu ")).at(1))
        hin = n.OR(hin, n.fill(n.cls(LO), n.AND(hend, hverb), 4), force=True)
        if "key_reach" in dir():       # a name position is enough by itself (after a quote mark too: name = 'nomvula')
            q_start = n.AND(lwt, n.cls("'\"").at(-1), ~n.cls(AL).at(-2))
            qtok = n.prop_right(q_start, lwt, 4)
            qword = n.AND(qtok, n.fill(qtok, n.AND(q_start, key_reach.at(-1), n.run(lwt, 3)), 4), ~c.english)
            q2 = n.fill(lwt, n.AND(lwt, ~lwt.at(-1), sp.at(-1), qword.at(-2)), 4)
            pos_l = n.OR(n.AND(lword, lpos), n.fill(lword, n.AND(lw_start, sp.at(-1), n.AND(lword, lpos).at(-2)), 4), qword,
                         n.AND(q2, ~c.english), force=True)
            lname = n.OR(lname, pos_l, force=True)
            lexical = n.OR(lexical, pos_l, force=True)
        # a listed first name in a Hindi-in-Latin-script sentence (two or more Hindi function words around it), at the start
        # of the sentence or before a postposition: "neha report mang rahi thi yaar", "kal neha ko bhej dena"
        hs = n.AND(hin, ~n.cls(LO).at(-1))
        hin_near = n.atleast(2, *[hs.at(k) for k in range(-44, 45)])
        l_first = n.AND(lw_start, n.OR(n.cls("\n\x00").at(-1), n.AND(sp.at(-1), n.cls(".!?,").at(-2))))
        l_post = n.AND(lend, n.OR(*[n.lit(" " + w + " ") for w in ("ne", "ko", "ki", "ka", "ke", "se", "bhi", "ji")]).at(1))
        hin_name = n.AND(lword, n.fill(lword, n.AND(lword, c.lex_given), 4), n.fill(lword, n.AND(lword, hin_near), 4),
                         n.OR(n.fill(lword, l_first, 4), n.fill(lword, l_post, 4)))
        # a listed first name that is the subject of a person verb: "neha wants the report", "did rahul reply"
        subj_name = n.AND(lword, n.fill(lword, n.AND(lword, c.lex_given), 4), lverb)
        lname = n.OR(lname, hin_name, subj_name, force=True)
        lexical = n.OR(lexical, hin_name, force=True)
        lname = n.AND(lname, lexical, ~hin)
        if os.environ.get("LC_UNCUED", "1") == "1":
            # in a lower-case register (chat), a word from the first-name list that is not an English word, not a Hindi
            # function word and not a key is a name by itself ("sanjay here from pricing", "loop in kate"); a word from the
            # surname list right after such a name is its surname ("mike petrosyan")
            given_only = n.fill(lword, n.AND(lword, c.lex_given), 4)
            not_key = ~n.fill(lword, n.AND(lend, n.OR(n.cls(":=").at(1), n.lit(" =").at(1), n.cls("(").at(1))), 4)
            gu = n.AND(given_only, ~hin, not_key)
            if "foreign_line" in dir() and "ffw" in dir():       # not on a line in another language, and not one of its function words
                gu = n.AND(gu, ~foreign_line, ~n.fill(lword, n.AND(lword, ffw), 4))
            # ... and only in an English sentence: an English function word within the 40 bytes around it
            efw = n.OR(*[n.AND(n.lit(w), ~n.cls(AL).at(-1), ~n.cls(AL).at(len(w))) for w in
                         ("the", "and", "to", "is", "in", "on", "with", "for", "from", "you", "it", "we", "me", "my", "can", "will",
                          "just", "got", "was", "are", "be", "that", "this", "so", "but", "if", "of", "at", "about", "what", "when",
                          "yet", "too", "also", "here", "there", "him", "her", "his", "she", "he", "they", "them", "did", "does",
                          "has", "have", "had", "not", "out", "up", "over", "back", "into", "again", "ok", "lol", "pls", "thx")])
            nonl2 = n.cls("".join(chr(i) for i in range(1, 256) if chr(i) != "\n"))
            eng_near = n.atleast(1, *[n.AND(efw, nonl2).at(k) for k in range(-40, 41, 1)])
            gu = n.AND(gu, n.fill(lword, n.AND(lword, eng_near), 4))
            sur_only = n.fill(lword, n.AND(lword, c.lex_sur), 4)
            sur_after = n.AND(sur_only, ~hin, n.fill(lword, n.AND(lw_start, sp.at(-1), n.AND(gu, lend).at(-2)), 4))
            lname = n.OR(lname, gu, sur_after, force=True)
            lexical = n.OR(lexical, gu, sur_after, force=True)
        c.hindi_fw = hin
        # a plain ASCII lower-case non-English word of 4+ letters without lexical evidence (other scripts, accented
        # names and particles like "van der" are judged by their own neurons)
        ascii_lw = n.AND(lword, ~n.fill(lword, n.AND(lword, n.cls(HI)), 4), n.fill(lword, n.run(n.cls(LO), 4), 4))
        c.lc_unsupported = n.AND(ascii_lw, ~lexical)
        c._lc_unsupported_raw = c.lc_unsupported
        name = n.OR(name, lname)
        c.known_given = n.OR(c.known_given, n.AND(lname, ~lprev))
        c.known_last = n.OR(c.known_last, n.AND(lname, lprev))
    apos = n.cls("'")
    poss_s = n.AND(n.cls("s"), apos.at(-1), ~c.wordc.at(1))       # the 's of a possessive is not part of the name
    name = n.AND(name, ~poss_s, ~n.AND(apos, poss_s.at(1)))
    if general():
        # surname first: "SHARMA, Priya"
        sfirst = n.fill(c.cap, n.AND(tok_end, comma.at(1), sp.at(2), n.AND(g_known, c.wstart).at(3), nameable))
        name = n.OR(name, sfirst)
        c.known_last = n.OR(c.known_last, sfirst)
        # lower-case greetings: "hi raj,", "thanks priya"
        wordtok2 = n.cls(AL + HI + "'-")
        gcue = n.OR(*[n.AND(n.lit(w + " ", nocase=True).at(-len(w) - 1), ~wordtok2.at(-len(w) - 2)) for w in ("hey", "hello", "thanks", "dear", "ping", "cc")],
                    n.AND(n.lit("hi ", nocase=True).at(-3), ~wordtok2.at(-4), ~n.AND(n.cls(" ").at(-4), n.cls(AL).at(-5))))
        lg0 = n.prop_right(n.AND(n.cls(LO), gcue, ~wordtok2.at(-1)), wordtok2, 5)
        # after a greeting: a word that is not English, or an English word that is also a first name (john, mark, rose)
        lg = n.OR(n.AND(lg0, ~c.english), n.AND(lg0, c.lex_given_amb_any), force=True)
        c.greeted_lc = lg
        name = n.OR(name, n.AND(lg, n.fill(lg, n.AND(lg, ~wordtok2.at(1), n.cls(",.!?\n ").at(1)), 5)))
        c.known_given = n.OR(c.known_given, lg)
    sure = n.OR(*c.generic_names, n.AND(place_person, proper), c.person_over)
    c.add("_NAME", n.AND(name, ~sure), 2)
    c.add("_NAME", n.AND(name, sure), 1)


def name_kind(c: Ctx):
    """Split undecided names into given / last by word ending."""
    n = c.n
    tok_end = n.AND(c.cap, ~c.wordc.at(1))
    ends_last = n.OR(n.cls("iorstkdczguvfxjpw" + HI), n.AND(n.cls("eo").at(-1), n.cls("n")),
                     n.AND(n.cls("e").at(-1), n.cls("l")))
    sp = n.cls(" ")
    for tier in (1, 2):
        if (tier, "_NAME") not in c.m:
            continue
        name = n.OR(*c.m.pop((tier, "_NAME")), force=True)
        if general():
            # particles between name words: "van der", "de la", "bin", "al"
            wt = n.cls(AL + HI + "'-")
            parts = []
            for w in ("van", "der", "den", "de", "la", "le", "del", "della", "da", "di", "do", "dos", "das", "du", "von", "zu",
                      "bin", "binti", "ibn", "bint", "al", "el", "ter", "ten", "y", "e", "st"):
                parts.append(n.AND(n.lit(w), ~wt.at(-1), ~wt.at(len(w))))
            part = n.prop_right(n.OR(*parts), n.cls(LO), 3)
            gap = n.prop_right(n.AND(part, sp.at(-1), name.at(-2)), n.OR(part, sp, force=True), 3)    # after a name word
            follows = n.prop_left(n.AND(n.OR(part, sp, force=True), c.wstart.at(1)), n.OR(part, sp, force=True), 3)
            name = n.OR(name, n.AND(part, gap, follows))
            # "al-Rashid", "el-Sayed"
            for pre in ("al-", "el-", "bin-", "abu-", "Al-", "El-"):
                pr = n.lit(pre)
                name = n.OR(name, n.spread_right(n.AND(pr, ~wt.at(-1), n.cls(UP).at(len(pre)), name.at(len(pre))), len(pre)))
            # initials right before a name: "J. R. R. Tolkien", "A.P.J. Abdul Kalam", "P. Ramanathan"
            ini = n.AND(n.cls(UP), ~n.cls(AL + HI).at(-1), n.cls(".").at(1))
            nm_start = n.AND(name, c.wstart, n.cls(LO + HI).at(1))
            ok = n.AND(ini, n.OR(n.AND(sp.at(2), nm_start.at(3)), nm_start.at(2)))
            for _ in range(4):
                ok = n.OR(ok, n.AND(ini, n.OR(n.AND(sp.at(2), ok.at(3)), ok.at(2))))
            name = n.OR(name, ok, n.AND(n.cls("."), ok.at(-1)))
        first_of_many = n.fill(name, n.AND(name, n.OR(tok_end, n.cls(".")), sp.at(1), name.at(2)))
        has_prev = n.fill(name, n.AND(name, c.wstart, sp.at(-1), name.at(-2)))
        lead = n.AND(first_of_many, ~has_prev)
        strong_given = n.AND(c.known_given, ~has_prev)      # a listed given name, unless it is the second word of a name
        last = n.AND(n.OR(n.AND(n.fill(name, n.AND(name, tok_end, ends_last)), ~lead), c.known_last, has_prev), ~strong_given, name)
        c.add("LASTNAME", last, tier)
        c.add("GIVENNAME", n.AND(name, ~last), tier)
