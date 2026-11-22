"""Measurements: units, scientific notation, measured values and quantities, and numeric field labels."""
from .words import *  # noqa: F401,F403  (word-part vocabulary and shared imports)


def measurements(c, k):
    NAMES = k.NAMES
    add_veto = k.add_veto
    alnum = k.alnum
    cls = k.cls
    ctx_not = k.ctx_not
    digit = k.digit
    duri = k.duri
    hexc = k.hexc
    letters = k.letters
    n = k.n
    not_secret_ctx = k.not_secret_ctx
    sp = k.sp
    # ================= measurements: units, scientific notation, field labels =================
    # a unit expression is a measurement, never a secret, id or handle: "10^3/uL", "mg/dL", "mmol/L", "mL/min/1.73m2", "x 10^9/L"
    BV = lambda t: t.encode("utf-8").decode("latin-1")                        # a literal in byte view
    UNITS = ("uL", "µL", "mL", "dL", "L", "l", "ml", "dl", "g", "mg", "mcg", "µg", "ug", "ng", "pg", "kg", "mol", "mmol", "umol", "µmol",
             "nmol", "pmol", "mEq", "IU", "mIU", "U", "mU", "cells", "min", "hr", "h", "s", "sec", "day", "d", "wk", "m", "m2", "cm", "mm",
             "mmHg", "kPa", "bpm", "Hz", "fL", "pg", "copies", "IU/mL", "kcal", "cal",
             "Ki", "Mi", "Gi", "Ti", "Pi", "KB", "MB", "GB", "TB", "PB", "kB", "KiB", "MiB", "GiB", "TiB", "ms", "ns", "us", "µs",
             "Mbps", "Gbps", "kbps", "GHz", "MHz", "kHz", "kWh", "mAh", "rpm", "fps", "dpi", "px", "pt", "em", "rem", "vh", "vw",
             "bytes", "byte", "bits", "inch", "inches", "ft", "feet", "foot", "yd", "mile", "miles", "km", "metre", "meter", "metres", "meters",
             "litre", "liter", "litres", "liters", "gallon", "gallons", "oz", "lb", "lbs", "mins", "minutes", "hours", "hrs", "seconds", "secs",
             "days", "weeks", "months", "years", "core", "cores", "seater", "watt", "watts", "volt", "volts", "amp", "amps")
    unit_w = n.OR(*[n.AND(n.lit(BV(u)), ~letters.at(-1), ~alnum.at(len(BV(u)))) for u in UNITS], force=True)
    unit_tok = n.OR(*[n.spread_right(n.AND(n.lit(BV(u)), ~letters.at(-1), ~alnum.at(len(BV(u)))), len(BV(u))) for u in UNITS], force=True)
    unitc = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789^./\xb5\xc2")
    sci = n.AND(n.lit("10^"), ~digit.at(-1))                                  # 10^3, 10^9
    ratio = n.AND(cls("/"), n.OR(unit_w.at(1), digit.at(1), force=True), n.OR(unit_tok.at(-1), digit.at(-1), cls("^").at(-2), force=True))
    meas_tok = n.prop_right(n.AND(unitc, ~unitc.at(-1)), unitc, 5)
    meas_tok = n.AND(meas_tok, n.fill(meas_tok, n.OR(n.AND(meas_tok, sci), n.AND(meas_tok, ratio), force=True), 5),
                     ~n.fill(meas_tok, n.AND(meas_tok, letters, ~unit_tok), 5),           # no letter outside a unit word
                     n.fill(meas_tok, n.AND(meas_tok, n.OR(unit_tok, sci, force=True)), 5))   # and a unit or 10^ in it ("98765/43210" is not)
    add_veto(("SECRET", "PASS", "ID", "USERNAME", "TEL", "CARD", "IDCARD", "COOKIE"), meas_tok)
    # a number followed by a unit or "x 10^" is a measured value ("250 x 10^3/uL", "98 mg/dL", "37.2 °C", "42.0%")
    numv = n.prop_right(n.AND(digit, ~n.OR(alnum, cls(".,"), force=True).at(-1)), n.OR(digit, n.AND(cls(".,"), digit.at(1)), force=True), 4)
    num_end = n.AND(numv, ~numv.at(1))
    unit_w2 = n.AND(unit_w, letters.at(1))                                       # a unit of two or more letters ("11-inch", not "-L")
    after_unit = n.OR(n.AND(sp.at(1), unit_w.at(2)), unit_w.at(1), n.AND(cls("-").at(1), unit_w2.at(2)), n.lit(" x 10^").at(1), n.lit(BV(" × 10^")).at(1), n.AND(cls("%").at(1), ~n.AND(hexc.at(2), hexc.at(3))),    # "%2F" is URL encoding, not percent
                      n.lit(BV(" °")).at(1), n.lit(BV("°")).at(1), force=True)
    measured = n.AND(numv, n.fill(numv, n.AND(num_end, after_unit), 4))
    add_veto(("TEL", "ID", "CARD", "SOCIALNUMBER", "IDCARD", "PASSPORT", "POSTCODE", "BUILDING"), measured)   # (not secrets: "7g+Zk1/...")
    ctx_not["ID"] = n.OR(ctx_not["ID"], measured, meas_tok, force=True)
    # a whole token that is a number with a unit attached ("512Mi", "500m", "2GB", "250ms", "16px") is a quantity, never a
    # password; "7g+Zk1/..." is not a whole quantity token
    qstart = n.AND(digit, n.OR(cls(" \t\n\"'`(=:,{[<>"), cls("\x00"), force=True).at(-1))
    qnum = n.prop_right(qstart, n.OR(digit, n.AND(cls(".,"), digit.at(1)), force=True), 4)
    qend = n.AND(qnum, ~qnum.at(1))
    unit_m = n.OR(unit_w, n.AND(cls("m"), ~alnum.at(1)), force=True)          # Kubernetes millicores: "500m"
    unit_span = n.spread_right(n.AND(unit_m.at(1), qend), 6)
    unit_close = n.AND(unit_span, alnum, ~alnum.at(1), ~cls("+/=_-@").at(1))
    qty = n.fill(n.OR(qnum, n.AND(unit_span, alnum), force=True), unit_close, 4)
    add_veto(("SECRET", "PASS", "COOKIE", "USERNAME"), n.AND(qty, qnum))
    # a label before a colon whose value is a number, at the start of a line or a list item, names a field, not a person
    # ("- Platelets: 250 x 10^3/uL", "1. Weight: 68 kg", "* Heart rate: 72 bpm")
    bullet_start = n.OR(n.prop_right(n.OR(cls("\n"), cls("\x00"), force=True), n.OR(sp, cls("-*>"), n.lit(BV("•")), n.AND(digit, cls(".)").at(1)),
                                                                                   n.AND(cls(".)"), digit.at(-1)), force=True), 5).at(-1), force=True)
    fld = n.prop_right(n.AND(letters, bullet_start), n.OR(letters, n.AND(cls(" ()-/"), alnum.at(1)), cls(")"), force=True), 5)
    fld_end = n.AND(fld, cls(":").at(1))
    num_value = n.OR(n.AND(sp.at(2), digit.at(3)), n.AND(sp.at(2), cls("<>~").at(3)), digit.at(2), force=True)
    field_label = n.fill(fld, n.AND(fld_end, num_value), 5)
    add_veto(NAMES + ("USERNAME", "CITY", "ORG"), field_label)
    ctx_not["NAME"] = n.OR(ctx_not["NAME"], field_label, force=True)
    ctx_not["SECRET"] = n.OR(ctx_not["SECRET"], not_secret_ctx, duri, force=True)     # paths, worked encodings, data: payloads
