PY    ?= uv run --with numpy --with scipy python
NODE  ?= node
PORT  ?= 8787
MODEL ?= web/model-general.bin

.PHONY: help demo model binary test test-unit

help:
	@echo "make demo        serve the browser demo on http://127.0.0.1:$(PORT)/"
	@echo "make model       compile blur/ into $(MODEL)"
	@echo "make binary      single-file executable dist/blur with the model embedded (needs Bun)"
	@echo "make test        evaluation suites (network alone and full pipeline)"
	@echo "make test-unit   circuit tests"

demo:
	tools/run.sh --port $(PORT)

model:
	$(PY) tools/export_model.py --profile general --out $(MODEL)

binary:
	$(NODE) tools/build_binary.mjs

test:
	$(NODE) tools/check_size.mjs
	$(NODE) tests/sdk/run.mjs
	$(NODE) tests/eval/run.mjs
	$(NODE) tests/secrets_context/run.mjs $(MODEL)
	$(NODE) tests/http/run.mjs $(MODEL)
	$(NODE) tests/precision/run.mjs $(MODEL)
	CASES=domains.json $(NODE) tests/precision/run.mjs $(MODEL)
	CASES=urls.json $(NODE) tests/precision/run.mjs $(MODEL)
	$(NODE) tests/secrets_edge/run.mjs $(MODEL)
	STANDALONE=1 $(NODE) tests/secrets_edge/run.mjs $(MODEL)
	CASES=more.json $(NODE) tests/secrets_edge/run.mjs $(MODEL)
	CASES=more.json STANDALONE=1 $(NODE) tests/secrets_edge/run.mjs $(MODEL)
	PII_DATES=0 $(NODE) tests/guide_run.mjs $(MODEL)
	PII_DATES=0 $(NODE) tests/spec3/run.mjs $(MODEL)
	PII_DATES=0 $(NODE) tests/fpfn/run.mjs $(MODEL)
	$(NODE) tests/tricky_run.mjs $(MODEL) dev3

test-unit:
	uv run --with numpy --with scipy --with pytest python -m pytest -q tests
