#!/usr/bin/env bash
# One command to see the demo:   tools/run.sh [--port N] [--rebuild] [--live]
#
#   (default)   reuse web/model-general.bin if it exists, otherwise build it; refresh site/ if needed; serve site/
#               on http://127.0.0.1:PORT/ (default port 8787). Inference runs in your browser.
#   --rebuild   rebuild the model from the Python program first (needs uv, or python3 with numpy and scipy).
#   --live      run demo/server.py instead: it rebuilds the model whenever a file in blur/ changes.
#               It listens on 127.0.0.1; set HOST=0.0.0.0 to serve other machines on the network.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PORT="${PORT:-8787}"; REBUILD=0; LIVE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="${2:?--port needs a number}"; shift 2 ;;
    --rebuild) REBUILD=1; shift ;;
    --live) LIVE=1; shift ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "run.sh: unknown option $1 (try --help)" >&2; exit 2 ;;
  esac
done
case "$PORT" in ''|*[!0-9]*) echo "run.sh: the port must be a number" >&2; exit 2 ;; esac
MODEL=web/model-general.bin
have() { command -v "$1" >/dev/null 2>&1; }

# The Python used to build the model: uv fetches numpy and scipy by itself; otherwise python3 must have them.
python_cmd() {
  if have uv; then echo "uv run --with numpy --with scipy python"
  elif have python3 && python3 -c 'import numpy, scipy' 2>/dev/null; then echo "python3"
  else return 1; fi
}
need_python() {
  PY="$(python_cmd)" || {
    echo "run.sh: building the model needs either uv (https://docs.astral.sh/uv/) or python3 with numpy and scipy." >&2
    echo "        Without Python you can still serve the prebuilt demo: any static file server on site/ will do." >&2
    exit 1; }
}

if [ "$LIVE" = 1 ]; then
  need_python
  echo "run.sh: starting the development server (it builds the model first, a few seconds)."
  echo "run.sh: open http://127.0.0.1:$PORT/   (Ctrl-C stops it)"
  PROFILE=general exec $PY demo/server.py "$PORT"
fi

if [ "$REBUILD" = 1 ] || [ ! -f "$MODEL" ]; then
  need_python
  echo "run.sh: building $MODEL"
  $PY tools/export_model.py --profile general --out "$MODEL"
else
  echo "run.sh: reusing $MODEL ($(wc -c < "$MODEL" | tr -d ' ') bytes); pass --rebuild to build it again"
fi

# site/ is the demo as static files, generated here (and regenerated when the model or the page changed).
stale=0
[ -f site/info.json ] && cmp -s "$MODEL" site/model.bin || stale=1
for f in demo/*.html demo/*.js demo/*.json web/*.js; do cmp -s "$f" "site/$(basename "$f")" || stale=1; done
if [ "$stale" = 1 ]; then
  have node || { echo "run.sh: site/ is out of date and regenerating it needs Node 18 or newer." >&2; exit 1; }
  node tools/build_site.mjs site
fi

URL="http://127.0.0.1:$PORT/"
if have python3; then
  echo "run.sh: demo at $URL   (Ctrl-C stops it)"
  exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory site
elif have node; then
  echo "run.sh: demo at $URL   (Ctrl-C stops it)"
  exec node tools/serve.mjs "$PORT" site
else
  echo "run.sh: no python3 and no node found. Serve the site/ directory with any static file server instead." >&2
  exit 1
fi
