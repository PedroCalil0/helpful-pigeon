# server.py — coloca em C:\pigeon\ ao lado do index.html
import http.server
import socketserver
import urllib.request
import urllib.parse
import urllib.error
import ssl
import sys
from pathlib import Path

PORT     = 8080
TOKEN    = "meu-segredo-super-longo"
BASE_DIR = Path(__file__).parent.resolve()

STRIP = {
    "x-frame-options", "content-security-policy",
    "content-security-policy-report-only", "cross-origin-opener-policy",
    "cross-origin-embedder-policy", "cross-origin-resource-policy",
    "strict-transport-security", "connection", "keep-alive",
    "proxy-authenticate", "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade", "content-encoding", "content-length",
}

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/proxy":
            self.handle_proxy(parsed)
            return
        if parsed.path in ("", "/"):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/proxy":
            self.handle_proxy(parsed)
        else:
            self.send_error(405, "Method Not Allowed")

    def handle_proxy(self, parsed):
        q      = urllib.parse.parse_qs(parsed.query)
        token  = (q.get("token") or [""])[0]
        target = (q.get("url")   or [""])[0]

        if token != TOKEN:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"Token invalido")
            return

        if not target:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"Falta parametro url")
            return

        # Converte links do GitHub "blob" para "raw" (evita 302 intermédio)
        if "github.com" in target and "/blob/" in target:
            target = target.replace("github.com", "raw.githubusercontent.com")
            target = target.replace("/blob/", "/")

        try:
            req = urllib.request.Request(
                target,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                },
            )
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                final_url = resp.url          # ← URL depois dos redirects

                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in STRIP:
                        continue
                    self.send_header(k, v)

                # Cabeçalho que o Helpful Pigeon usa para atualizar o <base>
                self.send_header("X-Final-URL", final_url)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Expose-Headers", "X-Final-URL")
                self.end_headers()

                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(("HTTP " + str(e.code) + ": " + str(e.reason)).encode())

        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(("Erro no proxy: " + str(e)).encode())

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print("=" * 60)
        print("  Helpful Pigeon — servidor a correr")
        print(f"  Local:   http://localhost:{PORT}")
        print(f"  Rede:    http://0.0.0.0:{PORT}")
        print(f"  Token:   {TOKEN}")
        print(f"  Pasta:   {BASE_DIR}")
        print("=" * 60)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor parado.")
