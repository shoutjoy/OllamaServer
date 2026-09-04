"""Korean Tkinter desktop manager for a local Ollama installation."""
import json
import os
import platform
import queue
import shlex
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from urllib.parse import quote

from core import Client, NO_WINDOW, fetch_tags, find_ollama, model_name, models_directory, search_models
from console_runner import ANSI, ConsoleRunner
from installer_download import DownloadCancelled, download_installer
from install_commands import COMMANDS, install_args
from install_terminal import InstallTerminalRunner
from CHAT.serve_ollama_say import create_server as create_chat_server

SOURCE_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', SOURCE_ROOT))
DATA = ((Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'OllamaDesk')
        if getattr(sys, 'frozen', False) else SOURCE_ROOT / '.data')
MDPRO_URL = 'https://mdproviewer.vercel.app/'
# Browser chat UIs (챗 열기, MDpro, file:// HTML) need Ollama to allow their Origin.
DEFAULT_CORS_ORIGINS = '*'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Ollama Desk · 로컬 AI 매니저')
        icon_path = RESOURCE_ROOT / 'Icon' / 'Ollama.png'
        if icon_path.is_file():
            try:
                self.app_icon = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, self.app_icon)
            except tk.TclError:
                self.app_icon = None
        self.geometry('1380x780')
        self.minsize(1100, 650)
        self.configure(bg='#f3f5f9')
        self.events = queue.Queue()
        self.client = Client()
        self.process = None
        self.chat_process = None
        self.chat_server = None
        self.console_runner = ConsoleRunner()
        self.install_terminal_active = False
        self.command_history = []
        self.command_index = 0
        self.last_pull_log = None
        self.busy = set()
        self.cancel = threading.Event()
        self.installer_cancel = threading.Event()
        self.installer_path = DATA / 'OllamaSetup.exe'
        self.history = []
        self.online = False
        self.closed = False
        self.tag_request = 0
        self.status = tk.StringVar(value='서버 확인 중…')
        self.install_status = tk.StringVar(value='Ollama 설치 확인 중…')
        self.download_status = tk.StringVar(value='설치 파일 다운로드 대기')
        self.selected = tk.StringVar()
        self.cors_origins = tk.StringVar(value=DEFAULT_CORS_ORIGINS)
        self.target = tk.StringVar(value='gemma3:1b')
        self.query = tk.StringVar()
        self.progress_text = tk.StringVar(value='설치할 모델을 검색하거나 이름:태그를 직접 입력하세요.')
        self.load_settings()
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
        shell = tk.Frame(self, bg='#f3f5f9')
        shell.pack(fill='both', expand=True)

        # Keep the brand visible beside the workspace, matching the desktop
        # layout while leaving all controls in the main panel on the right.
        brand = tk.Frame(shell, width=255, bg='#ffffff', highlightthickness=0)
        brand.pack(side='left', fill='y')
        brand.pack_propagate(False)
        brand_icon_path = RESOURCE_ROOT / 'Icon' / 'Ollama-sidebar.png'
        if brand_icon_path.is_file():
            try:
                self.brand_icon = tk.PhotoImage(file=brand_icon_path)
                tk.Label(brand, image=self.brand_icon, bg='#ffffff', borderwidth=0).pack(
                    anchor='n', pady=(62, 0), padx=9)
            except tk.TclError:
                self.brand_icon = None
        tk.Label(
            brand,
            text='제작: 박중희 (연세대 인지공학 박사,\n심리학과 겸임교수)\nshoutjoy1@yonsei.ac.kr',
            bg='#ffffff', fg='#334155', font=('맑은 고딕', 9),
            justify='center', wraplength=235,
        ).pack(anchor='n', pady=(18, 0), padx=10)

        outer = ttk.Frame(shell, padding=22)
        outer.pack(side='left', fill='both', expand=True)
        ttk.Label(outer, text='Ollama Desk', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text='설치부터 모델 탐색, 로컬 대화까지 한 곳에서').pack(anchor='w', pady=(2, 15))
        server = ttk.LabelFrame(outer, text='로컬 서버 · 127.0.0.1:11434', padding=12)
        server.pack(fill='x')
        self.server_light = tk.Canvas(server, width=22, height=24, bg='#f3f5f9', highlightthickness=0)
        self.server_light.pack(side='left', padx=(0, 5))
        self.server_light_dot = self.server_light.create_oval(4, 5, 18, 19, fill='#94a3b8', outline='')
        self.server_status_label = ttk.Label(server, textvariable=self.status)
        self.server_status_label.pack(side='left', padx=(0, 14))
        for label, command in [('서버 시작', self.start_server), ('서버 정지', self.stop_server),
                               ('새로고침', self.refresh), ('챗 열기', self.open_chat),
                               ('MDpro', self.open_mdpro)]:
            ttk.Button(server, text=label, command=command).pack(side='left', padx=3)
        self.install_nav_button = ttk.Button(server, text='Ollama 설치', command=self.show_install_tab)
        self.install_nav_button.pack(side='right', padx=3)
        cors = ttk.Frame(outer)
        cors.pack(fill='x', pady=(8, 0))
        ttk.Label(cors, text='CORS (OLLAMA_ORIGINS)').pack(side='left', padx=(0, 8))
        cors_entry = ttk.Entry(cors, textvariable=self.cors_origins)
        cors_entry.pack(side='left', fill='x', expand=True)
        cors_entry.bind('<FocusOut>', lambda _: self.save_settings(note_cors=True))
        cors_entry.bind('<Return>', lambda _: self.save_settings(note_cors=True))
        ttk.Button(cors, text='모두 허용 (*)', command=self.reset_cors_origins).pack(side='left', padx=(6, 0))
        ttk.Button(cors, text='저장', command=lambda: self.save_settings(note_cors=True)).pack(side='left', padx=(6, 0))
        ttk.Label(
            outer,
            text='서버 시작 시 적용됩니다. 예: * 또는 http://127.0.0.1:8767,https://mdproviewer.vercel.app',
        ).pack(anchor='w', pady=(4, 0))
        ttk.Label(outer, textvariable=self.install_status).pack(anchor='w', pady=8)
        folders = ttk.Frame(outer)
        folders.pack(fill='x', pady=(0, 8))
        ttk.Button(folders, text='Ollama 설치 폴더 열기',
                   command=lambda: self.open_ollama_folder('install')).pack(side='left')
        ttk.Button(folders, text='모델 다운로드 폴더 열기',
                   command=lambda: self.open_ollama_folder('models')).pack(side='left', padx=(8, 0))
        row = ttk.Frame(outer)
        row.pack(fill='x', pady=(0, 12))
        ttk.Label(row, text='사용할 모델').pack(side='left', padx=(0, 10))
        self.models = ttk.Combobox(row, textvariable=self.selected, state='readonly', width=42)
        self.models.pack(side='left', fill='x', expand=True)
        self.models.bind('<<ComboboxSelected>>', self.select_model)
        ttk.Button(row, text='모델 목록 갱신', command=self.refresh).pack(side='left', padx=(8, 0))
        notebook = ttk.Notebook(outer)
        self.notebook = notebook
        notebook.pack(fill='both', expand=True)
        catalog = ttk.Frame(notebook, padding=14)
        chat = ttk.Frame(notebook, padding=14)
        logs = ttk.Frame(notebook, padding=14)
        notebook.add(catalog, text='  모델 검색 · 설치  ')
        notebook.add(chat, text='  대화  ')
        notebook.add(logs, text='  작업 로그  ')
        self.build_install_tab()
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
        self.access_log_tab = ttk.Frame(notebook, padding=14)
        notebook.add(self.access_log_tab, text='  접속 LOG  ')
        access_header = ttk.Frame(self.access_log_tab)
        access_header.pack(fill='x', pady=(0, 8))
        ttk.Label(access_header, text='AI 접속 및 사용 기록 · 서버 연결, 모델, 질문, 응답, 오류').pack(side='left')
        ttk.Button(access_header, text='기록 지우기', command=self.clear_access_log).pack(side='right')
        self.access_log_view = ScrolledText(
            self.access_log_tab, state='disabled', wrap='word', bg='#101827', fg='#d6e4f0',
            insertbackground='white', font=('Consolas', 10), relief='flat', padx=12, pady=12)
        self.access_log_view.pack(fill='both', expand=True)
        self.load_access_log()
        self.access_log('APP', 'Ollama Desk 실행')
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
        self.results.bind('<Double-1>', self.show_model_details)
        self.results.bind('<Return>', self.show_model_details)
        actions = ttk.Frame(catalog)
        actions.pack(fill='x', pady=(6, 0))
        ttk.Button(actions, text='전체 설명 · 새 창', command=self.show_model_details).pack(side='left')
        ttk.Button(actions, text='선택 모델 공식 사이트', command=self.open_model_site).pack(side='left', padx=6)
        ttk.Button(actions, text='콘솔에서 pull', command=self.pull_in_console).pack(side='left')
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

    def show_install_tab(self):
        self.notebook.select(self.install_tab)

    def build_install_tab(self):
        self.install_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.install_tab, text='  Ollama 설치  ')
        self.install_canvas = tk.Canvas(self.install_tab, bg='#f3f5f9', highlightthickness=0)
        scroll = ttk.Scrollbar(self.install_tab, orient='vertical', command=self.install_canvas.yview)
        scroll.pack(side='right', fill='y')
        self.install_canvas.configure(yscrollcommand=scroll.set)
        self.install_canvas.pack(side='left', fill='both', expand=True)
        body = ttk.Frame(self.install_canvas)
        body_window = self.install_canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda _: self.install_canvas.configure(scrollregion=self.install_canvas.bbox('all')))
        self.install_canvas.bind('<Configure>', lambda event: self.install_canvas.itemconfigure(
            body_window, width=event.width, height=max(event.height, body.winfo_reqheight())))
        download = ttk.LabelFrame(body, text='Windows 다운로드 앱으로 설치', padding=8)
        download.pack(fill='x')
        self.install_button = ttk.Button(download, text='Windows 다운로드 앱으로 설치', command=self.install,
                                         state='normal' if platform.system() == 'Windows' else 'disabled')
        self.install_button.pack(anchor='w')
        location = ttk.Entry(download)
        location.insert(0, str(self.installer_path))
        location.configure(state='readonly')
        location.pack(fill='x', pady=4)
        controls = ttk.Frame(download)
        controls.pack(fill='x')
        ttk.Button(controls, text='다운로드 폴더 열기', command=self.open_download_folder).pack(side='left')
        self.stop_download_button = ttk.Button(controls, text='다운로드 중지',
                                               command=self.stop_installer_download, state='disabled')
        self.stop_download_button.pack(side='left', padx=8)
        ttk.Label(download, textvariable=self.download_status).pack(anchor='w')
        scripts = ttk.LabelFrame(body, text='앱 내부 터미널로 설치 · 현재 OS: ' + platform.system(), padding=8)
        scripts.pack(fill='x', pady=6)
        scripts.columnconfigure(1, weight=1)
        self.script_buttons = {}
        for row, (system, label) in enumerate([('Windows', '윈도우'), ('Linux', '리눅스'), ('Darwin', '맥')]):
            button = ttk.Button(scripts, text=label + ' 터미널 설치',
                                command=lambda os_name=system: self.start_terminal_install(os_name),
                                state='normal' if system == platform.system() else 'disabled')
            button.grid(row=row, column=0, sticky='w', pady=2)
            self.script_buttons[system] = button
            command = ttk.Entry(scripts, width=40)
            command.insert(0, COMMANDS[system])
            command.configure(state='readonly')
            command.grid(row=row, column=1, sticky='ew', padx=6)
            ttk.Button(scripts, text='복사', command=lambda os_name=system: self.copy_install_command(os_name)).grid(row=row, column=2)
        ttk.Label(body, text='현재 OS만 실행 가능 · 권한 확인창은 별도로 표시될 수 있습니다.\n중지는 이미 설치된 파일을 되돌리지 않습니다.').pack(anchor='w')
        self.install_terminal_view = ScrolledText(body, height=6, state='disabled', wrap='word',
                                                bg='#101827', fg='#d6e4f0', font=('Consolas', 10))
        self.install_terminal_view.pack(fill='both', expand=True, pady=5)
        inputs = ttk.Frame(body)
        inputs.pack(fill='x')
        self.install_input = ttk.Entry(inputs, show='*')
        self.install_input.pack(side='left', fill='x', expand=True)
        self.install_input.bind('<Return>', self.send_install_input)
        ttk.Button(inputs, text='입력 전송', command=self.send_install_input).pack(side='left', padx=6)
        self.stop_terminal_button = ttk.Button(inputs, text='터미널 중지', command=self.stop_terminal_install, state='disabled')
        self.stop_terminal_button.pack(side='left')
        self.install_terminal_write('설치 방법을 선택하세요. 출력은 이곳에 표시됩니다.\n입력란은 암호를 가려 표시하며 전송한 내용을 로그에 기록하지 않습니다.\n')

    def copy_install_command(self, system):
        self.clipboard_clear()
        self.clipboard_append(COMMANDS[system])

    def install_terminal_write(self, text):
        self.append(self.install_terminal_view, ANSI.sub('', text).replace('\r', '\n'))
        if int(self.install_terminal_view.index('end-1c').split('.')[0]) > 6000:
            self.install_terminal_view.configure(state='normal')
            self.install_terminal_view.delete('1.0', '1000.0')
            self.install_terminal_view.configure(state='disabled')

    def send_install_input(self, _=None):
        if self.install_terminal_active:
            value = self.install_input.get()
            self.install_input.delete(0, 'end')
            try:
                self.console_runner.send(value)
            except (OSError, RuntimeError) as exc:
                self.install_terminal_write(str(exc) + '\n')
        return 'break'

    def stop_terminal_install(self):
        if self.install_terminal_active:
            self.stop_terminal_button.configure(state='disabled')
            self.install_terminal_write('\n[중지 요청 · 설치된 파일은 자동으로 제거되지 않습니다.]\n')
            runner = self.console_runner
            def stop():
                try:
                    runner.stop()
                except Exception as exc:
                    self.emit(self.install_terminal_write, f'\n[중지 실패] {exc}\n')
                    self.emit(lambda: self.stop_terminal_button.configure(state='normal')
                              if self.install_terminal_active and self.console_runner is runner else None)
            threading.Thread(target=stop, daemon=True).start()

    def terminal_install_finished(self):
        self.install_terminal_active = False
        self.install_input.delete(0, 'end')
        self.stop_terminal_button.configure(state='disabled')
        self.install_button.configure(state='normal' if platform.system() == 'Windows' else 'disabled')
        for system, button in self.script_buttons.items():
            button.configure(state='normal' if system == platform.system() else 'disabled')
        self.refresh()

    def start_terminal_install(self, system):
        self.show_install_tab()
        if {'console', 'installer', 'pull', 'chat', 'server'} & self.busy:
            messagebox.showinfo('작업 진행 중', '현재 작업을 완료하거나 중지한 뒤 설치하세요.', parent=self)
            return
        try:
            args = install_args(system)
        except ValueError as exc:
            messagebox.showerror('터미널 설치', str(exc), parent=self)
            return
        if not messagebox.askyesno('터미널 설치', '아래 공식 스크립트를 다운로드하여 이 컴퓨터에 실행합니다.\n설치 또는 업데이트로 시스템이 변경되며 관리자 권한을 요청할 수 있습니다.\n\n' + COMMANDS[system] + '\n\n실행할까요?', parent=self):
            return
        self.console_runner = InstallTerminalRunner()
        runner = self.console_runner
        self.install_terminal_active = True
        self.install_button.configure(state='disabled')
        for button in self.script_buttons.values():
            button.configure(state='disabled')
        self.stop_terminal_button.configure(state='normal')
        self.install_canvas.yview_moveto(1)
        self.install_terminal_write('\n> ' + COMMANDS[system] + '\n')
        def work():
            try:
                code = runner.run(args, lambda text: self.emit(self.install_terminal_write, text))
                status = '중지됨' if runner.cancel.is_set() else ('스크립트 실행 완료' if code == 0 else '실패')
                self.emit(self.install_terminal_write, f'\n[{status} · 종료 코드 {code}]\n')
            except Exception as exc:
                self.emit(self.install_terminal_write, f'\n[실행 실패] {exc}\n')
            finally:
                self.emit(self.terminal_install_finished)
        self.job('console', work, quiet=True)

    def open_chat(self):
        url = 'http://127.0.0.1:8767'
        try:
            try:
                with socket.create_connection(('127.0.0.1', 8767), timeout=0.3):
                    pass
            except OSError:
                self.chat_server = create_chat_server()
                threading.Thread(target=self.chat_server.serve_forever, daemon=True).start()
                for _ in range(30):
                    try:
                        with socket.create_connection(('127.0.0.1', 8767), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError('챗 서버 시작 시간이 초과되었습니다.')

            if not webbrowser.open(url, new=2):
                raise RuntimeError('기본 브라우저를 열지 못했습니다.')
            self.log(f'챗 열기: {url}')
        except (OSError, RuntimeError) as exc:
            messagebox.showerror('챗 열기', str(exc), parent=self)

    def open_mdpro(self):
        if webbrowser.open(MDPRO_URL, new=2):
            self.log(f'MDpro 열기: {MDPRO_URL}')
        else:
            messagebox.showerror('MDpro', '기본 브라우저를 열지 못했습니다.', parent=self)

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

    @property
    def access_log_path(self):
        return DATA / 'access.log'

    def load_access_log(self):
        try:
            text = self.access_log_path.read_text('utf-8')
        except FileNotFoundError:
            text = 'AI 접속 및 사용 기록이 이곳에 표시됩니다.\n\n'
        except OSError as exc:
            text = f'[기존 기록 읽기 실패] {exc}\n\n'
        self.append(self.access_log_view, text)

    def access_log(self, event, detail):
        """Write a timestamped, local-only AI activity record."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        entry = f'[{timestamp}] [{event}] {detail}\n'
        self.append(self.access_log_view, entry)
        try:
            DATA.mkdir(exist_ok=True)
            with self.access_log_path.open('a', encoding='utf-8') as output:
                output.write(entry)
        except OSError as exc:
            self.append(self.access_log_view, f'[기록 저장 실패] {exc}\n')

    def clear_access_log(self):
        if not messagebox.askyesno('접속 LOG 지우기', '저장된 AI 접속 및 사용 기록을 모두 지울까요?', parent=self):
            return
        try:
            DATA.mkdir(exist_ok=True)
            self.access_log_path.write_text('', encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('기록 지우기 실패', str(exc), parent=self)
            return
        self.access_log_view.configure(state='normal')
        self.access_log_view.delete('1.0', 'end')
        self.access_log_view.configure(state='disabled')
        self.access_log('LOG', '사용자가 기록을 지웠습니다.')

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
        if self.install_terminal_active:
            self.show_install_tab()
            return 'break'
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
        if self.install_terminal_active:
            self.stop_terminal_install()
            return
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
            self.access_log('AI 오류', text)
            self.append(self.transcript, '\n[응답 실패] ' + text + '\n')
            self.send_button.configure(state='normal')
        if not quiet:
            messagebox.showerror('작업 안내', text, parent=self)

    def open_ollama_folder(self, kind):
        try:
            if kind == 'install':
                executable = find_ollama()
                if not executable:
                    messagebox.showinfo('설치 폴더', 'Ollama 설치 위치를 찾지 못했습니다. 먼저 설치하거나 PATH를 확인하세요.', parent=self)
                    return
                folder = Path(executable).resolve().parent
            else:
                folder = models_directory()
            if not folder.is_dir():
                messagebox.showinfo('폴더 없음', f'아직 폴더가 없거나 접근할 수 없습니다.\n{folder}\n\n모델 다운로드 전이라면 먼저 모델을 설치하세요.\n사용자 지정 위치는 OLLAMA_MODELS 설정 후 앱을 다시 실행하세요.', parent=self)
                return
            if os.name == 'nt':
                os.startfile(str(folder))
            else:
                webbrowser.open(folder.as_uri())
            self.log(f'폴더 열기: {folder}')
        except OSError as exc:
            messagebox.showerror('폴더 열기 실패', str(exc), parent=self)

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
            self.access_log('접속', f'Ollama 서버 연결 · version={version} · 127.0.0.1:11434')
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
            self.access_log('접속 종료', 'Ollama 서버 응답 없음 · 127.0.0.1:11434')
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
            # The server only listens on loopback. OLLAMA_ORIGINS controls which
            # browser Origins may call the API (CORS); default is '*'.
            origins = self.cors_origins.get().strip() or DEFAULT_CORS_ORIGINS
            env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11434', OLLAMA_ORIGINS=origins)
            with (DATA / 'server.log').open('ab') as output:
                offset = output.tell()
                self.process = subprocess.Popen([exe, 'serve'], env=env, stdout=output,
                                                stderr=output, creationflags=NO_WINDOW)
            self.emit(self.console_write, f'> ollama serve\n[CORS] OLLAMA_ORIGINS={origins}\n')
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

    def open_download_folder(self):
        try:
            self.installer_path.parent.mkdir(parents=True, exist_ok=True)
            os.startfile(str(self.installer_path.parent))
        except OSError as exc:
            messagebox.showerror('다운로드 폴더 열기', str(exc), parent=self)

    def stop_installer_download(self):
        self.installer_cancel.set()
        if self.chat_server is not None:
            self.chat_server.shutdown()
            self.chat_server.server_close()
            self.chat_server = None
        self.stop_download_button.configure(state='disabled')
        self.download_status.set('다운로드 중지 중… 네트워크 응답 대기 시 약 10초 걸릴 수 있습니다.')

    def installer_finished(self):
        self.stop_download_button.configure(state='disabled')
        self.install_button.configure(state='normal')

    def launch_installer(self, installer, launched):
        # The main UI thread orders a stop click against installer launch.
        try:
            if not self.installer_cancel.is_set() and not self.closed:
                self.stop_download_button.configure(state='disabled')
                self.download_status.set('다운로드 완료 · 설치 마법사에서 설치를 완료하세요.')
                launched.append(subprocess.Popen([str(installer)]))
        except Exception as exc:
            launched.append(exc)

    def install(self):
        if 'console' in self.busy:
            messagebox.showinfo('명령 실행 중', '콘솔 명령을 먼저 중지하세요.')
            return
        if os.name != 'nt':
            webbrowser.open('https://ollama.com/download')
            return
        if 'installer' in self.busy:
            return
        if not messagebox.askyesno('Ollama 설치', f'공식 Windows 설치 파일을 다운로드하고 실행합니다.\n\n저장 위치: {self.installer_path}\n\n다운로드 중에는 중지할 수 있습니다.\n설치 마법사 실행 후에는 마법사에서 취소하세요. 계속할까요?', parent=self):
            return
        self.installer_cancel.clear()
        self.install_button.configure(state='disabled')
        self.stop_download_button.configure(state='normal')
        self.download_status.set('설치 파일 다운로드 연결 중…')
        def work():
            installer = self.installer_path
            try:
                last_update = 0
                def progress(count, total):
                    nonlocal last_update
                    now = time.monotonic()
                    if now - last_update >= 0.2 or count == total:
                        last_update = now
                        text = f'설치 파일 다운로드: {count / 1048576:.1f} MB' + (f' / {total / 1048576:.1f} MB' if total else '')
                        self.emit(lambda: None if self.installer_cancel.is_set() else self.download_status.set(text))
                download_installer(installer, self.installer_cancel, progress)
                if self.installer_cancel.is_set():
                    raise DownloadCancelled()
                self.emit(self.download_status.set, '다운로드 완료 · 디지털 서명 확인 중…')
                path = str(installer).replace("'", "''")
                script = "$s=Get-AuthenticodeSignature -LiteralPath '" + path + "'; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'Ollama') { exit 1 }"
                verified = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                                          creationflags=NO_WINDOW, timeout=60)
                if verified.returncode:
                    raise RuntimeError('공식 Ollama 디지털 서명을 검증하지 못해 실행을 중단했습니다.')
                if self.installer_cancel.is_set():
                    raise DownloadCancelled()
                launched = []
                ready = threading.Event()
                def launch():
                    try:
                        self.launch_installer(installer, launched)
                    finally:
                        ready.set()
                self.emit(launch)
                while not ready.wait(0.1):
                    if self.closed:
                        raise DownloadCancelled()
                if not launched:
                    raise DownloadCancelled()
                if isinstance(launched[0], Exception):
                    raise launched[0]
                result = launched[0].wait()
                if result != 0:
                    raise RuntimeError(f'설치가 취소되었거나 실패했습니다 (코드 {result}).')
                if not find_ollama():
                    raise RuntimeError('설치 경로를 확인하지 못했습니다. 사용자 지정 설치라면 PATH에 Ollama를 추가하세요.')
                self.emit(self.download_status.set, 'Ollama 설치 완료')
                return 'Ollama 설치를 확인했습니다.'
            except DownloadCancelled:
                self.emit(self.download_status.set, '다운로드 중지됨 · 임시 파일 삭제 완료')
                return 'Ollama 설치 파일 다운로드를 중지했습니다.'
            except Exception:
                self.emit(self.download_status.set, '설치 작업 실패 · 다시 시도할 수 있습니다.')
                raise
            finally:
                self.emit(self.installer_finished)
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

    def selected_catalog_result(self):
        selection = self.results.selection()
        if not selection:
            messagebox.showinfo('모델 선택', '검색 결과에서 모델을 먼저 선택하세요.')
            return None
        return self.results.item(selection[0], 'values')

    def open_model_site(self, name=None):
        if name is None:
            result = self.selected_catalog_result()
            if not result:
                return
            name = result[0]
        webbrowser.open('https://ollama.com/library/' + quote(name, safe='/:'))

    def show_model_details(self, _=None):
        result = self.selected_catalog_result()
        if not result:
            return
        name, description = result
        window = tk.Toplevel(self)
        window.title(name + ' · 전체 설명')
        window.geometry('780x540')
        window.minsize(520, 360)
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=name, font=('맑은 고딕', 16, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='검색 결과의 전체 설명입니다. 상세 문서는 공식 사이트에서 확인하세요.').pack(anchor='w', pady=8)
        body = ScrolledText(frame, wrap='word', font=('맑은 고딕', 11), padx=12, pady=12)
        body.pack(fill='both', expand=True)
        body.insert('1.0', description or '설명이 없습니다.')
        body.configure(state='disabled')
        current = self.target.get()
        target = tk.StringVar(window, value=current if current.split(':')[0] == name else name + ':latest')
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(12, 0))
        ttk.Label(row, text='모델:태그').pack(side='left', padx=(0, 6))
        ttk.Entry(row, textvariable=target).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='콘솔에서 pull', command=lambda: self.pull_in_console(target.get())).pack(side='left', padx=6)
        ttk.Button(row, text='공식 사이트', command=lambda: self.open_model_site(name)).pack(side='left')

    def pull_in_console(self, name=None):
        # Never send a new pull command to the stdin of an existing process.
        if self.install_terminal_active or {'console', 'pull', 'chat', 'server', 'installer'} & self.busy:
            messagebox.showinfo('작업 진행 중', '진행 중인 작업을 종료한 뒤 콘솔 pull을 실행하세요.')
            return
        try:
            name = model_name(self.target.get() if name is None else name)
        except ValueError as exc:
            messagebox.showerror('모델 이름', str(exc))
            return
        self.notebook.select(self.console_tab)
        self.command.set('ollama pull ' + shlex.quote(name))
        self.console_execute()
        self.command_entry.focus_set()

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

    @property
    def settings_path(self):
        return DATA / 'settings.json'

    def load_settings(self):
        try:
            data = json.loads(self.settings_path.read_text('utf-8'))
        except (OSError, ValueError):
            return
        if isinstance(data.get('model'), str):
            self.selected.set(data['model'])
        origins = data.get('cors_origins', DEFAULT_CORS_ORIGINS)
        if isinstance(origins, str) and origins.strip():
            self.cors_origins.set(origins.strip())

    def save_settings(self, _=None, *, note_cors=False):
        DATA.mkdir(exist_ok=True)
        origins = self.cors_origins.get().strip() or DEFAULT_CORS_ORIGINS
        self.cors_origins.set(origins)
        payload = {'model': self.selected.get(), 'cors_origins': origins}
        try:
            self.settings_path.write_text(json.dumps(payload, ensure_ascii=False), 'utf-8')
        except OSError as exc:
            self.log('설정 저장 실패: ' + str(exc))
            return
        if note_cors:
            self.log(f'CORS 설정 저장: OLLAMA_ORIGINS={origins}')

    def reset_cors_origins(self):
        self.cors_origins.set(DEFAULT_CORS_ORIGINS)
        self.save_settings(note_cors=True)

    def select_model(self, _=None):
        self.save_settings()
        if self.selected.get():
            self.access_log('모델 선택', self.selected.get())
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
        started = time.monotonic()
        self.access_log('AI 요청', f'model={model} · messages={len(messages)}\n질문: {text}')
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
            answer = history[-1].get('content', '') if history else ''
            elapsed = time.monotonic() - started
            self.access_log('AI 응답', f'model={model} · {elapsed:.2f}초 · {len(answer)}자\n답변: {answer}')
        self.job('chat', work, done)
        return 'break'

    def close(self):
        active = self.busy - {'refresh'}
        if active and not messagebox.askyesno('작업 진행 중', '진행 중인 작업의 연결이 끊어집니다. 앱을 닫을까요?\nOllama 서버와 실행 중인 설치 마법사는 유지됩니다.'):
            return
        self.cancel.set()
        self.installer_cancel.set()
        try:
            self.console_runner.stop()
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            messagebox.showerror('작업 중지 실패', str(exc), parent=self)
            return
        self.closed = True
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
