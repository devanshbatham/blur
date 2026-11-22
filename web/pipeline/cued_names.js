// Names decided by what stands next to them: titles, kinship words, roles, organisations.
import { normalize } from "../normalize.js";
import { KEEP_LABELS } from "./common.js";
import { nm0 } from "./evidence.js";
import { KEY_HEADERLIKE, keyWords } from "./keys.js";
import { role } from "./labels.js";
import { rank } from "./spans.js";

export const TITLE_HEAD = /^(Director|Manager|Partner|Recruiter|Executive|Educator|Coordinator|Analyst|Officer|Lead|Engineer|Specialist|Associate|Consultant|Strategist|Administrator|Assistant|Supervisor|President|Counsel|Controller|Planner|Buyer|Representative|Advisor|Adviser|Scientist|Researcher|Designer|Developer|Architect|Owner|Head|Chief|Principal|Agent|Producer|Editor|Writer|Accountant|Auditor|Attorney|Paralegal|Nurse|Physician|Therapist|Pharmacist|Technician|Operator|Clerk|Secretary|Treasurer|Chair|Chairman|Chairwoman|Founder|Intern|Trainee|Contractor|Liaison|Steward|Superintendent|Foreman|Inspector|Investigator|Sponsor|Champion|Contact|Team|Desk|Office|Group|Committee|Board|Council|Department|Division|Unit)s?$/;

export const DEPT_WORD = /^(Finance|Financial|Revenue|Operations|Ops|Resources|Human|Strategy|Strategic|Acquisition|Talent|Systems|Marketing|Sales|Footwear|Apparel|Mass|Retail|Wholesale|Procurement|Purchasing|Supply|Chain|Logistics|Compliance|Legal|Risk|Credit|Treasury|Tax|Audit|Payroll|Benefits|Rewards|Total|Field|Medical|Clinical|Regulatory|Quality|Engineering|Product|Customer|Client|Service|Services|Support|Success|Partnerships|Partner|Brand|Category|Merchandising|Analytics|Data|Insights|Research|Development|Business|Corporate|Communications|Public|Relations|Investor|Facilities|Security|Information|Technology|Digital|Global|Regional|North|South|East|West|Central|America|Americas|Europe|Asia|Pacific|EMEA|APAC|Senior|Junior|Associate|Assistant|Deputy|Executive|Principal|Staff|Vice|General|Enterprise|Commercial|Account|Accounts|Key|National|Area|District|Territory|Store|Channel|Trade|Inside|Outside)$/;

// second halves of ordinary hyphenated words ("Faith-based", "Green-style", "Will-call"): never the end of a name
export const WORD_SUFFIX = /^(based|style|call|down|up|in|out|off|on|like|free|only|ready|side|wide|term|time|made|led|run|owned|aware|level|type|proof|shaped|sized|way|day|year|old|new|able|ish|fold|rate|grade|scale|size|line|free|safe|wise|bound|born|bred|built|point|step|stop|start|end|back|over|by|to|go|do|it|me|us|off|per|pre|pro|max|min|mode|test|only|first|last|long|high|low|mid|non|sub|all|one|two|ten|hop|top|tip|tap|zip|fit|fix|mix|set|get|let|cut|put|hit|kit|log|tag|map|key|pin|pad|pen|box|bag|bit|bot|bug|bus|cap|car|cat|dog|eye|fan|fee|gap|gas|gun|hat|ice|ink|jam|jet|job|lab|law|leg|lip|lot|man|men|mom|net|nut|oil|owl|pan|pay|pet|pie|pot|rag|ram|rat|raw|red|rib|rim|rod|row|rug|sea|sky|sun|tax|tea|tie|tin|toe|ton|toy|van|war|wax|web|wet|win|yes|zoo)$/;

