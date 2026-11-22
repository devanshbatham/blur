// blur inference engine. Plain ES module, no dependencies; runs in browsers and in Node.
//
//   import { loadModel } from "./engine.js";
//   const model = await loadModel("model.bin");        // URL, ArrayBuffer or Uint8Array
//   model.detect("mail bob@example.com")               // [{start, end, label, text}]
//
// The network is a stack of sparse ternary 1D convolutions over the UTF-8 bytes of the text:
//
//   out[i] = act(bias + sum_j w_j * x[src_j][i + off_j]),  w_j in {-1,+1}, bias <= 0
//
// Evaluation is event driven. A channel is held as the sorted list of positions where it is
// non-zero (plus the values, for the few channels that are not 0/1), or as a bitmap over the
// positions when it is dense. A neuron is visited only if an input it cannot fire without is
// non-empty; sparse inputs are then combined by walking the shortest list and probing the
// others, dense ones 32 positions at a time. Nothing is proportional to text length times
// network size.
//
//   model.detect(text, { includeAux })   spans with UTF-16 offsets; "kind:*" / "_*" labels hidden by default
//   model.detectBytes(uint8array, opts)  spans with byte offsets
//   model.info                           sizes, receptive field, model file size
//   model.labels                         label names in model order

const MAGIC0 = 0x50, MAGIC1 = 0x57, VERSION = 1, CODEC_DEFLATE_RAW = 1;
const MIN_CHUNK = 16384;
const BIG_FAN = 8; // OR/general neurons with at least this many positive inputs track which are active

const K_DEAD = 0;   // can never fire
const K_AND = 1;    // needs every positive input (all of them 0/1): shortest list drives, the rest are probed
const K_TRIE = 2;   // K_AND with exactly [embedding input, neuron input] and no negatives
const K_OR = 3;     // fires where any input fires (all inputs 0/1, no negatives)
const K_GEN = 4;    // anything else: accumulate, then threshold

class Reader {
  constructor(bytes) { this.b = bytes; this.i = 0; }
  v() { // unsigned LEB128, values below 2^31
    const b = this.b;
    let x = b[this.i++], r = x & 0x7f;
    for (let s = 7; x >= 0x80; s += 7) { x = b[this.i++]; r |= (x & 0x7f) << s; }
    return r;
  }
  sub() { const n = this.v(); const r = new Reader(this.b.subarray(this.i, this.i + n)); this.i += n; return r; }
}

const unzz = (u) => (u >>> 1) ^ -(u & 1);

