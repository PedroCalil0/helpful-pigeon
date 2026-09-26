# server.py — coloca em C:\pigeon\ ao lado do index.html
import http.server
import socketserver
import urllib.request
import urllib.parse
import urllib.error
import ssl
import sys
from pathlib import Path

# ============================================================
# CONFIGURAÇÃO
# ============================================================
PORT     = 8080
TOKEN    = "meu-segredo-super-longo"          # muda se quiseres (tem de bater com o index.html)
BASE_DIR = Path(__file__).parent.resolve()   # pasta onde está este ficheiro

# Headers que impedem o iframe de carregar — removidos da resposta
STRIP = {
    "x-frame-options",
    "content-security-policy",
    "content-security-policy-report-only",
    "cross-origin-opener-policy",
    "cross-origin-embedder-policy",
    "cross-origin-resource-policy",
    "strict-transport-security",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}


# ============================================================
# HANDLER
# ============================================================
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    # ---------- GET ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # Rota do proxy
        if parsed.path == "/proxy":
            self.handle_proxy(parsed)
            return

        # Rota raiz → index.html
        if parsed.path in ("", "/"):
            self.path = "/index.html"

        super().do_GET()

    # ---------- POST ----------
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/proxy":
            self.handle_proxy(parsed)
        else:
            self.send_error(405, "Method Not Allowed")

    # ---------- PROXY ----------
    def handle_proxy(self, parsed):
        q      = urllib.parse.parse_qs(parsed.query)
        token  = (q.get("token") or [""])[0]
        target = (q.get("url")   or [""])[0]

        # Validação do token
        if token != TOKEN:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"Token invalido")
            return

        # Validação do URL
        if not target:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"Falta parametro url")
            return

        # Faz o pedido ao site de destino
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

            # Contexto SSL permissivo (aceita certificados inválidos/self-signed)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                self.send_response(resp.status)

                for k, v in resp.headers.items():
                    if k.lower() in STRIP:
                        continue
                    self.send_header(k, v)

                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Lê e envia em blocos (streaming)
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

    # ---------- LOG ----------
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.address_string(), fmt % args))


# ============================================================
# ARRANQUE
# ============================================================
if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print("=" * 60)
        print(f"  Helpful Pigeon — servidor a correr")
        print(f"  Local:   http://localhost:{PORT}")
        print(f"  Rede:    http://0.0.0.0:{PORT}")
        print(f"  Token:   {TOKEN}")
        print(f"  Pasta:   {BASE_DIR}")
        print("=" * 60)
        print("  Ctrl+C para parar.")
        print()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor parado.")
