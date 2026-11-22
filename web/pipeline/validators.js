// Format validators (Luhn, Verhoeff, mod-97) and the specific kind of an identifier.

// --- format validators: a value that passes one gets the specific label
export function luhn(d) { let sum = 0, alt = false; for (let i = d.length - 1; i >= 0; i--) { let x = +d[i]; if (alt) { x *= 2; if (x > 9) x -= 9; } sum += x; alt = !alt; } return sum % 10 === 0; }

export const VD = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
  [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]];

export const VP = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],
  [4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]];

export function verhoeff(d) { let c = 0; const r = d.split("").reverse(); for (let i = 0; i < r.length; i++) c = VD[c][VP[i % 8][+r[i]]]; return c === 0; }

export function mod97(v) { const r = v.slice(4) + v.slice(0, 4); let m = 0; for (const ch of r) { const n = /\d/.test(ch) ? ch : String(ch.charCodeAt(0) - 55); for (const x of n) m = (m * 10 + +x) % 97; } return m === 1; }

export function specificKind(v) {
  const t = v.trim(), compact = t.replace(/[\s-]/g, "");
  if (/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(compact) && mod97(compact)) return "IBAN";
  if (/^\d{4}[ -]?\d{4}[ -]?\d{4}$/.test(t) && /^[2-9]/.test(compact) && verhoeff(compact)) return "AADHAAR";
  if (/^\d{13,19}$/.test(compact) && /^[3-6]/.test(compact) && luhn(compact) && /^[\d\s-]+$/.test(t)) return "CARD";
  if (/^MRN[-: ]?\d{4,}$/i.test(t)) return "MRN";
  if (/^[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]$/.test(t)) return "PAN";
  return null;
}
