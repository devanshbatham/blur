"""Shared context for the general detector: the circuit-building context (Ctx), cue helpers and the
word lists and constants every part uses.

Weight-space program for the ai4privacy/pii-masking-300k label set (English).

Design notes (from studying the dev split):
- A value's *shape* decides its label far more reliably than the key in front of it.
- Address fields come in a fixed order (country, building, street, city, state, postcode,
  secondary address), so neighbouring fields identify each other.
"""
from __future__ import annotations

import string

import os

from ..dsl import Net, Sig
from ..patterns import HI, byteset, parse_var

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")   # blur/data

D, UP, LO = string.digits, string.ascii_uppercase, string.ascii_lowercase
AL, AN = UP + LO, UP + LO + D
WORD = AN + HI
HEXC = D + "abcdefABCDEF"
MONTHS = "(January|February|March|April|May|June|July|August|September|October|November|December)"
SEC_WORDS = ("Ranch|Flat|Lodge|Cabin|Terrace|Farmhouse|Box|Tower|House|Penthouse|Townhouse|Castle|Palace|"
             "Apt|Room|PO|Station|Suite|Villa|Floor|Pod|Barracks|Office|Bungalow|Co-op|PB|Unit|Maisonette|"
             "Duplex|Attic|Basement|Dept|Loft|Dorm|Chalet|Fort|Condo|Residence|Block|Cottage|Building|"
             "Trailer|Mansion|Studio|Mobile Home|Bldg|Quadruplex|RV|Triplex|Apartment|PO Box")
STREET_SUFFIX = ("Road|Lane|Street|Close|Hill|Avenue|Grove|Way|Drive|Green|Crescent|Place|Park|Walk|"
                 "Court|View|Bank|Gardens|Square|Row|Mews|Rise|Drove|Fields|Highway|Causeway|Boulevard|"
                 "Rd|St|Ave|Blvd|Dr|Ln|Ct|Cir|Hwy|Pkwy|Pl|Ter|Trl|Circle|Trail|Parkway|Terrace")
TITLES = ("Mr|Mrs|Miss|Ms|Mayoress|Duchess|Archduchess|Princess|Dame|Prince|Ald|Queen|Chief|Prelate|Archduke|King|"
          "Countess|Sel|Baron|Lady|Baroness|Madame|Alderwoman|Friar|Mother|Abbess|Duke|Lord|Master|Sr|Pope|Pr|Rev|"
          "Sir|Selectwoman|Abbot|Alderman|Esquire|Fr|Ab|Brother|Sister|Selectman|Marshal|Pp|Heiress|Monsignor|Msgr|"
          "Father|Esq|Count|Mister|Major|Heir|Mayor|Reverend|Doctor|Secretary|Vicar|Mstr|Corp|General|Judge|"
          "Barrister|Colonel|Honour|Admiral|Pror|Corporal|Solicitor|Brig|Pref|Sec|Chan|Att|Ambassador|Min|Solicit|"
          "Priest|Governor|Col|Adm|Cllr|Pastor|Bailiff|Senator|Adv|Alderperson|Magistrate|Attorney|Excellency|Sen|"
          "Jr|Premier|Hon|Engineer|Selectperson|Barr|Epus|Lt|Minister|Cardinalis|Brigadier|Ofc|Commander|Mx")


EXTRA_WORDS = ("january february march april may june july august september october november december monday tuesday "
               "wednesday thursday friday saturday sunday britain british english london username postcode online "
               "offline email internship mentorship certification certifications wellbeing wellness lastname firstname "
               "birthdate webinar checklist stakeholder stakeholders facilitator evaluator panelist attendee holistic "
               "messaging alumni upcoming sustainability instructional outreach demographics tutoring tutor tutors "
               "readiness bullying proficiency bilingual extracurricular truancy kudos sincerely firstly lastly kindly "
               "guardians gamer assessor commenter borrower inclusivity lockdown maths app tech ltd edu tel unknown url "
               "ipv ip api id inc llc corp plc gmbh co county realty media group associates logistics "
               "dr mr mrs ms prof mx sr jr st mt "
               "google microsoft amazon apple facebook meta twitter linkedin youtube instagram whatsapp telegram tiktok "
               "kubernetes docker python java javascript typescript linux windows android iphone ipad macbook github gitlab "
               "slack zoom netflix uber paypal visa mastercard samsung sony toyota tesla nasa covid postgresql mysql mongodb "
               "redis nginx apache oracle ibm intel nvidia openai anthropic chatgpt gmail outlook yahoo excel powerpoint "
               "wikipedia reddit spotify airbnb fedex ups dhl walmart ikea nike adidas bitcoin ethereum wifi bluetooth "
               "amex hdfc icici sbi axis citi hsbc barclays aadhaar pan ifsc iban swift upi gst sku ist gmt utc pdf "
               "alzheimer alzheimers parkinson parkinsons gaussian newtonian darwinian euclidean freudian kafkaesque "
               "boolean hodgkin crohn tourette asperger huntington cartesian keynesian marxist orwellian "
               "diwali holi eid ramadan ramzan christmas easter pongal onam navratri dussehra thanksgiving hanukkah "
               "rs inr usd eur gbp lakh lakhs crore crores lpa ctc a i o admin administrator superuser moderator "
               "operator tester guest root staff user users customer customers patient patients").split()


