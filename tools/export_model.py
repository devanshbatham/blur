"""Export the compiled network to the compact browser format (web/model.bin).

    python tools/export_model.py [--profile ai4p|general] [--out web/model.bin] [--all]

File layout (format version 1)
    bytes 0..3   "PW" 0x01 codec        codec 1 = the rest is one raw-deflate stream
    payload      nine sections, each prefixed by its byte length as a varint:

    head    varints: E, PAD, nLayers, layer sizes..., nLabels, label channel ids...
    emb     per embedding channel: number of 1-runs over byte values 0..255, then the run
            edges as deltas (start0, end0-start0, start1-end0, ...)
    shapes  dictionary of neuron "shapes". A shape is everything about a neuron except which
            channels it reads: fan-in, how many of the inputs are embedding channels, the
            offset and sign of every input, the bias and the activation.
            varints: nShapes, then per shape: fan, nEmb, zigzag(bias + nPositive - 1)*2 + clip,
            then per input zigzag(offset)*2 + negative
    sid     one varint per neuron: its shape id (shapes are numbered by falling frequency)
    esrc    one entry per embedding input. If E <= 256: the channel id as one byte. Otherwise a
            varint holding the rank of the channel when channels are sorted by falling use count,
            so that the common ones (letters) stay one byte long
    erank   empty if E <= 256, else E varints: the channel id for each rank
    nsrc    one varint per neuron that has neuron inputs: zigzag(first source - previous first
            source of a neuron with the same shape); the first neuron of a shape is relative
            to its own channel id
    nrest   the remaining neuron inputs of each neuron as deltas to the previous input
    names   label names joined by "\n" (UTF-8)

Inputs of a neuron are stored sorted by (source channel, offset); embedding channels have the
lowest ids so they come first. The order of inputs inside a neuron carries no meaning (the
pre-activation is an exact integer sum), everything else (channel numbering, layer order,
neuron order, biases, activations, labels) is reproduced exactly; `decode` + `canonical` below
check that on every export.
"""
from __future__ import annotations

import argparse
import os
import sys
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MAGIC = b"PW\x01\x01"
PAD = 64  # must equal blur.engine.PAD; stored in the file


def varint(vals) -> bytes:
    out = bytearray()
    for v in vals:
        v = int(v)
        assert v >= 0
        while v >= 0x80:
            out.append((v & 0x7F) | 0x80)
            v >>= 7
        out.append(v)
    return bytes(out)


def zz(v: int) -> int:
    return (v << 1) ^ (v >> 63)


def unzz(u: int) -> int:
    return (u >> 1) ^ -(u & 1)


def deflate_raw(b: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 9)
    return c.compress(b) + c.flush()


def neurons_of(model):
    """Yield (channel id, sorted [(src, off, w)], bias, clip) in network order."""
    base = model["emb"].shape[1]
    for l in model["layers"]:
        n = len(l["bias"])
        assert len(l["out"]) == 0 or (np.diff(l["out"]) >= 0).all()
        st = np.searchsorted(l["out"], np.arange(n + 1))
        src, off, w = l["src"].tolist(), l["off"].tolist(), l["w"].tolist()
        bias, clip = l["bias"].tolist(), l["clip"].tolist()
        for i in range(n):
            a, b = st[i], st[i + 1]
            yield base + i, sorted(zip(src[a:b], off[a:b], w[a:b])), bias[i], bool(clip[i])
        base += n


def canonical(model: dict) -> dict:
    """Same network with the inputs of every neuron sorted by (src, off)."""
    layers = []
    it = neurons_of(model)
    for l in model["layers"]:
        out, src, off, w = [], [], [], []
        for i in range(len(l["bias"])):
            _, conns, _, _ = next(it)
            for s, o, ww in conns:
                out.append(i), src.append(s), off.append(o), w.append(ww)
        layers.append(dict(out=np.array(out, np.int32), src=np.array(src, np.int32), off=np.array(off, np.int32),
                           w=np.array(w, np.int8), bias=np.asarray(l["bias"], np.int32), clip=np.asarray(l["clip"], bool)))
    return dict(emb=np.asarray(model["emb"], np.uint8), layers=layers, labels=dict(model["labels"]))


