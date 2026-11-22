"""Python twin of web/normalize.js: the same fixed table, the same offset map (character offsets)."""
import re
import unicodedata

DROP = re.compile("[​-‏‪-‮⁦-⁩﻿­͏؜]")
SPACE = re.compile("[   -   　]")
DIGIT_BASES = [0x0660, 0x06F0, 0x07C0, 0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0x0DE6, 0x0E50,
               0x0ED0, 0x0F20, 0x1040, 0x17E0, 0x1810, 0xFF10]
HOMO = dict(zip("аеорсхуіјѕԁɡАВЕКМНОРСТХІЈΑΒΕΖΗΙΚΜΝΟΡΤΥΧον", "aeopcxyijsdgABEKMHOPCTXIJABEZHIKMNOPTYXov"))
ASCII_WORD = re.compile(r"[A-Za-z0-9@._-]")
OCR_MAP = {"l": "1", "I": "1", "|": "1", "O": "0"}   # scanning errors inside numbers (a digit on both sides)
OCR_END_MAP = {"O": "0", "o": "0", "I": "1", "l": "1", "G": "6", "S": "5", "B": "8", "Z": "2"}   # closing a phone-like digit group
ENTITY = re.compile(r"&(#\d{1,6}|#x[0-9a-fA-F]{1,5}|amp|lt|gt|quot|apos|nbsp);")
NAMED = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " "}


def _digit(cp):
    for b in DIGIT_BASES:
        if b <= cp < b + 10:
            return chr(48 + cp - b)
    return None


def normalize(text):
    out, mp = [], []
    k = -1
    while k + 1 < len(text):
        k += 1
        ch = text[k]
        cp = ord(ch)
        if ch == "&":
            e = ENTITY.match(text, k)
            if e:
                n = e.group(1)
                r = chr(int(n[2:], 16) if n[:2] == "#x" else int(n[1:])) if n[0] == "#" else NAMED[n]
                for x in r:
                    out.append(x)
                    mp.append(k)
                k = e.end() - 1
                continue
        if DROP.match(ch):
            continue
        if unicodedata.category(ch).startswith("M") and k > 0 and text[k - 1].isascii() and text[k - 1].isalpha():
            continue
        r = ch
        if (ch in OCR_END_MAP and re.fullmatch(r"\d{4}", text[max(0, k - 4):k] or "x") and re.search(r"\d{4,5}[ -]$", text[max(0, k - 10):max(0, k - 4)])
                and not (k + 1 < len(text) and text[k + 1].isascii() and text[k + 1].isalnum()) and not (k >= 11 and text[k - 11].isascii() and text[k - 11].isalpha())):
            r = OCR_END_MAP[ch]
        elif ch in OCR_MAP and 0 < k < len(text) - 1 and text[k - 1].isdigit() and text[k + 1].isdigit() and text[k - 1].isascii() and text[k + 1].isascii():
            r = OCR_MAP[ch]
        elif SPACE.match(ch):
            r = " "
        elif 0xFF01 <= cp <= 0xFF5E:
            r = chr(cp - 0xFEE0)
        elif _digit(cp):
            r = _digit(cp)
        elif ch in HOMO and ((k > 0 and ASCII_WORD.match(text[k - 1])) or (k + 1 < len(text) and ASCII_WORD.match(text[k + 1]))):
            r = HOMO[ch]
        elif 0x1D400 <= cp <= 0x1D7FF:
            f = unicodedata.normalize("NFKC", ch)
            r = f if len(f) == 1 else ch
        for x in r:
            out.append(x)
            mp.append(k)
    mp.append(len(text))
    return "".join(out), mp
