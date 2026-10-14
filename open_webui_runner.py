"""Isolated, persistent Open WebUI installation and loopback launcher."""
import json
import os
import platform
from pathlib import Path
import shutil
import socket
import subprocess
import time
import zipfile
from urllib.request import urlopen

URL = 'http://127.0.0.1:8080'
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def ready():
    try:
        with urlopen(URL + '/api/version', timeout=2) as response:
            return bool(json.load(response).get('version'))
    except (OSError, ValueError):
        return False


def executable(root):
    return Path(root) / 'venv' / ('Scripts/open-webui.exe' if os.name == 'nt' else 'bin/open-webui')


def find_uv(root, notify):
    local = Path(root) / 'tools' / 'uv.exe'
    if local.is_file():
        return str(local)
    uv = shutil.which('uv')
    if uv:
        return uv
    candidate = Path.home() / '.local' / 'bin' / ('uv.exe' if os.name == 'nt' else 'uv')
    if candidate.is_file():
        return str(candidate)
    if os.name != 'nt':
        raise RuntimeError('uv를 먼저 설치해주세요: https://docs.astral.sh/uv/getting-started/installation/')
    machine = platform.machine().lower()
    arch = 'aarch64' if machine in ('arm64', 'aarch64') else 'x86_64' if machine in ('amd64', 'x86_64') else 'i686'
    notify('설치 도구 uv 다운로드 중…')
    url = f'https://github.com/astral-sh/uv/releases/latest/download/uv-{arch}-pc-windows-msvc.zip'
    archive = Path(root) / 'uv.zip'
    try:
        with urlopen(url, timeout=60) as source, archive.open('wb') as target:
            shutil.copyfileobj(source, target)
        with zipfile.ZipFile(archive) as bundle:
            member = next(name for name in bundle.namelist() if Path(name).name == 'uv.exe')
            local.parent.mkdir(parents=True, exist_ok=True)
            temporary = local.with_suffix('.tmp')
            with bundle.open(member) as source, temporary.open('wb') as target:
                shutil.copyfileobj(source, target)
            temporary.replace(local)
    finally:
        archive.unlink(missing_ok=True)
    return str(local)


def install(root, notify=lambda text: None):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    uv = find_uv(root, notify)
    python = root / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    with (root / 'install.log').open('a', encoding='utf-8') as log:
        for command in ([uv, '--cache-dir', str(root / 'cache'), 'venv', '--python', '3.11', str(root / 'venv')],
                        [uv, '--cache-dir', str(root / 'cache'), 'pip', 'install', '--python', str(python), 'open-webui']):
            if 'venv' in command and python.is_file():
                continue
            notify('Python 3.11 환경 준비 중…' if 'venv' in command else 'Open WebUI 패키지 설치 중…')
            env = os.environ.copy()
            env['UV_PYTHON_INSTALL_DIR'] = str(root / 'python')
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8', errors='replace', env=env,
                                       creationflags=NO_WINDOW)
            with process.stdout:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    notify(line.rstrip())
            if process.wait():
                raise RuntimeError(f'Open WebUI 설치 실패. 설치 로그: {root / "install.log"}')
    if not executable(root).is_file():
        raise RuntimeError('설치가 완료되지 않았습니다. 설치 로그를 확인한 뒤 다시 시도해주세요.')
    notify('Open WebUI 설치 완료')


def start(root, notify=lambda text: None, base_url='http://127.0.0.1:11434'):
    if ready():
        return URL
    # Do not launch another service over a port owned by another application.
    try:
        with socket.create_connection(('127.0.0.1', 8080), timeout=0.5):
            raise RuntimeError('8080 포트를 다른 서비스가 사용 중입니다.')
    except OSError:
        pass
    root = Path(root).resolve()
    if not executable(root).is_file():
        notify('Open WebUI 설치 중… 첫 설치에는 시간이 걸릴 수 있습니다.')
        install(root, notify)
    root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(DATA_DIR=str((root / 'data').resolve()), OLLAMA_BASE_URL=base_url)
    env.setdefault('HF_HOME', str(root / 'cache' / 'huggingface'))
    notify('Open WebUI 시작 중…')
    with (root / 'server.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable(root)), 'serve', '--host', '127.0.0.1', '--port', '8080'],
                                   env=env, cwd=root, stdout=log, stderr=log, creationflags=NO_WINDOW)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if ready():
            return URL
        if process.poll() is not None:
            raise RuntimeError(f'Open WebUI 시작 실패. 로그: {root / "server.log"}')
        time.sleep(1)
    raise RuntimeError(f'Open WebUI 시작 대기 시간이 초과되었습니다. 로그: {root / "server.log"}')