COUNTRIES = ("United Kingdom|United States|United States of America|USA|France|Italia|Italy|Nederland|Netherlands|"
             "Deutschland|Germany|Schweiz|Switzerland|España|Spain|Canada|Australia|New Zealand|Ireland|Portugal|"
             "Belgium|Austria|Sweden|Norway|Denmark|Finland|Poland|Russia|Ukraine|Turkey|Greece|India|China|Japan|"
             "South Korea|North Korea|Brazil|Mexico|Argentina|Chile|Colombia|Peru|Egypt|Nigeria|Kenya|Ghana|"
             "South Africa|Morocco|Algeria|Tunisia|Sudan|Ethiopia|Saudi Arabia|United Arab Emirates|UAE|Qatar|Israel|"
             "Iran|Iraq|Pakistan|Bangladesh|Sri Lanka|Nepal|Indonesia|Malaysia|Singapore|Thailand|Vietnam|"
             "Philippines|Myanmar|Cambodia|Romania|Hungary|Czech Republic|Slovakia|Croatia|Serbia|Bulgaria|"
             "Scotland|England|Wales|Northern Ireland|Great Britain|Costa Rica|Cuba|Jamaica|Venezuela|Ecuador|"
             "Uruguay|Paraguay|Bolivia|Luxembourg|Iceland|Estonia|Latvia|Lithuania|Slovenia|Albania|Kosovo|"
             "Kazakhstan|Afghanistan|Jordan|Lebanon|Syria|Kuwait|Oman|Bahrain|Tanzania|Uganda|Zimbabwe|Zambia|"
             "Cameroon|Senegal|Taiwan|Hong Kong|Africa|Europe|Asia|Oceania|Antarctica|North America|South America|Latin America|"
             "Middle East|Scandinavia|Caribbean|Bharat|Hindustan|Holland|Britain|America|Czechia|Turkiye|Türkiye|"
             "Ivory Coast|Palestine|Libya|Yemen|Mongolia|Laos|Belarus|Moldova|Georgia|Armenia|Azerbaijan|Uzbekistan|"
             "Mozambique|Angola|Rwanda|Botswana|Namibia|Madagascar|Mali|Niger|Chad|Somalia|Guatemala|Honduras|"
             "Nicaragua|Panama|El Salvador|Dominican Republic|Haiti|Trinidad and Tobago|Bahamas|Barbados|Malta|"
             "Cyprus|Monaco|Liechtenstein|Montenegro|Bosnia and Herzegovina|North Macedonia|Guernsey|Jersey|"
             "Papua New Guinea|Fiji|Bhutan|Maldives|Brunei|Macau|Greenland|Lebanon|Oman")
STATE_NAMES = ("Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|"
               "Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|"
               "Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|"
               "North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|"
               "South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|"
               "Ontario|Quebec|British Columbia|Alberta|New South Wales|Victoria|Queensland|Bavaria")
