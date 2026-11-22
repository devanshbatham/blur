"""Tiny fixed-length pattern language used to *specify* circuits (and, separately, to derive
reference regexes and random samples for differential testing).

Supported: literal chars, backslash escapes (\\. \\d \\w), [classes] with ranges, and {n} repeats.
No alternation and no variable repeats: every pattern has one fixed length.
"""
from __future__ import annotations

import random
import string

from .dsl import byteset

_W = string.ascii_letters + string.digits + "_"
HI = "".join(chr(c) for c in range(128, 256))  # bytes of multi-byte UTF-8 characters: treated as letters
_ESC = {"d": string.digits, "w": _W, "u": string.ascii_uppercase, "l": string.ascii_lowercase + HI,
        "a": string.ascii_letters + HI, "s": " \t", "h": string.hexdigits}


def parse(pattern: str) -> list[tuple[frozenset, int]]:
    parts, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "[":
            j = pattern.index("]", i + 1)
            chars, body, k = set(), pattern[i + 1:j], 0
            while k < len(body):
                if body[k] == "\\":
                    chars |= set(_ESC.get(body[k + 1], body[k + 1]))
                    k += 2
                elif k + 2 < len(body) and body[k + 1] == "-":
                    chars |= {chr(c) for c in range(ord(body[k]), ord(body[k + 2]) + 1)}
                    k += 3
                else:
                    chars.add(body[k])
                    k += 1
            i = j + 1
        elif ch == "\\":
            chars = set(_ESC.get(pattern[i + 1], pattern[i + 1]))
            i += 2
        else:
            chars = {ch}
            i += 1
        count = 1
        if i < len(pattern) and pattern[i] == "{":
            j = pattern.index("}", i)
            count = int(pattern[i + 1:j])
            i = j + 1
        parts.append((byteset("".join(chars)), count))
    return parts


def length(pattern: str) -> int:
    return sum(n for _, n in parse(pattern))


def sample(pattern: str, rng: random.Random) -> str:
    return "".join(chr(rng.choice(sorted(chars))) for chars, n in parse(pattern) for _ in range(n))


def parse_var(pattern: str) -> list[tuple[frozenset, int, int | None]]:
    """Like parse(), plus quantifiers {m,n} {m,} ? + * . Returns (byteset, lo, hi) with hi=None unbounded."""
    parts, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "(":
            j = pattern.index(")", i)
            words = tuple(pattern[i + 1:j].split("|"))
            i = j + 1
            lo = 1
            if i < len(pattern) and pattern[i] == "?":
                lo, i = 0, i + 1
            parts.append((words, lo, 1))
            continue
        if ch == "[":
            j = i + 1
            while pattern[j] != "]" or pattern[j - 1] == "\\":
                j += 1
            chars, body, k = set(), pattern[i + 1:j], 0
            while k < len(body):
                if body[k] == "\\":
                    chars |= set(_ESC.get(body[k + 1], body[k + 1]))
                    k += 2
                elif k + 2 < len(body) and body[k + 1] == "-":
                    chars |= {chr(c) for c in range(ord(body[k]), ord(body[k + 2]) + 1)}
                    k += 3
                else:
                    chars.add(body[k])
                    k += 1
            i = j + 1
        elif ch == "\\":
            chars = set(_ESC.get(pattern[i + 1], pattern[i + 1]))
            i += 2
        else:
            chars = {ch}
            i += 1
        lo = hi = 1
        if i < len(pattern) and pattern[i] in "?+*":
            lo, hi = {"?": (0, 1), "+": (1, None), "*": (0, None)}[pattern[i]]
            i += 1
        elif i < len(pattern) and pattern[i] == "{":
            j = pattern.index("}", i)
            a, _, b = pattern[i + 1:j].partition(",")
            lo = int(a)
            hi = lo if "," not in pattern[i + 1:j] else (int(b) if b else None)
            i = j + 1
        parts.append((byteset("".join(chars)), lo, hi))
    return parts
