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
    return Client(saved.get('engine', 'ollama'))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *args):
        # pythonw.exe has no stderr; BaseHTTPRequestHandler's default logger
        # would fail before an HTTP response can be written.
        pass

    def allowed(self):
        hosts = {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
        origin = self.headers.get('Origin')
        return self.headers.get('Host') in hosts and (not origin or origin in {f'http://{h}' for h in hosts})

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
            elif self.path == '/ollama/api/tags':
                self.send_data(200, json.dumps(list_models(), ensure_ascii=False).encode())
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
        if self.path != '/ollama/api/chat':
            return self.send_error(404)
        started = False
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 4_000_000:
                return self.send_error(413)
            payload = self.rfile.read(size)
            client = selected_client()
            payload = client.prepare_chat(optimized_payload(json.loads(payload)))
            with open_url(client.base_url + '/api/chat', data=payload, timeout=300) as response:
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ndjson')
                self.send_header('Connection', 'close')
                self.end_headers()
                started = True
                self.close_connection = True
                for line in response:
                    self.wfile.write(line)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            if not started:
                self.send_data(502, json.dumps({'error': str(exc)}).encode())

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
