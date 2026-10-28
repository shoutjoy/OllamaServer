"""Safe, fixed commands for Lemonade Server and its FastFlowLM backend."""
import os
import shutil
from pathlib import Path


LEMONADE_WINGET_ID = 'AMD.LemonadeServer'


def find_lemonade_cli(server_executable=None):
    """Find the CLI installed beside Lemonade Server or exposed on PATH."""
    found = shutil.which('lemonade') or shutil.which('lemonade.exe')
    if found:
        return found
    candidates = []
    if server_executable:
        candidates.append(Path(server_executable).resolve().parent / 'lemonade.exe')
    local = os.environ.get('LOCALAPPDATA', '')
    if local:
        candidates.append(Path(local) / 'lemonade_server' / 'bin' / 'lemonade.exe')
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            pass
    return None


def lemonade_install_args():
    winget = shutil.which('winget.exe') or shutil.which('winget')
    if not winget:
        raise ValueError('Windows 패키지 관리자(winget)를 찾을 수 없습니다. Microsoft App Installer를 설치하거나 공식 다운로드 페이지를 이용하세요.')
    return [winget, 'install', '--exact', '--id', LEMONADE_WINGET_ID,
            '--accept-package-agreements', '--accept-source-agreements']


def fastflowlm_install_args(server_executable=None):
    cli = find_lemonade_cli(server_executable)
    if not cli:
        raise ValueError('Lemonade CLI를 찾을 수 없습니다. Lemonade Server 설치를 먼저 완료한 뒤 앱을 다시 실행하세요.')
    return [cli, 'backends', 'install', 'flm:npu']
