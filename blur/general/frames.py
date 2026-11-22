"""Context circuits: the evidence that used to live in the JavaScript pipeline, now in the weights.

A name is masked when something around it says it is a person, a secret when its key or sentence says so, a handle when
its syntax or cue says so. All rules are general statements about how text marks these things:
  1. chat speakers: lines "Name: speech" (optionally after a timestamp), with another speaker line nearby; a kinship or
     role word in the label is not part of the name; chat exports that put the time after the speaker ("Name  10:14");
  2. introductions before a name ("loop in", "courtesy of", "speaking with", "Name's", "gave her name as", "minutes by",
     "consent received from", "pulled in", ...), including a quoted name ("call him 'Bongs'");
  3. ranks, titles and kinship words before a name (Constable, Staff Nurse, Mister, Auntie, MS/MRS in capitals);
  4. a name followed by an initial ("Tomasz K.") or preceded by initials ("D. Ionesco", "D J Papadakis");
  5. role keys before a name ("Landlord:", "Lead traveller:", "Applicant:", JSON "owner"/"recipient"), capitals included;
  6. the first cell of a table row (tab or pipe separated) that also holds an e-mail address or a phone number;
  7. after the name: "X speaking", "X wrote:", "X (wife)", "X from <team>";
  8. credentials stated in English prose ("the gate code is 7309#", "wifi password is ...", "PIN: 4412");
  9. handles: @mentions, u/name, "logged in as", "triggered by", "<handle> on Telegram", user@host in ssh commands.
"""
from ..patterns import parse_var
from .languages import L, G
from .common import TITLES


def context_net(c):
    """Context circuits; every name they (and the multilingual frames) claim passes the name guard."""
    n = c.n
    cls = n.cls
    _add = c.add
    held = list(getattr(c, "_frame_names", []))
    def add(label, sig, tier=0):
        if label in ("GIVENNAME", "LASTNAME"):
            held.append((label, sig, tier))
        else:
            _add(label, sig, tier)
    c.add = add
    c.add_unguarded = _add
    try:
        _context_net(c)
    finally:
        c.add = _add
    # the name guard: a name found from its frame (a greeting, a key, a speaker label, an intro) must
    #  - start at the start of a word ("Dear T[eam]" is not a name),
    #  - not be an ordinary English word that is not also a known name ("Dear Team", "Dear Sir", "To Whom It May
    #    Concern", "Project Name: Mental Health Response"; but "Will", "Grace", "Rose" are names),
    #  - not be a time marker (AM, PM).
    letter = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" + "".join(chr(i) for i in range(0x80, 0x100)))
    asc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    known = n.OR(c.lex_given, c.lex_sur, *([c.lex_given_amb_any] if hasattr(c, "lex_given_amb_any") else []), force=True)
    plain_eng = n.AND(c.english, ~known)
    ampm = n.OR(*[n.AND(n.lit(w), ~letter.at(-1), ~letter.at(len(w))) for w in ("AM", "PM", "am", "pm")], force=True)
    ampm = n.spread_right(ampm, 2)
    # a saint's name is a place ("St. Anne's Chapel", "Saint Louis", "San Jose")
    saint = n.spread_right(n.OR(*[n.AND(n.lit(w), ~asc.at(-1)) for w in ("St. ", "St ", "Saint ", "San ", "Santa ", "Sainte ", "Sankt ")], force=True), 12)
    for label, sig, tier in held:
        bad = n.OR(n.AND(sig, ~sig.at(-1), asc.at(-1), asc), n.AND(sig, ampm), n.AND(sig, ~sig.at(-1), saint), force=True)
        # an English word is dropped unless a real name word comes before it in the same span ("Katherine Elise Wren")
        name_before = n.spread_right(n.AND(sig, asc, ~plain_eng), 30)
        _add(label, n.AND(sig, ~n.fill(sig, bad, 5), ~n.AND(plain_eng, ~name_before)), tier)


