"""Given-name and surname lists.
- sigpwned/popular-names-by-country-dataset (CC0): given names and surnames.
- gender-guesser's nam_dict.txt by Joerg Michael (GNU Free Documentation License): given names
  that are frequent in at least one country (frequency class >= MINFREQ). LICENCE NOTE: shipping
  weights derived from this list means complying with the GFDL; drop it with NAMDICT=0."""
import csv, os, re, unicodedata
MINFREQ = int(os.environ.get("MINFREQ", "5"))
def fold(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
def load(f):
    out = set()
    for row in csv.DictReader(open("data/" + f, encoding="utf-8")):
        nm = fold(row.get("Romanized Name") or row.get("Localized Name") or "")
        if re.fullmatch(r"[a-z]{3,}", nm): out.add(nm)
    return out
g, s = load("common-forenames-by-country.csv"), load("common-surnames-by-country.csv")
if os.environ.get("NAMDICT", "1") == "1":
    import gender_guesser
    p = os.path.join(os.path.dirname(gender_guesser.__file__), "data", "nam_dict.txt")
    for line in open(p, encoding="iso8859-1"):
        if line[0] in "#=" or len(line) < 86: continue
        parts = line[:30].split()
        if len(parts) < 2: continue
        freqs = [int(ch, 16) for ch in line[30:85] if ch.strip() and ch in "0123456789ABCDEF"]
        nm = fold(parts[1])
        if freqs and max(freqs) >= MINFREQ and re.fullmatch(r"[a-z]{3,}", nm): g.add(nm)
# US Census 2010 surnames (public domain), most frequent first
if os.path.exists("data/census_surnames.txt"):
    s |= {w for w in open("data/census_surnames.txt").read().split()[:int(os.environ.get("NSUR", "20000"))] if len(w) >= 3}
if os.path.exists("data/census_surnames.txt"):
    open("blur/data/surnames_ranked.txt", "w").write("\n".join(open("data/census_surnames.txt").read().split()[:5000]) + "\n")
s -= g
open("blur/data/given.txt", "w").write("\n".join(sorted(g)) + "\n")
open("blur/data/surnames.txt", "w").write("\n".join(sorted(s)) + "\n")
print(len(g), "given;", len(s), "surnames")
