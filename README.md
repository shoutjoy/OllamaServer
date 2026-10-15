# Ollama Desk

Python 표준 라이브러리와 Tkinter로 만든 한국어 Windows Ollama 관리자입니다.

## 실행 중 RAM 정리

실시간 상태 아래 **앱 RAM 정리** 버튼은 앱의 미사용 객체를 수거하고 Windows에서는 관리자 앱 자신의 작업 집합을 운영체제에 반환합니다. 표시되는 RAM은 이후 앱 사용에 따라 다시 증가할 수 있으며 모델 메모리나 다른 프로그램은 정리하지 않습니다. **유휴 시 자동 정리**는 기본으로 켜져 있으며 1분마다 진행 중인 작업이 없을 때 미사용 객체만 수거합니다. 체크를 해제하면 자동 정리를 끌 수 있습니다.

작업·접속·콘솔·설치 로그 화면은 각각 최근 20만 자까지만 유지합니다. 저장된 접속 로그와 대화 내용은 유지됩니다. 모델이 차지하는 RAM은 **성능 설정 → 미사용 모델 RAM 해제**로 정리하세요. 선택한 모델은 유지되며 다른 앱에서 사용하는 모델도 해제될 수 있으므로 외부 AI 작업이 끝난 뒤 실행하세요.

## AMD NPU 모델 사용

상단 **AI 실행 엔진**에서 **Lemonade · FastFlowLM NPU**를 선택한 뒤 **서버 시작**을 누르세요. 설치된 Lemonade 서버에 연결하거나 서버를 시작하고, 다운로드된 FLM 모델을 NPU turbo 모드로 로드합니다. **사용할 모델**에서 `qwen3-it-4b-FLM:latest` 등을 선택하면 관리자 **대화**와 **챗 열기**에서 NPU 모델을 사용할 수 있습니다. 엔진 선택은 소스/EXE 각각의 설정 파일에 저장됩니다.

Lemonade 모드의 모델 검색은 FastFlowLM 대화 모델을 표시하며 **모델 설치**로 다운로드합니다. NPU 모델과 Ollama 모델 파일은 별도로 관리됩니다. 관리자 및 웹 채팅 요청은 저장된 컨텍스트 길이를 사용하고 FLM 모델을 turbo 모드로 준비하며, Ollama GPU 레이어/추론 옵션은 NPU 요청에서 제외합니다. **GPU / NPU 사용 확인**은 Lemonade 모드에서 실제 실행 장치·모델 상태를 조회합니다. 서버 정지/재시작은 선택한 엔진에 적용되며, 엔진을 바꾸는 것만으로 이전 서버를 종료하지 않습니다.

Lemonade 서버 주소는 `http://127.0.0.1:13305`, Ollama는 `http://127.0.0.1:11434`입니다. 외부 Ollama 호환 앱은 연결 주소를 Lemonade 주소로 변경해야 NPU 모델을 사용할 수 있습니다. Open WebUI 신규 실행은 선택한 주소를 전달하지만, 이미 실행 중이거나 자체 연결 설정을 저장한 Open WebUI는 관리자 설정 → 연결에서 주소를 변경하세요. ‘챗 열기’ 웹 화면은 엔진 변경 후 모델 목록을 새로고침하세요.