def same(a: dict, b: dict) -> bool:
    if not np.array_equal(a["emb"], b["emb"]) or list(a["labels"].items()) != list(b["labels"].items()):
        return False
    if len(a["layers"]) != len(b["layers"]):
        return False
    return all(np.array_equal(x[k], y[k]) for x, y in zip(a["layers"], b["layers"])
               for k in ("out", "src", "off", "w", "bias", "clip"))


def sections(model: dict) -> dict:
    emb = np.asarray(model["emb"])
    assert emb.shape[0] == 256 and set(np.unique(emb)) <= {0, 1}
    E = emb.shape[1]
    S = {}
    labels = model["labels"]
    assert all("\n" not in k for k in labels)
    S["head"] = varint([E, PAD, len(model["layers"])] + [len(l["bias"]) for l in model["layers"]]
                       + [len(labels)] + list(labels.values()))
    runs = []
    for c in range(E):
        edges = np.flatnonzero(np.diff(np.concatenate(([0], emb[:, c], [0])).astype(np.int16)))
        runs.append(len(edges) // 2)
        prev = 0
        for e in edges:
            runs.append(e - prev)
            prev = e
    S["emb"] = varint(runs)

    count, per = {}, []
    for nid, conns, bias, clip in neurons_of(model):
        assert bias <= 0 and all(w in (-1, 1) for _, _, w in conns) and all(s < nid for s, _, _ in conns)
        assert len(set(conns)) == len(conns)
        npos = sum(1 for c in conns if c[2] > 0)
        shape = (tuple((c[1], c[2]) for c in conns), sum(1 for c in conns if c[0] < E), bias + npos - 1, clip)
        count[shape] = count.get(shape, 0) + 1
        per.append((nid, conns, shape))
    order = sorted(count, key=lambda s: -count[s])  # stable: ties keep first-seen order
    sid = {s: i for i, s in enumerate(order)}
    tab = [len(order)]
    for conns, ne, bc, clip in order:
        tab += [len(conns), ne, zz(bc) * 2 + int(clip)]
        tab += [zz(o) * 2 + int(w < 0) for o, w in conns]
    S["shapes"] = varint(tab)
    sids, esrc, nsrc, nrest, prev = [], [], [], [], {}
    for nid, conns, shape in per:
        k = sid[shape]
        sids.append(k)
        ne = shape[1]
        esrc += [c[0] for c in conns[:ne]]
        ns = [c[0] for c in conns[ne:]]
        if ns:
            nsrc.append(zz(ns[0] - prev.get(k, nid)))
            prev[k] = ns[0]
            nrest += [b - a for a, b in zip(ns, ns[1:])]
    S["sid"] = varint(sids)
    if E <= 256:
        S["esrc"], S["erank"] = bytes(esrc), b""
    else:
        use = np.bincount(esrc, minlength=E)
        by_rank = sorted(range(E), key=lambda c: (-use[c], c))
        rank = {c: r for r, c in enumerate(by_rank)}
        S["esrc"], S["erank"] = varint([rank[c] for c in esrc]), varint(by_rank)
    S["nsrc"] = varint(nsrc)
    S["nrest"] = varint(nrest)
    S["names"] = "\n".join(labels).encode()
    return S


def encode(model: dict, check: bool = True) -> bytes:
    S = sections(model)
    payload = b"".join(varint([len(v)]) + v for v in S.values())
    blob = MAGIC + deflate_raw(payload)
    if check:
        assert same(decode(blob), canonical(model)), "round-trip mismatch"
    return blob


class _Reader:
    def __init__(self, b: bytes):
        self.b, self.i = b, 0

    def v(self) -> int:
        r = s = 0
        while True:
            x = self.b[self.i]
            self.i += 1
            r |= (x & 0x7F) << s
            if x < 0x80:
                return r
            s += 7

    def take(self, n: int) -> bytes:
        self.i += n
        return self.b[self.i - n:self.i]


def decode(blob: bytes) -> dict:
    """Reference decoder (mirrors web/engine.js). Returns the model in canonical input order."""
    assert blob[:4] == MAGIC
    top = _Reader(zlib.decompress(blob[4:], -15))
    head, emb_s, shapes_s, sid_s, esrc_s, erank_s, nsrc_s, nrest_s, names = (_Reader(top.take(top.v())) for _ in range(9))
    E, pad, n_layers = head.v(), head.v(), head.v()
    assert pad == PAD
    sizes = [head.v() for _ in range(n_layers)]
    chans = [head.v() for _ in range(head.v())]
    labels = dict(zip(names.b.decode().split("\n") if chans else [], chans))
    by_rank = [erank_s.v() for _ in range(E)] if E > 256 else None
    emb = np.zeros((256, E), np.uint8)
    for c in range(E):
        pos = 0
        for _ in range(emb_s.v()):
            a = pos + emb_s.v()
            pos = a + emb_s.v()
            emb[a:pos, c] = 1
    shapes = []
    for _ in range(shapes_s.v()):
        fan, ne, x = shapes_s.v(), shapes_s.v(), shapes_s.v()
        conns = []
        for _ in range(fan):
            y = shapes_s.v()
            conns.append((unzz(y >> 1), -1 if y & 1 else 1))
        shapes.append((conns, ne, unzz(x >> 1), bool(x & 1)))
    layers, nid, prev = [], E, {}
    for n in sizes:
        out, src, off, w, bias, clip = [], [], [], [], [], []
        for i in range(n):
            k = sid_s.v()
            conns, ne, bc, cl = shapes[k]
            s = [esrc_s.take(1)[0] if E <= 256 else by_rank[esrc_s.v()] for _ in range(ne)]
            if len(conns) > ne:
                s.append(prev.get(k, nid) + unzz(nsrc_s.v()))
                prev[k] = s[-1]
                for _ in range(len(conns) - ne - 1):
                    s.append(s[-1] + nrest_s.v())
            for ss, (o, ww) in zip(s, conns):
                out.append(i), src.append(ss), off.append(o), w.append(ww)
            bias.append(bc - sum(1 for _, ww in conns if ww > 0) + 1)
            clip.append(cl)
            nid += 1
        layers.append(dict(out=np.array(out, np.int32), src=np.array(src, np.int32), off=np.array(off, np.int32),
                           w=np.array(w, np.int8), bias=np.array(bias, np.int32), clip=np.array(clip, bool)))
    return dict(emb=emb, layers=layers, labels=labels)


def build(profile: str) -> dict:
    os.environ["PROFILE"] = profile
    from blur import general
    return general.build()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", choices=["ai4p", "general"], default=os.environ.get("PROFILE", "ai4p"))
    ap.add_argument("--out", default=None, help="default web/model.bin")
    ap.add_argument("--all", action="store_true", help="write web/model-ai4p.bin and web/model-general.bin")
    ap.add_argument("--pkl", help="export a pickled compiled model instead of building one")
    a = ap.parse_args()
    from blur.dsl import stats
    jobs = [(p, os.path.join(ROOT, "web", f"model-{p}.bin")) for p in ("ai4p", "general")] if a.all \
        else [(a.profile, a.out or os.path.join(ROOT, "web", "model.bin"))]
    for profile, out in jobs:
        if a.pkl:
            import pickle
            model = pickle.load(open(a.pkl, "rb"))
        else:
            model = build(profile)
        blob = encode(model)
        with open(out, "wb") as f:
            f.write(blob)
        S = sections(model)
        print(f"{profile}: {stats(model)}")
        print(f"  {out}: {len(blob)} bytes (payload {sum(map(len, S.values()))} before deflate; round-trip verified)")
        print("  per-section deflate sizes:", " ".join(f"{k}={len(deflate_raw(v))}" for k, v in S.items()))


if __name__ == "__main__":
    main()