CITIES = ("London|Paris|Berlin|Madrid|Rome|Vienna|Amsterdam|Brussels|Lisbon|Dublin|Prague|Warsaw|Budapest|Athens|"
          "Stockholm|Oslo|Copenhagen|Helsinki|Zurich|Geneva|Munich|Hamburg|Frankfurt|Milan|Naples|Barcelona|Valencia|"
          "Manchester|Birmingham|Liverpool|Glasgow|Edinburgh|Leeds|Bristol|Cardiff|Belfast|Moscow|Kyiv|Istanbul|Ankara|"
          "New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|San Jose|Austin|"
          "San Francisco|Seattle|Denver|Boston|Atlanta|Miami|Detroit|Las Vegas|Portland|Toronto|Montreal|Vancouver|"
          "Ottawa|Mexico City|Bogota|Lima|Santiago|Buenos Aires|Sao Paulo|Rio de Janeiro|Caracas|Havana|"
          "Mumbai|Delhi|New Delhi|Bengaluru|Bangalore|Hyderabad|Chennai|Kolkata|Pune|Ahmedabad|Jaipur|Lucknow|Surat|"
          "Karachi|Lahore|Islamabad|Dhaka|Colombo|Kathmandu|Beijing|Shanghai|Shenzhen|Guangzhou|Chengdu|Hong Kong|"
          "Taipei|Tokyo|Osaka|Kyoto|Seoul|Busan|Bangkok|Hanoi|Ho Chi Minh City|Jakarta|Manila|Kuala Lumpur|Singapore|"
          "Sydney|Melbourne|Brisbane|Perth|Adelaide|Auckland|Wellington|Dubai|Abu Dhabi|Doha|Riyadh|Jeddah|Tehran|"
          "Baghdad|Tel Aviv|Jerusalem|Amman|Beirut|Cairo|Alexandria|Lagos|Abuja|Nairobi|Accra|Addis Ababa|"
          "Johannesburg|Cape Town|Durban|Casablanca|Algiers|Tunis|Khartoum|Kampala|Dar es Salaam")
MONTHS_ANY = ("(January|February|March|April|May|June|July|August|September|October|November|December|"
              "january|february|april|june|july|august|september|october|november|december|"
              "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)")
MON3 = "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
DAY3 = "(Mon|Tue|Wed|Thu|Fri|Sat|Sun)"


def u(text: str) -> str:
    """UTF-8 bytes viewed as one char per byte, so patterns can contain non-ASCII literals."""
    return text.encode("utf-8").decode("latin-1")


def general() -> bool:
    """PROFILE=general: real-world conventions (a 3-3-4 number is a phone, 3-2-4 is an SSN, bare
    digit strings are not guessed). Default profile follows the ai4privacy-300k conventions."""
    return os.environ.get("PROFILE", "ai4p") == "general"


class Ctx:
    def __init__(self):
        self.n = Net()
        self.m: dict[tuple[int, str], list[Sig]] = {}

    def P(self, pattern, pre=WORD, post=WORD, **kw):
        return self.n.match(parse_var(u(pattern)), byteset(pre) if pre else None,
                            byteset(post) if post else None, **kw)

    def add(self, label, sig, tier=0):
        """tier 0: shape is unambiguous. 1: decided by the key in front. 2: default guess for an
        ambiguous shape. Lower tiers win when two detectors claim the same characters."""
        self.m.setdefault((tier, label), []).append(sig)

    def get(self, label, tier=None) -> Sig:
        sigs = [s for (t, lab), v in self.m.items() if lab == label and tier in (None, t) for s in v]
        if not sigs:
            return self.n.cls("\x01")  # a byte that never occurs: constant false
        return self.n.OR(*sigs, force=True)


def said(c: Ctx, words, loose=False):
    """Positions right after a cue word used in running text: "<word> [is|of|was|:] <value>".
    With loose=True any run of lowercase words may sit in between (up to ~30 characters)."""
    n = c.n
    low, letter = n.cls(LO), n.cls(AL)
    ends = []
    for w in words:
        base = n.AND(n.lit(w, nocase=True), ~letter.at(-1))
        ends += [n.AND(base, ~low.at(len(w))).at(-(len(w) - 1)),
                 n.AND(base, n.cls("sS").at(len(w)), ~low.at(len(w) + 1)).at(-len(w))]
    cue_end = n.OR(*ends)
    gap = n.cls(" :#*|=\t\"'([`.")
    if loose:
        bridge = n.OR(gap, low, n.cls(","), force=True)
    else:
        links = [n.spread_right(n.lit(f" {w} ", nocase=True), len(w) + 2) for w in ("is", "of", "was", "are", "the", "number", "no")]
        bridge = n.OR(gap, *links, force=True)
    reach = n.prop_right(cue_end, bridge, 4)
    return n.AND(reach.at(-1), ~bridge, ~c.W.at(-1))


