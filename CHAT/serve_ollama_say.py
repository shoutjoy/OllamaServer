"""Loopback-only launcher; no arbitrary command execution or arbitrary proxy targets."""
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parent
PORT = 8767
# Match the desktop settings location, including packaged builds.
sys.path.insert(0, str(ROOT.parent))
from core import Client, chat_performance, effective_performance, open_url
SETTINGS = ((Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'OllamaDesk')
            if getattr(sys, 'frozen', False) else ROOT.parent / '.data') / 'settings.json'
CLIENTS = {engine: Client(engine) for engine in ('ollama', 'lemonade')}


def optimized_payload(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('model'), str):
        raise ValueError('모델을 선택하세요.')
    try:
        saved = json.loads(SETTINGS.read_text('utf-8'))
        settings = effective_performance(saved, payload['model'])
    except (OSError, ValueError, TypeError, AttributeError):
        settings = effective_performance({}, payload['model'])
    defaults = chat_performance(settings, payload['model'])
    # Explicit CHAT generation choices retain precedence.
    defaults['options'].update(payload.get('options') or {})
    return dict(defaults, **{k: v for k, v in payload.items() if k != 'options'},
                options=defaults['options'])


def list_models():
    result = selected_client().get('/api/tags')
    try:
        result['default_model'] = json.loads(SETTINGS.read_text('utf-8')).get('model', '')
    except (OSError, ValueError):
        pass
    return result


def selected_client():
    try:
        saved = json.loads(SETTINGS.read_text('utf-8'))
    except (OSError, ValueError):
        saved = {}
    return CLIENTS.get(saved.get('engine'), CLIENTS['ollama'])

class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *args):
        # pythonw.exe has no stderr; BaseHTTPRequestHandler's default logger
        # would fail before an HTTP response can be written.
        pass

    def allowed(self):
        hosts = {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
        origin = self.headers.get('Origin')
        parsed = urlsplit(origin or '')
        trusted = (not origin or origin == 'https://mdproviewer.vercel.app'
                   or (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')))
        return self.headers.get('Host') in hosts and trusted

    def end_headers(self):
        if self.allowed() and self.headers.get('Origin'):
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
            if self.headers.get('Access-Control-Request-Private-Network') == 'true':
                self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_OPTIONS(self):
        if not self.allowed():
            return self.send_error(403)
        self.send_response(204)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def api_path(self):
        return self.path.removeprefix('/ollama')

    def send_data(self, status, data, content_type='application/json; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.allowed():
            return self.send_error(403)
        try:
            if self.path in ('/', '/ollama-say.html'):
                self.send_data(200, (ROOT / 'ollama-say.html').read_bytes(), 'text/html; charset=utf-8')
            elif self.api_path() == '/api/tags':
                self.send_data(200, json.dumps(list_models(), ensure_ascii=False).encode())
            elif self.api_path() in ('/api/ps', '/api/version'):
                result = selected_client().get(self.api_path())
                self.send_data(200, json.dumps(result, ensure_ascii=False).encode())
            elif self.path.startswith('/academic/arxiv?'):
                params = parse_qs(urlsplit(self.path).query)
                query = (params.get('q') or [''])[0].strip()
                count = min(100, max(1, int((params.get('count') or ['10'])[0])))
                if not query or len(query) > 500:
                    return self.send_error(400)
                target = f'https://export.arxiv.org/api/query?search_query=all:{quote(query)}&start=0&max_results={count}&sortBy=relevance'
                request = Request(target, headers={'Accept': 'application/atom+xml', 'User-Agent': 'OllamaSay/1.0'})
                with urlopen(request, timeout=30) as response:
                    self.send_data(200, response.read(4_000_000), 'application/atom+xml; charset=utf-8')
            else:
                self.send_error(404)
        except Exception as exc:
            self.send_data(503, json.dumps({'error': str(exc)}, ensure_ascii=False).encode())

    def do_POST(self):
        if not self.allowed():
            return self.send_error(403)
        path = self.api_path()
        if path not in ('/api/chat', '/api/generate', '/api/show'):
            return self.send_error(404)
        started = False
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 4_000_000:
                return self.send_error(413)
            payload = json.loads(self.rfile.read(size))
            client = selected_client()
            if path == '/api/show':
                result = client.post(path, payload)
                return self.send_data(200, json.dumps(result, ensure_ascii=False).encode())
            payload = optimized_payload(payload)
            if payload.get('stream') is False:
                if path == '/api/chat':
                    payload = client.prepare_chat(payload)
                result = client.post(path, payload)
                return self.send_data(200, json.dumps(result, ensure_ascii=False).encode())
            # Delay response headers until upstream produces a valid first item.
            # This allows a known draft crash to recover before a 200 response.
            for item in client.stream(path, payload):
                if not started:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/x-ndjson')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    started = True
                    self.close_connection = True
                self.wfile.write((json.dumps(item, ensure_ascii=False) + '\n').encode())
                self.wfile.flush()
            if not started:
                raise RuntimeError('서버 응답 없이 연결이 종료되었습니다.')
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            if not started:
                self.send_data(502, json.dumps({'error': str(exc)}).encode())
            else:
                self.wfile.write((json.dumps({'error': str(exc)}) + '\n').encode())
                self.wfile.flush()

def create_server():
    return ThreadingHTTPServer(('127.0.0.1', PORT), Handler)


def serve(open_browser=True):
    server = create_server()
    if getattr(os.sys, 'stdout', None) is not None:
        print(f'Ollama Say: http://127.0.0.1:{PORT} (Ctrl+C to stop)', flush=True)
    if open_browser and os.environ.get('OLLAMA_SAY_NO_BROWSER') != '1':
        webbrowser.open(f'http://127.0.0.1:{PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    serve()
