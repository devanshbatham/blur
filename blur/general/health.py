"""Clinical context: health facts and the context that marks a document as clinical."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)


def clinical_context(c: Ctx):
    """Document-level clinical context: one clinical cue anywhere makes the whole document a record about a person."""
    if getattr(c, "_medctx", None) is not None:
        return c._medctx
    n = c.n
    letter = n.cls(AL + HI)
    cue = n.OR(*[n.AND(n.lit(w if w.isascii() else u(w), nocase=w.isascii()), ~letter.at(-1), ~letter.at(len(w.encode())))
                 for w in MED_CUES])
    anyc = n.cls("".join(chr(i) for i in range(1, 256)))
    c._medctx = n.OR(n.prop_right(cue, anyc, 11), n.prop_left(cue, anyc, 11))
    return c._medctx


def clinical(c: Ctx, personal, term_tree):
    n = c.n
    letter, low, d = n.cls(AL + HI), n.cls(LO), n.cls(D)
    sp = n.cls(" ")
    # a general statement ("diabetes affects millions", "is common in India") is not about a person
    gen = n.OR(*[n.AND(n.lit(w, nocase=True), ~letter.at(-1), ~letter.at(len(w))) for w in
                 ("millions", "million", "billions", "worldwide", "prevalence", "population", "populations", "awareness",
                  "common", "affects", "rates", "statistics", "nationwide", "globally", "people", "society")])
    stop = n.cls(".!?\n")
    sent = n.AND(n.cls("".join(chr(i) for i in range(32, 256) if chr(i) not in ".!?\n")), ~stop)
    general_stmt = n.OR(n.prop_right(gen, sent, 7), n.prop_left(gen, sent, 7))
    gate = n.OR(personal, n.AND(clinical_context(c), ~general_stmt))
    def words(ws, nocase=True):
        return n.OR(*[n.AND(n.lit(w if w.isascii() else u(w), nocase=nocase and w.isascii()), ~letter.at(-1),
                            ~letter.at(len(w.encode()))) for w in ws])
    def whole(seed):
        return n.fill(letter, seed, 4)
    # morphology: a word of 3+ letters before a drug or condition ending
    def suffixed(sufs):
        hits = []
        for suf in sufs:
            k = len(suf)
            hits.append(n.AND(n.lit(suf, nocase=True), ~letter.at(k), letter.at(-1), letter.at(-2), letter.at(-3)))
        return whole(n.OR(*hits))
    veto = whole(words(COND_VETO))
    drug = suffixed(DRUG_SUFFIXES)
    cond = n.AND(suffixed(COND_SUFFIXES), ~veto)
    head = whole(words(COND_HEADS))
    abbr = whole(words(COND_ABBR, nocase=False))
    epon = n.AND(words(EPONYMS), ~letter.at(-1))
    epon = n.prop_right(whole(epon), n.OR(n.cls("'s"), n.lit(u("’")), n.lit(u("’")).at(-1), n.lit(u("’")).at(-2), force=True), 2)
    eterm = words(["law", "laws", "principle", "rule", "theorem", "effect", "paradox", "constant", "razor", "equation", "problem",
                   "test", "number", "curve", "cycle"])
    epon = n.AND(epon, ~n.fill(n.OR(letter, n.cls("'"), force=True), n.AND(epon, n.cls("s"), n.cls(" ").at(1), eterm.at(2)), 4))
    # "Alzheimer's research fund", "Parkinson's law": an eponym followed by a noun that is not a disease word is a name of a thing
    dis_next = words(["disease", "diseases", "syndrome", "palsy", "dementia", "and", "or", "with", "since", "for", "is", "was",
                      "diagnosis", "patients", "patient", "symptoms", "medication", "in", "at", "on", "but", "which", "that"])
    epon = n.AND(epon, ~n.fill(n.OR(letter, n.cls("'"), force=True),
                               n.AND(epon, n.cls("s"), n.cls(" ").at(1), low.at(2), ~dis_next.at(2)), 4))
    core = n.OR(drug, cond, head, abbr, epon, term_tree, force=True)
    dis_next2 = words(["disease", "diseases", "syndrome", "palsy", "dementia", "diagnosis", "patients", "symptoms"])
    poss_thing = n.fill(n.OR(letter, n.cls("'"), force=True),
                        n.AND(core, n.cls("'").at(1), n.cls("s").at(2), n.cls(" ").at(3), low.at(4), ~dis_next2.at(4)), 4)
    core = n.AND(core, ~poss_thing)
    # dose, frequency, stage, results and lab values attach on the right
    num = n.prop_right(n.AND(d, ~n.cls(AN).at(-1)), n.cls(D + "."), 3)
    unit = whole(words(["mg", "mcg", "µg", "g", "ml", "mL", "iu", "units", "unit", "tab", "tabs", "tablet", "tablets",
                        "puff", "puffs", "mg/dL", "mmol/L", "mIU/L", "U/L", "g/dL", "°F", "°C"]))
    unit_glued = n.prop_right(n.AND(n.cls("mgUuI%"), d.at(-1)), n.cls(AL + "/%"), 3)
    freq = whole(words(DOSE_FREQ + ["stage", "grade", "type", "positive", "negative", "reactive", "status", "detected",
                                     "inhaler", "इन्हेलर", "இன்ஹேலர்"]))
    stagev = n.AND(n.cls(D + "IVXab"), n.OR(n.lit("stage ", nocase=True), n.lit("grade ", nocase=True), n.lit("type ", nocase=True)).at(-6))
    attach = n.OR(num, unit, unit_glued, freq, n.cls("-/()"), force=True)
    labs = n.fill(n.cls(AN), words(LABS, nocase=False), 3)
    tok = n.OR(core, attach, force=True)
    lab_end = n.AND(labs, ~labs.at(1))
    lab_reach = n.prop_right(lab_end, n.cls(' :="\\\''), 2)
    lab_val = n.prop_right(n.AND(n.cls(D), lab_reach.at(-1), ~labs, ~n.cls(AN).at(-1)), n.cls(D + ".%/"), 3)
    c.add("HEALTH", n.AND(lab_val, n.OR(personal, clinical_context(c))), 1)
    joint = n.AND(n.cls(" :="), tok.at(-1), tok.at(1))
    chain = n.OR(tok, joint, force=True)
    # modifiers and a noun on the left of a condition head ("severe shellfish allergy", "panic attacks", "early Parkinson's")
    fw = whole(words([w for w in FUNCTION_WORDS if w.isalpha()] + ["has", "have", "had", "with", "for", "from", "is", "was",
                                                                      "on", "takes", "taking", "started", "stopped", "known"]))
    mods = whole(words(COND_MODS))
    # a noun modifier: a lower-case word of 3+ letters, not after an apostrophe, not a verb in -s ("says", "takes")
    wst = n.AND(low, ~low.at(-1), ~n.cls("'").at(-1), low.at(1), low.at(2))
    s_end = n.fill(low, n.AND(n.cls("s"), ~low.at(1), ~n.cls("s").at(-1)), 4)
    noun = n.AND(n.fill(low, wst, 4), ~fw, ~s_end)
    left = n.OR(mods, noun, force=True)
    lj = n.AND(sp, left.at(-1), n.OR(core, left).at(1))
    lchain = n.OR(left, lj, force=True)
    lext = n.prop_left(n.AND(core, ~core.at(-1)), n.OR(lchain, force=True), 5)
    lspan = n.AND(n.OR(lchain, core, force=True), lext)
    seeds = n.AND(core, gate)
    span = n.OR(n.fill(chain, seeds, 5), n.AND(lspan, n.prop_left(seeds, n.OR(lchain, core, force=True), 5)), force=True)
    # the span ends on a token, never on a joint
    span = n.AND(span, ~n.AND(n.cls(" :=-/("), ~span.at(1)))
    c.add("HEALTH", span, 1)
