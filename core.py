"""Ollama transport and official model catalog; standard library only."""
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE_URL = 'http://127.0.0.1:11434'
LEMONADE_URL = 'http://127.0.0.1:13305'
ENGINE_LABELS = {'ollama': 'Ollama · CPU/GPU', 'lemonade': 'Lemonade · FastFlowLM NPU'}


def engine_url(engine):
    return LEMONADE_URL if engine == 'lemonade' else BASE_URL


def find_lemonade():
    candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'lemonade_server/bin/LemonadeServer.exe'
    if candidate.is_file():
        return str(candidate)
    return shutil.which('LemonadeServer')
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
                  if urllib.parse.urlsplit(url).hostname in ('127.0.0.1', 'localhost', '::1')
                  else urllib.request.build_opener())
        return opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:600]
        raise RuntimeError(f'HTTP {exc.code}: {detail}') from exc


class Client:
    def __init__(self, engine='ollama'):
        self.engine = engine if engine in ENGINE_LABELS else 'ollama'
        self.base_url = engine_url(self.engine)

    def get(self, path, timeout=4):
        with open_url(self.base_url + path, timeout=timeout) as response:
            return json.load(response)

    def post(self, path, data, timeout=300):
        with open_url(self.base_url + path, data, timeout=timeout) as response:
            result = json.load(response)
        if result.get('status') == 'error' or result.get('error'):
            raise RuntimeError(result.get('error') or result.get('message'))
        return result

    def prepare_chat(self, data):
        if self.engine != 'lemonade':
            return data
        data = dict(data, options=dict(data.get('options') or {}))
        name = data['model'].removesuffix(':latest')
        if name.lower().endswith('-flm'):
            self.post('/api/v1/load', {'model_name': name,
                      'ctx_size': data['options'].get('num_ctx', 8192),
                      'flm_args': '--pmode turbo', 'save_options': True})
        data['options'].pop('num_gpu', None)
        data.pop('think', None)
        return data

    def stream(self, path, data, cancel=None):
        if path == '/api/chat':
            data = self.prepare_chat(data)
        with open_url(self.base_url + path, data, timeout=300 if self.engine == 'lemonade' else 120) as response:
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


PERFORMANCE_DEFAULTS = {
    'keep_alive': '30m', 'context_length': 4096, 'num_parallel': 1,
    'flash_attention': False, 'kv_cache_type': 'f16',
    'num_predict': 4096, 'thinking': 'auto', 'integrated_gpu': False,
    'max_loaded_models': 1, 'num_gpu': -1,
}


def validate_performance(values):
    result = dict(PERFORMANCE_DEFAULTS, **values)
    for key, low, high in [('context_length', 512, 131072),
                           ('num_parallel', 1, 8), ('num_predict', 1, 32768),
                           ('max_loaded_models', 1, 8), ('num_gpu', -1, 256)]:
        value = result[key]
        if isinstance(value, bool):
            raise ValueError(key + ' 값을 확인하세요.')
        try:
            number = int(str(value))
        except (ValueError, TypeError):
            raise ValueError(key + '에는 정수를 입력하세요.') from None
        if not low <= number <= high:
            raise ValueError(f'{key}: {low}~{high} 범위로 입력하세요.')
        result[key] = number
    if result['keep_alive'] not in ('0', '5m', '10m', '30m', '1h', '-1'):
        raise ValueError('모델 유지 시간을 확인하세요.')
    if result['kv_cache_type'] not in ('f16', 'q8_0', 'q4_0'):
        raise ValueError('KV 캐시 유형을 확인하세요.')
    if type(result['integrated_gpu']) is not bool:
        raise ValueError('내장 GPU 설정을 확인하세요.')
    if type(result['flash_attention']) is not bool:
        raise ValueError('Flash Attention 설정을 확인하세요.')
    if result['kv_cache_type'] != 'f16' and not result['flash_attention']:
        raise ValueError('캐시 양자화를 사용하려면 Flash Attention을 켜세요.')
    if result['thinking'] not in ('auto', 'off', 'low'):
        raise ValueError('추론 설정을 확인하세요.')
    return {key: result[key] for key in PERFORMANCE_DEFAULTS}


