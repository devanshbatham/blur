// Deterministic structure and spelling layers used by postprocess.js. No value from any test text appears here: every
// rule is a format, a script table, or a link to an entity that the network already found in the same document.

// ---------- number words, NATO spelling, dates in words ----------
const NUM = { zero: 0, oh: 0, o: 0, nil: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
  // Hindi / Hinglish (romanised)
  shunya: 0, sunya: 0, shoonya: 0, ek: 1, do: 2, teen: 3, tin: 3, char: 4, chaar: 4, chār: 4, paanch: 5, panch: 5, pāñch: 5,
  chhe: 6, chhah: 6, chah: 6, che: 6, saat: 7, sat: 7, aath: 8, ath: 8, nau: 9, no: null };
delete NUM.no;
const REPEAT = { double: 2, triple: 3, treble: 3 };
const NATO = { alpha: "a", alfa: "a", bravo: "b", charlie: "c", delta: "d", echo: "e", foxtrot: "f", golf: "g", hotel: "h",
  india: "i", juliet: "j", juliett: "j", kilo: "k", lima: "l", mike: "m", november: "n", oscar: "o", papa: "p", quebec: "q",
  romeo: "r", sierra: "s", tango: "t", uniform: "u", victor: "v", whiskey: "w", whisky: "w", xray: "x", "x-ray": "x",
  yankee: "y", zulu: "z" };
const WORD_RE = /[\p{L}\p{M}-]+|\d+/gu;
function wordsWithPos(text) { const out = []; let m; WORD_RE.lastIndex = 0; while ((m = WORD_RE.exec(text))) out.push({ w: m[0], lw: m[0].toLowerCase(), a: m.index, b: m.index + m[0].length }); return out; }
const gapOk = (text, a, b) => /^[\s,;\-–]*(and\s+)?[\s,;\-–]*$/i.test(text.slice(a, b));

