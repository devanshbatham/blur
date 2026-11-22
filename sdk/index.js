// blur SDK: mask personal data and secrets in text, in the browser, a Web Worker or Node. No dependencies.
//
//   import { createBlur } from "blur";
//   const blur = await createBlur();
//   blur.mask("Call Priya on +91 98765 43210").text      // "Call [private_person] on [private_phone]"
import { loadModel } from "../web/engine.js";
import { maskStandalone } from "../web/standalone.js";

export const VERSION = "1.0.0";

/** The ten output labels. */
export const LABELS = Object.freeze(["private_person", "private_address", "private_email", "private_phone", "private_date",
  "private_url", "account_number", "personal_id", "secret", "online_identifier"]);

const DEFAULT_MODEL = new URL("../web/model-general.bin", import.meta.url);

async function modelBytes(source) {
  if (source instanceof ArrayBuffer) return source;
  if (ArrayBuffer.isView(source)) return source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength);
  const url = source == null ? DEFAULT_MODEL : source instanceof URL ? source : new URL(String(source), globalThis.location?.href ?? DEFAULT_MODEL);
  if (url.protocol === "file:") {                                   // Node: read the file directly
    const { readFile } = await import("node:fs/promises");
    const b = await readFile(url);
    return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`blur: cannot fetch the model (${res.status} ${url})`);
  return res.arrayBuffer();
}

function checkLabels(list, name) {
  if (list == null) return null;
  const set = new Set(list);
  for (const l of set) if (!LABELS.includes(l)) throw new TypeError(`blur: unknown label "${l}" in ${name}`);
  return set;
}

/**
 * Load the model and return a masker.
 * @param {object} [options]
 * @param {string|URL|ArrayBuffer|ArrayBufferView} [options.model]  model file (default: the bundled web/model-general.bin)
 * @param {boolean} [options.pipeline=false]  load the full pipeline (cross-document name linking, numbered placeholders)
 */
export async function createBlur(options = {}) {
  const model = await loadModel(await modelBytes(options.model));
  const pipeline = options.pipeline ? await import("../web/postprocess.js") : null;

  // spans with their placeholder, filtered and non-overlapping
  function find(text, opts) {
    if (typeof text !== "string") throw new TypeError("blur: text must be a string");
    const only = checkLabels(opts.only, "only"), keep = checkLabels(opts.keep, "keep");
    let spans;
    if (pipeline && opts.pipeline !== false) {
      spans = pipeline.maskText(model, text, { numbered: !!opts.numbered }).spans
        .map(s => ({ start: s.start, end: s.end, label: (s.tag10 || "[personal_id]").slice(1, -1), tag: s.shown || s.tag10 }));
    } else {
      if (opts.numbered) throw new Error("blur: numbered placeholders need createBlur({ pipeline: true })");
      spans = maskStandalone(model, text).spans.map(s => ({ start: s.start, end: s.end, label: s.label, tag: `[${s.label}]` }));
    }
    const out = [];
    let last = 0;
    for (const s of spans.sort((a, b) => a.start - b.start)) {
      if (s.start < last || (only && !only.has(s.label)) || (keep && keep.has(s.label))) continue;
      out.push({ ...s, text: text.slice(s.start, s.end) });
      last = s.end;
    }
    return out;
  }

  /**
   * Find personal data and secrets.
   * @returns {{start:number,end:number,label:string,text:string}[]}  UTF-16 offsets into `text`
   */
  function detect(text, opts = {}) {
    return find(text, opts).map(({ tag, ...s }) => s);
  }

  /**
   * Mask personal data and secrets.
   * @param {string} text
   * @param {object} [opts]  only / keep: label lists; numbered: [PERSON_1]-style placeholders (pipeline only);
   *                         char: replace each masked character with this one instead of a placeholder
   * @returns {{text:string, spans:{start:number,end:number,label:string,text:string}[]}}
   */
  function mask(text, opts = {}) {
    if (opts.char != null && [...String(opts.char)].length !== 1) throw new TypeError("blur: char must be one character");
    const spans = find(text, opts);
    let out = "", p = 0;
    for (const s of spans) {
      out += text.slice(p, s.start) + (opts.char != null ? [...s.text].map(ch => /\s/.test(ch) ? ch : opts.char).join("") : s.tag);
      p = s.end;
    }
    return { text: out + text.slice(p), spans: spans.map(({ tag, ...s }) => s) };
  }

  return Object.freeze({ mask, detect, labels: LABELS, info: model.info, version: VERSION });
}
