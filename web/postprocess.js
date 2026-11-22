// The pipeline around the network: decoding, clean-up, context rules, names, evidence, keys and numbered placeholders.
// Each stage is a module in pipeline/; this file is the public entry point. Offsets are the original text's UTF-16 offsets.
export { decodeSpans } from "./pipeline/decode.js";
export { specificKind } from "./pipeline/validators.js";
export { detect } from "./pipeline/detect.js";
export { dateKeys } from "./pipeline/consistency.js";
export { roleOf, labelOf } from "./pipeline/labels.js";
export { LABEL10, label10, numberedMask } from "./pipeline/placeholders.js";
export { KEEP_LABELS, OPTIONS } from "./pipeline/common.js";
export { pieces, detectLong, maskText } from "./pipeline/mask.js";
