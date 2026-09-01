"""Ollama transport and official model catalog; standard library only."""
import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE_URL = 'http://127.0.0.1:11434'
INSTALL_URL = 'https://ollama.com/download/OllamaSetup.exe'
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def find_ollama():
    found = shutil.which('ollama')
    if found:
        return found
    candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Ollama/ollama.exe'
    try:
        return str(candidate) if candidate.is_file() else None
    except OSError:
        return None


def model_name(value):
    value = value.strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]*', value):
        raise ValueError('모델 이름을 확인하세요. 예: gemma3:1b')
    return value


def models_directory():
    """Match the model location configured in this app's environment."""
    configured = os.environ.get('OLLAMA_MODELS', '').strip().strip('"')
    return Path(configured).expanduser().resolve() if configured else Path.home() / '.ollama' / 'models'


def open_url(url, data=None, timeout=30):
    body = None if data is None else json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, body, headers={
        'User-Agent': 'OllamaDesk/1.0', 'Content-Type': 'application/json'})
    try:
        # A system HTTP proxy must not intercept the local Ollama server.
        opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
                  if url.startswith(BASE_URL + '/') else urllib.request.build_opener())
        return opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:600]
        raise RuntimeError(f'HTTP {exc.code}: {detail}') from exc


class Client:
    def get(self, path, timeout=4):
        with open_url(BASE_URL + path, timeout=timeout) as response:
            return json.load(response)

    def stream(self, path, data, cancel=None):
        with open_url(BASE_URL + path, data, timeout=120) as response:
            for line in response:
                if cancel and cancel.is_set():
                    raise RuntimeError('작업을 취소했습니다.')
                if line.strip():
                    item = json.loads(line)
                    if item.get('error'):
                        raise RuntimeError(item['error'])
                    yield item


class CatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.models = []
        self.active = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get('href', '')
        if tag == 'a' and re.fullmatch(r'/library/[A-Za-z0-9._-]+', href):
            self.active = href.removeprefix('/library/')
            self.parts = []

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.active:
            name = self.active
            description = ' '.join(' '.join(self.parts).split())
            if name not in {item[0] for item in self.models}:
                self.models.append((name, description))
            self.active = None


def search_models(query):
    url = 'https://ollama.com/search?' + urllib.parse.urlencode({'q': query})
    with open_url(url) as response:
        parser = CatalogParser()
        parser.feed(response.read().decode('utf-8'))
    return parser.models


def fetch_tags(name):
    name = model_name(name).split(':')[0]
    with open_url('https://ollama.com/library/' + urllib.parse.quote(name, safe='') + '/tags') as response:
        html = response.read().decode('utf-8')
    values = re.findall(r'href="/library/' + re.escape(name) + r':([^"?]+)"', html)
    return list(dict.fromkeys(values))