def cue(c: Ctx, words, veto=(), whole=False):
    """First character of the value that follows a key containing one of `words`. With
    whole=True the word may not be glued to lowercase letters ("statement" is not "state")."""
    n = c.n
    low = n.cls(LO)
    hits = []
    for w in words:
        h = n.lit(w, nocase=True)
        if whole:
            plural = n.AND(n.cls("sS").at(len(w)), ~low.at(len(w) + 1))
            h = n.AND(h, ~low.at(-1), n.OR(plural, n.AND(h, ~low.at(len(w)))))
        hits.append(h)
    hit = n.AND(n.OR(*hits), n.OR(c.key, c.tag), ~c.ctag)
    reach = n.prop_right(hit, c.skip, 5)
    return n.AND(c.W, ~c.key, ~c.tag, ~n.cls("</").at(-1), reach.at(-1), *[~v for v in veto])


def word_tree(c: Ctx, words, first_upper=False):
    """A word list as a letter tree in the weights: one neuron per prefix, each ANDing its
    parent (one character back) with the next letter. Returns the mask of whole tokens that
    are in the list (optionally followed by 's)."""
    n = c.n
    letter = {ch: n.cls(ch + ch.upper()) for ch in string.ascii_lowercase}
    # all word lists share one letter tree (per first-letter mode): a prefix neuron is built once and reused
    cache = c.__dict__.setdefault("_tries", {})
    if first_upper not in cache:
        # a word starts at a token start that is followed by another letter (one-letter tokens never walk the tree)
        nxt = n.cls(string.ascii_letters)
        cache[first_upper] = {ch: n.AND(n.cls(ch.upper()) if first_upper else letter[ch], ~c.wordc.at(-1), nxt.at(1))
                              for ch in string.ascii_lowercase}
    node = cache[first_upper]
    finals = []
    for w in sorted(set(words)):
        if not w.isascii() or not w.isalpha():
            continue
        for i in range(2, len(w) + 1):
            if w[:i] not in node:
                node[w[:i]] = n.AND(node[w[:i - 1]].at(-1), letter[w[i - 1]])
        finals.append(node[w] if len(w) > 1 else n.AND(letter[w], ~c.wordc.at(-1), ~c.wordc.at(1)))
    groups = [n.OR(*finals[i:i + 256], force=True) for i in range(0, len(finals), 256)]
    hit = n.OR(*groups, force=True)
    apos, s_ = n.cls("'"), n.cls("sS")
    end = n.OR(n.AND(hit, ~c.wordc.at(1)), n.AND(s_, apos.at(-1), hit.at(-2), ~c.wordc.at(1)))
    return n.prop_left(end, c.wordc, 5)



def name_prefix_step(c):
    """At an upper-case letter that follows a surname prefix at the start of a word ("McKenzie", "MacKenzie", "DeLuca",
    "VanDyke", "FitzGerald"): the lower-to-upper step there is part of a name, not a CamelCase product."""
    n = c.n
    up, word = n.cls(UP), n.cls(AL)
    prefixes = ("Mc", "Mac", "De", "Di", "Da", "Du", "La", "Le", "Van", "Von", "Fitz")
    return n.AND(up, n.OR(*[n.AND(n.lit(p).at(-len(p)), ~word.at(-len(p) - 1)) for p in prefixes], force=True))


ID_CUES = ["lan", "claim", "claim no", "loan", "loan account", "id", "identifier", "number", "no", "vin", "plate", "pin", "cvv", "cvc", "cvc2", "cid", "serial", "iban", "account",
           "a/c", "acct", "routing", u("खाता संख्या"), u("खाता नंबर"), "cuenta", "kontonummer", "konto", "numéro de compte",
           "compte", "conta", "roll", "mrn", "roll no", "roll number", "imei", "imsi", "iccid", "uan", "abha", "epic", "voter id",
           "license", "licence", "policy", "record", "registration", "aadhaar", "pan", "passport", "insurance"]
