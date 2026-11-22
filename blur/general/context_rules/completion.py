"""Completing values: a stated password is its whole token; handles under author and user keys and in sign-offs."""
from .words import *  # noqa: F401,F403  (word-part vocabulary and shared imports)


def complete_values(c, k):
    NAMES = k.NAMES
    P = k.P
    add_veto = k.add_veto
    allb = k.allb
    alnum = k.alnum
    cls = k.cls
    digit = k.digit
    letters = k.letters
    lower = k.lower
    n = k.n
    sp = k.sp
    upper = k.upper
    # ================= recall: complete values =================
    # (11) a stated password is the whole token after the cue, symbols included ("River2023#", "SunnyBeach$WaveRide",
    #      "Sunset!RiverFlows", "PurpleElephant@FlyingFish"); a plain word is not one ("the password reset", "password for")
    _, pw_end = P(G("password ", "Password ", "PASSWORD ", "password: ", "Password: ", "password is ", "Password is ", "password was ",
                    "passcode ", "passcode is ", "passcode: ", "passphrase ", "passphrase is ", "passphrase: ", "Wi-Fi password ", "wifi password ",
                    "password like ", "password, ", "password = ", "password=", "pwd: ", "pwd=", "pass: "), pre="A-Za-z_")
    nonsp = cls(allb.replace(" ", "").replace("\n", "").replace("\t", "").replace('"', "").replace("'", "").replace("`", "").replace("&", "").replace(";", "").replace("<", ""))
    pwv = n.prop_right(n.AND(nonsp, ~cls("([{<").at(0) if False else nonsp, pw_end.at(-1)), nonsp, 6)
    pwv = n.AND(pwv, ~n.AND(cls(".,;:)!?*"), ~nonsp.at(1), ~cls("!$#@%^&*").at(0) if False else ~nonsp.at(1)))       # sentence punctuation at the end
    # (keep a trailing symbol that belongs to it: "River99$", "River1995!" - a ! or $ or # directly after a letter or digit)
    wsx = cls(" \n\t\"'`\x00")
    tok_end_ok = n.OR(wsx.at(1), n.AND(cls(".,;:").at(1), wsx.at(2)), force=True)
    pwv = n.OR(pwv, n.AND(cls("!$#@%^&*"), pwv.at(-1), alnum.at(-1), tok_end_ok), force=True)
    strong = n.OR(digit, cls("!@#$%^&*~+=?"), n.AND(upper, lower.at(-1)), force=True)          # a digit, a symbol or an inner capital
    pwv = n.AND(pwv, n.fill(pwv, n.AND(pwv, strong), 6), n.fill(pwv, n.run(nonsp, 6), 6))
    c.add("PASS", pwv, 0)
    c.add("SECRET", pwv, 0)              # the complete value, whichever circuit claimed part of it first
    add_veto(NAMES + ("USERNAME", "CITY", "ID", "TEL", "DATE"), pwv)
    # (12) handles under author / user keys and in sign-offs ("Author: aisha.al-fituri", "User ID,alison_kulavic",
    #      "User Name: LupitaGamer123", "Thanks,\ndavidtyra")
    _, au_end = P(G("Author:** ", "User Name:** ", "Username:** ", "User:** ", "Login:** ", "User ID:** ", "Handle:** ", "Author: ", "author: ", "User: ", "user: ", "User ID,", "User ID: ", "User Name: ", "Username: ", "username: ", "User name: ",
                    "Login: ", "login: ", "Handle: ", "handle: ", "Created by: ", "created by: ", "Assignee: ", "assignee: ", "Reviewer: ",
                    "Committer: ", "Owner: ", "Reported by: ", "Submitted by: ", "Modified by: ", "Approved by: "), pre="A-Za-z")
    hch = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")
    auv = n.prop_right(n.AND(hch, au_end.at(-1)), hch, 5)
    auv = n.AND(auv, ~n.AND(cls(".-"), ~hch.at(1)), ~sp.at(1) if False else auv)
    hshape = n.OR(cls("_0123456789"), n.AND(cls(".-"), alnum.at(-1), alnum.at(1)), n.AND(upper, lower.at(-1)), force=True)
    auv = n.AND(auv, n.fill(auv, n.OR(n.AND(auv, hshape), n.AND(auv, lower, ~auv.at(-1)), force=True), 5), ~n.fill(auv, n.AND(auv, ~auv.at(1), sp.at(1), upper.at(2)), 5))
    c.add("USERNAME", auv, 1)
    add_veto(("PASS", "SECRET", "GIVENNAME", "LASTNAME"), auv)
    # a capitalised word right after a first name is not a city ("Emily Hill", "Grace Dayton")
    gv = c.get("GIVENNAME")
    after_gv = n.prop_right(n.AND(upper, sp.at(-1), gv.at(-2), ~alnum.at(-1)), letters, 4)
    add_veto(("CITY", "STATE", "COUNTRY"), after_gv)
    if hasattr(c, "sur_word"):
        add_veto(("CITY", "STATE", "COUNTRY"), c.sur_word)
    _, so_end = P(G("Thanks,\n", "Thank you,\n", "Regards,\n", "Best regards,\n", "Best,\n", "Cheers,\n", "Sincerely,\n", "Warm regards,\n",
                    "Kind regards,\n", "Thanks!\n", "Cheers!\n"), pre="A-Za-z")
    sov = n.prop_right(n.AND(hch, so_end.at(-1)), hch, 5)
    sov = n.AND(sov, n.fill(sov, n.AND(sov, ~sov.at(1), n.OR(cls("\n"), cls("\x00"), force=True).at(1)), 5),
                n.fill(sov, n.OR(n.AND(sov, cls("_0123456789")), n.AND(sov, lower, ~sov.at(-1)), force=True), 5))     # a handle, not a capitalised name
    c.add("USERNAME", sov, 1)
    k.wsx = wsx