export function spokenSpans(text) {
  const ws = wordsWithPos(text), out = [];
  // runs of digit words (with double/triple), separated by spaces / commas / "and"
  for (let i = 0; i < ws.length; i++) {
    if (!(ws[i].lw in NUM) && !(ws[i].lw in REPEAT) && !/^\d$/.test(ws[i].w)) continue;
    let j = i, digits = "", rep = 1, words = 0;
    while (j < ws.length && (ws[j].lw in NUM || ws[j].lw in REPEAT || /^\d{1,5}$/.test(ws[j].w)) && (j === i || gapOk(text, ws[j - 1].b, ws[j].a))) {
      const lw = ws[j].lw;
      if (lw in REPEAT) rep = REPEAT[lw];
      else { const d = /^\d+$/.test(lw) ? lw : String(NUM[lw]); digits += d.repeat(rep); rep = 1; if (!/^\d+$/.test(lw) || lw.length === 1) words++; }
      j++;
    }
    if (words >= 3) {
      const a = ws[i].a, b = ws[j - 1].b, before = text.slice(Math.max(0, a - 24), a).toLowerCase();
      if (/(cvv|cvc|cid|security code)\W*$/.test(before) && digits.length >= 3 && digits.length <= 4) out.push({ start: a, end: b, label: "SECRET", kind: "CVV", value: digits });
      else if (digits.length >= 8) out.push({ start: a, end: b, label: "TEL", value: digits });
      else if (digits.length >= 4 && /(otp|pin|code|passcode)\W*(is\W*)?$/.test(before)) out.push({ start: a, end: b, label: "SECRET", value: digits });
      i = j - 1;
    }
  }
  // e-mail addresses spelled with the NATO alphabet and "at" / "dot"
  for (let i = 0; i < ws.length; i++) {
    if (!(ws[i].lw in NATO)) continue;
    let j = i, s = "", hasAt = false, nato = 0;
    while (j < ws.length && (j === i || /^\s+$/.test(text.slice(ws[j - 1].b, ws[j].a)))) {
      const lw = ws[j].lw;
      if (lw in NATO) { s += NATO[lw]; nato++; }
      else if (lw === "dot") s += ".";
      else if (lw === "at") { s += "@"; hasAt = true; }
      else if (lw === "underscore") s += "_";
      else if (lw === "dash" || lw === "hyphen") s += "-";
      else if (/^[a-z0-9]{2,}$/.test(lw) && /[.@]$/.test(s)) s += lw;     // plain domain words: "example dot com"
      else break;
      j++;
    }
    if (nato >= 3 && hasAt && /^[a-z0-9._-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(s)) { out.push({ start: ws[i].a, end: ws[j - 1].b, label: "EMAIL", value: s }); i = j - 1; }
  }
  // a secret dictated in words after a password cue in the last lines: "it's jasmine at jayanagar fourteen"
  const SAY = /\b(?:it'?s|it is|the password is|password is|pass is|pin is|passcode is|(?:note|post-?it|paper|slip|card|message|text) (?:says|reads|said))\s+([a-z0-9@#!$%&*._ -]{4,60}?)(?=,|\.(?:\s|$)|;|\n|$)/gi;
  for (const m of text.matchAll(SAY)) {
    const before = text.slice(Math.max(0, m.index - 300), m.index), v = m[1];
    const spoken = /\b(at|dot|underscore|hash|capital|caps|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|hundred)\b|\d/i.test(v);
    const descriptive = /^(the same|same|like|similar|a mix|a combination|based on|kind of|sort of|something|basically|just|my |your |our |the pattern|a pattern|in the|on the)/i.test(v.trim()) ||
                        /\b(pattern|same as|similar to|guess|format|combination|plus)\b/i.test(v);
    if (/\b(pass(word|code|phrase)?|pwd|pin)\b/i.test(before + text.slice(m.index, m.index + 20)) && spoken && !descriptive && v.trim().split(/\s+/).length >= 2) {
      const a = m.index + m[0].length - m[1].length;
      // a clarification right after the value belongs to it: ", capital J both times"
      const cl = /^,\s*((?:capital|caps|upper ?case|lower ?case|all caps|small|with a|then|no spaces|with spaces)[^.,;\n]{0,40})/i.exec(text.slice(a + v.trimEnd().length, a + v.trimEnd().length + 60));
      out.push({ start: a, end: a + v.trimEnd().length + (cl ? cl[0].length : 0), label: "PASS" });
    }
  }
  // a password stated in a sentence: "pw is X", "the password for the guest network is X", "login pass: X"
  const PWS = /\b(?:password|passphrase|passcode|pass|pwd|pw)\b[^.\n]{0,40}?(?:\bis\b|:|=)\s+["'`]?([^\s"'`]{4,512})/gi;
  for (const m of text.matchAll(PWS)) {
    let v = m[1].replace(/[.,;!?)]+$/, ""); const a = m.index + m[0].lastIndexOf(m[1]);
    const qc = text[a - 1];                                                  // a quoted value runs to its closing quote
    if (/["'`]/.test(qc)) { const close = text.indexOf(qc, a), nl = text.indexOf("\n", a); if (close > a && (nl < 0 || close < nl)) v = text.slice(a, close); }
    const wordy = /^[a-z]+$/.test(v) && v.length < 9;                         // "is the same", "is required": a plain short word
    if (v.length >= 4 && !wordy && !/^(the|same|not|required|optional|wrong|correct|incorrect|expired|invalid|reset|set|stored|hashed|encrypted|here|below|above|this|that|your|my|his|her|null|none|n\/a|\*+|x+|<.*|\$\{.*)$/i.test(v))
      out.push({ start: a, end: a + v.length, label: "PASS" });
  }
  // a key or token stated in a sentence, with words between the cue and the value: "The API key for accessing is mk_7Ry...",
  // "the auth token that we use for deploys is tk-4f9a...". The cue is the evidence; the value must look generated.
  const KEYS = /\b(?:api[ _-]?key|access[ _-]?key|secret[ _-]?key|client[ _-]?secret|webhook[ _-]?secret|signing[ _-]?(?:key|secret)|encryption[ _-]?key|private[ _-]?key|(?:access|auth|bearer|refresh|api|session|deploy|bot|personal access)[ _-]?token|auth[ _-]?key|token|secret|credentials?)\b[^.\n:=]{0,70}?(?:\b(?:is|was|are|were|set to|changed to|rotated to|updated to|reads?)\b|:|=)\s+["'`]?([A-Za-z0-9][A-Za-z0-9_\-+\/=.~]{11,})/gi;
  for (const m of text.matchAll(KEYS)) {
    const v = m[1].replace(/[.,;!?)]+$/, ""), a = m.index + m[0].lastIndexOf(m[1]);
    const digits = (v.match(/\d/g) || []).length, cases = (v.match(/[a-z][A-Z]|[A-Z][a-z]/g) || []).length;
    if (/^AAAA[A-Z]\d/.test(v) || /public[ _-]?$/i.test(text.slice(Math.max(0, m.index - 8), m.index))) continue;       // public key material
    const generated = /[A-Za-z]/.test(v) && (digits >= 2 && v.length >= 12 || cases >= 4 && v.length >= 16);
    if (generated && !/^(https?:|www\.|\/)|@|^\d{1,3}(\.\d{1,3}){3}$|^v?\d+(\.\d+)+|^\d{4}-\d{2}-\d{2}|\.(com|org|net|io|json|ya?ml|txt|env|pem|key)$/i.test(v) && !/^[a-z]+([-_.][a-z]+)*$/.test(v))
      out.push({ start: a, end: a + v.length, label: "SECRET" });
  }
  // the same cue with the value right after it and no "is": "use this key for now 9fK2...", "pasted the secret in the channel X".
  // Without a copula the value must be unmistakably generated: 20+ characters, letters in both cases and three or more digits.
  const KEYS2 = /\b(?:api[ _-]?key|access[ _-]?key|secret[ _-]?key|client[ _-]?secret|(?:access|auth|bearer|refresh|api|session|deploy|bot)[ _-]?token|key|token|secret|credentials?)\b[^.\n:=]{0,40}?\s["'`]?([A-Za-z0-9][A-Za-z0-9_\-+\/=~]{19,})/gi;
  for (const m of text.matchAll(KEYS2)) {
    const v = m[1], a = m.index + m[0].lastIndexOf(v);
    // (public key material is public: "ssh-ed25519 AAAAC3...", "the public key is ...")
    if (/^AAAA[A-Z]\d/.test(v) || /public[ _-]?$/i.test(text.slice(Math.max(0, m.index - 8), m.index)) || /\bssh-(rsa|ed25519|dss)\s+$/.test(text.slice(Math.max(0, a - 14), a))) continue;
    if ((v.match(/\d/g) || []).length >= 3 && /[a-z]/.test(v) && /[A-Z]/.test(v) && !/^(https?|www)/i.test(v) && !/\//.test(v.slice(0, 8)))
      out.push({ start: a, end: a + v.length, label: "SECRET" });
  }
  // a lower-case signature: a short line of its own right after a closing line ("thx\nbhaskar", "regards\nsaoirse gallagher")
  const SIG = /(?:^|\n)[ \t]*(?:thx|thanks|thank you|regards|best regards|kind regards|warm regards|best|cheers|sincerely|rgds|br|love|yours)[,!.]?[ \t]*\n+[ \t]*(?:[-–—~] ?)?(\p{Ll}[\p{L}'-]{2,}(?: \p{Ll}[\p{L}'-]{1,}){0,2})[ \t]*(?=\n|$)/gu;
  for (const m of text.matchAll(SIG)) {
    const v = m[1], a = m.index + m[0].lastIndexOf(v);
    if (!/\b(team|support|desk|dept|department|group|company|admin|management|hr|sales|crew|staff|all|everyone|guys|folks|sent|from|the|and|for|your|you|me|us|we|again|so much|in advance|bye|later|soon)\b/i.test(v))
      out.push({ start: a, end: a + v.length, label: "GIVENNAME" });
  }
  // a record kept under a number: "listed under 4829-1037-5581", "filed under no. 77120934", "registered under ID 4471 2209 31"
  // (the verb is the evidence that the digits identify a record; nine or more digits, so not a count, a year or a page)
  const UNDER = /\b(?:listed|filed|registered|recorded|stored|saved|booked|logged|held|kept|indexed|tracked|opened|issued)\s+(?:under|as|with)\s+(?:the\s+)?(?:(?:number|no\.?|id|reference|ref\.?|code|file|case|account)\s+)?#?(\d[\d -]{7,24}\d)(?![\w-])/gi;
  for (const m of text.matchAll(UNDER)) {
    const v = m[1], a = m.index + m[0].lastIndexOf(v);
    if (v.replace(/\D/g, "").length >= 9 && !/  |--/.test(v)) out.push({ start: a, end: a + v.length, label: "ID" });
  }
  // A credential stated in a sentence, in any of several languages. The cue names what kind of secret it is; a short gap
  // and a copula (or a quote mark) lead to the value. Three value shapes: a quoted string; a short code of digits (with
  // separators, "#" or "*"); a word or a few words ending in digits or a symbol; after a colon, a short all-lower-case phrase.
  // A bare "code" counts only with a security qualifier (gate, door, alarm, keypad, lock, safe, verification, SMS ...):
  // error codes, post codes, promo codes and booking codes are not secrets.
  {
    const QUAL = "(?:gate|door|alarm|keypad|lock|padlock|lockbox|key ?box|safe|entry|access|security|verification|sms|otp|recovery|backup|2fa|login|garage|building|portal|room|store|side[- ]gate|bike[- ]store|kellerschloss|portal)";
    const CUES = "(?:pass ?word|passcode|pass ?phrase|passwd|pwd|\\bpw\\b|\\bpin\\b|\\botp\\b|one[- ]time (?:code|password)|combination|keypad|padlock|basic[- ]auth|memorable word|secret word|secret phrase|wi-?fi|wlan|" +
      QUAL + "[^.\\n?!;:]{0,24}?\\bcode|\\bcode (?:you|we|they|i) (?:texted|sent|got|received)|\\bcode f[üu]rs? \\w+|cvv|cvc|three digits on the back|" +
      "c[óo]digo (?:de|del|da|do) (?:la |el |o |a )?(?:puerta|portal|acceso|alarma|porta|port[ãa]o|entrada|garaje|garagem)|digicode|code (?:de la porte|d'entr[ée]e|de l'alarme|du portail)|t[üu]rcode|contrase[ñn]a|\\bclave\\b|c[óo]digo de (?:acceso|seguridad|verificaci[óo]n)|passwort|kennwort|mot de passe|\\bsenha\\b|\\bphrase\\b)";
    const COP = "(?:\\bis\\b|\\bwas\\b|\\bare\\b|it'?s\\b|\\bto\\b|\\blautet\\b|\\bist\\b|\\bes\\b|\\bera\\b|(?<![\\p{L}])[éÉ](?![\\p{L}])|\\best\\b|changed to|\\bwhich was|\\bhai\\b|sigue siendo|toujours|:|=|—|–)";
    const BAD = /\b(error|status|exit|http|zip|post(al)?|area|country|dial(l?ing)?|promo|discount|coupon|voucher|referral|booking|product|qr|source|sort|ifsc|swift|tracking|auth(ori[sz]ation)?|order|invoice|bar|dress|colou?r|response|reason|hs|hsn|tax|course|class|project)[ -]?code\b/i;
    const re = new RegExp(CUES + "([^.\\n;!?]{0,48}?)[ \\t]*" + COP + "?[ \\t]*(?:\\(?it (?:is|was)[: \\t]+|übrigens[ \\t]+|all (?:lower ?case|caps|one word)[:,]?[ \\t]*|literally[ \\t]+|still[ \\t]+|now[ \\t]+|just[ \\t]+)?" +
      "(?:(['\"`«“‘(])[ \\t]?([^'\"`»”’)\\n]{3,40}?)[ \\t]?['\"`»”’)]|((?:\\d[ -]?){2,7}\\d[#*]?)(?![\\w@]|[ -]\\d)|(?<=(?:\\bis|\\bwas|:|literally|pass ?word|passphrase|login,|siendo|toujours|still|now|[«“\"']) ?)((?:[A-Za-z]{3,} ){1,4}\\d{1,4}!?)(?![\\w])|(?<=:[ \\t]*)(\\p{Ll}{3,}(?: \\p{Ll}{3,}){1,4})[ \\t]*(?=\\n|$|\\.(?:\\s|$))|((?=[^\\s'\"]*[\\d!@#$%^&*+])(?=[^\\s'\"]*\\p{L})[\\p{L}\\d][\\p{L}\\d!@#$%^&*+-]{3,30})(?![\\w@=]))", "giu");
    for (const m of text.matchAll(re)) {
      const cueText = m[0].slice(0, m[0].length), gap = m[1] || "";
      const v = m[3] ?? m[4] ?? m[5] ?? m[6] ?? m[7];
      const g6 = m[5], g7 = m[6], g5 = m[7];              // (phrase ending in digits, lower-case phrase after a colon, single word)
      if (v == null) continue;
      const a = m.index + m[0].lastIndexOf(v), head = text.slice(Math.max(0, m.index - 20), m.index + 30);
      if (BAD.test(head)) continue;
      const hasCop = new RegExp(COP, "i").test(m[0].slice(0, m[0].length - v.length).slice(-14)) || m[2];
      const wordOnly = /^\p{L}+$/u.test(v);
      if (!/(^|[\s'"`«“(:=,])$/u.test(text.slice(Math.max(0, a - 1), a))) continue;       // the value starts a token
      if (g5 != null) {                                 // a single word: must look like a password, and need a copula or stand right after the cue
        if (wordOnly || !/\d|[!@#$%^&*+]/.test(v) || !/\p{L}/u.test(v) || /==|^\d+(\.\d+)+$/.test(v)) continue;
        if (!hasCop && gap.trim().length > 12) continue;
        if (/^(https?|www|example|your|none|null|true|false)/i.test(v) || /\.(com|org|net|io)$/i.test(v)) continue;
      }
      if (m[4] != null) {                                 // digits: a short code, not a phone, amount, date or year in running text
        const d = v.replace(/\D/g, "");
        if (d.length < 3 || d.length > 8 || !hasCop && gap.trim().length > 16) continue;
        if (/^[ \t]*(%|percent|seconds?|secs?|ms\b|days?|hours?|mins?|minutes?|weeks?|months?|years?|times|people|users|characters|chars|digits|attempts|am\b|pm\b|[€$£₹]|rs\b|usd|eur|gb|mb|kb|:\d)/i.test(text.slice(a + v.length, a + v.length + 12))) continue;
        if (/[€$£₹]\s*$/.test(text.slice(Math.max(0, a - 3), a))) continue;
      }
      if (g6 != null && /^(is|was|are|it|its|the|a|an|to|of|for|and|or|in|on|at|by|with|then|code|pin|about|only|over|under|than|after|before|until|page|room|line|step|version|chapter|level) /i.test(v)) continue;
      if (/example|sample|dummy|placeholder|changeme|redacted|==/i.test(v)) continue;
      if (m[3] != null && (/^(the|a|an|your|my|our|not|same|none|n\/a|example|changeme|password|secret|redacted|hidden|\*+|x+)$/i.test(v.trim()) || /^\$\{|^<|^YOUR[_-]/.test(v))) continue;
      if (/\b(example|sample|placeholder|dummy|default|e\.g\.|for instance)\b/i.test(text.slice(Math.max(0, m.index - 40), a))) continue;
      if (/\b(expires?|valid|changed|rotated|reset|updated|sent|required|needed|forgot|must|should|will|has|have|long|short|strong|weak|wrong|correct|incorrect|same|different)\s*$/i.test(text.slice(Math.max(0, a - 12), a)) && m[3] == null) continue;
      out.push({ start: a, end: a + v.length, label: m[4] != null ? "SECRET" : "PASS", stated: true });
    }
    // a question about a credential, answered at the start of the next line: "- And the PIN on the account? - It's 4682"
    const QA = new RegExp("(?:" + CUES + ")[^\\n]{0,60}\\?[^\\n]{0,40}\\n(?:[^\\n:]{0,24}:)?[ \\t]*(?:(?:haan|yes|yeah|yep|sure|ok|it'?s|its|it is|it was|es|é|c'est|ist|sí|si)[,: \\t]+){0,2}((?:\\d[ -]?){2,7}\\d[#*]?|(?=\\S*[\\d!@#$%^&*])(?=\\S*\\p{L})[\\p{L}\\d][\\p{L}\\d!@#$%^&*+-]{5,30})(?![\\w@])", "giu");
    for (const m of text.matchAll(QA)) {
      const v = m[1], a = m.index + m[0].lastIndexOf(v);
      if (BAD.test(m[0]) || /example|sample|dummy/i.test(v)) continue;
      out.push({ start: a, end: a + v.length, label: "PASS", stated: true });
    }
    // a database client with the password glued to the flag: mysql -u deploy -pTulip-River-88
    for (const m of text.matchAll(/\b(?:mysql|mysqldump|mysqladmin|mariadb)\b[^\n|;&]*?\s-p([^\s'"-][^\s'"]{3,60})/g)) if (!/^(\$|<|YOUR|xxx|\*)/.test(m[1])) out.push({ start: m.index + m[0].length - m[1].length, end: m.index + m[0].length, label: "PASS", stated: true });
    // command-line credentials: -p'secret', sshpass -p 'secret', --password secret, --otp 304 771
    for (const m of text.matchAll(/(?:\bsshpass\s+-p\s*|\s-p(?=['"])|--(?:password|passwd|pass|secret|token|api[-_]?key|otp|pin)[= ])(?:(['"])([^'"\n]{3,60})\1|(\d{3}[ -]?\d{3})(?!\d)|([^\s'"]{4,60}))/g)) {
      const v = m[2] ?? m[3] ?? m[4], a = m.index + m[0].lastIndexOf(v);
      if (/^(\$|<|YOUR|your-|xxx|\*)/.test(v)) continue;
      out.push({ start: a, end: a + v.length, label: "PASS" });
    }
  }
  // Handles. A handle is masked when something says it names a person's account: an @ or u/ prefix, a login cue, a
  // person-action ("triggered by", "applied as", "streams as"), a git author column, an ssh login. The token must look
  // like a handle (a dot, underscore, hyphen or digit among letters, or inner capitals) unless the cue is explicit.
  {
    const SHAPE = v => /\p{L}/u.test(v) && (/[a-z0-9][._-][a-z0-9]/i.test(v) || /[a-z]\d|\d[a-z]/i.test(v) || /[a-z][A-Z]/.test(v));
    const NOTH = /^(root|admin|administrator|deploy|deployer|ubuntu|ec2-user|git|postgres|mysql|www-data|nobody|guest|test|user|username|example|null|none|true|false|localhost|system|service|bot|noreply|no-reply)$/i;
    const FILEY = /\.(com|org|net|io|dev|app|json|ya?ml|js|ts|py|go|rs|rb|java|md|txt|sh|sql|csv|html?|css|png|jpe?g|pdf|log|env|lock|toml|xml|zip|gz)$/i;
    const add = (a, v) => { v = v.replace(/[.,;:!?)'"`]+$/, ""); if (v.length >= 3 && v.length <= 32 && !NOTH.test(v) && !FILEY.test(v) && !/^\d+$/.test(v)) out.push({ start: a, end: a + v.length, label: "USERNAME" }); };
    // @mentions inside a sentence or list (not a decorator at the start of a line, not a scoped package, not an e-mail)
    for (const m of text.matchAll(/(?<=[ \t(,:]|^)@([A-Za-z][\w.-]{2,30})(?![\w/@])/gm)) {
      const ls = text.lastIndexOf("\n", m.index) + 1;
      if (/^[ \t]*$/.test(text.slice(ls, m.index)) && !/[._-]|\d/.test(m[1]) && /^\s*(\(|\n|$|def |class |public |private |async )/.test(text.slice(m.index + m[0].length, m.index + m[0].length + 10))) continue;
      if (/\b(the|a|an|use|using|with)\s$/i.test(text.slice(Math.max(0, m.index - 6), m.index)) && !/[._-]|\d/.test(m[1])) continue;   // "the @decorator"
      if (/^(param|returns?|media|import|override|property|staticmethod|classmethod|pytest|app|click|everyone|here|channel|all|team|deprecated|see|todo|types?|test|font-face|keyframes|supports|charset|include|mixin|extend|use|forward|throws|example|since|version|author|license|file|module|component|input|output|injectable)$/i.test(m[1])) continue;
      add(m.index, m[0]);
    }
    for (const m of text.matchAll(/(?<![\w/.])u\/[A-Za-z0-9][\w-]{2,24}(?![\w/])/g)) add(m.index, m[0]);
    // explicit cue: the token only has to be a single word; quoted or back-ticked values too
    for (const m of text.matchAll(/\b(?:user ?name|login|log-?in id|user id|handle|gamer ?tag|screen ?name|nick(?:name)?|alias|portal user|account)\b(?: on [\w ]{2,20})?\s*(?:is|was|:|=|as)?\s*[('"`]?([A-Za-z][\w.-]{2,31})/gi)) {
      const v = m[1], a = m.index + m[0].lastIndexOf(v), explicit = /\b(is|was|as)\s*[('"`]?$|[:=]\s*[('"`]?$/i.test(m[0].slice(0, m[0].length - v.length));
      if (SHAPE(v) && (explicit || /[_.]|\d/.test(v))) add(a, v);
    }
    // a person-action before a handle-shaped token
    for (const m of text.matchAll(/\b(?:(?:triggered|run|edited|approved|posted|pushed|committed|created|reported|requested|merged|reviewed|opened|closed|assigned|deployed)(?: via \w+)? by|push by|(?:applied|logged in|signed in|registered|signed up|joined|posts?|posting|streams?(?: it)?|known|commented)(?: [\w ]{0,24}?)? as|goes by|went by|(?:request|message|dm|email|ticket|comment) from(?: user)?|user|approver|author|git_author|reviewer|assignee|committer|created_by|updated_by|requested_by|that'?s|i was)\b["']?(?:\s*[:=]\s*|\s+)[('"`]?@?([A-Za-z][\w.-]{2,31})(?![\w@:])/gi)) {
      if (/[\w/.@-]$/.test(text.slice(Math.max(0, m.index - 1), m.index)) || /:\/\/[^\s]*$/.test(text.slice(Math.max(0, m.index - 40), m.index + 4))) continue;
      const v = m[1].replace(/[.,;:!?)'"`]+$/, ""), a = m.index + m[0].lastIndexOf(m[1]);
      if (!/[a-z0-9][._][a-z0-9]/i.test(v) && !(/[a-z]\d|\d[a-z]/i.test(v) && /[a-z][A-Z]|-/.test(v)) && !/[a-z]-[a-z]/i.test(v) && !/^[a-z]+[A-Z][a-z]+[A-Z]/.test(v)) continue;
      if (/^\s*[(=]/.test(text.slice(a + v.length, a + v.length + 2)) && !/^\s*\(/.test(text.slice(a + v.length, a + v.length + 2))) continue;
      if (/_(id|ids|at|by|name|count|key|type|url|path|time|date|size|ms|host|port|user|version|status|code|token|secret|email|phone)$/i.test(v) || /^(is|has|get|set|max|min|num|api|db|http|user|created|updated|deleted)_/i.test(v)) continue;
      add(a, v);
    }
    // Slack: the mention syntax of an export ("<@U02AARON_GOLDBERG>") is always a person's handle; a bare Slack user ID
    // ("U02MIKE_TORRES") is one when the line also holds an e-mail address or says Slack
    for (const m of text.matchAll(/<@([UW][A-Z0-9_]{2,40})(?:\|[^>\n]{1,40})?>/g)) out.push({ start: m.index + 2, end: m.index + 2 + m[1].length, label: "USERNAME" });
    for (const m of text.matchAll(/(?<![\w@<])U\d{1,3}[A-Z][A-Z0-9_]{2,30}(?![\w@])/g)) {
      const ls = text.lastIndexOf("\n", m.index) + 1, le = text.indexOf("\n", m.index) < 0 ? text.length : text.indexOf("\n", m.index), line = text.slice(ls, le);
      if (/@[\w-]+\.[a-z]{2,}/i.test(line) || /\bslack\b/i.test(line)) out.push({ start: m.index, end: m.index + m[0].length, label: "USERNAME" });
    }
    // "X on Telegram": a handle named with its platform after it
    for (const m of text.matchAll(/(?<![\w@.-])@?([A-Za-z][\w.-]{2,31}) on (?:Telegram|Discord|Instagram|Insta|Twitter|Signal|WhatsApp|Slack|GitHub|GitLab|Snapchat|TikTok|Reddit|Steam|Twitch|Skype|Mastodon|Bluesky|LinkedIn)\b/g)) if (SHAPE(m[1])) add(m.index + m[0].indexOf(m[1]), m[1]);
    // an ssh login; a git log author column before the author's e-mail
    for (const m of text.matchAll(/\bssh\s+(?:-\w+\s+\S+\s+)*([a-z][\w.-]{1,30})@[\w.-]+/g)) add(m.index + m[0].indexOf(m[1] + "@"), m[1]);
    for (const m of text.matchAll(/^[0-9a-f]{7,40} ([A-Za-z][\w.-]{2,30}) <[^>\s]+@[^>\s]+>/gm)) add(m.index + m[0].indexOf(m[1]), m[1]);
  }
  // Identifiers of a person named by their cue, in several languages: "passport on file: M70445518", "badge 7741193-2",
  // "DNI nuevo es el 53928174-L", "matrícula 4471 KLM", "CPF, passei 529.982.247-25", "employee number ... is 118204".
  // The cue says whose number it is; the value is a code with digits, cut at the first sentence punctuation.
  {
    const IDCUE = "(?:passports?(?: on file)?(?: (?:no\\.?|number))?|badge|dni|nie|nif|cpf|\\brg\\b|cart[ãa]o do sus|matr[íi]cula|number ?plate|licen[cs]e plate|\\brego\\b|vehicle reg(?:istration)?|\\breg(?:istration)? (?:plate|mark)|serial(?: (?:no\\.?|number))?|imei|employee (?:number|no\\.?|id|code)|staff (?:number|no\\.?|id)|payroll (?:number|no\\.?)|student (?:number|no\\.?|id)|patient (?:reference|ref\\.?|number|no\\.?|id)|member(?:ship)? (?:number|no\\.?|id)|customer number|num[ée]ro client|kundennummer|policy (?:number|no\\.?)|\\bgmc\\b|nhs(?: number| no\\.?)?|national insurance(?: number| no\\.?)?|personnummer|driving licen[cs]e(?: (?:no\\.?|number))?|licen[cs]e (?:no\\.?|number)|tax id|\\btin\\b|aadhaar|frequent flyer(?: (?:no\\.?|number))?|loyalty (?:number|no\\.?))";
    const re = new RegExp("(?<![\\p{L}])" + IDCUE + "(?![\\p{L}])([^.\\n;!?]{0,34}?)(?:\\b(?:is|was|es|est|é)\\b|:|#|\\(|,)?[ \\t]*(?:(?:el|la|le|o|a|passei)[ \\t]+)?([A-Z0-9](?:[A-Za-z0-9]|[ .\\/-](?=[A-Za-z0-9])){3,24})(?![A-Za-z0-9])", "giu");
    for (const m of text.matchAll(re)) {
      let v = m[2]; const a = m.index + m[0].lastIndexOf(v);
      // keep leading groups that look like parts of a code; stop before a lower-case word
      const cut = v.search(/[ .\/-][a-z]{2,}/); if (cut > 0) v = v.slice(0, cut);
      const digits = (v.match(/\d/g) || []).length;
      if (digits < 4 && !(digits >= 2 && /[A-Z]{2}/.test(v) && v.length >= 5)) continue;
      if (/^(19|20)\d{2}$/.test(v) || /^\d{1,2}[\/.-]\d{1,2}[\/.-]\d{2,4}$/.test(v) || /[a-z]{4,}/.test(v)) continue;
      if (/\b(expires?|expiry|valid|issued|renew\w*|runs out|since|until|dated?|on|from)\s*$/i.test(m[1] || "")) continue;
      if (/X{3}|\*{2}|x{4}/.test(v)) continue;                                  // a masked number
      out.push({ start: a, end: a + v.length, label: "ID", cued: true, weak: true });
    }
    // account numbers in a list after "account(s)": "legacy accounts (8842-4471, 8842-4481 and 8842-4482)"
    for (const m of text.matchAll(/\baccounts?\b[^.\n;:]{0,30}?[(:]?\s*((?:\d{3,6}-\d{3,6}|\d{8,12})(?:\s*(?:,|and|&|or|\/)\s*(?:\d{3,6}-\d{3,6}|\d{8,12}))*)/gi)) {
      const base = m.index + m[0].lastIndexOf(m[1]);
      for (const x of m[1].matchAll(/\d{3,6}-\d{3,6}|\d{8,12}/g)) out.push({ start: base + x.index, end: base + x.index + x[0].length, label: "ID", cued: true, weak: true });
    }
    // credentials in a URL: the password runs to the LAST "@" before the host ("mysql://svc:Mysql@Pune#2026@db:3306/x");
    // a bare key before "@" (a DSN: "https://<key>@o4504.ingest.example/45") is a secret
    for (const m of text.matchAll(/\b[a-z][a-z0-9+.-]{1,20}:\/\/([^\s:@\/"']*):([^\s"'\/]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*(?::\d+)?)(?=[\/"'\s?]|$)/g)) {
      const a = m.index + m[0].indexOf(":" + m[2] + "@", m[0].indexOf("//") + 2 + m[1].length) + 1;
      if (m[2].length >= 3 && !/^(\$|<|\*+$|x+$|password$|pass$|changeme$)/i.test(m[2])) out.push({ start: a, end: a + m[2].length, label: "SECRET", stated: true, weak: true });
    }
    for (const m of text.matchAll(/\bhttps?:\/\/([0-9a-f]{16,64})@[A-Za-z0-9.-]+/gi)) out.push({ start: m.index + m[0].indexOf(m[1]), end: m.index + m[0].indexOf(m[1]) + m[1].length, label: "SECRET" });
    // a delivery address after its cue: "Deliver to: Neha Kulkarni, B-702, Sai Krupa Heights, Baner Road, Pune 411045"
    for (const m of text.matchAll(/\b(?:deliver(?:ed|y)? to|ship(?:ping)? to|send (?:it )?to|address|addr\.?|bill(?:ing)? to|mail(?:ing)? address)\s*:\s*([^\n<]{8,160}?)(?=\s*(?:<|\n|$))/gi)) {
      let v = m[1], a = m.index + m[0].lastIndexOf(v);
      // the value ends with its sentence: "..., Kolkata 700016. Total due: ..." (not at "St." or "No. 5")
      const stop = /(?<![\p{L}](?:St|Rd|No|Nr|Dr|Ave|Apt|Bd|Mr|Mrs|Ms|Av|Avda|Blvd|Ln|Ct|Fl))[.!?;]\s+(?=\p{Lu})/u.exec(v);
      if (stop) v = v.slice(0, stop.index);
      const nmLead = /^(?:(?:Mr|Mrs|Ms|Dr)\.? )?\p{Lu}[\p{L}'’-]+(?: \p{Lu}[\p{L}'’-]+){0,3}, (?=[\p{Lu}\d#])/u.exec(v);
      if (nmLead && /\d/.test(v.slice(nmLead[0].length))) { a += nmLead[0].length; v = v.slice(nmLead[0].length); }
      if (/\d/.test(v) && /\b(road|rd|street|st|lane|ln|marg|nagar|block|cross|main|heights|apartments?|apt|flat|floor|sector|avenue|ave|drive|dr|way|court|place|square|plaza|colony|layout|boulevard|blvd|calle|rue|straße|strasse|rua|via)\b|\b\d{5,6}\b|\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b/i.test(v))
        out.push({ start: a, end: a + v.length, label: "ADDRESS", cued: true, weak: true });
    }
    // an order number identifies a customer's order (owner policy, 2026-11-17): "Order OD-90311", "order_id": "A-5521",
    // "/v1/orders/OD-90311"
    for (const m of text.matchAll(/\border\b(?:\s*(?:id|no\.?|number|ref(?:erence)?|#))?["']?\s*[:=#]?\s*["']?#?([A-Z0-9][A-Z0-9_/-]{2,30}\d[A-Z0-9-]*)(?![\w-])/gi)) {
      const v = m[1]; if (!/\d{3}/.test(v) || /^(19|20)\d{2}$/.test(v)) continue;
      out.push({ start: m.index + m[0].lastIndexOf(v), end: m.index + m[0].lastIndexOf(v) + v.length, label: "ID", cued: true });
    }
    for (const m of text.matchAll(/\/orders?\/([A-Za-z0-9][A-Za-z0-9_-]{3,40})(?=[\/?#\s"']|$)/g)) if (/\d/.test(m[1]))
      out.push({ start: m.index + m[0].length - m[1].length, end: m.index + m[0].length, label: "ID", cued: true });
    // a phone number named by its cue, in formats the network does not know: "mi número nuevo: 611 555 204", "(11) 95555-0147"
    for (const m of text.matchAll(/(?<![\p{L}])(?:n[úu]mero(?: nuevo| novo)?|m[óo]vil|tel[ée]fono|telefone|celular|portable|handy|whatsapp|zap)(?![\p{L}])[^.\n;!?]{0,28}?[: ][ \t]*(\(?\+?\d[\d ()-]{7,16}\d)(?![\w-])/giu)) {
      const v = m[1], d = v.replace(/\D/g, "").length;
      if (d >= 9 && d <= 13) out.push({ start: m.index + m[0].lastIndexOf(v), end: m.index + m[0].lastIndexOf(v) + v.length, label: "TEL", cued: true, weak: true });
    }
    for (const m of text.matchAll(/(?<![\w(])\(\d{2}\) ?9?\d{4}-\d{4}(?![\w-])/g)) out.push({ start: m.index, end: m.index + m[0].length, label: "TEL", cued: true, weak: true });
    // a postal address written street-first with a post code, as most of Europe and Latin America write it
    const ST = "(?:(?:\\d{1,4}(?:bis|ter)?,? )?(?:Calle|C\\/|Avenida|Avda\\.?|Paseo|Plaza|Carrer|Rua|Travessa|Praça|Alameda|Rue|Avenue|Boulevard|Bd\\.?|Chemin|Allée|Impasse|Place|Via|Viale|Piazza|Corso|ul\\.|al\\.|os\\.)[ \\u00a0]|\\p{Lu}[\\p{L}-]*(?:straße|strasse|str\\.|gasse|weg|platz|allee|laan|straat|plein|kade|gracht|singel|vej|gade|gatan|vägen)[ \\u00a0]\\d)";
    for (const m of text.matchAll(new RegExp("(?<![\\p{L}])" + ST + "[^\\n;!?]{2,90}?(?<![\\d-])(?:\\d{2}-\\d{3}|\\d{5}(?:-\\d{3})?|\\d{4} ?[A-Z]{2})(?![\\d-])(?:[ \\u00a0]\\p{Lu}[\\p{L}'’-]+(?:[ \\u00a0](?:de |del |am |sur |sous )?\\p{Lu}[\\p{L}'’-]+){0,2})?", "gu"))) {
      if (/[.]\s+\p{Lu}\p{Ll}+ \p{Ll}/u.test(m[0].slice(0, -8)) && m[0].length > 70) continue;       // ran over a sentence boundary
      out.push({ start: m.index, end: m.index + m[0].length, label: "ADDRESS", cued: true });
    }
  }
  // a handle stated in a sentence: "add me on discord: X", "insta pe X", "username is X", "Login ID X"
  const HND = /\b(?:discord|insta(?:gram)?|twitter|telegram|snap(?:chat)?|github|gitlab|skype|steam|xbox|psn|reddit|tiktok|username|user name|login id|user id|handle|gamertag)\b\s*(?:is|:|=|-|pe|par|id)?\s*:?\s*@?([A-Za-z][\w.#-]{2,31})/gi;
  for (const m of text.matchAll(HND)) {
    const v = m[1].replace(/[.,;!?)]+$/, ""), a = m.index + m[0].lastIndexOf(m[1]);
    if ((/[\d_.#-]/.test(v) || /[a-z][A-Z]/.test(v)) && !/\.(com|org|net|io)$/i.test(v)) out.push({ start: a, end: a + v.length, label: "USERNAME" });
  }
  // a card expiry said in words after its cue: "exp eleven twenty-nine"
  const NW = "(?:zero|oh|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty)";
  const EXPW = new RegExp(`\\b(?:exp(?:iry|ires)?|valid (?:thru|till|until))\\.?\\s+((?:${NW}[ -]){1,4}${NW})\\b`, "gi");
  for (const m of text.matchAll(EXPW)) { const a = m.index + m[0].length - m[1].length; out.push({ start: a, end: a + m[1].length, label: "CARD_EXPIRY" }); }
  // dates written in words: "9th of July, two thousand and one", "nineteenth March, nineteen eighty-eight"
  const MON = "(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)";
  const ORDW = "(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|twenty[- ](first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)|thirtieth|thirty[- ]first)";
  const UNITS = "(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)";
  const YEARW = `((nineteen|twenty)[- ](hundred[- ](and[- ])?)?${UNITS}([- ]${UNITS})?|two thousand([- ]and)?([- ]${UNITS})?([- ]${UNITS})?|(19|20)\\d\\d|(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[- ]${UNITS}|'?\\d\\d)`;
  const re = new RegExp(`\\b(${ORDW}|\\d{1,2}(st|nd|rd|th)?)( of)? ${MON},? ${YEARW}\\b`, "gi");
  let m;
  while ((m = re.exec(text))) {
    const a = m.index, b = a + m[0].length, before = text.slice(Math.max(0, a - 30), a).toLowerCase();
    out.push({ start: a, end: b, label: /(born|birth|dob|b'day|birthday)\W*(on\W*)?$/.test(before) ? "BOD" : "DATE" });
  }
  return out;
}

// ---------- structured content ----------
export const TOKEN_PREFIX = /^(gh[pousr]_|github_pat_|xox[abprs]-|sk-|sk_live_|sk_test_|rk_live_|glpat-|gldt-|npm_|pypi-|hf_|AKIA|ASIA|AIza|ya29\.|dop_v1_|shpat_|shpss_|SG\.|xapp-|eyJ)/;
const SETTINGS_COOKIES = /^_?(theme|lang|language|locale|tz|timezone|consent|cookie_?consent|currency|mode|dark_?mode|font|region|country|display|layout|sidebar|view|sort|density|accessibility)$/i;
const SENSITIVE_COL = [[/^(name|full_?name|fullname|display_?name)$/i, "GIVENNAME"], [/^(first|first_?name|fname|given|given_?name|forename)$/i, "GIVENNAME"],
  [/^(last|last_?name|lname|surname|family_?name)$/i, "LASTNAME"], [/^(dob|date_?of_?birth|birth_?date|birthdate|birthday)$/i, "BOD"],
  [/^(pan|aadhaar\w*|aadhar\w*|ssn|passport\w*|national_?id|voter_?id|tax_?id)$/i, "ID"], [/^(phone|mobile|msisdn|tel|phone_?(no|number))$/i, "TEL"],
  [/^(e_?mail|email_?address)$/i, "EMAIL"], [/^(mrn|patient_?id)$/i, "ID"], [/^(address|addr|street)$/i, "ADDRESS"]];
const ID_COL = /^(id|emp_?id|employee_?id|user_?id|uid|customer_?id|member_?id|student_?id)$/i;
function splitSql(s) { const out = []; let cur = "", q = null, start = 0; for (let i = 0; i < s.length; i++) { const ch = s[i]; if (q) { cur += ch; if (ch === q) q = null; } else if (ch === "'" || ch === '"') { q = ch; cur += ch; } else if (ch === ",") { out.push({ v: cur, at: start }); cur = ""; start = i + 1; } else cur += ch; } out.push({ v: cur, at: start }); return out; }
export function structuredSpans(text, spans) {
  const out = [];
  // SQL: map VALUES positions to the column list; a bare leading numeric id of a row about a person is that row's key
  const ins = /INSERT\s+INTO\s+[\w."`]+\s*(\(([^)]*)\))?\s*VALUES\s*\(([^)]*)\)/gi;
  let m;
  while ((m = ins.exec(text))) {
    const cols = m[2] ? m[2].split(",").map(x => x.trim().replace(/[`"]/g, "")) : null;
    const vbase = m.index + m[0].lastIndexOf(m[3]);
    const vals = splitSql(m[3]);
    const rowHasPerson = vals.some(v => spans.some(s => /NAME$/.test(s.label) && s.start >= vbase + v.at && s.end <= vbase + v.at + v.v.length + 1));
    vals.forEach((v, k) => {
      const raw = v.v, lead = raw.length - raw.trimStart().length, t = raw.trim();
      let a = vbase + v.at + lead, b = a + t.length;
      if (/^['"].*['"]$/.test(t)) { a++; b--; }
      const val = text.slice(a, b);
      if (!val || /^(null|n\/a|none|)$/i.test(val)) return;
      const col = cols ? cols[k] : null;
      if (/[X*•#]{3,}/.test(val)) return;                                 // partly masked: linked to its full value below
      if (col) { const kl = keyLabel(col);
                 if (kl && valueFits(kl.lab, val, false)) { const [label, kind] = kl.lab.split(":"); out.push({ start: a, end: b, label, kind, fromColumn: col }); return; }
                 for (const [re, lab] of SENSITIVE_COL) if (re.test(col)) { out.push({ start: a, end: b, label: lab, fromColumn: col }); return; }
                 if (ID_COL.test(col) && rowHasPerson) out.push({ start: a, end: b, label: "ID", kind: "EMPLOYEE_ID", quote: !/^['"]/.test(t) }); }
      else if (k === 0 && /^\d{1,10}$/.test(val) && rowHasPerson) out.push({ start: a, end: b, label: "ID", kind: "EMPLOYEE_ID", quote: true });
    });
  }
  // CSV: a header row names the columns; values under a sensitive header are that kind of data
  const lines = text.split("\n");
  let off = 0;
  for (let li = 0; li < lines.length; li++) {
    const hdr = lines[li];
    const sepM = /^[A-Za-z_][\w ]*([,;\t|])[A-Za-z_][\w ]*(\1[A-Za-z_][\w ]*){1,}$/.exec(hdr.trim());
    if (sepM && li + 1 < lines.length) {
      const SEP = sepM[1], cols = hdr.split(SEP).map(x => x.trim());
      let o2 = off + hdr.length + 1, lj = li + 1;
      for (; lj < lines.length; lj++) {
        const row = lines[lj], vals = SEP === "," ? splitSql(row) : (() => { let at = 0; return row.split(SEP).map(v => { const o = { v, at }; at += v.length + 1; return o; }); })();
        if (!row.trim() || vals.length !== cols.length) break;
        vals.forEach((v, k) => {
          const t = v.v.trim(); if (!t) return;
          let a = o2 + v.at + (v.v.length - v.v.trimStart().length), b = a + t.length;
          if (/^".*"$/.test(t)) { a++; b--; }
          const col = cols[k];
          { const kl = keyLabel(col); const val = text.slice(a, b);
            if (kl && valueFits(kl.lab, val, false)) { const [label, kind] = kl.lab.split(":"); out.push({ start: a, end: b, label, kind, fromColumn: col }); return; } }
          for (const [re, lab] of SENSITIVE_COL) if (re.test(col)) { out.push({ start: a, end: b, label: lab, fromColumn: col }); return; }
          if (/^(member|customer|patient|employee|holder|insured|beneficiary|contact_name|applicant)(_?name)?$/i.test(col) && /\p{L}/u.test(t)) out.push({ start: a, end: b, label: "GIVENNAME", fromColumn: col });
          else if (/^(policy|policy_?(no|number)|member_?id|customer_?id|patient_?id|account|account_?(no|number)|contact|contact_?(no|number))$/i.test(col) && /\d/.test(t))
            out.push({ start: a, end: b, label: /contact/i.test(col) ? "TEL" : "ID", fromColumn: col });
        });
        o2 += row.length + 1;
      }
      // the rows of this block are values, not further headers: continue after the block (linear, not quadratic)
      if (lj > li + 1) { for (let k = li; k < lj; k++) off += lines[k].length + 1; li = lj - 1; continue; }
    }
    off += hdr.length + 1;
  }
  // "<sensitive>_last4": "5731" — the visible tail of an identifier is masked, the key is kept
  const L4 = /"?\b(\w*(?:aadhaar|aadhar|ssn|card|pan|account|acct|phone|mobile|passport|iban)\w*_(?:last_?4|last_?four|suffix|tail|masked))"?\s*[:=]\s*"?([\w*-]{3,})"?/gi;
  while ((m = L4.exec(text))) { const a = m.index + m[0].lastIndexOf(m[2]); out.push({ start: a, end: a + m[2].length, label: "ID" }); }
  // cookies: keep the cookie name and attributes; settings cookies carry no identity
  for (const s of spans) {
    if (s.label !== "COOKIE") continue;
    const t = text.slice(s.start, s.end), eq = t.indexOf("=");
    if (eq > 0 && /^[\w.\-]+$/.test(t.slice(0, eq))) {
      if (SETTINGS_COOKIES.test(t.slice(0, eq))) { s.drop = true; continue; }
      s.start += eq + 1;
    }
    const semi = text.slice(s.start, s.end).indexOf(";");
    if (semi >= 0) s.end = s.start + semi;
    s.text = text.slice(s.start, s.end);
  }
  // capability tokens in share / invite / reset / download paths
  const url = /https?:\/\/[^\s"'<>]+/g;
  while ((m = url.exec(text))) {
    const u = m[0], base = m.index, path = u.replace(/^https?:\/\/[^\/]+/, "").split(/[?#]/)[0];
    const segs = path.split("/");
    let off = u.length - u.replace(/^https?:\/\/[^\/]+/, "").length, share = false;
    for (const sg of segs) {
      if (share && sg.length >= 8 && /\d/.test(sg) && /[A-Za-z]/.test(sg) && /^[A-Za-z0-9_-]+$/.test(sg) && !/^\d+$/.test(sg))
        out.push({ start: base + off, end: base + off + sg.length, label: "SECRET" });
      if (/^(s|share|shared|sharing|invite|invitation|i|reset|d|dl|download|downloads|file|files|f|join|link|l|r|v|t|token|magic|verify)$/i.test(sg)) share = true;
      off += sg.length + 1;
    }
  }
  // webhook URLs: every segment after the provider's fixed route is the credential
  const HOOKS = [/hooks\.slack\.com\/(?:services|workflows|triggers)\/([A-Za-z0-9\/_-]+)/g, /discord(?:app)?\.com\/api\/webhooks\/([\w\/-]+)/g,
                 /\.webhook\.office\.com\/webhookb2\/([^\s"'<>]+)/g, /outlook\.office\.com\/webhook\/([^\s"'<>]+)/g,
                 /hooks\.zapier\.com\/hooks\/catch\/([\w\/]+)/g, /chat\.googleapis\.com\/v1\/spaces\/[^\s"'<>]*?[?&]key=([^\s"'<>&]+)/g];
  for (const H of HOOKS) { while ((m = H.exec(text))) { const v = m[1].replace(/[.,;)]+$/, ""), a = m.index + m[0].length - m[1].length; out.push({ start: a, end: a + v.length, label: "SECRET" }); } }
  // recovery / backup codes: groups of 4-8 characters after the cue
  const RC = /\b(?:recovery|backup|scratch|one-time|2fa|mfa)\s+codes?\s*:?\s*((?:[A-Za-z0-9]{4,8}(?:-[A-Za-z0-9]{4,8})?[\s,]+){1,11}[A-Za-z0-9]{4,8}(?:-[A-Za-z0-9]{4,8})?)/gi;
  while ((m = RC.exec(text))) { const a = m.index + m[0].length - m[1].length; out.push({ start: a, end: a + m[1].length, label: "SECRET" }); }
  // URL userinfo runs to the LAST "@" before the host: "redis://:pass@word@host" (a password may contain "@")
  const UI = /\b([a-z][a-z0-9+.-]{1,15}):\/\/([^\s\/?#"']*@[^\s\/?#"']*)@([A-Za-z0-9.-]+(?::\d+)?)(?=[\/?#\s"']|$)/g;
  while ((m = UI.exec(text))) {
    const ui = m[2], base = m.index + m[1].length + 3, colon = ui.indexOf(":");
    const pa = colon >= 0 ? base + colon + 1 : base, pe = base + ui.length;
    out.push({ start: pa, end: pe, label: "PASS" });
    if (colon > 0 && !/^(svc|sa|app|api|service|admin|root|postgres|__token__|user|default)/i.test(ui.slice(0, colon))) out.push({ start: base, end: base + colon, label: "USERNAME" });
  }
  // {"name": X, "value": Y}: Y is a credential when X is session-like; X is a key and is never masked
  const NV = /"name"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*"([^"]*)"/g;
  while ((m = NV.exec(text))) if (/(sess|sid|token|auth|csrf|xsrf|jwt|remember|login|secret|pass|key|cred)/i.test(m[1]) && m[2]) {
    const a = m.index + m[0].length - m[2].length - 1; out.push({ start: a, end: a + m[2].length, label: "SECRET" });
  }
  // a token spelled out with spaces: "g h p _ 2 j b o ..." -> collapse and check the prefix
  const SPC = /(?<!\S)((?:[A-Za-z0-9_\-] ){5,}[A-Za-z0-9_\-])(?!\S)/g;
  while ((m = SPC.exec(text))) if (TOKEN_PREFIX.test(m[1].replace(/ /g, ""))) out.push({ start: m.index, end: m.index + m[1].length, label: "SECRET" });
  // partly redacted tokens and "ended in o1sq" tails next to a credential mention
  const PT = /\b(?:gh[pousr]_|github_pat_|xox[abprs]-|sk-|sk_live_|rk_live_|glpat-|npm_|pypi-|hf_|AKIA|AIza)[*•x]{3,}[A-Za-z0-9]{2,8}\b/g;
  while ((m = PT.exec(text))) out.push({ start: m.index, end: m.index + m[0].length, label: "SECRET" });
  const TAIL = /\b(?:ended|ending|ends|ending with)\s+(?:in|with)?\s*([A-Za-z0-9]{3,6})\b/gi;
  while ((m = TAIL.exec(text))) {
    const ctx = text.slice(Math.max(0, m.index - 80), m.index).toLowerCase(), a = m.index + m[0].length - m[1].length;
    if (/(key|token|secret|password|passphrase|credential)/.test(ctx) && /[a-z]/i.test(m[1]) && /\d/.test(m[1])) out.push({ start: a, end: a + m[1].length, label: "SECRET" });
  }
  // partly masked copies of a value found elsewhere ("XXXX XXXX 5814", "a****@example.org") get that value's tag
  const pm = /(?:[X*•#x]{2,}[\s-]?){1,4}\d{3,4}\b|\b[\w.]?[*•]{3,}[\w.]*@[\w.-]+\.\w+/g;
  while ((m = pm.exec(text))) {
    const a = m.index, b = a + m[0].length, vis = m[0].replace(/[^\dA-Za-z@.]/g, "");
    for (const s of spans) {
      if (s.drop) continue;
      const v = (s.value || text.slice(s.start, s.end));
      if (/^\d{3,4}$/.test(vis.replace(/\D/g, "")) && /^[\d\s-]{8,}$/.test(v) && v.replace(/\D/g, "").endsWith(vis.replace(/\D/g, "")) && !/@/.test(vis)) { out.push({ start: a, end: b, label: s.label, kind: s.kind, value: v }); break; }
      if (/@/.test(vis) && s.label === "EMAIL") { const [l1, d1] = v.toLowerCase().split("@"), [l2, d2] = m[0].toLowerCase().split("@");
        if (d1 === d2 && (!l2[0] || /[*•]/.test(l2[0]) || l1[0] === l2[0])) { out.push({ start: a, end: b, label: "EMAIL", value: v }); break; } }
    }
  }
  return out;
}

// ---------- values under explicit keys, in any carrier syntax ----------
// One table from key names to labels; one extractor per carrier (key=value, "key": "value", HTML attributes and
// table cells, {"field": k, "value": v}, "Field: k / Value entered: v", "k - v" lines, data-field attributes).
const KEYMAP = [
  [/^(user|login|screen|nick|account)(name|id)?$|^(username|userid|handle|login|nick|nickname|loginid)$/, "USERNAME"],
  [/^(full|first|last|given|middle|sur|family|customer|contact|display|member|patient|holder|applicant|employee|student|guardian|nominee|recipient|sender|owner|account ?holder|legal)?name$|^(fname|lname|forename|surname|givenname)$/, "GIVENNAME"],
  [/^(pass(word|wd|code|phrase)?|pwd|pw|passwd)$/, "PASS"],
  [/^(secret|security|memorable)(answer|word)$/, "SECRET"],
  [/^(api|access|secret|auth|client|private|bearer|refresh|session)?(key|token|secret)$|^(apikey|accesskey|clientsecret|authtoken|privatekey|apitoken)$/, "SECRET"],
  // any key that ends in a credential word (JWT_SIGNING_SECRET, dbPassword, x-csrf-token); pagination tokens are not secrets
  [/^(?!.*(next|page|continuation|cursor|max|num|count|public|publishable)).{2,30}(secret|token|passwd|password|passphrase|apikey|privatekey|signingkey|encryptionkey|secretkey|accesskey)$/, "SECRET"],
  [/^(csrf|xsrf|otp|cvv|cvc)(token|code)?$/, "SECRET"],
  [/^passport(no|num|number|id)?$/, "ID:PASSPORT"],
  [/^(aadhaar|aadhar|uidai)(no|num|number|id)?$/, "ID:AADHAAR"],
  [/^pan(no|num|number|card)?$/, "ID:PAN"],
  [/^(ssn|socialsecurity(no|number)?|nationalid|nationalinsurance(no|number)?|taxid)$/, "ID:NATIONAL_ID"],
  [/^(card|creditcard|debitcard|cc)(no|num|number)?$/, "CARD"],
  [/^(iban|bankaccount|account|acct|accountno|accountnumber|bankaccountnumber|bankaccountno)$/, "ID:BANK_ACCOUNT"],
  [/^((shipping|billing|home|postal|mailing|street|residential|delivery|permanent|current)?address|addr)$/, "ADDRESS"],
  [/^(dob|dateofbirth|birthdate|birthday|born)$/, "BOD"],
  [/^((phone|mobile|cell|tel|telephone|contact|whatsapp)(no|num|number)?|msisdn)$/, "TEL"],
  [/^(e?mail|emailaddress|emailid)$/, "EMAIL"],
  [/^(ip|ipaddress|clientip|remoteaddr|remoteip|sourceip|userip)$/, "IP"],
];
const EMPTYV = /^(null|none|nil|n\/a|na|-+|\?+|x+|\*+|true|false|yes|no|unknown|redacted|todo|tbd|example|placeholder|string|value|<[^>]*>|\$\{[^}]*\}|\{\{[^}]*\}\}|%\([^)]*\)s|\[[^\]]*\])$/i;
function keyLabel(k) {
  const n = k.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase().replace(/[^a-z]/g, "");
  for (const [re, lab] of KEYMAP) if (re.test(n)) return { lab, bare: n === "name" };
  return null;
}
function valueFits(lab, v, bare) {
  if (!v || EMPTYV.test(v) || v.length > 160) return false;
  if (lab === "GIVENNAME") {
    const ws = v.split(/\s+/);
    if (!/^[\p{L}\p{M} .'’-]+$/u.test(v) || ws.length > 5 || ws.some(w => w.length > 24)) return false;
    return !bare || ws.length >= 2 || /^\p{Lu}/u.test(v);                 // a bare "name:" key needs a name-like value
  }
  if (lab === "USERNAME") return /^[\w.@-]{2,40}$/.test(v) && /[a-z]/i.test(v);
  if (lab === "TEL") return /^[+()\d][\d ().+-]{6,22}$/.test(v) || /^[^\x00-\x7f +()-]{8,}/.test(v);
  if (lab === "EMAIL") return /@/.test(v);
  if (lab === "BOD") return /\d/.test(v) && v.length <= 40;
  if (lab === "IP") return /^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-f:]{6,39}$/i.test(v) && !/^(10\.|192\.168\.|127\.)/.test(v);
  if (lab === "CARD") return /^[\d -]{12,23}$/.test(v);
  if (lab.startsWith("ID")) return /\d/.test(v) && /^[\w ./-]{4,40}$/.test(v);
  if (lab === "ADDRESS") return /\d/.test(v) && /\p{L}{3}/u.test(v) && v.length >= 8;
  if (lab === "PASS" || lab === "SECRET") return v.length >= 4 && !/^\s|\s$/.test(v);
  return true;
}
export function keyValueSpans(text) {
  const out = [], seen = new Set();
  const add = (k, v, vStart) => {
    const kl = keyLabel(k); if (!kl) return;
    let val = v, a = vStart;
    const lead = /^\s+/.exec(val); if (lead) { a += lead[0].length; val = val.slice(lead[0].length); }
    // the value ends where the next field or sentence starts; a secret is one token unless it is quoted
    const q = /^(["'`])(.*?)\1/.exec(val);
    if (q) { a += 1; val = q[2]; }
    else {
      const cut = val.search(/\s{2,}|\s\|\s|\.\s+\p{Lu}|;\s/u); if (cut > 0) val = val.slice(0, cut);
      if (/^(PASS|SECRET)$/.test(kl.lab.split(":")[0])) val = val.split(/\s/)[0];
    }
    val = val.replace(/[\s.,;]+$/, "");
    if (!valueFits(kl.lab, val, kl.bare) || seen.has(a)) return;
    seen.add(a);
    const [label, kind] = kl.lab.split(":");
    out.push({ start: a, end: a + val.length, label, kind, fromColumn: k });
  };
  let m;
  const KQ = /(?<![\w.-])["']?([A-Za-z][\w -]{1,30}?)["']?\s*[:=]\s*(["'])([^"'\n]{1,160})\2/g;                 // key: "v"   "key": "v"   key='v'
  while ((m = KQ.exec(text))) add(m[1], m[3], m.index + m[0].length - m[3].length - 1);
  const KU = /(?<![\w.-])([A-Za-z][\w-]{1,30})[:=]([^\s,;&"'<>{}()\[\]]{2,120})/g;                               // key=v   key:v (no space)
  while ((m = KU.exec(text))) add(m[1], m[2], m.index + m[0].length - m[2].length);
  const KL = /^[ \t>*-]*([A-Za-z][A-Za-z ]{1,30}?)\s*(?::|-|\*\s\.{2,})\s+([^\n]{2,160})$/gm;                    // Key: value   Key - value   (whole line)
  while ((m = KL.exec(text))) add(m[1], m[2], m.index + m[0].length - m[2].length);
  const HA = /name=["']([\w.-]+)["'][^<>]{0,40}?value=["']([^"']*)["']/g;                                            // <input name="k" value="v">
  while ((m = HA.exec(text))) add(m[1], m[2], m.index + m[0].length - m[2].length - 1);
  const HT = /<(td|th|strong|b|label|dt)[^>]*>\s*([^<:]{2,40}?):?\s*<\/\1>\s*(?:<(?:td|dd|span)[^>]*>)?\s*([^<\n]{1,160})/g;  // <td>Key</td><td>v
  while ((m = HT.exec(text))) add(m[2], m[3], m.index + m[0].length - m[3].length);
  const DF = /data-field=["']([\w.-]+)["'][^<>]*>([^<\n]{1,160})</g;
  while ((m = DF.exec(text))) add(m[1], m[2], m.index + m[0].length - m[2].length - 1);
  const FV = /"(?:field|name|key|label)"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*"([^"]*)"/g;                          // {"field": k, "value": v}
  while ((m = FV.exec(text))) add(m[1], m[2], m.index + m[0].length - m[2].length - 1);
  const F2 = /\bField:\s*([^\n]{2,40})\n\s*Value(?: entered)?:\s*([^\n]{1,160})/gi;
  while ((m = F2.exec(text))) add(m[1], m[2], m.index + m[0].length - m[2].length);
  return out;
}

// ---------- scripts: transliterate Devanagari / Tamil, and fold Latin spellings, to a consonant skeleton ----------
const DEV = { "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n", "च": "c", "छ": "c", "ज": "j", "झ": "j", "ञ": "n", "ट": "t", "ठ": "t", "ड": "d",
  "ढ": "d", "ण": "n", "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n", "प": "p", "फ": "f", "ब": "b", "भ": "b", "म": "m", "य": "y", "र": "r",
  "ल": "l", "व": "v", "श": "s", "ष": "s", "स": "s", "ह": "h", "ं": "n", "ँ": "n", "क़": "k", "ख़": "k", "ग़": "g", "ज़": "j", "ड़": "r", "ढ़": "r", "फ़": "f" };
const TAM = { "க": "k", "ங": "n", "ச": "s", "ஞ": "n", "ட": "t", "ண": "n", "த": "t", "ந": "n", "ப": "p", "ம": "m", "ய": "y", "ர": "r",
  "ல": "l", "வ": "v", "ழ": "l", "ள": "l", "ற": "r", "ன": "n", "ஜ": "j", "ஷ": "s", "ஸ": "s", "ஹ": "h" };
export function skeleton(word) {
  let w = word.normalize("NFC"), out = "";
  if (/[ऀ-ॿ]/.test(w)) { for (const ch of w.normalize("NFD").normalize("NFC")) out += DEV[ch] || ""; }
  else if (/[஀-௿]/.test(w)) { for (const ch of w) out += TAM[ch] || ""; }
  else {
    w = w.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
    w = w.replace(/sh|ś|ṣ/g, "s").replace(/ch/g, "c").replace(/ph/g, "f").replace(/th/g, "t").replace(/dh/g, "d").replace(/bh/g, "b")
         .replace(/kh/g, "k").replace(/gh/g, "g").replace(/jh/g, "j").replace(/w/g, "v").replace(/z/g, "j").replace(/q/g, "k").replace(/x/g, "ks");
    out = w.replace(/[^bcdfghjklmnprstvy]/g, "");
  }
  out = out.replace(/c/g, "s").replace(/g/g, "k").replace(/d/g, "t").replace(/b/g, "p").replace(/j/g, "s").replace(/(.)\1+/g, "$1");
  return out.replace(/^y/, "y");
}
export const rot13 = s => s.replace(/[a-z]/gi, c => String.fromCharCode((c <= "Z" ? 90 : 122) >= (c = c.charCodeAt(0) + 13) ? c : c - 26));
export const unleet = s => s.toLowerCase().replace(/0/g, "o").replace(/1/g, "i").replace(/3/g, "e").replace(/4/g, "a").replace(/5/g, "s").replace(/7/g, "t").replace(/@/g, "a").replace(/\$/g, "s");
