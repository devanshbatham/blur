"""Reference inference engine. Event-driven: activations are kept sparse, so cost scales with
how much of the text actually excites a detector rather than with text length x network size.
All arithmetic is small-integer exact (carried in float32).

Per layer: gather the (source channel, offset) columns the layer reads, shift their row indices,
and do one sparse product with the layer's ternary weight matrix."""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

PAD = 64  # NUL bytes between documents in a batch; NUL excites no channel


class _Columns:
    """Append-only column store (CSC layout) with amortised growth."""

    def __init__(self, indptr, rows, vals):
        self.indptr = [np.asarray(indptr, np.int64)]
        self.n = len(rows)
        cap = max(1024, 2 * self.n)
        self.rows = np.empty(cap, np.int32)
        self.vals = np.empty(cap, np.float32)
        self.rows[:self.n], self.vals[:self.n] = rows, vals
        self._ptr = None

    def append(self, indptr, rows, vals):
        need = self.n + len(rows)
        if need > len(self.rows):
            cap = max(need, 2 * len(self.rows))
            self.rows = np.concatenate([self.rows[:self.n], np.empty(cap - self.n, np.int32)])
            self.vals = np.concatenate([self.vals[:self.n], np.empty(cap - self.n, np.float32)])
        self.rows[self.n:need], self.vals[self.n:need] = rows, vals
        self.indptr.append(np.asarray(indptr[1:], np.int64) + self.n)
        self.n = need
        self._ptr = None

    @property
    def ptr(self):
        if self._ptr is None:
            self._ptr = np.concatenate(self.indptr)
            self.indptr = [self._ptr]
        return self._ptr


class Engine:
    def __init__(self, model: dict):
        self.emb = sp.csr_matrix(model["emb"].astype(np.float32))
        self.labels = list(model["labels"])
        self.label_cols = np.array([model["labels"][k] for k in self.labels])
        self.layers = []
        for layer in model["layers"]:
            n_out = len(layer["bias"])
            pair = layer["src"].astype(np.int64) * 65536 + (layer["off"].astype(np.int64) + 32768)
            uniq, inv = np.unique(pair, return_inverse=True)
            A = sp.csr_matrix((layer["w"].astype(np.float32), (inv, layer["out"])), shape=(len(uniq), n_out))
            self.layers.append((uniq // 65536, (uniq % 65536 - 32768).astype(np.int32), A,
                                layer["bias"].astype(np.float32), layer["clip"]))

    def forward(self, data: bytes) -> np.ndarray:
        """Returns a (len(data), n_labels) boolean mask."""
        idx = np.frombuffer(data, np.uint8)
        N = len(idx)
        X0 = self.emb[idx].tocsc()
        X = _Columns(X0.indptr, X0.indices, X0.data)
        for src, off, A, bias, clip in self.layers:
            ptr = X.ptr
            starts = ptr[src]
            lens = ptr[src + 1] - starts
            total = int(lens.sum())
            n_out = A.shape[1]
            if total == 0:
                X.append(np.zeros(n_out + 1, np.int64), np.empty(0, np.int32), np.empty(0, np.float32))
                continue
            take = np.arange(total) + np.repeat(starts - (np.cumsum(lens) - lens), lens)
            r = X.rows[take] - np.repeat(off, lens)
            keep = (r >= 0) & (r < N)
            pcol = np.repeat(np.arange(len(src)), lens)[keep]
            Xe = sp.csr_matrix((X.vals[take][keep], (r[keep], pcol)), shape=(N, len(src)))
            pre = (Xe @ A).tocsc()
            col_of = np.repeat(np.arange(n_out), np.diff(pre.indptr))
            vals = np.maximum(pre.data + bias[col_of], 0)
            cm = clip[col_of]
            vals[cm] = np.minimum(vals[cm], 1)
            nz = vals > 0
            counts = np.bincount(col_of[nz], minlength=n_out)
            X.append(np.concatenate(([0], np.cumsum(counts))), pre.indices[nz], vals[nz])
        ptr = X.ptr
        mask = np.zeros((N, len(self.label_cols)), bool)
        for j, c in enumerate(self.label_cols):
            mask[X.rows[ptr[c]:ptr[c + 1]], j] = True
        return mask

    def spans(self, text: str | bytes) -> list[tuple[int, int, str]]:
        """Byte-offset spans (start, end, label)."""
        data = text.encode("utf-8") if isinstance(text, str) else text
        return self.batch_spans([data])[0]

    def batch_spans(self, docs: list[bytes]) -> list[list[tuple[int, int, str]]]:
        sep = b"\0" * PAD
        starts, pos = [], PAD
        for d in docs:
            starts.append(pos)
            pos += len(d) + PAD
        mask = self.forward(sep + sep.join(docs) + sep)
        return [decode(mask[s:s + len(d)], self.labels) for s, d in zip(starts, docs)]


def decode(mask: np.ndarray, labels: list[str]) -> list[tuple[int, int, str]]:
    out = []
    for j, lab in enumerate(labels):
        col = mask[:, j]
        if not col.any():
            continue
        edges = np.flatnonzero(np.diff(np.concatenate(([0], col.view(np.int8), [0]))))
        out.extend((int(a), int(b), lab) for a, b in zip(edges[::2], edges[1::2]))
    return sorted(out)
