"""Real Tk widgets with a fake Ollama transport; no downloads or server changes."""
import time
from unittest.mock import patch
from app import App
from installer_download import DownloadCancelled


def get(path, timeout=4):
    return {'version': 'test'} if path.endswith('version') else {'models': [{'name': 'test:1b'}]}


def stream(path, data, cancel=None):
    if path == '/api/pull':
        yield {'status': 'pulling', 'total': 100, 'completed': 50}
        yield {'status': 'success'}
    else:
        yield {'message': {'content': '테스트 응답'}, 'done': False}
        yield {'message': {'content': ''}, 'done': True}


with patch('app.Client.get', side_effect=get), patch('app.Client.stream', side_effect=stream), \
     patch('app.search_models', return_value=[('test', 'Test model')]), \
     patch('app.fetch_tags', return_value=['1b']), patch('app.App.select_model'):
    app = App()
    from tkinter import ttk
    style = ttk.Style(app)
    assert app.cget('background') == '#111827'
    assert style.lookup('TCombobox', 'fieldbackground', ('readonly',)) == '#1f2937'
    assert style.lookup('Treeview', 'background', ('selected',)) == '#2563eb'
    for text_widget in (app.transcript, app.prompt, app.log_view):
        assert text_widget.cget('background') == '#101827'
        assert text_widget.cget('insertbackground') == '#e5e7eb'
    with patch('app.Path.write_text') as save_theme:
        app.toggle_theme()
        assert app.ui_theme == 'light'
        for terminal in (app.console_view, app.install_terminal_view):
            assert terminal.cget('background') == '#000000'
            assert terminal.cget('foreground') == '#e5e7eb'
        assert app.resource_panel.canvas.cget('background') == '#101827'
        assert app.prompt.cget('background') == '#ffffff'
        assert style.lookup('TCombobox', 'fieldbackground', ('readonly',)) == '#ffffff'
        assert '"theme": "light"' in save_theme.call_args.args[0]
        app.toggle_theme()
        assert app.ui_theme == 'dark'
        assert app.console_view.cget('background') == '#000000'
        assert app.resource_panel.canvas.cget('background') == '#101827'
        assert app.prompt.cget('background') == '#101827'
    def settle():
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            app.update()
            if not app.busy and app.events.empty():
                return
            time.sleep(0.02)
        raise AssertionError('UI job timed out')
    settle()
    def buttons(widget):
        for child in widget.winfo_children():
            if child.winfo_class() == 'TButton':
                yield child.cget('text')
            yield from buttons(child)
    assert '서버 재시작' in list(buttons(app))
    assert 'Open WebUI 설치' in list(buttons(app))
    def fake_webui_install(root, notify):
        notify('테스트 설치 출력')
    with patch('app.open_webui_executable') as webui_exe, patch('app.install_open_webui', side_effect=fake_webui_install):
        webui_exe.return_value.is_file.return_value = False
        app.install_webui()
        settle()
        assert app.notebook.select() == str(app.install_tab)
        assert '설치 완료' in app.webui_install_status.get()
        assert '테스트 설치 출력' in app.install_terminal_view.get('1.0', 'end')
    app.resource_panel.update_sample({'connected': 100, 'gpu': 40, 'cpu': 25, 'ram': 50, 'ram_detail': '8 / 16 GB'})
    app.resource_panel.update_sample({'connected': 0, 'gpu': None, 'cpu': 30, 'ram': 55})
    app.update()
    labels = [app.resource_panel.canvas.itemcget(item, 'text') for item in app.resource_panel.canvas.find_all()
              if app.resource_panel.canvas.type(item) == 'text']
    assert any('연결 안 됨' in text for text in labels)
    assert any('CPU  30.0%' in text for text in labels)
    assert any('측정 대기 / 불가' in text for text in labels)
    assert app.online
    assert app.server_light.itemcget(app.server_light_dot, 'fill') == '#16a34a'
    app.refreshed((None, []))
    assert app.server_light.itemcget(app.server_light_dot, 'fill') == '#94a3b8'
    app.refreshed(('test', [{'name': 'test:1b'}]))
    assert app.server_light.itemcget(app.server_light_dot, 'fill') == '#16a34a'
    app.search()
    settle()
    app.results.selection_set(app.results.get_children()[0])
    app.update()
    settle()
    app.tags.set('1b')
    app.pick_tag()
    assert app.target.get() == 'test:1b'
    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText
    description = '긴 모델 설명 / 크기 / 정보 ' * 200
    app.results.item(app.results.selection()[0], values=('test', description))
    app.show_model_details()
    app.update()
    detail = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)
    body = next(w for w in descendants(detail) if isinstance(w, ScrolledText))
    assert body.get('1.0', 'end-1c') == description
    assert body.cget('wrap') == 'word'
    with patch('app.webbrowser.open') as opener:
        app.open_model_site()
        opener.assert_called_once_with('https://ollama.com/library/test')
    def pull_command(args, output):
        assert args == ['fake-ollama', 'pull', 'test:1b']
        output('pulling manifest\nsuccess\n')
        return 0
    with patch('app.find_ollama', return_value='fake-ollama'), patch('app.ConsoleRunner.run', side_effect=pull_command):
        app.pull_in_console()
        settle()
    assert app.notebook.select() == str(app.console_tab)
    assert 'pulling manifest' in app.console_view.get('1.0', 'end')
    detail.destroy()
    app.pull()
    settle()
    assert app.progress['value'] == 100
    app.prompt.insert('1.0', '안녕하세요')
    app.send()
    settle()
    assert app.history[-1]['content'] == '테스트 응답'
    assert '테스트 응답' in app.transcript.get('1.0', 'end')
    app.clear_chat()
    assert not app.history
    app.notebook.select(app.console_tab)
    def console_run(args, output):
        assert args == ['fake-ollama', 'list']
        output('NAME SIZE\ntest:1b 100 MB\n')
        return 0
    with patch('app.find_ollama', return_value='fake-ollama'), patch('app.ConsoleRunner.run', side_effect=console_run):
        app.command.set('ollama list')
        app.command_entry.event_generate('<Return>')
        # Explicit focus is not guaranteed on unattended desktops.
        if app.command.get():
            app.console_execute()
        settle()
    assert 'test:1b 100 MB' in app.console_view.get('1.0', 'end')
    app.console_history(-1)
    assert app.command.get() == 'ollama list'
    app.command.set('powershell whoami')
    app.console_execute()
    assert '지원 명령' in app.console_view.get('1.0', 'end')
    app.console_clear()
    assert not app.console_view.get('1.0', 'end').strip()
    assert app.winfo_width() >= 840
    with patch('app.download_installer') as download:
        app.install_nav_button.invoke()
        app.update()
        assert app.notebook.select() == str(app.install_tab)
        download.assert_not_called()
    def cancelled_download(path, cancel, progress):
        progress(1024, 2048)
        if not cancel.wait(3):
            raise AssertionError('Stop button did not cancel download')
        raise DownloadCancelled()
    with patch('app.messagebox.askyesno', return_value=True), \
         patch('app.download_installer', side_effect=cancelled_download), \
         patch('app.subprocess.Popen') as installer_launch:
        for _ in range(2):
            app.install_button.invoke()
            assert str(app.install_button['state']) == 'disabled'
            assert str(app.stop_download_button['state']) == 'normal'
            app.stop_download_button.invoke()
            settle()
            assert '다운로드 중지됨' in app.download_status.get()
            assert str(app.stop_download_button['state']) == 'disabled'
            assert str(app.install_button['state']) == 'normal'
        installer_launch.assert_not_called()
    with patch('app.messagebox.askyesno', return_value=True), \
         patch('app.InstallTerminalRunner.run', side_effect=lambda args, output: (output('SCRIPT TEST OUTPUT\n'), 0)[1]):
        app.script_buttons['Windows'].invoke()
        settle()
        assert 'SCRIPT TEST OUTPUT' in app.install_terminal_view.get('1.0', 'end')
        assert '스크립트 실행 완료' in app.install_terminal_view.get('1.0', 'end')
        assert not app.install_terminal_active
        assert str(app.script_buttons['Linux']['state']) == 'disabled'
        assert str(app.script_buttons['Darwin']['state']) == 'disabled'
    app.geometry('840x650')
    app.update()
    assert app.install_input.winfo_ismapped(), 'Install input must remain accessible at minimum size'
    assert app.install_terminal_view.winfo_height() >= 50, 'Terminal must remain usable at minimum size'
    app.close()
print('PASS: Tk window, search, pull, chat, console, install tab navigation, download stop/retry, embedded install output (mock transport)')
