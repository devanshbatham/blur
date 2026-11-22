"""Circuit DSL: every helper here only ever emits neurons of one form,

    out[i] = act(bias + sum_j w_j * x[src_j][i + off_j]),   w_j in {-1, +1}, bias <= 0 integer

i.e. a sparse ternary 1D convolution over the byte stream. There is no other primitive.
`compile()` turns the neuron graph into layers (by depth) of sparse ternary weights.
"""
from __future__ import annotations

import numpy as np


class Sig:
    """Reference to a channel read at a relative offset, optionally negated (inside AND only)."""

    __slots__ = ("ch", "off", "neg")

    def __init__(self, ch: int, off: int = 0, neg: bool = False):
        self.ch, self.off, self.neg = ch, off, neg

    def at(self, k: int) -> "Sig":
        return Sig(self.ch, self.off + k, self.neg)

    def __invert__(self) -> "Sig":
        return Sig(self.ch, self.off, not self.neg)


def byteset(chars) -> frozenset:
    if isinstance(chars, str):
        return frozenset(chars.encode("latin-1"))
    return frozenset(chars)


class Net:
    def __init__(self):
        self.kind: list[str] = []
        self.spec: list = []
        self.depth: list[int] = []
        self.boolean: list[bool] = []
        self._memo: dict = {}
        self._cache: dict = {}
        self.outputs: dict[str, list[Sig]] = {}

    # ---- primitives -------------------------------------------------------
    def _new(self, kind, spec, depth, boolean=True) -> int:
        key = (kind, spec)
        if key not in self._memo:
            self.kind.append(kind)
            self.spec.append(spec)
            self.depth.append(depth)
            self.boolean.append(boolean)
            self._memo[key] = len(self.kind) - 1
        return self._memo[key]

    def cls(self, chars) -> Sig:
        """Embedding channel: 1 where the byte is in `chars` (a row-lookup, {0,1} weights)."""
        return Sig(self._new("e", byteset(chars), 0))

    def neuron(self, conns, bias=0, act="clip", tag=0) -> Sig:
        conns = tuple(sorted(conns))
        assert bias <= 0 and any(w > 0 for _, _, w in conns), "neuron must be silent on silent input"
        assert all(w in (-1, 1) for _, _, w in conns)
        assert len({(c, o) for c, o, _ in conns}) == len(conns), "duplicate connection"
        depth = 1 + max(self.depth[c] for c, _, _ in conns)
        return Sig(self._new("n", (conns, bias, act, tag), depth, boolean=(act == "clip")))

    def vote(self, pos, neg, need: int = 2, tag="vote") -> Sig:
        """Evidence neuron: fires where (#active pos) - (#active neg) >= need. A signal may appear several
        times (it is then copied so each copy is a separate +1/-1 input); a signal on both sides cancels."""
        from collections import Counter
        key = lambda x: (x.ch, x.off)
        cp, cn = Counter(map(key, pos)), Counter(map(key, neg))
        conns = []
        for sign, cnt, other in ((1, cp, cn), (-1, cn, cp)):
            for (ch, off), k in cnt.items():
                k -= min(k, other.get((ch, off), 0))
                for j in range(k):
                    src = (ch, off) if j == 0 else (self.neuron([(ch, off, 1)], 0, tag=("copy", tag, j)).ch, 0)
                    conns.append((src[0], src[1], sign))
        return self.neuron(conns, -(need - 1), "clip", tag=tag)

    # ---- boolean logic ----------------------------------------------------
    def _split(self, sigs):
        pos, neg = {}, {}
        for s in sigs:
            assert self.boolean[s.ch], "logic gate on non-boolean channel"
            (neg if s.neg else pos)[(s.ch, s.off)] = 1
        assert pos, "gate needs at least one positive input"
        assert not (set(pos) & set(neg)), "x AND NOT x"
        return list(pos), list(neg)

    def _gate(self, pos, neg, bias, force=False) -> Sig:
        if len(pos) == 1 and not neg and bias == 0 and not force:
            return Sig(*pos[0])
        # Offsets are kept as written so each neuron lives at its natural text position
        # (normalising them lets a chain of shifts drift outside the buffer).
        conns = [(c, o, 1) for c, o in pos] + [(c, o, -1) for c, o in neg]
        return self.neuron(conns, bias)

    def AND(self, *sigs) -> Sig:
        pos, neg = self._split(sigs)
        return self._gate(pos, neg, -(len(pos) - 1))

    def OR(self, *sigs, force=False) -> Sig:
        pos, neg = self._split(sigs)
        assert not neg
        return self._gate(pos, [], 0, force)

    def atleast(self, t: int, *sigs) -> Sig:
        pos, neg = self._split(sigs)
        assert not neg and 1 <= t <= len(pos)
        return self._gate(pos, [], -(t - 1), force=True)

    # ---- sequence helpers -------------------------------------------------
    def run(self, c: Sig, n: int) -> Sig:
        """1 at i iff c[i..i+n-1] are all 1 (window STARTING at i). O(log n) neurons via doubling."""
        assert not c.neg and n >= 1
        key = ("run", c.ch, n)
        if key not in self._cache:
            base = Sig(c.ch)
            if n == 1:
                r = base
            else:
                p = 1 << ((n - 1).bit_length() - 1)  # largest power of two < n
                half = self.run(base, p)
                r = self.AND(half, half.at(n - p))
            self._cache[key] = r
        return self._cache[key].at(c.off)

    def spread_right(self, s: Sig, n: int) -> Sig:
        """1 at i iff s fired at some j in [i-n+1, i]."""
        key = ("spr", s.ch, n)
        if key not in self._cache:
            base = Sig(s.ch)
            if n == 1:
                r = base
            else:
                p = 1 << ((n - 1).bit_length() - 1)
                half = self.spread_right(base, p)
                r = self.OR(half, half.at(-(n - p)))
            self._cache[key] = r
        return self._cache[key].at(s.off)

    def spread_left(self, s: Sig, n: int) -> Sig:
        """1 at i iff s fired at some j in [i, i+n-1]."""
        key = ("spl", s.ch, n)
        if key not in self._cache:
            base = Sig(s.ch)
            if n == 1:
                r = base
            else:
                p = 1 << ((n - 1).bit_length() - 1)
                half = self.spread_left(base, p)
                r = self.OR(half, half.at(n - p))
            self._cache[key] = r
        return self._cache[key].at(s.off)

    def prop_right(self, seed: Sig, body: Sig, maxpow: int = 6) -> Sig:
        """Flood-fill rightwards: seed, plus every position reachable from a seed through an
        unbroken run of `body`, up to 2^(maxpow+1)-1 chars. Binary-decomposed hops, big to small."""
        s = seed
        for k in range(maxpow, -1, -1):
            w = 1 << k
            window_ending_here = self.run(body, w).at(-(w - 1))
            s = self.OR(s, self.AND(s.at(-w), window_ending_here))
        return s

    def prop_left(self, seed: Sig, body: Sig, maxpow: int = 6) -> Sig:
        s = seed
        for k in range(maxpow, -1, -1):
            w = 1 << k
            s = self.OR(s, self.AND(s.at(w), self.run(body, w)))
        return s

    def seq(self, parts) -> tuple[Sig, int]:
        """parts: list of (byteset, count). Returns (signal firing at first char, total length)."""
        terms, off = [], 0
        for chars, count in parts:
            terms.append(self.run(self.cls(chars), count).at(off))
            off += count
        return self.AND(*terms), off

    def lit(self, text: str, nocase: bool = False) -> Sig:
        parts = []
        for ch in text:
            chars = {ch.lower(), ch.upper()} if (nocase and ch.isascii()) else {ch}
            parts.append((byteset("".join(chars)), 1))
        return self.seq(parts)[0]

    def match(self, parts, pre=None, post=None, end_terms=(), start_terms=()):
        """Variable-length pattern as a forward state machine unrolled into layers.

        parts: list of (what, lo, hi). `what` is a byteset (a character class; hi=None means
        "as many as follow", up to 127) or a tuple of literal words (alternation; lo is 0 or 1).
        pre / post: bytesets that must NOT sit immediately before / after the match.
        start_terms / end_terms: extra signals ANDed at the first / last character.
        Returns (span mask, end signal firing on the last character).
        S[i] below means: the pattern so far has been matched with its last character at i."""
        guard = ([~self.cls(pre).at(-1)] if pre else []) + list(start_terms)
        if len(parts) == 1 and isinstance(parts[0][0], tuple):
            # a pure word alternation: each word is matched exactly, so a span can never run from the
            # start of one word to the end of another ("Georgia Brown lives in Georgia")
            spans, ends = [], []
            for w in parts[0][0]:
                L = len(w)
                post_t = [~self.cls(post).at(L)] if post else []
                hit = self.AND(self.lit(w), *guard, *post_t, *[t.at(L - 1) for t in end_terms])
                spans.append(self.spread_right(hit, L))
                ends.append(hit.at(-(L - 1)))
            return self.OR(*spans, force=True), self.OR(*ends, force=True)
        what0, lo0, hi0 = parts[0]
        assert lo0 >= 1, "first element cannot be optional"
        if isinstance(what0, tuple):
            firsts = [self.AND(self.lit(w), *guard) for w in what0]
            start = self.OR(*firsts)
            S = self.OR(*[f.at(-(len(w) - 1)) for f, w in zip(firsts, what0)])
        else:
            first = self.cls(what0)
            start = self.AND(first, *guard)
            if hi0 is None:
                S = self.prop_right(self.AND(start, self.run(first, lo0)).at(-(lo0 - 1)), first, 6)
            else:
                S = self.OR(*[self.AND(start, self.run(first, k)).at(-(k - 1)) for k in range(lo0, hi0 + 1)])
        for what, lo, hi in parts[1:]:
            if isinstance(what, tuple):
                opts = [S] if lo == 0 else []
                opts += [self.AND(S.at(-len(w)), self.lit(w).at(-(len(w) - 1))) for w in what]
                S = self.OR(*opts)
            elif hi is None:
                c = self.cls(what)
                seed = S if lo == 0 else self.AND(S.at(-lo), self.run(c, lo).at(-(lo - 1)))
                S = self.prop_right(seed, c, 6)
            else:
                c = self.cls(what)
                S = self.OR(*[S if k == 0 else self.AND(S.at(-k), self.run(c, k).at(-(k - 1)))
                              for k in range(lo, hi + 1)])
        end = self.AND(S, *([~self.cls(post).at(1)] if post else []), *end_terms)
        lens = [((min(map(len, w)) * lo, max(map(len, w)) * hi) if isinstance(w, tuple)
                 else (lo, 127 if hi is None else hi)) for w, lo, hi in parts]
        shortest, longest = sum(a for a, _ in lens), sum(b for _, b in lens)
        if shortest == longest:
            return self.spread_left(end, longest), end
        k = max(0, min(8, longest.bit_length() - 1))
        chars = frozenset()
        for w, _, _ in parts:
            chars |= frozenset(ord(ch) for word in w for ch in word) if isinstance(w, tuple) else w
        union = self.cls(chars)
        # Exact starts: run the pattern backwards from confirmed ends. T[i] means: the remaining
        # parts match starting at i and finish on a confirmed end.
        T = end.at(-1)
        for what, lo, hi in reversed(parts):
            if isinstance(what, tuple):
                opts = [T] if lo == 0 else []
                opts += [self.AND(T.at(len(w)), self.lit(w)) for w in what]
                T = self.OR(*opts)
            elif hi is None:
                c = self.cls(what)
                T = self.prop_left(T if lo == 0 else self.AND(T.at(lo), self.run(c, lo)), c, 6)
            else:
                c = self.cls(what)
                T = self.OR(*[T if j == 0 else self.AND(T.at(j), self.run(c, j)) for j in range(lo, hi + 1)])
        begin = self.AND(T, start)
        return self.AND(self.prop_right(begin, union, k), self.prop_left(end, union, k)), end

    def fill(self, mask: Sig, seed: Sig, maxpow: int = 5) -> Sig:
        """Flood `seed` through the connected run of `mask` it sits in (both directions)."""
        return self.AND(mask, self.OR(self.prop_right(seed, mask, maxpow), self.prop_left(seed, mask, maxpow)))

    def out(self, label: str, sig: Sig) -> None:
        self.outputs.setdefault(label, []).append(sig)

    # ---- compilation ------------------------------------------------------
    def compile(self) -> dict:
        finals = {lab: self.OR(*sigs, force=True) for lab, sigs in self.outputs.items()}
        for lab, s in finals.items():
            if s.off != 0:
                finals[lab] = self.neuron([(s.ch, s.off, 1)], 0, tag=("out", lab))
        need, stack = set(), [s.ch for s in finals.values()]
        while stack:
            c = stack.pop()
            if c in need:
                continue
            need.add(c)
            if self.kind[c] == "n":
                stack.extend(src for src, _, _ in self.spec[c][0])
        embs = [c for c in sorted(need) if self.kind[c] == "e"]
        nodes = sorted((c for c in need if self.kind[c] == "n"), key=lambda c: (self.depth[c], c))
        remap = {c: i for i, c in enumerate(embs + nodes)}
        emb = np.zeros((256, len(embs)), np.uint8)
        for j, c in enumerate(embs):
            emb[list(self.spec[c]), j] = 1
        layers, i = [], 0
        while i < len(nodes):
            d = self.depth[nodes[i]]
            j = i
            while j < len(nodes) and self.depth[nodes[j]] == d:
                j += 1
            out, src, off, w, bias, clip = [], [], [], [], [], []
            for local, c in enumerate(nodes[i:j]):
                conns, b, act, _ = self.spec[c]
                bias.append(b)
                clip.append(act == "clip")
                for s, o, ww in conns:
                    out.append(local), src.append(remap[s]), off.append(o), w.append(ww)
            layers.append(dict(
                out=np.array(out, np.int32), src=np.array(src, np.int32),
                off=np.array(off, np.int32), w=np.array(w, np.int8),
                bias=np.array(bias, np.int32), clip=np.array(clip, bool)))
            i = j
        return dict(emb=emb, layers=layers, labels={lab: remap[s.ch] for lab, s in finals.items()})


def stats(model: dict) -> dict:
    return dict(
        emb_channels=model["emb"].shape[1], layers=len(model["layers"]),
        neurons=sum(len(l["bias"]) for l in model["layers"]),
        connections=sum(len(l["w"]) for l in model["layers"]), labels=len(model["labels"]))