// Node: zlib (synchronous, a little faster). Browsers: DecompressionStream. `how` forces one of them.
async function inflateRaw(bytes, how) {
  if (how !== "stream" && typeof process !== "undefined" && process.versions && process.versions.node) {
    const zlib = await import("node:zlib");
    const out = zlib.inflateRawSync(bytes);
    return new Uint8Array(out.buffer, out.byteOffset, out.byteLength);
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

// First index in P[lo, hi) whose value is >= x (hi if none). Gallops from lo, so a sequence of
// calls with rising x over the same list costs O(log gap) each.
function seek(P, lo, hi, x) {
  if (lo >= hi || P[lo] >= x) return lo;
  let step = 1, i = lo + 1;
  while (i < hi && P[i] < x) { lo = i; step <<= 1; i = lo + step; }
  if (i > hi) i = hi;
  lo++;
  while (lo < i) {
    const m = (lo + i) >>> 1;
    if (P[m] < x) lo = m + 1; else i = m;
  }
  return lo;
}

// dst[i] (op)= word i of the source bitmap shifted so that output bit q is source bit q + off.
// mode 0: set, 1: and, 2: or, 3: and-not. Bits outside the nw-word bitmap read as 0.
function combine(B, dst, src, off, nw, mode) {
  const wo = off >> 5, sh = off & 31;
  for (let i = 0; i < nw; i++) {
    const j = i + wo;
    let v = j >= 0 && j < nw ? B[src + j] : 0;
    if (sh) v = (v >>> sh) | ((j + 1 >= 0 && j + 1 < nw ? B[src + j + 1] : 0) << (32 - sh));
    if (mode === 0) B[dst + i] = v;
    else if (mode === 1) B[dst + i] &= v;
    else if (mode === 2) B[dst + i] |= v;
    else B[dst + i] &= ~v;
  }
}

// Word i of a bitmap at `src` shifted so that bit q of the result is source bit q + off
// (wo = off >> 5, sh = off & 31); bits outside the nw words read as 0.
function sword(B, src, i, wo, sh, nw) {
  const j = i + wo;
  const lo = j >= 0 && j < nw ? B[src + j] : 0;
  if (sh === 0) return lo;
  return (lo >>> sh) | ((j + 1 >= 0 && j + 1 < nw ? B[src + j + 1] : 0) << (32 - sh));
}

function pop32(v) {
  v -= (v >>> 1) & 0x55555555;
  v = (v & 0x33333333) + ((v >>> 2) & 0x33333333);
  return Math.imul((v + (v >>> 4)) & 0x0f0f0f0f, 0x01010101) >>> 24;
}

// The common dense neurons in one pass: dst = a(oa) AND b(ob), a(oa) AND NOT b(ob) (andNot),
// or a(oa) OR b(ob) (or). Returns the number of bits set. tail masks the last word.
function bin2(B, dst, a, oa, b, ob, nw, op, tail) {
  const wa = oa >> 5, sa = oa & 31, wb = ob >> 5, sb = ob & 31;
  let c = 0;
  for (let i = 0; i < nw; i++) {
    const x = sword(B, a, i, wa, sa, nw), y = sword(B, b, i, wb, sb, nw);
    let v = op === 0 ? x & y : op === 1 ? x & ~y : x | y;
    if (i === nw - 1) v &= tail;
    B[dst + i] = v;
    if (v) c += pop32(v);
  }
  return c;
}

function popcount(B, at, nw) {
  let c = 0;
  for (let i = 0; i < nw; i++) {
    let v = B[at + i];
    if (v) {
      v -= (v >>> 1) & 0x55555555;
      v = (v & 0x33333333) + ((v >>> 2) & 0x33333333);
      c += Math.imul((v + (v >>> 4)) & 0x0f0f0f0f, 0x01010101) >>> 24;
    }
  }
  return c;
}

export class Model {
  // `payload` is the inflated model file body. opts.ablate switches optimisations off (benchmarks only).
  constructor(payload, opts = {}) {
    const ablate = opts.ablate || {};
    const top = new Reader(payload);
    const head = top.sub(), embS = top.sub(), shapeS = top.sub(), sidS = top.sub();
    const esrcS = top.sub(), erankS = top.sub(), nsrcS = top.sub(), nrestS = top.sub(), namesS = top.sub();

    const E = (this.E = head.v());
    const PAD = (this.PAD = head.v());
    const nLayers = (this.nLayers = head.v());
    const layerSize = new Int32Array(nLayers);
    let nNeu = 0;
    for (let l = 0; l < nLayers; l++) nNeu += layerSize[l] = head.v();
    this.nNeu = nNeu;
    const nCh = (this.nCh = E + nNeu);
    const nLabels = head.v();
    const labelCh = (this.labelCh = new Int32Array(nLabels));
    for (let i = 0; i < nLabels; i++) labelCh[i] = head.v();
    this.labels = nLabels ? new TextDecoder().decode(namesS.b).split("\n") : [];
    this.labelAux = this.labels.map((s) => s.startsWith("kind:") || s.startsWith("_"));

    // ---- embedding: emb[byte * E + channel], and per byte the list of channels it excites
    const emb = (this.emb = new Uint8Array(256 * E));
    const clsSize = new Int32Array(E);
    for (let c = 0; c < E; c++) {
      let pos = 0;
      for (let r = embS.v(); r > 0; r--) {
        const a = pos + embS.v();
        pos = a + embS.v();
        for (let b = a; b < pos; b++) emb[b * E + c] = 1;
        clsSize[c] += pos - a;
      }
    }
    const byteStart = (this.byteStart = new Int32Array(257));
    for (let b = 0; b < 256; b++) {
      let k = 0;
      for (let c = 0; c < E; c++) k += emb[b * E + c];
      byteStart[b + 1] = byteStart[b] + k;
    }
    const byteCls = (this.byteCls = new Int32Array(byteStart[256]));
    for (let b = 0, k = 0; b < 256; b++) for (let c = 0; c < E; c++) if (emb[b * E + c]) byteCls[k++] = c;
    // and per class the byte values in it
    const clsStart = (this.clsStart = new Int32Array(E + 1)), clsBytes = (this.clsBytes = new Uint8Array(byteStart[256]));
    for (let c = 0; c < E; c++) clsStart[c + 1] = clsStart[c] + clsSize[c];
    { const f = clsStart.slice(0, E); for (let b = 0; b < 256; b++) for (let k = byteStart[b]; k < byteStart[b + 1]; k++) clsBytes[f[byteCls[k]]++] = b; }

    // ---- shape dictionary. Besides the stored fields, work out per shape everything that
    // does not depend on which channels a neuron reads, assuming all its inputs are 0/1 valued
    // (true for all but a handful of neurons, which take the slow path below).
    const nShapes = shapeS.v();
    const shFan = new Int32Array(nShapes), shEmb = new Int32Array(nShapes), shBias = new Int32Array(nShapes);
    const shNP = new Int32Array(nShapes), shClip = new Uint8Array(nShapes), shStart = new Int32Array(nShapes + 1);
    const shKind = new Uint8Array(nShapes), shMax = new Int32Array(nShapes), shWatch = new Int32Array(nShapes);
    const shPrev = new Int32Array(nShapes).fill(-1);
    let shConn = 0;
    { const save = shapeS.i; for (let s = 0; s < nShapes; s++) { const fan = shapeS.v(); shapeS.v(); shapeS.v(); for (let j = 0; j < fan; j++) shapeS.v(); shConn += fan; } shapeS.i = save; }
    const shOff = new Int32Array(shConn), shDst = new Int32Array(shConn), shNeg = new Uint8Array(shConn);
    const classify = (np, fan, nEmbPos, b, posMax, allBool, outBool) => {
      if (posMax < 1 - b) return K_DEAD;
      if (allBool && 1 - b === np && !ablate.and) return np === 2 && fan === 2 && nEmbPos === 1 && !ablate.trie ? K_TRIE : K_AND;
      return allBool && np === fan && b === 0 && outBool ? K_OR : K_GEN;
    };
    let maxFan = 1;
    for (let s = 0, so = 0; s < nShapes; s++) {
      const fan = (shFan[s] = shapeS.v()), ne = (shEmb[s] = shapeS.v()), x = shapeS.v();
      shClip[s] = x & 1;
      let np = 0, nEmbPos = 0, lastPos = -1;
      for (let j = 0; j < fan; j++) {
        const y = shapeS.v();
        shOff[so + j] = unzz(y >>> 1);
        if (!(shNeg[so + j] = y & 1)) { np++; lastPos = j; if (j < ne) nEmbPos++; }
      }
      for (let j = 0, p = 0, q = np; j < fan; j++) shDst[so + j] = shNeg[so + j] ? q++ : p++; // positives first
      const b = (shBias[s] = unzz(x >>> 1) - np + 1);
      if (b > 0) throw new Error("blur: bad model (positive bias)");
      shNP[s] = np;
      shMax[s] = shClip[s] ? Math.min(1, Math.max(0, np + b)) : Math.max(0, np + b);
      shKind[s] = classify(np, fan, nEmbPos, b, np, 1, shMax[s] <= 1);
      shWatch[s] = lastPos >= ne ? shDst[so + lastPos] : -1; // the deepest neuron input, if there is one
      if (fan > maxFan) maxFan = fan;
      shStart[s + 1] = so += fan;
    }

    // ---- neurons. Inputs are stored positives first, then negatives.
    const cStart = (this.cStart = new Int32Array(nNeu + 1));
    const nPos = (this.nPos = new Int32Array(nNeu));
    const bias = (this.bias = new Int32Array(nNeu));
    const kind = (this.kind = new Uint8Array(nNeu));
    const layerOf = (this.layerOf = new Int32Array(nNeu));
    const negBool = (this.negBool = new Uint8Array(nNeu).fill(1)); // 1 if every negative input is 0/1
    const posBool = (this.posBool = new Uint8Array(nNeu).fill(1)); // same for the positive inputs
    const watch = new Int32Array(nNeu); // K_AND / K_TRIE: the one input channel that schedules the neuron
    const sidB = sidS.b, nsrcB = nsrcS.b, nrestB = nrestS.b, esrcB = esrcS.b, esrcByte = E <= 256;
    const byRank = new Int32Array(esrcByte ? 0 : E); // esrc holds use-count ranks when E > 256
    for (let r = 0; r < byRank.length; r++) byRank[r] = erankS.v();
    let nConn = 0;
    for (let n = 0, i = 0; n < nNeu; n++) {
      let s = sidB[i++];
      if (s >= 0x80) { s &= 0x7f; for (let sh = 7, x = 0x80; x >= 0x80; sh += 7) { x = sidB[i++]; s |= (x & 0x7f) << sh; } }
      watch[n] = s; // shape id for now
      cStart[n + 1] = nConn += shFan[s];
    }
    this.nConn = nConn;
    const cSrc = (this.cSrc = new Int32Array(nConn));
    const cOff = (this.cOff = new Int32Array(nConn));
    const maxVal = new Int32Array(nCh).fill(1, 0, E); // upper bound of the channel's value
    const isBool = (this.isBool = new Uint8Array(nCh).fill(1));
    // wStart/wList: channel -> neurons to wake when the channel is non-empty.
    const wStart = (this.wStart = new Int32Array(nCh + 1));
    let anyValues = false, bad = 0, ie = 0, ins = 0, inr = 0;
    for (let l = 0, n = 0; l < nLayers; l++) {
      for (let end = n + layerSize[l]; n < end; n++) {
        const s = watch[n], fan = shFan[s], ne = shEmb[s], ch = E + n, so = shStart[s], base = cStart[n];
        layerOf[n] = l;
        let j = 0, nb = 0;
        for (; j < ne; j++) {
          let src;
          if (esrcByte) src = esrcB[ie++];
          else {
            src = esrcB[ie++];
            if (src >= 0x80) { src &= 0x7f; for (let sh = 7, x = 0x80; x >= 0x80; sh += 7) { x = esrcB[ie++]; src |= (x & 0x7f) << sh; } }
            src = src < E ? byRank[src] : E;
          }
          if (src >= E) bad = 1;
          const d = base + shDst[so + j];
          cSrc[d] = src; cOff[d] = shOff[so + j];
        }
        if (j < fan) {
          let u = nsrcB[ins++];
          if (u >= 0x80) { u &= 0x7f; for (let sh = 7, x = 0x80; x >= 0x80; sh += 7) { x = nsrcB[ins++]; u |= (x & 0x7f) << sh; } }
          let src = (shPrev[s] < 0 ? ch : shPrev[s]) + ((u >>> 1) ^ -(u & 1));
          shPrev[s] = src;
          for (;;) {
            if (src >= ch || src < E) bad = 1;
            else nb |= 1 - isBool[src];
            const d = base + shDst[so + j];
            cSrc[d] = src; cOff[d] = shOff[so + j];
            if (++j >= fan) break;
            u = nrestB[inr++];
            if (u >= 0x80) { u &= 0x7f; for (let sh = 7, x = 0x80; x >= 0x80; sh += 7) { x = nrestB[inr++]; u |= (x & 0x7f) << sh; } }
            src += u;
          }
        }
        if (bad) throw new Error("blur: bad model (source channel out of range)");
        const np = (nPos[n] = shNP[s]), b = (bias[n] = shBias[s]);
        let k = shKind[s], w = shWatch[s];
        if (nb) {
          // some input carries values above 1: redo the analysis with the real bounds
          let allBool = 1, posMax = 0, nEmbPos = 0, negAll = 1;
          for (let c = base; c < base + fan; c++) {
            const src = cSrc[c];
            if (c < base + np) { allBool &= isBool[src]; posMax += maxVal[src]; if (src < E) nEmbPos++; }
            else negAll &= isBool[src];
          }
          negBool[n] = negAll;
          posBool[n] = allBool;
          const m = Math.min(2 ** 30, Math.max(0, posMax + b));
          maxVal[ch] = shClip[s] ? Math.min(1, m) : m;
          k = classify(np, fan, nEmbPos, b, posMax, allBool, maxVal[ch] <= 1);
        } else maxVal[ch] = shMax[s];
        if (maxVal[ch] > 1) { isBool[ch] = 0; anyValues = true; }
        kind[n] = k;
        if (k === K_AND || k === K_TRIE) {
          let c;
          if (w >= 0) c = cSrc[base + w];
          else { // only embedding inputs: wake on the class with the fewest byte values
            c = cSrc[base];
            for (let t = base + 1; t < base + np; t++) if (clsSize[cSrc[t]] < clsSize[c]) c = cSrc[t];
          }
          watch[n] = c;
          wStart[c]++;
        } else if (k !== K_DEAD) for (let t = base; t < base + np; t++) wStart[cSrc[t]]++;
      }
    }
    this.anyValues = anyValues;
    // Letter-tree children: AND(embedding class at 0, parent at -1). They are not scheduled one
    // by one; when a parent fires, its position list is walked once and the byte after each
    // position picks the children that fire (tStart/tByte/tKid: per parent, (byte, child)
    // pairs sorted by byte).
    const tStart = (this.tStart = new Int32Array(nCh + 1)), tKidOf = new Uint8Array(nNeu);
    this.minKids = opts.minKids ?? 3;
    if (!ablate.dispatch) {
      // only parents with several such children, all of them small classes (letters)
      const nKids = new Int32Array(nCh), bad = new Uint8Array(nCh);
      for (let n = 0; n < nNeu; n++) {
        if (kind[n] !== K_TRIE) continue;
        const base = cStart[n];
        if (cOff[base] !== 0 || cOff[base + 1] !== -1) continue;
        nKids[cSrc[base + 1]]++;
        if (clsSize[cSrc[base]] > 4) bad[cSrc[base + 1]] = 1;
      }
      for (let n = 0; n < nNeu; n++) {
        if (kind[n] !== K_TRIE) continue;
        const base = cStart[n], p = cSrc[base + 1];
        if (cOff[base] !== 0 || cOff[base + 1] !== -1 || nKids[p] < this.minKids || bad[p]) continue;
        tKidOf[n] = 1;
        tStart[cSrc[base + 1]] += clsSize[cSrc[base]];
        const c = watch[n]; // undo the wake-up count made above
        wStart[c]--;
      }
    }
    for (let c = 1; c <= nCh; c++) tStart[c] += tStart[c - 1];
    const tByte = (this.tByte = new Uint8Array(tStart[nCh])), tKid = (this.tKid = new Int32Array(tStart[nCh]));
    for (let n = nNeu - 1; n >= 0; n--) {
      if (!tKidOf[n]) continue;
      const base = cStart[n], ec = cSrc[base], p = cSrc[base + 1];
      for (let k = clsStart[ec + 1] - 1; k >= clsStart[ec]; k--) { const t = --tStart[p]; tByte[t] = clsBytes[k]; tKid[t] = n; }
    }
    for (let p = 0; p < nCh; p++) { // sort each parent's pairs by byte (insertion sort; segments are short)
      for (let i = tStart[p] + 1, e = tStart[p + 1]; i < e; i++) {
        const b = tByte[i], m = tKid[i];
        let j = i - 1;
        while (j >= tStart[p] && tByte[j] > b) { tByte[j + 1] = tByte[j]; tKid[j + 1] = tKid[j]; j--; }
        tByte[j + 1] = b; tKid[j + 1] = m;
      }
    }
    this.tCnt = new Int32Array(nNeu);
    this.tTouched = new Int32Array(nNeu);
    this.tStack = new Int32Array(nNeu + 1);
    // counts -> end offsets; filling backwards then leaves the start offsets in place
    for (let c = 1; c <= nCh; c++) wStart[c] += wStart[c - 1];
    // wConn: for OR/general neurons with many inputs, which input a wake-up entry stands for
    const wList = (this.wList = new Int32Array(wStart[nCh])), wConn = (this.wConn = new Int32Array(wStart[nCh]).fill(-1));
    for (let n = nNeu - 1; n >= 0; n--) {
      const k = kind[n], base = cStart[n];
      if (tKidOf[n]) continue;
      if (k === K_AND || k === K_TRIE) wList[--wStart[watch[n]]] = n;
      else if (k !== K_DEAD) {
        const big = nPos[n] >= BIG_FAN;
        for (let t = base + nPos[n] - 1; t >= base; t--) { const w = --wStart[cSrc[t]]; wList[w] = n; if (big) wConn[w] = t; }
      }
    }
    this.actHead = new Int32Array(nNeu).fill(-1); // per neuron: chain of wake-up entries whose input fired
    this.actNext = new Int32Array(wList.length);
    this.aj = new Int32Array(maxFan);
    this.scheduleAll = !!ablate.schedule;
    this.noMerge = !!ablate.merge;
    this.noBits = !!ablate.bits;
    this.noSkip = !!ablate.skip;
    this.denseShift = opts.denseShift || 4;

    // ---- run-time state
    this.cap = 1 << 16;
    this.P = new Int32Array(this.cap);             // positions of all channel lists, back to back
    this.V = anyValues ? new Int32Array(this.cap) : null; // values, only read for non-0/1 channels
    this.top = 0;
    this.chStart = new Int32Array(nCh);
    this.chLen = new Int32Array(nCh);
    this.chBits = new Int32Array(nCh).fill(-1);   // word offset of the channel's bitmap in B, or -1
    this.B = new Uint32Array(1 << 12);            // bitmaps of dense channels, back to back
    this.btop = 0;
    this.nw = 0;
    this.flag = new Uint8Array(nNeu);
    this.next = new Int32Array(nNeu);
    this.head = new Int32Array(nLayers).fill(-1);
    this.fired = new Int32Array(nNeu);
    this.nFired = 0;
    this.cur = new Int32Array(maxFan);
    this.skipMark = new Uint8Array(maxFan); // inputs of the current neuron that are probed, not walked
    this.skip = new Int32Array(4);
    this.acc = new Int32Array(1024);
    this.touched = new Int32Array(1024);
    this.hist = new Int32Array(256);
    this.bStart = new Int32Array(257); // per byte value: its positions are P[bStart[b] .. bStart[b+1])
    this.bFill = new Int32Array(256);
    this.present = new Uint8Array(256); // byte values that occur in the window
    this.nPresent = 0;
    this.byteBits = new Int32Array(256);
    this.byteBitsReady = false;
    this.tailMask = -1;
    this.wordCost = opts.wordCost ?? 0.5; // cost of one bitmap word operation relative to setting one bit
    this.dense = 0;
    this.scratch = new Uint8Array(4096);
    this.encoder = new TextEncoder();
    this.stats = { windows: 0, evaluated: 0, events: 0 };

    this._chunk = opts.chunk || 0;
    this._reachL = -1;
    this._reachR = -1;
    this.bytes = opts.bytes || 0;
    this.nShapes = nShapes;
  }

  // Receptive field: an output at byte i depends only on bytes i-reachLeft .. i+reachRight, and
  // on no intermediate value outside that range (every prefix of every path through the
  // network is counted, not just whole paths). Computed on first use.
  _reach() {
    const E = this.E, cStart = this.cStart, cSrc = this.cSrc, cOff = this.cOff;
    const L = new Int32Array(this.nCh), R = new Int32Array(this.nCh);
    let minL = 0, maxR = 0;
    for (let n = 0; n < this.nNeu; n++) {
      let lo = 0, hi = 0;
      for (let j = cStart[n], e = cStart[n + 1]; j < e; j++) {
        const src = cSrc[j], off = cOff[j], a = off + L[src], b = off + R[src];
        if (a < lo) lo = a;
        if (b > hi) hi = b;
      }
      L[E + n] = lo; R[E + n] = hi;
      if (lo < minL) minL = lo;
      if (hi > maxR) maxR = hi;
    }
    this._reachL = -minL;
    this._reachR = maxR;
  }
  get reachLeft() { if (this._reachL < 0) this._reach(); return this._reachL; }
  get reachRight() { if (this._reachR < 0) this._reach(); return this._reachR; }

  // Inputs longer than this many bytes (plus the receptive field) are processed in chunks.
  get chunk() { return this._chunk || Math.max(MIN_CHUNK, 4 * (this.reachLeft + this.reachRight)); }
  set chunk(v) { this._chunk = v; }

  get info() {
    return {
      embChannels: this.E, layers: this.nLayers, neurons: this.nNeu, connections: this.nConn, labels: this.labels.length,
      shapes: this.nShapes, reachLeft: this.reachLeft, reachRight: this.reachRight, pad: this.PAD, bytes: this.bytes,
    };
  }

  _grow(need) {
    let cap = this.cap;
    while (cap < need) cap *= 2;
    const P = new Int32Array(cap);
    P.set(this.P.subarray(0, this.top));
    this.P = P;
    if (this.V) { const V = new Int32Array(cap); V.set(this.V.subarray(0, this.top)); this.V = V; }
    this.cap = cap;
  }

  // Reserve one zeroed bitmap (this.nw words) in the bit pool; returns its word offset.
  _allocBits() {
    const at = this.btop, nw = this.nw;
    if (at + nw > this.B.length) {
      const B = new Uint32Array(Math.max(this.B.length * 2, at + nw));
      B.set(this.B.subarray(0, at));
      this.B = B;
    } else this.B.fill(0, at, at + nw);
    this.btop = at + nw;
    return at;
  }

  // Make sure channel c (non-empty, 0/1 valued) has a bitmap. May reallocate this.B.
  _toBits(c) {
    let at = this.chBits[c];
    if (at >= 0) return at;
    if (this.chStart[c] < 0) { this._emb(c, true); if ((at = this.chBits[c]) >= 0) return at; }
    at = this.chBits[c] = this._allocBits();
    const B = this.B, P = this.P;
    for (let i = this.chStart[c], e = i + this.chLen[c]; i < e; i++) { const p = P[i]; B[at + (p >>> 5)] |= 1 << (p & 31); }
    return at;
  }

  // Make sure channel c (non-empty) has a position list. May reallocate this.P.
  _toList(c) {
    let at = this.chStart[c];
    if (at >= 0) return at;
    if (this.chBits[c] < 0) { this._emb(c, false); if ((at = this.chStart[c]) >= 0) return at; }
    const len = this.chLen[c];
    if (this.top + len > this.cap) this._grow(this.top + len);
    at = this.chStart[c] = this.top;
    const B = this.B, P = this.P, bits = this.chBits[c];
    let top = at;
    for (let i = 0, nw = this.nw; i < nw; i++) {
      let v = B[bits + i];
      while (v) { const t = v & -v; P[top++] = (i << 5) + 31 - Math.clz32(t); v ^= t; }
    }
    this.top = top;
    return at;
  }

  // Embedding channels are not written out when the text is read: only their counts are known
  // (from the byte histogram). The first consumer that needs the positions of class c calls
  // this, which gathers them from the per-byte position lists, as a bitmap if c is dense (or
  // `bits` asks for one) and as a list otherwise. A byte belongs to about a hundred classes in
  // the larger models, most of which are only ever probed through the embedding table.
  _emb(c, bits) {
    const len = this.chLen[c], cs = this.clsStart, cb = this.clsBytes, bStart = this.bStart, hist = this.hist;
    if (bits || len >= this.dense) {
      // Either set the bits one position at a time, or OR together the bitmaps of the byte
      // values in the class (or of those not in it, then invert), whichever is less work.
      const nw = this.nw, present = this.present, np = this.nPresent, emb = this.emb, E = this.E;
      let kin = 0;
      for (let t = 0; t < np; t++) kin += emb[present[t] * E + c];
      const inv = np - kin + 1 < kin, words = (inv ? np - kin + 1 : kin) * nw;
      const at = (this.chBits[c] = this._allocBits());
      if (words * this.wordCost >= len) {
        const B = this.B, P = this.P;
        for (let k = cs[c]; k < cs[c + 1]; k++) {
          const b = cb[k];
          if (hist[b]) for (let i = bStart[b], e = bStart[b + 1]; i < e; i++) { const p = P[i]; B[at + (p >>> 5)] |= 1 << (p & 31); }
        }
        return;
      }
      if (!this.byteBitsReady) this._byteBits();
      const B = this.B, bb = this.byteBits;
      for (let t = 0; t < np; t++) {
        const b = present[t];
        if (emb[b * E + c] === (inv ? 0 : 1)) { const src = bb[b]; for (let i = 0; i < nw; i++) B[at + i] |= B[src + i]; }
      }
      if (inv) { for (let i = 0; i < nw; i++) B[at + i] = ~B[at + i]; B[at + nw - 1] &= this.tailMask; }
      return;
    }
    if (this.top + len > this.cap) this._grow(this.top + len);
    const P = this.P, at = (this.chStart[c] = this.top);
    let top = at, parts = 0;
    for (let k = cs[c]; k < cs[c + 1]; k++) {
      const b = cb[k];
      if (hist[b]) { parts++; for (let i = bStart[b], e = bStart[b + 1]; i < e; i++) P[top++] = P[i]; }
    }
    if (parts > 1) P.subarray(at, top).sort();
    this.top = top;
  }

  // Evaluate the letter-tree children of channel `root` (which has just fired), and theirs, and
  // so on. Called with this.top / this.nFired current; updates them.
  _trie(root, buf, W) {
    const E = this.E, chStart = this.chStart, chLen = this.chLen, chBits = this.chBits, fired = this.fired;
    const tStart = this.tStart, tByte = this.tByte, tKid = this.tKid, cnt = this.tCnt, touched = this.tTouched, stack = this.tStack;
    const wStart = this.wStart, wList = this.wList, wConn = this.wConn, actHead = this.actHead, actNext = this.actNext;
    const flag = this.flag, next = this.next, head = this.head, layerOf = this.layerOf;
    let depth = 0, evaluated = 0;
    stack[depth++] = root;
    while (depth) {
      const x = stack[--depth], s = tStart[x], e = tStart[x + 1];
      if (chStart[x] < 0) this._toList(x);
      let P = this.P, nk = 0, total = 0;
      const i0 = chStart[x], i1 = i0 + chLen[x];
      for (let pass = 0; pass < 2; pass++) {
        for (let i = i0; i < i1; i++) {
          const q = P[i] + 1;
          if (q >= W) break;
          const b = buf[q];
          let t = s;
          if (e - s > 12) { let hi = e; while (t < hi) { const mid = (t + hi) >>> 1; if (tByte[mid] < b) t = mid + 1; else hi = mid; } }
          for (; t < e; t++) {
            const tb = tByte[t];
            if (tb < b) continue;
            if (tb > b) break;
            const m = tKid[t];
            if (pass) P[cnt[m]++] = q;
            else { if (cnt[m] === 0) touched[nk++] = m; cnt[m]++; total++; }
          }
        }
        if (pass || nk === 0) break;
        // give each child its slice of P; cnt becomes the fill pointer
        if (this.top + total > this.cap) { this._grow(this.top + total); P = this.P; }
        let top = this.top;
        for (let u = 0; u < nk; u++) { const m = touched[u], c = cnt[m]; chStart[E + m] = top; chLen[E + m] = c; cnt[m] = top; top += c; }
        this.top = top;
      }
      evaluated += nk;
      for (let u = 0; u < nk; u++) {
        const m = touched[u], ch = E + m;
        cnt[m] = 0;
        chBits[ch] = -1;
        fired[this.nFired++] = ch;
        for (let w = wStart[ch], we = wStart[ch + 1]; w < we; w++) {
          const mm = wList[w];
          if (wConn[w] >= 0) { actNext[w] = actHead[mm]; actHead[mm] = w; }
          if (!flag[mm]) { flag[mm] = 1; const l = layerOf[mm]; next[mm] = head[l]; head[l] = mm; }
        }
        if (tStart[ch + 1] > tStart[ch]) stack[depth++] = ch;
      }
    }
    return evaluated;
  }

  // One bitmap per byte value present in the window (built on first use).
  _byteBits() {
    const P = this.P, bStart = this.bStart, present = this.present;
    for (let t = 0; t < this.nPresent; t++) {
      const b = present[t], at = (this.byteBits[b] = this._allocBits()), B = this.B;
      for (let i = bStart[b], e = bStart[b + 1]; i < e; i++) { const p = P[i]; B[at + (p >>> 5)] |= 1 << (p & 31); }
    }
    this.byteBitsReady = true;
  }

  // Evaluate the network on buf[0..W). Positions outside the buffer read as 0 and no neuron
  // is evaluated outside it, exactly like the Python reference on the same buffer. Afterwards
  // chLen[c] is the number of active positions of channel c and _toList(c) its sorted positions.
  //
  // A channel is held as a sorted position list, as a bitmap over the W positions, or both
  // (converted on demand and cached). Sparse inputs are combined by walking the shortest list
  // and probing the others; dense inputs are combined 32 positions at a time on bitmaps.
  _run(buf, W) {
    const E = this.E, emb = this.emb, chStart = this.chStart, chLen = this.chLen, chBits = this.chBits;
    const cStart = this.cStart, cSrc = this.cSrc, cOff = this.cOff, nPos = this.nPos, bias = this.bias, kind = this.kind;
    const wStart = this.wStart, wList = this.wList, layerOf = this.layerOf, isBool = this.isBool, negBool = this.negBool;
    const flag = this.flag, next = this.next, head = this.head, fired = this.fired, cur = this.cur;
    const posBool = this.posBool, skipMark = this.skipMark, skip = this.skip;
    const wConn = this.wConn, actHead = this.actHead, actNext = this.actNext, aj = this.aj, tStart = this.tStart;
    const byteStart = this.byteStart, byteCls = this.byteCls, hist = this.hist;
    const nLayers = this.nLayers;
    const nw = (this.nw = (W + 31) >>> 5), tailMask = W & 31 ? (1 << (W & 31)) - 1 : -1;
    const dense = this.noBits ? Infinity : Math.max(4, W >> this.denseShift); // lists at least this long go the bitmap way

    for (let i = 0; i < this.nFired; i++) { const c = fired[i]; chLen[c] = 0; chStart[c] = -1; chBits[c] = -1; }
    let nFired = 0, evaluated = 0;
    if (this.acc.length < W) { this.acc = new Int32Array(W * 2); this.touched = new Int32Array(W * 2); }
    const acc = this.acc, touched = this.touched;
    this.btop = 0;

    // ---- layer 0: positions grouped by byte value (counting sort); class counts from the histogram
    hist.fill(0);
    for (let i = 0; i < W; i++) hist[buf[i]]++;
    chLen.fill(0, 0, E);
    chBits.fill(-1, 0, E);
    chStart.fill(-1, 0, E);
    const bStart = this.bStart, present = this.present;
    let nPresent = 0;
    for (let b = 0; b < 256; b++) {
      const h = hist[b];
      bStart[b + 1] = bStart[b] + h;
      if (h) present[nPresent++] = b;
      if (h) for (let k = byteStart[b], e = byteStart[b + 1]; k < e; k++) chLen[byteCls[k]] += h;
    }
    if (W > this.cap) { this.top = 0; this._grow(W); }
    let P = this.P, V = this.V, B = this.B;
    { const f = this.bFill; f.set(bStart.subarray(0, 256)); for (let i = 0; i < W; i++) P[f[buf[i]]++] = i; }
    let top = W;
    this.dense = dense;
    this.nPresent = nPresent;
    this.byteBitsReady = false;
    this.tailMask = tailMask;
    for (let c = 0; c < E; c++) {
      if (chLen[c]) {
        for (let k = wStart[c], e = wStart[c + 1]; k < e; k++) {
          const m = wList[k];
          if (wConn[k] >= 0) { actNext[k] = actHead[m]; actHead[m] = k; }
          if (!flag[m]) { flag[m] = 1; const l = layerOf[m]; next[m] = head[l]; head[l] = m; }
        }
      }
    }
    if (this.scheduleAll) {
      for (let m = this.nNeu - 1; m >= 0; m--) if (!flag[m] && kind[m] !== K_DEAD) { flag[m] = 1; const l = layerOf[m]; next[m] = head[l]; head[l] = m; }
    }

    // ---- neurons, layer by layer; inside a layer the order does not matter
    for (let layer = 0; layer < nLayers; layer++) {
      let n = head[layer];
      head[layer] = -1;
      for (; n >= 0; n = next[n]) {
        flag[n] = 0;
        evaluated++;
        const s0 = cStart[n], sp = s0 + nPos[n], s1 = cStart[n + 1];
        const k = kind[n];
        let bitsAt = -1, count = 0;
        if (k === K_TRIE) {
          // AND(embedding channel ec at eo, neuron channel at go): walk the neuron's list
          const src = cSrc[s0 + 1], len = chLen[src];
          if (len === 0) continue;
          this.top = top;
          if (chStart[src] < 0) { this._toList(src); top = this.top; }
          if (top + len > this.cap) { this.top = top; this._grow(top + len); }
          P = this.P; V = this.V;
          const o = top, ec = cSrc[s0], eo = cOff[s0], go = cOff[s0 + 1];
          for (let i = chStart[src], e = i + len; i < e; i++) {
            const q = P[i] - go, x = q + eo;
            if (q >= 0 && q < W && x >= 0 && x < W && emb[buf[x] * E + ec]) P[top++] = q;
          }
          if (top === o) continue;
          chStart[E + n] = o; count = top - o;
        } else if (k === K_AND) {
          let g = s0, gl = chLen[cSrc[s0]];
          for (let j = s0 + 1; j < sp; j++) { const l = chLen[cSrc[j]]; if (l < gl) { gl = l; g = j; } }
          if (gl === 0) continue;
          if (gl >= dense && negBool[n]) {
            // every input is dense: AND the shifted bitmaps, clear where a negative input is set
            this.top = top;
            for (let j = s0; j < s1; j++) { const c = cSrc[j]; if (chLen[c] && chBits[c] < 0) this._toBits(c); }
            bitsAt = this._allocBits();
            B = this.B;
            if (s1 - s0 === 2 && (sp - s0 === 2 || chLen[cSrc[s0 + 1]])) {
              count = bin2(B, bitsAt, chBits[cSrc[s0]], cOff[s0], chBits[cSrc[s0 + 1]], cOff[s0 + 1], nw, sp - s0 === 2 ? 0 : 1, tailMask);
            } else {
              for (let j = s0; j < sp; j++) combine(B, bitsAt, chBits[cSrc[j]], cOff[j], nw, j === s0 ? 0 : 1);
              for (let j = sp; j < s1; j++) if (chLen[cSrc[j]]) combine(B, bitsAt, chBits[cSrc[j]], cOff[j], nw, 3);
              B[bitsAt + nw - 1] &= tailMask;
              count = popcount(B, bitsAt, nw);
            }
            if (count === 0) { this.btop = bitsAt; continue; }
          } else {
            this.top = top;
            const gc = cSrc[g];
            if (chStart[gc] < 0) { this._toList(gc); top = this.top; }
            if (top + gl > this.cap) { this.top = top; this._grow(top + gl); }
            P = this.P; V = this.V;
            for (let j = s0; j < s1; j++) cur[j - s0] = chStart[cSrc[j]];
            const o = top, go = cOff[g];
            if (s1 - s0 === 2) {
              // two inputs: the common case, one tight loop per representation of the other input
              const oj = g === s0 ? s0 + 1 : s0, c = cSrc[oj], oo = cOff[oj], neg = oj >= sp ? 1 : 0;
              const i0 = chStart[gc], e = i0 + gl;
              if (c < E) {
                for (let i = i0; i < e; i++) {
                  const q = P[i] - go, x = q + oo;
                  if (q >= 0 && q < W && (x >= 0 && x < W ? emb[buf[x] * E + c] : 0) !== neg) P[top++] = q;
                }
              } else if (chLen[c] === 0) { // an empty negative input
                for (let i = i0; i < e; i++) { const q = P[i] - go; if (q >= 0 && q < W) P[top++] = q; }
              } else if (chBits[c] >= 0) {
                const cb = chBits[c];
                for (let i = i0; i < e; i++) {
                  const q = P[i] - go, x = q + oo;
                  if (q >= 0 && q < W && (x >= 0 && x < W ? (B[cb + (x >>> 5)] >>> (x & 31)) & 1 : 0) !== neg) P[top++] = q;
                }
              } else {
                let lo = chStart[c];
                const hi = lo + chLen[c];
                for (let i = i0; i < e; i++) {
                  const q = P[i] - go;
                  if (q < 0) continue;
                  if (q >= W) break;
                  const x = q + oo;
                  lo = seek(P, lo, hi, x);
                  if ((lo < hi && P[lo] === x ? 1 : 0) !== neg) P[top++] = q;
                }
              }
            } else
            for (let i = chStart[gc], e = i + gl; i < e; i++) {
              const q = P[i] - go;
              if (q < 0) continue;
              if (q >= W) break;
              let s = 1;
              for (let j = s0; j < sp; j++) {
                if (j === g) continue;
                const c = cSrc[j], x = q + cOff[j];
                if (x < 0 || x >= W) { s = 0; break; }
                if (c < E) { if (!emb[buf[x] * E + c]) { s = 0; break; } }
                else if (chBits[c] >= 0) { if (!((B[chBits[c] + (x >>> 5)] >>> (x & 31)) & 1)) { s = 0; break; } }
                else {
                  const hi = chStart[c] + chLen[c], lo = seek(P, cur[j - s0], hi, x);
                  cur[j - s0] = lo;
                  if (lo >= hi || P[lo] !== x) { s = 0; break; }
                }
              }
              if (s === 0) continue;
              for (let j = sp; j < s1; j++) {
                const c = cSrc[j], x = q + cOff[j];
                if (x < 0 || x >= W) continue;
                if (c < E) { if (emb[buf[x] * E + c]) { s = 0; break; } }
                else if (chLen[c] === 0) continue;
                else if (chBits[c] >= 0) { if ((B[chBits[c] + (x >>> 5)] >>> (x & 31)) & 1) { s = 0; break; } }
                else {
                  const hi = chStart[c] + chLen[c], lo = seek(P, cur[j - s0], hi, x);
                  cur[j - s0] = lo;
                  if (lo < hi && P[lo] === x) { s -= isBool[c] ? 1 : V[lo]; if (s <= 0) break; }
                }
              }
              if (s > 0) P[top++] = q;
            }
            if (top === o) continue;
            chStart[E + n] = o; count = top - o;
          }
        } else {
          // aj: the positive inputs that are active. A neuron with many inputs gets them from
          // the list its wake-ups built, so 250 silent inputs of a 256-way OR cost nothing.
          let total = 0, na = 0;
          if (sp - s0 >= BIG_FAN) {
            for (let a = actHead[n]; a >= 0; a = actNext[a]) { const j = wConn[a]; aj[na++] = j; total += chLen[cSrc[j]]; }
            actHead[n] = -1;
          } else for (let j = s0; j < sp; j++) { const l = chLen[cSrc[j]]; if (l) { aj[na++] = j; total += l; } }
          if (total === 0) continue;
          this.top = top;
          if (s1 - s0 === 1 && !(k === K_OR && total >= dense)) {
            // one input: a shifted copy, or a threshold on a counter
            const c = cSrc[s0], off = cOff[s0], b = bias[n], outBool = isBool[E + n];
            if (chStart[c] < 0) { this._toList(c); top = this.top; }
            if (top + total > this.cap) { this.top = top; this._grow(top + total); }
            P = this.P; V = this.V;
            const o = top;
            let i = chStart[c];
            const e = i + total;
            while (i < e && P[i] < off) i++;
            if (isBool[c]) { if (b === 0) for (; i < e; i++) { const q = P[i] - off; if (q >= W) break; P[top++] = q; } }
            else for (; i < e; i++) {
              const q = P[i] - off, s = V[i] + b;
              if (q >= W) break;
              if (s > 0) { if (!outBool) V[top] = s; P[top++] = q; }
            }
            if (top === o) continue;
            chStart[E + n] = o; count = top - o;
          } else if (k === K_OR && total >= dense) {
            // dense union: OR the shifted inputs into a fresh bitmap (lists are scattered in directly)
            bitsAt = this._allocBits();
            B = this.B; P = this.P;
            if (na === 2) for (let u = 0; u < 2; u++) { const c = cSrc[aj[u]]; if (chBits[c] < 0) { this._toBits(c); B = this.B; } }
            if (na === 2) count = bin2(B, bitsAt, chBits[cSrc[aj[0]]], cOff[aj[0]], chBits[cSrc[aj[1]]], cOff[aj[1]], nw, 2, tailMask);
            else {
              for (let u = 0; u < na; u++) {
                const j = aj[u], c = cSrc[j], len = chLen[c], off = cOff[j];
                if (c < E && chStart[c] < 0 && chBits[c] < 0) { this._emb(c, true); B = this.B; }
                if (chBits[c] >= 0) combine(B, bitsAt, chBits[c], off, nw, 2);
                else {
                  for (let i = chStart[c], e = i + len; i < e; i++) {
                    const q = P[i] - off;
                    if (q >= 0 && q < W) B[bitsAt + (q >>> 5)] |= 1 << (q & 31);
                  }
                }
              }
              B[bitsAt + nw - 1] &= tailMask;
              count = popcount(B, bitsAt, nw);
            }
            if (count === 0) { this.btop = bitsAt; continue; }
          } else {
            // With many input events the sums are formed for all inputs, negatives included, and
            // every position is scanned afterwards; otherwise only touched positions are tracked.
            // A neuron that needs t >= 2 of its 0/1 positive inputs cannot fire where only its
            // t-1 longest inputs are active, so those are not walked: they are probed, like the
            // negatives, at the positions the other inputs produce.
            let nskip = 0, work = total;
            if (k === K_GEN && posBool[n] && bias[n] < 0 && !this.noSkip) {
              for (let want = Math.min(-bias[n], 4, na - 1); nskip < want; nskip++) {
                let best = -1, bl = 15; // not worth it for short lists
                for (let u = 0; u < na; u++) { const j = aj[u], l = chLen[cSrc[j]]; if (l > bl && !skipMark[j - s0]) { bl = l; best = j; } }
                if (best < 0) break;
                skipMark[best - s0] = 1; skip[nskip] = best; work -= bl;
              }
            }
            const scan = work >= W >> 1 && !(k === K_OR && sp - s0 === 2 && !this.noMerge);
            if (scan) { while (nskip) skipMark[skip[--nskip] - s0] = 0; }
            for (let u = 0; u < na; u++) {
              const j = aj[u], c = cSrc[j];
              if (chStart[c] < 0 && !(skipMark[j - s0] && (c < E || chBits[c] >= 0))) this._toList(c);
            }
            if (scan) for (let j = sp; j < s1; j++) { const c = cSrc[j]; if (chLen[c] && chStart[c] < 0) this._toList(c); }
            top = this.top;
            if (top + total > this.cap) { this._grow(top + total); }
            P = this.P; V = this.V;
            const o = top;
            if (k === K_OR && sp - s0 === 2 && !this.noMerge) {
              // union of two sorted lists
              const ca = cSrc[s0], cb = cSrc[s0 + 1], oa = cOff[s0], ob = cOff[s0 + 1];
              let i = chStart[ca], j = chStart[cb];
              const ie = i + chLen[ca], je = j + chLen[cb];
              while (i < ie && P[i] - oa < 0) i++;
              while (j < je && P[j] - ob < 0) j++;
              while (i < ie && j < je) {
                const a = P[i] - oa, b = P[j] - ob;
                if (a < b) { if (a >= W) { i = ie; break; } P[top++] = a; i++; }
                else if (b < a) { if (b >= W) { j = je; break; } P[top++] = b; j++; }
                else { if (a >= W) { i = ie; j = je; break; } P[top++] = a; i++; j++; }
              }
              for (; i < ie; i++) { const a = P[i] - oa; if (a >= W) break; P[top++] = a; }
              for (; j < je; j++) { const b = P[j] - ob; if (b >= W) break; P[top++] = b; }
            } else {
              // general neuron: sum the positive inputs into a dense accumulator, remember which
              // positions were touched, then subtract negatives and threshold at those positions
              const b = bias[n], outBool = isBool[E + n];
              if (scan) {
                for (let u = 0, ue = na + s1 - sp; u < ue; u++) {
                  const j = u < na ? aj[u] : sp + u - na, c = cSrc[j], len = chLen[c];
                  if (len === 0) continue;
                  const off = cOff[j], bool = isBool[c];
                  let i = chStart[c];
                  const e = i + len;
                  while (i < e && P[i] < off) i++;
                  if (j < sp) {
                    if (bool) for (; i < e; i++) { const q = P[i] - off; if (q >= W) break; acc[q]++; }
                    else for (; i < e; i++) { const q = P[i] - off; if (q >= W) break; acc[q] += V[i]; }
                  } else if (bool) for (; i < e; i++) { const q = P[i] - off; if (q >= W) break; acc[q]--; }
                  else for (; i < e; i++) { const q = P[i] - off; if (q >= W) break; acc[q] -= V[i]; }
                }
                for (let q = 0; q < W; q++) {
                  let s = acc[q];
                  if (s === 0) continue;
                  acc[q] = 0;
                  s += b;
                  if (s > 0) { if (!outBool) V[top] = s; P[top++] = q; }
                }
              } else {
              let nt = 0, sorted = true, last = -1;
              for (let u = 0; u < na; u++) {
                const j = aj[u], c = cSrc[j], len = chLen[c];
                if (skipMark[j - s0]) continue;
                const off = cOff[j], bool = isBool[c];
                for (let i = chStart[c], e = i + len; i < e; i++) {
                  const q = P[i] - off;
                  if (q < 0) continue;
                  if (q >= W) break;
                  if (acc[q] === 0) { touched[nt++] = q; if (q < last) sorted = false; last = q; }
                  acc[q] += bool ? 1 : V[i];
                }
              }
              if (!sorted) touched.subarray(0, nt).sort();
              for (let j = sp; j < s1; j++) cur[j - s0] = chStart[cSrc[j]];
              for (let u = 0; u < nskip; u++) cur[skip[u] - s0] = chStart[cSrc[skip[u]]];
              for (let t = 0; t < nt; t++) {
                const q = touched[t];
                let s = acc[q] + b;
                acc[q] = 0;
                for (let u = 0; u < nskip; u++) {
                  const j = skip[u], c = cSrc[j], x = q + cOff[j];
                  if (x < 0 || x >= W) continue;
                  if (c < E) s += emb[buf[x] * E + c];
                  else if (chBits[c] >= 0) s += (B[chBits[c] + (x >>> 5)] >>> (x & 31)) & 1;
                  else {
                    const hi = chStart[c] + chLen[c], lo = seek(P, cur[j - s0], hi, x);
                    cur[j - s0] = lo;
                    if (lo < hi && P[lo] === x) s++;
                  }
                }
                if (s <= 0) continue;
                for (let j = sp; j < s1; j++) {
                  const c = cSrc[j], x = q + cOff[j];
                  if (x < 0 || x >= W) continue;
                  if (c < E) { if (emb[buf[x] * E + c]) s--; }
                  else if (chLen[c] === 0) continue;
                  else if (chBits[c] >= 0) s -= (B[chBits[c] + (x >>> 5)] >>> (x & 31)) & 1;
                  else {
                    const hi = chStart[c] + chLen[c], lo = seek(P, cur[j - s0], hi, x);
                    cur[j - s0] = lo;
                    if (lo < hi && P[lo] === x) s -= isBool[c] ? 1 : V[lo];
                  }
                }
                if (s > 0) { if (!outBool) V[top] = s; P[top++] = q; }
              }
              while (nskip) skipMark[skip[--nskip] - s0] = 0;
              }
            }
            if (top === o) continue;
            chStart[E + n] = o; count = top - o;
          }
        }
        const ch = E + n;
        chBits[ch] = bitsAt;
        if (bitsAt >= 0) chStart[ch] = -1;
        chLen[ch] = count;
        fired[nFired++] = ch;
        for (let w = wStart[ch], e = wStart[ch + 1]; w < e; w++) {
          const m = wList[w];
          if (wConn[w] >= 0) { actNext[w] = actHead[m]; actHead[m] = w; }
          if (!flag[m]) { flag[m] = 1; const l = layerOf[m]; next[m] = head[l]; head[l] = m; }
        }
        if (tStart[ch + 1] > tStart[ch]) {
          this.top = top; this.nFired = nFired;
          evaluated += this._trie(ch, buf, W);
          top = this.top; nFired = this.nFired; P = this.P; V = this.V; B = this.B;
        }
      }
    }
    this.top = top;
    this.nFired = nFired;
    this.stats.windows++;
    this.stats.evaluated += evaluated;
    this.stats.events += top;
  }

  // Append the runs of every wanted label inside window positions [lo, hi) to `out` as
  // [start, end, labelIndex] in document byte offsets (window position p is byte p + shift).
  _collect(lo, hi, shift, includeAux, out, lastOf) {
    const chStart = this.chStart, chLen = this.chLen, labelCh = this.labelCh;
    let P = this.P;
    for (let li = 0; li < labelCh.length; li++) {
      if (!includeAux && this.labelAux[li]) continue;
      const c = labelCh[li];
      if (chLen[c] === 0) continue;
      if (chStart[c] < 0) { this._toList(c); P = this.P; }
      const end = chStart[c] + chLen[c];
      let i = seek(P, chStart[c], end, lo);
      while (i < end && P[i] < hi) {
        const a = P[i];
        let b = a + 1;
        i++;
        while (i < end && P[i] === b && b < hi) { b++; i++; }
        const prev = lastOf[li];
        if (prev && prev[1] === a + shift) prev[1] = b + shift; // run continues across a chunk seam
        else out.push((lastOf[li] = [a + shift, b + shift, li]));
      }
    }
  }

  // buf holds PAD zero bytes, the n document bytes, PAD zero bytes.
  _spans(buf, n, includeAux) {
    const PAD = this.PAD, B = n + 2 * PAD, out = [], lastOf = new Array(this.labelCh.length);
    let hl = 0, hr = 0, core = 0, whole = B <= (this._chunk || MIN_CHUNK);
    if (!whole) { hl = this.reachLeft; hr = this.reachRight; core = this.chunk; whole = B <= core + hl + hr; }
    if (whole) {
      this._run(buf.subarray(0, B), B);
      this._collect(PAD, PAD + n, -PAD, includeAux, out, lastOf);
    } else {
      // Long input: evaluate overlapping windows. A window covers `core` bytes plus reachLeft
      // bytes before and reachRight after (clamped to the padded buffer), so every value that
      // an output inside the core depends on is computed inside the window: results are exact.
      for (let a = PAD; a < PAD + n; a += core) {
        const b = Math.min(PAD + n, a + core);
        const w0 = Math.max(0, a - hl), w1 = Math.min(B, b + hr);
        this._run(buf.subarray(w0, w1), w1 - w0);
        this._collect(a - w0, b - w0, w0 - PAD, includeAux, out, lastOf);
      }
    }
    const labels = this.labels;
    out.sort((x, y) => x[0] - y[0] || x[1] - y[1] || (labels[x[2]] < labels[y[2]] ? -1 : labels[x[2]] > labels[y[2]] ? 1 : 0));
    return out;
  }

  _buffer(size) {
    if (this.scratch.length < size) this.scratch = new Uint8Array(Math.max(size, this.scratch.length * 2));
    return this.scratch;
  }

  // Spans over raw bytes: [{start, end, label}] with byte offsets, sorted by (start, end, label).
  detectBytes(bytes, opts = {}) {
    const PAD = this.PAD, n = bytes.length;
    const buf = this._buffer(n + 2 * PAD);
    buf.fill(0, 0, PAD);
    buf.set(bytes, PAD);
    buf.fill(0, PAD + n, n + 2 * PAD);
    const labels = this.labels;
    return this._spans(buf, n, !!opts.includeAux).map((s) => ({ start: s[0], end: s[1], label: labels[s[2]] }));
  }

  // Spans over a JavaScript string: [{start, end, label, text}] with UTF-16 offsets, sorted by
  // (start, end, label). Auxiliary labels ("kind:*", "_*") are left out unless opts.includeAux.
  detect(text, opts = {}) {
    const PAD = this.PAD;
    const buf = this._buffer(text.length * 3 + 2 * PAD);
    buf.fill(0, 0, PAD);
    const n = this.encoder.encodeInto(text, buf.subarray(PAD)).written;
    buf.fill(0, PAD + n, n + 2 * PAD);
    const spans = this._spans(buf, n, !!opts.includeAux);
    const labels = this.labels, res = new Array(spans.length);
    if (n === text.length) { // pure ASCII: byte offsets are string offsets
      for (let i = 0; i < spans.length; i++) {
        const s = spans[i];
        res[i] = { start: s[0], end: s[1], label: labels[s[2]], text: text.slice(s[0], s[1]) };
      }
      return res;
    }
    if (spans.length === 0) return res;
    // u16[i] = UTF-16 index of the character that byte i belongs to; u16[n] = text.length
    const u16 = new Int32Array(n + 1);
    for (let i = 0, cu = 0, nx = 0; i < n; i++) {
      const b = buf[PAD + i];
      if ((b & 0xc0) !== 0x80) { cu = nx; nx += b >= 0xf0 ? 2 : 1; }
      u16[i] = cu;
    }
    u16[n] = text.length;
    for (let i = 0; i < spans.length; i++) {
      const s = spans[i];
      let e = s[1];
      while (e < n && (buf[PAD + e] & 0xc0) === 0x80) e++; // a span covers whole characters
      const a = u16[s[0]], b = u16[e];
      res[i] = { start: a, end: b, label: labels[s[2]], text: text.slice(a, b) };
    }
    return res;
  }
}

// Load a model from a URL (string / URL, fetched), an ArrayBuffer or a typed array.
export async function loadModel(source, opts = {}) {
  let bytes;
  if (typeof source === "string" || (typeof URL !== "undefined" && source instanceof URL)) {
    const r = await fetch(source);
    if (!r.ok) throw new Error(`blur: cannot fetch ${source}: ${r.status}`);
    bytes = new Uint8Array(await r.arrayBuffer());
  } else if (source instanceof ArrayBuffer) bytes = new Uint8Array(source);
  else if (ArrayBuffer.isView(source)) bytes = new Uint8Array(source.buffer, source.byteOffset, source.byteLength);
  else throw new TypeError("blur: loadModel expects a URL, an ArrayBuffer or a typed array");
  if (bytes.length < 4 || bytes[0] !== MAGIC0 || bytes[1] !== MAGIC1) throw new Error("blur: not a model file");
  if (bytes[2] !== VERSION || bytes[3] !== CODEC_DEFLATE_RAW) throw new Error(`blur: unsupported model version ${bytes[2]}.${bytes[3]}`);
  const payload = await inflateRaw(bytes.subarray(4), opts.inflate);
  return new Model(payload, { ...opts, bytes: bytes.length });
}
