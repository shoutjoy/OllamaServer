"""Loopback-only launcher; no arbitrary command execution or arbitrary proxy targets."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parent
PORT = 8767

def list_models():
    executable = shutil.which('ollama')
    if not executable:
        candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Ollama/ollama.exe'
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        raise RuntimeError('Ollama 실행 파일을 찾을 수 없습니다. Ollama 설치 후 다시 실행하세요.')
    result = subprocess.run([executable, 'list'], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=15,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'ollama list 실패')
    return {'models': [{'name': line.split()[0]} for line in result.stdout.splitlines()[1:] if line.strip()]}

class Handler(BaseHTTPRequestHandler):
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
            json.loads(payload)
            request = Request('http://127.0.0.1:11434/api/chat', data=payload,
                              headers={'Content-Type': 'application/json'}, method='POST')
            with urlopen(request, timeout=300) as response:
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

if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print(f'Ollama Say: http://127.0.0.1:{PORT} (Ctrl+C to stop)', flush=True)
    webbrowser.open(f'http://127.0.0.1:{PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