# numbers introduced by these words describe things, not people
NOT_PERSONAL = ["version", "ver", "v", "android", "ios", "chrome", "firefox", "safari", "build", "release", "vat", "vat no",
                "cnpj", "gst no", "isin", "lei", "duns", "micr", "ts", "epoch", "unix", "timestamp", "seq", "offset", "pnr", "utr", "rrn", "txn", "txn id", "transaction id", "transaction", "request_id", "request id", "trace_id",
                "trace id", "span_id", "job_id", "correlation id", "awb", "asin", "isbn", "ean", "upc", "batch", "lot",
                "tracking code", "tracking number", "tracking", "sku", "version", "build",
                "timestamp", "invoice number", "invoice", "ticket", "reference", "ref", "model", "part number", "part", "release",
                "ifsc", "swift", "bic", "sort code", "chapter", "page", "section", "iso", "rfc", "error code", "error", "port",
                "return", "rma", "voucher", "complaint", "complaint no", "receipt", "receipt no", "case", "case no",
                "case number", "project", "cost centre", "cost center", "asset tag", "asset", "chargeback", "form", "booking",
                "booking ref", "confirmation", "confirmation number", "localizador", "referencia", "pedido", "factura", "commande",
                "facture", "bestellnummer", "rechnungsnummer", "aktenzeichen", "dtc", "msg", "message id", "routing",
                "routing number", "aba", "flight", "escalation", "incident", "bug", "issue", "jira", "sla", "advisory",
                "commit", "cve", "pr", "pull request", "changelog",
                "train", "coach", "berth", "seat", "gate", "terminal", "room", "petition", "writ petition", "suit", "appeal",
                "case file", "incident review",
                u("शिकायत संख्या"), u("संख्या"), u("ரசீது எண்"), u("எண்"), "application", "loan application", "policy no"]


HEALTH_TERMS = ("diabetes diabetic depression depressed anxiety bipolar schizophrenia ptsd adhd autism autistic dementia alzheimer "
                "epilepsy asthma cancer tumour tumor leukemia lymphoma hiv aids hepatitis tuberculosis covid pregnant pregnancy "
                "miscarriage abortion ivf infertility wheelchair deaf blind hearing-impaired disabled disability paralysed paralyzed "
                "amputee dyslexia stroke heart-attack hypertension obesity anorexia bulimia overdose self-harm suicidal addiction "
                "alcoholism rehab chemotherapy dialysis transplant brca1 brca2 truvada prep lithium suboxone methadone insulin "
                "metformin prozac sertraline fluoxetine antidepressant antiretroviral antipsychotic therapist psychiatrist "
                "psychiatry counselling counseling gay lesbian bisexual transgender trans queer nonbinary").split()
SPECIAL_TERMS = ("hindu muslim christian sikh jain buddhist jewish atheist dalit brahmin caste converted").split()


# ---- clinical text: context, morphology and dose neurons (no drug or disease list needed for most of it) ----------
# cues that mark a record ABOUT a patient (not a document about health in general)
MED_CUES = ("patient pt dx rx hx diagnosed prescribed allergies admitted discharged vitals mrn opd triage paciente "
            "ordonnance rezept मरीज रोगी நோயாளி").split() + ["chief complaint", "presents with", "presented with", "c/o",
            "lab results", "test results", "discharge summary", "case notes", "clinical notes", "known allergies", "doctor's note",
            "doctors note", "medical note", "sick note", "medical certificate", "fitness certificate", "manager's note", "hr note"]
DRUG_SUFFIXES = ("statin pril sartan olol dipine xaban gatran parin oxetine traline pram faxine azepam zolam prazole tidine "
                 "mycin cillin cycline floxacin ivir mab tinib triptan lukast formin gliptin glitazone gliflozin olone isone "
                 "terol tropium profen coxib setron peridol apine idone spirone barbital dronate thyroxine semide thiazide "
                 "oxacin azole").split()
COND_SUFFIXES = "itis osis emia aemia pathy algia plegia ectomy otomy plasty uria penia megaly carcinoma sarcoma".split()
COND_VETO = ("diagnosis prognosis empathy sympathy apathy telepathy antipathy homeopathy naturopathy osteopathy hypnosis "
             "osmosis symbiosis metamorphosis neurosis").split()
COND_HEADS = ("disorder disorders syndrome disease allergy allergies allergic fibrillation ideation attack attacks failure "
              "infection injury fracture insufficiency deficiency palsy sclerosis migraine migraines seizure seizures fever "
              "cough reflux arthritis asthma diabetes hypertension depression anxiety cancer tumour tumor stroke "
              "lesión lesion fractura enfermedad trastorno alergia asma krankheit störung allergie maladie "
              "ஆஸ்துமா दमा मधुमेह डायबिटीज कैंसर").split()
