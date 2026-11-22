"""Build blur/data/words<N>.txt from SCOWL (see data/scowl/Copyright; permissive licence).
Usage: python tools/make_wordlist.py 10"""
import glob, re, sys
size = int(sys.argv[1])
words = set()
for f in glob.glob("data/scowl/final/*"):
    m = re.match(r".*/(english|american|british|british_z)-words\.(\d+)$", f)
    if m and int(m.group(2)) <= size:
        words |= {w.strip().lower() for w in open(f, encoding="latin-1") if w.strip()}
words = sorted(w for w in words if re.fullmatch(r"[a-z]{2,}", w))
open(f"blur/data/words{size}.txt", "w").write("\n".join(words) + "\n")
print(len(words), "words")