def performance_environment(values):
    settings = validate_performance(values)
    environment = {
        'OLLAMA_MAX_LOADED_MODELS': str(settings['max_loaded_models']),
        'OLLAMA_KEEP_ALIVE': settings['keep_alive'],
        'OLLAMA_CONTEXT_LENGTH': str(settings['context_length']),
        'OLLAMA_NUM_PARALLEL': str(settings['num_parallel']),
        'OLLAMA_FLASH_ATTENTION': '1' if settings['flash_attention'] else '0',
        'OLLAMA_KV_CACHE_TYPE': settings['kv_cache_type'],
    }
    if settings['integrated_gpu']:
        environment.update(OLLAMA_IGPU_ENABLE='1', OLLAMA_VULKAN='1')
    return environment


def preferred_nvidia_gpu():
    """Return the first CUDA GPU UUID reported by the NVIDIA driver."""
    executable = shutil.which('nvidia-smi')
    if not executable and os.name == 'nt':
        candidate = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/nvidia-smi.exe'
        executable = str(candidate) if candidate.is_file() else None
    if not executable:
        return None
    try:
        output = subprocess.check_output(
            [executable, '--query-gpu=uuid', '--format=csv,noheader,nounits'],
            text=True, encoding='utf-8', errors='replace', timeout=5,
            creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    return next((line.strip() for line in output.splitlines()
                 if line.strip().startswith('GPU-')), None)


def gpu_preference_environment(values, nvidia_uuid=None):
    """Prefer CUDA over the optional integrated-GPU Vulkan backend."""
    environment = performance_environment(values)
    if nvidia_uuid:
        environment.update(CUDA_VISIBLE_DEVICES=nvidia_uuid,
                           OLLAMA_IGPU_ENABLE='0', OLLAMA_VULKAN='0')
    return environment


def chat_performance(values, model):
    settings = validate_performance(values)
    result = {'keep_alive': settings['keep_alive'], 'options': {
        'num_ctx': settings['context_length'], 'num_predict': settings['num_predict']}}
    if settings['num_gpu'] != -1:
        result['options']['num_gpu'] = settings['num_gpu']
    if settings['thinking'] != 'auto':
        # GPT-OSS supports effort levels, but cannot disable thinking.
        result['think'] = 'low' if model.split(':')[0].split('/')[-1] == 'gpt-oss' else False
    return result


def running_model_change(previous, models):
    """Infer a single observed model activity; /api/ps has no request history."""
    snapshot = {item.get('name') or item.get('model'): item.get('expires_at')
                for item in models if item.get('name') or item.get('model')}
    changed = [name for name, expiry in snapshot.items()
               if name not in previous or (expiry is not None and expiry != previous[name])]
    return (changed[0] if len(changed) == 1 else None), snapshot


def model_placement(models, engine='ollama'):
    label = 'Lemonade' if engine == 'lemonade' else 'Ollama'
    if not models:
        return label + ': 모델 미로드'
    parts = []
    for model in models:
        name = model.get('name') or model.get('model', '?')
        size, vram = model.get('size', 0), model.get('size_vram', 0)
        quant = model.get('details', {}).get('quantization_level', '?')
        if model.get('details', {}).get('family') == 'flm':
            placement = 'NPU · FastFlowLM'
        elif not isinstance(size, (int, float)) or size <= 0 or not isinstance(vram, (int, float)):
            placement = '배치 정보 없음'
        elif vram <= 0:
            placement = 'CPU 배치'
        elif vram < size:
            placement = f'CPU + GPU · GPU 할당 {vram / 2**30:.2f} GB'
        else:
            placement = f'GPU 배치 · {vram / 2**30:.2f} GB'
        parts.append(f'{name} [{quant}] {placement}')
    return label + ': ' + ' / '.join(parts)


def effective_performance(saved, model):
    """Exact model profiles keep context stable across repeated requests."""
    values = dict(saved.get('performance', {}))
    values.update(saved.get('model_profiles', {}).get(model, {}))
    return validate_performance(values)