// ---------- names decided by what stands next to them (no name list needed) ----------
// A name-shaped run: capitalised words, initials, with particles allowed between them ("Mairead Ó Súilleabháin",
// "Marguerite van der Westhuizen", "D J Papadakis", "Jun-seo").
export const NAME_RUN = "(?:\\p{Lu}[\\p{L}\\p{M}'’-]*[\\p{Ll}\\p{M}][\\p{L}\\p{M}'’-]*|\\p{Lu}\\.?)(?:[ \\u00a0](?:(?:de|da|do|dos|das|del|della|di|van|von|der|den|ter|ten|la|le|el|al|bin|bint|ibn|wa|y|e|Ó|O')[ \\u00a0])*(?:\\p{Lu}[\\p{L}\\p{M}'’-]*[\\p{Ll}\\p{M}][\\p{L}\\p{M}'’-]*|\\p{Lu}\\.?)){0,4}";

export const CAPS_RUN = "\\p{Lu}[\\p{Lu}'’-]+(?: \\p{Lu}[\\p{Lu}'’-]+){0,3}";

export const NOT_NAME = /^(The|A|An|This|That|These|Those|It|He|She|We|You|I|My|Our|Your|His|Her|Their|All|Everyone|Anyone|Someone|Nobody|Team|Support|Sales|HR|Legal|Finance|IT|Ops|Customer|Service|Services|Please|Thanks|Thank|Hello|Hi|Hey|Dear|Yes|No|Ok|Okay|Sure|Not|And|But|Or|If|So|Then|When|What|Who|Why|How|Here|There|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|June|July|August|September|October|November|December|Today|Tomorrow|Yesterday|Mr|Mrs|Ms|Dr|Sir|Madam|Mum|Mom|Dad|Papa|Mummy|Mama|Me|Agent|Caller|Customer|Client|Rep|Bot|System|Admin|User|Operator|Advisor|Adviser|Note|Edit|Update|Subject|From|To|Cc|Date|Time|Re|Fwd|Ref|Total|Status|Name|Email|Phone|Address|Reviewers?|Testing|Summary|Description|Treasury|Facilities|Security|Reception|Accounts|Billing|Payroll|Management|Engineering|Marketing|Compliance|God|Hope|Call|Text|Phone|Dial|Ring|Contact|Tel|Mobile|Mob|Cell|Fax|Office|Home|Work|Direct|Main|Helpline|Emergency|Whatsapp|WhatsApp|Mail|Reach|Ping|Message|SMS|Echo|Alexa|Siri|Google|Amazon|Apple|Microsoft)$/;

export const KIN = "(?:Auntie|Aunty|Aunt|Uncle|Abuela|Abuelo|Tia|Tía|Tio|Tío|Tante|Onkel|Oma|Opa|Nana|Nani|Dadi|Bua|Mama|Chacha|Cousin|Granny|Grandma|Grandpa)";

export const RANK = "(?:Miss|Mister|Constable|Sergeant|Sgt|Officer|Inspector|Detective|Nurse|Coach|Professor|Captain|Capt|Pastor|Rabbi|Imam|Agent|Doctora|Doctor|Señor|Señora|Senhor|Senhora|Dona|Herr|Frau|Monsieur|Madame|Mlle|Mme|Sra|Srta|Shri|Smt|MS|MRS|MR|MISS|DR|" + KIN + ")";

