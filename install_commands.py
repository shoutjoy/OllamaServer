"""Fixed official install commands; never execute a command entered as UI text."""
import platform
import shutil

COMMANDS = {
    'Windows': 'irm https://ollama.com/install.ps1 | iex',
    'Linux': 'curl -fsSL https://ollama.com/install.sh | sh',
    'Darwin': 'curl -fsSL https://ollama.com/install.sh | sh',
}


def install_args(system):
    if system != platform.system() or system not in COMMANDS:
        raise ValueError('현재 운영체제에 맞는 설치 방법을 선택하세요.')
    if system == 'Windows':
        shell = shutil.which('powershell.exe') or shutil.which('pwsh.exe')
        if not shell:
            raise ValueError('PowerShell을 찾을 수 없습니다.')
        # Do not inherit an uninstall request or an unofficial download override.
        prefix = ("$ErrorActionPreference='Stop'; "
                  "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
                  "$OutputEncoding=[Console]::OutputEncoding; "
                  "Remove-Item Env:OLLAMA_UNINSTALL -ErrorAction SilentlyContinue; "
                  "Remove-Item Env:OLLAMA_DOWNLOAD_URL -ErrorAction SilentlyContinue; ")
        return [shell, '-NoLogo', '-NoProfile', '-Command',
                prefix + 'try { ' + COMMANDS[system] + ' } catch { Write-Error $_; exit 1 }']
    shell = shutil.which('bash')
    if not shell or not shutil.which('curl'):
        raise ValueError('터미널 설치에는 bash와 curl이 필요합니다.')
    # pipefail also surfaces download failures rather than reporting sh's zero exit.
    return [shell, '-o', 'pipefail', '-c', COMMANDS[system]]
