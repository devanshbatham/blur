// node tools/serve.mjs [port] [dir]      a minimal static file server for site/, bound to 127.0.0.1 only.
// Any other static file server works as well; this one exists so that the demo needs nothing but Node.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const port = +(process.argv[2] || 8787), root = path.resolve(process.argv[3] || "site");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".bin": "application/octet-stream" };
http.createServer((req, res) => {
  let rel;
  try { rel = decodeURIComponent(new URL(req.url, "http://x").pathname); } catch { rel = "/"; }
  if (rel.endsWith("/")) rel += "index.html";
  const file = path.join(root, path.normalize(rel));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (err, body) => {
    if (err) { res.writeHead(404, { "Content-Type": "text/plain" }).end("not found\n"); return; }
    const type = TYPES[path.extname(file)] || (path.basename(file) === "info" ? "application/json" : "application/octet-stream");
    res.writeHead(200, { "Content-Type": type, "Content-Length": body.length, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer" }).end(body);
  });
}).listen(port, "127.0.0.1", () => console.log(`serving ${root} at http://127.0.0.1:${port}/`));