export const REF_CUE = /\b(?:ends?|ending(?: in)?|refs?\.?|reference|rma|tracking(?: no\.?| number| id)?|num[ée]ro de suivi|awb|consignment|shipment|comprovante|voo|vuelo|vol|flight|vendor id|po(?: number| no\.?)?|purchase order|registration no\.?|company no\.?|item|listing|project code|report|transaction id|txn id|invoice(?: no\.?| number)?|ticket|incident|booking(?: ref\w*)?|confirmation(?: no\.?| number| code)?|docket|quote|job|receipt|approved,|sku|model|part no\.?)\s*(?:is|was|:|no\.?|number)?\s*[#(]?$/i;

export const PUBLIC_LINE = /\b(?:switchboard|front desk|reception|main (?:line|number|office)|helpline|hotline|help line|customer (?:service|care|line|support|services)|call cent(?:re|er)|toll[- ]free|practice line|support line|office line|dept\.? office|department office|general enquiries|service client|hausverwaltung|caller id|queries:|enquiries:)[^.\n]{0,34}$/i;

export const ROLE_BOX = /^(?:parking|registrar|lettings|complaints|reception|enquir(?:y|ies)|inquir(?:y|ies)|bookings?|reservations?|admissions?|accounts?|billing|careers|jobs|recruit(?:ing|ment)|hr|press|media|legal|privacy|security|abuse|webmaster|admin|office|team|hello|contact|sales|marketing|orders?|returns?|service|customerservice|customer\.?care|helpdesk|help|feedback|newsletter|events?|claims?|payments?|finance|payroll|it|ops|devops|noc|dpo|compliance|facilities|frontdesk|concierge|housekeeping|appointments?|pharmacy|surgery|clinic|library|info|mail|post|support|no-?reply|donotreply|notifications?|alerts?|l10n|i18n|talent|people|partners?|vendors?|suppliers?|procurement|logistics|shipping|dispatch|warehouse|quality|qa|research|grants|alumni|students?|staff|membership|members|subscriptions?|tickets?|boxoffice|editor|editorial|news|pr|investors?|ir|ceo|md|director|secretary|treasurer|chair|council|planning|housing|licensing|revenues?|benefits|tax|customs|visa|consular|embassy)(?:[._-]?(?:team|desk|dept|office|uk|us|eu|in|global|emea|apac))?$/i;

export const ORG_WORD = "(?:Store|Stores|Surgery|Clinic|Clínica|Clinica|Hospital|Logistik|Logistics|School|College|University|Bank|Banco|Pharmacy|Bakery|Hotel|Motors|Industries|Enterprises|Traders|Solutions|Technologies|Services|Group|Holdings|Ltd|LLC|Inc|GmbH|AG|Pvt|Corp|Foundation|Trust|Associates|Partners|Agency|Studio|Labs?|Café|Restaurant|Salon|Garage|Market|Mart|Street|Road|Lane|Avenue|Park|Square|Bridge|Station|Airport|Mall|Tower|Towers|Plaza|Apartments|Residency|Nagar|Colony)";

export const ORG_END = new RegExp("(?:^|[ \\u00a0])" + ORG_WORD + "$");

export const ORG_NEXT = new RegExp("^[ \\u00a0](?:\\p{Lu}[\\p{L}'’-]+[ \\u00a0]){0,2}" + ORG_WORD + "(?![\\p{L}])", "u");

export const ORG_PREV = /(?:Clínica|Clinica|Hospital|Hotel|Café|Restaurant|Banco|Bank of|University of|College of|Colegio|Instituto|Universidad|Escuela|Dukaan|Dukan)[  ]$/i;

export function cuedNames(text, spans) {
  const taken = new Uint8Array(text.length + 1), org = new Uint8Array(text.length + 1), place = new Uint8Array(text.length + 1);
  for (const o of spans) { if (!KEEP_LABELS.has(o.label) && !nm0(o)) taken.fill(1, o.start, o.end); if (/^(ORG|DATE|TIME|URL|DATE_PLAIN)$/.test(o.label)) org.fill(1, o.start, o.end); if (/^(CITY|COUNTRY|STATE)$/.test(o.label)) place.fill(1, o.start, o.end); }
  let strong = false;        // a direct person frame outranks the network's guess that an unknown capitalised word is a place
  const add = [];
  const put = (a, v) => {
    v = v.replace(/[\s.,;:'’-]+$/, "");
    const first = v.split(/[ \u00a0]/)[0].replace(/\.$/, "");
    if (v.length < 2 || NOT_NAME.test(first) || /^\p{Lu}\.?$/u.test(v)) return;
    if (/(Bot|Desk|Support|Team|Service|Center|Centre|Helpline|Hotline|Dept|Department|Office)$/.test(v) || ORG_END.test(v) || ORG_NEXT.test(text.slice(a + v.length, a + v.length + 40))) return;
    for (let i = a; i < a + v.length; i++) if (taken[i] || org[i] || place[i] && !strong) return;
    const b = a + v.length;
    if (/(Error|Exception|Warning|Handler|Service|Manager|Controller|Factory|Builder|Client|Server|Rejection)$/.test(v) || /^ ?&/.test(text.slice(b, b + 2))) return;
    { const sfx = /-(\p{Ll}+)$/u.exec(v); if (sfx && WORD_SUFFIX.test(sfx[1])) return; }
    { const cov = new Uint8Array(b - a); for (const o of spans) if (nm0(o) && !o.drop && o.start < b && o.end > a) cov.fill(1, Math.max(0, o.start - a), Math.min(b, o.end) - a);
      if ([...text.slice(a, b)].every((ch, i) => cov[i] || !/[\p{L}]/u.test(ch))) return; }                       // every word of it is already found
    if (spans.some(o => nm0(o) && !o.drop && o.start <= a && o.end >= b) || add.some(o => o.start <= a && o.end >= b)) return;   // already covered
    for (const o of spans) if (nm0(o) && o.start >= a && o.end <= b) o.drop = true;                    // a part was found: the whole run replaces it
    for (const o of add) if (o.start >= a && o.end <= b) o.drop = true;
    add.push({ start: a, end: b, label: "GIVENNAME", byRule: true });
  };
  const OFF = (typeof process !== "undefined" && process.env && process.env.CUED_OFF || "").split(",");
  let ruleNo = 0;
  const each = (re, grp = 1) => { ruleNo++; if (OFF.includes(String(ruleNo))) return; for (const m of text.matchAll(re)) { const v = m[grp]; if (v) put(m.index + m[0].lastIndexOf(v), v); } };
  strong = true;
  // 1. a title, rank or kinship word before the name
  each(new RegExp("(?<![\\p{L}])" + RANK + "\\.?[ \\u00a0](" + NAME_RUN + "|" + CAPS_RUN + ")", "gu"));
  // 2. frames that introduce a person (the cue in any case; the name itself must be capitalised)
  const nameAt = new RegExp("['\"“‘«]?(" + NAME_RUN + ")", "uy");
  const frame = cue => { ruleNo++; if (OFF.includes(String(ruleNo))) return;
    for (const m of text.matchAll(cue)) { nameAt.lastIndex = m.index + m[0].length; const n = nameAt.exec(text); if (n) put(nameAt.lastIndex - n[1].length, n[1]); } };
  frame(/\b(?:loop(?:ing|ed)? in|courtesy of|ask(?:ed)? for(?: me,)?|speaking (?:with|to)|you'?re through to|name'?s|(?:my|his|her|their) name is|name (?:is|as)|gave (?:his|her|their) name as|records? (?:him|her|them) as|call(?:s|ed)? (?:him|her|them|me)|comment from|message from|note from|regards to|au nom de|a nombre de|em nome de|auf den Namen|c\/o|attn:?|on behalf of|married to|engaged to|survived by|accompanied by)[ \u00a0]/gi);
  frame(/\b(?:my|his|her|our|their|your) (?:husband|wife|son|daughter|cousin|brother|sister|friend|neighbou?r|flatmate|roommate|colleague|boss|manager|partner|mother|father|mum|dad|uncle|aunt|nephew|niece|landlord|tenant|assistant|lawyer|solicitor|accountant|doctor|dentist|therapist|teacher|tutor|recruiter|supervisor)(?: is|,)?[ \u00a0]/gi);
  ruleNo++;
  each(new RegExp("\\bI,[ \\u00a0](" + NAME_RUN + "),", "gu"));
  // 2a. copying, cc'ing and looping people in: "copying in Maggie", "cc'ing Dana", "cc: Raj"
  frame(/\b(?:copying(?: in)?|cc'?ing|cc'?d|cc:|bcc:?|copied|looping in|adding|forwarding to|forwarded to|handing (?:this )?(?:off |over )?to|deferring to)[ \u00a0]/gi);
  // 2a'. a sign-off: a lone name on the last non-empty line of a message, after a blank line
  each(new RegExp("\\n[ \\t]*\\n[ \\t]*[-–—~]?[ \\t]*(" + NAME_RUN + ")[ \\t]*\\s*$", "gu"));
  // 2b. people-taking verbs and praise; surname keys; a role key before the value; a quoted name after the word "name"
  frame(/\b(?:pull(?:ed|ing)? in|br(?:ing|ought) in|paged|pager went to|escalated to|handed (?:over )?to|check(?:ed)? with|spoke (?:to|with)|talk(?:ed)? to|reach(?:ed)? out to|consent (?:received )?from|well done to|congrat(?:s|ulations) to|kudos to|shout-?out to|thank you to|thanks to|thx|signed,|yours,|known as|surname|last name|family name|apellidos?|familia|family)[ \u00a0]/gi);
  frame(/\b(?:landlord|tenant|applicant|guarantor|owner|driver|second driver|lead traveller|traveller|traveler|passenger|witness|patient|employee|student|candidate|beneficiary|nominee|insured|cardholder|account holder|policyholder|signatory|next of kin|emergency contact|also travelling|also traveling)s?(?: \([^)\n]{0,24}\))?["']?[ \t]*[:=][ \t]*["']?(?:(?:MR|MRS|MS|MISS|DR|Mr|Mrs|Ms|Miss|Dr)\.? )?/gi);
  ruleNo++;
  if (!OFF.includes(String(ruleNo))) for (const m of text.matchAll(new RegExp("\\bname\\b[^.\\n]{0,40}?['‘\"“](" + NAME_RUN + ")['’\"”]", "giu"))) if (/^\p{Lu}/u.test(m[1])) put(m.index + m[0].lastIndexOf(m[1]), m[1]);
  // 2c. the same frames before a name in capitals (forms): "Applicant (as in passport): GANBAATAR TEMUULEN"
  ruleNo++;
  if (!OFF.includes(String(ruleNo))) for (const m of text.matchAll(new RegExp("\\b(?:landlord|tenant|applicant|guarantor|driver|second driver|lead traveller|traveller|passenger|witness|patient|employee|student|candidate|policyholder|cardholder|name)s?(?: \\([^)\\n]{0,24}\\))?[ \\t]*:[ \\t]*(?:(?:MR|MRS|MS|MISS|DR)\\.? )?(" + CAPS_RUN + ")(?=\\s*(?:\\n|$|  |[,;·|]))", "giu"))) if (/^\p{Lu}+[ '’-]\p{Lu}/u.test(m[1]) && m[1] === m[1].toUpperCase()) put(m.index + m[0].lastIndexOf(m[1]), m[1]);
  // 2d. a parenthesised speaker ("From adviser (Mairead):"); a full name in parentheses right after an identifier
  each(new RegExp("\\((" + NAME_RUN + ")\\):", "gu"));
  ruleNo++;
  if (!OFF.includes(String(ruleNo))) for (const o of spans) if (/^(ID|_ID|IDCARD)$/.test(o.label)) { const m = new RegExp("^ \\((" + NAME_RUN + ")\\)", "u").exec(text.slice(o.end, o.end + 60)); if (m && / /.test(m[1])) put(o.end + 2, m[1]); }
  // 2e. a signature: a name alone on the line after a closing line
  each(new RegExp("(?:^|\\n)[ \\t]*(?:Best|Best regards|Kind regards|Warm regards|Regards|Thanks|Thank you|Many thanks|With thanks|Cheers|Sincerely|Yours sincerely|Yours faithfully|Yours truly|Love|Saludos|Un abrazo|Atentamente|Cordialement|Viele Grüße|Mit freundlichen Grüßen|Liebe Grüße|Abraços|Atenciosamente|Obrigad[oa]),?[ \\t]*\\n+[ \\t]*(" + NAME_RUN + ")[ \\t]*(?=\\n|$)", "gu"));
  // 2f. a chat export that puts the time after the speaker: "Adaeze Onyekachi  10:14"
  each(new RegExp("(?:^|\\n)(" + NAME_RUN + ")[ \\t]{1,4}\\[?\\d{1,2}:\\d{2}(?: ?[AP]M)?\\]?[ \\t]*(?=\\n)", "gu"));
  // 2g. a name right before a phone number or an e-mail address: "on-call: Emeka, +234 803 555 0127"
  ruleNo++; strong = false;
  if (!OFF.includes(String(ruleNo))) for (const o of spans) if (o.label === "TEL" || o.label === "EMAIL") { const m = new RegExp("(?:^|[\\n:;(,–—-] ?)(" + NAME_RUN + ")(?:,| \\(|:| [-–—]) ?$", "u").exec(text.slice(Math.max(0, o.start - 60), o.start)); if (m) put(o.start - m[0].length + m[0].indexOf(m[1]), m[1]); }
  strong = true;
  // 2h. more frames: "name D J Papadakis", "Name in Cyrillic: ...", "Minutes by ...", "To Tomás, love ...", a modal before a
  //     name and a verb ("Could Åsa confirm?", "Did Rose get ..."), South Asian kinship words after or before a name
  frame(/\b(?:minutes|notes|prepared|written|compiled|taken|reviewed|approved|signed off|drafted|submitted) by[ \u00a0]/gi);
  frame(/\bname in [A-Za-z ]{3,20}:[ \t]*/gi);
  for (const m of text.matchAll(new RegExp("\\bname[ \\u00a0](" + NAME_RUN + ")", "gu"))) if (/[ \u00a0]/.test(m[1])) put(m.index + m[0].lastIndexOf(m[1]), m[1]);
  each(new RegExp("\\bTo (" + NAME_RUN + "),? (?:love|with love|from|best wishes)\\b", "gu"));
  each(new RegExp("\\b(?:[Cc]ould|[Cc]an|[Ww]ill|[Ww]ould|[Dd]id|[Dd]oes|[Hh]as|[Ss]hould) (\\p{Lu}[\\p{L}\\p{M}'’-]+)(?= (?:confirm|check|send|review|approve|call|reply|take|look|join|help|sign|share|update|let|get|do|have|be|make|come|go|know|want|need|pick|bring|cover|handle|own|fix|run|book|pay|say|ask|tell|meet|see|try|give|find|read|write|finish|start|still|also|already|ever|not|please)\\b)", "gu"));
  each(new RegExp("(?<![\\p{L}])(\\p{Lu}[\\p{L}\\p{M}'’-]+)(?= (?:didi|bhaiya|bhaiyya|paaji|bhabhi|chacha|chachi|mausi|beta|sahab|saab)(?![\\p{L}]))", "gu"));
  // a hyphenated given name as East Asian names are romanised: "Jae-won", "Soo-jin", "Mei-Ling" (not at the start of a sentence)
  for (const m of text.matchAll(/(?<=[\p{Ll},;] )(\p{Lu}\p{Ll}{1,5})-(\p{Ll}{2,5})(?![\p{L}-])/gu))
    if (WORD_SUFFIX.test(m[2])) continue; else
    if (!/^(Wi|Hi|Co|Pre|Re|Non|Self|Anti|Multi|Semi|Sub|Ex|Post|Mid|Check|Sign|Log|Follow|Sell|Start|Stand|Set|Back|Opt|Add|Plug|Pop|Drop|Pick|Walk|Drive|Take|Run|Roll|Built|Well|Part|Full|Long|Short|High|Low|Real|On|Off|In|Out|Up|All|Two|Three|Four|Five|Half|Top|Old|New|Open|Close|Hand|Break|Cut|Pay|Lock|Sold|Kick|Wrap|Write|Read|Print|Mix|Deep|Wide|Free|Near|Far|Fast|Slow|Easy|User|Client|Server|Third|First|Second|Last|Next|Best|Must|Know|Day|Night|Year|Week|Month|Time|Life|Work|Home|Web|App|Dev|Ops|Git|Api|Add|Go|No|Yes|Not|Hard|Soft|Dark|Light|Cross|Inter|Intra|Over|Under|Trans|Micro|Macro|Mega|Mini|Bi|Tri|Uni|Auto|Pro|Eco|Bio|Geo|Tele|Video|Audio|Photo|Thank|Trade|State|Rock|Hip|Ping|Tip|Zip|Tic|Flip|Ship|Know|Show|Slip|Clip)$/.test(m[1])) put(m.index, m[0]);
  // 3. frames after the name: "X speaking", "X wrote:", "X (wife)", "X (she/her)", "X from Treasury"
  each(new RegExp("(?<![\\p{L}'’-])(" + NAME_RUN + ")(?=,? speaking\\b| wrote:|, who\\b| \\((?:wife|husband|son|daughter|mother|father|brother|sister|partner|fianc[ée]e?|she\\/her|he\\/him|they\\/them|née [^)]*)\\)| (?:here )?from (?:comp|sales|treasury|hr|legal|finance|accounts|billing|support|payroll|marketing|engineering|ops|it|facilities|reception|the (?:office|bank|clinic|school|agency))\\b)", "gu"));
  strong = false;
  // 4. a name that matches the local part of an e-mail address near it ("Oyelaran,Temitope,temi.oyelaran@...", "Mark's email is mark.oduya@...")
  for (const e of spans) {
    if (e.label !== "EMAIL" || OFF.includes("mail")) continue;
    if (ROLE_BOX.test(text.slice(e.start, e.end).split("@")[0])) continue;      // a role mailbox names a function, not a person
    const local = text.slice(e.start, e.end).split("@")[0].toLowerCase().replace(/[^a-z]+/g, " ").trim().split(" ").filter(w => w.length >= 3);
    if (!local.length) continue;
    const a0 = Math.max(0, e.start - 140), win = text.slice(a0, Math.min(text.length, e.end + 60));
    for (const m of win.matchAll(/(?<![\p{L}\p{N}_@.-])\p{Lu}[\p{L}\p{M}'’-]{2,}(?![\p{L}\p{N}_@])/gu)) {
      const w = m[0].normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^a-z]/g, "");
      if (w.length >= 3 && local.some(l => l === w || l.length >= 4 && w.startsWith(l) || w.length >= 4 && l.startsWith(w))) {
        let run = null;
        for (const r of win.matchAll(new RegExp(NAME_RUN, "gu"))) if (r.index <= m.index && r.index + r[0].length >= m.index + m[0].length) { run = r; break; }
        if (run && run[0].split(/[ \u00a0]/).length <= 5) put(a0 + run.index, run[0]); else put(a0 + m.index, m[0]);
      }
    }
  }
  // 5. the first cell of a tab-separated row that also holds a phone number or an e-mail address
  for (const m of text.matchAll(new RegExp("(?:^|\\n)(" + NAME_RUN + ")(?=\\t[^\\n]*\\t)", "gu"))) {
    const a = m.index + m[0].lastIndexOf(m[1]), le = text.indexOf("\n", a) < 0 ? text.length : text.indexOf("\n", a);
    if (!OFF.includes("row") && / /.test(m[1]) && spans.some(o => (o.label === "EMAIL" || o.label === "TEL") && o.start > a && o.end <= le)) put(a, m[1]);
  }
  // 5b. the first cell of a Markdown table row that also holds an e-mail address or a phone number
  for (const m of text.matchAll(new RegExp("(?:^|\\n)\\|[ \\t]*(" + NAME_RUN + ")[ \\t]*\\|", "gu"))) {
    const a = m.index + m[0].lastIndexOf(m[1]), le = text.indexOf("\n", a) < 0 ? text.length : text.indexOf("\n", a);
    if (/ /.test(m[1]) && spans.some(o => (o.label === "EMAIL" || o.label === "TEL") && o.start > a && o.end <= le)) put(a, m[1]);
  }
  // 6. chat speakers: three or more lines of the form "Label: speech", where a label is one to three name-shaped words.
  //    Kinship and role words in a label are not masked ("Abuela Remedios:" masks Remedios; "Agent:" masks nothing).
  {
    const SP = new RegExp("(?:^|\\n)(?:\\[[^\\]\\n]{3,30}\\] ?)?((?:" + KIN + "[ \\u00a0])?)(" + NAME_RUN + ")(?: [^\\p{L}\\p{N}\\s:]{1,4})?:[ \\t]+(?=\\S[^\\n]{14,})", "gu");
    const kwds = keyWords(text);
    const hits = [...text.matchAll(SP)].filter(m => m[2].split(/[ \u00a0]/).length <= 3 && !NOT_NAME.test(m[2].split(/[ \u00a0]/)[0]) && !kwds.has(m[2]) && !KEY_HEADERLIKE.test(m[2]));
    const labels = new Map(); for (const m of hits) labels.set(m[2], (labels.get(m[2]) || 0) + 1);
    const lines = text.split("\n").length;
    // ... and at least one label is corroborated as a proper noun: the network already found it as a name somewhere, it
    // carries a kinship word, or it is used capitalised in the middle of a sentence ("llega Chema mañana")
    const proper = [...labels.keys()].some(l => { const w = l.split(/[ \u00a0]/)[0];
      return spans.some(o => nm0(o) && text.slice(o.start, o.end).split(/[ \u00a0]/).includes(w)) || new RegExp("[\\p{Ll},] " + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![\\p{L}])", "u").test(text); }) || hits.some(m => m[1])
      // ... or the lines are conversation: questions, greetings and thanks, in any of several languages
      || hits.filter(m => { const le = text.indexOf("\n", m.index + 1); const line = text.slice(m.index + m[0].length, le < 0 ? text.length : le);
           return /\?|(?<![\p{L}])(hallo|hi|hey|hello|danke|thanks|thx|gracias|merci|obrigad[oa]|ok|okay|haan|sí|oui|ja|nein|yes|yeah|lol|pls|please|bitte|por favor|salut|hola|oi|olá|namaste)(?![\p{L}])/iu.test(line); }).length >= 2;
    if (proper && !OFF.includes("chat") && hits.length >= 3 && (labels.size >= 2 || hits.length >= 4) && [...labels.values()].some(n => n >= 2) || proper && !OFF.includes("chat") && hits.length >= 3 && hits.length >= lines * 0.5)
      for (const m of hits) { const w = m[2].split(/[ \u00a0]/)[0];
        const own = labels.get(m[2]) >= 2 || m[1] || spans.some(o => nm0(o) && text.slice(o.start, o.end).split(/[ \u00a0]/).includes(w)) || new RegExp("[\\p{Ll},] " + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![\\p{L}])", "u").test(text);
        if (own) put(m.index + m[0].indexOf(m[2], m[0].indexOf(m[1]) + m[1].length), m[2]); }
  }
  // a code in parentheses right after a person's name, or in the same table row as a name, is that person's identifier
  strong = false;
  for (const o of spans.concat(add)) if (nm0(o) && !o.drop) {
    const m = /^,?\s*\(([A-Z][A-Z0-9]{0,6}(?:-[A-Z0-9]{1,8}){1,4})(?=[),;])/.exec(text.slice(o.end, o.end + 40));
    if (m && /\d/.test(m[1])) add.push({ start: o.end + m[0].length - m[1].length, end: o.end + m[0].length, label: "ID", byRule: true, cued: true });
  }
  for (const m of text.matchAll(/(?<![\w-])(?:[A-Z]{2,5}-)?(?:EMP|EID|STAFF|EMPL|PERS)[-_]?\d{3,8}(?![\w-])|(?<![\w-])[A-Z]{2,5}-(?:EMP|EID|STAFF)-\d{3,8}(?![\w-])/g))
    add.push({ start: m.index, end: m.index + m[0].length, label: "ID", byRule: true, cued: true });
  // every other capitalised occurrence of a name found here is the same person ("loop in Tjarra ... Tjarra Baker  10:24")
  strong = true;
  const found = new Set();
  const kw2 = keyWords(text);
  for (const o of add) if (!o.drop) for (const w of text.slice(o.start, o.end).split(/[^\p{L}\p{M}'’-]+/u)) if (w.length >= 4 && /^\p{Lu}/u.test(w) && !NOT_NAME.test(w) && !kw2.has(w) && !KEY_HEADERLIKE.test(w)) found.add(w);
  if (found.size && found.size <= 30) for (const m of text.matchAll(new RegExp("(?<![\\p{L}\\p{N}_@.-])(?:" + NAME_RUN + ")(?![\\p{L}\\p{N}_@])", "gu"))) {
    const ws = m[0].split(/[ \u00a0]/);
    if (ws.length <= 3 && ws.some(w => found.has(w.replace(/[.,]$/, ""))) && ws.every(w => found.has(w) || !NOT_NAME.test(w))) put(m.index, m[0]);
  }
  return add.length ? spans.concat(add).filter(o => !o.drop).sort((x, y) => x.start - y.start) : spans;
}
