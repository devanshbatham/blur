# Bundled data: sources and licences

Every data file under `blur/data/`, `tests/` and `demo/` is listed here with where it came
from and under what terms, as far as the project's own records say. The records are
the doc strings of `tools/make_wordlist.py` and `tools/make_names.py`. Where those records do not settle a
point it is marked **unverified**; nothing here was checked against the upstream projects when the release
was packaged, and nothing below is legal advice.

The code is MIT-licensed: see `LICENSE`. The data below keeps its own terms.

## Compiled into the model (`blur/data/`)

These files are read by `blur/general/` when the model is built, so `web/model-*.bin`
are derived from them.

| file | contents | source | licence |
|---|---|---|---|
| `words10.txt`, `words20.txt`, `words35.txt`, `words50.txt` | lower-case English words up to SCOWL size 10, 20, 35, 50 | SCOWL (Spell Checker Oriented Word Lists), files `english/american/british/british_z-words.*`, filtered by `tools/make_wordlist.py` | "permissive licence" according to the journal and the builder, which point to SCOWL's own `Copyright` file. That file is not included here. Exact terms and the required notice: **unverified** |
| `given.txt` | given names, ASCII-folded, lower case | built by `tools/make_names.py` from (1) `sigpwned/popular-names-by-country-dataset` and (2) `nam_dict.txt` by Joerg Michael as shipped in the `gender-guesser` Python package, names with frequency class 5 or more in at least one country | (1) CC0 according to the builder; (2) GNU Free Documentation License according to the builder. Whether the shipped file was built with the name dictionary (the default) or with `NAMDICT=0`: **unverified**, assume it is included. The GFDL version: **unverified** |
| `surnames.txt` | surnames, ASCII-folded, lower case, minus anything in `given.txt` | built by `tools/make_names.py` from `sigpwned/popular-names-by-country-dataset` and the most frequent US Census 2010 surnames (20,000 by default) | CC0 and public domain according to the builder; **unverified** upstream |
| `surnames_ranked.txt` | the 5,000 most frequent US Census 2010 surnames, most frequent first | US Census Bureau 2010 surname list, via `tools/make_names.py` | public domain according to the builder; **unverified** upstream |
| `bip39.txt` | 2,048 English words, used to recognise wallet seed phrases | it has the size and the first words of the BIP-39 English word list; the journal and the tools do not record where the file was taken from | **unverified** |

Only `words35.txt` (general profile), `words20.txt` (ai4p profile) and `words50.txt` are read by default;
`words10.txt` is used when the build is run with `LEX=10`.

Also compiled into the model, but typed into the program rather than bundled as files: honorifics, words
for secondary addresses, street suffixes and UK nation codes that were read off the development split of
ai4privacy/pii-masking-300k. See the last section.

## Demo documents

| file | contents | source | licence |
|---|---|---|---|
| `demo/examples.json` | 40 synthetic documents shown as examples in the demo | test split of `nvidia/Nemotron-PII` | CC BY 4.0 |

## Test data (`tests/`)

| file | contents | source | licence |
|---|---|---|---|
| `fpfn/negatives.json` | 600 texts without personal data | generated from hand-written pools | written for this project |
| `fpfn/positives.json` | carrier sentences with fabricated values | generated; values use reserved ranges where they exist | written for this project |
| `guide_cases.json` | one case per row of the project's edge-case guide | this project | written for this project |
| `spec3/cases.json` | exact-output acceptance cases | this project | written for this project |
| `http/`, `precision/`, `secrets_edge/` | HTTP traffic, contrastive pairs, secret containers | this project | written for this project |
| `tricky/*.json` | paragraph sets with mask and keep items (development and blind) | this project | written for this project |

All people, addresses, numbers and credentials in these files are meant to be invented. The key-shaped
strings are fixtures for the secrets detector (several are the providers' published example keys).

## Used for evaluation, not redistributed

| dataset | used by | terms |
|---|---|---|
| `ai4privacy/pii-masking-300k` | `eval/make_dev2.py`, `eval/suite.py` | licence field "other": academic use with citation; commercial use needs a licence from the authors. **No row of it is in this repository.** The frozen samples the scripts write to `data/*.jsonl` are excluded from the release and ignored by git; do not commit them. The closed word lists mentioned above were read off its development split |
| `nvidia/Nemotron-PII` | `eval/suite.py` | CC BY 4.0; downloaded at run time (two samples are bundled, see above) |
| `gretelai/gretel-pii-masking-en-v1` | `eval/suite.py` | Apache-2.0 according to the journal; downloaded at run time, not bundled |

## Project licence and the name list (added 2026-11-17)

The code in this repository is released under the MIT licence (`LICENSE`). That choice does not change the terms of
bundled data:

- `blur/data/given.txt` is built by `tools/make_names.py` from a CC0 list and, by default, from the name dictionary
  shipped with `gender-guesser` (`nam_dict.txt`, GNU Free Documentation License). Of its 15,394 names only 1,282 come
  from the CC0 list alone (measured by rebuilding with `NAMDICT=0`).
- `web/model-general.bin` contains a compiled form of that list, so the model file is derived from GFDL material as
  well as from MIT code. Anyone redistributing the model should treat the name list and the weights compiled from it
  as carrying the GFDL's terms, or rebuild with `NAMDICT=0` (far fewer first names, lower recall) or with another
  name source they have the rights to.

This note records the facts; it is not legal advice.
