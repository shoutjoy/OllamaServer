"""Korean Tkinter desktop manager for a local Ollama installation."""
import json
import os
import queue
import shlex
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from core import Client, INSTALL_URL, NO_WINDOW, fetch_tags, find_ollama, model_name, open_url, search_models
from console_runner import ANSI, ConsoleRunner

DATA = Path(__file__).resolve().parent / '.data'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Ollama Desk · 로컬 AI 매니저')
        self.geometry('1080x780')
        self.minsize(840, 650)
        self.configure(bg='#f3f5f9')
        self.events = queue.Queue()
        self.client = Client()
        self.process = None
        self.console_runner = ConsoleRunner()
        self.command_history = []
        self.command_index = 0
        self.last_pull_log = None
        self.busy = set()
        self.cancel = threading.Event()
        self.history = []
        self.online = False
        self.closed = False
        self.tag_request = 0
        self.status = tk.StringVar(value='서버 확인 중…')
        self.install_status = tk.StringVar(value='Ollama 설치 확인 중…')
        self.selected = tk.StringVar()
        self.target = tk.StringVar(value='gemma3:1b')
        self.query = tk.StringVar()
        self.progress_text = tk.StringVar(value='설치할 모델을 검색하거나 이름:태그를 직접 입력하세요.')
        try:
            self.selected.set(json.loads((DATA / 'settings.json').read_text('utf-8')).get('model', ''))
        except (OSError, ValueError):
            pass
        self.build()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(80, self.drain)
        self.refresh()
        self.after(5000, self.poll)

    def build(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('맑은 고딕', 10))
        style.configure('TFrame', background='#f3f5f9')
        style.configure('TLabel', background='#f3f5f9', foreground='#233047')
        style.configure('TButton', padding=(12, 7))
        style.configure('Title.TLabel', font=('맑은 고딕', 23, 'bold'))
        style.configure('Treeview', rowheight=32)
        outer = ttk.Frame(self, padding=22)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Ollama Desk', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text='설치부터 모델 탐색, 로컬 대화까지 한 곳에서').pack(anchor='w', pady=(2, 15))
        server = ttk.LabelFrame(outer, text='로컬 서버 · 127.0.0.1:11434', padding=12)
        server.pack(fill='x')
        self.server_light = tk.Canvas(server, width=22, height=24, bg='#f3f5f9', highlightthickness=0)
        self.server_light.pack(side='left', padx=(0, 5))
        self.server_light_dot = self.server_light.create_oval(4, 5, 18, 19, fill='#94a3b8', outline='')
        self.server_status_label = ttk.Label(server, textvariable=self.status)
        self.server_status_label.pack(side='left', padx=(0, 14))
        for label, command in [('Ollama 설치', self.install), ('서버 시작', self.start_server),
                               ('서버 정지', self.stop_server), ('새로고침', self.refresh)]:
            ttk.Button(server, text=label, command=command).pack(side='left', padx=3)
        ttk.Label(outer, textvariable=self.install_status).pack(anchor='w', pady=8)
        row = ttk.Frame(outer)
        row.pack(fill='x', pady=(0, 12))
        ttk.Label(row, text='사용할 모델').pack(side='left', padx=(0, 10))
        self.models = ttk.Combobox(row, textvariable=self.selected, state='readonly', width=42)
        self.models.pack(side='left', fill='x', expand=True)
        self.models.bind('<<ComboboxSelected>>', self.select_model)
        ttk.Button(row, text='모델 목록 갱신', command=self.refresh).pack(side='left', padx=(8, 0))
        ttk.Button(row, text='챗 열기', command=self.open_chat).pack(side='left', padx=(8, 0))
        notebook = ttk.Notebook(outer)
        self.notebook = notebook
        notebook.pack(fill='both', expand=True)
        catalog = ttk.Frame(notebook, padding=14)
        chat = ttk.Frame(notebook, padding=14)
        logs = ttk.Frame(notebook, padding=14)
        notebook.add(catalog, text='  모델 검색 · 설치  ')
        notebook.add(chat, text='  대화  ')
        notebook.add(logs, text='  작업 로그  ')
        self.console_tab = ttk.Frame(notebook, padding=14)
        notebook.add(self.console_tab, text='  CONSOLE  ')
        ttk.Label(self.console_tab, text='Ollama 명령 실행 · Enter 전송 · ↑/↓ 명령 기록 · 실행 중 입력은 표준 입력으로 전달').pack(anchor='w', pady=(0, 8))
        self.console_view = ScrolledText(self.console_tab, state='disabled', wrap='word',
                                        bg='#101827', fg='#d6e4f0', insertbackground='white',
                                        font=('Consolas', 11), relief='flat', padx=12, pady=12)
        self.console_view.pack(fill='both', expand=True)
        console_row = ttk.Frame(self.console_tab)
        console_row.pack(fill='x', pady=(10, 0))
        self.command = tk.StringVar()
        self.command_entry = ttk.Entry(console_row, textvariable=self.command)
        self.command_entry.pack(side='left', fill='x', expand=True)
        self.command_entry.bind('<Return>', self.console_execute)
        self.command_entry.bind('<Up>', lambda e: self.console_history(-1))
        self.command_entry.bind('<Down>', lambda e: self.console_history(1))
        ttk.Button(console_row, text='실행 / 입력', command=self.console_execute).pack(side='left', padx=5)
        ttk.Button(console_row, text='명령 중지', command=self.console_stop).pack(side='left')
        ttk.Button(console_row, text='지우기', command=self.console_clear).pack(side='left', padx=(5, 0))
        self.console_write('Ollama Desk Console\n예: ollama list / ollama ps / ollama show gemma3:1b\n'
                           'ollama pull gemma3:1b / ollama run gemma3:1b "안녕하세요"\n'
                           '서버 시작: ollama serve · 서버 정지: /server-stop\n'
                           '일반 CMD/PowerShell 셸이 아닌 Ollama 전용 콘솔입니다.\n\n')
        row = ttk.Frame(catalog)
        row.pack(fill='x')
        entry = ttk.Entry(row, textvariable=self.query)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<Return>', lambda _: self.search())
        ttk.Button(row, text='공식 모델 검색', command=self.search).pack(side='left', padx=6)
        ttk.Button(row, text='공식 사이트', command=lambda: webbrowser.open('https://ollama.com/search')).pack(side='left')
        ttk.Label(catalog, text='검색 결과는 Ollama 공식 라이브러리에서 가져옵니다. 선택 후 태그를 고르세요.').pack(anchor='w', pady=8)
        holder = ttk.Frame(catalog)
        holder.pack(fill='both', expand=True)
        self.results = ttk.Treeview(holder, columns=('name', 'description'), show='headings', selectmode='browse')
        self.results.heading('name', text='모델')
        self.results.heading('description', text='설명 / 크기 / 정보')
        self.results.column('name', width=180, stretch=False)
        self.results.column('description', width=580)
        scroll = ttk.Scrollbar(holder, command=self.results.yview)
        self.results.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.results.pack(fill='both', expand=True)
        self.results.bind('<<TreeviewSelect>>', self.pick_result)
        row = ttk.Frame(catalog)
        row.pack(fill='x', pady=(14, 6))
        ttk.Label(row, text='설치 모델').pack(side='left', padx=(0, 8))
        ttk.Entry(row, textvariable=self.target, width=28).pack(side='left', fill='x', expand=True)
        self.tags = ttk.Combobox(row, state='readonly', width=19)
        self.tags.pack(side='left', padx=6)
        self.tags.bind('<<ComboboxSelected>>', self.pick_tag)
        ttk.Button(row, text='모델 설치', command=self.pull).pack(side='left')
        ttk.Button(row, text='설치 취소', command=self.cancel_pull).pack(side='left', padx=(6, 0))
        self.progress = ttk.Progressbar(catalog, maximum=100)
        self.progress.pack(fill='x', pady=7)
        ttk.Label(catalog, textvariable=self.progress_text, wraplength=900).pack(anchor='w')
        self.transcript = ScrolledText(chat, wrap='word', font=('맑은 고딕', 11), state='disabled', relief='flat', padx=12, pady=12)
        self.transcript.pack(fill='both', expand=True)
        self.prompt = ScrolledText(chat, height=3, wrap='word', font=('맑은 고딕', 11), undo=True)
        self.prompt.pack(fill='x', pady=10)
        self.prompt.bind('<Control-Return>', lambda _: self.send())
        row = ttk.Frame(chat)
        row.pack(fill='x')
        ttk.Label(row, text='Ctrl+Enter로 전송 · 모델 변경 시 대화가 초기화됩니다.').pack(side='left')
        ttk.Button(row, text='새 대화', command=self.clear_chat).pack(side='right')
        self.send_button = ttk.Button(row, text='보내기', command=self.send)
        self.send_button.pack(side='right', padx=8)
        self.log_view = ScrolledText(logs, state='disabled', wrap='word', font=('맑은 고딕', 10))
        self.log_view.pack(fill='both', expand=True)

    def open_chat(self):
        path = Path(__file__).resolve().parent / 'CHAT' / 'ollama-say.html'
        try:
            if not path.is_file():
                raise FileNotFoundError(f'챗 파일을 찾을 수 없습니다.\n{path}')
            if not webbrowser.open(path.as_uri(), new=2):
                raise RuntimeError('기본 브라우저를 열지 못했습니다.')
            self.log(f'챗 열기: {path}')
        except (OSError, RuntimeError) as exc:
            messagebox.showerror('챗 열기', str(exc), parent=self)

    def emit(self, callback, *args):
        self.events.put((callback, args))

    def drain(self):
        for _ in range(200):
            try:
                fn, args = self.events.get_nowait()
            except queue.Empty:
                break
            fn(*args)
        if not self.closed:
            self.after(80, self.drain)

    def job(self, key, work, done=None, quiet=False):
        if key in self.busy:
            return
        self.busy.add(key)
        def run():
            try:
                result = work()
                if done:
                    self.emit(done, result)
            except Exception as exc:
                self.emit(self.failure, key, str(exc), quiet)
            finally:
                self.emit(self.busy.discard, key)
        threading.Thread(target=run, daemon=True).start()

    def log(self, text):
        self.append(self.log_view, time.strftime('[%H:%M:%S] ') + text + '\n')
        self.console_write(time.strftime('[%H:%M:%S] ') + text + '\n')

    def console_write(self, text):
        text = ANSI.sub('', text).replace('\r', '\n')
        self.append(self.console_view, text)
        if int(self.console_view.index('end-1c').split('.')[0]) > 6000:
            self.console_view.configure(state='normal')
            self.console_view.delete('1.0', '1000.0')
            self.console_view.configure(state='disabled')

    def console_clear(self):
        self.console_view.configure(state='normal')
        self.console_view.delete('1.0', 'end')
        self.console_view.configure(state='disabled')

    def console_history(self, step):
        self.command_index = max(0, min(len(self.command_history), self.command_index + step))
        self.command.set(self.command_history[self.command_index] if self.command_index < len(self.command_history) else '')
        return 'break'

    def console_execute(self, _=None):
        text = self.command.get().strip()
        if not text:
            return 'break'
        self.command.set('')
        self.console_write('> ' + text + '\n')
        if 'console' in self.busy:
            try:
                self.console_runner.send(text)
            except (OSError, RuntimeError) as exc:
                self.console_write(str(exc) + '\n')
            return 'break'
        self.command_history.append(text)
        self.command_index = len(self.command_history)
        try:
            args = shlex.split(text)
            if args == ['/server-stop']:
                self.stop_server()
                return 'break'
            if args and args[0].lower() in ('ollama', 'ollama.exe'):
                args.pop(0)
            if args == ['serve']:
                self.start_server()
                return 'break'
            if not args or args[0] not in {'list', 'ps', 'show', 'pull', 'run', 'stop', 'rm', 'cp', 'help', '--help', '--version', '-v'}:
                raise ValueError('지원 명령: ollama list, ps, show, pull, run, stop, rm, cp, help, --version')
            if {'pull', 'chat', 'server', 'installer'} & self.busy:
                raise ValueError('진행 중인 앱 작업이 끝난 뒤 명령을 실행하세요.')
            exe = find_ollama()
            if not exe:
                raise ValueError('Ollama가 설치되어 있지 않습니다. 상단의 Ollama 설치를 먼저 실행하세요.')
            if args[0] == 'rm' and not messagebox.askyesno('모델 삭제', '지정한 로컬 모델을 삭제할까요?\n' + ' '.join(args[1:])):
                return 'break'
            self.console_runner = ConsoleRunner()
            runner = self.console_runner
            def work():
                return runner.run([exe] + args, lambda chunk: self.emit(self.console_write, chunk))
            def done(code):
                self.console_write(f'\n[명령 종료 · 코드 {code}]\n')
                self.refresh()
            self.job('console', work, done, quiet=True)
        except ValueError as exc:
            self.console_write('[안내] ' + str(exc) + '\n')
        return 'break'

    def console_stop(self):
        if 'console' in self.busy:
            self.console_runner.stop()
            self.console_write('\n[명령 중지 요청 — Ollama 서버는 유지됩니다.]\n')

    def follow_server_log(self, process, offset):
        def follow():
            try:
                with (DATA / 'server.log').open('r', encoding='utf-8', errors='replace') as source:
                    source.seek(offset)
                    while not self.closed:
                        chunk = source.read(8192)
                        if chunk:
                            self.emit(self.console_write, chunk)
                        elif process.poll() is not None:
                            break
                        else:
                            time.sleep(0.15)
            except OSError as exc:
                self.emit(self.console_write, f'[서버 로그 읽기 실패] {exc}\n')
        threading.Thread(target=follow, daemon=True).start()

    @staticmethod
    def append(widget, text):
        widget.configure(state='normal')
        widget.insert('end', text)
        widget.see('end')
        widget.configure(state='disabled')

    def failure(self, key, text, quiet):
        self.log(f'{key}: {text}')
        if key == 'pull':
            self.progress_text.set(text)
        if key == 'chat':
            self.append(self.transcript, '\n[응답 실패] ' + text + '\n')
            self.send_button.configure(state='normal')
        if not quiet:
            messagebox.showerror('작업 안내', text, parent=self)

    def refresh(self):
        if 'installer' not in self.busy:
            self.install_status.set('설치 위치: ' + (find_ollama() or '미설치 — Ollama 설치 버튼을 누르세요.'))
        def work():
            try:
                version = self.client.get('/api/version')['version']
                models = self.client.get('/api/tags').get('models', [])
                return version, models
            except Exception:
                return None, []
        self.job('refresh', work, self.refreshed, quiet=True)

    def refreshed(self, result):
        version, models = result
        was_online = self.online
        self.online = version is not None
        self.status.set(f'서버 동작 중 · {version}' if self.online else '서버 응답 없음')
        color = '#16a34a' if self.online else '#94a3b8'
        self.server_light.itemconfigure(self.server_light_dot, fill=color)
        self.server_status_label.configure(foreground='#15803d' if self.online else '#64748b')
        if self.online and not was_online:
            self.log('서버 동작 확인: Ollama가 요청을 받을 준비가 되었습니다.')
            self.bell()
            notice = tk.Toplevel(self)
            notice.title('Ollama 서버 알림')
            notice.transient(self)
            notice.resizable(False, False)
            ttk.Label(notice, text='● Ollama 서버가 동작 중입니다.', foreground='#15803d', padding=20).pack()
            ttk.Button(notice, text='확인', command=notice.destroy).pack(pady=(0, 12))
            notice.after(3500, notice.destroy)
        elif was_online and not self.online:
            self.log('서버 응답이 없어 표시등을 껐습니다.')
        names = [m['name'] for m in models]
        self.models.configure(values=names)
        if names and self.selected.get() not in names:
            self.selected.set(names[0])
            self.select_model()

    def poll(self):
        if not self.closed:
            self.refresh()
            self.after(5000, self.poll)

    def start_server(self):
        self.notebook.select(self.console_tab)
        if 'console' in self.busy:
            self.console_write('실행 중인 콘솔 명령을 먼저 중지하세요.\n')
            return
        if 'server' in self.busy:
            return
        exe = find_ollama()
        if not exe:
            messagebox.showinfo('Ollama 설치 필요', '먼저 Ollama 설치 버튼으로 설치하세요.')
            return
        def work():
            try:
                self.client.get('/api/version')
                return '이미 실행 중인 서버에 연결했습니다.'
            except Exception:
                pass
            DATA.mkdir(exist_ok=True)
            env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11434')
            with (DATA / 'server.log').open('ab') as output:
                offset = output.tell()
                self.process = subprocess.Popen([exe, 'serve'], env=env, stdout=output,
                                                stderr=output, creationflags=NO_WINDOW)
            self.emit(self.console_write, '> ollama serve\n')
            self.follow_server_log(self.process, offset)
            for _ in range(30):
                try:
                    self.client.get('/api/version', timeout=1)
                    return '서버가 시작되었습니다.'
                except Exception:
                    if self.process.poll() is not None:
                        raise RuntimeError('서버가 종료되었습니다. .data/server.log를 확인하세요.')
                    time.sleep(0.5)
            raise RuntimeError('서버 시작 확인 시간이 초과되었습니다. 로그를 확인하세요.')
        self.job('server', work, lambda text: (self.log(text), self.refresh()))

    def stop_server(self):
        if 'server' in self.busy:
            return
        if {'pull', 'chat', 'console'} & self.busy:
            messagebox.showinfo('작업 중', '모델 설치 또는 응답 작업이 끝난 뒤 서버를 정지하세요.')
            return
        owned = self.process is not None and self.process.poll() is None
        if not owned and not messagebox.askyesno('기존 Ollama 서버 정지',
                '기존 Ollama 앱과 서버를 종료할까요?\n다른 앱에서 진행 중인 Ollama 작업도 중단될 수 있습니다.'):
            return
        def work():
            if owned:
                self.process.terminate()
                self.process.wait(timeout=10)
            elif os.name == 'nt':
                exe = find_ollama()
                if not exe:
                    raise RuntimeError('실행 파일 경로를 확인할 수 없습니다. 시스템 트레이에서 Ollama를 종료하세요.')
                # Only terminate binaries from the discovered Ollama installation directory.
                directory = str(Path(exe).resolve().parent).replace("'", "''")
                script = "$d='" + directory + "'; Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and ([IO.Path]::GetDirectoryName($_.ExecutablePath) -eq $d) -and ($_.Name -in @('ollama app.exe','ollama.exe')) } | Sort-Object Name | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }"
                subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                               check=True, capture_output=True, creationflags=NO_WINDOW, timeout=20)
            else:
                raise RuntimeError('외부에서 시작한 서버는 해당 터미널/서비스에서 종료하세요.')
            for _ in range(10):
                try:
                    self.client.get('/api/version', timeout=1)
                except Exception:
                    return '서버 정지를 확인했습니다.'
                time.sleep(0.5)
            raise RuntimeError('서버가 여전히 응답합니다. 시스템 트레이나 서비스 설정을 확인하세요.')
        self.job('server', work, lambda text: (self.log(text), self.refresh()))

    def install(self):
        if 'console' in self.busy:
            messagebox.showinfo('명령 실행 중', '콘솔 명령을 먼저 중지하세요.')
            return
        if os.name != 'nt':
            webbrowser.open('https://ollama.com/download')
            return
        if 'installer' in self.busy:
            return
        if not messagebox.askyesno('Ollama 설치', '공식 Windows 설치 파일을 다운로드하고 실행합니다.\n설치 마법사에서 설치를 완료해 주세요. 계속할까요?'):
            return
        def work():
            DATA.mkdir(exist_ok=True)
            installer = DATA / 'OllamaSetup.exe'
            partial = installer.with_suffix('.download')
            try:
                with open_url(INSTALL_URL, timeout=60) as response, partial.open('wb') as output:
                    total = int(response.headers.get('Content-Length', 0))
                    count = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        count += len(chunk)
                        self.emit(self.install_status.set, f'설치 파일 다운로드: {count / 1048576:.1f} MB' + (f' / {total / 1048576:.1f} MB' if total else ''))
                    if total and count != total:
                        raise RuntimeError('설치 파일 다운로드가 불완전합니다.')
                partial.replace(installer)
                path = str(installer).replace("'", "''")
                script = "$s=Get-AuthenticodeSignature -LiteralPath '" + path + "'; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'Ollama') { exit 1 }"
                verified = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                                          creationflags=NO_WINDOW, timeout=60)
                if verified.returncode:
                    raise RuntimeError('공식 Ollama 디지털 서명을 검증하지 못해 실행을 중단했습니다.')
                self.emit(self.install_status.set, '설치 마법사에서 설치를 완료하세요.')
                result = subprocess.Popen([str(installer)]).wait()
                if result != 0:
                    raise RuntimeError(f'설치가 취소되었거나 실패했습니다 (코드 {result}).')
                if not find_ollama():
                    raise RuntimeError('설치 경로를 확인하지 못했습니다. 사용자 지정 설치라면 PATH에 Ollama를 추가하세요.')
                return 'Ollama 설치를 확인했습니다.'
            finally:
                partial.unlink(missing_ok=True)
        self.job('installer', work, lambda text: (self.log(text), self.refresh()))

    def search(self):
        query = self.query.get().strip()
        self.progress_text.set('공식 라이브러리 검색 중…')
        self.job('search', lambda: search_models(query), self.show_results)

    def show_results(self, rows):
        self.results.delete(*self.results.get_children())
        for name, description in rows:
            self.results.insert('', 'end', values=(name, description))
        self.progress_text.set(f'{len(rows)}개 모델을 가져왔습니다.' if rows else '검색 결과가 없습니다. 공식 사이트를 확인하거나 모델 이름을 직접 입력하세요.')

    def pick_result(self, _=None):
        selection = self.results.selection()
        if not selection:
            return
        name = self.results.item(selection[0], 'values')[0]
        self.target.set(name + ':latest')
        self.tags.set('latest')
        self.tags.configure(values=['latest'])
        self.tag_request += 1
        request = self.tag_request
        def done(values):
            if request == self.tag_request:
                self.tags.configure(values=values or ['latest'])
                self.progress_text.set('태그별 크기는 공식 사이트에서 확인하세요. 큰 모델은 많은 디스크 공간과 메모리가 필요합니다.')
        self.job(f'tags-{request}', lambda: fetch_tags(name), done)

    def pick_tag(self, _=None):
        self.target.set(self.target.get().split(':')[0] + ':' + self.tags.get())

    def cancel_pull(self):
        if 'pull' in self.busy:
            self.cancel.set()
            self.progress_text.set('취소 요청됨 — 다음 서버 응답에서 연결을 닫습니다. 최대 120초 걸릴 수 있습니다.')

    def pull(self):
        if 'console' in self.busy:
            messagebox.showinfo('명령 실행 중', '콘솔 명령을 먼저 중지하세요.')
            return
        if 'pull' in self.busy:
            return
        if 'chat' in self.busy:
            messagebox.showinfo('대화 진행 중', '응답이 끝난 뒤 모델을 설치하세요.')
            return
        try:
            name = model_name(self.target.get())
        except ValueError as exc:
            messagebox.showerror('모델 이름', str(exc))
            return
        if not self.online:
            messagebox.showinfo('서버 필요', '먼저 서버를 시작하세요.')
            return
        self.cancel.clear()
        self.progress['value'] = 0
        self.progress_text.set(name + ' 설치 요청 중…')
        self.log('모델 설치 요청: ' + name)
        self.last_pull_log = None
        def work():
            success = False
            for item in self.client.stream('/api/pull', {'model': name, 'stream': True}, self.cancel):
                total, completed = item.get('total', 0), item.get('completed', 0)
                pct = completed / total * 100 if total else 0
                text = item.get('status', '')
                if total:
                    text += f' · 현재 파일 {pct:.1f}% ({completed / 1048576:.1f}/{total / 1048576:.1f} MB)'
                self.emit(self.update_progress, pct, text)
                success = item.get('status') == 'success'
            if not success:
                raise RuntimeError('완료 응답 없이 연결이 끝났습니다. 모델 목록을 확인하고 다시 시도하세요.')
            names = [item['name'] for item in self.client.get('/api/tags')['models']]
            expected = name if ':' in name else name + ':latest'
            if expected not in names:
                raise RuntimeError('다운로드 후 설치된 모델 목록에서 모델을 확인하지 못했습니다.')
            return expected
        self.job('pull', work, self.pulled)

    def update_progress(self, value, text):
        self.progress['value'] = value
        self.progress_text.set(text)
        marker = (text.split(' · ')[0], int(value) // 10)
        if marker != self.last_pull_log:
            self.console_write('[모델 설치] ' + text + '\n')
            self.last_pull_log = marker

    def pulled(self, name):
        self.update_progress(100, name + ' 설치 완료 — 사용할 모델로 선택했습니다.')
        self.selected.set(name)
        self.select_model()
        self.refresh()
        self.log(name + ' 설치 완료')

    def select_model(self, _=None):
        DATA.mkdir(exist_ok=True)
        try:
            (DATA / 'settings.json').write_text(json.dumps({'model': self.selected.get()}, ensure_ascii=False), 'utf-8')
        except OSError as exc:
            self.log('설정 저장 실패: ' + str(exc))
        self.clear_chat()

    def clear_chat(self):
        if 'chat' in self.busy:
            return
        self.history = []
        self.transcript.configure(state='normal')
        self.transcript.delete('1.0', 'end')
        self.transcript.configure(state='disabled')

    def send(self):
        if 'console' in self.busy:
            messagebox.showinfo('명령 실행 중', '콘솔 명령을 먼저 중지하세요.')
            return 'break'
        if 'chat' in self.busy:
            return 'break'
        if 'pull' in self.busy:
            messagebox.showinfo('설치 진행 중', '모델 설치가 끝난 뒤 대화를 시작하세요.')
            return 'break'
        text = self.prompt.get('1.0', 'end').strip()
        model = self.selected.get()
        if not text:
            return 'break'
        if not self.online or not model:
            messagebox.showinfo('모델 선택', '서버를 시작하고 설치된 모델을 선택하세요.')
            return 'break'
        messages = self.history + [{'role': 'user', 'content': text}]
        self.prompt.delete('1.0', 'end')
        self.append(self.transcript, '\n나: ' + text + '\n\n' + model + ': ')
        self.send_button.configure(state='disabled')
        self.models.configure(state='disabled')
        def work():
            answer = ''
            complete = False
            try:
                for item in self.client.stream('/api/chat', {'model': model, 'messages': messages, 'stream': True}):
                    chunk = item.get('message', {}).get('content', '')
                    answer += chunk
                    self.emit(self.append, self.transcript, chunk)
                    complete = item.get('done', False)
                if not complete:
                    raise RuntimeError('완료 응답 없이 연결이 종료되었습니다.')
                return messages + [{'role': 'assistant', 'content': answer}]
            finally:
                self.emit(self.models.configure, {'state': 'readonly'})
        def done(history):
            self.history = history if self.selected.get() == model else []
            self.append(self.transcript, '\n')
            self.send_button.configure(state='normal')
        self.job('chat', work, done)
        return 'break'

    def close(self):
        active = self.busy - {'refresh'}
        if active and not messagebox.askyesno('작업 진행 중', '진행 중인 작업의 연결이 끊어집니다. 앱을 닫을까요?\nOllama 서버와 실행 중인 설치 마법사는 유지됩니다.'):
            return
        self.cancel.set()
        self.console_runner.stop()
        self.closed = True
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