Windows에서는 **AI 엔진 · Open WebUI** 탭에서 **Lemonade Server 설치**를 누르면 WinGet의 공식 `AMD.LemonadeServer` 패키지를 설치하거나 업데이트할 수 있습니다. 이어서 **FastFlowLM 백엔드 설치**를 누르면 Lemonade CLI가 `flm:npu` 백엔드를 설치합니다. FastFlowLM에는 Windows 11, 지원되는 AMD Ryzen AI XDNA 2 NPU와 최신 NPU 드라이버가 필요하며 Intel NPU·NVIDIA GPU·XDNA 1 NPU에서는 동작하지 않습니다. Lemonade Server 자체는 FastFlowLM 없이도 CPU/GPU 백엔드로 사용할 수 있습니다. [Lemonade 설치 안내](https://lemonade-server.ai/docs/guide/install/windows/)와 [FastFlowLM Windows 안내](https://fastflowlm.com/docs/install_win/)도 참고하세요. Ollama 설치 앱과 OS별 공식 설치 스크립트는 별도의 **Ollama 설치** 탭에 있습니다. Ollama 모드의 GPU 성능 옵션은 Lemonade 엔진 설정에 적용되지 않습니다. 기존 EXE 실행 중에는 `powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1 -OutputName Ollama_Park_Updated.exe`로 별도 파일을 빌드할 수 있습니다.

## 실행

별도 Python 설치 없이 단일 파일 `Ollama_Park.exe`를 더블클릭하면 실행됩니다.

**[최신 Ollama_Park.exe 다운로드](https://github.com/shoutjoy/OllamaServer/releases/latest/download/Ollama_Park.exe)**

다운로드가 열리지 않으면 **[저장소의 Ollama_Park.exe 직접 다운로드](https://github.com/shoutjoy/OllamaServer/raw/refs/heads/main/Ollama_Park.exe)** 또는 **[릴리스 목록](https://github.com/shoutjoy/OllamaServer/releases)**에서 Windows 실행 파일을 받으세요.

로컬에서 빌드하거나 복구한 EXE는 GitHub에 자동 업로드되지 않습니다. 새 파일을 배포하려면 루트의 `Ollama_Park.exe`와 README 변경을 `main`에 커밋하고 푸시하세요. 아래 배포 workflow가 성공하면 최신 다운로드 링크에 반영됩니다.

Windows 다운로드는 GitHub Releases의 최신 배포 파일을 사용합니다. `main`의 `Ollama_Park.exe`가 변경되면 **Publish latest Windows executable** workflow가 저장소의 EXE를 그대로 업로드하고 최신 릴리스로 지정합니다. 실행 파일을 다시 빌드하지 않으므로 로컬에서 올린 파일과 배포 파일이 같습니다. [SHA256SUMS.txt](https://github.com/shoutjoy/OllamaServer/releases/latest/download/SHA256SUMS.txt)로 파일을 확인할 수 있습니다. 다운로드 폴더에 이전 파일이 있다면 새로 받은 파일의 이름에 `(1)` 등이 붙을 수 있으므로 새 파일을 실행하세요.

배포 상태는 [GitHub Actions](https://github.com/shoutjoy/OllamaServer/actions/workflows/publish-windows.yml)에서 확인할 수 있습니다. 자동 배포 실패 시 오류를 해결한 뒤 **Run workflow → main → Run workflow**로 다시 배포합니다. workflow 실행이 성공해야 위 최신 다운로드 링크가 갱신됩니다.

**[OllamaDesk Mac.dmg 다운로드](https://github.com/shoutjoy/OllamaServer/releases/download/mac-1.0/OllamaDesk-macOS.dmg)**

소스에서 실행하려면 Python 3.10 이상(Tkinter 포함)으로:

```powershell
python app.py
```

소스 실행에는 별도 pip 패키지가 필요하지 않습니다. 단일 EXE의 설정과 로그는 `%LOCALAPPDATA%\OllamaDesk`에 저장됩니다.

macOS 사용자는 아래 **Mac 사용자: 다운로드부터 실행까지**를 따라 `run_mac.command`로 실행하세요.

‘챗 열기’ 옆의 **Open WebUI** 버튼으로 Open WebUI를 시작하고 브라우저에서 열 수 있습니다 (`http://127.0.0.1:8080`). Ollama 연결은 `http://127.0.0.1:11434`로 설정됩니다. **AI 엔진 · Open WebUI → Open WebUI 설치**에서 먼저 설치할 수도 있습니다. 설치 상태와 진행 출력을 앱에서 확인할 수 있으며 실패하면 다시 설치 버튼을 누르세요. 이미 설치된 환경은 재사용합니다. Windows에서는 uv가 없으면 공식 배포 파일을 앱 데이터 폴더에 다운로드하고 Python 3.11 환경과 Open WebUI를 자동 설치합니다. 다른 OS에서는 uv를 먼저 설치하세요. 설치·시작 작업은 백그라운드에서 진행됩니다. 처음 열린 화면에서 관리자 계정을 생성하세요.

Open WebUI의 환경, 대화 데이터, 설치·서버 로그는 소스 실행 시 `.data/open-webui`, EXE 실행 시 `%LOCALAPPDATA%\OllamaDesk\open-webui`에 저장됩니다. EXE 옆 `.data/open-webui`에 이미 설치되어 있으면 그 환경을 재사용합니다. 매니저 종료 후에도 Open WebUI 서버는 유지되며, 다시 누르면 실행 중인 서버를 엽니다. 8080 포트를 다른 서비스가 사용하면 오류를 안내합니다. 설치 방법: [Open WebUI 공식 안내](https://docs.openwebui.com/getting-started/quick-start/).

상단의 **MDpro** 버튼은 브라우저에서 [MDpro Viewer](https://mdproviewer.vercel.app/)를 엽니다.

## Mac 사용자: 다운로드부터 실행까지

`run_mac.command`는 Windows의 `run.bat`처럼 Python 앱을 실행하는 macOS용 파일입니다. `Ollama_Park.exe`는 Windows 전용이므로 Mac에서는 아래 소스 실행 방법을 사용하세요. Apple Silicon과 Intel Mac 모두 설치한 Python으로 실행하며, 관리자 소스 실행에는 별도 pip 패키지가 필요하지 않습니다.

### 1. 프로젝트 전체 다운로드

1. **[프로젝트 ZIP 다운로드](https://github.com/shoutjoy/OllamaServer/archive/refs/heads/main.zip)**를 누릅니다. GitHub 저장소 화면에서 **Code → Download ZIP**으로 내려받아도 됩니다.
2. Finder의 **다운로드** 폴더에서 `OllamaServer-main.zip`을 더블클릭해 압축을 풉니다.
3. 압축을 푼 `OllamaServer-main` 폴더 안에 `run_mac.command`, `app.py`, `CHAT`, `Icon`이 있는지 확인합니다.

**`run_mac.command`만 따로 다운로드하면 실행되지 않습니다.** 프로젝트 폴더 전체가 필요하며, 실행 파일을 폴더 밖으로 옮기지 마세요. 폴더 전체는 원하는 위치로 옮겨도 됩니다.

### 2. Python 설치 및 확인

1. **[Python 공식 macOS 다운로드](https://www.python.org/downloads/macos/)**에서 Python 3.10 이상의 macOS 설치 프로그램(`.pkg`)을 다운로드합니다.
2. `.pkg`를 열고 설치 안내를 따릅니다. Tkinter가 포함된 Python이 필요합니다.
3. **응용 프로그램 → 유틸리티 → 터미널**을 열고 다음 명령을 각각 입력합니다.

```bash
python3 --version
python3 -m tkinter
```

첫 명령에서 Python 3.10 이상이 표시되고, 두 번째 명령에서 작은 Tk 창이 열리면 준비가 완료된 것입니다. 확인 창은 닫아도 됩니다. `python3`를 찾을 수 없거나 `No module named tkinter` / `_tkinter`가 나오면 위 공식 설치 프로그램으로 Python을 설치한 뒤 터미널을 다시 열어 확인하세요.

### 3. 처음 한 번 실행 권한 설정

다운로드한 ZIP은 실행 권한이 없을 수 있으므로 터미널에서 프로젝트 폴더로 이동한 뒤 실행 권한을 부여합니다. 기본 다운로드 위치에 압축을 풀었다면 다음 명령을 입력하세요.

```bash
cd "$HOME/Downloads/OllamaServer-main"
chmod +x run_mac.command
./run_mac.command
```

다른 위치에 저장했다면 터미널에 `cd `를 입력한 뒤(뒤에 공백 포함), Finder의 프로젝트 폴더를 터미널로 끌어 놓고 Enter를 누르세요. 그다음 위의 `chmod`와 실행 명령을 입력하면 됩니다.

### 4. 다음부터 더블클릭으로 실행

Finder에서 프로젝트 폴더 안의 **`run_mac.command`를 더블클릭**하세요. 터미널이 열리고 Ollama Desk 관리자 창이 표시됩니다. 앱을 사용하는 동안 실행한 터미널 창은 열어 두고, 종료할 때는 관리자 창을 먼저 닫으세요.

실행 스크립트는 자신의 폴더를 기준으로 `app.py`를 실행합니다. `.venv/bin/python3`가 있으면 해당 환경을 우선 사용하고, 없으면 PATH에서 `python3`를 찾습니다. 기존 가상환경에 Tkinter가 없다면 Tkinter를 포함한 Python으로 가상환경을 다시 준비해야 합니다.

### 5. Ollama 설치와 첫 대화

1. **[Ollama 공식 Mac 다운로드](https://ollama.com/download/mac)**에서 Mac용 Ollama를 설치하고 실행합니다. 관리자와 별도로 Ollama가 필요합니다.
2. `run_mac.command`로 관리자를 실행하고 **AI 실행 엔진**에서 **Ollama**를 선택합니다.
3. **서버 시작**을 눌러 로컬 Ollama 서버에 연결합니다.
4. **공식 모델 검색**에서 모델을 고른 뒤 **모델 설치**를 누릅니다. 다운로드 시간과 필요한 메모리는 모델마다 다릅니다.
5. 설치된 모델을 **사용할 모델**에서 선택하고 **대화** 탭에서 메시지를 입력합니다.

소스로 실행한 관리자의 설정과 로그는 프로젝트 폴더 안의 `.data`에 저장됩니다. 업데이트할 때 기존 설정을 유지하려면 해당 폴더를 보관하세요.

### 실행이 안 될 때

- **`Permission denied`**: 프로젝트 폴더에서 `chmod +x run_mac.command`를 다시 실행하세요.
- **`app.py`를 찾을 수 없음**: ZIP 전체를 압축 해제했는지, `run_mac.command`와 `app.py`가 같은 폴더에 있는지 확인하세요.
- **Python 또는 Tkinter 오류**: 2단계의 두 명령으로 설치를 확인하세요. 스크립트가 `.venv`를 사용한다면 그 환경의 Python도 확인하세요.
- **텍스트 편집기로 열림**: 터미널에서 `./run_mac.command`로 실행하거나 Finder의 **다음으로 열기 → 터미널**을 선택하세요.
- **macOS가 다운로드한 파일 실행을 차단함**: 파일 출처를 확인한 뒤 실행을 한 번 시도하고, **시스템 설정 → 개인정보 보호 및 보안**에 해당 파일의 **확인 없이 열기(Open Anyway)**가 표시되면 선택하세요. 자세한 절차는 [Apple 공식 안내](https://support.apple.com/guide/mac-help/open-an-app-by-overriding-security-settings-mh40616/mac)를 참고하세요.
- **관리자 창이 뜨지 않거나 곧 닫힘**: 터미널에서 `./run_mac.command`를 실행해 오류를 확인하세요. 실행 실패 시 스크립트는 Enter를 누를 때까지 오류 출력을 유지합니다.
- **Ollama 연결 실패**: Ollama 앱이 실행 중인지 확인하고 관리자에서 서버 시작을 다시 누르세요. 기본 연결 주소는 `http://127.0.0.1:11434`입니다.

## macOS 앱 / DMG 배포

macOS에서는 Python이 설치되지 않은 다른 Mac에서도 실행할 수 있도록 PyInstaller로 `.app`과 `.dmg`를 만들 수 있습니다. 빌드는 대상 Mac의 CPU 아키텍처에서 직접 실행하세요. Apple Silicon(`arm64`)과 Intel(`x86_64`)은 각각 별도로 빌드해야 하며, 한 번의 빌드만으로 두 아키텍처를 모두 지원하지는 않습니다.

```bash
python3 -m pip install pyinstaller
./packaging/build_macos.sh
```

결과물은 `dist/OllamaDesk.app`과 `dist/OllamaDesk-macOS.dmg`입니다. 스크립트는 `Icon`과 `CHAT` HTML 리소스를 앱에 포함하고, 앱 번들을 **Ad Hoc** 방식으로 서명합니다. Ad Hoc 서명은 Apple Developer 인증서 서명이나 공증(notarization)이 아니므로 인터넷에서 내려받은 앱을 처음 열 때 macOS의 보안 경고가 표시될 수 있습니다. 사용자는 DMG에서 앱을 `Applications`로 복사한 뒤 Finder에서 우클릭하여 **열기**를 선택해야 할 수 있습니다.

공식 배포에서 경고 없이 열리게 하려면 Ad Hoc 대신 Apple Developer ID Application 인증서로 서명하고, `notarytool` 공증 및 Staple 단계를 추가해야 합니다. 또한 대상 Mac에는 Ollama가 별도로 설치되어 있어야 하며, 앱 자체에 Ollama 모델 파일은 포함되지 않습니다.

## 사용 순서

1. **Ollama 설치**: 상단 **Ollama 설치** 버튼으로 별도의 **Ollama 설치** 탭을 열고 다음 중 원하는 방법을 선택합니다.
   - **Windows 다운로드 앱으로 설치**: 공식 설치 파일을 받고 디지털 서명을 검증한 뒤 설치 마법사를 엽니다. 저장 위치 `.data/OllamaSetup.exe`를 표시하고 **다운로드 폴더 열기**, **다운로드 중지**를 제공합니다. 중지/실패 시 미완성 `.download` 파일은 삭제합니다. 네트워크 대기 중에는 약 10초, 서명 검증 중에는 검증 종료까지 걸릴 수 있습니다. 마법사가 열린 후에는 마법사에서 취소하세요.
   - **윈도우 터미널 설치**: `irm https://ollama.com/install.ps1 | iex`
   - **리눅스 / 맥 터미널 설치**: `curl -fsSL https://ollama.com/install.sh | sh`
   - 터미널 설치는 확인 후 앱 내부 출력창에서 실행합니다. 현재 OS에 맞는 버튼만 활성화되며, 다른 OS 명령은 복사할 수 있습니다. Windows에서 Linux/맥 설치를 대신 실행하거나 WSL을 자동 설치하지 않습니다.
   - 터미널 입력은 아래의 가림 입력란으로 전송하고 **터미널 중지**로 실행 프로세스 트리의 종료를 요청합니다. 이미 설치된 파일/서비스는 되돌리지 않으며, 권한이 상승된 프로세스는 중지되지 않을 수 있습니다. OS 권한 확인창은 별도로 표시될 수 있습니다.
   - Windows 터미널 설치도 공식 스크립트 내부에서 `%TEMP%/OllamaSetup.exe`를 다운로드하여 자동 설치합니다. 앱 다운로드 방식의 `.data` 경로 및 임시 파일 정리와는 별개입니다. Linux/맥은 bash와 curl이 필요하며 권한 입력을 위해 PTY를 사용합니다. 기존 CONSOLE 탭은 Ollama 전용 명령 기능을 유지합니다.
2. **서버 시작**: 로컬 `127.0.0.1:11434` 서버에 연결하거나 `ollama serve`를 실행합니다. 앱의 **서버 시작**은 `OLLAMA_HOST=127.0.0.1:11434`, `OLLAMA_ORIGINS=*`로 Ollama를 실행하므로 로컬 브라우저 채팅 앱이 API에 직접 연결할 수 있습니다.
3. **공식 모델 검색**: 검색어를 입력하고 결과를 선택합니다. 태그 목록을 고르거나 `gemma3:1b`처럼 설치 모델을 직접 입력합니다.
4. **모델 설치**: 파일별 진행률과 다운로드 크기를 표시합니다. 설치 완료 후 로컬 모델 목록에서 확인하여 자동 선택합니다.
5. **대화**: 선택한 모델에 메시지를 보내고 스트리밍 응답을 확인합니다. Ctrl+Enter로 전송합니다.
6. **서버 정지**: 앱이 실행한 서버를 종료합니다. 기존 서버인 경우 안내 후 확인된 Ollama 설치 폴더의 Ollama 앱/서버 프로세스만 종료합니다.

## 동작과 제한

- 상단 **Ollama 설치 폴더 열기**와 **모델 다운로드 폴더 열기**로 탐색기를 엽니다. 설치 위치는 감지된 Ollama 실행 파일의 폴더이며, 모델 위치는 앱 실행 환경의 `OLLAMA_MODELS`를 우선하고 기본값은 `%USERPROFILE%\.ollama\models`입니다. 폴더가 없으면 안내만 표시하며 자동 생성하지 않습니다. 환경변수 변경 후 앱을 다시 실행하세요. 별도 계정/서비스에서 실행된 서버의 모델 위치는 다를 수 있습니다.

- 서버 API 응답을 확인하면 초록색 표시등과 **서버 동작 중** 문구를 표시합니다. 연결될 때 한 번 알림음과 3.5초 알림창을 띄우며, 응답이 끊기면 회색으로 바뀝니다. 자동 확인 주기는 5초입니다.
- CHAT HTML의 **답변 중지** 버튼은 항상 표시되고 생성 중에만 활성화됩니다. 응답 대기·스트리밍·학술/웹 검색 요청을 취소하며 이미 받은 답변은 유지합니다. 취소 정리가 끝나면 다시 전송할 수 있습니다.

- **CONSOLE** 탭에서 Ollama CLI 명령을 직접 실행하고 표준 출력·오류를 실시간 확인할 수 있습니다. 예: `ollama list`, `ollama ps`, `ollama pull gemma3:1b`, `ollama run gemma3:1b "안녕하세요"`.
- Enter는 명령 실행, 실행 중에는 해당 프로세스의 표준 입력 전송입니다. ↑/↓로 명령 기록을 탐색하고 **명령 중지**로 콘솔에서 실행한 프로세스만 종료합니다. 앱을 닫을 때도 콘솔 명령은 종료됩니다.
- `ollama serve`는 앱 서버 시작 기능으로 연결되고 `/server-stop`은 서버 정지 기능으로 연결됩니다. 앱에서 시작한 서버의 출력은 CONSOLE과 `.data/server.log`에서 확인합니다. 이미 외부에서 시작한 서버의 과거 로그는 가져오지 않습니다.
- 콘솔은 Ollama 전용 파이프 기반 콘솔입니다. CMD/PowerShell 명령, 파이프·리디렉션, 터미널 화면 제어는 지원하지 않습니다. 대화형 CLI의 터미널 기능이 필요하면 **대화** 탭 또는 `ollama run 모델 "질문"`을 사용하세요.
- 작업 로그와 모델 설치 진행 단계도 CONSOLE에 표시됩니다. 화면은 최근 약 6,000줄을 유지합니다. 콘솔 명령과 앱의 설치·대화 작업은 동시에 실행하지 않습니다.

- 모델 검색은 공식 라이브러리 검색 페이지의 반환 결과를 사용하며, 전체 페이지를 자동 순회하거나 커뮤니티 모델을 검색하지는 않습니다. 사이트 HTML 변경 시 공식 사이트 버튼 또는 모델명 직접 입력을 사용하세요.
- 태그에 따라 다운로드 크기, RAM/VRAM 요구량이 다릅니다. 모델별 크기는 공식 모델 페이지에서 확인하세요. 클라우드 모델은 계정/인터넷이 필요하며 일반 로컬 모델과 다릅니다.
- 설치 취소는 다음 스트리밍 응답 수신 시 연결을 닫습니다. 네트워크가 멈춘 경우 최대 120초 걸릴 수 있으며, 이미 받은 캐시 파일은 Ollama가 관리합니다.
- 앱을 닫아도 서버는 유지됩니다. 종료하려면 먼저 **서버 정지**를 누르세요. 서버 종료는 이를 사용하는 다른 앱에도 영향을 줍니다.
- Windows 외 환경은 공식 다운로드 페이지를 엽니다. 외부에서 시작한 서버의 정지는 운영체제의 터미널/서비스에서 수행하세요.
- 선택 모델은 `.data/settings.json`, 직접 시작한 서버 로그는 `.data/server.log`에 저장됩니다. 대화는 메모리에만 보관됩니다.
- 사용자 지정 경로에 Ollama를 설치했다면 해당 폴더를 PATH에 추가하세요.

## 검증

```powershell
python -m unittest discover -s tests -v
python smoke_test.py
```

공식 참고: [Windows 설치](https://docs.ollama.com/windows), [모델 다운로드 API](https://docs.ollama.com/api/pull), [모델 검색](https://ollama.com/search).

## 성능 설정

**성능 설정** 탭에서 모델 유지 시간, 컨텍스트 길이, 동시 요청 수, Flash Attention, KV 캐시 유형을 저장할 수 있습니다. **빠른 응답 프리셋 → 성능 설정 저장 → 서버 정지 → 서버 시작** 순서로 적용하세요. 프리셋은 유지 시간 30분, 컨텍스트 4096, 동시 요청 1, 관리자 대화 출력 1024토큰, 추론 끄기를 선택합니다. Flash Attention과 캐시 양자화는 별도로 선택합니다.

서버 설정은 이 관리자가 실행하는 `ollama serve`의 환경에만 적용하며 Windows 사용자 환경변수를 수정하지 않습니다. 이미 실행 중인 서버에 연결하면 재시작 전까지 새 서버 설정은 적용되지 않습니다. 모델 유지 시간·컨텍스트·출력 한도·추론 설정은 관리자 **대화** 탭 요청에도 적용됩니다. GPT-OSS의 추론 끄기는 `low`로 전송합니다. 추론 옵션을 지원하지 않는 모델은 `auto`를 선택하세요.

AI Jena 및 별도 웹 채팅의 출력 토큰·추론 설정은 각 앱에서 조절해야 합니다. 각 요청의 `options`와 `keep_alive`는 서버 기본값보다 우선합니다. 캐시 양자화는 Flash Attention이 필요하며 모델에 따라 정확도에 영향을 줄 수 있습니다. 속도 개선 정도는 GPU·모델·컨텍스트에 따라 다릅니다. **GPU 사용 확인** 버튼으로 CONSOLE에서 `ollama ps`를 실행할 수 있습니다.

참고: [Ollama 서버 성능 설정](https://docs.ollama.com/faq), [대화 API](https://docs.ollama.com/api/chat). 갱신된 `Ollama_Park.exe`에도 성능 설정, 모델 선택 동기화, 실시간 그래프, 내장 GPU 옵션이 포함됩니다. 서버 시작 시 NVIDIA 외장 GPU가 감지되면 CUDA 장치를 우선 지정하고 내장 GPU용 Vulkan 설정은 비활성화합니다. 적용하려면 기존 Ollama 서버를 이 앱의 **서버 재시작**으로 다시 시작하세요.

## 외부 앱 모델 선택 동기화

AI JENA 등에서 이 로컬 Ollama 서버를 호출하면 관리자가 5초마다 `/api/ps`를 확인해 새로 로드되거나 유지 시간이 변경된 모델을 **사용할 모델**에 반영하고 선택을 저장합니다. 모델이 변경되면 관리자 대화는 새로 시작합니다. 관리자 대화 생성 중에는 자동 변경을 보류합니다.

`/api/ps`는 호출 기록이 아닌 메모리에 올라온 모델 목록입니다. 여러 모델의 변화가 동시에 관찰되면 자동 선택하지 않습니다. 유지 시간 0으로 즉시 해제되어 조회 사이에 사라진 모델이나 유지 시간이 변하지 않는 호출은 감지하지 못할 수 있습니다. AI JENA에서 같은 로컬 서버 (`127.0.0.1:11434`)를 사용해야 합니다. 선택 표시 변경은 새 모델을 추가로 로드하거나 다른 모델을 종료하지 않습니다.

## 실시간 연결·사용량 그래프

화면 상단에서 서버 연결 상태와 GPU·CPU·RAM 사용률의 최근 5분 추이를 확인할 수 있습니다. 약 5초마다 별도 스레드에서 수집하므로 대화와 설치 화면을 계속 사용할 수 있습니다. 서버 연결은 로컬 Ollama API 응답 여부이며 접속한 클라이언트 수를 뜻하지 않습니다.

사용량은 Ollama 프로세스만이 아닌 **이 PC 전체** 기준입니다. RAM에는 사용/전체 GB를 함께 표시합니다. GPU는 NVIDIA의 `nvidia-smi`가 있으면 가장 바쁜 GPU 사용률을 표시하고, 그렇지 않거나 읽기에 실패하면 Windows GPU 성능 카운터에서 프로세스별 값을 엔진별로 합산하여 가장 바쁜 엔진을 표시합니다. 드라이버·성능 카운터를 사용할 수 없으면 측정 불가로 표시하며 그래프를 끊습니다. CPU는 첫 측정 후 다음 측정부터 표시됩니다. 추가 pip 패키지는 필요하지 않습니다. 갱신된 `Ollama_Park.exe`와 소스 실행에서 모두 사용할 수 있습니다.

## 작은 내장 GPU 함께 사용

**성능 설정 → 작은 GPU 프리셋 → 성능 설정 저장 → 서버 정지 → 서버 시작**으로 내장 GPU를 활성화합니다. `OLLAMA_IGPU_ENABLE=1`, `OLLAMA_VULKAN=1`을 서버 실행 환경에 전달합니다. 이전 설정에 없던 항목도 기본값으로 읽습니다. 이 PC의 Radeon 840M은 기존 로그에서 Vulkan으로 감지됐지만 내장 GPU 필터에 의해 제외되어 CPU로 실행되고 있었습니다.

작은 GPU 프리셋은 컨텍스트 2048, 동시 요청 1, 동시 상주 모델 1, 출력 1024, 추론 off를 선택합니다. GPU 레이어는 기본 자동(-1)이며 Ollama가 메모리에 맞춰 배치합니다. 관리자 대화에서 CPU와 GPU에 일부씩 배치하려면 **관리자 대화 GPU 레이어**를 2 또는 4부터 시험하세요. 0은 CPU 전용입니다. 이 요청 옵션은 관리자 대화에만 적용하며 AI JENA는 자체 요청 옵션과 Ollama 자동 배치를 사용합니다.

그래프 위에 실행 중 모델의 양자화 유형, CPU/GPU 메모리 배치와 GPU 할당 GB를 표시합니다. `size_vram`은 모델의 GPU 메모리 할당 정보이며 계산 사용률이나 레이어 비율이 아닙니다. 내장 GPU는 시스템 RAM을 공유하므로 GPU 활성화가 RAM 부족을 해소하지는 않습니다. GPU 인식·모델 배치에 실패하면 CPU로 실행될 수 있습니다.

KV 캐시의 q8_0/q4_0는 모델 가중치 양자화와 별개입니다. 가중치 메모리를 줄이려면 모델 검색에서 Q4 등으로 양자화된 모델 태그를 선택하세요. 이미 양자화된 모델을 앱이 자동 재양자화하지 않습니다. Vulkan과 Flash Attention 지원은 드라이버·모델에 따라 달라 작은 GPU 프리셋은 캐시 f16과 Flash Attention 끄기로 시작합니다.

참고: [설치 버전의 내장 GPU 환경변수](https://github.com/ollama/ollama/blob/v0.30.7/envconfig/config.go), [Ollama GPU 지원](https://docs.ollama.com/gpu).

## EXE 다시 빌드

Python과 PyInstaller가 설치된 개발 환경에서 `powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1`을 실행하면 단일 창 모드 EXE를 빌드하고 루트의 `Ollama_Park.exe`를 교체합니다. 아이콘과 CHAT HTML을 포함하고 사용자 설정·로그·모델 파일은 포함하지 않습니다. 중간 결과는 Git에서 제외된 `.data` 아래에 저장하며 100MB 이상이면 교체를 중단합니다. EXE 사용 시 설정은 `%LOCALAPPDATA%\OllamaDesk`에 저장되므로 소스 실행의 `.data/settings.json`과 별개입니다.


서버 설정을 저장한 뒤 상단 **서버 재시작**을 누르면 정지 확인 후 저장된 설정으로 시작합니다. 관리자 앱 밖에서 실행된 Windows Ollama 서버도 설치 경로를 확인하여 종료합니다. 설치·대화·콘솔 작업 중에는 재시작하지 않으며, 정지 실패 시 새 서버를 실행하지 않습니다.
GPU 그래프는 장치별 이름과 내장/외장 구분을 표시하며 알 수 없는 장치는 유형 미확인으로 표시합니다. CHAT은 저장된 유지 시간·컨텍스트·GPU 레이어와 모델별 요청 프로필을 사용합니다. CHAT에서 직접 지정한 생성 옵션은 우선 적용됩니다.

왼쪽 하단의 `일반모드로 전환` / `다크모드로 전환` 버튼으로 테마를 즉시 변경할 수 있습니다. 선택한 모드는 설정 파일에 저장되어 다음 실행에도 유지되며, 단일 EXE에서도 두 모드를 모두 사용할 수 있습니다.