COND_ABBR = "CKD COPD AFib AF GERD IBS OCD GAD MDD T2DM T1DM DM2 UTI CHF CAD HTN PCOS PCOD ADHD PTSD HIV TB DVT MI".split()
COND_MODS = ("mild moderate severe early late chronic acute recurrent suspected known generalized generalised major minor "
             "bilateral persistent intermittent seasonal life-threatening early-onset late-onset borderline").split()
EPONYMS = "parkinson alzheimer crohn huntington hashimoto addison cushing graves tourette asperger bell raynaud hodgkin".split()
LABS = ("TSH LDL HDL ALT AST eGFR GFR Hb Hgb HbA1c A1c WBC RBC INR PSA CRP ESR FT4 T3 T4 BNP creatinine glucose "
        "cholesterol triglycerides ferritin platelets sodium potassium").split()
DOSE_FREQ = ("daily nightly bid tid qid od bd prn qhs qd once twice weekly monthly morning night stat").split()


ROLE_MAILBOX = ("support help helpdesk info sales billing payroll hr talent ops admin noreply no-reply donotreply contact team "
                "ethics grievance grievances complaints whistleblower whistleblowing safeguarding audit governance board secretariat "
                "registrar admissions alumni library facilities hostel exams examinations principal headteacher enquiries enquiry "
                "careers jobs press media legal privacy security abuse postmaster webmaster accounts accounting finance treasury "
                "reservas reservations bookings booking orders service customercare care feedback hello office reception "
                "frontdesk it devops dpo compliance procurement marketing partners investors ir recruiting recruitment "
                "notifications alerts newsletter enquiries inquiries returns shipping claims grievance nodal").split()
MONTHS_DAYS = ("jan feb mar apr may jun jul aug sep sept oct nov dec january february march april june july august september "
               "october november december mon tue tues wed thu thur thurs fri sat sun monday tuesday wednesday thursday "
               "friday saturday sunday").split()
PUBLIC_ROLES = ["justice", "judge", "hon'ble justice", "honourable justice", "honorable judge", "chief justice", "magistrate"]
PLACEHOLDER_NAMES = ["jane doe", "john doe", "joe bloggs", "fred bloggs", "max mustermann", "erika mustermann", "john q. public",
                     "jane roe", "richard roe", "baby doe", "ola nordmann", "juan pérez", "mario rossi"]


CHILD_CUES = ("son daughter child children kid kids student pupil ward parents parent pta roll vidyalaya preschool nursery "
              "kindergarten school teacher classmate classmates homework admission").split() + [
              "बेटा", "बेटी", "बच्चा", "மகன்", "மகள்", "வகுப்பு", "பள்ளி", "hijo", "hija", "alumno", "élève", "schüler"]


# Romanised Hindi / Urdu function words (closed class, like FUNCTION_WORDS): never a name, never a secret
HINDI_FUNCTION_WORDS = ("hai hain tha thi the ho hoga hogi hua hui hue hun hoon gaya gayi gaye aaya aayi aaye aa ja jao jana kar karo karna "
    "karke kiya kiye ki ka ke ko se mein me par pe tak aur ya lekin magar par phir fir toh to bhi hi na nahi nahin mat haan han ji "
    "mera meri mere tera teri tere uska uski uske unka unki unke hamara hamari humara humari aapka aapki aapke apna apni apne "
    "main mai hum tum aap woh wo yeh ye is us in un kya kyun kyon kaise kab kahan kahaan kaun kitna kitni kitne jo jab jaha jahan "
    "wahi wohi yahi wahan wahaan yahan yahaan ab abhi kal aaj parso baad pehle pahle saath sath liye wala wali wale waala "
    "likha likhi likhe bola boli bole boliye bolo batao bataiye bhejo bhejein bhejna bheja diya diye di do dena dijiye lena liya "
    "chalega chalegi chahiye raha rahi rahe sakta sakti sakte tha thay hota hoti hote badal purana purani naya nayi bas sirf "
    "bahut bohot thoda zyada kam accha achha theek thik sahi galat agar jaise jaisa waisa matlab yaar bhai behen didi sir "
    "madam kripya dhanyavad shukriya namaste arre arey acha haanji mujhe mujhko tumhe tumko unhe use isse usse inhe").split()