def _context_net(c):
    n = c.n
    cls = n.cls
    allb = "".join(chr(i) for i in range(1, 256))
    nonl = cls(allb.replace("\n", ""))
    sp = cls(" \t")
    digit = cls("0123456789")
    cap, wst = c.cap, c.wstart
    letter_or = n.OR(cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"), cls("".join(chr(i) for i in range(0x80, 0xC0))), cls("\xc3\xc4\xc5"), force=True)

    def P(pattern, pre=None, post=None, **kw):
        cs = lambda x: parse_var("[" + x + "]")[0][0] if x else None
        return n.match(parse_var(pattern), cs(pre), cs(post), **kw)

    def lits(words, nocase=False):
        return n.OR(*[n.lit(w.encode("utf-8").decode("latin-1"), nocase=nocase) for w in words], force=True)

    # a run of 1-4 capitalised words (particles allowed between) starting where `start` fires
    part = n.OR(*[n.lit(" " + p + " ").at(1) for p in ("de", "da", "do", "dos", "das", "del", "van", "der", "den", "le", "du", "y", "von", "al", "bin", "wa", "ter")], force=True)
    def cap_run(start):
        w1 = n.fill(cap, n.AND(wst, start), 5)
        out = [w1]
        prev = w1
        for _ in range(3):
            nxt = n.fill(cap, n.AND(wst, n.OR(n.AND(sp.at(-1), prev.at(-2)), n.AND(sp.at(-1), part.at(-4)), force=True)), 5)
            out.append(nxt); prev = nxt
        return n.OR(*out, force=True)

    # ---------- 1. chat speakers ----------
    nl_or_start = n.OR(cls("\n").at(-1), cls("\x00").at(-1), force=True)
    after_stamp = n.OR(n.lit("] ").at(-2), n.AND(sp.at(-1), digit.at(-2), cls("0123456789: APMapm").at(-3)), force=True)
    kin = lits(("Auntie ", "Aunty ", "Aunt ", "Uncle ", "Abuela ", "Abuelo ", "Tia ", "Tía ", "Tio ", "Tío ", "Tante ", "Onkel ", "Oma ", "Opa ",
                "Nana ", "Nani ", "Dadi ", "Bua ", "Mama ", "Cousin ", "Granny ", "Grandma ", "Grandpa ", "Vó ", "Vô ", "Tita ", "Lolo ", "Lola "))
    lab_start = n.AND(wst, n.OR(nl_or_start, after_stamp, force=True))
    run = cap_run(n.OR(lab_start, n.AND(lab_start.at(-k), kin.at(-k)) if False else lab_start, force=True))
    # the label (1-3 capitalised words, a kinship word allowed first), then ": " and speech with at least two words
    colon_sp = n.AND(cls(":"), sp.at(1))
    run_end = n.AND(run, ~cap.at(1))
    same_line_ahead = lambda sig: n.prop_left(n.AND(sig, nonl), nonl, 5)      # sig occurs later on this line (within 32 bytes)
    speech = n.AND(letter_or.at(2), same_line_ahead(n.AND(sp, letter_or.at(1), letter_or.at(-1))).at(3))   # a second word: prose, not a value
    machine = same_line_ahead(n.OR(cls("=;/<>{}"), n.AND(cls("."), letter_or.at(-1), letter_or.at(1)), n.AND(cls("-"), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(1), letter_or.at(-1)), force=True)).at(2)
    sp_label_end = n.AND(run_end, n.OR(colon_sp.at(1), n.AND(cls(" "), colon_sp.at(2)) if False else colon_sp.at(1), force=True), speech.at(1), ~machine.at(1))
    sp_label = n.prop_left(sp_label_end, n.OR(cap, n.AND(sp, cap.at(1), cap.at(-1)), force=True), 5)
    # another speaker label within 600 bytes before or after
    s_mark = n.AND(sp_label_end, nonl)
    near = n.OR(n.spread_right(s_mark, 600).at(-1), n.spread_left(s_mark, 600).at(1), force=True)
    speaker = n.AND(sp_label, n.fill(sp_label, n.AND(sp_label_end, near), 5))
    # a speaker label is a name only when a word of it is name-like: in the name lists, or not an ordinary English word
    # ("Fixed:", "Added:", "Item:" in a changelog are headings)
    namelike = n.OR(c.lex_given, c.lex_sur, n.AND(cap, ~c.english), force=True)
    speaker = n.AND(speaker, n.fill(speaker, n.AND(speaker, namelike), 5))
    # a label with a header-shaped word (Content-Type, X-Request-Id) is a key, not a speaker
    speaker = n.AND(speaker, ~n.fill(speaker, n.AND(speaker, cls("-"), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(1)), 5))
    kin_word = n.fill(cap, n.AND(wst, kin), 5)
    c.add("GIVENNAME", n.AND(speaker, ~kin_word, ~lits(("Agent", "Caller", "Customer", "Client", "Me", "You", "Mum", "Mom", "Dad", "Bot", "System",
                                                          "Admin", "User", "Operator", "Rep", "REP", "CUST", "Note", "Edit", "Update", "Subject", "From",
                                                          "To", "Date", "Re", "Fwd", "Ref", "Total", "Status", "Name", "Email", "Phone", "Address", "Mummy", "Daddy", "Papa", "Mama",
                                                          "Bua", "Nani", "Dadi", "HelpDesk", "Helpdesk", "Support", "Team", "Staff", "Host", "Guarantor",
                                                          "Landlord", "Tenant", "Applicant", "Witness", "Patient", "Doctor", "Nurse", "Teacher", "Manager",
                                                          "Owner", "Reviewer", "Author", "Assignee", "Present", "Attendees", "Absent", "Chair", "Server",
                                                          "Accept", "Cookie", "Origin", "Referer", "Authorization", "Vary", "Location", "Pragma", "Expires")),
                                ~n.fill(speaker, n.AND(speaker, lits((" Bot", " bot", "Bot", "Desk"))), 5)), 1)
    # a chat export that puts the time after the speaker on its own line: "Adaeze Onyekachi  10:14"
    t_after = n.AND(run_end, n.OR(n.lit("  ").at(1), n.lit(" ").at(1), force=True), n.OR(n.AND(digit.at(3), cls(":").at(4)), n.AND(digit.at(3), digit.at(4), cls(":").at(5)), n.AND(digit.at(2), cls(":").at(3)), n.AND(digit.at(2), digit.at(3), cls(":").at(4)), force=True))
    c.add("GIVENNAME", n.AND(run, n.fill(run, n.AND(t_after, n.prop_left(n.AND(t_after, nonl), n.OR(cap, sp), 5).at(0)), 5), n.fill(run, lab_start, 5)), 2)

    ranks = ("Constable ", "Sergeant ", "Sgt ", "Sgt. ", "Officer ", "Inspector ", "Detective ", "Nurse ", "Staff Nurse ", "Sister ", "Coach ",
             "Professor ", "Captain ", "Capt. ", "Pastor ", "Rabbi ", "Imam ", "Mister ", "Miss ", "Auntie ", "Aunty ", "Uncle ", "Abuela ", "Abuelo ",
             "Tia ", "Tío ", "Tía ", "Tio ", "Granny ", "Grandma ", "Grandpa ", "MS ", "MRS ", "MR ", "MISS ", "DR ", "Herr ", "Frau ")
    rank_word = n.fill(cap, n.AND(wst, lits(tuple(r.strip() for r in ranks) + ("Staff", "Nurse", "Emeritus", "Prof", "Professor"))), 5)
    # ---------- 2. introductions before a name ----------
    intro = ("loop in ", "looping in ", "looped in ", "courtesy of ", "speaking with ", "speaking to ", "you're speaking with ", "Name's ", "name's ",
             "gave her name as ", "gave his name as ", "gave their name as ", "records him as ", "records her as ", "call him ", "call her ",
             "called him ", "called her ", "comment from ", "message from ", "note from ", "notes from ", "thanks to ", "Thanks to ", "thx ",
             "c/o ", "attn ", "Attn: ", "attn: ", "on behalf of ", "married to ", "minutes by ", "Minutes by ", "notes by ", "prepared by ",
             "consent received from ", "well done to ", "Well done to ", "kudos to ", "congrats to ", "pulled in ", "brought in ", "paged ",
             "pager went to ", "handed over to ", "handed over by ", "escalated to ", "approved for ", "registered as ", "a bloke called ",
             "a woman called ", "a man called ", "someone called ", "surname ", "last name ", "first name ", "Signed, ", "signed, ", "Signed ",
             "ask for me, ", "ask for ", "check with ", "spoke to ", "spoke with ", "talked to ", "reach out to ", "reached out to ", "deputy, ",
             "his deputy ", "her deputy ", "cc ", "cc: ", "Cc: ", "CC: ", "cc'ing ", "copying in ", "copied ", "adding ", "forwarded to ",
             "Reviewer comment from ", "repro steps from ", "Repro steps from ", "engraved 'To ", "To ", "Dear ", "dear ", "Hi ", "Hey ", "Hello ",
             # aliases and nicknames
             "everyone calls ", "everybody calls ", "people call ", "friends call ", "we call ", "they call ", "calls him ", "calls her ",
             "calls them ", "known as ", "also known as ", "aka ", "a.k.a. ", "nicknamed ", "goes by ", "go by ", "went by ",
             "refer to them as ", "refer to him as ", "refer to her as ", "refers to them as ", "refers to him as ", "refers to her as ",
             "listed as ", "legally ", "née ", "nee ", "born ",
             # statements about a person: "This document certifies that Demarcus Cyprian ..."
             "certifies that ", "certify that ", "certified that ", "attests that ", "declares that ", "acknowledges that ")
    i_span, i_end = P(G(*intro), pre="A-Za-z")
    c.add("GIVENNAME", n.AND(cap_run(i_end.at(-1)), ~rank_word, ~lits(("The ", "This ", "That ", "Our ", "Your ", "My ", "All ", "Team", "Everyone", "Support", "Legal", "Finance", "HR ", "Sales", "IT "))), 2)
    # a capitalised word right after given names completes the name, even when it is also an English word
    # ("Katherine Elise Wren", "Priya Baker"); not a weekday, month, title, organisation or place word
    given_any = c.get("GIVENNAME")
    # two name words before it ("Katherine Elise Wren"); one is not enough evidence ("Robin Hood", "Victoria Falls")
    two_names = n.AND(given_any, sp.at(1) if False else given_any, n.spread_right(n.AND(given_any, sp.at(1)), 24))
    # two name words before it, or one known first name when the word itself is a known surname or not an ordinary
    # English word ("John Doe", "Victor Formby", "Junho Kim"; not "Robin Hood", "Victoria Falls")
    two_before = n.spread_right(n.AND(sp, given_any.at(-1), cap.at(1)), 24).at(-2)
    word_ok = n.fill(cap, n.AND(cap, wst, n.OR(c.lex_sur, ~c.english, force=True) if False else c.lex_sur), 5)
    unknown = n.AND(cap, ~n.fill(cap, n.AND(cap, c.english), 5))
    one_before = n.AND(c.lex_given.at(-2), n.fill(cap, n.OR(n.AND(cap, wst, c.lex_sur), n.AND(unknown, wst), force=True), 5))
    after_given = n.AND(cap, wst, sp.at(-1), given_any.at(-2), n.OR(two_before, one_before, force=True))
    sur_word = n.fill(cap, after_given, 5)
    not_sur = lits(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March", "April",
                    "May ", "June", "July", "August", "September", "October", "November", "December", "Street", "Road", "Lane", "Avenue",
                    "Hospital", "University", "College", "School", "Bank", "Ltd", "Inc", "LLC", "Group", "Team", "The ", "And ", "Or ",
                    "From ", "On ", "In ", "At ", "To ", "For ", "With ", "If ", "But ", "I ", "Ltd", "Corp", "Foundation", "Trust", "Mr", "Mrs",
                    "Ms", "Dr", "Hall", "House", "Centre", "Center", "Clinic", "Office", "Station", "Airport", "Park", "Square", "Plaza"))
    sur_word = n.AND(sur_word, ~n.fill(sur_word, n.AND(sur_word, not_sur), 5))
    c.add_unguarded("LASTNAME", sur_word, 2)
    c.sur_word = sur_word            # the given names before it are the evidence; the guard would drop "Wren"
    # spelled-out digit chains: three or more digit words joined by hyphens ("seven-seven-zero-zero", "one-zero-four") write
    # a number down; a phone number when a phone word is near before it, an identifier otherwise
    dwords = ("zero", "oh", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "double", "triple")
    dw = n.OR(*[n.AND(n.lit(w, nocase=True), ~cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz").at(len(w))) for w in dwords], force=True)
    dw_start = n.AND(dw, ~cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz").at(-1))
    dchar = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-")
    dtok = n.prop_right(dw_start, dchar, 6)
    # three digit words: at least two hyphens joining digit words inside the token
    hy = n.AND(cls("-"), dtok, dw_start.at(1) if False else dw.at(1))
    two_hy = n.AND(hy, n.spread_right(hy, 7).at(-1) if False else n.spread_right(hy, 7).at(-1))
    chain = n.AND(dtok, n.fill(dtok, two_hy, 6))
    phone_cue = n.spread_right(lits(("phone", "mobile", "cell", "call", "dial", "whatsapp", "tel", "Phone", "Mobile", "Cell"), nocase=False), 100)
    c.add("TEL", n.AND(chain, phone_cue), 1)
    c.add("ID", n.AND(chain, ~phone_cue), 1)
    # a quoted name after an introduction: "call him 'Bongs'", "returned 'D. Ionesco'", "display name 'Roz", "agent called 'Stella M.'"
    q_intro = ("call him ", "call her ", "has as ", "returned ", "display name ", "called ", "registered as ", "named ", "known as ", "says ", "reads ")
    q_span, q_end = P(G(*q_intro) + G("'", "\"", "‘", "“"), pre="A-Za-z")
    q_run = cap_run(q_end.at(-1))
    init_tail = n.AND(cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), sp.at(-1), cls(".").at(1))
    c.add("GIVENNAME", n.OR(q_run, n.spread_right(n.AND(init_tail, q_run.at(-2)), 2), force=True), 1)

    # ---------- 2b. a person named by their role, or described right after their name ----------
    # "The primary witness, Le Lee, provided ...", "the tenant Ana Ruiz said", "Le Lee, a MAGA supporter, ...",
    # "Ana Ruiz, the claimant, ...", "Tom Kwan, 34, of Leeds": the frame is the evidence, so the words need not be in a
    # name list (short or rare names such as "Le", "Ly", "Bo")
    roles = ("witness", "victim", "suspect", "patient", "client", "customer", "applicant", "complainant", "claimant", "defendant",
             "plaintiff", "petitioner", "respondent", "tenant", "landlord", "driver", "passenger", "employee", "caller", "member",
             "guest", "resident", "student", "beneficiary", "borrower", "debtor", "accused", "deceased", "survivor", "informant",
             "donor", "buyer", "seller", "owner", "occupant", "subscriber", "policyholder", "insured", "nominee", "guardian",
             "spouse", "partner", "neighbour", "neighbor", "colleague", "contractor", "candidate", "intern", "volunteer", "visitor",
             "attendee", "participant", "cardholder", "account holder", "householder", "homeowner", "renter", "lodger", "user")
    role_w = n.OR(*[n.AND(n.lit(r), ~letter_or.at(-1), ~letter_or.at(len(r))) for r in roles], force=True)
    role_end = n.OR(*[n.AND(n.lit(r), ~letter_or.at(-1), ~letter_or.at(len(r))).at(-(len(r) - 1)) for r in roles], force=True)   # its last letter
    after_role = n.OR(n.AND(n.lit(", ").at(-2), role_end.at(-3)), n.AND(sp.at(-1), role_end.at(-2)), force=True)
    run_a = cap_run(after_role)
    run_a_end = n.AND(run_a, ~run_a.at(1), ~cap.at(1))
    closes = n.OR(cls(",.;:)(").at(1), n.AND(sp.at(1), cls("abcdefghijklmnopqrstuvwxyz").at(2)), force=True)
    runj = n.OR(run_a, n.AND(sp, run_a.at(-1), run_a.at(1)), force=True)            # the run's words joined across spaces
    two_words = n.fill(runj, n.AND(runj, sp), 5)
    comma_led = n.fill(runj, n.AND(run_a, wst, n.lit(", ").at(-2)), 5)
    frame_a = n.AND(run_a, n.fill(runj, n.AND(run_a_end, closes), 5), n.OR(comma_led, two_words, force=True))
    # described after the name: ", a/an/the ... <person noun>" or an age
    person_nouns = ("supporter", "resident", "student", "teacher", "nurse", "doctor", "mother", "father", "man", "woman", "boy",
                    "girl", "citizen", "member", "volunteer", "employee", "worker", "engineer", "driver", "owner", "tenant",
                    "witness", "victim", "suspect", "patient", "client", "customer", "claimant", "applicant", "neighbour",
                    "neighbor", "friend", "colleague", "manager", "nurse", "pensioner", "retiree", "veteran", "mum", "dad",
                    "son", "daughter", "wife", "husband", "widow", "widower", "grandmother", "grandfather", "parent", "carer")
    noun_w = n.OR(*[n.AND(n.lit(w), ~letter_or.at(-1), ~letter_or.at(len(w))) for w in person_nouns], force=True)
    # or any word shaped like a person noun: technologist, technician, engineer, director, consultant, attendee
    lowc = cls("abcdefghijklmnopqrstuvwxyz")
    lw = n.prop_right(n.AND(lowc, ~letter_or.at(-1)), lowc, 4)
    lw_end = n.AND(lw, ~letter_or.at(1))
    suffix_end = n.OR(*[n.AND(n.lit(sfx).at(-(len(sfx) - 1)), lw_end) for sfx in ("ist", "ian", "er", "or", "ant", "ent", "eer", "ee")], force=True)
    shaped = n.fill(lw, n.AND(suffix_end, n.run(lowc, 5).at(-4)), 4)                      # five letters or more
    noun_w = n.OR(noun_w, n.AND(shaped, ~shaped.at(-1)), force=True)
    # a person noun within the same clause (no "," ";" "." in between): "Le Lee, a MAGA supporter"
    in_clause = cls("".join(chr(i) for i in range(32, 256) if chr(i) not in ",;.:!?()"))
    noun_soon = n.AND(n.prop_left(noun_w, in_clause, 5), n.spread_left(noun_w, 32))
    art = n.OR(n.AND(n.lit(", a "), noun_soon.at(4)), n.AND(n.lit(", an "), noun_soon.at(5)), n.AND(n.lit(", the "), noun_soon.at(6)),
               n.AND(n.lit(", aged "), cls("0123456789").at(7)), n.AND(n.lit(", age "), cls("0123456789").at(6)),
               n.AND(n.lit(", "), cls("0123456789").at(2), n.OR(n.AND(cls("0123456789").at(3), cls(",").at(4)), cls(",").at(3), force=True)),
               force=True)
    run_b_end = n.AND(cap, ~cap.at(1), art.at(1))
    run_b = n.prop_left(run_b_end, n.OR(cap, n.AND(sp, cap.at(-1), wst.at(1)), force=True), 5)
    run_b = n.AND(run_b, n.fill(run_b, n.AND(run_b, sp), 5))                          # two or three words
    run_b = n.AND(run_b, ~n.fill(run_b, n.AND(wst, lits(("The ", "A ", "An ", "This ", "That ", "Our ", "Your ", "My "))), 5))
    # the run looks like a name: a word outside the dictionary, or a known first name or surname ("New York" and "Big
    # Data" are ordinary words); and it is not an organisation ("Acme Corp, a leading provider")
    runbj = n.OR(run_b, n.AND(sp, run_b.at(-1), run_b.at(1)), force=True)
    namey_w = n.OR(n.AND(cap, ~c.english), c.lex_given, c.lex_sur, force=True)
    org_words = ("Corp", "Corporation", "Inc", "Ltd", "LLC", "LLP", "PLC", "GmbH", "Co", "Company", "Group", "Bank", "Labs",
                 "Systems", "Technologies", "Technology", "Solutions", "Software", "Industries", "Holdings", "Partners",
                 "Associates", "Foundation", "Trust", "University", "College", "School", "Hospital", "Clinic", "Agency",
                 "Council", "Ministry", "Department", "Services", "Media", "Studio", "Studios", "Games", "Motors", "Airlines",
                 "Insurance", "Capital", "Ventures", "Networks", "Institute", "Society", "Association", "Club", "Pvt", "Limited")
    org_w = n.fill(cap, n.AND(wst, n.OR(*[n.AND(n.lit(w), ~letter_or.at(len(w))) for w in org_words], force=True)), 5)
    run_b = n.AND(run_b, n.fill(runbj, n.AND(run_b, namey_w), 5), ~n.fill(runbj, n.AND(run_b, n.OR(c.get("ORG"), org_w, force=True)), 5))
    title_word = n.fill(cap, n.AND(wst, n.OR(*[n.AND(n.lit(t), ~letter_or.at(len(t))) for t in TITLES.split("|")], force=True)), 5)
    framed = n.AND(n.OR(frame_a, run_b, force=True), ~rank_word, ~title_word)
    c.add_unguarded("GIVENNAME", framed, 1)
    c.name_framed = framed                    # the frame outranks word-level doubts ("Lee" is also a noun)

    # ---------- 3. ranks, titles, kinship words ----------
    r_span, r_end = P(G(*ranks), pre="A-Za-z")
    upper = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    caps_word_start = n.AND(upper, upper.at(1), ~letter_or.at(-1))
    caps_run = n.prop_right(n.AND(caps_word_start, r_end.at(-1)), n.OR(upper, cls("'-"), n.AND(sp, upper.at(1), upper.at(-1)), force=True), 5)
    c.add("GIVENNAME", n.AND(n.OR(cap_run(r_end.at(-1)), caps_run, force=True), ~rank_word), 1)

    # ---------- 4. initials ----------
    # "Tomasz K.", "Kostas P.": a capitalised word followed by a capital initial and a full stop
    w_init = n.fill(cap, n.AND(cap, ~letter_or.at(1), sp.at(1), upper.at(2), cls(".").at(3), ~letter_or.at(-1) if False else cap), 5)
    w_init = n.AND(w_init, n.fill(cap, n.AND(wst, ~sp.at(-1) if False else wst), 5))
    initial_after = n.AND(upper, sp.at(-1), cls(".").at(1), w_init.at(-2))
    namey = n.OR(c.lex_given, c.lex_sur, force=True) if hasattr(c, "lex_given") and hasattr(c, "lex_sur") else None
    if namey is not None:
        c.add("GIVENNAME", n.OR(n.AND(w_init, n.fill(cap, n.AND(cap, namey), 5)), n.spread_right(n.AND(initial_after, n.fill(cap, namey, 5).at(-2)), 2), force=True), 2)
    # "D. Ionesco", "D J Papadakis": initials before a capitalised word
    lead_init = n.OR(n.AND(upper, ~letter_or.at(-1), cls(".").at(1), sp.at(2)), n.AND(upper, ~letter_or.at(-1), sp.at(1), upper.at(2), sp.at(3)), force=True)
    after_inits = n.fill(cap, n.AND(wst, n.OR(n.AND(sp.at(-1), cls(".").at(-2), lead_init.at(-3)), n.AND(sp.at(-1), upper.at(-2), sp.at(-3), lead_init.at(-4)), force=True), cap.at(1)), 5)
    c.add("GIVENNAME", n.AND(after_inits, n.fill(cap, n.OR(namey, c.lex_sur if hasattr(c, "lex_sur") else namey, force=True) if namey is not None else after_inits, 5)), 2)

    # ---------- 5. role keys ----------
    roles = ("Landlord", "Tenant", "Tenants", "Applicant", "Guarantor", "Lead traveller", "Lead traveler", "Also travelling", "Also traveling", "Passenger",
             "Witness", "Second driver", "SECOND DRIVER", "Driver", "Owner", "Recipient", "Present", "Attendees", "Reviewers", "Reviewer", "Author",
             "Assignee", "Reporter", "Patient", "Employee", "Student", "Candidate", "Beneficiary", "Nominee", "Cardholder", "Account holder",
             "Policyholder", "Signatory", "Next of kin", "Emergency contact", "Referee", "Contact", "Guardian", "Parent", "Customer", "Client",
             "Prepared by", "Approved by", "Reviewed by", "Requested by", "Booked by", "Name", "Full name", "NAME", "APPLICANT", "PASSENGER")
    _, rk_end1 = P(G(*roles) + G(": ", ":\t", " - "), pre="A-Za-z")
    _, rk_end2 = P(G(*roles) + " \\([A-Za-z0-9 ,.'-]{1,30}\\)" + G(": ", ":\t"), pre="A-Za-z")
    rk_end = n.OR(rk_end1, rk_end2, force=True)
    title_after = n.OR(lits(("Mr ", "Mrs ", "Ms ", "Miss ", "Dr ", "MR ", "MRS ", "MS ", "MISS ", "DR ", "Mr. ", "Mrs. ", "Ms. ", "Dr. ")), force=True)
    st = n.OR(rk_end.at(-1), *[n.AND(title_after.at(-k), rk_end.at(-k - 1)) for k in (3, 4, 5)], force=True)
    caps_run2 = n.prop_right(n.AND(caps_word_start, st), n.OR(upper, cls("'-"), n.AND(sp, upper.at(1), upper.at(-1)), force=True), 5)
    c.add("GIVENNAME", n.OR(cap_run(st), caps_run2, force=True), 1)
    # JSON / dict keys that hold a person: "owner": "Wambui Kariuki", "recipient": ..., "emergency_contact": "Akosua (wife)"
    jk_span, jk_end = P("\"" + G("owner", "recipient", "emergency_contact", "contact", "customer", "patient", "applicant", "approver", "author",
                                 "assignee", "reporter", "requester", "reviewer", "guardian", "next_of_kin", "beneficiary", "holder", "driver",
                                 "passenger", "tenant", "landlord", "witness", "signatory", "manager", "agent", "doctor", "nurse") + "\"" + G(": \"", ":\"", ": '"))
    c.add("GIVENNAME", cap_run(jk_end.at(-1)), 1)

    # ---------- 6. first cell of a table row with an e-mail address or phone number ----------
    email_sig = c.get("EMAIL")
    tel_sig = c.get("TEL")
    contact_ahead = n.spread_left(n.OR(email_sig, tel_sig, force=True), 220)
    row_start = n.OR(nl_or_start, n.lit("| ").at(-2), n.lit("|").at(-1), force=True)
    cell_end_tab = n.OR(cls("\t"), n.lit(" |"), n.lit("|"), force=True)
    row_run = cap_run(n.AND(row_start, n.OR(nl_or_start, n.AND(n.lit("| ").at(-2), nl_or_start.at(-2)), n.AND(cls("|").at(-1), nl_or_start.at(-1)), force=True)))
    row_end = n.AND(row_run, ~cap.at(1), n.OR(cell_end_tab.at(1), n.AND(sp.at(1), cls("|").at(2)), force=True), contact_ahead.at(1),
                    n.prop_right(n.AND(row_run, ~cap.at(1)), nonl, 7) if False else row_run)
    two_words = n.fill(row_run, n.AND(row_run, sp, cap.at(1)), 5)
    c.add("GIVENNAME", n.AND(row_run, n.fill(row_run, row_end, 5), two_words), 1)

    # ---------- 7. after the name ----------
    after = (" speaking", " wrote:", " (wife)", " (husband)", " (son)", " (daughter)", " (mother)", " (father)", " (brother)", " (sister)",
             " (partner)", " (she/her)", " (he/him)", " (they/them)", ", who ", " from comp", " from Legal", " from Treasury", " from HR",
             " from Finance", " from Sales", " from Accounts", " from Billing", " from Support", " from the ", " here from ")
    aft = lits(after)
    name_before = n.fill(cap, n.AND(cap, ~letter_or.at(1), aft.at(1)), 5)
    prev_name = n.fill(cap, n.AND(cap, ~letter_or.at(1), sp.at(1), n.AND(wst, name_before).at(2)), 5)
    nb = n.OR(name_before, prev_name, force=True)
    if namey is not None:
        c.add("GIVENNAME", n.AND(nb, n.fill(cap, n.OR(namey, wst, force=True) if False else namey, 5)), 2)

    # ---------- 8. credentials stated in English prose ----------
    cue = ("password", "passcode", "passphrase", "pin", "PIN", "gate code", "door code", "alarm code", "keypad", "keypad code", "padlock code",
           "lockbox", "combination", "wifi password", "wifi", "Wi-Fi password", "Wi-Fi", "wi-fi", "the code", "code you texted", "otp", "OTP",
           "verification code", "security code", "recovery code", "memorable word", "secret word", "access code", "safe code", "basic-auth")
    cue_span, cue_end = P(G(*cue), pre="A-Za-z")
    near_cue = n.AND(n.spread_right(cue_end, 48), n.prop_right(cue_end, nonl, 5))
    cop_span, cop_end = P(G(" is ", " was ", ": ", " to ", " changed to ", " is: ", " it's ", " it is: ", "(it was ", " = ", " literally ",
                              " is all lowercase: ", " is literally "))
    after_cop = n.AND(cop_end, near_cue)
    vchar = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*_+-.")
    quote_open = cls("'\"`")
    vstart = n.AND(vchar, ~vchar.at(-1), n.OR(after_cop.at(-1), n.AND(quote_open.at(-1), after_cop.at(-2)), force=True))
    val = n.prop_right(vstart, n.OR(vchar, n.AND(cls(" -"), digit.at(1), digit.at(-1)), force=True), 5)
    val = n.AND(val, ~n.AND(cls("."), ~vchar.at(1)), n.fill(val, n.OR(digit, cls("!@#$%^&*_"), force=True), 5))
    c.add("PASS", val, 1)

    # ---------- 9. handles ----------
    hchar = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")
    at_m = n.AND(cls("@"), ~hchar.at(-1), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz").at(1))
    mention = n.prop_right(at_m, n.OR(cls("@"), hchar, force=True), 5)
    # not an e-mail, not a decorator at a line start, not a scoped package or an npm/docker registry reference
    mention = n.AND(mention, ~n.fill(mention, n.AND(mention, cls("@").at(-1), nl_or_start.at(-1)), 5), ~n.fill(mention, n.AND(mention, cls("/:").at(1)), 5))
    c.add("USERNAME", n.AND(mention, ~n.AND(cls("."), ~hchar.at(1))), 1)
    u_slash = n.AND(cls("u"), cls("/").at(1), ~hchar.at(-1))
    u_name = n.prop_right(n.AND(hchar, u_slash.at(-2)), hchar, 5)                  # the name after "u/", not the prefix
    c.add("USERNAME", n.AND(u_name, ~n.AND(cls("."), ~hchar.at(1))), 1)
    hcue = ("logged in as ", "signed in as ", "login as ", "triggered by ", "push by ", "posted by ", "Posted by ", "applied through the portal as ",
            "goes by ", "went by ", "I was ", "streams it as ", "handle ", "username is ", "login is ", "My login is ", "my login is ", "gamertag ",
            "user ", "from user ", "Okta login ", "GitHub handle ", "chat handle was ", "account is ", "tag is ", "Telegram: ", "on Telegram: ")
    hc_span, hc_end = P(G(*hcue), pre="A-Za-z")
    hs = n.AND(hchar, n.OR(hc_end.at(-1), n.AND(cls("'\"`@").at(-1), hc_end.at(-2)), force=True))
    hval = n.prop_right(hs, hchar, 5)
    hshape = n.fill(hval, n.AND(hval, n.OR(cls("_0123456789"), n.AND(cls(".-"), hchar.at(1), hchar.at(-1)), force=True)), 5)
    c.add("USERNAME", n.AND(hval, hshape, ~n.AND(cls(".-"), ~hchar.at(1))), 1)
    # "<handle> on Telegram/Discord/..." and ssh user@host
    plat = lits((" on Telegram", " on Discord", " on Instagram", " on Twitter", " on Signal", " on WhatsApp", " on Slack", " on GitHub", " on GitLab",
                 " on Reddit", " on Steam", " on Twitch", " on TikTok", " on Snapchat"))
    h_before = n.prop_left(n.AND(hchar, plat.at(1)), hchar, 5)
    c.add("USERNAME", n.AND(h_before, n.fill(h_before, n.AND(h_before, n.OR(cls("_0123456789"), force=True)), 5)), 1)
    ssh_span, ssh_end = P(G("ssh ", "ssh -v ", "scp ", "sftp "))
    ssh_reach = n.AND(n.spread_right(ssh_end, 60), nonl)
    user_at = n.prop_left(n.AND(hchar, cls("@").at(1), ssh_reach), hchar, 5)
    c.add("USERNAME", n.AND(user_at, ~n.fill(user_at, n.AND(user_at, cls("-").at(-1) if False else user_at, cls(" ").at(-1) if False else user_at), 5) if False else user_at), 1)
