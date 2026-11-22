"""Dates (including dates of birth) and times of day."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)


def dates(c: Ctx):
    """One shape family, two labels. Measured on dev: with a birth cue it is a birth date; with
    no date-ish cue an old year (before 2006) or a Month/yy form is a birth date; else a date."""
    n = c.n
    # numeric parts are checked: a year 1700-2199, a month 01-12, a day 01-31 ("8517.62.00" is a tariff code)
    Y4 = r"(17|18|19|20|21)\d\d"
    MM = "(" + "|".join(f"{i:02d}" for i in range(1, 13)) + ")"
    DD = "(" + "|".join(f"{i:02d}" for i in range(1, 32)) + ")"
    D12 = "(" + "|".join([f"{i:02d}" for i in range(1, 32)] + [str(i) for i in range(1, 32)]) + ")"
    pats = (rf"{DD}/{DD}/{Y4}", rf"{Y4}-{MM}-{DD}T\d{{2}}:\d{{2}}:\d{{2}}", rf"{Y4}-{MM}-{DD}",
            rf"\d{{1,2}}(st|nd|rd|th) {MONTHS} \d{{4}}", rf"{MONTHS} \d{{1,2}}(st|nd|rd|th), \d{{4}}",
            rf"{MONTHS} \d{{1,2}}, \d{{4}}")
    pats += (rf"{Y4}\.{MM}\.{DD}", rf"{DD}\.{DD}\.{Y4}", rf"{D12}/{D12}/{Y4}", rf"{Y4}/{MM}/{DD}", rf"{DD}-{DD}-{Y4}",
             rf"\d{{1,2}} {MONTHS} \d{{4}}", rf"\d{{1,2}} {MON3} \d{{4}}", rf"{MON3} \d{{1,2}}, \d{{4}}",
             rf"{DAY3}, \d{{1,2}} {MON3} \d{{4}}", rf"{MONTHS} \d{{4}}", rf"\d{{1,2}}(st|nd|rd|th) of {MONTHS},? \d{{4}}",
             rf"\d{{1,2}} {MONTHS},? \d{{4}}", rf"{D12}/{D12}/\d{{2}}", rf"\d{{1,2}} {MON3} \d{{2}}", rf"{DD}\.{DD}\.\d{{2}}")
    if general():
        o = "(st|nd|rd|th)"
        pats += (rf"\d{{1,2}}{o} {MONTHS_ANY},? \d{{4}}", rf"\d{{1,2}}{o} {MONTHS_ANY}", rf"\d{{1,2}} {MONTHS_ANY},? \d{{4}}",
                 rf"{MONTHS_ANY} \d{{1,2}}{o},? \d{{4}}", rf"{MONTHS_ANY} \d{{1,2}}{o}", rf"\d{{1,2}}{o} of {MONTHS_ANY},? \d{{4}}",
                 rf"\d{{1,2}}{o} of {MONTHS_ANY}", rf"\d{{1,2}} {MONTHS}", rf"{MONTHS} \d{{1,2}}",
                 rf"{D12} {MON3}", rf"{MON3} {D12}")          # "on 3 Dec", "Dec 14": day and short month, no year
    if general():
        up3 = "(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
        hi_m = "(" + "|".join(u(w) for w in ("जनवरी", "फ़रवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
                                             "सितंबर", "सितम्बर", "अक्टूबर", "नवंबर", "नवम्बर", "दिसंबर", "दिसम्बर")) + ")"
        pats += (rf"\d{{1,2}} {up3} \d{{4}}", rf"\d{{1,2}}{up3}\d{{4}}", rf"\d{{1,2}} {hi_m} \d{{4}}")
    full = n.OR(*[c.P(p, pre=WORD + "/-.", post=WORD + "/")[0] for p in pats], force=True)
    short, _ = c.P(rf"{MONTHS}/\d{{2}}", pre=WORD + "/-", post=WORD + "/")
    date = n.OR(full, short, force=True)
    d = n.cls(D)
    year = n.AND(n.run(d, 4), ~d.at(-1), ~d.at(4))
    old = n.AND(year, n.OR(n.lit("19"), n.AND(n.lit("200"), n.cls("012345").at(3))))
    start = n.AND(date, ~date.at(-1))
    near = lambda words, k: n.AND(start, n.spread_right(n.OR(*[n.lit(w, nocase=True) for w in words]), k))
    if general():   # the birth cue binds to the first date after it, not to every date nearby
        cue_b = n.OR(*[n.lit(w, nocase=True) for w in ("birth", "born", "dob", "birthday", "d.o.b", "date of b", "bday", "b'day",
                                                       "geburtsdatum", "geboren", "nacimiento", "nacido", "nacida", "naissance",
                                                       u("né le"), u("née le"), "nascimento", "nascita", "nato il", "nata il",
                                                       u("doğum"), "geb.")],
                     *[n.lit(u(w)) for w in ("जन्म", "பிறந்த", "生年月日", "تاريخ الميلاد", "생년월일")])
        birth = n.fill(date, n.AND(start, n.prop_right(cue_b, n.cls("".join(chr(i) for i in range(32, 127) if not chr(i).isdigit())), 5).at(-1)))
    else:
        birth = n.fill(date, near(["birth", "born", "dob", "bod"], 45))
    datecue = n.fill(date, near(["date", " on ", "time", "day"], 45))
    oldish = n.OR(n.fill(date, n.AND(date, old)), short)
    if general():   # "Priya (07/11/1984)": a date in parentheses right after a name-like word
        paren = n.AND(start, n.cls("(").at(-1), n.cls(" ").at(-2), n.cls(AL).at(-3))
        birth = n.OR(birth, n.fill(date, paren))
    bod = birth if general() else n.OR(birth, n.AND(oldish, ~datecue))
    c.add("BOD", bod)
    c.add("DATE", n.AND(date, ~bod))


def times(c: Ctx):
    n = c.n
    d, dash, sp = n.cls(D), n.cls("-"), n.cls(" ")
    ap = "(AM|PM|am|pm)"
    in_range_l = n.OR(n.AND(dash.at(1), d.at(2)), n.AND(sp.at(1), dash.at(2), sp.at(3), d.at(4)))
    in_range_r = n.OR(dash.at(-1), n.AND(dash.at(-2), sp.at(-1)))
    kw = dict(pre=WORD + ":.+", post=WORD + ":", start_terms=[] if general() else [~in_range_r],
              end_terms=[] if general() else [~in_range_l])
    for pat in (r"\d{1,2}:\d{2}", r"\d{1,2}:\d{2}:\d{2}", rf"\d{{1,2}}:\d{{2}} ?{ap}", rf"\d{{1,2}} ?{ap}",
                rf"\d{{1,2}}:\d{{2}}:\d{{2}} ?{ap}", r"\d{1,2}:\d{2} ?(a\.m\.|p\.m\.)",
                r"\d{1,2} o'clock", rf"\d{{1,2}} o'clock {ap}"):
        c.add("TIME", c.P(pat, **kw)[0])
    # a bare 1-2 digit number: a time when it follows " at " or stands alone as a quoted/bracketed field
    at = n.AND(n.lit(" at ").at(-4))
    opener, closer = n.cls("\"'[<*`").at(-1), n.cls("\"']>*`").at(1)
    c.add("TIME", c.P(r"\d{1,2}", start_terms=[at], end_terms=[~n.cls(":").at(1), ~n.AND(sp.at(1), n.cls(UP).at(2))])[0], 2)
    c.add("TIME", c.P(r"\d{1,2}", pre=None, post=None, start_terms=[opener, ~n.cls("=").at(-2)],
                      end_terms=[closer, ~n.AND(n.cls("\"'").at(1), n.cls(":").at(2))])[0], 2)
