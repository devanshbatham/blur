"""Differential tests: every circuit is checked against an independent reference regex on
random positives, near-miss mutations and noise. The regexes exist only here, never at inference."""
import random
import re
import string

import numpy as np
import pytest

from blur import patterns
from blur.secrets import circuits
from blur.dsl import Net
from blur.engine import Engine
from blur.secrets.table import TOKENS

RNG = random.Random(7)
NOISE = string.ascii_letters + string.digits + " \n\t=:\"'-_./+@()[]{},;"


def engine(*parts):
    return Engine(circuits.build(list(parts)))


def mask_of(eng, text, label):
    return eng.forward(text.encode())[:, eng.labels.index(label)]


def regex_mask(rx, text):
    m = np.zeros(len(text), bool)
    for hit in re.finditer(f"(?=({rx}))", text):
        m[hit.start(1):hit.end(1)] = True
    return m


def noise(k):
    return "".join(RNG.choice(NOISE) for _ in range(k))


def mutate(tok):
    i = RNG.randrange(len(tok))
    op = RNG.randrange(3)
    if op == 0:
        return tok[:i] + tok[i + 1:]
    if op == 1:
        return tok[:i] + RNG.choice(NOISE) + tok[i + 1:]
    return tok[:i] + RNG.choice(NOISE) + tok[i:]


def test_primitives():
    n = Net()
    a, d = n.cls("a"), n.cls(string.digits)
    n.out("run3", n.run(d, 3))
    n.out("run5", n.run(d, 5))
    n.out("right", n.prop_right(a, d, 3))
    n.out("left", n.prop_left(a, d, 3))
    n.out("spr4", n.spread_right(a, 4))
    eng = Engine(n.compile())
    text = "x12345a1234567890123456789012 99a x a..."
    m = eng.forward(text.encode())
    get = lambda lab: "".join("1" if v else "." for v in m[:, eng.labels.index(lab)])
    ref = lambda rx: "".join("1" if v else "." for v in regex_mask(rx, text))
    assert get("run3") == "".join("1" if re.match(r"\d{3}", text[i:]) else "." for i in range(len(text)))
    assert get("run5") == "".join("1" if re.match(r"\d{5}", text[i:]) else "." for i in range(len(text)))
    assert get("right") == ref(r"a\d{0,15}")
    assert get("left") == ref(r"\d{0,15}a")
    assert get("spr4") == ref(r"a.{0,3}")


def token_regex(pats, tail, endb):
    alts = []
    for p in pats:
        body = "".join(f"[{''.join(re.escape(chr(c)) for c in sorted(cs))}]{{{k}}}" for cs, k in patterns.parse(p))
        if tail:
            body += tail + "*"
        if endb:
            body += f"(?!{endb})"
        alts.append(body)
    return "(?<![A-Za-z0-9])(?:" + "|".join(alts) + ")"


def test_provider_tokens_match_reference():
    eng = engine(circuits.provider_tokens)
    rx = "|".join(token_regex(p, t, e) for _, p, t, e in TOKENS)
    docs = []
    for _, pats, tail, _ in TOKENS:
        for p in pats:
            for _ in range(6):
                tok = patterns.sample(p, RNG)
                if tail and RNG.random() < 0.5:
                    tok += "".join(RNG.choice(string.ascii_letters + string.digits) for _ in range(RNG.randrange(40)))
                for variant in (tok, mutate(tok), tok[:-1], RNG.choice(NOISE) + tok):
                    docs.append(noise(RNG.randrange(20)) + RNG.choice(" ='\":\n") + variant + noise(RNG.randrange(20)))
    for text in docs:
        got, want = mask_of(eng, text, "SECRET"), regex_mask(rx, text)
        assert (got == want).all(), (text, got.nonzero()[0], want.nonzero()[0])


