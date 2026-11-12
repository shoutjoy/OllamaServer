# Ollama Desk 런타임 진단 · 2026-11-10

## 확인된 문제와 수정

- 실제 Ollama 0.33.2의 `gemma4:e4b` 빈 generate 요청이 HTTP 500 (`Gemma4Assistant requires ctx_other … error loading model: vector`)으로 실패했다.
- 기존 CLI 선로딩은 대화의 num_ctx / GPU 설정을 전달하지 않았다. 같은 chat_performance 설정을 사용하는 빈 generate API로 통일하고 별도 CLI와 완료 후 ps 조회를 제거했다. keep_alive 0은 로딩 성공으로 오인하지 않고 거부한다.
- 알려진 Gemma 4 오류에 한해 draft_num_predict=0으로 1회 재시도한다. 일반 실패·메모리 부족·전송된 응답 이후에는 재전송하지 않는다. 관리자와 호환 서버가 Client를 공유해 후속 요청에 복구 옵션을 유지한다. 프로세스 재시작 시 다시 감지할 수 있다.
- 시작 시 고정 모델로 저장 선택을 덮어쓰지 않는다. 이미 적재된 모델이 있으면 시작 시 추가 로딩을 생략한다. 설치 모델이 없으면 자동 다운로드하지 않는다.
- 2초마다 version/tags/ps를 모두 조회하던 흐름을 ps 2초 / 목록·버전 30초로 나누고 자원 감시의 중복 API 조회를 제거했다. 정상 연결 시 약 1.9회/초였던 조회가 약 0.57회/초로 줄어든다. 수동 새로고침과 오류 확인은 추가 조회한다.
- GPU/NPU 성능 카운터 PowerShell 실행을 5초마다에서 15초마다로 줄였다. CPU/RAM 그래프는 5초마다 유지하며 장치 값은 직전 측정값을 사용한다.
- 연결 알림음·자동 팝업을 제거했다. 같은 모델 목록은 재설정하지 않는다. 외부 앱 모델 감지로 관리자 대화를 지우지 않는다.
- 실제 Windows 확인에서 대화 출력창이 입력창과 전송 버튼을 아래로 밀어내는 문제를 발견했다. 입력창/버튼 공간을 먼저 배정하고 상단 여백·그래프를 줄였다. 기본 1380×780 창의 입력창과 전송 버튼이 보이는 실제 Tk 위젯 검사를 추가했다.
- Tkinter 스트리밍은 빈 토큰 이벤트를 생략하고 약 50ms 단위로 묶어 갱신한다. 첫 내용과 완료는 즉시 반영한다. 빈 답변과 완료 없는 연결 종료는 오류로 표시한다. 차가운 모델의 HTTP 읽기 제한을 300초로 통일했다.
- Windows 자동 실행 레지스트리를 읽을 수 없어도 앱 시작이 중단되지 않게 했다.

## MDPro 호환 서버

앱 시작 시 loopback 8767에서 기존 웹 채팅 서버를 시작한다. MDPro Ollama 기본 URL을 http://127.0.0.1:8767로 지정하면 /api/tags, version, ps, show, generate, chat이 선택 엔진의 고정 로컬 주소로 전달된다. 임의 대상 URL이나 모델 삭제·설치 경로는 제공하지 않는다. 기존 /ollama/api 경로도 유지한다. 호출자의 명시적 옵션과 유지 시간은 보존한다.

MDPro HTTPS 출처와 HTTP localhost에 CORS/preflight를 지원한다. 비스트림은 JSON, 스트림은 NDJSON으로 반환하고 매 응답을 flush한다. 헤더는 첫 유효 응답까지 보류해 최초 실패를 HTTP 502로 전달하고 중간 실패는 NDJSON error로 전달한다. 기존 11434 직접 호출에는 관리자 복구 처리가 적용되지 않는다. 별도 도메인의 WebDAV 및 브라우저 로컬 네트워크 권한은 이 검사 범위 밖이다.

## 실측 결과

설치 모델 13개. 기존 직접 서버 CORS는 MDPro 출처에 200 / Access-Control-Allow-Origin:*이므로 해당 시점의 CORS 차단은 원인이 아니었다.

직접 API 복구: 초기 실패+재시도 11.625초, GPU 적재 3,475,578,551 bytes, 이후 짧은 답변 OK의 첫 토큰 0.266초 / 전체 0.344초 / done:true.

MDPro 형식 호환 경로: OPTIONS 204, 출처 허용 일치, 설치 모델 목록 13개, 빈 generate done:true. 최초 적재는 실패 재시도를 포함해 15.859초였다.

| 회차 | 첫 내용 수신 | 전체 완료 | 답변 | done | 모델 load_duration |
|---|---:|---:|---|---|---:|
| 1 | 0.328초 | 0.391초 | OK | true | 23.081ms |
| 2 | 0.437초 | 0.484초 | OK | true | 16.860ms |
| 3 | 0.484초 | 0.516초 | OK | true | 9.424ms |

원시 결과: `.data/runtime-diagnosis-20261110.json`. 측정 스크립트: `.data/diagnose_runtime.py`. 모두 로컬 진단 파일이며 Git에는 포함하지 않는다. 성공 응답의 기존 기준선이 없으므로 속도 향상 배수는 주장하지 않는다. 장문·이미지·동시 사용·다른 하드웨어의 응답 속도는 별도로 측정해야 한다.

## 검증과 실행 파일

- python -m unittest discover -s tests -q: 116/116 통과 (실제 loopback HTTP 테스트 포함).
- node --test tests/*.test.cjs: 15/15 통과. 이전 테스트의 저장 복원 준비 상태 mock과 관리자 프록시 연결 계약을 현행 코드에 맞게 보완했다.
- sandbox 내부의 설치 자식 프로세스 종료 및 임시 경로 대소문자 테스트는 환경 제약으로 실패했지만 실제 Windows 권한으로 전체 검사는 통과했다.
- python smoke_test.py: 실제 Tk 위젯의 검색·설치 진행·대화·콘솔·설치 취소 및 재시도 검사 통과 (모델/다운로드 전송은 mock). 자동 시작 작업을 격리하고 현행 카탈로그 3열 fixture를 반영했다.
- PyInstaller 6.22.2 / Python 3.10.11의 onefile windowed 수정본: `.data/fast-final/Ollama_Park_Fast.exe`.
- 기존 미커밋 변경, staged 항목과 EXE 충돌은 보존했다. 커밋·푸시·배포는 수행하지 않았다.
- MDPro와 같은 요청 형식의 실제 HTTP 왕복을 검증했다. 실제 MDPro 브라우저 UI에서 주소를 저장하고 질문하는 전체 흐름과 Lemonade 실서버는 검증하지 않았다.

API 사양 근거: [공식 Ollama FAQ](https://docs.ollama.com/faq), [generate API](https://docs.ollama.com/api/generate). 빈 요청 선로딩, keep_alive, num_ctx와 GPU 배치 의미를 확인했다.

Windows 확인: 첫 수정본 EXE를 실제 실행해 서버 온라인·기존 Gemma 4 GPU 적재 유지·시작 시 추가 로딩 생략을 확인했다. 이 과정에서 입력창 배치 결함을 찾아 수정했다. 최종 배치는 Tk 실위젯 회귀로 검증했고 사용 중인 확인용 앱은 종료하지 않았다. 최종 EXE는 별도 fast-final 폴더에 빌드한다.

최종 빌드 SHA256: `c18f80b42bc0ec42f95f7e88b352bb696b331651de55596e9d5fd4548389ed85` (13,586,075 bytes).
