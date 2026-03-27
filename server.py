#!/usr/bin/env python3
import json, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DATA_FILE    = os.path.join(os.path.dirname(__file__), 'data.json')
DATABASE_URL = os.environ.get('DATABASE_URL')
AUTH_TOKEN   = os.environ.get('AUTH_TOKEN', 'ta-secure-2025')

# ── STORAGE ──────────────────────────────────────────────────────────
if DATABASE_URL:
    import psycopg2

    def _conn():
        return psycopg2.connect(DATABASE_URL, sslmode='require')

    def _init():
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute('''CREATE TABLE IF NOT EXISTS ta_appdata
                               (id INT PRIMARY KEY, data TEXT NOT NULL)''')
                cur.execute('''INSERT INTO ta_appdata (id, data)
                               VALUES (1, %s) ON CONFLICT (id) DO NOTHING''',
                            [json.dumps({'positions': [], 'candidates': []})])
                c.commit()
    _init()

    def load_data():
        try:
            with _conn() as c:
                with c.cursor() as cur:
                    cur.execute('SELECT data FROM ta_appdata WHERE id=1')
                    row = cur.fetchone()
                    return json.loads(row[0]) if row else {'positions': [], 'candidates': []}
        except Exception as e:
            print(f'[DB READ ERROR] {e}')
            return {'positions': [], 'candidates': []}

    def save_data(data):
        try:
            with _conn() as c:
                with c.cursor() as cur:
                    cur.execute('UPDATE ta_appdata SET data=%s WHERE id=1', [json.dumps(data)])
                    c.commit()
        except Exception as e:
            print(f'[DB WRITE ERROR] {e}')

else:
    def load_data():
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        return {'positions': [], 'candidates': []}

    def save_data(data):
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
# ─────────────────────────────────────────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Auth-Token')

    def do_OPTIONS(self):
        self.send_response(200); self.send_cors(); self.end_headers()

    def check_auth(self):
        token = self.headers.get('X-Auth-Token', '')
        return token == AUTH_TOKEN

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/data':
            if not self.check_auth():
                self.send_response(401); self.end_headers(); return
            body = json.dumps(load_data()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors(); self.end_headers()
            self.wfile.write(body)
        elif path in ('/', '/index.html'):
            with open(os.path.join(os.path.dirname(__file__), 'index.html'), 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_cors(); self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(length)

        if path == '/api/data':
            if not self.check_auth():
                self.send_response(401); self.end_headers(); return
            save_data(json.loads(body_bytes))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors(); self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404); self.end_headers()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8082))
    print(f'TA Tracker running on port {port}')
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