CASES = {
    "EMAIL": (circuits.email, [
        ("mail jane.doe+tag@sub.example.co.uk now", "jane.doe+tag@sub.example.co.uk"),
        ("a@b.com.", "a@b.com"), ("<x_y@host-1.io>", "x_y@host-1.io"),
        ("not@email", None), ("@handle and a@b", None), ("git@github.com:org/repo", "git@github.com")]),
    "IPV4": (circuits.ipv4, [
        ("host 192.168.1.100:8080", "192.168.1.100"), ("ip=8.8.8.8.", "8.8.8.8"),
        ("256.1.1.1", None), ("1.2.3", None), ("v1.2.3.4.5", None), ("12.34.56.789", None)]),
    "SSN": (circuits.ssn, [
        ("SSN 250-38-8116.", "250-38-8116"), ("000-12-3456", None), ("900-12-3456", None),
        ("1250-38-8116", None), ("250-38-81167", None), ("2023-05-17", None)]),
    "PHONE": (circuits.phone, [
        ("call 707-859-9753 now", "707-859-9753"), ("(415) 555-2671", "(415) 555-2671"),
        ("+1 415.555.2671", "+1 415.555.2671"), ("1-800-555-0199", "1-800-555-0199"),
        ("+44 20 7946 0958", "+44 20 7946 0958"), ("+91-98765-43210", "+91-98765-43210"),
        ("2023-05-17", None), ("192.168.100.1234", None), ("id 123-456-7890", None)]),
    "MAC": (circuits.mac, [
        ("mac 00:24:81:A7:B2:F9;", "00:24:81:A7:B2:F9"), ("00-24-81-a7-b2-f9", "00-24-81-a7-b2-f9"),
        ("00:24:81:A7:B2", None), ("00:24:81:A7:B2:F9:11", None)]),
    "CARD": (circuits.credit_card, [
        ("card 4111 1111 1111 1111 ok", "4111 1111 1111 1111"), ("4111111111111111", "4111111111111111"),
        ("5500-0000-0000-0004", "5500-0000-0000-0004"), ("378282246310005", "378282246310005"),
        ("3782 822463 10005", "3782 822463 10005"), ("4111 1111 1111 1112", None),
        ("4111111111111121", None), ("14111111111111111", None)]),
    "SECRET": (None, [
        ('password = "hunter2hunter"', "hunter2hunter"),   # (KEY=value lines are read by blur/general/keys.py: tests/secrets_edge)
        ('"api_key": "a8f3k29dk20dk3"', "a8f3k29dk20dk3"), ("password: str = None", None),
        ("token = os.environ['TOKEN_V2_NAME']", None), ("secret = hashlib.sha256(data)", None),
        ("password = your_password_123", None), ("max_tokens: 4096000000", None),
        ("postgres://admin:s3cr3tPass@db.internal:5432/app", "s3cr3tPass"),
        ("http://localhost:8080/path@x", None),
        # (the documentation JWT, payload {"sub":"1234567890"}, is deliberately not reported)
        ("auth eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLTQyIiwicm9sZSI6ImFkbWluIn0.Qm8xZXlLaFhUcWdzRzNZcjdKbm9wUQ ok",
         "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLTQyIiwicm9sZSI6ImFkbWluIn0.Qm8xZXlLaFhUcWdzRzNZcjdKbm9wUQ"),
        ("x\n-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA7q2Vt8RzK1pW7nY3bH6jD0sC\nabc/+==\n-----END RSA PRIVATE KEY-----\nbye",
         "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA7q2Vt8RzK1pW7nY3bH6jD0sC\nabc/+==\n-----END"),
        ("-----BEGIN PUBLIC KEY-----\nMIIB\n-----END PUBLIC KEY-----", None)]),
}


@pytest.mark.parametrize("label", list(CASES))
def test_examples(label):
    part, cases = CASES[label]
    eng = engine(part) if part else engine(*circuits.SECRET_PARTS)
    for text, want in cases:
        got = [text.encode()[a:b].decode() for a, b, lab in eng.spans(text) if lab == label]
        assert got == ([want] if want else []), (text, got)


def luhn_ok(digits):
    total = 0
    for j, ch in enumerate(reversed(digits)):
        v = int(ch)
        if j % 2:
            v = v * 2 - 9 if v >= 5 else v * 2
        total += v
    return total % 10 == 0


def test_luhn_circuit_is_exact():
    eng = engine(circuits.credit_card)
    for _ in range(600):
        k = RNG.choice([15, 16])
        digs = RNG.choice("34" if k == 15 else "23456") + "".join(RNG.choice(string.digits) for _ in range(k - 1))
        if k == 15:
            digs = "3" + digs[1:]
        text = RNG.choice([digs, " ".join([digs[:4], digs[4:8], digs[8:12], digs[12:]])]) if k == 16 else digs
        hit = any(lab == "CARD" for _, _, lab in eng.spans("n " + text + " n"))
        want = luhn_ok(digs) and (k == 16 or digs[1] in "0123456789")
        assert hit == want, (text, hit, want)


def test_match_agrees_with_regex():
    from blur.patterns import parse_var
    cases = [(r"\d{1,3}\.\d{1,3}", r"0-9."), (r"[a-z]+\d{2,4}", "a-z0-9"), (r"[A-Z]{2}\d{5}[A-Z]{2}", "A-Z0-9"),
             (r"\d{1,2}:\d{2} ?[AP]M", "0-9A-Z"), (r"ab*c", "a-z"), (r"(ab|c)x?(M|PM)", "a-zA-Z")]
    for pat, bound in cases:
        n = Net()
        from blur.patterns import byteset
        import re as _re
        bset = byteset("".join(chr(c) for c in range(128) if _re.match(f"[{bound}]", chr(c))))
        span, _ = n.match(parse_var(pat), pre=bset, post=bset)
        n.out("M", span)
        eng = Engine(n.compile())
        rx = f"(?<![{bound}])(?:{pat})(?![{bound}])"
        alphabet = "ab cxAPM0123459.:ZQ"
        for _ in range(300):
            text = "".join(RNG.choice(alphabet) for _ in range(RNG.randrange(1, 40)))
            got = eng.forward(b"\0" * 8 + text.encode() + b"\0" * 8)[8:-8, 0]
            want = np.zeros(len(text), bool)
            for h in re.finditer(rx, text):
                want[h.start():h.end()] = True
            # the circuit marks every maximal match; regex finditer is leftmost-greedy and can
            # differ only when one match is a suffix of a longer overlapping one
            assert (got == want).all(), (pat, text, got.nonzero()[0], want.nonzero()[0])