# English function words (closed class): never a name, whatever the capitalisation
FUNCTION_WORDS = ("a an the and or but if then else when while for nor so yet of in on at by to from with without into onto upon "
                  "over under above below about after before during since until than as is are was were be been being am do does "
                  "did have has had would should could might not no yes this that these those there here "
                  "it its he she they we you i me him her them us my your our their his hers ours theirs who whom whose which what "
                  "where why how all any each every some many much more most few other another such both either neither only own "
                  "same also just very too please thanks hello hi dear regards").split()


NOT_NAMES = set(FUNCTION_WORDS) | set("the and his her our you she him its who one two son man boy sir mum dad are was has had not but for all any can new old red big sun sky sea see say use try end key law art job day way war top low high long short in on at an as is it be do go no so to up us we me my by or of if am".split())


# Word endings that are frequent in personal names across naming traditions and rare in English words.
# They are written into convolution templates that fire at the end of a token: name morphology, not a name list.
NAME_ENDINGS = ("ansh esh ish endra indra deep preet jeet jit raj iki ika ita anth nath appa amma bhai ben ji priya "
                "lakshmi kumar kumari shree shri devi deva dev ravi rao reddy aiah ayya appan oslav slav ovic ovich evich enko "
                "escu opoulos akis ides sson sen stein berg mann ez ini etti ucci elli ova eva ski ska wicz czyk uddin ullah "
                "ullah allah abad ani ara ina iya ya ia ah ana ya ika ova ovna ikh vili adze uk yuk chuk ko oglu "
                "zadeh pour nejad iyan yan ian ishvili guchi moto hara mura kawa yama oka ko mi ki ji shi suke taro "
                "bayev ov ev in ina sky nova ito ida").split()


# Word endings frequent in place names (towns, districts, regions, countries) and rare in English words.
PLACE_ENDINGS = ("pur pura puram abad nagar garh ganj kota kot halli palli pally pet peth gaon gaam wadi wada guda bad "
                 "ville ton town burg burgh berg borough shire stan land ia istan grad sk insk ovsk ford by wick chester "
                 "caster cester mouth field ham stad dorf heim hausen furt bruck ingen ach au eux ac ignan ière ville "
                 "aka ata ka ra la pradesh desh kerala nadu bengal haryana gujarat sthan khand tal pally konda giri "
                 "dam wijk sund havn holm by valley vale port haven bay cove ridge hill hills springs falls").split()


US_STATES = ("AL AK AZ AR CA CO CT DE FL GA IA IL KS KY LA MA MD MI MN MO MT NC ND NE NH NJ NM NV NY OH PA RI SC SD "
             "TN TX UT VA VT WA WI WV WY DC").split()
AMBIGUOUS = {"PASSPORT": 2, "USERNAME": 2}

__all__ = ['name_prefix_step', 'DATA_DIR', 'Net', 'Sig', 'HI', 'byteset', 'parse_var', 'AL', 'AMBIGUOUS', 'AN', 'CHILD_CUES', 'CITIES', 'COND_ABBR', 'COND_HEADS', 'COND_MODS', 'COND_SUFFIXES', 'COND_VETO', 'COUNTRIES', 'Ctx', 'D', 'DAY3', 'DOSE_FREQ', 'DRUG_SUFFIXES', 'EPONYMS', 'EXTRA_WORDS', 'FUNCTION_WORDS', 'HEALTH_TERMS', 'HEXC', 'HINDI_FUNCTION_WORDS', 'ID_CUES', 'LABS', 'LO', 'MED_CUES', 'MON3', 'MONTHS', 'MONTHS_ANY', 'MONTHS_DAYS', 'NAME_ENDINGS', 'NOT_NAMES', 'NOT_PERSONAL', 'PLACEHOLDER_NAMES', 'PLACE_ENDINGS', 'PUBLIC_ROLES', 'ROLE_MAILBOX', 'SEC_WORDS', 'SPECIAL_TERMS', 'STATE_NAMES', 'STREET_SUFFIX', 'TITLES', 'UP', 'US_STATES', 'WORD', 'cue', 'general', 'said', 'u', 'word_tree', 'string', 'os']
