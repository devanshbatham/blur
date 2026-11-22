import glob
"""Live demo server: left pane text, right pane masked text. Inference runs here with the
Python reference engine; the model is rebuilt automatically whenever the circuit files change.
    PROFILE=general .venv/bin/python demo/server.py 8787"""
import json, os, re, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("PROFILE", "general")
WEB_JS = re.compile(r"/(pipeline/)?[a-z_]+\.js")                                   # files served from web/
def watched():                                                   # every module of the program, listed fresh each time
    return glob.glob(os.path.join(ROOT, "blur", "**", "*.py"), recursive=True)
STATE = {"engine": None, "info": {}, "stamp": 0, "building": False, "error": None}
LOCK = threading.Lock()


def stamp():
    # (a file renamed or deleted since the last look is skipped, so a refactor never stops the watcher)
    times = []
    for f in watched():
        try: times.append(os.path.getmtime(f))
        except OSError: pass
    return max(times) if times else 0


def build():
    STATE["building"] = True
    try:
        # a fresh import of the whole program: every blur module is dropped and loaded again, so new files need no list
        for name in [m for m in sys.modules if m == "blur" or m.startswith("blur.")]:
            del sys.modules[name]
        import blur.dsl, blur.engine, blur.general
        s = stamp()
        t0 = time.time()
        model = blur.general.build()
        eng = blur.engine.Engine(model)
        st = blur.dsl.stats(model)
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import export_model
        blob = export_model.encode(model)
        STATE["bin"] = blob
        with LOCK:
            STATE.update(engine=eng, stamp=s, error=None, info={
                "built": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()), "neurons": st["neurons"],
                "weights": st["connections"], "labels": st["labels"], "build_seconds": round(time.time() - t0, 1), "bytes": len(blob), "stamp": s,
                "profile": os.environ["PROFILE"]})
    except Exception as e:  # keep serving the previous model
        STATE["error"] = f"{type(e).__name__}: {e}"
    STATE["building"] = False


def watcher():
    while True:
        time.sleep(5)
        try:
            if stamp() != STATE["stamp"] and not STATE["building"]:
                build()
        except OSError:
            pass


def detect_many(texts):
    """One forward pass over a batch of texts. Returns (list of span lists in character offsets, ms)."""
    datas = [t.encode("utf-8") for t in texts]
    with LOCK:
        eng = STATE["engine"]
        t0 = time.time()
        all_spans = eng.batch_spans(datas)
        ms = (time.time() - t0) * 1000
    results = []
    for data, spans in zip(datas, all_spans):
        pos, cnt = [], 0
        for b in data:                       # byte offset -> character offset
            if (b & 0xC0) != 0x80:
                cnt += 1
            pos.append(cnt - 1)
        out = [[pos[a], pos[b - 1] + 1, lab] for a, b, lab in spans if not lab.startswith(("kind:", "_"))]
        out.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        merged = []
        for sp in out:
            if not merged or sp[0] >= merged[-1][1]:
                merged.append(sp)
        results.append(merged)
    return results, ms


def detect(text):
    results, ms = detect_many([text])
    return results[0], ms


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] in ("/info", "/info.json"):
            self._send(200, json.dumps({**STATE["info"], "building": STATE["building"], "error": STATE["error"]}).encode(), "application/json")
        elif self.path.startswith("/model.bin"):
            self._send(200, STATE.get("bin", b""), "application/octet-stream")
        elif self.path == "/worker.js":
            self._send(200, open(os.path.join(ROOT, "demo", "worker.js"), "rb").read(), "text/javascript; charset=utf-8")
        elif self.path.split("?")[0] in ("/app", "/app.html"):
            self._send(200, open(os.path.join(ROOT, "demo", "index.html"), "rb").read(), "text/html; charset=utf-8")
        elif WEB_JS.fullmatch(self.path.split("?")[0]) and os.path.isfile(os.path.join(ROOT, "web", self.path.split("?")[0][1:])):
            # the runtime and the pipeline modules (only "/name.js" or "/pipeline/name.js": no other path can be read)
            self._send(200, open(os.path.join(ROOT, "web", self.path.split("?")[0][1:]), "rb").read(), "text/javascript; charset=utf-8")
        elif self.path == "/examples.json":
            self._send(200, open(os.path.join(ROOT, "demo", "examples.json"), "rb").read(), "application/json")
        else:
            self._send(200, open(os.path.join(ROOT, "demo", "index.html"), "rb").read(), "text/html; charset=utf-8")


if __name__ == "__main__":
    build()
    threading.Thread(target=watcher, daemon=True).start()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    host = os.environ.get("HOST", "127.0.0.1")       # HOST=0.0.0.0 to serve other machines on the network
    print("serving on", f"http://{host}:{port}/", STATE["info"], STATE["error"], flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()
