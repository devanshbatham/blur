<p align="center"><img src="assets/logo.svg" alt="blur" width="360"></p>

<p align="center">Hand-written rules for masking PII and secrets, compiled into a 609 KB neural network.</p>

<p align="center"><a href="https://devanshbatham.github.io/blur/">Live demo</a></p>

---

Finds names, addresses, e-mails, phones, dates, account numbers, IDs, credentials and online identifiers.
It is a rule-based detector, not a trained model: hand-written rules (value formats, cue words, name and word lists)
are compiled into a sparse network of 1,061,528 ternary (±1) weights that scans raw bytes. Runs offline in the browser or Node.

## CLI

```bash
npm install -g .
echo "Call Priya Sharma on +91 98765 43210" | blur
# Call [private_person] on [private_phone]

blur -n report.txt                        # numbered: [PERSON_1], [EMAIL_1]
blur --json --only secret logs/*.txt      # JSON findings, secrets only
blur --char '*' -o masked.txt notes.txt   # mask per character
```

## SDK

```js
import { createBlur } from "blur";

const blur = await createBlur();           // { pipeline: true } keeps one placeholder per person
blur.mask("Call Priya on +91 98765 43210").text;   // "Call [private_person] on [private_phone]"
blur.detect("mail priya@example.org");              // [{ start, end, label: "private_email", text }]
```

Options: `only`, `keep`, `numbered`, `char`. Types in `sdk/index.d.ts`.

## Results

Closely matches OpenAI's 2.8 GB [privacy-filter](https://openai.com/index/introducing-openai-privacy-filter/), and sometimes beats it, at ~1/4,600th the size.

## Build

```bash
make model    # write web/model-general.bin (Python 3, numpy, scipy)
make test     # evaluation suites
make demo     # browser demo on http://127.0.0.1:8787
make binary   # single executable dist/blur (Bun)
```

## License

MIT. Bundled word lists keep their own terms: [DATA_LICENSES.md](DATA_LICENSES.md).
